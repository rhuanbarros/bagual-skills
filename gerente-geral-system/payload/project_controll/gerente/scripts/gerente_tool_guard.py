#!/usr/bin/env python3
"""gerente_tool_guard.py — hook `PreToolUse` que bloqueia mecanicamente `Edit`/`Write`/
`NotebookEdit` sobre código de produto quando quem chama a tool é a persona nativa
`gerente-geral` (Story E15.1, T2.1 — Epic E15, hardening comportamental -> mecânico).

Contrato do hook `PreToolUse` (docs oficiais do harness, confirmadas ao vivo nesta
story): o processo recebe no stdin um JSON com (entre outros) `agent_type` — presente
só quando a chamada acontece dentro de um sub-agente ou de uma sessão `--agent`; para um
agente nativo custom (`.claude/agents/<nome>.md`) o valor é exatamente o campo `name` do
frontmatter, não o nome do arquivo — aqui, `"gerente-geral"`. Isso é o que torna este
guard escopado SÓ à persona `gerente-geral`: qualquer outra sessão (interativa do dono,
ou um sub-agente despachado pelo próprio Gerente rodando `bmad-quick-dev`/
`bagual-epic-runner`/etc., cujo `agent_type` é outro valor ou está ausente) nunca bate
neste bloqueio, mesmo compartilhando o mesmo `.claude/settings.json`.

Por que hook (`PreToolUse`), não exclusão no `tools:` do frontmatter do agente
(a Opção A descartada — ver Entrada de Ledger que esta story transiciona,
`agente-persona-nativo-tools-sem-restricao-ate-teste-real`): o `tools:` do frontmatter é
um allowlist GROSSEIRO por NOME de tool inteiro, sem escopo por path — remover
`Edit`/`Write`/`NotebookEdit` da lista bloquearia TAMBÉM as duas escritas diretas
legítimas que `gerente-geral.md` já documenta (exceção (d) — os 3 documentos canônicos
WDS; e a escrita de Entradas de Ledger não-oráculo) já que nenhuma das duas passa por
script hoje. Um hook `PreToolUse` escopado por PATH resolve isso: bloqueia só os globs de
código de produto, deixando toda outra escrita (Ledger, WDS, Tickets) livre — e nunca
toca a lista `tools:` do agente, então não há nenhum risco (o motivo original que esta
story supera) de quebrar silenciosamente a resolução de tools carregadas via
`ToolSearch` (o mecanismo de tools deferidas nem é tocado por este guard).

Globs bloqueados (produção + superfície de skill/agente BMad — nunca fork de `bmad-*`):
  - `frontend/**`
  - `backend/**`
  - `supabase/**`
  - qualquer segmento de path que comece com `bmad-` (ex.: `.claude/skills/bmad-quick-dev/**`)
  - qualquer segmento de path que comece com `bagual-` (ex.: `.claude/skills/bagual-tickets/**`)

Uso (chamado pelo harness via `.claude/settings.json` § hooks.PreToolUse, matcher
`Edit|Write|NotebookEdit`, stdin = JSON do hook):
    python3 gerente_tool_guard.py

Também pode ser invocado manualmente para depuração/self-test, passando o JSON por stdin:
    echo '{"agent_type":"gerente-geral","tool_name":"Edit",
           "tool_input":{"file_path":"/repo/frontend/x.ts"},"cwd":"/repo"}' \
      | python3 gerente_tool_guard.py

Sem dependências externas (stdlib apenas: json, sys, posixpath).
"""
from __future__ import annotations

import json
import sys
from pathlib import PurePosixPath

GUARDED_AGENT_TYPE = "gerente-geral"
GUARDED_TOOLS = {"Edit", "Write", "NotebookEdit"}
BLOCKED_EXACT_SEGMENTS = {"frontend", "backend", "supabase"}
BLOCKED_SEGMENT_PREFIXES = ("bmad-", "bagual-")


def _extract_file_path(tool_name: str, tool_input: dict) -> str:
    """Extrai o path do arquivo-alvo do `tool_input`, por tool.

    `Edit`/`Write` usam `file_path`; `NotebookEdit` usa `notebook_path`. Path ausente/
    vazio nunca é tratado como bloqueio (nada para checar).
    """
    if tool_name == "NotebookEdit":
        return str(tool_input.get("notebook_path") or "")
    return str(tool_input.get("file_path") or "")


def is_blocked_path(raw_path: str, cwd: str = "") -> tuple[bool, str]:
    """Decide se `raw_path` cai num glob de código de produto/skill BMad.

    Retorna `(blocked, matched_glob_description)`. `matched_glob_description` só é
    significativo quando `blocked` é True — vira parte da `permissionDecisionReason`
    devolvida ao harness.

    Estratégia — varredura de SEGMENTOS de path, deliberadamente sem depender de
    `raw_path` estar relativizado contra `cwd` (o hook sempre recebe `file_path`
    absoluto na prática, mas um path relativo funciona igual): (1) qualquer segmento
    IGUAL a `frontend`/`backend`/`supabase` bloqueia (`{segmento}/**`); (2) qualquer
    segmento que COMECE com `bmad-`/`bagual-` bloqueia (cobre `.claude/skills/bmad-*/**`
    e `.claude/skills/bagual-*/**` em qualquer profundidade, sem hardcodar
    `.claude/skills/`). `cwd` é aceito por simetria com o payload do hook e para uso
    futuro (ex.: normalizar path relativo -> absoluto), mas a decisão de bloqueio em si
    é fail-safe por design: um path fora do `cwd` esperado (ex. symlink, worktree
    inesperado) ainda é escaneado pelos mesmos segmentos, nunca liberado por engano só
    por não bater um prefixo relativo. Um path vazio nunca é bloqueado (nada para
    checar).
    """
    if not raw_path:
        return False, ""

    posix_raw = raw_path.replace("\\", "/")
    p = PurePosixPath(posix_raw)

    for seg in p.parts:
        if seg in BLOCKED_EXACT_SEGMENTS:
            return True, f"{seg}/**"
        for prefix in BLOCKED_SEGMENT_PREFIXES:
            if seg.startswith(prefix):
                return True, f"**/{seg}/**"

    return False, ""


def evaluate(payload: dict) -> dict | None:
    """Decide a ação do guard para um payload de hook `PreToolUse` já parseado.

    Retorna `None` quando o guard não tem nada a dizer (deixa a permission flow normal
    decidir) — cobre: agente != `gerente-geral`, tool fora de {Edit, Write, NotebookEdit},
    ou path que não bate nenhum glob bloqueado. Retorna o dict de `hookSpecificOutput`
    (pronto para `json.dumps`) só quando a decisão é `deny`.
    """
    if payload.get("agent_type") != GUARDED_AGENT_TYPE:
        return None

    tool_name = payload.get("tool_name")
    if tool_name not in GUARDED_TOOLS:
        return None

    tool_input = payload.get("tool_input") or {}
    file_path = _extract_file_path(tool_name, tool_input)
    cwd = str(payload.get("cwd") or "")

    blocked, matched = is_blocked_path(file_path, cwd)
    if not blocked:
        return None

    reason = (
        "E15.1: a persona gerente-geral nunca edita codigo de producto/skills BMad "
        f"diretamente (path bate {matched}). Toda mudanca de codigo acontece num "
        "sub-agente Sonnet despachado via Agent/Skill -- nunca dentro do proprio "
        "contexto da persona. Ledger nao-oraculo, os 3 documentos canonicos WDS "
        "(excecao (d), E9.8) e Tickets continuam liberados."
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
