---
title: "Bagual Skills v2"
status: final
created: 2026-08-04
updated: 2026-08-04
---

# Bagual Skills v2 — PRD

> **Scope note.** This PRD opened as a single-skill document for
> `bagual-bmad-loop-runner`. During discovery the scope grew: the configuration mechanism, the
> naming scheme, the distribution model and the knowledge loop are shared infrastructure, and a
> second anchor skill (`bagual-manager`, renamed from `bagual-gerente-geral`) carries half of the
> requirements. Splitting them would duplicate the shared half into two documents that then drift.
> This is therefore a suite PRD with two anchor skills.

## 1. Context

The owner runs an autonomous implementation pipeline across several personal projects on one
machine, plus at least one project belonging to a different company with its own ticket-handling
rules, workflows and MCP servers. Until now the pipeline's orchestration layer has been
`bagual-epic-runner`: a skill that drives an epic end to end (create-story → dev-story → review →
QA gate → retrospective) from inside an agent session.

`bagual-epic-runner` works, but it orchestrates *inside a model context*. That context compacts
under load, which is where its weaknesses show. `bmad-loop` is a deterministic, script-driven
orchestrator that replaces that inner loop with a real process: it spawns sessions, enforces limits,
commits, and never forgets state because its state is on disk rather than in a context window.

Epic 22 (2026-08-03 → 2026-08-04) was the first epic delivered end to end by `bmad-loop`: 11 stories
in roughly six hours overnight. It also exposed exactly what `bmad-loop` does *not* do, and one
failure mode that only exists because it is deterministic.

**The defining property: `bmad-loop` is literal.** There is no judgment-bearing agent between the
spec and the code. A silent gap in a spec is not read as an oversight to hesitate over — it is read
as an instruction. Story 22.1's migration copied 950 rows and dropped the source tables while
omitting two live columns, because the spec described the new schema without ever inventorying the
old one. The root cause was documentary, not executional.

That property is not a defect to fix. It is the contract to design around: **if the night is
literal, the day must be complete.** The owner is available during planning and unavailable during
execution, so every ambiguity must be spent while he is present.

This PRD defines `bagual-bmad-loop-runner`: the skill that wraps `bmad-loop`, guarantees the
planning phase is complete before a run starts, supervises the run, and closes the epic afterwards —
portable across projects and organizations without editing the skill itself.

## 2. Goals

- Replace `bagual-epic-runner` as the orchestration layer for epics, with better outcomes rather
  than merely cheaper ones.
- Guarantee that a run only starts from a planning artifact that has been audited with the owner
  present.
- Close the epic after the loop finishes: verification, retrospective, knowledge capture, and debt
  triage — none of which `bmad-loop` does on its own.
- Make the skill generic. Everything project- or organization-specific lives in project files the
  skill reads at startup.

## 2.0 Delivery sequence — decided 2026-08-04

The document specifies nine skills. It ships in two bets, not one.

**First increment — proves the thesis.** The loop-plus-closure half: the planning gate (FR7–FR12a),
run supervision (FR13–FR16a), and epic closure (FR17–FR21). Most of its parts already exist; what is
missing is the wrapper and the closure sequence. If "if the night is literal, the day must be
complete" is wrong, this is where it fails, cheaply.

**Second increment — rides on the first.** `bagual-wiki`, `bagual-semgrep-rules`, and the
`bagual-manager` / `bagual-tickets` rewrite, plus distribution (FR31–FR33b).

This ordering exists because adversarial review pointed out — fairly — that a document which grew
from one skill to nine mid-discovery, with no named first step, is a wish rather than a plan.

## 2.1 The two anchor skills

| Skill | Who drives it | Role |
|---|---|---|
| **`bagual-manager`** (was `bagual-gerente-geral`) | Nobody — it drives itself | The central skill. Does everything in the project for the owner: reads state, decides, dispatches, records, learns. The default entry point. |
| **`bagual-bmad-loop-runner`** | The owner, directly, in a dedicated window | The only skill the owner drives by hand. Wraps `bmad-loop`, guards the planning gate, supervises the run, closes the epic. Isolated on purpose so the owner has full control over it. |

Every other `bagual-*` skill is something `bagual-manager` invokes.

## 2.2 The three persistence layers

These are distinct and must not be conflated. Each has one owner skill.

| Layer | Holds | Lives in | Owner |
|---|---|---|---|
| **Configuration** | Which stages are on, which paths, which MCP servers, which workflow variant | `.bagual/` | `bagual-manager` writes it; every skill reads its own slice |
| **Knowledge** | Code patterns, anti-patterns, product decisions, operational learnings, org rules | the wiki | `bagual-wiki` |
| **Work** | Tasks in flight, tasks done, deferred work | one file per ticket | `bagual-tickets` |

The ticket layer's intake rules are part of its value, not overhead: before a ticket is created it is
checked against what was already done or implemented, against similar existing tickets, and against
recorded product decisions — so the system stops undoing and redoing its own work.

**FR43 — Ticket states are configurable per project, and each carries its own written meaning.** One
of the owner's companies already needs a state for a situation that occurs only there. A fixed state
machine would force either a fork or a misused generic state. The configuration therefore declares
the states this project uses **and, for each one, what it means and when to move a ticket into it** —
so the meaning travels with the configuration instead of living in the owner's head, and an agent
reading the config knows how to use a state it has never seen before.

**FR42 — No shared ticket index and no lock.** Each ticket is its own file; the listing is derived on
read by scanning them. Several `bagual-manager` windows must be able to work at once (FR26), and a
shared index is a shared write target — the one thing that makes concurrent writers collide. Removing
it removes the race outright, with no lock that can go stale when a window dies. Rejected
alternatives: file locking on the index (reintroduces exactly the lock cut from the manager, and a
crashed window blocks every other one) and an append-only journal (more robust still, but more to
build for a problem the derived-listing approach already closes). The current implementation is
already halfway there — its board is documented as a derived index with a rebuild script, and the
per-ticket files are already the source of truth.

## 2.3 v2 skill roster

**Spine**

| Name | Role |
|---|---|
| `bagual-manager` | Central skill. Runs the project for the owner. Renamed from `bagual-gerente-geral`. |
| `bagual-tickets` | Work persistence and intake gate. Behaviour kept, fully rewritten in English including its data files. |
| `bagual-wiki` | **New.** Creates and maintains the knowledge layer. Bootstraps from an existing `CLAUDE.md`/`AGENTS.md` plus a codebase scan rather than from an empty tree. |

**Epic pipeline**

| Name | Role |
|---|---|
| `bagual-spec-gate` | Audits the epic and its stories before any run. Owns the grounding rule (FR22). |
| `bagual-bmad-loop-runner` | **New.** Runs `bmad-loop`, supervises idle, closes the epic. The only skill the owner drives directly. |

**Support**

| Name | Role |
|---|---|
| `bagual-worktree` | Ad-hoc worktree creation for parallel manager windows. Pool mode dropped — superseded by `bmad-loop`'s native isolation. |
| `bagual-qa-setup` · `bagual-qa-builder` · `bagual-qa-run` | The QA stage. Optional per project (FR5). |
| `bagual-semgrep-rules` | **New.** Turns a green-sealed anti-pattern into a real mechanical rule and marks the ledger entry automated. This step has never had an owner — which is why five Semgrep scripts exist and zero rules do. |

**Retired or out of scope for v2**

| Name | Why |
|---|---|
| `bagual-epic-runner` | Replaced by `bagual-bmad-loop-runner`. |
| `bagual-qa-cowork` | Tied to a specific external tool, not part of the generic suite. |
| `bagual-template-init` · `bagual-template-sync` · `bagual-template-push` | **Parked, not decided.** These serve the owner's own local template projects. Deliberately left out of this round's discussion rather than ruled out — revisit before v2 ships. |
| `bagual-import-planilhas` | Project-specific to gorioapp. Stays where it is. |

## 3. Non-Goals

- Replacing `bmad-loop`. This skill orchestrates it; it does not reimplement it.
- Becoming a `bmad-loop` plugin. Explicit owner decision: this is a separate skill that invokes
  `bmad-loop run`, not a manifest dropped into `.bmad-loop/plugins/`.
- Rewriting the skills that already work. v2 is a re-architecture of naming, configuration,
  language and distribution — not a from-scratch reimplementation of every skill's logic.
- Migrating the existing Portuguese wiki. Existing content stays as-is; only new artifacts produced
  by this skill are English.
- Parallel epic execution. `bmad-loop`'s `max_parallel` clamps to 1 today; multi-track parallelism
  is out of scope.
- Replacing `bagual-spec-gate`. That skill is a dependency this one invokes and enforces.

## 4. Users

A single user — the owner — operating in two distinct shapes:

- **Home projects.** Several near-identical projects on one machine. Usage shape is effectively
  uniform; configuration differences are cosmetic.
- **Client / other-company projects.** Different rules for handling tickets, different workflows,
  different MCP servers available. The skill must adapt without being edited.

There is no second operator, no onboarding surface, and no multi-tenant concern. What there *is* is
a portability concern: the same skill file must behave correctly in organizations whose rules it
does not know at authoring time.

## 5. Product Concerns

These drive the requirements below.

| Concern | Why it matters here |
|---|---|
| **Literal execution** | No agent judgment between spec and code. Planning completeness is a safety property, not a quality preference. |
| **Portability across orgs** | Rules, workflows and MCPs differ per project. Any literal in the skill is a bug the moment it travels. |
| **Knowledge continuity** | Discovered patterns must be captured and must reach the next spec, or every night relearns yesterday. |
| **Unattended failure** | The owner is asleep. Escalations, stalls and irreversible risks need defined disposal, not a paused terminal nobody reads. |
| **Cost shape** | Management should be thin; the spend belongs in planning and execution, not in an orchestrator burning context. |

## 6. What already exists (do not rebuild)

Investigation on 2026-08-04 against this project's installed `bmad-loop` found several capabilities
that overlap with what was originally imagined as new construction. The skill consumes these; it
does not reimplement them.

| Capability | Where | Status here |
|---|---|---|
| Git worktree isolation, branch per story, merge-back, gitignored-config seeding | `policy.toml [scm]` | Exists. Currently `isolation = "none"`. |
| Deferred-work triage | `bmad-loop sweep` | Exists. Never run in this project. |
| Deterministic gates before commit | `policy.toml [verify] commands` | Exists. Empty. |
| Stories authored upfront, dispatched by folder + id | `policy.toml [stories] source = "stories"` | Exists. Currently `"sprint-status"`. |
| Per-stage model overrides (dev / review / triage) | `policy.toml [adapter.*]` | Exists. Unused. |
| Retrospective signal | `policy.toml [gates] retrospective` | Partial — `notify` only; `auto` unsupported in v1. |
| Escalation resolution, decisions queue | `bmad-loop resolve`, `bmad-loop decisions` | Exists. |

**Consequence, corrected after review:** `bmad-loop`'s worktree mode seeds **adapter CLI/MCP config
files only** by default. `bagual-worktree` additionally replicates every gitignored dependency tree,
env file and secret, plus the source checkout's uncommitted diff — none of which `bmad-loop` does
unless `worktree_seed` is configured explicitly. So the pool lifecycle is genuinely superseded, but
**the hydration is not**. Either `worktree_seed` is configured per project as part of `init`, or
`bagual-worktree`'s hydration stays in the loop's path. An earlier version of this document claimed
full equivalence; that was overstated.

## 7. Functional Requirements

### 7.1 Initialization and configuration

**FR1 — Init mode on first use.** On invocation, the skill checks for its configuration in the
project. If absent or incomplete, it enters an interactive init before doing any work. Init never
runs silently and never guesses a value it could ask for.

**FR2 — Configuration lives in `.bagual/` at project root.** This folder holds *configuration only*:
which optional stages are enabled, which paths this project uses, which MCP servers are available,
which workflow variant applies. It does not hold knowledge.

**FR3 — Organization rules live in the project wiki, not in `.bagual/`.** The wiki belongs to the
project; the rules that govern that project belong with it. Rules are knowledge, subject to the same
lifecycle, grounding and grep-native retrieval as everything else in the wiki.

**FR4 — Configuration merge follows BMad's `customize.toml` semantics.** Base defaults ship with the
skill; team overrides and personal overrides layer on top. The exact algorithm and its guarantees are
specified once, in **FR39** — deliberately not restated here. (An earlier draft stated the merge
rules in both places; epic design caught the duplication.)

**FR5 — Every optional stage is configuration-driven.** The QA gate is the motivating case: this
project has heavy frontend and runs it; another project may have no QA skill installed at all. The
skill must run correctly with the stage absent, and must not treat its absence as failure.

**FR6 — No project-specific literal in the skill.** Branch names, deploy commands, package names,
document paths, environment identifiers and Supabase references are all configuration. A literal
that survives into the skill body is a defect.

### 7.2 Pre-flight — the planning gate

**FR7 — All stories are authored before the run.** The epic's stories are written while the owner is
present, not derived overnight at dispatch time. This is the central change: today the artifact the
loop executes is created when nobody can be asked about it.

**FR8 — The run is driven from the sprint queue, and the epic breakdown is the contract.** Revised
2026-08-05 after checking what actually produces what.

The original version specified `bmad-loop`'s stories mode, which consumes a spec folder holding
`stories.yaml` + `SPEC.md`. That mode exists, but **no installed skill produces `stories.yaml`** — the
component that emits it is not part of this installation. Specifying a format with no producer is how
a plan becomes a wish.

The queue is therefore the sprint-status queue, which does have a producer and is already proven in
this project.

**Why this does not weaken FR7, which was the reason stories mode was chosen in the first place.** The
executor's own first step compiles its context from the **epic breakdown document and its stories** —
the artifact authored while the owner is present and audited by the gate. It then investigates the
codebase and writes an *implementation plan* from that contract. So:

- Requirements are authored by the owner, upfront. Unchanged.
- What the executor writes overnight is a derived plan, not invented intent — and it halts rather than
  fantasize when the contract has a gap.
- Story 22.1 is consistent with this reading: the executor did not invent the missing columns, it
  faithfully executed an upstream document that never inventoried them. The fix was always upstream.

**What the gate audits therefore stays exactly as FR9 says:** the stories in the epic breakdown, not a
separate file format. The dial `per-story-spec-approval` remains available if the owner ever wants to
approve each derived plan before it executes — at the cost of the unattended run.

**FR9 — `bagual-spec-gate` audits the stories, not only the epic document.** The story is the
executable contract. Auditing the epic doc while the stories are generated later leaves the actual
contract ungoverned — the structural gap that let Story 22.1's column omission reach a `DROP TABLE`.

⚠️ **Evidence caveat, added after adversarial review.** The gate has **never prevented anything**.
Git history settles it: the destructive migration was committed at 14:23 on 2026-08-03 (`ad4f1fc5`);
the spec-gate artifact for that same epic first appeared at 19:55 (`de1df602`), five and a half hours
later. The gate was *created because of* 22.1 and then ran as a post-hoc audit of the same epic — it
was never in the preventive position this requirement puts it in. What it did do in that one real
run is find a genuinely new, uncatalogued issue before code (`on delete cascade` erasing paid expense
history), which became a product decision. That is real evidence of usefulness, but of a different
kind. **Treat FR9–FR11 as a reasoned bet, not a validated control**, and treat the first epic that
runs through it as the actual test.

**FR10 — Open questions are resolved with the owner, synchronously, before the run.** The gate's
`Block If` mechanism never infers product behavior. Every gap becomes a literal question with a
literal answer recorded. This is the moment the owner exists; it is not to be deferred.

**FR11 — No `PASS`, no run.** The skill refuses to start `bmad-loop` for an epic whose gate verdict
is not literally `PASS`. Refusal is explicit and names the blocking gap.

**FR12 — Story staleness is handled by re-running the gate, not by defensive upfront design.** If
execution changes the terrain, whoever adjusts a story spec starts from a mostly-complete artifact,
and a fast re-run of the gate verifies the adjustment. [ASSUMPTION] The re-run is scoped to the
affected stories rather than the whole epic.

**FR12a — The gate's verdict is bound to the exact stories it audited.** Raised by review: FR12
described the intended workflow but nothing forced it. A story edited by hand after `PASS` would
still satisfy FR11, because FR11 only checks that a `PASS` exists. That reproduces Story 22.1's root
cause one layer up — an artifact trusted for a state it no longer describes. The verdict therefore
records a fingerprint of each story it audited, and a mismatch at run time invalidates the `PASS`
for those stories rather than warning about it.

### 7.3 Run supervision

**FR13 — Worktree isolation is on.** Runs execute under `isolation = "worktree"`. Rationale: with
`"none"`, a concurrently dispatched agent writing to the same checkout collides silently. This
happened during Epic 22, produced duplicated live code, and the test suite stayed green throughout —
a passing suite is not evidence of no collision.

**FR13a — The other side of that collision is also governed.** Raised by review: the Epic 22
collision had two participants, and FR13 only hardens one of them. The other was an agent the
*manager* dispatched into the same checkout while a run was live. Isolating the loop while leaving
manager dispatches to the same human judgement that already failed once fixes half a bug. Before
dispatching any agent that writes to the repository, the manager checks for a live run and either
waits or allocates its own worktree — mechanically, not by remembering.

**FR14 — Resident but idle.** The skill stays open for the duration of a run, in its own dedicated
window, but **does not consume tokens while nothing is happening**. It waits on an event — a hook, a
completion signal, a marker on disk — and wakes only when there is something to decide. A supervisor
that tails a log and narrates it is exactly the context-burning behavior this whole redesign exists
to remove. It observes through `bmad-loop`'s own surfaces (`status`, the run directory, the
ATTENTION file), never by holding a live conversation with the run.

**FR15 — Escalations have defined disposal.** A `CRITICAL` escalation pauses the run by design.
The skill records it, surfaces it to the owner for the next interactive session, and never invents
an answer to resume overnight. `bmad-loop resolve` is the interactive path back in.

**FR16 — Stalls and budget trips are reported, not absorbed.** A session that stalls or trips its
token budget produces a named outcome in the closing report, never a silent retry that hides cost.

🔴 **FR16a — Silence is not success. The watcher covers every terminal state, not just the happy
path.** A watcher that matches only the attention signal stays **completely silent** through a crash,
a hang, or a budget kill — and silence is indistinguishable from "still running". A supervisor built
that way would sit quietly from 2am until morning while the night was already dead.

The watcher's filter must therefore cover, at minimum: the attention signal, run completion, process
death, stall signatures, and budget termination. The test to apply when writing it: *if this run
crashed right now, would my watcher emit anything?* If not, the filter is too narrow — widen it and
accept the noise. This is a correctness requirement, not a nicety; it was found while proving FR14
and would not have surfaced from design alone.

### 7.4 Epic closure — the gap this skill exists to fill

`bmad-loop` closes stories. It does not close epics. In Epic 22 all 11 stories reached `done` and
the epic sat `in-progress` for about ten hours, visually indistinguishable from an epic mid-flight.

**FR17 — Triage deferred work.** The skill runs `bmad-loop sweep` (or equivalent triage) over
`deferred-work.md` before an epic can be considered closed. Epic 22's own reviews found four
atomicity risks and one capability regression — including one the review itself called
"genuinely irreversible" — and every one of them sat in the file untouched because nothing forced a
read. A review finding recorded as debt is not a review finding resolved.

**FR18 — Run the QA gate when configured.** Integration-level verification of the assembled epic,
not per-story test suites. Epic 22's four new screens had never been seen in a browser until a human
ran the gate manually. Skipped cleanly when the project has no QA stage configured (FR5).

**FR19 — Run the retrospective.** Not optional decoration: it is what turns "every story passed its
own review" into "the epic as a whole is done", and it is the entry point for FR20.

**FR20 — Capture knowledge into the wiki.** This is the highest-value requirement in the document.
The knowledge-capture loop's entry point is the retrospective, and `bmad-loop` does not run one —
therefore everything the agents discover during an unattended night is currently lost unless a human
closes the epic by hand. The skill closes that circuit.

**FR21 — An epic reaches `done` only after the closure checklist passes.** Partial closure is a
named, reported state, never a silent one.

### 7.5 The knowledge loop

**FR22 — One grounding rule, one owner.** The wiki-grounding procedure currently exists as three
independently authored copies (`bmad-create-story.toml`, `bmad-dev-auto.toml`, `bagual-spec-gate`
Step 7). `bmad-dev-auto.toml` states in its own text that it had to restate the rule because the
loop's story format does not receive create-story's version. Three texts of one rule will diverge.
`bagual-spec-gate` becomes the single owner; every other consumer references it.

**FR23 — Grounding is embedded, distilled, and signals absence.** The searched slice is written into
the spec itself with each source path, never a generic pointer and never the full source text. When
a topic the spec touches has no matching wiki entry, that absence is stated explicitly. Absence is a
signal, not silence.

**FR24 — Spec debt is harvested into standing rules.** When execution escalates because it had to
ask, that is a planning failure by definition, not an execution failure. The escalation records what
the spec left implicit, the exact question, and an actionable generalization. The gate harvests
these and enforces them on subsequent specs. This is the mechanism by which the ruler grows without
anyone maintaining it.

**FR25a — The wiki is governed as a liability, not an asset.** Adopted directly from BMad's own
reversal (see `research/03-bmad-philosophy.md`): they measured the accumulate-documentation model,
found it degraded agent performance, and deprecated their own doc-generation skills. Three
disciplines become requirements of `bagual-wiki`:

1. **The pruning test.** Every line must answer: *would removing this change agent behaviour?* If
   not, it does not go in and does not stay in.
2. **Trust status on every entry.** `verified` (a human confirmed it) or `inferred`, plus source and
   date. An unconfirmed claim is stored visibly as inference and never laundered into fact.
3. **A curation pass ends the knowledge base the same size or smaller, never larger.**

Excluded by rule: code paraphrase, file maps, overview/tour documents, ecosystem defaults, history
narration, inference dressed as fact, aspirational future state.

Rationale worth keeping in front of whoever builds this: *"Wrong context is worse than no context. An
agent with no documentation explores and finds the truth. An agent with a stale document confidently
follows it off a cliff. Staleness is not a cosmetic problem; it is the failure mode."*

**FR25b — Pruning needs a trigger, and `verified` needs an expiry.** Two gaps raised by review:

1. **Growth is automatic (FR28 records every correction); shrinkage was discretionary.** A system
   that only grows by construction will grow. The pruning pass therefore fires on a defined event —
   at minimum every epic closure, alongside the retrospective — not when someone remembers.
2. **A `verified` entry currently stays verified forever.** That is exactly the "stale document
   followed off a cliff" case the rationale above warns about, left open for the entries the system
   trusts most. Verification carries a date, and an entry whose date is old enough, or whose subject
   was touched by later work, drops back to `inferred` until re-confirmed.

Our wiki is not the thing BMad deprecated — theirs was auto-generated and always-loaded, ours is
curated and fetched on demand by grep, which already avoids the per-session tax. But it carried none
of the three defences above, which left it fully exposed to the staleness failure mode.

**FR25 — New artifacts are English.** The skill, its configuration, and everything it produces are
written in English. Pre-existing Portuguese wiki content is left untouched; the language boundary is
"from this skill onward", not a migration.

### 7.6 `bagual-manager` — the central skill

**FR26 — `bagual-manager` is the default entry point.** Renamed from `bagual-gerente-geral`. It runs
the project for the owner: reads state, prioritizes, dispatches, reviews, records. Everything except
`bagual-bmad-loop-runner` is invoked through it. The owner should not need to know which skill does
what — that routing is the manager's job.

**FR27 — Communication contract.** The manager's output is written to be read on a phone, fast.
- Objective and short by default. A conclusion first, then the support.
- Lists over paragraphs. Scannable at a glance.
- **No abbreviations, no internal codes, no references to prior numbered items.** The owner is never
  obliged to remember what "D1" or "FR7" meant. Every message is self-contained.
- Detail on demand only. The owner asks to expand; the manager does not pre-emptively expand.

This is a functional requirement, not a style preference: an unreadable report from an autonomous
overnight system is functionally equivalent to no report.

**FR28 — Self-learning from correction.** When the owner corrects the manager — "in this project we
do it this way", "we commit `.env` files here", "we don't use that", "you got this wrong again" —
the manager records the lesson itself, in the right place, without being told where. The owner must
never teach the same thing twice.

**FR29 — The manager knows the skill map and where each skill's configuration lives.** Routing a
lesson to the correct file is what makes FR28 real rather than aspirational. Worked example: at one
company, opening a ticket via `bagual-tickets` must first query the ClickUp MCP server to pull the
upstream ticket's data and populate the local ticket from it. The manager knows this belongs in that
skill's configuration for that project, and writes it there — it does not memorize it in a session
that ends.

**FR30 — Learned rules are configuration or knowledge, never a skill edit.** A lesson lands in
`.bagual/` when it is configuration (which MCP, which workflow, which stage is on) or in the wiki
when it is knowledge (a project rule, a pattern, an anti-pattern). It never lands as an edit to the
skill body — that is what breaks portability.

### 7.7 Distribution

**FR31 — v2 lives in the `bagual-skills` repository, under a new `v2/` folder.** Existing skill
names are reused inside it. v1 stays on disk untouched for reference.

**FR32 — Installation is copy-and-run.** The owner copies the skill folder into the target project,
runs `init`, and it works. An install script may exist as convenience, but the primary path must not
depend on one — a folder that only works through a script is a folder that stops working when the
script rots. [ASSUMPTION] "Copy into place" means into the project's skills directory, matching
where `bagual-*` skills already live.

**FR33 — A skill carries no state from the machine it was copied from.** After copy, everything
project-specific comes from `init` + `.bagual/`. This is the mechanical test for FR6.

**FR33a — `init` owns every file it must touch, including outside `.bagual/`.** Raised by review:
FR14's supervision may require a harness-level hook, and worktree hydration (section 6) may require
`worktree_seed` in `.bmad-loop/policy.toml` — neither lives in `.bagual/`. A skill that installs by
copy-and-`init` but silently needs a hand-edited file elsewhere does not actually install by
copy-and-`init`. `init` must either write those files itself or state plainly what the operator has
to do, and verify it afterwards.

**FR33b — Distribution is a sync problem, not a copy problem.** The `bagual-skills` repository
already exists and already diverges: its `bagual-spec-gate` payload is roughly an eighth the size of
the live version in this project. A one-time copy is how that happened. Whatever v2 ships with must
answer how a skill improved in one project reaches the others, or `v2/` becomes archaeology the same
way the current payload did.

### 7.8 Authoring standard

v2 is written against BMad's own documented skill-quality doctrine rather than a house style invented
for the occasion. Full extraction in `research/01-bmad-skill-authoring-craft.md` and
`research/02-bmad-infrastructure.md`.

**FR34 — v2 skills are built through `bmad-workflow-builder`.** It carries the doctrine
(`references/skill-quality-principles.md`), the build procedure, the field schema and the skeleton,
and it audits against the same file it teaches from. Hand-rolling the skills means re-deriving a
standard that already exists and is enforced.

**FR35 — Every instruction earns its place.** The governing test: *would a model do this correctly
without being told? If yes, cut it.* An instruction exists to prevent a failure that would otherwise
happen — not to restate competence the model already has.

**FR36 — Size discipline.** `SKILL.md` targets ~80 lines, ceiling ~130; up to ~250 when genuinely
multi-branch. Past that, content lifts into `references/`. Carve-outs split on **size**, not on stage
count; each must read standalone because compaction can drop `SKILL.md` mid-flow; and nesting is one
level deep only, never reference-to-reference chains.

**FR37 — Freedom is graded per instruction.** Judgment-heavy sections stay prose. Fragile operations
(destructive migrations, mandatory gates, state-file mutation) get exact, one-right-way steps with
explicit stop conditions. Choosing which dialect a given instruction needs is the craft; applying one
uniformly to a whole skill is the mistake.

**FR38 — Headless is designed in, not bolted on.** Own reference file, own detection, and a strict
tri-state vocabulary: `complete` (stands alone) · `partial` (artifact produced but carries open
questions or inferred critical inputs) · `blocked` (no artifact). Never invent to fill a gap — record
it. Never block on input that cannot arrive — halt with a reason. Return the smallest set of paths
the caller needs; the log carries the detail.

**FR39 — Configuration merge follows the proven algorithm exactly.** Structural, not name-aware:
scalars override, dicts deep-merge, arrays-of-tables merge by a shared `code`/`id` key with matches
replaced in place, everything else appends. **No removal primitive** — overrides only add or replace,
which keeps forks rare. Every skill that shells out to the resolver also documents, in its own text,
the manual fallback for resolving the same layers by hand, so tooling absence degrades instead of
blocking.

**FR40 — Script conventions.** Standard library only, with a PEP 723 header so `uv run` picks the
interpreter. stdout carries the machine contract as JSON; stderr carries diagnostics; the two never
mix. Exit codes distinguish failure *kind*: `0` success, `1` required input missing or unparseable,
`2` usage or state error, `3` environment failure. All persisted state is written atomically —
temp file, flush, fsync, replace. Logs append only and echo the new state back so a caller never
re-reads what it just wrote. Optional layers fail soft; required ones fail loud.

**FR41 — Configuration explains itself.** Every key documents *why*, not just *what*; enums list
their legal values inline; dangerous options carry their warning at the point of use; escape hatches
appear commented-out and copy-paste-ready; numeric defaults cite the observed behaviour that
justifies them. Where our config deliberately disagrees with an underlying tool's default, the
disagreement is explained at the point of override — the pattern that already saved this project once
when a reinstall would have silently reverted a cost-critical model pin.

### 7.9 `bagual-semgrep-rules`

Added 2026-08-05. Epic design found that the skill appeared in the roster with **no requirement
describing what it does** — a gap the reviewer pass also missed. These four close it.

The subsystem it completes already exists in fragments: the ledger seals each anti-pattern as
mechanically detectable, hybrid, or human-only; a script derives the candidate queue; another script
marks an entry automated once a rule exists. **Nothing and nobody authors the rule.** That missing
middle is why five scripts and zero rules exist today.

**FR44 — The candidate queue is a query, never a maintained list.** Candidacy is derived:
mechanically-detectable seal, entry not retired, not already automated. The skill reads that queue
rather than accepting a hand-curated backlog, so a newly sealed anti-pattern enters the queue without
anyone remembering to add it.

**FR45 — A rule is validated against the real codebase before it ships.** Two proofs, both required:
it **fires on the actual occurrence** the anti-pattern was written from, and it **does not fire** on
code the project accepts. A rule that cannot demonstrate both is not written — the anti-pattern stays
in the queue with the reason recorded. This is what stops the queue draining into rules nobody trusts.

**FR46 — Authoring closes the ledger loop.** Once a rule ships, its source entry is marked automated
and leaves the queue without being retired — the knowledge stays alive, only the enforcement moves
from prose to machine.

**FR47 — Enforcement has a defined escape hatch that never silently accepts.** A blocked change can
be recorded as a suspected false positive, with a mandatory justification, downgrading that specific
finding — never the rule, never silently. Violations accumulate as a log that curation reconciles;
enforcement itself never mutates the knowledge store directly.

### 7.10 `bagual-wiki` — creation

Added 2026-08-05. Epic design found that FR25a/FR25b govern the wiki **once it exists** but nothing
described bringing one into being. These two close it.

**FR48 — The wiki is bootstrapped from what the project already knows, not from an empty tree.** An
existing `CLAUDE.md`, `AGENTS.md` or equivalent, plus a scan of the codebase, seed the initial
entries. The bootstrap is subject to FR25a's pruning test and exclusion list **from birth** — this is
precisely where the deprecated approach went wrong, generating volume that read as thoroughness and
measurably degraded the agents consuming it. A bootstrap that produces a large wiki has failed, not
succeeded.

**FR49 — Structure serves grep-native retrieval.** Entries are typed and indexed such that the search
loop FR22 specifies — read the index, grep by term, read candidates, refine, grep again — actually
converges. No retrieval script, no tag machine, no embedding store: the structure itself is the
retrieval mechanism, and it is judged by whether that loop finds the right slice.

## 8. Non-Functional Requirements

- **Portability.** The skill must run unmodified against a project it has never seen, after init.
  Any behavior that cannot be expressed as configuration is a design failure.
- **Thin management.** Orchestration overhead stays small. The spend belongs in planning (owner
  present, judgment-heavy) and execution (Sonnet, deterministic), not in a supervising context that
  compacts.
- **Determinism where available.** Prefer a `bmad-loop` subcommand or a script over an instruction
  asking a model to remember. Prose that promises to obey is the failure mode this whole system
  exists to reduce.
- **Unattended safety.** No destructive action, no production write, and no merge to a protected
  branch happens without the owner present. Work ends at a commit on the development branch.
- **Graceful absence.** A missing optional stage, a missing MCP server, or a missing config key
  degrades to a reported skip, never a crash and never a silent pass.

## 9. Success Metrics

| Metric | Target |
|---|---|
| Epics reaching `done` without manual closure intervention | Rising toward 100% |
| Overnight escalations caused by spec gaps | Falling toward 0 |
| Review findings resolved before epic closure | 100% (triaged, not necessarily fixed) |
| Knowledge entries captured per epic | Non-zero for every epic |
| Standing rules promoted from spec debt | Rising, then plateauing as the ruler matures |

**Counter-metrics** — watch these or the targets above get gamed:

| Counter-metric | Why |
|---|---|
| Owner hours spent in the planning gate | If planning cost explodes, the bottleneck simply moved to the owner |
| Stories authored but never executed | Upfront authoring wasted on epics that got cut |
| Gate `PASS` verdicts followed by CRITICAL escalations | A gate that passes and then fails is worse than no gate — it manufactures false confidence |
| Rules promoted but never triggered | Ruler growing with noise instead of signal |

## 10. Open Questions

**Resolved during discovery** (kept for the record): supervision is resident-but-idle (FR14); stories
are authored by the existing PM/story skills (FR7); gate re-run is scoped to the affected story with
the system judging the boundary (FR12); the runner owns the retrospective (FR19); distribution is
`bagual-skills/v2` by copy + `init` (FR31–FR32); `bagual-gerente-geral` becomes `bagual-manager` and
stays central (FR26).

Still open:

1. **Does gorioapp itself migrate to v2, and when?** Building v2 in the `bagual-skills` repo while
   gorioapp keeps running v1 means two live versions. Deferred by explicit owner decision.
2. **Inherited debt.** 54 tickets carry a track assigned by a classifier that has since been retired
   and have never been re-triaged. The Semgrep subsystem is dormant — five scripts, zero rules, no
   hook, no binary installed. Both belong to the gorioapp project rather than to the skills.
   Deferred by explicit owner decision.
3. **Template skills.** `bagual-template-init` / `sync` / `push` are parked, not ruled out. Revisit
   before v2 ships.
4. **~~The mid-run wake mechanism (FR14).~~** **Closed 2026-08-04** — proven by live test, see above.

### Reviewer pass — run 2026-08-04

Four parallel reviewers: rubric walker, adversarial, edge-case hunter, evidence verifier. Full
reviews in `review-rubric.md`, `review-adversarial.md`, `review-edge-cases.md`, `review-evidence.md`.

Findings that changed the document: the FR14 retraction, the FR9 evidence caveat, the corrected
worktree-equivalence claim, and five new requirements (FR12a, FR13a, FR25b, FR33a, FR33b).

Findings accepted but not yet applied: no glossary; FR42 sits in §2.2 outside §7's numbering; the
assumptions index does not round-trip with the inline tags; FR27 and the thin-management NFR assert
bounds without numbers where FR36 gives them. These are traceability debt for whoever builds from
this, not blockers.

### Resolved during discovery

Kept for the record — supervision is resident-but-idle with a proven mechanism (below); stories are
authored by the existing PM/story skills; gate re-run is scoped to the affected story with the system
judging the boundary; the runner owns the retrospective; distribution is `bagual-skills/v2` by copy
plus `init`; `bagual-gerente-geral` becomes `bagual-manager` and stays central; self-learning records
every correction automatically with no manual marking step.

✅ **FR14's wake mechanism — CLOSED, proven by live test on 2026-08-04.**

Two corrections got the document here, and both are worth keeping visible:

1. An earlier version claimed the mechanism was `bmad-loop`'s own hook. **That was wrong.** The hook
   is gated on environment variables set only on sessions the orchestrator itself spawned, and is
   silently inert in an ordinary interactive window — exactly the case FR14 describes. It solves the
   orchestrator's problem, not the supervisor's.
2. The actual mechanism does not involve that hook at all. It is two harness primitives, tested
   together against a simulated run that raised two mid-run attention signals and then finished:

| Need | Primitive | Result |
|---|---|---|
| Wake **during** the run, once per occurrence | A watcher process streaming the run directory; each matching line becomes an event | ✅ 2 of 2 signals delivered |
| Wake **at** the end of the run | The run launched as a background command; the session is re-invoked on its exit | ✅ delivered |

**Zero tokens are consumed between events.** The supervising session holds nothing open and reads
nothing while waiting — the watcher is an ordinary process outside the model's context.

The end-of-run signal arrived on **two independent paths** (the watcher's terminal event and the
background command's exit). Both are kept: the redundancy costs nothing and covers the case where one
is missed.

### Manager capability triage — settled

24 capabilities of the current `bagual-gerente-geral` were reviewed one by one with the owner.

**Cut (6):** singleton session lock · morning briefing · self-healing of its own skills ·
percentage-of-decisions-ratified metric · sampling review of historical auto-assigned tracks ·
breaking a large request into epics (delegated to the PM agent instead).

**Disabled by default, configurable (2):** proactive work on an empty queue · scheduled self-wake.

**Moved into `init` (1):** the branch and environment promotion flow, because it is company-specific.

**Kept (14):** crash detection and reconciliation · orphan dispatch sweep · append-only diary ·
deciding ambiguity without waking the owner · precedent-gated action with parking otherwise · never
repeating a correction the owner already made · owner ratification in the following session ·
spec/epic work waiting for the owner · product-change detection updating design documents
(simplified) · stuck-ticket warning · file-mediated dispatch · quota tracking with automatic stop ·
retrospective debt becoming a ticket · skill defects becoming tickets.

## 11. Assumptions

- [ASSUMPTION] `bmad-loop`'s stories mode is production-ready in the installed version; it is
  documented in `policy.toml` but has never been exercised in this project.
- [ASSUMPTION] One epic at a time. `max_parallel` clamps to 1, so no parallelism design is needed.
- [ASSUMPTION] "Copy into place" means into the project's skills directory, matching where `bagual-*`
  skills already live (FR32).

## 12. Research grounding

Three parallel research passes ran on 2026-08-04; reports live in `research/` beside this document
and are the evidence behind sections 7.5–7.8.

| Report | Covers |
|---|---|
| `research/01-bmad-skill-authoring-craft.md` | Skill structure, the `SKILL.md` contract, headless design, instruction style, state and handoff, 12 transferable techniques |
| `research/02-bmad-infrastructure.md` | The customization resolver and its exact merge rules, override surface ranked by leverage, config layering, script conventions, the hook coordination model, `policy.toml` as a config-design model |
| `research/03-bmad-philosophy.md` | The problem BMad states it solves, why documents beat conversation memory, why the two-phase split (and when it is not worth it), why personas, the full deprecation table, and open community critique |

Two findings changed decisions rather than merely supporting them:

1. **BMad reversed its own documentation-as-asset model after measuring it.** That produced FR25a.
2. **The wake mechanism for an idle supervisor already exists and runs.** That closed the sharpest
   open question in the document.

One finding is recorded as a caution rather than a decision: two substantial community critiques of
BMad's core design sit unanswered in public. Their content argues *for* the gates this PRD
specifies — superficial fixes passing review, and the cost of removing forced elicitation — but they
are one-sided criticism, not settled trade-offs, and are logged as such.
