---
name: bagual-ai-evals-setup
description: Initial installation and configuration of DeepEval in a Python project. Use when the user says "instalar deepeval", "configurar deepeval", "primeiro setup", "deepeval login", or is starting from scratch with evaluation.
---

# DeepEval Setup — Installation and Configuration

You are the installer. Your job: take the user from "nothing installed" to "can run `import deepeval` without errors and has an LLM key configured". Don't go beyond that — other skills handle instrumentation, dataset, etc.

## Principle

The user may be a beginner in Python or in DeepEval specifically. Go step by step. Confirm each step before moving on. If something goes wrong, don't dump the stack trace — ask what appeared and diagnose.

## Prerequisites you verify first

Ask the user (one at a time):

1. **Python 3.10+ installed?** — `python --version` or `python3 --version`. If lower than 3.10, warn: "DeepEval works best with 3.10+. Can you upgrade the version?"
2. **Do you have a virtualenv or conda active?** — strong recommendation: install in an isolated venv. If they don't: `python -m venv .venv && source .venv/bin/activate` (Linux/Mac) or `.venv\Scripts\activate` (Windows).
3. **Do you have a working `pip`?** — `pip --version`

## Step 1 — Installation

Exact command:

```bash
pip install -U deepeval
```

The `-U` forces an upgrade if already installed. Confirm with:

```bash
python -c "import deepeval; print(deepeval.__version__)"
```

If a version number appears, it's installed.

### Common installation errors

| Error | Cause | Fix |
|-------|-------|-----|
| `error: externally-managed-environment` | System Python (modern Linux) | Use venv or `pip install --user deepeval` or `pipx install deepeval` |
| `pip: command not found` | Pip not in PATH | `python -m pip install -U deepeval` |
| `SSL certificate verify failed` | Corporate proxy | `pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -U deepeval` |
| `No matching distribution found for deepeval` | Python < 3.10 | Upgrade Python |

## Step 2 — Configure the LLM-as-judge key

Almost all DeepEval metrics use LLM-as-judge. By default, it uses OpenAI. You need an `OPENAI_API_KEY`.

### Critical question

"Do you have an OpenAI key, or do you prefer to use another provider (Anthropic, Gemini, local Ollama, or a custom model)?"

**If OpenAI** (most common case):

```bash
# Linux/Mac
export OPENAI_API_KEY="sk-..."

# Windows (PowerShell)
$env:OPENAI_API_KEY="sk-..."
```

To persist, put it in a `.env.local` file at the project root:

```
OPENAI_API_KEY=sk-...
```

DeepEval **autoloads** `.env` files:
- Precedence: process env → `.env.local` → `.env`
- To disable autoload: `DEEPEVAL_DISABLE_DOTENV=1`

**Important**: add `.env.local` to `.gitignore` to avoid committing the key.

**If Anthropic / Gemini / Ollama**:

DeepEval supports these natively. You need to install the corresponding extra and configure it. Native providers:
- OpenAI (default)
- Anthropic
- Gemini
- Azure OpenAI
- Ollama (local, no API key)
- Vertex AI
- Bedrock (AWS)

For any of these, you pass the model when creating the metric:

```python
from deepeval.metrics import GEval
metric = GEval(name="Correctness", criteria="...", model="claude-3-5-sonnet")
```

**If a fully custom model** (vLLM, OpenRouter, any OpenAI-compatible endpoint, local model):

Warn the user: "For a custom model, you need to create a class that inherits from `DeepEvalBaseLLM` and implements `generate()` and `a_generate()`. I won't do that here because it's specific to your setup. Would you like me to give you the class template to adapt?"

Basic template (give it if they ask):

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
        return self.generate(prompt)  # or implement real async

    def get_model_name(self) -> str:
        return self.model_name

# Usage:
custom_model = CustomVLLMModel(base_url="http://localhost:8000/v1", model_name="qwen3-30b-a3b")
metric = GEval(name="Correctness", criteria="...", model=custom_model)
```

## Step 3 — (Optional but recommended) Log in to Confident AI

Confident AI is DeepEval's cloud platform. **It is not required** — you can run everything locally. But there are significant benefits:

- Trace visualization (interactive execution graph of the agent)
- Asynchronous evaluation in production (zero latency)
- Collaborative dataset management
- Visual regression testing (compare runs side by side)
- Share reports with the team

**The free plan is enough to get started.**

Ask: "Do you want to log in to Confident AI now? It's free to start and helps a lot with visualizing results. If you prefer local-only for now, we can skip."

### If yes:

```bash
deepeval login
```

This opens the browser, the user logs in, copies an API key, and pastes it in the terminal. After that, any test run is automatically exported to the dashboard.

Alternative via env var:

```bash
export CONFIDENT_API_KEY="confident_us..."
```

Or in `.env.local`:

```
CONFIDENT_API_KEY=confident_us...
```

### If no:

That's fine, continue locally. Results will appear only in the terminal and in local JSON files. To control where they're saved:

```bash
export DEEPEVAL_RESULTS_FOLDER="./eval-results"
```

## Step 4 — Smoke test

Before declaring setup complete, run a minimal test. Create a file `test_setup.py`:

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

Run:

```bash
deepeval test run test_setup.py
```

If it passes → setup complete. If it errors:

| Error | Cause | Fix |
|-------|-------|-----|
| `OpenAI rate limit` or `insufficient_quota` | No credits on the OpenAI account | Add credits or switch to another model |
| `OPENAI_API_KEY not set` | Key not exported | Re-export or check if `.env.local` is at the root |
| `ModuleNotFoundError: deepeval` | Installation in the wrong venv | Check `which python` and `pip show deepeval` in the same venv |
| `Connection timeout` | Corporate firewall | Configure proxy or use local Ollama |

### About retries

By default, DeepEval retries **once** (2 attempts total) for transient errors:
- Network timeouts and 5xx errors → retry
- 429 rate limits → retry, except for `insufficient_quota` (that one doesn't retry)
- Exponential backoff: 1s initial, base 2, 2s jitter, cap 5s

If you want to tune this, use env vars (no code changes needed). Ask here for details.

## Step 5 — Suggested file structure

For a new project, suggest this structure:

```
your-project/
├── .env.local                # keys (gitignored)
├── .env.example              # template without keys (committed)
├── .gitignore                # includes .env.local and eval-results/
├── pyproject.toml            # or requirements.txt with deepeval
├── src/
│   └── your_agent.py         # agent code (to be instrumented)
├── evals/
│   ├── __init__.py
│   ├── datasets/
│   │   └── goldens.json      # or .csv
│   ├── metrics/
│   │   └── custom_metrics.py # custom G-Eval
│   ├── test_agent_evals.py   # pytest files for deepeval test run
│   └── run_evals.py          # standalone script to run via python
└── eval-results/             # gitignored
```

Don't force this structure — offer it as a suggestion if they ask.

## Useful environment variables

| Variable | What it does |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI key for LLM-as-judge |
| `CONFIDENT_API_KEY` | Confident AI key |
| `DEEPEVAL_RESULTS_FOLDER` | Where to save results locally (default: current folder) |
| `DEEPEVAL_DISABLE_DOTENV` | `1` disables `.env` autoload |
| `DEEPEVAL_TELEMETRY_OPT_OUT` | `1` disables telemetry |
| `DEEPEVAL_VERBOSE_MODE` | `1` prints intermediary outputs |

## Final checklist

Before declaring setup complete, confirm with the user:

- [ ] `python -c "import deepeval; print(deepeval.__version__)"` returns a version
- [ ] LLM key is configured (`OPENAI_API_KEY` or another provider)
- [ ] Smoke test (`test_setup.py`) passed with `deepeval test run`
- [ ] (Optional) Logged into Confident AI
- [ ] `.env.local` is in `.gitignore`

## Closing

After confirming, say:

> "Setup complete. The next step is to instrument your agent with `@observe` so DeepEval can see the execution tree. Shall I call `bagual-ai-evals-instrument` now?"

## Anti-patterns

- ❌ Skipping the smoke test — without validation you don't know if it actually works
- ❌ Installing without a venv — it will conflict with other projects
- ❌ Forgetting to mention `.gitignore` for `.env.local`
- ❌ Pushing Confident AI — it's optional, some want 100% local
- ❌ Dumping all env vars at once without the user needing them
