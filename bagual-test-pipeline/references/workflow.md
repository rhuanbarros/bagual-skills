# Test Pipeline Workflow

**Goal:** Execute a fully automated, adversarial test pipeline — framework auto-setup, unit/component tests, E2E tests with full log capture, and auto-fix loops until all tests pass.

**Your Role:** Thin pipeline orchestrator. You ask upfront questions, spawn isolated agents per phase, run test commands directly, and produce the final report.
- You spawn subagents to invoke skills (bmad-testarch-framework, bmad-testarch-atdd, bmad-testarch-automate, bmad-quick-dev)
- You run test commands directly via Bash to capture results between skill phases
- You spawn an isolated e2e-runner agent for the E2E phase (reads `references/e2e-runner.md`)
- You DO NOT implement code or fix tests yourself — subagents do that
- Communicate all responses in `{communication_language}`

---

## RULES

- Never HALT for a missing framework — auto-setup instead
- Always ask coverage target upfront if not provided in args (skip if yolo mode)
- Fix loops cap at 3 iterations per phase — HALT with report if still failing after 3
- E2E must run against a real server + database — never accept mocked backends
- Browser console errors and server logs must appear in every E2E failure report
- Never remove or weaken tests to make them pass — always fix the source code

---

## INITIALIZATION

### Configuration Loading

Load config from `{project-root}/_bmad/bmm/config.yaml` and resolve:
- `project_name`, `user_name`
- `communication_language`, `document_output_language`
- `implementation_artifacts`
- `date` as system-generated current datetime

### Paths

- `test_report_file` = `{implementation_artifacts}/test-pipeline-report-{date}.md`
- `e2e_runner_path` = `.claude/skills/bagual-test-pipeline/references/e2e-runner.md`

### Input Parsing

Parse args from invocation:
- Extract `{coverage_target}` if provided (numeric string, e.g. `80` or `100`)
- Detect `yolo` flag for no-confirm mode
- Extract `--scope {path}` if provided

If `{coverage_target}` not provided and NOT in yolo mode, ask the user:
> "What's your target test coverage? (e.g. 80 for critical paths, 100 for full coverage)"

If in yolo mode and no coverage target provided: default to `80`.

---

## EXECUTION

<workflow>
  <critical>Never HALT for a missing framework — auto-setup it via bmad-testarch-framework.</critical>
  <critical>All test generation must include the Adversarial Testing Mandate verbatim in every subagent prompt.</critical>
  <critical>E2E phase requires a real running server + database — halt clearly if not running, never mock.</critical>

  <!-- ==================== STEP 0: Diagnostic Scan ==================== -->
  <step n="0" goal="Scan existing test infrastructure — identify what exists vs. what needs setup">
    <output>
      ============================================================
      TEST PIPELINE — DIAGNOSTIC SCAN
      Project: {project_name}
      ============================================================
    </output>

    <action>Scan {project_root} for existing test infrastructure. Check each item:

      STACK DETECTION (run this first — every subsequent check depends on it)
      Detect project stack by looking for these indicators:
      - .NET/C#: any `*.csproj`, `*.sln`, or `global.json` file; or `dotnet` in any script/Makefile
      - Python: `pytest.ini`, `setup.cfg` with [tool:pytest], `pyproject.toml` with pytest, or `conftest.py`
      - JavaScript/TypeScript: `package.json` at project root
      Set {detected_stack} = "dotnet" | "python" | "js" | "unknown"
      (If multiple match, prefer dotnet > python > js based on primary language of source files)

      FRAMEWORK — check based on {detected_stack}
      - js: `jest.config.*`, `vitest.config.*`, jest/vitest in package.json devDependencies; E2E: `playwright.config.*`, `cypress.config.*`, @playwright/test or cypress in devDependencies
      - dotnet: `*.Test.csproj`, `*Tests.csproj`, or xUnit/NUnit/MSTest in any .csproj `<PackageReference>`; E2E: `Microsoft.Playwright` in any .csproj
      - python: `pytest.ini`, `conftest.py`, or pytest in requirements.txt/pyproject.toml; E2E: `playwright` in requirements.txt/pyproject.toml

      UNIT TESTS — check based on {detected_stack}
      - js: Test files `**/*.test.*`, `**/*.spec.*` (exclude node_modules, dist, e2e dirs) — count them; Coverage: `c8`, `istanbul`, `nyc`, or coverage section in vitest/jest config; Report: `coverage/coverage-summary.json` or `coverage/lcov.info`
      - dotnet: Test files `**/*Tests.cs`, `**/*Test.cs` (exclude obj, bin) — count them; Coverage: Coverlet in any .csproj `<PackageReference>`; Report: `coverage/coverage.cobertura.xml` or `TestResults/*.xml`
      - python: Test files `**/test_*.py`, `**/*_test.py` — count them; Coverage: pytest-cov in requirements; Report: `htmlcov/index.html` or `.coverage`

      E2E TESTS — check based on {detected_stack}
      - js: Test files in `tests/e2e/**/*`, `e2e/**/*`, `playwright/**/*` — count them; Console capture: `page.on('console'` in any test file; Server log references in test files
      - dotnet: Test files matching E2E pattern (PlaywrightFixture, IPage usage) in any `*Tests.cs` — count them; Console capture: `page.Console +=` or `Page.Console +=` in any test file
      - python: Test files using `async_playwright` or `page.goto` — count them; Console capture: `page.on("console"` in any test file

      VISUAL VALIDATION — check based on {detected_stack}
      - js: Screenshot helper `tests/e2e/helpers/screenshot.*` or `captureScreenshot` in any test file
      - dotnet: Screenshot helper `Tests/E2E/Helpers/ScreenshotHelper.cs` or `ScreenshotHelper.CaptureAsync` in any test file; also check `page.ScreenshotAsync` calls with explicit path parameters
      - python: Screenshot helper `tests/e2e/helpers/screenshot.py` or `capture_screenshot` in any test file
      - All stacks: `{project_root}/visual-requirements.yaml`

      OTHER
      - CI config: `.github/workflows/*.yml`, `.gitlab-ci.yml`, `Jenkinsfile`
    </action>

    <action>Build the diagnostic state: for each item, record FOUND / MISSING / PARTIAL with details.</action>

    <output>
      ## Test Infrastructure Diagnostic

      ### Stack
      - Detected stack: {detected_stack} (dotnet | python | js | unknown)

      ### Framework
      - Unit/component framework: {FOUND: "xUnit" / "vitest" / "pytest" / MISSING: "not detected"}
      - E2E framework (Playwright): {FOUND / MISSING}

      ### Unit Tests
      - Test files: {N} found {in paths, or "none found"}
      - Coverage config: {FOUND / MISSING}
      - Current coverage: {X% from report / "not measured yet"}

      ### E2E Tests
      - Test files: {N} found {in paths, or "none found"}
      - Browser console capture: {FOUND: "log-capture fixture detected" / MISSING}
      - Server log capture: {FOUND / MISSING}

      ### Visual Validation
      - Screenshot helper: {FOUND / MISSING}
      - visual-requirements.yaml: {FOUND: "{N} entries" / MISSING}

      ### CI/CD
      - CI pipeline: {FOUND: "GitHub Actions" / MISSING}

      ---
      **Stack:** {detected_stack}
      **Items to configure:** {list of MISSING items, or "none — project is fully configured"}
      **Items already in place:** {list of FOUND items}
    </output>

    <check if="NOT yolo mode">
      <check if="no MISSING items found">
        <output>All test infrastructure is already configured. Proceeding to run tests.</output>
      </check>

      <check if="MISSING items exist">
        <output>
          How would you like to proceed?

          [1] Auto-configure all missing pieces and run the full pipeline
          [2] Auto-configure missing pieces, but pause before each test run for review
          [3] Diagnostic only — I'll configure manually and run the pipeline later

          Choice:
        </output>
        <action>Wait for user response. Store as {proceed_mode}:
          - [1] → {proceed_mode} = "auto"
          - [2] → {proceed_mode} = "step"
          - [3] → HALT. Output: "Diagnostic complete. Run /bagual-test-pipeline when ready."
          - Default (no response / unclear) → {proceed_mode} = "auto"
        </action>
      </check>
    </check>

    <check if="yolo mode">
      <output>[Step 0] YOLO mode — proceeding automatically.</output>
      <action>Set {proceed_mode} = "auto"</action>
    </check>
  </step>

  <!-- ==================== STEP 1: Framework Check ==================== -->
  <step n="1" goal="Ensure test framework is installed — auto-install if missing (uses diagnostic findings from Step 0)">
    <output>
      ============================================================
      TEST PIPELINE STARTING
      Project: {project_name} | Coverage target: {coverage_target}%
      ============================================================
    </output>

    <check if="framework was FOUND in Step 0 diagnostic">
      <output>[Step 1] Test framework already configured. Proceeding.</output>
    </check>

    <check if="framework was MISSING in Step 0 diagnostic">
      <output>[Step 1] No test framework detected. Auto-installing via bmad-testarch-framework...</output>

      <action>Spawn an Agent subagent with this prompt:
        "Run the skill /bmad-testarch-framework.
         This is running inside an automated pipeline. Auto-approve all checkpoints.
         Do not ask for user input — proceed automatically with sensible defaults.
         Detected project stack: {detected_stack}.
         Goal: install Playwright for E2E and configure a unit test framework appropriate for the project stack.
         - If dotnet: use Microsoft.Playwright and xUnit/NUnit as appropriate; run via dotnet test
         - If python: use pytest-playwright; run via pytest
         - If js: use @playwright/test and vitest or jest; run via npx"
      </action>

      <check if="Agent failed">
        <output>
          PIPELINE HALTED: Framework auto-setup failed.
          Error: {error_description}
          Fix the framework issue manually, then re-run: /bagual-test-pipeline {coverage_target}
        </output>
        <action>HALT</action>
      </check>

      <output>[Step 1] Framework installed successfully.</output>
    </check>

    <check if="{proceed_mode} == 'step'">
      <output>
        [Step 1] Framework ready. Pausing before test generation — press Enter to continue with Step 2 (unit test generation).
      </output>
      <action>Wait for user confirmation before proceeding.</action>
    </check>
  </step>

  <!-- ==================== STEP 2: Generate Adversarial Unit/Component Tests ==================== -->
  <step n="2" goal="Generate adversarial unit/component tests via bmad-testarch-atdd + bmad-testarch-automate">
    <output>[Step 2] Generating adversarial unit/component tests (target: {coverage_target}%)...</output>

    <action>Spawn an Agent subagent with this prompt:
      "Run the skill /bmad-testarch-atdd.
       This is running inside an automated pipeline. Auto-approve all checkpoints.
       Do not ask for user input — proceed automatically.

       *** ADVERSARIAL TESTING MANDATE — NON-NEGOTIABLE ***
       - Tests must DISCOVER bugs, not confirm existing behavior
       - Test what the code *intended* to do, not what it currently does
       - Every button, filter, CRUD operation, form field, navigation action must be covered
       - Test valid inputs AND invalid inputs AND boundary conditions AND error states
       - No 'element exists' or 'component renders' assertions — every test must verify
         functional behavior: correct data returned, correct state change, correct error shown
       - Create complete test data and fixtures — never rely on pre-existing data in the environment
       - Coverage target: {coverage_target}%
       - If coverage will be below {coverage_target}%, output a COVERAGE GAP REPORT listing
         exactly what is NOT covered before proceeding — do not silently skip features
       *** END MANDATE ***"
    </action>

    <check if="Agent failed">
      <output>
        PIPELINE HALTED at Step 2 (ATDD generation).
        Error: {error_description}
      </output>
      <action>HALT</action>
    </check>

    <action>Spawn an Agent subagent with this prompt:
      "Run the skill /bmad-testarch-automate.
       This is running inside an automated pipeline. Auto-approve all checkpoints.
       Do not ask for user input — proceed automatically. Use standalone mode.

       *** ADVERSARIAL TESTING MANDATE — NON-NEGOTIABLE ***
       - Expand coverage to fill all gaps left by the ATDD phase
       - Every feature, code path, and component not yet covered must be covered now
       - Test valid inputs AND invalid inputs AND boundary conditions AND error states
       - No 'element exists' assertions — verify functional behavior
       - Coverage target: {coverage_target}%
       - Output a COVERAGE GAP REPORT for anything remaining below {coverage_target}%
       *** END MANDATE ***"
    </action>

    <check if="Agent failed">
      <output>[Step 2] WARNING: Test automation expansion failed. Continuing with tests from ATDD phase.</output>
    </check>

    <output>[Step 2] Test generation complete.</output>
  </step>

  <!-- ==================== STEP 3: Run Unit Tests — Fix Loop ==================== -->
  <step n="3" goal="Run unit/component tests with auto-fix loop (max 3 iterations)">
    <check if="{proceed_mode} == 'step'">
      <output>
        [Step 3] Tests generated. Pausing before running unit tests — press Enter to continue.
      </output>
      <action>Wait for user confirmation before proceeding.</action>
    </check>

    <action>Set {unit_fix_iteration} = 0</action>
    <action>Set {unit_tests_passing} = false</action>
    <action>Set {unit_test_output} = ""</action>

    <loop while="{unit_fix_iteration} less than 3 AND {unit_tests_passing} == false">
      <action>Increment {unit_fix_iteration} by 1</action>
      <output>[Step 3] Running unit tests — iteration {unit_fix_iteration}/3...</output>

      <action>Detect and run the project's unit test command based on {detected_stack}:
        - dotnet: `dotnet test --logger "console;verbosity=detailed" /p:CollectCoverage=true /p:CoverletOutputFormat=cobertura`
          (if Coverlet not installed, run `dotnet test --logger "console;verbosity=detailed"` without coverage flags)
        - python: `pytest --tb=short -v --cov=. --cov-report=term-missing`
          (if pytest-cov not installed, run `pytest --tb=short -v` without coverage flags)
        - js: Check `package.json` scripts for `test`, `test:unit`, `test:coverage`; prefer commands with coverage (e.g. `npx vitest run --coverage`, `npx jest --coverage`)
        - unknown: Try each in order: dotnet test → pytest → npx vitest run → npx jest
        Run the command and capture: exit code, full stdout/stderr, coverage summary.
        Store full output as {unit_test_output}.
      </action>

      <check if="exit code 0 AND (no coverage threshold configured OR actual coverage >= {coverage_target})">
        <action>Set {unit_tests_passing} = true</action>
        <output>[Step 3] Unit tests PASSED (iteration {unit_fix_iteration}).</output>
      </check>

      <check if="tests failing OR coverage below {coverage_target} AND {unit_fix_iteration} less than 3 AND {unit_tests_passing} == false">
        <output>[Step 3] Failures detected. Spawning bmad-quick-dev fix attempt {unit_fix_iteration}...</output>

        <action>Spawn an Agent subagent with this prompt:
          "Run the skill /bmad-quick-dev with the following intent:

          Fix failing unit/component tests. Full test run output:

          ---
          {unit_test_output}
          ---

          Fix rules (all mandatory):
          - Fix the SOURCE CODE to make the functionality correct — never weaken tests
          - If a test assertion is wrong (testing incorrect behavior), fix both the test AND the source
          - Do NOT remove tests, skip tests, or comment them out to make them pass
          - Do NOT mock things that should be tested for real
          - Do NOT lower coverage thresholds in config
          - Coverage target is {coverage_target}% — add missing tests if needed

          This is running inside an automated pipeline. Auto-approve all checkpoints.
          Do not ask for user input — proceed automatically."
        </action>
      </check>
    </loop>

    <check if="{unit_tests_passing} == false AND {unit_fix_iteration} >= 3">
      <action>Write failure summary to {test_report_file}:
        # Test Pipeline — HALTED: Unit Tests

        **Date:** {date}
        **Project:** {project_name}
        **Coverage target:** {coverage_target}%

        ## Status: FAILED after 3 fix iterations

        ## Last Test Run Output
        {unit_test_output}
      </action>
      <output>
        PIPELINE HALTED: Unit tests still failing after 3 fix iterations.
        Report saved to: {test_report_file}
        Re-run after manual resolution: /bagual-test-pipeline {coverage_target}
      </output>
      <action>HALT</action>
    </check>
  </step>

  <!-- ==================== STEP 4: E2E Phase (isolated runner) ==================== -->
  <step n="4" goal="Run full-stack E2E tests with browser + server log capture">
    <check if="{proceed_mode} == 'step'">
      <output>
        [Step 4] Unit tests passed. Pausing before E2E phase — make sure your server and database are running, then press Enter to continue.
      </output>
      <action>Wait for user confirmation before proceeding.</action>
    </check>

    <output>[Step 4] Starting E2E phase — server + database must be running...</output>
    <action>Set {e2e_tests_passing} = false</action>
    <action>Set {e2e_failure_report} = ""</action>

    <action>Spawn an isolated Agent subagent with this prompt:
      "You are an E2E test runner agent. Read and follow ALL instructions in the file: {e2e_runner_path}

      Input values:
      - project_root: {project-root}
      - coverage_target: {coverage_target}
      - config_path: {project-root}/_bmad/bmm/config.yaml
      - date: {date}
      - detected_stack: {detected_stack}

      This is running inside an automated pipeline. Auto-approve all checkpoints.
      Do not ask for user input — proceed automatically.

      Return your result as a structured block starting with either:
        ## E2E RUNNER RESULT: PASSED
      or:
        ## E2E RUNNER RESULT: FAILED"
    </action>

    <check if="Agent output contains 'E2E RUNNER RESULT: PASSED'">
      <action>Set {e2e_tests_passing} = true</action>
      <output>[Step 4] E2E tests PASSED.</output>
    </check>

    <check if="Agent output contains 'E2E RUNNER RESULT: FAILED' OR Agent failed">
      <action>Store full agent output as {e2e_failure_report}</action>
      <output>[Step 4] E2E failures detected. Entering E2E fix loop...</output>
    </check>
  </step>

  <!-- ==================== STEP 5: E2E Fix Loop ==================== -->
  <step n="5" goal="E2E auto-fix loop (max 3 iterations)">
    <action>Set {e2e_fix_iteration} = 0</action>

    <loop while="{e2e_fix_iteration} less than 3 AND {e2e_tests_passing} == false">
      <action>Increment {e2e_fix_iteration} by 1</action>
      <output>[Step 5] E2E fix iteration {e2e_fix_iteration}/3...</output>

      <action>Spawn an Agent subagent with this prompt:
        "Run the skill /bmad-quick-dev with the following intent:

        Fix failing E2E tests. Full failure report (includes browser console logs and server logs):

        ---
        {e2e_failure_report}
        ---

        Fix rules (all mandatory):
        - Fix the SOURCE CODE to make the feature work correctly — never weaken E2E tests
        - Do NOT mock the backend, database, or API responses
        - Do NOT remove or skip E2E tests
        - Browser console errors (pageerror, console.error) indicate real bugs — fix them
        - Server log errors indicate real bugs — fix them
        - Pay attention to BOTH test assertion failures AND the captured error logs
        - The fix must work against a real running server + database

        This is running inside an automated pipeline. Auto-approve all checkpoints.
        Do not ask for user input — proceed automatically."
      </action>

      <output>[Step 5] Fix applied. Re-running E2E tests...</output>

      <action>Spawn an isolated Agent subagent with this prompt:
        "You are an E2E test runner agent. Read and follow ALL instructions in: {e2e_runner_path}

        Input values:
        - project_root: {project-root}
        - coverage_target: {coverage_target}
        - config_path: {project-root}/_bmad/bmm/config.yaml
        - date: {date}
        - detected_stack: {detected_stack}

        This is running inside an automated pipeline. Proceed automatically.
        Return your result starting with 'E2E RUNNER RESULT: PASSED' or 'E2E RUNNER RESULT: FAILED'."
      </action>

      <check if="Agent output contains 'E2E RUNNER RESULT: PASSED'">
        <action>Set {e2e_tests_passing} = true</action>
        <output>[Step 5] E2E tests PASSED after {e2e_fix_iteration} fix iteration(s).</output>
      </check>

      <check if="Agent output contains 'E2E RUNNER RESULT: FAILED' OR Agent failed">
        <action>Update {e2e_failure_report} with latest agent output</action>
      </check>
    </loop>

    <check if="{e2e_tests_passing} == false AND {e2e_fix_iteration} >= 3">
      <action>Write failure summary to {test_report_file}:
        # Test Pipeline — HALTED: E2E Tests

        **Date:** {date}
        **Project:** {project_name}

        ## Status: FAILED after 3 E2E fix iterations

        ## Unit Tests
        PASSED (completed before E2E phase)

        ## E2E Failure Report (last run)
        {e2e_failure_report}
      </action>
      <output>
        PIPELINE HALTED: E2E tests still failing after 3 fix iterations.
        Report saved to: {test_report_file}
        Re-run after manual resolution: /bagual-test-pipeline {coverage_target}
      </output>
      <action>HALT</action>
    </check>
  </step>

  <!-- ==================== STEP 6: Report + Commit ==================== -->
  <step n="6" goal="Write final report and commit all test artifacts">
    <output>[Step 6] All tests passing. Writing report and committing...</output>

    <action>Write {test_report_file}:
      # Test Pipeline Report — {project_name} — {date}

      ## Summary
      | Phase            | Status | Fix Iterations Used |
      |------------------|--------|---------------------|
      | Unit/Component   | PASSED | {unit_fix_iteration} / 3 |
      | E2E (full stack) | PASSED | {e2e_fix_iteration} / 3  |

      **Coverage target:** {coverage_target}%

      ## What Was Tested
      All tests generated with the Adversarial Testing Mandate:
      - Functional behavior verified (not just element existence)
      - Valid inputs, invalid inputs, boundary conditions, error states
      - Complete test fixtures and data factories created
      - Full-stack E2E: server + database running throughout

      ## Coverage Gaps Reported
      (Any COVERAGE GAP REPORTs from Step 2 agents)

      ## E2E Log Summary
      Browser console and server logs captured — no errors in passing run.
    </action>

    <action>Stage test files, fixtures, and report. Avoid staging .env or credentials.</action>
    <action>Run: git commit using a HEREDOC:
      test: adversarial test suite — {coverage_target}% target, full-stack E2E passing

      Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
    </action>

    <check if="git commit failed">
      <output>WARNING: Git commit failed (pre-commit hook or no changes staged). Tests are passing — commit manually if needed.</output>
    </check>

    <output>
      ============================================================
      TEST PIPELINE COMPLETE

      Unit/Component tests: PASSED
      E2E tests: PASSED (full stack — server + database)
      Report: {test_report_file}
      ============================================================
    </output>
  </step>

</workflow>
