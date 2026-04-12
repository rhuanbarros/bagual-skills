---
name: bagual-test-pipeline
description: Automated adversarial test pipeline — auto-setup + unit tests + full-stack E2E with browser/server log capture + auto-fix loops. Use when the user says "run test pipeline", "test everything", "automate tests", or "bagual-test-pipeline".
---

# Test Pipeline

Orchestrates a complete, adversarial test pipeline — from framework auto-setup to full-stack E2E validation — fully automated, no halts for missing setup.

**Pipeline order:** auto-setup → adversarial unit/component tests → fix loop → full-stack E2E (browser + server log capture) → fix loop → report + commit

**Args:** `[coverage_target]` (e.g. `80`, `100`), `yolo` to skip confirmations, `--scope [path]` to limit to a directory.

**Key guarantees:**
- Framework is auto-installed if missing — never halts for missing setup
- All tests are adversarial: they discover bugs, not confirm existing behavior
- E2E runs against a real server + database — never mocked
- Browser console errors and server logs captured and reported with every failure
- Auto-fix loop (max 3 iterations per phase) via bmad-quick-dev

**Config dependency:** Requires `{project-root}/_bmad/bmm/config.yaml` (BMad Method Module).

Follow the instructions in references/workflow.md.
