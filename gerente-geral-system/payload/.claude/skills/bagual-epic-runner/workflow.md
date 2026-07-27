# Epic Pipeline Workflow

**Goal:** Supervise the execution of a SET of one or more epics (Story E10.1, PRD 03
FR-1). Build an Execution Graph — Tracks of epics, declared paralela vs sequencial per
pair — **before** running any story, then run the Tracks: in series when the graph
computed exactly 1 Track (the common case today), or CONCURRENTLY — one background
Agent per Track, each anchored to its own pool-allocated worktree — when the graph
computed 2 or more (Story E11.4, PRD 03 FR-5c cwd anchoring + FR-6 parallel isolation).
For each Track, its own epics still run in series, through the unchanged create-story →
dev-story → code-review → retrospective pipeline — whether that Track is
running inline (1-Track case) or inside its own worktree (2+-Track case). When 2+
Tracks ran (Step 0P), each successful one's worktree is left un-merged/un-returned
(Story E11.4's own boundary) — Story E11.5 (PRD 03 FR-7) closes that loop with Step
0P.5: the SUPERVISOR itself, on `{project-root}` (never inside a worktree), merges
each successful Track back into `staging` ONE AT A TIME (serialized), reapplies that
Track's own sprint-status.yaml/board.yaml status changes as a scoped delta (never a
blind file merge — that is what makes 3 parallel Tracks produce ZERO conflict on those
files), renumbers any colliding migration timestamps, then runs ONE post-merge
integrated gate (build of the merged set) before declaring the run
successful — a gate failure reverts only the most-recently-merged Track's contribution
and marks that Track `blocked`, leaving the other, healthy Tracks' merges intact.

> **Framing (F14, honest rewrite):** this file is a rewrite of the orchestration
> layer, not an adaptation. The pre-E10.1 version was a linear single-epic agent that
> ran the story-processor inline, with ~15 global HALTs and a hard-coded
> `<critical>Never parallelize</critical>` decree. This version is a supervisor: it
> parses a SET of epics, resolves each one's paths, builds+persists an Execution Graph
> before touching a single story, then dispatches Tracks (Story E10.3: the graph is now
> the REAL disjunction of declared areas — see `scripts/compute_execution_graph.py` —
> so it can genuinely emit multiple parallel-eligible Tracks). Through Story E10.5,
> Track *iteration* was still series, always, regardless of how many Tracks the graph
> emitted. Story E11.4 changes exactly that: when the graph emits 2+ Tracks, Step 0P
> (below) dispatches them as concurrent background Agents, each rooted (via strict
> absolute-path discipline — see Step 0P's F15 critical block for why, not the
> `EnterWorktree` primitive the PRD originally assumed) at its own pool-allocated
> worktree (`bagual-worktree`, Story E11.1-E11.3). The 1-Track case (still the common
> one — most epics lack a populated `epic_areas:` declaration and fail-safe to a single
> Track) keeps running through Step 0 exactly as E10.5 left it, byte-for-byte, no
> worktree, zero added cost. The **miolo** (`story-processor.md`, Steps 0–F) is
> untouched — it is invoked exactly as before, once per epic,
> whether from inside Step 0's inline loop or from inside a Step 0P Track-Agent's own
> execution of workflow.md's Steps 1-5 rooted at its worktree. Story E11.5 (PRD 03
> FR-7) adds exactly one more link, Step 0P.5, which runs AFTER Step 0P's Track-Agents
> have all reported, on `{project-root}` itself (never inside a worktree, never inside
> a Track-Agent). `story-processor.md` stays untouched by E11.5 too — the PREFERRED
> path of the two the story's Ficha de Build offered (see
> `ideias/sistema-artifacts/E11-5-merge-automatico.md` § "story-processor path"): the
> shared-file conflict a Track's in-worktree writes would otherwise cause at merge time
> is handled entirely at the supervisor/merge layer (`.gitattributes` `merge=union` for
> the append-only knowledge/Ledger/history files + a scoped delta-reapply script for
> sprint-status.yaml/board.yaml), never by changing what `story-processor.md` writes or
> where.

**Your Role:** Thin supervisor. You parse the requested epic set, resolve each epic's
paths (including the E-prefixed meta-system routing override), build and persist the
Execution Graph, then dispatch each Track — in series (Step 0, 1-Track case) or as
concurrent background Agents anchored to pool-allocated worktrees (Step 0P, 2+-Track
case) — and for each epic within a Track, in series — build the story queue, spawn one
isolated Agent per story, verify completion, and
run the retrospective.
- You do NOT implement code, run sub-skills, or manage story state yourself
- You DO read sprint-status.yaml to build the queue and verify results after each story
- You DO spawn one isolated Agent per story using story-processor.md
- You DO build and persist the Execution Graph before the first story of any epic in
  the set runs — this is the FR-1 requirement made literal
- Communicate all responses in {communication_language}

---

## RULES

- The Execution Graph decides Track membership; **within** a Track, epics run ONE AT A
  TIME, in order, and **within** an epic, stories run ONE AT A TIME, in order. As of
  Story E10.3 the graph is a REAL disjunction computation (`scripts/
  compute_execution_graph.py`) — it CAN emit more than one Track when the epics in
  `{epic_set}` declare genuinely disjoint areas (including no shared-touchpoint
  overlap). **Story E11.4:** how the Tracks THEMSELVES are dispatched now depends on
  how many the graph emitted — 1 Track still runs inline through Step 0 (unchanged
  since E10.5, byte-for-byte); 2+ Tracks run CONCURRENTLY through Step 0P, one
  background Agent per Track, each anchored to its own pool-allocated worktree. This
  is a property of the graph's own Track count, decided once, right after the graph is
  built — never a mode flag the invoker sets. **Within** each Track, its own epics
  still run strictly in series (Step 0's inner loop, or a Track-Agent executing that
  same inner loop from inside Step 0P) — E11.4 only parallelizes ACROSS Tracks, never
  within one.
- Each story MUST run in its own Agent subagent (story-processor.md) for full context
  isolation. Do not process stories inline. This holds identically inside Step 0
  (inline) and inside a Step 0P Track-Agent (which spawns its own story-processor
  sub-agents, anchored at its worktree, exactly as Step 0 does at `{project-root}`).
- **Three distinct HALT kinds exist in this chassis (Story E10.5, extended by E11.4's
  parallel dimension) — never conflate them:**
  1. **Cycle-HALT (Story E10.4, stays GLOBAL).** A `depends_on` cycle detected while
     *building* the graph, before any story runs, is a planning error, not a runtime
     failure — it HALTs the entire supervisor invocation (see the Graph-build step
     below). This is unchanged by E10.5/E11.4.
  2. **Per-story HALT WITHIN a Track (preserved).** If any epic's Steps 1–5 fail or
     HALT (a story HALTs inside story-processor.md, or the retrospective fails), **that
     epic's Track stops** — no further
     epic in `{track.epics}` after the failing one runs, exactly as if the whole
     pipeline had HALTed for that Track. This is the same failure-stops-progress
     guarantee the pre-E10.5 chassis had, just now scoped to the Track instead of the
     whole run — and, since E11.4, evaluated identically whether the Track is running
     inline (Step 0) or inside a Track-Agent (Step 0P).
  3. **Track-scoped isolation (Story E10.5, extended by E11.4 to the PARALLEL
     dimension — replaces the old global HALT).** A Track that stops per (2) above
     does **not** abort the supervisor run: it is marked `blocked` (with an explicit
     reason) in the persisted `execution_graph`, a `bagual-tickets` Ticket is left in
     an explicit blocked state, and a Briefing entry is recorded — then, in Step 0,
     **the outer loop continues to the next Track**; in Step 0P, **every other
     Track-Agent keeps running/reporting independently** (FR-6, parallel isolation — a
     Track-Agent never even learns a sibling failed). Healthy sibling Tracks
     (already-done ones, and ones still queued/running) are completely unaffected. See
     Step 0's per-epic check (serial) and Step 0P's per-Track-Agent-result check
     (parallel) for the full mechanics — both reuse the SAME Ticket/Briefing
     bookkeeping procedure, never two copies of it.
- Never modify sprint-status.yaml's per-story (`{epic}-{n}-*`) entries yourself —
  story-processor agents handle all story-level writes. The supervisor itself DOES
  write two things that were already outside that boundary: the epic-completion status
  at Step 5 (unchanged from before E10.1) and, new in E10.1, the top-level
  `execution_graph:` block (Path Resolution / Graph step below) — both are additive,
  non-story-level writes.
- **Modelo por papel (Story E6.5, PRD 03 FR-12):** this Orchestrator (workflow.md +
  story-processor.md) runs on the model it was invoked with (typically Opus —
  decides/composes). Every executor sub-agent it spawns (`bmad-create-story`,
  `bmad-dev-story`, `bmad-quick-dev`, `bmad-code-review`) is spawned with the Agent
  tool's `model` param set explicitly to `sonnet` — never inheriting the parent's
  model by omission. Each spawn point across `story-processor.md` and this file
  carries that directive inline in its own `<action>`. Spawns of `bmad-retrospective`
  stay outside FR-12's literal scope (which names only
  create-story/dev-story/quick-dev/code-review) and continue inheriting the parent's
  model.

---

## INVARIANTS (Story E10.2 — hardening, no behavior change)

> Full proof (byte-diff, dry-traces) lives in
> `ideias/sistema-artifacts/E10-2-preservar-miolo.md`. This block is the pointer any
> future editor of this file should read BEFORE changing anything below — if a change
> would break one of these bullets, it is out of this file's scope (it belongs to a
> different, explicitly-named story) and must not be made here.

- **`story-processor.md` (Steps 0, A–F) is byte-identical.** It is never edited by this
  file or by anything this file spawns. Verify with
  `git diff --stat <any-pre-E10.1-commit> -- .claude/skills/bagual-epic-runner/story-processor.md`
  — must be empty.

## INVARIANTS (Story E10.5 — Track-scoped failure isolation, closes Epic E10)

- **Only the RUNTIME-failure HALT (Steps 1–5 of a single epic) is Track-scoped.** The
  cycle-HALT (E10.4, a planning error caught while *building* the graph, before any
  story runs) stays GLOBAL — a cycle anywhere in `{epic_set}` HALTs the entire
  invocation, exactly as E10.4 left it. E10.5 never touches the Graph-build step's HALT
  checks.
- **The per-story HALT inside a Track is preserved, not removed.** A story that HALTs
  (story-processor.md returns failure) still stops all further progress in that epic's
  Track — no epic queued after the failing one in `{track.epics}` runs. E10.5 changes
  what happens *after* that point (the Track is marked `blocked` and the run continues
  to other Tracks) — it does not weaken the story-level HALT itself.
- **A blocked Track/epic is never silently dropped or marked `done`.** It always leaves
  three pieces of explicit, reconcilable state: (1) `execution_graph.tracks[].status` /
  `.epic_status{}` = `"blocked"` in `{sprint_status}` (never left `"in-progress"` — that
  would look like an orphaned run to E9.5's orphan-sweep / E8.2's crash-recovery); (2) a
  `bagual-tickets` Ticket with `escalonar: true` + a `## Log` entry describing the
  reason (found via the same `origem: TCK-*` lookup story-processor.md Step F.5 already
  uses, or created fresh if none exists — see Step 0 below); (3) a Briefing entry in
  `project_controll/gerente/briefing-{YYYYMMDD}.md`. All three writes are best-effort/
  non-blocking (same F.5 contract) — a failure to write the Ticket or Briefing is logged
  as a WARNING and never escalates back into a global HALT.
- **The final summary is "K of N done; {blocked list} — reason", never a total
  "pipeline halted".** See the end of Step 0 below.

## INVARIANTS (Story E11.4 — F15 cwd anchoring + real parallel Track dispatch)

> Full probe transcripts (2 failed anchoring attempts + the working mechanism, proven
> with 3 real concurrent background Agents) live in
> `ideias/sistema-artifacts/E11-4-ancoragem-paralelismo.md`. Read this block before
> changing Step 0P or the dispatcher check above it.

- **The PRD's literal "background Agent whose cwd root IS the worktree" primitive was
  tested against this harness and does NOT work for a pre-existing, externally-created
  (pool-managed) worktree — confirmed adversarially, not assumed.** Two real attempts
  both failed: (1) a plain background Agent calling `EnterWorktree(path={dest})` from
  a session whose cwd is the repo root — refused outright ("switching is only
  available to sessions whose working directory is inside a worktree of this
  repository"); (2) a background Agent launched with `isolation: worktree` (which DOES
  pin a cwd at launch) then calling `EnterWorktree(path={dest})` to redirect from its
  own auto-created throwaway worktree to the target pool worktree — reports success but
  leaves the session split-brained (the tracked cwd label updates, but Bash/Write
  enforcement still only permits the originally-pinned directory; every subsequent
  command against `{dest}` is refused). Neither is used by Step 0P.
- **The mechanism Step 0P actually wires — proven, zero leakage — is strict
  absolute-path discipline, not session-level cwd rooting.** Every Track-Agent is
  spawned WITHOUT `isolation`. Its prompt is an absolute, non-negotiable rule: never
  rely on a `cd` persisting across separate Bash tool calls (confirmed: each new Bash
  invocation resets to the session's default cwd — this is a general harness property,
  not specific to worktrees), and never use a bare relative path in ANY tool call.
  Every Bash command touching the worktree is self-contained in one invocation
  (`git -C {dest} ...`, or `cd {dest} && ...` chained in the SAME call); every
  Read/Write/Edit call uses the full absolute path rooted at `{dest}`. This IS the
  literal realization of the AC's "todo prompt de Track paralelo usa paths absolutos"
  — proven with 3 real concurrent background Agents (2 succeeding, 1 simulating
  failure) each confined to its own worktree, `git -C {project-root} status`
  (the root `staging` checkout) staying clean for the entire duration, and zero
  cross-Track marker contamination (see the story file's Dev Notes for the exact
  transcripts).
- **Only Tracks (2+) trigger Step 0P; a 1-Track graph is dormant, zero-cost.** Most
  epics today still lack a populated `epic_areas:` declaration and fail-safe to a
  single `sequencial` Track (E10.3) — that overwhelmingly common case runs through
  Step 0 exactly as E10.5 left it, no worktree ever allocated, no behavior change from
  before E11.4. Step 0P only activates when `compute_execution_graph.py` itself
  computed 2+ genuinely disjoint Tracks for a given `{sprint_status_group}`.
- **A Track-Agent NEVER calls `pool_manager.py return` itself, on success OR failure.**
  On success, `return` would `git reset --hard` the Track's own branch — destroying the
  very commits that still need to be merged into `staging`; that merge (and the
  `return` that follows it) is E11.5's job, not E11.4's. On failure, the AC requires
  the failed Track to "stop in its worktree" — leaving it allocated/un-returned is the
  literal mechanism, not an oversight. Both cases leave the worktree `em-uso` in the
  pool registry until a later process (E11.5 for success, manual/future-story triage
  for failure) reconciles it.
- **Process/knowledge-file writes made by `story-processor.md` while running inside a
  Track-Agent's worktree are NOT reconciled into `staging` by this story.** A
  successful Track's `sprint-status.yaml`/knowledge-file/Ticket/`projects-history.md`
  writes live inside `{dest}`'s own branch until merged — serializing them into
  `staging` one merge at a time is explicitly E11.5's scope (FR-7), not built here.
  Step 0P's own bookkeeping (marking `{track.epic_status[...]}` = `"done"`/`"blocked"`)
  writes ONLY to the supervisor's own `{sprint_status}` under `{project-root}` — it
  never touches the worktree's copy.
- **Parallelism degree is realized by calling `allocate` once per Track, immediately,
  never a throttled queue.** `pool_manager.py allocate` already implements the
  "(3) prewarmed pool → (2) copy-on-demand" fallback internally (E11.1/FR-5b); calling
  it for every Track in the dispatch list, with no gating, means the first
  `min(pool worktrees currently livre, number of parallel Tracks)` get a zero-extra-cost
  prewarmed worktree and the rest pay on-demand hydration cost inline — still
  concurrent, just slower to start. This literally satisfies "grau de paralelismo =
  min(pool, epics paralelas); excedente sob demanda". The AC's alternative ("...ou
  aguarda" — a Track blocking/queueing instead of paying on-demand cost) is the
  untaken option, documented as deferred, not built (see the story's Dev Notes,
  Self-review item on this).
- **The final summary shape is identical whether Step 0 or Step 0P ran** ("K of N
  done; {blocked list} — reason") — Step 0P feeds the same `{done_epics}`/
  `{blocked_tracks}` accumulators Step 0 already defines, never a second reporting
  format. **Extended by Story E11.5:** a Track's `"done"` mark made here (upon its
  Track-Agent's SUCCESS report) is now PROVISIONAL until Step 0P.5 finishes — see the
  E11.5 INVARIANTS block below for what happens if the post-merge gate demotes it back
  to `"blocked"`.

## INVARIANTS (Story E11.5 — merge-back, serialized shared-file writes, post-merge gate; PRD 03 FR-7)

> Full mechanism proof (3 real concurrent throwaway Tracks, zero conflict; a real
> migration-timestamp collision renumbered deterministically; a simulated post-merge
> gate failure reverted cleanly without disturbing healthy Tracks) lives in
> `ideias/sistema-artifacts/E11-5-merge-automatico.md`. Read this block — and that
> file's Dev Notes — before changing Step 0P.5 or `scripts/merge_manager.py`.

- **`story-processor.md` stays byte-identical (the PREFERRED path this story's Ficha
  de Build offered, not the minimal-edit fallback).** A Track's own copy of the shared
  process/knowledge files (the 4 knowledge files, `projects-history.md`,
  `sprint-status.yaml`, `board.yaml`) is written EXACTLY as `story-processor.md`
  already writes it today, inside `{track.dest}`'s own branch — E11.5 never asks
  `story-processor.md` to emit a "payload instead of a write" or to detect that it is
  running inside a parallel Track. The conflict those N-worktree writes would
  otherwise cause at merge time is resolved entirely AFTER the fact, by the
  SUPERVISOR, in Step 0P.5 below — never by changing what or where
  `story-processor.md` writes.
- **Two disjoint classes of shared file, two disjoint resolutions — never the same
  mechanism for both:**
  1. **UNION-SAFE (append-only) files** — the 4 knowledge files, `projects-history.md`,
     and Ledger entries under `wiki/ledger/**/*.md` — carry `merge=union`
     in the repo's `.gitattributes` (new file, Story E11.5). This is a git BUILT-IN
     merge strategy (gitattributes(5)) — no custom driver, no `.git/config` entry.
     `git merge` resolves these natively at merge time; Step 0P.5 does not special-case
     them. **Adversarial finding from this story's own testing:** `.gitattributes`
     ONLY takes effect if it is present (committed) in the worktree/branch actually
     being merged FROM and the branch being merged INTO — a `.gitattributes` that
     exists only as an untracked file in one checkout does nothing. It must be
     committed to `staging` (this repo: done as part of this story's own commit) so
     every future Track branch (which forks from `staging`) inherits it automatically.
  2. **DELTA-REAPPLY files** — `sprint-status.yaml` (both the product and meta-system
     paths) and `board.yaml` — are NEVER merged at the file level, `merge=union`
     included (a `status:` field is a value two Tracks could each want different,
     which union would silently interleave into corrupt/ambiguous YAML). Step 0P.5
     force-resets them to the pre-merge (staging) blob via `merge_manager.py
     merge-track`, then calls `merge_manager.py reapply-status-delta` to copy over
     ONLY the specific field(s) — by default `status:` — for ONLY that Track's own
     keys (its `epic-{N}` / `epic-{N}-retrospective` / `{N}-{M}-*` story keys in
     `sprint-status.yaml`; its `TCK-*` keys in `board.yaml`), scoped and
     structure-preserving, never a blind file merge. **Adversarial finding, fixed
     before this story closed:** the first implementation used `git checkout --ours --
     <path>` to force the pre-merge content back — this is a NO-OP for a path git
     auto-merged WITHOUT a conflict (only one side touched it), because `--ours`/
     `--theirs` only resolve paths that actually have multiple index stages. The fix
     (now in `merge_manager.py`) checks out the path's blob from the recorded
     `{pre_merge_sha}` by commit, not by stage — reliable regardless of whether git
     saw a conflict on that path or not. Verified with a real test where this bug
     silently let a Track's raw file through; after the fix, three real parallel
     Tracks each flipped ONLY their own key, with zero cross-Track leakage.
  3. **Any OTHER conflicted path** (real product code) means the FR-3 disjunction
     computation missed a real overlap — `merge_manager.py merge-track` refuses to
     guess a resolution: it aborts the merge (`git merge --abort`) and reports the
     unexpected path(s). **Superseded by Story E11.6:** "any other conflicted path" no
     longer aborts immediately — `merge-track` first tries the ONE additional
     conservative safe class (import-reorder-only conflicts, all-or-nothing across
     every conflicted path in the merge); only if that also fails does it abort exactly
     as described here. It still, in both cases, realizes this story's own slice of
     FR-8 ("the owner never sees a `<<<<<<<` marker as a task"): an unresolved merge is
     never left half-done or committed with markers in it. See the "INVARIANTS (Story
     E11.6)" block below for the full ladder.
- **Merges are serialized, one Track at a time, in the deterministic order
  `{parallel_tracks}` was built in (Step 0P's own group-then-Track order — the
  "topológica" default the Ficha de Build calls for; not completion order, which is
  non-deterministic across real background Agents).** Step 0P.5 never merges two
  Tracks concurrently — it is a plain sequential loop over the SUCCESSFUL entries
  already collected by Step 0P (Tracks that reported FAILURE were already handled by
  Step 0P's own bookkeeping and are skipped here entirely — their worktree stays
  allocated/un-returned, untouched by Step 0P.5).
- **Migrations are renumbered ONCE PER TRACK, immediately after that Track's own merge
  + delta-reapply — never batched at the very end across all Tracks.** This keeps each
  Track's contribution to `staging`'s history fully self-contained (its merge commit +
  its delta-reapply commit + its own migration-renumber commit, if any, all landing
  before the NEXT Track's merge begins) — which is exactly what makes "revert the
  LAST Track's contribution" (the gate-fail case below) a clean, boundeded revert
  instead of one that risks unpicking an earlier, healthy Track's migration rename.
  `merge_manager.py renumber-migrations` is deterministic: colliding timestamp
  prefixes are resolved by keeping the alphabetically-first filename at its original
  timestamp and bumping every other one by +1 second (repeating until free) —
  verified against a real collision in this story's own test (two Tracks independently
  adding a migration with the identical `20990101000001` prefix; the second was
  renamed to `...000002`, no data lost, no manual step).
- **The post-merge integrated gate runs exactly ONCE, after every successful Track in
  `{parallel_tracks}` has been merged + delta-reapplied + migration-renumbered — never
  once per Track.** A Track's per-worktree build passing ≠ the merged set building
  (PRD 03 FR-7) — a Track's OWN build (inside its Track-Agent) already validated it in
  isolation; this gate validates the INTEGRATION of all of them together on `staging`.
- **Gate failure triggers root-cause BISECTION (Story E16.6), never a blind "revert
  only the last Track".** Superseded by Story E16.6 — see the "INVARIANTS (Story
  E16.6)" block below for the full algorithm (`merge_manager.py`'s `revert-track` +
  re-run `{run_gate}` + `git reset --hard` to discard a failed trial, tried in reverse
  merge order, bounded by `{merged_tracks length}`, HALT if none resolves). This
  block's original E11.5 text asked literally for "revert do último merge" and shipped
  exactly that (a documented residual: bisection to an EARLIER Track was explicitly
  NOT built here) — E16.6 closes that residual. The properties that DID hold under the
  original single-revert behavior still hold under bisection, generalized: `git revert`
  (never `git reset --hard`) is used for the FINAL, KEPT resolution — auditable, safe
  even if `staging` has already been fetched/pulled by something else, consistent with
  this project's git-safety discipline (see AGENTS.md); the blamed Track's
  `{track.status}`/`{track.epic_status[...]}` (marked `"done"` provisionally by Step
  0P's own bookkeeping) is set back to `"blocked"`, via the SAME Ticket/Briefing
  bookkeeping Step 0's per-epic HALT-check already defines (never duplicated); every
  OTHER already-merged, healthy Track is left exactly as it was — FR-6/E10.5's
  Track-scoped isolation applied to the post-merge phase, not a new mechanism. `git
  reset --hard` IS now used, but only for DISCARDING a bisection TRIAL that turned out
  not to be the culprit (a scratch probe this very step created moments earlier, reset
  back to a SHA it itself just recorded) — never for the final, kept resolution, and
  never for a real, already-integrated Track's work; see the E16.6 INVARIANTS block for
  the real adversarial git-conflict finding that specifically required this distinction.
- **A Track-Agent's own worktree is only `return`ed by Step 0P.5 AFTER its merge (and,
  if it was the one reverted, its revert) is fully resolved** — `pool_manager.py
  return --base-branch staging` is called once per successfully-and-durably-merged
  Track at the very end of Step 0P.5, never by the Track-Agent itself (E11.4's own
  boundary, unchanged) and never before the post-merge gate has run (a `return` before
  the gate would `git reset --hard` a worktree whose commits might still need
  inspecting if the gate fails and the merge needs a closer look before the NEXT
  invocation).

## INVARIANTS (Story E11.6 — residual-conflict ladder + SM-2=0 mechanical guardrail; PRD 03 FR-8)

> Full mechanism proof (a real safe-class import-reorder conflict auto-resolved clean;
> a real non-safe conflict aborted with zero marker ever committed anywhere in the
> scratch branch's history; a real "one resolvable + one non-resolvable file in the
> SAME merge" case aborting the WHOLE merge, not a partial one; the `assert-clean`
> guardrail exercised as a positive control) lives in
> `ideias/sistema-artifacts/E11-6-conflito-residual.md`. Read this block — and
> `scripts/merge_manager.py`'s own header comment — before changing the ladder or the
> guardrail.

- **Exactly TWO safe classes exist, total — this story adds ONE of them, not a general
  auto-resolution framework.** (1) **Union-safe (append-only) files** — unchanged from
  E11.5, resolved by git ITSELF via `.gitattributes`' `merge=union` before `git merge`
  even returns control to `merge_manager.py`; this story does not touch that mechanism.
  (2) **Import-reorder** — the ONE new conservative class this story adds, resolved
  INSIDE `merge_manager.py merge-track` itself (not a separate workflow.md step): a
  conflicted path qualifies ONLY if its file extension is one of `.py`/`.ts`/`.tsx`/
  `.js`/`.jsx`/`.mjs` AND every non-blank line on BOTH sides of EVERY conflict hunk in
  that file matches that extension's import-statement pattern. **All-or-nothing across
  the WHOLE merge, never per-file:** if even ONE unexpectedly-conflicted path in a
  given merge does not qualify (wrong extension, a hunk mixing real code into the same
  hunk as imports, a malformed/nested marker structure), `merge-track` resolves NOTHING
  and aborts the entire merge exactly as before this story — never a partial
  auto-resolution sitting next to an aborted one. Proven with a real test: a merge
  touching both an import-only-conflicted file AND a real-code-conflicted file
  together aborted BOTH, including the file that would have qualified on its own. This
  is the literal reading of "outra classe → bloqueio, não chute".
- **The ladder runs BEFORE `merge-track` ever commits, never after, and it is entirely
  internal to the script.** Step 0P.5's own control flow (the loop below, the `status
  == "conflict"` check) is UNCHANGED in shape — `merge-track`'s JSON now carries an
  extra `auto_resolved_paths` field (empty list when the ladder never triggered,
  non-empty when it resolved a conflict that would otherwise have been reported as
  `"conflict"`) on its `"merged"` result, and its commit message notes which path(s)
  were auto-resolved, for audit. Step 0P.5 logs this field when non-empty (see the
  per-Track loop below) — purely for audit, it does not change which of the two
  branches (success/conflict) is taken.
- **SM-2=0 (owner never sees a `<<<<<<<` marker) is enforced MECHANICALLY, twice, not
  just by control-flow discipline:** (1) `merge-track` itself runs a raw TEXTUAL scan
  (`git grep`, independent of git's own `--diff-filter=U` index bookkeeping used
  everywhere else in this file) across every tracked file in the working tree
  immediately before its own commit — any marker found there aborts the merge instead
  of committing, regardless of source (a bug in the ladder above, an unexpected
  union-driver leftover, anything else). (2) Step 0P.5 additionally calls the SAME scan
  as its own standalone step, `merge_manager.py assert-clean --project-root
  {project-root}`, immediately after EVERY `merge-track` invocation in its loop
  (success or conflict) — a SECOND, independently-invoked checkpoint. In correct
  operation this second call is redundant with (1) and always reports `"clean"`
  (verified with a real positive control: a marker manually injected into a tracked
  file was correctly detected with its exact file:line occurrence, then cleared before
  the check was re-run clean); it exists as a tripwire for the case where
  `merge-track`'s own internal guarantee somehow failed. **If `assert-clean` EVER
  reports `"conflict_markers_found"`, this is not a Track-scoped failure** — treat it
  as a full pipeline HALT (not the usual Ticket+Briefing+continue-siblings pattern) and
  surface the exact file:line occurrences, because a marker having reached this point
  means `staging` itself may already be compromised and no further merge in this
  batch (or write to `staging`) should proceed until a human inspects it.
- **`story-processor.md` stays byte-identical — unchanged invariant, reaffirmed, not
  re-tested by this story** (E10.2/E10.5/E11.4/E11.5 already established and verified
  this repeatedly; E11.6 touches only `merge_manager.py` and this file).
- **The non-resolvable path (ladder failed or was never applicable) is UNCHANGED from
  E11.5, not rebuilt:** `merge-track` still aborts (`git merge --abort`) before
  returning `"conflict"`, Step 0P.5 still reuses Step 0's Track-blocked bookkeeping
  VERBATIM (Ticket + Briefing + `"blocked"` in `{sprint_status}`), `staging` still
  returns to exactly its pre-merge state for that Track (proven: HEAD unchanged, zero
  `MERGE_HEAD`, zero marker anywhere in the working tree, immediately after a real
  aborted merge), and every OTHER Track in `{tracks_to_merge}` still continues
  untouched (FR-6 — proven with a real sibling Track merging cleanly right after a
  preceding Track's abort, on the SAME integration checkout). This story's job was
  narrowly to (a) give the ladder ONE more chance before that abort, conservatively,
  and (b) add the textual guardrail on top — not to change what happens once the
  ladder gives up.

## INVARIANTS (Story E16.6 — post-merge gate root-cause bisection + Track-Agent periodic heartbeat; T3.7 + T3.9)

> Full test proof (real git repos, real `revert`/`reset --hard`, all 3 AC scenarios —
> culprit-is-last base case, culprit-is-first bisection, no-individual-revert-resolves
> HALT — plus a genuine git-conflict-during-a-trial HALT) lives in
> `.claude/skills/bagual-epic-runner/scripts/tests/test_merge_manager.py` and
> `ideias/sistema-artifacts/E16-6-robustez-merge-paralelo.md`. Read this block (and
> `merge_manager.py`'s own module docstring / the `bisect_revert()` docstring) before
> changing the bisection loop in Step 0P.5 above.

- **Closes the documented E11.5 residual verbatim: "gate-failure root-cause bisection
  to an EARLIER Track remains a documented, un-built residual."** Before this story,
  ANY gate failure blamed `{last_merged_track}` unconditionally, even when the real
  cause was an earlier Track. Now: reverse-merge-order trial-and-error, ONE Track
  reverted at a time, `{run_gate}` re-run after each trial, bounded by
  `{merged_tracks length}`.
- **The tested reference algorithm is `merge_manager.py::bisect_revert()` — Step 0P.5's
  prose loop mirrors it, but cannot literally CALL it**, because the gate itself is an
  Agent (build+pyright+pytest) — a pure Python function
  cannot spawn an LLM Agent. `bisect_revert()` takes a `gate_fn: Callable[[], bool]`
  injected by its CALLER (a test's fake gate, in the test suite); Step 0P.5's own loop
  is the REAL caller, substituting a real Agent-spawn for `gate_fn()`. Both share the
  exact same control flow: try newest-to-oldest, one candidate at a time, stop on the
  first PASS, discard-and-continue on FAIL, HALT if none resolves.
- **Adversarial finding that shaped the discard mechanism — read before "simplifying"
  it back to a second `revert-commit`:** the first draft discarded a failed trial by
  reverting the trial's OWN revert commits (`restore_track_commits` — still available
  as a general-purpose CLI primitive, `restore-track`, but NOT used internally by
  `bisect_revert()`/this step's loop). Reproduced with a REAL git repo: 3 Tracks each
  appending ONE line to the SAME small shared file (the actual shape
  `sprint-status.yaml`/`board.yaml` delta commits take) — after trying-and-restoring
  the newest Track via a 2nd revert-commit pair, reverting an OLDER Track's own delta
  commit next hit a genuine `CONFLICT (content)` purely from insufficient context lines
  around the hunk (git's 3-way merge gets confused when unrelated revert/reapply
  commit PAIRS on the same tiny file sit in between, even though every underlying diff
  is a pure single-line append with zero semantic overlap). **Fix, used by both
  `bisect_revert()` and Step 0P.5's loop:** a failed trial is discarded via `git reset
  --hard` to the SHA recorded immediately before that trial started — never a 2nd
  revert. This is explicitly NOT the dangerous class of `git reset --hard` the
  "INVARIANTS (Story E11.5)" block warns against (discarding real, already-integrated
  Track work): it discards only a SCRATCH probe this very loop created a moment
  earlier, to a SHA it itself just recorded — the same "reset to a known SHA" primitive
  `pool_registry.py::cleanup_worktree()` already uses elsewhere in this codebase for
  disposable state. The FINAL, KEPT resolution (the actually-blamed Track) is still a
  real `git revert` (via `revert-track`), auditable, never discarded.
- **A git-level failure DURING a trial's own `revert-track` call (as opposed to a gate
  failure) is a DIFFERENT, more severe condition than "this candidate isn't the
  culprit" — it means bisection cannot even MECHANICALLY test that candidate in
  isolation.** Step 0P.5 (and `bisect_revert()`) treat this as an immediate
  pipeline-level HALT (same severity as the SM-2 guardrail above), never a silent skip
  to the next candidate and never a fallback to a cruder resolution — PRD 03 FR-8's
  "never guess a resolution" discipline extended from merge-conflicts to
  gate-failure-bisection.
- **Bounded, never revert-tudo:** at most `{merged_tracks length}` trials — one per
  Track, and if NONE individually makes `{run_gate}` pass, every trial has already been
  discarded (nothing left reverted, `staging` byte-identical to before bisection
  started) and the WHOLE invocation HALTs with an explicit reason, never a fallback to
  reverting every Track as a guess.
- **Part (b) — Track-Agent periodic heartbeat (T3.9) — see the Track-Agent prompt
  template above (Step 0P), HEARTBEAT section.** Before this story, a Track-Agent only
  touched its lease's heartbeat at the END of each epic it completed (E11.4's own
  documented residual: "heartbeat do Track-Agent só toca a lease 'ao final de cada
  epic'... uma única story MUITO longa... poderia, em teoria, ser confundida com
  órfã"). This story adds a DETACHED background heartbeat loop
  (`.claude/skills/bagual-worktree/scripts/heartbeat_daemon.py`), started via the
  Bash tool's `run_in_background: true` (a real, separate OS process — never inline in
  the Track-Agent's own foreground tool-call sequence), ticking on the SAME
  `heartbeat_interval_minutes` config key E11.2 already defines
  (`bagual_worktree.pool.lease.*` — schema UNCHANGED, only the FREQUENCY of touches
  changes). Non-blocking by construction: because it is a separate OS process, it can
  never serialize behind (or be serialized by) whatever Steps 1-5 work the Track-Agent
  is doing in its own foreground turn — proven with a real detached `subprocess.Popen`
  ticking concurrently while the "foreground" continues unblocked (see
  `test_heartbeat_daemon.py`). The daemon stops gracefully the moment a STOP FILE the
  Track-Agent creates (via its own Write tool, once ALL its epics are done — success or
  failure, the SAME "at the end" moment the pre-existing end-of-epic heartbeat call
  already fires at) appears — polling a plain file, never relying on being killed by a
  signal (this harness's background-process lifecycle does not guarantee that). The
  pre-existing end-of-epic heartbeat call is UNCHANGED (kept as harmless
  defense-in-depth — a Track finishing right on an interval boundary still gets an
  extra, cheap touch).

---

## INVARIANTS (Story E13.3 — sensitive path floor precedes fast_mode, per story; PRD 04 FR-9)

> `semgrep/scripts/sensitive_path_floor.py` (E7.6) existed, tested, callable — but
> nothing invoked it automatically; E7.6's own Dev Notes flagged this explicitly as
> "next natural step, not implemented in that story" (`ideias/sistema-artifacts/
> E7-6-ordem-portoes-piso.md` § "Fora de escopo"). This story closes that gap: the
> hook lives in Step 2 above (see the "Story E13.3" block inside the per-story
> `<action>`), not as a separate step, because it must run mid-story (between
> story-processor's Step B and Step C), never once per epic — see below for why.

- **The floor is evaluated PER STORY, not once per epic.** `sensitive_path_floor.py
  --diff` reads real `git diff` (unstaged ∪ staged) — at the moment an epic's Track
  begins (before its first story's Step B/dev-story ran), the working tree is clean
  (the previous story/epic already committed, E10.x/E11.x), so a check run "before
  the epic" would see nothing and always report `floor_triggered: false`, silently
  defeating the floor's purpose. The only point in the pipeline where a real,
  story-scoped diff exists is right after story-processor's Step B and before its
  Step C reads `fast_mode` — that is where Step 2 above invokes the script, once per
  story, for every story of every epic the supervisor dispatches (single-Track and
  multi-Track/worktree cases alike, since Step 2 is unchanged in shape by E11.4's
  parallel dispatch — each Track still runs its own epics' stories in series through
  this same Step 2). **Known fail-safe gap:** if a prior story in the same epic left
  uncommitted changes on disk (story-processor's Step F treats a failed `git commit`
  as non-blocking), the next story's `--diff` will also see that leftover diff — since
  the floor only ever ADDS Cerco (next bullet), the worst case is an unnecessary full
  review, never a missed one.
- **The floor can only ADD Cerco, never remove it (E7.6 AC4, reaffirmed, not
  reopened).** Step 2's `{effective_fast_mode}` starts equal to the global
  `{fast_mode}` and is only ever pulled from `true` to `false` by a `floor_triggered:
  true` result — there is no code path in this story's addition that turns a `false`
  Trilha/global decision into `true`. The global `{fast_mode}` value itself (set once
  at argument-parsing time, in "Parse the Epic Set and Mode Flag" under
  `## INITIALIZATION` below) is NEVER mutated by this block; only the
  per-story `fast_mode` input handed to that one story's inline story-processor
  execution is substituted.
- **Script absence/failure degrades NOISILY, never blocks or crashes the
  supervisor.** If `sensitive_path_floor.py` cannot run or produces unparsable
  output, Step 2 falls back to `{effective_fast_mode}` = the original `{fast_mode}`
  (today's pre-E13.3 behavior, unchanged) and emits a visible `[Floor] AVISO:`
  output — this is a soft-degrade by design (E7.6's script itself is a
  classification, not a gate; it always exits 0), not a HALT condition. A HALTed
  pipeline over a missing floor script would be a worse failure mode than silently
  falling back to the Trilha's own (still valid, just unconfirmed-by-the-floor)
  classification.
- **`story-processor.md` stays byte-identical — unchanged invariant, reaffirmed, not
  re-tested by this story** (E10.2/E10.5/E11.4/E11.5/E11.6 already established and
  verified this repeatedly). `story-processor.md`'s Step C still reads whatever
  `fast_mode` value it receives as an input exactly as before E13.3 — it has no idea
  a floor check ran; the substitution happens entirely in `workflow.md`, one layer
  up, in the value it hands down.
- **`.github/skills/bagual-epic-runner/workflow.md` is intentionally NOT touched by
  this story.** That mirror has been stale since commit `2d416366` (the bagual-*
  rename) — it never received any of the E10.1→E11.7 rewrites (no `{epic_set}`, no
  Tracks, no `epic_areas:`, no Step 0P/0P.5). It DOES still carry a per-story
  `fast_mode` input line in its own single-epic story loop (same shape this story is
  patching here), so the floor hook is not conceptually inapplicable to it — but its
  `story_processor` path already points at `{project-root}/.claude/skills/
  bagual-epic-runner/references/story-processor.md`, a `references/` subdirectory
  that does not exist in this repo (the real file is
  `.claude/skills/bagual-epic-runner/story-processor.md`, no `references/`
  component) — that mirror was already broken/unusable as a standalone runbook
  before this story, independent of anything E13.3 touches. Patching only this
  story's narrow addition into an already-broken, structurally-divergent copy would
  misrepresent it as "kept in sync" while leaving its pre-existing breakage
  unaddressed; the gap is tracked as its own deferred item
  (`_bmad-output/implementation-artifacts/deferred-work.md` § "Duas cópias de
  skill... sem tooling de sincronização", LOW, out of scope for a point migration)
  and is unchanged by this story — neither closed nor widened.

---

## INITIALIZATION

### Configuration Loading

Load config from `{project-root}/_bmad/bmm/config.yaml` and resolve:
- `project_name`, `user_name`
- `communication_language`, `document_output_language`
- `implementation_artifacts` (this is the **config-default** path — used verbatim for
  product epics; E-prefixed meta-system epics override it per-epic below, exactly as
  the pre-E10.1 workflow did for its single epic)
- `date` as system-generated current date

### Paths

- `story_processor` = `{project-root}/.claude/skills/bagual-epic-runner/story-processor.md`
  — used by Step 2 below, unchanged from before E10.1.

### Parse the Epic Set and Mode Flag

Parse the user-provided epic identifiers and mode flag from the invocation arguments.

- Split the raw argument string on whitespace and commas into tokens.
- **Mode flag:** if any token case-insensitively matches "fast" or "no-review", set
  `{fast_mode}` = true and remove that token from the list. Otherwise `{fast_mode}` =
  false (default: full, code review enabled). This flag is global to the whole
  invocation — every epic in the set runs in the same mode.
  - Output: "Mode: {fast_mode == false ? 'full (with review loop)' : 'fast (no review)'}"
- The remaining tokens are epic identifiers, in the order given. A token is either
  purely numeric (e.g. `"2"`, `"38"` — a product epic) or `E`-prefixed (e.g. `"E10"` —
  a meta-system epic).
- **If zero epic-identifier tokens remain** (no arguments, or only a mode flag):
  - Read the FULL default `{sprint_status}` = `{implementation_artifacts}/sprint-status.yaml`
    (the config-default path — auto-select only ever considers product epics, same as
    the pre-E10.1 workflow; meta-system epics are never auto-selected)
  - Find the first epic key (pattern: `epic-N`) whose status is NOT "done"
  - If found, set `{epic_set}` = `[that epic's number]` (a size-1 set) and output:
    "No epic number provided. Auto-selected epic {epic_num} (first not done)."
  - If none found, HALT: "All epics are done. Nothing to process."
- **Else** (one or more epic tokens given): set `{epic_set}` = the token list,
  preserving invocation order. `{epic_set}` of size 1 is exactly the single-epic
  invocation the pre-E10.1 workflow accepted — everything downstream degenerates to
  today's behavior for that case.
- Output: "Epic set ({epic_set_length}): {epic_set joined by ', '}"

### Per-Epic Path Resolution

For each `{epic_num}` in `{epic_set}`, resolve (same meta-system routing rule
introduced 2026-07-11, preserved unchanged — now applied per-epic instead of once
globally):
- **Meta-system routing override:** if `{epic_num}` starts with `E` (a meta-system
  epic like `E1`, `E10` — the autonomous memory/orchestrator system, tracked
  separately from product epics), set `{implementation_artifacts(epic_num)}` =
  `{project-root}/ideias/sistema-artifacts`. Product epics (numeric like `2`, `38`)
  keep the config-default `{implementation_artifacts}`. This keeps the meta-system's
  sprint-status, story files, and deferred findings isolated in
  `ideias/sistema-artifacts/`, never mixed into the product sprint.
- `{sprint_status(epic_num)}` = `{implementation_artifacts(epic_num)}/sprint-status.yaml`
- `{deferred_findings_file(epic_num)}` = `{implementation_artifacts(epic_num)}/epic-{epic_num}-deferred-findings.md`

These per-epic resolved values are what Steps 1–5 below use for `{implementation_artifacts}`,
`{sprint_status}`, and `{deferred_findings_file}` once the Track loop reaches that epic.

### Validate Every Epic in the Set (before building the graph or running any story)

For each `{epic_num}` in `{epic_set}`, using its resolved `{sprint_status(epic_num)}`:

<check if="epic-{epic_num} not found in {sprint_status(epic_num)}">
  <output>PIPELINE HALTED: Epic {epic_num} not found in sprint-status.yaml</output>
  <action>HALT. No graph is built, nothing runs — not even for other epics in the set.</action>
</check>

<check if="epic-{epic_num} status is 'done'">
  <output>PIPELINE HALTED: Epic {epic_num} is already marked as done. Nothing to process.</output>
  <action>HALT. No graph is built, nothing runs.</action>
</check>

> Non-regression note: for a size-1 `{epic_set}`, this reproduces byte-for-byte the two
> HALT checks that used to open old Step 1 — only the timing moved a few lines earlier
> (from "inside the per-epic loop, right before building the story queue" to "before
> the graph is built, right after parsing"). The HALT text, the HALT condition, and the
> fact that zero stories run afterward are all unchanged. Step 1 below no longer
> repeats these checks — they are not duplicated.

### Build and Persist the Execution Graph (before the first story runs)

<critical>This runs exactly once per invocation, after every epic in {epic_set} has
been validated, and BEFORE any story-processor Agent is spawned for any epic. This is
FR-1 made literal: the graph exists on disk before story 1 of any epic starts.</critical>

<action>Group {epic_set} by resolved {sprint_status(epic_num)} — in practice one group
(all product epics, or all meta-system epics); a mixed set produces one group per
distinct sprint_status file. Call each group a {sprint_status_group}, preserving the
{epic_set} order of its members.</action>

<critical>Story E10.3 (PRD 03 FR-3): the graph is computed by a stdlib script, never
guessed or hand-assembled by you. This is the "conflito zero por construção" fix (F2)
— `paralela` is trustworthy only because it comes from a partition-computer that (a)
fails safe to `sequencial` on any missing declaration, and (b) treats the fixed
shared-touchpoint set (`frontend/src/App.tsx`, `backend/api/index.py`, `package.json`/
lockfile, `pyproject.toml`, `supabase/migrations/`, and the process/knowledge files —
`sprint-status.yaml`, the 4 knowledge files, `projects-history.md`, `board.yaml`) as
part of the disjunction check, not just literal code-file overlap. Full algorithm,
declaration format, and fixture-proven test results:
`ideias/sistema-artifacts/E10-3-grafo-disjuncao.md`.</critical>

<critical>Story E10.4 (PRD 03 FR-4): the same script also layers a declared
`depends_on` dependency edge on top of the disjunction check — a dependency BEATS
disjunction, forcing two epics into the same Track (and a specific relative order)
even when their declared areas are fully disjoint. A dependency CYCLE anywhere in
{epic_set} is a planning error, never a schedule to approximate: the script HALTs
(non-zero exit, `"halt": true` in its stdout JSON, and it does NOT touch
`{sprint_status}` at all — no partial/guessed graph is ever written) instead of
producing any Track order. See the HALT check right after the invocation below. Full
algorithm, `depends_on` format, and fixture-proven test results:
`ideias/sistema-artifacts/E10-4-dependencias-ciclo.md`.</critical>

<action>For each {sprint_status_group}, invoke the script (stdlib Python, no
dependencies to install):

```
python3 {project-root}/.claude/skills/bagual-epic-runner/scripts/compute_execution_graph.py \
  --epics {the epics in this group, in {epic_set} order} \
  --sprint-status {sprint_status path for this group} \
  --write \
  --date {date}
```

This single invocation does everything: it reads that group's `epic_areas:` block
(if present — one JSON-flow-mapping line per epic key, the format Story E9.3's
planning brain / `project_controll/gerente/planning-brain.md` is expected to populate
per epic when it declares area/files/dependencies; a missing block, or a missing entry
for a specific epic, is NOT an error — every pair touching an undeclared epic fails
safe to `sequencial`), computes pairwise disjointness (a declared dependency edge OR
shared-touchpoint overlap OR code-area overlap ⇒ `sequencial`; all absent ⇒
`paralela`), groups epics into Tracks via the connected components of the
"sequencial" graph, topologically sorts each Track's epics by its `depends_on` edges
(deterministic — ties broken by `{epic_set}` invocation order), and splices the
resulting `execution_graph:` block into `{sprint_status}` in place — preserving every
other top-level key (`generated`, `last_updated`, `epic_areas`, `development_status`,
and all comments/indentation/story entries) exactly as-is. `development_status` is
never touched by this step; it remains story-processor's and Step 5's exclusive
territory per RULES. **If the script instead detects a dependency cycle, it does NOT
write anything** — see the HALT check below.

The script also prints the computed graph as JSON to stdout — read it to build the
human-readable output block below (do not re-derive the graph yourself; the script's
stdout is the source of truth for `{N}`/`{M}`/Track membership/topo order).
</action>

<check if="the script's stdout JSON contains `"halt": true` (equivalently: the script
exited non-zero) for ANY {sprint_status_group}">
  <critical>Story E10.4: a dependency cycle was detected in the requested
  {epic_set}. This is a planning error, not a recoverable condition — HALT THE ENTIRE
  SUPERVISOR RUN NOW, before Step 0 and before any story-processor Agent is spawned
  for ANY epic in ANY group (even groups whose own graph computed cleanly — the
  invocation as a whole is invalid until the cycle is fixed at the declaration
  level).</critical>
  <action>Do not retry, do not guess a fallback order, do not fall back to
  `mode: "trivial-placeholder"` or any other approximation. Report to the operator:
  the `{sprint_status_group}` whose graph halted, the full `cycles` list from the
  script's stdout JSON (each entry's `cycle_path`, e.g. `["epic-A", "epic-B",
  "epic-A"]`), and instruct that the offending epics' `depends_on` declarations in
  `epic_areas:` must be corrected before this invocation can be retried. The
  pre-existing `execution_graph:` block (if any) in `{sprint_status}` was left
  untouched by the script — do not hand-edit it to work around the HALT.</action>
</check>

<output>
============================================================
EXECUTION GRAPH BUILT AND PERSISTED
{{for each sprint_status_group: "- {sprint_status path}: {T} Track(s), {N} epic(s) [{epics joined}], {M} pair(s) [{K} paralela / {M-K} sequencial] — mode: disjunction-v1 (Story E10.3 + E10.4 dependency ordering)"}}
============================================================
</output>

---

## EXECUTION

<workflow>
  <critical>Story E11.4 (PRD 03 FR-5c cwd anchoring + FR-6 parallel dimension): how
  Tracks are dispatched depends on how many the built Execution Graph emitted — this is
  decided ONCE, right after the Graph-build step above, never a mode flag. A graph with
  exactly 1 Track (combined across every `{sprint_status_group}` — still the common
  case, since most epics lack a populated `epic_areas:` declaration and fail-safe to a
  single `sequencial` Track per E10.3) runs through Step 0 below, UNCHANGED since Story
  E10.5 — inline, in this session, no worktree, zero added cost. A graph with 2+ Tracks
  (for ANY `{sprint_status_group}`) runs those 2+ Tracks through Step 0P instead —
  CONCURRENTLY, one background Agent per Track, each anchored (via strict absolute-path
  discipline — see the INVARIANTS block above for why not `EnterWorktree`) to its own
  worktree allocated from the `bagual-worktree` pool (E11.1-E11.3). A mixed invocation
  can have some `{sprint_status_group}`s go through Step 0P and others through Step 0
  in the SAME run — each group's own Track count decides its own group independently.
  Only ONE of Step 0 / Step 0P ever runs for a given group; they are alternatives, not
  a pipeline.</critical>
  <check if="the combined `{execution_graph.tracks}` count for a given
    `{sprint_status_group}` is 2 or more">
    <action>Run STEP 0P (Parallel Dispatch) below for that group's Tracks.</action>
  </check>
  <check if="the combined `{execution_graph.tracks}` count for a given
    `{sprint_status_group}` is 1 (or the set is otherwise degenerate to a single
    Track)">
    <action>Run STEP 0 (unchanged since Story E10.5) below for that group's Track.</action>
  </check>
  <critical>Each story MUST run in its own Agent subagent (story-processor.md) for full
  context isolation. Do not process stories inline. This holds identically whether a
  story runs inline (Step 0) or inside a Step 0P Track-Agent's own execution of this
  same file's Steps 1-5, anchored at its worktree instead of `{project-root}`.</critical>
  <critical>Story E10.5 (PRD 03 FR-6, sequential dimension — closes Epic E10),
  extended by Story E11.4 to the PARALLEL dimension: if any epic's pipeline (Steps 1–5
  below) fails or HALTs, that epic's TRACK stops — no further epic queued after it in
  the same Track runs. This does NOT HALT the supervisor run: the Track is marked
  `blocked` (execution_graph + Ticket + Briefing, see Step 0's per-epic check or Step
  0P's per-Track-Agent-result check — same bookkeeping, reused, never duplicated), and
  the run CONTINUES — Step 0's outer loop moves to the next Track (serial case), or
  Step 0P's other Track-Agents simply keep running/reporting independently, never even
  learning a sibling failed (parallel case). Healthy sibling Tracks are unaffected
  either way. The only HALT that still aborts the entire supervisor run is the
  cycle-HALT (E10.4), which happens earlier, during the Graph-build step, before this
  EXECUTION block is even reached.</critical>

  <step n="0P" goal="Dispatch 2+ disjoint Tracks concurrently, each as a background Agent anchored (via absolute-path discipline) to its own pool-allocated worktree (Story E11.4 — F15 + FR-6 parallel)">
    <critical>See the "INVARIANTS (Story E11.4)" block above for the full F15
    anchoring contract (why `EnterWorktree` is NOT used here, and what IS proven to
    work) before changing anything in this step.</critical>

    <action>Reclaim any orphaned leases first, so a stale lease from a crashed prior
    run doesn't shrink the effective pool:
    `python3 {project-root}/.claude/skills/bagual-worktree/scripts/pool_manager.py
    reclaim-orphan --project-root {project-root}` (real persistent pool, default
    location — never a `--pool-dir` override; those are for throwaway test pools
    only). Log the JSON result; a failure here is a WARNING, not a HALT — `allocate`
    below still runs its own mandatory health-check regardless (E11.3, F17).</action>

    <action>Flatten every `{track}` across every `{sprint_status_group}` whose OWN
    graph computed 2+ Tracks into one combined dispatch list, `{parallel_tracks}`,
    preserving group-then-Track order (a group that itself computed only 1 Track
    contributes that Track to Step 0 instead, per the dispatcher check above — the two
    lists are disjoint by construction).</action>

    <action>For EACH `{track}` in `{parallel_tracks}`, BEFORE spawning anything,
    allocate its worktree:
    `python3 {project-root}/.claude/skills/bagual-worktree/scripts/pool_manager.py
    allocate --owner "track-{track.track_id}" --label "{track.epics joined by ','}"
    --project-root {project-root}`.
    This is a health-checked lease (E11.3) — every candidate is dep-hash-compared
    against `staging` HEAD and re-hydrated if stale, `.venv`-revalidated, and
    frontend-smoke-built before being handed back; it falls back to copy-on-demand
    hydration if the pool has no free worktree (E11.1's strategy 2). Read
    `{track.dest}` (= the JSON's `path`), `{track.lease_token}` (= `token`),
    `{track.pool_name}` (= `name`) from its output.</action>

    <check if="`allocate` fails for a `{track}` (non-zero exit / no healthy candidate
      within `health.max_allocation_attempts`)">
      <critical>This Track never gets a worktree, so it never runs — treat it EXACTLY
      like a Steps-1-5 HALT. Reuse Step 0's per-epic HALT-check bookkeeping VERBATIM
      (Ticket lookup/creation + Briefing append + `{track.status}` /
      `{track.epic_status[*]}` = `"blocked"` persistence, generalized to EVERY epic in
      this Track since none of them ran) — do not duplicate that procedure's text here,
      just its outcome. `{track_failure_reason}` = "Step 0P: could not allocate a
      healthy worktree for Track {track.track_id} ({track.epics joined}) —
      pool_manager.py allocate failed after health.max_allocation_attempts". Append to
      `{blocked_tracks}`. This Track never spawns a background Agent — move to the
      next `{track}` in `{parallel_tracks}`.</critical>
    </check>

    <action>Design note (parallelism degree, PRD 03 FR-5c/§8): the loop above calls
    `allocate` once per Track, immediately, with NO throttling/queueing — since
    `pool_manager.py allocate` already implements the "(3) prewarmed pool → (2)
    copy-on-demand" fallback internally (E11.1/FR-5b), this alone realizes "grau de
    paralelismo = min(pool livre, epics paralelas no grafo); excedente sob demanda" AS
    WRITTEN: the first `min(pool worktrees livre at the start of this step, length of
    {parallel_tracks})` get a zero-extra-cost prewarmed worktree, the rest pay
    on-demand hydration cost inline inside their own `allocate` call but still run
    concurrently. The AC's alternative ("...ou aguarda" — literally blocking/queueing a
    Track instead of paying on-demand cost) is the untaken option, deferred — see the
    story's Dev Notes.</action>

    <action>For EACH `{track}` that got a worktree above, spawn ONE background Agent
    (Agent tool, `run_in_background: true`; do NOT pass `isolation` — see the
    INVARIANTS block for why; do NOT pin `model` — this Track-Agent inherits the
    invoking session's model, the same "decides/composes" discipline this supervisor
    itself runs on, since it acts as a mini-supervisor for its own Track; it is
    DISTINCT from the `sonnet`-pinned executors it will itself spawn per E6.5/FR-12)
    with this prompt template (substitute every `{...}` literally; every path ABSOLUTE):

    "You are the Track-Agent for Track {track.track_id} (epics: {track.epics joined}),
    part of an automated, unattended epic pipeline. Auto-approve every checkpoint.
    Never ask for user input.

    ANCHORING RULE (non-negotiable for your ENTIRE session): your assigned worktree is
    the absolute path `{track.dest}` — a full parity clone of the project (every path
    `{project-root}/X` also exists at `{track.dest}/X`). NEVER write outside
    `{track.dest}` (Write/Edit tool, or any Bash command that creates/modifies/deletes
    a file). Do NOT call the EnterWorktree tool (confirmed unreliable for a
    pre-existing worktree in this harness — see the INVARIANTS block above). Do NOT
    rely on a `cd` persisting across separate Bash tool calls (each new Bash invocation
    resets to this session's default cwd). Every Bash command touching your worktree
    must be self-contained in ONE invocation: `git -C {track.dest} <cmd>`, or
    `cd {track.dest} && <cmd>` chained in that SAME call. Every Read/Write/Edit call
    must use the FULL absolute path starting with `{track.dest}/...` — never a bare
    relative path.

    YOUR JOB: read `{track.dest}/.claude/skills/bagual-epic-runner/workflow.md`'s Steps
    1 through 5 (the SAME steps this supervisor runs for a serial Track) and execute
    them YOURSELF, once per epic in [{track.epics joined}], in that exact order —
    treating `{track.dest}` as `{project-root}` for every path those steps reference
    (config, sprint_status, story_processor, the 4 knowledge files,
    deferred_findings_file — all rooted at `{track.dest}`, never at
    `{project-root}`). Every story you process still runs in its own isolated Agent
    subagent via story-processor.md, exactly as Step 2 already specifies, spawned by
    YOU (a Track-Agent nesting further sub-agents is the design: supervisor →
    Track-Agent → per-story executor). Every create-story/dev-story/quick-dev/
    code-review sub-agent you spawn stays pinned to `sonnet`, exactly as those steps
    already specify (E6.5/FR-12) — you do not change that.

    HEARTBEAT — PERIODIC (Story E16.6, T3.9), do this FIRST, before Step 1: set
    `{track.heartbeat_stop_file}` = `{track.dest}/.claude/worktrees/.heartbeat-stop-
    {track.track_id}.marker` (an ordinary file inside your OWN worktree — the
    ANCHORING RULE above still applies; a real path under `{track.dest}` satisfies it,
    and `pool_manager.py return`'s `git clean -fd` sweeps it away later, same as any
    other untracked scratch marker). Start the periodic heartbeat daemon as a
    DETACHED background process — Bash tool, `run_in_background: true` — and do NOT
    wait for it to finish (it runs for your ENTIRE Track, only exiting once the stop
    file appears):
    `python3 {track.dest}/.claude/skills/bagual-worktree/scripts/heartbeat_daemon.py
    run --project-root {project-root} --name {track.pool_name} --token
    {track.lease_token} --stop-file {track.heartbeat_stop_file}` (no `--interval-
    minutes` override — it reads the configured `bagual_worktree.pool.lease.
    heartbeat_interval_minutes`, the SAME E11.2 config key the end-of-epic heartbeat
    below already uses). This runs as a SEPARATE OS process from your own tool-call
    sequence — it can never block or serialize your Steps 1-5 work, and your Steps 1-5
    work can never block or delay it. Because it runs a real wall-clock cadence
    throughout, a single epic longer than `heartbeat_interval_minutes` (E11.4's own
    documented residual) is no longer at risk of `reclaim-orphan` mistaking you for
    crashed mid-epic.

    HEARTBEAT — END-OF-EPIC (unchanged from before this story, kept as harmless
    defense-in-depth): at the end of EACH epic you finish inside this Track (success
    or failure), ALSO run: `python3 {track.dest}/.claude/skills/bagual-worktree/
    scripts/pool_manager.py heartbeat {track.pool_name} --token {track.lease_token}
    --project-root {project-root}` (best-effort — a failed heartbeat call is a
    WARNING, never a reason to stop).

    HEARTBEAT — STOPPING THE DAEMON: the MOMENT you are done with ALL your epics
    (every SUCCESS/FAILURE report below), your VERY LAST action before reporting back
    is to create the stop file: write ANY content to
    `{track.heartbeat_stop_file}` (Write tool). This lets the background daemon exit
    gracefully within one interval — never leaving an orphaned background process
    running after your own session ends. If you forget this, the daemon is harmless
    (it just keeps touching a lease nobody is reading from anymore until the process
    is eventually reaped) but do not skip it.

    ON SUCCESS (every epic in your Track reaches Step 5 and is marked done): do NOT run
    `pool_manager.py return` — leave `{track.dest}` exactly as-is, fully allocated,
    holding every commit you made. Returning it would `git reset --hard` and DESTROY
    those commits before they can be merged — that merge (and the `return` after it) is
    a LATER story's job (E11.5), not yours. Report back: SUCCESS, the epics completed,
    and `{track.dest}`.

    ON FAILURE (any epic's Steps 1-5 HALT inside your Track, exactly as Steps 2/3/5
    of workflow.md already define): STOP immediately — no further epic in your Track,
    no cleanup, no `pool_manager.py return`. Report back: FAILURE, which epic/step
    failed and why (the exact `{epic_failure_reason}` text those steps already
    produce), and `{track.dest}` (left in place for inspection)."
    </action>

    <action>Do not poll or sleep waiting for these background Agents — each delivers
    its own completion notification when it finishes, exactly like every other
    background Agent this project already spawns.</action>

    <action>As each Track-Agent's completion notification arrives:
      <check if="it reports SUCCESS">
        <action>Set `{track.dispatch_result}` = `"success"` (a new, in-memory field on
        this `{track}` entry — not yet persisted; Step 0P.5 below reads it to decide
        what to merge). Update `{track.epic_status[epic_num]}` = `"done"` for every
        epic the Track-Agent reported complete, IN THE SUPERVISOR'S OWN
        `{sprint_status}` (under `{project-root}`, never the worktree's own copy).
        Recompute `{track.status}` = `"done"`. Append every epic in this Track to
        `{done_epics}`. **Story E11.5:** this "done" mark is PROVISIONAL — the Track's
        actual code has not been merged into `staging` yet, and Step 0P.5 below can
        still demote it back to `"blocked"` if the post-merge integrated gate fails and
        this Track's contribution is the one reverted. Do not treat this mark as final
        until Step 0P.5 (below) has run to completion.</action>
      </check>
      <check if="it reports FAILURE">
        <action>Set `{track.dispatch_result}` = `"failure"`.</action>
        <critical>Reuse Step 0's Track-blocked bookkeeping VERBATIM (Ticket
        lookup/creation + Briefing append + `{track.status}`/`{track.epic_status[*]}`
        = `"blocked"` persistence) — the only differences from Step 0's own trigger:
        (1) the trigger is this Track-Agent's failure report, not an inline HALT; (2)
        `{track_failure_reason}` is built from the Track-Agent's reported
        epic/step/reason; (3) note explicitly in the Ticket/Briefing text that
        `{track.dest}` is left allocated and un-returned (the Track-Agent already did
        not call `return`) so a human knows where to look. Append to
        `{blocked_tracks}`.</critical>
      </check>
      <action>Do NOT abort or wait on any OTHER Track-Agent because one failed — every
      other `{parallel_tracks}` entry keeps running/reporting independently (FR-6,
      parallel isolation — the literal AC "3 paralelas + falha de uma → as outras 2
      completam").</action>
    </action>

    <output>
      ============================================================
      PARALLEL DISPATCH COMPLETE (Step 0P): {parallel_tracks length} Track(s) run
      concurrently, each anchored to its own pool-allocated worktree.
      {{for each track: "  - Track {track.track_id} ({track.epics joined}): {done|blocked} (provisional) — {track.dest}"}}
      Proceeding to Step 0P.5 (merge-back) for every Track marked "done" above.
      ============================================================
    </output>

    <action>Once every Track-Agent in `{parallel_tracks}` has reported (this step's own
    bookkeeping loop waits for all of them — it does not serialize their EXECUTION,
    only this loop's own completion): build `{tracks_to_merge}` = the subset of
    `{parallel_tracks}` with `{track.dispatch_result}` == `"success"`, PRESERVING
    `{parallel_tracks}`'s OWN order (group-then-Track, deterministic) — never the real
    arrival order of the background completion notifications above, which is
    non-deterministic across real concurrent Agents. Run STEP 0P.5 below with
    `{tracks_to_merge}`. Its own final action falls through to the SAME final "K of N
    done; {blocked list}" output Step 0 already produces below — reuse its shape
    verbatim with `{done_epics}`/`{blocked_tracks}` as they stand AFTER Step 0P.5 has
    finished (which may have moved an entry from one list to the other — see Step
    0P.5's gate-failure handling).</action>
  </step>

  <step n="0P.5" goal="Merge-back: serialize each successful Track into staging one at a time, reapply its own sprint-status/board.yaml delta, renumber colliding migrations, then run ONE post-merge integrated gate before declaring the whole set successful (Story E11.5, PRD 03 FR-7)">
    <critical>See the "INVARIANTS (Story E11.5)" block above for the full contract
    (union-safe vs. delta-reapply file classes, serialized order, per-Track migration
    renumbering, gate-fail revert scope) before changing anything in this step. This
    step runs ONLY after Step 0P (never after Step 0 — a Track that ran inline through
    Step 0 already wrote directly onto `{project-root}`/`staging`, nothing to merge).
    Everything below runs ON `{project-root}`, already checked out to `staging` — this
    step never `cd`s into, nor spawns any Agent rooted at, a Track's worktree.</critical>

    <check if="`{tracks_to_merge}` is empty (every Track in this batch either failed, or
      there were zero parallel Tracks this invocation)">
      <output>[Step 0P.5] Nothing to merge — no Track in this batch reported success. Skipping merge-back and the post-merge gate.</output>
      <action>GOTO the end of this step (fall through to the final "K of N" output with
      `{done_epics}`/`{blocked_tracks}` unchanged from Step 0P).</action>
    </check>

    <action>Set `{merge_manager}` = `{project-root}/.claude/skills/bagual-epic-runner/scripts/merge_manager.py`.
    Set `{merged_tracks}` = [] (Tracks successfully integrated so far this invocation)
    and `{last_merged_track}` = null (the most recent one — the gate-fail revert target
    if the post-merge gate below fails).</action>

    <action>For EACH `{track}` in `{tracks_to_merge}`, IN ORDER (one at a time — never
    concurrently; this loop body is the literal "serializado, um merge por vez" the AC
    requires):

      1. Merge: `python3 {merge_manager} merge-track --project-root {project-root}
         --base-branch staging --track-branch {track.branch} --track-id
         {track.track_id} --epics {track.epics joined by ' '}`. `{track.branch}` is the
         `branch` field `pool_manager.py allocate` already returned for this Track back
         in Step 0P (the pool worktree's own dedicated branch — read it from the same
         JSON `{track.dest}`/`{track.lease_token}`/`{track.pool_name}` were read from;
         Step 0P did not need it, Step 0P.5 does). Parse the JSON result. **Story
         E11.6:** before deciding a merge is unresolvable, `merge-track` itself already
         tried the ONE documented conservative safe class beyond union-merge —
         import-reorder-only conflicts, all-or-nothing across every conflicted path in
         this merge — and only reports `"status": "conflict"` if that ladder also
         failed (or did not apply to every conflicted path). A `"status": "merged"`
         result may now carry a non-empty `auto_resolved_paths` list if the ladder
         resolved something. See the INVARIANTS block above for the full contract.

      <action>SM-2 mechanical guardrail (Story E11.6), run unconditionally right after
      the Merge call above, REGARDLESS of its `status` (success or conflict — this is a
      SECOND, independently-invoked checkpoint on top of the raw textual scan
      `merge-track` already runs internally right before its own commit): `python3
      {merge_manager} assert-clean --project-root {project-root}`. Log the JSON
      result.</action>

      <check if="`assert-clean` reports `"status": "conflict_markers_found"`">
        <critical>This should be UNREACHABLE in correct operation — `merge-track`
        itself already refuses to commit if its own pre-commit scan finds a marker, so
        this call is normally a redundant confirmation. If it EVER fires anyway,
        `staging` may already be compromised: do NOT treat this as a Track-scoped
        block. HALT THE ENTIRE SUPERVISOR RUN immediately (the same severity as the
        cycle-HALT during graph-build), reporting the exact `occurrences` (file:line)
        `assert-clean` returned, and do not attempt any further merge, story, or write
        to `staging` in this invocation — a human must inspect `staging` before
        anything else touches it.</critical>
        <output>
          ============================================================
          PIPELINE HALTED — SM-2 GUARDRAIL TRIPPED (Story E11.6): a conflict marker was
          detected on `staging` after a merge attempt for Track {track.track_id}. This
          must never happen; stopping immediately for manual inspection.
          Occurrences: {occurrences}
          ============================================================
        </output>
      </check>

      <check if="the merge result's `status` is `"conflict"`">
        <critical>An UNEXPECTED conflict (outside the union-safe / import-reorder
        classes `merge-track` already tried, per the INVARIANTS block above) — the
        merge was already aborted by the script itself (`git merge --abort`), `staging`
        is unchanged. Per FR-8, this NEVER reaches the owner as a `<<<<<<<` marker to
        resolve. Treat exactly like a Track failure: reuse Step 0's Track-blocked
        bookkeeping VERBATIM (Ticket + Briefing + `{track.status}`/
        `{track.epic_status[*]}` = `"blocked"`), with `{track_failure_reason}` = "Step
        0P.5: unexpected merge conflict on {unexpected_conflicts joined} — outside the
        union-safe/import-reorder/delta-reapply classes; the E11.6 safe-class ladder
        was tried and could not resolve it (or did not apply to every conflicted
        path); FR-3's disjunction computation should have prevented this". Move
        `{epic_num}` from `{done_epics}` back out and append to `{blocked_tracks}`
        instead (undo the provisional "done" mark Step 0P made). Note in the
        Ticket/Briefing text that `{track.dest}` remains allocated, un-returned, for
        inspection. Do NOT abort the loop — continue to the NEXT `{track}` in
        `{tracks_to_merge}` (this Track's failure to merge does not block its
        siblings, same FR-6 discipline as everywhere else in this
        file).</critical>
        <action>Continue to the next `{track}` (skip steps 2-4 below for this
        one).</action>
      </check>

      <check if="the merge result's `status` is `"merged"` and its `auto_resolved_paths`
        list is non-empty">
        <output>[Step 0P.5] Track {track.track_id}: safe-class ladder (Story E11.6)
        auto-resolved an import-reorder conflict in: {auto_resolved_paths joined}.</output>
      </check>

      2. Reapply the sprint-status.yaml delta, scoped to ONLY this Track's own keys:
         `python3 {merge_manager} reapply-status-delta --target
         {sprint_status(epic_num) for each epic_num in track.epics — same resolved
         path(s) Path Resolution built above} --source {track.dest}/{same relative
         path} --keys epic-{N} epic-{N}-retrospective {N}-{M}-* {for each epic_num N in
         track.epics; expand {N}-{M}-* to the actual story keys by reading
         {track.dest}'s own sprint-status.yaml development_status: section, same
         pattern Step 1 below already uses to build a {story_queue}} --anchor
         development_status`. If `{track.epics}` spans more than one resolved
         `{sprint_status}` path (mixed product/meta-system epics in the same Track —
         rare but possible), run this once per distinct path, each scoped to only the
         keys belonging to that path's epics.

      3. Reapply the board.yaml delta the SAME way, scoped to only the `TCK-*` keys
         Step F.5 (inside this Track's own story-processor runs) actually touched:
         `python3 {merge_manager} reapply-status-delta --target
         {project-root}/project_controll/tickets/board.yaml --source
         {track.dest}/project_controll/tickets/board.yaml --keys {the TCK-* ids found
         via a git diff of board.yaml between {track's merge-base and its HEAD}, or
         skip this call entirely if that diff is empty} --fields status escalonar
         updated --anchor tickets`.

      4. `git -C {project-root} add {every path touched by steps 2-3}` then `git -C
         {project-root} commit -m "chore: reapply sprint-status/board delta for Track
         {track.track_id} (E11.5)" --allow-empty` (allow-empty: a Track that touched
         neither file, e.g. one whose epic had no traceable Ticket, still gets this
         bookkeeping commit as a harmless no-op — simpler than a conditional skip).

      5. Migrations, scoped to THIS Track only (never batched across the whole set —
         see the INVARIANTS block for why): `python3 {merge_manager}
         renumber-migrations --migrations-dir {project-root}/supabase/migrations`. If
         the JSON result's `renamed` list is non-empty, `git -C {project-root} add
         supabase/migrations/` and `git -C {project-root} commit -m "chore: renumber
         colliding migration timestamps post-merge — Track {track.track_id} (E11.5)"`.
         **This story never runs `make migrate-staging`/applies these migrations to
         the real Supabase Dev database itself** — that is a separate, already-allowed
         (per AGENTS.md) staging deploy action the operator or a LATER invocation
         triggers; this step's job ends at "the migration files exist, correctly
         ordered, in `staging`'s history" (PRD 03 FR-7's literal scope: "aplicadas em
         ordem determinística pós-merge, nunca cada worktree... antes do merge").

      6. Set `{last_merged_track}` = `{track}` (with its `merge_commit`,
         `delta_commit`, and `migration_commit` shas recorded from the steps above —
         Step 0P.5's gate-fail branch below reverts exactly these, newest first).
         Append `{track}` to `{merged_tracks}`.
    </action>

    <check if="`{merged_tracks}` is empty (every Track in `{tracks_to_merge}` hit an
      unexpected conflict above)">
      <output>[Step 0P.5] No Track merged cleanly this batch — skipping the post-merge gate (nothing was integrated).</output>
      <action>GOTO the end of this step.</action>
    </check>

    <output>
      ============================================================
      MERGE-BACK COMPLETE: {merged_tracks length} Track(s) merged into staging, in
      order: {{for each track in merged_tracks: "  {index}. Track {track.track_id} ({track.epics joined}) — merge {track.merge_commit}"}}
      Running the post-merge integrated gate before declaring success...
      ============================================================
    </output>

    <action>Define `{run_gate}` — the SAME check, re-run VERBATIM every time it is
    invoked below (once up front, and once more per bisection trial on gate failure,
    Story E16.6 — see the "INVARIANTS (Story E16.6)" block for why this must be the
    literal same check every time, never a cheaper/partial one on retries): the build
    of the current `staging` checkout (PRD 03 FR-7: a Track's per-worktree build
    passing ≠ the merged set building). Spawn an Agent subagent (model inherited, this is
    orchestration/verification, not an executor per FR-12) with this prompt: "Run a
    build check of the current `staging` checkout at {project-root}. Frontend:
    `cd {project-root}/frontend && npm run build`. Backend: `cd {project-root}/backend
    && uv run pyright && uv run pytest -m unit`. This is running inside an automated pipeline. Do not ask for user
    input. Report PASS or FAIL for each check, with the full command output for any
    failing one." `{run_gate}` PASSES iff every check the gate Agent ran reports PASS.</action>

    <action>Run `{run_gate}` once now.</action>

    <check if="`{run_gate}` PASSED">
      <output>[Step 0P.5] Post-merge integrated gate PASSED. All {merged_tracks length} Track(s) in this batch are DURABLY done.</output>
      <action>For each `{track}` in `{merged_tracks}`: `python3
      {project-root}/.claude/skills/bagual-worktree/scripts/pool_manager.py return
      {track.pool_name} --token {track.lease_token} --base-branch staging
      --project-root {project-root}` (best-effort — a failed `return` is a WARNING,
      logged, never a reason to undo the merge; the worktree just stays allocated for
      manual reclaim later). The provisional `"done"` marks Step 0P made for these
      Tracks' epics stand as final — no further action needed on
      `{done_epics}`/`{sprint_status}`.</action>
    </check>

    <check if="`{run_gate}` FAILED">
      <critical>Story E16.6 (T3.7) — root-cause BISECTION, not a blind "revert only the
      last Track" (that was this step's ENTIRE behavior before this story — see the
      "INVARIANTS (Story E16.6)" block above for the algorithm's full rationale and the
      real adversarial finding that shaped it). Try candidates in REVERSE
      `{merged_tracks}` order (most-recently-merged first — so the common case,
      "culprit is the last Track", resolves on the FIRST trial, zero regression from
      the pre-E16.6 behavior), reverting EXACTLY ONE candidate at a time, never
      accumulating reverts across trials:

      For EACH `{candidate}` in `reversed({merged_tracks})`, IN ORDER, until one is
      blamed or every candidate has been tried:
        1. `{pre_trial_sha}` = `git -C {project-root} rev-parse HEAD` (recorded BEFORE
           this trial touches anything — the exact SHA a failed trial discards back
           to).
        2. `python3 {merge_manager} revert-track --project-root {project-root}
           --track-id {candidate.track_id} --merge-commit {candidate.merge_commit}
           --delta-commit {candidate.delta_commit} [--migration-commit
           {candidate.migration_commit}, if set]`. Parse the JSON.
           <check if="the JSON `status` is NOT `"reverted"` (a git-level failure —
             e.g. the exact adjacent-shared-file 3-way-merge conflict class documented
             in the INVARIANTS block, NOT a gate failure)">
             <critical>Run `git -C {project-root} reset --hard {pre_trial_sha}` to
             discard whatever partially landed, then HALT THE ENTIRE invocation
             immediately (do not try any further candidate, do not fall back to a
             cruder resolution) — `{track_failure_reason}` = "Step 0P.5: bisection
             could not even MECHANICALLY revert Track {candidate.track_id} in
             isolation to test it ({error detail}) — refusing to keep guessing against
             a Track this cannot cleanly test". Report to the operator and STOP; this
             is a pipeline-level HALT (same severity class as the SM-2 guardrail check
             above), not a per-Track block.</critical>
           </check>
        3. Run `{run_gate}` again (the LITERAL same check as step 1 above — never a
           cheaper/partial re-check).
           <check if="`{run_gate}` PASSED this trial">
             <action>STOP the bisection loop. `{candidate}` is BLAMED — its revert (the
             `revert-track` commits just made) STAYS, this is the real, kept fix.
             `{last_merged_track}` = `{candidate}` for the bookkeeping below. Every
             OTHER Track in `{merged_tracks}` (including any earlier candidate this
             loop already tried-and-discarded) is UNAFFECTED and stays merged/done —
             this is the literal "sem reverter sadios além do necessário" the AC
             requires.</action>
           </check>
           <check if="`{run_gate}` FAILED this trial too">
             <action>Discard this trial — `git -C {project-root} reset --hard
             {pre_trial_sha}` (never a 2nd `revert-track`/`revert-commit` here; see the
             INVARIANTS block for the real git-conflict class this specifically avoids)
             — then continue to the NEXT candidate.</action>
           </check>
      </action>

      <check if="the loop above tried EVERY `{candidate}` in `{merged_tracks}` and NONE
        made `{run_gate}` pass (bounded — at most `{merged_tracks length}` trials,
        never more)">
        <critical>PRD 03 FR-8's discipline extended to gate-failures (T3.7): NEVER fall
        back to reverting every Track as a guess. Every trial above was already
        discarded (`git reset --hard` back to its own pre-trial SHA) — `staging` is
        byte-identical to before this bisection started, every Track still merged.
        HALT THE ENTIRE invocation (pipeline-level, same severity as the SM-2
        guardrail) — this is not a single-Track block, since bisection could not
        isolate the fault to any one Track: `{track_failure_reason}` = "Step 0P.5:
        post-merge gate failed and root-cause bisection tried all
        {merged_tracks length} Track(s) individually — none alone resolved it. Likely
        a cross-Track interaction or a pre-existing issue on staging. Every trial
        revert was discarded; every Track remains merged, unreverted. Manual
        inspection required before the next invocation." Report this to the operator
        and STOP.</critical>
        <output>
          ============================================================
          STEP 0P.5 HALTED — POST-MERGE GATE BISECTION EXHAUSTED (Story E16.6): tried
          reverting each of {merged_tracks length} Track(s) individually, in reverse
          merge order; none alone made the gate pass. Every trial was discarded — every
          Track remains merged on staging exactly as it landed. This is NOT a
          single-Track block (never a silent revert-all guess) — a human must inspect
          staging before this pipeline runs again.
          ============================================================
        </output>
      </check>

      <action if="a `{candidate}` WAS blamed above (the bisection loop's PASSED branch
        ran)">
        Move every epic in `{last_merged_track}.epics` out of `{done_epics}` and set
        `{last_merged_track.status}`/`{last_merged_track.epic_status[*]}` = `"blocked"`
        in the SUPERVISOR's own persisted `{sprint_status}` (undoing the provisional
        "done" mark Step 0P made — this file's own on-disk state, already reflecting
        the reapply-status-delta commits above, is now stale for THIS Track only;
        those specific keys are the ones being flipped back, nothing else).
        `{track_failure_reason}` = "Step 0P.5: post-merge integrated gate FAILED after
        merging {merged_tracks length} Track(s) — root-cause bisection (E16.6)
        identified and reverted Track {last_merged_track.track_id}'s contribution
        ({last_merged_track.merge_commit}); {bisection_trial_count} trial(s) run; gate
        output: {gate_failure_detail}". Reuse Step 0's Track-blocked bookkeeping
        VERBATIM (Ticket + Briefing) for `{last_merged_track}`, noting explicitly that
        `{last_merged_track.dest}` remains allocated/un-returned for inspection (do NOT
        call `pool_manager.py return` for this Track — same reasoning as a Step 0P
        FAILURE report). Append to `{blocked_tracks}`.

        Every OTHER Track in `{merged_tracks}` (i.e. `{merged_tracks}` minus
        `{last_merged_track}`) is UNAFFECTED — its merge, delta-reapply, and any
        migration-renumber commits stay in `staging` exactly as they landed, its epics
        stay in `{done_epics}`, and its worktree is `return`ed exactly as in the
        gate-PASSED branch above (FR-6 applied to the post-merge phase: one Track's
        integration failing does not undo its healthy siblings').

        <output>
          ============================================================
          STEP 0P.5 — POST-MERGE GATE FAILED. Root-cause bisection (Story E16.6)
          identified and reverted Track {last_merged_track.track_id}'s contribution
          ({last_merged_track.merge_commit}) after {bisection_trial_count} trial(s).
          {merged_tracks length - 1} sibling Track(s) remain merged and done, exactly
          as they landed — no healthy Track was reverted beyond the one actually
          blamed. This Track's worktree ({last_merged_track.dest}) is left allocated
          for inspection.
          ============================================================
        </output>
      </action>
    </check>

    <action>Fall through to the SAME final "K of N done; {blocked list}" output Step 0
    already produces below — `{done_epics}`/`{blocked_tracks}` now reflect whatever
    Step 0P.5 did above (a full pass-through on gate success; one Track moved from done
    to blocked on gate failure via bisection; or a pipeline HALT if bisection found no
    single culprit or hit a git-level failure mid-trial — in either HALT case, this
    step's own `<critical>` already reported to the operator and stopped, so this
    fall-through is unreached).</action>
  </step>

  <step n="0" goal="Iterate Tracks in series; within each Track, iterate its epics in series; a Track failure blocks only that Track (Story E10.5)">
    <action>Initialize {done_epics} = [] and {blocked_tracks} = [] (both empty lists,
    accumulated across the whole run, used for the final "K of N" summary below).</action>

    <action>For each {track} in the {execution_graph.tracks} built above (across all
      {sprint_status_group}s, in the order those groups were built — deterministic,
      since {epic_set} order is preserved throughout):

        For each {epic_num} in {track.epics} (in order):
          Set {sprint_status} = {sprint_status(epic_num)}, {implementation_artifacts} =
          {implementation_artifacts(epic_num)}, {deferred_findings_file} =
          {deferred_findings_file(epic_num)} — the values resolved during Path
          Resolution above. Steps 1 through 5 below use these exact variable names,
          unchanged from the pre-E10.1 single-epic workflow's own Steps 1-5.

          Update {track.epic_status[epic_num]} = "in-progress" and {track.status} =
          "in-progress" in the persisted {execution_graph} (re-read/re-write the same
          `execution_graph:` block in {sprint_status}, same pattern as the Graph-build
          step) before Step 1 begins for this epic — this is the "per-Track/per-epic
          status lives on disk" half of the AC; it doubles as the marker that a future
          consumer (e.g. Story E11's pool manager) can read without re-deriving
          anything. `track.status` reflects the Track as a whole and stays
          "in-progress" for as long as ANY of its epics is not yet done or blocked — it
          is a function of {epic_status}, never written directly by an individual
          epic's own completion (a Track with 2+ epics is only "done" once the LAST one
          finishes; see below).

          Set {epic_steps_1_5_halted} = false and {epic_failure_reason} = "" before
          running Steps 1 through 5 (each sub-step below sets these two on failure
          instead of terminating the whole invocation — see the per-step edits in
          Steps 2/3/5).

          Run STEPS 1 through 5 below for {epic_num}.

          <check if="{epic_steps_1_5_halted} is true (a story HALTed inside
            story-processor.md, or the retrospective failed — see the specific sub-step
            for exactly which)">
            <critical>Story E10.5 (PRD 03 FR-6): this is TRACK-SCOPED failure isolation,
            not a global supervisor HALT. This Track stops here — {epic_num} and any
            epic still queued after it in {track.epics} never run. Sibling Tracks
            (already-done ones, and ones not yet started) are completely unaffected —
            Step 0's outer loop below continues to the NEXT Track, it does not
            terminate.</critical>

            <action>Set {track.epic_status[epic_num]} = "blocked". For every OTHER epic
            in {track.epics} that comes after {epic_num} and has not yet started (still
            "pending"), also set its {track.epic_status[...]} = "blocked" — they will
            never run because this Track stopped, and leaving them "pending" forever
            would be indistinguishable from "not reached yet" to a future reader (E9.5's
            orphan-sweep / E8.2's crash-recovery must be able to tell "blocked, will
            never run without manual action" apart from "queued, will run later" or
            "still executing"). Recompute {track.status} = "blocked" (a Track is
            "blocked" if ANY of its epics is "blocked", regardless of how many others
            are already "done" — this takes priority over the "done"/"in-progress" rules
            below). Persist this via the same re-read/re-write splice pattern used
            everywhere else in this file.</action>

            <action>Build {track_failure_reason}: a one-paragraph, human-readable
            description of exactly what failed — which epic ({epic_num}), which
            sub-step (Step 2's failing story key + its {error_description}, or the
            specific Step 3/5 condition that failed — each sub-step's own
            {epic_failure_reason} assignment below supplies this text verbatim).</action>

            <action>Ticket bookkeeping — best-effort, NON-BLOCKING (same contract as
            story-processor.md Step F.5: a Ticket write NEVER re-escalates into a HALT
            of any kind; on any failure below, log a WARNING and continue to the
            Briefing step):
              1. Search {sprint_status} for the existing `origem: (TCK-[\w-]+)` comment
                 convention immediately above `epic-{epic_num}:` (the exact lookup
                 story-processor.md Step F.5 already performs — read-only, no new
                 convention invented).
              2. If one or more TCK ids are found: for each, open
                 `project_controll/tickets/TCK-{id}.md`. PRD 02 explicitly forbids
                 renaming/reordering the Ticket lifecycle's existing status values — so
                 this does NOT invent a new `status: bloqueado`. Instead it reuses the
                 field `bagual-tickets` already defines for exactly this situation
                 ("an explicit, undecided blocker that needs the Gerente/dono's
                 attention"): set `escalonar: true` in the front-matter (if not already
                 true) and append a `## Log` entry: "{date}: epic {epic_num} bloqueada
                 pelo bagual-epic-runner (Track {track.track_id}) — {track_failure_reason}".
                 Mirror the same `escalonar: true` + `updated: {date}` update into that
                 ticket's entry in `project_controll/tickets/board.yaml` (the index —
                 same convention Resolver already uses). Set
                 {track_blocking_ticket_id} = the first TCK id found.
              3. If NO `origem: TCK-*` is found for this epic: materialize a fresh Ticket
                 by SPAWNING an Agent subagent (never hand-roll the .md/board.yaml write
                 yourself — compose the existing skill, same discipline as E5.6's
                 headless batch-creation) with this prompt: "Run the skill
                 /bagual-tickets --headless to add a ticket: category chore, area
                 {epic_area if declared in epic_areas, else 'orquestrador'}, priority
                 alta, origem proativo, title 'Epic {epic_num} bloqueada —
                 bagual-epic-runner (Track {track.track_id})', description
                 {track_failure_reason}. This is running inside an automated pipeline.
                 Do not ask for user input." Then, on success, set `escalonar: true` on
                 the returned ticket (same as branch 2) — a freshly materialized
                 blocking ticket is, by definition, exactly the kind of undecided item
                 `escalonar: true` exists for. Set {track_blocking_ticket_id} = the
                 returned `ticket_id`.
            </action>

            <action>Briefing bookkeeping — best-effort, NON-BLOCKING (same contract as
            above; a failure here is a WARNING, never an escalation): append an entry to
            today's Briefing artifact (PRD 00/E8.7),
            `project_controll/gerente/briefing-{date, compact YYYYMMDD}.md`, so the next
            interactive session surfaces this without the dono going looking for it.
              - If the file does not exist: create it with minimal frontmatter
                (`status: unread`, `written_at: {now, ISO}`) and body
                `# Briefing — {date}\n\n## Bloqueios de execução (bagual-epic-runner)\n\n- {bullet, see below}\n`.
              - If it exists: this file's format (E8.7/`gerente_briefing.py`) is a
                frontmatter block followed by a title region and zero or more `## Ciclo
                {cycle_id}` sections. Everything BEFORE the first line matching
                `^## Ciclo ` (or the entire body, if no such line exists) is the
                "title region" — `gerente_briefing.py write-briefing` only ever
                replaces/appends `## Ciclo` sections and always preserves this title
                region verbatim, so it is the only safe place to append free-form notes
                without a future Gerente cycle silently discarding them. Within that
                title region, find or create a `## Bloqueios de execução
                (bagual-epic-runner)` subsection and append one bullet to it (do not
                replace prior bullets — a second blocked Track the same day adds a
                second bullet). Force the frontmatter `status` field to `unread`
                (unchanged fields otherwise preserved) — a new blocker always makes the
                Briefing unread again, same rule the script itself applies on every new
                section.
              - Bullet text: "- {date} — epic {epic_num} bloqueada (Track
                {track.track_id}), Ticket {track_blocking_ticket_id}:
                {track_failure_reason}".
            </action>

            <action>Append {"track_id": track.track_id, "epic": epic_num, "reason":
            track_failure_reason, "ticket": track_blocking_ticket_id} to
            {blocked_tracks}.</action>

            <output>
              ============================================================
              TRACK {track.track_id} BLOCKED — epic {epic_num} failed; this Track stops
              here (no further epic in this Track's queue runs).
              Reason: {track_failure_reason}
              Ticket: {track_blocking_ticket_id}
              Briefing: entry recorded in project_controll/gerente/briefing-{date}.md
              This is Track-scoped isolation (Story E10.5) — healthy sibling Tracks are
              UNAFFECTED and the supervisor run CONTINUES to the next Track. The
              supervisor is NOT halted.
              ============================================================
            </output>

            <action>BREAK out of the inner "for each {epic_num} in {track.epics}" loop
            now (do not attempt any further epic in THIS Track) and CONTINUE the outer
            "for each {track}" loop with the NEXT Track, if any. Do NOT HALT the
            supervisor run.</action>
          </check>

          Update {track.epic_status[epic_num]} = "done" in the persisted
          {execution_graph} once Step 5 completes for this epic (only reached when
          {epic_steps_1_5_halted} stayed false). THEN recompute {track.status}: "done"
          if and only if every entry in {track.epic_status} is now "done" (i.e. this was
          the last epic in {track.epics}); otherwise it stays "in-progress" and the loop
          continues to the next epic in this same Track. This two-level update
          (per-epic status, then a Track-status recompute derived from it — never a
          direct "mark the Track done because one epic finished") is what keeps a
          multi-epic Track's on-disk state accurate for every epic in it, not just the
          first or the last.

          Append {epic_num} to {done_epics}.
    </action>

    <output>
      ============================================================
      RUN COMPLETE: {done_epics length} of {epic_set_length} epic(s) done: {done_epics
      joined by ', '}.
      {if {blocked_tracks} is non-empty:}
      BLOCKED: {blocked_tracks length} epic(s) —
      {{for each entry in blocked_tracks: "  - epic {entry.epic} (Track {entry.track_id}) — {entry.reason} — Ticket {entry.ticket}"}}
      {/if}
      {if {blocked_tracks} is empty:}
      No blocked Tracks.
      {/if}
      ============================================================
    </output>
  </step>

  <step n="1" goal="Build the story queue for the current epic">
    <action>Read {sprint_status} and parse the development_status section</action>

    <action>Collect ALL stories for this epic into an ordered list called {story_queue}:
      - Find all keys matching pattern: {epic_num}-*-* (e.g., 2-1-*, 2-2-*, etc.)
      - Exclude epic keys (epic-N) and retrospective keys (epic-N-retrospective)
      - Preserve the order they appear in the file (top to bottom)
      - Record each story's current status
    </action>

    <action>Filter {story_queue} to only stories that are NOT "done"</action>

    <check if="{story_queue} is empty">
      <output>All stories in epic {epic_num} are already done.</output>
      <action>GOTO step 3 (epic completion check)</action>
    </check>

    <output>
      EPIC {epic_num} PIPELINE STARTING

      Stories to process ({story_queue_length} remaining):
      {{for each story in story_queue: "- {story_key}: {story_status}"}}

      Processing will begin with: {first_story_key}
    </output>
  </step>

  <step n="2" goal="Process each story via isolated story-processor agent">
    <critical>Each story runs in its own Agent subagent. Do not implement stories inline.</critical>

    <action>For each story in {story_queue}:
      Set {current_story_key} = the story's full key (e.g., "1-8-text-message-handler")
      Set {current_story_id} = numeric prefix only (e.g., "1-8")
      Set {current_story_status} = the story's current status
    </action>

    <output>
      ============================================================
      SPAWNING STORY AGENT: {current_story_key} (status: {current_story_status})
      ============================================================
    </output>

    <action>Read {story_processor} and execute ALL its steps (A through F) directly for {current_story_key}.
      Do NOT spawn a subagent to read story-processor — follow its instructions yourself inline.
      When a step says "Spawn an Agent subagent" for create-story, dev-story, code-review, or quick-dev,
      YOU spawn that agent directly (you are the orchestrator, not a nested subagent).

      **Story E13.3 — sensitive-path floor, evaluated per story, right after story-processor's own Step B
      (dev-story) and BEFORE its Step C reads `fast_mode`:** compute `{effective_fast_mode}` (used ONLY in
      the "Input values" list right below, as the `fast_mode` handed to this one story's story-processor
      execution) BEFORE you start reading that list. Step B is the first point in this story's pipeline
      where a real diff exists on disk — running the floor check any earlier (e.g. once per epic, before
      any story ran) would see an empty/irrelevant diff, since a clean `staging` checkout has nothing to
      check yet. So, immediately after story-processor's Step B reports implementation complete and before
      you evaluate its Step C `{fast_mode} == true` check for {current_story_key}:
        1. Run `python3 {project-root}/semgrep/scripts/sensitive_path_floor.py --diff --json` (E7.6 — do
           not modify this script; it already checks the union of unstaged + staged changes against the
           project's sensitive-path catalog and always exits 0).
        2. **Success, `floor_triggered: true`:** set `{effective_fast_mode}` = `false` for this story's
           Step C only — full Cerco forced, regardless of the invocation's global `{fast_mode}`.
           Output: "[Floor] sensitive_path_floor.py: floor_triggered=true (categories: {categories_hit})
           — full Cerco forced for {current_story_key}, overriding global fast_mode ({fast_mode})."
        3. **Success, `floor_triggered: false`:** set `{effective_fast_mode}` = `{fast_mode}` (global value,
           unchanged — today's behavior is fully preserved when nothing sensitive was touched).
        4. **Failure** — any of: binary/script missing, non-zero/unexpected exit code, unparsable JSON
           output, or a JSON object that parses but is MISSING the `floor_triggered` key (unexpected
           schema) — degrade NOISILY, never block or crash the pipeline: set `{effective_fast_mode}` =
           `{fast_mode}` (the original global value, exactly as if this story block did not exist) and
           output a visible warning: "[Floor] WARNING: sensitive_path_floor.py failed ({error_summary}) —
           floor could not be checked, keeping original fast_mode ({fast_mode}) for {current_story_key}."
        5. The floor can only ever push `{effective_fast_mode}` from `true` toward `false` (more Cerco) —
           it never pushes the other way. When the global `{fast_mode}` is already `false`, the floor check
           still runs (for the audit trail/output) but `{effective_fast_mode}` stays `false` either way —
           there is nothing to force that the Trilha's own posture wasn't already covering (E7.6 AC4: "a
           Trilha só pode reduzir fora do piso").
        6. `{effective_fast_mode}` is scoped to THIS story's Step C evaluation only. The next story in
         {story_queue} (or the next epic) re-derives its own `{effective_fast_mode}` from a fresh floor
         check against ITS OWN diff — `{fast_mode}` itself (the global, user-supplied flag) is never
         mutated by this block. (Known fail-safe gap around leftover uncommitted diff from a prior story
         — see `## INVARIANTS (Story E13.3...)` below; it can only ever cause an unnecessary full review,
         never a missed one.)

      Input values to use throughout story-processor execution:
      - story_key: {current_story_key}
      - story_id: {current_story_id}
      - story_status: {current_story_status}
      - config_path: {project-root}/_bmad/bmm/config.yaml
      - implementation_artifacts: {implementation_artifacts}
      - sprint_status: {sprint_status}
      - date: {date}
      - project_root: {project-root}
      - epic_num: {epic_num}
      - fast_mode: {effective_fast_mode}   <!-- Story E13.3 — computed above; {fast_mode} itself is never overwritten -->

      CONTEXT CONTINUITY — before step A, read these files to have full accumulated project context
      (they persist across context compactions and are updated after each story):
      - {project-root}/_bmad-output/anti-patterns.md
      - {project-root}/_bmad-output/decisions.md
      - {project-root}/_bmad-output/product-decisions.md
      - {project-root}/_bmad-output/notes.md

      Complete all steps A through F before moving to the next story.
    </action>

    <check if="Agent returned failure or HALTED">
      <output>
        STEP 2 HALTED for {current_story_key} (epic {epic_num}).
        Error: {error_description}

        Story E10.5: this stops epic {epic_num}'s Track, not the whole supervisor run.
        After fixing, re-run: /bagual-epic-runner {epic_num}
      </output>
      <action>Set {epic_steps_1_5_halted} = true and {epic_failure_reason} = "Step 2:
      story {current_story_key} failed — {error_description}". Do NOT process any
      remaining story in {story_queue} and do NOT proceed to Step 3/4/5 for this
      epic — return control to Step 0's per-epic check now (story-processor.md's own
      per-story HALT is unchanged; this is only where the SUPERVISOR'S response to that
      HALT changes from "abort everything" to "block this Track, Story E10.5").</action>
    </check>

    <action>Re-read {sprint_status} to verify {current_story_key} is now "done"</action>

    <check if="{current_story_key} status is NOT 'done' in sprint_status">
      <output>
        STEP 2 HALTED: Story agent completed but {current_story_key} was not marked done
        in sprint-status.yaml (epic {epic_num}). Check the story agent output for errors.

        Story E10.5: this stops epic {epic_num}'s Track, not the whole supervisor run.
        After fixing, re-run: /bagual-epic-runner {epic_num}
      </output>
      <action>Set {epic_steps_1_5_halted} = true and {epic_failure_reason} = "Step 2:
      story {current_story_key} completed its Agent but was not marked done in
      sprint-status.yaml". Do NOT process any remaining story in {story_queue} and do
      NOT proceed to Step 3/4/5 for this epic — return control to Step 0's per-epic
      check now.</action>
    </check>

    <output>
      ============================================================
      STORY {current_story_key} COMPLETE — moving to next story
      ============================================================
    </output>

    <action>Move to next story in {story_queue}. Repeat this step for each remaining story.</action>
  </step>

  <step n="3" goal="Verify all stories are done before running retrospective">
    <critical>This check is unreachable in the normal path — Step 2 above already HALTs
    (Story E10.5: sets {epic_steps_1_5_halted} and returns to Step 0) on the first
    story failure and never falls through to here with an incomplete queue. This check
    exists only for the degraded/resumed case (e.g. the whole process was killed
    externally between stories and re-invoked with a stale {story_queue}).</critical>
    <action>Re-read {sprint_status} and verify ALL stories for epic {epic_num} are "done"</action>

    <check if="some stories are not done">
      <output>
        STEP 3 HALTED: epic {epic_num} pipeline finished processing available stories,
        but some stories remain incomplete (likely due to earlier interruption).
        Story E10.5: this stops epic {epic_num}'s Track, not the whole supervisor run.
        Re-run /bagual-epic-runner {epic_num} after addressing any issues.
      </output>
      <action>Set {epic_steps_1_5_halted} = true and {epic_failure_reason} = "Step 3:
      some stories for epic {epic_num} remain incomplete after Step 2 (likely an
      earlier interruption)". Do NOT proceed to Step 4/5 for this epic — return
      control to Step 0's per-epic check now.</action>
    </check>

    <output>All stories for epic {epic_num} are done. Checking for deferred findings...</output>
  </step>

  <step n="4" goal="Address deferred findings from review loops via bmad-quick-dev">
    <action>Check if {deferred_findings_file} exists and contains content</action>

    <check if="file does not exist or is empty">
      <output>[Step 4] No deferred findings. Skipping batch fix pass.</output>
    </check>

    <check if="file exists and has content">
      <output>[Step 4] Deferred findings found. Running bmad-quick-dev batch fix pass...</output>

      <action>Spawn an Agent subagent using the Agent tool's `model` parameter set explicitly to `sonnet` (Story E6.5, PRD 03 FR-12 — executors run Sonnet; do NOT let this subagent inherit the parent Orchestrator's model, typically Opus) with this prompt:
        "Run the skill /bmad-quick-dev with the following intent:

        Address all deferred code review findings from epic {epic_num}. Read the findings file at {deferred_findings_file}. These are issues flagged during per-story review that were not resolved within the 2-iteration review limit.

        IMPORTANT: Re-validate each finding first before acting — some may already be resolved by later story implementations. Only fix confirmed active issues. Group related fixes across stories when possible.

        This is running inside an automated pipeline. Auto-approve all checkpoints.
        Do not ask for user input — proceed automatically."
      </action>

      <check if="Agent failed">
        <output>WARNING: Deferred findings batch fix failed. File preserved at {deferred_findings_file}. Continuing to retrospective.</output>
      </check>

      <check if="Agent succeeded">
        <action>Stage all files changed by the batch fix (avoid staging sensitive files like .env or credentials).</action>
        <action>Run: git commit using a HEREDOC:
          fix: epic-{epic_num} deferred review findings — batch fix pass

          Co-Authored-By: Claude Opus 4.6 (1M context) &lt;noreply@anthropic.com&gt;
        </action>
        <action>Delete {deferred_findings_file} to prevent stale findings from accumulating on re-runs.</action>
        <output>[Step 4] Deferred findings addressed, committed, and findings file cleaned up.</output>
      </check>
    </check>
  </step>

  <!-- ==================== STEP 5: Retrospective + Mark Epic Done ==================== -->
  <step n="5" goal="Run retrospective and mark epic done">
    <critical>The epic is NOT complete until the retrospective finishes. Do NOT mark epic as done before this step succeeds.</critical>

    <action>Note (Story E6.6, PRD 03 FR-13 — recording on completion): the epic-level Ledger recording already happens inside `/bmad-retrospective`'s own `on_complete` hook, wired by Story E4.5 (`_bmad/custom/bmad-retrospective.toml`) — this step does not duplicate it. The per-story Ledger recording (Step D.6) and per-story Ticket `## Fechamento` recording (Step F.5) already ran inside story-processor.md for every story processed in Step 2 above. This step's spawn below is unchanged by E6.6 other than the model pin already noted in RULES.</action>

    <output>[Step 5] Running retrospective for epic {epic_num}...</output>

    <action>Spawn an Agent subagent with this prompt:
      "Run the skill /bmad-retrospective with args: epic {epic_num} yolo
       This is running inside an automated pipeline. Auto-approve all checkpoints and prompts.
       Do not ask for user input — proceed automatically."
    </action>

    <check if="Agent failed">
      <output>
        STEP 5 HALTED (Retrospective) for epic {epic_num}.
        Error: {error_description}
        All stories are done but the epic cannot be marked done without a completed
        retrospective.
        Story E10.5: this stops epic {epic_num}'s Track, not the whole supervisor run.
        Run manually: /bmad-retrospective yolo — or re-run: /bagual-epic-runner {epic_num}
      </output>
      <action>Set {epic_steps_1_5_halted} = true and {epic_failure_reason} = "Step 5:
      retrospective failed — {error_description}. All stories were done but the epic
      could not be marked done without a completed retrospective." Do NOT mark the epic
      done — return control to Step 0's per-epic check now.</action>
    </check>

    <output>[Step 5] Retrospective complete. Marking epic as done...</output>

    <action>Update {sprint_status}: set epic-{epic_num} and epic-{epic_num}-retrospective to done, update last_updated to current date. Preserve all existing comments and structure.</action>

    <action>Stage sprint-status.yaml and any retrospective artifacts. Avoid staging sensitive files.</action>
    <action>Run: git commit using a HEREDOC:
      docs: epic-{epic_num} retrospective — epic complete

      Co-Authored-By: Claude Opus 4.6 (1M context) &lt;noreply@anthropic.com&gt;
    </action>

    <output>
      ============================================================
      EPIC {epic_num} PIPELINE COMPLETE

      All stories implemented, reviewed, and committed.
      Retrospective completed and committed.
      Epic {epic_num} marked as done.
      ============================================================
    </output>
  </step>

</workflow>
