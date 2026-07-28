# Planning Brain (E9.3) — headless where possible, in-thread where not

> Reference contract for the "Planning Brain" Protocol in
> `.claude/skills/bagual-gerente-geral/SKILL.md`. Story: `ideias/sistema-artifacts/E9-3-cerebro-planejamento.md`.
> Canonical: `ideias/prd-00-sistema-orquestrador.md` §4.2 (FR-4), UJ-2. Spike that grounds
> the design: `ideias/fase-0-spikes.md` § S2+S3.

## 1. The problem this document solves

UJ-2 (PRD 00): the owner delegates a **large** effort ("beef up test coverage and
app accessibility") without breaking it down into epics/stories, and disappears. The Gerente needs
to turn this into an epic/story plan **on its own**, without stalling waiting for the owner on
every micro-decision, but also without inventing scope on its own where there is real
product ambiguity.

The obvious tool would be to reuse John's (`bmad-agent-pm`) planning skills as
headless sub-agents — exactly as the Gerente already does with `bmad-quick-dev`/
`bmad-dev-story`/`bagual-epic-runner` in the "dispatch" phase. The S2/S3 spike
(`ideias/fase-0-spikes.md`) found that **this only works for a subset of them** —
see §2.

## 2. Class 1 vs Class 2 — the S2/S3 spike finding

| Class | Skills | Headless behavior | Evidence |
|---|---|---|---|
| **Class 1 — automatable** | `bmad-prd` | Has a **formal headless mode**: `.claude/skills/bmad-prd/references/headless.md` + `assets/headless-schemas.md`. Detects `headless: true` (or invocation from another non-interactive skill/runner) on the first message, never asks, produces a terminal JSON payload (`status: complete\|partial\|blocked`). | Formal, documented in the skill itself. Reconfirmed live in this story (§4 below) — ran end-to-end with zero interactive prompts. |
| **Class 1 — automatable** (reference, not used in this story) | `create-story`/`dev-story`/`code-review` | No formal headless mode, but **no hard facilitator gates** — they honor "yolo/auto-approve/don't ask" in the spawn prompt. | `bagual-epic-runner` already runs this way in production (Epics E1-E8 of this very meta sprint). |
| **Class 2 — facilitator-only** | `bmad-create-epics-and-stories`, `bmad-check-implementation-readiness`, `bmad-correct-course` | **Lacks** `references/headless.md`. Have `🛑 WAIT FOR INPUT` / `YOU ARE A FACILITATOR not a content generator` / `[C] Continue` menus — *semantic turn-yields*, not permission dialogs. Auto-approve does **not** solve this — these are gates that wait for a real human response from inside the skill's body. | Tested live in spike S3 against `wds-8` (same class/same gates): stalled at the very first `step-01-identify`, ≥5 hard halts. Inspected (not run to completion) in `bmad-create-epics-and-stories`/`bmad-check-implementation-readiness`/`bmad-correct-course` — same textual gates confirmed by directly reading the skills. |

**Derived rule (the one this protocol applies):** the Gerente **never spawns** a
Class 2 skill as a headless sub-agent — this would stall the autonomous cycle waiting for a human
who isn't there (exactly the F5/E2.2 "hung sub-agent", just caused by the skill itself,
not by the harness). For whatever these skills would do, the Gerente reasons **in-thread**
(the Gerente's own Opus, within its own context, applies the skill's METHOD as
knowledge — without invoking `Skill(bmad-create-epics-and-stories)`), or flags the step as
pending on the owner when the judgment required exceeds what the oracle is confident to
decide alone (the same mechanical veto F10 already used by the Oracle Protocol, E9.1).

**Never fork the Class 2 skills** to "fix" the lack of a headless mode — this would
violate the rule "native > generic; never fork `bmad-*`" (`AGENTS.md`). The skill remains
fully intact for the owner's normal interactive use; the Gerente simply doesn't call it
when it's alone.

## 3. The protocol — 4 steps

### Step 1 — `bmad-prd` headless via a Sonnet sub-agent

The Gerente dispatches an `Agent` (**`model: "sonnet"`**, foreground — same discipline of
"never a hung dispatch" as the other phases) instructed to invoke the `bmad-prd` skill with
a headless payload in the first message, literally following
`.claude/skills/bmad-prd/references/headless.md`:

```
headless: true
intent: create   # ou update/validate, conforme o caso
brief: "<o intent grande do dono, verbatim + qualquer contexto que o Gerente já tenha
         (Ledger, tickets relacionados, grounding do projeto)>"
doc_workspace: "<pasta de destino do PRD — NUNCA a pasta de planejamento real do produto
                 sem que o dono tenha pedido isso; para trabalho de rascunho/exploração,
                 usar uma pasta de trabalho dedicada>"
```

Real ambiguity (the `brief` can't be resolved to a target without inventing product
detail) → the skill returns `status: "blocked"` with a `reason` — **never** an interactive
prompt (that's exactly what the formal headless mode guarantees). The Gerente reads the terminal
JSON:

- `status: "complete"` → proceeds to Step 2 with the produced `prd`.
- `status: "partial"` → proceeds to Step 2, but each item in `open_questions[]` becomes
  a tracked question (see "Product ambiguity" below) — it does not stall the whole
  Step 2 because of this.
- `status: "blocked"` → **does not** proceed to Step 2. The `reason` becomes the ambiguity
  record (same treatment as "Product ambiguity" below) and the Gerente stops that specific
  workstream, without stalling the whole cycle (other Tickets in the queue
  keep being processed normally).

### Step 2 — Decomposition into epics/stories, IN-THREAD (never spawned)

The Gerente, in its own Opus context (without `Skill(bmad-create-epics-and-stories)`),
applies that skill's METHOD as knowledge: it reads the PRD produced in Step 1 + the
project's grounding (existing patterns, `_bmad-output/{anti-patterns,decisions,
product-decisions,notes}.md`, Ledger — the same grounding a normal story carries at
spec-time, PRD 03), and decomposes it into epics/stories.

**Mandatory output contract — every epic in the plan DECLARES:**
- `title` + `description` (what it delivers).
- `area` — the same area/feature tag used in `bagual-tickets` (`area:` in
  the Ticket's front-matter) and in the Ledger (`areas: [...]`).
- `likely files/directories` — the Gerente's best-grounded guess about where
  the work will touch (e.g., `frontend/src/features/clients/**`,
  `backend/domain/vehicles/**`). Doesn't need to be exhaustive or definitive — it is the
  INPUT to the PRD 03 parallelism graph calculation (area/file disjointness
  between epics = parallelizable); **the graph calculation itself is not done here**.
- `depends-on` — other epics from the SAME plan that must finish first (if any).

The plan is written to disk (**file-mediated**, same principle as FR-8): one
Markdown file per plan, `project_controll/gerente/planning/<intent-slug>-plano.md`, one
`## Epic N — <title>` section per epic with the 4 fields above. This file is the artifact
that the "dispatch" phase (E8.4) consumes later — never a loose return value in
the Gerente's context.

**ADDITIONAL output contract (Story `bridge-declaracao-areas` — the bridge that connects
PRD 03/E10-E11 parallelism): every `## Epic N` section also carries a STRUCTURED sentinel
of the SAME declaration above**, mechanically extractable — never a second
source of truth to keep manually synced, it is the same declaration you (the Gerente)
are already making in prose, just restated once as single-line JSON:

```
<!-- epic-decl: {"epic_key": "epic-E12", "epic_type": "feature", "areas": ["frontend/src/features/x/"], "touches_shared": ["supabase/migrations"], "depends_on": ["epic-E11"]} -->
```

Format: an HTML comment (invisible on a normal human read of the plan) containing
A single one-line JSON object, placed right below the `## Epic N — <title>` section
it describes. Fields — the SAME 5 that `compute_execution_graph.py` already consumes, no more
no less (see that script's module docstring,
`.claude/skills/bagual-epic-runner/scripts/compute_execution_graph.py`):
- `epic_key` (**required**) — the REAL key that `sprint-status.yaml` will use
  when this epic is dispatched (e.g., `epic-42`, `epic-E12`). **Never infer this
  from the `## Epic N` section number** — the plan number is just a document index; the
  real key only exists once the Ticket/epic is materialized against the live board (Step
  4). You are the one who knows the right key — declare it explicitly.
- `epic_type` — `"feature"` (an epic that adds a route/endpoint — auto-injects
  `App.tsx`/`api/index.py` into the disjointness calculation), `"refactor"` or `"other"`.
- `areas` — the same "likely files/directories" declared in prose above,
  as an array of strings (path prefixes).
- `touches_shared` (optional) — when you already know this epic touches one of the
  fixed shared touchpoints (migrations, `package.json`/`pyproject.toml`,
  process/knowledge files) even outside `areas`.
- `depends_on` (optional) — the `epic_key`s (not the `## Epic N` numbers) of other
  epics from the SAME plan that must finish first.

The VALUES of these fields are your (Opus) judgment — the same decision you already
made for the prose above, never inferred back from it by a script. A mechanical
bridge (`project_controll/gerente/scripts/emit_epic_areas.py`, subcommand
`from-plan`) extracts this sentinel and writes/updates the `epic_areas:` block of a
target `sprint-status.yaml` — no NLP, no prose parsing, just extraction of already-ready
JSON. A missing or malformed declaration (invalid JSON, missing/invalid
`epic_key`, `epic_type` outside the enum) is SKIPPED by the bridge — fail-safe, the
corresponding epic falls back to `compute_execution_graph.py`'s default `sequencial`,
never a "guessed" declaration. Full format detail + end-to-end proof
(synthetic fixture making the real `compute_execution_graph.py` compute 2 parallel
Tracks): `ideias/sistema-artifacts/bridge-declaracao-areas.md`.

### Step 3 — Readiness check, IN-THREAD (never spawned)

Same discipline as Step 2: no `Skill(bmad-check-implementation-readiness)`. The Gerente
applies the readiness checklist as knowledge — re-reading the plan against the PRD:
does every epic have clear scope? Is there a circular dependency? Is any epic too
large and should be split into two? It notes the verdict (`ready` / `needs adjustment`) in the
plan file itself, under the `## Readiness check` section. An epic marked "needs adjustment" is not
dispatched in this round — but **keeps the area/file declaration from Step 2 in
the plan file** (the readiness check happens AFTER the declaration and never
replaces/erases it); it is recorded with the specific gap, for the owner to resolve or for
a future round of the Planning Brain.

### Step 4 — Materialize Tickets + dispatch via E8.4

For each `ready` epic in the plan: the Gerente invokes `bagual-tickets` (composition, never
direct `board.yaml` editing) to create a Ticket with `trilha: epic`, `area: <the
one declared in the plan>`, `## Locais afetados` filled with the files/directories
declared in Step 2, and `## Descrição` citing the plan's path
(`project_controll/gerente/planning/<slug>-plano.md#epic-N`). From here, the Ticket
enters the normal `pronto-para-implementar` queue and follows the standard operational cycle
("prioritize" phase → "dispatch" via `gerente_dispatch.py open-dispatch --trilha epic
--skill bagual-epic-runner`, see the trilha→skill mapping table in
`.claude/skills/bagual-gerente-geral/references/dispatch-and-review.md` § "3. despachar") — **no new dispatch
mechanism is invented here**; the Planning Brain ends the moment the Tickets exist, one
per epic. Parallelism between these Tickets (dispatching more than one
epic at a time, per worktree) is PRD 03/Execution Orchestrator territory —
out of scope for this story, which continues dispatching **one Ticket at a time**, as every
"dispatch" phase already has since E8.1.

**Before dispatching the set of `ready` epics from this plan to the multi-epic
supervisor (Story `bridge-declaracao-areas`):** run the mechanical bridge to populate the
target `sprint-status.yaml`'s `epic_areas:` with the sentinels you already wrote in
Step 2 —

```
python3 project_controll/gerente/scripts/emit_epic_areas.py from-plan \
  --plan project_controll/gerente/planning/<slug-do-intent>-plano.md \
  --sprint-status <sprint-status.yaml alvo>
```

This is what makes `workflow.md`'s Graph-build step (which runs
`compute_execution_graph.py --epics ... --sprint-status ... --write` at the start of every
`bagual-epic-runner` invocation) stop always falling back to the fail-safe `sequencial` and
compute real parallel Tracks when this plan's epics' areas are indeed
disjoint — without this call, `epic_areas:` stays empty and behavior is identical
to before this story (correct, just not parallelized). The bridge is idempotent and never
fails the whole Step 4: a malformed sentinel is just skipped (with a warning) and that
specific epic stays on the fail-safe, the plan's other epics continue normally.

## 4. Product ambiguity the oracle doesn't decide → a ticket, never a total block

Any point in the protocol (an `open_questions[]` from Step 1, an ambiguous scope
decision noticed in Step 2/3) that requires a product judgment with no reliable precedent
follows the existing **Oracle Protocol (E9.1)**: the Gerente tries to decide
with a trail (Ticket + Ledger); if the confidence comes out `low` (no `estado: ativa`
+ `ratification: ratified` precedent to support `high` — F10, `gerente_oracle.py`'s
mechanical gate), the question stays **recorded on the affected epic's Ticket** and
the Gerente **proceeds with what it has** — never stalling the whole plan over an
isolated doubt in one of the epics (UJ-2, "Edge case"). Epics unaffected by
the ambiguity continue normally to Step 4.

## 5. Skill visibility record (S2, tooling note)

The S2/S3 spike recorded a tooling doubt: when testing via a `general-purpose`
sub-agent, the sub-agent **did not see** the `bmad-*` skills in its registry — only
generic skills — even though `bagual-epic-runner` proves in practice that sub-agents
CAN invoke them. It was left as "likely a spike-harness artifact, to confirm".

**Confirmed in this story (E9.3), with a real, on-disk verifiable smoke test:** a
fresh `general-purpose` sub-agent (no prior context), spawned exactly as the
Gerente would spawn a dispatch, had `bmad-prd` **listed in its available-skills
system-reminder** and invoked it successfully in headless mode — no interactive prompt,
no error, producing a real `prd.md` (`ideias/sistema-artifacts/fixtures/E9/
e9-3-headless-smoke/prd.md`, `status: "partial"`, 3 `open_questions`, a `.memlog.md` with 4
entries via the shared script). In other words: **today, on this project's harness/version,
`bmad-prd` visibility for a `general-purpose` sub-agent spawned via `Agent`
is not an issue** — no additional measure (explicit namespace, special prompt,
etc.) was necessary for the sub-agent to find and invoke the skill.

**What the Gerente should still do (defense in depth, since S2 recorded a
real failure in another harness context):** when spawning the Step 1 sub-agent, the
prompt must explicitly name the skill (`invoke the "bmad-prd" skill via the Skill
tool`), never implicitly assume the sub-agent "will know what to do" — the same
discipline `bagual-epic-runner` already uses when explicitly naming `bmad-create-story`/`bmad-dev-story`
in every dispatch's prompt. If a sub-agent reports the skill didn't
appear in its registry (the scenario S2 saw), the Gerente treats this as a Step 1
failure (equivalent to `status: blocked`) and records the occurrence in
`_bmad-output/notes.md` as a recurrence of the tooling gap — never tries to work around it
by inventing a direct call to the PRD skipping the skill.

## 6. What this document does NOT cover (out of scope, deliberate)

- Computing the parallelism graph from declared `area`/files — PRD 03.
- Parallel per-worktree execution of multiple epics from the same plan — PRD 03/E10-E11.
- `wds-8` (product change with design) — same Class 2, but resolved by E9.8
  (in-thread OR waits on the owner), not by this document.
- Escalating trivial tickets (`bagual-tickets` deciding the trilha on its own) — E9.4.
