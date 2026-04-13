---
title: 'Eval Scenario Quality Infrastructure'
type: 'feature'
created: '2026-04-13'
status: 'done'
baseline_commit: '1a75998327823e1b653d485fe7ba76794131a317'
context: []
---

<frozen-after-approval reason="human-owned intent — do not modify unless human renegotiates">

## Intent

**Problem:** All existing bagual-ai-evals skills produce eval scenarios that "coach" the LLM — the user_message explicitly contains information (document format, file type, IDs) that in production arrives via system state (InjectedState, metadata, tool context). Evals pass because user messages are informationally complete; production fails because real user messages are not.

**Approach:** (1) Create a new `bagual-ai-evals-scenario-review` skill that audits existing eval scenarios for realism, generates adversarial variants, and produces a coverage gap report. (2) Embed a mandatory "Production Realism Gate" into `bagual-ai-evals-build-dataset` so the problem is caught at creation time. (3) Register the new skill in `bagual-ai-evals-help` routing.

## Boundaries & Constraints

**Always:**
- Preserve all existing skill names and SKILL.md frontmatter structure.
- The realism audit must include a concrete checklist: "What info is in user_message that wouldn't be there in production?" — per scenario, not per run.
- Adversarial variants must include at least: minimal-intent, ambiguous, conflicting, and off-topic variants.
- Coverage matrix must map scenarios against: happy path, error path, adversarial, and information-gap axes.

**Ask First:**
- If the user's eval scenarios reference a framework not yet seen (AutoGen, Semantic Kernel, etc.), ask before assuming injection mechanism.

**Never:**
- Do not change `bagual-ai-evals-error-analysis` scope — open coding stays focused on failure discovery, not scenario review.
- Do not require a code execution environment — all review steps must be conversational/manual.
- Do not add a new skill for each concern — bundle realism audit + adversarial generation + coverage into one `bagual-ai-evals-scenario-review` skill.

## I/O & Edge-Case Matrix

| Scenario | Input / State | Expected Output / Behavior | Error Handling |
|---|---|---|---|
| Coached scenario caught | user_message contains format hint ("It is a PDF") that should come from metadata | Skill flags HIGH severity: "user_message bridges an information gap the LLM can't bridge in production" + generates adversarial variant with "helo" as user_message | N/A |
| Clean scenario passes | user_message has no leaked context, all required info comes from system prompt or tool | Skill marks scenario PASS, suggests one adversarial variant anyway (off-topic) | N/A |
| No existing scenarios | User hasn't built a dataset yet | Skill redirects to `bagual-ai-evals-build-dataset` with warning about realism gate | N/A |
| Coverage gap detected | No error-path or adversarial scenarios exist | Coverage matrix shows RED for missing axes, recommends minimum 1 scenario per gap | N/A |

</frozen-after-approval>

## Code Map

- `bagual-ai-evals-scenario-review/SKILL.md` — new skill file to create (does not exist yet)
- `bagual-ai-evals-build-dataset/SKILL.md` — existing skill, add Production Realism Gate section
- `bagual-ai-evals-help/SKILL.md` — existing routing hub, register the new skill

## Tasks & Acceptance

**Execution:**
- [x] `bagual-ai-evals-scenario-review/SKILL.md` — CREATE — new skill implementing the 4-phase workflow: (1) Realism Audit, (2) Adversarial Variants, (3) Coverage Matrix, (4) Quality Report. See Design Notes for phase details.
- [x] `bagual-ai-evals-build-dataset/SKILL.md` — EDIT — insert a "Production Realism Gate" section after the scenario creation steps. Gate asks: "For each scenario: what information is in user_message that the LLM would NOT have in production?" If coaching detected, redirect to adversarial variant generation or `bagual-ai-evals-scenario-review`.
- [x] `bagual-ai-evals-help/SKILL.md` — EDIT — add `bagual-ai-evals-scenario-review` to the skill map table and routing logic: trigger when user says "review evals", "check scenario quality", "realistic scenarios", "adversarial evals", or "coverage gap".

**Acceptance Criteria:**
- Given a set of coached eval scenarios, when `bagual-ai-evals-scenario-review` is called, then it produces at least one HIGH-severity finding per scenario where user_message contains information that should come from system state.
- Given coached scenarios, when the skill runs Phase 2, then it produces at minimum one adversarial variant per scenario with a minimal-intent user_message (e.g., "helo", "do it", "yes").
- Given any set of scenarios, when Phase 3 runs, then the coverage matrix explicitly marks missing axes (adversarial, error-path, information-gap) as gaps, not as implicitly covered.
- Given the updated `bagual-ai-evals-build-dataset`, when a user creates a scenario, then the Realism Gate fires before the scenario is finalized and cannot be skipped.
- Given `bagual-ai-evals-help`, when a user says "realistic scenarios", then it routes to `bagual-ai-evals-scenario-review`.

## Design Notes

**Phase 0 — Entry Guard:**
Before Phase 1: if user has no scenarios, redirect immediately to `bagual-ai-evals-build-dataset` with message: "Build your dataset first — come back here after you have at least 5 scenarios to review." Do not attempt to audit an empty dataset.

**Phase 1 — Realism Audit (per scenario):**
Ask for each scenario: What does the system prompt tell the LLM it can access? What does the user_message actually provide? Does the user_message "bridge" information the LLM can't access in production (InjectedState, metadata, tool context, orchestrator fields)? Severity: HIGH = user_message contains required operational context (format, IDs, flags). MEDIUM = user_message contains optional context that biases the LLM toward correct behavior. LOW = user_message is neutral.
**Fallback when user doesn't know the system prompt:** Use heuristic detection. Scan each `input` field for: file format tokens (pdf, image, docx, jpg), UUID/ID-like strings, state-flag vocabulary (tier, role, metadata key names, orchestrator-sounding verbs). Flag matches as candidate-coached. Ask: "Would the LLM produce the same output if the user had sent only 'process this' instead?"
**Multi-turn ConversationalGolden:** Apply the audit to the `scenario` field instead of `input`. Ask: does the scenario description contain info the simulated user wouldn't know (format, IDs, system state)? Does `expected_outcome` encode system-state information?

**Phase 2 — Adversarial Variants (per scenario):**
Four mandatory variant types: (a) Minimal-intent — strip all domain hints, keep only the action word ("helo", "proceed", "do it"); (b) Ambiguous — user message allows 2+ valid interpretations of the required parameter; (c) Conflicting — user message explicitly contradicts what metadata/state would say; (d) Off-topic — user message is completely unrelated to the expected task. Minimum output: one variant per type per HIGH/MEDIUM scenario (4 variants minimum). Optional (e) State-staleness — user message is valid but system state is in an unexpected lifecycle phase (e.g., state["booking"] is already confirmed when user says "confirm it").

**Phase 3 — Coverage Matrix:**
Preamble: detect whether the agent uses tools. If tool-free: replace tool-call rows with reasoning/output rows (correct output, incorrect output, hallucinated output, refused task). If tool-using: use standard matrix. Axes: [happy-path, error-path, adversarial, information-gap (LLM lacks required context)]. Fill matrix: ✅ covered, ⚠️ partial, ❌ missing. Flag any axis with zero coverage as a blocker.

**Phase 4 — Quality Report:**
Lead with blocking findings (HIGH), then warnings (MEDIUM), then gaps from the matrix. Close with: minimum recommended additions (one scenario per ❌ gap) and a one-line realism score: "X/Y scenarios are production-realistic."

## Spec Change Log

**Loop 1 — bad_spec loopback (2026-04-13):**
- Triggering findings: (E1) Phase 1 stalls when user doesn't know system prompt; (E2) tool-free agent causes Coverage Matrix blocker to mis-fire; (E3) ConversationalGolden datasets bypass entire Realism Gate; (A1) "No existing scenarios" not handled in skill.
- Amendments: Added Phase 0 entry guard (empty dataset redirect); added heuristic detection fallback to Phase 1 for unknown system prompts; added ConversationalGolden audit path to Phase 1; added tool-free agent detection branch to Phase 3.
- Known-bad state avoided: skill stalling on first question; Coverage Matrix incorrectly blocking valid tool-free datasets; coached multi-turn scenarios passing undetected; skill attempting to audit a nonexistent dataset.
- KEEP: Phase 1 HIGH/MEDIUM/LOW severity definitions unchanged; Phase 2 four variant types A-D with all examples unchanged; Phase 3 matrix structure with four axes unchanged; Phase 4 report format unchanged; Production Realism Gate in build-dataset unchanged.

## Verification

**Manual checks (if no CLI):**
- Open `bagual-ai-evals-scenario-review/SKILL.md`: verify the 4 phases are distinct sections with clear instructions and no Portuguese text.
- Open `bagual-ai-evals-build-dataset/SKILL.md`: search for "Realism Gate" — section must be present and contain the "what info in user_message wouldn't exist in production?" question.
- Open `bagual-ai-evals-help/SKILL.md`: search for "scenario-review" — must appear in both the routing table and trigger list.

## Suggested Review Order

**New skill — core design**

- Entry guard prevents empty-dataset stall; redirects to build-dataset
  [`SKILL.md:33`](../../bagual-ai-evals-scenario-review/SKILL.md#L33)

- Phase 1 realism audit: 4-item checklist + severity classification (HIGH/MEDIUM/LOW)
  [`SKILL.md:45`](../../bagual-ai-evals-scenario-review/SKILL.md#L45)

- Heuristic detection fallback when user doesn't know system prompt
  [`SKILL.md:68`](../../bagual-ai-evals-scenario-review/SKILL.md#L68)

- Multi-turn ConversationalGolden audit path (audits `scenario` field, not `input`)
  [`SKILL.md:80`](../../bagual-ai-evals-scenario-review/SKILL.md#L80)

- Phase 2 adversarial variants: 4 mandatory types + optional state-staleness variant
  [`SKILL.md:106`](../../bagual-ai-evals-scenario-review/SKILL.md#L106)

- Phase 3 coverage matrix: tool-use detection branch + simplified matrix for tool-free agents
  [`SKILL.md:174`](../../bagual-ai-evals-scenario-review/SKILL.md#L174)

- Phase 4 quality report: severity-weighted findings + realism score
  [`SKILL.md:225`](../../bagual-ai-evals-scenario-review/SKILL.md#L225)

- Framework injection patterns table (incl. multi-agent handoff row + orchestrator ID note)
  [`SKILL.md:257`](../../bagual-ai-evals-scenario-review/SKILL.md#L257)

**Build-dataset integration**

- Production Realism Gate section (mandatory checkpoint before finalizing)
  [`SKILL.md:394`](../../bagual-ai-evals-build-dataset/SKILL.md#L394)

- Numbered script step 6 (gate wired into the workflow)
  [`SKILL.md:388`](../../bagual-ai-evals-build-dataset/SKILL.md#L388)

**Help routing**

- New Question 4.5 with spot-check for "yes" self-attestation
  [`SKILL.md:84`](../../bagual-ai-evals-help/SKILL.md#L84)

- Q4.7 consequence framing for "No" path
  [`SKILL.md:118`](../../bagual-ai-evals-help/SKILL.md#L118)

- Updated skill map table (scenario-review row + description note)
  [`SKILL.md:153`](../../bagual-ai-evals-help/SKILL.md#L153)
