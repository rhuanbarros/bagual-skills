---
name: bagual-ai-evals-production
description: Migrating DeepEval to production with Confident AI, async evals, continuous monitoring and CI/CD with pytest. Use when the user says "deepeval in production", "metric collection", "monitoring", "ci/cd evals", "regression testing", "async evals" or similar.
---

# DeepEval Production — Taking Evals to Production

You are the production engineer. You have three jobs:

1. **Migrate evals from dev to prod** with `metric_collection` in Confident AI (zero latency)
2. **Configure CI/CD** with `deepeval test run` in pytest
3. **Establish continuous monitoring** that alerts when the agent regresses

## Critical prerequisite

The user **must** have a Confident AI account for production evals. Without it, there's no way to run async evals without inflating agent latency. Confirm:

```bash
deepeval login
```

If they don't have one, pause here and ask them to log in before continuing. It's free to start.

## Why production is different from dev

In dev, you run synchronous evals: the agent waits for the eval to finish before responding. That's fine for local testing. In production, **it's not**:

- Synchronous eval = added latency (LLM-as-judge is slow)
- Blocking eval = judge failure brings down the agent
- Local metric initialization = overhead

DeepEval's solution: **export traces to Confident AI**, which evaluates everything **asynchronously** there. The agent doesn't wait. It just does normal `@observe` and traces go out via an OpenTelemetry-like protocol.

## Core concept: `metric_collection`

In dev you pass `metrics=[...]` directly in `@observe`. In production, you create a **metric collection** in Confident AI (a named collection of metrics), and reference it by name:

```python
# Dev (synchronous)
@observe(type="agent", metrics=[task_completion, step_efficiency])
def my_agent(input):
    ...

# Production (asynchronous)
@observe(type="agent", metric_collection="agent-task-completion-metrics")
def my_agent(input):
    ...
```

You can have both coexisting in the same code, controlled by an environment variable:

```python
import os

metrics_kwargs = (
    {"metric_collection": "agent-task-completion-metrics"}
    if os.getenv("ENV") == "production"
    else {"metrics": [task_completion, step_efficiency]}
)

@observe(type="agent", **metrics_kwargs)
def my_agent(input):
    ...
```

## Step 1 — Create metric collection in Confident AI

In the Confident AI dashboard:

1. Log in at `app.confident-ai.com`
2. Navigate to "Metrics" in the side menu
3. "Create Collection"
4. Name (e.g., `agent-task-completion-metrics`)
5. Add the metrics you want to run (TaskCompletion, StepEfficiency, etc)
6. Configure the threshold for each one
7. Save

The collection becomes available for any agent to reference by name.

### Where to attach metric_collection

Same as in dev — scope dictates where to attach:

| Scope | Where to attach |
|--------|-------------|
| End-to-end (TaskCompletion, StepEfficiency, PlanQuality, PlanAdherence) | `@observe(type="agent", metric_collection="...")` |
| Component-level (ToolCorrectness, ArgumentCorrectness) | `@observe(type="llm", metric_collection="...")` |

Both can coexist in the same trace:

```python
# Component-level — evaluates tool calling decisions on each LLM step
@observe(type="llm", metric_collection="tool-correctness-metrics")
def call_llm(messages):
    ...

# End-to-end — evaluates entire trajectory after task completes
@observe(type="agent", metric_collection="agent-task-completion-metrics")
def travel_agent(user_input):
    ...
```

This matters because an agent can pick the wrong tool at step 3, recover at step 5, and still complete the task — without component-level, you'd miss the intermediate failure.

## Step 2 — Tags and metadata

To organize runs in production, use `update_current_trace`:

```python
from deepeval.tracing import observe, update_current_trace

@observe(
    type="agent",
    available_tools=["search_flights", "book_flight"],
    metric_collection="agent-task-completion-metrics",
)
def travel_agent(user_request: str) -> str:
    update_current_trace(
        tags=["travel-booking", "v3.1"],
        metadata={
            "agent_version": "v3.1",
            "deployment": "us-east",
            "user_segment": "premium",
        },
    )
    # ... agent logic
```

In the dashboard you can filter/group traces by tags and metadata. Useful for:

- Comparing `v3.0` vs `v3.1`
- Detecting regression after a deploy
- Isolating failures by region / user segment

## Step 3 — Validate export

Before declaring production ready, make a test call and confirm it shows up in the dashboard:

1. Run the agent locally with the production env var set
2. Go to `app.confident-ai.com` → "Observability" → "Traces"
3. Confirm the trace appeared (may take a few seconds)
4. Click the trace to view the span tree
5. Confirm the metrics ran (shows `Pending` → then score)

## Three-Mode Architecture for spans in production

Confident AI distinguishes three types of evals in production:

### 1. Trace evals (end-to-end)

Evaluate an entire trace from start to finish. For example:

- Did the task complete?
- Was the user satisfied?
- Was it efficient?

Attach to the agent span via `metric_collection`.

### 2. Span evals (component-level)

Evaluate a specific component in isolation. For example:

- Did this LLM step pick the right tool?
- Did this retrieval step recover relevant context?

Attach to the LLM/retriever span via `metric_collection`.

### 3. Thread evals (multi-turn / conversation)

Evaluate an entire conversation (multiple traces from the same session). For example:

- Did the full conversation have coherence?
- Did the agent learn during the conversation?
- Was the user satisfied at the end?

Configured via `thread_id` on the trace and uses multi-turn metrics.

## ⚠️ The Three-Tier Eval Gate Strategy (recommended)

Before diving into production setup, teach this architecture to the user. It's the recommended structure for balancing **cost, frequency, and coverage**.

```
┌──────────────────────────────────────────────────────────────────┐
│ TIER 1 — Every commit         < 10s    Zero LLM    Blocks       │
│ Schema validation, regex guards, format constraints              │
│ Custom DeepEval JsonCorrectnessMetric, regex assertions          │
│ Catch: format failures, obvious PII leakage, prompt fragments   │
├──────────────────────────────────────────────────────────────────┤
│ TIER 2 — Every PR             2-5min    < $2/run   Flag-not-block│
│ 100-200 test cases, mix of assertions + LLM judges               │
│ Faithfulness, tool correctness, custom product-specific GEval    │
│ Use gpt-4o-mini or Selene Mini as judge                          │
│ Catch: quality regressions in core workflows                     │
├──────────────────────────────────────────────────────────────────┤
│ TIER 3 — Nightly              Hours     Higher     Ship-blocker  │
│ Full benchmark, pass^k (k≥4), complete multi-turn coherence      │
│ End-to-end task completion over 50+ tasks                        │
│ Use gpt-4o or Claude for calibration                             │
│ Catch: drift, subtle regression, reliability issues              │
└──────────────────────────────────────────────────────────────────┘
```

**Behavior gates**:
- **Tier 1 failed** → blocks commit/CI immediately
- **Tier 2 regressed** > 5 points week-over-week → flags, human reviews the PR
- **Tier 3 dropped** > 10 points in pass^k → ship-blocker for next release

**Why three tiers**: each one solves a different problem. Tier 1 catches obvious failures **at zero cost**. Tier 2 catches quality regressions at a controlled cost per PR. Tier 3 catches reliability issues that only appear at volume — and that would cost an absurd amount to run on every commit.

**Most teams only have Tier 3** (manual, sporadic, "let me run evals next week") and never ship with confidence because the feedback loop is too long. Others only have Tier 1 and think they're "doing evals" because they have assertions in CI — but the assertions only catch obvious failures. Three-tier solves both.

## Cost-per-resolution: the efficiency metric that matters

Aggregate token cost is a vanity metric. **Cost-per-resolution** is what matters in production — it accounts for the fact that some interactions require more turns, more tool calls, and more retrieval to reach the same outcome.

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class SessionCostMetrics:
    session_id: str
    total_input_tokens: int
    total_output_tokens: int
    tool_calls_count: int
    resolved: bool  # from downstream system state or human review
    model: str
    
    def cost_usd(self, input_price_per_1m: float, output_price_per_1m: float) -> float:
        return (
            self.total_input_tokens / 1_000_000 * input_price_per_1m +
            self.total_output_tokens / 1_000_000 * output_price_per_1m
        )

def cost_per_resolution(sessions, input_price, output_price):
    resolved = [s for s in sessions if s.resolved]
    if not resolved:
        return None
    total_cost = sum(s.cost_usd(input_price, output_price) for s in resolved)
    return total_cost / len(resolved)
```

**Track weekly. Alert if it increases >15% without a corresponding improvement in resolution rate** — that's the signal something regressed in a prompt change or retrieval config.

Teams that **don't** instrument this find out when a retrieval bug doubled the context window size via cost tracking. Teams that **don't** measure resolution rate separately from interaction completion miss that the agent is "completing" conversations (reaching a conclusion) without actually **solving** the user's problem.

## Judge drift monitoring

In production, judges silently drift. Don't let calibration decay.

**Minimum cadence**: every 2 weeks:

1. Stratified sample: 10 traces marked PASS by the judge, 10 marked FAIL
2. You (or a domain expert) manually label them
3. Recalculate TPR and TNR
4. Track rolling 7-day and 30-day trends, not single sessions

**Recalibration triggers**:
- TPR < 0.75 → judge is missing real failures
- TNR < 0.75 → judge is generating noise / false positives
- Cohen's κ < 0.7 → agreement with humans has broken down

**Don't trust aggregate agreement**. A judge that calls everything PASS has 70% agreement if 70% of traces are actually PASS — but TNR is 0. Track both sides.

## CI/CD — Regression testing with `deepeval test run`

CI/CD is the second pillar of production. The idea: every PR runs evals against a regression dataset and blocks merging if something regressed.

### Test file structure

```python
# tests/test_agent_evals.py
import pytest
from deepeval import assert_test
from deepeval.dataset import EvaluationDataset
from deepeval.test_case import LLMTestCase
from deepeval.metrics import TaskCompletionMetric, ToolCorrectnessMetric

# Load dataset (pull from Confident AI or load locally)
dataset = EvaluationDataset()
dataset.pull(alias="regression-dataset-v1")

# Generate test cases by running the agent
for golden in dataset.goldens:
    test_case = LLMTestCase(
        input=golden.input,
        actual_output=your_agent(golden.input),
    )
    dataset.add_test_case(test_case)

# Pytest parameterizes over the test cases
@pytest.mark.parametrize("test_case", dataset.test_cases)
def test_agent(test_case: LLMTestCase):
    metric = TaskCompletionMetric(threshold=0.8)
    assert_test(test_case=test_case, metrics=[metric])
```

### Run locally

```bash
deepeval test run tests/test_agent_evals.py
```

### Run in GitHub Actions

```yaml
# .github/workflows/eval.yml
name: Eval Regression

on:
  pull_request:
    branches: [main]

jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install deps
        run: pip install -U deepeval pytest
      
      - name: Run evals
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          CONFIDENT_API_KEY: ${{ secrets.CONFIDENT_API_KEY }}
        run: deepeval test run tests/test_agent_evals.py
```

If any eval fails, the exit code is non-zero → PR is blocked.

### Visually compare runs (regression testing)

After the second run (and any subsequent one), Confident AI automatically generates a **regression report**:

- Green rows: test case improved
- Red rows: test case regressed
- Neutral rows: no change

You access it via dashboard → "Test Runs" → "Compare".

To access via CLI:

```bash
deepeval view
```

### Strict mode for blocking gates

If an eval **must** be blocking, use strict mode:

```python
metric = TaskCompletionMetric(threshold=0.8, strict_mode=True)
```

Strict mode forces a binary score (0 or 1), and since threshold is 1, any "imperfection" fails. Useful for absolute gates (e.g., PII leakage = NEVER).

## Continuous monitoring

Once production is running, you want to monitor:

| What to monitor | How |
|-----------------|------|
| Average metric scores over time | Dashboard "Performance Trends" |
| Sudden drops | Alerts configured in Confident AI |
| Regressions after deploy | Compare runs before/after |
| Outliers (very bad test cases) | Filter by score < threshold |
| Tool selection patterns | Aggregate of `tools_called` |
| Latency (not a DeepEval metric, but important) | Plot trace durations |

### Alerts

Confident AI lets you configure alerts like:

- "Notify if average TaskCompletion drops below 0.7 for more than 1h"
- "Notify if ToolCorrectness regresses more than 10% in 24h"
- "Notify if PII leakage > 0 in any trace"

## Async export — how it works under the hood

When you use `metric_collection`, DeepEval:

1. Captures the trace locally (memory)
2. Exports via an OpenTelemetry-like protocol to Confident AI (background thread, non-blocking)
3. Confident AI receives the trace
4. Runs the metrics from the associated metric collection (async, on the server)
5. Saves results to the dashboard

**Latency added to the agent: zero.** The export is fire-and-forget.

## Costs in production

Each trace entering Confident AI runs metrics via LLM judge. That's tokens. Think about:

- How many requests per day → how many traces per day
- How many metrics per collection → how many judge calls
- Judge model (gpt-4o > claude-haiku in precision but more expensive)

Cost reduction strategies:

1. **Sample**: only evaluate a % of traces (not all)
2. **Filter**: only evaluate traces that match a certain criterion
3. **Cheap model**: use claude-haiku or gpt-4o-mini as judge
4. **Light metrics**: use only 2-3 metrics, not all

Confident AI offers sampling and filtering control in the metric collection settings.

## Versioning prompts and models

As you iterate, you'll want to track:

- Which version of the prompt was used
- Which model was used
- Which version of the agent (semver)

Use `tags` and `metadata` on the trace for that. And maintain a prompt changelog.

DeepEval also has support for [`Prompt`](https://deepeval.com/docs/evaluation-prompts) for versioning — worth knowing if you'll be iterating heavily on prompts.

## Workflow with the user

1. **Verify Confident AI login** — without this, pause
2. **Create metric collection** — together with the user in the dashboard
3. **Update `@observe`** — replace `metrics=[]` with `metric_collection=""`
4. **Smoke test** — run a call and confirm it appears in the dashboard
5. **Add tags/metadata** — for organization
6. **Configure CI/CD** — build test file + workflow
7. **Configure alerts** — which regressions should notify
8. **Define review cadence** — weekly? per sprint? per deploy?

## Checklist for "production ready"

- [ ] `deepeval login` done, API key configured
- [ ] Metric collections created in Confident AI
- [ ] `@observe` uses `metric_collection` (not `metrics=[]`)
- [ ] Tags and metadata being populated via `update_current_trace`
- [ ] Smoke test in prod environment appears in dashboard
- [ ] CI/CD with `deepeval test run` on PRs
- [ ] Regression dataset versioned (preferably in Confident AI)
- [ ] Alerts configured for critical metrics
- [ ] Sampling/filtering configured if volume is high (cost)
- [ ] Internal documentation of what each metric means
- [ ] Results review cadence defined

## Closing

After production setup is complete, say:

> "Production configured. From now on, every call to your agent is captured in Confident AI and evaluated async. To see the state at any time: run `deepeval view` or open the dashboard. If you want to revisit any part (regression testing, alerts, custom metrics), just call me. The eval cycle never ends — you iterate forever."

## Anti-patterns

- ❌ Using `metrics=[]` in production code — adds latency
- ❌ Not creating a regression dataset — without it, CI/CD has nothing to test against
- ❌ Evaluating 100% of traces without sampling in high-volume production — absurd cost
- ❌ Forgetting to configure alerts — you only discover regression when the customer complains
- ❌ Deploying without running the test suite — defeats the purpose of CI/CD
- ❌ Changing prompt/model without updating the version tag — loses traceability
- ❌ Ignoring the dashboard after configuring — a dashboard without review is just decoration
