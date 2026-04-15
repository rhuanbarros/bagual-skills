# Script Opportunities Analysis
**Skills:** bagual-test-pipeline + bagual-bmad-implement-quick-epic
**Date:** 2026-04-15
**Analyst:** ScriptHunter

---

## Existing Scripts Inventory

**bagual-test-pipeline:** No `scripts/` directory. Zero scripts exist.
**bagual-bmad-implement-quick-epic:** No `scripts/` directory. Zero scripts exist.

Both skills are pure LLM-prose workflows. Every deterministic operation — stack detection, service health checks, mock pattern scanning, coverage threshold comparison — is delegated to the reasoning model at runtime.

---

## Assessment

Both skills are heavily over-relying on LLM reasoning for work that is 100% deterministic and could be done by a 20-line script in milliseconds with zero hallucination risk. The production failures documented by the skill author are a direct consequence of this pattern:

- The LLM "detected" a JS stack on a C# project because it reasoned from partial evidence instead of running `ls *.csproj`.
- E2E tests ran silently without services because there was no TCP check script to fail loudly.
- Mock patterns went undetected because there was no grep-based scanner.
- Coverage thresholds were never enforced because no script parsed the cobertura XML and compared it to the target.

**LLM Tax** (estimated time wasted per pipeline run due to LLM doing deterministic work):
- Stack detection: ~15-30 seconds of LLM reasoning + risk of wrong answer
- Service health checks: ~30-60 seconds of LLM "checking" (often hallucinated as "UP" without actually testing)
- Mock/stub scan: ~45-90 seconds of LLM grep reasoning over test files
- Coverage threshold check: ~20-40 seconds of LLM parsing XML + arithmetic
- E2E data seeding/cleanup detection: ~30-60 seconds of LLM reviewing test setup code

**Total estimated LLM Tax per pipeline run: 2-5 minutes of unnecessary LLM reasoning, with non-zero hallucination probability on each step.**

---

## Key Findings and Script Opportunities

### OPPORTUNITY 1 — Stack Detector
**Category:** Pre-processing / Validation
**Severity:** Critical
**Affects:** bagual-test-pipeline (Step 0, all subsequent steps depend on it)

**Problem:** The LLM is asked to detect the project stack by "looking for indicators." This failed in production: a C# + xUnit project was identified as JS/TS, causing all subsequent commands (npx playwright test, playwright.config.ts) to be wrong.

**Deterministic rule:**
```
if any *.csproj or *.sln exists → dotnet
elif pytest.ini or conftest.py or pyproject.toml[tool.pytest] exists → python
elif package.json exists at project root → js
else → unknown
```
Priority: dotnet > python > js (match first hit, in order).

**Proposed script:** `scripts/detect-stack.sh {project_root}` — exits 0, prints one of: `dotnet` | `python` | `js` | `unknown` to stdout.

**LLM Tax eliminated:** ~15-30 sec reasoning per run + eliminates entire class of wrong-stack errors.
**Confidence:** 100% deterministic. No LLM needed.

---

### OPPORTUNITY 2 — Service Health Check
**Category:** Validation / Structure Check
**Severity:** Critical
**Affects:** bagual-test-pipeline (E2E runner Step A)

**Problem:** The e2e-runner is instructed to "attempt GET to /health or TCP connect" for each required service. In practice, LLMs simulate this check rather than executing it, or they execute it but silently accept a failed connection as "probably fine." The production failure: E2E tests ran with PostgreSQL, .NET app, and Python API all down — no warnings.

**Deterministic rule:**
For each service: TCP connect with 3-second timeout. Non-zero exit = service down = hard fail.

**Proposed script:** `scripts/check-services.sh {host:port} [{host:port} ...]`
- Uses `nc -z -w3` or `curl --connect-timeout 3` per endpoint
- Exits 0 only if ALL services respond
- Prints clear UP/DOWN status for each
- Exits non-zero on any DOWN — orchestrator reads exit code, not LLM interpretation

**LLM Tax eliminated:** ~30-60 sec per run. More importantly, eliminates false-positive "all services running" verdicts.
**Confidence:** 100% deterministic.

---

### OPPORTUNITY 3 — E2E Mock/Stub Pattern Scanner
**Category:** Validation / Content Search
**Severity:** Critical
**Affects:** bagual-test-pipeline (Step 0.5 — E2E Mocking Audit)

**Problem:** Step 0.5 asks the LLM to "scan all E2E test files for these violation patterns." The LLM may miss patterns, misclassify them, or flag false positives. The production failure: `KnowledgeSearchTestDataFixture` replaced the real Python API, and `IsAnyResponseOrErrorVisibleAsync` accepted errors as success — neither was caught.

**Deterministic rule:**
Grep for exact patterns in E2E test file paths only (not unit test paths):
- dotnet E2E: `Tests/E2E/**/*.cs`
- python E2E: `tests/e2e/**/*.py`
- js E2E: `tests/e2e/**/*.{ts,js}`, `playwright/**/*.{ts,js}`

**Forbidden patterns by category:**
```
HTTP stubs:    HttpListener|WireMock|MockHttp|TestServer|nock|msw|responses|httpretty
InMemory DB:   UseInMemoryDatabase|SQLite.*test|sqlite.*e2e
Accept-error:  successVisible.*||.*errorVisible|success.*or.*error|IsAnyResponseOrError
Silent skip:   \[Ignore\]|\[Skip\]|pytest\.mark\.skip|\.skip\(|catch.*return;
```

**Proposed script:** `scripts/scan-e2e-mocks.sh {project_root} {stack}`
- Greps for each pattern category in the appropriate E2E test directory for the stack
- Outputs: `CLEAN` (exit 0) or `VIOLATIONS FOUND` with file:line:snippet (exit 1)
- The orchestrator reads exit code; violations are printed for the LLM to act on

**LLM Tax eliminated:** ~45-90 sec per run. Replaces imprecise LLM grep with exact ripgrep patterns.
**Confidence:** ~95% (some patterns require context to distinguish unit vs E2E test; mitigated by scoping to E2E paths only).

---

### OPPORTUNITY 4 — Coverage Threshold Enforcer
**Category:** Comparison / Validation
**Severity:** High
**Affects:** bagual-test-pipeline (Step 3 — unit test fix loop condition)

**Problem:** The workflow says "exit code 0 AND actual coverage >= {coverage_target}" but leaves the comparison to the LLM, which must parse coverage output from stdout or XML and do arithmetic. In practice, coverage thresholds were silently skipped.

**Deterministic rules per stack:**
- dotnet: parse `coverage.cobertura.xml` — XPath `//coverage/@line-rate` * 100 vs threshold
- python: parse `.coverage` or `pytest --cov` stdout line `TOTAL ... X%` vs threshold
- js: parse `coverage/coverage-summary.json` — `total.lines.pct` vs threshold

**Proposed script:** `scripts/check-coverage.sh {stack} {threshold} {report_path}`
- Reads the coverage report for the given stack
- Prints actual coverage percentage
- Exits 0 if actual >= threshold, exits 1 with message if below
- Orchestrator uses exit code to drive the fix loop, not LLM interpretation

**LLM Tax eliminated:** ~20-40 sec per run + eliminates silent threshold bypass.
**Confidence:** 100% deterministic (given a valid report file).

---

### OPPORTUNITY 5 — E2E Data Seeding / Teardown Checker
**Category:** Validation / Content Search
**Severity:** High
**Affects:** bagual-test-pipeline (Step 0.5 and Step B of e2e-runner)

**Problem:** The production failure notes: "data seeding before E2E and cleanup after were systematically forgotten." No step in the current workflow checks whether test files contain setup/teardown hooks. The LLM never flags this because it is not asked to — it assumes the test author handled it.

**Deterministic rule:**
For each E2E test file, check that it contains at least one of:
- dotnet: `[SetUp]`, `[TearDown]`, `IAsyncLifetime`, `InitializeAsync`, `DisposeAsync`, or `BeforeTestRunAsync`
- python: `@pytest.fixture`, `setup_method`, `teardown_method`, or `yield` in a conftest fixture
- js: `beforeEach`, `afterEach`, `beforeAll`, `afterAll` in the test file

**Proposed script:** `scripts/check-e2e-lifecycle.sh {project_root} {stack}`
- Scans E2E test files for the presence of lifecycle hooks
- For files with zero hooks AND more than N test cases (threshold: 1), emits a warning
- Exits 0 with `CLEAN` or exits 1 with list of files missing lifecycle hooks

**LLM Tax eliminated:** ~30-60 sec per run. More importantly, surfaces a systematic omission before tests run.
**Confidence:** ~90% (some projects use class-level fixtures defined elsewhere; script may need to check fixture files too).

---

### OPPORTUNITY 6 — Port / Web App Endpoint Detector
**Category:** Pre-processing / Data Extraction
**Severity:** Medium
**Affects:** bagual-test-pipeline (e2e-runner Step A — port detection for Playwright baseURL)

**Problem:** The e2e-runner is told to "detect the web app port" by reading launchSettings.json, appsettings.Development.json, .env, or playwright.config.ts. This multi-file search is purely data extraction — the LLM adds no value here and may read the wrong file or extract the wrong value.

**Deterministic rule by stack:**
- dotnet: `jq -r '.profiles[].applicationUrl' Properties/launchSettings.json | grep -oP ':\K[0-9]+'`
- python: grep for `PORT=` in `.env`, or `base_url` in `pytest.ini` / `conftest.py`
- js: `jq -r '.use.baseURL' playwright.config.json` or grep `baseURL` in playwright.config.ts

**Proposed script:** `scripts/detect-port.sh {project_root} {stack}`
- Outputs the detected port number (or 5000/8000/3000 as default fallback)
- Exits 0 always; prints detected port to stdout

**LLM Tax eliminated:** ~15-25 sec per run. Removes risk of LLM reading the wrong config file.
**Confidence:** ~90% (edge cases: monorepos with multiple configs, non-standard config locations).

---

### OPPORTUNITY 7 — Sprint Status Story Queue Builder
**Category:** Data Extraction / Pre-processing for LLM
**Severity:** Medium
**Affects:** bagual-bmad-implement-quick-epic (workflow.md Step 1)

**Problem:** The orchestrator is asked to "read sprint-status.yaml and parse the development_status section" to build the story queue. This is pure YAML parsing — finding all keys matching `{epic_num}-*-*`, excluding epic keys and retrospective keys, ordering them as they appear in the file. The LLM can and does this, but it is deterministic data extraction that adds no reasoning value.

**Deterministic rule:**
```python
import yaml, sys, re
data = yaml.safe_load(open(sprint_status))
epic_num = sys.argv[1]
pattern = re.compile(rf'^{re.escape(epic_num)}-\d+-\w')
exclude = re.compile(r'^epic-|retrospective')
queue = [k for k in data['development_status'] if pattern.match(k) and not exclude.search(k) and data['development_status'][k] != 'done']
print('\n'.join(queue))
```

**Proposed script:** `scripts/build-story-queue.py {sprint_status_path} {epic_num}`
- Outputs one story key per line, in file order, filtered to not-done stories
- Exits 0 if queue non-empty, exits 1 if queue empty (with message)

**LLM Tax eliminated:** ~20-40 sec per run. Also eliminates risk of the LLM misreading YAML structure or including retrospective/epic keys in the queue.
**Confidence:** 99% deterministic (YAML is structured data).

---

### OPPORTUNITY 8 — E2E Test File Location Scanner
**Category:** Structure / Filesystem Check
**Severity:** Medium
**Affects:** bagual-test-pipeline (Step 0 — diagnostic scan)

**Problem:** The diagnostic scan asks the LLM to count E2E test files by "looking for PlaywrightFixture, IPage usage in any *Tests.cs." This is a grep operation. The LLM may undercount (missing files) or overcount (including unit tests that happen to import IPage for unrelated reasons).

**Deterministic rule by stack:**
- dotnet: `grep -rl "IPage\|PlaywrightFixture\|IPlaywright" --include="*Tests.cs" {project_root} | grep -v "/bin/\|/obj/"`
- python: `grep -rl "async_playwright\|page\.goto\|Playwright" --include="*.py" {project_root}/tests/e2e/`
- js: Files in `tests/e2e/`, `e2e/`, or `playwright/` directories matching `*.spec.ts|*.test.ts`

**Proposed script:** `scripts/find-e2e-tests.sh {project_root} {stack}`
- Prints file paths, one per line
- Exits 0; last line is count summary

**LLM Tax eliminated:** ~15-30 sec per run. Provides accurate input for later steps.
**Confidence:** 95%.

---

### OPPORTUNITY 9 — Visual Validation Enablement Check
**Category:** Validation / Structure Check
**Severity:** Low
**Affects:** bagual-test-pipeline (e2e-runner Step B2)

**Problem:** The e2e-runner must decide whether visual validation applies by detecting frontend indicators. This is a series of filesystem checks (does `*.cshtml` exist? does `wwwroot/index.html` exist? does `package.json` contain react?). The LLM can do this but it is pure data lookup.

**Deterministic rule:**
```bash
# dotnet frontend indicators
ls *.cshtml *.razor wwwroot/index.html ClientApp/ 2>/dev/null | head -1

# js frontend
jq -e '.dependencies | keys[] | select(test("react|vue|angular|next|svelte|vite"))' package.json

# python
ls templates/ static/ 2>/dev/null | head -1
```

**Proposed script:** `scripts/check-frontend.sh {project_root} {stack}`
- Exits 0 if frontend indicators found (visual validation should be enabled)
- Exits 1 if backend-only
- Honors `VISUAL_VALIDATION_ENABLED` env var override

**LLM Tax eliminated:** ~10-20 sec per run.
**Confidence:** 95% (some edge cases: backend projects serving SPA from a different repo).

---

### OPPORTUNITY 10 — Screenshot/Requirement Coverage Sync
**Category:** Comparison / Cross-Reference
**Severity:** Low
**Affects:** bagual-test-pipeline (e2e-runner Step B2)

**Problem:** Step B2 asks the LLM to "scan E2E test files for any screenshot capture calls whose name is NOT yet in visual-requirements.yaml." This is a set-difference operation: names extracted from code vs. keys in a YAML file.

**Deterministic rule:**
1. Extract all screenshot names from test files: grep for `CaptureAsync(Page, "(.+?)"` / `captureScreenshot(page, '(.+?)'` / `capture_screenshot(page, "(.+?)"`
2. Load keys from `visual-requirements.yaml`
3. Print keys in set(extracted) - set(yaml_keys)

**Proposed script:** `scripts/check-screenshot-coverage.sh {project_root} {stack}`
- Exits 0 if all screenshot names have entries in visual-requirements.yaml
- Exits 1 with list of missing names if any are absent

**LLM Tax eliminated:** ~15-30 sec per run.
**Confidence:** 95% (regex extraction of string literals is reliable for standard patterns).

---

## Aggregate Savings

| # | Opportunity | Severity | Est. LLM Tax / Run | Failure Risk Eliminated |
|---|-------------|----------|--------------------|------------------------|
| 1 | Stack Detector | Critical | 15-30 sec | Wrong stack → wrong commands throughout pipeline |
| 2 | Service Health Check | Critical | 30-60 sec | Silent E2E runs against stopped services |
| 3 | E2E Mock/Stub Scanner | Critical | 45-90 sec | Mocks/stubs slipping into E2E without detection |
| 4 | Coverage Threshold Enforcer | High | 20-40 sec | Thresholds silently bypassed |
| 5 | E2E Data Seeding/Teardown Checker | High | 30-60 sec | Systematic omission of test lifecycle hooks |
| 6 | Port / Endpoint Detector | Medium | 15-25 sec | Wrong baseURL for Playwright |
| 7 | Story Queue Builder | Medium | 20-40 sec | Wrong story list fed to epic pipeline |
| 8 | E2E Test File Scanner | Medium | 15-30 sec | Inaccurate diagnostic counts |
| 9 | Visual Validation Enablement Check | Low | 10-20 sec | Visual validation skipped/enabled incorrectly |
| 10 | Screenshot/Requirement Coverage Sync | Low | 15-30 sec | Orphaned screenshot names with no requirements |

**Total estimated LLM Tax per full pipeline run (all 10 scripts): 215-425 seconds (3.5-7 minutes)**

**High-value priority (implement first, highest failure risk):**
1. Service Health Check (Opportunity 2) — directly caused silent E2E failures
2. Stack Detector (Opportunity 1) — directly caused JS commands on C# project
3. E2E Mock/Stub Scanner (Opportunity 3) — directly caused stub slippage into E2E

**Implementation note:** Scripts 1-5 are blockers that should fail the pipeline with non-zero exit codes. Scripts 6-10 are advisory (emit warnings; pipeline continues). All scripts should write output to stdout and use exit codes, not prose, as their primary signal to the orchestrator.

---

## Notes on LLM Residual Role

After scripting the above, the LLM retains its legitimate role for:
- **Interpreting ambiguous results** — e.g., when a script reports a violation, the LLM decides whether to auto-fix or halt
- **Generating test code** — adversarial test generation (Steps 2, E2E test writing) is inherently creative/reasoning work
- **Producing fix prompts** — crafting the bmad-quick-dev prompt with the right failure context
- **Writing startup docs** — e2e-startup.md when no startup script exists

Scripts handle the deterministic gates. The LLM handles the judgment calls. This division eliminates the failure modes identified in the production failures without reducing the skill's value.
