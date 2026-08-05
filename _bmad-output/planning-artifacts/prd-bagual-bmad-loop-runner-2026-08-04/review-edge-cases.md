# Edge-Case Review — `prd-bagual-bmad-loop-runner-2026-08-04`

> Method-driven pass: for each behaviour-bearing requirement, enumerate its states/transitions and
> report only the ones the PRD does not say what to do about. Cases the PRD already handles are
> excluded. Style issues are out of scope for this lens.

## 1. Run lifecycle

- **Two runs started by accident on the same epic.** FR13 turns on worktree isolation and FR11 gates
  on a `PASS` verdict, but nothing says what happens if the owner (or two supervising windows)
  invokes `bmad-loop run` twice against the same spec folder/epic. `[scm] max_parallel = 1` bounds
  concurrency *within* a run, not across two independently-started runs on the same epic. Two runs
  could create two worktrees/branches against the same target branch and collide at merge-back — the
  exact "concurrent writer, silent collision" failure the PRD (§7.3, FR13's own rationale) treats as
  the motivating danger for `isolation="none"`, now recreated one level up. No dedup/lock/refusal is
  specified for this level.
- **Supervising window is closed mid-run.** FR14 makes the skill "resident but idle... in its own
  dedicated window" for the run's duration. `bmad-loop`'s actual dev/review sessions run under a
  separate tmux-backed mechanism (per `.bmad-loop/policy.toml [mux]` and the hook model in
  `research/02`), so the run plausibly continues even if this window is closed — but the PRD never
  states that independence, nor what the owner should do when they reopen a window: does the skill
  reattach to the in-flight run and resume "resident but idle" supervision, or does invoking it fresh
  start a second, uncoordinated supervisor (colliding with the case above)?
- **Supervising window survives but `bmad-loop` (the orchestrator process) dies.** FR14 says the
  skill "observes through `bmad-loop`'s own surfaces (`status`, the run directory, the ATTENTION
  file)". If the orchestrator process itself has died, those surfaces go stale rather than
  disappearing — there is no stated way for the resident-but-idle skill to distinguish "nothing is
  happening because the run is healthy and quiet" from "nothing is happening because the orchestrator
  crashed and will never post another event." No staleness/heartbeat check is specified for the wake
  mechanism.
- **Machine sleeps or reboots overnight.** Not mentioned anywhere in the run-lifecycle or NFR
  sections. A run that was mid-story when the host slept/rebooted has no stated recovery path (resume
  automatically on next boot? require an explicit `bmad-loop resolve`-style re-entry? surface as a
  named failure at the next manager cycle per FR16's "stalls... are reported, not absorbed"?). Given
  the PRD's own framing — "the owner is asleep... escalations, stalls and irreversible risks need
  defined disposal, not a paused terminal nobody reads" (§5) — a host sleep/reboot is arguably the
  single most likely unattended-overnight event and it has no disposal.
- **Run crashes (not a stall, not a CRITICAL escalation — e.g. the orchestrator process itself
  segfaults/OOMs).** FR15 covers `CRITICAL` escalations (by-design pause) and FR16 covers stalls and
  budget trips. A hard crash of the orchestrator is a third category with no stated disposal — is it
  detected at all by the resident skill, or does it look identical to "run finished silently" absent
  a terminal marker?

## 2. Planning gate

- **Gate passes, then the epic document itself changes (not a story).** FR11 gates on the verdict
  being `PASS`; FR12 only names *story* staleness ("If execution changes the terrain... a fast
  re-run of the gate verifies the adjustment"). An edit to the epic document after `PASS` — the
  artifact FR9 says the gate must audit alongside the stories — has no stated staleness trigger.
- **Gate passes, then a story is hand-edited without going through the "adjust → re-run" flow FR12
  describes.** FR12 describes the intended workflow ("whoever adjusts a story spec... a fast re-run
  of the gate verifies the adjustment") but does not require it — it reads as a convention, not an
  enforced check. No mechanism (hash, mtime, content digest recorded at `PASS` time) is specified for
  the runner to detect that a story file changed *since* the recorded `PASS` and refuse to start (or
  force a re-gate) the way FR11 refuses on an outright missing `PASS`. This is the direct sibling of
  Story 22.1's root cause (§1) recreated at the story layer instead of the schema layer.
- **A story is added to `stories.yaml` after the gate already returned `PASS` for the epic.** FR12
  only discusses *adjusting* an existing story. A net-new story appended post-gate is a different
  transition — does the epic-level `PASS` verdict silently cover it (nothing re-audits it), or is it
  blocked? Not stated either way.
- **The gate itself fails or crashes partway** (script error, interrupted session, corrupted output)
  rather than completing and returning an explicit non-`PASS` verdict. FR11's "refusal is explicit
  and names the blocking gap" describes the disposal for a *completed* audit that found a gap. It is
  not stated whether a partial/errored gate run is (a) indistinguishable from "gate never run" and
  safely defaults to no-run, or (b) could leave a stale/ambiguous artifact that a later check
  misreads as a real verdict.

## 3. Epic closure

- **Some stories `done`, some `failed`.** FR21 states partial closure is "a named, reported state,
  never silent," which covers *that a report happens*, but not the disposal of the failed stories
  themselves: are they auto-converted to tickets, left for the owner to manually re-drive, retried by
  the closure flow, or does the epic simply sit blocked indefinitely? FR17 (deferred-work triage)
  covers *review-finding* debt inside `deferred-work.md`, not stories that ended in a terminal
  `failed` state — a different object with no stated handling.
- **`bmad-loop sweep` (FR17) surfaces something during closure that needs an owner decision, and the
  owner is asleep.** FR15 defines exactly this disposal for a `CRITICAL` escalation *during the run*
  ("pauses... records it, surfaces it... for the next interactive session, never invents an answer").
  FR17 does not reference that mechanism, or any disposal, for the equivalent situation arising during
  *closure* triage — closure is described as a checklist (FR17–FR21) with no stated pause/escalate
  path if a triage item can't be safely resolved unattended.
- **The retrospective (FR19) produces knowledge that contradicts existing wiki content (FR20).**
  Neither FR mentions conflict detection or resolution at write time; see also §6 below — this is the
  same gap surfacing at the specific moment closure writes new knowledge next to old.
- **Closure runs twice** (owner re-invokes it on an epic already `done`, or two manager windows both
  attempt closure on the same finished run). FR21 says an epic "reaches `done` only after the closure
  checklist passes" but does not say closure is idempotent or guarded against re-entry — a second run
  could re-trigger the QA gate, re-run the retrospective, and re-append knowledge/duplicate wiki
  entries with nothing described to detect "this epic is already closed."

## 4. Configuration and init

- **Init ran against an older version of the skill; the skill was later updated and now ships new
  base-default config keys the project's existing `.bagual/` predates.** FR1 triggers init when
  config is "absent or incomplete," but "incomplete" is not defined against a versioned schema —
  there is no stated mechanism (schema version stamp, key-diff check) for the skill to detect that a
  *new* key was added upstream after this project's `.bagual/` was written, so FR1's own guarantee
  ("init never guesses a value it could ask for") has no described trigger to re-fire for that one new
  key. This is the concrete form of the prompt's "config key added after this project was configured"
  case, and it is also "init ran against an older version" from the other direction.
- **Two manager windows both hit init at the same time** (both detect absent/incomplete `.bagual/`
  simultaneously and both start interactive init). FR26/FR42 explicitly design for multiple concurrent
  `bagual-manager` windows and FR42 explicitly reasons through the concurrent-write race for the
  ticket index — but no equivalent statement exists for a concurrent *write* to `.bagual/` itself
  during two simultaneous inits. FR4's merge algorithm describes how layered config is *resolved* on
  read, not how two processes writing the same file at once are reconciled.
- **Config references an MCP server that is not installed** is close to covered by the NFR "Graceful
  absence" bullet ("a missing MCP server... degrades to a reported skip, never a crash and never a
  silent pass") — but that NFR is written for the case where the *stage itself* is absent (FR5's
  motivating case). It does not say how the skill detects the gap between "config declares this MCP
  available" and "the MCP is not actually reachable at runtime" (a drift case, not an intentional
  absence) — worth a note even though the NFR partially covers the outcome.

## 5. Concurrency

- **Two windows create a ticket describing the same problem at the same time.** §2.2 states intake
  checks a new ticket "against similar existing tickets" before creation, and FR42's whole rationale
  is built around removing lock contention on a shared index. But the dedup check itself is a
  time-of-check-to-time-of-use race: if both windows run the "check for similar tickets" step before
  either has written its new ticket file, both checks see the same (not-yet-updated) set of files, both
  pass, and both create duplicate tickets. FR42 argues convincingly why the *index* is race-free; it
  does not address that the *semantic* dedup guarantee it leans on can still race.
- **One window closes a ticket another window is mid-edit on.** FR42's per-file, no-lock design means
  two windows writing the same ticket file (one a `close`, one an in-progress edit) is a last-write-
  wins interleave with no stated conflict detection (no version/etag check mentioned) — the PRD
  states why there's no lock on the *index*, but says nothing about concurrent writers to the same
  *ticket file*, which the no-lock rationale doesn't actually rule out as a risk.
- **The derived listing is computed while a ticket file is half-written.** FR42 says "the listing is
  derived on read by scanning them" — this is only race-free if every ticket-file write is atomic
  (temp-file + rename, per FR40's script convention). FR40's atomic-write requirement is scoped to
  "scripts" in the authoring-standard section (§7.8); it is never explicitly bound to `bagual-tickets`'
  own ticket-file writes, so a torn read during a scan is not ruled out by anything stated for FR42
  specifically.

## 6. Knowledge

- **A learning contradicts an earlier learning.** FR28 covers the owner correcting the manager
  directly (single-source correction, single write). It does not cover two independently-captured
  learnings — e.g. two different epics' retrospectives (FR20) — landing in the wiki in direct
  contradiction of each other, with no stated detection or reconciliation step.
- **A wiki entry marked `verified` becomes false over time** (the code it describes changes after the
  human confirmed it). FR25a introduces the `verified`/`inferred` trust field but only guards against
  *inference laundered into fact at write time* ("An unconfirmed claim is stored visibly as inference
  and never laundered into fact"). It does not describe any re-verification trigger, expiry, or
  staleness check for an entry that *was* correctly verified once and has since drifted — which is
  precisely the "stale document confidently followed off a cliff" failure mode the same requirement's
  own rationale warns about, just applied to the trusted case rather than the inferred one.
- **The pruning test (FR25a) would delete something a spec currently cites.** FR23 says the grounding
  slice is "written into the spec itself with each source path" and FR25a requires curation passes
  that shrink the wiki. Nothing cross-checks a candidate-for-pruning entry against specs (in-flight or
  otherwise) that already embedded a citation to it before deleting it — a curation pass could orphan
  an already-embedded grounding reference mid-epic with no stated reconciliation.

---

*Reviewed against sections 6–11 of the PRD plus `.bmad-loop/policy.toml` and
`research/02-bmad-infrastructure.md` for mechanism context. No code-level artifacts existed at review
time (pre-implementation PRD), so all findings are gaps in stated behaviour, not implementation bugs.*
