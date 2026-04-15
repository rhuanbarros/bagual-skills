# Skill Cohesion Analysis
## bagual-test-pipeline + bagual-bmad-implement-quick-epic
**Date:** 2026-04-15  
**Scope:** Pair analysis — test pipeline skill and epic implementation skill as an integrated system  
**Analyst:** SkillCohesionBot

---

## Overall Assessment

**Cohesion score: STRONG with one structural gap**

The two skills, as currently written after the fixes described in the production failure context, form a coherent and well-designed system for the test pipeline skill individually. The epic skill, however, has not yet received the two new phases (Phase A and Phase B) described in the desired outcomes. That gap is the single most significant structural finding — everything else is detail-level.

Within the test pipeline skill itself, cohesion across its four files (SKILL.md, workflow.md, e2e-runner.md, visual-validation.md) is very high. Instructions align, anti-patterns are enumerated consistently, and the agent delegation model is clean. The epic skill's existing workflow (workflow.md + story-processor.md) is internally coherent but is still operating as an implementation-only pipeline with no testing integration.

---

## Cohesion Dimensions

### 1. Stage Flow Coherence

**bagual-test-pipeline — STRONG**

The pipeline flow is logical and well-sequenced:

```
Step 0  Diagnostic Scan (stack detection)
Step 0.5  Mocking Audit (must precede test generation)
Step 1  Framework Auto-Install
Step 2  Generate Adversarial Unit Tests
Step 3  Run Unit Tests + Fix Loop (max 3 iterations)
Step 4  E2E Phase (spawns isolated e2e-runner agent)
Step 5  E2E Fix Loop (max 3 iterations)
Step 6  Final Report + Commit
```

Inside e2e-runner:
```
Step A  Service Verification (hard fail if any service down)
Step B  Log Capture Setup
Step B2 Visual Validation Setup (screenshot helper + visual-requirements.yaml)
Step C  Run Playwright E2E Tests
Step D  Inline Visual Validation (Read tool on PNGs)
Step E  Return structured PASSED/FAILED to orchestrator
```

Each step has clear entry and exit conditions. State flows forward via named variables ({unit_tests_passing}, {e2e_tests_passing}, {visual_passed}). The split between orchestrator (workflow.md) and isolated runner (e2e-runner.md) is architecturally sound — it enforces context isolation for the E2E phase while keeping the fix loop logic in the orchestrator.

One minor flow issue: Step 0.5 (Mocking Audit) runs before Step 1 (Framework Install) but after Step 0 (Diagnostic Scan). If the framework is not installed, there are no E2E test files to scan yet, so the audit would find nothing. This is not harmful but the ordering could confuse someone reading the file. The audit is most valuable when re-running the pipeline against an existing project, which is its primary use case, so the placement is defensible.

**bagual-bmad-implement-quick-epic (current state) — ADEQUATE for what it does, INCOMPLETE for desired outcomes**

Current flow:
```
Step 1  Parse sprint status, build story queue
Step 2  For each story: create-story → dev-story → code-review (2 iterations) → mark done → commit
Step 3  Verify all stories done
Step 4  Batch-fix deferred findings via bmad-quick-dev
Step 5  Retrospective → mark epic done
```

This is a clean implementation pipeline. Flow is coherent for the implementation-only goal. The deferred-findings batch fix at Step 4 is a good structural decision — it prevents per-story fix loops from blocking the pipeline while still addressing review debt before the retrospective.

The desired Phase A (create all tests) and Phase B (run everything, with service confirmation and fix loops) are entirely absent. In the current state, the epic pipeline produces implemented code with no test verification phase. The retrospective at Step 5 receives no test outcome signal to report on.

### 2. Purpose Alignment

**bagual-test-pipeline — FULLY ALIGNED**

Every file in the pipeline skill serves its declared purpose. SKILL.md states the guarantees ("E2E runs against a real server + database — never mocked", "Auto-fix loop max 3 iterations"). workflow.md implements those guarantees precisely. e2e-runner.md enforces the no-mocks mandate with a lookup table of anti-patterns. visual-validation.md defines the integration mandate (screenshots inside existing tests, not separate classes).

The production failures listed (JS/TS assumption, separate VisualTestSuite.cs, silent E2E, error-as-success) are all directly addressed by explicit rules in the current files. Stack detection is stack-aware throughout. The Integration Mandate in visual-validation.md explicitly prohibits the VisualTestSuite.cs pattern with a named example. The E2E Anti-Patterns Mandate in e2e-runner.md has a dedicated row for "accept error as valid outcome." Service verification (Step A) hard-fails if any required service is down — not silent.

**bagual-bmad-implement-quick-epic — PARTIALLY ALIGNED**

The skill is aligned with its current stated purpose (implement an epic end-to-end). It is not yet aligned with the desired purpose (implement an epic and verify it works). The SKILL.md description does not mention testing. workflow.md does not mention bagual-test-pipeline. story-processor.md has no test-related steps.

This is not a bug in what was written — it reflects that the two new phases have not been added yet.

### 3. Complexity Appropriateness

**bagual-test-pipeline — APPROPRIATE**

The complexity is high but justified by the problem. The pipeline manages: stack detection across four runtimes, mocking audits with per-language pattern recognition, framework auto-install delegation, adversarial test generation via two sub-skills, unit test fix loops with coverage enforcement, a fully isolated E2E runner agent with service verification, log capture fixture generation, visual validation with semantic requirements, and a structured final report. Each of these is genuinely necessary for the stated goal.

The delegation model (orchestrator spawns isolated subagents for each phase) is the right choice for context isolation. The e2e-runner agent is correctly isolated — it cannot be contaminated by the unit test phase's context.

One complexity risk: the e2e-runner spawns no subagents of its own, which is correct, but it is instructed to both run tests AND create fixtures (log capture, screenshot helper) AND generate visual-requirements.yaml if missing. That is a lot for one agent context. In practice, a large project with many E2E tests could make Step B2's visual-requirements.yaml generation very expensive. This is a performance concern, not a correctness one.

**bagual-bmad-implement-quick-epic — APPROPRIATE for current scope**

The epic pipeline is a thin orchestrator — it reads a queue, spawns story agents, and collects results. That is the correct complexity level for an orchestrator. The story-processor.md carries the per-story complexity. This separation is clean.

Adding Phase A and Phase B will significantly increase the orchestrator's complexity. Based on the desired outcomes, Phase A will spawn several subagents (framework setup, mocking audit, unit test generation, E2E screenshot integration, startup script creation, seed data creation). Phase B will add: user pause for service confirmation, TCP/HTTP service verification, seed data execution, unit test run with fix loop (3x), E2E run with fix loop (3x), inline visual validation, cleanup, and report generation. That is essentially the entire bagual-test-pipeline workflow embedded inside the epic workflow. The natural solution — calling bagual-test-pipeline directly — is the integration pattern the user wants and that is not yet present.

### 4. Gap and Redundancy Detection

**Gaps in bagual-test-pipeline:**

G1. **Data seeding and cleanup are not addressed anywhere in the current pipeline.** workflow.md, e2e-runner.md, and visual-validation.md are all silent on seeding test data before E2E runs and cleaning up after. The desired outcomes explicitly list "seed data before E2E tests — document/create process to populate DB; cleanup after tests." This is missing from all four pipeline files. The e2e-runner's Step A (service verification) confirms services are running but makes no mention of populating them with test data. Step B (log capture) and B2 (visual validation) also have no seed/cleanup hooks.

G2. **Coverage level selection is present in workflow.md but the high/95% default when invoked by the epic pipeline is defined in the desired outcomes and not yet surfaced as an invocation parameter in the epic workflow.** The epic would need to call the test pipeline with a specific coverage level argument. The pipeline accepts a `[coverage_target]` argument in SKILL.md, but the default when no arg is provided is "medium" (80%) in yolo mode, not "high" (95%). The epic pipeline would need to pass `high` or `95` explicitly.

G3. **The e2e-runner's Step C runs Playwright but uses the stack-native dotnet/python/js command without specifying how to distinguish unit tests from E2E tests in a dotnet solution that has both.** In a .NET project, `dotnet test` runs all test projects. If the solution has both a `MyApp.Tests` (unit) project and a `MyApp.E2ETests` project, Step 3 (unit tests) and Step C (E2E) would both run `dotnet test`. The e2e-runner's Step C command does not filter to only the E2E project. This can cause unit tests to run again during the E2E phase, wasting time and potentially producing confusing output. A `--filter` or project path specification is needed.

G4. **No explicit coverage gap report is requested from e2e-runner.** The orchestrator's Step 6 report section lists "What is NOT covered" but the e2e-runner only returns pass/fail and a services manifest. E2E coverage gaps (features with no E2E test) must come from somewhere. The coverage gap report in Step 6 relies on "all COVERAGE GAP REPORTs from Step 2 agents" (unit test generation) and "any E2E features with no test." The latter has no defined collection mechanism in e2e-runner.

**Gaps in bagual-bmad-implement-quick-epic:**

G5. **Phase A and Phase B are entirely missing.** This is the primary gap — fully described in the desired outcomes section.

G6. **No mechanism for the epic pipeline to detect that a story's implementation requires new services** and update the startup documentation accordingly. Phase A would create/update e2e-startup.md, but the signal of "this story added a dependency on service X" comes from the implementation, which the epic pipeline does not inspect.

G7. **The retrospective (Step 5) has no test outcome input.** The bmad-retrospective skill is called with `epic {epic_num} yolo` — it receives no signal about whether tests passed, how many fix iterations were needed, or what coverage was achieved. Once Phase B is added, the retrospective prompt should include the test report path so the retrospective can document test quality alongside implementation quality.

**Redundancies:**

R1. **The mocking anti-patterns are enumerated three times across the pipeline skill files** — once in workflow.md (Step 0.5, the audit patterns), once in e2e-runner.md (the E2E Anti-Patterns Mandate table), and indirectly in visual-validation.md (the Integration Mandate). This is not a harmful redundancy — each instance serves a different agent context (the orchestrator, the runner, and the visual validator). Because agents read their assigned file in isolation, the repetition is necessary. It is not a defect.

R2. **The screenshot helper code appears in full in both e2e-runner.md (Step B2) and visual-validation.md.** e2e-runner.md says "Follow the language-specific helper in visual-validation.md" but then also contains `<check if="helper not found">` with an `<action>` to create the helper. The action block does not reproduce the helper code inline — it delegates to visual-validation.md. This is the correct pattern, but the delegation instruction ("Follow the language-specific helper in visual-validation.md") is positioned inside Step B2 rather than being the sole source. If a future author updates the helper code in visual-validation.md but not the surrounding Step B2 context, drift could occur. The delegation is fine; just note that visual-validation.md is the single source of truth for helper code.

### 5. Dependency Graph Logic

The dependency graph for the integrated system (desired end state) should be:

```
bagual-bmad-implement-quick-epic
  └─ story-processor.md (per story: create-story → dev-story → code-review)
  [Phase A, after all stories done, before retrospective]
  └─ bagual-test-pipeline (or equivalent inline logic)
       └─ bmad-testarch-framework (if framework missing)
       └─ bmad-testarch-atdd
       └─ bmad-testarch-automate
       └─ bmad-quick-dev (fix loops)
       └─ e2e-runner (isolated)
            └─ visual-validation
  └─ bmad-retrospective (receives test report path as input)
```

In the current state, bagual-test-pipeline is a standalone skill. The epic pipeline makes no reference to it. The dependency from epic to test pipeline is the missing link.

One dependency concern: Phase A in the desired outcomes includes "framework setup if missing, mocking audit, generate unit tests at HIGH coverage, log capture fixture for E2E, add screenshots to existing E2E tests, create/document startup script, create seed data and cleanup process." This is almost exactly what bagual-test-pipeline Steps 0 through B2 do. If Phase A is implemented by calling bagual-test-pipeline rather than duplicating logic, the dependency is clean. If Phase A is implemented inline in the epic workflow, it will create a maintenance burden (two places to update when test setup logic changes).

**Recommendation:** Phase A and Phase B together should be implemented by invoking bagual-test-pipeline with a high coverage level, with one addition: a pre-check pause for user service confirmation. The pause already exists in bagual-test-pipeline's `{proceed_mode} == 'step'` logic (Step 4: "Pausing before E2E phase — make sure your server and database are running"). The epic pipeline's Phase B "pause for user to confirm services running" would be satisfied by invoking the pipeline in step mode (not yolo mode) for the E2E portion.

However, if the epic pipeline invokes bagual-test-pipeline in yolo mode (as it does for all subagents), the pause will not happen. This is a behavioral conflict that needs to be resolved in the design: either the epic pipeline should call the test pipeline in step mode for the E2E portion, or the test pipeline should accept a separate `--pause-before-e2e` flag.

### 6. External Skill Integration Coherence

**Within bagual-test-pipeline:**

The pipeline correctly delegates to four external skills:
- `bmad-testarch-framework` for framework auto-install
- `bmad-testarch-atdd` for adversarial test generation
- `bmad-testarch-automate` for coverage expansion
- `bmad-quick-dev` for fix loops (both unit and E2E)

Each delegation includes the Adversarial Testing Mandate verbatim in the subagent prompt. This is a good pattern — it prevents the mandate from being lost in context when a subagent starts fresh.

The `bmad-quick-dev` fix loop integration for E2E (Step 5) instructs the fix agent to fix source code without mocking — this is the right constraint.

**Between epic and test pipeline (desired end state):**

The integration point is entirely absent from the current epic workflow and story-processor. Once added, the integration should:

1. Pass the coverage level explicitly: `high` or `95` (not the default medium)
2. Pass the services manifest from e2e-runner back to the retrospective
3. Handle the "tests don't pass after 3 iterations — warn but continue" gracefully (the test pipeline currently HALTs after 3 failed iterations; the epic's desired behavior is to warn and continue to retrospective — this means the epic would need to invoke the test pipeline in a way that captures failure without treating it as a pipeline halt)

This last point is a genuine interface mismatch. bagual-test-pipeline exits with HALT on 3 failed iterations. The epic's desired behavior is to not stop but to flag. Either the test pipeline needs a `--no-halt-on-failure` mode, or the epic pipeline needs to handle the test pipeline's HALT by catching the failure report and continuing to retrospective with a "tests failed" flag.

---

## Key Findings

**Finding 1 — Critical: Phase A and Phase B are missing from the epic pipeline**

The epic pipeline is an implementation pipeline. It produces code. It does not verify the code works. The two new phases described in the desired outcomes do not exist in workflow.md or story-processor.md. Until they are added, the epic pipeline cannot satisfy the "deliver tested software" goal.

**Finding 2 — High: Data seeding and cleanup are absent from the test pipeline**

All four test pipeline files are silent on database seeding before E2E and cleanup after. The e2e-runner confirms services are running but never populates them with test data. Real E2E tests against a real database will fail or produce false results without a known data state. This is listed as a production failure for the test pipeline and is not yet addressed in the current files.

**Finding 3 — High: Test pipeline invocation from epic lacks interface contract**

bagual-test-pipeline currently HALTs on 3 failed E2E iterations. The epic's desired behavior is "warn but continue to retrospective." There is no flag or mode in the test pipeline that supports non-halting failure. This interface mismatch must be resolved before Phase B can be added to the epic.

**Finding 4 — Medium: dotnet test command in e2e-runner does not isolate E2E project**

`dotnet test` without a project path filter runs all test projects in the solution. In a .NET project with both unit and E2E test projects, the e2e-runner's Step C will run unit tests again. The command should target the E2E project specifically (e.g., `dotnet test Tests/E2E/MyApp.E2ETests.csproj`).

**Finding 5 — Medium: Epic coverage level defaults to medium when invoking test pipeline in yolo mode**

If Phase B calls bagual-test-pipeline with yolo mode and no explicit coverage argument, the default is medium (80%). The desired behavior when invoked from the epic pipeline is high (95%). An explicit argument is required.

**Finding 6 — Medium: No E2E coverage gap collection mechanism**

The final report in Step 6 lists "What is NOT covered" under E2E, but the e2e-runner returns only pass/fail and a services manifest. There is no mechanism for the e2e-runner to identify and return which features have no E2E test. The coverage gap list in the report will be empty by default unless the orchestrator infers it from the Step 2 unit test generation's coverage gap reports.

**Finding 7 — Low: Mocking audit (Step 0.5) before framework install (Step 1) has an ordering edge case**

If no E2E test files exist yet (first run of the pipeline on a new project), Step 0.5 runs before any tests are created and will always find nothing. This is harmless but wastes agent effort. Mocking audits are most meaningful on re-runs against existing projects, which is the primary use case.

**Finding 8 — Low: Retrospective receives no test outcome signal**

bmad-retrospective is called with `epic {epic_num} yolo` only. It has no way to include test pass/fail status, coverage achieved, or number of fix iterations in the retrospective document. Once Phase B generates a test report, the retrospective invocation should pass the report path.

---

## Strengths

**S1. The no-mocks principle is enforced at every layer.** The rule appears in SKILL.md (key guarantees), workflow.md (RULES section and Step 0.5), e2e-runner.md (Anti-Patterns Mandate and Step A), and visual-validation.md (Integration Mandate). An agent executing any part of the system will encounter the rule in its context. This is excellent defense-in-depth.

**S2. The Integration Mandate for screenshots is unambiguous.** visual-validation.md explicitly names the anti-pattern (VisualTestSuite.cs), explains why it is wrong, and provides a concrete correct example (C# code snippet). This prevents the most common screenshot failure mode without relying on the agent to infer the intent.

**S3. Stack detection drives everything correctly.** Detecting the stack in Step 0 and threading `{detected_stack}` through all subsequent steps is the right pattern. Every framework check, every test command, every fixture creation, and every helper code example is stack-conditional. This eliminates the JS/TS assumption failure.

**S4. Service verification is immediate and loud.** e2e-runner's Step A builds a services manifest, checks each service via TCP/HTTP, and halts with a clear per-service error message if any service is down. It also creates docs/e2e-startup.md if no startup script exists. This directly addresses the silent E2E failure mode.

**S5. The agent delegation model is clean.** The orchestrator never implements code. It spawns isolated subagents and collects results. This is the right abstraction for a pipeline orchestrator. Context isolation prevents earlier phases from contaminating later phases.

**S6. The fix loop structure is sound.** Each phase (unit, E2E) has a dedicated fix loop capped at 3 iterations. The fix mandate explicitly forbids weakening tests, lowering thresholds, or mocking things that should be real. The loop exits on confirmed pass, not on "no errors in fix agent output."

**S7. The deferred-findings pattern in the epic pipeline is clever.** Per-story review loops cap at 2 iterations and defer remaining findings to a batch fix at the end of the epic. This prevents any single story's review debt from blocking all subsequent stories while still addressing the debt before the retrospective.

---

## Creative Suggestions

**CS1. Add a `--no-halt` flag to bagual-test-pipeline for pipeline-embedded invocations**

The epic pipeline needs to call the test pipeline and continue even if tests fail after 3 iterations (warn, not stop). The cleanest solution is a `--no-halt` or `--soft-fail` flag in bagual-test-pipeline that, instead of halting and outputting a HALT message, returns a structured failure result that the caller can handle. The SKILL.md args section already defines `[coverage_target]` and `yolo` — add `soft-fail` to the list. The epic workflow would invoke: `/bagual-test-pipeline high soft-fail`.

**CS2. Define a "seed contract" file: `_bmad/test-data/seed.yaml`**

Rather than discovering seeding requirements ad-hoc during e2e-runner Step A, define a convention for a seed contract file. This file would list: which entities need to exist before E2E tests run, minimum counts, and how to create them (script path, SQL file, API call). The e2e-runner would read this file and either verify the data exists or execute the seed commands. Cleanup would be the reverse (delete by the same criteria). This makes seeding reproducible and auditable.

**CS3. Add a "test debt" section to the epic's retrospective output**

Once Phase B exists and the retrospective receives the test report, create a structured "Test Debt" section in the retrospective document. This section would list: coverage gaps, mocking violations if any survived, services not verified, and fix iterations required. The retrospective already serves as the epic's quality summary — including test debt here makes it the single source of truth for the epic's health.

**CS4. Create a per-story test stub obligation in story-processor.md**

Phase A of the desired outcomes generates tests after all stories are done. A stronger approach: as each story is marked done (story-processor.md Step D), append a "test obligations" entry to a manifest file (e.g., `_bmad/test-obligations.md`). This entry would list: which features were implemented, which behaviors should be testable, and which UI states are new. Phase A would then read this manifest instead of scanning the codebase cold. This produces better test generation prompts because the implementation context is captured at implementation time, not reverse-engineered later.

**CS5. Visual validation requirements should be committed per story, not generated at pipeline time**

Currently, visual-requirements.yaml is generated by the e2e-runner agent during the pipeline run. This means requirements are created after the tests run — they describe what happened, not what should happen. The better workflow: when a dev-story agent adds a screenshot call to an E2E test, it should also append the corresponding requirements to visual-requirements.yaml. The pipeline's Step B2 would then only need to verify completeness, not generate from scratch. This converts visual requirements from a post-hoc description to a pre-run specification, which is their intended purpose.

**CS6. Consider a "dry run" mode for the test pipeline that only produces the diagnostic and mocking audit**

A `/bagual-test-pipeline dry-run` mode would run Steps 0 and 0.5 only: stack detection, infrastructure scan, and mocking audit. It would output the full diagnostic without generating tests or running anything. This is useful for teams onboarding to the pipeline who want to understand their current state before committing to the full run. The existing `[3] Diagnostic only` option in Step 0 is close to this, but it requires interactive confirmation. A `dry-run` flag would work in yolo mode.

---

## Integration Verdict

The test pipeline skill is production-ready as a standalone tool. Its internal cohesion is high. All production failures listed have been addressed in the current files.

The epic pipeline skill is internally coherent for its current scope but is not yet integrated with the test pipeline. The system as a whole does not deliver tested software — it delivers implemented software. The missing integration is Phase A and Phase B in the epic workflow, with a resolved interface for the soft-fail mode and an explicit high-coverage invocation.

Priority order for changes:

1. Add seed data and cleanup to e2e-runner (Finding 2 — affects test pipeline standalone use)
2. Add `soft-fail` mode to bagual-test-pipeline (Finding 3 — required before epic integration)
3. Add Phase A and Phase B to the epic workflow (Finding 1 — the primary gap)
4. Fix dotnet test command in e2e-runner to target E2E project only (Finding 4)
5. Pass test report path to retrospective invocation (Finding 8)
6. Add E2E coverage gap collection to e2e-runner (Finding 6)
