# Oracle Protocol (E9.1)

Canonical reference: `ideias/prd-00-sistema-orquestrador.md` FR-5 (§4.3) and the F10 hardening
("blast radius gated by confidence"). Script: `project_controll/gerente/scripts/gerente_oracle.py`
(`record-decision`/`list-pending`/`set-ratification`) — never write/edit an oracle Ledger Entry by
hand, always through these subcommands (they guarantee atomic writes, the mechanical confidence
gate, and the self-check). Script mechanics/schema are documented in full in
`project_controll/gerente/README.md` § "Oracle (E9.1)" — this file only carries the Gerente's
operational "when/how to decide" recipe, not the script internals.

## When the protocol fires

1. **A sub-agent you dispatched (the "despachar" phase) returns `outcome: pendencias`** with
   `pending_items` in `{ticket, note}` format (the same marker channel as E8.4,
   `close-dispatch --pending-json`) — the `note` is the decision question the execution layer
   raised. This is the standard "ask the Gerente, not the owner" channel: a sub-agent that today
   would stop to ask the user should instead record the question as `pending_items` and hand
   control back to you.
2. **You yourself, during "priorizar"/"despachar"**, notice that a Ticket cannot be mapped to a
   trilha/skill without first resolving a scope/product/trade-off question.

## Step by step

0. **Consult precedent BEFORE formulating the decision (E9.2 — style learning).** Run:
   ```
   python3 project_controll/gerente/scripts/gerente_style.py consult-precedent \
     --ledger-root wiki/ledger --tipo decisao-tecnica|decisao-de-produto|decisao-de-arquitetura \
     --areas "a,b"
   ```
   using the SAME `--tipo`/`--areas` you intend to use in `record-decision` — it is a pure query,
   **it never writes anything**. Read `suggested_confidence`/`matches_ratified`/`matches_corrected`/
   `reason`: if `matches_corrected` comes back non-empty (the owner already corrected something
   similar — same `tipo` + overlapping `areas`), treat that as a strong low-confidence signal, even
   if a favorable `matches_ratified` ALSO exists — a similar correction always outweighs similar
   support (this is how the owner's "style" gets learned: it is the Ledger entries themselves,
   ratified and corrected, NEVER a trained model — PRD 00 §4.3/FR-6). This is a HINT to avoid
   wasting the turn trying for `high` without evidence — `record-decision` (step 3) already applies
   this SAME veto mechanically on its own even if you skip this step, but consulting first lets you
   pick a better `--areas`/`--precedent` and understand the "why" that goes into `## Consequências`.
1. **Formulate the three trace fields** — never decide without all three: `--context` (what
   prompted the question — the problem, not the solution), `--decision` (the decision itself,
   actionable), `--justification` (the why — becomes `## Consequências`).
2. **Determine confidence mechanically, never by "gut feel":**
   - You may only ask for `--confidence high` if you can cite `--precedent <path>` pointing to an
     **already-existing** Ledger Entry, `estado: ativa` (not just "not retired" — a `candidata`/
     pending one, including your own from minutes ago, never counts as precedent) and
     `ratification` absent or `ratified` (never `corrected`/`pending`). Look for that precedent in
     `wiki/ledger/decisao-tecnica|decisao-de-produto|decisao-de-arquitetura/` — step 0
     (`consult-precedent`) already does this search for you, including an informational
     (never gating) sweep of `decisions.md`/`product-decisions.md` by section whose title mentions
     the same `areas`.
   - **No precedent that survives verification → don't ask for `high`.** The script itself
     downgrades to `low` regardless (it never trusts your claim — that's the F10 mechanical
     guarantee), but don't waste the turn trying "high" without a real precedent in hand.
   - **Even with a valid `--precedent` in hand, `record-decision` can still downgrade to `low`
     (E9.2 — history-aware gate):** if there exists, for the same `tipo`, a `ratification: corrected`
     decision whose `areas` overlap enough with yours (configurable threshold per category in
     `project_controll/gerente/oracle.config.json` — more sensitive categories, e.g.
     `decisao-de-produto`, require more support overlap, but ANY contradiction overlap already
     counts), the script vetoes `high` on its own and returns `contradicting_corrected` in the
     response explaining why. Do not try to work around this by reading step 0's
     `matches_ratified` and ignoring a competing `matches_corrected` — the veto is intentional and
     is the core of FR-6.
   - When genuinely unsure whether the precedent applies, treat it as low confidence — never the
     opposite.
3. **Record the decision:**
   ```
   python3 project_controll/gerente/scripts/gerente_oracle.py record-decision \
     --ledger-root wiki/ledger --ticket <id> --tipo decisao-tecnica|decisao-de-produto|decisao-de-arquitetura \
     --question "<question raised>" --decision "<decision>" \
     --justification "<why>" --context "<what prompted it>" \
     --confidence low|high [--precedent <path>] [--areas "a,b"]
   ```
   Read `proceed_dispatch`/`blast_radius`/`ledger_path`/`ticket_note`/`pending_entry`/
   `contradicting_corrected` from the response.
4. **Ticket (mandatory trace, AC1 — "Ticket + Ledger"):** invoke `bagual-tickets` to attach
   `ticket_note` (already formatted by the response) to the Ticket — never edit `board.yaml`/the
   ticket's `.md` by hand.
5. **Act per `proceed_dispatch`:**
   - **`true` (high confidence):** work depending on this Ticket stays unblocked — dispatch/proceed
     normally in this same run (the "despachar" phase), as if the question had never paused the
     flow. The decision is STILL reported to the owner in the Briefing (include the response's
     `pending_entry` in `decisions_pending` on the next `write-snapshot --pending-json`) — high
     confidence doesn't mean "hide it from the owner", only "don't block work until they see it".
   - **`false` (low confidence/parked):** work depending on this Ticket is **not** dispatched/merged
     this cycle. Move the Ticket to `triado` via `bagual-tickets`, with a note citing `ledger_path`
     ("parked — low-confidence oracle decision, awaiting owner ratification"). Include the
     `pending_entry` in `decisions_pending` on the next `write-snapshot --pending-json` — that's
     what makes the owner's next interactive session show the pending decision in the Briefing
     (Story E8.7).
   - In both cases, move on to the next item in the cycle — the oracle protocol is never, by
     itself, a reason to stop the whole cycle.

## Ratification (next interactive session)

When the owner reviews the Briefing and confirms or corrects a pending oracle decision, run:
```
python3 project_controll/gerente/scripts/gerente_oracle.py set-ratification \
  --entry <ledger_path> --status ratified|corrected [--note "<owner's note>"]
```
- **`ratified`**: the entry is promoted `candidata -> ativa` automatically — from now on IT ITSELF
  can be cited as `--precedent` for a future high-confidence decision. If the work was parked
  (Ticket in `triado`), move it back to `pronto-para-implementar` (via `bagual-tickets`) — the
  "morning fix" here is **ratifying a park**, never reverting already-merged multi-epic work.
- **`corrected`**: the entry keeps whatever `estado` it already had — `ratification: corrected` is
  the signal, written to disk, that Story E9.2 (style learning) consumes on the next cycle via
  `consult-precedent`/`record-decision`'s history-aware gate (steps 0 and 2 above); do not delete or
  rewrite the entry. If the owner's correction reveals the RIGHT decision (not just "this one was
  wrong"), record it as a NEW `record-decision` (ideally citing a better precedent, if one exists) —
  a `corrected` entry never again serves as a high-confidence precedent for anything (mechanical
  verification by the script itself), and starts VETOING future similar decisions (same `tipo` +
  `areas` overlap) even when they cite another valid precedent.

To track SM-2 ("% of oracle decisions ratified", PRD 00 §7) — e.g. when assembling the
Briefing — run `python3 project_controll/gerente/scripts/gerente_style.py sm2
[--tipo decisao-tecnica|decisao-de-produto|decisao-de-arquitetura]`: it returns
`ratified`/`corrected`/`pending`/`decided`/`total`/`pct_ratified`, always DERIVED from the real
Ledger trace (never a fixed number) — `pct_ratified` is `null` when no decision has been ratified
or corrected yet (don't confuse "no data" with "0%").
