# Execution Efficiency Analysis
**Skills:** bagual-test-pipeline + bagual-bmad-implement-quick-epic
**Date:** 2026-04-15
**Scanner:** ExecutionEfficiencyBot

---

## Assessment

**bagual-test-pipeline:** Structurally efficient. The orchestrator correctly separates concerns — it runs bash directly for test commands, delegates to subagents for skill invocations, and isolates the E2E phase into a dedicated runner. The stage ordering is sound (diagnostic → mocking audit → framework → unit tests → E2E → report). No critical efficiency defects.

**bagual-bmad-implement-quick-epic:** Contains two pre-pass-flagged critical issues (subagent-chain violations in both workflow.md and story-processor.md). Beyond those, the orchestrator model is correct in design but has a structural gap: no testing phase exists after implementation. The pipeline ends at retrospective without any verification that the implemented stories actually work.

**Integration gap (cross-skill):** No orchestration story exists for when the epic pipeline calls the test pipeline. The epic skill marks stories done after code review passes, with no execution of bagual-test-pipeline at any point. This is the largest systemic gap across the pair.

---

## Key Findings

### bagual-test-pipeline

**[HIGH] Step 2 runs two subagents sequentially when only the first output is needed to proceed**
- `bmad-testarch-atdd` and `bmad-testarch-automate` are spawned back-to-back (workflow.md lines 314–362).
- atdd generates the base tests; automate expands coverage gaps. These are genuinely sequential (automate depends on atdd output), so the ordering is correct.
- However: the failure handler for the automate agent issues only a warning and continues. This is intentional (non-blocking expansion), but the prompts repeat the full Adversarial Testing Mandate verbatim twice. The mandate text is large and could be extracted into a single shared reference block passed once and referenced by both agents rather than duplicated.
- Classification: low/cosmetic — not an efficiency defect, but increases prompt token overhead.

**[MEDIUM] E2E runner spawned twice per fix iteration in Step 5**
- In the E2E fix loop (workflow.md lines 493–565), each iteration spawns a `bmad-quick-dev` agent and then immediately spawns the full e2e-runner agent again. The e2e-runner re-runs Steps A through E each time (service verification, log capture setup, screenshot helper check, full test run, visual validation).
- Steps A and B (service verification, log capture setup) are idempotent checks that add latency on every fix iteration with no new information. Service status does not change between fix attempts. Log capture fixtures do not change between fix attempts. Step B2 (visual validation setup) is also unlikely to change.
- Optimization: the e2e-runner prompt in fix iterations (Step 5) could pass a flag `skip_setup=true` to bypass Steps A, B, and B2 and go directly to Step C (run tests) and Step D (evaluate screenshots). This avoids re-doing service discovery and fixture scaffolding on fix iterations 2 and 3.
- Classification: medium — in a project with many services, Step A alone can take 15-30 seconds per iteration × up to 3 iterations = meaningful latency.

**[LOW] Step 4 and Step 5 are split into two numbered steps but function as one phase**
- Step 4 runs the E2E runner once and Step 5 is the fix loop. The initial run in Step 4 is structurally identical to the re-runs in Step 5, but they live in separate steps with separate iteration counters. This means the "3 fix iterations" cap effectively allows 4 total E2E runner executions (1 in Step 4 + 3 in Step 5), which may be surprising to authors reading the cap.
- Classification: low — not an efficiency defect, but the intent of the cap is ambiguous.

**[LOW] Adversarial Testing Mandate copied verbatim into every subagent prompt**
- The mandate block (approximately 120 words) is pasted in full into both Step 2 agent prompts and the fix-loop agent prompt. For a pipeline that runs 3+ subagents, this is a repeated cost.
- Classification: low — each mandate copy is a fixed overhead per agent invocation, not blocking.

### bagual-bmad-implement-quick-epic

**[CRITICAL] Subagent-chain violation in story-processor.md**
- story-processor.md (Steps A, B, C) spawns Agent subagents for `bmad-create-story`, `bmad-dev-story`, and `bmad-code-review`. story-processor.md is itself loaded as a subagent by workflow.md Step 2.
- Subagents cannot spawn subagents in the current execution model. This means the chain: orchestrator → story-processor-agent → [create-story agent, dev-story agent, code-review agent] is not executable.
- Fix required: the orchestrator (workflow.md) must inline the story-processor logic and manage all story sub-skill spawning directly, or story-processor.md must be treated as an instruction document the orchestrator reads and executes, not a file delegated to a subagent.
- Classification: critical — the pipeline cannot function as written.

**[CRITICAL] Subagent-chain violation in workflow.md**
- workflow.md Step 2 spawns a story-processor agent that itself contains subagent spawn instructions (see above). The violation is at both levels.
- Classification: critical — same root cause as above.

**[HIGH] No test phase in the epic pipeline**
- After all stories are done (Step 3), the pipeline runs deferred findings (Step 4) and retrospective (Step 5) and marks the epic done.
- No call to bagual-test-pipeline at any point. Stories are marked done based on code review pass, not on whether the implementation actually runs and passes tests.
- The user-identified production failure ("implemented all stories then marked done without verifying anything works") is a direct consequence of this missing step.
- Classification: high — this is a correctness gap, not just an efficiency gap.

**[MEDIUM] Step C review loop cap is 2 iterations, but the comment in story-processor.md line 198 says "5"**
- The loop guard is `{review_iteration} less than 2` (correctly limiting to 2 iterations).
- The failure output message at line 198 reads "Review iteration: {review_iteration}/5".
- This is a stale copy-paste artifact and will confuse agents reading the failure output.
- Classification: medium — incorrect user-facing message, potential source of misinterpretation.

**[LOW] Deferred findings file deletion races with re-run behavior**
- Step 4 (workflow.md line 204) deletes `{deferred_findings_file}` after the batch fix. If the batch fix agent fails partway through, the file is not deleted. On re-run, the file accumulates new deferred findings on top of old ones.
- Classification: low — the batch fix agent is instructed to re-validate findings before acting, which partially mitigates stale accumulation.

**[LOW] Sprint-status re-read after each story is a sequential disk read inside the story loop**
- After each story agent completes, the orchestrator re-reads sprint-status.yaml to verify the story was marked done (workflow.md lines 137-147). For epics with many stories, this adds a small overhead on each iteration. This is unavoidable given the current architecture (the story processor writes status to disk as its only communication channel), so it is acceptable.
- Classification: low — no optimization available without changing the communication protocol.

### Integration Gap (Cross-Skill)

**[HIGH] No orchestration story for epic → test-pipeline handoff**
- bagual-bmad-implement-quick-epic does not call bagual-test-pipeline at any stage.
- There is no defined handoff point: the epic skill has no step that says "after all stories are done, run the test pipeline before declaring the epic complete."
- Consequence: an epic can be fully "done" in sprint-status.yaml while the implemented code has never been tested end-to-end. Code review (bmad-code-review) reviews code against the story spec, not against running behavior.
- The natural insertion point is between Step 4 (deferred findings) and Step 5 (retrospective): after all code is fixed, run the full test pipeline to confirm the implementation works. If the pipeline fails, halt before marking the epic done.
- Classification: high — this is the primary architectural gap between the two skills.

**[MEDIUM] No shared configuration for which stack the test pipeline should use**
- Both skills read `_bmad/bmm/config.yaml` for project settings, but bagual-test-pipeline auto-detects the stack on every run. If the epic skill were to invoke the test pipeline, it would need to pass no special arguments (stack is auto-detected). This is fine.
- However, bagual-test-pipeline's coverage level defaults to "medium" (80%) in yolo mode, which may be too low for a post-epic validation gate. There is no mechanism for the epic skill to specify coverage expectations.
- Classification: medium — the default would work but the coverage level should be configurable from the epic invocation.

---

## Optimization Opportunities

### Priority 1 (fix before use): Subagent-chain violations in epic skill
- story-processor.md must not be loaded as a subagent if it contains subagent spawn instructions.
- Resolution options:
  - (A) Inline story-processor logic into workflow.md and have the orchestrator directly spawn create-story, dev-story, and code-review agents.
  - (B) Treat story-processor.md as an instruction document that the orchestrator loads and follows, not a file delegated to a subagent. This requires removing the "Spawn Agent subagent to read story-processor.md" pattern and replacing it with "Read story-processor.md and execute its steps directly."
  - Option B preserves the single-story isolation intent and does not require rewriting workflow.md. Preferred.

### Priority 2 (correctness gap): Add test-pipeline gate to epic completion
- Insert a new step between the current Step 4 (deferred findings) and Step 5 (retrospective) in workflow.md.
- The step should: invoke bagual-test-pipeline in yolo mode with a coverage target passed as an argument or defaulting to medium; if it fails, halt the epic pipeline and require manual resolution before marking the epic done.
- Example insertion in workflow.md:
  ```
  <step n="4.5" goal="Validate implementation by running the full test pipeline">
    <output>[Step 4.5] Running bagual-test-pipeline to validate epic implementation...</output>
    <action>Spawn an Agent subagent with this prompt:
      "Run the skill /bagual-test-pipeline with args: {coverage_target} yolo
       This is running inside an automated pipeline. Proceed automatically."
    </action>
    <check if="Agent failed or test pipeline HALTED">
      <output>PIPELINE HALTED at Step 4.5: test pipeline failed. All stories are implemented but tests are not passing. Fix the failures and re-run.</output>
      <action>HALT</action>
    </check>
  </step>
  ```

### Priority 3 (latency reduction): Skip e2e-runner setup steps on fix iterations
- In Step 5 of bagual-test-pipeline, the e2e-runner prompt on re-run iterations should include an explicit instruction to skip Steps A, B, and B2 and proceed directly to running tests (Step C).
- This reduces per-fix-iteration overhead by skipping service checks (no services change between fix attempts) and fixture scaffolding (already in place from Step 4).

### Priority 4 (correctness): Fix stale "/5" iteration count in story-processor.md
- Change "Review iteration: {review_iteration}/5" to "Review iteration: {review_iteration}/2" in the halt message at story-processor.md Step C.

### Priority 5 (token efficiency): Extract Adversarial Testing Mandate as a named block
- Define the mandate once in workflow.md (e.g., in a `<mandate name="adversarial">` block) and reference it by name in each subagent prompt instead of duplicating the text. This reduces orchestrator message size on each spawn.

---

## What Is Already Efficient

**bagual-test-pipeline:**
- Stack detection runs once in Step 0 and the result (`{detected_stack}`) is passed to all subsequent steps and subagents. No redundant detection across phases.
- The diagnostic scan (Step 0) and mocking audit (Step 0.5) run before any subagent is spawned, preventing wasted subagent invocations on projects that are not in a valid state.
- The e2e-runner is isolated in its own agent with explicit input variables, preventing context bleed from the unit test phase.
- Fix loops are capped at 3 iterations per phase with immediate halt and report on exhaustion — avoids infinite retry spirals.
- Coverage level inference from numeric target (Step 0 Input Parsing) avoids requiring two arguments when one is sufficient.
- Visual validation activation is conditional on frontend detection — backend-only projects skip the screenshot/vision overhead entirely.
- Service verification (e2e-runner Step A) fails loudly and immediately rather than running tests and letting them fail mysteriously — correct fail-fast behavior.
- The final report (Step 6) explicitly distinguishes unit mock usage (acceptable) from E2E mock usage (violation) — this is a clear and useful separation.

**bagual-bmad-implement-quick-epic:**
- The orchestrator correctly reads sprint-status.yaml to build the story queue rather than hard-coding story lists — correctly handles partial epic runs (stories already done are skipped).
- Deferred findings pattern is sound: deferring minor review issues to a batch pass rather than blocking story progress on every finding avoids excessive re-review loops.
- The story-processor's dual communication channel design (disk state as implicit result) is correct for subagent isolation — the orchestrator verifies the outcome by reading the file rather than parsing agent output.
- Epic auto-selection (when no epic number is provided) avoids requiring the user to look up the current epic number.
- Git commit happens at story granularity (not epic granularity), which produces meaningful atomic commits in the project history.
