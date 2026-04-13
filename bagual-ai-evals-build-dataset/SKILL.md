---
name: bagual-ai-evals-build-dataset
description: Creating and managing a goldens dataset for agent evaluation. Use when the user says "create dataset", "make goldens", "synthesizer", "generate tests", "how to create goldens", "import csv dataset", or similar.
---

# DeepEval Build Dataset — Creating Goldens

You are the dataset builder. Without a dataset, there is no evaluation. Your mission: take the user from "I have no examples" to "I have an `EvaluationDataset` with at least 5-10 goldens ready to go".

## ⚠️ Important recommendation: trace-driven > generic manual

Before creating a dataset, ask the user: **"Do you already have the agent instrumented and generating traces (even synthetic ones)?"**

If **yes**, strongly recommend they do **trace review (open coding)** before creating manual goldens. The `bagual-ai-evals-error-analysis` skill covers the complete Hamel Husain workflow (open coding → axial coding → binary judges) which produces **product-specific goldens** based on real failures, not imagined ones.

The difference is critical:

| Approach | Result |
|----------|-----------|
| Manual goldens "from imagination" | You create cases for problems you **think** will appear. You'll likely measure things the agent already does well, and miss the real failure modes. |
| Trace review → product-specific goldens | You create cases for failures you **observed** happening. Catches real failure modes with high signal. |

**Rule of thumb**: 5-10 goldens derived from trace review are worth more than 50 goldens created from scratch. Hamel demonstrated this in workshops with 3000+ engineers.

**When creating manual goldens without trace review makes sense**:
- You don't have a working agent yet (you need something to run before generating traces)
- Smoke tests / sanity checks
- Synthesizer (automatic generation) needs seed examples

For these cases, keep reading. For cases where you **have** traces, **go to `bagual-ai-evals-error-analysis` first**.

## Core concepts — embedded

### What is a Golden

**Golden** = "pending test case". Unlike an `LLMTestCase` which is ready to evaluate, a Golden only contains the input data and the expected output. The `actual_output` (what the agent actually produced) is generated **dynamically** when you run the agent.

The analogy: a Golden is the **mold**, a TestCase is the **finished piece** after you run the agent against the golden.

### Why Goldens > TestCases

- Allow re-running the same dataset against **different versions** of the agent (regression)
- Allow evaluating the agent against **inputs that haven't been processed yet**
- Are the **preferred** way to initialize a dataset

### Data model — Single-turn Golden

```python
from pydantic import BaseModel
from typing import List, Optional, Dict
from deepeval.test_case import ToolCall

class Golden(BaseModel):
    input: str                                  # REQUIRED — the user input
    expected_output: Optional[str] = None       # ideal output (optional)
    context: Optional[List[str]] = None         # pre-existing context (optional)
    expected_tools: Optional[List[ToolCall]] = None  # tools that should be called
    
    # Useful metadata
    additional_metadata: Optional[Dict] = None
    comments: Optional[str] = None
    custom_column_key_values: Optional[Dict[str, str]] = None
    
    # DO NOT populate manually — generated dynamically
    actual_output: Optional[str] = None
    retrieval_context: Optional[List[str]] = None
    tools_called: Optional[List[ToolCall]] = None
```

### Data model — Multi-turn ConversationalGolden

```python
class ConversationalGolden(BaseModel):
    scenario: str                              # REQUIRED — description of the conversation scenario
    expected_outcome: Optional[str] = None     # what should happen at the end
    user_description: Optional[str] = None     # who the simulated user is
    context: Optional[List[str]] = None
    
    additional_metadata: Optional[Dict] = None
    comments: Optional[str] = None
    
    # Generally DO NOT populate — generated dynamically via ConversationSimulator
    turns: Optional[list] = None
```

### Single-turn vs Multi-turn dataset

Datasets in DeepEval are **statefully single OR multi-turn**, not both. The first `add_golden()` determines which type it is:

```python
from deepeval.dataset import EvaluationDataset, Golden, ConversationalGolden

# Single-turn
ds_single = EvaluationDataset(goldens=[Golden(input="What is your name?")])
print(ds_single._multi_turn)  # False

# Multi-turn
ds_multi = EvaluationDataset(goldens=[
    ConversationalGolden(
        scenario="Frustrated user asking for a refund.",
        expected_outcome="Redirected to a human agent."
    )
])
print(ds_multi._multi_turn)  # True
```

You can't change it afterwards. **Decide at the start**.

## Critical question

"Do you want to evaluate **single-turn** interactions (one question → one agent response) or **multi-turn** (a full conversation with multiple exchanges)?"

- **Single-turn** → use `Golden` (most common case for agents that execute tasks)
- **Multi-turn** → use `ConversationalGolden` (for chatbots, conversational copilots)

## The 4 paths to create a dataset

1. **Manual** — write goldens by hand (recommended to start)
2. **Synthesizer** — automatically generate goldens from docs / context / scratch
3. **Import** — JSON, CSV, or Hugging Face
4. **Cloud** — pull/push via Confident AI

## Path 1 — Manual creation (RECOMMENDED TO START)

For a new agent, **start manually** with 5-10 goldens. They are your "ground truth" and teach you what matters.

### Structured conversation with the user

**Question 1**: "Give me 3 real examples of inputs users would send to your agent. They can vary widely: a simple case, a difficult case, an edge case."

Note as `inputs_iniciais`.

**Question 2**: "For each of those, what would be the ideal result? E.g.: 'book a flight NYC→Paris' → 'flight booked, confirmation returned'."

Note as `expected_outputs`.

**Question 3**: "Which tools do you expect the agent to call in each case? E.g.: for 'book flight' → `search_flights` + `book_flight`."

Note as `expected_tools`.

**Question 4** (important!): "Remember the failure modes you prioritized in the evaluation plan? Let's create 1-2 goldens for each failure mode. For example: for 'agent books the wrong flight', we create a golden with an ambiguous input to see if it clarifies or makes a mistake."

### Resulting code

```python
from deepeval.dataset import EvaluationDataset, Golden
from deepeval.test_case import ToolCall

dataset = EvaluationDataset(goldens=[
    # Simple case
    Golden(
        input="Book a flight from NYC to Paris for next Monday",
        expected_output="Flight booked, confirmation CONF-XXX returned",
        expected_tools=[
            ToolCall(name="search_flights"),
            ToolCall(name="book_flight"),
        ],
    ),
    # Ambiguous case (tests robustness)
    Golden(
        input="I want to go to Paris",
        expected_output="Asked for more details (date, origin) before searching",
        expected_tools=[],  # should not call any tool yet
    ),
    # Edge case (broken input)
    Golden(
        input="book flight nyc-paris 2099-13-45",  # invalid date
        expected_output="Validation error, asked for a valid date",
        expected_tools=[],
    ),
    # ... more goldens
])
```

### Adding more goldens later

```python
dataset.add_golden(Golden(input="Cancel my last booking"))
```

## Path 2 — Synthesizer (automatic generation)

Synthesizer generates **synthetic** goldens from documents, contexts, or from scratch. Useful when you don't have enough examples or want to expand coverage.

### 4 available methods

| Method | When to use |
|--------|-------------|
| `generate_goldens_from_docs()` | You have a knowledge base (PDFs, .docx, .txt) and want to generate questions based on the content. **Most useful for RAG**. |
| `generate_goldens_from_contexts()` | You already have ready-made chunks/contexts as a list of strings |
| `generate_goldens_from_scratch()` | Zero base — purely from-scratch generation based on a description |
| `generate_goldens_from_goldens()` | Augments an existing set of goldens (variations/evolutions) |

### Example — from docs

```python
from deepeval.synthesizer import Synthesizer
from deepeval.dataset import EvaluationDataset

goldens = Synthesizer().generate_goldens_from_docs(
    document_paths=['knowledge_base.txt', 'manual.docx', 'product.pdf']
)

dataset = EvaluationDataset(goldens=goldens)
```

### Example — from scratch

```python
goldens = Synthesizer().generate_goldens_from_scratch(
    subject="Travel booking agent capable of searching flights and hotels",
    task="Test the agent's ability to handle ambiguous requests",
    output_format="Standard input → expected_output",
    num_goldens=20,
)
```

### How it works internally

Synthesizer uses **evolution techniques** to complicate and make the generated goldens more realistic and similar to human-made data. Under the hood, it's an LLM generating inputs + expected outputs based on the parameters you passed.

**Important**: manually review the generated goldens before trusting them. Synthesizer is great for coverage but can generate artificial examples.

### Conversation Simulator (multi-turn)

To generate **turns** inside a `ConversationalTestCase`, use `ConversationSimulator` instead of Synthesizer:

```python
from deepeval.simulator import ConversationSimulator
from typing import List, Dict

simulator = ConversationSimulator(
    user_intentions={"Opening a bank account": 1},
    user_profile_items=[
        "full name",
        "current address",
        "bank account number",
        "date of birth",
        "phone number",
    ],
)

async def model_callback(input: str, conversation_history: List[Dict[str, str]]) -> str:
    # Your function that receives input + history and returns the agent's response
    return await your_agent_function(input, conversation_history)

convo_test_cases = simulator.simulate(
    model_callback=model_callback,
    stopping_criteria="Stop when the user's banking request has been fully resolved.",
)
```

## Path 3 — Import from files

### From JSON

Format: array of objects where each object has keys from Golden.

```python
from deepeval.dataset import EvaluationDataset

dataset = EvaluationDataset()

# As goldens
dataset.add_goldens_from_json_file(
    file_path="example.json",
)

# As already-ready test cases (rare)
dataset.add_test_cases_from_json_file(
    file_path="example.json",
    input_key_name="query",
    actual_output_key_name="actual_output",
    expected_output_key_name="expected_output",
    context_key_name="context",
    retrieval_context_key_name="retrieval_context",
)
```

If the JSON keys differ from the convention, pass the names via parameters (`input_key_name`, etc).

### From CSV

```python
dataset = EvaluationDataset()

# As goldens
dataset.add_goldens_from_csv_file(
    file_path="example.csv",
)

# As test cases
dataset.add_test_cases_from_csv_file(
    file_path="example.csv",
    input_col_name="query",
    actual_output_col_name="actual_output",
    expected_output_col_name="expected_output",
    context_col_name="context",
    context_col_delimiter=";",  # IMPORTANT for columns that become a list
    retrieval_context_col_name="retrieval_context",
    retrieval_context_col_delimiter=";",
)
```

`expected_output`, `context`, `retrieval_context`, `tools_called`, `expected_tools` are **all optional**.

## Path 4 — Cloud (Confident AI)

If the user is logged into Confident AI, they can manage datasets in the cloud with collaboration from domain experts.

### Pull (download)

```python
from deepeval.dataset import EvaluationDataset

dataset = EvaluationDataset()
dataset.pull(alias="My Dataset")  # alias is the name given in Confident AI
print(dataset.goldens)  # sanity check
```

### Push (upload)

```python
dataset = EvaluationDataset(goldens=[...])
dataset.push(alias="My dataset")
```

If you're not sure they're ready:

```python
dataset.push(alias="My dataset", finalized=False)
# They won't be pulled until you mark them as finalized in Confident AI manually
```

### Advantages of cloud

- Domain experts (non-technical) create, annotate, and comment on goldens via UI
- Built-in versioning
- CSV upload via interface
- Automatic combination with test runs
- Custom columns

## Save locally

If you don't use Confident AI, save to a file:

```python
# As JSON
dataset.save_as(
    file_type="json",
    directory="./eval-data",
    file_name="my_dataset",  # optional, default is YYYYMMDD_HHMMSS
    include_test_cases=False,  # if True, also saves test cases
)

# As CSV
dataset.save_as(
    file_type="csv",
    directory="./eval-data",
)
```

## Best practices for a good dataset

- **Diverse coverage**: real inputs varying in complexity, extreme cases, edge cases
- **Quantitative focus**: each golden tests something specific, not everything at once
- **Clear objectives**: align goldens with the chosen metrics
- **Small and good > large and bad**: 10 well-thought-out goldens > 100 generic goldens
- **Include failure modes**: at least 1-2 goldens for each prioritized failure mode
- **Versioning**: keep goldens in git (or Confident AI) to track changes

## How many goldens?

| Stage | Recommendation |
|---------|--------------|
| Smoke test (validate setup) | 1-2 |
| Early dev | 5-10 |
| Regular iteration | 20-50 |
| Pre-production | 50-200 |
| CI/CD in production | depends on cost (LLM-as-judge costs tokens) |

**Remember**: each golden = 1 agent call (token cost) + 1 LLM-as-judge call per metric (token cost). Do the math before running 1000 goldens with 5 metrics.

## Script you follow with the user

1. **Question**: "Single-turn or multi-turn?"
2. **Question**: "Do you prefer to start manually (recommended) or generate with Synthesizer?"
3. **If manual**: guide the user to create 5-10 goldens (use the 4 questions from Path 1)
4. **If Synthesizer**: ask about the source (docs/contexts/scratch), generate, then review together
5. **Validation**: run `print(dataset.goldens)` or `len(dataset.goldens)` to confirm
6. **Realism Gate**: run through the Production Realism Gate section below for each golden before finalizing. Do not skip. This step is mandatory.
7. **Save**: offer to save locally as JSON or push to Confident AI

## Production Realism Gate — mandatory before finalizing any scenario

This is the most important quality check. Before considering any golden final, answer this for **each one**:

> **"What information is in the `input` field that the LLM would NOT have in production?"**

Walk through every golden:

1. **What does the system prompt tell the LLM it can access?** (e.g., "use document_format from metadata", "use the filename from state")
2. **What context lives in system state, invisible to the LLM?** Common sources: `InjectedState` / LangGraph `state["..."]` fields, tool parameters populated by the orchestrator, metadata injected at runtime (document format, user tier, flags).
3. **Does the `input` field contain any of that invisible context?** Ask: "Would a real user plausibly type this exact phrase? Or does it carry information only the system would know?"

### Red flags (coached scenarios)

| Pattern in `input` | Why it's coached |
|---|---|
| "It is a PDF file named patient_records.pdf" | `document_format` lives in state, not in user text |
| "Please reprocess document with upload ID 64f3a2b1c9e7f05a" | The ID and the reprocess intent are separate concerns — in production the message can just be "helo" |
| "The image consists of scanned pages, not a PDF" | Format is injected via metadata; user message wouldn't carry this |
| Anything describing document type, file format, or system IDs | These almost always come from state, not user text |

### What to do when coaching is found

- **Option A**: Strip the coaching. Replace the coached `input` with a realistic minimal message ("process this", "go", "helo") and verify the expected outcome still holds — or update the expected outcome to reflect what should happen when the LLM lacks that context.
- **Option B**: Keep the coached golden as a "fully-informed happy path" **and** add an adversarial variant alongside it with the coaching stripped.
- **Option C**: If you find multiple coached scenarios, call `bagual-ai-evals-scenario-review` for a systematic audit across the full dataset.

### Quick self-check before saving

- [ ] Every `input` could plausibly be typed by a real user (or a real orchestrator message) in production
- [ ] No `input` bridges a gap between what the system prompt claims and what the LLM can actually see
- [ ] At least one scenario tests the agent when the user message is minimal/ambiguous
- [ ] At least one scenario tests an error path (tool failure, missing state field, invalid input)

## Closing

After creating the dataset, say:

> "Dataset with {N} goldens ready. Before choosing metrics, quick checkpoint: did all scenarios pass the Production Realism Gate? If any `input` fields contain format hints or IDs the LLM wouldn't have in production, now is the time to strip them or add adversarial variants. Want to run `bagual-ai-evals-scenario-review` to check, or proceed to `bagual-ai-evals-pick-metrics`?"

## Anti-patterns

- ❌ Forcing Synthesizer on a beginner user — doing it manually teaches better
- ❌ Creating 100 goldens before running any eval — small batch first
- ❌ Forgetting to cover failure modes — those are the most important ones
- ❌ Skipping `expected_tools` when you'll use `ToolCorrectnessMetric`
- ❌ Mixing single-turn and multi-turn in the same dataset (not possible)
