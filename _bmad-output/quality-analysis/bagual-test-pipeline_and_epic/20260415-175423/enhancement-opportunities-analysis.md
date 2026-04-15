# Enhancement Opportunities Analysis
**Skills:** bagual-test-pipeline + bagual-bmad-implement-quick-epic
**Date:** 2026-04-15
**Scanner:** DreamBot Creative Quality Scan

---

## 1. Skill Understanding

### bagual-test-pipeline

The pipeline is a thin orchestrator that sequences: diagnostic scan → mocking audit → framework setup → unit test generation → unit test fix loop (max 3) → E2E runner (isolated agent) → E2E fix loop (max 3) → final report + commit.

The current skill text (SKILL.md, workflow.md, e2e-runner.md, visual-validation.md) already incorporates most of the desired behaviors described in the brief:

- Stack detection in Step 0 is explicit and stack-gated throughout (dotnet / python / js / unknown).
- E2E mocking audit (Step 0.5) runs before any test execution and catalogs six violation types.
- e2e-runner Step A: service discovery + startup-doc creation + hard fail on any DOWN service — this is all present.
- Coverage level selection (small/medium/high → 60/80/95) is present in workflow.md INITIALIZATION.
- Final report (Step 6) includes coverage, mocking audit, and verified services list.
- visual-validation.md has the Integration Mandate in bold: screenshots must live inside existing E2E tests, never in a separate class.

What the skill text says vs. what the agent actually did diverge. The production failures happened despite the intent being written down, which means the failures are not "missing features" — they are **enforcement failures**. The mandates exist but the agent was able to ignore or misread them.

### bagual-bmad-implement-quick-epic

The pipeline sequences: queue stories → per-story isolated agent (create → dev → review loop → mark done → commit) → deferred findings batch fix → retrospective → mark epic done.

Testing is entirely absent from the story pipeline. story-processor.md has no phase that invokes the test pipeline or any test runner. The retrospective (Step 5) is the only quality gate after all implementation, and bmad-retrospective is a documentation skill, not a test execution skill. There is no invocation of `/bagual-test-pipeline` anywhere in workflow.md or story-processor.md.

---

## 2. User Journeys

### Journey A: Agent runs quick-epic on a new C# project

1. Orchestrator reads sprint-status, queues stories.
2. Story agent spawns: create-story → dev-story → code-review → mark done → commit.
3. dev-story implements C# code. No test phase is called.
4. code-review is a static analysis agent — it reviews code quality, not whether the system actually runs.
5. All stories marked done. Retrospective runs. Epic marked done.
6. **Gap:** The agent has never run a single test. The application may not compile, may crash on startup, or may have broken E2E flows. The epic is "done" and the user discovers failures only later.

### Journey B: Agent runs test-pipeline on the same project, which now has E2E tests that use stubs

1. Step 0 detects dotnet stack correctly (current skill text handles this).
2. Step 0.5 scans for mocking violations. If `KnowledgeSearchTestDataFixture` replaced a real HTTP call, this scan should detect it — but only if the agent correctly identifies the stub pattern. The violation catalog covers `WireMock`, `MockHttp`, `TestServer` with stub handlers, but a custom `TestDataFixture` that intercepts HTTP via a named `HttpMessageHandler` or a fake `IKnowledgeSearchService` registered in DI would not match those patterns. The audit relies on textual pattern matching of class names and keywords, not semantic analysis of what the class does.
3. Step A of e2e-runner verifies all required services. If no service is running, it hard-fails. This is correctly specified. However: if the project's `.env` or `appsettings.Development.json` contains a base URL pointing to `localhost:18081` (the stub port) rather than the real Python API URL, the service check will verify that port — which is the stub, not the real API. The service check verifies "something is listening," not "the real service is listening."
4. **Gap:** A stub that listens on the expected port passes the service verification. The mocking violation is thus invisible to both the audit (no keyword match) and the service check (port is occupied by the stub).

### Journey C: Agent runs test-pipeline and generates new E2E tests from scratch

1. Step 2 spawns bmad-testarch-atdd with the Adversarial Testing Mandate.
2. atdd agent generates E2E tests. If the story stories include a knowledge search feature, the test agent may introduce a test data fixture (common practice) that replaces the real API. The mandate says "never mock" but the test generator is a different agent with its own context — it may not internalize the mandate fully.
3. Step 0.5 is designed to catch this after tests exist. But Step 0.5 runs before Step 2 (test generation). The audit does not re-run after Step 2 generates new tests.
4. **Gap:** Mocking violations introduced by the test generator are never audited. Step 0.5 only audits pre-existing tests.

### Journey D: The developer with a non-standard stack

1. Agent detects stack as "unknown" (e.g., Go, Rust, Elixir).
2. Step 0 falls through to "unknown" and subsequent steps use try-order commands.
3. Step 1 spawns bmad-testarch-framework with `detected_stack: unknown`, which instructs to "try each in order: dotnet test → pytest → npx vitest run → npx jest." These are all wrong for a Go project.
4. **Gap:** "Unknown" stack degrades to a generic attempt that almost certainly fails. The agent has no way to signal "I cannot identify this stack — please help me."

### Journey E: Developer uses the epic pipeline for a brownfield project mid-sprint

1. Some stories are already "in-progress." story-processor handles this: if status != backlog, it skips Step A (create-story) but still runs dev-story.
2. dev-story runs on a story file that already has partial implementation notes and uncommitted changes.
3. code-review runs on "uncommitted changes" — but if the previous human developer had uncommitted changes unrelated to this story, those will be included in the review.
4. **Gap:** No isolation between human-authored uncommitted changes and agent-authored changes.

### Journey F: Test pipeline invoked by epic pipeline (the intended integration)

This journey cannot currently happen because the epic pipeline does not call the test pipeline. There is no invocation path.

---

## 3. Headless Assessment

Both skills run fully headless (no user prompts in yolo mode, subagent architecture). The orchestrators are thin — they communicate intent via subagent prompts, not via shared state objects. This design has two structural weaknesses in headless operation:

**Mandate drift across agent boundaries.** The Adversarial Testing Mandate is embedded in the orchestrator's prompt strings to sub-skill agents. When sub-skills (bmad-testarch-atdd, bmad-quick-dev) run, they receive the mandate as a string in their invocation prompt. But those skills have their own SKILL.md and workflow files with their own instructions. If those instructions conflict with or simply don't reinforce the mandate, the sub-skill agent will follow its native instructions. The mandate is advisory in the sub-skill's context, not structurally enforced.

**Result parsing is fragile.** The orchestrator detects E2E results by checking if agent output "contains 'E2E RUNNER RESULT: PASSED'". If an agent produces verbose output and the result string appears in an unexpected position, or if the agent outputs a slightly different string ("E2E RESULT: PASSED", "## E2E RUNNER RESULT: PASSED\n\nTests: ..."), the parse may fail and the orchestrator interprets it as a failure. This is recoverable (it triggers the fix loop) but wastes an iteration.

**No re-audit after generation.** The mocking audit (Step 0.5) is a pre-generation check. There is no equivalent post-generation check. In headless operation, the agent has no way to flag "I just generated tests — please verify they are clean" because the orchestrator never re-runs the audit.

**E2E fix loop cannot restart services.** In headless mode, if E2E fails because a service went down mid-run (intermittent crash), the fix loop will attempt to fix source code rather than restart the service. The agent has no way to distinguish "service crashed" from "code bug." The failure report format could capture this, but the fix-loop prompt does not instruct the agent to check service health before applying fixes.

---

## 4. Key Findings

### Finding 1: The audit gap — violations introduced after the audit are invisible

**Root cause of original failure:** KnowledgeSearchTestDataFixture was created by the test generator (Step 2), after Step 0.5 ran. Step 0.5 never ran again.

**Current state:** Step 0.5 is positioned at the start, before test generation. This is correct for pre-existing violations but entirely blind to violations introduced by the pipeline itself.

**What would make the agent structurally unable to make this mistake:** A second mocking audit immediately after Step 2 (test generation), before any test run. If the generator produced a violation, it would be caught before Step 3 runs.

### Finding 2: Port occupancy is not identity verification

**Root cause of original failure:** E2E tests ran "silently" without real services. If a stub occupied the port, Step A's service check would report UP.

**Current state:** Step A checks HTTP /health or TCP connect with a 3-5 second timeout. It does not verify service identity — just that something answers.

**What would make the agent structurally unable to make this mistake:** Include a version or identity check in the service verification. For the Python AI API: check `/health` and verify the response body contains a known field (e.g., `{"status": "ok", "service": "knowledge-api"}`). This requires service-specific knowledge that the skill currently lacks — it can only be provided via `appsettings` or a new config section listing expected health response fields.

### Finding 3: The epic pipeline has no testing phase — by design omission, not by accident

**Root cause of original failure:** story-processor.md has no step that runs tests. The skill's described behavior (create → dev → review → done) has no test execution. The retrospective is documentation, not verification.

**Current state:** No invocation of bagual-test-pipeline anywhere in the epic pipeline. No test-run verification before marking a story done or an epic done.

**What would make the agent structurally unable to make this mistake:** A Phase B step in story-processor.md after Sub-step B (dev-story) and before Sub-step C (code-review). Phase B would invoke the test pipeline in a scoped mode (e.g., `/bagual-test-pipeline high --scope {story_scope_path} yolo`). If tests fail after 3 iterations, the story-processor would warn, document in the story file, and mark the story done with a `done-with-test-failures` flag rather than `done`.

### Finding 4: The mocking violation catalog is keyword-based, not semantic

**Current state:** Step 0.5 searches for `WireMock`, `MockHttp`, `HttpListener`, `UseInMemoryDatabase`, etc. A custom class named `KnowledgeSearchTestDataFixture` that wraps a fake `IKnowledgeSearchService` would not appear in this catalog unless the agent happens to notice the pattern from reading the class implementation.

**What would make this more robust:** Add to the violation catalog: any class registered in the test DI container that implements a service interface but whose class name contains `Fake`, `Stub`, `Mock`, `Test`, or `Fixture` and whose implementation does not make real HTTP calls (i.e., it returns hardcoded data). This is a heuristic, not foolproof, but would catch the KnowledgeSearchTestDataFixture pattern.

### Finding 5: Data seeding and cleanup are not mentioned in the skill text

**Desired behavior:** Seed data before E2E tests, clean up after. Document or create the process.

**Current state:** e2e-runner.md Step A discovers services and Step B sets up log capture. There is no step for data seeding. The test generation mandate (Step 2) says "Create complete test data and fixtures — never rely on pre-existing data in the environment," but this applies to unit tests. E2E tests against a real database need real seeding — the test cannot create its own data unless it also tests the creation flow.

**Gap:** No seeding step, no teardown step, no mention of a seed script or fixture strategy in either the E2E runner or the visual validation reference.

### Finding 6: "Accept error as valid outcome" detection relies on comment text, not logic structure

**Root cause of original failure:** `IsAnyResponseOrErrorVisibleAsync` is a method that checks for either success or error. The violation catalog includes: `// Accepts both ... so the test passes even when service is not running`. This catches the comment, not the structural assertion pattern. A developer who writes the same logic without that comment bypasses the audit.

**Current state:** The catalog lists the pattern structurally (`Assert.True(successVisible || errorVisible)`) as a dotnet example. This is better. But the agent reads code via text search — it would need to recognize disjunctive boolean assertions as a pattern, which requires more context than a simple string match.

**What would be more robust:** The mocking audit should explicitly call out the pattern: "any assertion that passes when EITHER a success indicator OR an error indicator is visible." Add to the catalog: any Playwright `Expect` or xUnit `Assert` call that includes a logical OR (`||`) between a success-locator check and an error-locator check.

### Finding 7: Coverage level defaults differ between standalone and epic-pipeline invocations

**Current state:** The skill specifies that when invoked by the epic pipeline, coverage level should default to "high" (95%). But the workflow.md initialization sets default (yolo mode) to "medium" (80%). There is no branch for "invoked by epic pipeline" in the current workflow.

**Gap:** If the epic pipeline calls `/bagual-test-pipeline yolo`, it will get medium coverage, not the high coverage intended for epic completion gates.

**What would make this structurally correct:** The epic pipeline would need to pass a flag (e.g., `/bagual-test-pipeline high yolo`) when invoking the test pipeline after epic implementation, and the test pipeline's arg parsing already supports this — `{coverage_level}` can be passed as an argument. The gap is that the epic pipeline does not yet exist as an invocation, so there is no opportunity to pass the flag. When integration is added, the epic workflow should hardcode `high yolo` in the invocation.

---

## 5. Top Insights

### Insight 1: The skills are aspirationally complete but structurally non-enforcing

Reading the current skill text without the context of the production failures, one would conclude these skills are well-designed. The mandates are present, the anti-patterns are named, the violation types are cataloged. Yet the agent violated all of them in production. This is the central design problem: **the agent is given rules but not structural constraints that make violations impossible.**

The difference between a rule ("never create mocks in E2E") and a structural constraint ("re-audit for mocks after every code-generation step before any test run") is that the rule can be forgotten, misapplied, or overridden by another instruction in context. The structural constraint executes regardless of what the agent "remembers."

### Insight 2: The fix-loop is the wrong response to infrastructure failures

The current design treats all E2E failures the same: run fix loop. But there are two categories of E2E failures with completely different remediation paths:

- **Infrastructure failures** (service down, wrong port, DB not seeded): no amount of code fixing helps. The fix loop wastes all 3 iterations on source code while the real problem is environment setup.
- **Code failures** (assertion wrong, feature broken): the fix loop is appropriate.

The E2E runner already distinguishes these — Step A returns a different failure format than Step C. But the orchestrator's Step 5 (E2E fix loop) does not check which type of failure occurred. It always spawns bmad-quick-dev. The orchestrator should: if E2E RUNNER RESULT: FAILED contains "Required services not running," halt immediately with an environment-setup message instead of entering the fix loop.

### Insight 3: The epic pipeline's testing gap is a sequencing problem, not a missing feature

The user's desired outcome (Phase A: create tests, Phase B: run everything) can be implemented as a post-implementation, pre-review step in story-processor.md. The correct insertion point is after Sub-step B (dev-story) and before Sub-step C (code-review). This way, code review receives feedback from actual test runs, not just static analysis. A story that fails tests would be flagged in the code review context alongside any code issues.

The fail-soft mechanism (warn + document + mark done with flag after 3 test iterations) maps well to the existing deferred findings pattern. A test failure can be recorded in `{deferred_findings_file}` alongside code review findings, and the same end-of-epic batch fix pass can attempt to resolve them.

### Insight 4: The startup doc creation is a one-time side effect with no feedback loop

e2e-runner Step A creates `docs/e2e-startup.md` if no startup script exists. This is a useful artifact. But the e2e-runner also immediately tries to verify all services — and fails if they are not running. The startup doc is created and then the test immediately fails. The developer must read the doc, start the services manually, and re-run. In headless/yolo mode, this is invisible: the pipeline halts, the doc exists, but nothing prompts the developer to look at it.

The failure message when services are down does reference `docs/e2e-startup.md` ("See docs/e2e-startup.md for instructions"). This is present. The gap is that in a non-interactive context, this message may scroll past without the developer noticing. A more prominent signal — such as including the first 10 lines of the startup doc inline in the failure output — would reduce friction.

### Insight 5: Visual validation's integration mandate is stated but not verifiable

The Integration Mandate says "DO NOT create a separate test class for screenshots." But the e2e-runner has no step that verifies this constraint after test generation. If the test generator created `VisualTestSuite.cs`, Step B2 of the e2e-runner would proceed to set up the screenshot helper without noticing that screenshots are in the wrong place. The mandate needs a verification step: after test generation, check whether any file named `*Visual*`, `*Screenshot*`, or `*VisualTest*` exists that is not an existing test file. If found, flag it as a violation and require integration into existing tests.

---

## 6. Facilitative Workflow Patterns Check

### Pattern: Pre-flight checklist before execution

**Present:** Yes — Step 0 (diagnostic scan) and Step 0.5 (mocking audit) are explicit pre-flight steps.
**Gap:** The pre-flight runs once. For a multi-phase pipeline that generates code, a post-generation re-audit is needed. Pre-flight should be a reusable procedure, not a one-time step.

**Enhancement opportunity:** Extract the mocking audit into a named procedure (`AUDIT_MOCKING_VIOLATIONS`) that can be called at two points: before test generation (current position) and immediately after test generation completes (new position). The workflow XML structure supports this — it is currently a step, not a reusable action block.

### Pattern: Fail fast vs. fail soft calibration

**Present:** Fail fast on infrastructure failures (service down → immediate halt). Fail soft on code failures (3-iteration fix loop). This is appropriate.
**Gap:** No discrimination between these two failure types in the E2E fix loop entry point. The orchestrator always enters the fix loop, even when Step A already indicated an infrastructure failure.

**Enhancement opportunity:** Add a check before entering the E2E fix loop: if the failure reason is "Required services not running," halt immediately with the environment-setup message. Only enter the fix loop for code failures (Step C or Step D failures).

### Pattern: Artifact continuity (what gets created persists and is usable)

**Present:** `docs/e2e-startup.md`, `visual-requirements.yaml`, test reports, deferred findings file — all created as persistent artifacts.
**Gap:** The deferred findings file in the epic pipeline accumulates findings from multiple stories and is deleted after the batch fix. If the batch fix fails, the file persists — but there is no mechanism to prevent stale entries from a previous epic run from contaminating the next run.

**Enhancement opportunity:** Prefix each deferred finding entry with the epic number. At the start of each epic run, scan the deferred findings file and remove any entries from a different epic number. This prevents cross-epic contamination.

### Pattern: Scope isolation in automated pipelines

**Present:** Each story in the epic pipeline runs in its own isolated Agent subagent. This is explicitly required and enforced.
**Gap:** The test pipeline's sub-skills (bmad-testarch-atdd, bmad-testarch-automate) do not have scope isolation from each other. If atdd generates tests that reference a fixture, automate may encounter that fixture and interpret it differently.

**Enhancement opportunity:** Pass `--scope {path}` to both sub-skills when the test pipeline is invoked by the epic pipeline with a story scope. The test pipeline already supports `--scope` in its SKILL.md args, but neither workflow.md nor story-processor.md specifies which path to pass. The story's source directory (derived from the story file's "Files Changed" section or from a config-defined source root) would be the appropriate scope.

### Pattern: Human oversight checkpoints

**Present:** In non-yolo mode, the pipeline pauses before each major phase and waits for user confirmation. This is well-designed.
**Gap:** When the test pipeline is invoked by the epic pipeline (which is always in yolo mode), all human oversight is bypassed by design. The E2E phase pause ("make sure your server and database are running, then press Enter") becomes a no-op. This is the moment where the "services not running" failure was originally silent — the human gate that would have caught it was removed by yolo mode.

**Enhancement opportunity:** Distinguish between "user-initiated yolo mode" and "pipeline-invoked yolo mode." When the epic pipeline invokes the test pipeline, pass a flag like `--pipeline-mode` that skips human prompts but retains the service verification step and makes it a hard fail (not a prompt). The current behavior already does this — Step A always hard-fails on missing services regardless of yolo mode. The gap is only that the pause message ("make sure services are running") disappears in yolo mode, which was the user's mental checkpoint. In pipeline mode, this should be replaced with an automated pre-check log line: "[Pre-E2E] Verifying all required services before proceeding in pipeline mode..."

### Pattern: Retrospective as a learning artifact, not a quality gate

**Present:** The retrospective runs after all stories are done and is the final step before marking the epic done.
**Gap:** The retrospective is a documentation skill (bmad-retrospective), not a verification skill. It does not check whether tests pass, whether coverage targets were met, or whether deferred findings were resolved. It documents what happened, but a failed test pipeline result would not prevent the retrospective from completing and the epic from being marked done.

**Enhancement opportunity:** If the test pipeline is integrated into the epic pipeline (Phase B per story), the retrospective should summarize test results: how many stories had test failures, what coverage was achieved, how many deferred test failures remain. This requires passing test pipeline result data to the retrospective agent, which is currently not in the workflow.

---

## Summary of Highest-Priority Enhancement Opportunities

| Priority | Skill | Enhancement | Root cause addressed |
|----------|-------|-------------|----------------------|
| 1 | test-pipeline | Re-run mocking audit after Step 2 (test generation) | Violations introduced by generator were never caught |
| 2 | epic | Add Phase B (test pipeline invocation) in story-processor after dev-story, before code-review | No testing phase in epic pipeline |
| 3 | test-pipeline | Discriminate infrastructure failures from code failures before entering E2E fix loop | Fix loop wasted on environment problems |
| 4 | test-pipeline | Add E2E data seeding step (Step A2) and cleanup step (Step E2) | Data seeding/cleanup systematically forgotten |
| 5 | test-pipeline | Add visual integration check: flag `*Visual*` / `*VisualTest*` files created outside existing tests | VisualTestSuite.cs created as separate class |
| 6 | epic | Pass `high yolo` to test pipeline when invoked from epic pipeline | Coverage level defaults to medium instead of high |
| 7 | test-pipeline | Add service identity verification (not just port check) to Step A | Stub on the expected port passed as "UP" |
| 8 | test-pipeline | Extend mocking violation catalog to include DI-registered fakes by naming convention | Custom fixture classes not caught by keyword search |
