# Visual Validation — Implementation Reference

Automated visual validation using the agent's built-in vision capabilities. No external API key required — the running agent reads screenshots directly and evaluates them against semantic requirements.

---

## Activation Policy

**Frontend projects: always active.** Visual validation runs automatically for any project with a frontend layer:
- JS/TS: `package.json` with React/Vue/Angular/Next/Svelte/Vite, or `playwright.config.*` exists
- .NET/C#: Razor pages (`*.cshtml`), Blazor (`*.razor`), or `wwwroot/index.html` / `ClientApp/` directory
- Python: `templates/` directory, `static/` with frontend assets, or `index.html` at a served path

**To disable explicitly** (e.g. CI environment without image support): set `VISUAL_VALIDATION_ENABLED=false`.

**Backend-only projects**: disabled by default unless `VISUAL_VALIDATION_ENABLED=true` is explicitly set.

---

## How It Works

No external API calls are made. The e2e-runner agent reads each captured PNG using its built-in Read tool (vision-capable) and evaluates the screenshot against the requirements in `visual-requirements.yaml`.

This means:
- No API key setup required
- No validate-screenshots script to install
- No network calls during validation
- Validation happens inline, within the e2e-runner agent

---

## Two Types of Validation

Every screenshot must be checked for **both** types:

### 1. Visual Layout
- Elements are properly aligned and centered
- No text truncation or overflow
- Consistent spacing between elements
- No overlapping content (toasts, modals, dropdowns)
- Buttons, inputs, tables in correct positions
- Responsive layout not broken

### 2. Semantic Data Consistency
This is the harder and more valuable check: **do the values and states shown on screen make logical sense together?**

Examples of semantic bugs to catch:
- Filter shows "Active" as selected → the list must only show active items (not all items)
- A counter badge shows "0" → the list below must be empty or have 0 qualifying items
- A "No results" empty state is visible → the table/list must actually have no rows
- Pagination shows "Page 1 of 5 (47 results)" → approximately 10 rows should be visible (assuming 10/page)
- A "selected" checkbox next to an item → the item must appear visually selected/highlighted
- A total displayed at the bottom of a table → should match the visible sum of the rows above
- An error banner is visible → form fields below must have visible error indicators
- A "Loading" spinner is absent → content must be fully populated, not partially loaded

**Why this matters**: semantic bugs often pass functional tests because the test checks individual assertions, not the overall coherence of the screen. A filter UI can call the API correctly and render the response correctly, yet still display a misleading active-filter indicator when the result is unfiltered.

---

## Integration Mandate — Where Screenshots Live

**Screenshots MUST be captured inside existing E2E tests, not in a separate test class.**

The correct pattern:
- Take each existing E2E test (e.g. `ChatSmokeTest`, `KnowledgeSearchSmokeTest`)
- Identify every meaningful UI state that test passes through: initial load, after user action, with results, with drawer/modal open, with error, empty state, etc.
- Add a screenshot call AFTER the assertions for each state are confirmed stable
- Name the screenshot `{feature}-{state}` (e.g. `chat-initial-load`, `search-with-results`, `search-error`)

**What to never do:**
- Never create a separate `VisualTestSuite.cs` / `visual_tests.py` / `visual.spec.ts` class with hardcoded screenshots
- Never capture a screenshot before the state-confirming assertions
- Never capture the same state twice

Example (correct — C#):
```csharp
[Test]
public async Task SearchTest_ShowsResultsAndError()
{
    await Page.GotoAsync("/search");
    await Expect(Page.Locator("h1")).ToContainTextAsync("Search");
    await ScreenshotHelper.CaptureAsync(Page, "search-initial-load"); // ← after confirming state

    await Page.FillAsync("[data-testid='query']", "test query");
    await Page.ClickAsync("[data-testid='search-btn']");
    await Expect(Page.Locator("[data-testid='results']")).ToBeVisibleAsync();
    await ScreenshotHelper.CaptureAsync(Page, "search-with-results"); // ← after confirming state

    await Page.FillAsync("[data-testid='query']", "");
    await Page.ClickAsync("[data-testid='search-btn']");
    await Expect(Page.Locator("[data-testid='error-msg']")).ToBeVisibleAsync();
    await ScreenshotHelper.CaptureAsync(Page, "search-empty-error"); // ← after confirming state
}
```

---

## Generating `visual-requirements.yaml`

When creating this file (or updating it for new screenshots), the agent must **analyze each E2E test** to understand what state the app is in at the moment `captureScreenshot()` is called, and generate requirements for both layout AND semantic consistency.

**Process for each screenshot:**

1. Read the test file and find the `captureScreenshot(page, '{name}')` call
2. Trace backward through the test to understand:
   - What user actions were performed before this capture?
   - What data was set up (fixtures, form inputs, API responses)?
   - What UI state should be active (selected filters, active tabs, pagination page, etc.)?
   - What counts or totals should be visible?
3. Generate requirements that verify both layout AND that the visible data matches the expected state

**Example — a filter interaction test:**
```typescript
// Test code context
await page.getByRole('button', { name: 'Status' }).click();
await page.getByRole('option', { name: 'Active' }).click();
await page.waitForLoadState('networkidle');
await captureScreenshot(page, 'transaction-list-filtered-active');
```

Generated requirements:
```yaml
transaction-list-filtered-active:
  - The "Status: Active" filter chip/badge must appear visually selected or highlighted
  - EVERY row in the table must show status "Active" — no other status values visible
  - If fixture data has 3 active items, exactly 3 rows must be visible
  - The result count shown (e.g. "3 results") must match the number of visible rows
  - The "Clear filters" button or similar must be visible and accessible
  - Table columns must be properly aligned with no overflow
  - No "No results" empty state should be showing (filter matches data)
```

**Example — empty state test:**
```typescript
await page.getByRole('button', { name: 'Archived' }).click();
await page.waitForLoadState('networkidle');
await captureScreenshot(page, 'transaction-list-empty-archived');
```

Generated requirements:
```yaml
transaction-list-empty-archived:
  - An empty state illustration or message must be visible (no table rows)
  - The result count must show 0 or "No results found"
  - The "Archived" filter must appear as selected/active
  - The table or list container must NOT show any data rows
  - The empty state message must be centered and properly styled
```

**Starter `visual-requirements.yaml` format** (write this when the file doesn't exist):
```yaml
# visual-requirements.yaml
# Generated by bagual-test-pipeline — review and refine each entry.
# Key = exact screenshot filename without .png
# Format: kebab-case names only, no spaces

# ── LAYOUT RULES (apply to all screens) ──────────────────────────────────────
# Verify proper centering, no text overflow, consistent spacing, no overlapping elements.
# Buttons and inputs must be in correct positions.

# ── SEMANTIC RULES (per screen) ──────────────────────────────────────────────
# Verify that displayed data is logically consistent with the app state.
# Counts must match visible items. Active filters must visibly filter the list.
# Empty states must show when data is absent. Totals must match row data.
```

---

## File 1: Screenshot Helper

**Path in target project**: `tests/e2e/helpers/screenshot.{ts|js|py|cs}`

**C#/.NET (Microsoft.Playwright):**
```csharp
// Tests/E2E/Helpers/ScreenshotHelper.cs
using System.IO;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using Microsoft.Playwright;

public static class ScreenshotHelper
{
    private const string ScreenshotsDir = "test-artifacts/screenshots";

    /// <summary>
    /// Capture a named screenshot for visual validation.
    /// Name must match a key in visual-requirements.yaml.
    /// Call AFTER confirming the UI state is stable and assertions have passed.
    /// </summary>
    public static async Task CaptureAsync(IPage page, string name)
    {
        Directory.CreateDirectory(ScreenshotsDir);
        var cleanName = Regex.Replace(
            name.ToLowerInvariant().Replace(' ', '-'), @"[^\w-]", ""
        );
        if (cleanName.Length > 50) cleanName = cleanName.Substring(0, 50);
        await page.ScreenshotAsync(new PageScreenshotOptions
        {
            Path = Path.Combine(ScreenshotsDir, $"{cleanName}.png")
        });
    }
}
```

**Usage** — always capture AFTER asserting the UI state is what you expect:
```csharp
// ✅ Correct: capture after confirming state
await Expect(Page.GetByRole(AriaRole.Cell, new() { Name = "Active" })).ToBeVisibleAsync();
await ScreenshotHelper.CaptureAsync(Page, "transaction-list-filtered-active");

// ❌ Wrong: capture before verifying state is stable
await Page.ClickAsync("button");
await ScreenshotHelper.CaptureAsync(Page, "transaction-list-filtered-active"); // might be loading
```

---

**TypeScript/Playwright (JS):**
```typescript
// tests/e2e/helpers/screenshot.ts
import { Page } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';

const SCREENSHOTS_DIR = './test-artifacts/screenshots';

function ensureDir() {
  if (!fs.existsSync(SCREENSHOTS_DIR)) fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });
}

/**
 * Capture a named screenshot for visual validation.
 * Name must match a key in visual-requirements.yaml.
 * Call AFTER confirming the UI state is stable and assertions have passed.
 */
export async function captureScreenshot(page: Page, name: string) {
  ensureDir();
  const cleanName = name.toLowerCase().replace(/\s+/g, '-').replace(/[^\w-]/g, '').slice(0, 50);
  await page.screenshot({ path: path.join(SCREENSHOTS_DIR, `${cleanName}.png`) });
}
```

**Usage** — always capture AFTER asserting the UI state is what you expect:
```typescript
// ✅ Correct: capture after confirming state
await expect(page.getByRole('cell', { name: 'Active' })).toBeVisible();
await captureScreenshot(page, 'transaction-list-filtered-active');

// ❌ Wrong: capture before verifying state is stable
await page.click('button');
await captureScreenshot(page, 'transaction-list-filtered-active'); // might be loading
```

---

**Python/pytest-playwright:**
```python
# tests/e2e/helpers/screenshot.py
import os
import re
from playwright.sync_api import Page

SCREENSHOTS_DIR = "test-artifacts/screenshots"

def capture_screenshot(page: Page, name: str) -> None:
    """
    Capture a named screenshot for visual validation.
    Name must match a key in visual-requirements.yaml.
    Call AFTER confirming the UI state is stable and assertions have passed.
    """
    os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
    clean_name = re.sub(r'[^\w-]', '', name.lower().replace(' ', '-'))[:50]
    page.screenshot(path=os.path.join(SCREENSHOTS_DIR, f"{clean_name}.png"))
```

---

## Output: Report Format

`_bmad-output/test-artifacts/visual-validation/latest.json`:
```json
{
  "totalScreenshots": 5,
  "passedCount": 3,
  "failedCount": 2,
  "generatedAt": "2026-04-12T17:00:00.000Z",
  "results": [
    { "screenshot": "auth-login-form.png", "timestamp": "...", "passed": true },
    {
      "screenshot": "transaction-list-filtered-active.png",
      "timestamp": "...",
      "passed": false,
      "issues": "SEMANTIC: Filter 'Active' button shows as selected but the list contains items with status 'Pending' and 'Closed' — list appears unfiltered. LAYOUT: No layout issues."
    }
  ]
}
```

---

## Common Gotchas

| Problem | Cause | Fix |
|---------|-------|-----|
| All screenshots pass | Requirements too generic | Add specific semantic rules per screen |
| Semantic bugs not caught | No semantic requirements | Analyze test context to generate data-consistency rules |
| Screenshot not found | Path mismatch | Ensure helper saves to `test-artifacts/screenshots/` regardless of stack |
| Requirements missing for a screenshot | New test added without updating yaml | Step B2 appends entries for new screenshot calls automatically |
| Screenshots created in separate class | Dev agent followed wrong spec | Screenshots MUST live inside existing E2E tests — see Integration Mandate |
| .NET: working dir mismatch | dotnet test runs from project dir | Use absolute path via `Path.Combine(Directory.GetCurrentDirectory(), "test-artifacts/screenshots", ...)` |
