---
name: bagual-tickets
description: 'Logs, triages, and tracks ad-hoc bug/request tickets as a lightweight board. Use when the user says "criar ticket", "novo ticket", "ver o board de tickets", "triar tickets", "resolver ticket [id]", or asks to record a bug/request for later instead of fixing it right away.'
---

# bagual-tickets

Talk to the user in `communication_language` (from `{project-root}/_bmad/config.yaml` / `config.user.yaml`, default Portuguese); this skill's artifacts are English regardless of `document_output_language`.

## Overview

This skill logs, triages, and tracks bug and ad-hoc request tickets for this project as a lightweight kanban board, in `{project-root}/project_controll/tickets/`. When adding a ticket, it checks whether it's minimally clear, whether it isn't a duplicate of one already open, whether it doesn't contradict an already-recorded product decision, and — for bugs — whether the problem actually exists in the code and whether the same pattern shows up elsewhere in the project (expanding the ticket instead of creating duplicates). Beyond that, it's just board + triage + status changes. **It does not produce a spec or do requirements elicitation** — that's the job of `/bmad-quick-dev`, `/bmad-spec`, or the WDS skills; this skill recommends which one to call once a ticket is ready for implementation.

`Ticket` is a first-class Document-type of the Wiki (`wiki/document-types.md` § `ticket`) — `board.yaml` is the native index of this subtree, referenced directly from the Wiki's root index (`wiki/index.md`), with no separate `index.md`. `project_controll/tickets/` remains the sole physical location of tickets (outside the `wiki/` tree — a decision already made).

## On Activation

Load available config from `{project-root}/_bmad/config.yaml` and `{project-root}/_bmad/config.user.yaml` if present. Use sensible defaults for anything not configured. Write ticket content in Portuguese, regardless of what the config says — that's the language actually used in `_bmad-output/` in this project.

`{tickets_dir}` = `{project-root}/project_controll/tickets/`
`{board_file}` = `{tickets_dir}/board.yaml`

If `{tickets_dir}` doesn't exist, create it on the first action that needs to write something.

## Dispatch

From the user's request, identify the action: **Add**, **Board**, **Triage**, or **Resolve**. If the invocation is explicit but the action isn't clear (e.g. `/bagual-tickets` on its own), show a short menu with these four options and wait for the choice.

## Add

0. **Fast-path for trivial items (F22).** Before anything else, assess whether the request is **trivial**: cosmetic or obviously correct (e.g. swap a color/text/spacing, an obvious value tweak, a typo fix) — nothing that requires confirming behavior in the code or investigating impact. If trivial: skip steps 2-4 below (dedup against open tickets, checking `product-decisions.md`, the `file:line` verification, and the sibling search) and go straight to step 5 with a **minimal record**: the request's description + a `## Log` note stating `fast-path trivial — verification/dedup skipped`. Any real `bug`/`feature` (anything requiring code confirmation or with non-obvious impact) **always** goes through the full pipeline below — the lightweight path is exclusive to trivial items, never an excuse to skip verifying a real bug. When in doubt between trivial and real, treat it as real (the heavy pipeline is the default; the fast-path is the assumed exception).
1. **Raw-check.** A ticket is only accepted with the bare minimum: what (the problem or request, even informally stated) and roughly where (screen/component/flow). If missing, ask 1-2 direct questions — it's not a spec, just enough to route it. In headless mode, don't ask: fill in whatever the received payload allows and log every assumption in the ticket's `## Log`. Runs even on the fast-path — it's the only step trivial items don't skip.
2. **Duplication** (outside the fast-path). Compare against the tickets still open in `{board_file}` (status other than `concluido`/`descartado`). If there's plausible overlap, offer to merge the information into the existing ticket instead of creating a new one.
3. **Product-decision check** (outside the fast-path). Read `{project-root}/_bmad-output/product-decisions.md`, especially the `**Cuidado:**` lines. If the reported problem matches something marked there as intentional, warn the user before proceeding — this may be a decided behavior, not a bug.
4. **Verification and expansion** (category `bug`, outside the fast-path). Confirm in the code that the problem is real — cite `file:line` as evidence. Then search for the same pattern elsewhere in the project (e.g. the same component reused in other features). If more occurrences are found, fold them all into the same ticket, marking `expanded: true` and listing the locations — don't create one ticket per location.
5. Save the ticket (see Storage) with initial status `novo` or `precisa-de-info`, and update `{board_file}`. A trivial fast-path item still becomes a trackable ticket — "everything is trackable" still holds, only the verification toll disappears.

## Triage

For a ticket in `novo` or `precisa-de-info`: fill in category (`bug`/`feature`/`chore`/`duvida`), affected area, and suggest priority `alta`/`media`/`baixa` — heuristic: does it break a critical product flow vs. is it cosmetic, how many locations the expansion found, whether it's blocking other work. The user can override the suggestion.

**`visivel_pro_cliente` flag (F21).** Category `bug`/`feature`: ask the user whether resolving this ticket should appear in the client's changelog (interactive mode). Category `chore`/`duvida`: `visivel_pro_cliente: false` by default, without asking (an internal change is rarely client-facing news) — the user can override. **In headless mode, `bug`/`feature` never defaults to `false`:** record `visivel_pro_cliente: pendente` (sentinel) + log the applied heuristic in `## Log` (user-facing bug/feature → candidate for `true`, but unconfirmed) — resolving the `pendente` before any changelog is the librarian's/Gerente's job (PRD 01 FR-12), never this skill deciding `true` out of optimism. `chore`/`duvida` in headless mode go straight to `false`, no sentinel — the heuristic is already safe enough for those.

The `trilha` field stays `null` at the end of this step — Triage only sets category/area/priority. The `trilha` decision always happens downstream, by Gerente/owner judgment, on the transition to `pronto-para-implementar` (see "Trilha escalation" under Resolve) — this step never decides `trilha` on its own.

**Design signal for the `feature` category.** While still in Triage, if it becomes **unambiguous** that the resolution requires a new screen/visual component (not just logic/data) — e.g. the request itself already describes a new screen, a new visual flow — record `design_confirmado: true` in the front-matter. This is a strong signal feeding the Gerente's downstream `trilha`/product-routing judgment (route (i) → `wds`, see `dispatch-and-review.md`) — never set `true` on assumption/plausibility; when in doubt, leave the default (`false`, the field can be absent). Category `bug`/`chore`/`duvida` never fills this field.

Once triage is done with verification complete, move the status to `triado`.

## Board

Read `{board_file}` and present the tickets grouped by status (`novo`, `precisa-de-info`, `triado`, `pronto-para-implementar`, `em-implementacao`, `concluido`, `duplicado`, `descartado`), ordered by priority within each group.

## Resolve

Update a ticket's status (by id or description).

**Trilha escalation — 🔴 retired mechanical classifier (TCK-20260727143826-7573, 2026-07-27).**
`project_controll/tickets/scripts/classify_trilha.py` is **no longer invoked here** (or anywhere in
the dispatch flow) as a `trilha` decider — see
`wiki/ledger/decisao-tecnica/roteamento-de-trilha-e-plano-antes-da-execucao.md` for the full
rationale (its 2 narrow regex-shaped rules funneled almost everything into `rapida` and never
assigned `spec`/`epic` automatically). **The file and its test are NOT deleted** — kept for history
— they're just off the hot path. This skill **never decides `trilha` itself anymore, for any
category**: when moving a ticket to `pronto-para-implementar`, always record `trilha: null` +
`escalonar: true` in the front-matter **and** in `board.yaml` (the index field — the Gerente scans
escalated tickets in a single read, without opening each `.md`), with a `## Log` note stating
"trilha decision deferred to Gerente/owner judgment (classify_trilha.py retired,
TCK-20260727143826-7573)". This is the same `escalonar: true` state the ambiguous cases already used
— now it's simply the state for 100% of tickets, not a subset. There is no other write here: no
guessing, no partial commit, no round-trip to a pricier model, and never invoking any implementation
skill (whoever triggers the work is always the Gerente or the owner, never this skill as a side
effect).

The trilha is decided downstream, by judgment, using the criteria table and John-first gate in
`.claude/skills/bagual-gerente-geral/references/dispatch-and-review.md` (phase "priorizar"/
"despachar") — this skill has no opinion on `rapida` vs `spec` vs `epic` vs `wds` vs
`correct-course`, it only routes the ticket into that queue.

After marking it escalated, **do not recommend a specific follow-up skill** — the trilha isn't known
yet at this point. Note in `## Log` only that the ticket awaits a trilha decision from the Gerente
(`list-escalated`/Oracle Protocol) or the owner.

When moving to `duplicado`, record `duplicate_of` pointing at the canonical ticket.

**Closure with commit trail — non-blocking (F4).** When moving a ticket to `concluido`: if related commit(s) already exist — reported by whoever called Resolve, or found by searching the repository history for the ticket id (e.g. `git log --oneline -i --grep="<ticket-id>"`) — record the hash(es) in a `## Fechamento` section in the ticket file body: one hash per line, a plain list, no per-commit summary (the summary already lives in the description/`## Log`). If no commit exists or is found, the transition to `concluido` happens normally, **without** a `## Fechamento` section — its absence never blocks closure (solo work directly on the branch, no PR). When moving to `descartado`, never record a commit — only the reason in `## Log`.

Outside the commit trail above, when moving to `concluido`/`descartado` leave the ticket as-is — don't delete files.

## Storage

`{board_file}` — a **derived** index: the source of truth is the per-ticket `.md` files (below), not `board.yaml`. If the index is lost/corrupted, `board.yaml` is **reconstructible** by running `project_controll/tickets/scripts/rebuild_board.py` (stdlib, see Board Reconstruction below) — no real data is ever trapped only in the index.

```yaml
tickets:
  TCK-001:
    title: "..."
    status: novo
    priority: alta
    category: bug
    area: clients
    expanded: false
    created: 2026-07-07
    updated: 2026-07-07
    origem: manual
    visivel_pro_cliente: false
    trilha: null
    escalonar: false
    ledger_refs: []
  TCK-20260711143512-9f2a:
    title: "..."
    status: novo
    priority: media
    category: feature
    area: proposals
    expanded: false
    created: 2026-07-11
    updated: 2026-07-11
    origem: proativo
    visivel_pro_cliente: pendente
    trilha: null
    escalonar: false
    ledger_refs: []
  TCK-20260711150000-a1b2:
    title: "..."
    status: pronto-para-implementar
    priority: alta
    category: bug
    area: proposals
    expanded: false
    created: 2026-07-11
    updated: 2026-07-11
    origem: manual
    visivel_pro_cliente: false
    trilha: rapida
    escalonar: false
    ledger_refs: []
  TCK-20260711150500-c3d4:
    title: "..."
    status: pronto-para-implementar
    priority: media
    category: feature
    area: simulation
    expanded: false
    created: 2026-07-11
    updated: 2026-07-11
    origem: manual
    visivel_pro_cliente: false
    trilha: null
    escalonar: true   # ambiguous — Gerente/Oracle (E9.5) or the owner decides; the skill never guesses
    ledger_refs: []
```

`next_id` (the legacy sequential counter for the oldest `TCK-NNN` tickets) **is no longer used to generate new ids** — new ids use the collision-free scheme below. The field may keep appearing in `board.yaml` for compatibility (e.g. generated by the reconstruction script), but never read it or increment it to decide the next id.

`{tickets_dir}/TCK-<id>-slug.md` — one file per ticket:

```markdown
---
id: TCK-001
title: "..."
status: novo
priority: alta
category: bug
area: clients
expanded: false
created: 2026-07-07
updated: 2026-07-07
origem: manual              # manual | proativo — default manual (headless defaults to proativo, see Headless Mode)
visivel_pro_cliente: false  # false | true | "pendente" — default false (see Triage)
trilha: null                 # rapida | spec | epic | wds | correct-course | null — always decided by the Gerente/owner on escalated tickets (see Resolve § Trilha escalation); this skill never commits it itself
escalonar: false             # true once the ticket reaches pronto-para-implementar (every ticket is escalated now — see Resolve) — default false
design_confirmado: false     # only relevant for category:feature — true only once the need for design (new screen/component) is already unambiguous at Triage (see Triage); never inferred, always defaults to false
ledger_refs: []               # list of Ledger Entry paths promoted from this ticket (e.g. ledger/decisao-tecnica/foo.md)
---

## Descrição
(original report)

## Verificação
- Confirmado: sim | não | não verificado
- Evidência: file:line

## Locais afetados
(only if expanded: true — list of the other spots with the same pattern)

## Checagem de decisão de produto
(nenhum conflito encontrado, ou referência à entrada de product-decisions.md em conflito)

## Fechamento
(only when a commit exists at closing time — see Resolve; a plain list of hashes, one per line; absent when the resolution didn't involve code)

## Log
- 2026-07-07: created
```

`created`/`updated` in the `.md` front-matter (new as of this version, F9) are what lets `board.yaml` be reconstructible without depending solely on the index — always record them when creating/updating a ticket from now on.

**Backward compatibility (F9).** The 26 pre-existing `TCK-001`..`TCK-026` tickets have no `origem`/`visivel_pro_cliente`/`trilha`/`escalonar`/`design_confirmado`/`ledger_refs`/`created`/`updated`/`## Fechamento` in the `.md`  — treat the absence as `origem: manual`, `visivel_pro_cliente: false`, `trilha: null`, `escalonar: false`, `design_confirmado: false`, `ledger_refs: []`, with no `## Fechamento`; missing `created`/`updated` fall back to the file's modification date. **None of these 26 tickets needs to be edited/migrated** — the new fields only start being written on tickets created or re-closed from now on. No new field is required at creation. `escalonar` defaulting to `false` on a legacy ticket is never read as "not escalated, automated decision confirmed" — it's only "this story didn't exist yet when the ticket was resolved"; don't reopen or reclassify the 26 retroactively.

**Id generation — collision-free (F9).** Don't read/increment a shared counter anymore (`next_id` read-then-written by two parallel `create`s is a classic TOCTOU race: both read the same value, one of the two ids disappears). Generate the new id as `TCK-<compact UTC timestamp>-<short random suffix>`, e.g. `TCK-20260711143512-9f2a` — via `date -u +%Y%m%d%H%M%S` combined with a short hex suffix, or in a single command:

```
python3 -c "import secrets,datetime;print('TCK-'+datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')+'-'+secrets.token_hex(2))"
```

A second-resolution timestamp plus a random suffix never collides, even in batch creation (headless, see E5.6) — no need to re-read `{board_file}` to decide the next id. Old sequential `TCK-NNN` ids remain valid forever; the new scheme only applies to tickets created from this version onward.

**Board reconstruction (F9).** `{board_file}` is a derived index; the per-ticket `.md` files are the source of truth. To rebuild it from scratch (lost/corrupted index, or just to audit consistency):

```
python3 project_controll/tickets/scripts/rebuild_board.py --tickets-dir project_controll/tickets --out project_controll/tickets/board.yaml
```

The script is pure stdlib, only reads the `.md` files, never reads `{board_file}` itself, and writes atomically (temp + fsync + rename). Use `--dry-run` to check the result without writing, and `--json` for machine-readable output. The `escalonar` field (E9.4) is loaded into the index the same way as the other additive fields — reconstructible from the `.md` front-matter, defaulting to `false` when absent.

## Headless Mode

When invoked with `--headless`/`-H`: skip every confirmation (log the assumption made in the ticket's `## Log` instead of asking) and return only JSON, no prose.

**Origin and batch creation (F9/E5.6).** A ticket created in headless mode gets `origem: proativo` by default — unless the input payload explicitly declares `origem: manual` (e.g. a batch import of items the owner already wrote elsewhere, pasted in via automation). A sub-agent/Gerente that finds N issues materializes N tickets by invoking this skill N times by composition, one finding per call — each call runs the full Add flow normally (raw-check/fast-path, dedup, product check, verification), just without interactive questions; **never** reimplement dedup/raw-check/product-decision-check outside this skill to "go faster" in batch. Ids from batch calls never collide (collision-free scheme, see Storage). No finding from proactive work ever turns into a silent fix — it always becomes a trackable ticket first.

```json
{
  "status": "complete",
  "action": "add | board | triage | resolve",
  "ticket_id": "TCK-001",
  "path": "{tickets_dir}/TCK-001-slug.md",
  "board_path": "{board_file}"
}
```

On a block (e.g. raw-check failed and there isn't enough payload to infer from), swap `"complete"` for `"blocked"` and add `"reason"`.
