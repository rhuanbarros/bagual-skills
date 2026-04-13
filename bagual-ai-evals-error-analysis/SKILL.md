---
name: bagual-ai-evals-error-analysis
description: Error-analysis-first workflow to discover real agent failures via trace review (Hamel Husain). Use when the user says "I don't know what to evaluate", "I need to discover failures", "trace review", "open coding", "axial coding", "trace-driven evals", "vibe check", "how to create evals from scratch", or when they have an agent running but no structured evals.
---

# DeepEval Error Analysis — Trace Review and Trace-Driven Workflow

You are the error analysis instructor. This is the most important skill in the module, and the one that differs most from the intuition of those who have never done LLM evaluation.

## Why this skill exists — the vibe-check trap

Most teams fall into a predictable pattern:

1. Sprints 1-2: prompt works, demo passes, everyone is happy
2. Someone changes something (chunking, prompt, model, tool schema)
3. Demo still passes
4. Ship
5. Six weeks later: customer complains. Something regressed in week 3, but there's no signal trail

This is the **vibe-check trap** that Hamel Husain describes after running workshops with 3000+ engineers from OpenAI/Anthropic/Google. **It's not stupidity**. It's a structural problem: the feedback loop of "changed prompt → saw output" **looks like** evaluation but isn't. It's sampling **one point** from a distribution and concluding that the entire distribution is fine.

The `bagual-ai-evals-strategy` skill helps you plan WHAT to evaluate. **This skill** helps you **discover** what to evaluate — because the failures you need to catch you don't know yet.

## Core principle: error-analysis-first, not EDD

There is a school of thought called **EDD (Eval-Driven Development)** that says: write evals **before** the code, just like TDD. The theory is elegant. The practice is cracked.

The reason is structural: **LLMs have "infinite surface area for potential failures"**. You can't write evals for failure modes you haven't observed yet — and you will observe failure modes you couldn't predict before shipping something real. Writing a "complete" eval suite before seeing production traces means writing evals for imaginary problems while real failures go unmeasured.

The practical resolution (Hamel): **use EDD's infrastructure principles** (build harness early, gate in CI), but **use error-analysis-first to populate them**. Don't write evals for what you think might fail. Write evals for what you **observe** failing.

This changes **when** in the cycle you do each thing. And it means that **your first 100 traces are worth more than any benchmark dataset someone else built**.

## Prerequisites

You need **real traces**. At least 30-50.

| Scenario | What to do |
|---------|-------------|
| Have agent in production | Export 50 traces from the last week via Confident AI / LangSmith / Langfuse / Braintrust |
| Have agent in staging but not prod | Run 50 synthetic inputs representative of the expected distribution |
| No agent running yet | **Stop here** — go to `bagual-ai-evals-strategy` first, instrument the agent (`bagual-ai-evals-instrument`), generate traces, and come back |

**Synthetics count to get started**. If you sample from the expected distribution of real inputs, it's legitimate. It's not an excuse to skip error analysis — it's just a temporary substitute.

## The 4-Step Workflow

This is the process that converts raw traces into a working evals system. It's not glamorous. It involves lots of spreadsheets and Jupyter notebooks. **Do it anyway.**

```
┌─────────────────────────────────────────────┐
│  Step 1 — OPEN CODING                        │
│  Read 30-50 traces, write freeform notes     │
│  ~2 sessions of 30 minutes                   │
├─────────────────────────────────────────────┤
│  Step 2 — AXIAL CODING                       │
│  LLM clusters notes into failure categories  │
│  Aim: 4-8 product-specific categories        │
├─────────────────────────────────────────────┤
│  Step 3 — BINARY LLM JUDGES                  │
│  Per category: 2-sentence pass/fail          │
│  Validate with 2nd annotator before scaling  │
├─────────────────────────────────────────────┤
│  Step 4 — CI DEPLOYMENT                      │
│  Integrate judges in CI + ongoing calibration│
│  TPR/TNR tracking biweekly                   │
└─────────────────────────────────────────────┘
```

## Step 1 — Open Coding

**Goal**: stop relating to your agent as an abstraction ("it handles billing questions") and start relating to it as a **distribution of real behaviors**.

### Setup

Open a Jupyter notebook (or any long-form notes tool). **Don't use an evals tool yet.** Don't try to categorize anything. Don't use a template.

```python
import json
from deepeval.tracing import trace_manager  # if already instrumented with deepeval

# OR export from other platforms:
# - Confident AI: dataset.pull(alias="prod-traces")
# - Langfuse: langfuse.fetch_traces(...)
# - LangSmith: client.list_runs(...)
# - Braintrust: braintrust.fetch_dataset(...)

# Load 50 traces with everything: input, output, retrieved_context, tool_calls
traces = load_traces_with_full_context(n=50)

for i, trace in enumerate(traces):
    print(f"=" * 80)
    print(f"TRACE {i+1}/{len(traces)}")
    print(f"=" * 80)
    print(f"\nUSER INPUT:\n{trace['input']}\n")
    print(f"\nAGENT OUTPUT:\n{trace['output']}\n")
    print(f"\nRETRIEVED CONTEXT:\n{trace.get('retrieval_context')}\n")
    print(f"\nTOOL CALLS:")
    for tc in trace.get('tool_calls', []):
        print(f"  - {tc['name']}({tc['args']}) -> {tc['result'][:200]}")
```

### How to read

For each trace, spend **2-5 minutes**. In two 30-minute sessions you can review 30-50 traces.

For each trace, write freeform notes answering:

- **What is surprising here?**
- **What seems wrong?**
- **What seems right in a way I didn't expect?**
- **Is this output factually correct?** (compare with your knowledge)
- **Did the agent do something I wouldn't ask it to do?**
- **Did the agent fail to do something I would expect?**

**Don't try to categorize.** Don't try to be concise. Write like field research notes. Researchers call this **open coding** — you're building intuition, not taxonomy yet.

### Examples of the kind of notes you want

**Trace 7** (billing dispute):
> Asked for account number on turn 3, but the user already gave it on turn 1. Response on turn 5 cites the correct refund policy but the amount ($50) is wrong, should be $75. Mentioned escalation process but then tried to resolve it anyway, became somewhat incoherent.

**Trace 12** (feature question):
> User asked if plan X has international coverage. Retrieved doc says international coverage is a $15/month add-on. Agent responded "yes, your plan includes international coverage at no additional cost". **CONFIDENT HALLUCINATION**. Relevance score passed because it was on-topic but the response was wrong.

**Trace 23** (return request):
> Tool call `get_order_status` was called with `order_id="ABC-123"` but the user said `#ABC123` (no hyphen). Tool returned an error but agent didn't notice, continued making subsequent calls as if it had succeeded. Ended up giving a fake confirmation.

Note how these notes are **specific**, not generic. "Hallucination" alone would be useless. "Confident hallucination about international coverage feature, contradicting the retrieved doc" is actionable.

### How long it takes

| Activity | Time |
|-----------|-------|
| Notebook setup | 30 min |
| Reading 30-50 traces and taking notes | 1-2h in 2 sessions |
| Note cleanup | 30 min |
| **Total** | **3-4 hours** |

**Don't skip it.** This is the highest-ROI work in the entire evals cycle.

## Step 2 — Axial Coding

**Goal**: cluster your raw notes into **mutually exclusive failure categories** that are **product-specific**, not generic.

The difference is critical:

| Generic (bad) | Product-specific (good) |
|-----------------|--------------------------|
| "Quality issues" | "Agent applies wrong policy version when multiple versions exist" |
| "Hallucination" | "Agent confidently quotes pricing that contradicts retrieved doc" |
| "Tool error" | "Agent doesn't notice when tool returns 404, continues as if successful" |
| "Coherence problem" | "Agent re-asks for info already provided 3+ turns ago" |

A generic eval for "factual accuracy" doesn't distinguish between hallucinating a product feature and misapplying a discount policy — two failures with completely different root causes and fixes.

### How to do it

Take all the notes from step 1 (collated into a single text file) and use an LLM to cluster them. Don't use LLM-as-judge — use Claude/GPT to help you **think**, this is not an evaluation.

Suggested prompt:

```
Here are my open coding notes on 47 traces from a customer support 
agent that makes tool calls against a billing API and does RAG over a 
policies knowledge base:

[paste all notes here]

Group these observations into mutually exclusive failure categories, 
following these rules:
- 4-8 categories total (not 20)
- Each category must be PRODUCT-SPECIFIC, not generic
- Each category needs a precise name and a description that distinguishes 
  it from adjacent categories
- Categories should be actionable: "what fix will solve this" should be 
  obvious from the name
- List 2-3 example traces per category (use note numbers)

Return as markdown with category + description + examples.
```

### Expected output

```markdown
## Failure Categories (8 total)

### 1. Context Amnesia
**Description**: Agent requests information that was already provided in the current conversation.
**Examples**: Trace 7, Trace 19, Trace 31

### 2. Policy Retrieval Mismatch
**Description**: Correct doc retrieved but agent applies wrong policy version,
or applies a policy that doesn't apply to the customer's product type.
**Examples**: Trace 12, Trace 28

### 3. Tool Argument Format Mismatch
**Description**: Correct tool, but args are in wrong format and tool returns
a silent error. Agent doesn't detect the error.
**Examples**: Trace 23, Trace 41

### 4. Escalation Abandonment
**Description**: Agent commits to escalating to a human but then tries to
resolve it anyway, causing incoherence.
**Examples**: Trace 7, Trace 33

### 5. Confident Hallucination Over Retrieved Context
**Description**: Retrieved doc contains correct information, agent generates a response
factually contrary to the doc with a confident tone.
**Examples**: Trace 12, Trace 39

### 6. Number/Amount Hallucination
**Description**: Agent cites numerical values (prices, deadlines, counts) that are not
in the docs or tool results. Correct policy, wrong number.
**Examples**: Trace 7, Trace 14

### 7. Missing Slot Re-confirmation
**Description**: Agent doesn't confirm slot/product availability before
asserting availability, based on stale cache.
**Examples**: Trace 22, Trace 38

### 8. Tone Drift on Frustration
**Description**: When user expresses frustration, agent becomes defensive or
overly formal instead of empathetic.
**Examples**: Trace 11, Trace 26
```

Each of these becomes an **eval criterion** in step 3.

### Why this works

Hamel shows that these categories derived from real traces consistently catch failures that generic metrics miss. You can't design these categories before seeing the traces — because you didn't know that "Number Hallucination" was different from "Policy Hallucination" until you saw the 47 traces and realized the fix for each one is different.

## Step 3 — Binary LLM Judges

**Goal**: for each category from step 2, create an LLM judge with a **binary** pass/fail definition.

### Principle: binary > Likert

Hamel Husain and Eugene Yan independently converged on binary pass/fail, not Likert scales. The reasons are practical:

**Reason 1 — inter-rater agreement on ordinal scales is genuinely bad.** Human Cohen's Kappa on 5-point scales frequently falls between **0.2 and 0.3**, meaning two experts reviewing the same response give scores 2 points apart. If humans can't agree, you can't calibrate an LLM judge against human judgment, and your eval becomes noise.

**Reason 2 — stakeholders don't use the scale anyway.** They ask for a recommended threshold and treat everything above as pass, everything below as fail — which is binary behavior forced onto a scale that pretended to be continuous.

### How to write a binary definition

**The two-sentence rule**: one sentence defining PASS, one sentence defining FAIL. No rubric. No scale.

**Quality test**: if two people reading your definition **would disagree on a borderline case**, the definition needs tightening before you ask an LLM to apply it.

### Concrete example — "Context Amnesia" category

```python
CONTEXT_AMNESIA_JUDGE_PROMPT = """
You are evaluating a customer support agent's response in the context of a 
multi-turn conversation.

PASS: The agent's response does not request information that the user already 
provided in earlier turns of this conversation. If the agent needs to confirm 
information, it does so by referencing what was provided (e.g., "I see you 
mentioned account 88291 — let me look that up").

FAIL: The agent requests information that was already explicitly stated by the 
user in any prior turn of the conversation.

Conversation history:
{conversation_history}

Current agent response:
{agent_response}

Return JSON: {{"result": "pass" | "fail", "reason": "<one sentence>"}}
"""
```

**Why this prompt works**:
- Explicit role ("you are evaluating") as impartial evaluator
- PASS and FAIL each defined in a single sentence
- Actionable criterion: "did the agent ask for information already given"
- Reason field mandatory (not optional!) — it's the data that makes failures debuggable
- JSON output for programmatic parsing

### Implementation in DeepEval with GEval

```python
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCaseParams

context_amnesia = GEval(
    name="Context Amnesia",
    evaluation_steps=[
        "Read the full conversation history including all prior user turns.",
        "Identify any information the user explicitly stated in prior turns.",
        "Check whether the current agent response requests any of that information again.",
        "PASS if the agent does not re-request previously-provided information.",
        "FAIL if the agent requests information that was already given.",
    ],
    evaluation_params=[
        LLMTestCaseParams.INPUT,
        LLMTestCaseParams.ACTUAL_OUTPUT,
        LLMTestCaseParams.CONTEXT,  # full history
    ],
    threshold=1.0,  # zero tolerance for context amnesia
    strict_mode=True,  # binary
)
```

Note `threshold=1.0` + `strict_mode=True` — forces binary 0/1 output, aligned with the philosophy.

### Inter-annotator validation

**Before declaring the judge ready**:

1. Take 10-15 traces (mix of probable PASS and FAIL)
2. **You** apply the definition manually. Note your verdict.
3. **Someone else** (ideally a team engineer) applies it independently
4. Compare. If they agree on **8/10 or more**, OK.
5. If they disagree on more than 2 cases, **the definition has ambiguity** — discuss the disagreement cases, refine the definition, repeat.

Only after this go to the LLM. This human validation step is what separates an eval that works from one that produces noise.

### ⚠️ Judge model selection

**NEVER use the same model as both judge and agent**. Self-enhancement bias is documented: Claude evaluating Claude, GPT-4o evaluating GPT-4o — the judge systematically favors its own outputs (Claude→Claude drops to 44.8% agreement with humans in JudgeBench ICLR 2025).

Simple rule:
- Agent uses GPT-4o → judge uses Claude Sonnet
- Agent uses Claude → judge uses GPT-4o (or Selene Mini for Tier 2 with controlled cost)
- Agent uses local model → judge uses cloud model

This is not a detail — it's the difference between an eval system that measures real quality and one that measures "how much the judge likes itself".

### Calibration against human (AlignEval)

Eugene Yan formalized this as the **AlignEval workflow**:

```
1. You manually label 30+ samples
2. Write the two-sentence definition
3. Run the LLM judge on the same samples
4. Calculate:
   - TPR (True Positive Rate) = TP / (TP + FN) — does the judge catch real failures?
   - TNR (True Negative Rate) = TN / (TN + FP) — does the judge not flag correct PASSes?
   - Cohen's Kappa = chance-adjusted agreement
5. Iterate on the prompt until κ ≥ 0.7
6. When OK, declare baseline and deploy
```

Target: **κ ≥ 0.7** before deploying in CI. Below that, annotators (human or LLM) disagree too often for the eval to be a reliable signal.

```python
from sklearn.metrics import cohen_kappa_score, confusion_matrix

# You manually labeled 30 traces
human_labels = [1, 0, 1, 1, 0, 1, 0, 0, 1, 1, ...]  # 1=PASS, 0=FAIL

# Run the LLM judge on the same 30 traces
llm_labels = [1, 0, 1, 1, 1, 1, 0, 0, 1, 0, ...]

# Metrics
kappa = cohen_kappa_score(human_labels, llm_labels)
tn, fp, fn, tp = confusion_matrix(human_labels, llm_labels).ravel()
tpr = tp / (tp + fn)  # sensitivity / recall
tnr = tn / (tn + fp)  # specificity

print(f"Cohen's κ: {kappa:.2f}")
print(f"TPR: {tpr:.2f}")
print(f"TNR: {tnr:.2f}")

# Acceptance threshold:
assert kappa >= 0.7, "Judge needs more calibration"
assert tpr >= 0.75, "Judge missing too many real failures"
assert tnr >= 0.75, "Judge flagging too many false positives"
```

### Partitioning calibration data correctly

Critical insight from "Who Validates the Validators" (ACM CHI 2024): your calibration data needs to come from the **current distribution** of agent outputs, not from old samples.

If your agent changed (new model, new prompt), the calibration set needs to include **recent samples** from that distribution. Otherwise you're calibrating against an agent that no longer exists.

Do a 60/40 split:
- **60% dev**: for iterating the judge prompt
- **40% test**: never used for iteration — only for the final check

Iterating against the test set is memorization, not calibration.

## Step 4 — CI Deployment

Once the judge is calibrated, integrate into CI/CD with appropriate gating.

### Recommended structure

```python
# tests/test_agent_quality.py
import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase
from deepeval.metrics import GEval

# Load golden dataset (same traces you used to calibrate + others)
from my_evals.datasets import load_regression_dataset
from my_evals.metrics import (
    context_amnesia,
    policy_retrieval_mismatch,
    tool_argument_format_mismatch,
    escalation_abandonment,
    confident_hallucination,
    number_hallucination,
)

dataset = load_regression_dataset()

@pytest.mark.parametrize("test_case", dataset.test_cases)
def test_agent_quality(test_case: LLMTestCase):
    assert_test(
        test_case=test_case,
        metrics=[
            context_amnesia,
            policy_retrieval_mismatch,
            tool_argument_format_mismatch,
            escalation_abandonment,
            confident_hallucination,
            number_hallucination,
        ]
    )
```

Run:

```bash
deepeval test run tests/test_agent_quality.py
```

In CI/CD, gate on:
- **Tier 1 (every commit)**: deterministic assertions only (see `bagual-ai-evals-production`)
- **Tier 2 (every PR)**: these product-specific judges
- **Tier 3 (nightly)**: full benchmark with pass^k

### Ongoing calibration

Judges drift. Three things change over time:

1. **Underlying model updates** — even with version pinning, behavior changes subtly between minor versions
2. **Product output distribution changes** — system prompt evolves, knowledge base updates
3. **Your criteria loosen in your head** — you review more traces and what seemed like a FAIL now seems like a PASS

**Minimum calibration cadence**: every 2 weeks:

1. Stratified sample: 10 traces the judge marked PASS, 10 it marked FAIL
2. You (or domain expert) label manually
3. Recalculate TPR and TNR
4. If TPR < 0.75 → judge is missing real failures → recalibrate
5. If TNR < 0.75 → judge is generating noise → recalibrate

**Track 7-day and 30-day rolling trends**, not individual sessions. Single-session audits are flaky; aggregates are reliable.

## Domain expertise is non-negotiable

This is one of the most underestimated points in Hamel's framework: you need **someone who deeply understands what good outputs look like for your specific product**. Not a generalist who says "this looks reasonable". Someone who looks at the billing dispute response and **knows** whether the policy application is correct.

For a customer support agent, this means the person calibrating your evals should:
- Know the support policies
- Understand what information the agent actually has access to
- Be able to distinguish between "vague but acceptable" and "actively wrong"

**If that person is you**, protect time for trace review. Don't delegate.

**If it's an SME (subject matter expert)**, your evals workflow needs to **include** them without requiring them to understand LLM infrastructure. Confident AI has a UI for this (golden annotation by non-technical users). Send a Google Sheet if needed. The tool doesn't matter — what matters is having the domain expert **in the loop**.

## Eugene Yan: evals are a practice, not a deliverable

Critical mindset from Eugene Yan: **an eval suite you write in month 1 and never touch is worse than no eval suite in month 6**, because it's generating false confidence.

Your agent's failure modes change as prompts change, knowledge base updates, and users find new ways to phrase requests. The eval suite needs to **keep up** with this.

Explicit maintenance loops:

- **Each production incident your evals DIDN'T catch = a missing eval**. Write it immediately, add to the suite, do a post-mortem on why existing coverage didn't see it.
- **Each calibration session that reveals judge drift = signal to update judge prompts**.
- **Each new feature shipped = new failure surface that needs coverage before ship**.

The **EDDOps framework** formalizes this as continuous evaluation governance: evaluation is not a phase, it's a **function** running in parallel with all dev activity. In practice, someone on the team **owns** the eval suite the same way someone owns the data pipeline. It's infrastructure, not a task to close.

## The good eval suite test

This is an incredibly useful criterion that the book distills:

> **If everything passes 95% of the time in your suite, you are measuring things your agent already does well.**
> **A well-designed suite derived from real failure patterns should produce a ~70% pass rate on the first run.**

| Initial pass rate | Diagnosis |
|-------------------|-------------|
| 95%+ | Suite is measuring things that aren't a problem. **False security.** Go back to Step 1. |
| 70-85% | **Healthy.** There's real signal to act on. |
| 40-70% | Also OK — agent needs work but evals are calibrated |
| <40% | Definitions too loose OR agent has a fundamental problem before evals are the bottleneck |

If you run evals and everything passes, **that's red**, not green.

## Complete script with the user

1. **Question**: "Do you have an agent already running and generating traces?"
   - No → send to `bagual-ai-evals-strategy` + `bagual-ai-evals-instrument`
   - Yes → continue
2. **Question**: "How many traces can you collect from the last 7 days? Ideally 30-50."
3. **Setup**: help export traces (Confident AI / LangSmith / Langfuse / Braintrust / via `trace_manager`)
4. **Open coding session 1** (30 min): read 15-25 traces together, write freeform notes. Model the type of notes they should take — specific, not generic.
5. **Open coding session 2** (30 min, ideally another day): another 15-25 traces.
6. **Axial coding**: take the notes, build the clustering prompt, run it with Claude/GPT, refine the categories with the user.
7. **Binary judge writing**: for each category (4-8), write the 2-sentence definition together. You draft, the user validates.
8. **Inter-annotator validation**: 10-15 traces. You label, they label, compare. Refine where they disagree.
9. **AlignEval calibration**: 30+ traces, TPR/TNR/κ metrics, iterate until κ ≥ 0.7.
10. **CI integration**: build the test file, integrate into the pipeline.
11. **Cadence**: agree on a biweekly re-calibration cadence.

## Tools for exporting traces

| Platform | How to export traces |
|------------|----------------------|
| DeepEval (local) | `from deepeval.tracing import trace_manager; traces = trace_manager.get_all_traces_dict()` |
| Confident AI | `dataset.pull(alias="prod-traces-week-15")` or export via UI |
| LangSmith | `client.list_runs(project_name="...", start_time=...)` |
| Langfuse | `langfuse.fetch_traces(start_time=...)` |
| Braintrust | `braintrust.fetch_dataset(...)` |
| Arize Phoenix | Phoenix UI export or SDK |

All have exportable JSON format. What matters is bringing the **complete trace**: input, output, retrieved context, tool calls with args and outputs.

## Closing

After finishing the 4-step workflow, say:

> "Done, you have {N} calibrated product-specific judges, derived from {M} real traces. This is your **baseline**. From now on, these judges are part of your infrastructure — biweekly recalibration is mandatory. Next step is integrating this into your three-tier strategy: Tier 1 (deterministic assertions on every commit), Tier 2 (these judges on each PR), Tier 3 (nightly with pass^k). Want me to call `bagual-ai-evals-production` to set that up?"

## Anti-patterns

- ❌ **Skipping open coding** because "I already know what failures exist" — you know the ones you've seen, not the ones that exist
- ❌ **Generic categories** ("hallucination", "quality") instead of product-specific ones
- ❌ **Likert scales** instead of binary — inter-rater agreement will be bad
- ❌ **Skipping inter-annotator validation** — a definition that seems clear to you may be ambiguous to others
- ❌ **Calibrating once and never again** — judges drift silently
- ❌ **Aggregate agreement** without separate TPR/TNR — hides bias on both sides
- ❌ **95% pass rate** and thinking it's fine — it's a signal of weak evals, not a good agent
- ❌ **Iterating judge prompt against test set** — memorization, not calibration
- ❌ **Using the same model as judge and agent** — self-enhancement bias (see `bagual-ai-evals-custom-metric`)
- ❌ **Domain expert out of the loop** — generic eval without domain grounding produces generic scores that don't predict real quality
