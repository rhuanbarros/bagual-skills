---
name: bagual-ai-evals-instrument
description: Instrumenting AI agent code with @observe so DeepEval can see the execution tree. Use when the user says "instrument agent", "add tracing", "how to decorate the agent", "use @observe", "instrument langgraph", "instrument crewai", or similar.
---

# DeepEval Instrument — Adding @observe to the Agent

You are the instrumenter. Your job: take the code of an agent (which may be plain Python or use a framework) and add the right `@observe` decorators so DeepEval can map the execution tree. Without this, metrics like `ToolCorrectnessMetric` and `TaskCompletionMetric` will not work.

## Core concept — in one sentence

Tracing is what transforms the agent from a **black box** (input → output) into a **glass box** (input → reasoning → tool calls → tool outputs → reasoning → ... → output). DeepEval needs to see the entire tree to evaluate individual components.

## What `@observe` does

- Marks a function as a **span** within a trace
- Captures input and output automatically
- Nests child spans automatically based on the call stack (via `ContextVar`)
- **Adds no latency** — it's non-intrusive
- Allows attaching metrics directly to the function: `@observe(metrics=[...])`

## The 4 span types

| Type | What it represents | Where to place it |
|------|------------------|--------------|
| `agent` | Root orchestrator, top-level of the agent | Main agent function |
| `llm` | LLM inference call | Function that calls `client.chat.completions.create()` or similar |
| `tool` | External tool execution (API, function, DB) | Each function decorated as a tool |
| `retriever` | Context fetch (RAG) | Function that does vector search / retrieves docs |

The golden rule: **decorate functions, not classes**. DeepEval tracks function calls.

## Critical question before starting

"Are you using any agent framework, or is it plain Python?"

- **Plain Python / OpenAI direct** → follow the "Manual instrumentation" section
- **LangGraph** → "LangGraph" section
- **CrewAI** → "CrewAI" section
- **LlamaIndex** → "LlamaIndex" section
- **Pydantic AI** → "Pydantic AI" section
- **OpenAI Agents SDK** → "OpenAI Agents" section

## Manual instrumentation (plain Python)

You add decorators to the relevant functions. Here is the complete example of a travel agent:

```python
import json
from openai import OpenAI
from deepeval.tracing import observe

client = OpenAI()

# Tools — each decorated with type="tool"
@observe(type="tool", description="Search for available flights between two cities")
def search_flights(origin: str, destination: str, date: str) -> list:
    # your API here
    return [{"id": "FL123", "price": 450}, {"id": "FL456", "price": 380}]

@observe(type="tool", description="Book a flight by ID")
def book_flight(flight_id: str) -> dict:
    # your API here
    return {"confirmation": "CONF-789", "flight_id": flight_id}

# The function that calls the LLM — decorated with type="llm"
@observe(type="llm")
def call_llm(messages: list) -> str:
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        tools=tools_schema,
    )
    return response

# The orchestrator — decorated with type="agent" at the top
@observe(
    type="agent",
    available_tools=["search_flights", "book_flight"],
)
def travel_agent(user_input: str) -> str:
    messages = [{"role": "user", "content": user_input}]
    while True:
        response = call_llm(messages)
        # ... loop logic ...
        if final_answer:
            return final_answer
```

When you call `travel_agent("Book a flight NYC→Paris")`, DeepEval automatically creates a tree:

```
agent: travel_agent
├── llm: call_llm (call 1)
├── tool: search_flights
├── llm: call_llm (call 2)
├── tool: book_flight
└── llm: call_llm (call 3, generates final response)
```

### Special attributes of the `agent` span

| Attribute | What it does |
|----------|-----------|
| `available_tools` | (Static) list of tools the agent can use. Appears in Confident AI and helps metrics understand the universe of options. |
| `agent_handoffs` | List of other agents this one can delegate to (multi-agent). |
| `metric_collection` | Name of a metric collection in Confident AI to run async in production. |
| `metrics` | List of metrics to run **synchronously** during dev. |

### Attributes of the `tool` span

| Attribute | What it does |
|----------|-----------|
| `description` | Description of the tool. Logged on the span and automatically propagated to the `tools_called` attribute of the parent LLM span. |

### How tools_called is populated automatically

When a `type="tool"` function executes **inside** a `type="llm"`, DeepEval **automatically** infers that this tool was called by that LLM inference and populates the `tools_called` attribute of the LLM span. You don't need to set it manually.

```python
@observe(type="llm")
def call_openai(messages):
    response = client.chat.completions.create(...)
    
    # If any @observe(type="tool") function is called inside here,
    # DeepEval records it in tools_called for this call_openai span automatically.
    
    if tool_call:
        result = search_flights(...)  # type="tool" → becomes a child span
    
    return response
```

## Multi-Agent

When one agent delegates to another, DeepEval tracks it automatically because `@observe` uses `ContextVar` to see the call stack.

```python
@observe(type="agent", available_tools=["search_hotels"], agent_handoffs=[])
def hotel_agent(request: str) -> str:
    # sub-agent logic
    return result

@observe(
    type="agent",
    available_tools=["search_flights"],
    agent_handoffs=["hotel_agent"],  # static declaration of what is POSSIBLE
)
def travel_coordinator(request: str) -> str:
    flights = search_flights(...)
    
    # When travel_coordinator calls hotel_agent, hotel_agent becomes
    # a child span of travel_coordinator AUTOMATICALLY.
    hotels = hotel_agent("Hotel for Dec 1st in LAX")
    
    return f"Flights: {flights}, Hotels: {hotels}"
```

**Important**: `agent_handoffs` is a **static declaration** of what is possible. The actual delegations that occur at runtime are captured dynamically by the span tree itself.

## Ground truth for evaluation — `expected_tools`

For `ToolCorrectnessMetric` to calculate precision/recall, it needs to know which tools **should** have been called. You provide this via `update_current_span` inside the LLM span:

```python
from deepeval.tracing import observe, update_current_span
from deepeval.test_case import ToolCall

@observe(type="llm")
def call_llm(messages: list, expected_tool_calls: list = None) -> str:
    response = client.chat.completions.create(model="gpt-4o", messages=messages)
    
    # Attach ground truth to the component
    if expected_tool_calls:
        update_current_span(expected_tools=expected_tool_calls)
    
    return response
```

And the dataset golden carries this info:

```python
from deepeval.dataset import Golden
from deepeval.test_case import ToolCall

golden = Golden(
    input="Search for flights from NYC to LA",
    expected_tools=[ToolCall(name="search_flights")],
)
```

When you run `evals_iterator`, the Golden is exposed via `get_current_golden()` and you retrieve its `expected_tools`:

```python
from deepeval.dataset import get_current_golden

@observe(type="llm", metrics=[tool_correctness])
def call_llm(messages):
    response = client.chat.completions.create(...)
    update_current_span(
        input=messages[-1]["content"],
        output=str(response),
        expected_tools=get_current_golden().expected_tools,
    )
    return response
```

## LangGraph (auto-instrumentation) — IMPORTANT FOR LANGGRAPH USERS

If you use LangGraph, **you don't need to add `@observe` manually**. DeepEval has a native integration: you pass a `CallbackHandler` in the `config` when invoking the graph, and it intercepts chain, LLM, and tool events automatically, assembling the span tree.

```python
from langgraph.prebuilt import create_react_agent
from deepeval.integrations.langchain import CallbackHandler

def get_weather(city: str) -> str:
    """Returns the weather in a city."""
    return f"It's always sunny in {city}!"

agent = create_react_agent(
    model="openai:gpt-4o-mini",
    tools=[get_weather],
    prompt="You are a helpful assistant",
)

# Pass CallbackHandler as config — all spans are captured automatically
result = agent.invoke(
    input={"messages": [{"role": "user", "content": "What's the weather in Paris?"}]},
    config={"callbacks": [CallbackHandler()]},
)
```

For custom graphs (not `create_react_agent`), pass the `CallbackHandler` in the same place — any execution inside that graph gets traced.

## CrewAI (auto-instrumentation)

One line before defining the crew:

```python
from crewai import Task, Crew, Agent
from crewai.tools import tool
from deepeval.integrations.crewai import instrument_crewai

instrument_crewai()  # ← one line, registers event listener

@tool
def get_weather(city: str) -> str:
    """Fetch weather data."""
    return f"It's sunny in {city}!"

agent = Agent(
    role="Weather Reporter",
    goal="Provide accurate weather.",
    backstory="An experienced meteorologist.",
    tools=[get_weather],
)

task = Task(
    description="Get the current weather for {city}.",
    expected_output="A brief weather report.",
    agent=agent,
)

crew = Crew(agents=[agent], tasks=[task])
crew.kickoff({"city": "Paris"})  # everything captured automatically
```

## LlamaIndex (auto-instrumentation)

```python
import llama_index.core.instrumentation as instrument
from llama_index.llms.openai import OpenAI
from llama_index.core.agent import FunctionAgent
from deepeval.integrations.llama_index import instrument_llama_index

# One-liner: auto-instruments all spans
instrument_llama_index(instrument.get_dispatcher())

def get_weather(city: str) -> str:
    """Get weather in a city."""
    return f"Sunny in {city}!"

agent = FunctionAgent(
    tools=[get_weather],
    llm=OpenAI(model="gpt-4o-mini"),
    system_prompt="You are a helpful assistant.",
)

import asyncio
result = asyncio.run(agent.run("What's the weather in Paris?"))
```

## Pydantic AI (auto-instrumentation)

```python
from pydantic_ai import Agent
from deepeval.integrations.pydantic_ai import ConfidentInstrumentationSettings

agent = Agent(
    "openai:gpt-4o-mini",
    instructions="You are a helpful travel assistant.",
    instrument=ConfidentInstrumentationSettings(),  # ← exports via OTel
)

result = agent.run_sync("Book me a flight from JFK to LAX.")
```

This exports via OpenTelemetry to Confident AI automatically.

## OpenAI Agents SDK (auto-instrumentation)

```python
from agents import Runner, add_trace_processor
from deepeval.openai_agents import Agent, DeepEvalTracingProcessor

# Register globally, once
add_trace_processor(DeepEvalTracingProcessor())

travel_agent = Agent(
    name="Travel Agent",
    instructions="You are a helpful travel assistant.",
)

result = Runner.run_sync(travel_agent, "Book me a flight from JFK to LAX.")
```

## Verifying it worked — local trace access

Even without Confident AI, you can see the captured traces in-memory:

```python
from deepeval.tracing import trace_manager

# Run the agent
travel_agent("Book flight NYC→Paris")

# Get all traces as Python dicts
traces = trace_manager.get_all_traces_dict()

for trace in traces:
    print(f"Input: {trace.get('input')}")
    print(f"Output: {trace.get('output')}")
    
    # Inspect each span
    for span_type in ["agentSpans", "llmSpans", "toolSpans"]:
        for span in trace.get(span_type, []):
            print(f"  [{span_type}] {span.get('name')}: {span.get('input')} → {span.get('output')}")
```

**Tip**: use `trace_manager.clear_traces()` between runs to avoid accumulating old traces in memory.

## Instrumentation script you follow with the user

1. **Question**: "What framework? Plain Python / LangGraph / CrewAI / LlamaIndex / Pydantic AI / OpenAI Agents?"
2. **Question**: "Can you show me the current code of your agent? Or at least the structure: which function is the orchestrator, which functions are tools, which one calls the LLM?"
3. **Diagnosis**: look at the code and identify:
   - Orchestrator function → will become `@observe(type="agent")`
   - Function(s) that call the LLM → will become `@observe(type="llm")`
   - Functions that call APIs/DB/external functions → will become `@observe(type="tool")`
   - If there's RAG → the retrieval function becomes `@observe(type="retriever")`
4. **Apply**: edit the code together with the user, showing before/after.
5. **Validate**: run it once, then `trace_manager.get_all_traces_dict()` and show the trace dict.

## Common instrumentation errors

| Error | Cause | Fix |
|------|-------|-----|
| Spans don't nest | Calling an undecorated function in the middle | Decorate the intermediate function, or make a direct call |
| `tools_called` is empty | Tool is not decorated with `type="tool"` | Check the decorator |
| Metric doesn't run | Not using `evals_iterator` | Use the pattern `for golden in dataset.evals_iterator(metrics=[...]): your_agent(golden.input)` |
| Empty traces | Agent was not run inside a traceable context | Check that `@observe(type="agent")` is applied |
| Multi-agent doesn't nest | Sub-agent was called outside the parent's call stack | Ensure the sub-agent is called directly from within the parent |

## How to run evals with an instrumented agent

You'll use this pattern often (and it's detailed in `bagual-ai-evals-run-and-analyze`):

```python
from deepeval.dataset import EvaluationDataset, Golden
from deepeval.metrics import TaskCompletionMetric

dataset = EvaluationDataset(goldens=[
    Golden(input="Book a flight from NYC to Paris for next Monday"),
])

task_completion = TaskCompletionMetric(threshold=0.7)

# Loop through the dataset
for golden in dataset.evals_iterator(metrics=[task_completion]):
    travel_agent(golden.input)  # any function decorated with @observe(type="agent")
```

DeepEval automatically collects the traces inside `evals_iterator` and runs the metrics on them.

## Closing

After instrumenting and validating, the next step depends on where the user is:

**If they already have production traffic or can run the agent against real inputs**:
> "Great, agent instrumented. Now that you can generate real traces, the critical next step is **trace review** — reading 30-50 agent outputs to discover the real failure modes before writing evals. This is what separates a real eval system from a disguised vibe-check. Want me to call `bagual-ai-evals-error-analysis`?"

**If they can't yet generate real traces**:
> "Great, agent instrumented. Next step is creating an initial golden dataset to be able to run the agent and generate traces. Want me to call `bagual-ai-evals-build-dataset`? After that, I strongly recommend doing trace review via `bagual-ai-evals-error-analysis` before choosing metrics — it's the step most teams skip and the one that most determines eval quality."

## Anti-patterns

- ❌ Decorating **all** functions — only decorate the relevant ones (orchestrator, LLM call, tools, retriever)
- ❌ Using `@observe()` without `type=` — it works but loses semantics and the visualization degrades
- ❌ Forgetting `update_current_span(expected_tools=...)` when you're going to use `ToolCorrectnessMetric`
- ❌ Mixing manual instrumentation with the framework's auto-instrumentation — choose one path
- ❌ Decorating a function and calling it outside the `evals_iterator` context expecting metrics to run
