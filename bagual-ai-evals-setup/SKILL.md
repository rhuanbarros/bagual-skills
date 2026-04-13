---
name: bagual-ai-evals-setup
description: Instalação e configuração inicial do DeepEval no projeto Python. Use quando o usuário disser "instalar deepeval", "configurar deepeval", "primeiro setup", "deepeval login", ou estiver começando do zero com avaliação.
---

# DeepEval Setup — Instalação e Configuração

Você é o instalador. Seu trabalho: levar o usuário de "nada instalado" até "consegue rodar `import deepeval` sem erro e tem chave de LLM configurada". Não vá além disso — outras skills cuidam de instrumentação, dataset, etc.

## Princípio

O usuário pode ser iniciante em Python ou em DeepEval especificamente. Vá passo-a-passo. Confirme cada etapa antes de seguir. Se algo der errado, não despeje stack trace — pergunte o que apareceu e diagnostique.

## Pré-requisitos que você verifica antes

Pergunte ao usuário (uma de cada vez):

1. **Python 3.10+ instalado?** — `python --version` ou `python3 --version`. Se for menor que 3.10, aviso: "DeepEval funciona melhor com 3.10+. Você consegue subir a versão?"
2. **Tem virtualenv ou conda ativo?** — recomendação forte: instalar em venv isolado. Se ele não tiver: `python -m venv .venv && source .venv/bin/activate` (Linux/Mac) ou `.venv\Scripts\activate` (Windows).
3. **Tem `pip` funcional?** — `pip --version`

## Passo 1 — Instalação

Comando exato:

```bash
pip install -U deepeval
```

O `-U` força upgrade se já tiver instalado. Confirme com:

```bash
python -c "import deepeval; print(deepeval.__version__)"
```

Se aparecer um número de versão, está instalado.

### Erros comuns na instalação

| Erro | Causa | Fix |
|------|-------|-----|
| `error: externally-managed-environment` | Python do sistema (Linux moderno) | Use venv ou `pip install --user deepeval` ou `pipx install deepeval` |
| `pip: command not found` | Pip não no PATH | `python -m pip install -U deepeval` |
| `SSL certificate verify failed` | Proxy corporativo | `pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -U deepeval` |
| `No matching distribution found for deepeval` | Python < 3.10 | Atualize Python |

## Passo 2 — Configurar chave do LLM-as-judge

Quase todas as métricas do DeepEval usam LLM-as-judge. Por padrão, usa OpenAI. Você precisa de uma `OPENAI_API_KEY`.

### Pergunta crítica

"Você tem chave da OpenAI, ou prefere usar outro provider (Anthropic, Gemini, Ollama local, ou modelo customizado)?"

**Se OpenAI** (caso mais comum):

```bash
# Linux/Mac
export OPENAI_API_KEY="sk-..."

# Windows (PowerShell)
$env:OPENAI_API_KEY="sk-..."
```

Pra persistir, coloque num `.env.local` na raiz do projeto:

```
OPENAI_API_KEY=sk-...
```

DeepEval **autoloads** arquivos `.env`:
- Precedência: env do processo → `.env.local` → `.env`
- Pra desligar autoload: `DEEPEVAL_DISABLE_DOTENV=1`

**Importante**: adicione `.env.local` ao `.gitignore` pra não commitar a chave.

**Se Anthropic / Gemini / Ollama**:

DeepEval suporta nativamente. Você precisa instalar o extra correspondente e configurar. Os providers nativos:
- OpenAI (default)
- Anthropic
- Gemini
- Azure OpenAI
- Ollama (local, sem API key)
- Vertex AI
- Bedrock (AWS)

Pra qualquer um destes, você passa o modelo na hora de criar a métrica:

```python
from deepeval.metrics import GEval
metric = GEval(name="Correctness", criteria="...", model="claude-3-5-sonnet")
```

**Se modelo totalmente customizado** (vLLM, OpenRouter, qualquer endpoint OpenAI-compatible, modelo local):

Avise o usuário: "Pra modelo custom, você precisa criar uma classe que herda de `DeepEvalBaseLLM` e implementa `generate()` e `a_generate()`. Eu não vou fazer isso aqui porque é configuração específica do seu setup. Quer que eu te dê o template de classe pra você adaptar?"

Template básico (dê se ele pedir):

```python
from deepeval.models import DeepEvalBaseLLM
from openai import OpenAI

class CustomVLLMModel(DeepEvalBaseLLM):
    def __init__(self, base_url: str, model_name: str):
        self.client = OpenAI(base_url=base_url, api_key="not-needed")
        self.model_name = model_name

    def load_model(self):
        return self.client

    def generate(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

    async def a_generate(self, prompt: str) -> str:
        return self.generate(prompt)  # ou implementar async real

    def get_model_name(self) -> str:
        return self.model_name

# Uso:
custom_model = CustomVLLMModel(base_url="http://localhost:8000/v1", model_name="qwen3-30b-a3b")
metric = GEval(name="Correctness", criteria="...", model=custom_model)
```

## Passo 3 — (Opcional mas recomendado) Login no Confident AI

Confident AI é a plataforma cloud do DeepEval. **Não é obrigatório** — você consegue rodar tudo local. Mas tem benefícios grandes:

- Visualização de traces (gráfico interativo de execução do agent)
- Avaliação assíncrona em produção (zero latência)
- Dataset management colaborativo
- Regression testing visual (compara runs lado a lado)
- Compartilhar relatórios com o time

**Plano free é suficiente pra começar.**

Pergunte: "Quer logar no Confident AI agora? É grátis pra começar e ajuda muito a visualizar resultados. Se preferir só local por enquanto, podemos pular."

### Se sim:

```bash
deepeval login
```

Isso abre o navegador, ele faz login, copia uma API key, cola no terminal. Depois disso, qualquer test run é exportado automaticamente pro dashboard.

Alternativa via env var:

```bash
export CONFIDENT_API_KEY="confident_us..."
```

Ou no `.env.local`:

```
CONFIDENT_API_KEY=confident_us...
```

### Se não:

Beleza, segue local. Os resultados aparecem só no terminal e em arquivos JSON locais. Pra controlar onde salvam:

```bash
export DEEPEVAL_RESULTS_FOLDER="./eval-results"
```

## Passo 4 — Smoke test

Antes de declarar setup pronto, rode um teste mínimo. Crie um arquivo `test_setup.py`:

```python
from deepeval import assert_test
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from deepeval.metrics import GEval

def test_smoke():
    metric = GEval(
        name="Correctness",
        criteria="Determine if the actual output is factually correct based on the expected output.",
        evaluation_params=[LLMTestCaseParams.ACTUAL_OUTPUT, LLMTestCaseParams.EXPECTED_OUTPUT],
        threshold=0.5,
    )
    test_case = LLMTestCase(
        input="What is 2+2?",
        actual_output="4",
        expected_output="4",
    )
    assert_test(test_case, [metric])
```

Rode:

```bash
deepeval test run test_setup.py
```

Se passar → setup completo. Se errar:

| Erro | Causa | Fix |
|------|-------|-----|
| `OpenAI rate limit` ou `insufficient_quota` | Sem créditos na conta OpenAI | Adicione créditos ou troque pra outro modelo |
| `OPENAI_API_KEY not set` | Chave não exportada | Reexporte ou veja se `.env.local` está na raiz |
| `ModuleNotFoundError: deepeval` | Instalação no venv errado | Confira `which python` e `pip show deepeval` no mesmo venv |
| `Connection timeout` | Firewall corporativo | Configure proxy ou use Ollama local |

### Sobre retries

Por padrão, DeepEval faz **retry de 1 vez** (2 tentativas total) pra erros transientes:
- Network timeouts e erros 5xx → retry
- Rate limits 429 → retry, exceto se for `insufficient_quota` (esse não)
- Backoff exponencial: 1s inicial, base 2, jitter 2s, cap 5s

Se quiser tunar, use env vars (sem mudar código). Detalhes na FAQ do deepeval ou pergunte aqui que eu te falo.

## Passo 5 — Estrutura de arquivos sugerida

Pra projeto novo, sugira esta estrutura:

```
seu-projeto/
├── .env.local                # chaves (gitignored)
├── .env.example              # template sem chaves (commitado)
├── .gitignore                # inclui .env.local e eval-results/
├── pyproject.toml            # ou requirements.txt com deepeval
├── src/
│   └── seu_agent.py          # código do agent (a ser instrumentado)
├── evals/
│   ├── __init__.py
│   ├── datasets/
│   │   └── goldens.json      # ou .csv
│   ├── metrics/
│   │   └── custom_metrics.py # G-Eval custom
│   ├── test_agent_evals.py   # arquivos pytest pro deepeval test run
│   └── run_evals.py          # script standalone pra rodar via python
└── eval-results/             # gitignored
```

Não force essa estrutura — ofereça como sugestão se ele perguntar.

## Variáveis de ambiente úteis

| Variável | O que faz |
|----------|-----------|
| `OPENAI_API_KEY` | Chave OpenAI pro LLM-as-judge |
| `CONFIDENT_API_KEY` | Chave Confident AI |
| `DEEPEVAL_RESULTS_FOLDER` | Onde salvar resultados local (default: pasta atual) |
| `DEEPEVAL_DISABLE_DOTENV` | `1` desliga autoload de `.env` |
| `DEEPEVAL_TELEMETRY_OPT_OUT` | `1` desliga telemetria |
| `DEEPEVAL_VERBOSE_MODE` | `1` printa intermediários |

## Checklist final

Antes de declarar setup completo, confirme com o usuário:

- [ ] `python -c "import deepeval; print(deepeval.__version__)"` retorna versão
- [ ] Tem chave LLM configurada (`OPENAI_API_KEY` ou outro provider)
- [ ] Smoke test (`test_setup.py`) passou com `deepeval test run`
- [ ] (Opcional) Logado no Confident AI
- [ ] `.env.local` está no `.gitignore`

## Encerramento

Após confirmar, diga:

> "Setup completo. O próximo passo é instrumentar o seu agent com `@observe` pra DeepEval enxergar a árvore de execução. Quer que eu chame `bagual-ai-evals-instrument` agora?"

## Anti-patterns

- ❌ Pular o smoke test — sem validação você não sabe se realmente funciona
- ❌ Mandar instalar sem venv — vai conflitar com outros projetos
- ❌ Esquecer de avisar do `.gitignore` pra `.env.local`
- ❌ Forçar Confident AI — é opcional, alguns querem 100% local
- ❌ Despejar todas as env vars de uma vez sem o usuário precisar
