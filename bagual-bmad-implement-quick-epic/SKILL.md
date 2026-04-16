---
name: bagual-bmad-implement-quick-epic
description: 'Faster epic pipeline: create-story → dev-story → code-review (max 2 loops, deferred findings batched at end via bmad-quick-dev) → test pipeline (HIGH coverage, soft-fail) → retrospective. Use when the user says "run quick epic {N}" or "quick pipeline epic {N}"'
---

# Quick Epic Pipeline

## Overview

Orchestrates an entire epic end-to-end: parses the sprint backlog, implements each story through the create-story → dev-story → code-review pipeline sequentially, runs the full test suite after all stories are done, and closes with a retrospective. The pipeline is a thin orchestrator — it reads story-processor instructions and executes them directly (no subagent-to-subagent chains), spawning isolated agents for create-story, dev-story, code-review, and quick-dev as directed. The testing phase runs at HIGH coverage (95%) in soft-fail mode: if tests do not pass, the epic continues to retrospective where failures are documented, and the epic is marked done but flagged for test attention. This ensures quality signal always reaches the retrospective even when tests need follow-up work.

**Pipeline per story:** create-story → dev-story → code-review (max 2 iterations, deferred findings batched at end)
**After all stories:** batch-fix deferred findings → run test pipeline (HIGH, soft-fail) → retrospective → mark epic done

**Input:** Epic number (e.g., `2`). If omitted, auto-selects the first non-done epic from sprint-status.yaml.

**Key rules:**
- Stories are processed ONE AT A TIME, in order — never parallelized
- The orchestrator reads story-processor instructions directly and executes them — no subagent-to-subagent chains
- If any story fails, the pipeline HALTs immediately
- The orchestrator never implements code directly — it spawns agents for create-story, dev-story, code-review

**Config dependency:** Requires `_bmad/bmm/config.yaml` (BMad Method Module).

## On Activation

Load config from `{project-root}/_bmad/bmm/config.yaml`. Follow all instructions in `references/workflow.md`.
