# Route spec/epic execution — John never headless (TCK-20260727143826-7573)

Canonical reference: `wiki/ledger/decisao-tecnica/roteamento-de-trilha-e-plano-antes-da-execucao.md`
— the decision already closed with the owner (2026-07-27). This file is the operational mirror,
applied to the `bmad-agent-pm` (John) persona for `trilha: spec|epic`, of the same pattern already
proven for `wds-8` in `wds-routing-execution.md` — read that file too if you haven't; the mechanism
being mirrored is identical, only the persona and the menu differ.

**When it fires:** in the "3. despachar" phase (`dispatch-and-review.md`), step 1, right after you
(the Gerente) have judged a Ticket's `trilha` to be `spec` or `epic` per the criteria table there.
**Hard rule, no exceptions:** you never invoke `bmad-agent-pm` (nor `/bmad-create-story` /
`/bagual-epic-runner`) as a headless sub-agent for this Ticket before this gate resolves — there is
no dispatch line "trilha spec/epic → spawn the executor directly". Stop before assembling any
`open-dispatch` and follow the steps below instead.

## Why — the technical restriction

`bmad-agent-pm`'s own activation (`.claude/skills/bmad-agent-pm/SKILL.md` § "Step 8: Dispatch or
Present the Menu") ends with: render the menu, then **"Stop and wait for input."** This is not prose
guidance you could work around with a clever prompt — it is the literal last instruction of the
skill's own activation sequence. Dispatched headless (the `Agent` tool, no interactive human on the
other end), John either hangs waiting for an input that will never arrive, or a sub-agent
hallucinates an answer to its own menu — producing an unattended "conversation with itself" that
never reflects a real requirements-discovery interview. This is the same class of failure already
**confirmed live** for `wds-8` (`ideias/fase-0-spikes.md` § S3 — locked up on the very first Analyze
step even with auto-approve) — same underlying mechanism (a facilitator persona built to pause for a
human), simply a different named agent and a different menu (John's is `PRD`/`CE`/`IR`/`CC`, per
`bmad-agent-pm/customize.toml`).

**No oracle escape hatch (unlike `wds-8`'s mode (a)).** The `wds-8` protocol allows a rare in-thread
oracle mode because the Gerente itself can walk Analyze/Scope/Design **as knowledge**, without
needing Freya's/Saga's personal facilitation. There is no equivalent shortcut here: the ledger
decision says literally "**with the owner**" — a `spec`/`epic` plan is a genuine
requirements-discovery interview (scope, trade-offs, what's really being asked), not a mechanical
template you can substitute with a written précis. There is no confidence-gated bypass; every
`spec`/`epic` Ticket waits for the owner.

## What happens

1. **Park the Ticket, don't dispatch.** Move it (via `bagual-tickets`) to a state that reflects "the
   owner needs to run the plan with me" — `precisa-de-info` is the existing specialization for this
   (same choice already made for `wds` in `wds-routing.md` §6: real unblocking requires an
   interactive session, not just a written note). Include it in the next `write-snapshot
   --pending-json` so it surfaces in the Briefing, same mechanism as any other blocked item.
2. **When the owner is present**, in the SAME interactive session (never a sub-agent you spawned),
   load `bmad-agent-pm` (John) and pick the relevant menu item (`PRD` for a fresh plan; `CC` if the
   trigger was a recorded product decision needing revisiting) and conduct the plan with the owner —
   this is a real conversation, not a formality to rubber-stamp.
3. **Adversarial review of the plan, before implementing.** Once John's plan/PRD is drafted, run
   `bmad-review-adversarial-general` over the resulting plan **before dispatching execution** — this
   catches problems while they're still cheap to fix (the whole point of routing `spec`/`epic`
   through a real plan instead of straight to `rapida`-style execution). This step is not optional
   busywork even when the owner is eager to start.
4. **Decisions and research get resolved HERE, never mid-execution.** Anything requiring a decision
   or research (an ambiguous product behavior, an unclear technical approach, an unresolved
   trade-off) is settled during this planning phase — via the Oracle Protocol if it's squarely your
   call, or by asking the owner directly if it's part of John's interview — never deferred to "we'll
   figure it out once the Sonnet executor starts". A plan that ships with a known open question is
   not ready to dispatch.
5. **Brainstorm / market research / elicitation — judgment, not automatic.** `bmad-brainstorming`,
   `bmad-market-research`, and `bmad-advanced-elicitation` are **not** on John's own menu (`PRD`/`CE`/
   `IR`/`CC` only, per `bmad-agent-pm/customize.toml`) — they are separate skills. Before (or during)
   the PRD, assess whether the Ticket is genuinely under-explored: the problem itself isn't well
   understood, multiple viable directions exist, or this is exactly the kind of "reiterated problem"
   that justified escalating to `epic` in the first place. If so, **propose** running one of these
   first (to the owner, in-thread) — never run one reflexively on an obvious Ticket, but never skip
   it either when the problem is genuinely murky. This is a case-by-case call, not a fixed rule.
6. **Visual verification is already named in the plan** if the Ticket's affected area has a visible
   product surface — see `dispatch-and-review.md`'s "Visual-surface check" note (applies to every
   trilha, not just this one): the plan states up front how that surface will be checked (screenshot
   check vs. a full QA validation pass — QA validation is out of scope for this kit, install your
   own gate if you want one).
7. **Only once the plan is closed** (drafted + adversarially reviewed + open decisions resolved +
   visual-check named, when applicable) do you dispatch execution normally, through the standard
   disk-marker contract (`dispatch-contract.md`) — unchanged by this file: `spec` →
   `/bmad-create-story` then `/bmad-dev-story {story-file}`; `epic` → `/bagual-epic-runner {N}`
   (loaded via `Skill` in your own session — see `dispatch-and-review.md` § "Orchestration model for
   `epic`", not this file).

## Relationship to Planning Brain (E9.3) — not the same flow, don't conflate them

`planning-brain.md` fires when the **owner delegates an undefined, not-yet-broken-down effort
directly to you** — there, `bmad-prd` runs **headless** as a Sonnet sub-agent, because that skill
(unlike the `bmad-agent-pm` persona invoked here) tolerates headless PRD drafting; you then do
epic/story breakdown in-thread yourself. This file's rule fires **later** in the lifecycle: a Ticket
already exists on the board and gets classified `trilha: spec|epic` during "priorizar" — at that
point it's the **interactive John persona** (not the headless `bmad-prd` skill) who conducts the
plan, because the 2026-07-27 decision explicitly requires the owner's presence for this route. A
Ticket that emerged from Planning Brain's own breakdown still goes through this file's gate once it
reaches "despachar" with `trilha: spec|epic` — the two mechanisms are complementary, not
interchangeable substitutes for each other.

## Retirement of `classify_trilha.py` as trilha decider

`project_controll/tickets/scripts/classify_trilha.py` is **retired** as of TCK-20260727143826-7573
(decision: `wiki/ledger/decisao-tecnica/roteamento-de-trilha-e-plano-antes-da-execucao.md`). Live
board data showed its only two rules (confirmed bug → `rapida`, feature with confirmed design →
`wds`) funneled almost everything into `rapida` — `spec`/`epic` were **never** assigned
automatically, so real/substantial work kept landing in the light path unless a human remembered to
escalate it by hand. The trilha decision is now **always Gerente/owner judgment** (the criteria table
in `dispatch-and-review.md` + this file's gate for `spec`/`epic`) — never a script call.

**The file and its test are NOT deleted** (`classify_trilha.py`, `test_classify_trilha.py`) — kept
on disk for history; the owner may want to consult the old mechanical rules later. What actually
changed:

- `bagual-tickets/SKILL.md` § Resolve **no longer invokes it**. Every Ticket reaching
  `pronto-para-implementar` is now marked `escalonar: true` unconditionally (`trilha` stays `null`)
  — routing through the same `list-escalated` queue the Gerente already had for the ambiguous cases
  (`priorities-and-proactive-work.md` step 1). There is no longer a "committed automatically by the
  skill" lane distinct from "escalated" — everything is escalated now.
- `gerente_escalation.py` itself is **untouched** — still a valid mechanical primitive
  (`list-escalated`/`dead-letter-check`/`sample-decisions`/`orphan-sweep`); only its INPUT changes
  (100% of new Tickets flow through it now, instead of only the previous ambiguous remainder).
  `sample-decisions`/`record-sample-review` keep working exactly as before for the **historical**
  backlog (the 54 `rapida` tickets the retired script already auto-committed — see the ledger
  decision's "Consequences"). Re-triaging that historical backlog against the new 3-way criteria is a
  **separate, still-pending** action (item 7 of TCK-20260727143826-7573) — explicitly **not** done by
  this change; it stays with the Gerente to do together with the owner.
- No hook/cron/CI invoked `classify_trilha.py` directly outside `bagual-tickets/SKILL.md` — confirmed
  by a full-repo grep at the time of this change. Nothing else needed disabling.
