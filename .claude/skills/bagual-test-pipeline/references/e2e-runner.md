# E2E Runner

**Goal:** Run Playwright E2E tests against a fully running stack. Capture browser console logs and server logs. Return a structured pass/fail report to the orchestrator.

**Your Role:** Isolated E2E execution agent. Verify the stack is up, instrument logging, run tests, capture everything. Return results — do NOT fix code.

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

  <!-- ==================== STEP C: Run Playwright E2E Tests ==================== -->
  <step name="C" goal="Execute all E2E tests and collect full results">
    <action>Run Playwright with structured output:
      `npx playwright test --reporter=list,json --output=test-results`

      Capture: exit code, full stdout/stderr, path to JSON results.
    </action>

    <action>Read browser console log file if it was written: `{browser_log_file}`</action>
    <action>Read server log file if available: `{server_log_source}`</action>

    <check if="exit code 0 (all tests passed)">
      <output>
        ## E2E RUNNER RESULT: PASSED

        **Tests:** {passed_count} passed, 0 failed
        **Duration:** {duration}

        All tests executed against real running server (http://localhost:{detected_port}) + database.
        No browser console errors or server errors detected during the run.
      </output>
      <action>Return success to orchestrator</action>
    </check>

    <check if="exit code non-zero (tests failed)">
      <action>Parse JSON results to extract per-test failure details</action>
      <action>Filter browser log for warnings and errors only (console.warn, console.error, pageerror, request_failed)</action>
      <action>Filter server log for ERROR/WARN level lines (if available)</action>

      <output>
        ## E2E RUNNER RESULT: FAILED

        **Tests:** {failed_count} failed, {passed_count} passed
        **Duration:** {duration}
        **Server:** http://localhost:{detected_port} (real — no mocks)

        ---

        ### Test Failures

        {for each failed test:}
        #### FAIL: {test_name}
        - **File:** {test_file}:{line}
        - **Error:** {error_message}
        - **Expected:** {expected_value}
        - **Received:** {received_value}
        {/for}

        ---

        ### Browser Console Errors (captured during failed tests)

        {browser_errors_and_warnings — if empty, write "None captured"}

        ---

        ### Server Log Errors (captured during test run)

        {server_errors_and_warnings — if empty or unavailable, write "Not captured / no log file found"}

        ---

        ### Likely Root Causes

        Correlate browser errors, server errors, and test failures to identify probable root causes.
        List each correlation as:
        - **[Test name]** → likely caused by: [browser error or server error that matches the timing/feature]
      </output>
      <action>Return failure with full structured report to orchestrator</action>
    </check>
  </step>

</workflow>
