---
name: bagual-ai-evals-production
description: Migração de DeepEval para produção com Confident AI, evals assíncronos, monitoring contínuo e CI/CD com pytest. Use quando o usuário disser "deepeval em produção", "metric collection", "monitoring", "ci/cd evals", "regression testing", "async evals" ou similar.
---

# DeepEval Production — Levando Evals pra Produção

Você é o engenheiro de produção. Tem três trabalhos:

1. **Migrar evals de dev pra prod** com `metric_collection` no Confident AI (zero latência)
2. **Configurar CI/CD** com `deepeval test run` em pytest
3. **Estabelecer monitoring contínuo** que avisa quando o agent regride

## Pré-requisito crítico

O usuário **precisa** ter conta no Confident AI pra production evals. Sem isso, não tem como rodar evals async sem inflar a latência do agent. Confirme:

```bash
deepeval login
```

Se não tem, pause aqui e mande logar antes de continuar. É grátis pra começar.

## Por que produção é diferente de dev

Em dev, você roda evals síncronas: o agent espera o eval terminar pra responder. Isso é OK em testes locais. Em produção, **não dá**:

- Eval síncrona = latência adicionada (LLM-as-judge é lento)
- Eval bloqueante = falha do judge derruba o agent
- Inicialização local de métrica = overhead

A solução do DeepEval: **exportar traces pro Confident AI**, que avalia tudo **assíncrono** lá. O agent não espera. Ele só faz `@observe` normal e os traces saem via OpenTelemetry-like protocol.

## Conceito central: `metric_collection`

Em dev você passa `metrics=[...]` direto no `@observe`. Em produção, você cria uma **metric collection** no Confident AI (uma coleção nomeada de métricas), e referencia pelo nome:

```python
# Dev (síncrono)
@observe(type="agent", metrics=[task_completion, step_efficiency])
def my_agent(input):
    ...

# Produção (assíncrono)
@observe(type="agent", metric_collection="agent-task-completion-metrics")
def my_agent(input):
    ...
```

Você pode ter as duas coexistindo no mesmo código, controladas por variável de ambiente:

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

## Passo 1 — Criar metric collection no Confident AI

No dashboard do Confident AI:

1. Login em `app.confident-ai.com`
2. Navega pra "Metrics" no menu lateral
3. "Create Collection"
4. Nome (ex: `agent-task-completion-metrics`)
5. Adiciona as métricas que quer rodar (TaskCompletion, StepEfficiency, etc)
6. Configura threshold de cada uma
7. Save

A coleção fica disponível pra qualquer agent referenciar pelo nome.

### Onde anexar metric_collection

Igual em dev — o escopo dita onde anexar:

| Escopo | Onde anexar |
|--------|-------------|
| End-to-end (TaskCompletion, StepEfficiency, PlanQuality, PlanAdherence) | `@observe(type="agent", metric_collection="...")` |
| Component-level (ToolCorrectness, ArgumentCorrectness) | `@observe(type="llm", metric_collection="...")` |

Os dois podem coexistir na mesma trace:

```python
# Component-level — avalia decisões de tool calling em cada step LLM
@observe(type="llm", metric_collection="tool-correctness-metrics")
def call_llm(messages):
    ...

# End-to-end — avalia trajetória inteira após task completar
@observe(type="agent", metric_collection="agent-task-completion-metrics")
def travel_agent(user_input):
    ...
```

Isso é importante porque um agent pode escolher tool errada no passo 3, recuperar no passo 5, e ainda completar a task — sem o component-level, você não pegaria a falha intermediária.

## Passo 2 — Tags e metadata

Pra organizar runs em produção, use `update_current_trace`:

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
    # ... lógica do agent
```

No dashboard você pode filtrar/agrupar traces por tags e metadata. Útil pra:

- Comparar `v3.0` vs `v3.1`
- Detectar regressão depois de deploy
- Isolar falhas por região / segmento de user

## Passo 3 — Validar exportação

Antes de declarar produção pronta, faça uma chamada de teste e confirme que aparece no dashboard:

1. Roda o agent localmente com o env var de produção setado
2. Vai em `app.confident-ai.com` → "Observability" → "Traces"
3. Confirma que a trace apareceu (pode demorar alguns segundos)
4. Click na trace pra ver a árvore de spans
5. Confirma que as métricas rodaram (aparece `Pending` → depois score)

## Three-Mode Architecture pra spans em produção

Confident AI distingue três tipos de evals em produção:

### 1. Trace evals (end-to-end)

Avaliam um trace inteiro do começo ao fim. Tipo:

- Task completou?
- O usuário ficou satisfeito?
- Foi eficiente?

Anexa na agent span via `metric_collection`.

### 2. Span evals (component-level)

Avaliam um componente específico isoladamente. Tipo:

- Esse step de LLM escolheu a tool certa?
- Esse retrieval recuperou contexto relevante?

Anexa na LLM/retriever span via `metric_collection`.

### 3. Thread evals (multi-turn / conversation)

Avaliam uma conversa inteira (várias traces da mesma sessão). Tipo:

- A conversa toda teve coesão?
- O agent aprendeu durante a conversa?
- O usuário ficou satisfeito no fim?

Configurado via `thread_id` na trace e usa métricas multi-turn.

## ⚠️ A Three-Tier Eval Gate Strategy (recomendada)

Antes de mergulhar em production setup, ensine essa arquitetura ao usuário. É a estrutura recomendada pra balancear **custo, frequência, e cobertura**.

```
┌──────────────────────────────────────────────────────────────────┐
│ TIER 1 — Toda commit          < 10s    Zero LLM    Bloqueia     │
│ Schema validation, regex guards, format constraints              │
│ Custom DeepEval JsonCorrectnessMetric, regex assertions          │
│ Catch: format failures, PII leakage óbvios, prompt fragments    │
├──────────────────────────────────────────────────────────────────┤
│ TIER 2 — Toda PR              2-5min    < $2/run   Flag-not-block│
│ 100-200 test cases, mix de assertions + LLM judges               │
│ Faithfulness, tool correctness, custom GEval product-specific    │
│ Use gpt-4o-mini ou Selene Mini como judge                        │
│ Catch: quality regressions em workflows core                     │
├──────────────────────────────────────────────────────────────────┤
│ TIER 3 — Nightly              Horas     Maior      Ship-blocker  │
│ Full benchmark, pass^k (k≥4), multi-turn coherence completo      │
│ End-to-end task completion sobre 50+ tasks                       │
│ Use gpt-4o ou Claude pra calibração                              │
│ Catch: drift, regressão sutil, reliability issues                │
└──────────────────────────────────────────────────────────────────┘
```

**Gates de comportamento**:
- **Tier 1 falhou** → bloqueia commit/CI imediatamente
- **Tier 2 regrediu** > 5 pontos week-over-week → flagga, humano review da PR
- **Tier 3 caiu** > 10 pontos em pass^k → ship-blocker pro próximo release

**Por que três tiers**: cada um resolve um problema diferente. Tier 1 catch falhas óbvias **a custo zero**. Tier 2 catch quality regressions a custo controlado por PR. Tier 3 catch reliability issues que só aparecem em volume — e que custariam absurdo rodar a cada commit.

A **maioria dos times tem só Tier 3** (manual, esporádico, "deixa eu rodar evals semana que vem") e nunca consegue ship com confiança porque o feedback loop é longo demais. Outros têm só Tier 1 e acham que tão "fazendo evals" porque tem assertion no CI — mas as assertions só pegam falhas óbvias. Three-tier resolve os dois.

## Cost-per-resolution: a métrica de eficiência que importa

Aggregate token cost é vanity metric. **Cost-per-resolution** é o que importa em produção — leva em conta que algumas interações exigem mais turns, mais tool calls e mais retrieval pra alcançar o mesmo outcome.

```python
from dataclasses import dataclass
from typing import Optional

@dataclass
class SessionCostMetrics:
    session_id: str
    total_input_tokens: int
    total_output_tokens: int
    tool_calls_count: int
    resolved: bool  # do downstream system state ou human review
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

**Track weekly. Alerta se aumentar >15% sem melhora correspondente em resolution rate** — esse é o signal que algo regrediu numa prompt change ou retrieval config.

Times que **não** instrumentam isso descobrem quando um retrieval bug dobrou o tamanho do context window via cost tracking. Times que **não** medem resolution rate separadamente de interaction completion miss que o agent tá "completando" conversas (chegando a uma conclusão) sem realmente **resolver** o problema do user.

## Judge drift monitoring

Em produção, judges driftam silenciosamente. Não deixe a calibração vencer.

**Cadência mínima**: a cada 2 semanas:

1. Sample estratificado: 10 traces marcados PASS pelo judge, 10 marcados FAIL
2. Você (ou domain expert) labeia manualmente
3. Recalcula TPR e TNR
4. Track tendências rolling 7-day e 30-day, não single sessions

**Triggers de recalibração**:
- TPR < 0.75 → judge missing failures reais
- TNR < 0.75 → judge gerando ruído / false positives
- Cohen's κ < 0.7 → agreement com humanos rachou

**Não confie em aggregate agreement**. Um judge que chama tudo de PASS tem 70% agreement se 70% das traces realmente são PASS — mas TNR é 0. Track os dois lados.

## CI/CD — Regression testing com `deepeval test run`

CI/CD é o segundo pilar de produção. A ideia: cada PR roda evals contra um dataset de regressão e bloqueia merge se algo regrediu.

### Estrutura do test file

```python
# tests/test_agent_evals.py
import pytest
from deepeval import assert_test
from deepeval.dataset import EvaluationDataset
from deepeval.test_case import LLMTestCase
from deepeval.metrics import TaskCompletionMetric, ToolCorrectnessMetric

# Carrega dataset (pull do Confident AI ou load local)
dataset = EvaluationDataset()
dataset.pull(alias="regression-dataset-v1")

# Gera test cases rodando o agent
for golden in dataset.goldens:
    test_case = LLMTestCase(
        input=golden.input,
        actual_output=your_agent(golden.input),
    )
    dataset.add_test_case(test_case)

# Pytest parameteriza sobre os test cases
@pytest.mark.parametrize("test_case", dataset.test_cases)
def test_agent(test_case: LLMTestCase):
    metric = TaskCompletionMetric(threshold=0.8)
    assert_test(test_case=test_case, metrics=[metric])
```

### Rodar localmente

```bash
deepeval test run tests/test_agent_evals.py
```

### Rodar em GitHub Actions

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

Se algum eval falhar, exit code é não-zero → PR fica bloqueado.

### Comparar runs visualmente (regression testing)

Após o segundo run (e qualquer um depois), Confident AI gera **relatório de regressão** automaticamente:

- Linhas verdes: test case melhorou
- Linhas vermelhas: test case regrediu
- Linhas neutras: sem mudança

Você acessa pelo dashboard → "Test Runs" → "Compare".

Pra acessar via CLI:

```bash
deepeval view
```

### Strict mode pra blocking gates

Se um eval **deve** ser bloqueante, use strict mode:

```python
metric = TaskCompletionMetric(threshold=0.8, strict_mode=True)
```

Strict mode força score binário (0 ou 1), e como threshold é 1, qualquer "imperfeição" falha. Útil pra gates absolutos (ex: PII leakage = NUNCA).

## Monitoring contínuo

Após produção rolando, você quer monitorar:

| O que monitorar | Como |
|-----------------|------|
| Score médio das métricas ao longo do tempo | Dashboard "Performance Trends" |
| Quedas súbitas | Alertas configurados no Confident AI |
| Regressões depois de deploy | Compare runs antes/depois |
| Outliers (test cases muito ruins) | Filtra por score < threshold |
| Tool selection patterns | Aggregate de `tools_called` |
| Latência (não é métrica DeepEval, mas é importante) | Plot de duração das traces |

### Alertas

Confident AI permite configurar alertas tipo:

- "Avise se TaskCompletion médio cair abaixo de 0.7 por mais de 1h"
- "Avise se ToolCorrectness regredir mais de 10% em 24h"
- "Avise se PII leakage > 0 em qualquer trace"

## Async export — como funciona por baixo

Quando você usa `metric_collection`, DeepEval:

1. Captura a trace localmente (memory)
2. Exporta via OpenTelemetry-like protocol pro Confident AI (background thread, não bloqueia)
3. Confident AI recebe a trace
4. Roda as métricas da metric collection associada (async, no servidor)
5. Salva resultados no dashboard

**Latência adicionada ao agent: zero.** O export é fire-and-forget.

## Custos em produção

Cada trace que entra no Confident AI roda as métricas via LLM judge. Isso é tokens. Pense em:

- Quantas requests por dia → quantas traces por dia
- Quantas métricas por collection → quantas chamadas de judge
- Modelo do judge (gpt-4o > claude-haiku em precisão mas mais caro)

Estratégias de redução:

1. **Sample**: avalie só uma % das traces (não todas)
2. **Filter**: avalie só traces que matcham certo critério
3. **Modelo barato**: use claude-haiku ou gpt-4o-mini como judge
4. **Métricas leves**: use só 2-3 metrics, não todas

Confident AI oferece controle de sampling e filtering nas configurações da metric collection.

## Versionamento de prompts e modelos

Conforme você itera, vai querer rastrear:

- Qual versão do prompt foi usada
- Qual modelo foi usado
- Qual versão do agent (semver)

Use `tags` e `metadata` na trace pra isso. E mantenha um changelog dos prompts.

DeepEval também tem suporte a [`Prompt`](https://deepeval.com/docs/evaluation-prompts) pra versionamento — vale a pena conhecer se vai mexer muito em prompts.

## Roteiro com o usuário

1. **Verificar Confident AI login** — sem isso, pause
2. **Criar metric collection** — junto com o usuário no dashboard
3. **Atualizar `@observe`** — trocar `metrics=[]` por `metric_collection=""`
4. **Smoke test** — rodar uma chamada e confirmar que aparece no dashboard
5. **Adicionar tags/metadata** — pra organizar
6. **Configurar CI/CD** — montar test file + workflow
7. **Configurar alertas** — quais regressões devem avisar
8. **Definir cadência de revisão** — semanal? por sprint? por deploy?

## Checklist pra "produção pronta"

- [ ] `deepeval login` feito, API key configurada
- [ ] Metric collections criadas no Confident AI
- [ ] `@observe` usa `metric_collection` (não `metrics=[]`)
- [ ] Tags e metadata sendo populados via `update_current_trace`
- [ ] Smoke test em ambiente de prod aparece no dashboard
- [ ] CI/CD com `deepeval test run` em PRs
- [ ] Dataset de regressão versionado (preferencialmente no Confident AI)
- [ ] Alertas configurados pras métricas críticas
- [ ] Sampling/filtering configurado se volume é alto (custo)
- [ ] Documentação interna do que cada métrica significa
- [ ] Cadência de revisão de resultados definida

## Encerramento

Após production setup completo, diga:

> "Produção configurada. A partir de agora, toda chamada do seu agent é capturada no Confident AI e avaliada async. Pra ver o estado em qualquer momento: rode `deepeval view` ou abra o dashboard. Se quiser revisitar qualquer parte (regression testing, alertas, custom metrics), me chama. O ciclo de evals nunca termina — você itera pra sempre."

## Anti-patterns

- ❌ Usar `metrics=[]` em código de produção — adiciona latência
- ❌ Não criar dataset de regressão — sem ele, CI/CD não tem como testar
- ❌ Avaliar 100% das traces sem sampling em produção de alto volume — custo absurdo
- ❌ Esquecer de configurar alertas — você só descobre regressão quando o cliente reclama
- ❌ Deploy sem rodar test suite — defeats the purpose of CI/CD
- ❌ Mudar prompt/modelo sem atualizar tag de versão — perde rastreabilidade
- ❌ Ignorar o dashboard depois de configurar — dashboard sem revisão é só decoração
