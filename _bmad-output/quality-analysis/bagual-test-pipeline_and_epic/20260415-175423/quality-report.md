# Quality Report: bagual-test-pipeline + bagual-bmad-implement-quick-epic

**Grade:** Poor  
**Date:** 2026-04-15  
**Skill path:** `/home/rhuan/2_temporario/bagual-skills/bagual-test-pipeline + bagual-bmad-implement-quick-epic`  
**Scanners run:** 8 distinct scanner runs (6 LLM analysis passes + 2 lint prepass scripts per skill pair)

---

## Narrative

These two skills are analyzed as an integrated system: an epic implementation pipeline (`bagual-bmad-implement-quick-epic`) that is meant to produce feature code, and a test pipeline (`bagual-test-pipeline`) that is meant to verify it. The pair suffered real production failures — the agent assumed a JS stack on a C# project, ran E2E tests silently against stopped services, accepted error responses as test success, generated a separate `VisualTestSuite.cs` instead of integrating screenshots, and marked an entire epic "done" without running a single test.

**The test pipeline has been substantially repaired.** Stack detection now runs before any command is issued. E2E runs fail loudly if any required service is down. The mocking audit catalogs six violation types by name. The Integration Mandate in `visual-validation.md` explicitly names the `VisualTestSuite.cs` anti-pattern. Fix loops are capped and structured. All six critical production failures that touched the test pipeline alone have been addressed in the current prompt text.

**The epic pipeline has not been repaired.** It still has no testing phase. Stories are marked "done" after code review without any test execution. The test pipeline is never invoked. The two skills do not interact. This is the same failure mode that caused the original production incident.

Beyond the integration gap, a deeper structural problem runs across both skills: nearly every deterministic gate — stack detection, service health checks, mock pattern scanning, coverage threshold comparison — is delegated to LLM reasoning at runtime. When these gates fail, they fail silently or with hallucinated results. The production failures were not failures of intent; the mandates were present. They were failures of enforcement: LLM reasoning substituted for deterministic scripts at every critical checkpoint.

The result is a skill pair that is **aspirationally complete but structurally non-enforcing**. The rules exist. The gates do not.

---

## Grade: Poor

The Poor grade reflects the combination of: (1) a broken integration — the primary system purpose is unachievable in the current state because the epic pipeline never invokes the test pipeline; (2) two critical subagent-chain violations in the epic skill that prevent it from executing as written; (3) systematic over-reliance on LLM reasoning for deterministic validation work that caused every documented production failure; and (4) residual gaps in data seeding and E2E project isolation that affect standalone test pipeline correctness.

The test pipeline alone, evaluated in isolation, would grade Fair. It has been meaningfully repaired and the internal cohesion is strong. The epic pipeline alone would grade Poor. Together, as a system that is supposed to deliver verified software, the grade is Poor because the verification half is not connected.

---

## Broken Items (Must Fix Before Use)

### 1. Epic pipeline subagent-chain violation — story-processor.md
**File:** `bagual-bmad-implement-quick-epic/story-processor.md`  
**Severity:** Critical  
`story-processor.md` is loaded as a subagent by `workflow.md` Step 2. Inside `story-processor.md`, Steps A, B, and C each spawn their own Agent subagents (`bmad-create-story`, `bmad-dev-story`, `bmad-code-review`). Subagents cannot spawn subagents in the current execution model. The chain `orchestrator → story-processor-agent → [create-story, dev-story, code-review]` is not executable as written. The pipeline cannot run.

**Fix:** Treat `story-processor.md` as an instruction document the orchestrator reads and follows directly, not a file delegated to a subagent. Remove the "Spawn Agent to read story-processor.md" pattern; replace with "Read story-processor.md and execute its steps."

### 2. Epic pipeline subagent-chain violation — workflow.md
**File:** `bagual-bmad-implement-quick-epic/workflow.md`  
**Severity:** Critical  
`workflow.md` Step 2 is the source of the spawn that produces the chain violation above. Both files are implicated. The violation is at both orchestrator and processor levels.

**Fix:** Same root fix as above — restructure Step 2 so the orchestrator executes story-processor logic directly.

### 3. Epic pipeline has no testing phase
**File:** `bagual-bmad-implement-quick-epic/workflow.md`  
**Severity:** Critical  
The pipeline ends at retrospective without any invocation of `bagual-test-pipeline` or any test execution. Stories are marked "done" after code review, which is a static analysis step. Running code that actually passes tests is never verified. This reproduces the exact production failure: "implemented all stories then marked done without verifying anything works."

**Fix:** Add a step between Step 4 (deferred findings) and Step 5 (retrospective) that invokes `/bagual-test-pipeline high yolo`. If the test pipeline fails, halt and require manual resolution before marking the epic done. Consider also a per-story lightweight test gate inside story-processor.md after `dev-story` completes.

### 4. Mocking audit (Step 0.5) runs before test generation — never re-runs after
**File:** `bagual-test-pipeline/references/workflow.md` (Step 0.5 placement)  
**Severity:** Critical  
The pre-generation audit in Step 0.5 is correct for detecting pre-existing violations. But violations introduced by the test generator in Step 2 are never audited. This is the exact root cause of the `KnowledgeSearchTestDataFixture` failure: the test generator produced a stub after the audit ran, and the stub was never caught. Step 0.5 must also run immediately after Step 2 completes.

**Fix:** Add a second mocking audit after Step 2 (test generation) before Step 3 (run tests). The same audit procedure applies; it catches violations introduced by `bmad-testarch-atdd` and `bmad-testarch-automate`.

### 5. Wrong command name in epic HALT messages
**File:** `bagual-bmad-implement-quick-epic/workflow.md:133,143`  
**Severity:** High  
Two HALT recovery messages tell the user to re-run `/bagual-bmad-implement-epic` (missing "quick"). The skill's correct name is `/bagual-bmad-implement-quick-epic`. A user following the recovery instruction invokes a nonexistent skill.

**Fix:** Change both occurrences to `/bagual-bmad-implement-quick-epic`.

### 6. Missing `## Overview` and `## On Activation` sections in both SKILL.md files
**File:** `bagual-test-pipeline/SKILL.md:1`, `bagual-bmad-implement-quick-epic/SKILL.md:1`  
**Severity:** High  
Both files jump from frontmatter directly to prose without the required structural sections. The scanner framework requires these sections to prime AI comprehension and declare the activation entry point. The content exists but is unheadered.

**Fix:** Add `## Overview` before the opening prose and `## On Activation` with a minimal delegation line (e.g., "Load config. Follow all instructions in references/workflow.md.") in both SKILL.md files.

### 7. Story-processor Step D has no action body
**File:** `bagual-bmad-implement-quick-epic/story-processor.md:232-234`  
**Severity:** High  
Step D ("Mark story as done") has a goal description and an output tag but no `<action>` block. The agent must infer what to do from the XML `goal` attribute text. Since the parent orchestrator halts if this step doesn't produce the correct disk state change, a misfire here halts the entire pipeline.

**Fix:** Add explicit `<action>` elements: read `{sprint_status}`, update story key status to "done", update `last_updated`, write the file. Repeat for the story file's Status field.

---

## Themes (Root Cause Groups)

### Theme 1: LLM Doing Deterministic Work (All Production Failures Trace Here)
**Severity:** Critical  
Every documented production failure happened at a checkpoint that should have been a script but was instead LLM reasoning. Stack detection reasoned from file evidence instead of running `ls *.csproj`. Service health checked via LLM simulation instead of a TCP connect script. Mock scanning was pattern-based LLM inspection instead of ripgrep. Coverage threshold was LLM arithmetic on stdout instead of XML parsing. Each of these is 100% deterministic, zero-hallucination work if scripted. As LLM reasoning, each carries a probability of being wrong, slow, or silently accepted even when the answer is wrong. Estimated 3.5-7 minutes of unnecessary LLM reasoning per full pipeline run, with non-zero failure probability at every gate.

### Theme 2: No Integration Between Epic and Test Pipeline
**Severity:** Critical  
The two skills do not interact. The epic pipeline never invokes the test pipeline. Stories are marked done after static code review. Epics are marked done without test execution. The system as a whole does not deliver verified software — it delivers implemented software. This is the primary architectural gap and the direct cause of the production failure that motivated this analysis.

### Theme 3: Audit and Enforcement Gaps (Rules Without Gates)
**Severity:** High  
The mandates are present — no mocking in E2E, integration mandate for screenshots, stack-conditional commands throughout. But the enforcement mechanisms have holes: the mocking audit doesn't re-run after generation; the visual integration mandate has no verification step that checks for separate screenshot classes after test generation; the E2E fix loop enters code-fix mode even when the failure is an infrastructure problem (service down); data seeding and cleanup are declared as mandates but have no structural step or verification. Rules can be forgotten or overridden in context. Gates cannot.

### Theme 4: Epic Skill Structural Defects (Cannot Execute As Written)
**Severity:** Critical  
The epic skill has two critical subagent-chain violations (story-processor.md loaded as a subagent but contains its own subagent spawns), a missing action body in Step D, a stale iteration count in an error message, and four path-standards violations. These are structural defects that make the skill non-executable in its current form, independent of the integration gap.

### Theme 5: Missing Sections and Path Standards Violations
**Severity:** High  
Both SKILL.md files are missing required structural sections. The epic skill has four high-severity path-standards violations: `workflow.md` and `story-processor.md` belong in `references/` not at skill root, and two `_bmad` path references lack the `{project-root}` prefix required by BMad convention. The test pipeline has clean path standards.

---

## Strengths

### Stack detection is thorough and prioritized correctly
`workflow.md` Step 0 in the test pipeline detects dotnet first (`.csproj`, `.sln`, `global.json`), then python, then js — with explicit priority ordering that matches real-world precedence. The detection result gates every subsequent command. This addresses the root cause of the original JS-on-C# failure at the design level, even if it should be backed by a script.

### The no-mock mandate is layered across four independent checkpoints
No-mocking is enforced in the RULES section, the Step 0.5 pre-run audit, the e2e-runner's Anti-Patterns Mandate table, and the fix-loop mandate. Each appears in a different agent's context window. A single mandate can be forgotten; four layered ones are structurally harder to violate.

### Visual validation integration mandate is unambiguous and named
`visual-validation.md` explicitly names the failure pattern (`VisualTestSuite.cs`), explains why it is wrong, and repeats the prohibition verbatim in `e2e-runner.md` Step B2. The dual-placement is intentional and correct for context isolation.

### Service verification is fail-loud and immediate
e2e-runner Step A builds a per-service manifest, checks each independently, and returns `E2E RUNNER RESULT: FAILED` immediately on any DOWN service. The fail-loud pattern is correct and well-specified.

### Fix loops are capped, bounded, and mandated not to cheat
Every fix loop (unit tests, E2E) is capped at 3 iterations with a structured HALT on exhaustion. The fix mandate explicitly prohibits weakening tests, lowering thresholds, or introducing mocks as a "fix." This is the correct structure for an adversarial pipeline.

### Epic deferred-findings pattern is pragmatic and sound
Per-story review loops cap at 2 iterations and defer remaining findings to a batch fix at epic end. The batch fix re-validates each finding before acting (some may already be resolved). This balances throughput against quality without permanently deferring debt.

### Mandate injection into subagent prompts eliminates context gap failures
The Adversarial Testing Mandate and E2E Anti-Patterns Mandate are inserted verbatim into every subagent prompt rather than referenced by pointer. A subagent that reads only its own prompt file still receives the full mandate. This is the correct pattern for distributed agent execution.

---

## Detailed Analysis

### Structure

Both skills use a thin SKILL.md dispatch shell that delegates to reference files — an appropriate architecture for orchestrator-style skills. The test pipeline's four-file structure (SKILL.md, workflow.md, e2e-runner.md, visual-validation.md) has clean separation of concerns. The epic skill's three-file structure (SKILL.md, workflow.md, story-processor.md) is internally logical but has the file placement defects noted above.

Both SKILL.md files are missing required structural sections (`## Overview`, `## On Activation`). The epic skill has four path-standards violations. The test pipeline passes all path standards.

### Prompt Craft

**Test pipeline:** STRONG. 24-line SKILL.md at ~323 tokens. All detail in references/ loaded on demand. Zero waste patterns. Zero back-references. The mandate injection pattern (verbatim in every subagent prompt) is particularly well-designed for an adversarial pipeline. Progressive disclosure is fully implemented.

**Epic skill:** ADEQUATE for current scope. SKILL.md at ~285 tokens optimal. workflow.md and story-processor.md at ~6,050 total tokens are loaded together, which is larger than ideal. Prompt health shows prompts with progression conditions present. The primary craft gap is what is absent: no test execution in the prompt flow at all.

### Cohesion

Within the test pipeline, internal cohesion is very high. Instructions align across all four files. Anti-patterns are enumerated consistently. The variable threading ({detected_stack}, {unit_tests_passing}, {e2e_tests_passing}, {visual_passed}) is clean and forward-flowing. Stage flow: Diagnostic → Mocking Audit → Framework → Unit Tests → Fix Loop → E2E Runner → E2E Fix Loop → Report.

Cross-skill cohesion between the two skills is essentially zero. There is no invocation path, no shared interface contract, no handoff point. The epic pipeline has no way to surface test results to the retrospective, and the test pipeline has no soft-fail mode the epic could use without halting.

### Execution Efficiency

**Test pipeline:** Structurally efficient. Stack detection runs once and threads forward. Diagnostic and mocking audit run before any subagent is spawned. E2E runner is isolated. Fix loops cap at 3 iterations. One efficiency issue: e2e-runner Steps A and B re-run on every fix iteration in Step 5 even though service status and log fixtures do not change between fix attempts. These steps could be skipped on re-run iterations.

**Epic skill:** Two critical subagent-chain violations prevent execution as written. Structurally, the orchestrator model is correct (thin orchestrator, isolated story agents, disk state as communication channel). The missing test phase is a correctness gap, not an efficiency gap.

### Developer Experience

The test pipeline provides meaningful diagnostic output at each stage and a structured final report. Fix loop HALT messages include a re-run command. The startup doc creation fallback (`docs/e2e-startup.md`) turns an invisible failure into an actionable document. Visual validation failure messages include per-screenshot detail.

The epic pipeline's developer experience is adequate for implementation but opaque on quality. A developer who ran the epic to completion received no signal about whether the code works — the epic was "done" with no test output, no coverage report, no verification artifact.

---

## Recommendations (Ranked)

### Rank 1 — Fix subagent-chain violations in epic skill
**Resolves:** Epic pipeline non-executable (Themes 4, broken items 1-2)  
**Effort:** Medium  
Restructure `workflow.md` Step 2 to execute story-processor logic directly rather than spawning a subagent that then spawns further subagents. Option B (treat story-processor.md as an instruction document the orchestrator reads and follows) is preferred — it preserves isolation intent without requiring story-processor.md rewrite.

### Rank 2 — Add test pipeline integration to epic workflow
**Resolves:** No testing phase in epic pipeline (Themes 2, broken item 3)  
**Effort:** High  
Insert a new step between Step 4 (deferred findings) and Step 5 (retrospective) in `workflow.md` that invokes `/bagual-test-pipeline high yolo`. Resolve the interface mismatch: add a `soft-fail` mode to bagual-test-pipeline so the epic can receive a failure report and continue to retrospective rather than halting. Pass the test report path to the retrospective invocation.

### Rank 3 — Add a second mocking audit after Step 2 (post-generation)
**Resolves:** Violations introduced by test generator invisible to audit (Theme 3, broken item 4)  
**Effort:** Low  
Add a second invocation of the mocking audit procedure immediately after Step 2 (test generation) completes, before Step 3 runs unit tests. This is the same audit procedure as Step 0.5; the only change is placement.

### Rank 4 — Script the three critical deterministic gates
**Resolves:** LLM-as-validator causing all production failures (Theme 1)  
**Effort:** Medium  
Implement in priority order: (a) `scripts/check-services.sh` — TCP connect with 3-second timeout per service; exit code drives the E2E gate, not LLM interpretation; (b) `scripts/detect-stack.sh` — filesystem check for `.csproj`/`pytest.ini`/`package.json`; (c) `scripts/scan-e2e-mocks.sh` — ripgrep for forbidden patterns in E2E test paths only. These three directly caused the three most severe production failures.

### Rank 5 — Move epic skill files to references/ and fix path standards
**Resolves:** Path-standards violations and structure defects (Theme 5)  
**Effort:** Low  
Move `workflow.md` and `story-processor.md` to `references/workflow.md` and `references/story-processor.md`. Update all internal references. Fix bare `_bmad` path references to use `{project-root}/_bmad` prefix.

### Rank 6 — Add `## Overview` and `## On Activation` sections to both SKILL.md files
**Resolves:** Missing structural sections (Theme 5, broken items 6)  
**Effort:** Low  
Add the two required headers. Content already exists inline — it just needs to be headed. `## On Activation` for each should be a one-liner that loads config and delegates to the appropriate workflow file.

### Rank 7 — Add data seeding step to e2e-runner
**Resolves:** Data seeding and cleanup systematically absent (Theme 3)  
**Effort:** Medium  
Add Step A2 (after service verification, before log capture) in `e2e-runner.md` that checks for and executes a data seed script or creates one if absent. Add Step E2 (after visual validation) for cleanup. Alternatively, define a `_bmad/test-data/seed.yaml` contract and script its execution with `scripts/check-e2e-lifecycle.sh`.

### Rank 8 — Discriminate infrastructure failures from code failures before E2E fix loop
**Resolves:** Fix loop wasted on environment problems (Theme 3)  
**Effort:** Low  
In `workflow.md` Step 5 entry point: check if the E2E failure reason is "Required services not running." If yes, HALT with an environment-setup message immediately instead of entering the code fix loop.

### Rank 9 — Fix stale iteration count and wrong command name in epic error messages
**Resolves:** Misleading error messages (broken items 5, workflow integrity findings)  
**Effort:** Trivial  
`story-processor.md:199` — change "/5" to "/2" in the HALT message. `workflow.md:133,143` — change `/bagual-bmad-implement-epic` to `/bagual-bmad-implement-quick-epic`.

### Rank 10 — Add `scripts/check-coverage.sh` and `scripts/build-story-queue.py`
**Resolves:** Coverage thresholds silently bypassed; YAML parsing risk in epic queue builder (Theme 1)  
**Effort:** Medium  
Coverage enforcer: parse cobertura XML (dotnet), pytest stdout (python), coverage-summary.json (js); exit code drives the fix loop. Story queue builder: deterministic YAML filter for story keys matching epic pattern, excluding done stories.
