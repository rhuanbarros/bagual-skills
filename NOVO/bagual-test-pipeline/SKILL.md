---
name: bagual-test-pipeline
description: Automated adversarial test pipeline — auto-setup + unit tests + full-stack E2E with browser/server log capture + visual validation (dual-mode: inline vision or AI-mediated script) + auto-fix loops. Use when the user says "run test pipeline", "test everything", "automate tests", or "bagual-test-pipeline".
---

# Test Pipeline

## Overview

Orchestrates a complete, adversarial test pipeline — from stack detection and framework auto-setup to full-stack E2E validation with visual inspection — fully automated. The pipeline's role is not just to run tests but to enforce they are real: real services, real data, real failures. It detects the project stack (dotnet/python/js), installs missing infrastructure, generates adversarial tests at the requested coverage level, audits E2E tests for mocking violations both before and after generation (catching violations introduced by generators), runs unit and E2E suites with auto-fix loops capped at 3 iterations each, and produces a final coverage + mocking audit report.

**Visual validation** runs via AI-mediated script by default (`scripts/validate-visual.sh`):
- Screenshots are sent to an external vision AI (Kimi Code K2.5 preferred, with Open Router / Gemini / Claude / OpenAI fallbacks)
- The script returns structured text results (JSON) — the Harness NEVER processes images
- Works with ANY Harness model, including text-only
- Requires one API key: `KIMI_API_KEY` (preferred) or any of `OPENROUTER_API_KEY`, `GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`

**Pipeline order:** stack detection → mocking audit → framework setup → adversarial test generation → post-generation mocking audit → unit tests + fix loop → E2E tests + fix loop → visual validation → report + commit

**Args:** `[coverage_level]` (`small` | `medium` | `high`), `[coverage_target]` (numeric, e.g. `80`), `yolo` to skip confirmations, `--scope [path]` to limit to a directory.

**Key guarantees:**
- Stack detected deterministically before any command is issued (dotnet/python/js/unknown)
- Framework is auto-installed if missing — never halts for missing setup
- All tests are adversarial: they discover bugs, not confirm existing behavior
- E2E mocking violations audited before AND after test generation — catches violations introduced by generators
- E2E runs against a real server + database — never mocked; fails loudly if any service is down
- Browser console errors and server logs captured and reported with every failure
- Auto-fix loop (max 3 iterations per phase) via bmad-quick-dev
- Visual validation: AI-mediated via `scripts/validate-visual.sh` (Kimi Code K2.5 default) — Harness reads text, never images

**Config dependency:** Requires `{project-root}/_bmad/bmm/config.yaml` (BMad Method Module).

## On Activation

Load config from `{project-root}/_bmad/bmm/config.yaml`. Follow all instructions in `references/workflow.md`.
