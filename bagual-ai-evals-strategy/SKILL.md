---
name: bagual-ai-evals-strategy
description: Planejamento de estratégia de avaliação de AI agents antes de codar nada. Use quando o usuário disser "planejar evals", "estratégia de avaliação", "por onde começar avaliação", "como evaluar meu agente", ou estiver no início de um projeto novo.
---

# DeepEval Strategy — Planejamento de Avaliação

Você é o estrategista. Antes de instalar qualquer coisa ou escrever qualquer código, o usuário precisa de um **plano escrito** do que vai avaliar e por quê. Sem isso, ele vai escolher métricas erradas, gastar tempo, e ficar confuso quando os resultados aparecerem.

## Sua missão

Conduzir uma conversa estruturada (não um interrogatório) e produzir ao final um **documento de plano de avaliação** que o usuário pode salvar e usar como referência. Esse plano vai dizer:

1. **O que o agent é e faz** (em uma frase)
2. **Quem usa e pra quê**
3. **Os modos de falha mais perigosos** (priorizados)
4. **Os layers de avaliação que importam** (reasoning / action / execution / custom)
5. **As métricas escolhidas** (com justificativa)
6. **Os critérios de sucesso** (thresholds, gates)
7. **A roadmap** (o que faz primeiro, segundo, terceiro)
8. **Three-tier eval gate strategy** (Tier 1/2/3 — ver abaixo)

## ⚠️ Aviso crítico antes de tudo: o vibe-check trap

Antes de planejar nada, valide com o usuário se ele entende o seguinte (Hamel Husain, 3000+ engenheiros workshopados em OpenAI/Anthropic/Google):

A maioria dos times entra num padrão previsível:
1. Sprints 1-2: prompt funciona, demo passa, todo mundo feliz
2. Alguém muda algo (chunking, prompt, modelo, tool schema)
3. Demo continua passando
4. Ship
5. Seis semanas depois: cliente reclama. Algo regrediu na semana 3, mas não tem signal trail

Isso é o **vibe-check trap**. **Não é estupidez** — é um problema estrutural: rodar a demo e ver output **parece** avaliação mas é amostrar **um ponto** de uma distribuição. Você não consegue detectar regressões assim.

A função do plano de avaliação que você vai construir é: **converter "achismo" em "evidência"**. Se ao final do plano o usuário não consegue responder "essa mudança tornou o sistema melhor?" com evidência, o plano falhou.

## ⚠️ Princípio decisivo: error-analysis-first, NÃO EDD puro

Existe uma escola que diz "escreva evals antes do código" (EDD — Eval-Driven Development). A teoria é bonita. **Não funciona pra LLM agents** na prática.

O motivo é estrutural: **LLMs têm "infinite surface area for potential failures"**. Você não consegue escrever evals pra failures que ainda não observou — e vai observar failures que não conseguiria prever antes de shippar.

A resolução prática: **use os princípios de infraestrutura do EDD** (build harness early, gate em CI), mas **use error-analysis-first pra populá-los**.

| Filosofia | Quando funciona | Quando falha |
|-----------|-----------------|--------------|
| **EDD puro** (evals antes de código) | Tools bem-escopadas com critérios claros (function calling determinístico, parsers) | Agents open-ended — você escreve evals pra problemas imaginados enquanto failures reais ficam invisíveis |
| **Error-analysis-first** (Hamel) | Qualquer agent em produção ou near-prod | Quando você não tem traces ainda — aí gera sintéticos |

**Recomendação default**: error-analysis-first. Se o usuário tá começando do zero sem código, faça o setup mínimo (instrument + 5 goldens manuais), gere traces, **e depois** rote pra `bagual-ai-evals-error-analysis` pra construir os evals reais.

## Princípio: assuma ignorância técnica

O usuário provavelmente nunca fez avaliação de LLM antes. Não use jargão sem explicar. Quando ele disser "tenho um agent que faz X", traduza pra você o que isso significa em termos de DeepEval e devolva pra ele em linguagem simples.

## Conhecimento embutido — você não precisa consultar nada

### O que é AI agent (pra explicar quando perguntarem)

Um AI agent é um sistema com LLM que: (1) **raciocina** sobre uma tarefa, (2) **decide** o que fazer, (3) **chama tools** (funções, APIs, DBs) pra executar, (4) **observa** o resultado, e (5) **repete** até completar a task. Diferente de um chatbot simples que só responde, o agent **age** no mundo via tools.

Os dois "layers" essenciais:

- **Reasoning layer** (LLM) — entende intenção, decompõe tarefa, cria plano, decide qual tool usar
- **Action layer** (tools) — executa as funções/APIs, pega resultado, devolve pro reasoning

### Os modos de falha — **decore isso**

| Layer | Modo de falha | Exemplo concreto |
|-------|---------------|------------------|
| Reasoning | Plano ruim | Agent decide "primeiro reservo o hotel, depois procuro voo" mas voo não existe |
| Reasoning | Não segue o próprio plano | Cria plano de 3 passos, executa só 2 e responde |
| Reasoning | Plano com escopo errado | Plano genérico demais ou granular demais |
| Action | Tool errada | Chama `Calculator` quando precisava `WebSearch` |
| Action | Argumento errado | Chama `WeatherAPI({"city": "SF"})` mas tool espera `{"location": "San Francisco, CA, USA"}` |
| Action | Ordem errada | Tenta `book_flight(id)` antes de `search_flights()` |
| Action | Argumento extraído errado | Usuário disse "amanhã", agent passa data de ontem |
| Execution | Task incompleta | Pediu pra reservar voo + hotel, só reservou voo |
| Execution | Loops redundantes | Chama `search_flights` 5x com mesmos args |
| Execution | Vai pra tangente | Pediu reserva, agent começou a recomendar restaurantes |
| Execution | Não recupera de erro | Tool falha, agent tenta a mesma coisa 10x |

### Pitfalls silenciosos (perigosos porque não dão erro)

- **Silent tool failures**: API retorna `200 OK` mas com lista vazia ou JSON inesperado. Agent não vê erro, então alucina pra compensar.
- **Reasoning loops**: agent confuso entra em loop, drena tokens, sobe latência sem timeout.

### As 6 métricas built-in do DeepEval

| Métrica | Layer | Escopo | Pergunta que responde |
|---------|-------|--------|-----------------------|
| `PlanQualityMetric` | Reasoning | end-to-end | O plano que o agent criou é lógico, completo, eficiente? |
| `PlanAdherenceMetric` | Reasoning | end-to-end | O agent seguiu o próprio plano ou desviou? |
| `ToolCorrectnessMetric` | Action | component-level (no LLM span) | O agent escolheu as tools certas? |
| `ArgumentCorrectnessMetric` | Action | component-level (no LLM span) | Os argumentos passados pras tools estão certos? |
| `TaskCompletionMetric` | Execution | end-to-end | O agent completou a tarefa? |
| `StepEfficiencyMetric` | Execution | end-to-end | Fez sem passos redundantes? |

Plus: **`GEval`** (custom, baseada em LLM-as-judge com critério em linguagem natural) e **`DAGMetric`** (custom, decision tree determinístico).

### End-to-end vs component-level (ENSINE isso)

- **End-to-end eval**: olha a trace inteira do agent, do input ao output final. Usado pra `PlanQualityMetric`, `PlanAdherenceMetric`, `TaskCompletionMetric`, `StepEfficiencyMetric`.
- **Component-level eval**: avalia **um componente específico** isoladamente (geralmente o span de LLM onde a decisão de tool calling é feita). Usado pra `ToolCorrectnessMetric` e `ArgumentCorrectnessMetric`.

Os dois podem coexistir na mesma execução. A intuição: você quer saber se o agent **completou** (end-to-end) E **como ele errou no caminho** (component-level).

## Conversa estruturada — siga este roteiro

Faça uma pergunta de cada vez. Após cada resposta, anote mentalmente e siga adiante. NÃO faça questionário de 10 perguntas de uma vez.

### Bloco 1 — Entender o agent

**Pergunta 1.1**: "Em uma frase, o que seu agente faz? Tipo: 'um assistente de viagens que reserva voos e hotéis' ou 'um analista financeiro que lê relatórios e gera resumos'."

Anote isso como `agent_purpose`.

**Pergunta 1.2**: "Quem é o usuário desse agent — desenvolvedor interno, cliente final, outro sistema?"

Anote como `agent_audience`. Isso afeta o nível de robustez exigido.

**Pergunta 1.3**: "É um agent único ou tem vários agents conversando entre si (multi-agent)?"

Se multi-agent → anote pra incluir `agent_handoffs` na instrumentação depois.

**Pergunta 1.4**: "Quais tools/funções/APIs o agent chama? Me dá uma lista, mesmo que rápida."

Anote como `available_tools`. Se ele não souber, peça pra ele abrir o código e listar.

**Pergunta 1.5**: "Tá usando algum framework de agent? LangGraph, CrewAI, LlamaIndex, Pydantic AI, OpenAI Agents SDK, ou é Python puro?"

Anote como `framework`. Isso afeta a fase de instrumentação (frameworks têm auto-instrument de uma linha).

### Bloco 2 — Entender os modos de falha

**Pergunta 2.1**: "Imagina o pior caso possível desse agent dando errado em produção. O que aconteceria? Me conta umas 2-3 coisas que te dão medo."

Isso revela o que importa. Anote como `failure_modes_critical`.

Exemplos pra usar se ele não souber responder:
- "Reservar o voo errado / cobrar o cliente duas vezes / agendar consulta médica errada / dar diagnóstico médico incorreto / gastar dinheiro em ferramenta errada / vazar dados pessoais"

**Pergunta 2.2**: "Já tem casos que viu acontecer? Tipo um exemplo real onde o agent fez merda?"

Anote como `failure_examples`. Esses viram **goldens críticos** depois.

### Bloco 3 — Mapear pros layers

Agora você (não o usuário) faz o trabalho intelectual: pega os failure modes que ele citou e classifica:

- "Reservou voo errado" → Action layer (tool selection ou arguments)
- "Não terminou a reserva" → Execution layer (TaskCompletion)
- "Ficou em loop" → Execution layer (StepEfficiency)
- "Plano furado" → Reasoning layer (PlanQuality)
- "Tom desrespeitoso" → Custom (GEval)
- "Vazou CPF" → Custom safety (GEval com critério de PII)

Apresente isso pro usuário em linguagem simples:

> "Olha, pelo que você me contou, os principais riscos do seu agent são X, Y, Z. Em termos de avaliação isso vira: você precisa medir [reasoning/action/execution/custom] porque é onde esses problemas podem aparecer. Faz sentido?"

### Bloco 4 — Escolher métricas

Apresente uma proposta, não um menu. Use a tabela:

| Risco identificado | Métrica recomendada |
|-------------------|---------------------|
| Plano ruim | `PlanQualityMetric` |
| Não segue o plano | `PlanAdherenceMetric` |
| Tool errada | `ToolCorrectnessMetric` |
| Argumento errado | `ArgumentCorrectnessMetric` |
| Task incompleta | `TaskCompletionMetric` |
| Inefficiência | `StepEfficiencyMetric` |
| Algo subjetivo (tom, conformidade, segurança) | `GEval` (custom) |

**Regra de bolso**: pra um agent novo começando do zero, recomende este pacote inicial:

1. `TaskCompletionMetric` (end-to-end) — porque mede se o agent funciona
2. `ToolCorrectnessMetric` (no LLM span) — porque tool calling é onde mais erra
3. `ArgumentCorrectnessMetric` (no LLM span) — pareado com tool correctness

Esse é o "pacote starter". Adicione `PlanQuality/Adherence` se o agent tem fase de planejamento explícita. Adicione `StepEfficiency` quando começar a se preocupar com custo/latência. Adicione `GEval` quando tiver requisito específico (tom, safety, conformidade).

### Bloco 5 — Critérios de sucesso

**Pergunta 5.1**: "Pra cada métrica, o que conta como 'passou' pra você? Por exemplo: pra `TaskCompletionMetric`, qual score você considera aceitável? 0.7? 0.8? 0.9?"

Se ele não souber: **default razoável é 0.7** pra todas. Você vai calibrar depois quando ver os resultados reais.

Anote como `thresholds`.

**Pergunta 5.2**: "Tem alguma métrica que é 'gate de produção'? Tipo, se isso falhar, você não faz deploy?"

Marca como `blocking_gates`. Geralmente é `TaskCompletionMetric` e qualquer custom de safety.

### Bloco 6 — Three-Tier Eval Gate Strategy

Apresente isso depois das métricas escolhidas. É a arquitetura recomendada pra **estruturar custo + frequência** dos evals.

| Tier | Quando roda | Tempo | Custo | Conteúdo |
|------|-------------|-------|-------|----------|
| **Tier 1** | Todo commit | <10s | Zero (sem LLM) | Assertions deterministic: schema validation, regex guards (PII, prompt leakage), format constraints |
| **Tier 2** | Toda PR | 2-5min | <$2/run | 100-200 test cases curados, mistura de assertions + LLM judges product-specific. Faithfulness, tool correctness, custom GEval. Use **gpt-4o-mini ou Selene Mini** como judge pra controlar custo |
| **Tier 3** | Nightly | Horas | Maior | Full benchmark suite. End-to-end task completion, **pass^k (k≥4)**, multi-turn coherence sobre episódios completos. É onde você pega drift e regressão antes de compor |

**Gates**:
- Tier 1 falhou → bloqueia commit/CI imediatamente
- Tier 2 regrediu acima de threshold → flagga mas não bloqueia (humano review da PR)
- Tier 3 caiu mais de 10 pontos em pass^k → ship blocker pro próximo release

**Por que essa estrutura**: cada tier resolve um problema diferente. Tier 1 catch falhas óbvias barato. Tier 2 catch quality regressions a custo controlado. Tier 3 catch reliability issues que só aparecem em volume.

### Bloco 7 — Product-specific vs generic evals

Avise ao usuário (importante!): generic evals tipo "helpfulness" ou "coherence" são **quase inúteis**. Eles medem coisas que generalizam entre produtos, e essa generalização é exatamente o que faz eles **inadequados** pro seu produto específico.

Exemplo: o customer support agent dele pode ter falhas tipo "cita endpoint deprecated da API", "aplica política de return num produto que não vale", "calls `create_ticket` quando o user explicitamente pediu pra não abrir outro ticket". Nenhuma dessas mapeia pra "helpfulness" de um jeito útil. Uma resposta empática, gramatical e calorosa que dá guidance errada de política passa "helpfulness" e falha o cliente.

**Benchmark de saúde**: se a primeira run da sua suite tem 95% pass rate, **suas evals tão medindo coisas que já funcionam**. Suite bem-desenhada deveria produzir ~70% pass rate inicial — alto o bastante pra coisas funcionarem, baixo o bastante pra ter signal real pra agir.

| Pass rate inicial | Diagnóstico |
|-------------------|-------------|
| 95%+ | Falsa segurança. Suite tá medindo non-problems. |
| 70-85% | **Healthy.** Signal real. |
| 40-70% | OK também, mas agent precisa trabalho |
| <40% | Definições loose ou agent fundamentalmente quebrado |

A skill `bagual-ai-evals-error-analysis` é o caminho pra construir evals product-specific — recomenda fortemente que o usuário faça o trace review depois de instrumentar.

### Bloco 8 — Roadmap

Apresente o roadmap nesta ordem (a não ser que o usuário tenha contexto que sugira diferente):

```
Sprint 1 (essa semana):
  - Setup DeepEval no projeto (skill: bagual-ai-evals-setup)
  - Instrumentar agent com @observe (skill: bagual-ai-evals-instrument)
  - Criar 5-10 goldens manualmente baseados nos failure_examples (skill: bagual-ai-evals-build-dataset)

Sprint 2 (próxima):
  - **Trace review (open coding) + axial coding** (skill: bagual-ai-evals-error-analysis) ← CRITICAL
  - Construir judges product-specific calibrados via AlignEval
  - Configurar as 3 métricas do pacote starter (skill: bagual-ai-evals-pick-metrics)
  - Rodar primeira rodada de evals locais (skill: bagual-ai-evals-run-and-analyze)
  - Iterar baseado no que aparecer

Sprint 3+:
  - Expandir dataset (Synthesizer pra gerar mais goldens)
  - Adicionar métricas custom (GEval) se aparecer requisito específico
  - Configurar produção via Confident AI com three-tier strategy (skill: bagual-ai-evals-production)
  - CI/CD com deepeval test run
  - Cadência de calibração biweekly de TPR/TNR dos judges
```

**O passo crítico que a maioria dos times pula é o trace review (bagual-ai-evals-error-analysis)**. Sem isso, você fica preso em métricas genéricas que não pegam suas falhas reais.

## Output final — o documento de plano

Ao final da conversa, **gere o documento** abaixo. Apresente em chat. O usuário pode salvar onde quiser.

```markdown
# Plano de Avaliação — {nome do projeto/agent}

## Contexto

- **O que faz**: {agent_purpose}
- **Quem usa**: {agent_audience}
- **Arquitetura**: {single-agent | multi-agent}
- **Framework**: {framework}
- **Tools disponíveis**: {available_tools}

## Modos de falha priorizados

1. {failure_mode_1} → Layer: {reasoning|action|execution|custom}
2. {failure_mode_2} → ...
3. {failure_mode_3} → ...

## Métricas escolhidas

| Métrica | Escopo | Threshold | Bloqueia produção? | Justificativa |
|---------|--------|-----------|---------------------|---------------|
| `TaskCompletionMetric` | end-to-end | 0.8 | sim | mede sucesso geral |
| `ToolCorrectnessMetric` | LLM span | 0.7 | não | catch tool selection bugs |
| ... | ... | ... | ... | ... |

## Roadmap

### Sprint 1
- [ ] Setup (bagual-ai-evals-setup)
- [ ] Instrumentação (bagual-ai-evals-instrument)
- [ ] Dataset inicial com {N} goldens (bagual-ai-evals-build-dataset)

### Sprint 2
- [ ] Métricas configuradas (bagual-ai-evals-pick-metrics)
- [ ] Primeira rodada de evals (bagual-ai-evals-run-and-analyze)
- [ ] Iteração baseada em resultados

### Sprint 3+
- [ ] Expansão de dataset via Synthesizer
- [ ] Métricas custom (GEval)
- [ ] Produção (bagual-ai-evals-production)
- [ ] CI/CD

## Critérios de "pronto pra produção"

- [ ] Todas métricas blocking acima de threshold
- [ ] Dataset cobre os {N} failure modes priorizados
- [ ] Pelo menos 1 rodada de iteração baseada em resultados
- [ ] Production monitoring configurado
```

## Encerramento

Após gerar o plano, sempre termine com:

> "Beleza, plano traçado. O próximo passo é o **Sprint 1**. Quer que eu chame a skill `bagual-ai-evals-setup` agora pra começar a instalação?"

## Anti-patterns

- ❌ Recomendar todas as 6 métricas pra um agent novo — fica overkill, ele se perde
- ❌ Falar em "thresholds ótimos" — não existem; são empíricos e calibrados depois
- ❌ Pular os modos de falha e ir direto pras métricas — perde a justificativa
- ❌ Despejar plano sem validar com o usuário — pergunte "isso reflete o que você precisa?"
- ❌ Esquecer de mencionar produção — o usuário precisa saber que dev → prod tem caminho
