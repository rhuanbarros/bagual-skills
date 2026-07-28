---
title: "Product routing (E9.6) — operational definition of 'product change' + 3 routes"
tipo: reference
created: 2026-07-12
status: living-document
source_prd: "ideias/prd-05-wds.md — FR-1/FR-1b (§4.1)"
source_epic: "ideias/epics.md — Epic E9"
source_story: "ideias/sistema-artifacts/E9-6-roteamento-produto.md"
---

# Product routing (E9.6)

Canonical contract for the sub-protocol `.claude/skills/bagual-gerente-geral/SKILL.md` invokes
inside the "prioritize" phase (`references/priorities-and-proactive-work.md` §
"Escalated decisions + reconciliation (E9.5)") — for EACH escalated
ticket, before/alongside deciding the `trilha` via the Oracle Protocol (E9.1), the Gerente
decides **whether the ticket changes the product** and, if so, **through which of the 3
routes**. Read this document in full before the first time this sub-step triggers.

This document is **prose/judgment**, not mechanics — the only mechanized component is the
Coverage Matrix touch detector (`gerente_product_routing.py`, see §5). The decision
itself (does it change or not? which route?) never gets a fixed heuristic, same discipline as
"confidence gate never by feel" (E9.1) and "promotion to the Ledger is judgment" (E9.5)
— here, "classify changes-product/doesn't-change-product" and "pick the route" are the judgment.

## 1. The documented product truth (the test's anchor)

A ticket **changes the product** if it would leave any of the three canonical
documents that spec-time grounding derives from out of date:

| Document | Path | What it anchors |
|---|---|---|
| Trigger Map | `_bmad-output/B-Trigger-Map/trigger-map.md` | Business goals → personas → forces → desired behavior changes |
| Coverage Matrix / UX Scenarios | `_bmad-output/C-UX-Scenarios/00-ux-scenarios.md` | Scenarios → pages/screens → the purpose of each journey |
| Product decisions | `_bmad-output/product-decisions.md` | Already decided/confirmed behavior rules, with "Cuidado:" marking what is intentional |

Never use any other source as "product truth" for this test (not the code
itself, not the opinion of the sub-agent that triaged the ticket) — only these three, and
only what would go out of date **in them** is what counts.

## 2. The 3-question test (any YES ⇒ changes the product)

1. **Does observable behavior/rule change?** New capability, different business
   rule, new validation, a step added/removed in the flow.
2. **Does the flow/navigation change?** Adds/removes/reorders a screen, route, or journey step.
3. **Does a visible surface with product meaning change?** New field, new state,
   text that carries a rule (not purely cosmetic).

A behavior change **with no UI at all** (e.g., "proposals can be reopened
after being declined") is already a YES on question 1 — the trigger is product, not interface.

## 3. Hard exclusions (NOs — do not route, even if they look like a change)

- **Refactor with identical behavior** (same input → same output, only the
  code changes).
- **Performance with no observable behavior change.**
- **Bugfix that RESTORES already-documented behavior** — the doc is already right, the
  code was wrong. *Exception within the exception:* if the bugfix reveals that the
  **document** was wrong/ambiguous (the documented "correct" behavior isn't what the
  product should actually do), then ROUTE — because now it's the doc that needs to change.
- **Purely cosmetic** (spacing/color) that no scenario asserts as a rule.
- **Infra/tooling/test-only** (nothing visible to a user/stakeholder).

## 4. Safety bias — when in doubt, ROUTE

**A false negative is worse than a false positive.** If a product change slips past
routing, the doc goes stale and spec-time grounding (which derives from it) goes
**blind** — whoever consumes those docs won't even know it should check the new
behavior. A false positive costs
wasted effort (routed for nothing), but the doc stays correct.

So: **when in genuine doubt, route** — bounded by §3's hard exclusions (which
prevent "route everything out of caution"). Genuine doubt is not laziness about applying
the test — it's having applied the 3 questions + the exclusions and still not being able
to decide with confidence.

## 5. Hard rule — touching the Coverage Matrix ALWAYS forces route (i)

**This is not fine judgment, it's a hard test, no exception (PRD 05 FR-1b, "hardened —
F19"):** if the ticket touches a scenario/page listed in the Coverage Matrix
(`_bmad-output/C-UX-Scenarios/00-ux-scenarios.md`), the route is **always (i)** — never (ii).

**Why this is mechanical and not fine-grained:** route (ii) (recording the change as a
`decisao-de-produto` Ledger entry) is **contractually read-only for design truth** — it
only creates a Ledger entry, never rewrites `scenarios`/the Coverage Matrix. If a ticket touches a scenario
and you tried to route it via (ii) anyway, the Coverage Matrix would go stale by
CONSTRUCTION — route (ii) has no way to fix it. That's why the boundary is mechanical:
touched a page/scenario ⇒ route (i), always, with no "but it's a small change" escape hatch.

**Mechanical detector (a signal, not a decision-maker):**
```
python3 project_controll/gerente/scripts/gerente_product_routing.py check-coverage-touch \
  --touched "<comma-separated terms — pages/area of the ticket>"
```
Read `area`/`## Locais afetados`/the ticket's description to extract the terms (pages,
screens, named flows). `forced_route_i: true` (some `matches`) mechanically forces
route (i) — there is no room for judgment here, it is exactly this section's rule.
**`forced_route_i: false` does NOT prove there is no touch** — it's only the absence of
a textual match (the ticket might describe the same page with a different name than the
Coverage Matrix's, or be a behavior change with no new page — question 1 of the 3-
question test). A negative from the detector **never** excuses skipping the judgment-
based 3-question test before concluding "doesn't change the product" (route iii) — the
detector only fast-tracks the easy case (a mechanical positive), it never decides the hard case.

## 6. The 3 routes

| # | Situation | Action | Produces |
|---|---|---|---|
| **(i)** | Changes the product **and** needs design (new capability, new/changed scenario, flow redesign) **OR** touches a Coverage Matrix page/scenario (hard rule, §5) | `trilha: wds` on the ticket (Pass `wds-8`, real execution is E9.8 — here, only the routing) | Updates `scenarios` + `trigger-map` (when the Pass runs) |
| **(ii)** | Changes the product but is a **small, already-decided rule** (no design, no Coverage Matrix touch — just record the rule) | Records the change as a `decisao-de-produto` Ledger entry (`wiki/ledger/decisao-de-produto/`, composition §7) — **orthogonal to `trilha`**, not an enum value | A `decisao-de-produto` Ledger entry |
| **(iii)** | **Does not** change the product (no §2 question is YES, or it falls into a §3 hard exclusion) | No document maintenance | — |

**Route (i) uses the ticket's `trilha`** — it's the same field the Oracle Protocol
(E9.1) already decides for dispatch (`rapida\|spec\|epic\|wds\|correct-course`); when route
(i) applies, the trilha decision IS `wds` (it's not a second, parallel decision — this
section's classification **is** the reason the trilha is `wds`).

**Route (ii) is orthogonal** — the ticket's `trilha` keeps being decided normally
by the Oracle Protocol (it can be `rapida`/`spec`/`epic`, whatever the work's REAL nature
calls for), and recording the `decisao-de-produto` Ledger entry happens as an ADDITIONAL
ACTION, "riding along" — never competing with the chosen trilha.

**Route (iii)** changes nothing in this sub-protocol — the trilha keeps being decided
normally, with no document-maintenance action.

## 7. Combined case — route (i) DOMINATES + enrich as a side effect

A change that touches **both** a scenario/page (§5) **and** hits/updates a decision
already recorded in `product-decisions.md` never triggers both routes in disorderly
parallel. **Route (i) dominates**: `trilha: wds` is the routing decision. The
`product-decisions.md` enrich (what route (ii) would do) happens as a **side effect**
of the same ticket — not as a second, independent route, but as part of the same Pass
(when `wds-8` runs — E9.8) or, if the rule itself is already clear before the Pass, as an
additional "log change" trigger ALONGSIDE the `trilha: wds` marking (never
REPLACING it). The point is: **never conclude (ii) alone when (i) also applies**
— the Coverage Matrix never ends up orphaned of an update it needed.

## 8. Composition — none of this is reimplemented

- **Pass `wds-8`** (route i): composed as a sub-agent. The real execution (`wds-8` doesn't
  run headless — in-thread oracle OR wait on the owner) is **E9.8**'s scope, not this
  story/protocol's. Here, the classification's result is just `trilha: wds` written on
  the ticket via `bagual-tickets` — the same commit mechanism E9.5 already uses.
- **Record the product change as a `decisao-de-produto` Ledger entry** (route ii):
  record the change as a `decisao-de-produto` Ledger entry in
  `wiki/ledger/decisao-de-produto/` (via the `on_complete` contract,
  `wiki/ledger/on-complete-contract.md`), capturing what changed (before→after), where
  (pages/routes, if determinable), why (the ticket's justification) and whether it's
  bug-or-not (the old behavior becomes a bug if it reappears, or it's just an additive
  difference). On completion, record the path of the produced Ledger entry in the
  ticket's `## Log`. *(QA-builder-based logging was removed from this kit — route (ii)
  now registers directly in the Ledger.)*
  - **A composition boundary, not a new marker dispatch.** Unlike the ticket's primary
    dispatch (`gerente_dispatch.py open-dispatch`/`close-dispatch`,
    E8.4 — which exists to survive context compaction/a crash over the ticket's MAIN
    work), this is a lightweight, IDEMPOTENT write: if the
    session dies before the Ledger entry is written, the next cycle
    simply re-detects the same ticket (if still escalated/without the `## Log` note)
    and tries again — there is no dangerous partial state to reconcile (the Ledger
    entry is only written once, at the end, never left half-done).
    That's why we deliberately **don't** use E8.4's on-disk marker contract
    for this secondary action — see the story's Review Findings for the documented
    trade-off.
- **Coverage Matrix detector** (`gerente_product_routing.py`, §5): mechanizes only the
  objective sub-question "does the text match a page?" — it never decides the
  changes/doesn't-change classification alone nor chooses between (ii)/(iii).

## 9. Boundary with `bagual-tickets` triage (the detector vs. the classifier)

`bagual-tickets` (Triage, `.claude/skills/bagual-tickets/SKILL.md` § "Product decision
check") already reads `product-decisions.md` and flags whether the request matches
something marked as intentional — that is the **detector**: "this might touch the
product/collide with a recorded decision". This protocol (E9.6) is the **classification +
the routing**: given that signal (or even in its absence, applying the 3-question test
on its own), it decides WHETHER it changes the product and BY WHICH route. They never
overlap — the skill doesn't choose a route, the Gerente doesn't reimplement the
`product-decisions.md` check the skill already does at triage.

## 10. Worked examples

See `ideias/sistema-artifacts/E9-6-roteamento-produto.md` § Validação for the 4
complete cases (Coverage Matrix touch → i; small, already-decided rule → ii; refactor/
cosmetic → iii; combined case → i dominates + enrich) run for real against the
detector and the actual product document.
