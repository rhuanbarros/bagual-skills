---
name: deepeval-error-analysis
description: Workflow de error-analysis-first para descobrir falhas reais do agent via trace review (Hamel Husain). Use quando o usuário disser "não sei o que avaliar", "preciso descobrir falhas", "review de traces", "open coding", "axial coding", "trace-driven evals", "vibe check", "como criar evals do zero", ou tiver agent rodando mas sem evals estruturados.
---

# DeepEval Error Analysis — Trace Review e Workflow Trace-Driven

Você é o instrutor de error analysis. Esta é a skill mais importante do módulo, e a que mais difere da intuição de quem nunca fez avaliação de LLM.

## Por que essa skill existe — o vibe-check trap

A maioria dos times entra num padrão previsível:

1. Sprints 1-2: prompt funciona, demo passa, todo mundo feliz
2. Alguém muda alguma coisa (chunking, prompt, modelo, tool schema)
3. Demo continua passando
4. Ship
5. Seis semanas depois: cliente reclama. Algo regrediu na semana 3, mas não tem signal trail

Isso é o **vibe-check trap** que Hamel Husain descreve depois de rodar workshops com 3000+ engenheiros de OpenAI/Anthropic/Google. **Não é estupidez**. É um problema estrutural: o feedback loop de "mudou prompt → viu output" **parece** avaliação mas não é. É amostrar **um ponto** de uma distribuição e concluir que a distribuição inteira está OK.

A skill `deepeval-strategy` te ajuda a planejar O QUE avaliar. **Esta skill** te ajuda a **descobrir** o que avaliar — porque as falhas que você precisa pegar você ainda não conhece.

## Princípio fundamental: error-analysis-first, não EDD

Existe uma escola de pensamento chamada **EDD (Eval-Driven Development)** que diz: escreva evals **antes** do código, igual TDD. A teoria é bonita. A prática rachada.

O motivo é estrutural: **LLMs têm "infinite surface area for potential failures"**. Você não consegue escrever evals pra modos de falha que ainda não observou — e você vai observar modos de falha que não conseguiria prever antes de shippar algo real. Escrever uma suite de evals "completa" antes de ver traces de produção significa escrever evals pra problemas imaginários enquanto falhas reais ficam não medidas.

A resolução prática (Hamel): **use os princípios de infraestrutura do EDD** (build harness early, gate em CI), mas **use error-analysis-first pra populá-los**. Não escreva evals pro que você acha que pode falhar. Escreva evals pro que você **observa** falhando.

Isso muda **quando** no ciclo você faz cada coisa. E significa que **seus primeiros 100 traces valem mais que qualquer benchmark dataset que outra pessoa construiu**.

## Pré-requisito

Você precisa de **traces reais**. Pelo menos 30-50.

| Cenário | O que fazer |
|---------|-------------|
| Tem agent em produção | Exporta 50 traces da última semana via Confident AI / LangSmith / Langfuse / Braintrust |
| Tem agent em staging mas não prod | Roda 50 inputs sintéticos representativos da distribuição esperada |
| Não tem agent rodando ainda | **Pare aqui** — vai pra `deepeval-strategy` primeiro, instrumenta o agent (`deepeval-instrument`), gera traces, e volta |

**Sintéticos contam pra começar**. Se você sampleia da distribuição esperada de inputs reais, é legítimo. Não é desculpa pra não fazer error analysis — é só um substituto temporário.

## O Workflow de 4 Passos

Esse é o processo que converte traces brutos em sistema de evals funcionando. Não é glamoroso. Envolve muita planilha e Jupyter notebook. **Faça assim mesmo.**

```
┌─────────────────────────────────────────────┐
│  Passo 1 — OPEN CODING                       │
│  Lê 30-50 traces, escreve notas freeform     │
│  ~2 sessões de 30 minutos                    │
├─────────────────────────────────────────────┤
│  Passo 2 — AXIAL CODING                      │
│  LLM agrupa as notas em categorias de falha  │
│  Aim: 4-8 categorias produto-específicas     │
├─────────────────────────────────────────────┤
│  Passo 3 — BINARY LLM JUDGES                 │
│  Pra cada categoria: 2 frases pass/fail      │
│  Validar com 2º annotador antes de escalar   │
├─────────────────────────────────────────────┤
│  Passo 4 — CI DEPLOYMENT                     │
│  Integrar judges em CI + calibração ongoing  │
│  TPR/TNR tracking biweekly                   │
└─────────────────────────────────────────────┘
```

## Passo 1 — Open Coding

**Objetivo**: parar de relacionar com seu agent como abstração ("ele lida com perguntas de billing") e começar a relacionar como **distribuição de comportamentos reais**.

### Setup

Abra um Jupyter notebook (ou qualquer ferramenta de notas longas). **Não use ferramenta de evals ainda.** Não tente categorizar nada. Não use template.

```python
import json
from deepeval.tracing import trace_manager  # se já instrumentado com deepeval

# OU exporta de outras plataformas:
# - Confident AI: dataset.pull(alias="prod-traces")
# - Langfuse: langfuse.fetch_traces(...)
# - LangSmith: client.list_runs(...)
# - Braintrust: braintrust.fetch_dataset(...)

# Carrega 50 traces com tudo: input, output, retrieved_context, tool_calls
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

### Como ler

Pra cada trace, gaste **2-5 minutos**. Em duas sessões de 30 minutos você vê 30-50 traces.

Pra cada trace, escreva notas freeform respondendo:

- **O que é surpreendente aqui?**
- **O que parece errado?**
- **O que parece certo de um jeito que eu não esperava?**
- **Esse output é factualmente correto?** (compare com sua knowledge)
- **O agent fez algo que eu não pediria pra ele fazer?**
- **O agent deixou de fazer algo que eu esperaria?**

**Não tente categorizar.** Não tente ser conciso. Escreva como notas de campo de pesquisa. Os pesquisadores chamam isso de **open coding** — você está construindo intuição, não taxonomia ainda.

### Exemplos do tipo de notas que você quer

**Trace 7** (billing dispute):
> Pediu número da conta no turno 3, mas o user já tinha dado no turno 1. Resposta no turno 5 cita política de refund correta mas o valor (R$ 50) tá errado, deveria ser R$ 75. Mencionou processo de escalação mas depois tentou resolver mesmo assim, ficou meio incoerente.

**Trace 12** (feature question):
> User perguntou se o plano X tem cobertura internacional. Doc retornado diz que cobertura internacional é add-on de R$ 15/mês. Agent respondeu "sim, seu plano inclui cobertura internacional sem custo adicional". **HALLUCINATION CONFIANTE**. Score de relevância passou porque tava on-topic mas resposta tava errada.

**Trace 23** (return request):
> Tool call `get_order_status` foi chamado com `order_id="ABC-123"` mas o user disse `#ABC123` (sem hífen). Tool retornou erro mas agent não percebeu, continuou fazendo as próximas chamadas como se tivesse dado certo. Ended up dando confirmação fake.

Note como essas notas são **específicas**, não genéricas. "Hallucination" sozinho seria inútil. "Hallucination confiante sobre feature de cobertura internacional, contradizendo o doc retornado" é acionável.

### Quanto tempo leva

| Atividade | Tempo |
|-----------|-------|
| Setup do notebook | 30 min |
| Ler 30-50 traces e tomar notas | 1-2h em 2 sessões |
| Limpeza das notas | 30 min |
| **Total** | **3-4 horas** |

**Não pule.** Esse é o trabalho mais alto-ROI do ciclo inteiro de evals.

## Passo 2 — Axial Coding

**Objetivo**: clusterizar suas notas brutas em **categorias de falha mutuamente exclusivas** que sejam **produto-específicas**, não genéricas.

A diferença é crítica:

| Genérico (ruim) | Produto-específico (bom) |
|-----------------|--------------------------|
| "Quality issues" | "Agent applies wrong policy version when multiple versions exist" |
| "Hallucination" | "Agent confidently quotes pricing that contradicts retrieved doc" |
| "Tool error" | "Agent doesn't notice when tool returns 404, continues as if successful" |
| "Coherence problem" | "Agent re-asks for info already provided 3+ turns ago" |

Generic eval pra "factual accuracy" não distingue entre alucinar uma feature de produto e aplicar mal uma política de desconto — duas falhas com root causes e fixes completamente diferentes.

### Como fazer

Pega todas as notas do passo 1 (collated num único arquivo de texto) e usa um LLM pra clusterizar. Não use o LLM-as-judge — use Claude/GPT pra ajudar você a **pensar**, isso não é uma avaliação.

Prompt sugerido:

```
Aqui estão minhas notas de open coding sobre 47 traces de um customer support 
agent que faz tool calls contra uma API de billing e RAG sobre uma knowledge 
base de políticas:

[cola todas as notas aqui]

Agrupe essas observações em categorias de falha mutuamente exclusivas, 
seguindo essas regras:
- 4-8 categorias no total (não 20)
- Cada categoria deve ser PRODUTO-ESPECÍFICA, não genérica
- Cada categoria precisa de um nome preciso e uma descrição que distinga 
  ela de categorias adjacentes
- Categorias devem ser acionáveis: "qual fix vai resolver isso" deve ser 
  óbvio pelo nome
- Liste 2-3 traces de exemplo pra cada categoria (use os números das notas)

Devolva como markdown com categoria + descrição + exemplos.
```

### Output esperado

```markdown
## Categorias de Falha (8 total)

### 1. Context Amnesia
**Descrição**: Agent pede informação que já foi fornecida na conversa atual.
**Exemplos**: Trace 7, Trace 19, Trace 31

### 2. Policy Retrieval Mismatch
**Descrição**: Doc correto retrievado mas agent aplica versão errada da política,
ou aplica política que não vale pro tipo de produto do cliente.
**Exemplos**: Trace 12, Trace 28

### 3. Tool Argument Format Mismatch
**Descrição**: Tool é a correta, mas args estão em formato errado e tool retorna
erro silencioso. Agent não detecta o erro.
**Exemplos**: Trace 23, Trace 41

### 4. Escalation Abandonment
**Descrição**: Agent commits a fazer escalação pra humano mas depois tenta
resolver mesmo assim, gerando incoerência.
**Exemplos**: Trace 7, Trace 33

### 5. Confident Hallucination Over Retrieved Context
**Descrição**: Doc retornado contém informação correta, agent gera resposta
factualmente contrária ao doc com tom confiante.
**Exemplos**: Trace 12, Trace 39

### 6. Number/Amount Hallucination
**Descrição**: Agent cita valores numéricos (preços, prazos, contagens) que não
estão nos docs ou nos tool results. Política certa, número errado.
**Exemplos**: Trace 7, Trace 14

### 7. Missing Slot Re-confirmation
**Descrição**: Agent não confirma availability de slots/produtos antes de
afirmar disponibilidade, baseado em cache antigo.
**Exemplos**: Trace 22, Trace 38

### 8. Tone Drift on Frustration
**Descrição**: Quando user expressa frustração, agent fica defensivo ou
formal demais em vez de empático.
**Exemplos**: Trace 11, Trace 26
```

Cada uma dessas vira uma **eval criterion** no passo 3.

### Por que isso funciona

Hamel mostra que essas categorias derivadas de traces reais consistentemente catch failures que generic metrics não pegam. Você não consegue projetar essas categorias antes de ver os traces — porque não sabia que "Number Hallucination" era diferente de "Policy Hallucination" até você ver os 47 traces e perceber que o fix de cada um é diferente.

## Passo 3 — Binary LLM Judges

**Objetivo**: pra cada categoria do passo 2, criar um judge LLM com definição **binária** de pass/fail.

### Princípio: binário > Likert

Hamel Husain e Eugene Yan convergiram independentemente em pass/fail binário, não escalas Likert. Os motivos são práticos:

**Motivo 1 — inter-rater agreement em escalas ordinais é genuinamente ruim.** Cohen's Kappa humano em escalas de 5 pontos frequentemente fica entre **0.2 e 0.3**, o que significa que dois experts revisando a mesma resposta dão scores 2 pontos de distância. Se humanos não conseguem concordar, você não consegue calibrar um LLM judge contra julgamento humano, e seu eval vira ruído.

**Motivo 2 — stakeholders não usam a escala mesmo.** Eles pedem um threshold recomendado e tratam tudo acima como pass, tudo abaixo como fail — o que é comportamento binário forçado numa escala que fingia ser contínua.

### Como escrever uma definição binária

**Regra das duas frases**: uma frase definindo PASS, uma frase definindo FAIL. Sem rubrica. Sem escala.

**Teste de qualidade**: se duas pessoas lendo sua definição **discordariam num caso borderline**, a definição precisa apertar antes de você pedir pra um LLM aplicar.

### Exemplo concreto — Categoria "Context Amnesia"

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

**Por que esse prompt funciona**:
- Role explícito ("you are evaluating") como avaliador imparcial
- PASS e FAIL definidos em frase única cada
- Critério acionável: "did the agent ask for information already given"
- Reason field obrigatório (não opcional!) — é o dado que torna failures debugáveis
- JSON output pra parsing programático

### Implementação em DeepEval com GEval

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

Note `threshold=1.0` + `strict_mode=True` — força output binário 0/1, alinhado com a filosofia.

### Validação inter-annotator

**Antes de declarar o judge pronto**:

1. Pegue 10-15 traces (mistura de PASS e FAIL prováveis)
2. **Você** aplica a definição manualmente. Anota seu verdict.
3. **Outra pessoa** (idealmente um engenheiro do time) aplica independentemente
4. Compare. Se concordam em **8/10 ou mais**, OK.
5. Se discordam em mais de 2 casos, **a definição tem ambiguidade** — discuta os casos discordantes, refine a definição, repita.

Só depois disso vai pro LLM. Esse passo de validação humana é o que separa um eval que funciona de um que produz ruído.

### ⚠️ Escolha do modelo do judge

**NUNCA use o mesmo modelo como judge e como agent**. Self-enhancement bias é documentado: Claude avaliando Claude, GPT-4o avaliando GPT-4o — o judge sistematicamente favorece seus próprios outputs (Claude→Claude cai pra 44.8% de agreement com humanos em JudgeBench ICLR 2025).

Regra simples:
- Agent usa GPT-4o → judge usa Claude Sonnet
- Agent usa Claude → judge usa GPT-4o (ou Selene Mini pra Tier 2 com custo controlado)
- Agent usa modelo local → judge usa modelo cloud

Isso não é detalhe — é a diferença entre um eval system que mede qualidade real e um que mede "quanto o judge gosta de si mesmo".

### Calibração contra humano (AlignEval)

Eugene Yan formalizou isso como **AlignEval workflow**:

```
1. Você labeia 30+ amostras manualmente
2. Escreve a definição de duas frases
3. Roda o LLM judge nas mesmas amostras
4. Calcula:
   - TPR (True Positive Rate) = TP / (TP + FN) — judge pega failures reais?
   - TNR (True Negative Rate) = TN / (TN + FP) — judge não flagga PASSes corretos?
   - Cohen's Kappa = agreement ajustado por chance
5. Itera no prompt até κ ≥ 0.7
6. Quando OK, declara baseline e deploya
```

Target: **κ ≥ 0.7** antes de deployar em CI. Abaixo disso, anotadores (humano ou LLM) discordam frequentemente demais pro eval ser sinal confiável.

```python
from sklearn.metrics import cohen_kappa_score, confusion_matrix

# Você labeou manualmente 30 traces
human_labels = [1, 0, 1, 1, 0, 1, 0, 0, 1, 1, ...]  # 1=PASS, 0=FAIL

# Roda o LLM judge nos mesmos 30 traces
llm_labels = [1, 0, 1, 1, 1, 1, 0, 0, 1, 0, ...]

# Métricas
kappa = cohen_kappa_score(human_labels, llm_labels)
tn, fp, fn, tp = confusion_matrix(human_labels, llm_labels).ravel()
tpr = tp / (tp + fn)  # sensitivity / recall
tnr = tn / (tn + fp)  # specificity

print(f"Cohen's κ: {kappa:.2f}")
print(f"TPR: {tpr:.2f}")
print(f"TNR: {tnr:.2f}")

# Threshold de aceite:
assert kappa >= 0.7, "Judge needs more calibration"
assert tpr >= 0.75, "Judge missing too many real failures"
assert tnr >= 0.75, "Judge flagging too many false positives"
```

### Particionar dados de calibração corretamente

Insight crítico de "Who Validates the Validators" (ACM CHI 2024): seus dados de calibração precisam vir da **distribuição atual** de outputs do agent, não de samples antigos.

Se seu agent mudou (modelo novo, prompt novo), o calibration set precisa incluir **samples recentes** dessa distribuição. Senão você tá calibrando contra um agent que não existe mais.

Faça split 60/40:
- **60% dev**: pra iterar o prompt do judge
- **40% test**: nunca usado pra iteração — só pra check final

Iterar contra o test set é memorização, não calibração.

## Passo 4 — CI Deployment

Depois que o judge está calibrado, integra no CI/CD com gating apropriado.

### Estrutura recomendada

```python
# tests/test_agent_quality.py
import pytest
from deepeval import assert_test
from deepeval.test_case import LLMTestCase
from deepeval.metrics import GEval

# Carrega golden dataset (mesmos traces que você usou pra calibrar + outros)
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

Roda:

```bash
deepeval test run tests/test_agent_quality.py
```

Em CI/CD, gate em:
- **Tier 1 (every commit)**: deterministic assertions only (ver `deepeval-production`)
- **Tier 2 (every PR)**: esses judges product-specific
- **Tier 3 (nightly)**: full benchmark com pass^k

### Calibração ongoing

Judges driftam. Três coisas mudam ao longo do tempo:

1. **Modelo subjacente atualiza** — mesmo com version pinning, comportamento muda sutilmente entre minor versions
2. **Distribuição de outputs do produto muda** — system prompt evolui, knowledge base atualiza
3. **Seus critérios afrouxam na sua cabeça** — você revisa mais traces e o que parecia FAIL agora parece PASS

**Cadência de calibração mínima**: a cada 2 semanas:

1. Sample estratificado: 10 traces que o judge marcou PASS, 10 que marcou FAIL
2. Você (ou domain expert) labeia manualmente
3. Recalcula TPR e TNR
4. Se TPR < 0.75 → judge tá perdendo failures reais → recalibra
5. Se TNR < 0.75 → judge tá gerando ruído → recalibra

**Track tendências rolling de 7 e 30 dias**, não sessões individuais. Single-session audits são flaky; aggregates são confiáveis.

## Domain expertise é não-negociável

Esse é um dos pontos mais subestimados do framework do Hamel: você precisa de **alguém que entenda profundamente o que outputs bons parecem pro seu produto específico**. Não um generalista que diz "isso parece razoável". Alguém que olha a resposta de billing dispute e **sabe** se a aplicação da política tá correta.

Pra customer support agent, isso significa que a pessoa calibrando seus evals deveria:
- Conhecer as políticas de support
- Entender que informação o agent realmente tem acesso
- Conseguir distinguir entre "vago mas aceitável" e "ativamente errado"

**Se essa pessoa é você**, proteja tempo pra trace review. Não delegue.

**Se é um SME (subject matter expert)**, seu workflow de evals precisa **incluir** ele sem exigir que ele entenda LLM infrastructure. Confident AI tem UI pra isso (anotação de goldens por não-técnicos). Mande um Google Sheets se for o caso. Não importa a ferramenta — importa o domain expert estar **no loop**.

## Eugene Yan: evals são prática, não deliverable

Mindset crítico do Eugene Yan: **eval suite que você escreve no mês 1 e nunca toca é pior que nenhum eval suite no mês 6**, porque tá gerando false confidence.

Os modos de falha do seu agent mudam à medida que prompts mudam, knowledge base atualiza, users encontram novos jeitos de phrasear pedidos. O eval suite precisa **acompanhar** isso.

Loops de manutenção explícitos:

- **Cada incident em produção que seus evals NÃO pegaram = um eval faltante**. Escreve imediatamente, adiciona à suite, faz post-mortem do porquê a coverage existente não viu.
- **Cada calibration session que revela judge drift = signal pra atualizar judge prompts**.
- **Cada nova feature shippada = nova failure surface que precisa coverage antes de ship**.

O **EDDOps framework** formaliza isso como continuous evaluation governance: avaliação não é uma fase, é uma **função** rodando em paralelo com toda atividade de dev. Em prática, alguém no time **owns** o eval suite do mesmo jeito que alguém owna o data pipeline. É infraestrutura, não tarefa que se fecha.

## O test do bom eval suite

Esse é um critério incrivelmente útil que o livro destila:

> **Se tudo passa 95% das vezes na sua suite, você está medindo coisas que seu agent já faz bem.**
> **Uma suite bem-desenhada derivada de padrões reais de falha deveria produzir pass rate ~70% na primeira rodada.**

| Pass rate inicial | Diagnóstico |
|-------------------|-------------|
| 95%+ | Suite tá medindo coisas que não são problema. **Falsa segurança.** Volte pro Step 1. |
| 70-85% | **Healthy.** Tem signal real pra agir. |
| 40-70% | OK também — agent precisa trabalho mas evals tão calibrados |
| <40% | Definições muito loose OU agent tem problema fundamental antes de eval ser bottleneck |

Se você roda evals e tudo passa, **isso é vermelho**, não verde.

## Roteiro completo com o usuário

1. **Pergunta**: "Você tem agent já rodando e gerando traces?"
   - Não → manda pra `deepeval-strategy` + `deepeval-instrument`
   - Sim → continua
2. **Pergunta**: "Quantas traces você consegue coletar dos últimos 7 dias? Idealmente 30-50."
3. **Setup**: ajude a exportar traces (Confident AI / LangSmith / Langfuse / Braintrust / via `trace_manager`)
4. **Open coding session 1** (30 min): leia 15-25 traces juntos, escreva notas freeform. Modele o tipo de notas que ele deve fazer — específicas, não genéricas.
5. **Open coding session 2** (30 min, idealmente outro dia): outros 15-25 traces.
6. **Axial coding**: pegue as notas, monte o prompt de clusterização, rode com Claude/GPT, refine as categorias com o usuário.
7. **Binary judge writing**: pra cada categoria (4-8), escreva a definição de 2 frases junto. Você gera o draft, o usuário valida.
8. **Inter-annotator validation**: 10-15 traces. Você labeia, ele labeia, comparam. Refinar onde discordam.
9. **AlignEval calibration**: 30+ traces, métricas TPR/TNR/κ, iterar até κ ≥ 0.7.
10. **CI integration**: monta o test file, integra no pipeline.
11. **Cadência**: combina cadência de re-calibração biweekly.

## Ferramentas pra exportar traces

| Plataforma | Como exportar traces |
|------------|----------------------|
| DeepEval (local) | `from deepeval.tracing import trace_manager; traces = trace_manager.get_all_traces_dict()` |
| Confident AI | `dataset.pull(alias="prod-traces-week-15")` ou export via UI |
| LangSmith | `client.list_runs(project_name="...", start_time=...)` |
| Langfuse | `langfuse.fetch_traces(start_time=...)` |
| Braintrust | `braintrust.fetch_dataset(...)` |
| Arize Phoenix | Phoenix UI export ou SDK |

Todas têm formato JSON exportable. O importante é trazer **trace completa**: input, output, retrieved context, tool calls com args e outputs.

## Encerramento

Após terminar o workflow de 4 passos, diga:

> "Pronto, você tem {N} judges product-specific calibrados, derivados de {M} traces reais. Esse é seu **baseline**. A partir de agora, esses judges são parte da sua infraestrutura — recalibração biweekly é mandatory. Próximo passo é integrar isso na sua estratégia de three-tier: Tier 1 (assertions deterministic em todo commit), Tier 2 (esses judges em cada PR), Tier 3 (nightly com pass^k). Quer que eu chame `deepeval-production` pra montar isso?"

## Anti-patterns

- ❌ **Pular open coding** porque "já sei que falhas existem" — você sabe as que viu, não as que existem
- ❌ **Categorias genéricas** ("hallucination", "quality") em vez de produto-específicas
- ❌ **Likert scales** em vez de binário — inter-rater agreement vai ser ruim
- ❌ **Skipar inter-annotator validation** — definição que parece clara pra você pode ser ambígua pra outros
- ❌ **Calibrar uma vez e nunca mais** — judges driftam silenciosamente
- ❌ **Aggregate agreement** sem TPR/TNR separados — esconde bias dos dois lados
- ❌ **95% pass rate** e achar que tá bom — é signal de evals fracos, não de agent bom
- ❌ **Iterar prompt do judge contra test set** — memorização, não calibração
- ❌ **Usar mesmo modelo como judge e agent** — self-enhancement bias (ver `deepeval-custom-metric`)
- ❌ **Domain expert fora do loop** — generic eval sem domain grounding produz scores genéricos que não predizem qualidade real
