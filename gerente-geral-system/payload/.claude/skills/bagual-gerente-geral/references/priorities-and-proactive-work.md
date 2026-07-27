# Phase 2: priorizar

**Escalated decisions + reconciliation (Story E9.5, PRD 02 FR-6) — ALWAYS first, before ordering the
normal queue.** 🔴 **Since TCK-20260727143826-7573 (2026-07-27), the `bagual-tickets` skill no longer
auto-commits any `trilha`** — the mechanical classifier it used to call
(`classify_trilha.py`) is retired as a trilha decider (kept on disk for history, never deleted; see
`wiki/ledger/decisao-tecnica/roteamento-de-trilha-e-plano-antes-da-execucao.md`). Every Ticket
reaching `pronto-para-implementar` now arrives marked `escalonar: true` in `board.yaml`
unconditionally — there is no longer a "committed automatically" subset distinct from "escalated":
**100% of Tickets are yours to decide `trilha` for**, by judgment, using the criteria table in
`dispatch-and-review.md` step 1 (`rapida`/`spec`/`epic`) plus product routing below (`wds`). Script:
`project_controll/gerente/scripts/gerente_escalation.py` (`list-escalated`/`dead-letter-check`/
`sample-decisions`/`record-sample-review`/`orphan-sweep`) — full contract in
`project_controll/gerente/README.md` § "Escalation decided by the Gerente (E9.5)", read it in full
before the first time this step fires.

1. **`list-escalated`** — reads only `board.yaml` (never opens each `.md`, F20). For EACH ticket
   returned:
   - **a. Product routing (Story E9.6, PRD 05 FR-1/FR-1b) — ALWAYS first, before formulating step
     b's trilha decision.** Apply the 3-question test (behavior/rule? flow/navigation? visible
     surface with product meaning?) against the **documented product truth** (`trigger-map` +
     Coverage Matrix `_bmad-output/C-UX-Scenarios/00-ux-scenarios.md` +
     `_bmad-output/product-decisions.md`) — full protocol, hard exclusions, safety bias, and the
     3-route table in `project_controll/gerente/product-routing.md` (read it in full before the
     first time this sub-step fires). Operational summary:
     - **Hard mechanical rule:** run `python3 project_controll/gerente/scripts/
       gerente_product_routing.py check-coverage-touch --touched "<ticket's pages/area>"` (terms
       extracted from `area`/`## Locais afetados`/description). A `forced_route_i: true` forces
       route **(i)** with no exception — this is not fine judgment, it's a hard test (route ii
       never touches the Coverage Matrix, it's contractually read-only over the design truth). A
       `forced_route_i: false` does **not** exempt you from applying the 3-question test by
       judgment — it's only the absence of a textual match, never proof of "doesn't change
       anything".
     - If no question is YES, or the ticket falls into a hard exclusion (identical refactor,
       perf with no behavior change, bugfix restoring already-documented behavior, purely cosmetic,
       infra/test-only) → route **(iii)**: no document maintenance; move on to step b normally.
     - If it changes the product and needs design (new/changed scenario, flow redesign) **or** the
       detector above forced it → route **(i)**: step b's `trilha` decision IS `wds` (these aren't
       two independent decisions — this classification is the reason). The real execution (Story
       E9.8 — `wds-8` **never** runs headless, see `wds-routing-execution.md`) only happens later,
       in the "despachar" phase — here, at escalation time, it's only the routing.
     - If it changes the product but is a small, already-decided rule (no design, no Coverage
       Matrix touch) → route **(ii)**: **orthogonal to `trilha`** (which keeps being decided
       normally in step b, by the ticket's actual work). Record the change as a `decisao-de-produto`
       Ledger entry (`wiki/ledger/decisao-de-produto/`, via the `on_complete` contract), capturing
       what changed (before→after), where, why, and whether the old behavior is now a bug. Cite the
       produced Ledger entry's path in the ticket's `## Log`. *(QA-builder-based logging was removed
       from this kit — route (ii) now registers directly in the Ledger.)*
     - **Combined case** (touches the Coverage Matrix **and** matches/updates a recorded decision)
       → route **(i) dominates**; the `product-decisions.md` enrichment (what route ii would do)
       happens as a side effect of the same ticket, never as a standalone route (ii) — never
       conclude (ii) alone when (i) also applies.
     - **When genuinely unsure, route it** (a false negative — a product change slips through and the
       docs go stale — is worse than a false positive).
   - **b. Decide the `trilha`** via the "Oracle Protocol" (see `oracle-protocol.md` — step 0
     `consult-precedent`, formulate `--context`/`--decision`/`--justification`, `--confidence` only
     `high` with a real precedent) — if sub-step a above concluded route (i), the trilha IS `wds`;
     otherwise, decide by the ticket's actual work (`rapida\|spec\|epic\|correct-course`), using the
     criteria table in `dispatch-and-review.md` step 1 (`rapida` = pontual/simple; `spec` = bigger
     than pontual, smaller than epic; `epic` = multiple tickets/large or reiterated effect). The
     decision itself is judgment — never a fixed heuristic here (same discipline as "promotion to
     the Ledger is judgment", below). 🔴 If the decided trilha is `spec` or `epic`, the "despachar"
     phase still has to clear the `spec-epic-routing-execution.md` John-never-headless gate before
     any execution dispatch opens — deciding `trilha` here does not skip that gate. After
     `record-decision`, **commit via `bagual-tickets`
     (Resolve, composition — the skill is NEVER re-edited in this story, E9.4 is already its side of
     the contract)**: write `trilha: <decided>` + `escalonar: false` + a `## Log` line citing the
     oracle decision's `ledger_path` (and, if the route was (ii), the `decisao-de-produto` Ledger
     entry from sub-step a). **Promotion to the Ledger is judgment, no fixed heuristic** (PRD 02
     §4.4, decided 2026-07-10) — only when you notice real reuse potential (the same decision
     pattern is likely to repeat), also write `ledger_refs` pointing to the entry; promotion
     mistakes (an entry that shouldn't have been promoted, or one that should have and wasn't) are
     normal — they feed the curation (librarian) and style learning (E9.2) like any other Ledger
     entry, never silently reverted.
2. **`sample-decisions --sample-size N`** — a sample (never 100%) of tickets whose `trilha` was
   committed AUTOMATICALLY by the skill (`trilha` != null + `escalonar: false`), not yet reviewed
   (tracked in `sampled-decisions.json`, your own artifact). 🔴 Since `classify_trilha.py`'s
   retirement (TCK-20260727143826-7573), the skill no longer auto-commits any NEW ticket this way —
   this step now only surfaces the **historical** backlog the retired script already committed
   before this change (the 54 `rapida` tickets cited in the ledger decision's "Consequences");
   re-triaging that backlog against the new 3-way criteria is a separate, still-pending action, not
   done by this change. For each one: ratify (the
   auto-committed trilha is right) or correct (it isn't). Record the verdict with
   `record-sample-review --verdict ratificado|corrigido ...`. **`--verdict ratificado`** only needs
   `--ticket`/`--trilha-auto`/`--note`, as always. **`--verdict corrigido` is ONE SINGLE COMMAND
   since Story E15.3 (T2.3) — not two.** Besides `--trilha-corrigida`, it now REQUIRES the
   decision-trace fields (`--question`/`--justification`/`--context`; `--tipo`/`--areas` optional,
   with a default) and, in the SAME invocation, internally calls `gerente_oracle.py::
   record_decision()` + `set_ratification(status="corrected")` (direct import, never subprocess) —
   one call produces, by construction, BOTH artifacts: `sampled-decisions.json` **and** the
   `ratification: corrected` Ledger Entry that E9.2's history-aware gate
   (`find_corrected_contradictions`) already knows how to consume to veto `--confidence high` on
   future similar decisions (same `tipo` + `areas` overlap). If the trace fields are incomplete, the
   command refuses (exit != 0, clear error citing the missing fields) **without writing anything**
   (neither `sampled-decisions.json` nor the Ledger) — it never accepts a "partial" correction. If
   the Ledger write fails after the decision was already recorded (`ratification: pending`), the
   whole operation aborts and `sampled-decisions.json` is NOT touched — the `pending` entry stays
   visible via `gerente_oracle.py list-pending` for a manual `set-ratification` retry (same
   "all-or-nothing" discipline as E15.2). You NEVER need to (nor should) run `gerente_oracle.py
   record-decision`/`set-ratification` manually for a corrected sample — this single command already
   does it. Include the array of reviewed samples (with `verdict`) in the next `write-snapshot
   --sample-review-json '[...]'`, so the Briefing can render them (even with the verdict still
   pending, if you didn't get to review all of them this cycle).
3. **`dead-letter-check`** — escalated tickets stuck (no update at all) beyond the configured limit
   (`escalation.config.json`, default 3 days) — F20 hardening, "an escalated-never-decided ticket
   never rots". Include the result in the next `write-snapshot --dead-letter-json '[...]'` — this is
   what forces you (or the owner) to look, instead of leaving the ticket invisible forever; never
   resolve a dead letter silently without recording why it stayed stuck that long.

**Note — `orphan-sweep` does NOT live here.** The `em-implementacao` orphan sweep (Story E9.5)
already ran in step 0 of "Activation" (see `activation-and-lock.md`, BEFORE your own
`acquire-lock` — read why there: running it after acquiring your lock would make the sweep see your
OWN fresh lock and never revert anything). If something was reverted, log a diary line now
(`append-diario --event decidi --text "reverted <ticket>: <reason from the orphan sweep>"`) — this
is only the recording point, not where the sweep runs.

Among the `pronto-para-implementar` Tickets (board.yaml), sort by `priority` (`alta` > `media` >
`baixa`) and, within the same level, prefer the oldest (`created`). Read each Ticket's `trilha` to
know what kind of dispatch it calls for (see PRD 00 §3 Glossary: `rapida | spec | epic | wds |
correct-course`). Work **one item at a time in the shared root checkout** — real multi-epic
parallelism (dependency graph, per-Track failure isolation) is still the Execution Orchestrator's
territory (PRD 03, E10/E11), not this persona's. But **disjoint-Ticket parallelism via an isolated
worktree** is already yours, conditionally (Story TCK-20260717131540-622d) — see "Ticket parallelism"
in `dispatch-and-review.md` before deciding to dispatch more than one Ticket this pass.

**Empty queue → proactive work with a hard cap + historical dedup (Story E8.5 — REAL since this
story, replaces the provisional "stop and report" from E8.1).** If there is NO `pronto-para-
implementar` Ticket at all, you don't sit idle, but you also don't invent arbitrary work — you pick
from a **restricted, very-low-risk catalog**, `project_controll/gerente/proactive-catalog.md` (read
it in full before the first time you enter this branch — it documents the content and guardrails of
each category; here only the mechanics). Repeat this mini-loop until `cap-reached` or until a real
Ticket reappears in the queue (a new Ticket can show up at any time — e.g., the owner added one by
hand — and always takes priority over continuing proactive work):

1. `python3 project_controll/gerente/scripts/gerente_proactive.py next-task --root
   project_controll/gerente --cycle-id <this cycle's id>`. If `"verdict": "cap-reached"`, **stop the
   proactive work** and move to the "parar" phase with `stop_reason: fila-vazia` but explicitly
   reporting "stopped by proactive cap" (not "by quota" — distinct guardrails; `check-lock`/
   `gerente_quota.py check` keep applying independently). If `"verdict": "go"`, read
   `category.id`/`category.label` from the response.
2. Dispatch a **single** `Agent` sub-agent (**always `model: "sonnet"`**, foreground, same
   discipline as "never leave a dispatch hanging" in `dispatch-and-review.md`) instructed to:
   (a) execute ONLY the chosen category's investigation, per `proactive-catalog.md` § for that
   category — reading/grep/existing tests, **never** `Edit`/`Write` over
   `frontend/**`/`backend/**`/`supabase/**`/any `bmad-*`/`bagual-*` skill; (b) return a list of
   findings (0 to N), each with a title + description + `file:line` evidence when applicable —
   never a diff, never a claim of "already fixed".
3. For each returned finding (if none, skip to step 4): run `python3
   project_controll/gerente/scripts/gerente_proactive.py dedup-check --root
   project_controll/gerente --tickets-dir project_controll/tickets --title "<title>"
   --description "<description>"` — this scans the **full proactive history**, including
   `concluido`/`descartado` (the dimension `bagual-tickets` alone doesn't cover — it only dedups
   against open tickets). If `"duplicate": true`, **do not create the Ticket** — log in the diary
   (`gerente_state.py append-diario`) that the finding is already known, citing
   `best_match.ticket_id`; this is exactly what F24 requires (never re-file the same "3 bugs" every
   night). If `"duplicate": false`, invoke the `bagual-tickets` skill `--headless` (Add, or Triage/
   Resolve for the `refino-de-tickets` category — see the doc) — it runs its own full pipeline
   (raw-check, dedup against OPEN tickets, `product-decisions.md` check, verification/expansion) on
   its own; you never skip or reimplement those steps. In `--headless` mode, the Ticket is already
   born `origem: proativo` by default.
4. After processing all of this iteration's findings, run `python3
   project_controll/gerente/scripts/gerente_proactive.py record-proactive --root
   project_controll/gerente --cycle-id <same cycle_id> --category <category.id from step 1>
   --outcome <summary: "ticket-filed"|"duplicate-skipped"|"no-finding"|"ticket-refined">
   [--tickets-filed-json '[...]'] [--duplicates-skipped N]` — **exactly once per iteration**, even
   if 0 findings turned into a Ticket (the real cost is the analysis sub-agent's dispatch in step 2,
   not how many Tickets came out of it). Go back to step 1.

Never call `bagual-tickets`/edit code from an analysis sub-agent's report without going through
`dedup-check` first — skipping that step is exactly the scenario F24 forbids.
