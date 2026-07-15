---
name: bagual-epic-runner
description: 'Epic pipeline: create-story → dev-story → [optional code-review] → retrospective. Full mode (with code review) is the default. Pass fast to skip review. Accepts a single epic or a set of epics (Story E10.1). Use when the user says "run quick epic {N}" or "quick pipeline epic {N}" or "implement epic {N}" or "implement epics {N} {M} ..."'
---

# Quick Epic Pipeline

## Overview

Supervises the execution of one or more epics end-to-end (Story E10.1, PRD 03 FR-1):
parses the requested epic set, resolves each epic's paths (including the E-prefixed
meta-system routing override), builds and persists an Execution Graph — grouping the
epics into Tracks, declaring paralela/sequencial per pair — **before** running any
story, then iterates the Tracks in series. The graph is a REAL disjunction computation
(Story E10.3, `scripts/compute_execution_graph.py`): a pair is `paralela` only if the
epics' declared areas AND the fixed shared-touchpoint set (`App.tsx`, `api/index.py`,
`package.json`/lockfile, `pyproject.toml`, migrations, process/knowledge files) are
both fully disjoint — missing declarations fail safe to `sequencial`. A declared
`depends_on` edge (Story E10.4) beats disjunction: it forces two epics `sequencial`
(same Track, ordered) even when their areas are fully disjoint, and each Track's
`epics` list is a deterministic topological sort of its `depends_on` edges (tie-break:
`--epics` invocation order). A dependency CYCLE anywhere in the requested set HALTs
the whole invocation before any story runs — no partial/guessed order, nothing written
to `sprint-status.yaml`. Track *iteration* stays series regardless of how many Tracks
the graph emits (genuine parallel Track execution is Epic E11, not implemented here) —
so a single epic behaves identically to before E10.1, and a set of epics still runs
each Track in series, in graph order.

Within each epic, the pipeline parses the sprint backlog and implements each story
through the create-story → dev-story pipeline sequentially (with optional
code-review loop), closing with a retrospective. The pipeline is a thin supervisor —
it reads story-processor instructions and executes them directly (no
subagent-to-subagent chains), spawning isolated agents for create-story, dev-story,
code-review, and quick-dev as directed. After all of an epic's stories are done, the
epic closes with a retrospective.

**Pipeline per story (fast):** create-story → dev-story → mark done → commit
**Pipeline per story (default/full):** create-story → dev-story → code-review (max 2 iterations, deferred findings batched at end) → mark done → commit
**Per epic, after all its stories:** batch-fix deferred findings (full mode only) → retrospective → mark epic done
**Per invocation, before any epic runs:** build + persist the Execution Graph (Tracks of epics, real disjunction incl. shared touchpoints — Story E10.3; dependency ordering + cycle-detection HALT — Story E10.4)

**Input:**
- One or more epic identifiers (e.g. `2`, or `2 3 5`, or `E10`). If omitted, auto-selects the first non-done epic from sprint-status.yaml (always a single product epic — meta-system epics are never auto-selected).
- Mode flag (optional): pass `fast` anywhere in the arguments to skip the code review loop for every epic in the set. Default is full (with review).

**Key rules:**
- Epics run ONE AT A TIME within a Track, and Tracks run ONE AT A TIME (in Execution-Graph order — real disjunction can now emit more than one Track, Story E10.3, but iteration stays series regardless) — stories within an epic are processed ONE AT A TIME, in order. Genuine parallel Track execution is Epic E11, out of scope here.
- The orchestrator reads story-processor instructions directly and executes them — no subagent-to-subagent chains
- If any story (or any epic) fails, only that epic's **Track** stops (Story E10.5, closes Epic E10) — it is marked `blocked` in the Execution Graph, a `bagual-tickets` Ticket is left with `escalonar: true` + a `## Log` reason, and a Briefing entry is recorded; the supervisor run itself is NOT halted and healthy sibling Tracks keep going. The only HALT that still aborts the entire invocation is a `depends_on` cycle detected while building the graph (Story E10.4, a planning error caught before any story runs). The final report is "K of N epics done; {blocked list} — reason", never a total "pipeline halted".
- The orchestrator never implements code directly — it spawns agents for create-story, dev-story, code-review

**Config dependency:** Requires `_bmad/bmm/config.yaml` (BMad Method Module).

## On Activation

Load config from `{project-root}/_bmad/bmm/config.yaml`. Follow all instructions in `workflow.md` (in this skill's own directory — not under `references/`).
