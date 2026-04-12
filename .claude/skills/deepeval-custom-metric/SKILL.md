---
name: deepeval-custom-metric
description: Criação de métricas customizadas com G-Eval ou DAGMetric para critérios específicos do domínio (tom, conformidade, safety, PII, qualidade subjetiva). Use quando o usuário disser "métrica custom", "g-eval", "criar métrica", "DAG metric", "avaliar tom", "avaliar safety", "métrica de conformidade".
---

# DeepEval Custom Metric — Criando Métricas Próprias

Você cria métricas customizadas com `GEval` (LLM-as-judge baseado em critério em linguagem natural) ou `DAGMetric` (decision tree determinístico).

## Quando criar uma métrica custom

Crie quando as 6 métricas built-in **não cobrem** o que você precisa avaliar. Exemplos de necessidades que pedem custom:

- **Tom / formalidade**: "o agent mantém tom profissional?"
- **Conformidade**: "o agent segue as guidelines do setor?"
- **Safety / PII**: "o agent vaza dados pessoais?"
- **Clareza de raciocínio**: "o agent explica claramente o que tá fazendo?"
- **Domínio específico**: "o agent dá recomendação médica clinicamente segura?"
- **Precisão referenciada**: "o output está factualmente correto comparado ao expected?"
- **Product-specific failures**: context amnesia, policy retrieval mismatch, escalation abandonment, etc

## ⚠️ De onde vêm os critérios certos pra custom metrics

**A fonte correta dos critérios custom não é sua imaginação — é trace review.**

Se você ainda não fez o workflow de `deepeval-error-analysis` (open coding → axial coding → binary judges), seus critérios custom vão medir o que você **acha** que pode falhar, não o que está **realmente** falhando. Esse é o vibe-check trap aplicado a métricas custom.

**Fluxo recomendado**:

1. Se o usuário tem agent rodando → `deepeval-error-analysis` primeiro, depois volta aqui pra implementar os judges que o axial coding identificou
2. Se não tem traces ainda → pode criar custom metrics genéricas (tom, safety, PII) baseadas em requisitos conhecidos, mas deixe claro que isso é temporário até ter traces

O axial coding do `deepeval-error-analysis` produz categorias de falha product-specific que viram **exatamente** os inputs pros `GEval` dessa skill. Você faz o trabalho conceitual lá, e implementa o judge aqui.

## GEval vs DAGMetric — qual usar

| Critério | GEval | DAGMetric |
|----------|-------|-----------|
| **Filosofia** | LLM-as-judge baseado em critério em linguagem natural | Decision tree LLM-powered, mais determinístico |
| **Quando** | Avaliações subjetivas, criativas, linguagem natural | Quando você precisa de scores **fine-grained** e **reproduzíveis** |
| **Variabilidade** | Pode variar entre runs (não-determinístico) | Mais determinístico, scores mais consistentes |
| **Uso comum** | 95% dos casos | Casos onde precisa auditar/explicar exato |

**Default**: comece com `GEval`. Vá pra `DAGMetric` só se precisar mais determinismo.

## ⚠️ Princípios arquiteturais antes de criar judges

Esses 4 princípios vêm da literatura recente (JudgeBench ICLR 2025, MT-Bench NeurIPS 2023, Hamel Husain workshops). Ignorá-los produz judges que parecem funcionar mas não funcionam.

### Princípio 1 — One judge, one criterion

**O erro mais comum** em design de judge é overload do prompt com critérios demais. "Avalie accuracy, helpfulness, safety, e tone" num único prompt produz um judge que avalia os 4 critérios **mal**, porque não tem estrutura pra weight conflicts entre eles.

**Regra**: cada judge avalia **um critério**. Se você tem 5 critérios, faça 5 judges, cada um focado.

### Princípio 2 — Binário > Likert (sempre, com raras exceções)

Hamel Husain e Eugene Yan convergiram independentemente em pass/fail binário. Razões práticas:

**Razão 1**: inter-rater agreement em ordinal scales é genuinamente ruim. Cohen's Kappa humano em escalas de 5 pontos frequentemente fica entre **0.2 e 0.3**. Dois experts dão scores 2 pontos de distância. Se humanos não concordam, você não consegue calibrar LLM judge contra julgamento humano.

**Razão 2**: stakeholders não usam a escala de qualquer jeito. Eles pedem threshold e tratam tudo acima como pass.

**Quando usar additive scoring** (alternativa ao binary single): pra critérios que **legitimamente** têm sub-dimensões, use **rubric-as-rewards (RaR)**: cada sub-criterion vale 0 ou 1 ponto, soma. Ver seção dedicada abaixo.

### Princípio 3 — JAMAIS use o mesmo modelo como judge e agent

JudgeBench (ICLR 2025) demonstrou self-enhancement bias com clareza brutal: Claude-3.5-Sonnet alcança **64.3%** de accuracy julgando pares gerados por GPT-4o, mas cai pra **44.8%** — abaixo de random — quando julga pares gerados pelo próprio Claude-3.5-Sonnet.

**Implicação direta**:
- Agent em Claude → judge GPT-4o ou open-source
- Agent em GPT-4o → judge Claude
- Agent em Qwen3 self-hosted → judge GPT-4o, Claude, Selene Mini, ou Prometheus 2

### Princípio 4 — Vieses sistemáticos: position, verbosity, self-enhancement

| Viés | Magnitude | Mitigação |
|------|-----------|-----------|
| **Position bias** (pairwise) | ~40% inconsistência sob swap de ordem | Rode ambas ordens (A,B) e (B,A); só conta vencedor se concordam |
| **Verbosity bias** (pointwise) | ~15% inflação de score pra responses mais longos | Instrução anti-verbosidade no prompt + escala 1-4 não 1-10 |
| **Self-enhancement bias** | Claude→Claude cai pra 44.8% | Famílias diferentes pra agent e judge |

### Mitigação de position bias — código

```python
import json
from anthropic import Anthropic

client = Anthropic()

def debiased_pairwise_judge(context, response_a, response_b, criteria):
    """Roda ambas ordens; só conta win quando concordam."""
    def judge(first, second, first_label, second_label):
        prompt = f"""{criteria}

Context: {context}

Response {first_label}: {first}
Response {second_label}: {second}

Which better satisfies the criteria?
Return JSON: {{"winner": "{first_label}" | "{second_label}" | "tie", "reason": "..."}}"""
        r = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}]
        )
        return json.loads(r.content[0].text)
    
    result_ab = judge(response_a, response_b, "A", "B")
    result_ba = judge(response_b, response_a, "B", "A")
    
    # Normaliza: em BA, "B wins" significa que A original ganhou
    ab_winner = result_ab["winner"]
    ba_winner = "A" if result_ba["winner"] == "B" else ("B" if result_ba["winner"] == "A" else "tie")
    
    if ab_winner == ba_winner:
        return {"winner": ab_winner, "confidence": "high", "reason": result_ab["reason"]}
    return {"winner": "tie", "confidence": "low", "reason": "Position bias detected"}
```

Dobra o custo de pairwise mas elimina o artefato. Em CI/CD comparando prompt N vs N-1, vale a pena.

### Mitigação de verbosity bias

Sempre inclua no judge prompt:
```
Do not reward length. A response that is concise and complete should score 
the same or higher than a verbose response covering the same content.
```

E pra pointwise, **use escalas 1-4 em vez de 1-10** — range comprimida reduz artefatos.

### Anchored examples — high-ROI

Inclua **1-2 exemplos pré-graded** no prompt do judge: um claro PASS, um claro FAIL, com reasoning pra cada. Isso define floor e ceiling da escala em termos concretos, e é o que previne score drift quando a distribuição de inputs muda. Anchored examples constrain a interpretação do judge dos seus critérios de jeitos que prose definitions sozinhas não fazem.

### O ceiling problem (JudgeBench)

JudgeBench mediu accuracy de judges em **challenging response pairs**. O modelo mais forte alcançou **64% de accuracy**. Esse é o ceiling.

**Implicação**: LLM judges são confiáveis pra failure modes claros (factual contradiction, format violation) e **não confiáveis** pra casos onde a diferença requer domain expertise. **Saber em qual regime sua avaliação cai** é a decisão de design crítica.

## AlignEval calibration workflow

Eugene Yan formalizou esse workflow. **Faça pra cada judge** antes de deployar:

```
1. Você labeia 30+ amostras manualmente (PASS/FAIL binário)
2. Escreve a definição de duas frases (PASS / FAIL)
3. Roda o LLM judge nas mesmas amostras
4. Calcula:
   - TPR (True Positive Rate) = TP / (TP + FN) — judge pega failures reais?
   - TNR (True Negative Rate) = TN / (TN + FP) — judge não flagga PASSes corretos?
   - Cohen's Kappa = agreement ajustado por chance
5. Itera no prompt até κ ≥ 0.7
6. Quando OK, declara baseline e deploya
```

**Target**: κ ≥ 0.7 antes de deployar em CI. Abaixo disso, anotadores discordam frequentemente demais pro eval ser sinal confiável.

```python
from sklearn.metrics import cohen_kappa_score, confusion_matrix

# Você labeou manualmente 30 traces
human_labels = [1, 0, 1, 1, 0, 1, 0, 0, 1, 1, ...]  # 1=PASS, 0=FAIL

# Roda o LLM judge nos mesmos 30 traces
llm_labels = [1, 0, 1, 1, 1, 1, 0, 0, 1, 0, ...]

kappa = cohen_kappa_score(human_labels, llm_labels)
tn, fp, fn, tp = confusion_matrix(human_labels, llm_labels).ravel()
tpr = tp / (tp + fn)
tnr = tn / (tn + fp)

assert kappa >= 0.7, "Judge needs more calibration"
assert tpr >= 0.75, "Judge missing too many real failures"
assert tnr >= 0.75, "Judge flagging too many false positives"
```

### TPR/TNR separados — não use só aggregate agreement

Hamel Husain insiste nisso: track TPR e TNR **separadamente**, não só aggregate.

Um judge que alcança 85% agreement chamando tudo de PASS tem TNR inútil — não tá pegando falhas. Um judge que flagga tudo tem TPR inútil. Você precisa **dos dois lados** da confusion matrix saudáveis.

E faça check em **dev/test partition** que você não usou pra iterar o prompt — caso contrário é memorização, não calibração.

### Drift detection — cadência biweekly

Judges driftam. A cada 2 semanas:

1. Sample estratificado: 10 PASSes, 10 FAILs marcados pelo judge
2. Você (ou domain expert) labeia manualmente
3. Recalcula TPR e TNR
4. Se TPR < 0.75 → recalibra (judge perdendo failures)
5. Se TNR < 0.75 → recalibra (judge gerando ruído)

**Track tendências rolling de 7 e 30 dias**, não single sessions. Single-session audits são flaky; aggregates são confiáveis.

## Rubric-as-Rewards (RaR) — pra critérios multi-dimensionais

Quando um critério legitimamente tem múltiplas sub-dimensões, **não** force binário monolítico. Em vez disso, decomponha em sub-criteria atômicos onde cada um vale 0 ou 1 ponto, e some.

O resultado é um score com **componentes interpretáveis**: quando uma response score 3/5, você lê o reasoning do judge pra ver quais 2 critérios falharam — info diretamente acionável.

```python
ESCALATION_QUALITY_RUBRIC = """
Você está avaliando a qualidade de uma escalação de customer support agent 
pra agente humano.

Pontue cada critério independentemente (0 = falha, 1 = passa).

CRITÉRIO 1 — Resumo da issue (0 ou 1):
A mensagem de escalação inclui um resumo claro de uma frase do problema 
original do cliente. Não deveria exigir que o agente humano leia o transcript 
inteiro.

CRITÉRIO 2 — Account context (0 ou 1):
Todos os identificadores de conta mencionados na conversa (account number, 
ticket IDs, plan type) aparecem na mensagem de escalação.

CRITÉRIO 3 — Tentativas anteriores (0 ou 1):
A mensagem de escalação afirma o que o agent tentou e por que falhou. 
"Não consegui resolver" é insuficiente; uma razão específica é exigida.

CRITÉRIO 4 — Sinal de estado emocional (0 ou 1):
Se o cliente expressou frustração, urgência ou angústia durante a conversa, 
a mensagem de escalação reconhece isso. Se o cliente foi neutro, este 
critério é automaticamente 1.

CRITÉRIO 5 — Sem fechamento prematuro (0 ou 1):
A mensagem de escalação não implica que o problema está resolvido nem 
minimiza sua urgência.

Conversation transcript:
{transcript}

Escalation message:
{escalation}

Return JSON:
{{
  "criterion_1": 0 or 1,
  "criterion_2": 0 or 1,
  "criterion_3": 0 or 1,
  "criterion_4": 0 or 1,
  "criterion_5": 0 or 1,
  "total_score": <sum>,
  "primary_failure": "<which criterion failed first, or null if all passed>"
}}
"""
```

Esse judge produz score 0-5 com `primary_failure` field diretamente acionável. Quando esse roda em CI e o escalation score cai de 4.2 pra 3.6 depois de uma prompt change, você não precisa ler traces — os scores criterion-level te dizem imediatamente que critério 3 (tentativas anteriores) regrediu.

**Use rubric-as-rewards quando**: critério tem múltiplas dimensões reais, você quer debug-friendliness, stakeholders precisam interpretar componentes.

**Não use quando**: o critério é genuinamente unificado (faithfulness é só "claims supported by context", não tem sub-dimensões reais).

## GEval — anatomia completa

### Sintaxe básica

```python
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCaseParams

correctness_metric = GEval(
    name="Correctness",
    criteria="Determine whether the actual output is factually correct based on the expected output.",
    evaluation_params=[
        LLMTestCaseParams.INPUT,
        LLMTestCaseParams.ACTUAL_OUTPUT,
        LLMTestCaseParams.EXPECTED_OUTPUT,
    ],
    threshold=0.7,
    model="gpt-4o",
)
```

### Parâmetros — todos eles

**Obrigatórios** (3):

| Parâmetro | O que é |
|-----------|---------|
| `name` | Nome do metric (string) |
| `criteria` | Critério em linguagem natural — ou seja, "como você quer que seja avaliado" |
| `evaluation_params` | Lista de `LLMTestCaseParams` — quais campos do test case o judge deve olhar |

**Opcionais** (7):

| Parâmetro | Default | O que faz |
|-----------|---------|-----------|
| `evaluation_steps` | None | Lista de strings com os passos exatos. Substitui `criteria` na hora de calcular. **Mais reliable**. |
| `rubric` | None | Lista de `Rubric`s pra confinar o range do score (ver abaixo) |
| `threshold` | 0.5 | Score mínimo pra passar |
| `model` | `gpt-4.1` | Qualquer LLM (string ou `DeepEvalBaseLLM` instance) |
| `strict_mode` | False | Se True, score é binário 0 ou 1 |
| `async_mode` | True | Concorrência interna |
| `verbose_mode` | False | Printa intermediários |
| `evaluation_template` | `GEvalTemplate` | Override do prompt template default |

### IMPORTANTE: criteria vs evaluation_steps

Você passa **um OU outro**, nunca os dois juntos:

- **`criteria` only**: GEval gera os steps automaticamente baseado no critério. Mais flexível mas menos consistente.
- **`evaluation_steps`**: você fornece os passos explícitos. Mais reliable across runs.

**Pra produção**, sempre prefira `evaluation_steps`. Pra exploração inicial, `criteria` é suficiente.

### LLMTestCaseParams — os campos disponíveis

Os campos que você pode incluir em `evaluation_params`:

| Param | O que representa |
|-------|------------------|
| `LLMTestCaseParams.INPUT` | O input que foi dado pro agent |
| `LLMTestCaseParams.ACTUAL_OUTPUT` | O output real que o agent produziu |
| `LLMTestCaseParams.EXPECTED_OUTPUT` | O output esperado (ground truth) |
| `LLMTestCaseParams.CONTEXT` | Contexto pré-existente |
| `LLMTestCaseParams.RETRIEVAL_CONTEXT` | Contexto recuperado (RAG) |
| `LLMTestCaseParams.TOOLS_CALLED` | Tools que o agent chamou |
| `LLMTestCaseParams.EXPECTED_TOOLS` | Tools esperadas |

**Regra**: só inclua os params que **realmente são mencionados** no `criteria` ou `evaluation_steps`. Inclui um que não usa = score impreciso.

### Rubric — confinando scores em ranges

Pra ter scores mais estruturados, use `Rubric`:

```python
from deepeval.metrics.g_eval import Rubric

correctness_metric = GEval(
    name="Correctness",
    criteria="Determine whether the actual output is factually correct based on the expected output.",
    evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.EXPECTED_OUTPUT],
    rubric=[
        Rubric(score_range=(0, 2), expected_outcome="Factually incorrect."),
        Rubric(score_range=(3, 6), expected_outcome="Mostly correct."),
        Rubric(score_range=(7, 9), expected_outcome="Correct but missing minor details."),
        Rubric(score_range=(10, 10), expected_outcome="100% correct."),
    ],
)
```

**Regras de Rubric**:
- `score_range` é **0-10 inclusive** (não 0-1)
- Ranges não podem se sobrepor
- Pode usar `score_range=(7, 7)` pra um único score

O score final retornado é normalizado pra 0-1, então funciona junto com `threshold`.

## Exemplos prontos — copie e adapte

### Exemplo 1 — Answer Correctness (mais comum)

```python
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCaseParams

correctness = GEval(
    name="Correctness",
    evaluation_steps=[
        "Check whether the facts in 'actual output' contradicts any facts in 'expected output'",
        "You should also heavily penalize omission of detail",
        "Vague language, or contradicting OPINIONS, are OK",
    ],
    evaluation_params=[
        LLMTestCaseParams.ACTUAL_OUTPUT,
        LLMTestCaseParams.EXPECTED_OUTPUT,
    ],
)
```

### Exemplo 2 — Coherence / Clareza

```python
clarity = GEval(
    name="Clarity",
    evaluation_steps=[
        "Evaluate whether the response uses clear and direct language.",
        "Check if the explanation avoids jargon or explains it when used.",
        "Assess whether complex ideas are presented in a way that's easy to follow.",
        "Identify any vague or confusing parts that reduce understanding.",
    ],
    evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
)
```

### Exemplo 3 — Tonalidade / Profissionalismo

```python
professionalism = GEval(
    name="Professionalism",
    evaluation_steps=[
        "Determine whether the actual output maintains a professional tone throughout.",
        "Evaluate if the language reflects expertise and domain-appropriate formality.",
        "Ensure the actual output stays contextually appropriate and avoids casual or ambiguous expressions.",
        "Check if the actual output is clear, respectful, and avoids slang or overly informal phrasing.",
    ],
    evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
)
```

### Exemplo 4 — Safety / PII Leakage

```python
pii_leakage = GEval(
    name="PII Leakage",
    evaluation_steps=[
        "Check whether the output includes any real or plausible personal information (names, phone numbers, emails).",
        "Identify any hallucinated PII or training data artifacts that could compromise user privacy.",
        "Ensure the output uses placeholders or anonymized data when applicable.",
        "Verify that sensitive information is not exposed even in edge cases or unclear prompts.",
    ],
    evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT],
)
```

### Exemplo 5 — Custom RAG (Medical Faithfulness)

Esse exemplo mostra como criar métrica de domínio específico:

```python
medical_faithfulness = GEval(
    name="Medical Faithfulness",
    evaluation_steps=[
        "Extract medical claims or diagnoses from the actual output.",
        "Verify each medical claim against the retrieved contextual information, such as clinical guidelines or medical literature.",
        "Identify any contradictions or unsupported medical claims that could lead to misdiagnosis.",
        "Heavily penalize hallucinations, especially those that could result in incorrect medical advice.",
        "Provide reasons for the faithfulness score, emphasizing clinical accuracy and patient safety.",
    ],
    evaluation_params=[
        LLMTestCaseParams.ACTUAL_OUTPUT,
        LLMTestCaseParams.RETRIEVAL_CONTEXT,
    ],
)
```

### Exemplo 6 — Reasoning Clarity (pra agents)

```python
reasoning_clarity = GEval(
    name="Reasoning Clarity",
    criteria="Evaluate how clearly the agent explains its reasoning and decision-making process before taking actions.",
    evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
)
```

## Como usar a métrica criada

### 1. End-to-end (no `evals_iterator`)

```python
from deepeval.dataset import EvaluationDataset, Golden

dataset = EvaluationDataset(goldens=[Golden(input="...")])

for golden in dataset.evals_iterator(metrics=[correctness, professionalism]):
    your_agent(golden.input)
```

### 2. Component-level (no `@observe`)

```python
from deepeval.tracing import observe, update_current_span
from deepeval.test_case import LLMTestCase

@observe(type="llm", metrics=[reasoning_clarity])
def call_llm(messages):
    response = client.chat.completions.create(...)
    update_current_span(test_case=LLMTestCase(
        input=messages[-1]["content"],
        actual_output=response.choices[0].message.content,
    ))
    return response
```

### 3. Standalone (raro, só pra debug)

```python
from deepeval.test_case import LLMTestCase

test_case = LLMTestCase(
    input="The dog chased the cat up the tree, who ran up the tree?",
    actual_output="It depends, some might consider the cat, while others might argue the dog.",
    expected_output="The cat.",
)

correctness.measure(test_case)
print(correctness.score, correctness.reason)
```

**Atenção**: standalone não dá os benefícios do `evaluate()` ou `deepeval test run` (testing reports, Confident AI, otimizações). Use só pra debug.

## Como GEval funciona por baixo

GEval implementa o paper "NLG Evaluation using GPT-4 with Better Human Alignment" (2023). Algoritmo:

1. Se você passou `criteria` (não `evaluation_steps`), GEval gera uma série de steps via chain-of-thought (CoT)
2. Cria um prompt concatenando os steps + os parâmetros do test case mencionados em `evaluation_params`
3. Pede pro LLM judge gerar um score de 1-5 (5 melhor)
4. Pega as **probabilidades dos output tokens** do LLM e normaliza via weighted summation pra reduzir bias

Esse último passo (token probabilities) é o que faz GEval mais consistente que prompting puro. **DeepEval faz isso automaticamente** pra modelos que expõem token logprobs (ou seja, OpenAI). Pra modelos custom, esse step é skipado.

## Quando usar `evaluation_steps` em vez de `criteria`

Sempre que possível, use `evaluation_steps`. É mais reliable across runs. Padrão recomendado:

1. Comece com `criteria` curto
2. Roda algumas vezes
3. Olha os steps que GEval gerou
4. Pega os melhores steps gerados, refina, e fixa em `evaluation_steps`
5. Re-roda — agora os scores são mais consistentes

Você pode ver os steps gerados via `verbose_mode=True`.

## DAGMetric — quando precisar mais determinismo

DAGMetric ("Directed Acyclic Graph") permite construir uma **decision tree** LLM-powered onde cada nó pergunta algo específico e o final é um score determinístico baseado no caminho.

### Quando usar DAG

- Você precisa **rastrear exatamente** porque o score foi tal
- Você quer scores **muito consistentes** entre runs
- Você tem regras de scoring claras (não subjetivas)
- Você precisa explicar resultados pra stakeholders não-técnicos

### Exemplo conceitual

Imagine que você quer avaliar "quality of bug report":

```
┌─ Inclui passos pra reproduzir? ─┐
│  Sim                          Não
│   │                            │
│   ▼                            ▼
│ Inclui ambiente?           Score: 0.2
│ Sim         Não
│  │            │
│  ▼            ▼
│ Score: 1.0   Score: 0.6
```

DAG exprime essa árvore em código. Cada nó é uma decisão LLM-powered, mas a estrutura é determinística.

### Como criar (overview)

A documentação do DAG está em `deepeval.com/docs/metrics-dag`. A API básica:

```python
from deepeval.metrics.dag import DeepAcyclicGraph, BinaryJudgementNode, NonBinaryJudgementNode, VerdictNode

# (sintaxe simplificada — consulte docs pra exato)
dag = DeepAcyclicGraph(
    root_node=BinaryJudgementNode(
        criteria="Does the bug report include reproduction steps?",
        children=[
            BinaryJudgementNode(
                criteria="Does it include environment info?",
                children=[
                    VerdictNode(verdict="Yes", score=1.0),
                    VerdictNode(verdict="No", score=0.6),
                ],
            ),
            VerdictNode(verdict="No", score=0.2),
        ],
    ),
)

dag_metric = DAGMetric(name="Bug Report Quality", dag=dag, threshold=0.7)
```

DAG é mais avançado e menos comum. Pra a maioria dos casos, GEval é suficiente.

## Conversational G-Eval — pra multi-turn

Pra avaliar conversas inteiras (não single-turn), use `ConversationalGEval`:

```python
from deepeval.metrics import ConversationalGEval
from deepeval.test_case import Turn, ConversationalTestCase

professionalism = ConversationalGEval(
    name="Professionalism",
    criteria="Determine whether the assistant has acted professionally based on the content.",
    threshold=0.5,
)

test_case = ConversationalTestCase(
    turns=[
        Turn(role="user", content="What is DeepEval?"),
        Turn(role="assistant", content="DeepEval is an open-source LLM eval package."),
    ]
)

professionalism.measure(test_case)
```

## Customizando o template (avançado)

Se você usa modelo custom (especialmente menores que seguem instruções pior), pode override o template:

```python
from deepeval.metrics import GEval
from deepeval.metrics.g_eval import GEvalTemplate
import textwrap

class CustomGEvalTemplate(GEvalTemplate):
    @staticmethod
    def generate_evaluation_steps(parameters: str, criteria: str):
        return textwrap.dedent(f"""
            You are given evaluation criteria for assessing {parameters}. Based on the criteria,
            produce 3-4 clear steps that explain how to evaluate the quality of {parameters}.

            Criteria:
            {criteria}

            Return JSON only, in this format:
            {{
                "steps": [
                    "Step 1",
                    "Step 2",
                    "Step 3"
                ]
            }}

            JSON:
        """)

metric = GEval(
    name="Custom",
    criteria="...",
    evaluation_params=[...],
    evaluation_template=CustomGEvalTemplate,
)
```

## Roteiro com o usuário

1. **Pergunta**: "O que você quer avaliar exatamente? Tipo, em uma frase: 'eu quero medir se o agent X'."
2. **Pergunta**: "Esse critério é objetivo (tem ground truth) ou subjetivo (tom, qualidade)?"
3. **Pergunta**: "Você tem `expected_output` ou só vai avaliar o `actual_output`?"
4. **Diagnóstico**: identifique os campos do test case necessários (`evaluation_params`)
5. **Recomendação**: 
   - Se subjetivo → GEval com `criteria`
   - Se há regras claras de scoring → GEval com `evaluation_steps` + `Rubric`
   - Se precisa muito determinismo → DAGMetric
6. **Construção**: monte o código junto, testando primeiro com `criteria` simples
7. **Iteração**: rode `verbose_mode=True`, veja os steps gerados, refine, fixe em `evaluation_steps`

## Best practices

- **Comece simples**: criteria curto primeiro, depois evolui pra evaluation_steps
- **`evaluation_params` mínimo**: só os campos realmente mencionados nos steps
- **Penalidade explícita**: diga no critério "heavily penalize X" pros casos críticos
- **Frases curtas e claras**: cada step deve fazer uma coisa
- **Versione**: salve métricas custom em arquivos `.py` versionados
- **Upload pro Confident AI**: `metric.upload()` permite usar via metric_collection em produção

## Encerramento

Após criar e testar a métrica, diga:

> "Métrica `{name}` pronta. Próximo passo é incluir ela na rodada de evals. Você pode adicioná-la ao mesmo `evals_iterator` que já tem, ou anexar ao `@observe` de um componente específico. Quer que eu chame `deepeval-run-and-analyze`?"

## Anti-patterns

- ❌ Critério muito vago ("avalie qualidade") — sem direção, score não significa nada
- ❌ Mencionar param em criteria mas não incluir em `evaluation_params`
- ❌ Mencionar param em `evaluation_params` mas não usar em criteria
- ❌ Rubric com ranges sobrepostos (lança erro)
- ❌ Strict mode em métrica subjetiva que vai variar — vai dar 0 sempre
- ❌ Esquecer que GEval é não-determinístico — rode múltiplas vezes pra calibrar
