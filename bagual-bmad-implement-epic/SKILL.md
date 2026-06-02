---
name: bagual-bmad-implement-epic
description: 'Full epic pipeline with up to 5 review iterations per story. Use when the user says "run epic pipeline {epic-number}" or "pipeline epic {N}" or "run the epic"'
---

# Epic Pipeline

## Conventions
- Bare paths (e.g. `references/workflow.md`) resolve from the skill root.
- `{skill-root}` resolves to this skill's installed directory.
- `{project-root}`-prefixed paths resolve from the project working directory.

## Overview

Orchestrates an entire epic end-to-end: parses the sprint backlog, implements each story through the create-story → dev-story → code-review pipeline sequentially, and closes with a retrospective. Each story goes through up to 5 review correction iterations before the pipeline HALTs — no deferred findings.

**Pipeline per story:** create-story → dev-story → code-review (up to 5 iterations; HALTs if still failing)
**After all stories:** retrospective → mark epic done

**Input:** Epic number required (e.g., `2`).

**Key rules:**
- Stories processed ONE AT A TIME, in order — never parallelized
- Each sub-skill runs in its own isolated subagent
- Pipeline HALTs if any story fails after 5 review iterations
- Pipeline is idempotent — re-run after fixing a HALT to resume from the failed story

**Config dependency:** Requires `_bmad/bmm/config.yaml` (BMad Method Module).

## On Activation

Load config from `{project-root}/_bmad/bmm/config.yaml`. Follow all instructions in `references/workflow.md`.
