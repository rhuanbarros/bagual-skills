# E2E Runner

**Goal:** Run Playwright E2E tests against a fully running stack. Capture browser console logs and server logs. Run visual validation inline using built-in vision. Return a structured pass/fail report to the orchestrator.

**Your Role:** Isolated E2E execution agent. Verify the stack is up, instrument logging, run tests, capture everything, evaluate screenshots. Return results — do NOT fix code.

---

## E2E ANTI-PATTERNS MANDATE — NON-NEGOTIABLE

Any of the following found in an E2E test is a **blocker** that must be reported and cannot be tolerated:

| Pattern | Why it's wrong |
|---------|----------------|
| HTTP stub listeners / fake servers replacing real services | Hides real integration failures. The stub passes when the real API would fail. |
| In-memory database replacing real DB | Schema diffs, type coercions, and constraint violations only appear with the real DB. |
| "Accept error as valid outcome" (`assert success OR error`) | Makes the test always pass regardless of system state. Provides zero quality signal. |
| Silent skip when service unavailable | Masks infrastructure problems. CI appears green while the system is broken. |
| `try/catch` swallowing connection errors in setup | Same as silent skip — test runs as if services are up when they're not. |
| `[Ignore]` / `pytest.mark.skip` / `.skip()` on E2E tests | E2E tests must run. If a service is missing, fix the environment, not the test. |

**The rule:** E2E tests must FAIL LOUDLY and IMMEDIATELY if any required service is not running.
A test that passes without all services running is not a test — it is a false guarantee.

---

---

## INPUTS

Received from orchestrator:
- `{project_root}` — project root directory
- `{coverage_target}` — coverage target percentage
- `{config_path}` — path to `{project-root}/_bmad/bmm/config.yaml`
- `{date}` — current datetime string
- `{detected_stack}` — project stack: "dotnet" | "python" | "js" | "unknown" (detected by orchestrator in Step 0)

Derived:
- `{browser_log_file}` = `{project_root}/test-results/browser-console-{date}.log`
- `{browser_log_dir}` = `{project_root}/test-results`
- `{server_log_file}` = `{project_root}/test-results/server-{date}.log`
- `{screenshots_dir}` = `{project_root}/test-artifacts/screenshots`
- `{visual_report}` = `{project_root}/_bmad-output/test-artifacts/visual-validation/latest.json`
- `{visual_validation_enabled}` = true if frontend project detected and not explicitly disabled
- `{services_manifest}` = list of all required services with their expected ports and check status (built during Step A)

---

## EXECUTION

<workflow>

  <!-- ==================== STEP A: Verify All Required Services ==================== -->
  <step name="A" goal="Confirm ALL required services are reachable before running any tests — fail loudly if any are missing">

    <action>
      *** SERVICE VERIFICATION MANDATE ***
      E2E tests require ALL services to be running. A missing service is not a reason to skip or mock —
      it is a blocker that must cause immediate failure with a clear, actionable message.
      Never proceed if any required service is down.
      *** END MANDATE ***
    </action>

    <!-- ── 1. Discover required services ──────────────────────────────────────── -->
    <action>Discover all services this project needs by reading:
      - Config files: `appsettings.json`, `appsettings.Development.json`, `.env`, `.env.test`, `.env.local`
      - Connection strings: look for `ConnectionStrings`, `DATABASE_URL`, `REDIS_URL`, `RABBITMQ_URL`, etc.
      - External API base URLs: look for `AiService:BaseUrl`, `AI_API_URL`, `EXTERNAL_API_URL`, etc. — any HTTP endpoint the app calls
      - Playwright/test config: `baseURL`, `webServer` config

      Build a {required_services} list. For each service record:
      - name (e.g. "Web App (.NET)", "PostgreSQL", "Python AI API", "Redis")
      - expected host:port
      - check URL or TCP check
      - whether it is the web app, a database, or an external API
    </action>

    <!-- ── 2. Check for startup script ────────────────────────────────────────── -->
    <action>Check if a startup script exists:
      Look for: `start-all.sh`, `start-services.sh`, `docker-compose.yml`, `docker-compose.test.yml`,
      `Makefile` with a `start` or `run` target, `scripts/start.sh`, `run.sh`
    </action>

    <check if="no startup script found">
      <action>Create a startup reference file at `{project_root}/docs/e2e-startup.md` (or append to existing):
        # E2E Test — Required Services

        Before running E2E tests, ensure ALL of the following services are running:

        {for each required_service:}
        ## {service.name}
        - **Port:** {service.port}
        - **How to start:** {best-effort instruction based on project config}
        {/for}

        Tip: Create a `start-e2e-services.sh` script to start all services at once.
      </action>
      <output>[E2E Step A] No startup script found. Created docs/e2e-startup.md with service list.</output>
    </check>

    <!-- ── 3. Verify each service ─────────────────────────────────────────────── -->
    <action>For each service in {required_services}:
      - Web app / HTTP service: attempt GET to /health, /api/health, or / (max 3s timeout each)
      - PostgreSQL / SQL Server: attempt TCP connect to host:port (max 3s)
      - Redis: attempt TCP connect (max 3s)
      - External API (Python AI, etc.): attempt GET to {base_url}/health or HEAD to {base_url} (max 5s)

      Record result: { service_name, port, status: "UP" | "DOWN", error_detail }
      Build {services_manifest} from all results.
    </action>

    <!-- ── 4. Detect port-based stack config ─────────────────────────────────── -->
    <action>Detect the web app port (for use in Playwright) based on {detected_stack}:
      - dotnet: Read `Properties/launchSettings.json` `applicationUrl`; or `appsettings.Development.json`; or `.env` PORT; default 5000
      - python: Read `pytest.ini` or `conftest.py` `base_url`; or `.env` PORT; default 8000
      - js: Read `playwright.config.ts` / `.js` `baseURL`; or `package.json` scripts; or `.env` PORT; default 3000
      Set {web_app_port}.
    </action>

    <!-- ── 5. Fail loudly if any service is down ──────────────────────────────── -->
    <check if="any service in {services_manifest} has status DOWN">
      <output>
        ## E2E RUNNER RESULT: FAILED

        ### Reason: Required services not running

        E2E tests require ALL services to be running. The following are DOWN:

        {for each DOWN service:}
        ❌ {service.name} — expected at {service.host}:{service.port}
           Error: {service.error_detail}
        {/for}

        **Services confirmed UP:**
        {for each UP service:}
        ✓ {service.name} at {service.host}:{service.port}
        {/for}

        **How to fix:**
        {if startup script exists: "Run: {startup_script_path}"}
        {else: "See docs/e2e-startup.md for instructions on starting each service"}

        E2E tests must run against a real stack — no mocking, no skipping.
        Fix the environment and re-run: /bagual-test-pipeline
      </output>
      <action>HALT and return failure to orchestrator</action>
    </check>

    <output>
      [E2E Step A] All required services are running:
      {for each service in services_manifest:}
      ✓ {service.name} at {service.host}:{service.port}
      {/for}
    </output>
  </step>

  <!-- ==================== STEP A2: Seed Test Data ==================== -->
  <step name="A2" goal="Ensure the database has the data E2E tests need — discover existing seed, or derive and create one from the tests and schema">

    <action>Set {seed_ran} = false and {seed_marker} = "" and {seed_cleanup_script} = ""</action>

    <!-- ── 1. Discover existing seed mechanism ────────────────────────────── -->
    <action>Search for an existing seed mechanism in this priority order:
      1. Shell scripts: `scripts/seed-e2e.sh`, `scripts/seed-test.sh`, `seed-e2e.sh`, `seed.sh`
      2. Makefile targets: grep Makefile for `seed-e2e`, `seed-test`, `seed` targets
      3. Stack-specific seeders:
         - dotnet: `**/DatabaseSeeder.cs`, `**/SeedData.cs`, `**/DataSeeder.cs`, `*Seed*.cs` in test project; also `dotnet run --seed` or `-- --seed` in any launch config
         - python: `python manage.py loaddata`, `pytest fixtures` in `conftest.py`, `**/fixtures/*.json`, `**/fixtures/*.yaml`
         - js: `scripts/seed.{js,ts,mjs}`, `prisma db seed`, `knex seed:run`, `sequelize db:seed:all`
      4. SQL files: `seeds/e2e.sql`, `test-data.sql`, `seed.sql`, `fixtures.sql`
      5. Docker compose: `docker-compose.test.yml` with seed service or init SQL

      Record: {existing_seed_mechanism} = path/command if found, null if not found.
    </action>

    <!-- ── 2a. Run existing seed ───────────────────────────────────────────── -->
    <check if="{existing_seed_mechanism} found">
      <action>Run the seed mechanism:
        - Shell script: `bash {path}`
        - Makefile: `make {target}`
        - dotnet seeder: `dotnet run --project {seeder_project}` or run via test setup if it's a fixture
        - python: execute the discovered command
        - js: execute the discovered command
        - SQL: `psql {connection_string} -f {path}` or equivalent for the detected DB

        Capture exit code and output.
      </action>

      <check if="seed command failed">
        <output>
          ⚠️  [E2E Step A2] Seed mechanism found but failed to run:
          Command: {seed_command}
          Error: {error_output}
          Attempting to continue — tests may fail due to missing data.
        </output>
      </check>

      <check if="seed command succeeded">
        <action>Set {seed_ran} = true</action>
        <output>[E2E Step A2] Seed ran successfully: {existing_seed_mechanism}</output>
      </check>

      <!-- Detect cleanup companion -->
      <action>Look for a paired cleanup script next to the seed:
        Same directory as seed, look for: `cleanup-e2e.sh`, `cleanup.sh`, `cleanup.sql`, `teardown.sh`
        If found, set {seed_cleanup_script} = that path.
      </action>
    </check>

    <!-- ── 2b. Derive and create seed from tests + schema ─────────────────── -->
    <check if="{existing_seed_mechanism} NOT found">
      <output>[E2E Step A2] No existing seed mechanism found. Deriving seed from tests and schema...</output>

      <action>Read ALL E2E test files (based on {detected_stack}):
        - dotnet: `**/*Tests.cs` files that contain `IPage` or `PlaywrightFixture` usage
        - python: `tests/e2e/**/*.py` or files with `async_playwright`/`page.goto`
        - js: `tests/e2e/**/*.{ts,js}` or `playwright/**/*.{ts,js}`

        For each test, identify what data it assumes exists:
        - Navigation targets: what pages/routes does it visit? What entities must exist to render them?
        - Search/filter actions: what does it search for? What must be in the DB to return results?
        - Form interactions: what does it fill? Does it require existing records (e.g. categories, users)?
        - Assertions: what counts, names, or values does it assert on screen?

        Build {required_data}: list of entities and minimum records needed, with their key fields.
      </action>

      <action>Read the project's data schema:
        - dotnet: migration files (`Migrations/*.cs`), entity classes (`*Entity.cs`, `*Model.cs`), DbContext
        - python: migration files, model definitions (`models.py`, `**/models/*.py`)
        - js: migration files, Prisma schema (`schema.prisma`), Sequelize models
        - All stacks: also check any existing `seed.sql` or `fixtures/` even if incomplete

        Map {required_data} entities to their actual DB tables, required columns, and foreign key constraints.
      </action>

      <action>Generate seed data:

        Choose marker convention based on {detected_stack}:
        - Email fields: use `@e2e.test` domain (e.g. `testuser@e2e.test`)
        - Name fields: prefix with `E2E_` (e.g. `E2E_TestProduct`)
        - Boolean flag: if schema has `is_test_data` or `is_seeded` field, set to true
        Set {seed_marker} = the chosen convention (e.g. "email domain @e2e.test and name prefix E2E_")

        Generate the minimum seed that satisfies {required_data}, respecting FK order.
        Write seed file in the appropriate format:
        - dotnet: `{project_root}/Tests/E2E/Seed/E2ESeed.cs` — a static class with async Seed(DbContext) method
        - python: `{project_root}/tests/e2e/seed/seed_e2e.py` — async function with SQLAlchemy or raw psycopg2
        - js: `{project_root}/tests/e2e/seed/seed-e2e.{ts,js}` — async function using the project's ORM/query builder
        - Any stack (fallback): `{project_root}/tests/e2e/seed/seed.sql` — pure SQL INSERT statements

        Generate paired cleanup file that deletes exactly what the seed inserted, using the marker:
        - dotnet: `{project_root}/Tests/E2E/Seed/E2ECleanup.cs`
        - python: `{project_root}/tests/e2e/seed/cleanup_e2e.py`
        - js: `{project_root}/tests/e2e/seed/cleanup-e2e.{ts,js}`
        - SQL fallback: `{project_root}/tests/e2e/seed/cleanup.sql`

        Write `{project_root}/docs/e2e-seed.md`:
        # E2E Test Seed Data
        ## What was seeded
        {for each entity in required_data: "- {entity}: {count} record(s), {key fields}"}
        ## Marker convention
        {seed_marker}
        ## How to re-run seed
        {run command}
        ## How to clean up manually
        {cleanup command}
        ## How to regenerate
        Delete the seed files and re-run /bagual-test-pipeline — the pipeline will re-derive from tests.

        Set {seed_cleanup_script} = path to generated cleanup file.
      </action>

      <action>Run the generated seed:
        - dotnet: compile and invoke E2ESeed via a small runner or dotnet-script; or call directly if test project exposes a CLI entry
        - python: `python tests/e2e/seed/seed_e2e.py`
        - js: `npx ts-node tests/e2e/seed/seed-e2e.ts` or `node tests/e2e/seed/seed-e2e.js`
        - SQL fallback: `psql {connection_string} -f tests/e2e/seed/seed.sql`

        Capture exit code. If it fails, output a warning and continue — tests will surface data errors explicitly.
      </action>

      <check if="seed ran successfully">
        <action>Set {seed_ran} = true</action>
        <output>[E2E Step A2] Seed derived from tests and schema, created and ran successfully. Marker: {seed_marker}</output>
      </check>

      <check if="seed failed">
        <output>
          ⚠️  [E2E Step A2] Generated seed failed to run. Tests may fail due to missing data.
          Seed file: {seed_file_path}
          Error: {error_output}
          Review docs/e2e-seed.md and fix the seed manually if needed.
        </output>
      </check>
    </check>

    <output>[E2E Step A2] Data seeding complete. seed_ran={seed_ran}, marker="{seed_marker}"</output>
  </step>

  <!-- ==================== STEP B: Set Up Log Capture ==================== -->
  <step name="B" goal="Instrument browser console capture and server log capture">
    <action>Ensure `{project_root}/test-results/` directory exists (create if needed)</action>

    <action>Check if Playwright already has a fixture or global setup that captures browser console logs.
      - dotnet: look for `page.Console +=` or `Page.Console +=` in any test class or fixture
      - python: look for `page.on("console"` in any conftest.py or test file
      - js: look for `page.on('console'` or `page.on('pageerror'` in any fixture or global-setup
    </action>

    <check if="no console capture fixture found">
      <action>Create a log capture fixture adapted to {detected_stack}:

        IF dotnet: Create `{project_root}/Tests/E2E/Fixtures/LogCaptureFixture.cs`:
        ```csharp
        // Tests/E2E/Fixtures/LogCaptureFixture.cs
        using System.Collections.Generic;
        using System.IO;
        using Microsoft.Playwright;

        public class LogCaptureFixture
        {
            private readonly List<string> _logs = new();

            public void Attach(IPage page)
            {
                page.Console += (_, msg) =>
                    _logs.Add($"[{msg.Type.ToUpper()}] {msg.Text}");
                page.PageError += (_, err) =>
                    _logs.Add($"[PAGEERROR] {err}");
                page.RequestFailed += (_, req) =>
                    _logs.Add($"[REQUEST_FAILED] {req.Method} {req.Url} — {req.Failure}");
            }

            public void FlushOnFailure(string testName)
            {
                if (_logs.Count == 0) return;
                var content = string.Join("\n", _logs);
                Directory.CreateDirectory("{browser_log_dir}");
                File.AppendAllText("{browser_log_file}", $"\n=== {testName} ===\n{content}\n");
            }
        }
        ```
        Add `LogCaptureFixture` to the base test class or PlaywrightFixture used by E2E tests.
        Call `fixture.Attach(page)` in test setup and `fixture.FlushOnFailure(testName)` in teardown.

        IF python: Create `{project_root}/tests/e2e/conftest.py` (or append to existing):
        ```python
        # tests/e2e/conftest.py
        import pytest

        @pytest.fixture
        def page_with_logs(page, request):
            logs = []
            page.on("console", lambda msg: logs.append(f"[{msg.type.upper()}] {msg.text}"))
            page.on("pageerror", lambda err: logs.append(f"[PAGEERROR] {err}"))
            yield page
            if request.node.rep_call.failed if hasattr(request.node, "rep_call") else False:
                import os
                os.makedirs("{browser_log_dir}", exist_ok=True)
                with open("{browser_log_file}", "a") as f:
                    f.write(f"\n=== {request.node.name} ===\n" + "\n".join(logs) + "\n")
        ```

        IF js: Create `{project_root}/tests/fixtures/log-capture.ts` (or `.js`):
        ```typescript
        import { test as base } from '@playwright/test';
        type ConsoleLogs = { logs: string[] };
        export const test = base.extend<ConsoleLogs>({
          logs: async ({}, use) => { await use([]); },
          page: async ({ page, logs }, use, testInfo) => {
            page.on('console', msg => logs.push(`[${msg.type().toUpperCase()}] ${msg.text()}`));
            page.on('pageerror', err => logs.push(`[PAGEERROR] ${err.message}\n${err.stack ?? ''}`));
            page.on('requestfailed', req => logs.push(`[REQUEST_FAILED] ${req.method()} ${req.url()} — ${req.failure()?.errorText}`));
            await use(page);
            if (testInfo.status !== testInfo.expectedStatus) {
              const logContent = logs.join('\n');
              await testInfo.attach('browser-console', { body: logContent, contentType: 'text/plain' });
              const fs = await import('fs');
              fs.appendFileSync('{browser_log_file}', `\n=== ${testInfo.title} ===\n${logContent}\n`);
            }
          },
        });
        export { expect } from '@playwright/test';
        ```
        Update existing E2E test files to import from this fixture instead of `@playwright/test`.
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
      - Otherwise: detect if this is a frontend project based on {detected_stack}:
          dotnet: scan for Razor pages (`*.cshtml`), Blazor (`*.razor`), or a frontend bundle (`wwwroot/index.html`, `ClientApp/`)
          python: scan for templates (`templates/`, `static/`), or a frontend folder with `index.html`
          js: scan for `package.json` with react/vue/angular/next/svelte/vite in dependencies, `playwright.config.*`, `next.config.*`, `vite.config.*`, `angular.json`
      - If frontend indicators found → set {visual_validation_enabled} = true (default on)
      - If backend-only and no explicit true → set {visual_validation_enabled} = false
    </action>

    <check if="{visual_validation_enabled} == false">
      <output>[E2E Step B2] Visual validation not applicable (backend-only project or explicitly disabled). Skipping.</output>
    </check>

    <check if="{visual_validation_enabled} == true">

      <!-- ── Screenshot helper ──────────────────────────────────────────── -->
      <action>Determine the screenshot call pattern for {detected_stack}:
        - dotnet: look for `ScreenshotHelper.CaptureAsync(page, "name")` or `await page.ScreenshotAsync(new PageScreenshotOptions { Path = "..." })` calls with a path under `test-artifacts/screenshots/`
        - python: look for `capture_screenshot(page, "name")` or `await page.screenshot(path="test-artifacts/screenshots/...")` calls
        - js: look for `captureScreenshot(page, 'name')` calls
        Set {screenshot_pattern} to the detected call pattern.
      </action>

      <action>Check if screenshot helper exists:
        - dotnet: `Tests/E2E/Helpers/ScreenshotHelper.cs` or {screenshot_pattern} found in any test file
        - python: `tests/e2e/helpers/screenshot.py` or {screenshot_pattern} found in any test file
        - js: `tests/e2e/helpers/screenshot.*` or {screenshot_pattern} found in any test file
      </action>

      <check if="helper not found">
        <action>Create the screenshot helper adapted to the project's language and framework.
          Follow the language-specific helper in visual-validation.md. Core contract (all stacks):
          - normalize name → save PNG to `test-artifacts/screenshots/{name}.png`
          - call AFTER assertions confirm the UI state is stable
          Path conventions:
          - dotnet: `{project_root}/Tests/E2E/Helpers/ScreenshotHelper.cs`
          - python: `{project_root}/tests/e2e/helpers/screenshot.py`
          - js: `{project_root}/tests/e2e/helpers/screenshot.{ts|js}`
        </action>
      </check>

      <!-- ── CRITICAL: Screenshots belong inside existing E2E tests ──────── -->
      <action>
        *** INTEGRATION MANDATE — NON-NEGOTIABLE ***
        Screenshots MUST be captured inside the existing E2E test methods, at meaningful UI states.
        DO NOT create a separate test class, test file, or test suite just for screenshots.

        For each existing E2E test (e.g. ChatSmokeTest, KnowledgeSearchSmokeTest):
          - Identify the key UI states within that test: initial load, after user action, with results,
            with drawer/modal open, with error, empty state, etc.
          - Add a screenshot capture call AFTER the assertions for each state are confirmed
          - Name each screenshot descriptively: "{feature}-{state}" (e.g. "chat-initial-load", "search-with-results")

        A test that navigates through 5 states should have up to 5 screenshots — one per state.
        Never capture a screenshot before the assertions that confirm that state is stable.
        *** END MANDATE ***
      </action>

      <!-- ── visual-requirements.yaml — generate with semantic rules ────── -->
      <action>Check if `{project_root}/visual-requirements.yaml` exists.</action>

      <check if="file does not exist OR file exists but has only placeholder comments">
        <action>Generate `{project_root}/visual-requirements.yaml` with real semantic requirements:

          For EACH screenshot capture call found in E2E test files (using {screenshot_pattern}):

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
        <action>Scan E2E test files for any screenshot capture calls (using {screenshot_pattern}) whose name is NOT yet in visual-requirements.yaml.
          For each new name found, append an entry using the same analysis process above.
        </action>
        <output>[E2E Step B2] visual-requirements.yaml updated with {new_count} new entries.</output>
      </check>

      <output>[E2E Step B2] Visual validation ready — screenshot helper and requirements in place. Validation will run inline after E2E tests.</output>
    </check>
  </step>

  <!-- ==================== STEP C: Run Playwright E2E Tests ==================== -->
  <step name="C" goal="Execute all E2E tests and collect full results">
    <action>Run E2E tests using the command appropriate for {detected_stack}:
      - dotnet: `dotnet test --logger "console;verbosity=detailed" --results-directory test-results`
        (test output includes Playwright traces and failure details)
      - python: `pytest tests/e2e/ --tb=short -v --output=test-results`
        (or the path where E2E tests are located, detected from test file locations)
      - js: `npx playwright test --reporter=list,json --output=test-results`
      - unknown: try `npx playwright test` first; if it fails with "not found", try `dotnet test`; then `pytest`

      Capture: exit code, full stdout/stderr, path to results/JSON output.
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

  <!-- ==================== STEP E2: Cleanup Test Data ==================== -->
  <step name="E2" goal="Remove seed data created during this test run — leave the database in pre-test state">

    <check if="{seed_ran} == false">
      <output>[E2E Step E2] No seed was run. Skipping cleanup.</output>
    </check>

    <check if="{seed_ran} == true">
      <output>[E2E Step E2] Cleaning up seed data...</output>

      <!-- ── Strategy A: Run paired cleanup script ──────────────────────── -->
      <check if="{seed_cleanup_script} is set and file exists">
        <action>Run the cleanup script:
          - Shell: `bash {seed_cleanup_script}`
          - dotnet: invoke E2ECleanup via dotnet-script or test runner CLI
          - python: `python {seed_cleanup_script}`
          - js: `npx ts-node {seed_cleanup_script}` or `node {seed_cleanup_script}`
          - SQL: `psql {connection_string} -f {seed_cleanup_script}`

          Capture exit code.
        </action>

        <check if="cleanup succeeded">
          <output>[E2E Step E2] ✓ Seed data cleaned up via cleanup script.</output>
        </check>

        <check if="cleanup failed">
          <output>
            ⚠️  [E2E Step E2] Cleanup script failed. Seed data may remain in the database.
            Script: {seed_cleanup_script}
            Error: {error_output}
            Run manually to clean up, or re-run seed before next E2E run.
          </output>
        </check>
      </check>

      <!-- ── Strategy B: Delete by marker (fallback if no cleanup script) ── -->
      <check if="{seed_cleanup_script} NOT set AND {seed_marker} is set">
        <action>Delete seed data by marker convention ({seed_marker}):
          Construct DELETE queries based on what was seeded and the marker used:
          - If marker is email domain `@e2e.test`: DELETE FROM users WHERE email LIKE '%@e2e.test'
          - If marker is name prefix `E2E_`: DELETE FROM relevant tables WHERE name LIKE 'E2E_%'
          - Execute in reverse FK order (delete children before parents)
          - Use the DB connection from the same config used by the seed

          Execute via the appropriate client for {detected_stack}:
          - dotnet: via DbContext or raw SQL with connection string from appsettings
          - python: via sqlalchemy or psycopg2 with DATABASE_URL
          - js: via project's query builder or raw pg client
        </action>

        <output>[E2E Step E2] ✓ Seed data removed by marker ({seed_marker}).</output>
      </check>

      <check if="{seed_cleanup_script} NOT set AND {seed_marker} NOT set">
        <output>
          ⚠️  [E2E Step E2] No cleanup script and no marker — cannot auto-clean seed data.
          Database may contain test data from this run. See docs/e2e-seed.md for manual cleanup instructions.
        </output>
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

        ### Services (all real — no mocks)
        {for each service in services_manifest:}
        ✓ {service.name} at {service.host}:{service.port}
        {/for}

        ### Data Lifecycle
        Seed: {if seed_ran: "ran — " + (existing_seed_mechanism OR "derived from tests") else: "not needed"}
        Cleanup: {if seed_ran: "completed" else: "skipped"}
      </output>
      <action>Return success to orchestrator, including {services_manifest}</action>
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

        ### Services (verified running at test start)
        {for each service in services_manifest:}
        ✓ {service.name} at {service.host}:{service.port} (real — no mocks)
        {/for}

        ### Likely Root Causes

        Correlate test failures, visual failures, browser errors, and server errors.
        List each correlation as:
        - **[Failure name]** → likely caused by: [matching browser error, server error, or visual issue]
      </output>
      <action>Return failure with full structured report to orchestrator, including {services_manifest}</action>
    </check>
  </step>

</workflow>
