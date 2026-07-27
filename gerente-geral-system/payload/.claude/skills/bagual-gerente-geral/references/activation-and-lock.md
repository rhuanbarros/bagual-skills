# Activation — read the state BEFORE deciding anything

When activated (headless or interactive), your FIRST action is always to rebuild situational
awareness, in this order — never decide anything before completing this read:

0. **Singleton lock + crash recovery (Story E8.2, `project_controll/gerente/`, full contract in
   `project_controll/gerente/README.md`).** Before touching any other state file, run in this
   order:
   - **Alternate entry via local wake (Story E8.8 — `loop`/`ScheduleWakeup`, contract in
     `project_controll/gerente/wake.md`):** if this activation was triggered by a wake (the
     dispatch prompt already carries `cycle_id`/`token`, produced by `python3
     project_controll/gerente/scripts/gerente_wake.py wake-attempt`), the wake has ALREADY acquired
     the lock on your behalf — **skip the `acquire-lock` call below** (it would fail: you are
     already the holder, and a second `acquire-lock` attempt for the same cycle_id isn't the
     designed flow). If `wake-attempt` signaled `pending_crash` (not `null`), treat it exactly like
     the result of a `detect-crash` you had run yourself — run `reconcile --cycle-id <cycle_id from
     pending_crash>` and resolve the orphans via `bagual-tickets` **before** moving on to
     "priorizar", same as the flow below. After that, go straight to steps 1-4 (skipping only the
     `acquire-lock` sub-step, never the read/crash-check steps that come after it) — use the
     received `token` for `refresh-lock`/`release-lock` normally throughout the cycle, exactly as
     you would if you had acquired it yourself. If this activation did NOT come from a wake
     (direct interactive, or headless via `Agent`/`subagent_type: gerente-geral` without going
     through `gerente_wake.py`), ignore this bullet and follow the normal sequence below.
     **Mechanical guard (Story E15.4):** `wake-attempt` itself already recorded, by composition,
     the crash-check sentinel for this `cycle_id` (the same one `gerente_dispatch.py::open-dispatch`
     requires in the "despachar" phase) — you **never** need to run `detect-crash` again just to
     satisfy the guard on this path; it is already satisfied before this activation even starts.
   - `python3 project_controll/gerente/scripts/gerente_state.py check-lock --root
     project_controll/gerente` — if `held: true` and not `stale`, another instance (or the owner,
     present interactively) is already active: **do not start** (or resume) an autonomous cycle in
     parallel; the presence of another live holder always preempts yours.
   - **Decide the `<new-cycle-id>` for this cycle now** (same format as always, e.g.
     `cycle-<timestamp>`) — this used to be decided further down, at `acquire-lock` time; since
     Story E15.4 you decide it HERE because the following `detect-crash` step already needs it (see
     the bullet below). It's just a string — no script call depends on it yet; the SAME
     `<new-cycle-id>` is reused across ALL remaining steps of this step 0 (including the final
     `acquire-lock`).
   - `python3 project_controll/gerente/scripts/gerente_state.py detect-crash --root
     project_controll/gerente --cycle-id <new-cycle-id>` — if `crashed: true`, run
     `reconcile --cycle-id <orphan cycle_id> --root project_controll/gerente` **before** moving on
     to "priorizar"; read `orphans`/`recommended_next_step` from the output and resolve each orphan
     via `bagual-tickets` (never editing `board.yaml`/tickets by hand) before deciding any new
     work. **Mechanical guard (Story E15.4 — per-`cycle_id` crash-check sentinel):** passing
     `--cycle-id <new-cycle-id>` here WRITES the sentinel that `gerente_dispatch.py::open-dispatch
     --cycle-id <new-cycle-id>` (the "despachar" phase) will later require — without it,
     `open-dispatch` refuses (error, without writing `request.yaml`) any dispatch for this cycle,
     even if you already acquired the lock. The real gap was never `acquire-lock` (E8.2 correctly
     refused to block it — that would break the state inspection you just did two lines above); it
     was exactly this next step, which is now mechanically required, not just a prose convention.
     `reconcile` (when `crashed: true`) writes the SAME kind of sentinel for the `cycle_id` it
     reconciled — the `<new-cycle-id>`'s sentinel was already written by this `detect-crash`, so you
     never need to run it again just because of the guard.
   - **(Story E8.4 — always, unconditionally, even if the `detect-crash` above didn't fire):**
     `python3 project_controll/gerente/scripts/gerente_dispatch.py list-inflight --root
     project_controll/gerente`. **Why this is needed on top of E8.2's `detect-crash`/`reconcile`**,
     a real finding from this story's adversarial self-review: `reconcile` only sees dispatches
     already recorded in `estado-atual.yaml`'s `dispatches` array (via `write-snapshot
     --dispatches-json`); if a context compaction happens exactly between `open-dispatch` (the
     "despachar" phase, step 2) and the following `write-snapshot` that would record the
     `dispatch_entry` (step 3), the dispatch ends up with `request.yaml` on disk and NO
     `DONE.marker`, but `reconcile` reports `needs_attention: false` — a confirmed false negative,
     reproduced manually. `list-inflight` scans `dispatches/` directly, without depending on
     `estado-atual.yaml` — that's why it's the check that closes this gap. Since this check runs
     BEFORE you open any dispatch for the new cycle (you're still in the "ler-estado" phase), any
     entry it returns necessarily belongs to a PAST cycle, never your own in-progress one — no risk
     of the same false positive `detect-crash` had to solve for a healthy active cycle (there is no
     concurrent active cycle here: the `check-lock` above would already have blocked you if a live
     holder existed). For each returned dispatch, run `reconcile-orphan-dispatch --dispatch-id <id>
     --root project_controll/gerente` and resolve each orphan via `bagual-tickets` (never editing
     `board.yaml`/tickets by hand), same as the previous step — the two findings (from `reconcile`
     and from `list-inflight`) converge on the same treatment, never resolved through different
     paths.
   - **`em-implementacao` orphan sweep (Story E9.5, PRD 02 FR-6) — ALWAYS HERE, never after your own
     `acquire-lock` below.** `python3 project_controll/gerente/scripts/gerente_escalation.py
     orphan-sweep --gerente-root project_controll/gerente --tickets-dir project_controll/tickets
     --board-path project_controll/tickets/board.yaml`. **Why the order matters (a real finding
     from this story's adversarial self-review):** the command only reverts when NO lock is
     held-and-fresh on disk — the same heartbeat from `gerente_state.py` (E8.2) that
     `check-lock`/`detect-crash` already use, never a parallel timeout. If you called this AFTER
     `acquire-lock` (e.g., already in the "priorizar" phase), your OWN just-acquired lock would
     already be held-and-fresh, and the sweep would sit permanently inert (`swept: false` always) —
     a real bug, found and fixed while designing this story: the lock represents "some Gerente cycle
     is alive right now", and you, running this step, already ARE that cycle. Here, BEFORE
     `acquire-lock`, you are not yet the holder — a held-and-fresh lock can only belong to another
     genuinely live instance (the `check-lock` at the top of this step 0 would already have stopped
     you before reaching here if that were the case), and an absent/stale lock confirms no cycle is
     currently touching `em-implementacao` — safe to revert any ticket in that state back to
     `pronto-para-implementar`. Every orphan reverted becomes a diary line after you acquire your
     lock (`append-diario --event decidi`, see the "priorizar" phase in `priorities-and-proactive-
     work.md`). Full contract in `project_controll/gerente/README.md` § "Escalation decided by the
     Gerente (E9.5)".
   - Only then `acquire-lock --root project_controll/gerente --cycle-id <new-cycle-id>` (the SAME
     `<new-cycle-id>` already decided/used in the `detect-crash` above — never generate a different
     id here) to open today's cycle; keep the returned `token` — it authorizes `refresh-lock`/
     `release-lock` later. Call `refresh-lock` periodically during the cycle (at least on every
     phase transition) — a heartbeat that stops updating is what makes the lock reclaimable by
     another instance later.
   **Degradation (`project_controll/gerente/` legitimately absent — only before the VERY FIRST
   cycle ever, never after E8.2):** if the whole directory doesn't exist, treat it as the first
   activation ever — there's no lock to acquire nor crash to detect; proceed to steps 1-4 normally,
   without blocking.
1. **`project_controll/gerente/estado-atual.yaml`** — snapshot of the previous cycle (in-flight
   dispatches, pending decisions, quota, last Briefing timestamp). Written via `gerente_state.py
   write-snapshot --marker start` at the start of your own cycle (optimistic) and `--marker end`
   when closing it (confirmed) — see README.md § Schema. **Degradation (file absent but
   `project_controll/gerente/` already exists):** treat as the first activation ever; there's no
   previous-cycle snapshot to reconcile (step 0 above would already have detected a crash if one
   were pending); move on without blocking.
2. **Tail of `project_controll/gerente/diario.md`** — the latest entries in the append-only log of
   what's already been done (appended by you via `gerente_state.py append-diario --event ...` in
   each of the cycle's 6 phases, plus the `CICLO-INICIO`/`CICLO-FIM` markers). **Degradation
   (absent):** same treatment — skip it, don't invent past entries, don't block.
3. **`project_controll/tickets/board.yaml`** — the Ticket queue, always exists today (Epic E5
   done). Filter by `status: pronto-para-implementar`, read each Ticket's `priority`, `category`,
   `area`, `trilha`.
4. **`sprint-status.yaml`** — two possible files, don't confuse them: the **product** one
   (`_bmad-output/implementation-artifacts/sprint-status.yaml`, if an active sprint exists — see the
   note in `AGENTS.md` "only exists during an active sprint") and the **meta** one
   (`ideias/sistema-artifacts/sprint-status.yaml`, tracking the autonomous system's own build). Read
   whichever is relevant to the Ticket/effort at hand — a product Ticket points to the product
   sprint; a story of the system itself (`E1`-`E11`) points to the meta one. If no sprint is active,
   that's not an error — it's a sign that no product epic is currently underway.
5. **Unread Briefing (Story E8.7)** — only relevant when this activation is an **interactive
   session** (the owner is in the chat, not a headless cycle triggering you via `loop`/wake): run
   `python3 project_controll/gerente/scripts/gerente_briefing.py detect-unread --root
   project_controll/gerente`. For each entry returned with `status: unread` (usually 0 or 1), read
   the file (`path` from the response) and **render its full content in your own activation
   response** — time worked, what was done, decisions (with a trace), and what needs attention/
   ratification already come ready-made in the file's Markdown; do not summarize or edit the
   content, present it as the Briefing it is. Right after rendering, run `mark-read --root
   project_controll/gerente --date <the file's date> --expected-last-cycle-id <the last_cycle_id
   that detect-unread returned>` — the `--expected-last-cycle-id` protects against a concurrent
   headless cycle having appended a new section between your `detect-unread` and this `mark-read`
   (if `ok: false`/`error: "stale"` comes back, a new Briefing arrived in the meantime: run
   `detect-unread` again and render the updated content before trying `mark-read` again, instead of
   just insisting). Never leave a rendered Briefing unmarked as read (or the NEXT activation renders
   it again, duplicating the message). If `detect-unread` returns `count: 0` (nothing pending) or you
   are in a headless/proactive cycle (no owner to read it), skip this step silently — it's not an
   error, it's the common case. This never blocks or delays steps 0-4 above; it's purely
   informational for the owner.

**Singleton lock (Story E8.2 — real, see step 0 of "Activation" above):** the mechanical lock covers
concurrency between Gerente instances (autonomous vs. autonomous, or autonomous vs. you yourself
reactivated in a new window). It **does not** replace your own contextual awareness — keep avoiding
starting a cycle if you notice, from the conversation itself, clear signs of other work in progress
in the same session (e.g., a visibly ongoing `bagual-epic-runner`) even if the lock on disk is free
(e.g., a sibling process that hasn't yet called `acquire-lock`). The owner's interactive presence
always takes precedence — if they're in the chat, you don't start (or you pause) a parallel
autonomous cycle, and step 0's `check-lock` is the mechanism that makes this verifiable, not just a
behavioral promise.
