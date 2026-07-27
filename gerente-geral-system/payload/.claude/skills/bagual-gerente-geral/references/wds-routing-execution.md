# Route (i) execution — wds-8 never headless (E9.8)

Canonical reference: `ideias/prd-05-wds.md` FR-6 and `ideias/fase-0-spikes.md` § S3 (`wds-8` was
**tested live** and locked up on the very first Analyze step even with auto-approve — this is not a
hypothesis, it's a confirmed fact). The full contract, with the gate's exact mechanism and the
three canonical documents, is in `project_controll/gerente/wds-routing.md` — read it in full before
the first time a Ticket with `trilha: wds` reaches the "despachar" phase. This file is only the
operational summary.

**When it fires:** in the "3. despachar" phase (see `dispatch-and-review.md`), step 1 (mapping
`trilha` → skill), when `trilha == wds` (decided by "Product routing (Story E9.6)" via route (i)).
**Hard rule, no exceptions:** you never invoke `wds-8` (nor any of its `workflow-*.md`) as a
headless sub-agent — not even "just the Analyze step". There is no dispatch line "trilha wds →
spawn the corresponding wds-*" — stop before assembling any `open-dispatch` for this Ticket and
follow the sub-step below instead.

**The decision — (a) vs (b), (b) is the default:**
1. Run the "Oracle Protocol" (see `oracle-protocol.md`) for THIS specific question —
   `--tipo decisao-de-produto`, `--areas` = the Ticket's area + the fixed tag
   `wds8-design-in-thread`, `--decision` = "execute route (i) in in-thread mode (a)".
2. `--confidence high` is only honored if you cite a `--precedent` from an **existing**
   `decisao-de-produto` Ledger Entry, `estado: ativa`, `ratification: ratified` (or absent), from a
   **previous** execution of mode (a) already reviewed by the owner. **At first, no such precedent
   exists** — `record-decision` mechanically downgrades to `low`, `proceed_dispatch: false`. That is
   what makes "(b) is the default" a mechanical guarantee (F10), not a prose promise.
3. **`proceed_dispatch: false` (the normal case) → mode (b), wait for the owner:** move the Ticket
   to **`precisa-de-info`** (not `triado` — a deliberate specialization, see `wds-routing.md` §6:
   real unblocking requires the owner to run `wds-8` interactively, not just ratify a written
   sentence) via `bagual-tickets`, citing the `ledger_path` + the instruction "awaiting the owner
   running wds-8 interactively". Include the `pending_entry` in `decisions_pending` on the next
   `write-snapshot --pending-json` (same mechanism as any low-confidence decision — surface it in
   the Briefing, E8.7, no new wiring). What the owner does next (how far they take `wds-8`,
   including `[I]/[T]/[P]` if they decide to) is out of this protocol's scope — it's their
   interactive session, not a dispatch of yours.
4. **`proceed_dispatch: true` (rare, a real and ratified precedent) → mode (a), in-thread oracle:**
   you yourself — never a sub-agent, never `Skill(wds-8)` — apply Analyze/Scope/Design as knowledge
   (same pattern as the "Planning Brain" for facilitator-only skills) and write the update directly
   to the three canonical documents (see the identity/inviolable-rules core's exception on direct
   writes): `_bmad-output/C-UX-Scenarios/00-ux-scenarios.md`, `_bmad-output/B-Trigger-Map/
   trigger-map.md`, `_bmad-output/product-decisions.md`. Log the conclusion in the Ticket's
   `## Log` (via `bagual-tickets`), citing the `ledger_path`. **Stop there.**

**A/S/D-only boundary, no exception — `[I]/[T]/[P]` never in the autonomous flow, in any mode:**
you already never execute product code (`frontend/**`/`backend/**`/`supabase/**` — see the
identity/inviolable-rules core), which already bars `[I]/[T]/[P]` from `wds-8` by construction;
mode (a) stops explicitly at Design (step 4 above, never advances); and `ideias/prd-05-wds.md` §
"Non-Goals" confirms that Implement/Test/Deploy are BMad territory (`bagual-epic-runner`/
`bmad-quick-dev`), never `wds-8`'s — if the design reveals code work, that becomes a **normal**
Ticket/`trilha` (`rapida`/`spec`/`epic`), never `wds-8`'s `workflow-implement.md`.

**Route (ii) stays 100% autonomous — it never touches this protocol, never invokes
`wds-8`.** No change for it.
