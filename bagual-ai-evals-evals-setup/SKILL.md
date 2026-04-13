---
name: bagual-ai-evals-evals-setup
description: Installs the DeepEval Evals module into a BMad project. Use when the user says "instalar bagual-evals", "setup deepeval module", "registrar deepeval no bmad", or similar.
---

# DeepEval Evals — Module Setup

## Overview

Installs and configures the DeepEval Evals module into this BMad project. Module identity comes from `./assets/module.yaml`. Registers all 10 skills into the BMad help system and configures the output path for evaluation artifacts.

**Args:** Accepts `-H` / `--headless` for non-interactive execution, or inline values like `output folder is eval-artifacts`.

**Output:** Updates `{project-root}/_bmad/config.yaml`, `{project-root}/_bmad/config.user.yaml`, and `{project-root}/_bmad/module-help.csv`.

---

## On Activation

1. Read `./assets/module.yaml` to load module metadata (`code`, `name`, `module_version`, variables with prompts/defaults).

2. If the user passed `-H` or `--headless`, set `headless_mode=true` and skip all interactive prompts — use defaults for everything.

3. Check whether `{project-root}/_bmad/config.yaml` already contains a section with `code: dev-evals`. If yes, this is an **update** — tell the user.

## Collect Configuration

Ask the user for values. Show defaults in brackets. Present all values together so the user can answer once with only the ones they want to change.

**Core config** (only if not already set in `{project-root}/_bmad/config.yaml`):
- `output_folder` — default: `{project-root}/_bmad-output`
- `communication_language` and `document_output_language` — ask as a single language question

**Module config** (from `./assets/module.yaml`):
- `eval_output_folder` — where evaluation artifacts (plans, reports, datasets) are saved. Default: `{project-root}/eval-artifacts`

## Write Config Files

### 1. `{project-root}/_bmad/config.yaml`

If the file does not exist, create it. If it exists and already has a `dev-evals` section, replace that section entirely. Never leave stale entries.

Add or update:
```yaml
output_folder: {project-root}/_bmad-output       # only if not already set at root

modules:
  dev-evals:
    name: DeepEval Evals
    version: 1.1.0
    eval_output_folder: {collected_eval_output_folder}
```

Use literal `{project-root}` as a token — do not resolve to an absolute path.

### 2. `{project-root}/_bmad/config.user.yaml`

If `user_name` or `communication_language` were collected, add them here (these are personal settings that should be gitignored):
```yaml
user_name: {user_name}
communication_language: {communication_language}
```

### 3. `{project-root}/_bmad/module-help.csv`

Read `./assets/module-help.csv` to get this module's skill entries.

If `{project-root}/_bmad/module-help.csv` exists:
  - Read the existing file
  - Remove all rows where `module` column equals `DeepEval Evals` (the old entries for this module)
  - Append the new entries from `./assets/module-help.csv`
  - Write the result back

If `{project-root}/_bmad/module-help.csv` does NOT exist:
  - Copy `./assets/module-help.csv` as the new file

The CSV header must appear exactly once (first line). Do not duplicate it.

## Create Output Directories

After writing config, create any directories that were configured but do not yet exist on disk. For each path-type variable in config (values starting with `{project-root}/`), resolve `{project-root}` to the actual project root and create the directory with `mkdir -p`. The stored config values must keep the literal `{project-root}` token.

Directories to create:
- Resolved `eval_output_folder` (e.g. `/path/to/project/eval-artifacts`)

## Confirmation Summary

Show the user a summary of what was written:

```
✓ Module registered: DeepEval Evals v1.1.0 (code: dev-evals)
✓ Config written:    {project-root}/_bmad/config.yaml
✓ Help CSV updated:  {project-root}/_bmad/module-help.csv  (12 entries)
✓ Output folder:     {eval_output_folder}

Skills now available:
  [DH]   bagual-ai-evals-help         — Router and diagnostic
  [DEST] bagual-ai-evals-strategy     — Eval plan document
  [DSU]  bagual-ai-evals-setup        — pip install + API keys
  [DIN]  bagual-ai-evals-instrument   — @observe decorators
  [DBD]  bagual-ai-evals-build-dataset — Goldens / dataset
  [DEA]  bagual-ai-evals-error-analysis — ⭐ Trace review (most important)
  [DPM]  bagual-ai-evals-pick-metrics  — Built-in metric selection
  [DCM]  bagual-ai-evals-custom-metric — GEval / DAGMetric
  [DRA]  bagual-ai-evals-run-and-analyze — Execute + interpret
  [DPD]  bagual-ai-evals-production   — Confident AI + CI/CD

Start with:  bagual-ai-evals-help
```

## Encerramento

Após mostrar o summary:

> "Módulo instalado. Comece com `bagual-ai-evals-help` — ele vai perguntar uma coisa de cada vez e rotear pro skill certo pro seu estágio atual."

## Anti-patterns

- ❌ Substituir `{project-root}` por um caminho absoluto nos arquivos de config — é um token literal
- ❌ Duplicar o header CSV ao fazer append
- ❌ Deixar entradas antigas de `DeepEval Evals` no CSV ao atualizar
- ❌ Criar diretórios de output sem o mkdir-p (vai falhar se path parcialmente inexistente)
