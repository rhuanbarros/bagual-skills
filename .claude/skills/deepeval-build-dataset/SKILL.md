---
name: deepeval-build-dataset
description: Criação e gerenciamento de dataset de goldens para avaliação de agents. Use quando o usuário disser "criar dataset", "fazer goldens", "synthesizer", "gerar testes", "como criar goldens", "importar dataset csv", ou similar.
---

# DeepEval Build Dataset — Criando Goldens

Você é o construtor de dataset. Sem dataset, não tem avaliação. Sua missão: levar o usuário de "não tenho exemplos" até "tenho um `EvaluationDataset` com pelo menos 5-10 goldens prontos".

## ⚠️ Recomendação importante: trace-driven > manual genérico

Antes de criar dataset, pergunte ao usuário: **"Você já tem o agent instrumentado e gerando traces (mesmo que sintéticos)?"**

Se **sim**, recomende fortemente que ele faça **trace review (open coding)** antes de criar goldens manuais. A skill `deepeval-error-analysis` cobre o workflow completo de Hamel Husain (open coding → axial coding → binary judges) que produz **goldens product-specific** baseados em failures reais, não em failures imaginadas.

A diferença é crítica:

| Approach | Resultado |
|----------|-----------|
| Goldens manuais "from imagination" | Você cria casos pra problemas que **acha** que vão aparecer. Provavelmente vai medir coisas que o agent já faz bem, e missar os failure modes reais. |
| Trace review → goldens product-specific | Você cria casos pra falhas que **observou** acontecendo. Catch dos failure modes reais com signal alto. |

**Regra de bolso**: 5-10 goldens derivados de trace review valem mais que 50 goldens criados from scratch. Hamel mostrou isso em workshops com 3000+ engenheiros.

**Quando criar goldens manuais sem trace review faz sentido**:
- Você ainda não tem o agent funcionando (precisa de algo pra rodar antes de gerar traces)
- Smoke tests / sanity checks
- Synthesizer (geração automática) precisa de seed examples

Pra esses casos, continue lendo. Pros casos onde você **tem** traces, **vá pra `deepeval-error-analysis` primeiro**.

## Conceitos centrais — embutidos

### O que é um Golden

**Golden** = "caso de teste pendente". Diferente de um `LLMTestCase` que está pronto pra avaliar, um Golden contém só os dados de entrada e o esperado. O `actual_output` (o que o agent realmente produziu) é gerado **dinamicamente** quando você roda o agent.

A analogia: Golden é o **molde**, TestCase é a **peça pronta** após você rodar o agent contra o golden.

### Por que Goldens > TestCases

- Permitem rerodar o mesmo dataset contra **versões diferentes** do agent (regressão)
- Permitem avaliar o agent com **inputs que ainda não foram processados**
- São o jeito **preferido** de inicializar um dataset

### Data model — Single-turn Golden

```python
from pydantic import BaseModel
from typing import List, Optional, Dict
from deepeval.test_case import ToolCall

class Golden(BaseModel):
    input: str                                  # OBRIGATÓRIO — o input do usuário
    expected_output: Optional[str] = None       # output ideal (opcional)
    context: Optional[List[str]] = None         # contexto pré-existente (opcional)
    expected_tools: Optional[List[ToolCall]] = None  # tools que deveriam ser chamadas
    
    # Metadata útil
    additional_metadata: Optional[Dict] = None
    comments: Optional[str] = None
    custom_column_key_values: Optional[Dict[str, str]] = None
    
    # NÃO popular manualmente — geram dinamicamente
    actual_output: Optional[str] = None
    retrieval_context: Optional[List[str]] = None
    tools_called: Optional[List[ToolCall]] = None
```

### Data model — Multi-turn ConversationalGolden

```python
class ConversationalGolden(BaseModel):
    scenario: str                              # OBRIGATÓRIO — descrição do cenário da conversa
    expected_outcome: Optional[str] = None     # o que deveria acontecer no final
    user_description: Optional[str] = None     # quem é o user simulado
    context: Optional[List[str]] = None
    
    additional_metadata: Optional[Dict] = None
    comments: Optional[str] = None
    
    # Geralmente NÃO popular — geram dinamicamente via ConversationSimulator
    turns: Optional[list] = None
```

### Single-turn vs Multi-turn dataset

Datasets em DeepEval são **statefully single OU multi-turn**, não os dois. A primeira `add_golden()` define qual tipo é:

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

Não dá pra mudar depois. **Decida no início**.

## Pergunta crítica

"Você quer avaliar interações **single-turn** (uma pergunta → uma resposta do agent) ou **multi-turn** (uma conversa inteira com várias trocas)?"

- **Single-turn** → use `Golden` (caso mais comum pra agents que executam tarefas)
- **Multi-turn** → use `ConversationalGolden` (caso de chatbots, copilots de conversa)

## Os 4 caminhos pra criar dataset

1. **Manual** — escreve goldens à mão (recomendado pra começar)
2. **Synthesizer** — gera goldens automaticamente a partir de docs / contexto / scratch
3. **Importar** — JSON, CSV, ou Hugging Face
4. **Cloud** — pull/push via Confident AI

## Caminho 1 — Criação manual (RECOMENDADO PRA COMEÇAR)

Pra um agent novo, **comece manualmente** com 5-10 goldens. Eles são teus "ground truth" e te ensinam o que é importante.

### Conversa estruturada com o usuário

**Pergunta 1**: "Me dá 3 exemplos de inputs reais que usuários mandariam pro seu agent. Pode ser bem variado: um caso simples, um caso difícil, um edge case."

Anote como `inputs_iniciais`.

**Pergunta 2**: "Pra cada um desses, qual seria o resultado ideal? Ex: 'reserva um voo NYC→Paris' → 'voo reservado, confirmação retornada'."

Anote como `expected_outputs`.

**Pergunta 3**: "Quais tools você espera que o agent chame em cada caso? Ex: pra 'reservar voo' → `search_flights` + `book_flight`."

Anote como `expected_tools`.

**Pergunta 4** (importante!): "Lembra dos failure modes que você priorizou no plano de avaliação? Vamos criar 1-2 goldens pra cada modo de falha. Por exemplo: pra 'agent reserva voo errado', criamos um golden com input ambíguo pra ver se ele clarifica ou erra."

### Código resultante

```python
from deepeval.dataset import EvaluationDataset, Golden
from deepeval.test_case import ToolCall

dataset = EvaluationDataset(goldens=[
    # Caso simples
    Golden(
        input="Reserve um voo de NYC pra Paris pra próxima segunda",
        expected_output="Voo reservado, confirmação CONF-XXX retornada",
        expected_tools=[
            ToolCall(name="search_flights"),
            ToolCall(name="book_flight"),
        ],
    ),
    # Caso ambíguo (testa robustez)
    Golden(
        input="Quero ir pra Paris",
        expected_output="Pediu mais detalhes (data, origem) antes de buscar",
        expected_tools=[],  # não deve chamar nenhuma tool ainda
    ),
    # Edge case (input quebrado)
    Golden(
        input="reserva voo nyc-paris 2099-13-45",  # data inválida
        expected_output="Erro de validação, pediu data válida",
        expected_tools=[],
    ),
    # ... mais goldens
])
```

### Adicionar mais goldens depois

```python
dataset.add_golden(Golden(input="Cancele minha última reserva"))
```

## Caminho 2 — Synthesizer (geração automática)

Synthesizer gera goldens **sintéticos** a partir de documentos, contextos, ou do zero. Útil quando você não tem exemplos suficientes ou quer expandir cobertura.

### 4 métodos disponíveis

| Método | Quando usar |
|--------|-------------|
| `generate_goldens_from_docs()` | Tem knowledge base (PDFs, .docx, .txt) e quer gerar perguntas baseadas no conteúdo. **Mais útil pra RAG**. |
| `generate_goldens_from_contexts()` | Já tem chunks/contextos prontos como list de strings |
| `generate_goldens_from_scratch()` | Zero base — geração puramente do nada baseada em descrição |
| `generate_goldens_from_goldens()` | Aumenta um conjunto existente de goldens (variações/evoluções) |

### Exemplo — from docs

```python
from deepeval.synthesizer import Synthesizer
from deepeval.dataset import EvaluationDataset

goldens = Synthesizer().generate_goldens_from_docs(
    document_paths=['knowledge_base.txt', 'manual.docx', 'product.pdf']
)

dataset = EvaluationDataset(goldens=goldens)
```

### Exemplo — from scratch

```python
goldens = Synthesizer().generate_goldens_from_scratch(
    subject="Travel booking agent capable of searching flights and hotels",
    task="Test the agent's ability to handle ambiguous requests",
    output_format="Standard input → expected_output",
    num_goldens=20,
)
```

### Como funciona internamente

Synthesizer usa **técnicas de evolução** pra complicar e tornar os goldens gerados mais realistas e parecidos com dados feitos por humanos. Por baixo, é um LLM gerando inputs + expected outputs baseado nos parâmetros que você passou.

**Importante**: revise os goldens gerados manualmente antes de confiar neles. Synthesizer é ótimo pra cobertura mas pode gerar exemplos artificiais.

### Conversation Simulator (multi-turn)

Pra gerar **turns** dentro de um `ConversationalTestCase`, use `ConversationSimulator` em vez do Synthesizer:

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
    # Sua função que recebe input + histórico e retorna resposta do agent
    return await your_agent_function(input, conversation_history)

convo_test_cases = simulator.simulate(
    model_callback=model_callback,
    stopping_criteria="Stop when the user's banking request has been fully resolved.",
)
```

## Caminho 3 — Importar de arquivos

### De JSON

Formato: array de objetos onde cada objeto tem keys do Golden.

```python
from deepeval.dataset import EvaluationDataset

dataset = EvaluationDataset()

# Como goldens
dataset.add_goldens_from_json_file(
    file_path="example.json",
)

# Como test cases já prontos (raro)
dataset.add_test_cases_from_json_file(
    file_path="example.json",
    input_key_name="query",
    actual_output_key_name="actual_output",
    expected_output_key_name="expected_output",
    context_key_name="context",
    retrieval_context_key_name="retrieval_context",
)
```

Se as keys do JSON forem diferentes do convencional, passe os nomes via parâmetros (`input_key_name`, etc).

### De CSV

```python
dataset = EvaluationDataset()

# Como goldens
dataset.add_goldens_from_csv_file(
    file_path="example.csv",
)

# Como test cases
dataset.add_test_cases_from_csv_file(
    file_path="example.csv",
    input_col_name="query",
    actual_output_col_name="actual_output",
    expected_output_col_name="expected_output",
    context_col_name="context",
    context_col_delimiter=";",  # IMPORTANTE pra colunas que viram lista
    retrieval_context_col_name="retrieval_context",
    retrieval_context_col_delimiter=";",
)
```

`expected_output`, `context`, `retrieval_context`, `tools_called`, `expected_tools` são **todos opcionais**.

## Caminho 4 — Cloud (Confident AI)

Se o usuário tá logado no Confident AI, ele pode gerenciar datasets na nuvem com colaboração de domain experts.

### Pull (baixar)

```python
from deepeval.dataset import EvaluationDataset

dataset = EvaluationDataset()
dataset.pull(alias="My Dataset")  # alias é o nome dado no Confident AI
print(dataset.goldens)  # sanity check
```

### Push (subir)

```python
dataset = EvaluationDataset(goldens=[...])
dataset.push(alias="My dataset")
```

Se não tem certeza que estão prontos:

```python
dataset.push(alias="My dataset", finalized=False)
# Não vão ser pulled até você marcar como finalized no Confident AI manualmente
```

### Vantagens do cloud

- Domain experts (não-técnicos) criam, anotam, comentam goldens via UI
- Versionamento built-in
- Upload em CSV via interface
- Combinação com test runs automaticamente
- Custom columns

## Salvar local

Se não usa Confident AI, salve em arquivo:

```python
# Como JSON
dataset.save_as(
    file_type="json",
    directory="./eval-data",
    file_name="my_dataset",  # opcional, default é YYYYMMDD_HHMMSS
    include_test_cases=False,  # se True, salva test cases também
)

# Como CSV
dataset.save_as(
    file_type="csv",
    directory="./eval-data",
)
```

## Best practices pra dataset bom

- **Cobertura diversa**: inputs reais variando em complexidade, casos extremos, edge cases
- **Foco quantitativo**: cada golden testa algo específico, não tudo de uma vez
- **Objetivos claros**: alinhe goldens com as métricas escolhidas
- **Pequeno e bom > grande e ruim**: 10 goldens bem pensados > 100 goldens genéricos
- **Inclua failure modes**: pelo menos 1-2 goldens pra cada modo de falha priorizado
- **Versionamento**: mantenha goldens em git (ou Confident AI) pra rastrear mudanças

## Quantos goldens?

| Estágio | Recomendação |
|---------|--------------|
| Smoke test (validar setup) | 1-2 |
| Dev inicial | 5-10 |
| Iteração regular | 20-50 |
| Pré-produção | 50-200 |
| CI/CD em produção | depende do custo (LLM-as-judge custa) |

**Lembre**: cada golden = 1 chamada do agent (custo de tokens) + 1 chamada de LLM-as-judge por métrica (custo de tokens). Faça a conta antes de rodar 1000 goldens com 5 métricas.

## Roteiro que você segue com o usuário

1. **Pergunta**: "Single-turn ou multi-turn?"
2. **Pergunta**: "Você prefere começar manual (recomendado) ou gerar com Synthesizer?"
3. **Se manual**: conduza o usuário a criar 5-10 goldens (use as 4 perguntas do Caminho 1)
4. **Se Synthesizer**: pergunte sobre fonte (docs/contextos/scratch), gere, depois revise junto
5. **Validação**: rode `print(dataset.goldens)` ou `len(dataset.goldens)` pra confirmar
6. **Salvar**: ofereça salvar local em JSON ou push pro Confident AI

## Encerramento

Após criar o dataset, diga:

> "Dataset com {N} goldens pronto. Próximo passo é escolher quais métricas vão rodar contra ele. Quer que eu chame `deepeval-pick-metrics`?"

## Anti-patterns

- ❌ Forçar Synthesizer pra usuário iniciante — manual ensina melhor
- ❌ Criar 100 goldens antes de rodar nenhum eval — small batch primeiro
- ❌ Esquecer de cobrir failure modes — esses são os mais importantes
- ❌ Pular `expected_tools` quando vai usar `ToolCorrectnessMetric`
- ❌ Misturar single-turn e multi-turn no mesmo dataset (não dá)
