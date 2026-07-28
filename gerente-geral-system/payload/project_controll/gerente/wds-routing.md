---
title: "Route (i) execution — wds-8 never headless (E9.8)"
tipo: reference
created: 2026-07-12
status: living-document
source_prd: "ideias/prd-05-wds.md — FR-6 (§4.1); ideias/fase-0-spikes.md — S3"
source_epic: "ideias/epics.md — Epic E9 (last story, closes the epic)"
source_story: "ideias/sistema-artifacts/E9-8-wds8-in-thread-ou-dono.md"
---

# Route (i) execution — wds-8 never headless (E9.8)

Canonical contract for the sub-protocol `.claude/skills/bagual-gerente-geral/SKILL.md` invokes in
the **"dispatch"** phase whenever a Ticket's `trilha` is `wds` — the classification decision
itself (is it route (i)? which ticket?) has already been made by `product-routing.md` (E9.6); this
document decides **how this already-routed route (i) is executed**, given that `wds-8` was
**proven infeasible headless** (spike S3, tested live — stalled at the very first Analyze
step). Read it in full before the first time a Ticket with `trilha: wds` reaches
the "dispatch" phase.

## 1. The fact that anchors this protocol (S3, tested live)

`ideias/fase-0-spikes.md` § S3: `wds-8` is a **facilitator** skill with hard gates
— `🛑 NEVER generate content without user input` / `📋 YOU ARE A FACILITATOR, not a
content generator` / `WAIT FOR INPUT` — present in **every** `step-*.md` of **all**
its phases (`steps-a/` Analyze, `steps-d/` Design, `steps-p/` Publish/handoff,
`steps-t/` Test). An autonomous sub-agent spawned with an explicit instruction to
"auto-approve, yolo, don't ask" stalled anyway at `step-01-identify.md` (Analyze)
— these gates are **semantic turn-yields**, not permission dialogs that
auto-approve resolves. **Confirmed, not hypothetical: no autonomous path in this
system can invoke `wds-8` (or any `wds-*` that is part of the same pipeline) as a
headless sub-agent.**

## 2. Hard rule, no exception

**No autonomous flow in this system — neither the Gerente nor any sub-agent it
dispatches — spawns `wds-8` (nor `Skill(wds-8-product-evolution)`, nor any of its
`workflow-*.md`: `workflow-analyze.md`, `workflow-scope.md`, `workflow-design.md`,
`workflow-implement.md`, `workflow-test.md`, `workflow-deploy.md`) as a headless
sub-agent.** This holds even if the instruction looks like "just the Analyze, which is
lightweight" — S3 stalled exactly there. There is no safe "partial" version of running
`wds-8` autonomously.

`wds-8`'s files (`.claude/skills/wds-8-product-evolution/**`) are **never
edited** by this system — not to try to work around the gates, nor for any
other reason (the project's general rule, "never fork `bmad-*`/`wds-*`"). The answer to S3
is not "fix wds-8" — it is to route around it.

## 3. When this protocol triggers

In the "dispatch" phase (`.claude/skills/bagual-gerente-geral/references/dispatch-and-review.md` § "3. despachar"), step 1
(map `trilha` → skill): when the Ticket at hand has `trilha: wds` (decided by
`product-routing.md` §6 route (i) — needs design, or touched the Coverage Matrix, E9.6's
hard rule), **stop before assembling any `open-dispatch`**. There is no line
"the stage the Ticket indicates → spawn the corresponding `wds-*`" — that would be
exactly the headless invocation §2 forbids. Instead, follow steps 4-7
below.

## 4. The two options — table

| # | Option | Who does the A/S/D | Trigger | Default? |
|---|---|---|---|---|
| **(a)** | In-thread oracle | The Gerente itself, in its Opus context, applying the WDS method (Analyze/Scope/Design) as knowledge — **never invoking `Skill(wds-8)`** | Only when the Oracle Protocol (E9.1) reaches `--confidence high` for this specific decision (§6) | **No** — gated, future evolution |
| **(b)** | Wait on the owner | The owner, interactively, running `wds-8` themselves, with a real human present to honor the `WAIT FOR INPUT` gates | Whenever (a) doesn't reach high confidence — the normal/initial case | **Yes** — default path |

New design is exactly the class of work that **deserves human attention** (PRD 05
FR-6, Notes) — that's why the default is (b), not (a). (a) exists for when the oracle has
already accumulated enough style (E9.2) about in-thread design decisions — not on day
1.

## 5. The gate for (a) — reuse of the Oracle Protocol, no new machinery

There is no new config, no new script, to decide (a) vs (b). The gate is literally the
confidence mechanism the Oracle Protocol (E9.1) already has — reused, never
reimplemented:

1. The Gerente runs the Oracle Protocol (`.claude/skills/bagual-gerente-geral/references/
   oracle-protocol.md`) with `--tipo decisao-de-produto`, `--areas` including the Ticket's
   area **and** the fixed tag `wds8-design-in-thread` (so that precedents of this SAME
   class of decision — "can the oracle do in-thread design?" — are findable
   by `consult-precedent`/E9.2's history-aware gate, without being confused with other
   product decisions from the same area).
2. `--context` = what the Ticket asks for (new design); `--decision` = "execute route (i) in
   in-thread mode (a)" (the alternative being, implicitly, (b)); `--justification` = the
   reason this choice is safe now.
3. `--confidence high` is only honored (mechanically, by `record-decision`, never by
   assertion) if a real `--precedent` exists: a `decisao-de-produto` Ledger Entry with
   `estado: ativa`, `ratification: ratified` (or absent), from a **previous** execution
   of mode (a) that the owner has already reviewed and approved. **At the start of this
   protocol's life, no such precedent exists** — so `record-decision` mechanically
   downgrades to `low` (`downgrade_reason` explained), `proceed_dispatch: false`, and the
   route falls to (b) by construction, not by convention. This is what makes "(b) is the
   default" a mechanical guarantee (F10), not just a protocol sentence the persona could
   forget to follow.
4. Only after the owner ratifies (`set-ratification --status ratified`) at least one
   execution of mode (a) — and provided no conflicting correction exists for the same
   `--areas` (the same E9.2 history-aware veto) — can a FUTURE, similar decision
   legitimately claim `high` by citing that precedent, unlocking (a) for that specific
   Ticket.

**This is Story E9.8's Build Card "Autonomy: (a) in-thread OR (b) wait on the owner;
default (b)" made mechanical as its "future evolution"**: it is not a manual switch
someone flips one day — it is the same style-learning (E9.2) that already governs every
oracle decision, applied to this specific decision.

## 6. Mechanics of (b) — DEFAULT, "wait on the owner"

When `record-decision` returns `proceed_dispatch: false` (the normal case, §5.3):

1. **Do not** move the Ticket to `triado` (the Oracle Protocol's generic low-confidence
   destination) — move it to **`precisa-de-info`**, via `bagual-tickets`. This is a
   deliberate specialization, not an accidental deviation from the general protocol:
   `triado` assumes ratifying the decision alone unlocks the work (the Ticket goes back
   to `pronto-para-implementar` and the Gerente redispatches on its own); here, the
   genuine unblock isn't "the owner confirms a written sentence" — it is **the owner
   physically/interactively needing to run `wds-8`**, exactly the class of blocker
   `precisa-de-info` is already reserved for ("Ativação"/"Quem você é" in
   `gerente-geral.md`: "requires a literal action from the owner").
2. The Ticket's note (`## Log`, via `bagual-tickets`) cites the parked decision's
   `ledger_path` **and** a human-readable instruction: *"Waiting on the owner: run `wds-8`
   interactively (Analyze → Scope → Design) for this Ticket — the autonomous flow cannot
   get past wds-8's WAIT-FOR-INPUT gates (spike S3, see `wds-routing.md`)."*
3. Include the `pending_entry` in `decisions_pending` on the next `write-snapshot
   --pending-json` — the same mechanism already used by any low-confidence oracle
   decision (E9.1/E8.7); this is what makes the Morning Briefing (E8.7) surface this
   Ticket to the owner in the next interactive session, with no new wiring.
4. **What the owner does next is out of this protocol's scope.** They run `wds-8`
   interactively in THEIR OWN session (not a Gerente dispatch) — they can go as far as
   they want, including `[I]/[T]/[P]` if they decide to implement/publish themselves as a
   human at the keyboard. When done, if code work remains for the autonomous flow to
   pick back up, they update the Ticket themselves (via `bagual-tickets`, or directly)
   — `trilha` re-decided normally (`rapida`/`spec`/`epic`, the design is already done) and
   status back to `pronto-para-implementar`. None of this needs a Gerente mechanism
   — it's the owner using the system as they always could.

## 7. Mechanics of (a) — GATED, "in-thread oracle"

Only when `proceed_dispatch: true` (§5, a real, ratified precedent):

1. The Gerente **invokes no skill** — neither `wds-8`, nor an `Agent` sub-agent to
   do the work. It applies the WDS method (Analyze → Scope → Design) as knowledge itself,
   in its own Opus context — **exactly the same pattern already
   established in the "Planning Brain (E9.3)"** for `bmad-create-epics-and-
   stories`/`bmad-check-implementation-readiness`/`bmad-correct-course` (facilitator-only
   skills, S2/S3): "what they would do, you do in-thread". `wds-8` falls into the
   SAME class — this protocol is the concrete application of that class to product
   design.
2. **Analyze:** understand the Ticket's request against the already-existing canonical
   documents (Coverage Matrix, trigger-map, product-decisions — the same "documented
   product truth" `product-routing.md` §1 already uses).
3. **Scope:** decide the size of the design change (new scenario? existing
   scenario changed? new trigger?) without generating speculative content beyond what the
   Ticket asks for.
4. **Design:** write the update directly into the **three canonical documents** — and ONLY
   these three, never a fourth place:
   - `_bmad-output/C-UX-Scenarios/00-ux-scenarios.md` (Coverage Matrix/scenario)
   - `_bmad-output/B-Trigger-Map/trigger-map.md` (if the change affects goal→persona→force)
   - `_bmad-output/product-decisions.md` (the resulting behavior rule, same
     format `## [PRODUCT] Título — YYYY-MM-DD` already used by every
     existing entry)
5. **Explicit exception to `gerente-geral.md`'s "Quem você é" section:** these three
   files are the ONLY direct product-writing surface the Gerente has — and
   only when executing this protocol's mode (a) specifically (never as a
   general habit). They are not product code (`frontend/**`/`backend/**`/`supabase/**`) nor
   a `bmad-*`/`bagual-*` skill — they are the same canonical documents WDS itself
   would produce via `steps-d/step-01-design-update.md`, just written by the oracle instead
   of an interactive facilitator.
6. Record the conclusion: a note in the Ticket's `## Log` (via `bagual-tickets`) citing
   the (a) decision's `ledger_path` and a summary of what changed in the 3 documents.
7. **Stop here.** See §8 — nothing beyond Analyze/Scope/Design happens in this protocol,
   in either mode.

## 8. A/S/D-only boundary — `[I]/[T]/[P]` always outside the autonomous flow

**No exception, in EITHER mode (a) or (b):** the autonomous flow (the Gerente and any
sub-agent it dispatches) **never** advances to `[I]/[T]/[P]` (Implement/Test/Publish
— branch, PR, deploy) of the `wds-8` pipeline (`workflow-implement.md`/`workflow-test.md`/
`workflow-deploy.md`). This is reinforced across three independent layers, not one
lone prose promise:

1. **Structural (already existing):** the Gerente already never executes product
   code (`frontend/**`/`backend/**`/`supabase/**`) — `wds-8`'s `[I]/[T]/[P]` touch
   exactly that surface. The rule "the Gerente never executes code" (the "Quem você
   é" section) already blocks this by construction, even without this protocol.
2. **Explicit in this protocol (§7.7):** mode (a) stops at Design — no instruction
   in this document takes the Gerente further than that.
3. **A PRD non-goal (ideias/prd-05-wds.md § "Não-Objetivos"):** "Does not use WDS as
   an implementation/test engine — it's a lens; Implement/Test/Deploy are BMad." If
   the design decision (mode (a)) reveals real code work
   needed, that becomes a **normal** Ticket/`trilha` decision (`rapida`/`spec`/
   `epic`), dispatched by the already-existing BMad pipeline (`bagual-epic-runner`/
   `bmad-quick-dev`) — never by `wds-8`'s `workflow-implement.md`. The two pipelines
   never touch each other.

When the owner runs `wds-8` interactively (mode (b), §6.4), they CAN go all the way to
`[I]/[T]/[P]` like any human at the keyboard — that is not "the autonomous flow doing
`[I]/[T]/[P]`", it's the owner using the tool as they always could. The guardrail is about what
the **autonomous system** (Gerente + dispatches) does on its own, never about what the owner
does interactively.

## 9. Light route (ii) remains autonomous — it never touches wds-8

No part of this protocol applies to **route (ii)** (`product-routing.md` §6) — "small
rule already decided" records the change as a `decisao-de-produto` Ledger entry
(`wiki/ledger/decisao-de-produto/`), which **never** invokes `wds-8` or any `wds-*`. It
remains 100% autonomous, no gate, no waiting on the owner.

Both continue exactly as they were before this story — this protocol does not touch them.

## 10. Composition — nothing reimplemented

- **Oracle Protocol (E9.1)** — `gerente_oracle.py record-decision`/
  `set-ratification`: reused in full as the (a) vs (b) gate (§5). No new
  script/config.
- **`bagual-tickets`** — composition to move the Ticket to `precisa-de-info` (§6) or
  annotate (a)'s conclusion (§7.6). Never edit `board.yaml`/the Ticket's `.md` by hand.
- **Planning Brain (E9.3)** — the "in-thread for facilitator-only skill" pattern
  already established is reapplied to `wds-8` (§7.1), not reinvented.
- **`write-snapshot --pending-json`/Briefing (E8.7)** — reused to surface the
  (b) parking to the owner, with no new wiring.

## 11. Proof — no path spawns `wds-8` headless

Verifiable by grep, whenever this protocol is reviewed: no instruction in
`.claude/skills/bagual-gerente-geral/**`, `project_controll/gerente/**`, or any
`gerente_*.py` contains a call to `Skill(wds-8`/`Agent(...wds-8...)`/"invoke
wds-8"/"spawn wds-8" outside the explicit "this is forbidden" context (§2 above). See
Story E9.8's Dev Agent Record for the exact commands run and the output confirming
zero hits.

## 12. Worked examples

See `ideias/sistema-artifacts/E9-8-wds8-in-thread-ou-dono.md` § Validação for the
complete cases: (1) Ticket via route (i) with new design → no precedent → default (b), `record-
decision` downgrades to `low`, Ticket parked in `precisa-de-info`; (2) the SAME Ticket
after a ratified precedent exists → gated (a), `high` honored, in-thread A/S/D
over fixture documents, `[I]/[T]/[P]` never reached; (3) Ticket via route (ii) → never touches
this protocol; (4) grep showing zero occurrences of a headless `wds-8` invocation.
