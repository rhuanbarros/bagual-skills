---
stepsCompleted: ['step-01-validate-prerequisites', 'step-02-design-epics', 'step-03-create-stories', 'step-04-final-validation']
inputDocuments:
  - _bmad-output/planning-artifacts/prd-bagual-bmad-loop-runner-2026-08-04/prd.md
  - _bmad-output/planning-artifacts/prd-bagual-bmad-loop-runner-2026-08-04/research/01-bmad-skill-authoring-craft.md
  - _bmad-output/planning-artifacts/prd-bagual-bmad-loop-runner-2026-08-04/research/02-bmad-infrastructure.md
  - _bmad-output/planning-artifacts/prd-bagual-bmad-loop-runner-2026-08-04/research/03-bmad-philosophy.md
---

# Bagual Skills v2 - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for Bagual Skills v2, decomposing the
requirements from the PRD into implementable stories.

No Architecture document exists for this effort, and none is required: PRD §7.8 (authoring standard),
§6 (capabilities consumed rather than rebuilt) and research report 02 (configuration merge, script
conventions, coordination model) together carry what an architecture document would otherwise hold.
Confirmed with the owner 2026-08-05.

No UX design contract exists and none applies — this is a suite of terminal skills with no visual
surface.

**Delivery sequence is already decided (PRD §2.0) and constrains epic ordering:**
- **First increment** — loop + closure (FR7–FR21). Proves the thesis; most parts already exist.
- **Second increment** — wiki, semgrep rules, manager/tickets rewrite, distribution.

## Requirements Inventory

### Functional Requirements

**Initialization and configuration**

FR1: On invocation, a skill checks for its configuration in the project; if absent or incomplete it enters an interactive init before doing any work, and never guesses a value it could ask for.
FR2: Configuration lives in `.bagual/` at project root and holds configuration only — enabled stages, paths, available MCP servers, workflow variant.
FR3: Organization rules live in the project wiki, not in `.bagual/`, and follow the same lifecycle and retrieval as all other knowledge.
FR4: Configuration merge follows BMad's `customize.toml` semantics — skill defaults, then team overrides, then personal overrides.
FR5: Every optional stage is configuration-driven; the skill runs correctly when a stage is absent and never treats absence as failure.
FR6: No project-specific literal survives in a skill body — branch names, deploy commands, package names, document paths and environment identifiers are all configuration.

**Pre-flight — the planning gate**

FR7: All of an epic's stories are authored before the run, while the owner is present.
FR8: The run is driven from the sprint queue; the epic breakdown document and its stories are the contract the executor compiles its context from. *(Revised 2026-08-05 — the originally specified spec-folder mode has no producer in this installation.)*
FR9: `bagual-spec-gate` audits the stories themselves, not only the epic document.
FR10: Open questions are resolved with the owner synchronously before the run; product behaviour is never inferred to close a gap.
FR11: The skill refuses to start a run for an epic whose gate verdict is not literally `PASS`, and the refusal names the blocking gap.
FR12: Story staleness is handled by re-running the gate on the affected stories, not by defensive upfront design.
FR12a: The gate verdict records a fingerprint of each story it audited; a mismatch at run time invalidates the `PASS` for those stories rather than warning.

**Run supervision**

FR13: Runs execute under worktree isolation.
FR13a: Before dispatching any agent that writes to the repository, the manager mechanically checks for a live run and either waits or allocates its own worktree.
FR14: The supervising skill stays resident but idle, consuming no tokens between events, waking only on a signal.
FR15: A `CRITICAL` escalation is recorded and surfaced for the owner's next interactive session; the skill never invents an answer to resume overnight.
FR16: A session that stalls or trips its token budget produces a named outcome in the closing report, never a silent retry.
FR16a: The watcher's filter covers every terminal state — attention, completion, process death, stall, budget termination — because silence is indistinguishable from still-running.

**Epic closure**

FR17: Deferred work is triaged before an epic can be considered closed.
FR18: The integration QA gate runs when the project has that stage configured, and is skipped cleanly when it does not.
FR19: The retrospective runs as part of closure.
FR20: Knowledge discovered during the run is captured into the wiki — the circuit `bmad-loop` leaves open.
FR21: An epic reaches `done` only after the closure checklist passes; partial closure is a named, reported state.

**The knowledge loop**

FR22: One grounding rule with one owner (`bagual-spec-gate`); every other consumer references it rather than restating it.
FR23: The searched knowledge slice is embedded in the spec, distilled, with source paths; absence of knowledge on a touched topic is stated explicitly.
FR24: Spec debt raised by execution escalations is harvested into standing rules the gate then enforces.
FR25: The skills, their configuration and everything they produce are written in English; pre-existing Portuguese wiki content is left untouched.
FR25a: The wiki is governed as a liability — a pruning test on every line, a `verified`/`inferred` trust status with source and date, and a curation pass that ends the knowledge base the same size or smaller.
FR25b: Pruning fires on a defined event (at minimum every epic closure) and `verified` entries expire back to `inferred` when stale or when later work touched their subject.

**`bagual-manager`**

FR26: `bagual-manager` is the default entry point and routes all work except `bagual-bmad-loop-runner`.
FR27: Manager output is objective, conclusion-first, list-shaped, self-contained, and free of abbreviations, internal codes and references to prior numbered items; detail expands only on request.
FR28: Every owner correction is recorded automatically, in the right place, without the owner marking it.
FR29: The manager knows the skill map and where each skill's configuration lives, so a lesson is routed to the correct file.
FR30: A learned rule lands in `.bagual/` (configuration) or the wiki (knowledge), never as an edit to a skill body.

**Distribution**

FR31: v2 lives in the `bagual-skills` repository under a new `v2/` folder, reusing existing skill names.
FR32: Installation is copy the folder into place and run `init`; an install script is convenience, never the only path.
FR33: A copied skill carries no state from its source machine; everything project-specific comes from `init` and `.bagual/`.
FR33a: `init` owns every file it must touch, including files outside `.bagual/`, or states plainly what the operator must do and verifies it afterwards.
FR33b: Distribution answers how a skill improved in one project reaches the others; a one-time copy is what caused the existing payload to diverge.

**Authoring standard**

FR34: v2 skills are built through `bmad-workflow-builder`, which carries and audits the doctrine.
FR35: Every instruction earns its place — a model that would do it correctly unprompted needs no instruction.
FR36: `SKILL.md` targets ~80 lines with a ~130 ceiling (~250 when genuinely multi-branch); carve-outs split on size, read standalone, and nest one level only.
FR37: Freedom is graded per instruction — prose for judgment, exact steps for fragile operations.
FR38: Headless mode has its own reference file, its own detection, and a strict `complete`/`partial`/`blocked` vocabulary; it never invents to fill a gap and never blocks on input that cannot arrive.
FR39: Configuration merge is structural with no removal primitive, and every skill documents the manual fallback for resolving the same layers by hand.
FR40: Scripts are stdlib-only with PEP 723 headers, JSON on stdout, diagnostics on stderr, distinct exit codes by failure kind, atomic writes, and append-only logs that echo new state.
FR41: Configuration explains itself — why not just what, legal enum values inline, warnings at the point of use, commented-out escape hatches, justified numeric defaults, and deviations from tool defaults explained where they occur.

**`bagual-tickets`**

FR42: No shared ticket index and no lock — each ticket is its own file and the listing is derived on read.
FR43: Ticket states are configurable per project, and the configuration declares both the state and a written explanation of when and how to use it.

**`bagual-semgrep-rules`** *(added 2026-08-05 — epic design found this skill had no requirements at all)*

FR44: The candidate queue is derived by query (detectable seal, not retired, not already automated), never a hand-maintained list.
FR45: A rule ships only after proving both that it fires on the real occurrence the anti-pattern was written from, and that it does not fire on code the project accepts; otherwise the anti-pattern stays queued with the reason recorded.
FR46: Authoring marks the source ledger entry automated so it leaves the queue without being retired — the knowledge stays alive, only enforcement moves from prose to machine.
FR47: Enforcement has a defined escape hatch — a blocked change can be recorded as a suspected false positive with mandatory justification, downgrading that finding only, never the rule and never silently; violations accumulate as a log that curation reconciles.

**`bagual-wiki` — creation** *(added 2026-08-05 — governance existed, creation did not)*

FR48: The wiki is bootstrapped from existing project documents plus a codebase scan, subject to FR25a's pruning test and exclusion list from birth; a bootstrap that produces a large wiki has failed.
FR49: Structure is typed and indexed so the grep-native search loop converges — no retrieval script, no tag machine, no embedding store.

### NonFunctional Requirements

NFR1 (Portability): A skill must run unmodified against a project it has never seen, after `init`. Any behaviour that cannot be expressed as configuration is a design failure.
NFR2 (Thin management): Orchestration overhead stays small. Spend belongs in planning (owner present, judgment-heavy) and execution (deterministic), not in a supervising context that compacts.
NFR3 (Determinism where available): Prefer a subcommand or script over an instruction asking a model to remember. Prose that promises to obey is the failure mode this system exists to reduce.
NFR4 (Unattended safety): No destructive action, no production write and no merge to a protected branch happens without the owner present. Work ends at a commit on the development branch.
NFR5 (Graceful absence): A missing optional stage, MCP server or config key degrades to a reported skip — never a crash, never a silent pass.

### Additional Requirements

Derived from PRD §6 (capabilities consumed rather than rebuilt) and research report 02.

- Consume `bmad-loop`'s native worktree isolation for run isolation; do not reimplement it.
- Consume `bmad-loop`'s deferred-work triage rather than writing a new triage mechanism.
- Consume `bmad-loop`'s stories mode (`--spec <folder>`), currently disabled in the reference project.
- `bmad-loop` worktree seeding covers adapter CLI/MCP configs only; dependency trees, env files and uncommitted diffs need either explicit seed configuration or retained hydration.
- `bmad-loop`'s `retrospective = "auto"` is unsupported, so the retrospective is the runner skill's own responsibility.
- The wake mechanism is proven and depends on two harness primitives (a watcher process streaming the run directory, and the run launched as a background command) — not on `bmad-loop`'s own hook, which is inert outside sessions the orchestrator spawned.
- Two independent paths deliver the end-of-run signal; both are kept for redundancy.
- The `bagual-skills` repository already contains a diverging snapshot of at least one skill; any distribution design must account for existing drift, not assume a clean start.

### UX Design Requirements

Not applicable. Bagual Skills v2 is a suite of terminal skills with no visual surface, no screens and
no end-user interface. The one requirement that touches presentation, FR27, governs the readability
of the manager's text output and is tracked as a functional requirement.

### FR Coverage Map

| FR | Epic | Note |
|---|---|---|
| FR1, FR2, FR5 | Epic 1 | Init and config, minimal — only what the runner itself needs |
| FR7–FR12a | Epic 1 | The planning gate, including the gate auditing stories and binding its verdict |
| FR13, FR14, FR15, FR16, FR16a | Epic 1 | Run supervision |
| FR17–FR21 | Epic 1 | Epic closure — the gap the whole effort exists to fill |
| FR34–FR41 | Epic 1 | Authoring standard: established while writing the first v2 skill, applied by every epic after |
| FR3, FR22, FR23, FR24, FR25a, FR25b, FR48, FR49 | Epic 2 | The knowledge layer, creation through governance |
| FR44–FR47 | Epic 3 | Anti-pattern to mechanical rule |
| FR42, FR43 | Epic 4 | Ticket persistence and per-project states |
| FR13a, FR26–FR30 | Epic 5 | The manager, including the collision check that needs it to exist |
| FR4, FR6, FR31, FR32, FR33, FR33a, FR33b | Epic 6 | Portability and distribution |
| FR25 | All | English artifacts — a constraint on every epic, not a deliverable of one |

**Cross-cutting, deliberately not owned by a single epic:** FR25 (English) and FR34–FR41 (authoring
standard) constrain every epic. FR34–FR41 are mapped to Epic 1 because that is where the standard is
first established and proven; every later epic is held to it.

## Epic List

### Epic 1: Run an epic overnight and have it actually close

The owner can hand an audited epic to the runner in a dedicated window, walk away, and return to an
epic that is genuinely done — verified, retrospected, knowledge captured, deferred work triaged —
instead of one whose stories are individually `done` while the epic sits open and its reviews' debt
sits unread.

🔨 **Built by hand, with the owner present.** This epic delivers the very skill that would otherwise
run it; it is the only epic in this document that cannot be executed by the pipeline it creates.
From Epic 2 onward, the runner executes the work.

The scope is deliberately large, and the reason is bootstrap rather than affinity: everything the
skill needs in order to safely execute the *next* epic unattended must exist before that epic starts.
A runner without the closure sequence would reproduce Epic 22's outcome; a runner whose gate audits
only the epic document, not the stories, would leave the artifact that actually gets executed
ungoverned.

**FRs covered:** FR1, FR2, FR5, FR7, FR8, FR9, FR10, FR11, FR12, FR12a, FR13, FR14, FR15, FR16,
FR16a, FR17, FR18, FR19, FR20, FR21, FR34, FR35, FR36, FR37, FR38, FR39, FR40, FR41

### Epic 2: Knowledge that stays true

The owner can trust what is written down. Project knowledge is created from what the project already
knows, reaches the specs that need it, and is governed so it shrinks under curation rather than
accreting until it misleads.

**FRs covered:** FR3, FR22, FR23, FR24, FR25a, FR25b, FR48, FR49

### Epic 3: Anti-patterns become rules a machine enforces

The owner can turn a catalogued bad pattern into a rule that blocks it mechanically, instead of
relying on a reviewer remembering. Closes the middle of a pipeline whose two ends already exist.

**FRs covered:** FR44, FR45, FR46, FR47

### Epic 4: Work that never gets lost

The owner can run several windows at once without corrupting the record, and can declare the ticket
states a particular company actually needs — with the meaning of each state written down beside it.

**FRs covered:** FR42, FR43

### Epic 5: The manager that learns

The owner corrects something once and never again — the correction is recorded automatically, in the
right file, by a manager that knows where each skill's configuration lives. It also stops dispatching
writers into a checkout a run is already using.

**FRs covered:** FR13a, FR26, FR27, FR28, FR29, FR30

### Epic 6: Install anywhere, stay current

The owner can drop the suite into a project it has never seen — including one at another company with
different rules and different tooling — run the init, and have it work. An improvement made in one
project reaches the others instead of stranding a snapshot.

**FRs covered:** FR4, FR6, FR31, FR32, FR33, FR33a, FR33b

### Dependencies

Epic 1 stands alone and enables every other. Epics 2–6 each build on Epic 1 (they are executed by it)
but do not require each other:

- Epic 2 formalizes the knowledge store Epic 1 writes into; Epic 1 creates only the minimal structure
  it needs, so it does not depend on Epic 2 existing.
- Epic 3 depends on the ledger's existing seals, not on Epic 2.
- Epic 5 is where FR13a's collision check lands, because it needs a manager to live in. **Interim
  risk, accepted knowingly:** until Epic 5 ships, avoiding a write collision during a live run stays
  a discipline rather than a mechanism.

## Epic 1: Run an epic overnight and have it actually close

The owner can hand an audited epic to the runner in a dedicated window, walk away, and return to an
epic that is genuinely done. Built by hand, with the owner present — it delivers the skill that would
otherwise run it.

**Applies to every story in this epic, not repeated in each:** the skill is authored against the
BMad skill-quality doctrine (FR34–FR41) — the pruning test on every instruction, the size ceiling,
graded freedom, the headless contract, and the script conventions (standard library only, JSON on
stdout, diagnostics on stderr, distinct exit codes, atomic writes). Story 1.12 verifies it.

### Story 1.1: Launch a supervised run

As the owner,
I want to open a dedicated window, name an epic, and have the run start correctly configured,
So that I do not have to remember which orchestrator flags this project needs every single night.

**Acceptance Criteria:**

**Given** a project whose configuration declares where its planning artifacts live and which stages
are enabled
**When** the owner invokes the skill and names an epic
**Then** the orchestrator starts against that epic's queue entries
**And** it runs under worktree isolation, not in the shared checkout
**And** the launch is a background process, so the session is free immediately

**Given** an epic whose breakdown is incomplete — a queue entry with no authored story, or a story the
breakdown never lists
**When** the owner tries to start a run
**Then** the skill refuses and names what is missing, because the breakdown is the contract the
executor compiles its context from, and a gap in it is executed rather than questioned (FR7)

**Given** a project where the orchestrator's own policy still carries a default that contradicts this
project's decisions (isolation off, sprint-status mode, or an unpinned model)
**When** the skill prepares to launch
**Then** it reports the contradiction and does not launch silently against the wrong setting

**Given** the skill has never run in this project and no configuration exists
**When** it is invoked
**Then** it enters init rather than guessing a value it could ask for (FR1)

### Story 1.2: Be woken by what matters — including by failure

As the owner,
I want the supervising window to sleep until something needs a decision, and to speak up when the
run dies,
So that the night costs nothing while it goes well and does not go silent when it goes wrong.

**Acceptance Criteria:**

**Given** a run in progress with nothing needing attention
**When** time passes
**Then** the supervising session consumes no tokens and holds nothing open

**Given** a run that raises an attention signal mid-flight
**When** the signal appears
**Then** the supervising session is woken with the signal's content
**And** it is woken again on each subsequent occurrence, not only the first

**Given** a run that dies, hangs, or is terminated for exceeding its budget
**When** that happens
**Then** the watcher emits a terminal event naming which of those occurred (FR16a)
**And** the outcome appears in the closing report rather than being retried silently (FR16)

**Given** the run finishes normally
**When** it exits
**Then** the session is woken by both the watcher's terminal event and the process exit, and treats
the duplicate as one completion

### Story 1.3: Refuse to run an epic that was never audited

As the owner,
I want the skill to refuse an epic without a passing gate verdict,
So that an unaudited spec can never be executed literally while I am asleep.

**Acceptance Criteria:**

**Given** an epic with no gate artifact at all
**When** the owner tries to start a run
**Then** the skill refuses, names the missing artifact, and starts nothing

**Given** an epic whose gate artifact exists but whose verdict is not literally the pass value
**When** the owner tries to start a run
**Then** the skill refuses and quotes the blocking gap from the artifact
**And** the refusal is not overridable by a flag

### Story 1.4: Audit the stories, not only the epic document

As the owner,
I want the gate to inspect the stories themselves,
So that the artifact actually executed is the artifact that was governed.

**Acceptance Criteria:**

**Given** an epic whose stories exist as a spec folder
**When** the gate runs
**Then** it audits each story, not only the epic document
**And** the verdict names which stories it audited

**Given** a story that leaves a product decision open
**When** the gate reaches it
**Then** the gate asks the owner a literal question and records the literal answer, never inferring
the behaviour (FR10)

**Given** the gate runs with no owner present
**When** it finds an open decision
**Then** it records the gap as pending and returns a blocking verdict rather than guessing

### Story 1.5: Bind the verdict to the exact stories it audited

As the owner,
I want a hand-edit after the gate to invalidate the pass,
So that a story cannot be changed after approval and still execute unattended.

**Acceptance Criteria:**

**Given** a gate verdict recorded for a set of stories
**When** the verdict is written
**Then** it records a fingerprint of each story's content

**Given** a story edited after the gate passed
**When** a run is attempted
**Then** the pass is invalid for that story and the run does not start — a warning is not sufficient
**And** the message names which story changed

**Given** only some stories changed
**When** the gate is re-run
**Then** it re-audits the changed stories rather than the whole epic (FR12)

### Story 1.6: Park an escalation instead of inventing an answer

As the owner,
I want an overnight escalation to wait for me,
So that nobody guesses a product decision at three in the morning.

**Acceptance Criteria:**

**Given** a run that raises a blocking escalation
**When** the supervising session is woken
**Then** it records the escalation with its question and context
**And** it never answers the question itself to resume the run

**Given** an escalation was recorded overnight
**When** the owner opens the next session
**Then** the escalation is surfaced with everything needed to decide

### Story 1.7: Triage deferred work before the epic can close

As the owner,
I want the debt the run's own reviews found to be pulled back into view,
So that a risk the review already diagnosed cannot sit unread because nobody opened the file.

**Acceptance Criteria:**

**Given** a finished run whose reviews recorded deferred items
**When** closure begins
**Then** every open item is triaged and given an explicit outcome

**Given** a deferred item that needs a decision only the owner can make
**When** triage reaches it
**Then** it is parked and surfaced for the owner, and closure records that it is outstanding

**Given** deferred work that is not resolved during closure
**When** closure completes
**Then** each unresolved item exists as a tracked ticket rather than a line in a file

### Story 1.8: Verify the assembled epic when the project has that stage

As the owner,
I want integration verification to run where it is configured and be skipped cleanly where it is not,
So that the same skill works in a project with heavy frontend and in one with no such stage at all.

**Acceptance Criteria:**

**Given** a project whose configuration enables the verification stage
**When** closure reaches it
**Then** the stage runs against the assembled epic, not story by story
**And** its verdict is recorded in the closing report

**Given** a project with no verification stage configured or installed
**When** closure reaches it
**Then** the stage is reported as skipped and closure continues — absence is never treated as failure

### Story 1.9: Retrospect and capture what the night learned

As the owner,
I want the run's lessons written down where the next spec will find them,
So that an unattended night stops being knowledge that evaporates at dawn.

**Acceptance Criteria:**

**Given** a finished run
**When** closure reaches the retrospective
**Then** a retrospective is produced covering what was delivered, what went wrong, and what was learned

**Given** the retrospective surfaces durable knowledge
**When** closure records it
**Then** it is written into the project's knowledge store in the typed form the next spec's search can
find
**And** each entry carries whether it was confirmed by a human or inferred

**Given** the project has no knowledge store yet
**When** closure needs to write one
**Then** the minimal structure is created rather than the knowledge being dropped

### Story 1.10: Close the epic only when the checklist actually passed

As the owner,
I want an epic to reach done only after every closing step has run,
So that I never again find an epic sitting open for ten hours with nobody aware.

**Acceptance Criteria:**

**Given** an epic whose stories are all individually done
**When** closure has not completed
**Then** the epic is not marked done, and its state names what is still outstanding

**Given** every closing step passed
**When** closure completes
**Then** the epic is marked done and the closing report states what each step produced

**Given** one closing step failed or was skipped
**When** closure completes
**Then** the epic is reported in a named partial state, never silently marked done

### Story 1.11: Set the skill up in a project that has never used it

As the owner,
I want a first-run setup that asks what it cannot know,
So that dropping the skill into another company's project does not mean editing the skill.

**Acceptance Criteria:**

**Given** a project with no configuration for this skill
**When** the skill is invoked
**Then** setup asks for what it cannot derive — spec folder location, which optional stages exist,
branch and promotion flow — and never guesses a value it could ask for

**Given** setup completes
**When** it writes
**Then** configuration lands in the project's configuration folder, and any file it must touch outside
that folder is either written by setup itself or named explicitly for the operator and verified
afterwards (FR33a)

**Given** configuration exists but is missing a key added by a later version
**When** the skill is invoked
**Then** it asks only for what is missing rather than restarting setup from scratch

### Story 1.12: Prove the skill meets the standard it was built to

As the owner,
I want the first v2 skill audited against the doctrine,
So that the standard the rest of the suite inherits is demonstrated, not asserted.

**Acceptance Criteria:**

**Given** the skill is being authored
**When** work begins
**Then** it is built through the skill-building tool that carries and enforces the doctrine, not
hand-rolled against a remembered version of it (FR34)

**Given** the skill as built
**When** it is audited against the skill-quality doctrine
**Then** it is within the size targets, its carved-out sections read standalone, and no reference
chains deeper than one level exist

**Given** each instruction in the skill
**When** the pruning test is applied
**Then** every instruction that a capable model would follow correctly unprompted has been removed

**Given** the skill exposes a headless path
**When** it is invoked that way
**Then** it returns one of the three defined statuses, never invents input, and never blocks waiting
for a reply that cannot arrive

## Epic 2: Knowledge that stays true

The owner can trust what is written down. Knowledge is created from what the project already knows,
reaches the specs that need it, and shrinks under curation rather than accreting until it misleads.

### Story 2.1: Structure that makes searching converge

As the owner,
I want the store shaped so a term-based search actually finds the right slice,
So that retrieval needs no script, no tag machine, and no index to keep in sync.

*Ordered before bootstrap deliberately: entries cannot be written into a shape that does not exist
yet. Final validation caught the opposite ordering.*

**Acceptance Criteria:**

**Given** an entry being written
**When** it is stored
**Then** it carries a type and lands where the recursive index will surface it

**Given** a searcher who knows only the domain terms of a task
**When** they read the index, search by term, read candidates, refine, and search again
**Then** the loop converges on the relevant entries rather than returning everything or nothing

### Story 2.2: Bring a knowledge store into being without generating noise

As the owner,
I want a new project's knowledge store seeded from what the project already knows,
So that I start with the non-obvious facts instead of an empty tree or a generated encyclopedia.

**Acceptance Criteria:**

**Given** a project with existing agent-facing documents and a codebase
**When** the store is bootstrapped
**Then** entries are drawn from those documents and from what the codebase actually reveals
**And** each entry is written into the structure Story 2.1 established

**Given** a candidate entry during bootstrap
**When** it is considered
**Then** it is admitted only if removing it would change an agent's behaviour, and rejected outright
if it is code paraphrase, a file map, a tour document, an ecosystem default, history narration,
inference dressed as fact, or aspirational future state

**Given** a completed bootstrap
**When** its size is assessed
**Then** a large store is treated as a failed bootstrap, not a thorough one

### Story 2.3: A spec arrives already carrying what the project knows

As the owner,
I want the relevant knowledge embedded in the spec itself,
So that an executor working literally has the context in front of it rather than a pointer it will
not follow.

**Acceptance Criteria:**

**Given** a spec being written for a task
**When** grounding runs
**Then** the searched slice is embedded in the spec, distilled, with each source path cited — never
the full source text and never a generic instruction to go read something

**Given** a topic the spec touches for which the store has nothing
**When** grounding completes
**Then** the absence is stated explicitly in the spec

**Given** more than one consumer needs this procedure
**When** the procedure is defined
**Then** it exists in exactly one place and every other consumer references it rather than restating it

### Story 2.4: Company rules live with the project they govern

As the owner,
I want another company's way of working stored as project knowledge,
So that its rules are searchable, dated and prunable like everything else instead of hiding in
configuration or in my head.

**Acceptance Criteria:**

**Given** a rule that is specific to one organization
**When** it is recorded
**Then** it lands in the project's knowledge store, not in the configuration folder
**And** it is subject to the same trust status, pruning and expiry as any other entry

### Story 2.5: A question that had to be asked becomes a rule that prevents it

As the owner,
I want every mid-execution question to harden the next spec,
So that the ruler grows from real failures instead of from someone remembering to write guidance.

**Acceptance Criteria:**

**Given** an execution that escalated because it had to ask
**When** the escalation is recorded
**Then** it captures what the spec left implicit, the exact question, and an actionable
generalization

**Given** recorded spec debt
**When** the gate next runs
**Then** it harvests that debt into a standing rule and checks subsequent specs against it

### Story 2.6: Every entry says how much it can be trusted

As the owner,
I want to see whether a claim was confirmed or merely inferred,
So that an unverified guess can never be read as established fact.

**Acceptance Criteria:**

**Given** an entry being written
**When** it is stored
**Then** it carries a trust status of confirmed or inferred, plus its source and a date

**Given** a claim nobody confirmed
**When** it is stored
**Then** it is visibly inferred — it is never promoted to fact by omission

### Story 2.7: Curation makes the store smaller

As the owner,
I want pruning to happen on a schedule and trust to expire,
So that a store which only grows cannot quietly become the thing that misleads the agents.

**Acceptance Criteria:**

**Given** an epic closes
**When** closure completes
**Then** a curation pass has run — pruning is triggered by an event, never by someone remembering

**Given** a curation pass
**When** it finishes
**Then** the store is the same size or smaller than before it started

**Given** a confirmed entry whose verification is old, or whose subject was touched by later work
**When** curation reaches it
**Then** it drops back to inferred until someone re-confirms it

## Epic 3: Anti-patterns become rules a machine enforces

The owner can turn a catalogued bad pattern into a rule that blocks it mechanically. This closes the
middle of a pipeline whose two ends already exist and whose middle has never had an owner — which is
why the tooling exists today with zero rules written.

### Story 3.1: See what is ready to become a rule

As the owner,
I want the candidate list derived rather than maintained,
So that a newly catalogued pattern enters the queue without anyone remembering to add it.

**Acceptance Criteria:**

**Given** the catalogue of anti-patterns
**When** the queue is requested
**Then** it is computed from the entries themselves — mechanically detectable, not retired, not
already automated — and never read from a hand-kept list

**Given** an entry that is hybrid or human-only
**When** the queue is computed
**Then** it does not appear, regardless of its other fields

### Story 3.2: Write a rule that proves itself before it ships

As the owner,
I want a new rule tested against the real codebase in both directions,
So that the queue does not drain into rules nobody trusts.

**Acceptance Criteria:**

**Given** a candidate anti-pattern with a real occurrence in the codebase
**When** a rule is authored for it
**Then** the rule is demonstrated to fire on that actual occurrence

**Given** code the project accepts as correct
**When** the rule runs against it
**Then** it does not fire

**Given** a rule that cannot demonstrate both
**When** authoring concludes
**Then** the rule is not shipped, and the anti-pattern stays queued with the reason recorded

### Story 3.3: Shipping a rule closes the loop

As the owner,
I want an automated pattern to leave the queue without being killed,
So that the knowledge stays alive while only its enforcement changes.

**Acceptance Criteria:**

**Given** a rule that has shipped
**When** the source entry is updated
**Then** it is marked automated and disappears from the queue
**And** it is not retired — its lifecycle state is untouched

### Story 3.4: Blocked work has an honest way forward

As the owner,
I want an unattended agent to have an exit that is not "ignore the rule",
So that a false positive at two in the morning neither freezes the night nor silently erodes
enforcement.

**Acceptance Criteria:**

**Given** a change blocked by an active rule
**When** the agent believes it is a false positive
**Then** it can record that, with a mandatory justification, and proceed

**Given** such a record
**When** it is written
**Then** it downgrades that specific finding only — never the rule, and never silently

**Given** accumulated violations and false-positive claims
**When** curation next runs
**Then** it reconciles them; enforcement itself never writes to the knowledge store directly

## Epic 4: Work that never gets lost

The owner can run several windows at once without corrupting the record, and can declare the ticket
states a particular company actually needs.

*This epic also carries the English rewrite of the existing behaviour, including the files it
produces (FR25) — behaviour is preserved, language is not.*

### Story 4.1: Several windows, one intact record

As the owner,
I want to work in parallel windows without them corrupting each other's tickets,
So that concurrency does not cost me a lock that can stick when a window dies.

**Acceptance Criteria:**

**Given** two windows creating tickets at the same moment
**When** both write
**Then** both tickets survive with distinct identities and neither corrupts a shared file

**Given** a request to list the work
**When** the listing is produced
**Then** it is derived by reading the individual records, not from a stored index that writers contend
over

**Given** a window that dies mid-write
**When** another window lists or writes
**Then** it is unaffected — there is no lock to release and no index left half-updated

### Story 4.2: The states this organization actually uses

As the owner,
I want to declare a state that only one company needs, and say what it means,
So that an agent can use a state it has never seen without me explaining it again.

**Acceptance Criteria:**

**Given** a project whose configuration declares its own set of states
**When** work is tracked
**Then** those states are the ones available, without editing the skill

**Given** a declared state
**When** it is configured
**Then** the configuration also carries what the state means and when to move work into it

**Given** an agent encountering a state it has not seen before
**When** it reads the configuration
**Then** it can decide correctly whether this piece of work belongs in that state

## Epic 5: The manager that learns

The owner corrects something once and never again. The correction is recorded automatically, in the
right file, by a manager that knows where each skill's configuration lives.

### Story 5.1: One place to ask for anything

As the owner,
I want a single entry point that routes the work,
So that I do not have to remember which skill does what.

**Acceptance Criteria:**

**Given** a request stated in the owner's own words
**When** the manager receives it
**Then** it selects and invokes the appropriate skill without the owner naming it

**Given** a request that belongs to the run supervisor
**When** the manager receives it
**Then** it says so and hands off, because that skill is the one the owner drives directly

### Story 5.2: Output built to be read fast

As the owner,
I want short, scannable, self-contained answers,
So that I can decide quickly, including on a phone.

**Acceptance Criteria:**

**Given** any report or answer
**When** it is written
**Then** it leads with the conclusion, uses lists over paragraphs, and stays short by default

**Given** a message referring to a prior decision, requirement or finding
**When** it is written
**Then** it restates what that thing was — no abbreviations, no internal codes, no bare references to
earlier numbered items

**Given** the owner asks for depth
**When** they ask
**Then** detail is expanded; it is never volunteered pre-emptively

### Story 5.3: Corrected once, remembered forever

As the owner,
I want a correction recorded without me marking it,
So that I never teach the same thing twice.

**Acceptance Criteria:**

**Given** the owner corrects the manager's behaviour or states a project-specific way of working
**When** the correction is made
**Then** it is recorded automatically, without the owner flagging it as worth keeping

**Given** a recorded correction
**When** a later session encounters the same situation
**Then** the correction is already in effect

**Given** a correction that names another skill's behaviour
**When** it is recorded
**Then** it lands in that skill's configuration, because the manager knows where each skill's
configuration lives

### Story 5.4: Lessons land as configuration or knowledge, never as a skill edit

As the owner,
I want learning to leave the skills themselves untouched,
So that portability survives everything the manager learns.

**Acceptance Criteria:**

**Given** a lesson that determines how a skill should behave here
**When** it is recorded
**Then** it lands in the project's configuration

**Given** a lesson about how this project or company works
**When** it is recorded
**Then** it lands in the project's knowledge store

**Given** any lesson at all
**When** it is recorded
**Then** no skill body is modified

### Story 5.5: Never send a writer into a checkout a run is using

As the owner,
I want the collision risk closed mechanically,
So that it stops depending on me remembering which window is busy.

**Acceptance Criteria:**

**Given** a live run in progress
**When** the manager is about to dispatch an agent that writes to the repository
**Then** it detects the live run and either waits or gives that agent its own isolated checkout

**Given** no live run
**When** the manager dispatches
**Then** it proceeds without ceremony

## Epic 6: Install anywhere, stay current

The owner can drop the suite into a project it has never seen — including one at another company with
different rules and tooling — run the setup, and have it work. An improvement made in one project
reaches the others.

### Story 6.1: Drop it in and it works

As the owner,
I want installation to be copying the folder and running setup,
So that a project I set up on another machine does not depend on a script that has since rotted.

**Acceptance Criteria:**

**Given** a project that has never had the suite
**When** the owner copies the folder into place and runs setup
**Then** the skills work, with no further manual editing

**Given** a skill copied from a machine where it was configured
**When** it runs in the new project
**Then** it carries nothing from the source machine — every project-specific value comes from setup

**Given** setup must touch a file outside its own configuration folder
**When** it runs
**Then** it either writes that file itself or names it explicitly for the operator and verifies it
afterwards

### Story 6.2: Nothing project-specific left in the skill body

As the owner,
I want every environment-specific value to be configuration,
So that the same file works at home and at a client without a diff.

**Acceptance Criteria:**

**Given** any skill in the suite
**When** it is inspected for branch names, deploy commands, package names, document paths or
environment identifiers
**Then** none are found in the skill body — all are read from configuration

**Given** a value that cannot be expressed as configuration
**When** it is discovered
**Then** it is treated as a design defect, not accommodated

### Story 6.3: Change behaviour without forking

As the owner,
I want a project to override a skill's behaviour by declaring it,
So that a client-specific need never costs me a divergent copy.

**Acceptance Criteria:**

**Given** a project that declares overrides
**When** a skill resolves its configuration
**Then** skill defaults, team overrides and personal overrides merge in that order

**Given** the merge
**When** it runs
**Then** it is structural and predictable, and cannot delete a base entry — overrides add or replace
only

**Given** the resolution tooling is unavailable
**When** a skill activates
**Then** it documents and follows the manual equivalent rather than blocking

### Story 6.4: An improvement in one project reaches the others

As the owner,
I want a fix made in one project to flow back and outward,
So that the shared copy stops being an archaeological snapshot.

**Acceptance Criteria:**

**Given** a skill improved while working in one project
**When** the improvement is durable
**Then** there is a defined path for it to reach the shared source

**Given** a project running an older copy
**When** the owner wants it current
**Then** there is a defined path to bring it forward, and a way to see what differs

**Given** the shared source already contains copies that diverged before this epic
**When** the path is designed
**Then** it accounts for reconciling existing drift rather than assuming a clean start

**Given** the shared repository
**When** the suite is placed in it
**Then** it lives under its own versioned folder alongside the previous generation, which stays intact
for reference (FR31)

## Validation Record — 2026-08-05

Run as the final step of epic and story creation. Findings and what was done about each.

**Requirement coverage.** All 56 requirements map to an epic; verified by script, not by eye. Three
had no story whose acceptance criteria actually exercised them, despite being mapped — coverage at
epic level had hidden it:

- **FR7** (all stories authored before the run) — the spec-folder mode implied it structurally but
  nothing checked it, so a partially authored folder could have executed. Added as an acceptance
  criterion on Story 1.1.
- **FR34** (skills built through the skill-building tool) — Story 1.12 audited the result but never
  required the tool that enforces the standard during authoring. Added.
- **FR31** (versioned folder in the shared repository) — mapped but never asserted anywhere. Added to
  Story 6.4.

**Story ordering.** Epic 2 had a genuine forward dependency: bootstrap was ordered before the
structure it writes into. Swapped. All other epics verified — each story builds only on previous ones.

**Two acknowledged in-epic gaps, deliberately not fixed.** Story 1.1 can launch before Story 1.3 adds
the refusal check, and Story 6.1 promises an install that Stories 6.2–6.3 make robust. Both are
incremental build order within an epic that ships as a unit, not forward dependencies between
delivered capabilities.

**Cross-cutting constraint, tracked but not story-shaped.** FR25 (everything written in English)
constrains every epic and is not testable as a single story's acceptance criteria. It is carried as an
epic-level note where the rewrite is concrete (Epic 4) and as a standing constraint elsewhere.

**Not applicable.** No architecture document exists, so the starter-template check does not apply.
No database or entity work exists in this suite, so the entity-creation check does not apply. No UX
design contract exists.

**File overlap.** Epics target distinct skills, with two deliberate exceptions: Epic 5 (the manager
must know where every skill's configuration lives) and Epic 6 (every skill must be purged of
project-specific literals) both touch the whole suite by nature. Consolidating them was considered
and rejected — they are different concerns with a real feedback boundary between them.
