# Phase 3: despachar / Phase 4: revisar

## 3. despachar

**Formal contract (Story E8.4 — REAL since this story, replaces E8.1's provisional direct
mechanism): every dispatch goes through a marker on disk, never a return value.** Full contract in
`project_controll/gerente/dispatch-contract.md` — read the schema, the ordering guarantee, and dual
detection there; here only the operational step by step:

🔴 **Mandatory closed scope (post-incident Epic 18, TCK-20260723153000-9f21):** every PARALLEL
dispatch prompt assembles the 5 rules from `project_controll/gerente/dispatch-contract.md` §
"Closed scope in the parallel dispatch prompt" — read there, not duplicated here.

1. Map `trilha` (from the Ticket chosen in "priorizar") → skill. 🔴 **`trilha` is decided by YOUR
   OWN judgment (TCK-20260727143826-7573, 2026-07-27) — never by a script.**
   `project_controll/tickets/scripts/classify_trilha.py` is **retired as a trilha decider** (kept on
   disk for history, never deleted, never invoked in this flow anymore — see
   `wiki/ledger/decisao-tecnica/roteamento-de-trilha-e-plano-antes-da-execucao.md` for the full
   rationale). Every Ticket reaching `pronto-para-implementar` now arrives with `trilha: null` +
   `escalonar: true` (`bagual-tickets` marks 100% of them this way, no auto-committed subset anymore)
   — deciding the 3 non-`wds`/non-`correct-course` tracks below is squarely your call, using these
   criteria (not a fixed heuristic, not a keyword match):

   | `trilha` | When (judgment criteria) | Execution |
   |---|---|---|
   | `rapida` | Pontual/simple modification — a single clear location, no real design/architecture question. | `/bmad-quick-dev` direct, no John. |
   | `spec` | More complex than pontual, smaller than an epic — touches more than one place or needs a written plan, but isn't a multi-story body of work. | 🔴 **John (`bmad-agent-pm`) first** — see below — then `/bmad-create-story` + `/bmad-dev-story {story-file}`. |
   | `epic` | Multiple tickets, a large effect across several files/features, or a **recurring/reiterated problem** (the same class of issue keeps coming back as separate tickets — a signal the real fix is structural, not another point patch). | 🔴 **John (`bmad-agent-pm`) first** — see below — then `/bagual-epic-runner {N}`. |
   | `wds` | **Never `wds-8`/`wds-*` headless.** Stop here and follow "Route (i) execution — wds-8 never headless (E9.8)" (`wds-routing-execution.md`) — it decides (a) in-thread or (b) wait for the owner; only after that is resolved does this Ticket go back (or not) to a normal `trilha`. |
   | `correct-course` | `/bmad-correct-course` |

   🔴 **`spec`/`epic` → John never headless (TCK-20260727143826-7573).** Before opening a dispatch to
   `/bmad-create-story`/`/bagual-epic-runner` for either of these two tracks, stop and follow
   `.claude/skills/bagual-gerente-geral/references/spec-epic-routing-execution.md` in full — it
   mirrors the same "never headless" pattern already proven for `wds-8` above, applied to the
   `bmad-agent-pm` (John) persona: you load John in the MAIN session with the owner present, close a
   reviewed plan (adversarial review included), and only THEN dispatch execution. This is not
   optional busywork — a `spec`/`epic` Ticket dispatched straight to execution without this gate is a
   contract violation of the 2026-07-27 decision, exactly the failure mode that motivated it (real
   work quietly funneled into the light path).

   **Visual-surface check belongs in the plan, in ANY trilha (TCK-20260727143826-7573, item 6):**
   when a Ticket's affected area has a visible product surface, the plan — John's plan for
   `spec`/`epic` (see the file above), or the dispatch prompt itself for `rapida`/`wds`/
   `correct-course` — must already name HOW that surface will be checked before the work counts as
   done: a lightweight screenshot-based check for a small fix, or a full QA validation pass for a
   feature epic (QA validation is out of scope for this kit — install your own gate if you want
   one; this rule just says the plan/prompt must name HOW the surface gets checked, whatever gate
   you use).

   🔴 **Orchestration model for `epic` (2026-07-23):** `/bagual-epic-runner {N}` is loaded via
   `Skill` IN YOUR OWN session (you are the single hub/orchestrator) — never dispatch the
   epic-runner AS a background sub-agent; that drops it into an inline mode with no isolated
   reviewer. Full detail, the supported alternative, and the routing rule are in
   `.claude/skills/bagual-epic-runner/SKILL.md` § "Orchestration model" — read there, not
   duplicated here.

2. Open the dispatch:
   ```
   python3 project_controll/gerente/scripts/gerente_dispatch.py open-dispatch \
     --root project_controll/gerente --cycle-id <this cycle's cycle_id> \
     --tickets-json '["<Ticket id>"]' --unit <epic-EN or ticket:TCK-xxx> \
     --trilha <the Ticket's trilha> --skill <skill mapped above> [--worktree <path>]
   ```
   Keep `dispatch_id` and `dispatch_entry_json` from the response. **Mechanical guard (Story
   E15.4):** this command REFUSES (error, without writing `request.yaml`) if the `cycle_id` passed
   has no crash-check sentinel recorded — something that can only happen if you skipped this
   cycle's `detect-crash --cycle-id`/`reconcile`/`wake-attempt` from step 0 of "Activation"; in the
   normal flow (you always complete step 0 before reaching here) this never fires.
3. Include the just-opened `dispatch_entry` (along with any other still-in-flight dispatches from
   the same cycle) in the next `gerente_state.py write-snapshot --dispatches-json`.
4. Spawn the `Agent` tool (**always `model: "sonnet"`** — FR-7, "management on Opus, execution on
   Sonnet" — never execute the implementation inside your own Opus context) **in the background by
   default (`run_in_background: true`) — Story TCK-20260717131540-622d, replaces E8.1-E8.4's
   foreground-by-default.** You fire the dispatch and **move on IMMEDIATELY** to the next cycle step
   (recording the `dispatch_entry` in `write-snapshot`, prioritizing the next Ticket, or ending the
   cycle) — never block waiting for the return. The "4. revisar" phase **no longer runs in the same
   turn**: it runs when this specific dispatch's `<task-notification>` arrives (which may be a turn
   much later, even outside the current synchronous cycle — see "4. revisar" below for detail). The
   sub-agent's prompt instructs: (a) invoke the mapped skill, passing the Ticket's id, its content
   (`## Descrição`, `## Locais afetados`), the instruction to run on `dev` (never `main`),
   auto-approving as every other autonomous flow in this project already does; and (b) as its LAST
   action before finishing, call `python3 project_controll/gerente/scripts/gerente_dispatch.py
   close-dispatch --root project_controll/gerente --dispatch-id <step 2's dispatch_id> --outcome
   sucesso|falhou|pendencias --verdict "<summary>" [--evidence-json '{"commit":"...",
   "story_file":"..."}'] [--pending-json '[...]'] --tokens-used <RAW estimate of tokens spent on
   this dispatch>` with the REAL observed outcome — never `sucesso` by assumption.
   **`--tokens-used` (Story E15.2) mechanizes this dispatch's quota count as a side effect of the
   SAME call that closes the dispatch** — `close-dispatch` accumulates into `quota-ciclo.json` via
   `record_usage()` (direct import from `gerente_quota.py`) BEFORE writing `result.yaml`/
   `DONE.marker`, applying the same safety multiplier as always. **After E15.2, you never need to
   call `gerente_quota.py record-usage` manually for a dispatch again** — only omit `--tokens-used`
   if you genuinely have no estimate at all (in that case that dispatch's quota is undercounted, so
   prefer always passing an estimate, even a rough one, over omitting it).

**Ticket parallelism — forbidden in the shared root checkout, allowed via an isolated worktree
(Story TCK-20260717131540-622d, conditional, replaces E8.1's hard ban).** Dispatching more than one
Ticket at the same time in the shared root checkout stays **forbidden** — multiple sub-agents
editing the same working tree is a real risk of commit collision between concurrent runs. But it
**is allowed** when each parallel Ticket gets its own isolated worktree via `bagual-worktree`, one
step at a time:
1. Allocate one worktree per Ticket to be parallelized:
   `python3 .claude/skills/bagual-worktree/scripts/pool_manager.py allocate --owner
   <something> --label <something> --base-branch dev` (this project works on `dev`, not `staging` —
   the root checkout and all autonomous work start from `dev`; `staging` is only the promotion
   flow's destination, never a dispatch worktree's base).
2. For each Ticket, open the dispatch already pointing to the received worktree:
   `open-dispatch ... --worktree <path returned by allocate>`.
3. Dispatch the N `Agent`s (**always `model: "sonnet"`**, each in the background — same default as
   this story), one per worktree, all in the same "despachar" pass.
4. Each sub-agent, on finishing, calls `close-dispatch` normally (see step 4 above) and **before
   returning the worktree, MERGES the worktree's branch into `dev` from the main root checkout**
   (`git fetch`/`git merge --ff-only <worktree-branch>` or equivalent, run in the root checkout —
   never inside the worktree itself). **Only after the merge is confirmed** does it call
   `pool_manager.py return <name> --token <token>`. 🔴 **Returning the worktree BEFORE the merge is
   FORBIDDEN** (TCK-20260718135718-c49f): `return`/`clean` does a `git reset --hard` on the
   worktree's own branch against `--base-branch` (default `staging`) to recycle it — any commit not
   yet merged into `dev` at that point becomes orphan/dangling (only recoverable from the object
   store, and only while `git gc` hasn't run). This **already happened twice in the same cycle**
   (see `wiki/nota-operacional/worktree-return-hard-resets-branch-merge-before-returning.md`). The
   tool now **mechanically refuses** this scenario: `pool_manager.py return` checks whether the
   worktree's branch has commits unreachable from `dev` (`--merge-target`, default `dev`) and, if
   so, exits with an error instead of resetting — only proceed without the merge by passing
   `--force-discard` explicitly, and only when discarding those commits is **truly** the intent (not
   a shortcut to skip the merge). **Gerente judgment, not automatic:** Tickets whose `## Locais
   afetados` genuinely overlap files stay **sequential**, even with a worktree available —
   parallelism is only for genuinely disjoint work.

**Never leave a dispatch untraced (background version):** with background as the default, ending a
cycle with dispatches legitimately still in flight is **normal**, no longer a crash/hanging-dispatch
signal — the source of truth remains the on-disk dual-detection contract
(`dispatch-contract.md` § Dual completion detection), only the EXPECTATION of *when* you check it
changes: instead of blocking in the same turn, you reconcile each dispatch (a) when that dispatch's
notification arrives in this same session, or (b) on the next cycle/wake, via `list-inflight`/
`read-result`/`reconcile-orphan-dispatch` (already part of step 0 of "Activation") — no dispatch is
ever forgotten forever, but it's also never mandatory anymore for it to resolve before the current
turn ends. A dispatch only truly becomes "hanging" if it never shows up in `estado-atual.yaml`
(`dispatches[]`) nor in `list-inflight` — that gap, not simply being in flight, is what E8.1's
acceptance criterion keeps forbidding.

**A distinction that NEVER changes — Gerente level vs. nested sub-agent:** the background default
above is **only for your own dispatch, at the top level** (the Gerente dispatching the execution
layer). Rule E19.1 (`dispatch-contract.md` § "Rule E19.1") still applies strictly to any sub-agent
YOU dispatched: if that executor, in turn, spawns another gate/sub-flow (a marker-confirmed
sub-flow is the canonical case), that gate must resolve to a terminal verdict **in the same turn as the executor**,
never `run_in_background` without the executor waiting for it — a nested sub-agent that spawns
background children without awaiting them loses the child's conclusion (a lesson already logged in
the `subagent-background-child-orphan` memory). These are two distinct levels: you (the Gerente) can
hand back control immediately after dispatching; an executor you dispatched can never do the same
with its OWN children.

**Rule E19.1 (1st live-cycle gap — marker-confirmed sub-flow ↔ dispatch):** an executor that
spawns a marker-confirmed sub-flow can come back **`idle`/no-verdict** if that sub-tree goes
quiescent instead of resolving — neither success nor failure, `done: false`, `close-dispatch`
never reached, quota burning invisibly. Treat an `idle`/no-verdict return **exactly
like the `done: false` case** (reconcile + fail, never wait/hop babysitting the tree). Any such
gate must be hardened to NOT return idle (block until the in-turn verdict), and Story E19.2 makes
the quota guardrail see a dispatch still open in the middle of the tree (in-flight estimate). See
`dispatch-contract.md` § "Rule E19.1".

## 4. revisar

**When this phase runs, since the background default (Story TCK-20260717131540-622d):** no longer
"right after" the "despachar" phase in the same turn — it runs **when that dispatch's
`<task-notification>` arrives**, which may be a turn much later, even in a future activation outside
the synchronous cycle in which the dispatch was opened. The notification is the PRIMARY signal
(replaces the old "return of the foreground `Agent` tool call" — same role, just decoupled from the
dispatch turn). When processing a `dispatch_id`'s notification, read the marker (SECONDARY
signal/payload, only consulted after the notification):
```
python3 project_controll/gerente/scripts/gerente_dispatch.py read-result \
  --root project_controll/gerente --dispatch-id <dispatch_id>
```
- **`done: true`**: use `result.yaml` (via the response) as the truth — `outcome`/`verdict`/
  `pending_items`/`evidence`. Confirm the result is real, not just claimed — cross-check
  `evidence.commit`/`evidence.story_file` against verifiable traces when possible (a story file with
  `Status: done`, an entry in `sprint-status.yaml` moved to `done`, a real commit).
- **`done: false`** despite the notification already arriving (the case "the dispatch signaled
  completion but never called `close-dispatch`" — executor died mid-way, or a compaction lost the
  thread): run `reconcile-orphan-dispatch --dispatch-id <dispatch_id>` for diagnosis and treat it
  **exactly as a failure** — never wait longer, never poll the marker.

**`outcome: pendencias` with `pending_items` in QUESTION/DECISION format (E9.1) — before treating it
as a generic blocker:** if a `pending_item.note` is a question you're in a position to decide
(scope/product/trade-off ambiguity, not a missing credential/action only the owner has), **do not**
go straight to `precisa-de-info` — run the "Oracle Protocol" (see `oracle-protocol.md`) for each
`pending_item` of that type. That protocol's result (parked `triado` or proceed/redispatch) IS the
final state for this Ticket in this phase — don't apply the generic treatment below on top of it.

In ANY other case that isn't `outcome: sucesso` with confirmed real evidence (failure, a pending
item requiring information/action only the owner has, or an orphan dispatch), the Ticket **cannot**
stay in an orphaned `em-implementacao` state nor become `concluido` — move it to an explicit state
(`triado` with a note, or `precisa-de-info` if the blocker is information/action only the owner has)
via `bagual-tickets`, never leave it silently "done" without verification (see `dispatch-contract.md`
§ Ticket never silently becomes `concluido`).
