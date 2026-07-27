# Local wake for the Gerente Geral (Story E8.8)

> Story `ideias/sistema-artifacts/E8-8-wake-local.md` (Epic E8, last story — closes the
> Epic). Covers PRD 00 FR-1 (mechanism) and §8-Q2 (owner's decision, 2026-07-10: LOCAL, no
> OS cron, no cloud). See also `ideias/fase-0-spikes.md` § S4 and
> `ideias/revisao-adversarial-furos.md` § F1 (full resolution).

## What this is

The trigger for the Gerente Geral's "idle window" — the machine/session being put to use
at night without the owner present. **There is no OS cron or cloud routine in this
mechanism.** The trigger is: **a local Claude Code session left open and running**,
inside which the harness itself paces a wake — via the `loop` skill or via `CronCreate`
(native scheduling, **session-only**, never written to disk, never persisted outside the
session). When the wake fires, it calls `gerente_wake.py wake-attempt` (this directory,
`scripts/`) — a cheap gate that decides, WITHOUT spawning any sub-agent, whether it's
worth waking the Gerente Geral (Opus persona, `.claude/agents/gerente-geral.md`) right now.

## Why not OS cron / not cloud (the §8-Q2 decision, summarized)

- **Subscription-only quota, metered API forbidden** (`AGENTS.md`, `ideias/prd-00-sistema-orquestrador.md`
  § Constraints). A wake that depended on cloud infrastructure (this harness's `schedule`
  skill, which creates "routines" executed remotely) would run OUTSIDE the local
  session — with no guarantee the billing stays subscription-only, and the owner was
  explicit: "it never crossed my mind, it really is local".
- **OS cron** (`crontab`, Task Scheduler, etc.) would require a process/daemon outside the
  harness invoking Claude Code non-interactively — new infrastructure, outside the
  already-established "native > generic" spirit (`bagual-epic-runner` already spawns
  sub-agents locally without any external process orchestrator; this project doesn't use
  `tmux`/orchestration subprocesses anywhere).
- **Only accepted residue (a constraint, not a bug):** the session/machine needs to stay
  alive for the Gerente to work at night. If the session closes, the wake simply stops
  firing — this is expected, not an error case to handle.

## Prerequisite: a live local session

This mechanism only works **inside** an open, idle Claude Code session (a free REPL —
no query in progress). There is no "ghost" wake outside a real session: closing the
session (or the machine) stops the wake. The owner decides when to keep the session
alive (e.g. before going to sleep, leaving the terminal open).

## The two local mechanisms available in this harness

Both run **inside** the open session, neither writes to OS cron, neither is a cloud
"routine".

### Mechanism A — skill `loop` (recommended, simplest to operate)

`loop` runs a prompt (or slash command) at a recurring interval, or self-paces if the
interval is omitted — "Run a prompt or slash command on a recurring interval... Omit the
interval to let the model self-pace" (the skill's native description). Stays alive as
long as the session is open; ends when the session ends.

**Start:**
```
/loop 15m {PROMPT-DE-WAKE below}
```
(15 minutes is a reasonable starting point — adjust to the desired pace; a
smaller interval spends more `wake-attempt` turns, but each attempt that defers
(`proceed:false`) is cheap: just an `os.mkdir`/local file read, no sub-agent.)

**Stop:** ask to interrupt the loop within the session itself (e.g. "stop the Gerente's
loop") — or simply close the session.

### Mechanism B — `CronCreate` (the closest analog to "ScheduleWakeup" in this harness)

`CronCreate` schedules a prompt to be re-queued at a future time, with
**session-only** semantics: "Jobs live only in this Claude session — nothing is written
to disk, and the job is gone when Claude exits" and "Jobs only fire while the REPL is
idle" (the tool's native description). This is exactly the "auto-pausing/waking inside
the open session" the PRD asks for — no disk persistence, no execution outside the live
session, and with the 7-day limit the tool itself documents (reschedule by running
`CronCreate` again if more time is needed).

**Start** (example, every 15 min, recurring):
```
CronCreate(cron="7,22,37,52 * * * *", recurring=true, prompt="{PROMPT-DE-WAKE below}")
```
(minutes deliberately off `:00`/`:30`, following the tool's native guidance not to
align with the exact top of the hour — no practical effect here, since it's 100% local
and doesn't compete for a shared window, but it costs nothing to follow the convention.)

**Stop:** `CronDelete(id="<id returned by CronCreate>")` — or `CronList()` to
recover the id if lost, or simply close the session (jobs die with it).

### Why not to confuse this with the `schedule` skill

This harness also exposes a `schedule` skill ("Create, update, list, or run scheduled
**cloud** agents (routines) that execute on a cron schedule") — this is exactly what
§8-Q2/F1 forbids: execution outside the local session, potentially outside the
subscription quota. `schedule`/routines are **never** used by this mechanism, on
purpose. If a future agent considers using `schedule` "to better automate the wake",
that is a regression to an already-decided constraint — stop and use `/loop` or
`CronCreate` instead.

## The PROMPT-DE-WAKE (the exact text each tick runs)

```
Rode: python3 project_controll/gerente/scripts/gerente_wake.py wake-attempt --root project_controll/gerente

Leia o JSON de saída.
- Se "proceed": true — invoque a tool Agent com subagent_type: "gerente-geral" (model
  sonnet NÃO — a persona roda em Opus, config nativa do próprio arquivo de agente), com um
  prompt que inclui literalmente: "Você foi acordado via wake local (Story E8.8,
  loop/ScheduleWakeup). cycle_id=<cycle_id>, token=<token>, pending_crash=<pending_crash
  ou null — cole o JSON aqui>. No passo 0 da sua Ativação, use a entrada alternativa via
  wake: pule a sub-etapa acquire-lock (já feita por gerente_wake.py) e, se pending_crash
  não for null, reconcilie normalmente antes de priorizar." Aguarde o retorno do Agent
  (foreground) antes de considerar este tick concluído.
- Se "proceed": false — não invoque nada. O motivo (out["reason"], geralmente "held") já
  significa que o dono está interativo ou outro ciclo está em voo; este tick termina aqui,
  sem custo adicional. Não é um erro.
```

This is the same text, paste it literally, for `/loop` or for `CronCreate(prompt=...)` —
the two mechanisms only differ in HOW they schedule, not in what each tick does.

## `gerente_wake.py` — the cycle's entry gate

`project_controll/gerente/scripts/gerente_wake.py` (stdlib-only, reuses
`gerente_state.py::acquire_lock` via a direct IMPORT of the sibling file — the same reuse
pattern `gerente_quota.py`/`gerente_briefing.py` already use, not a pasted copy).

### `wake-attempt`

```
python3 project_controll/gerente/scripts/gerente_wake.py wake-attempt \
  --root project_controll/gerente \
  [--note "texto livre"] [--cycle-id <id>] [--stale-after-seconds N]
```

Tries `acquire_lock` (the SAME atomic primitive from E8.2 — `mkdir` + stale reclaim via
`rename`, never a reimplementation) on the wake's behalf, with a `cycle_id` generated
automatically (`wake-<timestamp>-<hex>`, labeling only for human reading in the diary —
not mechanically consumed by any other script).

**Output `proceed: true`** (free lock or stale-reclaimed):
```json
{
  "ok": true, "proceed": true,
  "cycle_id": "wake-20260711T221149-068e47",
  "token": "<holder uuid>",
  "acquired_at": "2026-07-11T22:11:49-03:00",
  "pending_crash": null,
  "note": "wake local (E8.8 — loop/ScheduleWakeup)",
  "guidance": "..."
}
```
`pending_crash` comes populated (not `null`) when the reclaimed lock was stale AND
there's an orphan `CICLO-INICIO` in the diary — the same field `acquire_lock` already
exposes as a safety net since E8.2, here just passed through as-is (`gerente_wake.py`
NEVER calls `reconcile` on its own — reconciling is the persona's judgment call, in
step 0 of the Ativação).

**Output `proceed: false`** (held-and-fresh lock — interactive owner OR another cycle in flight):
```json
{
  "ok": true, "proceed": false,
  "cycle_id": "wake-20260711T221149-9dfbe5",
  "reason": "held",
  "detail": null,
  "holder": {"token": "...", "pid": null, "acquired_at": "...", "heartbeat_at": "...", "note": "...", "cycle_id": "..."},
  "guidance": "..."
}
```
**Both outcomes exit with `exit code 0`** — deferring is a clean outcome for the gate,
not an error. Only a genuinely unexpected failure (`ok: false`) exits `1`.

### Why the gate matters (it's not just "call acquire-lock directly")

The gain from having `gerente_wake.py` as a separate step, BEFORE invoking
`Agent(subagent_type="gerente-geral")`, is that the decision "is it worth waking the
Gerente now?" is made by a millisecond stdlib script — no turn of the expensive
(Opus) agent is spent when the owner is interactive or another cycle is already
running. A `/loop` running every 15 minutes all night will, most of the time, either
find the lock free (real work happening) or find the lock held-and-fresh by a cycle it
itself started shortly before and that hasn't finished yet — in neither case is it
worth reimplementing the decision inside the Opus agent itself.

## Composition with the singleton lock (E8.2) — no 2nd decider

The central point of this story: **the wake uses the SAME lock, the SAME atomic
primitive, that any other activation (interactive or direct headless) has already been
using since E8.2.** There is no special "wake priority" path nor a "force" that jumps
the queue —
`acquire_lock` is an atomic `mkdir`, whoever arrives first (interactive owner, another
wake, or this wake) wins; the rest see `held: true`/`stale: false` and defer.

- **`gerente_wake.py wake-attempt`** is the FIRST half of what would be step 0 of the
  Ativação (`acquire-lock`) — just run OUTSIDE the expensive agent, before deciding
  whether it's even worth invoking it.
- **`.claude/agents/gerente-geral.md` step 0** gained an alternate entry (see the file,
  bullet "Entrada alternativa via wake local (Story E8.8)"): when the persona is
  invoked with a `cycle_id`/`token` already prepared (passed along by the
  PROMPT-DE-WAKE above), it **skips the `acquire-lock` sub-step** (the wake already did
  it) but still handles `pending_crash` exactly as if it had run `detect-crash` itself —
  no safety step is skipped, only the duplicate `acquire-lock` call (which would
  actually FAIL if tried again — the wake itself is already the holder).
- This means **there are no two independent decision points that could diverge**: the
  `wake-attempt` and the persona's step 0 literally use the same Python function
  (`acquire_lock` from `gerente_state.py`, imported by both), not two parallel
  implementations that would need to be kept in sync.

### "Interactive owner preempts the wake" — what this means mechanically

The phrase (already used in `gerente-geral.md`, "the owner's interactive presence
always takes precedence") **is not** a force-kill of a cycle already in flight — there
is no mechanism, in this harness, for a new interactive session to forcibly end an
`Agent` from another session already running. What actually happens, and what is
proven headlessly (see "Headless test results" below): **whoever acquires the lock
first, proceeds; whoever arrives later, sees the lock held and gives up.** If the owner
opens an interactive session WHILE a wake-triggered cycle is already in flight, the
interactive session (via the same step-0 `check-lock`) sees the lock held-and-fresh and
doesn't start its own cycle in parallel — it simply waits or works on something else;
the wake's cycle continues and finishes normally, releasing the lock at the end.
Symmetric, not a hard-coded privilege — but the practical effect (never two deciders at
the same time) is exactly what the AC asks for.

## No wake incurs metered API usage

The whole wake chain runs within the subscription quota, 100% local:
- `/loop`/`CronCreate` are native primitives of the current session's harness — none of
  them makes its own network call; `CronCreate` is explicitly described as
  session-only/in-memory, nothing written to disk.
- `gerente_wake.py` only imports stdlib (`argparse`, `importlib.util`, `json`, `sys`,
  `uuid`, `datetime`, `pathlib`, `typing`) — no network SDK, no HTTP call.
  Verified mechanically (not just claimed in prose) by
  `test_gerente_wake.py::test_no_network_path`, which scans the file's actual
  `import`/`from` lines (not the raw text — the docstring itself MENTIONS the
  forbidden tokens as a search example, so a raw-text check would self-trip).
- When `proceed: true`, the only additional "cost" is invoking `Agent(subagent_type:
  "gerente-geral")` — the SAME native call a direct interactive/headless activation
  already made before this story; the wake introduces no new provider, no API key, no
  billing route.
- When `proceed: false`, no `Agent` is invoked — zero cost beyond the `wake-attempt`
  itself (an `os.mkdir`/local JSON read).

## Manual 60s micro-test (requires a real interactive session — not headless-executable)

Just as `E1-4-validacao-round-trip.md` and `E2-4-validacao-deadlock.md` documented their
e2e verification procedures as manual steps (operations that require a real environment
a headless story cannot exercise on its own), the same applies here: scheduling a real
`ScheduleWakeup`/`loop` that fires 60s later and re-invokes the Gerente **cannot be
exercised from inside a headless sub-agent** — nobody can schedule their own wake and
block waiting for it in the same turn they schedule it. When the owner wants to confirm
this live, the procedure is:

1. Open an interactive Claude Code session in this repository, branch `staging`.
2. Run:
   ```
   /loop 1m Rode: python3 project_controll/gerente/scripts/gerente_wake.py wake-attempt --root project_controll/gerente; imprima o JSON de saída literalmente na resposta (não invoque o Agent gerente-geral neste micro-teste — só confirme que o wake dispara e o portão decide).
   ```
   (1 minute — the smallest practical interval to observe in real time; for production
   use a larger interval, see "Mechanism A" above.)
3. **Success criterion:** within ~60-90s (the `/loop` itself already embeds some
   scheduling variation), a new reply appears in the session with the
   `wake-attempt` JSON — confirming the wake actually fired inside the live session,
   with no manual action from the owner beyond having left the session open.
4. Run `python3 project_controll/gerente/scripts/gerente_state.py check-lock --root
   project_controll/gerente` in the same session to confirm that step 2's
   `wake-attempt` actually created/kept the lock on disk (`held: true`), closing the
   link between "the wake fired" and "the wake touched the real E8.2 mechanism", not a
   mock.
5. Stop the loop ("stop the Gerente's loop") and, if a lock was left held by the test,
   release it:
   `python3 project_controll/gerente/scripts/gerente_state.py release-lock --root
   project_controll/gerente --token <token from step 2's wake-attempt>` — so as not to
   leave a test lock blocking a real cycle afterward.
6. **Full variant** (optional, more realistic): repeat with the full PROMPT-DE-WAKE
   (not step 2's "just print the JSON" version) to confirm that a
   `proceed: true` actually invokes `Agent(subagent_type: "gerente-geral")` and that the
   persona recognizes the alternate entry via wake (step 0 of `gerente-geral.md`)
   without trying `acquire-lock` again.

Once this procedure is executed, its result should be appended to the Dev Agent
Record of `ideias/sistema-artifacts/E8-8-wake-local.md` as the final e2e proof — the same
"structural proof + documented manual procedure" pattern already used by E1.4/E2.4.

## Headless test results (what IS proven without a live session)

`project_controll/gerente/scripts/test_gerente_wake.py` — 33 assertions via a real
subprocess (not mocked), against `gerente_state.py`'s REAL lock, in isolated temporary
directories (never touches the real `project_controll/gerente/`):

1. **Singleton respected:** the 1st `wake-attempt` against a free root acquires
   (`proceed:true`); the 2nd IMMEDIATE `wake-attempt` against the same root (lock still
   held-and-fresh) defers (`proceed:false`, `reason:held`) — no 2nd decider.
2. **Mid-flight:** a wake "A" in flight (lock held, fresh heartbeat, no release yet)
   makes a concurrent wake "B" defer without a token — direct proof of the requirement
   "a wake colliding with a cycle in flight doesn't duplicate the decider".
3. **Interactive owner preempts:** a lock acquired the way an interactive activation
   already acquires it today (`gerente_state.py acquire-lock`, nothing wake-specific)
   blocks a subsequent `wake-attempt` exactly like scenario 1 — confirms there is no
   path that would let a wake "jump" the queue ahead of the owner.
4. **Reentrancy:** after the holder releases the lock (normal end of cycle), the next
   `wake-attempt` acquires again with a NEW `cycle_id`, `pending_crash: null` — no
   state from the previous cycle holds onto the next wake.
5. **Composition with crash-recovery (E8.2):** a pre-existing orphan `CICLO-INICIO` in
   the diary makes the following `wake-attempt` (successful, no competing lock) return
   `pending_crash` populated with the orphan `cycle_id` — and confirms that
   `gerente_wake.py` NEVER reconciles on its own (a direct `detect-crash` still fires
   after the `wake-attempt`, proving the actual resolution is left to the persona).
6. **Clean exit codes:** both `proceed:true` and `proceed:false` exit with `exit 0` —
   deferring is not treated as an error anywhere in the chain.
7. **No network path:** a scan of the file's actual `import`/`from` lines confirms
   zero network/billing SDK module; only stdlib.

**Real self-review finding (fixed in this session, before any external test):** the
first version of `wake-attempt` auto-filled `--pid` with the script's own
`os.getpid()`. Since `gerente_wake.py` is a SHORT-LIVED process
(it ends as soon as it prints the JSON), by the time a SECOND `wake-attempt` ran, the
first one's PID was already dead — `pid_alive()` saw it as `False` and
`lock_is_stale()` reclaimed the lock IMMEDIATELY, breaking mutual exclusion in
practice (reproduced: `proceed:true` on the 2nd wake, should have been `false`).
**Fixed** by removing the `--pid` auto-fill (default remains `None`), aligning with the
convention `.claude/agents/gerente-geral.md` already uses — never pass `--pid` to
`acquire-lock`, because "no single OS process reliably represents 'the Gerente' in this
agent/tool-calls harness" (original comment from `gerente_state.py::lock_is_stale`,
Story E8.2). See the story's Dev Agent Record for the full before/after.

## Adversarial self-review (scenarios considered)

- **Wake firing while a cycle holds the lock:** DEFERS (doesn't duplicate) — proven in
  test 2 above.
- **Wake after a crash:** `pending_crash` is passed through, but the actual RESOLUTION
  (reconcile) remains a step for the persona, not the gate script — this prevents
  `gerente_wake.py` from becoming a second place where reconciliation logic needs to be
  kept in sync
  with `gerente_state.py`/`gerente-geral.md`.
- **Interactive vs. autonomous owner — order:** symmetric by construction (whoever
  acquires first wins); there is no "force" for the owner over a wake cycle already in
  flight — see the dedicated section above. This is a characteristic inherited from
  E8.2, not a new gap in this story.
- **Accidental cron/cloud path:** none. `gerente_wake.py` doesn't schedule anything on
  its own (it's not the one deciding WHEN to run — that's `/loop`/`CronCreate`, chosen by
  the owner in the session); the script itself only reacts to ONE synchronous
  invocation at a time. No reference
  to `crontab`, `at`, `systemd`, or to the (cloud) `schedule` skill in `gerente_wake.py` nor
  in this document, outside the section that explains why it's forbidden.
- **Does the doc actually allow starting/stopping?** Yes — "Mechanism A"/"Mechanism B"
  above have the exact start command and the stop command for both available
  mechanisms.
- **The wake's `--stale-after-seconds` diverging from what the persona uses:** both use
  the default `DEFAULT_STALE_AFTER_SECONDS` from `gerente_state.py` (900s) when
  unspecified — the same imported constant, not a hardcoded duplicated value in two
  places.
