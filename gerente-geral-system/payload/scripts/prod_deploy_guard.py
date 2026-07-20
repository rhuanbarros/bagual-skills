#!/usr/bin/env python3
"""prod_deploy_guard.py — hook `PreToolUse` que nega mecanicamente comandos `Bash` que
disparam deploy/migração de Produção quando quem chama a tool é um agente (sub-agente
despachado, ou uma persona nativa como `gerente-geral`) — nunca a sessão interativa do
dono. Mesmo espírito de `project_controll/gerente/scripts/gerente_tool_guard.py` (E15.1),
aplicado à superfície `Bash` em vez de `Edit`/`Write`/`NotebookEdit`.

Por que isto existe: a regra "Produção — só com autorização EXPRESSA do dono" costuma
viver só em prosa (`AGENTS.md`/`CLAUDE.md` do projeto-destino, ou o equivalente): nenhum
agente roda `make deploy-*-production` / `make migrate-production`, nem escreve no banco
de Produção. Este script é o backstop MECÂNICO que não depende só da persona se
lembrar/obedecer a prosa.

Contrato do hook `PreToolUse` (mesmo confirmado ao vivo em `gerente_tool_guard.py`): o
processo recebe no stdin um JSON com `agent_type` (presente só dentro de um sub-agente ou
de uma sessão `--agent`/agente nativo; ausente na sessão interativa do dono),
`tool_name`, `tool_input` (para `Bash`, o campo `command`), `cwd`. Deny é sinalizado
imprimindo `{"hookSpecificOutput": {...}}` no stdout; silêncio = fluxo normal de
permissão.

Escopo deliberadamente ESTREITO (fail-safe por composição com o resto do sistema, não por
tentar adivinhar todo padrão de comando perigoso):
  1. `make <alvo>` onde `<alvo>` é um dos 3 alvos de Produção do Makefile:
     `deploy-frontend-production`, `deploy-backend-production`, `migrate-production`.
  2. Qualquer comando que referencie o env var `SUPABASE_PROD_DB_URL` (o nome mesmo do
     var já é o sinal — normalmente a única connection string de produção que o Makefile
     do projeto-destino usa).

Por que casar no NOME dos alvos/env var em vez do VALOR de uma ref de projeto Supabase
específica: os dois sinais acima (alvo `make` explícito de produção, ou o nome do env var
`SUPABASE_PROD_DB_URL`) continuam válidos mesmo que o projeto-destino ainda não tenha
separado fisicamente seus projetos Supabase de dev/staging/produção (uma simplificação
comum logo no início de um projeto) — casar por VALOR de ref exigiria reconfigurar o
guard a cada projeto-destino; casar pelo NOME do alvo/env var funciona sem porting assim
que o `Makefile` do projeto-destino define `PROD_PROJECT_REF`/`DEV_PROJECT_REF` com
valores reais.

Nunca bloqueia leitura de produção (diagnóstico) — só os 2 sinais de escrita/deploy
acima. Nunca bloqueia a sessão interativa do dono (`agent_type` ausente): "Leitura de
produção para diagnóstico é permitida; escrita não... deixe a instrução exata para o
dono rodar."

Uso (chamado pelo harness via `.claude/settings.json` § hooks.PreToolUse, matcher `Bash`,
stdin = JSON do hook):
    python3 prod_deploy_guard.py

Também pode ser invocado manualmente para depuração/self-test:
    echo '{"agent_type":"gerente-geral","tool_name":"Bash",
           "tool_input":{"command":"make deploy-frontend-production"}}' \
      | python3 prod_deploy_guard.py

Sem dependências externas (stdlib apenas: json, re, sys).
"""
from __future__ import annotations

import json
import re
import sys

GUARDED_TOOLS = {"Bash"}

BLOCKED_MAKE_TARGETS = (
    "deploy-frontend-production",
    "deploy-backend-production",
    "migrate-production",
)
_MAKE_TARGET_PATTERN = re.compile(
    r"\bmake\b[^\n;&|]*\b(" + "|".join(re.escape(t) for t in BLOCKED_MAKE_TARGETS) + r")\b"
)
_PROD_DB_URL_VAR = "SUPABASE_PROD_DB_URL"


def matched_signal(command: str) -> str:
    """Decide se `command` bate um dos 2 sinais de Produção. Retorna a descrição do
    sinal batido (não-vazia) ou string vazia quando nada bate — path vazio/None nunca
    é bloqueado (nada para checar)."""
    if not command:
        return ""

    m = _MAKE_TARGET_PATTERN.search(command)
    if m:
        return f"make target de producao: {m.group(1)}"

    if _PROD_DB_URL_VAR in command:
        return f"referencia ao env var {_PROD_DB_URL_VAR}"

    return ""


def evaluate(payload: dict) -> dict | None:
    """Decide a ação do guard para um payload de hook `PreToolUse` já parseado.

    Retorna `None` quando o guard não tem nada a dizer (deixa a permission flow normal
    decidir) — cobre: `agent_type` ausente (sessão interativa do dono), tool != `Bash`,
    ou comando que não bate nenhum sinal de Produção. Retorna o dict de
    `hookSpecificOutput` (pronto para `json.dumps`) só quando a decisão é `deny`.
    """
    agent_type = payload.get("agent_type")
    if not agent_type:
        return None

    tool_name = payload.get("tool_name")
    if tool_name not in GUARDED_TOOLS:
        return None

    tool_input = payload.get("tool_input") or {}
    command = str(tool_input.get("command") or "")

    signal = matched_signal(command)
    if not signal:
        return None

    reason = (
        "Producao e exclusiva do dono. Nenhum agente (agent_type="
        f"'{agent_type}') roda deploy/migracao de Producao -- comando bate {signal}. "
        "Leitura de producao para diagnostico continua liberada; so escrita/deploy "
        "e negado. Peca para o dono rodar este comando ele mesmo, na sessao dele."
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def main() -> int:
    raw_stdin = sys.stdin.read()
    try:
        payload = json.loads(raw_stdin) if raw_stdin.strip() else {}
    except json.JSONDecodeError:
        # Input malformado nunca deve travar o harness inteiro -- sem output, cai no
        # fluxo de permissao normal (mesma semantica de "silencio = normal flow").
        return 0

    decision = evaluate(payload)
    if decision is not None:
        print(json.dumps(decision))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
