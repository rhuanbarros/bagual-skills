# Phase 5: registrar / Phase 6: parar

## 5. registrar

- **Ticket:** invoke `bagual-tickets` (composition, never reimplement the skill's transition/dedup
  logic) to move the Ticket to the real state observed in phase 4.
- **Ledger:** classify whether THIS Gerente cycle (the prioritization decision, a choice between
  dispatch alternatives, a scope decision of the Gerente's own) — not the internal work already
  logged by the dispatched skill, which has had its own `on_complete` since Story E6.6, and not an
  oracle decision already recorded via `gerente_oracle.py record-decision` in the "revisar" phase
  (E9.1 — that flow already writes and runs its own self-check; don't re-emit the same decision
  here) — produced something Ledger-worthy per `wiki/ledger/on-complete-contract.md` §2. When in
  doubt, **do not emit** (that's the contract's own strict default). If you do emit, always `estado:
  candidata`, always run `python3 wiki/ledger/scripts/validate_ledger.py --ledger-root wiki/ledger
  --json` as a self-check before considering the phase done.
- **Retrospective debt → Tickets (never let it die in the doc).** When the dispatch was an epic and
  it produced a **retrospective** (or the skill's result lists follow-ups/tech debt/deferred gaps),
  do NOT leave those items as plain text in the retro doc or in `deferred-work.md` — they get lost.
  For each debt/follow-up item that doesn't yet **have** a Ticket, materialize it via
  `bagual-tickets` (composition: raw-check → dedup against the board → create), with a short summary
  + the file:line pointer the retro already provides. Let the skill itself do the dedup (it already
  checks for duplicates against `board.yaml`), don't do it by hand — an item that already has a
  matching Ticket is skipped, not recreated. Report in the Briefing how many follow-ups became a
  Ticket (and which were skipped by dedup). This closes the gap observed in cycle
  `cycle-20260713-225357` (Epic 38's retro found 2 debts — admin parity for `down_payment`;
  `edit_client_vehicle` doesn't re-sync on vehicle swap — that stayed only as action items and never
  became a Ticket).
- **Meta-defect → `area: meta-sistema` Ticket (self-healing, E22.1).** When YOU detect a defect in a
  **meta-skill** during the cycle — a dispatch that failed due to a skill bug (not a product one), a
  gate that decided wrong, a structural gap (like E19's), an inconsistent script output, a
  contradictory skill instruction — do NOT let it become just an operational note (knowledge). Also
  materialize a **Ticket via `bagual-tickets`** with `area: meta-sistema` and `category: meta-bug`
  (dedup against the board), describing the defect + the meta-skill's file:line + how to reproduce
  it. This is the queue the **self-heal** dispatch consumes (E22.3, see "Self-healing" in
  `self-healing.md`). Distinguish: operational-note/Ledger = *knowledge*; this Ticket = *repair work
  to do*. (Detection can happen in the "revisar" phase — a dispatch that came back failed due to a
  defect in the tool itself — or here; log it as soon as you notice.)

## 6. parar

Before starting a NEW unit of work (going back to phase 2), check quota awareness — real since
Story E8.3, no longer a best-effort read of just the snapshot. **Since Story E15.2, you no longer
call `record-usage` manually for a dispatch** — each dispatch already recorded its quota
mechanically via `close-dispatch --tokens-used` in the "despachar" phase (see `dispatch-and-
review.md`), as an atomic side effect of the same call that closed the dispatch. Manual
`record-usage` (`python3 project_controll/gerente/scripts/gerente_quota.py record-usage --root
project_controll/gerente --cycle-id <this cycle's id> --tokens <estimate> --note <what it was>`) is
now **restricted to the accepted residual: your own standalone Opus turns** within the cycle (e.g.,
at every phase transition, or a long analysis you did yourself without dispatching a sub-agent) —
never again to cover a dispatch, which is already covered automatically. (See
`project_controll/gerente/README.md` § Quota (E8.3)/§ Dispatch (E8.4) for what counts in that
residual and its honest limits.) Here, in the "parar" phase, run:
```
python3 project_controll/gerente/scripts/gerente_quota.py check \
  --root project_controll/gerente --cycle-id <same cycle id> --stop-diario
```
This reads `~/.claude/rate-limits-state.json` (which may be FROZEN in a headless cycle — written by
an interactive session's statusline hook) **and** the cycle's own self-tracking accumulator, and
returns the **strongest** (most conservative) signal of the two against a configurable threshold
(`quota.config.json`, default 85%). If `"verdict": "stop"`, **do not** start anything else — the
`--stop-diario` already wrote `parei-por-cota: <reason>` in `diario.md`/`diario.jsonl` for you;
report "stopped for quota" citing `stronger_signal_pct` and `stronger_signal_source` from the
output. If the queue went empty and you didn't enter the proactive branch (e.g., degradation,
`project_controll/gerente/` legitimately absent), stop and report "stopped by completion — empty
queue". If you entered the proactive branch (phase 2) and it ended by `cap-reached`, report "stopped
by proactive cap" (cite `count_so_far`/`cap_per_cycle` from `next-task`'s last response) — a
distinct guardrail from quota, even though both use `stop_reason: fila-vazia` in the snapshot (there
is no third `stop_reason` value just for this; the distinction lives in the report text and the
diary). If something blocked in a way you couldn't work around, stop and report "stopped by
blockage", describing the Ticket and the reason. Also keep the `check`'s JSON — the
`write_snapshot_quota_args` field carries the exact arguments (`--quota-five-hour`,
`--quota-self-tokens`, `--quota-stronger-pct`, etc.) to pass along to `write-snapshot` below, without
you having to recompose the flag names by hand.

**Before ending, always confirm the consistency invariant (updated for the background default —
Story TCK-20260717131540-622d):**
- No Ticket was left in `em-implementacao` without a genuinely in-flight dispatch you're tracking.
- **Ending the cycle with dispatches legitimately in flight (background, notification not yet
  arrived) is normal, no longer a violated invariant** — the real condition is: every dispatch still
  in flight is recorded in `estado-atual.yaml` (`dispatches[]`, with `dispatch_id`) and therefore
  reconstructible/reconcilable by the next cycle/wake via `list-inflight`/`read-result`/
  `reconcile-orphan-dispatch` (step 0 of "Activation"). No sub-agent you dispatched can fall outside
  this trace — that, and only that, is the "hanging dispatch" that stays forbidden.
- Every Ticket you touched this cycle has a current state coherent with what actually happened (not
  what you expected to happen).

**Close the cycle's operational state (Story E8.2 — whenever `project_controll/gerente/` exists,
see step 0 of "Activation"):**
```
python3 project_controll/gerente/scripts/gerente_state.py write-snapshot \
  --root project_controll/gerente --marker end --cycle-id <same id as the start> \
  --started-at <start ts> --ended-at <now> --phase parar \
  --stop-reason cota|fila-vazia|bloqueio \
  [--quota-five-hour N --quota-seven-day N --quota-source STR --quota-read-at ISO \
   --quota-self-tokens N --quota-self-pct N --quota-stronger-pct N \
   --quota-stronger-source STR]   # from the `check` above (Story E8.3) — see write_snapshot_quota_args \
  [--sample-review-json '[...]' --dead-letter-json '[...]']   # Story E9.5 — this cycle's reviewed
   # samples (with `verdict`) and the `dead-letter-check` result, see
   # "Escalated decisions + reconciliation (E9.5)" in `priorities-and-proactive-work.md` \
  [remaining cycle fields]
python3 project_controll/gerente/scripts/gerente_state.py append-diario \
  --root project_controll/gerente --event CICLO-FIM --cycle-id <same id>
```
**Write the Morning Briefing (Story E8.7) — always, right after the `append-diario CICLO-FIM` above
and before the `release-lock` below, so the Briefing can already read this cycle's complete
`diario.jsonl`/`estado-atual.yaml`:**
```
python3 project_controll/gerente/scripts/gerente_briefing.py write-briefing \
  --root project_controll/gerente --cycle-id <same id as the start> \
  --started-at <start ts> --ended-at <now> \
  --stop-reason cota|fila-vazia|bloqueio \
  [--stop-detail teto-proativo]   # only when the proactive branch stopped by cap-reached
python3 project_controll/gerente/scripts/gerente_state.py release-lock \
  --root project_controll/gerente --token <the token acquire-lock returned>
```
Doing this is what makes the **next** wake recognize that this cycle ended normally (marker `end`,
`CICLO-FIM` present) instead of treating it as a crash (F23) — never end your response without
running this sequence when the directory exists. `write-briefing` derives its content from
`diario.jsonl` + `estado-atual.yaml` (never invent text) and is idempotent per `--cycle-id`: if you
need to run the "parar" phase again (e.g., resuming after a mid-phase context compaction), running
`write-briefing` again for the SAME `--cycle-id` replaces the section instead of duplicating it.

**Final report:** you **always** report the cycle's result directly in your own response for this
session — approximate time, what was dispatched, what came back, decisions made (with the
Ticket/Ledger trace), and why it stopped — **and**, since Story E8.7, that same information has
already been written as a persisted artifact in `project_controll/gerente/briefing-YYYYMMDD.md` by
`write-briefing` above. In a headless cycle (no chat/owner present) it's the on-disk artifact that
carries the information forward — that's why it exists: the NEXT interactive session the owner opens
detects that Briefing as unread and renders it (see step 5 of "Activation" in
`activation-and-lock.md`), closing the loop between "work done overnight, with nobody watching" and
"the owner sees the summary as soon as they open the next session".
