---
name: deepeval-pick-metrics
description: Seleção das métricas DeepEval certas para o tipo de agent e objetivos. Use quando o usuário disser "qual métrica usar", "escolher métricas", "que métricas pra meu agent", "tool correctness", "task completion", "métricas de planning" ou similar.
---

# DeepEval Pick Metrics — Escolhendo as Métricas Certas

Você é o consultor de métricas. Seu trabalho: ajudar o usuário a escolher o conjunto **mínimo necessário** de métricas pro caso dele, e configurar elas com `threshold` e escopo (end-to-end vs component-level) corretos.

## ⚠️ Leia antes: métricas built-in não substituem judges product-specific

Antes de escolher métricas built-in, confirme com o usuário: **as 6 métricas built-in do DeepEval são "genéricas" por design**. Elas cobrem os layers (reasoning/action/execution) de um jeito que funciona pra qualquer agent, mas **elas não substituem evals product-specific** derivadas de trace review.

A recomendação ideal é **combinar os dois**:

| Camada de eval | Como construir | O que pega |
|----------------|----------------|------------|
| **Built-in (essa skill)** | Escolha das 6 métricas — TaskCompletion, ToolCorrectness, etc | Falhas estruturais genéricas (não completou, tool errada, ineficiente) |
| **Product-specific judges** | `deepeval-error-analysis` → open coding → binary judges | Falhas específicas do SEU produto (Context Amnesia, Policy Retrieval Mismatch, etc) |

Se o usuário ainda não fez trace review e tem agent rodando, **sugira fortemente** que ele faça `deepeval-error-analysis` **antes** de fechar a lista de métricas. Os judges product-specific geralmente pegam falhas que as built-in missam — e vice-versa.

**Se o usuário tá em smoke test mode** (primeira rodada de evals pra validar pipeline), pode usar só as built-in. Escale pra product-specific na segunda iteração.

## Princípio fundamental

**Não use todas as métricas.** Cada métrica custa tokens (LLM-as-judge), adiciona latência, e gera ruído nos resultados. Use só o que faz sentido pro modo de falha que você quer pegar.

## ⚠️ Mental models críticos antes de escolher métricas

Esses três insights vêm da literatura recente (τ-bench NeurIPS 2024, BFCL V4 Agentic 2025) e do Hamel Husain workshop. **Ensine isso ao usuário antes de recomendar métricas** — vai mudar o que ele pede.

### 1. Single-run completion rate é uma vanity metric — use pass^k

τ-bench publicou um resultado em NeurIPS 2024 que reframou como o campo pensa em eval de agentes:

GPT-4o achieved **pass^1 ≈ 50%** em retail customer service tasks. Razoável, embora decepcionante. Aí mediram **pass^8** — a probabilidade do agent ter sucesso em **todos os 8 trials independentes** da mesma task — e o número colapsou pra **menos de 25%**.

Esse colapso é o ponto. Um sistema com 50% de sucesso por run **não é** um sistema que funciona metade do tempo. É um sistema que, em qualquer semana de tráfego de produção, vai falhar com o mesmo cliente em tentativas repetidas a uma taxa compounding. Se seu support agent resolve return request com 50% reliability por run, e um cliente frustrado tenta 3 vezes, a probabilidade dele **nunca** conseguir resolver é 12.5%. Isso não é artefato de benchmark — é um SLA de produção que sua metodologia de eval estava escondendo de você.

**Implicação prática**: rode seus golden tasks **k vezes** (k≥4, idealmente k=8) e meça pass^k. O gap entre pass^1 e pass^k te diz sobre **variância** — gap grande significa agente inconsistente, não só imperfeito.

```python
import numpy as np
from collections import defaultdict

def compute_pass_k(results: list[dict], k: int = 8) -> dict:
    """
    results: lista de dicts com 'task_id' e 'success' (bool)
    """
    task_runs = defaultdict(list)
    for r in results:
        task_runs[r["task_id"]].append(r["success"])
    
    pass_k_per_task = {}
    for task_id, runs in task_runs.items():
        if len(runs) < k:
            continue
        # Sample k runs sem replacement, repete pra reduzir variância
        trials = [all(np.random.choice(runs, k, replace=False)) for _ in range(200)]
        pass_k_per_task[task_id] = np.mean(trials)
    
    aggregate = np.mean(list(pass_k_per_task.values()))
    return {"per_task": pass_k_per_task, "aggregate": aggregate, "k": k}
```

**Targets recomendados** pra customer support agent:
- `pass^1 ≥ 0.75` pra tasks transacionais
- `pass^4 ≥ 0.60` pra multi-turn complexas (3+ tool calls)
- `pass^8 ≥ 0.40` como floor de reliability agregado

Ship-blocker se abaixo disso em staging.

### 2. Faithfulness ≠ Factual Correctness

São **modos de falha diferentes** com **fixes diferentes**. Conflar produz evals que não pegam nenhum dos dois confiavelmente.

| | Faithfulness | Factual Correctness |
|---|--------------|---------------------|
| **Mede** | Claims do output suportadas pelo retrieved context? | Claims do output corretas em relação ao mundo real? |
| **Ground truth** | O contexto retrievado | A realidade (ou reference annotation) |
| **Falha exemplo** | Doc diz "refund em 5 dias", agent diz "7 dias" | Doc diz "refund em 7 dias" mas a política mudou pra 3 e a KB tá stale |
| **Fix** | Generator (prompt, modelo, position bias) | Knowledge base refresh, document staleness signals |

**História real do livro**: fintech lançou agent com faithfulness >0.85. Users reclamavam mesmo assim. O agent estava precisamente citando políticas retrievadas — score 1.0 nesses turns — mas a política era stale há 6 meses. Faithfulness perfeito + factual correctness zero.

**Implicação prática**: se você só tem faithfulness, você só pega errors de geração. Pra pegar errors de KB stale, ou você adiciona metadata de staleness aos chunks (creation_date, last_reviewed) e flagga, ou você mantém reference answers pras top scenarios e roda `RAGAS FactualCorrectness` (nota: RAGAS é um pacote separado — `pip install ragas` — não uma métrica built-in do DeepEval).

### 3. Database state > LLM judge quando possível

Pra agents com backend API access, **o signal mais confiável de completion não é judgment de LLM** — é **query no estado real do sistema** depois da conversa terminar. Mudou o status do ticket? Foi criada a row do refund? Isso é **deterministic, fast, e imune a variância de LLM judge**.

Onde você consegue instrumentar, **faça**. LLM-based completion metrics são pra casos onde system state é inacessível ou não suficientemente granular.

```python
# Em vez de:
task_completion = TaskCompletionMetric(threshold=0.7)

# Faça:
def db_state_check(test_case):
    """Checa estado real do DB pós-conversa"""
    ticket = db.tickets.find_one({"id": test_case.metadata["ticket_id"]})
    return ticket["status"] == "resolved"
```

Isso vira um custom non-LLM metric ou um assertion no Tier 1 do CI/CD.

### 4. Latência e custo são métricas first-class, não afterthoughts

BFCL V4 Agentic (julho/2025) reporta **custo em USD e latência em segundos junto com accuracy** pra cada modelo evaluado. Essa é a postura correta: pra agents em produção, um modelo 5% mais accurate mas 3x mais caro ou 2x mais lento pode ser a escolha errada dependendo da SLA e margem.

**Targets pra customer support agent**:
- Chat: P90 time-to-first-token <1.5s; P90 full response <3s
- Voice-adjacent (TTS feed): P90 <800ms pra primeira sentença

E mais importante que custo agregado: **cost-per-resolution**. Um modelo com 95% completion que consome 3x os tokens de um modelo com 90% pode não valer o premium se seu volume é alto.

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

Track essa weekly. Alerta se aumentar >15% sem melhoria correspondente em resolution rate — isso é signal que algo regrediu (retrieval bug dobrou context window, prompt change foi verboso demais, etc).

## τ-bench fault taxonomy — use pra diagnóstico

Em vez de "o agent falhou", classifique falhas nessa taxonomia (entity × failure type). Isso converte post-mortems em categorias acionáveis.

| Fault type | Descrição | Signal primário |
|------------|-----------|-----------------|
| `goal_partially_completed` | Agent resolveu parte da task mas missed subgoals | `ConversationCompletenessMetric < 1.0` |
| `used_wrong_tool` | Intent correto, tool errada | Trajectory mismatch |
| `used_wrong_tool_argument` | Tool correta, args malformados ou incorretos | Schema validation + argument audit |
| `took_unintended_action` | Agent fez algo que o user não pediu | Policy DAG violation |

**Por que isso importa**: se seus incident logs mostram 80% `used_wrong_tool_argument` depois de uma schema change, o fix é **schema documentation no system prompt**, não prompt rewriting. Se você tá vendo spikes de `took_unintended_action`, você tem policy enforcement problem que `ConversationalDAGMetric` deveria estar pegando em CI antes de chegar em produção.

## As 6 métricas built-in pra agents

### Reasoning Layer

#### `PlanQualityMetric`

**O que avalia**: se o **plano** que o agent gerou é lógico, completo e eficiente pra cumprir a tarefa.

**Quando usar**: quando seu agent tem fase de planejamento explícita (chain-of-thought, `Plan: 1) X, 2) Y`, ou similar). Se o agent não cria plano explícito, o metric passa com score 1 por default.

**Como é calculado**:
```
Plan Quality Score = AlignmentScore(Task, Plan)
```
Extrai task e plan da trace, usa LLM judge pra pontuar alinhamento.

**Escopo**: end-to-end (analisa a trace inteira)

**Código**:
```python
from deepeval.metrics import PlanQualityMetric

plan_quality = PlanQualityMetric(
    threshold=0.7,
    model="gpt-4o",  # opcional, qualquer LLM
    include_reason=True,  # mostra a justificativa do score
    strict_mode=False,    # se True, score é binário (0 ou 1)
)
```

#### `PlanAdherenceMetric`

**O que avalia**: se o agent **seguiu o próprio plano** durante execução, ou desviou.

**Quando usar**: pareada com `PlanQualityMetric`. Plano ótimo ignorado é tão ruim quanto plano ruim seguido perfeitamente.

**Como é calculado**:
```
Plan Adherence Score = AlignmentScore((Task, Plan), Execution Steps)
```

**Escopo**: end-to-end

**Código**:
```python
from deepeval.metrics import PlanAdherenceMetric

plan_adherence = PlanAdherenceMetric(threshold=0.7, model="gpt-4o")
```

### Action Layer

#### `ToolCorrectnessMetric`

**O que avalia**: se o agent **selecionou as tools certas** e as chamou da maneira esperada, comparando com lista de `expected_tools`.

**Quando usar**: quando você tem expectativas determinísticas sobre quais tools devem ser chamadas. Esse é um dos metrics mais importantes pra agents.

**Como é calculado**:
```
Tool Correctness = (Number of Correctly Used Tools) / (Total Number of Tools Called)
```

**Escopo**: **component-level** (no LLM span, NÃO end-to-end)

**Modos de strictness configuráveis**:
- **Default**: só compara nomes das tools
- **Input parameter matching**: também exige args iguais
- **Output matching**: também exige outputs iguais
- **Ordering consideration**: força sequência exata
- **Exact matching**: `tools_called` precisa ser idêntico ao `expected_tools`

**Código**:
```python
from deepeval.metrics import ToolCorrectnessMetric
from deepeval.test_case import LLMTestCaseParams

tool_correctness = ToolCorrectnessMetric(
    threshold=0.7,
    # Pode adicionar mais params via evaluation_params se quiser strictness
)
```

**Importante**: precisa do `expected_tools` no Golden e o `update_current_span(expected_tools=...)` no LLM span. Sem isso, não funciona.

**Atenção**: quando `available_tools` é fornecido no agent span, o metric também usa LLM pra avaliar se a seleção foi ótima dentre todas as opções. Score final = `min(deterministic_score, llm_score)`.

#### `ArgumentCorrectnessMetric`

**O que avalia**: se o agent gerou os **argumentos corretos** pras tool calls, baseado no input e contexto.

**Quando usar**: sempre que `ToolCorrectnessMetric` é usado. Tool certa com args errados é tão ruim quanto tool errada.

**Como é calculado**:
```
Argument Correctness = (Number of Correctly Generated Input Parameters) / (Total Number of Tool Calls)
```

Diferente do `ToolCorrectnessMetric`, esse é **totalmente LLM-based** e **referenceless** — avalia baseado no contexto do input, não comparando com valores predefinidos.

**Escopo**: component-level (LLM span)

**Código**:
```python
from deepeval.metrics import ArgumentCorrectnessMetric

argument_correctness = ArgumentCorrectnessMetric(
    threshold=0.7,
    model="gpt-4o",
)
```

### Execution Layer

#### `TaskCompletionMetric`

**O que avalia**: se o agent **realmente cumpriu a tarefa pedida**. Esse é o métrica de "sucesso final".

**Quando usar**: praticamente sempre. É o indicador top-level de qualquer agent.

**Como é calculado**:
```
Task Completion Score = AlignmentScore(Task, Outcome)
```

A task pode ser auto-inferida do trace ou passada explicitamente.

**Escopo**: end-to-end (analisa trace inteira)

**Código**:
```python
from deepeval.metrics import TaskCompletionMetric

task_completion = TaskCompletionMetric(threshold=0.7, model="gpt-4o")
```

**IMPORTANTE**: é **trace-only**. NÃO pode ser usada standalone — só dentro de `evals_iterator` ou `@observe` decorator.

#### `StepEfficiencyMetric`

**O que avalia**: se o agent completou a tarefa **sem passos desnecessários**. Penaliza tool calls redundantes, loops, ações fora do escopo.

**Quando usar**: sempre que custo/latência importam (basicamente, sempre em produção).

**Como é calculado**:
```
Step Efficiency Score = AlignmentScore(Task, Execution Steps)
```

**Escopo**: end-to-end

**Código**:
```python
from deepeval.metrics import StepEfficiencyMetric

step_efficiency = StepEfficiencyMetric(threshold=0.7, model="gpt-4o")
```

**IMPORTANTE**: também é **trace-only**.

**Combinação típica**: `TaskCompletionMetric` (alta) + `StepEfficiencyMetric` (baixa) = agent funciona mas precisa otimização.

## End-to-End vs Component-Level — DECISIVO

Esse é o ponto que mais confunde. Decore:

| Tipo de eval | Como passa as métricas | Quando usar |
|--------------|------------------------|-------------|
| **End-to-end** | `evals_iterator(metrics=[...])` ou `@observe(metrics=[...])` no agent span | Métricas que precisam ver a trace inteira (PlanQuality, PlanAdherence, TaskCompletion, StepEfficiency) |
| **Component-level** | `@observe(type="llm", metrics=[...])` no LLM span específico | Métricas que avaliam decisão isolada de um componente (ToolCorrectness, ArgumentCorrectness) |

**Os dois podem coexistir na mesma trace.** Um agent pode ter `ToolCorrectnessMetric` rodando no LLM span (catching wrong tool selections) e `TaskCompletionMetric` rodando no agent span (medindo se conseguiu a meta final). Isso é importante porque um agent pode escolher tool errada no passo 3, recuperar no passo 5, e ainda completar a task — sem component-level, você não pegaria a falha intermediária.

## Tabela de decisão — escolha do pacote

Use essa tabela com o usuário pra recomendar o conjunto certo:

| Situação | Pacote recomendado |
|----------|-------------------|
| Agent novo, primeira eval, quer simples | `TaskCompletionMetric` only (no agent span) |
| Agent com tools (caso comum) | `TaskCompletionMetric` (e2e) + `ToolCorrectnessMetric` + `ArgumentCorrectnessMetric` (LLM span) |
| Agent com planejamento explícito (CoT) | Adicione `PlanQualityMetric` + `PlanAdherenceMetric` |
| Agent em produção, custo importa | Adicione `StepEfficiencyMetric` |
| Tem requisito específico (tom, segurança, conformidade) | Adicione `GEval` custom (ver `deepeval-custom-metric`) |
| Multi-turn chatbot | Use as conversational metrics (`ConversationalGEval`, etc) — não esses |
| RAG | Use as RAG metrics (`AnswerRelevancyMetric`, `FaithfulnessMetric`, `ContextualPrecisionMetric`, `ContextualRecallMetric`, `ContextualRelevancyMetric`) |

### Pacote starter (default que você recomenda quando em dúvida)

```python
from deepeval.metrics import (
    TaskCompletionMetric,
    ToolCorrectnessMetric,
    ArgumentCorrectnessMetric,
)

# end-to-end
task_completion = TaskCompletionMetric(threshold=0.7)

# component-level (no LLM span)
tool_correctness = ToolCorrectnessMetric(threshold=0.7)
argument_correctness = ArgumentCorrectnessMetric(threshold=0.7)
```

E aplica:

```python
@observe(type="llm", metrics=[tool_correctness, argument_correctness])
def call_llm(messages):
    ...

@observe(type="agent", metrics=[task_completion])
def my_agent(user_input):
    ...
```

## Configurações comuns das métricas

Todas as métricas aceitam estes parâmetros:

| Parâmetro | O que faz |
|-----------|-----------|
| `threshold` | Score mínimo pra "passar" (default 0.5) |
| `model` | Qual LLM usa como judge (default `gpt-4.1`). Pode ser string ou instância de `DeepEvalBaseLLM` |
| `include_reason` | Inclui justificativa textual do score |
| `strict_mode` | Score binário 0/1 — força threshold pra 1 |
| `async_mode` | Concorrência interna no `measure()` (default True) |
| `verbose_mode` | Printa intermediários (debug) |

Exemplo com tudo:
```python
TaskCompletionMetric(
    threshold=0.8,
    model="claude-3-5-sonnet",  # ou instância custom
    include_reason=True,
    strict_mode=False,
    verbose_mode=True,
)
```

## Pergunta crítica: thresholds

Usuários sempre perguntam "qual threshold usar". Resposta honesta:

1. **Default 0.7** é um bom ponto de partida pra qualquer métrica
2. Rode pelo menos uma vez e veja **a distribuição real** dos scores
3. **Calibre** baseado no que você considera aceitável dado seu domínio
4. Pra **gates de produção**, você geralmente quer 0.8+ (e binário, com `strict_mode=True`)
5. Pra **monitoring** (sem bloquear), 0.6-0.7 funciona como alarme

## Roteiro com o usuário

1. **Pergunta**: "Qual o tipo do agent? Single-shot que executa task, multi-turn chat, ou RAG?"
2. **Pergunta**: "Tem fase de planejamento explícito (chain of thought)? Ou vai direto pra ação?"
3. **Pergunta**: "Quais são os 2-3 modos de falha mais críticos que você quer pegar?"
4. **Mapeamento**: pegue cada modo de falha e mapeie pra métrica
5. **Recomendação**: apresente o pacote mínimo + justifique cada métrica
6. **Configuração**: monte o código com thresholds default 0.7 (ou diferente se ele tiver opinião)
7. **Localização**: explique onde anexar (LLM span pra component-level, agent span pra end-to-end)

## Pergunta: "Por que não rodar todas as 6?"

Se o usuário insistir em rodar todas:

- **Custo**: cada métrica é uma chamada de LLM judge por golden. 6 métricas × 50 goldens = 300 chamadas extras.
- **Ruído**: você fica olhando pra 6 scores e não sabe qual mexer
- **Dependência redundante**: `TaskCompletionMetric` já cobre boa parte do que `PlanQualityMetric` cobre se não tem plano explícito
- **Sinal vs. ruído**: melhor 2 métricas que você confia do que 6 que te confundem

Mas se ele realmente quer todas, OK, você apoia. Só avise dos custos.

## Métricas além das 6 agentic — saiba que existem

DeepEval tem 50+ métricas. Algumas categorias:

| Categoria | Exemplos | Quando |
|-----------|----------|--------|
| **RAG** | `AnswerRelevancyMetric`, `FaithfulnessMetric`, `ContextualPrecisionMetric`, `ContextualRecallMetric`, `ContextualRelevancyMetric` | Pra RAG. Use o "RAG triad" (recall, precision, relevancy) |
| **Multi-turn** | `ConversationalGEval`, `TurnRelevancyMetric`, `RoleAdherenceMetric`, `ConversationCompletenessMetric`, `KnowledgeRetentionMetric` | Pra chatbots/copilots |
| **MCP** | `MCPUseMetric`, `MCPTaskCompletionMetric` | Pra agents que usam MCP servers |
| **Safety** | `BiasMetric`, `ToxicityMetric`, `PromptInjectionMetric` (via DeepTeam) | Verificações de safety |
| **Non-LLM** | `ExactMatchMetric`, `RegexMetric`, `JsonMatchingMetric` | Comparações determinísticas |
| **Custom** | `GEval`, `DAGMetric`, `ConversationalGEval`, `ConversationalDAG`, `ArenaGEval` | Critérios próprios |
| **Multimodal** | `ImageCoherenceMetric`, `TextToImageMetric` | Pra outputs multimodais |
| **Outras** | `SummarizationMetric`, `HallucinationMetric` | Casos específicos |

Se o usuário pedir uma métrica que não está nas 6 agentic, ofereça pesquisar mais detalhes ou crie uma custom com `GEval` (skill `deepeval-custom-metric`).

## Encerramento

Após escolher e configurar as métricas, diga:

> "Métricas escolhidas: {lista}. Próximo passo é rodar a primeira rodada de evals e analisar resultados. Quer que eu chame `deepeval-run-and-analyze`?"

Se ele quer custom:

> "Beleza, escolhemos {lista}. Você também mencionou que precisa avaliar {tom/segurança/conformidade}. Pra isso vamos criar uma métrica G-Eval custom. Quer que eu chame `deepeval-custom-metric`?"

## Anti-patterns

- ❌ Recomendar todas as 6 métricas — overkill, custo, ruído
- ❌ Esquecer de explicar end-to-end vs component-level — vai gerar bug de "métrica não roda"
- ❌ Default sem contexto — sempre pergunte os modos de falha primeiro
- ❌ Threshold sem justificativa — explique que é ponto de partida e calibra depois
- ❌ Misturar metric pra agent com metric pra RAG/multi-turn — são categorias separadas
