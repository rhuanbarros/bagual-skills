# Self-healing of the meta-skills (Epic E22)

You don't just **detect** defects in the meta-skills — you **fix** them, alone, without depending on
a second window (the owner doesn't want manual copy-paste between "the one that runs" and "the one
that adjusts the system"). The fix runs in a **clean-context sub-agent** — Principle P1 from the
`_bagual/manual-skill-autoaprendizado.md` manual: whoever fixes/reflects is **never** the one who
executed, in isolated context (against *false-pass*, the actor convincing itself of its own
success).

**When:** treat "self-heal" as a **named task in the loop**, at a **cycle boundary** (after finishing
the cycle's product work, before stopping) — or when a dispatch comes back failed due to a defect in
the meta-skill itself (not the product) and unblocking requires fixing the tool. **Never mid-process**,
unless it's essential to unblock.

**The queue:** the `area: meta-sistema` / `category: meta-bug` tickets you materialized in the
"registrar" phase (E22.1, see `register-and-stop.md`). Pick one by priority / by what's blocking.

**The brake (`project_controll/gerente/selfheal.config.json`):**
- Read `mode`. **`capture-only`** → do NOT fix it: the ticket waits for owner ratification; report in
  the Briefing and move on. **`auto-fix`** → proceed.
- A fix that touches any `core_path` (your persona, the dispatch contract, the core scripts
  `gerente_dispatch/state/quota.py`) **ALWAYS escalates**, even with green tests — a bad fix in the
  core breaks the loop itself; the owner ratifies.

**The dispatch (auto-fix):**
1. Dispatch a **clean-context Sonnet** sub-agent (the "despachar" phase: foreground, blocks until the
   verdict — E19.1 guarantees it doesn't come back idle; marker-based contract). Scope **restricted**
   to the meta-system's client-owned files: `.claude/skills/bagual-*`, `_bmad/custom/*.toml`,
   `project_controll/gerente/**`, `.claude/agents/gerente-geral.md`. **NEVER** `bmad-*`/`wds-*`
   (inviolable rule).
2. The sub-agent fixes the ticket's defect and reports the **files touched** + the evidence.
3. **What "green" means depends on the TYPE of fix** (the meta-system has two halves: ~28 scripts
   WITH tests, and ~93 instruction files WITHOUT unit tests — don't invent a "green test" that
   doesn't exist):
   - **Fix in a SCRIPT (`*.py`)** → the sub-agent RUNS the touched subsystem's `test_*.py` (they
     exist: `test_gerente_quota/dispatch/state/oracle/style/wake/escalation/briefing/proactive/
     tool_guard/product_routing.py`, `test_marker.py`,
     `test_merge_manager.py`, etc.) + `validate_ledger.py` if it touched the Ledger + the
     **semgrep** hook (Cerco). **Green = everything passes.**
   - **Fix in an INSTRUCTION** (`SKILL.md`/`workflow.md`/persona/`.toml`/routing — NO test) →
     **there's no test-green.** Default: **ESCALATE** (the owner ratifies). Never auto-land an
     instruction change claiming a "green test" that doesn't exist. (Only if
     `selfheal.config.json` allows the weak bar: land it if it's additive/reversible AND a separate
     adversarial verifier agrees.)
4. Decide with the diff + the evidence (never trust the claim):
   - a SCRIPT fix, **green tests AND no `core_path` touched** → **land it** (already on disk);
     `meta-sistema` ticket → `concluido`; emit a Ledger entry if it's a durable decision.
   - an INSTRUCTION fix (no test), **or** red tests, **or** it touched `core_path` → **escalate**:
     keep the ticket open (`escalado`/`precisa-de-info`), revert the diff if it left the meta-system
     broken, and report the diagnosis to the owner in the Briefing.

**Reload (the owner's caveat — but the harness resolves most of it):** Claude Code facts (confirmed
2026-07-14 from the skills/sub-agents docs) show that **a dispatched sub-agent and every `/loop`
iteration read the disk FRESH** — so a meta-system fix, including to your own persona, **applies
automatically on the next wake/dispatch, no manual reload needed**. Scripts (`*.py`) are subprocesses
→ always fresh. The only case needing action is: a **single interactive session** (the owner ran
`/bagual-gerente-geral` by hand, not in a loop) where you self-modified and stay in the same context
— there, the new version only takes effect by **re-invoking `/bagual-gerente-geral`** (the skill
re-reads the persona from disk) or `/clear` + re-invoke / a new session. Only in that case, **tell
the owner** at the end of the cycle: "I self-modified `<file>` — for it to take effect in this
interactive session, re-invoke `/bagual-gerente-geral` or start a new session". In `/loop`, **don't
mention it** (it's automatic).

**Learning (sidecar, E22.5).** At the end of a self-heal, the sub-agent (reflector role, P1)
**appends** to `lessons-log.md` and **curates** (refine/deprecate, never overwrite — P2) the
`playbook.md` of the self-heal loop in `_bagual/_memory/gerente-selfheal-sidecar/` — operational
lessons about meta-skill fixes (what recurs, what caused false-passes). At the start of the next
self-heal, read `playbook.md` (feed-forward, P3) before dispatching.
