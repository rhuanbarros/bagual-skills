# `project_controll/gerente/` — Persistent operational state of the Gerente Geral

Story E8.2 (`ideias/sistema-artifacts/E8-2-estado-operacional.md`), PRD 00 FR-11 (§4.8),
`ideias/epics.md` Epic E8. Materializes the situational awareness that the persona
`.claude/skills/bagual-gerente-geral/SKILL.md` (Story E8.1) reads **before deciding anything** when
activated. This document is the canonical schema/CLI contract — the persona and future
stories (E8.5-E8.7-E8.8, the E9 oracle) must treat it as the source of truth, not
duplicate the schema in prose elsewhere. As of Story E8.3, this README is also the
canonical contract of the quota guardrail (`gerente_quota.py`) — see § Quota (E8.3) below. As
of Story E8.4, the on-disk marker-file dispatch contract (what the Gerente
hands to the Execution Orchestrator and how it collects the result) has its OWN contract in
`dispatch-contract.md` (not duplicated here) — see § Dispatch (E8.4) below for the
pointer + a summary of what integrates with this file.

## What lives here

| File | Role | Written by |
|---|---|---|
| `estado-atual.yaml` | Snapshot of the CURRENT CYCLE — **overwritten** every cycle, never historical | `gerente_state.py write-snapshot` |
| `estado-atual.example.yaml` | Documented example of the schema (not real state, always present in the repo) | maintained manually |
| `diario.md` | Append-only, human-readable diary — same flat-log philosophy as `_bmad/scripts/memlog.py` | `gerente_state.py append-diario` |
| `diario.jsonl` | JSON-lines mirror of the same diary, for mechanical reconciliation (detect-crash) | `gerente_state.py append-diario` |
| `.lock/` | Singleton lock (a directory, not a file — see §Lock) | `gerente_state.py acquire-lock` |
| `quota-ciclo.json` | Auto-tracking of the CURRENT CYCLE (Story E8.3) — accumulator of estimated tokens, **overwritten**/reset on every new `--cycle-id` | `gerente_quota.py record-usage` (residual: standalone Opus turn) **or** `gerente_dispatch.py close-dispatch --tokens-used` (Story E15.2 — mechanized path, every dispatch) |
| `quota.config.json` | Committed config for the quota guardrail (threshold, auto-tracking budget, multiplier) — editable by the owner | maintained manually |
| `dispatches/{dispatch_id}/request.yaml` | OPEN dispatch (Story E8.4) — unit, Ticket(s), track, worktree, skill, model | `gerente_dispatch.py open-dispatch` |
| `dispatches/{dispatch_id}/result.yaml` | Dispatch result (Story E8.4) — outcome/verdict/pending items/evidence, written BEFORE the marker | `gerente_dispatch.py close-dispatch` |
| `dispatches/{dispatch_id}/DONE.marker` | Empty completion marker (Story E8.4) — written LAST, only after `result.yaml` is durable | `gerente_dispatch.py close-dispatch` |
| `dispatch-contract.md` | Canonical contract for the on-disk marker-file dispatch (Story E8.4) — full schema, ordering guarantee, dual detection, E10 forward-compat | maintained manually |
| `proactive-catalog.md` | Restricted catalog of proactive work (Story E8.5) — content/guardrails of the 4 categories (empty queue) | maintained manually |
| `proactive-ciclo.json` | Accumulator of catalog iterations consumed in the CURRENT CYCLE (Story E8.5) — **overwritten**/reset on every new `--cycle-id` | `gerente_proactive.py record-proactive` |
| `proactive.config.json` | Committed config for the hard cap + dedup threshold of proactive work (Story E8.5) — editable by the owner | maintained manually |
| `scripts/gerente_state.py` | stdlib-only CLI with all the operational-state subcommands | — |
| `scripts/gerente_quota.py` | stdlib-only CLI for the quota guardrail (Story E8.3) | — |
| `scripts/gerente_dispatch.py` | stdlib-only CLI for the dispatch contract (Story E8.4) | — |
| `scripts/gerente_proactive.py` | stdlib-only CLI for proactive work — hard cap + historical dedup (Story E8.5) | — |
| `scripts/gerente_oracle.py` | stdlib-only CLI for the Oracle Protocol (Story E9.1) — `record-decision`/`list-pending`/`set-ratification`; writes/mutates Ledger Entries `oracle: true` under `wiki/ledger/`, outside this folder (see § Oracle (E9.1) below). Since Story E9.2, `record-decision` also applies the history-aware gate (§ Style learning (E9.2) below) | — |
| `scripts/gerente_style.py` | stdlib-only CLI for Style Learning (Story E9.2) — `consult-precedent` (pure query, never writes)/`sm2` (SM-2 derived from the real trace); imports `gerente_oracle.py` for direct reuse (see § Style learning (E9.2) below) | — |
| `oracle.config.json` | Committed config for the support/contradiction threshold of the history-aware gate, PER decision CATEGORY (`decisao-tecnica`/`decisao-de-produto`/`decisao-de-arquitetura`) — editable by the owner | maintained manually |
| `scripts/test_gerente_state.py` | Suite of real proofs (concurrent subprocesses) of the E8.2 invariants | — |
| `scripts/test_gerente_quota.py` | Suite of real proofs (subprocesses) of the E8.3 invariants | — |
| `scripts/test_gerente_dispatch.py` | Suite of real proofs (subprocesses) of the E8.4 invariants, including end-to-end integration with `detect-crash`/`reconcile` from E8.2 | — |
| `scripts/test_gerente_proactive.py` | Suite of real proofs (subprocesses) of the E8.5 invariants, against real fixtures in `ideias/sistema-artifacts/fixtures/E8/proactive-tickets/` | — |
| `scripts/test_gerente_oracle.py` | Suite of real proofs (subprocesses, including real concurrency via `ThreadPoolExecutor`) of the E9.1 invariants, against real fixtures in `ideias/sistema-artifacts/fixtures/E9/` — 68 assertions | — |
| `scripts/test_gerente_style.py` | Suite of real proofs (subprocesses) of the E9.2 invariants — precedent lookup, down-weight for a corrected decision, per-category threshold (including custom `--oracle-config`), SM-2 derived from the real trace — 52 assertions | — |

**`estado-atual.yaml`, `diario.md`, `diario.jsonl`, `.lock/`, `quota-ciclo.json`,
`proactive-ciclo.json` and `dispatches/` are not committed at rest** — they only exist on
disk during/after a real cycle. Before the very first cycle ever, their absence
is expected and is exactly the graceful-degradation path that
`.claude/skills/bagual-gerente-geral/references/activation-and-lock.md` already documents — it is not an error, and no
story should create them preemptively "just so they don't appear absent." `quota.config.json`,
`proactive.config.json`, `proactive-catalog.md`, `estado-atual.example.yaml`,
`dispatch-contract.md` and `oracle.config.json` are the exception — they are CONFIG/doc/CONTRACT,
not cycle state, and therefore **are** committed.

## `estado-atual.yaml` schema

See `estado-atual.example.yaml` for a complete example. Top-level fields:

| Field | Type | Description |
|---|---|---|
| `schema_version` | int | Schema version (today `1`) |
| `written_at` | ISO8601 | Timestamp of the write itself (diagnostic) |
| `marker` | `start` \| `end` | **The key field for crash recovery (F23).** `start` = written at the beginning of the cycle (optimistic); `end` = written at the end (confirmed). A surviving `marker: start` on the next wake, together with a `CICLO-INICIO` with no matching `CICLO-FIM` in the diary, is the crash signal. |
| `cycle.id` | string | Cycle identifier (`cycle-YYYYMMDD-HHMMSS` by convention — not mechanically enforced, just a readability convention) |
| `cycle.started_at` / `cycle.ended_at` | ISO8601 \| null | `ended_at` is only non-null at `marker: end` |
| `cycle.phase` | string | One of the loop's 6 phases (`ler-estado\|priorizar\|despachar\|revisar\|registrar\|parar`) — the phase in which the snapshot was taken |
| `cycle.stop_reason` | `cota\|fila-vazia\|bloqueio` \| null | Only populated at `marker: end` |
| `dispatches` | list of objects | In-flight dispatches: `{ticket, unit, trilha, worktree, status, started_at, dispatch_id}`. `status` ∈ `em-voo\|concluido\|falhou\|reconciliado` — **this is the array `reconcile` reads to know what to check after a crash.** `dispatch_id` (Story E8.4, optional/additive — dispatches predating E8.4 never carry this key) is the pointer to `dispatches/{dispatch_id}/` (see `dispatch-contract.md`); when present, `reconcile` resolves the FULL list of tickets by reading `request.yaml` (never embedded here — this file's mini YAML serializer only supports a 1-level dict-of-scalars, see `dispatch-contract.md` § Integration) and cross-checks the absence of `DONE.marker` as one more reason for orphan status. |
| `decisions_pending` | list of `{ticket, note}` | Decisions awaiting ratification/info |
| `decisions_escalated` | list of `{ticket, note}` | Tickets moved to `precisa-de-info` this cycle |
| `semgrep_fp_pending` | list of `{fingerprint, rule_id, file, line, reason, status, timestamp}` | Suspected Semgrep false positives (`flag_suspected_fp.py`, E7.3) still `pending_ratification` — populated by `read_fp_suspects.py list-pending` and passed along here by the persona (Story E13.4, PRD 04 FR-2, see § Suspected false positives (Semgrep) (E13.4) below). Additive/optional, same spirit as `escalation_sample_review`/`escalation_dead_letter` — absent or `[]` renders a neutral phrase in the Briefing, never breaks a pre-story state. |
| `priorities` | list of `{ticket, priority}` | Prioritization order decided this cycle |
| `quota.*` | — | Quota snapshot — `five_hour_used_pct`/`seven_day_used_pct`/`source`/`read_at` (raw, read from `~/.claude/rate-limits-state.json`) **+** `self_tracked_tokens`/`self_tracked_pct`/`stronger_signal_pct`/`stronger_signal_source` (Story E8.3 — see § Quota (E8.3) below). The 4 new fields are optional/`null` until the persona passes `check`'s `write_snapshot_quota_args` to `write-snapshot`. |
| `last_briefing_at` | ISO8601 \| null | Timestamp of the last Briefing delivered. Informative — the source of truth for "read/unread" is the front matter of the `briefing-YYYYMMDD.md` file itself (`status:`), read directly by `gerente_briefing.py detect-unread`, never just this field (see § Briefing (E8.7)) |

**The parser/serializer is a minimal, closed YAML subset** (`yaml_scalar` /
`dump_estado` / `parse_estado` in `gerente_state.py`) — a 1-level dict-of-scalars and
lists-of-dict-of-scalars, exactly enough for this schema. It is not a generic
YAML implementation; do not use these files as a base for a general-purpose YAML parser.

## Diary (`diario.md` + `diario.jsonl`)

A **plain, chronological, append-only** log — same philosophy as `_bmad/scripts/memlog.py`
("A memlog is... kept minimal like human memory... no sections or grouping. Every entry
is one line, recorded at the END"). `diario.md` is the human/persona-readable
surface; `diario.jsonl` is the structured mirror that `detect-crash` scans
mechanically (avoids parsing free-form markdown for a critical recovery
decision).

Each cycle is delimited by a pair:
```
## CICLO-INICIO <ts> <cycle-id>
...cycle entries (acordei, li-estado, decidi, despachei, revisei, parei)...
## CICLO-FIM <ts> <cycle-id>
```
Valid events (`--event`): `CICLO-INICIO`, `CICLO-FIM`, `acordei`, `li-estado`,
`decidi`, `despachei`, `revisei`, `parei` — the 6 phase names of
`gerente-geral.md`'s loop plus the two cycle markers. A `CICLO-FIM` closing after
crash recovery carries `--reconciled` (appears as `(reconciled)` in the `.md` and
`"reconciled": true` in the `.jsonl`).

**Atomic write**: every mutation (write-snapshot, append-diario, lock) uses
`write_atomic` **imported directly from `_bmad/scripts/memlog.py`** (a file import,
not a copy-paste — see `_memlog()` in `gerente_state.py`) — temp + flush +
`fsync` + `os.replace` — the same primitive used by `transition_ledger_entry.py` and
`rebuild_board.py`. Each `append` does an **atomic rewrite of the entire file**, just like
`memlog.py` — it is not an incremental `open(..., "a")` (which could leave a
truncated line if the process dies mid-`write()`).

## Quota (E8.3)

Story E8.3 (`ideias/sistema-artifacts/E8-3-consciencia-cota.md`), PRD 00 FR-2, §4.1. The
guardrail that keeps the Gerente from blowing through the subscription quota: before starting a
new unit of work, it reads `~/.claude/rate-limits-state.json` **as an input**,
but — because that file is written by the statusline hook of an INTERACTIVE session and
can end up **frozen** during a headless cycle (no live interactive session writing to it)
— it ALSO self-tracks the tokens spent in its own cycle and uses the **stronger**
(more conservative) **signal** between the two. `scripts/gerente_quota.py` implements this — no
subcommand makes a network call: `read-limits` only reads a local file, `record-usage`/
`check` only read/write local files in `project_controll/gerente/`. Quota is
**subscription-only** — there is no path to a metered API in this module.

### Real schema of `~/.claude/rate-limits-state.json` (verified, not assumed)

```json
{"updated_at": 1783807722, "model": "Opus 4.8 (1M context)",
 "five_hour": {"used_percentage": 9, "resets_at": 1783822800},
 "seven_day": {"used_percentage": 25, "resets_at": 1783843200}}
```

`updated_at`/`resets_at` are epoch seconds. `read-limits` parses exactly this schema
and is **defensive by construction** — a missing file, malformed JSON, or unexpected schema
(missing keys) never raise an exception: they return `ok: false` + a descriptive `error`, with
all numeric fields `null`. `check` treats that case as an **unavailable** signal
(`degraded_rate_limit_signal`), never as "0% used" nor as "100% used" — a first
cycle ever (no file yet, or a new machine) generates neither a false `start` from
undue optimism nor a false `stop` from undue pessimism; it just loses the
rate-limit corroboration and falls back entirely to self-tracking (which also starts
at zero), which is the correct behavior for that situation.

### Local self-tracking — what it counts, and its honest limitations

`record-usage --cycle-id ID --tokens N [--note TXT]` accumulates a GROSS estimate of
tokens in a per-cycle count in `quota-ciclo.json` (resets automatically when
`--cycle-id` changes relative to what was recorded — there is no separate `reset-cycle`
subcommand because the Gerente already always calls this with the current cycle's
`cycle_id`).

**Story E15.2 — the "after every dispatch" case is now MECHANIZED, no longer
behavioral discipline.** Until E15.2, this section instructed the persona to remember to
call `record-usage` manually after every dispatch returned — a real residual concern
(see item 4 below, rewritten today). Since E15.2, `gerente_dispatch.py
close-dispatch` accepts `--tokens-used N` and, **in the same call that closes the dispatch**,
calls `record_usage()` (from `gerente_quota.py`, via direct import — never subprocess)
BEFORE writing `result.yaml`/`DONE.marker` — see § Dispatch (E8.4) below for the
full ordering mechanism. **What must be counted, by the persona's operational
convention:**
- **After EVERY dispatch (`Agent`/`Skill`) returns** — pass `--tokens-used
  <estimate>` in the very `close-dispatch` call that closes the dispatch (the persona's
  "dispatch" phase), no longer a separate `record-usage` call. The estimate is the
  same as always: ideally the usage reported by the sub-agent itself in its response,
  or, absent that, a rough estimate (e.g., proportional to the size of the
  returned transcript, or a fixed value per dispatch type).
- **Manual `record-usage` still exists (backward-compat) and is now restricted to
  the accepted residual: standalone Opus turns of the Gerente itself** within the cycle (e.g., at each
  phase transition, a long analysis done without dispatching any sub-agent) — no longer
  for covering a dispatch, which is now automatically covered by `close-dispatch
  --tokens-used`.

Each value passed in `--tokens` is multiplied by a **safety multiplier**
(`--multiplier`, default resolved `1.15`) and rounded **up** before being added —
deliberately biased to overestimate, never underestimate, real spend.

**Honest limitations (documented, not hidden):** this is an APPROXIMATION with no
real token counting — there is no local API in this environment that returns the
exact token consumption of a turn/dispatch (and we are not going to build one, since that would
require a metered API, forbidden by construction). The count is only as good as what is
actually reported — since E15.2, the dispatch case is mechanized (`close-dispatch
--tokens-used`, always runs when the dispatch closes), so the risk of forgetting is now
restricted to the explicit residual below (standalone Opus turn via manual `record-usage`); if the
persona **forgets** to pass `--tokens-used` on a `close-dispatch`, or forgets to
call `record-usage` for a standalone turn, that spend becomes invisible to self-tracking,
in the DANGEROUS direction (underestimation). Mitigations applied:
1. The safety multiplier biases every recorded entry upward.
2. The self-tracking budget (`self_tracked_budget_tokens`, default conservative
   `300000`) is deliberately small/pessimistic — a real cycle tends to hit the
   self-tracking cap well before it hits a real subscription token cap, which
   brings the stop earlier rather than later.
3. **`check` always uses the MAXIMUM of the two signals**, never just self-tracking — if
   `rate-limits-state.json` is fresh (a live interactive session writing to it), Anthropic's
   own authoritative signal dominates regardless of any gap
   in self-tracking. The real risk window is specifically "headless cycle +
   frozen snapshot + persona forgot to call record-usage" — a compound case, not the
   common path.
4. **Residual concern, accepted and not "fixed," BUT NARROWED by Story E15.2**: until
   E15.2, this item covered "there is no mechanical enforcement forcing the persona to call
   `record-usage` after every dispatch" — that specific case (the most common, one
   dispatch at a time) is now mechanized: `close-dispatch --tokens-used` is passed in the
   SAME call that already closes the dispatch (the persona is already required to call
   `close-dispatch`; passing `--tokens-used` along is one extra flag on the same call, not
   a separate step that can be forgotten). The residual concern left is narrower:
   there is no mechanical enforcement forcing the persona to call manual `record-usage` for its
   own standalone Opus turns (phase transitions, analyses without a dispatch) — this
   remains behavioral discipline, documented here and in
   `.claude/skills/bagual-gerente-geral/SKILL.md`, of the same class as other disciplines already accepted
   in this system (e.g., "always invoke `bagual-tickets` instead of hand-editing `board.yaml`").
   Closing this completely would require instrumenting the agent's own execution
   (outside the reach of a local stdlib script) — territory for a future story, not
   this one.
5. **Residual concern about concurrency**: `record-usage` does a
   read-modify-write cycle (reads `quota-ciclo.json`, sums, writes atomically) — the
   WRITE itself never corrupts the file (same atomic primitive as E8.2), but two
   *concurrent* calls to `record-usage` in the same cycle could lose an increment
   (last write wins). This was a non-problem when dispatch in this phase of the
   system was strictly sequential — "never dispatch more than one Ticket in parallel"
   (E8.1). **Since Story TCK-20260717131540-622d, this is no longer guaranteed**: parallel
   Tickets via an isolated worktree run concurrent sub-agents, each of which can call
   `close-dispatch --tokens-used` (which already embeds `record_usage()`) in overlapping
   time windows. The concern remains **accepted without a fix** (the same class of risk
   just becomes a bit more likely, not qualitatively different — it is still
   local read-modify-write, a single trusted agent, not an
   adversarial surface), but it stops being hypothetical: real parallelism from E10/E11 (or even
   the conditional parallelism already available today via worktree) is the trigger, no longer a
   "would only matter someday" future case.

`self_tracked_pct = ceil(min(100, self_tracked_tokens / self_tracked_budget_tokens * 100))`
— rounded UP (not to the nearest integer), biased in favor of "stop
early" rather than underestimate due to rounding (explicit story constraint:
"an approximation error never causes an overrun").

### `check` — the stronger signal + verdict

`check --cycle-id ID [--limits-path PATH] [--threshold-pct N] [--self-tracked-budget-tokens N] [--stop-diario]`
reads both signals (`read-limits` + `quota-ciclo.json`), normalizes both to comparable
percentages (rate-limit = the worse of the 5h/7d windows; self-tracked = accumulated tokens /
configured budget), takes the **maximum** of the two (`stronger_signal_pct` +
`stronger_signal_source`), and compares it against the configurable threshold (a `>=`
comparison, no off-by-one — exactly at the threshold it is already `stop`). It also returns `write_snapshot_quota_args`: the
exact arguments to pass on to `gerente_state.py write-snapshot` at cycle close, so the
persona doesn't have to recompose flag names by hand. With `--stop-diario`,
if the verdict is `stop`, it writes `parei-por-cota: <reason>` to `diario.md`/`diario.jsonl`
with `--event parei` **via the same `append-diario` mechanism from E8.2** (direct import
from `gerente_state.py`, not a reimplementation).

### Config — precedence (highest wins)

1. CLI flag (`--threshold-pct`, `--self-tracked-budget-tokens`, `--multiplier`,
   `--stale-snapshot-seconds`).
2. Environment variable (`GERENTE_QUOTA_THRESHOLD_PCT`,
   `GERENTE_QUOTA_SELF_TRACKED_BUDGET_TOKENS`, `GERENTE_QUOTA_SAFETY_MULTIPLIER`,
   `GERENTE_QUOTA_STALE_SNAPSHOT_SECONDS`).
3. `project_controll/gerente/quota.config.json` (committed with defaults — the owner edits
   it directly to calibrate against their real plan).
4. Hardcoded default in `gerente_quota.py`: `threshold_pct=85.0`,
   `self_tracked_budget_tokens=300000`, `safety_multiplier=1.15`,
   `stale_snapshot_seconds=900`, `per_dispatch_inflight_estimate_tokens=200000`,
   `inflight_grace_seconds=600`.

**Recommended calibration (not automatic):** `self_tracked_budget_tokens=300000` is a
conservative starting guess, not a measured number — after observing
a few real cycles with a fresh `rate-limits-state.json` (interactive session), the owner can compare
`self_tracked_pct` against the real reported `five_hour_used_pct`/`seven_day_used_pct`
for the same volume of work, and adjust `self_tracked_budget_tokens` in
`quota.config.json` so the two signals land in the same order of magnitude.

**Guardrail kill-switch (`enabled` flag, owner decision 2026-07-14).** `enabled: false` in
`quota.config.json` **turns off the whole guardrail**: `check` still computes and reports both
signals (diagnostics stay useful — `natural_verdict` shows what it WOULD BE), but `verdict` is
forced to `start`, so **the Gerente never stops for quota reasons**. It is OFF right now (the owner tracks
throughput manually). To turn the control back on: `enabled: true`. Precedence: `--no-enabled`
(CLI) > `GERENTE_QUOTA_ENABLED` (env) > `enabled` (config) > default `true`. This is NOT the same as
raising `self_tracked_budget_tokens` — it is an explicit shutdown of the control, not a higher cap.

**In-flight dispatch estimate (E19.2, Gap 2 — quota doesn't go blind mid-tree):**
the `self_tracked_tokens_total` accumulator only advances on `close-dispatch`. While
a dispatch's tree executes (executor → a marker-confirmed sub-flow), it stays frozen — so
`check` used to report a false margin mid-tree (incident `cycle-20260713-202850`: 44%
while ~1M was burning). `check` now adds to the self-tracked signal an estimate per
dispatch still OPEN (`request.yaml` present, `DONE.marker` absent) in the current cycle that has already
passed `inflight_grace_seconds` (default 600s) — `per_dispatch_inflight_estimate_tokens`
(default 200000) each. This way the guardrail can trigger even before close-dispatch and even if it
never runs (orphan), without false-aborting a freshly opened dispatch (within
the grace period). A "stop" from this NEVER kills the in-flight tree — it moves the Gerente to the
'stop' phase (reconciles/waits for in-flight dispatches). Set
`per_dispatch_inflight_estimate_tokens=0` in `quota.config.json` to turn it off.

## Dispatch (E8.4)

Story E8.4 (`ideias/sistema-artifacts/E8-4-contrato-despacho.md`), PRD 00 FR-8 (+ the
Sonnet side of FR-7). FULL contract in `dispatch-contract.md` (not duplicated here, same
"one contract, one owner" discipline already used by this README) — read there for the
`request.yaml`/`result.yaml` schema, the ordering guarantee (result durable BEFORE
DONE.marker), the dual completion detection (Agent tool return = primary signal;
`DONE.marker` = secondary/payload signal, never polled), and the forward-compat with the
E10 multi-epic supervisor. Summary of what matters for THIS file:
`scripts/gerente_dispatch.py` never writes `estado-atual.yaml` directly (same
"single owner" rule already applied to `quota-ciclo.json` in E8.3) —
`open-dispatch` returns a `dispatch_entry` ready for the persona to pass along to the
next `write-snapshot --dispatches-json`, and `gerente_state.py
reconcile` (E8.2) was extended to cross-check the `DONE.marker` of every dispatch that carries a
`dispatch_id` (see the reconciliation checklist above, item 4b).

### `close-dispatch --tokens-used` — quota mechanized as a side effect (E15.2)

Story E15.2 (`ideias/sistema-artifacts/E15-2-mecanizar-record-usage.md`), Epic E15
(behavioral→mechanical hardening), T2.2. `close-dispatch` accepts `--tokens-used N
[--tokens-note TXT] [--tokens-multiplier F]` — when passed, BEFORE writing
`result.yaml`/`DONE.marker` (the ordering guarantee already documented above and in
`dispatch-contract.md`), the script calls `gerente_quota.py::record_usage()` **via direct
import** (never subprocess — same reuse technique already used for `gerente_state.py`),
reading `cycle_id` from the dispatch's own `request.yaml`, applying the same safety
multiplier resolved by `resolve_safety_multiplier()`. **Central guarantee**: `DONE.marker`
(the definitive "dispatch closed" signal in the contract) is never observable without the
quota already having been counted — there is no half-closed state where the dispatch is
closed but the quota was not accounted for. The symmetric window (process dies BETWEEN the
quota write and the `result.yaml` write) is safe in the opposite direction: the quota ends up
"ahead," but the dispatch is still detectable as an orphan via
`reconcile-orphan-dispatch`/`list-inflight` as always — never "dispatch closed, quota
forgotten." Omitting `--tokens-used` preserves the pre-E15.2 behavior (no write to
`quota-ciclo.json`) — full backward compatibility; standalone `record-usage` keeps
working with no change, now restricted to the residual standalone-Opus-turn case (see § Quota
above).

## Proactive work (E8.5)

Story E8.5 (`ideias/sistema-artifacts/E8-5-trabalho-proativo.md`), PRD 00 FR-3, UJ-4,
hardening F24. When `project_controll/tickets/board.yaml` has no Ticket in
`pronto-para-implementar`, the Gerente does not sit idle — but it picks from a
RESTRICTED, very-low-risk catalog (`proactive-catalog.md`, content/guardrails of the 4
categories, not duplicated here). The mechanics (cap + dedup) live in
`scripts/gerente_proactive.py`:

- **`next-task`** — a configurable hard cap per cycle (`proactive.config.json`
  `cap_per_cycle`, default 3). Each call with `count_so_far < cap_per_cycle` returns
  `"verdict": "go"` + the category from a deterministic round-robin rotation (`count_so_far %
  4`); once the cap is reached, it returns `"verdict": "cap-reached"` (`category: null`) — no
  off-by-one, proven in `test_gerente_proactive.py` [1]/[1b] for N=1 and N=3. **The unit
  of cost is the catalog ITERATION** (a Sonnet sub-agent analysis dispatch), not the
  number of Tickets it produces — see `proactive-catalog.md` § "Cost unit".
- **`dedup-check`** — scans ALL `TCK-*.md` files in `--tickets-dir` with `origem: proativo`
  (default; `--include-non-proactive` widens it), **in any status, including
  `concluido`/`descartado`** — the dimension that `bagual-tickets`'s native dedup does not
  cover (it only compares against OPEN tickets, see `.claude/skills/bagual-tickets/SKILL.md` §
  Add step 2). Heuristic: Jaccard of tokens (normalized, accent-stripped, PT/EN
  stopwords removed) between the candidate finding's `--title`/`--description` and
  the `title + "## Descrição" section` of each historical ticket (not the whole body — that
  would dilute the real overlap with noise from `## Verificação`/`## Log`/commit
  hashes). Above the configurable threshold (`dedup_similarity_threshold`, default
  `0.30` — empirically calibrated against paraphrased findings in the real tests, same
  "calibratable guess, not measured" caveat documented for
  `self_tracked_budget_tokens` in E8.3), `"duplicate": true` points to the `best_match`.
  **This is candidate-retrieval + heuristic for the caller (LLM) to review, not an
  infallible algorithmic verdict** — the same spirit as the human/LLM-read dedup that
  the `bagual-tickets` skill itself already uses against open tickets; here only the
  corpus dimension changes (full history vs. open only).
- **`record-proactive`** — increments `proactive-ciclo.json` (auto-reset on a new
  `--cycle-id`, same "single owner"/"overwritten per cycle" philosophy as
  `quota-ciclo.json`/E8.3), called **once per** catalog **iteration** (never once
  per finding/Ticket).

**Composition, never reimplementation:** this module NEVER creates/edits a Ticket
directly — materializing a non-duplicate finding is always `bagual-tickets
--headless` (which already writes `origem: proativo` by default in headless mode, see `SKILL.md` §
Headless Mode), invoked by the persona after `dedup-check` returns `duplicate: false`.
The analysis sub-agent dispatched for the chosen category is **read-only** by
contract (`proactive-catalog.md` § "Golden rule") — it never calls `Edit`/`Write` against
production code; the only accepted output artifact is a text list of findings.

## Briefing (E8.7)

Story E8.7 (`ideias/sistema-artifacts/E8-7-briefing-manha.md`), PRD 00 FR-10, §4.7. The
Gerente's cycle runs **headless** — there is no "chat message" at all to deliver
at the end of an autonomous cycle with no owner present. `scripts/gerente_briefing.py` solves this
by making the Briefing a **persisted artifact**, derived from `diario.jsonl` (E8.2) +
`estado-atual.yaml` (E8.2), which the NEXT interactive session detects as unread and
renders on activation:

- **`write-briefing`** — called by the persona in the "stop" phase (step 6 of the loop), after
  `append-diario --event CICLO-FIM` and before `release-lock`. It reads `diario.jsonl`
  filtering for the entries of the given `--cycle-id` (event `despachei`/`revisei` → "what was
  done", `decidi` → "decisions made (trace)") and `estado-atual.yaml` (`decisions_pending`
  + `decisions_escalated` → "needs attention/ratification"), and writes/updates
  `briefing-YYYYMMDD.md`. `--stop-reason cota|fila-vazia|bloqueio` maps to the AC's
  readable label `cota|conclusão|bloqueio` (`fila-vazia` → "conclusão"); an optional
  `--stop-detail teto-proativo` annotates the nuance of the proactive-work guardrail
  (E8.5) without inventing a 4th `stop_reason` value — the same distinction that used to live only
  in the persona's "final report" prose (see `gerente-geral.md`'s "stop" phase).
- **File date** comes from the calendar date of `--ended-at` (the end of the actual CYCLE), never
  from the clock of when the script runs — a cycle that ends at 23:58 and whose `write-briefing`
  is only called after the day turns over still produces the correct
  `briefing-<ended_at-date>.md`. It only falls back to the script's own clock (`now_iso()`)
  when `--ended-at` is not supplied (`used_fallback_date: true` in the response — documented
  degradation, not the primary path).
- **Idempotent by `--cycle-id`**: the file is `YAML front matter (status/written_at/
  last_cycle_id/read_at) + one Markdown "## Ciclo <cycle_id>" section per cycle`. Running
  `write-briefing` again for the SAME `--cycle-id` (e.g., resuming the "stop" phase after
  a context compaction in the middle of it) **replaces** the existing section instead of
  duplicating it. A SECOND cycle ending on the same calendar day **appends** a new
  section to the same file, preserving the earlier one(s) — never overwrites the entire day.
  Every new write marks the entire file `status: unread` again (new content = new
  pending-read event), even if an earlier section had already been read.
- **Forward-dep on E9.1 (oracle)**: the "needs attention/ratification" section already reads
  `decisions_pending`/`decisions_escalated` from `estado-atual.yaml` with a defensive
  `.get(..., [])` — today always `[]` (or the key absent, treated the same), so the
  section always renders "no decision pending ratification." When Story E9.1 populates those
  fields for real, the Briefing starts listing the entries with no rework of this script.
- **`detect-unread`** — read-only, scans `briefing-*.md` and lists the ones with
  `status: unread` in front matter (a missing/unrecognizable front matter counts as
  unread — a Briefing is never lost by mistake). Called by the persona at step 5 of
  "Activation," only when the session is interactive (not during a headless cycle — there is no
  owner to read it).
- **`mark-read`** — `--date YYYYMMDD` (or `--path`), sets `status: read` + `read_at`.
  Idempotent: marking an already-read Briefing again is not an error (`already_read: true` in
  the response, without duplicating or corrupting the file). The persona calls this right after
  rendering the content — never leave a rendered Briefing without `mark-read`, or the
  NEXT activation renders it again (double-render).
- **Race between `detect-unread` and `mark-read` (a real finding from this story's adversarial
  self-review)**: an interactive session may `detect-unread` → start rendering →
  while, meanwhile, a CONCURRENT headless cycle runs `write-briefing` again (adding
  a new section, marking the file `unread` again) → if the interactive session then
  called `mark-read` blindly, it would clobber that freshly-written `unread` back to `read`, and
  the new section would never be rendered in ANY future session — a silent loss of
  Briefing. `mark-read --expected-last-cycle-id <value returned by detect-unread>` is the
  compare-and-swap that closes this: if the file's `last_cycle_id` no longer
  matches (someone wrote in the meantime), `mark-read` refuses (`ok: false`,
  `error: "stale"`, returning the current `actual_last_cycle_id`) instead of marking it as read — the
  caller must re-`detect-unread`/re-render before trying again. Without
  `--expected-last-cycle-id` (omitted), the old behavior (always marks) remains available for calls
  outside this race (e.g., manual test/debugging), but the persona ALWAYS passes the parameter.
- **A torn/partial diary never brings down the Briefing**: if the `CICLO-INICIO`/`CICLO-FIM` pair for the
  `--cycle-id` is not found complete in `diario.jsonl` (a crash mid-cycle, or
  `write-briefing` called before the normal `append-diario CICLO-FIM` — shouldn't happen
  in the correct flow, but is handled anyway), the Briefing is still written with what
  exists, with the "Diagnóstico" section flagging `diário: incompleto`. A single
  malformed line in `diario.jsonl` (an isolated invalid JSON) is skipped, it does not abort the
  whole file.
- **Its OWN `--root` on every call**: never write/detect against the real
  `project_controll/gerente/` from a test — always a temp-directory `--root` (see
  `test_gerente_briefing.py` and the fixtures under `ideias/sistema-artifacts/fixtures/E8/`).
- **`PushNotification`** — optional, best-effort: if the tool is available in the
  session running the cycle, the persona MAY call it after `write-briefing` to
  notify the owner outside the session; its ABSENCE never prevents the next
  `detect-unread`/`mark-read` from rendering — it is just an extra signal, not a prerequisite. This
  module does not invoke it directly (it is not a hard-wired dependency).

## Local wake (E8.8)

Story E8.8 (`ideias/sistema-artifacts/E8-8-wake-local.md`), PRD 00 FR-1/§8-Q2. The
full contract, the two locally available mechanisms (`loop`/`CronCreate`), the exact
`PROMPT-DE-WAKE` and the 60s manual micro-test live in
[`project_controll/gerente/wake.md`](./wake.md) — this paragraph is just the mechanical
summary for anyone who has already read the "Singleton lock" section below:

`scripts/gerente_wake.py wake-attempt` reuses `gerente_state.py::acquire_lock` (the same
function, imported, not a copy) to decide — WITHOUT spawning any sub-agent — whether a
`loop`/`CronCreate` tick should wake the persona (`Agent(subagent_type:
"gerente-geral")`). `proceed: true` returns an already-acquired `cycle_id`/`token` (the
persona skips the `acquire-lock` sub-step of its own step 0, see `gerente-geral.md` §
"Activation" bullet "Alternative entry via local wake"); `proceed: false` (lock
held-and-fresh) makes the wake defer at no cost, `exit 0` in both cases. `pending_crash`
is passed along verbatim when `acquire_lock` reclaims a stale lock with an orphaned
`CICLO-INICIO` associated — `gerente_wake.py` never reconciles on its own, that is still
the persona's judgment call. 100% local: `loop`/`CronCreate` are native primitives of the OPEN
SESSION (never OS cron, never the `schedule`/routines cloud skill — forbidden by
§8-Q2/F1), and `gerente_wake.py` only imports stdlib (mechanically verified by
`test_gerente_wake.py::test_no_network_path`).

## Oracle (E9.1)

Story E9.1 (`ideias/sistema-artifacts/E9-1-oraculo-decisao-delegada.md`), PRD 00 FR-5
(§4.3, UJ-3), `ideias/epics.md` Epic E9. Canonical contract for the trust gate; the
operational protocol (when it fires, step by step, ratification) lives in
`.claude/skills/bagual-gerente-geral/references/oracle-protocol.md` — this README only documents
the script's mechanics (`scripts/gerente_oracle.py`).

**Where it writes:** unlike everything else in this folder, an oracle decision is
recorded as a Ledger Entry in `wiki/ledger/{decisao-tecnica,decisao-de-
produto,decisao-de-arquitetura}/*.md` (outside `project_controll/gerente/`) — the full
front matter of the `wiki/ledger/README.md` §1 schema **plus** 5 fields specific to
oracle entries: `oracle: true`, `ticket: <id>`, `confidence: high|low`,
`blast_radius: auto-merge|parked`, `ratification: pending|ratified|corrected`,
`precedent: <path>|null`. The body follows full MADR (`## Contexto`/`## Decisão`/
`## Alternativas...`/`## Consequências`) — the 3 fields of the trace required by AC1
(decision, justification, context) map 1:1 to `## Decisão`/`## Consequências`/
`## Contexto`.

**The trust gate — core of hardening F10 ("blast radius").** `record-decision`
only grants `confidence: high` (and `proceed_dispatch: true` in the JSON response) when
**all** the conditions below are checked MECHANICALLY against `--precedent <path>`
(never taken on the caller's word):

1. `--precedent` was passed, points to a file (not a directory) that exists and is
   readable as UTF-8.
2. The front matter has `tipo` ∈ {decisão-técnica, decisão-de-produto,
   decisão-de-arquitetura}.
3. `estado: ativa` — **it is not enough to be "different from aposentada"**; a `candidata`
   entry (including one just emitted by the oracle itself minutes earlier, still `ratification:
   pending`) never supports high confidence. Without this requirement, two ordinary,
   non-adversarial calls could chain "low-confidence decision" → "precedent of a
   second high-confidence decision" (a real finding from this story's adversarial
   self-review — see `## Consequências` of the corresponding fixture and tests `[1]`-`[7]` of
   `test_gerente_oracle.py`).
4. `ratification` absent or `ratified` — never `corrected`/`pending`. An entry the
   owner corrected **never again** serves as a precedent, even if `estado` remains
   `ativa` (the `set-ratification --status corrected` does not revert `estado` — it only marks
   the signal; see below).

Any failure in 1-4 downgrades confidence to `low` with a `downgrade_reason` explained in
the response — **never** an `exit`/exception that leaves the caller without a verdict. The
default with no explicit `--confidence`, or any value outside `{high, low}`, is already
`low` (conservative by construction — "uncertain" never becomes "high" by omission). Also,
`proceed_dispatch` is always also conditioned on the self-check (`validate_ledger.py`) having
passed — a malformed entry never releases auto-merge, even with a calculated
`confidence: high`.

**Atomic write under real concurrency:** `record-decision` reserves the file path via
`os.open(..., O_CREAT|O_EXCL)` **before** writing the content (never a
`path.exists()` followed by a later write) — the same mutual-exclusion guarantee that
the singleton lock (`os.mkdir`, § below) uses at the filesystem level. Proven with 20 real
concurrent processes writing the SAME ticket/decision (`test_gerente_oracle.py` `[12c]`):
20 unique paths, 20 surviving files on disk, zero crashes. A naive earlier `unique_path()`
(check-then-write) allowed a `.tmp` collision between two intermediate
processes and silent overwriting — fixed in this same story before closing.

**Front-matter injection.** `--ticket`, `--precedent` and each item of `--areas` are
rejected (`exit 2`) if they contain `\n`/`\r` — since the front matter is assembled by
literal interpolation (not a YAML serializer that escapes newlines), a value with an
embedded line break could, without this guard, forge extra lines inside the same
`---...---` block (e.g., injecting `ratification: ratified` via a malicious/malformed
`--precedent`). It never sanitizes silently — it always refuses loudly and explicitly.

**`ratification` lifecycle:** `pending` (at birth, always) → `ratified` (owner
confirms; `set-ratification` automatically promotes `estado: candidata -> ativa`, if
still `candidata`) | `corrected` (owner corrects; `estado` stays as it was — the field
is only the signal, consumed by the style-learning Story E9.2; the entry is never
deleted/rewritten). `list-pending` only sees `oracle: true` + `ratification: pending` —
it is the persistent source of truth (survives any restart/context compaction,
unlike `estado-atual.yaml`, which is overwritten every cycle); the `pending_entry`
returned by `record-decision` is what the persona passes on to
`write-snapshot --pending-json` for Briefing visibility (E8.7), but the
canonical, durable trace is always the Ledger file itself.

**Reuse, never reimplementation:** `gerente_oracle.py` directly imports (same technique
as `_memlog()` in `gerente_state.py`) the primitives from
`wiki/ledger/scripts/transition_ledger_entry.py`
(`split_front_matter`/`set_front_matter_field`/`get_front_matter_field`/
`append_transition_note`/`write_atomic`/`render`) and from `validate_ledger.py`
(`parse_front_matter`/`scan_and_validate`) — no parallel reimplementation of the
front-matter parser or the self-check.

## Style learning (E9.2)

Story E9.2 (`ideias/sistema-artifacts/E9-2-aprendizado-estilo.md`), PRD 00 FR-6 (§4.3,
Phase 2). Makes `record-decision`'s trust gate **history-aware**: before
deciding, the oracle consults the history of decisions — both ratified AND corrected — and
adjusts the confidence radius accordingly. "Style" continues to be **Ledger entries +
`product-decisions.md`/`decisions.md` consulted at spec time**, NEVER a
trained model (`[ASSUNÇÃO]` from PRD 00 §9, ratified by this story).

**"Similar" — an OPERATIONAL definition, never by feel/NLP:** same `tipo` (category)
**+** N `areas` tags in common (exact intersection, case-insensitive/trimmed —
`gerente_oracle.py::shared_areas`) between the candidate and an existing Ledger Entry.
N is the **threshold** — configurable **per category** in `oracle.config.json`
(a sibling of this README, same committed/editable pattern as `quota.config.json`, E8.3):
`min_shared_areas_support` (how much overlap a **ratified** precedent needs to
support `high`) and `min_shared_areas_contradict` (how much overlap a **corrected**
decision needs to VETO `high`). The committed default is
`decisao-de-produto: support=2` (the most sensitive category — requires a stronger precedent)
vs. `decisao-tecnica`/`decisao-de-arquitetura: support=1`; `contradict=1` in every
category (it is always easier to prove contradiction than to prove support — never the
other way around, conservative by design).

**The history-aware gate, inside `record-decision`:** even when a cited `--precedent`
passes the 4 mechanical F10 checks (Oracle (E9.1) above), `record-decision`
STILL scans the Ledger for a decision of the SAME `tipo`, `ratification: corrected`, with
`areas` overlap >= `min_shared_areas_contradict` against the candidate's `--areas`
(`gerente_oracle.py::find_corrected_contradictions`). If it finds one, it downgrades to
`low` regardless — **the owner's correction always beats a competing favorable
precedent**, never the other way around (proven by `test_gerente_style.py [C]`/`[D]`: a
scenario with BOTH a similar ratified precedent AND a similar correction coexisting
always resolves to `low`). `record-decision`'s JSON response gained two new
fields: `category_threshold` (the resolved threshold, for auditing) and
`contradicting_corrected` (the list of corrected decisions that vetoed it, empty on the happy
path).

**`gerente_style.py` (sibling script, never writes anything) — 2 subcommands:**

- **`consult-precedent --tipo <slug> --areas "a,b"`** — the same query that
  `record-decision` performs internally, but BEFORE deciding and with no side effect:
  returns `matches_ratified`/`matches_corrected`/`suggested_confidence`/`reason`. A
  contradiction found ALWAYS results in `suggested_confidence: low`, even if
  `matches_ratified` also comes back non-empty — the down-weight is never obscured by competing
  support. It also scans `product-decisions.md`/`decisions.md` (configurable paths,
  default the project's real files) for a `## [TAG] Título` section whose title
  mentions the same `areas`/extra `--keywords` — **purely
  informational** (`product_decisions_hits`/`decisions_hits` in the response), never part
  of the mechanical calculation of `suggested_confidence` (these two monolithic files don't have
  structured `tipo`/`areas`/`estado`/`ratification` to support a real mechanical
  check — only the Ledger does).
- **`sm2 [--tipo <slug>] [--verbose]`** — computes SM-2 (PRD 00 §7: "% of oracle
  decisions ratified, not corrected, rising over time") **from the real
  trace** (scans `wiki/ledger/` for `oracle: true`, counts
  `ratification` ∈ {ratified, corrected, pending}) — never a hardcoded value.
  `pct_ratified = ratified / (ratified + corrected) * 100`, excluding `pending` from the
  denominator (a not-yet-ratified/corrected decision is neither evidence for nor
  against); `null` when `decided == 0` (SM-2 undefined — never `0`/`100` by
  omission). `--tipo` filters by category; with no filter, it aggregates all.

**Config — same pattern as `quota.config.json` (E8.3):** `oracle.config.json`
(committed, editable by the owner) resolves per category; `--oracle-config <path>` (in
both scripts) picks WHICH file to load — tested end-to-end in
`test_gerente_style.py [G]`: a custom `oracle.config.json` really changes the verdict of
`consult-precedent` **and** the real gate in `record-decision`, not just the
hardcoded defaults. A missing/malformed file silently degrades to the
hardcoded defaults (`CATEGORY_THRESHOLD_DEFAULTS` in `gerente_oracle.py`) — it never raises.

**Reuse, never reimplementation:** `gerente_style.py` directly imports `gerente_oracle.py`
(same direct-file-import technique already used by the latter for
`transition_ledger_entry.py`/`validate_ledger.py`) — it reuses the type tables,
`shared_areas`, `load_oracle_config`/`get_category_threshold`,
`find_ratified_support`/`find_corrected_contradictions`, `validate_precedent_fm`.
The dependency is unidirectional (`gerente_style.py` -> `gerente_oracle.py`, never the
other way around) — the real gate lives in `gerente_oracle.py` because it is the one that writes;
the pure query lives in `gerente_style.py` because it should not be able to write anything.

**Known limitation (residual, documented — not fixed in this story):** if the
caller passes `--areas ""` (empty) — never happens with the CLI default
(`sistema-orquestrador,gerente-geral,oraculo`), but is possible by explicitly
overriding it — no overlap is computable against anything, so the history-aware gate
never finds support nor contradiction, and behavior falls back to the pure F10
gate (E9.1), without E9.2's benefit. The Gerente's protocol (`.claude/agents/
gerente-geral.md` § Oracle Protocol) instructs it to always formulate real `areas` —
but the script itself does not reject an empty `areas` (a deliberate decision: an empty `--areas`
is still a valid call under pure F10, and rejecting it would expand this story's scope
beyond what is needed).

## Escalation decided by the Gerente (E9.5)

Story E9.5 (PRD 02 FR-6), `scripts/gerente_escalation.py` + `escalation.config.json`.
Closes the other side of the contract opened by Story E9.4: `bagual-tickets` marks
`escalonar: true` in the `board.yaml` INDEX (F20 — the Gerente scans the escalated ones in a single
read, without opening each `.md`). This script gives the Gerente the MECHANICAL primitives for the
rest — the decision of WHICH track and WHETHER to promote to the Ledger remains pure judgment
(Oracle Protocol, E9.1/E9.2, with no fixed heuristic — decided 2026-07-10, PRD 02 §4.4/FR-6).

🔴 **Retired since TCK-20260727143826-7573 (2026-07-27):** `bagual-tickets` used to auto-commit
`trilha` for two narrow "obvious" cases via `classify_trilha.py` before marking the rest
`escalonar: true`. That mechanical classifier is now retired as a trilha decider (kept on disk for
history, not deleted — see
`wiki/ledger/decisao-tecnica/roteamento-de-trilha-e-plano-antes-da-execucao.md`): its two rules
funneled almost everything into `rapida` and never assigned `spec`/`epic` automatically. Every
Ticket reaching `pronto-para-implementar` now arrives `escalonar: true` unconditionally — there is
no longer an "auto-committed" subset distinct from "escalated"; 100% of Tickets go through the flow
below, decided by Gerente/owner judgment (criteria in
`.claude/skills/bagual-gerente-geral/references/dispatch-and-review.md` step 1, plus the
`spec`/`epic` John-never-headless gate in `spec-epic-routing-execution.md`). `gerente_escalation.py`
itself is unchanged — only its input widened from "the ambiguous remainder" to "everything".

**`list-escalated`** — reads only `board.yaml`, returns the tickets with `escalonar: true`.
`escalonar: false` is set at the exact moment a track is committed — since
TCK-20260727143826-7573, only the Gerente/owner ever does this commit (the skill itself no longer
auto-commits any track, see "Retired" note above) — so this command never relists an
already-decided ticket; the exclusion of "already resolved" is a property of the state itself, not
an extra filter.

**Committing the decided track — via `bagual-tickets` (composition, not a new script):**
after deciding via the Oracle Protocol (`.claude/skills/bagual-gerente-geral/references/oracle-protocol.md`),
the persona invokes `bagual-tickets` (Resolver) to record `trilha: <decided>`
+ `escalonar: false` + a `## Log` line citing the trace (Ledger path if any) +
`ledger_refs` when promoted — the skill is NEVER re-edited by this story (E9.4 is already
its side of the contract); the same generic "update fields of a ticket" mechanism
that Resolver already exposes is reused, without requiring a new documented section in
`SKILL.md`.

**`dead-letter-check`** — of the escalated ones, how many days since `updated` (or `created`)
with no update at all; `>= dead_letter_limit_days` (default 3, `escalation.config.json`)
becomes a dead letter, exposed in the Briefing (F20 hardening — "an escalated item that never gets
decided doesn't rot"). An unreadable/missing date NEVER becomes a dead letter by omission (it stays
out with a warning — conservative: an indeterminate age is not proof of being stalled).

**`sample-decisions` / `record-sample-review`** — samples tickets that had a `trilha` committed
automatically by the skill (`trilha` != null + `escalonar: false`) not yet reviewed
by the Gerente. 🔴 Since `classify_trilha.py`'s retirement (TCK-20260727143826-7573), the skill
no longer auto-commits any NEW ticket this way — this pair of commands now only applies to the
**historical** backlog committed before the retirement; re-triaging it against the new 3-way
criteria is a separate, still-pending action. Kept for ratification/correction **by sampling** in
the Briefing (AC2 — never
100%). "Already reviewed" is tracked in `sampled-decisions.json` (an operational artifact of the
Gerente ITSELF, analogous to `estado-atual.yaml`/`diario.md` — never a new
field on the ticket/board, so it doesn't require re-editing `bagual-tickets`). Deterministic
order (oldest first, by `updated`/`created`) — never leaves the same old ticket
waiting forever behind newer ones.

**A correction feeds E9.2 — mechanized in a single command since Story E15.3 (T2.3).**
`record-sample-review --verdict corrigido` REQUIRES the decision-trace fields
(`--trilha-auto`/`--trilha-corrigida`/`--question`/`--justification`/`--context`;
`--tipo`/`--areas`/`--ledger-root`/`--oracle-config` optional) and, in the SAME invocation,
internally calls `gerente_oracle.py::record_decision()` +
`set_ratification(status="corrected")` — via DIRECT IMPORT (`importlib.util`, never
subprocess), reusing the same PURE functions that `gerente_oracle.py`'s CLI already uses
internally (extracted in this story from what used to be just the bodies of
`cmd_record_decision`/`cmd_set_ratification`). A single call produces, by construction, both
artifacts — `sampled-decisions.json` **and** the `ratification:
corrected` Ledger Entry — never one without the other; the entry is born
`ratification: corrected` right away (it never passes through an observable intermediate
`pending` state). The Gerente NEVER again needs to run
`record-decision`/`set-ratification` manually for a sampling correction — the old
"always run both commands, never just one" instruction (pre-E15.3 behavioral
contract) became a mechanical guarantee from a single command.

**Write order + all-or-nothing** (same discipline as E15.2 — the Ledger Entry
`mecanizar-efeito-colateral-antes-da-escrita-que-finaliza-a-operacao`): the new
side effect (the Ledger Entry) is written **before** the write that finalizes the
operation (`sampled-decisions.json`). If the trace fields are incomplete, the
command refuses (exit != 0, a clear error citing the missing fields) without writing anything. If
`record_decision`/`set_ratification` fails after the fields have been validated, the whole
operation aborts and `sampled-decisions.json` is NOT touched — there is never a state of
"sample marked as reviewed, without the corresponding Ledger Entry." The symmetric,
safe residual window (Ledger already written as `pending`, `sampled-decisions.json`
not yet) is visible via `gerente_oracle.py list-pending` for a manual retry of
`set-ratification`, exactly like any other pending oracle decision.
`--verdict ratificado` is unchanged — it never touches the Ledger.

**`orphan-sweep`** — reverts `em-implementacao -> pronto-para-implementar` for orphan
tickets, using **exactly** the same staleness definition (singleton-lock heartbeat)
that `gerente_state.py` (E8.2) already uses in `detect-crash`/`reconcile`
(`_read_lock_info`/`lock_is_stale`/`DEFAULT_STALE_AFTER_SECONDS`, imported by
file — never a parallel timeout reinvented). The whole sweep is **skipped** (zero
tickets touched) whenever ANY held-and-fresh lock exists on disk — conservative
by construction: it only sweeps when it is objectively safe to assume "no Gerente cycle
is alive right now." Unlike `reconcile()` (which requires a `--cycle-id` from an
already-detected crash and iterates only the dispatches tracked in `estado-atual.yaml`), this
command is a broader complement: it scans the WHOLE `board.yaml` for `status: em-implementacao`,
with no dependency on any dispatch having been registered — a safety net for when
the dispatch trace itself was lost. It is the only command in this script that WRITES (it mutates
the `status:` field of the `.md` + appends a line to `## Log`, then regenerates `board.yaml`
by reusing `rebuild_board.py::load_tickets`/`render_board_yaml` via direct import) —
deliberate: it is a mechanical correction of a single field under an objective, auditable
condition, the same class of exception that `transition_ledger_entry.py` already is for
Ledger Entries (direct mutation, not a conversational skill).

`escalation.config.json` (committed, editable by the owner): `dead_letter_limit_days`
(default 3), `sample_size` (default 3), `orphan_stale_after_seconds` (default 900 —
same value as `DEFAULT_STALE_AFTER_SECONDS`, repeated here only to be editable without
touching `gerente_state.py`; absent falls back to `gerente_state.py`'s runtime value,
never a different number).

## Suspected false positives (Semgrep) (E13.4)

Story E13.4 (`ideias/sistema-artifacts/E13-4-loop-fp-briefing.md`), PRD 04 FR-2. Closes
the loop opened by Story E7.3: `flag_suspected_fp.py` (`semgrep/scripts/`) already writes
a JSON entry to `project_controll/semgrep-fp-suspects.jsonl` every time a headless agent
uses the pre-commit hook's escape valve to let a commit through despite an
`status: active` violation — but before this story nobody read that log
back; the only way to discover a suspect was to open the `.jsonl` by hand.

**`read_fp_suspects.py list-pending`** — a **strictly read-only** reader
(not a single `open(..., "w"/"a")` in the whole script): reads the entire `.jsonl`, groups by
`fingerprint` (`rule_id::file::line`, the same format as `flag_suspected_fp.py`)
keeping only the MOST RECENT entry for each (the log is append-only and chronological — the
last line for a fingerprint is always the most current known status), and returns the
ones still `status: pending_ratification`. It never mutates `rules.yaml`, never mutates the
`.jsonl` itself — ratifying a suspect (truly accepting it as a FP, rejecting it, promoting
it to a rule in `rules.yaml`) is a gesture of **another flow** (owner/oracle), outside the
scope of this story: it is represented, for this reader, as a new append-only line
in the SAME `.jsonl` with the SAME fingerprint and a `status` different from
`pending_ratification` (e.g., `ratified`) — as soon as that line exists, the fingerprint
disappears from `pending` on the next read, with no earlier line ever erased
or rewritten (the whole log stays auditable and git-trackable).

The persona passes the output (`pending`) along as `--semgrep-fp-pending-json` to the next
`write-snapshot`, populating `semgrep_fp_pending` in `estado-atual.yaml` (see Schema
above) — from which `gerente_briefing.py` (write-briefing) reads and renders the
"Suspected false positives (Semgrep)" section (fingerprint + rule_id/file:line + reason +
status) with no rework, the same additive pattern already used by `escalation_sample_review`/
`escalation_dead_letter` (E9.5).

## Product routing (E9.6)

Story E9.6 (PRD 05 FR-1/FR-1b), `product-routing.md` (the full protocol — the 3-question
test, the hard exclusions, the "when in doubt, route" safety bias, the 3-way
table, the Coverage Matrix's hard rule, and the combined case — read it in full before
the first time this sub-step fires) + `scripts/gerente_product_routing.py`
(the mechanical detector, a single command). Inside sub-step 1 (`list-escalated`) of
"Escalation decided by the Gerente (E9.5)" above, BEFORE deciding the `trilha`: the
Gerente classifies whether the ticket **changes the product** (a test anchored in `trigger-map` +
Coverage Matrix `_bmad-output/C-UX-Scenarios/00-ux-scenarios.md` + `product-decisions.md`
— the "documented product truth") and, if so, chooses among 3 paths:

- **(i) needs design** (or touches a page/scenario of the Coverage Matrix — a hard rule,
  no exception) → `trilha: wds` (the actual execution of the `wds-8` Pass is E9.8, out of scope for this story).
- **(ii) small rule already decided** (without touching the Coverage Matrix) → orthogonal to the `trilha`;
  records the change as a `decisao-de-produto` Ledger entry
  (`wiki/ledger/decisao-de-produto/`, via the `on_complete` contract). *(QA-builder-based
  logging was removed from this kit — path (ii) now registers directly in the Ledger.)*
- **(iii) does not change the product** → no document action; `trilha` is decided
  normally by the ticket's actual work.

**Combined case** (touches the Coverage Matrix **and** matches a recorded decision) → path (i)
**wins**; the enrichment of `product-decisions.md` happens as a side effect of the same
ticket, never as an isolated path (ii) in parallel.

**`gerente_product_routing.py check-coverage-touch`** — a single command, read-only,
stdlib only. It mechanizes ONLY the objective sub-question "does the ticket touch a
page/scenario of the Coverage Matrix?" (the hard rule §5 of `product-routing.md`) — it parses the
`**Pages:**` blocks of each scenario in `00-ux-scenarios.md` and compares (normalized: lowercase,
accent-stripped, substring in either direction, with a minimum-length-3-character
guardrail — a real finding from adversarial self-review: without it, short terms like
"a"/"de"/"e" matched as substrings in almost every page of the document, producing a spurious
`forced_route_i: true` for any ticket) against the touched terms the Gerente extracts from the
ticket's `area`/`## Locais afetados`/description. A POSITIVE match **forces**
path (i) mechanically — it is the only point in this protocol where the script decides, because
the rule itself IS mechanical (path ii is contractually read-only with respect to the design truth, it could
never fix the Coverage Matrix even if it tried). A NEGATIVE result never proves
"doesn't change [the product]" — it is just the absence of a textual match; the judgment-based
3-question test remains mandatory before concluding path (iii). The rest of the classification (changes or
not, path i vs. ii) remains 100% judgment — same discipline as "trust gate
never by feel" (E9.1)/"promotion to the Ledger is judgment" (E9.5): what is
objectively verifiable becomes testable mechanics, what is judgment never gets a fixed
heuristic.

## Executing path (i) — wds-8 never headless (E9.8)

Story E9.8 (PRD 05 FR-6, `ideias/fase-0-spikes.md` § S3 — **tested live: `wds-8`
got stuck headless**, not a hypothesis). Closes the **last story of Epic E9**. Full
contract in `wds-routing.md` (protocol, the mechanical gate for (a), the A/S/D-only
boundary) — read it in full before the first time a Ticket with `trilha: wds` reaches the
"dispatch" phase of `.claude/skills/bagual-gerente-geral/SKILL.md`.

**Hard rule, no exception:** no autonomous flow (the Gerente, nor any sub-agent it
dispatches) invokes `wds-8` (or any of its `workflow-*.md` files) headlessly — the
`WAIT FOR INPUT`/`NEVER generate content without user input` guards are semantic turn-yields,
not permission dialogs that auto-approve resolves (S3, reproduced live).

**The decision, when `trilha: wds` reaches the "dispatch" phase:** (a) in-thread oracle —
you yourself apply Analyze/Scope/Design as knowledge (never invoking `Skill(wds-8)`)
and write directly to the three canonical documents (`00-ux-scenarios.md`/`trigger-map.md`/
`product-decisions.md`); OR (b) wait for the owner — the Ticket goes to `precisa-de-info`,
citing that only the owner, interactively, can honor `wds-8`'s guards. **(b) is the default.**
(a) is **gated**, not a manual switch — it reuses the OWN Oracle
Protocol (E9.1): `record-decision --tipo decisao-de-produto` only grants `--confidence high`
for "run (a)" if a real `--precedent` exists (a previous execution of (a) already
ratified by the owner). With no precedent — the initial/normal case — the script mechanically
downgrades to `low`, `proceed_dispatch: false`, and the path falls to (b) **by
construction**, not by convention. No new config, no new script — the same
confidence mechanism from E9.1/E9.2 is the entire gating machine.

**A/S/D-only boundary:** `[I]/[T]/[P]` (Implement/Test/Publish — branch/PR/deploy) from
`wds-8` **never** happen in the autonomous flow, in any mode — already blocked
structurally ("the Gerente never runs code"), reinforced explicitly in mode (a)
("stop at Design"), and confirmed by PRD 05's Non-Goal ("Implement/Test/Deploy are
BMad", never `wds-8`). Path (ii) (light Ledger registration) remains 100% autonomous —
it never touches this protocol.

## Singleton lock (F9)

`.lock/` is a **directory**, not a file — `os.mkdir()` is atomic at the
filesystem level (fails with `FileExistsError` if it already exists), the same guarantee
`open(..., O_CREAT|O_EXCL)` would give for a file, with no TOCTOU between "check if it exists" and
"create it." Inside it, `info.json` carries `{token, pid, acquired_at, heartbeat_at,
note}`.

### Why it is not based on PID alone

There is no single long-lived OS process representing "the Gerente" in this harness —
every `gerente_state.py` call via the `Bash` tool is a short-lived process that dies on
return; the real "Gerente" is an LLM session/agent orchestrating tool calls.
Because of that:
- **`--pid` is optional and best-effort** (default `null`). When supplied with a PID that
  genuinely represents something long-lived (e.g., a `sleep`/test-daemon process, or
  eventually the root process of the headless session), a dead PID is a
  **faster** detection shortcut — the `os.kill(pid, 0)` check already flags the lock as
  reclaimable even before the heartbeat silence hits the threshold (proven in
  `test_gerente_state.py::test_dead_pid_shortcut`).
- **The primary, mandatory signal is heartbeat SILENCE**, not the cycle's fixed age:
  `stale = (pid is not alive) OR (now - heartbeat_at > --stale-after-seconds)`. A
  long cycle that keeps calling `refresh-lock` periodically never grows "old" on its
  own — it only becomes reclaimable if it **stops** giving a heartbeat. This aligns with the
  heartbeat model E11.2 will later generalize (not an isolated decision of this story).
  `DEFAULT_STALE_AFTER_SECONDS = 900` (15min) — whoever holds the lock through a long cycle
  **must** call `refresh-lock` at an interval shorter than that (e.g., at every
  phase transition of the 6-phase loop).

### Reclaim without TOCTOU

When `acquire-lock` finds the directory already existing and considers it stale, it does
**not** delete and recreate it directly (that would be a TOCTOU window: two processes could
both decide "stale" and both try to delete/recreate). Instead, it tries
`os.rename(lock_dir, unique_temp_name)` — `rename` is atomic at the filesystem: **only one
process can win** a rename of a given source name (the others get
`FileNotFoundError` and go back to the top of the loop, competing again via `mkdir`, this
time against a free path). The winner of the rename cleans up the stolen directory and also goes
back to competing via `mkdir` normally — **it does not force its own win**, it only removes the dead
lock from contention. Proven in `test_gerente_state.py::test_mutual_exclusion` (25
concurrent processes → exactly 1 winner) and `::test_stale_vs_fresh_heartbeat` (reclaim only
after silence, never before).

### Ownership via token, not via PID

`acquire-lock` generates a `token` (`uuid4`) and returns it to the caller — `refresh-lock` and
`release-lock` require that `--token` and refuse (`reason: not-owner`) if it does not match
the current holder. This decouples "proof of ownership" (the token) from "liveness
signal" (PID/heartbeat) — a legitimate holder can always prove ownership even if its nominal
PID is not trackable in this environment.

### `--cycle-id` on the lock — avoids a false crash positive

The lock also carries the `cycle_id` of the cycle it is opening for (`acquire-lock --cycle-id
...`). This exists for a real adversarial case found in self-review: a naive
`diario.jsonl` scanner (just looking at `CICLO-INICIO` with no `CICLO-FIM`) would confuse a
**long, healthy cycle running in another session** — which by definition has an open start
until it finishes — with a crash. `detect-crash` cross-checks the `cycle_id` of any orphaned
start against the `cycle_id` of a lock that is **held and not stale** at the moment of the check; if
they match, that "orphan start" is excluded from the reported orphans (it is just an ongoing
cycle, not a crash) — see `excluded_active_cycle_id` in the output and the test
`test_no_false_positive_for_healthy_long_cycle`. As soon as that lock's heartbeat stops
(silence > `--stale-after-seconds`), the exclusion no longer applies and the same cycle
correctly lights up as a crash again.

### Safety net in `acquire-lock`

Every successful `acquire-lock` also runs the `detect-crash` check internally
(excluding the `cycle_id` just acquired) and appends `pending_crash` to the response
whenever it finds something — even if the caller forgets to run `detect-crash`
explicitly beforehand, the signal that "there is an unreconciled crash" cannot pass
unnoticed in the `acquire-lock` response itself. This does not block acquisition (the
reconciliation itself remains a decision for the persona, not a mechanical gate) — it is
a structural reinforcement, not a guarantee of total enforcement (see the Residual Concern in the
story's Dev Agent Record).

### Mechanical guard on `open-dispatch` (Story E15.4)

The "safety net" above (`acquire-lock` runs `detect-crash` internally and appends
`pending_crash` to the response) is deliberately **non-blocking** — E8.2 correctly rejected
gating `acquire-lock`, because it is also used for pure state inspection
(`check-lock` calls the same read primitive, and blocking lock acquisition itself would break
that use). The real gap was never `acquire-lock` — it was the NEXT step: nothing
stopped the persona from jumping from "I acquired the lock" straight into
`gerente_dispatch.py open-dispatch` without ever having actually run `detect-crash`/`reconcile`
(the safety net only *reports*, never *prevents*).

Story E15.4 closes that gap with a lightweight **per-`cycle_id` sentinel**:
`detect-crash --cycle-id X`/`reconcile --cycle-id X` (and, by composition,
`gerente_wake.py wake-attempt` when `proceed: true`) write, when run — even when
they find nothing to reconcile —, a file `<root>/.crash-check-sentinels/
<cycle_id>.json` (`{cycle_id, source, checked_at[, detail]}`, atomic write, the same
`write_atomic` primitive as always). `gerente_dispatch.py::open-dispatch --cycle-id X`
now REQUIRES that sentinel: if absent, it refuses (`ok:false`, exit 1) BEFORE any
write — `request.yaml` never even gets created. The sentinel is scoped strictly
by `cycle_id` (never global) — one for cycle A never unlocks `open-dispatch` for cycle
B. `acquire-lock`/`check-lock`/any read remain **free**, requiring no
sentinel — the guard is only about `open-dispatch`.

`--cycle-id` in `detect-crash` is **optional and backward-compatible**: if omitted, the command
stays in pure diagnostic mode (no sentinel written) — only the persona, in its step
0 of Activation, decides the new cycle's `cycle_id` ahead of time and passes it
explicitly. `reconcile --cycle-id` was already required and always writes the sentinel for
the `cycle_id` it reconciled. See `.claude/skills/bagual-gerente-geral/references/activation-and-lock.md` (step 0)
for the exact sequence the persona follows, and `test_gerente_state.py` §[6]/
`test_gerente_dispatch.py` §[13]/`test_gerente_wake.py` §[7] for the mechanical proofs
(blocking, releasing, scoping by `cycle_id`, and that `acquire-lock`/`check-lock` remain
free).

### Preemption by the owner's interactive presence

FR-11/F9: *"if the owner opens the chat interactively while the nighttime Gerente is running, the
owner's presence preempts/pauses the autonomous loop."* This story (E8.2) delivers the
**observable mechanism** (`acquire-lock`/`check-lock` correctly refuse when there is already
a live holder) — the **action** of stopping/yielding the autonomous loop upon detecting this is
persona behavior (`gerente-geral.md` § Activation, already updated by this story
to call `check-lock` before deciding to start a cycle). Killing/signaling a running
autonomous process (process supervision) is out of scope for E8.2 — this directory is
a *state* layer, not a supervisor; that is E8.8's territory (local wake).

## Crash recovery (F23)

`diario.md`/`diario.jsonl` are the **primary source of truth** for detecting a crash —
`estado-atual.yaml` is only corroborative, never blindly trusted (this is exactly the text
of PRD 00 §4.8: *"does not blindly trust estado-atual.yaml"*). `detect-crash`'s algorithm:
scan the entire `diario.jsonl`, push `CICLO-INICIO` by `cycle_id`,
pop on `CICLO-FIM`; any `cycle_id` left over at the end is a cycle that started and
never ended → `crashed: true`.

### Reconciliation checklist (what `reconcile` does, in order)

1. Reads `estado-atual.yaml`; only uses the `dispatches` array if `cycle.id` matches the
   detected orphan `cycle_id` (otherwise it records the discrepancy in `notes` and proceeds with no
   trackable dispatches — it never invents data).
2. For each in-flight dispatch: checks whether `status` is already terminal
   (`concluido|falhou|reconciliado`); if not, it is suspicious.
3. Cross-checks the dispatch's `ticket(s)` against
   `project_controll/tickets/board.yaml` (read-only, `reconcile` is **purely
   diagnostic**, never a write) — a ticket still `em-implementacao` is a strong orphan signal.
   When the dispatch carries a `dispatch_id` (Story E8.4), the FULL list of tickets is
   resolved by reading `dispatches/{dispatch_id}/request.yaml` (source of truth), not just the
   single `ticket` of the snapshot.
4. If the dispatch recorded a `worktree`, checks whether the path still exists on disk
   (orphan removed) or still exists (needs manual verification — might be
   mergeable, might be trash).
4b. **(Story E8.4)** If the dispatch carries a `dispatch_id`, checks whether
   `dispatches/{dispatch_id}/DONE.marker` exists — its absence is one more reason for
   orphan status, cross-checking directly against the on-disk dispatch contract
   (`dispatch-contract.md`) from this checklist. The two mechanisms converge here: the
   `dispatch_id` is the link connecting the E8.2 snapshot to the E8.4 file-mediated contract.
5. Reports `orphans` (a list) + `recommended_next_step` — **never moves the Ticket on its own**;
   the recommendation is always to invoke `bagual-tickets` (composition, never hand-editing
   `board.yaml` — the same rule `gerente-geral.md` already follows for every Ticket
   write).
6. Appends a summary to the diary (`reconciliei: N despacho(s) verificado(s), M órfão(s)`) and
   a synthetic `CICLO-FIM ... (reconciled)` for the orphan `cycle_id` — closing the cycle
   in the diary so `detect-crash` stops lighting up for it. **This happens before
   any new decision of the following cycle**, by construction: the persona calls
   `detect-crash` → if `crashed: true`, calls `reconcile` → only then proceeds to
   `priorizar`/`despachar` for the new cycle (see `gerente-geral.md` § Activation).

## CLI reference

```
python3 project_controll/gerente/scripts/gerente_state.py write-snapshot \
  --root project_controll/gerente --marker start|end --cycle-id ID --started-at ISO \
  [--ended-at ISO] --phase FASE [--stop-reason cota|fila-vazia|bloqueio] \
  [--dispatches-json '[...]'] [--pending-json '[...]'] [--escalated-json '[...]'] \
  [--sample-review-json '[...]'] [--dead-letter-json '[...]'] \
  [--semgrep-fp-pending-json '[...]']   # Story E13.4, output of read_fp_suspects.py list-pending \
  [--priorities-json '[...]'] [--quota-five-hour N] [--quota-seven-day N] \
  [--quota-source STR] [--quota-read-at ISO] \
  [--quota-self-tokens N] [--quota-self-pct N] [--quota-stronger-pct N] \
  [--quota-stronger-source STR]   # last 4: Story E8.3, see `check`'s write_snapshot_quota_args \
  [--last-briefing-at ISO]

python3 project_controll/gerente/scripts/gerente_state.py append-diario \
  --root project_controll/gerente --event EVENTO --cycle-id ID [--text STR] [--ts ISO] \
  [--reconciled]   # only --event CICLO-FIM

python3 project_controll/gerente/scripts/gerente_state.py acquire-lock \
  --root project_controll/gerente [--pid N] [--note STR] [--cycle-id ID] \
  [--stale-after-seconds N=900]

python3 project_controll/gerente/scripts/gerente_state.py refresh-lock \
  --root project_controll/gerente --token TOKEN [--pid N] [--cycle-id ID]

python3 project_controll/gerente/scripts/gerente_state.py release-lock \
  --root project_controll/gerente --token TOKEN

python3 project_controll/gerente/scripts/gerente_state.py check-lock \
  --root project_controll/gerente [--stale-after-seconds N=900]

python3 project_controll/gerente/scripts/gerente_state.py detect-crash \
  --root project_controll/gerente [--stale-after-seconds N=900] \
  [--cycle-id ID]   # Story E15.4 — if given, writes the crash-check sentinel for ID
                    # (open-dispatch guard); omitted: pure diagnostic mode, backward-compat

python3 project_controll/gerente/scripts/gerente_state.py reconcile \
  --root project_controll/gerente --cycle-id ID [--board-path PATH]
  # always writes the crash-check sentinel (E15.4) for --cycle-id, in addition to the
  # usual reconciliation work

python3 project_controll/gerente/scripts/gerente_quota.py read-limits \
  [--root project_controll/gerente] [--path ~/.claude/rate-limits-state.json] \
  [--stale-snapshot-seconds N=900]

python3 project_controll/gerente/scripts/gerente_quota.py record-usage \
  --root project_controll/gerente --cycle-id ID --tokens N [--note STR] \
  [--multiplier N=1.15] [--reset]

python3 project_controll/gerente/scripts/gerente_quota.py check \
  --root project_controll/gerente --cycle-id ID \
  [--limits-path ~/.claude/rate-limits-state.json] [--threshold-pct N=85.0] \
  [--self-tracked-budget-tokens N=300000] [--stale-snapshot-seconds N=900] \
  [--stop-diario]

python3 project_controll/gerente/scripts/gerente_dispatch.py open-dispatch \
  --root project_controll/gerente [--dispatch-id ID] --cycle-id ID \
  --tickets-json '["TCK-123"]' --unit epic-E8 --trilha rapida|spec|epic|wds|correct-course \
  [--worktree PATH] --skill bagual-epic-runner [--model sonnet=default] [--note STR]
  # Story E15.4 — REQUIRES a crash-check sentinel already written for --cycle-id
  # (detect-crash/reconcile --cycle-id, or wake-attempt on the wake path); refuses
  # (ok:false, exit 1, nothing written) if absent — see § Mechanical guard above

python3 project_controll/gerente/scripts/gerente_dispatch.py close-dispatch \
  --root project_controll/gerente --dispatch-id ID --outcome sucesso|falhou|pendencias \
  --verdict STR [--pending-json '[...]'] [--evidence-json '{...}'] [--closed-by STR] [--force]

python3 project_controll/gerente/scripts/gerente_dispatch.py read-result \
  --root project_controll/gerente --dispatch-id ID

python3 project_controll/gerente/scripts/gerente_dispatch.py list-inflight \
  --root project_controll/gerente [--cycle-id ID]

python3 project_controll/gerente/scripts/gerente_dispatch.py reconcile-orphan-dispatch \
  --root project_controll/gerente --dispatch-id ID [--board-path PATH]

python3 project_controll/gerente/scripts/gerente_proactive.py next-task \
  --root project_controll/gerente --cycle-id ID [--cap-per-cycle N=3]

python3 project_controll/gerente/scripts/gerente_proactive.py dedup-check \
  --root project_controll/gerente [--tickets-dir project_controll/tickets] \
  --title STR [--description STR] [--threshold N=0.30] [--top-n N=5] \
  [--include-non-proactive]

python3 project_controll/gerente/scripts/gerente_proactive.py record-proactive \
  --root project_controll/gerente --cycle-id ID \
  --category analise-adversarial-feature|completude-de-testes|descoberta-de-padroes|refino-de-tickets \
  --outcome STR [--tickets-filed-json '["TCK-..."]'] [--duplicates-skipped N=0] \
  [--note STR] [--cap-per-cycle N=3] [--reset]

python3 project_controll/gerente/scripts/gerente_briefing.py write-briefing \
  --root project_controll/gerente --cycle-id ID [--started-at ISO] [--ended-at ISO] \
  --stop-reason cota|fila-vazia|bloqueio [--stop-detail teto-proativo] \
  [--diario-jsonl-path PATH] [--estado-path PATH] [--ts ISO]

python3 project_controll/gerente/scripts/gerente_briefing.py detect-unread \
  --root project_controll/gerente

python3 project_controll/gerente/scripts/gerente_briefing.py mark-read \
  --root project_controll/gerente (--date YYYYMMDD | --path PATH) [--ts ISO]

python3 project_controll/gerente/scripts/gerente_wake.py wake-attempt \
  --root project_controll/gerente [--note STR] [--cycle-id ID] \
  [--stale-after-seconds N=900]   # default = DEFAULT_STALE_AFTER_SECONDS from gerente_state.py

python3 project_controll/gerente/scripts/gerente_oracle.py record-decision \
  --ledger-root wiki/ledger [--tipo decisao-tecnica=default|decisao-de-produto|decisao-de-arquitetura] \
  --ticket TCK-123 --question STR --decision STR --justification STR --context STR \
  [--alternatives STR] [--areas "sistema-orquestrador,gerente-geral,oraculo"=default] \
  [--confidence low=default|high] [--precedent PATH] [--slug STR]

python3 project_controll/gerente/scripts/gerente_oracle.py list-pending \
  --ledger-root wiki/ledger [--ticket TCK-123]

python3 project_controll/gerente/scripts/gerente_oracle.py set-ratification \
  (--entry PATH | [--ledger-root wiki/ledger] --ticket TCK-123) \
  --status ratified|corrected [--note STR]

python3 project_controll/gerente/scripts/gerente_style.py consult-precedent \
  --ledger-root wiki/ledger \
  --tipo decisao-tecnica=default|decisao-de-produto|decisao-de-arquitetura \
  --areas "a,b" [--keywords "c,d"] [--oracle-config PATH] \
  [--product-decisions-path PATH] [--decisions-path PATH]

python3 project_controll/gerente/scripts/gerente_style.py sm2 \
  --ledger-root wiki/ledger \
  [--tipo decisao-tecnica|decisao-de-produto|decisao-de-arquitetura] [--verbose]

python3 project_controll/gerente/scripts/gerente_escalation.py list-escalated \
  [--board-path project_controll/tickets/board.yaml] [--pretty]

python3 project_controll/gerente/scripts/gerente_escalation.py dead-letter-check \
  [--board-path project_controll/tickets/board.yaml] [--limit-days N] [--config PATH] [--pretty]

python3 project_controll/gerente/scripts/gerente_escalation.py sample-decisions \
  [--board-path project_controll/tickets/board.yaml] \
  [--state-path project_controll/gerente/sampled-decisions.json] \
  [--sample-size N] [--config PATH] [--pretty]

python3 project_controll/gerente/scripts/gerente_escalation.py record-sample-review \
  [--state-path project_controll/gerente/sampled-decisions.json] \
  --ticket TCK-123 --verdict ratificado|corrigido \
  [--trilha-auto STR] [--trilha-corrigida STR] [--note STR] \
  # --verdict corrigido (E15.3, T2.3): REQUIRES, besides --trilha-auto/--trilha-corrigida,
  # the decision-trace fields below — writes record_decision + set_ratification
  # (status: corrected) in the SAME invocation (direct import of gerente_oracle.py):
  [--question STR] [--justification STR] [--context STR] \
  [--decision STR] [--tipo decisao-tecnica=default|decisao-de-produto|decisao-de-arquitetura] \
  [--areas "a,b"=escalonamento,gerente-geral,trilha] \
  [--ledger-root wiki/ledger] [--oracle-config PATH]

python3 project_controll/gerente/scripts/gerente_escalation.py orphan-sweep \
  [--gerente-root project_controll/gerente] [--tickets-dir project_controll/tickets] \
  [--board-path project_controll/tickets/board.yaml] \
  [--stale-after-seconds N=900] [--config PATH] [--dry-run] [--pretty]

python3 project_controll/gerente/scripts/read_fp_suspects.py list-pending \
  [--log project_controll/semgrep-fp-suspects.jsonl] [--pretty]

python3 project_controll/gerente/scripts/gerente_product_routing.py check-coverage-touch \
  [--coverage-matrix-path _bmad-output/C-UX-Scenarios/00-ux-scenarios.md] \
  --touched "termo1,termo2,..."
```
See `dispatch-contract.md` for the full contract of the 5 `gerente_dispatch.py`
commands (schema of `request.yaml`/`result.yaml`, ordering guarantee, dual detection). See
`proactive-catalog.md` for the content/guardrails of the 4 categories of the 3
`gerente_proactive.py` commands above. See § Oracle (E9.1) above for the full trust gate
of the 3 `gerente_oracle.py` commands, and § Style learning (E9.2) for the 2
`gerente_style.py` commands + the `--oracle-config`/history that now also gates
`record-decision`.

All commands print a JSON line (`ok`/`acquired`/`held`/`crashed` depending on
the command) — the same "write-only, echo the new state" spirit as `memlog.py`, so
callers never need to reread the file to know where things stand.

## How the persona uses this (see `.claude/skills/bagual-gerente-geral/references/activation-and-lock.md`)

**Local wake (Story E8.8) — only when this activation was triggered by `loop`/
`CronCreate`, see `wake.md` and § Local wake (E8.8) above:**
0. BEFORE anything below, `gerente_wake.py wake-attempt` has already run (outside the agent, via the
   `PROMPT-DE-WAKE`) and only invoked `Agent(subagent_type: "gerente-geral")` when
   `proceed: true` — the persona receives `cycle_id`/`token` already prepared in the dispatch
   prompt. In that case, steps 1-2 below are SKIPPED (the wake already did the
   crash-check by composition via `acquire_lock`, and is already the lock's holder) — call
   `reconcile --cycle-id <orphan>` only if the wake flagged `pending_crash`. Step 3
   (`acquire-lock`) is also SKIPPED — the wake is already the holder. Outside this
   path (direct interactive activation, or headless without having gone through a wake), ignore this
   bullet and follow 1-4 normally. **`open-dispatch` guard (E15.4):** `wake-attempt`
   already wrote the crash-check sentinel for this `cycle_id` — the persona never needs to
   run `detect-crash --cycle-id` again just because of the guard on this path.

On activation, before deciding anything:
1. `check-lock` — if `held: true` and not `stale`, another instance (or the owner) is active;
   do not start a new cycle.
2. Decide `<new-id>` (the cycle_id of the cycle about to open) and run
   `detect-crash --cycle-id <new-id>` — if `crashed: true`, call
   `reconcile --cycle-id <orphan>` **before** proceeding. **`open-dispatch` guard
   (E15.4):** passing `--cycle-id <new-id>` here writes the sentinel that `open-dispatch`
   will require in the "dispatch" phase — without it, every dispatch of this cycle is
   refused even with the lock already acquired (see § Mechanical guard on `open-dispatch` above).
3. `acquire-lock --cycle-id <new-id>` — the SAME id as step 2, only then acquires the lock
   for the new cycle; keeps the `token`. Passing `--cycle-id` here is what lets a
   FUTURE wake distinguish "this cycle is just ongoing" from "this is a crash" (see
   §`--cycle-id` on the lock above).
4. `write-snapshot --marker start` at the start of the cycle (optimistic); `refresh-lock`
   periodically during it; `write-snapshot --marker end` + `append-diario --event
   CICLO-FIM` + `release-lock --token ...` when closing.

**Quota (Story E8.3), during the cycle and in the "stop" phase:**
5. After EVERY dispatch returns (and periodically for its own turns), calls
   `gerente_quota.py record-usage --cycle-id <same cycle id> --tokens N --note ...`
   with an estimate of the spend (see § Quota (E8.3) above for what to count).
6. Before starting a NEW unit of work (returning to the "priorizar" phase), calls
   `gerente_quota.py check --cycle-id <same id> --stop-diario`. If `verdict: "stop"`,
   it **does not start** the new unit — `--stop-diario` already writes `parei-por-cota` to the
   diary; the persona proceeds to the "stop" phase normally (write-snapshot end,
   CICLO-FIM, release-lock).
7. When writing the cycle's final `write-snapshot`, passes along the
   fields from `check`'s `write_snapshot_quota_args` as extra arguments (`--quota-self-tokens`,
   `--quota-self-pct`, `--quota-stronger-pct`, `--quota-stronger-source`, in addition to the 4 already
   present from E8.2) — this way the cycle's quota snapshot carries both signals and which
   one won, not just the raw input.

**Dispatch (Story E8.4, updated by Story TCK-20260717131540-622d), "dispatch"/"review" phases
— see `dispatch-contract.md` for the full contract:**
8. "Dispatch" phase: `open-dispatch` (requires the crash-check sentinel from step 2/0
   above for this `cycle_id` — Story E15.4, see § Mechanical guard above) → includes the
   returned `dispatch_entry` in the next `write-snapshot --dispatches-json` → spawns the
   executor sub-agent (the `Agent` tool, `model: "sonnet"`, **in background by default**
   `run_in_background: true`) instructed to call `close-dispatch` as its last action. The
   persona returns control immediately after the spawn, without waiting for the return this
   turn. Disjoint parallel Tickets may repeat this step once per isolated
   worktree (`bagual-worktree`, `--base-branch dev`) — see `gerente-geral.md` §
   "Ticket Parallelism".
9. "Review" phase: runs when the `<task-notification>` for that `dispatch_id`
   arrives — the primary signal, now asynchronous (it can be a turn much later, or a
   future activation). `read-result --dispatch-id ID` reads the payload (only when `done:
   true`). If `done: false` despite the notification having already arrived,
   `reconcile-orphan-dispatch --dispatch-id ID` diagnoses it — treated as a failed
   dispatch, a Ticket never silently becomes `concluido`. If the cycle/session ends before
   some notification arrives, that is expected (not a crash) — the next cycle/wake
   reconciles it via `list-inflight` at step 0 of "Activation."

**Proactive work (Story E8.5), "priorizar" phase when the queue is empty — see §
Proactive work (E8.5) above and `proactive-catalog.md` for the full contract:**
10. `next-task --cycle-id <same id>` → if `cap-reached`, ends the proactive branch (proceeds
    to "stop," reporting "stopped due to the proactive cap"); if `go`, dispatches ONE
    read-only Sonnet sub-agent for the returned category.
11. For each finding from the sub-agent: `dedup-check --title ... --description ...` → only
    invokes `bagual-tickets --headless` when `duplicate: false`; always calls
    `record-proactive` once at the end of the iteration, then goes back to step 10.

**Briefing (Story E8.7) — activation (step 5, interactive session only) and "stop" phase (step
6) — see § Briefing (E8.7) above for the full contract:**
12. Activation, after steps 1-4: `detect-unread` — for each `status: unread` entry,
    read the file and render its full content in the response, then `mark-read --date
    <date> --expected-last-cycle-id <last_cycle_id returned by detect-unread>` (the
    compare-and-swap that avoids clobbering a new section written by a concurrent headless
    cycle — see § Briefing (E8.7) above "Race between detect-unread and mark-read"; if
    it returns `error: "stale"`, re-detect and re-render before trying again). Skipped
    silently in headless/proactive cycles (no owner to read it) or when `count: 0`.
13. "Stop" phase, right after `append-diario --event CICLO-FIM` and before `release-lock`:
    `write-briefing --cycle-id <same id> --started-at <start ts> --ended-at <now>
    --stop-reason cota|fila-vazia|bloqueio [--stop-detail teto-proativo]` — idempotent
    by `--cycle-id`, safe to repeat if the "stop" phase is resumed after a
    context compaction.

**Escalation decided by the Gerente (Story E9.5) — "priorizar" phase, before handling the
regular `pronto-para-implementar` queue — see § Escalation decided by the Gerente (E9.5)
above for the full contract:**
14. `list-escalated` — for EACH escalated item returned, first classifies Product routing
    (E9.6, section above — `check-coverage-touch` for the hard rule + the 3-question
    judgment test), then decides the `trilha` via the Oracle Protocol (section
    above — path (i) forces `trilha: wds`; path (ii) records the change as a
    `decisao-de-produto` Ledger entry as an orthogonal action; path (iii) changes nothing
    here), and finally
    invokes `bagual-tickets` (Resolver) to commit `trilha`/`escalonar: false`/`## Log`/
    `ledger_refs` — never reimplements that write outside the skill. A `trilha: wds`
    committed here does **not** trigger `wds-8` yet — the actual execution (E9.8, "Executing
    path (i)" section above) only happens later, when the Ticket reaches the "dispatch" phase.
15. `sample-decisions --sample-size N` — for each sample returned, ratifies or
    corrects it (judgment); `record-sample-review --verdict ratificado|corrigido` records the
    verdict; a correction also becomes a `gerente_oracle.py record-decision` + `set-
    ratification --status corrected` (feeds E9.2, see section above). Includes the
    result in the next `write-snapshot --sample-review-json '[...]'`.
16. `dead-letter-check` — includes the result in the next `write-snapshot --dead-letter-
    json '[...]'`, so `write-briefing` (step 13) renders both in the Briefing.

**Suspected false positives (Semgrep) (Story E13.4)** — at any point in the cycle
before `write-snapshot --marker end` (step 4), typically alongside steps 15-16
above — see § Suspected false positives (Semgrep) (E13.4) above for the full
contract:
17. `read_fp_suspects.py list-pending` — includes the returned `pending` field in the next
    `write-snapshot --semgrep-fp-pending-json '[...]'`, so `write-briefing` (step
    13) renders the "Suspected false positives (Semgrep)" section in the Briefing. This
    step never writes anything — it only reads `project_controll/semgrep-fp-suspects.jsonl` and
    passes the JSON along; ratifying a suspect remains outside the scope of the
    Gerente's cycle (a gesture from the owner/oracle in another flow).

**`orphan-sweep` does NOT live in the "priorizar" phase** — it runs at step 0 of "Activation"
(section above), ALONGSIDE `detect-crash`/`list-inflight`, but **always BEFORE** the new
cycle's own `acquire-lock`. A real finding from this story's adversarial self-review:
`orphan-sweep` only reverts when NO lock is held-and-fresh on disk; if it ran
AFTER `acquire-lock` (e.g., here in the "priorizar" phase), the JUST-ACQUIRED lock
itself would already be fresh, and the sweep would never revert anything — the lock represents
"some cycle is alive right now," and the persona running this command already IS that cycle after
acquiring the lock. Before `acquire-lock`, held-and-fresh can only be
ANOTHER genuinely live instance (the `check-lock` at the top of step 0 would already have
blocked the cycle before reaching here). Orphans reverted there go into the diary
(`append-diario --event decidi`, already in the "priorizar" phase, after the lock was
acquired) and, if relevant, into the Briefing via a free-text note.

## Running the tests

```
python3 project_controll/gerente/scripts/test_gerente_state.py
python3 project_controll/gerente/scripts/test_gerente_quota.py
python3 project_controll/gerente/scripts/test_gerente_dispatch.py
python3 project_controll/gerente/scripts/test_gerente_proactive.py
python3 project_controll/gerente/scripts/test_gerente_briefing.py
python3 project_controll/gerente/scripts/test_gerente_wake.py
python3 project_controll/gerente/scripts/test_gerente_oracle.py
python3 project_controll/gerente/scripts/test_gerente_style.py
python3 project_controll/gerente/scripts/test_gerente_escalation.py
python3 project_controll/gerente/scripts/test_gerente_product_routing.py
python3 project_controll/gerente/scripts/test_read_fp_suspects.py
```

28 + 33 + 42 + 31 + 71 + 33 + 68 + 52 + 31 + 12 + 24 = 425 assertions (71 in
`test_gerente_briefing.py` already includes the 12 new E13.4 checks; 24 in
`test_read_fp_suspects.py`, new), all against real subprocesses (real OS
concurrency via `multiprocessing` in the E8.2 tests, simple subprocesses in the rest — not
mocks): lock mutual exclusion, reclaim by heartbeat silence (never fixed age),
dead-PID shortcut, crash detection+reconciliation, no confusion between a healthy
active cycle and a crash, no torn reads during concurrent writes of
`estado-atual.yaml`, quota's stronger-signal in both directions, (E8.4) the
result-before-DONE.marker ordering guarantee, round-trip of pure-scalar lists,
orphan-dispatch detection, end-to-end integration with E8.2's `detect-crash`/`reconcile`, and (E8.5)
the hard cap with no off-by-one (N=1 and N=3), dedup matching against `concluido`/
`descartado` history but never against genuinely new findings, and exclusion of
`origem: manual` tickets from the scan by default. (E8.7) the 3 `stop_reason`
labels derived correctly, the `teto-proativo` nuance without inventing a 4th value,
forward-dep E9.1 populated vs. empty vs. missing key, a torn/isolated malformed diary
line without a crash, the detect-unread → mark-read → disappears-from-list idempotent
cycle, `write-briefing` idempotency by `--cycle-id` (replaces, doesn't duplicate) and
appending a section for a 2nd cycle on the same calendar day, file date derived
from `--ended-at` (never from the system clock, save the documented fallback),
no traceback for `mark-read`/`detect-unread` against an empty/missing `--root`,
and the `mark-read --expected-last-cycle-id` compare-and-swap refusing to mark as read
when a concurrent `write-briefing` already appended a new section in the meantime
(without losing the new section). The fixtures used live in
`ideias/sistema-artifacts/fixtures/E8/` (they never write to the real `project_controll/gerente/`
— always a `--root` from `tempfile.TemporaryDirectory()`).

(E8.8) singleton respected (a 2nd immediate `wake-attempt` over a held-and-fresh lock defers,
`proceed:false`), a mid-flight wake never doubles the decision-maker, an interactive owner (lock acquired
outside any wake) preempts a subsequent `wake-attempt` exactly like any
other holder, reentrancy after `release-lock` (new `cycle_id`, `pending_crash: null`),
composition with E8.2's crash-recovery (a pre-existing orphan `CICLO-INICIO` → the next
`wake-attempt` returns `pending_crash` populated, but `gerente_wake.py` never reconciles
on its own — `detect-crash` directly keeps lighting up afterward), exit code 0 for `proceed:true`
AND `proceed:false`, and the absence of any import of a network/billing SDK module (a mechanical
scan of the file's real `import`/`from` lines, not raw text — the
docstring itself cites the tokens as an example of the search). `test_gerente_wake.py` uses
`tempfile.TemporaryDirectory()` (never the real `project_controll/gerente/`).

(E9.1) F10's CENTRAL CASE proven both ways — `high` honored only with a precedent that has
`estado: ativa` + `ratification` absent/`ratified` (`[7]`), and downgraded to `low` in
EVERY other case: no `--precedent` (`[3]`), a nonexistent precedent (`[4]`),
retired (`[5]`), corrected by the owner (`[6]`), and — the test that closes the loop — an
entry that JUST got corrected (`set-ratification --status corrected`) never again
supports `high` as a precedent for a subsequent decision (`[10b]`); `proceed_dispatch`
always `false` for every low-confidence case, never just an unaccompanied text field
with no real effect; front-matter injection rejected (`exit != 0`, never silent
sanitization) for `--ticket`/`--precedent`/an `--areas` item with an embedded line break
(`[12b]`); real concurrency with 20 simultaneous processes writing the same
ticket/decision — 20 unique paths, 20 surviving files, zero crashes (`[12c]`);
`set-ratification` promoting `candidata -> ativa` only on `ratified` (never on
`corrected`) and resolving by `--ticket` with an explicit error on ambiguity/absence;
`list-pending` reflecting the real state after every mutation, reread by a NEW subprocess
on every call (proof of on-disk persistence, not in-memory state); and
`validate_ledger.py --json` against the whole tree generated by the tests with no
violation. Real fixtures (`ativa`/`aposentada`/`corrected` precedents) live in
`ideias/sistema-artifacts/fixtures/E9/`; the working ledger-root is always a
`tempfile.TemporaryDirectory()` — the real `wiki/ledger/` is never written to.

(E9.2) `consult-precedent` suggesting `high` when a similar ratified precedent
exists, `low` when there isn't enough `areas` overlap (`[A]`); the SAME absolute
overlap (1 tag) supporting `decisao-tecnica` (threshold 1) but NOT `decisao-de-produto`
(threshold 2, the more sensitive category) — only with 2 tags does the stricter
category also support it (`[B]`); **the story's central case**: a ratified precedent AND a
corrected decision, both similar, coexisting in the same Ledger always resolve to `low` —
the correction is never obscured by competing support (`[C]`); the SAME invariant inside
the real `record-decision` gate (not just `consult-precedent`'s suggestion) — an
explicit, mechanically valid (F10) `--precedent` is still vetoed when a similar
`corrected` exists, with `contradicting_corrected` populated in the response for
auditing; a positive control proving the veto is selective by real overlap, not a
blind block after the first correction (`[D]`); `sm2` computing `ratified`/`corrected`/
`pending`/`decided`/`pct_ratified` from a count built and checked with simple
arithmetic (never hardcoded in the script), with and without `--tipo`, `null` over an
empty/nonexistent ledger-root (never a crash), and the `pct` correctly changing when a
NEW real ratification is added mid-test (`[E]`); the informational scan
of `product-decisions.md`/`decisions.md` by section title correctly finding/filtering,
without ever influencing `suggested_confidence` (`[F]`); and a
CUSTOM `oracle.config.json` (via `--oracle-config`) actually changing the verdict of both
`consult-precedent` and the real `record-decision` gate — proof that
per-category configurability is real, not just the hardcoded defaults working by
coincidence (`[G]`). All working ledger-roots are `tempfile.TemporaryDirectory()`
— the real `wiki/ledger/` is never written (`git status --short` checked before/
after each run).

(E9.5) `list-escalated` returns only `escalonar: true`, never the auto-committed ones nor the
control one (`[1]`); `dead-letter-check` correctly classifies an escalated item with a very old
`updated` as dead-letter and — proven with the REAL date of the machine running the
test, not a fixed date that would break in the future — an item updated just now is not
dead-letter (`[2]`); `sample-decisions` samples only `trilha` != null + `escalonar: false`
(never the escalated one nor the control one), and a ticket already reviewed
(`record-sample-review`) NEVER reappears in a later sample, proven with a real second call
(`[3]`); and `orphan-sweep` proven across the 3 scenarios that close the AC ("does not revert a
genuinely in-flight ticket"): no lock on disk at all → reverts (`[4a]`); a held-and-fresh
lock genuinely acquired via `gerente_state.py acquire-lock` (not simulated) → does NOT revert,
the orphan ticket preserved intact in the `.md` and in the regenerated `board.yaml` (`[4b]`); a
lock present but with an artificially old heartbeat (>900s, the same
`DEFAULT_STALE_AFTER_SECONDS` from E8.2, cited in the returned reason) → reverts (`[4c]`).
All tests operate on a COPY of the fixtures in `tempfile.mkdtemp()` — they never
write to the real fixtures in `ideias/sistema-artifacts/fixtures/E9/E9-5/tickets/`,
proven by a byte-for-byte content snapshot before/after the whole run (`[5]`).
