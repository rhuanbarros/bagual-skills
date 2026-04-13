---
name: bagual-ai-evals-run-and-analyze
description: Running local evals and analyzing/interpreting DeepEval results. Use when the user says "run evals", "analyze results", "interpret score", "evals_iterator", "deepeval test run", "diagnose failure", or similar.
---

# DeepEval Run and Analyze — Running and Interpreting Evals

You are the executor and analyst. You have two jobs:

1. **Run the first eval** with the setup the user has (instrumented agent + dataset + metrics)
2. **Analyze the results** and say what to change

## Prerequisites — check before starting

- [ ] Agent instrumented with `@observe` (skill `bagual-ai-evals-instrument`)
- [ ] Dataset with goldens created (skill `bagual-ai-evals-build-dataset`)
- [ ] Metrics defined and configured (skill `bagual-ai-evals-pick-metrics`)
- [ ] LLM key configured (skill `bagual-ai-evals-setup`)

If anything is missing, route to the corresponding skill before proceeding.

## The 3 ways to run evals

| Method | When to use | Command |
|-------|-------------|---------|
| **`evals_iterator`** | Default case for agents (recommended standard) | `python script.py` |
| **`evaluate()`** | Test cases already ready, without using dataset with loop | `python script.py` |
| **`deepeval test run`** | CI/CD, integration with pytest | `deepeval test run test_file.py` |

## Method 1 — `evals_iterator` (default for agents)

This is what you'll use 95% of the time for agents. It:

1. Iterates over the dataset's goldens
2. For each golden, calls the agent (which is decorated with `@observe`)
3. Collects traces automatically
4. Runs the metrics (end-to-end and component-level)
5. Aggregates the results

```python
from deepeval.dataset import EvaluationDataset, Golden
from deepeval.tracing import observe
from deepeval.metrics import (
    TaskCompletionMetric,
    StepEfficiencyMetric,
    ToolCorrectnessMetric,
    ArgumentCorrectnessMetric,
)
from deepeval.test_case import ToolCall

# Metrics
task_completion = TaskCompletionMetric(threshold=0.7)
step_efficiency = StepEfficiencyMetric(threshold=0.7)
tool_correctness = ToolCorrectnessMetric(threshold=0.7)
argument_correctness = ArgumentCorrectnessMetric(threshold=0.7)

# Dataset
dataset = EvaluationDataset(goldens=[
    Golden(
        input="Book a flight from NYC to Paris for next Monday",
        expected_tools=[ToolCall(name="search_flights"), ToolCall(name="book_flight")],
    ),
    Golden(
        input="I want to go to Paris",
        expected_tools=[],
    ),
])

# Component-level metrics → on the LLM span
@observe(type="llm", metrics=[tool_correctness, argument_correctness])
def call_llm(messages):
    response = client.chat.completions.create(model="gpt-4o", messages=messages, tools=tools_schema)
    update_current_span(
        input=messages[-1]["content"],
        output=str(response),
        expected_tools=get_current_golden().expected_tools,
    )
    return response

# Agent
@observe(type="agent", available_tools=["search_flights", "book_flight"])
def travel_agent(user_input):
    messages = [{"role": "user", "content": user_input}]
    while True:
        response = call_llm(messages)
        # ... loop logic ...
        if final:
            return final_answer

# Run — end-to-end metrics are passed here
for golden in dataset.evals_iterator(metrics=[task_completion, step_efficiency]):
    travel_agent(golden.input)
```

When this cell finishes, DeepEval prints the report in the terminal. If logged into Confident AI, it also sends to the dashboard.

### Typical terminal output

```
========================================================
Evaluating 2 test cases
========================================================

Test case 1: "Book a flight from NYC to Paris for next Monday"
  ✓ TaskCompletionMetric: 0.85 (threshold: 0.7) — PASSED
  ✓ StepEfficiencyMetric: 0.78 (threshold: 0.7) — PASSED
  ✓ ToolCorrectnessMetric: 1.00 (threshold: 0.7) — PASSED
  ✓ ArgumentCorrectnessMetric: 0.92 (threshold: 0.7) — PASSED

Test case 2: "I want to go to Paris"
  ✗ TaskCompletionMetric: 0.45 (threshold: 0.7) — FAILED
    Reason: Agent didn't ask for clarification on dates and origin.
  ✓ StepEfficiencyMetric: 0.95 (threshold: 0.7) — PASSED
  ✓ ToolCorrectnessMetric: 1.00 (threshold: 0.7) — PASSED  
  ✓ ArgumentCorrectnessMetric: 0.85 (threshold: 0.7) — PASSED

========================================================
Summary: 1/2 passed (50%)
========================================================
```

## Method 2 — `evaluate()` (ready test cases)

Use when you have ready `LLMTestCase`s (not goldens) and just want to run metrics on them:

```python
from deepeval import evaluate
from deepeval.metrics import AnswerRelevancyMetric

evaluate(
    test_cases=dataset.test_cases,  # or direct list
    metrics=[AnswerRelevancyMetric()],
)
```

## Method 3 — `deepeval test run` (CI/CD)

For integration with pytest:

```python
# test_my_agent.py
import pytest
from deepeval import assert_test
from deepeval.metrics import TaskCompletionMetric
from deepeval.test_case import LLMTestCase

dataset = ...  # loads the dataset

@pytest.mark.parametrize("test_case", dataset.test_cases)
def test_agent(test_case: LLMTestCase):
    metric = TaskCompletionMetric(threshold=0.7)
    assert_test(test_case=test_case, metrics=[metric])
```

Then run:

```bash
deepeval test run test_my_agent.py
```

This command treats each test case as a separate pytest test. It will show PASSED/FAILED per test case, and the exit code is non-zero if any fail — perfect for CI/CD.

For CI/CD details, see the `bagual-ai-evals-production` skill.

## After running — analyzing results

The part that matters: **interpreting what happened and deciding what to change**. Use this diagnostic tree:

### Diagnostic tree

```
TaskCompletionMetric LOW (< 0.7)?
│
├── YES → Where is the problem?
│   │
│   ├── ToolCorrectnessMetric LOW?
│   │   └── Agent picks the wrong tool
│   │       FIX: improve tool descriptions in the schema
│   │       FIX: improve tool names (make them descriptive)
│   │       FIX: reduce number of tools (LLM gets confused with too many)
│   │       FIX: add examples in the system prompt
│   │
│   ├── ArgumentCorrectnessMetric LOW?
│   │   └── Agent picks the right tool but with wrong args
│   │       FIX: improve tool schemas (types, required, enum)
│   │       FIX: add input/output examples
│   │       FIX: use a better model (gpt-4o vs gpt-3.5)
│   │       FIX: lower temperature (more deterministic)
│   │
│   ├── PlanQualityMetric LOW?
│   │   └── Agent doesn't create a coherent plan
│   │       FIX: improve system prompt (explicit CoT)
│   │       FIX: use a model with better reasoning
│   │       FIX: provide examples of good plans
│   │
│   ├── PlanAdherenceMetric LOW but PlanQuality OK?
│   │   └── Agent creates a good plan but doesn't follow it
│   │       FIX: force agent to re-read the plan before each step
│   │       FIX: structure the plan in a more rigid format
│   │       FIX: explicitly instruct "follow your plan"
│   │
│   └── Everything OK but TaskCompletion low?
│       └── Orchestration failure or edge case
│           FIX: review the agent's loop logic
│           FIX: add error handling
│           FIX: look at the raw trace to see what happened
│
├── NO (TaskCompletion OK) → Other metrics?
│   │
│   ├── StepEfficiencyMetric LOW?
│   │   └── Agent works but is inefficient
│   │       FIX: detect redundancy (same tool called 2x with same args)
│   │       FIX: cache tool results within a run
│   │       FIX: improve prompt to avoid circular reasoning
│   │
│   └── Custom metric (GEval) LOW?
│       └── Specific criterion not being met
│           FIX: depends on the criterion, but generally prompt engineering
```

### Common patterns you'll see

**Pattern A**: TaskCompletion high + StepEfficiency low
- **Diagnosis**: agent works but wastes steps
- **Action**: optimize (don't change logic, just reduce steps)

**Pattern B**: ToolCorrectness high + ArgumentCorrectness low
- **Diagnosis**: picks the right tool, wrong args
- **Action**: tool schemas need more detail

**Pattern C**: PlanQuality high + PlanAdherence low
- **Diagnosis**: plans well but doesn't execute the plan
- **Action**: more rigid structure or plan re-injection at each step

**Pattern D**: Everything passes except on edge case goldens
- **Diagnosis**: agent is good on the happy path, bad on hard cases
- **Action**: improve ambiguity handling in the prompt

**Pattern E**: Everything is random (passes today, fails tomorrow)
- **Diagnosis**: temperature too high or unstable prompt
- **Action**: lower temperature, more explicit prompt

### Reading the `reason` for each metric

When you pass `include_reason=True`, the metric returns a textual justification. **READ IT**. That's where you find the "why" behind the score.

Example:
```
TaskCompletionMetric: 0.45
Reason: The agent partially addressed the user request by searching for flights, 
but did not complete the booking step despite the user explicitly asking for it. 
The output ended with a list of options instead of a confirmation.
```

This tells you exactly what to change.

## ⚠️ Critical mental models before analyzing

These 3 insights radically change how you read eval results.

### 1. 70% pass rate is healthy. 95% is a red flag.

> If everything passes 95% of the time in your suite, your evals are measuring things your agent **already does well**.
> A well-designed suite derived from real failure patterns should produce a pass rate of **~70% in the first run**.

| Initial pass rate | Diagnosis | Action |
|-------------------|-------------|------|
| **95%+** | False safety. Suite doesn't test things that fail. | Go back to `bagual-ai-evals-error-analysis`, do trace review, derive product-specific criteria. |
| **70-85%** | **Healthy.** Has real signal. | Iterate on the agent, not the evals. |
| **40-70%** | Also OK — agent needs work but evals are calibrated | Prioritize categories with the worst score. |
| **<40%** | Definitions too loose OR agent fundamentally broken | Re-validate the judge definitions (bagual-ai-evals-custom-metric). |

If the user runs evals and everything passes, **that is a red flag**, not a green one. The function of evals is to catch failures — if they're not catching anything, they're not doing their job.

### 2. τ-bench fault taxonomy — classify failures instead of "quality dropped"

Instead of noting "quality score dropped", classify each failure in this taxonomy (entity × failure type). Converts post-mortems into **actionable** categories.

| Fault type | Description | Primary signal | Typical fix |
|------------|-----------|-----------------|------------|
| `goal_partially_completed` | Agent solved part of the task, missed subgoals | `ConversationCompletenessMetric < 1.0` | Prompt clarification, multi-intent handling |
| `used_wrong_tool` | Correct intent, wrong tool | Trajectory mismatch | Tool descriptions, schemas, naming |
| `used_wrong_tool_argument` | Correct tool, malformed args | Schema validation + audit | Schema docs in system prompt |
| `took_unintended_action` | Agent did something not requested | Policy DAG violation | Policy enforcement, ConversationalDAGMetric |

**Use this to group incidents**. If 80% of your incidents this week are `used_wrong_tool_argument`, the fix is **schema documentation in the system prompt**, not generic prompt rewriting. If you're seeing spikes of `took_unintended_action`, you have a policy enforcement problem that should be caught in CI before reaching prod.

### 3. Single-run failure may be variance, not a bug

Before declaring "this is a bug that needs fixing", **run the test case 4-8 times**. Calculate pass^k.

If pass^1 ≈ 70% and pass^4 ≈ 60%, it's low variance — agent is consistently good but imperfect. If pass^1 ≈ 70% and pass^4 ≈ 25%, it's high variance — agent is unstable. The fixes are different:

| Pattern | Diagnosis | Fix |
|--------|-------------|-----|
| Pass^1 high, pass^k close | Reliability OK, agent is dependable | Focus on specific cases that fail |
| Pass^1 high, pass^k collapses | High variance — instability | Lower temperature, more explicit prompt, more rigid decision logic |
| Pass^1 low | Consistent failure | Address the root cause — could be model, prompt, schema |

## Accessing local traces for deep debugging

If the metric doesn't tell you enough, go to the raw trace:

```python
from deepeval.tracing import trace_manager

# Run
travel_agent("...")

# Get traces
traces = trace_manager.get_all_traces_dict()

for trace in traces:
    print(f"\n=== Trace: {trace.get('input')[:50]}... ===")
    print(f"Output: {trace.get('output')}")
    
    # Go by span type
    for llm_span in trace.get("llmSpans", []):
        print(f"\n  LLM call:")
        print(f"    Input: {llm_span.get('input')}")
        print(f"    Output: {llm_span.get('output')}")
        print(f"    tools_called: {llm_span.get('tools_called')}")
    
    for tool_span in trace.get("toolSpans", []):
        print(f"\n  Tool: {tool_span.get('name')}")
        print(f"    Input args: {tool_span.get('input')}")
        print(f"    Output: {tool_span.get('output')}")
```

Use `trace_manager.clear_traces()` between runs to avoid accumulation.

## Confident AI — visualization

If logged in, everything appears there automatically. To view:

```bash
deepeval view
```

Opens the browser on the most recent test run. Advantages:

- Visual span tree (click to inspect inputs/outputs)
- Side-by-side comparison of runs (regression testing)
- Filters by test case status (passed/failed)
- Export reports to share with the team

## Iteration — the cycle

This is the cycle you'll repeat:

```
1. Run evals
2. Look at results
3. Identify the worst pattern (use the tree above)
4. Hypothesize ONE change
5. Apply the change
6. Re-run
7. Compare with before (Confident AI does this visually)
8. Keep (if improved) or revert (if worse)
9. Repeat
```

**Golden rule**: change **one thing at a time**. If you change prompt + model + tool at the same time, you won't know what helped.

## Caching — save tokens

DeepEval has built-in cache. If you run the same test cases multiple times (because you're iterating on the agent, not the metric), the cache can save evaluation tokens. Check the cache documentation if running is costly.

## Dealing with LLM judge failures

If the judge LLM fails (rate limit, timeout):

- DeepEval retries automatically (1 time by default)
- Can adjust via env vars: `DEEPEVAL_RETRY_MAX_ATTEMPTS`, etc
- If the error is `insufficient_quota` (OpenAI), no retry — you need to add credits

Common error:
```
Evaluations getting "stuck"?
```
→ Usually it's a rate limit. Reduce parallelism or switch to a cheaper model.

## Common hypotheses worth testing

When results are bad, these hypotheses are the first to test:

1. **Bad system prompt** — redo with more clarity, more examples, more structure
2. **Undersized model** — gpt-3.5 → gpt-4o, claude-haiku → claude-sonnet
3. **Temperature too high** — lower to 0.1-0.3 for agents
4. **Vague tool descriptions** — rewrite each description thinking "if I were the LLM, would I know when to call this?"
5. **Weak tool schemas** — add `enum`, `required`, examples
6. **Loop without break condition** — agent loops until max_iterations
7. **No error handling** — tool fails, agent doesn't know how to handle it
8. **No clarification step** — agent assumes instead of asking

## Workflow with the user

1. **Verify prerequisites** (instrumentation, dataset, metrics)
2. **Build the execution script** (method 1 = `evals_iterator`)
3. **Run for the first time** — see output in terminal
4. **Read together with the user** — go through the report, metric by metric
5. **Diagnosis** — use the tree above to identify the worst pattern
6. **Hypothesize ONE change** — which prompt/config/tool to change
7. **Support iteration** — they apply it, re-run, you compare

## Closing

After running and analyzing, depending on the result:

**If ready for production**:
> "Great results! Next step is taking this to production with continuous monitoring. Want me to call `bagual-ai-evals-production`?"

**If needs iteration**:
> "I'll suggest a change based on the diagnosis: {hypothesis}. Apply it and we'll re-run. When you re-run, call me again here so we can analyze the comparison."

**If needs custom metric**:
> "From what we've seen, there's a criterion not covered by the built-in metrics: {thing}. To evaluate that, we'll create a custom GEval. Want me to call `bagual-ai-evals-custom-metric`?"

## Anti-patterns

- ❌ Running and not looking at results — eval without analysis is a waste
- ❌ Changing multiple things at the same time — can't isolate the cause
- ❌ Tweaking the metric instead of the agent — measuring wrong vs. bad agent
- ❌ Ignoring `include_reason` — that's where the diagnostic value lives
- ❌ Running 1000 goldens before the first analysis — small batch first
- ❌ Accepting a score of 0.7 as "good enough" without questioning the chosen threshold
