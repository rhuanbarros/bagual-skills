---
name: bagual-ai-evals-run-and-analyze
description: Execução de evals locais e análise/interpretação de resultados de DeepEval. Use quando o usuário disser "rodar evals", "analisar resultados", "interpretar score", "evals_iterator", "deepeval test run", "diagnosticar falha", ou similar.
---

# DeepEval Run and Analyze — Executando e Interpretando Evals

Você é o executor e analista. Tem dois trabalhos:

1. **Rodar a primeira eval** com o setup que o usuário tem (agent instrumentado + dataset + métricas)
2. **Analisar os resultados** e dizer o que mudar

## Pré-requisitos — confira antes de começar

- [ ] Agent instrumentado com `@observe` (skill `bagual-ai-evals-instrument`)
- [ ] Dataset com goldens criados (skill `bagual-ai-evals-build-dataset`)
- [ ] Métricas definidas e configuradas (skill `bagual-ai-evals-pick-metrics`)
- [ ] Chave LLM configurada (skill `bagual-ai-evals-setup`)

Se faltar alguma coisa, rote pra skill correspondente antes de prosseguir.

## Os 3 jeitos de rodar evals

| Forma | Quando usar | Comando |
|-------|-------------|---------|
| **`evals_iterator`** | Caso default pra agents (padrão recomendado) | `python script.py` |
| **`evaluate()`** | Test cases já prontos, sem usar dataset com loop | `python script.py` |
| **`deepeval test run`** | CI/CD, integração com pytest | `deepeval test run test_file.py` |

## Forma 1 — `evals_iterator` (padrão pra agents)

Esse é o que você vai usar 95% das vezes pra agents. Ele:

1. Itera sobre os goldens do dataset
2. Pra cada golden, chama o agent (que tá decorado com `@observe`)
3. Coleta as traces automaticamente
4. Roda as métricas (end-to-end e component-level)
5. Agrega os resultados

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

# Métricas
task_completion = TaskCompletionMetric(threshold=0.7)
step_efficiency = StepEfficiencyMetric(threshold=0.7)
tool_correctness = ToolCorrectnessMetric(threshold=0.7)
argument_correctness = ArgumentCorrectnessMetric(threshold=0.7)

# Dataset
dataset = EvaluationDataset(goldens=[
    Golden(
        input="Reserve um voo de NYC pra Paris pra próxima segunda",
        expected_tools=[ToolCall(name="search_flights"), ToolCall(name="book_flight")],
    ),
    Golden(
        input="Quero ir pra Paris",
        expected_tools=[],
    ),
])

# Component-level metrics → no LLM span
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
        # ... lógica do loop ...
        if final:
            return final_answer

# Rodar — end-to-end metrics passam aqui
for golden in dataset.evals_iterator(metrics=[task_completion, step_efficiency]):
    travel_agent(golden.input)
```

Quando essa célula termina, DeepEval imprime o relatório no terminal. Se logado no Confident AI, também envia pra dashboard.

### Output típico no terminal

```
========================================================
Evaluating 2 test cases
========================================================

Test case 1: "Reserve um voo de NYC pra Paris pra próxima segunda"
  ✓ TaskCompletionMetric: 0.85 (threshold: 0.7) — PASSED
  ✓ StepEfficiencyMetric: 0.78 (threshold: 0.7) — PASSED
  ✓ ToolCorrectnessMetric: 1.00 (threshold: 0.7) — PASSED
  ✓ ArgumentCorrectnessMetric: 0.92 (threshold: 0.7) — PASSED

Test case 2: "Quero ir pra Paris"
  ✗ TaskCompletionMetric: 0.45 (threshold: 0.7) — FAILED
    Reason: Agent didn't ask for clarification on dates and origin.
  ✓ StepEfficiencyMetric: 0.95 (threshold: 0.7) — PASSED
  ✓ ToolCorrectnessMetric: 1.00 (threshold: 0.7) — PASSED  
  ✓ ArgumentCorrectnessMetric: 0.85 (threshold: 0.7) — PASSED

========================================================
Summary: 1/2 passed (50%)
========================================================
```

## Forma 2 — `evaluate()` (test cases prontos)

Use quando você tem `LLMTestCase`s prontos (não goldens) e quer só rodar metrics neles:

```python
from deepeval import evaluate
from deepeval.metrics import AnswerRelevancyMetric

evaluate(
    test_cases=dataset.test_cases,  # ou lista direta
    metrics=[AnswerRelevancyMetric()],
)
```

## Forma 3 — `deepeval test run` (CI/CD)

Pra integração com pytest:

```python
# test_my_agent.py
import pytest
from deepeval import assert_test
from deepeval.metrics import TaskCompletionMetric
from deepeval.test_case import LLMTestCase

dataset = ...  # carrega o dataset

@pytest.mark.parametrize("test_case", dataset.test_cases)
def test_agent(test_case: LLMTestCase):
    metric = TaskCompletionMetric(threshold=0.7)
    assert_test(test_case=test_case, metrics=[metric])
```

Depois roda:

```bash
deepeval test run test_my_agent.py
```

Esse comando trata cada test case como um teste pytest separado. Vai mostrar PASSED/FAILED por test case, e o exit code é não-zero se algum falhar — perfeito pra CI/CD.

Pra detalhes de CI/CD, veja a skill `bagual-ai-evals-production`.

## Após rodar — análise dos resultados

A parte que importa: **interpretar o que aconteceu e decidir o que mudar**. Use essa árvore de diagnóstico:

### Árvore de diagnóstico

```
TaskCompletionMetric BAIXO (< 0.7)?
│
├── SIM → Onde tá o problema?
│   │
│   ├── ToolCorrectnessMetric BAIXO?
│   │   └── Agent escolhe tool errada
│   │       FIX: melhorar descrição das tools no schema
│   │       FIX: melhorar nome das tools (descritivos)
│   │       FIX: reduzir número de tools (LLM se confunde com muitas)
│   │       FIX: adicionar exemplos no system prompt
│   │
│   ├── ArgumentCorrectnessMetric BAIXO?
│   │   └── Agent escolhe tool certa mas com args errados
│   │       FIX: melhorar schemas das tools (types, required, enum)
│   │       FIX: adicionar exemplos de input/output
│   │       FIX: usar modelo melhor (gpt-4o vs gpt-3.5)
│   │       FIX: temperature menor (mais determinístico)
│   │
│   ├── PlanQualityMetric BAIXO?
│   │   └── Agent não cria plano coerente
│   │       FIX: melhorar system prompt (CoT explicit)
│   │       FIX: usar modelo com melhor reasoning
│   │       FIX: dar exemplos de planos bons
│   │
│   ├── PlanAdherenceMetric BAIXO mas PlanQuality OK?
│   │   └── Agent cria bom plano mas não segue
│   │       FIX: forçar agent a re-ler o plano antes de cada step
│   │       FIX: estruturar plano em formato mais rígido
│   │       FIX: instruir explicitamente "follow your plan"
│   │
│   └── Tudo OK mas TaskCompletion baixo?
│       └── Falha de orquestração ou edge case
│           FIX: revisar loop logic do agent
│           FIX: adicionar handling de erros
│           FIX: olhar a trace bruta pra ver o que aconteceu
│
├── NÃO (TaskCompletion OK) → Outras métricas?
│   │
│   ├── StepEfficiencyMetric BAIXO?
│   │   └── Agent funciona mas é ineficiente
│   │       FIX: detectar redundância (mesmo tool 2x com mesmos args)
│   │       FIX: cache de tool results dentro de uma run
│   │       FIX: melhorar prompt pra evitar reasoning circular
│   │
│   └── Custom metric (GEval) BAIXO?
│       └── Critério específico não tá sendo atendido
│           FIX: depende do critério, mas geralmente prompt engineering
```

### Padrões comuns que você vai ver

**Padrão A**: TaskCompletion alto + StepEfficiency baixo
- **Diagnóstico**: agent funciona mas faz desperdício
- **Ação**: otimizar (não muda lógica, só reduz steps)

**Padrão B**: ToolCorrectness alto + ArgumentCorrectness baixo
- **Diagnóstico**: escolhe tool certa, args errados
- **Ação**: schemas das tools precisam de mais detalhe

**Padrão C**: PlanQuality alto + PlanAdherence baixo
- **Diagnóstico**: planeja bem mas não executa o plano
- **Ação**: estrutura mais rígida ou re-injection do plano em cada step

**Padrão D**: Tudo passa exceto em goldens edge case
- **Diagnóstico**: agent tá bom no caminho feliz, ruim em casos difíceis
- **Ação**: melhorar handling de ambiguidade no prompt

**Padrão E**: Tudo aleatório (passa hoje, falha amanhã)
- **Diagnóstico**: temperature muito alto ou prompt instável
- **Ação**: temperature menor, prompt mais explícito

### Lendo a `reason` de cada métrica

Quando você passa `include_reason=True`, a métrica retorna uma justificativa textual. **LEIA**. É onde você acha o "porquê" do score.

Exemplo:
```
TaskCompletionMetric: 0.45
Reason: The agent partially addressed the user request by searching for flights, 
but did not complete the booking step despite the user explicitly asking for it. 
The output ended with a list of options instead of a confirmation.
```

Isso te diz exatamente o que mudar.

## ⚠️ Mental models críticos antes de analisar

Esses 3 insights mudam radicalmente como você lê resultados de evals.

### 1. 70% pass rate é healthy. 95% é vermelho.

> Se tudo passa 95% das vezes na sua suite, suas evals tão medindo coisas que seu agent **já faz bem**.
> Uma suite bem-desenhada derivada de padrões reais de falha deveria produzir pass rate **~70% na primeira rodada**.

| Pass rate inicial | Diagnóstico | Ação |
|-------------------|-------------|------|
| **95%+** | Falsa segurança. Suite não testa coisas que falham. | Volte pro `bagual-ai-evals-error-analysis`, faça trace review, derive critérios product-specific. |
| **70-85%** | **Healthy.** Tem signal real. | Itere no agent, não nos evals. |
| **40-70%** | OK também — agent precisa trabalho mas evals tão calibrados | Priorize as categorias com pior score. |
| **<40%** | Definições muito loose OU agent fundamentalmente quebrado | Re-valide as definições dos judges (bagual-ai-evals-custom-metric). |

Se o usuário roda evals e tudo passa, **isso é vermelho**, não verde. A função do eval é catch failures — se não tá pegando nada, não tá fazendo o trabalho.

### 2. τ-bench fault taxonomy — classifique falhas em vez de "quality dropped"

Em vez de notar "quality score caiu", classifique cada falha nessa taxonomia (entity × failure type). Converte pos-mortems em categorias **acionáveis**.

| Fault type | Descrição | Signal primário | Fix típico |
|------------|-----------|-----------------|------------|
| `goal_partially_completed` | Agent resolveu parte da task, missed subgoals | `ConversationCompletenessMetric < 1.0` | Prompt clarification, multi-intent handling |
| `used_wrong_tool` | Intent correto, tool errada | Trajectory mismatch | Tool descriptions, schemas, naming |
| `used_wrong_tool_argument` | Tool correta, args malformados | Schema validation + audit | Schema docs no system prompt |
| `took_unintended_action` | Agent fez algo não pedido | Policy DAG violation | Policy enforcement, ConversationalDAGMetric |

**Use isso pra agrupar incidents**. Se 80% dos seus incidents da semana são `used_wrong_tool_argument`, o fix é **schema documentation no system prompt**, não prompt rewriting genérico. Se você tá vendo spikes de `took_unintended_action`, você tem policy enforcement problem que deveria estar pegando em CI antes de chegar em prod.

### 3. Single-run failure pode ser variance, não bug

Antes de declarar "isso é um bug que precisa fix", **rode o test case 4-8 vezes**. Calcule pass^k.

Se pass^1 ≈ 70% e pass^4 ≈ 60%, é variance baixa — agent é consistentemente bom mas imperfeito. Se pass^1 ≈ 70% e pass^4 ≈ 25%, é variance alta — agent é instável. Os fixes são diferentes:

| Padrão | Diagnóstico | Fix |
|--------|-------------|-----|
| Pass^1 alto, pass^k próximo | Reliability OK, agent é confiável | Foco em casos específicos que falham |
| Pass^1 alto, pass^k colapsa | High variance — instabilidade | Temperature baixar, prompt mais explícito, decision logic mais rígida |
| Pass^1 baixo | Falha consistente | Mexer no que tá causando — pode ser modelo, prompt, schema |

## Acessando traces local pra debug profundo

Se a métrica não te diz o suficiente, vá pra trace bruta:

```python
from deepeval.tracing import trace_manager

# Roda
travel_agent("...")

# Pega traces
traces = trace_manager.get_all_traces_dict()

for trace in traces:
    print(f"\n=== Trace: {trace.get('input')[:50]}... ===")
    print(f"Output: {trace.get('output')}")
    
    # Vai por tipo de span
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

Use `trace_manager.clear_traces()` entre runs pra não acumular.

## Confident AI — visualização

Se logado, tudo aparece automaticamente lá. Pra ver:

```bash
deepeval view
```

Abre o navegador no test run mais recente. Vantagens:

- Árvore visual de spans (click pra inspecionar inputs/outputs)
- Comparação lado-a-lado de runs (regression testing)
- Filtros por test case status (passed/failed)
- Export de relatórios pra compartilhar com time

## Iteração — o ciclo

Esse é o ciclo que você vai repetir:

```
1. Rodar evals
2. Olhar resultados
3. Identificar pior padrão (use a árvore acima)
4. Hipotetizar UMA mudança
5. Aplicar a mudança
6. Re-rodar
7. Comparar com antes (Confident AI faz isso visualmente)
8. Ficar (se melhorou) ou reverter (se piorou)
9. Repetir
```

**Regra de ouro**: mude **uma coisa por vez**. Se mudar prompt + modelo + tool ao mesmo tempo, você não sabe o que ajudou.

## Caching — economize tokens

DeepEval tem cache built-in. Se você roda os mesmos test cases várias vezes (porque tá iterando no agent, não na métrica), o cache pode poupar tokens de avaliação. Verifique a documentação de cache se rodar custosamente.

## Lidando com falhas no LLM judge

Se o judge LLM falhar (rate limit, timeout):

- DeepEval faz retry automático (1 vez por default)
- Pode ajustar via env vars: `DEEPEVAL_RETRY_MAX_ATTEMPTS`, etc
- Se o erro for `insufficient_quota` (OpenAI), não retry — você precisa adicionar créditos

Erro comum:
```
Evaluations getting "stuck"?
```
→ Geralmente é rate limit. Reduza paralelismo ou troque pra modelo mais barato.

## Hipóteses comuns que valem testar

Quando os resultados forem ruins, essas hipóteses são as primeiras a testar:

1. **System prompt ruim** — refazer com mais clareza, mais exemplos, mais estrutura
2. **Modelo subdimensionado** — gpt-3.5 → gpt-4o, claude-haiku → claude-sonnet
3. **Temperature alto demais** — baixar pra 0.1-0.3 pra agents
4. **Tool descriptions vagas** — reescrever cada description pensando "se eu fosse o LLM, eu saberia quando chamar isso?"
5. **Schemas de tool fracos** — adicionar `enum`, `required`, exemplos
6. **Loop sem break condition** — agent fica em loop até max_iterations
7. **Sem error handling** — tool falha, agent não sabe lidar
8. **Sem clarification step** — agent assume em vez de perguntar

## Roteiro com o usuário

1. **Verificar pré-requisitos** (instrumentação, dataset, métricas)
2. **Montar o script de execução** (forma 1 = `evals_iterator`)
3. **Rodar a primeira vez** — ver output no terminal
4. **Ler junto com o usuário** — passar pelo relatório, métrica por métrica
5. **Diagnóstico** — usar a árvore acima pra identificar o pior padrão
6. **Hipotetizar UMA mudança** — qual prompt/config/tool mudar
7. **Apoiar a iteração** — ele aplica, re-roda, vocês comparam

## Encerramento

Após rodar e analisar, dependendo do resultado:

**Se está pronto pra produção**:
> "Resultados ótimos! Próximo passo é levar isso pra produção com monitoring contínuo. Quer que eu chame `bagual-ai-evals-production`?"

**Se precisa iterar**:
> "Vou sugerir uma mudança baseada no diagnóstico: {hipótese}. Aplica e re-rodamos. Quando re-rodar, me chama de novo aqui pra analisarmos a comparação."

**Se precisa custom metric**:
> "Pelo que vimos, existe um critério não coberto pelas métricas built-in: {coisa}. Pra avaliar isso, vamos criar um GEval custom. Quer que eu chame `bagual-ai-evals-custom-metric`?"

## Anti-patterns

- ❌ Rodar e não olhar os resultados — eval sem análise é desperdício
- ❌ Mudar várias coisas ao mesmo tempo — não consegue isolar causa
- ❌ Mexer na métrica em vez do agent — tá medindo errado vs. agent ruim
- ❌ Ignorar `include_reason` — é onde tá a riqueza do diagnóstico
- ❌ Rodar 1000 goldens antes da primeira análise — small batch primeiro
- ❌ Aceitar score 0.7 como "bom o suficiente" sem questionar o threshold escolhido
