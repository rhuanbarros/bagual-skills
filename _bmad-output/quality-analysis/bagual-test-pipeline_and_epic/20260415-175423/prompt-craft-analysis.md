# PromptCraftBot Analysis
**Skills:** `bagual-test-pipeline` + `bagual-bmad-implement-quick-epic`
**Date:** 2026-04-15
**Analyzer:** PromptCraftBot

---

## Assessment

**bagual-test-pipeline:** STRONG — significant repair already applied. The production failures identified by the author are directly addressed in the current prompts. The skill has been substantially rewritten since the failures occurred.

**bagual-bmad-implement-quick-epic:** ADEQUATE — structurally sound orchestrator, but the critical gap (no testing integration) remains unfixed in the prompts.

---

## Prompt Health Summary

| Dimension | bagual-test-pipeline | bagual-bmad-implement-quick-epic |
|---|---|---|
| SKILL.md size | 24 lines / ~323 tokens — optimal | 24 lines / ~285 tokens — optimal |
| Total context load | ~323 tokens (SKILL.md only; references loaded on demand) | ~6,050 tokens across 3 files |
| Progressive disclosure | YES — SKILL.md defers to references/ | PARTIAL — workflow.md + story-processor.md both loaded at once |
| Config header present | NO (workflow.md has no frontmatter) | YES (workflow.md has header) |
| Progression conditions | NOT APPLICABLE (SKILL.md only; references are not standalone stages) | YES — story-processor and workflow have stage transitions |
| Self-containment | YES — all paths and inputs are explicit | YES |
| Structural anti-patterns | None detected | None detected |
| Token waste patterns | 0 detected | 0 detected |
| Back-references | 0 detected | 0 detected |

---

## Key Findings

### FINDING 1 — CRITICAL (epic skill): No testing phase, no bagual-test-pipeline integration
**Severity:** Critical  
**File:** `bagual-bmad-implement-quick-epic/workflow.md`, `story-processor.md`

The production failure summary confirms: "No testing phase — implemented all stories then marked done without verifying anything works." The current workflow.md and story-processor.md contain no step, check, or mention of running tests at any point. The pipeline moves: create-story → dev-story → code-review → mark done → retrospective, with zero testing verification.

This is the highest-priority gap. An epic pipeline that marks stories "done" without running tests provides a false quality signal identical to the failure that prompted this analysis.

**What is missing:**
- After all stories complete (between step 3 and step 4 in workflow.md), there is no invocation of `bagual-test-pipeline`
- story-processor.md has no step that runs unit tests after `dev-story` completes
- There is no pre-done-marking gate that verifies the implementation actually works

**Fix direction:** Add a step between the current step 3 (verify all stories done) and step 4 (deferred findings) in workflow.md that spawns `/bagual-test-pipeline` with `yolo` mode and at minimum `medium` coverage. If it fails, HALT the epic — do not mark done. Optionally also add a lightweight unit-test-only gate inside story-processor.md after step B (dev-story), so regressions are caught per-story rather than only at epic end.

---

### FINDING 2 — RESOLVED (pipeline skill): Stack assumption now fixed
**Severity:** Informational (was Critical, now resolved)

The original failure: "Assumed JS/TS stack — referenced playwright.config.ts, npx playwright test — when project is actually C# + xUnit + Playwright .NET."

The current workflow.md (Step 0) now contains explicit multi-stack detection logic: it scans for `.csproj`/`.sln`/`global.json` (dotnet), `pytest.ini`/`conftest.py` (python), and `package.json` (js), preferring dotnet > python > js. Every subsequent step branches on `{detected_stack}`. The e2e-runner.md also carries full stack-conditional logic for every action.

This production failure is fully addressed in the current prompt text.

---

### FINDING 3 — RESOLVED (pipeline skill): Visual tests no longer use a separate class
**Severity:** Informational (was High, now resolved)

The original failure: "Agent created a separate VisualTestSuite.cs class for screenshots instead of integrating them into existing E2E tests."

The current visual-validation.md contains an explicit, named mandate — "INTEGRATION MANDATE — NON-NEGOTIABLE" — that prohibits creating a separate test class. It includes the exact anti-pattern by name (`VisualTestSuite.cs`) in a "What to never do" list, and the e2e-runner.md (Step B2) repeats this mandate verbatim. The prohibition is reinforced in two places in two different files.

This production failure is fully addressed. The double-placement is intentional and appropriate given how easily this constraint is violated.

---

### FINDING 4 — RESOLVED (pipeline skill): Silent E2E pass without required services
**Severity:** Informational (was Critical, now resolved)

The original failure: "E2E tests ran silently without PostgreSQL, .NET app, or Python API running — no warnings."

The current e2e-runner.md Step A is entirely dedicated to service verification. It discovers required services from config files, attempts TCP/HTTP checks per service, builds a `{services_manifest}`, and immediately returns `E2E RUNNER RESULT: FAILED` with a clear message if any service is down. The mandate text states: "Never proceed if any required service is down." The workflow.md RULES section also lists "E2E tests must FAIL LOUDLY if any required service is not running — never silently skip or accept errors."

This production failure is fully addressed.

---

### FINDING 5 — RESOLVED (pipeline skill): Accept-error patterns now audited
**Severity:** Informational (was Critical, now resolved)

The original failure: "ChatSmokeTest accepted error responses as success (IsAnyResponseOrErrorVisibleAsync)."

Step 0.5 of workflow.md is an entire pre-run audit step specifically targeting "accept error as valid outcome" patterns. It lists the exact C# assertion pattern (`Assert.True(successVisible || errorVisible)`) as a named violation type, flags it as a blocker, and either auto-fixes it via `bmad-quick-dev` or halts. The rule appears in both RULES section and the violation table in e2e-runner.md.

This production failure is fully addressed.

---

### FINDING 6 — RESOLVED (pipeline skill): E2E mocking violations now audited
**Severity:** Informational (was Critical, now resolved)

The original failure: "E2E tests used stubs/mocks (KnowledgeSearchTestDataFixture replaced real Python API)."

Step 0.5 catalogs four violation types with dotnet/js/python-specific pattern names: HTTP stub listeners (WireMock, HttpListener, nock, msw), in-memory database substitutes (UseInMemoryDatabase, SQLite), accept-error patterns, and silent skips. The e2e-runner.md ANTI-PATTERNS MANDATE table also covers all of these with a "why it's wrong" explanation for each.

This production failure is fully addressed.

---

### FINDING 7 — RESOLVED (pipeline skill): Coverage selection now present
**Severity:** Informational (was Medium, now resolved)

The original failure: "No coverage level selection."

INITIALIZATION in workflow.md now contains a full coverage selection UX: a three-option prompt (Small/Medium/High) with numeric target mappings (60/80/95), inference from a provided numeric target, and yolo-mode default (medium/80). The args documentation in SKILL.md mentions `[coverage_target]` and `yolo`.

This production failure is fully addressed.

---

### FINDING 8 — RESOLVED (pipeline skill): Data seeding and cleanup
**Severity:** Informational (was High, now resolved)

The original failure: "Data seeding before E2E and cleanup after were systematically forgotten."

The ADVERSARIAL TESTING MANDATE injected into every subagent prompt in Step 2 contains: "Create complete test data and fixtures — never rely on pre-existing data in the environment." The mandate is explicit that tests must be self-contained with respect to data. The fix-loop prompts in Steps 3 and 5 preserve this mandate by passing it verbatim to `bmad-quick-dev`.

This production failure is addressed at the mandate level. Note: the mandate sets the rule but relies on subagent compliance. There is no structural verification step that confirms data seeding occurred. This is an acceptable tradeoff given the mandate's strength and placement.

---

### FINDING 9 — MEDIUM (pipeline skill): No startup script creation gate in workflow.md
**Severity:** Medium

The e2e-runner.md Step A creates `docs/e2e-startup.md` when no startup script is found. However, the orchestrator workflow.md has no awareness of this file. If the startup doc is created during one run and services are still down, the runner returns FAILED with "See docs/e2e-startup.md" — which is correct. But the orchestrator's fix loop (Step 5) passes the failure to `bmad-quick-dev` with instructions to "fix the source code," not to help the user start services. A developer reading the HALT message at the orchestrator level gets "E2E tests still failing after 3 fix iterations" without a clear pointer to the service startup issue.

**Fix direction:** In the Step 5 E2E fix loop, when the failure report contains "Required services not running," the orchestrator should HALT immediately with a service-specific message rather than burning 3 fix iterations on an infrastructure problem that code changes cannot solve.

---

### FINDING 10 — LOW (pipeline skill): `story-processor` path in e2e-runner step C uses `npx` for dotnet projects
**Severity:** Low

In e2e-runner.md Step C, the `unknown` stack fallback tries `npx playwright test` before `dotnet test`. For a confirmed dotnet project (`{detected_stack}` == "dotnet"), this is not a problem — the dotnet branch runs correctly. But if stack detection ever produces `unknown` for a C# project, the runner will attempt the wrong command first before falling back. This is a minor edge case because Step 0 has robust detection logic.

---

### FINDING 11 — LOW (epic skill): story-processor.md Step D has no action body
**Severity:** Low  
**File:** `bagual-bmad-implement-quick-epic/story-processor.md`, line 232-234

Step D ("Mark story as done") has a goal description but no `<action>` elements inside the step — only an `<output>` line. The actual update to `sprint-status.yaml` and `{story_file}` is described in the `goal` attribute only. This is structurally ambiguous: the agent must infer the implementation from the goal text, which is a known failure mode for step-based prompts.

**Fix direction:** Add explicit `<action>` elements: read `{sprint_status}`, update the story key status to "done", update `last_updated`, write the file. Same for `{story_file}` Status field.

---

### FINDING 12 — LOW (epic skill): `review_iteration` error message says "5" instead of "2"
**Severity:** Low  
**File:** `bagual-bmad-implement-quick-epic/story-processor.md`, line 199

The HALT message in Step C when `dev-story` fails during a review fix reads: "Review iteration: {review_iteration}/5". The loop cap is 2, not 5. The number 5 is a stale reference from an earlier version of the prompt and will produce a misleading error message.

**Fix direction:** Change `/5` to `/2` in the error message on line 199.

---

### FINDING 13 — LOW (pipeline skill): `e2e_runner_path` uses `.claude/skills/` prefix — not passed to E2E sub-agent
**Severity:** Low

In workflow.md INITIALIZATION, `e2e_runner_path` is set to `.claude/skills/bagual-test-pipeline/references/e2e-runner.md`. This is the correct path for the orchestrator's own context. However, when this path is passed to the isolated E2E runner sub-agent, that agent's working directory may differ. The sub-agent prompt says "Read and follow ALL instructions in the file: {e2e_runner_path}" — if the sub-agent uses a different working directory, the relative path will resolve incorrectly.

**Fix direction:** In the orchestrator, resolve `e2e_runner_path` to an absolute path using `{project-root}` before passing it to the sub-agent.

---

## Strengths

### bagual-test-pipeline

1. **Mandate injection pattern is excellent.** The ADVERSARIAL TESTING MANDATE and E2E ANTI-PATTERNS MANDATE are inserted verbatim into every subagent prompt, not referenced by pointer. This eliminates context-gap failures where sub-agents would ignore rules they didn't receive.

2. **Progressive disclosure is well-implemented.** SKILL.md is a clean 24-line entry point. All implementation detail lives in `references/`. The e2e-runner runs as an isolated agent reading its own file — it never pollutes the orchestrator's context window.

3. **Stack detection is thorough and prioritized.** Detecting dotnet > python > js with explicit file markers prevents the JS assumption that caused the original failure. The detection result gates every subsequent action.

4. **Service verification fail-loud is well-structured.** Step A of e2e-runner builds a manifest, checks each service independently, and returns a structured FAILED block with per-service details. The pattern is both machine-readable (for the orchestrator to parse) and human-readable.

5. **Mocking audit pre-pass (Step 0.5) is well-placed.** Running the audit before any test generation prevents the pipeline from building on top of a corrupted baseline.

6. **Visual validation is correctly scoped.** Activation is conditional on frontend detection, disabled for backend-only projects, and explicitly overridable via env var. The dual-check (layout + semantic) is well-articulated and the "semantic data consistency" framing is particularly strong.

7. **Fix loop caps prevent infinite loops.** Every fix loop is bounded at 3 iterations with a structured HALT that writes a report and gives a re-run command.

### bagual-bmad-implement-quick-epic

1. **Context isolation per story is the right architecture.** Spawning an isolated sub-agent per story prevents context bleed where a failing story poisons the orchestrator's reasoning about subsequent stories.

2. **Deferred findings pattern is pragmatic.** Rather than blocking the pipeline on a 3rd review iteration, findings are deferred to a batch fix pass at epic end. This balances throughput against quality and the batch re-validation step ("re-validate each finding first — some may already be resolved") prevents stale work.

3. **Spec correction in review loop is novel.** Step C distinguishes between code findings and spec-level intent gaps, applies minimal corrections to the story file before re-running `dev-story`, and appends lessons to `{spec_lessons}`. This closes the feedback loop between implementation and specification.

4. **Fail-fast story gating.** The orchestrator re-reads `sprint-status.yaml` after each story agent completes and halts if the story is not marked done. This prevents silent failures where a sub-agent reports success but produces no disk state change.

5. **Thin orchestrator rule is enforced.** workflow.md explicitly states "You DO NOT implement code, run sub-skills, or manage story state yourself" and the prompts are consistent with this — all work is delegated to sub-agents.
