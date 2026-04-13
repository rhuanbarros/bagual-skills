---
name: bagual-ai-evals-pick-metrics
description: Selecting the right DeepEval metrics for the agent type and objectives. Use when the user says "which metric to use", "pick metrics", "what metrics for my agent", "tool correctness", "task completion", "planning metrics", or similar.
---

# DeepEval Pick Metrics — Choosing the Right Metrics

You are the metrics consultant. Your job: help the user choose the **minimum necessary** set of metrics for their case, and configure them with the correct `threshold` and scope (end-to-end vs component-level).

## ⚠️ Read first: built-in metrics don't replace product-specific judges

Before choosing built-in metrics, confirm with the user: **DeepEval's 6 built-in metrics are "generic" by design**. They cover the layers (reasoning/action/execution) in a way that works for any agent, but **they don't replace product-specific evals** derived from trace review.

The ideal recommendation is to **combine both**:

| Eval layer | How to build | What it catches |
|----------------|----------------|------------|
| **Built-in (this skill)** | Choose from the 6 metrics — TaskCompletion, ToolCorrectness, etc | Generic structural failures (didn't complete, wrong tool, inefficient) |
| **Product-specific judges** | `bagual-ai-evals-error-analysis` → open coding → binary judges | Failures specific to YOUR product (Context Amnesia, Policy Retrieval Mismatch, etc) |

If the user hasn't done trace review yet and has an agent running, **strongly suggest** they do `bagual-ai-evals-error-analysis` **before** finalizing the metrics list. Product-specific judges generally catch failures that built-ins miss — and vice versa.

**If the user is in smoke test mode** (first round of evals to validate the pipeline), they can use just the built-ins. Scale to product-specific in the second iteration.

## Core principle

**Don't use all the metrics.** Each metric costs tokens (LLM-as-judge), adds latency, and generates noise in results. Use only what makes sense for the failure mode you want to catch.

## ⚠️ Critical mental models before choosing metrics

These three insights come from recent literature (τ-bench NeurIPS 2024, BFCL V4 Agentic 2025) and the Hamel Husain workshop. **Teach this to the user before recommending metrics** — it will change what they ask for.

### 1. Single-run completion rate is a vanity metric — use pass^k

τ-bench published a result at NeurIPS 2024 that reframed how the field thinks about agent eval:

GPT-4o achieved **pass^1 ≈ 50%** on retail customer service tasks. Reasonable, if disappointing. Then they measured **pass^8** — the probability of the agent succeeding on **all 8 independent trials** of the same task — and the number collapsed to **less than 25%**.

That collapse is the point. A system with 50% success per run **is not** a system that works half the time. It's a system that, over any week of production traffic, will fail the same customer on repeated attempts at a compounding rate. If your support agent resolves a return request with 50% reliability per run, and a frustrated customer tries 3 times, the probability they **never** get it resolved is 12.5%. That's not a benchmark artifact — it's a production SLA that your eval methodology was hiding from you.

**Practical implication**: run your golden tasks **k times** (k≥4, ideally k=8) and measure pass^k. The gap between pass^1 and pass^k tells you about **variance** — a large gap means an inconsistent agent, not just an imperfect one.

```python
import numpy as np
from collections import defaultdict

def compute_pass_k(results: list[dict], k: int = 8) -> dict:
    """
    results: list of dicts with 'task_id' and 'success' (bool)
    """
    task_runs = defaultdict(list)
    for r in results:
        task_runs[r["task_id"]].append(r["success"])
    
    pass_k_per_task = {}
    for task_id, runs in task_runs.items():
        if len(runs) < k:
            continue
        # Sample k runs without replacement, repeat to reduce variance
        trials = [all(np.random.choice(runs, k, replace=False)) for _ in range(200)]
        pass_k_per_task[task_id] = np.mean(trials)
    
    aggregate = np.mean(list(pass_k_per_task.values()))
    return {"per_task": pass_k_per_task, "aggregate": aggregate, "k": k}
```

**Recommended targets** for a customer support agent:
- `pass^1 ≥ 0.75` for transactional tasks
- `pass^4 ≥ 0.60` for complex multi-turn (3+ tool calls)
- `pass^8 ≥ 0.40` as aggregate reliability floor

Ship-blocker if below this in staging.

### 2. Faithfulness ≠ Factual Correctness

These are **different failure modes** with **different fixes**. Conflating them produces evals that reliably catch neither.

| | Faithfulness | Factual Correctness |
|---|--------------|---------------------|
| **Measures** | Are output claims supported by the retrieved context? | Are output claims correct relative to the real world? |
| **Ground truth** | The retrieved context | Reality (or reference annotation) |
| **Failure example** | Doc says "refund in 5 days", agent says "7 days" | Doc says "refund in 7 days" but the policy changed to 3 and the KB is stale |
| **Fix** | Generator (prompt, model, position bias) | Knowledge base refresh, document staleness signals |

**Real story from the book**: a fintech launched an agent with faithfulness >0.85. Users complained anyway. The agent was precisely citing retrieved policies — score 1.0 on those turns — but the policy was stale for 6 months. Perfect faithfulness + zero factual correctness.

**Practical implication**: if you only have faithfulness, you only catch generation errors. To catch stale KB errors, either add staleness metadata to chunks (creation_date, last_reviewed) and flag them, or maintain reference answers for top scenarios and run `RAGAS FactualCorrectness` (note: RAGAS is a separate package — `pip install ragas` — not a built-in DeepEval metric).

### 3. Database state > LLM judge when possible

For agents with backend API access, **the most reliable completion signal is not an LLM judgment** — it's a **query on the actual system state** after the conversation ends. Did the ticket status change? Was the refund row created? That's **deterministic, fast, and immune to LLM judge variance**.

Where you can instrument this, **do it**. LLM-based completion metrics are for cases where system state is inaccessible or not granular enough.

```python
# Instead of:
task_completion = TaskCompletionMetric(threshold=0.7)

# Do:
def db_state_check(test_case):
    """Checks real DB state post-conversation"""
    ticket = db.tickets.find_one({"id": test_case.metadata["ticket_id"]})
    return ticket["status"] == "resolved"
```

This becomes a custom non-LLM metric or a Tier 1 assertion in CI/CD.

### 4. Latency and cost are first-class metrics, not afterthoughts

BFCL V4 Agentic (July/2025) reports **cost in USD and latency in seconds alongside accuracy** for each model evaluated. That's the correct posture: for agents in production, a model 5% more accurate but 3x more expensive or 2x slower may be the wrong choice depending on SLA and margin.

**Targets for a customer support agent**:
- Chat: P90 time-to-first-token <1.5s; P90 full response <3s
- Voice-adjacent (TTS feed): P90 <800ms for the first sentence

And more important than aggregate cost: **cost-per-resolution**. A model with 95% completion that consumes 3x the tokens of a model with 90% may not be worth the premium if your volume is high.

```python
def cost_per_resolution(sessions, input_price_per_1m, output_price_per_1m):
    resolved = [s for s in sessions if s.resolved]
    if not resolved:
        return None
    total_cost = sum(
        s.total_input_tokens / 1_000_000 * input_price_per_1m +
        s.total_output_tokens / 1_000_000 * output_price_per_1m
        for s in resolved
    )
    return total_cost / len(resolved)
```

Track this weekly. Alert if it increases >15% without a corresponding improvement in resolution rate — that's a signal something regressed (retrieval bug doubled context window, prompt change was too verbose, etc).

## τ-bench fault taxonomy — use for diagnosis

Instead of "the agent failed", classify failures in this taxonomy (entity × failure type). This converts post-mortems into actionable categories.

| Fault type | Description | Primary signal |
|------------|-----------|-----------------|
| `goal_partially_completed` | Agent solved part of the task but missed subgoals | `ConversationCompletenessMetric < 1.0` |
| `used_wrong_tool` | Correct intent, wrong tool | Trajectory mismatch |
| `used_wrong_tool_argument` | Correct tool, malformed or incorrect args | Schema validation + argument audit |
| `took_unintended_action` | Agent did something the user didn't request | Policy DAG violation |

**Why this matters**: if your incident logs show 80% `used_wrong_tool_argument` after a schema change, the fix is **schema documentation in the system prompt**, not prompt rewriting. If you're seeing spikes of `took_unintended_action`, you have a policy enforcement problem that `ConversationalDAGMetric` should be catching in CI before it reaches production.

## The 6 built-in metrics for agents

### Reasoning Layer

#### `PlanQualityMetric`

**What it evaluates**: whether the **plan** the agent generated is logical, complete, and efficient to accomplish the task.

**When to use**: when your agent has an explicit planning phase (chain-of-thought, `Plan: 1) X, 2) Y`, or similar). If the agent doesn't create an explicit plan, the metric passes with score 1 by default.

**How it's calculated**:
```
Plan Quality Score = AlignmentScore(Task, Plan)
```
Extracts task and plan from the trace, uses LLM judge to score alignment.

**Scope**: end-to-end (analyzes the entire trace)

**Code**:
```python
from deepeval.metrics import PlanQualityMetric

plan_quality = PlanQualityMetric(
    threshold=0.7,
    model="gpt-4o",  # optional, any LLM
    include_reason=True,  # shows the score justification
    strict_mode=False,    # if True, score is binary (0 or 1)
)
```

#### `PlanAdherenceMetric`

**What it evaluates**: whether the agent **followed its own plan** during execution, or deviated from it.

**When to use**: paired with `PlanQualityMetric`. An optimal plan that's ignored is just as bad as a bad plan followed perfectly.

**How it's calculated**:
```
Plan Adherence Score = AlignmentScore((Task, Plan), Execution Steps)
```

**Scope**: end-to-end

**Code**:
```python
from deepeval.metrics import PlanAdherenceMetric

plan_adherence = PlanAdherenceMetric(threshold=0.7, model="gpt-4o")
```

### Action Layer

#### `ToolCorrectnessMetric`

**What it evaluates**: whether the agent **selected the right tools** and called them in the expected way, comparing against the `expected_tools` list.

**When to use**: when you have deterministic expectations about which tools should be called. This is one of the most important metrics for agents.

**How it's calculated**:
```
Tool Correctness = (Number of Correctly Used Tools) / (Total Number of Tools Called)
```

**Scope**: **component-level** (on the LLM span, NOT end-to-end)

**Configurable strictness modes**:
- **Default**: only compares tool names
- **Input parameter matching**: also requires matching args
- **Output matching**: also requires matching outputs
- **Ordering consideration**: enforces exact sequence
- **Exact matching**: `tools_called` must be identical to `expected_tools`

**Code**:
```python
from deepeval.metrics import ToolCorrectnessMetric
from deepeval.test_case import LLMTestCaseParams

tool_correctness = ToolCorrectnessMetric(
    threshold=0.7,
    # Can add more params via evaluation_params for strictness
)
```

**Important**: requires `expected_tools` in the Golden and `update_current_span(expected_tools=...)` in the LLM span. Without that, it won't work.

**Note**: when `available_tools` is provided on the agent span, the metric also uses an LLM to evaluate whether the selection was optimal among all options. Final score = `min(deterministic_score, llm_score)`.

#### `ArgumentCorrectnessMetric`

**What it evaluates**: whether the agent generated the **correct arguments** for tool calls, based on input and context.

**When to use**: whenever `ToolCorrectnessMetric` is used. The right tool with wrong args is just as bad as the wrong tool.

**How it's calculated**:
```
Argument Correctness = (Number of Correctly Generated Input Parameters) / (Total Number of Tool Calls)
```

Unlike `ToolCorrectnessMetric`, this one is **fully LLM-based** and **referenceless** — it evaluates based on the input context, not by comparing against predefined values.

**Scope**: component-level (LLM span)

**Code**:
```python
from deepeval.metrics import ArgumentCorrectnessMetric

argument_correctness = ArgumentCorrectnessMetric(
    threshold=0.7,
    model="gpt-4o",
)
```

### Execution Layer

#### `TaskCompletionMetric`

**What it evaluates**: whether the agent **actually completed the requested task**. This is the "final success" metric.

**When to use**: practically always. It's the top-level indicator for any agent.

**How it's calculated**:
```
Task Completion Score = AlignmentScore(Task, Outcome)
```

The task can be auto-inferred from the trace or passed explicitly.

**Scope**: end-to-end (analyzes the entire trace)

**Code**:
```python
from deepeval.metrics import TaskCompletionMetric

task_completion = TaskCompletionMetric(threshold=0.7, model="gpt-4o")
```

**IMPORTANT**: it's **trace-only**. CANNOT be used standalone — only inside `evals_iterator` or `@observe` decorator.

#### `StepEfficiencyMetric`

**What it evaluates**: whether the agent completed the task **without unnecessary steps**. Penalizes redundant tool calls, loops, out-of-scope actions.

**When to use**: whenever cost/latency matter (basically, always in production).

**How it's calculated**:
```
Step Efficiency Score = AlignmentScore(Task, Execution Steps)
```

**Scope**: end-to-end

**Code**:
```python
from deepeval.metrics import StepEfficiencyMetric

step_efficiency = StepEfficiencyMetric(threshold=0.7, model="gpt-4o")
```

**IMPORTANT**: also **trace-only**.

**Typical combination**: `TaskCompletionMetric` (high) + `StepEfficiencyMetric` (low) = agent works but needs optimization.

## End-to-End vs Component-Level — DECISIVE

This is the point that causes the most confusion. Memorize:

| Eval type | How to pass metrics | When to use |
|--------------|------------------------|-------------|
| **End-to-end** | `evals_iterator(metrics=[...])` or `@observe(metrics=[...])` on the agent span | Metrics that need to see the entire trace (PlanQuality, PlanAdherence, TaskCompletion, StepEfficiency) |
| **Component-level** | `@observe(type="llm", metrics=[...])` on the specific LLM span | Metrics that evaluate an isolated component decision (ToolCorrectness, ArgumentCorrectness) |

**Both can coexist in the same trace.** An agent can have `ToolCorrectnessMetric` running on the LLM span (catching wrong tool selections) and `TaskCompletionMetric` running on the agent span (measuring whether it achieved the final goal). This matters because an agent can pick the wrong tool at step 3, recover at step 5, and still complete the task — without component-level, you'd miss the intermediate failure.

## Decision table — choosing the package

Use this table with the user to recommend the right set:

| Situation | Recommended package |
|----------|-------------------|
| New agent, first eval, wants simple | `TaskCompletionMetric` only (on the agent span) |
| Agent with tools (common case) | `TaskCompletionMetric` (e2e) + `ToolCorrectnessMetric` + `ArgumentCorrectnessMetric` (LLM span) |
| Agent with explicit planning (CoT) | Add `PlanQualityMetric` + `PlanAdherenceMetric` |
| Agent in production, cost matters | Add `StepEfficiencyMetric` |
| Has specific requirement (tone, safety, compliance) | Add custom `GEval` (see `bagual-ai-evals-custom-metric`) |
| Multi-turn chatbot | Use the conversational metrics (`ConversationalGEval`, etc) — not these |
| RAG | Use the RAG metrics (`AnswerRelevancyMetric`, `FaithfulnessMetric`, `ContextualPrecisionMetric`, `ContextualRecallMetric`, `ContextualRelevancyMetric`) |

### Starter package (default you recommend when in doubt)

```python
from deepeval.metrics import (
    TaskCompletionMetric,
    ToolCorrectnessMetric,
    ArgumentCorrectnessMetric,
)

# end-to-end
task_completion = TaskCompletionMetric(threshold=0.7)

# component-level (on the LLM span)
tool_correctness = ToolCorrectnessMetric(threshold=0.7)
argument_correctness = ArgumentCorrectnessMetric(threshold=0.7)
```

And apply:

```python
@observe(type="llm", metrics=[tool_correctness, argument_correctness])
def call_llm(messages):
    ...

@observe(type="agent", metrics=[task_completion])
def my_agent(user_input):
    ...
```

## Common metric configurations

All metrics accept these parameters:

| Parameter | What it does |
|-----------|-----------|
| `threshold` | Minimum score to "pass" (default 0.5) |
| `model` | Which LLM to use as judge (default `gpt-4.1`). Can be a string or a `DeepEvalBaseLLM` instance |
| `include_reason` | Includes a textual justification of the score |
| `strict_mode` | Binary score 0/1 — forces threshold to 1 |
| `async_mode` | Internal concurrency in `measure()` (default True) |
| `verbose_mode` | Prints intermediates (debug) |

Example with everything:
```python
TaskCompletionMetric(
    threshold=0.8,
    model="claude-3-5-sonnet",  # or custom instance
    include_reason=True,
    strict_mode=False,
    verbose_mode=True,
)
```

## Critical question: thresholds

Users always ask "which threshold to use". Honest answer:

1. **Default 0.7** is a good starting point for any metric
2. Run at least once and look at **the actual distribution** of scores
3. **Calibrate** based on what you consider acceptable for your domain
4. For **production gates**, you generally want 0.8+ (and binary, with `strict_mode=True`)
5. For **monitoring** (non-blocking), 0.6-0.7 works as an alarm

## Workflow with the user

1. **Question**: "What type of agent? Single-shot that executes a task, multi-turn chat, or RAG?"
2. **Question**: "Is there an explicit planning phase (chain of thought)? Or does it go straight to action?"
3. **Question**: "What are the 2-3 most critical failure modes you want to catch?"
4. **Mapping**: take each failure mode and map it to a metric
5. **Recommendation**: present the minimum package + justify each metric
6. **Configuration**: build the code with default thresholds of 0.7 (or different if they have a preference)
7. **Placement**: explain where to attach (LLM span for component-level, agent span for end-to-end)

## Question: "Why not run all 6?"

If the user insists on running all of them:

- **Cost**: each metric is one LLM judge call per golden. 6 metrics × 50 goldens = 300 extra calls.
- **Noise**: you end up looking at 6 scores and don't know which one to act on
- **Redundant dependency**: `TaskCompletionMetric` already covers much of what `PlanQualityMetric` covers if there's no explicit plan
- **Signal vs. noise**: better to have 2 metrics you trust than 6 that confuse you

But if they really want all of them, OK, you support it. Just warn about the costs.

## Metrics beyond the 6 agentic — know they exist

DeepEval has 50+ metrics. Some categories:

| Category | Examples | When |
|-----------|----------|--------|
| **RAG** | `AnswerRelevancyMetric`, `FaithfulnessMetric`, `ContextualPrecisionMetric`, `ContextualRecallMetric`, `ContextualRelevancyMetric` | For RAG. Use the "RAG triad" (recall, precision, relevancy) |
| **Multi-turn** | `ConversationalGEval`, `TurnRelevancyMetric`, `RoleAdherenceMetric`, `ConversationCompletenessMetric`, `KnowledgeRetentionMetric` | For chatbots/copilots |
| **MCP** | `MCPUseMetric`, `MCPTaskCompletionMetric` | For agents using MCP servers |
| **Safety** | `BiasMetric`, `ToxicityMetric`, `PromptInjectionMetric` (via DeepTeam) | Safety checks |
| **Non-LLM** | `ExactMatchMetric`, `RegexMetric`, `JsonMatchingMetric` | Deterministic comparisons |
| **Custom** | `GEval`, `DAGMetric`, `ConversationalGEval`, `ConversationalDAG`, `ArenaGEval` | Custom criteria |
| **Multimodal** | `ImageCoherenceMetric`, `TextToImageMetric` | For multimodal outputs |
| **Others** | `SummarizationMetric`, `HallucinationMetric` | Specific cases |

If the user asks for a metric not in the 6 agentic ones, offer to research more details or create a custom one with `GEval` (skill `bagual-ai-evals-custom-metric`).

## Closing

After choosing and configuring the metrics, say:

> "Metrics chosen: {list}. Next step is running the first round of evals and analyzing the results. Want me to call `bagual-ai-evals-run-and-analyze`?"

If they want custom:

> "Great, we've chosen {list}. You also mentioned needing to evaluate {tone/safety/compliance}. For that we'll create a custom G-Eval metric. Want me to call `bagual-ai-evals-custom-metric`?"

## Anti-patterns

- ❌ Recommending all 6 metrics — overkill, cost, noise
- ❌ Forgetting to explain end-to-end vs component-level — will generate a "metric doesn't run" bug
- ❌ Default without context — always ask about failure modes first
- ❌ Threshold without justification — explain it's a starting point and calibrate later
- ❌ Mixing agent metrics with RAG/multi-turn metrics — they are separate categories
