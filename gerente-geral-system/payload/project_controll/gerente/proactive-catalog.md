---
title: Gerente Geral proactive work catalog — empty queue
tipo: reference
created: 2026-07-11
status: living-document
source_prd: "ideias/prd-00-sistema-orquestrador.md — FR-3, UJ-4"
source_epic: "ideias/epics.md — Epic E8, Story E8.5"
source_story: "ideias/sistema-artifacts/E8-5-trabalho-proativo.md"
extends: ".claude/agents/gerente-geral.md"
---

# Proactive work catalog — empty queue

## What this document is

When the Gerente Geral (`.claude/agents/gerente-geral.md`) wakes up and `project_controll/tickets/board.yaml`
has no ticket in `pronto-para-implementar`, it doesn't sit idle — but it also doesn't
invent arbitrary work. This is the **restricted catalog** (PRD 00 FR-3) of **very-low-risk**
proactive tasks the Gerente can pick from at that moment. It is deliberately restricted:
every category below is **read-only/investigation** — it never generates a directly
committed code change. Every finding turns into a **traceable Ticket**
(`origem: proativo`), never a silent fix.

Rotation/cap/dedup mechanics: see `project_controll/gerente/scripts/gerente_proactive.py`
(`next-task`/`dedup-check`/`record-proactive`) and phase 2 (prioritize) of
`.claude/agents/gerente-geral.md`. This document is only the catalog's **content** — the
mechanics of "how many times per cycle" and "how to avoid rediscovering the same finding" live in the
scripts, not here.

## Golden rule — never commit code, only investigate and report

Every task in this catalog is dispatched as a **read-only Sonnet sub-agent**: it
can use read-only `Read`/`Grep`/`Glob`/`Bash` (e.g., `git log`, `grep`, running the existing
test suite to measure coverage), but **never** `Edit`/`Write` over product code
(`frontend/**`, `backend/**`, `supabase/**`) nor over `bmad-*`/`bagual-*` skills.
The only accepted output artifact is a **findings report** (a list of findings, each
with a short title + description + `file:line` evidence when applicable) — never a
diff. The Gerente takes that report and, for each finding, runs the dedup flow +
`bagual-tickets --headless` (see "How a finding becomes a Ticket" below) — the analysis
sub-agent itself never calls `bagual-tickets` nor writes to `project_controll/tickets/`
directly (this avoids a second concurrent writer to the board).

No category below authorizes deciding an ambiguous product/behavior question —
if the investigation runs into one (e.g., "this looks like a bug, but it might be intentional
per `product-decisions.md`"), the finding still becomes a Ticket, but with `category: duvida` and
the suspicion recorded — never a fix proposed as a certainty.

## Categories (minimum 4, PRD 00 FR-3)

Round-robin rotation among the 4 (`gerente_proactive.py next-task` decides the order — the list
below is the source of truth for each one's CONTENT/guardrails; the rotation order itself is
an implementation detail of the script, not of this doc).

### 1. `analise-adversarial-feature` — Adversarial analysis of a feature

Pick **one** `[CLIENT]` feature already in production (see `AGENTS.md` § "Template features vs
Client features" — never a `[TEMPLATE]` feature, which is maintained upstream) that hasn't
been adversarially reviewed recently (check `_bmad-output/projects-history.md`
for the last mention). Read the feature's source code (not just the spec) and look
for real bugs: unhandled edge cases, missing validation, inconsistent state — the same
kind of finding `/bmad-code-review` (Blind Hunter/Edge Case Hunter) already produces for
recently changed code, here applied to code that's **already stable**, with no recent diff to
anchor to. Every real bug confirmed in the code (never hypothetical — cite `file:line`)
becomes a `category: bug` finding.

### 2. `completude-de-testes` — Increasing test completeness

Pick a module/feature with signs of weak coverage (e.g., `grep` for code files
with no matching test file, or a critical flow — payment, IDOR,
state transition — with no test exercising it). The finding is not "write the test" (that
would be code) — it's a `category: chore` Ticket describing the gap ("function X in
`arquivo.py` has no test covering branch Y") for a normal track
(`/bmad-quick-dev` or `/bmad-testarch-*`) to close later.

### 3. `descoberta-de-padroes` — Discovery of patterns to consolidate

Scan `_bmad-output/anti-patterns.md`/`decisions.md` and the source code for
a pattern that repeats **≥2 times** consistently but hasn't been consolidated yet (e.g.,
the same validation logic copied in 2+ places, a utility candidate for extraction). The
finding becomes a `category: chore` Ticket proposing the consolidation — never the consolidation itself.

### 4. `refino-de-tickets` — Refining poorly elucidated tickets

Re-read tickets in `precisa-de-info` or `triado` with a shallow description in
`project_controll/tickets/board.yaml`. Investigate the related code to fill in the
gap (confirm whether the bug exists, find `file:line`, check whether it matches an
already-recorded product decision). **This is the only case in the catalog that doesn't necessarily
create a NEW Ticket** — the result is normally to enrich the already-existing Ticket via
`bagual-tickets`'s "Triage" action (move to `triado`, fill in `## Verificação`), the same
composition as the others. If the investigation reveals the old ticket is actually two
distinct problems, then it can generate an additional new Ticket (`origem: proativo`) — but
the common case is enriching, not duplicating.

## How a finding becomes a Ticket (composition — never reimplemented here)

For each finding in the analysis sub-agent's report:

1. `python3 project_controll/gerente/scripts/gerente_proactive.py dedup-check --root
   project_controll/gerente --tickets-dir project_controll/tickets --title "<finding
   title>" --description "<finding description>"` — scans the **full proactive
   history**, including `concluido`/`descartado` (the dimension `bagual-tickets` alone
   doesn't cover — it only dedups against open tickets, see `SKILL.md` § Adicionar, step 2).
2. If `"duplicate": true` — **do not create the Ticket**; record in the cycle's diary
   (`gerente_state.py append-diario`) that the finding is already known (point to the
   `best_match.ticket_id`). This is exactly the behavior F24 requires: never
   re-file the same findings every night.
3. If `"duplicate": false` — invoke the `bagual-tickets` skill in `--headless` mode for
   **Adicionar** (or, for category 4, **Triar**/**Resolver** on the
   existing ticket) — the skill runs its own full pipeline (raw-check, dedup against
   OPEN tickets, `product-decisions.md` check, verification/expansion) on its
   own; don't skip or reimplement those steps here. In headless mode, a new ticket is
   born `origem: proativo` by default (see `SKILL.md` § Headless Mode) — there's no need
   to pass the field explicitly.
4. After processing ALL findings from one catalog iteration, call
   `gerente_proactive.py record-proactive` **exactly once** (consumes 1 unit of the
   per-cycle cap — see below, "Cost unit").

## Hard per-cycle cap (F24) — what counts as 1 unit

`cap_per_cycle` (configurable in `project_controll/gerente/proactive.config.json`,
default 3) limits how many **catalog iterations** (not how many Tickets) the Gerente runs
per cycle — one iteration is "pick a category (`next-task`) → dispatch ONE analysis
Sonnet sub-agent → process its findings (dedup + Ticket, 0 to N possible findings) →
`record-proactive` once". The real cost unit is the **analysis sub-agent
dispatch** (what burns quota), not the number of Tickets it produces — an analysis that
finds nothing has still consumed a dispatch and counts as 1 unit just like one that
found 3 bugs. On reaching the cap, `next-task` returns `"verdict": "cap-reached"` — the
Gerente stops proactive work and moves to the cycle's "stop" phase (reporting "stopped
due to proactive cap", not "stopped due to quota" — these are distinct guardrails).
