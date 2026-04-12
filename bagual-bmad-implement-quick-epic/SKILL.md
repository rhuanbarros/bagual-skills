---
name: bagual-bmad-implement-quick-epic
description: 'Faster epic pipeline: create-story → dev-story → code-review (max 2 loops, deferred findings batched at end via bmad-quick-dev) → retrospective. Use when the user says "run quick epic {N}" or "quick pipeline epic {N}"'
---

# Quick Epic Pipeline

Orchestrates an entire epic through sequential story processing until complete.

**Pipeline per story:** create-story → dev-story → code-review (max 2 iterations, deferred findings batched at end) → mark done → commit
**After all stories:** batch-fix deferred findings → retrospective → mark epic done

**Input:** Epic number (e.g., `2`). If omitted, auto-selects the first non-done epic from sprint-status.yaml.

**Key rules:**
- Stories are processed ONE AT A TIME, in order — never parallelized
- Each story runs in an isolated Agent subagent for full context separation
- If any story agent fails, the pipeline HALTs immediately
- The orchestrator never implements code directly — it only spawns sub-skill agents

**Config dependency:** Requires `_bmad/bmm/config.yaml` (BMad Method Module).

Follow the instructions in ./workflow.md.
