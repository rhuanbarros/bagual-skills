---
name: deepeval-instrument
description: Instrumentação do código do AI agent com @observe para DeepEval enxergar a árvore de execução. Use quando o usuário disser "instrumentar agent", "adicionar tracing", "como decorar o agent", "usar @observe", "instrumentar langgraph", "instrumentar crewai", ou similar.
---

# DeepEval Instrument — Adicionando @observe ao Agent

Você é o instrumentador. Seu trabalho: pegar o código de um agent (que pode ser Python puro ou usar um framework) e adicionar os decoradores `@observe` certos pra DeepEval mapear a árvore de execução. Sem isso, métricas como `ToolCorrectnessMetric` e `TaskCompletionMetric` não funcionam.

## Conceito central — em uma frase

Tracing é o que transforma o agent de **caixa-preta** (input → output) em **caixa-de-vidro** (input → reasoning → tool calls → tool outputs → reasoning → ... → output). DeepEval precisa enxergar a árvore inteira pra avaliar componentes individualmente.

## O que `@observe` faz

- Marca uma função como **span** dentro de uma trace
- Captura input e output automaticamente
- Aninha child spans automaticamente baseado na call stack (via `ContextVar`)
- **Não adiciona latência** — é não-intrusivo
- Permite anexar métricas direto à função: `@observe(metrics=[...])`

## Os 4 tipos de span

| Tipo | O que representa | Onde colocar |
|------|------------------|--------------|
| `agent` | Orquestrador raiz, top-level do agent | Função principal do agent |
| `llm` | Chamada de inferência do LLM | Função que chama `client.chat.completions.create()` ou similar |
| `tool` | Execução de tool externa (API, função, DB) | Cada função decorada como tool |
| `retriever` | Fetch de contexto (RAG) | Função que faz busca vetorial / recupera docs |

A regra de ouro: **decore as funções, não as classes**. DeepEval rastreia chamadas de função.

## Pergunta crítica antes de começar

"Você está usando algum framework de agent, ou é Python puro?"

- **Python puro / OpenAI direto** → siga seção "Instrumentação manual"
- **LangGraph** → seção "LangGraph"
- **CrewAI** → seção "CrewAI"
- **LlamaIndex** → seção "LlamaIndex"
- **Pydantic AI** → seção "Pydantic AI"
- **OpenAI Agents SDK** → seção "OpenAI Agents"

## Instrumentação manual (Python puro)

Você adiciona decoradores nas funções relevantes. Aqui o exemplo completo de um travel agent:

```python
import json
from openai import OpenAI
from deepeval.tracing import observe

client = OpenAI()

# Tools — cada uma decorada como type="tool"
@observe(type="tool", description="Search for available flights between two cities")
def search_flights(origin: str, destination: str, date: str) -> list:
    # sua API aqui
    return [{"id": "FL123", "price": 450}, {"id": "FL456", "price": 380}]

@observe(type="tool", description="Book a flight by ID")
def book_flight(flight_id: str) -> dict:
    # sua API aqui
    return {"confirmation": "CONF-789", "flight_id": flight_id}

# A função que chama o LLM — decorada como type="llm"
@observe(type="llm")
def call_llm(messages: list) -> str:
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        tools=tools_schema,
    )
    return response

# O orquestrador — decorado como type="agent" no topo
@observe(
    type="agent",
    available_tools=["search_flights", "book_flight"],
)
def travel_agent(user_input: str) -> str:
    messages = [{"role": "user", "content": user_input}]
    while True:
        response = call_llm(messages)
        # ... lógica de loop ...
        if final_answer:
            return final_answer
```

Quando você chama `travel_agent("Reserve um voo NYC→Paris")`, DeepEval automaticamente cria uma árvore:

```
agent: travel_agent
├── llm: call_llm (chamada 1)
├── tool: search_flights
├── llm: call_llm (chamada 2)
├── tool: book_flight
└── llm: call_llm (chamada 3, gera resposta final)
```

### Atributos especiais do `agent` span

| Atributo | O que faz |
|----------|-----------|
| `available_tools` | Lista (estática) das tools que o agent pode usar. Aparece no Confident AI e ajuda métricas a entender o universo de opções. |
| `agent_handoffs` | Lista de outros agents que esse pode delegar pra (multi-agent). |
| `metric_collection` | Nome de coleção de métricas no Confident AI pra rodar async em produção. |
| `metrics` | Lista de métricas pra rodar **síncronas** durante dev. |

### Atributos do `tool` span

| Atributo | O que faz |
|----------|-----------|
| `description` | Descrição da tool. Loga no span e propaga automaticamente pro `tools_called` do LLM span pai. |

### Como tools_called é populado automaticamente

Quando uma função `type="tool"` executa **dentro** de uma `type="llm"`, DeepEval **automaticamente** infere que essa tool foi chamada por aquela inferência LLM e popula o atributo `tools_called` do LLM span. Você não precisa setar manualmente.

```python
@observe(type="llm")
def call_openai(messages):
    response = client.chat.completions.create(...)
    
    # Se aqui dentro alguma função @observe(type="tool") for chamada,
    # DeepEval anota ela em tools_called do span deste call_openai automaticamente.
    
    if tool_call:
        result = search_flights(...)  # type="tool" → vira child span
    
    return response
```

## Multi-Agent

Quando um agent delega pra outro agent, DeepEval rastreia automaticamente porque `@observe` usa `ContextVar` pra ver a call stack.

```python
@observe(type="agent", available_tools=["search_hotels"], agent_handoffs=[])
def hotel_agent(request: str) -> str:
    # lógica do sub-agent
    return result

@observe(
    type="agent",
    available_tools=["search_flights"],
    agent_handoffs=["hotel_agent"],  # declaração estática do que é POSSÍVEL
)
def travel_coordinator(request: str) -> str:
    flights = search_flights(...)
    
    # Quando travel_coordinator chama hotel_agent, hotel_agent vira
    # child span do travel_coordinator AUTOMATICAMENTE.
    hotels = hotel_agent("Hotel pra Dec 1st em LAX")
    
    return f"Voos: {flights}, Hotéis: {hotels}"
```

**Importante**: `agent_handoffs` é uma **declaração estática** do que é possível. As delegações reais que ocorrem em runtime são capturadas dinamicamente pelo span tree em si.

## Ground truth pra avaliação — `expected_tools`

Pra `ToolCorrectnessMetric` calcular precisão/recall, ele precisa saber quais tools **deveriam** ter sido chamadas. Você fornece isso via `update_current_span` dentro do LLM span:

```python
from deepeval.tracing import observe, update_current_span
from deepeval.test_case import ToolCall

@observe(type="llm")
def call_llm(messages: list, expected_tool_calls: list = None) -> str:
    response = client.chat.completions.create(model="gpt-4o", messages=messages)
    
    # Anexa ground truth pro componente
    if expected_tool_calls:
        update_current_span(expected_tools=expected_tool_calls)
    
    return response
```

E o golden do dataset traz essa info:

```python
from deepeval.dataset import Golden
from deepeval.test_case import ToolCall

golden = Golden(
    input="Search for flights from NYC to LA",
    expected_tools=[ToolCall(name="search_flights")],
)
```

Quando você roda `evals_iterator`, o Golden é exposto via `get_current_golden()` e você pega o `expected_tools` dele:

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

## LangGraph (auto-instrumentação) — IMPORTANTE PRA QUEM USA LANGGRAPH

Se você usa LangGraph, **não precisa adicionar `@observe` manualmente**. DeepEval tem uma integração nativa: você passa um `CallbackHandler` no `config` quando invoca o graph, e ele intercepta chain, LLM e tool events automaticamente, montando a árvore de spans.

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

# Passa CallbackHandler como config — todos os spans são capturados automaticamente
result = agent.invoke(
    input={"messages": [{"role": "user", "content": "What's the weather in Paris?"}]},
    config={"callbacks": [CallbackHandler()]},
)
```

Pra graphs custom (não `create_react_agent`), passa o `CallbackHandler` no mesmo lugar — qualquer execução dentro daquele graph fica rastreada.

## CrewAI (auto-instrumentação)

Uma linha antes de definir o crew:

```python
from crewai import Task, Crew, Agent
from crewai.tools import tool
from deepeval.integrations.crewai import instrument_crewai

instrument_crewai()  # ← uma linha, registra event listener

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
crew.kickoff({"city": "Paris"})  # tudo capturado automaticamente
```

## LlamaIndex (auto-instrumentação)

```python
import llama_index.core.instrumentation as instrument
from llama_index.llms.openai import OpenAI
from llama_index.core.agent import FunctionAgent
from deepeval.integrations.llama_index import instrument_llama_index

# One-liner: auto-instrumenta todos os spans
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

## Pydantic AI (auto-instrumentação)

```python
from pydantic_ai import Agent
from deepeval.integrations.pydantic_ai import ConfidentInstrumentationSettings

agent = Agent(
    "openai:gpt-4o-mini",
    instructions="You are a helpful travel assistant.",
    instrument=ConfidentInstrumentationSettings(),  # ← exporta via OTel
)

result = agent.run_sync("Book me a flight from JFK to LAX.")
```

Esse exporta via OpenTelemetry pro Confident AI automaticamente.

## OpenAI Agents SDK (auto-instrumentação)

```python
from agents import Runner, add_trace_processor
from deepeval.openai_agents import Agent, DeepEvalTracingProcessor

# Registra global, uma vez
add_trace_processor(DeepEvalTracingProcessor())

travel_agent = Agent(
    name="Travel Agent",
    instructions="You are a helpful travel assistant.",
)

result = Runner.run_sync(travel_agent, "Book me a flight from JFK to LAX.")
```

## Verificando que funcionou — acesso local ao trace

Mesmo sem Confident AI, você pode ver as traces capturadas in-memory:

```python
from deepeval.tracing import trace_manager

# Roda o agent
travel_agent("Reserve voo NYC→Paris")

# Pega todas as traces como dicts Python
traces = trace_manager.get_all_traces_dict()

for trace in traces:
    print(f"Input: {trace.get('input')}")
    print(f"Output: {trace.get('output')}")
    
    # Inspeciona cada span
    for span_type in ["agentSpans", "llmSpans", "toolSpans"]:
        for span in trace.get(span_type, []):
            print(f"  [{span_type}] {span.get('name')}: {span.get('input')} → {span.get('output')}")
```

**Tip**: use `trace_manager.clear_traces()` entre rodadas pra não acumular traces antigas em memória.

## Roteiro de instrumentação que você segue com o usuário

1. **Pergunta**: "Qual framework? Python puro / LangGraph / CrewAI / LlamaIndex / Pydantic AI / OpenAI Agents?"
2. **Pergunta**: "Pode me mostrar o código atual do seu agent? Ou pelo menos a estrutura: qual função é o orquestrador, quais funções são tools, qual chama o LLM?"
3. **Diagnóstico**: olhe o código e identifique:
   - Função orquestradora → vai virar `@observe(type="agent")`
   - Função(ões) que chamam LLM → vai virar `@observe(type="llm")`
   - Funções que chamam APIs/DB/funções externas → vão virar `@observe(type="tool")`
   - Se tem RAG → função de retrieval vira `@observe(type="retriever")`
4. **Aplica**: edite o código junto com o usuário, mostrando antes/depois.
5. **Valida**: rode uma vez, depois `trace_manager.get_all_traces_dict()` e mostre o trace dict.

## Erros comuns na instrumentação

| Erro | Causa | Fix |
|------|-------|-----|
| Spans não nidificam | Está chamando função não decorada no meio | Decore a função intermediária, ou faça call direto |
| `tools_called` vazio | Tool não tá decorada como `type="tool"` | Confira o decorator |
| Métrica não roda | Não tá usando `evals_iterator` | Use o pattern `for golden in dataset.evals_iterator(metrics=[...]): your_agent(golden.input)` |
| Traces vazias | Não rodou o agent dentro do contexto rastreável | Confira que o `@observe(type="agent")` está aplicado |
| Multi-agent não nidifica | Sub-agent foi chamado fora do call stack do parent | Garanta que sub-agent é chamado de dentro do parent diretamente |

## Como rodar evals com agent instrumentado

Esse padrão você vai usar muito (e tá detalhado em `deepeval-run-and-analyze`):

```python
from deepeval.dataset import EvaluationDataset, Golden
from deepeval.metrics import TaskCompletionMetric

dataset = EvaluationDataset(goldens=[
    Golden(input="Reserve um voo de NYC pra Paris pra próxima segunda"),
])

task_completion = TaskCompletionMetric(threshold=0.7)

# Loop através do dataset
for golden in dataset.evals_iterator(metrics=[task_completion]):
    travel_agent(golden.input)  # qualquer função decorada com @observe(type="agent")
```

DeepEval automaticamente coleta as traces dentro do `evals_iterator` e roda as métricas nelas.

## Encerramento

Após instrumentar e validar, o próximo passo depende de onde o usuário está:

**Se já tem tráfego de produção ou pode rodar o agent contra inputs reais**:
> "Beleza, agent instrumentado. Agora que você consegue gerar traces reais, o próximo passo crítico é **trace review** — ler 30-50 outputs do agent pra descobrir os modos de falha reais antes de escrever evals. Isso é o que separa eval system real de vibe-check disfarçado. Quer que eu chame `deepeval-error-analysis`?"

**Se ainda não tem como gerar traces reais**:
> "Beleza, agent instrumentado. Próximo passo é criar dataset inicial de goldens pra conseguir rodar o agent e gerar traces. Quer que eu chame `deepeval-build-dataset`? Depois disso, recomendo fortemente fazer trace review via `deepeval-error-analysis` antes de escolher métricas — é o passo que a maioria dos times pula e que mais determina qualidade dos evals."

## Anti-patterns

- ❌ Decorar **todas** as funções — só decore as relevantes (orchestrator, LLM call, tools, retriever)
- ❌ Usar `@observe()` sem `type=` — funciona mas perde a semântica e a visualização piora
- ❌ Esquecer de `update_current_span(expected_tools=...)` quando vai usar `ToolCorrectnessMetric`
- ❌ Misturar instrumentação manual com auto-instrument do framework — escolha um caminho
- ❌ Decorar uma função e chamar ela fora do contexto do `evals_iterator` esperando que métricas rodem
