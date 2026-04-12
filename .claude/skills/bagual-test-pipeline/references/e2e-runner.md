# E2E Runner

**Goal:** Run Playwright E2E tests against a fully running stack. Capture browser console logs and server logs. Run visual validation inline using built-in vision. Return a structured pass/fail report to the orchestrator.

**Your Role:** Isolated E2E execution agent. Verify the stack is up, instrument logging, run tests, capture everything, evaluate screenshots. Return results — do NOT fix code.

---

## INPUTS

Received from orchestrator:
- `{project_root}` — project root directory
- `{coverage_target}` — coverage target percentage
- `{config_path}` — path to `{project-root}/_bmad/bmm/config.yaml`
- `{date}` — current datetime string

Derived:
- `{browser_log_file}` = `{project_root}/test-results/browser-console-{date}.log`
- `{server_log_file}` = `{project_root}/test-results/server-{date}.log`
- `{screenshots_dir}` = `{project_root}/test-artifacts/screenshots`
- `{visual_report}` = `{project_root}/_bmad-output/test-artifacts/visual-validation/latest.json`
- `{visual_validation_enabled}` = true if frontend project detected and not explicitly disabled

---

## EXECUTION

<workflow>

  <!-- ==================== STEP A: Verify Server Running ==================== -->
  <step name="A" goal="Confirm server and database are reachable before running any tests">
    <action>Detect the server port:
      - Read `playwright.config.ts` or `playwright.config.js` for `baseURL`
      - Read `package.json` scripts for port hints (--port, PORT=)
      - Read `.env`, `.env.test`, or `.env.local` for PORT or API_URL
      - Default to 3000 if undetermined
    </action>

    <action>Run health check: attempt GET to each until one responds (max 3s timeout each):
      1. `http://localhost:{detected_port}/health`
      2. `http://localhost:{detected_port}/api/health`
      3. `http://localhost:{detected_port}/`
    </action>

    <check if="all health checks fail (no response or connection refused)">
      <output>
        ## E2E RUNNER RESULT: FAILED

        ### Reason: Server not running

        The server is not responding on port {detected_port}.

        E2E tests require a real running server and database — no mocking allowed.

        **Start the full stack before running the pipeline:**
        - Server: `npm run dev` / `yarn dev` / `python manage.py runserver` / etc.
        - Database: ensure your DB service is running and migrations are applied

        Then re-run: /bagual-test-pipeline {coverage_target}
      </output>
      <action>HALT and return failure to orchestrator</action>
    </check>

    <output>[E2E Step A] Server confirmed running at http://localhost:{detected_port}</output>
  </step>

  <!-- ==================== STEP B: Set Up Log Capture ==================== -->
  <step name="B" goal="Instrument browser console capture and server log capture">
    <action>Ensure `{project_root}/test-results/` directory exists (create if needed)</action>

    <action>Check if Playwright already has a fixture or global setup that captures browser console logs.
      Look for: `page.on('console'`, `page.on('pageerror'` in existing test fixtures or `global-setup.ts`.
    </action>

    <check if="no console capture fixture found">
      <action>Create `{project_root}/tests/fixtures/log-capture.ts` (or `.js` if the project uses JS):

        ```typescript
        import { test as base } from '@playwright/test';

        type ConsoleLogs = { logs: string[] };

        export const test = base.extend<ConsoleLogs>({
          logs: async ({}, use) => {
            await use([]);
          },
          page: async ({ page, logs }, use, testInfo) => {
            page.on('console', msg => {
              const level = msg.type();
              const text = msg.text();
              logs.push(`[${level.toUpperCase()}] ${text}`);
            });
            page.on('pageerror', err => {
              logs.push(`[PAGEERROR] ${err.message}\n${err.stack ?? ''}`);
            });
            page.on('requestfailed', req => {
              logs.push(`[REQUEST_FAILED] ${req.method()} ${req.url()} — ${req.failure()?.errorText}`);
            });

            await use(page);

            // On failure: attach logs to test report and write to file
            if (testInfo.status !== testInfo.expectedStatus) {
              const logContent = logs.join('\n');
              await testInfo.attach('browser-console', {
                body: logContent,
                contentType: 'text/plain',
              });
              // Append to shared log file
              const fs = await import('fs');
              fs.appendFileSync(
                '{browser_log_file}',
                `\n=== ${testInfo.title} ===\n${logContent}\n`
              );
            }
          },
        });

        export { expect } from '@playwright/test';
        ```

        Update existing E2E test files to import from this fixture instead of `@playwright/test`
        where the `page` fixture is used.
      </action>
    </check>

    <action>Set up server log capture (best effort):
      - Check if the project writes logs to a file (e.g. `logs/app.log`, `server.log`)
      - If a log file exists: note its path as `{server_log_source}`
      - If the server was started by Playwright's `webServer` config: logs go to test output automatically
      - If neither: note "server logs captured via test output only"
    </action>

    <output>[E2E Step B] Log capture configured. Browser: fixture installed. Server: {server_log_capture_method}</output>
  </step>

  <!-- ==================== STEP B2: Set Up Visual Validation ==================== -->
  <step name="B2" goal="Determine if visual validation applies, set up screenshot helper, generate semantic requirements">

    <!-- ── Activation decision ───────────────────────────────────────────── -->
    <action>Load the full reference from:
      `.claude/skills/bagual-test-pipeline/references/visual-validation.md`
    </action>

    <action>Check `VISUAL_VALIDATION_ENABLED` in `.env`, `.env.local`, `.env.test`:
      - If explicitly `false` → set {visual_validation_enabled} = false
      - Otherwise: detect if this is a frontend project:
          Scan {project_root} for any of: `package.json` with react/vue/angular/next/svelte/vite in dependencies,
          `playwright.config.*`, `next.config.*`, `vite.config.*`, `angular.json`
      - If frontend indicators found → set {visual_validation_enabled} = true (default on)
      - If backend-only (none of the above) and no explicit true → set {visual_validation_enabled} = false
    </action>

    <check if="{visual_validation_enabled} == false">
      <output>[E2E Step B2] Visual validation not applicable (backend-only project or explicitly disabled). Skipping.</output>
    </check>

    <check if="{visual_validation_enabled} == true">

      <!-- ── Screenshot helper ──────────────────────────────────────────── -->
      <action>Check if screenshot helper exists:
        Look for `tests/e2e/helpers/screenshot.*` or `captureScreenshot` in any test file.
      </action>

      <check if="helper not found">
        <action>Create the screenshot helper adapted to the project's language and framework.
          Follow File 1 in visual-validation.md. Core contract:
          - normalize name → save PNG to `test-artifacts/screenshots/{name}.png`
          - call AFTER assertions confirm the UI state is stable
          Save to `{project_root}/tests/e2e/helpers/screenshot.{ext}`.
        </action>
      </check>

      <!-- ── visual-requirements.yaml — generate with semantic rules ────── -->
      <action>Check if `{project_root}/visual-requirements.yaml` exists.</action>

      <check if="file does not exist OR file exists but has only placeholder comments">
        <action>Generate `{project_root}/visual-requirements.yaml` with real semantic requirements:

          For EACH `captureScreenshot(page, '{name}')` call found in E2E test files:

          1. Read the surrounding test code (the full test function or describe block)
          2. Identify the app state at the moment of capture:
             - Which user actions were performed just before? (clicks, form fills, filters applied)
             - What fixture data or test data was set up? (what counts, what statuses, what values)
             - What UI state should be active? (which tab, which filter, which page, etc.)
             - What numbers or totals should be visible on screen?
          3. Generate BOTH types of requirements:
             - LAYOUT: alignment, overflow, spacing, no overlapping elements
             - SEMANTIC: data displayed must match the app state
               Focus on: active filter → list must be filtered; count shown = items visible;
               empty state shown ↔ list actually empty; totals match row data;
               selected/active indicators match actual selection state

          Write each entry in visual-requirements.yaml with specific, verifiable rules.
          Generic rules like "elements are aligned" are insufficient — be precise.

          For screens without detailed test context, write the best rules possible
          and add a comment: `# TODO: refine these requirements after reviewing the screen`
        </action>

        <output>[E2E Step B2] visual-requirements.yaml generated with layout + semantic requirements for {screenshot_count} screenshots.</output>
      </check>

      <check if="file exists and has real content">
        <action>Scan E2E test files for any `captureScreenshot()` calls whose name is NOT yet in visual-requirements.yaml.
          For each new name found, append an entry using the same analysis process above.
        </action>
        <output>[E2E Step B2] visual-requirements.yaml updated with {new_count} new entries.</output>
      </check>

      <output>[E2E Step B2] Visual validation ready — screenshot helper and requirements in place. Validation will run inline after E2E tests.</output>
    </check>
  </step>

  <!-- ==================== STEP C: Run Playwright E2E Tests ==================== -->
  <step name="C" goal="Execute all E2E tests and collect full results">
    <action>Run Playwright with structured output:
      `npx playwright test --reporter=list,json --output=test-results`

      Capture: exit code, full stdout/stderr, path to JSON results.
    </action>

    <action>Read browser console log file if it was written: `{browser_log_file}`</action>
    <action>Read server log file if available: `{server_log_source}`</action>

    <action>Store {playwright_exit_code}, {playwright_output}, {passed_count}, {failed_count}, {duration}</action>
  </step>

  <!-- ==================== STEP D: Visual Validation (inline) ==================== -->
  <step name="D" goal="Evaluate captured screenshots inline using built-in vision — no external API required">
    <check if="{visual_validation_enabled} == false">
      <output>[E2E Step D] Visual validation disabled. Skipping.</output>
      <action>Set {visual_failures} = [] and {visual_passed} = true</action>
    </check>

    <check if="{visual_validation_enabled} == true">
      <output>[E2E Step D] Running inline visual validation on captured screenshots...</output>

      <action>List all PNG files in `{screenshots_dir}` (test-artifacts/screenshots/).
        If directory is empty or does not exist:
          Set {visual_failures} = [] and {visual_passed} = true
          Output: "[E2E Step D] No screenshots captured. Skipping visual validation."
          Skip the rest of this step.
      </action>

      <action>Read `{project_root}/visual-requirements.yaml` to load all requirements.</action>

      <action>For EACH PNG file found:
        1. Read the PNG file using the Read tool (built-in vision) — the file will render visually
        2. Look up requirements for this screenshot by matching the filename (without .png) to a key in visual-requirements.yaml
        3. If no requirements found for this name: mark as passed with note "no requirements defined"
        4. Evaluate the image against ALL requirements for this screenshot:
           - LAYOUT checks: alignment, overflow, spacing, no overlapping elements
           - SEMANTIC checks: does the displayed data match the expected app state?
             (active filter visually highlighted, count matches visible items, etc.)
        5. Record result:
           - passed: true/false
           - issues: specific description of each violation found (empty if passed)

        Be strict. A requirement is failed if there is any reasonable doubt it is not satisfied.
        Generic layout issues (slightly off-center) are warnings, not failures.
        Semantic data inconsistencies (filter selected but list unfiltered) are always failures.
      </action>

      <action>Compile results into {visual_results} list:
        Each entry: { screenshot: "filename.png", passed: bool, issues: "..." }
      </action>

      <action>Write `{visual_report}` (latest.json):
        {
          "totalScreenshots": N,
          "passedCount": X,
          "failedCount": Y,
          "generatedAt": "{date}",
          "results": [ ... {visual_results} ... ]
        }
        Create parent directories if they don't exist.
      </action>

      <check if="failedCount == 0">
        <action>Set {visual_passed} = true and {visual_failures} = []</action>
        <output>[E2E Step D] Visual validation: all {totalScreenshots} screenshot(s) passed.</output>
      </check>

      <check if="failedCount > 0">
        <action>Set {visual_passed} = false</action>
        <action>Set {visual_failures} = list of { screenshot, issues } for each failed result</action>
        <output>[E2E Step D] Visual validation: {failedCount} screenshot(s) failed.</output>
      </check>
    </check>
  </step>

  <!-- ==================== STEP E: Return Results ==================== -->
  <step name="E" goal="Combine all results and return structured report to orchestrator">
    <action>Determine overall result:
      - PASSED only if: playwright_exit_code == 0 AND visual_passed == true
      - FAILED if: playwright_exit_code != 0 OR visual_passed == false
    </action>

    <check if="overall result is PASSED">
      <output>
        ## E2E RUNNER RESULT: PASSED

        **Tests:** {passed_count} passed, 0 failed
        **Duration:** {duration}
        **Visual Validation:** {if visual_validation_enabled: "PASSED — all screenshots match requirements" else: "disabled"}
        **Server:** http://localhost:{detected_port} (real — no mocks)
      </output>
      <action>Return success to orchestrator</action>
    </check>

    <check if="overall result is FAILED">
      <action>Filter browser log for warnings and errors only (console.warn, console.error, pageerror, request_failed)</action>
      <action>Filter server log for ERROR/WARN level lines (if available)</action>

      <output>
        ## E2E RUNNER RESULT: FAILED

        **Tests:** {failed_count} failed, {passed_count} passed
        **Visual Failures:** {visual_failures count} screenshot(s) failed visual validation
        **Duration:** {duration}
        **Server:** http://localhost:{detected_port} (real — no mocks)

        ---

        ### Test Failures

        {for each failed playwright test:}
        #### FAIL: {test_name}
        - **File:** {test_file}:{line}
        - **Error:** {error_message}
        - **Expected:** {expected_value}
        - **Received:** {received_value}
        {/for}

        ---

        ### Visual Validation Failures

        {if visual_validation_enabled and visual_failures not empty:}
        {for each failed screenshot:}
        #### VISUAL FAIL: {screenshot}
        - **Issues:** {issues}
        {/for}
        {else: "Visual validation disabled or no screenshots captured."}

        ---

        ### Browser Console Errors (captured during failed tests)

        {browser_errors_and_warnings — if empty, write "None captured"}

        ---

        ### Server Log Errors (captured during test run)

        {server_errors_and_warnings — if empty or unavailable, write "Not captured / no log file found"}

        ---

        ### Likely Root Causes

        Correlate test failures, visual failures, browser errors, and server errors.
        List each correlation as:
        - **[Failure name]** → likely caused by: [matching browser error, server error, or visual issue]
      </output>
      <action>Return failure with full structured report to orchestrator</action>
    </check>
  </step>

</workflow>
