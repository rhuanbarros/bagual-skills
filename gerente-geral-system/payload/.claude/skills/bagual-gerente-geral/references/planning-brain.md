# Planning Brain (E9.3)

Canonical reference: `ideias/prd-00-sistema-orquestrador.md` §4.2 (FR-4), UJ-2. The full contract
(the two skill classes, the exact plan schema, the smoke test that confirmed skill visibility to a
sub-agent) lives in `project_controll/gerente/planning-brain.md` — read it in full before the first
time the owner hands you a large effort without breaking it down. This file only carries the
operational step-by-step, summarized.

**When it fires:** the owner hands you a large/multi-epic intent that doesn't already come broken
down into Tickets (UJ-2 — "strengthen the app's test coverage and accessibility"), OR you yourself,
during "priorizar", notice that a Ticket is too large to map directly to a trilha (`rapida | spec |
epic | wds | correct-course`) without first turning it into a multi-epic plan.

**The two skill classes (S2/S3 spike — never forget this distinction):**
- **`bmad-prd`** has a formal headless mode (`references/headless.md`) → you run it as a headless
  Sonnet sub-agent (Step 1 below).
- **`bmad-create-epics-and-stories` / `bmad-check-implementation-readiness` /
  `bmad-correct-course`** are facilitator-only (`WAIT FOR INPUT`/`YOU ARE A FACILITATOR` gates,
  tested live against the sister skill `wds-8` in spike S3 — it locked up on the very first step)
  → you **never** spawn them as a sub-agent. Whatever they would do, you do **in-thread**, in your
  own Opus context, applying their method as knowledge — never invoking
  `Skill(bmad-create-epics-and-stories)`/`Skill(bmad-check-implementation-readiness)`/
  `Skill(bmad-correct-course)` on an autonomous sub-agent. This isn't a shortcut — it's the only way
  to avoid stalling the cycle waiting for a human who isn't there.

## Step by step

1. **`bmad-prd` headless (Sonnet sub-agent, foreground):** spawn an `Agent` (`model: "sonnet"`)
   instructed to explicitly invoke the `bmad-prd` skill (name the skill in the prompt — never leave
   it implicit) with the headless payload from `.claude/skills/bmad-prd/references/headless.md`
   (`headless: true`, `intent`, `brief` = the owner's intent + whatever relevant context you already
   have, `doc_workspace`). Read the terminal JSON: `status: "complete"` or `"partial"` → go to Step 2
   (any `open_questions[]` from a `"partial"` becomes an ambiguity handled in Step 4, it doesn't
   block the whole plan); `status: "blocked"` → **do not** prompt, **do not** invent — the `reason`
   is the ambiguity and goes straight to Step 4 (Oracle Protocol) for this specific workstream.
2. **Break it down into epics/stories IN-THREAD** (without spawning `bmad-create-epics-and-stories`):
   read Step 1's PRD + the project's grounding (the 4 knowledge files + Ledger + existing patterns),
   and write the plan to `project_controll/gerente/planning/<intent-slug>-plano.md`, one `## Epic N`
   section per epic, **each one mandatorily declaring**: title/description, `área` (the same tag
   used in Tickets/Ledger), `arquivos/diretórios prováveis` (the input for PRD 03's parallelism
   graph — you do NOT compute the graph here, just declare it), and `depende-de` (other epics in the
   same plan, if any). **Each section also carries a structured sentinel from the SAME
   declaration** — Story `bridge-declaracao-areas`, the bridge that links E10/E11's parallelism —, a
   line `<!-- epic-decl: {"epic_key": "...", "epic_type": "...", "areas": [...],
   "touches_shared": [...], "depends_on": [...]} -->` right below the section. `epic_key` is the
   REAL key from `sprint-status.yaml` (never the `## Epic N` section number, which is only a
   document index — the real key only exists once the Ticket is materialized). Full format +
   rationale: `project_controll/gerente/planning-brain.md` §3 Step 2.
3. **Readiness check IN-THREAD** (without spawning `bmad-check-implementation-readiness`): re-read
   the plan against the PRD applying the readiness checklist as knowledge — clear scope? circular
   dependency? epic too large? Note the verdict (`pronto` / `precisa de ajuste`) per epic in the
   same `## Checagem de prontidão` section of the plan file. An epic marked `precisa de ajuste` is
   not dispatched this round.
4. **Product ambiguity → Oracle Protocol (E9.1), never a whole-plan block:** any `open_questions[]`/
   `reason` from Step 1 or scope doubt noticed in Steps 2-3 follows the "Oracle Protocol" (see
   `oracle-protocol.md`) per affected epic — decide with a trace if confidence allows (`high`, a
   real precedent), or record the question on that epic's Ticket and move on to the plan's other
   epics, which are not blocked by a sibling's doubt (UJ-2, "Edge case").
5. **Materialize Tickets + dispatch via the existing contract (E8.4):** for each `pronto` epic,
   invoke `bagual-tickets` (never edit `board.yaml` by hand) to create a Ticket with `trilha: epic`,
   the `area:` declared in the plan, `## Locais afetados` filled with Step 2's files/directories,
   `## Descrição` citing the plan's path. From here on **there is no new mechanism** — the Ticket
   enters the normal `pronto-para-implementar` queue and follows the already-described
   "priorizar"/"despachar" phases (`trilha: epic` → `/bagual-epic-runner {N}`,
   `gerente_dispatch.py open-dispatch`). Keep dispatching **one Ticket at a time** —
   parallelism between this same plan's epics is PRD 03/E10-E11 territory, out of scope here.
   **Before dispatching this plan's set of epics, run the bridge**
   (`python3 project_controll/gerente/scripts/emit_epic_areas.py from-plan --plan
   <plano.md> --sprint-status <target>`) to populate the `epic_areas:` that
   `compute_execution_graph.py` reads at the start of every `bagual-epic-runner` invocation —
   without this, the graph keeps falling back to the sequential fail-safe even with epics from
   disjoint areas. Detail in `planning-brain.md` §3 Step 4.

**Skill visibility in the sub-agent (S2 tooling note — resolved by this story, but keep the defense
in depth):** the S2 spike had seen a `general-purpose` sub-agent NOT see `bmad-*` skills in its
registry, in a different harness context. A real smoke test from this story (E9.3, evidence in
`ideias/sistema-artifacts/fixtures/E9/e9-3-headless-smoke/`) confirmed that, in this harness/project
version, a `general-purpose` sub-agent spawned via `Agent` did see `bmad-prd` listed in its skill
registry and invoked it headless with no interactive prompt. Even so, always **name the skill
explicitly** in the sub-agent's prompt (never leave it implicit) — if a sub-agent ever reports that
the skill didn't show up, treat it as a Step 1 failure (equivalent to `blocked`) and log the
recurrence in `_bmad-output/notes.md`, never work around it by inventing a direct call that skips
the skill.
