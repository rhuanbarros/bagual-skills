---
review: adversarial
target: prd.md (Bagual Skills v2 — bagual-manager + bagual-bmad-loop-runner)
reviewer_lens: adversarial (parallel panel, one of three)
date: 2026-08-04
---

# Adversarial review — Bagual Skills v2 PRD

Method: read the PRD in full, then checked its central evidence claims against the actual repo —
`.bmad-loop/policy.toml`, the Epic 22 spec-gate document, the Epic 22 retrospective, `deferred-work.md`,
`project_controll/tickets/board.yaml`, and `git log` timestamps on the relevant files. Several findings
below rest on that cross-check, not on the PRD's text alone — cited with paths and, where it matters,
commit hashes.

---

## 1. The core bet — "if the night is literal, the day must be complete"

**The founding anecdote is more complicated than the PRD's telling of it, and that matters.**

The PRD's Context section (lines 30–38) and FR9 both frame Story 22.1 as proof that a **pre-flight**
spec-gate would have caught the missing-column bug before the destructive migration ran. The actual
timeline, reconstructed from git:

- `ad4f1fc5` (2026-08-03 14:23) — the destructive migration (`DROP TABLE actual_expenses` /
  `property_expenses`) is **already committed and applied**. The commit message itself says "22.1 esta
  BLOCKED, nao backlog — e commita a migration ja aplicada" (already applied).
- `de1df602` (2026-08-03 19:55) — `spec-gate-epic-22.md` is authored, five and a half hours *after* the
  drop, and its own finding (c) literally says "**Already-applied** migration ... had no CSV rollback."

So in the one incident this whole PRD is built around, the gate that FR9/FR11 propose to make
mandatory-before-run did not run before the run — it ran as a post-hoc audit of damage already done, and
the CSV-rollback half of finding (c) is explicitly logged as "not retroactively fixable (data already
gone)." The retrospective (`epic-22-retro-2026-08-04.md`, lines 30–37) confirms the actual mechanism: a
dev session escalated CRITICAL *during execution*, after the DDL had already run. FR11 ("No PASS, no
run") gates the **start** of a run. Nothing in the PRD gates an individual destructive action **inside**
a running session — the review/escalation layer that caught this in reality operates after the turn
completes, not before an irreversible statement executes. A future spec that passes the gate (because
the gap it contains isn't the kind the gate happens to check) still lets a `DROP TABLE` fire unreviewed
mid-session. The PRD's mitigation for this class is FR9's inventory audit getting better over time via
FR24 (spec debt → standing rules) — but that is reactive, one incident at a time, forever a step behind
whatever the current rule set doesn't yet cover. "The day must be complete" is a completeness claim about
a document; it does not, by itself, insert a checkpoint before an irreversible statement executes, which
is where the actual damage happened in the anecdote used to justify it.

**A second, cleanly evidenced failure class the core bet handles badly: cross-story emergent defects.**
`deferred-work.md` (current file, ~470 lines) is full of findings that are *only visible once two
stories' code sits side by side* — e.g. the review of Story 22.7 found "the same failure communicated
twice, inconsistently" between a raw `error.message` alert and a localized error block, explicitly
because the story was "directed to mirror" an earlier screen "near-1:1" — the inconsistency is a property
of the *pair*, not of either story's spec. Story 22.8's review found `useVencidaExpensesCount()` "has no
in-flight-request dedup" because a second consumer (this story) started mounting alongside an existing
one. No amount of upfront spec completeness for a single story can catch a defect whose precondition is
"another story exists." FR7 authors all stories upfront; FR9 audits stories, not their pairwise
interaction; nothing in section 7.2–7.4 assigns ownership of cross-story consistency checking before
code exists — it is discovered, as evidenced, only by a human or review pass reading the diffs after the
fact, and then deliberately **not fixed** ("out of scope for a single-story mechanical patch") six times
in a row in this one epic's `deferred-work.md`. This is not a spec-completeness problem the gate can
solve; it is a category the "complete plan, literal execution" model is structurally blind to.

**What happens when the plan is complete and still wrong?** Section 9 lists "Gate `PASS` verdicts
followed by CRITICAL escalations" as a counter-metric with the honest note that such a gate "manufactures
false confidence" — credit where due, the PRD names this risk. But naming it as a metric to *watch* is
not a disposal plan. If a spec is internally consistent, inventory-complete, and every Block-If answered,
but rests on a wrong product assumption that was never ambiguous enough to surface as a Block-If, nothing
in FR7–FR24 catches it before the loop executes it across the whole epic overnight. FR18 (QA gate) is the
only backstop, and it is generated from the same `qa-pack/` that is itself derived from the same
documents the spec shares its wrong assumption with (per `AGENTS.md`, `bagual-qa-builder` derives the
pack from "canonical WDS/BMad docs") — so the QA gate is not guaranteed to be independent of the error it
would need to catch.

---

## 2. The bottleneck move — is the owner now the bottleneck, and is that acknowledged?

FR7 ("All stories are authored before the run") and FR10 ("Open questions are resolved with the owner,
**synchronously**") together move every unit of ambiguity resolution that used to be absorbed inline by
an executing agent (bagual-epic-runner's model) onto the owner, up front, before anything runs. FR10 goes
further than "the owner must be present" — it forbids the gate from ever inferring, which forecloses even
a batched-async-questions mode (the owner answering a queued list on their own time, the way FR27
describes the *manager's* own communication contract — "short, scannable, expand on demand"). The gate's
mode (synchronous, thorough, no inference) and the manager's mode (terse, async-friendly, phone-readable)
are two different cognitive-load contracts for the same owner, on the same night, and the PRD never
reconciles them or estimates the cost of context-switching between them.

The PRD names exactly one counter-metric for this: "Owner hours spent in the planning gate... If planning
cost explodes, the bottleneck simply moved to the owner" (§9). That is an honest label, not a design
response. There is no target number, no time-box, no fallback if a given epic's Block-If list runs long
(what happens at Block-If #6 on a large epic — does the gate ever say "good enough, proceed with recorded
assumptions" or does it hold the line indefinitely per FR10's "never infers"?), and no answer for what the
owner does differently once the counter-metric trends badly. A counter-metric with no threshold and no
lever is a label on a known problem, not a mitigation of it.

Compounding this: per §2.1, `bagual-bmad-loop-runner` is explicitly **the only skill the owner drives by
hand**, "isolated on purpose so the owner has full control over it" — and §7.6 states everything *except*
this skill is invoked through `bagual-manager`. Read literally, this means the manager — the skill whose
entire job is "reads state, prioritizes, dispatches" (FR26) — cannot itself start an epic run, even after
it has verified the gate is `PASS` and decided the epic is next in priority. It can get everything ready
and then must wait for the owner to personally open a separate window and invoke the runner. That is a
second, structural bottleneck the PRD does not discuss as one: readiness and execution are decoupled by a
mandatory human handoff that has to happen for every single epic, not only for the planning-gate content
itself.

---

## 3. Contradictions

**FR13 (worktree isolation for the loop) hardens one arm of a two-arm collision it names, and leaves the
other arm exactly as exposed.** FR13's own rationale cites Epic 22: "a concurrently dispatched agent
writing to the same checkout collides silently. This happened during Epic 22." Verified — the retro
(lines 56–63) describes it precisely: a table-relinking agent was dispatched into the same working
directory while `bmad-loop` ran Story 22.2 under `isolation="none"`, "**neither side knew about the
other**," producing duplicated live code cleaned up later (`TCK-20260803234901-fefe`). FR13 fixes this by
forcing `isolation="worktree"` for loop runs. But the collision had two participants: the loop run, and a
manager-dispatched ad-hoc agent writing directly into the main checkout. FR13 only isolates the first.
The manager side is still governed by FR26's soft judgment call — "where parallel file edits would
collide, the manager creates a worktree" — which is the exact judgment that failed in the recorded
incident ("neither side knew about the other"). The project's own recorded fix for that incident was a
*procedural* reminder ("always run `bmad-loop list` before dispatching any repo-writing agent" —
`checar-bmad-loop-antes-de-despachar`), not a structural guarantee. The PRD hardens the loop's own
concurrency but does not extend the same discipline to the manager's dispatch path, despite citing the
exact incident that involved both.

**FR42's "no lock, no shared index" design is stated for tickets and silently assumed — not
demonstrated — for `deferred-work.md`, which the retro shows is exactly the kind of file FR42 was
designed to avoid.** FR42's rationale: "several `bagual-manager` windows must be able to work at once
(FR26), and a shared index is a shared write target — the one thing that makes concurrent writers
collide." `deferred-work.md` (`_bmad-output/implementation-artifacts/deferred-work.md`, checked directly)
is a single shared file, not one-file-per-entry — FR17 has the closure checklist reading, triaging, and
annotating it (`resolved_by:` entries) as part of every epic close. If a second manager window is mid-
review on a different epic and appends a new deferred item to the same file at the same moment
`bagual-bmad-loop-runner` is mid-sweep on it, that is precisely the shared-write collision FR42 reasoned
its way out of for tickets — reintroduced, unaddressed, for the file this epic's own retrospective singles
out as central to closure. The PRD applies concurrency discipline to one persistence surface and not to
the sibling surface that the same document's own motivating incident touches.

**FR28 (capture every correction automatically) has no filter; FR25a (pruning test, shrink-or-same-size)
has no trigger.** FR28: "the manager records the lesson itself... The owner must never teach the same
thing twice" — stated as unconditional and automatic, confirmed in `.memlog.md`: "Self-learning records
EVERY owner correction, automatically. No manual marking step." FR25a's three disciplines (pruning test,
trust status, shrink-or-same-size curation pass) are stated as `bagual-wiki`'s governance model, but
nothing in FR20/FR25a/FR28 says *when* a curation pass runs, who triggers it, or how the immediate,
unconditional writes FR28 mandates get subjected to the pruning test at all before they land. Growth is
mandatory and immediate; shrinkage is a named discipline with no scheduled event that invokes it. Left
as designed, the two FRs describe a one-way valve, not the closed loop FR25a's own rationale ("a curation
pass ends the knowledge base the same size or smaller, never larger") requires.

**FR14's proven mechanism is in tension with FR32/FR33's portability claim.** The "resolved during
discovery" note under §10 spells out FR14's actual mechanism: "a hook gated by environment-variable
tagging (set only on sessions the orchestrator spawned)... that atomically drops timestamped event files
into a run directory, which the orchestrator polls." A Claude Code hook lives in `.claude/settings.json`
(or equivalent harness config) — a machine/project config surface, not the skill folder. FR32 states
installation is "copy the skill folder into the target project, runs `init`, and it works," and FR2/FR1
scope `init`'s writes to `.bagual/` (configuration only). Nowhere does the PRD say `init` is empowered
to also write the harness's own hook configuration. If it isn't, FR14's proven wake mechanism is not
actually portable by "copy + init" — it depends on a manual, undocumented setup step outside the skill's
own installation contract, which is exactly the kind of thing FR6 calls "a defect the moment it travels."

---

## 4. Scope — plan or wish?

The roster (§2.3) is ten skills (`bagual-manager`, `bagual-tickets`, `bagual-wiki` **new**,
`bagual-spec-gate`, `bagual-bmad-loop-runner` **new**, `bagual-worktree`, three QA skills,
`bagual-semgrep-rules` **new**), plus a new configuration architecture (FR2–FR6, FR39–FR41), a new
authoring standard enforced through a meta-skill (FR34–FR41), and a full English rewrite of
`bagual-tickets` "including its data files" (§2.3). Non-Goals explicitly disclaims "Rewriting the skills
that already work... not a from-scratch reimplementation of every skill's logic" — but §2.3 and FR26–FR30
describe exactly that for the renamed manager (new communication contract, new self-learning obligation,
new routing responsibility, 24 capabilities individually re-triaged), and `bagual-tickets` is rewritten
"fully... including the data files it produces (board, ticket files, JSON output)" per `.memlog.md`. The
Non-Goal and the actual content of the roster are in tension; a rename-plus-rewrite-plus-new-contract is
not "naming, configuration, language and distribution" alone.

**The PRD does not name a minimal slice that would prove the thesis**, and the thesis is narrow and
testable: does auditing stories (not the epic doc) before a gated, worktree-isolated `bmad-loop run`,
followed by a mandatory closure checklist, actually reduce Epic-22-class incidents? That is FR7–FR13 and
FR17–FR21 — a bounded, already-mostly-existing set (§6's own table shows stories mode, worktree
isolation, and sweep all already implemented, just unconfigured or unused). None of `bagual-wiki`
(new), `bagual-semgrep-rules` (new), the manager's self-learning/routing apparatus (FR26–FR30), the
`customize.toml`-style merge machinery (FR4, FR39), or the authoring-standard tooling (FR34–FR41) is
required to run that test. The PRD instead ships them as one bundled unit with one shared verdict, closed
on the owner's instruction "after the research was folded in" with its own adversarial review explicitly
"not run... flagged as unspent" (§10, item 4). Bundling a proof-of-thesis slice with a suite-wide
infrastructure rewrite means a failure of the thesis and a failure of, say, the config-merge design are
indistinguishable in the metrics of §9 — both would show up as the same disappointing numbers, with no
way to tell which part is at fault.

---

## 5. What is missing entirely

**Migration and rollback are explicitly deferred, not designed.** Open Question #1: "Does gorioapp itself
migrate to v2, and when?... Deferred by explicit owner decision." Yet §2.3's roster table lists
`bagual-epic-runner` as "**Retired**. Replaced by `bagual-bmad-loop-runner`" and Goal #1 is to "Replace
`bagual-epic-runner`" outright. The document simultaneously declares the old orchestrator retired and
leaves open whether the one real project this was designed against (gorioapp itself, whose Epic 22 is the
entire evidentiary basis of the PRD) will ever run v2 at all, or when, or under what criteria. There is no
runbook for: what happens to an epic mid-flight under v1 conventions (`sprint-status.yaml` mode,
`isolation="none"`) if a switch happens mid-epic; what triggers a decision to revert if v2 underperforms
(§9's targets are directional — "rising toward," "falling toward" — with no threshold that would count as
"this isn't working"); or what "v1 stays on disk untouched for reference" (FR31) actually buys
operationally beyond the ability to read old code, since nothing describes re-enabling it in a live
project.

**No recovery contract for the runner's own session dying.** FR15/FR16 cover disposal for a `CRITICAL`
escalation and for stalls/budget trips *inside the run* `bmad-loop` supervises. Nothing covers the
`bagual-bmad-loop-runner` skill's own resident window itself dying mid-supervision — laptop sleep,
terminal killed, network drop — which is a normal overnight failure mode for a process meant to stay
resident for hours unattended. The manager's kept-capability list (§10) explicitly retains "crash
detection and reconciliation of a session that died mid-cycle" and "orphan dispatch sweep" for
`bagual-manager`, but the loop-runner — the skill actually resident during the highest-stakes unattended
window — has no equivalent stated contract for its own crash/reattachment.

**No defined ceiling on the planning gate itself.** FR10's "never infers" combined with no stated cap on
Block-If rounds or elapsed time means the gate has no defined exit other than eventual `PASS` — there is
no stated behavior for "the owner is out of time tonight but three Block-Ifs remain," which is a plausible
and unaddressed real state given §2's own premise that the owner is "available during planning and
unavailable during execution" — i.e., on a clock.

**`FR42`'s "no shared index" claim is not fully verified against what currently exists.** The live
`project_controll/tickets/board.yaml` carries the header comment "reconstruído por rebuild_board.py...
Fonte de verdade = arquivos TCK-*.md" and is a checked-in, committed file. If v2 keeps a committed,
periodically-rebuilt `board.yaml` (for git-diffability / human browsing, as the current one clearly is),
that file is itself a shared write target every time the rebuild runs, regardless of whether reads always
re-derive from source. FR42 does not say whether `board.yaml` becomes purely ephemeral/gitignored in v2
or stays a committed artifact — if the latter, the race it claims to remove by design still exists at the
rebuild-write step, just less frequently triggered.

---

## Summary judgment

The PRD's central, evidenced anecdote (Story 22.1) is real and the closure gap it names (FR17–FR21) is
real and precisely diagnosed — the retro's own words back it almost verbatim. But the anecdote is being
asked to carry more than it supports: the gate that's proposed as mandatory-before-run did not, in the
one case cited, run before the harm; the collision fix (FR13) hardens only the half of a two-sided
incident that involves the loop, not the manager's own dispatch path implicated in the same incident; and
several of the document's own governance mechanisms (FR28 growth vs. FR25a shrink, FR42's no-lock
guarantee vs. `deferred-work.md`'s continued existence as a shared file) point in opposite directions
without a stated point of reconciliation. The scope grew from one skill to a ten-skill infrastructure
program without the document ever isolating the small, mostly-already-built slice (FR7–FR13, FR17–FR21)
that would actually test whether "complete plan, literal execution" beats what came before — and it says
so itself, in its own open questions: the adversarial pass was "closed... flagged as unspent."
