---
name: bagual-spec-gate
description: 'Audits a shared design-spec + epic document for schema-inventory gaps, missing rollback/count-check ACs on destructive migrations, and undecided product behavior before any story is sliced from it. Use when the user says "rodar o spec gate", "/bagual-spec-gate <N>", "gate de spec da epic {N}", "auditar a spec antes de rodar a epic", or wants a design-spec+epic document checked before it becomes stories.'
---

# bagual-spec-gate

## Overview

This skill runs one linear pass over a shared design-spec + epic document — ONE layer above
stories, before any story is created from it — and reports `PASS` or `HALT`. It exists because
the bmad-loop treats a spec as a literal, executable contract: what a spec doesn't mention isn't
hesitated over, it's silently dropped. In Story 22.1, a migration's `INSERT ... SELECT` carried
13 of an old table's columns forward and silently omitted two live ones (`expense_type`,
`investor_name`, PRD FR99) before `DROP TABLE`ing the source — no rollback CSV, no row-count
check between the copy and the drop. The story's own auto-review caught the gap correctly
(`bmad-dev-auto/step-02-plan.md`'s existing intent-gap HALT), but only after the destructive half
of the migration had already run against the shared Dev database. This skill does not add a new
stop mechanism — it adds the inventory that makes the existing one fire in time, one layer
earlier, over the document everything downstream gets sliced from.

It walks 8 fixed checks (`workflow.md`): document resolution, growing the checklist from prior
Wiki lessons, an unscoped repo-wide inventory sweep, edge-case coverage, destructive-action
safeguards, `Block If` completeness, verifiable Acceptance Criteria, and Wiki grounding. Four of
those checks (inventory, edge cases, destructive-action safeguards, verifiable ACs) are facts
checkable against the repository and get corrected in place. One check — undecided product
behavior surfacing as a missing `Block If` — is never inferred; it always becomes a literal
question put to the project owner, with the literal answer recorded. The final verdict field
(`PASS`/`HALT`) is a contract another workstream's `bmad-dev-auto.toml` guard reads directly.

## On Activation

Load available config from `{project-root}/_bmad/config.yaml` and `{project-root}/_bmad/config.user.yaml` if present. Use sensible defaults for anything not configured. Talk to the user in `communication_language` (default Portuguese); this skill's artifacts — the SKILL.md/workflow.md prose, the generated `spec-gate-epic-<N>.md` report, and every corrected section written back into the target document — are English regardless of `document_output_language`. The one exception: a Step 5 `Block If` question-and-answer exchange with the owner is transcribed verbatim, in whatever language the owner actually used — a direct quote is never translated.

Resolve these path-vars for the run:
- `{spec_gate_output_dir}` = `{project-root}/_bmad-output/implementation-artifacts/`
- `{inventory_sweep_script}` = `{project-root}/.claude/skills/bagual-spec-gate/scripts/inventory_sweep.py`

Follow `workflow.md` (in this skill's own directory, not under `references/`) for the 8-step gate.
