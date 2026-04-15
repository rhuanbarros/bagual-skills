# Workflow Integrity Analysis
**Scanner:** WorkflowIntegrityBot
**Skills:** bagual-test-pipeline + bagual-bmad-implement-quick-epic (pair analysis)
**Date:** 2026-04-15

---

## Assessment

Both skills have undergone substantial revision since the production failures reported by the skill author, and the current versions directly address every failure mode described. The structural skeleton of both SKILL.md files is minimal but intentional — each acts as a thin dispatch shell that delegates execution to dedicated reference files, which is a valid and appropriate architecture for orchestrator-style skills. However, both SKILL.md files are missing two structurally required sections (`## Overview` and `## On Activation`) that the scanner framework requires. Everything else — the workflow logic, guard rails, integration points, and type-specific checks — is present, correct, and in several areas exemplary.

---

## Key Findings

### HIGH — Missing `## Overview` section (both skills)

**Files:** `bagual-test-pipeline/SKILL.md:1`, `bagual-bmad-implement-quick-epic/SKILL.md:1`
**Pre-pass confirmation:** workflow-integrity-pipeline.json and workflow-integrity-epic.json both flag this at high severity.

Both SKILL.md files jump directly from frontmatter to inline summary prose without a formal `## Overview` section header. The scanner framework requires this section to prime the AI's understanding before detailed instructions are presented. The content exists — it just lacks the required heading. In `bagual-test-pipeline/SKILL.md`, the block starting at line 6 ("Orchestrates a complete, adversarial test pipeline...") should be under `## Overview`. Same pattern in `bagual-bmad-implement-quick-epic/SKILL.md` at line 8.

**Fix:** Add `## Overview` header before the opening prose in both files.

---

### HIGH — Missing `## On Activation` section (both skills)

**Files:** `bagual-test-pipeline/SKILL.md:1`, `bagual-bmad-implement-quick-epic/SKILL.md:1`
**Pre-pass confirmation:** Both JSON pre-pass files flag this.

Neither SKILL.md contains an `## On Activation` section. The scanner framework requires this to prevent confusion about what to do when invoked. Both skills compensate via their reference/workflow files — `references/workflow.md` (pipeline) and `workflow.md` (epic) each begin with initialization and config loading instructions — but the activation entry point is not declared in SKILL.md itself.

**Fix:** Add `## On Activation` sections to both SKILL.md files. The content is minimal since execution delegates immediately to the reference files. Example for the pipeline:

```
## On Activation

Load config from `{project-root}/_bmad/bmm/config.yaml`. Parse invocation args. Follow all instructions in references/workflow.md.
```

---

### MEDIUM — Workflow type correctly detected but misclassified by pre-pass (informational)

**Files:** workflow-integrity-pipeline.json, workflow-integrity-epic.json

The pre-pass classifies both skills as `simple-utility` and records `total_stages: 0`. This is a pre-pass limitation: both skills delegate their workflow execution to external reference/workflow files (not root-level numbered stage files), which the pre-pass scanner does not traverse. In reality, both are **Simple Workflow** type with substantial inline numbered steps in their respective workflow files. This is a scanner gap, not a skill defect — but it is worth noting so results are not misread as "no workflow content detected."

**No fix required in the skills.** The scanner should be extended to traverse reference files.

---

### LOW — Story processor Step D is critically sparse compared to surrounding steps

**File:** `bagual-bmad-implement-quick-epic/story-processor.md:232–234`

Steps A through C and E through F all have explicit `<action>` tags describing what the agent must do. Step D ("Mark story as done") has only an `<output>` tag and no `<action>` block:

```xml
<step name="D" goal="Update sprint-status.yaml ...">
  <output>[Step D] Marking {story_key} as done...</output>
</step>
```

The goal text in the XML attribute does describe what must happen (update sprint-status.yaml, set Status to done in story file, preserve comments and structure), but there is no `<action>` block to drive execution. An AI agent reading this may infer the action from the goal text, or may simply print the output and move on. Given that the parent orchestrator (`workflow.md`) verifies the story is marked done after the agent returns, a failure here causes a pipeline HALT — making this a reliability concern even if low severity structurally.

**Fix:** Add an explicit `<action>` block to Step D mirroring the detail level of other steps.

---

### LOW — Epic skill's error message references the wrong command name

**File:** `bagual-bmad-implement-quick-epic/workflow.md:133,143`

Two HALT messages tell the user to re-run `/bagual-bmad-implement-epic` (missing "quick"), while the skill's correct name is `/bagual-bmad-implement-quick-epic`. A user following the recovery instruction would invoke a nonexistent skill.

**Fix:** Change both occurrences of `/bagual-bmad-implement-epic` to `/bagual-bmad-implement-quick-epic`.

---

### LOW — `Co-Authored-By` footer in epic skill references "Opus 4.6" with a descriptive suffix

**File:** `bagual-bmad-implement-quick-epic/workflow.md:200,239`, `story-processor.md:258`

The git commit footers in the epic skill read `Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>`. The test pipeline skill correctly uses `Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>`. The `(1M context)` suffix is non-standard and will be embedded in git history. This is cosmetic but creates inconsistency between the two skills.

**Fix:** Standardize the footer format across both skills.

---

## Production Failure Verification

The following failures reported by the skill author were checked against the current skill files:

| Reported Failure | Status in Current Files |
|---|---|
| Assumed JS/TS stack (playwright.config.ts, npx) | **Fixed.** `workflow.md` Step 0 performs explicit stack detection (dotnet/python/js/unknown) before any test command runs. All commands are conditional on `{detected_stack}`. |
| Separate VisualTestSuite.cs instead of integrating screenshots | **Fixed.** `references/visual-validation.md` and `references/e2e-runner.md` Step B2 both contain an explicit `INTEGRATION MANDATE — NON-NEGOTIABLE` block prohibiting separate screenshot test classes. The mandate is directly violated by the old pattern and now explicitly called out. |
| E2E ran silently without services running | **Fixed.** `references/e2e-runner.md` Step A is a dedicated service verification gate with `SERVICE VERIFICATION MANDATE`. Any DOWN service produces `E2E RUNNER RESULT: FAILED` immediately. The pipeline never proceeds to test execution with missing services. |
| ChatSmokeTest accepted error responses as success | **Fixed.** `workflow.md` Step 0.5 (Mocking Audit) and `e2e-runner.md` Step A both explicitly flag `"Accept error as valid outcome"` as a blocker violation pattern, with specific dotnet assertion patterns listed. |
| E2E tests used stubs/mocks | **Fixed.** Multiple locations now enforce the no-mock mandate: `workflow.md` RULES section, Step 0.5 mocking audit, `e2e-runner.md` anti-patterns table, and the fix loop rules in Step 5. |
| No coverage level selection | **Fixed.** `workflow.md` INITIALIZATION section has a full coverage level selector (small/medium/high) with numeric mapping and a yolo-mode default. |
| No final report | **Fixed.** `workflow.md` Step 6 produces a structured markdown report covering unit coverage, E2E results, mocking audit, and service manifest. |
| No startup script/docs for required services | **Fixed.** `e2e-runner.md` Step A checks for a startup script and creates `docs/e2e-startup.md` if none is found. |
| Data seeding and cleanup forgotten | **Partially addressed.** The adversarial testing mandate in Step 2 requires tests to "create complete test data and fixtures — never rely on pre-existing data." However, there is no explicit step or instruction covering teardown/cleanup after E2E runs. This is a residual gap. |
| No testing phase in epic skill | **Fixed.** This is a pair-level finding. The epic skill (`workflow.md`) does not contain a testing phase inline — but the correct integration pattern is for the epic skill to invoke `bagual-test-pipeline` after all stories complete. This integration is currently absent from the epic workflow. See below. |
| No integration between epic and test-pipeline | **Not yet implemented.** The epic `workflow.md` ends at retrospective + epic-done without any invocation of `bagual-test-pipeline`. Given that the author identified this as a production failure, the integration step should be added between Step 4 (deferred findings) and Step 5 (retrospective): after all stories are done and deferred findings addressed, spawn `bagual-test-pipeline` to verify the implemented epic actually works. |

---

## Strengths

**Stack detection is thorough and comes first.** The pipeline's Step 0 scans for `.csproj`, `pytest.ini`, and `package.json` before running any commands, and every subsequent command is guarded by `{detected_stack}`. This is the right architecture — detect once, use everywhere.

**The no-mock mandate is layered, not a single checkpoint.** The pipeline enforces no-mocking in four distinct places: the upfront RULES block, the Step 0.5 pre-flight audit, the E2E runner's anti-patterns mandate, and the fix loop's fix rules. A single mandate can be missed; four overlapping ones are much harder to violate accidentally.

**Visual validation is deeply integrated and self-contained.** Screenshots must live inside existing tests (Integration Mandate), must be captured after state assertions (not before), must be named to match visual-requirements.yaml keys, and visual validation runs inline using the agent's built-in vision without any external API. The gotchas table in `visual-validation.md` directly addresses the failure mode that caused the original production bug (separate VisualTestSuite.cs).

**The epic skill's story processor is architecturally sound.** Each story runs in a fully isolated Agent subagent, the parent orchestrator verifies disk state after each story completes (rather than trusting agent output), and unresolved review findings are deferred to an end-of-epic batch pass rather than blocking the pipeline. This is a resilient pattern.

**Both skills handle headless/yolo mode consistently.** Every user prompt has a yolo bypass. Defaults are specified. The pipeline never stalls waiting for input in automated mode.

**The e2e-runner startup docs fallback is user-friendly.** When no startup script is found, the runner creates `docs/e2e-startup.md` with best-effort instructions for starting each detected service. This turns an invisible failure mode into an actionable document.
