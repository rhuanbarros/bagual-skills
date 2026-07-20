#!/usr/bin/env python3
"""test_prod_deploy_guard.py — provas reais (subprocess, stdin JSON de verdade) do guard
mecânico `prod_deploy_guard.py`.

Espelha `project_controll/gerente/scripts/test_gerente_tool_guard.py` (mesmo estilo:
subprocess real, sem mocks, JSON no stdin exatamente como o harness invoca). Cobre:

  1. `make deploy-frontend-production`/`deploy-backend-production`/`migrate-production`
     com `agent_type` presente -> `permissionDecision: deny`.
  2. Referência ao env var `SUPABASE_PROD_DB_URL` com `agent_type` presente -> `deny`.
  3. Os mesmos comandos exatos, sem `agent_type` (sessão interativa do dono) -> sem
     decisão -- prova que o dono nunca é bloqueado.
  4. Alvos de staging/dev (`deploy-frontend-staging`, `migrate-staging`) com `agent_type`
     presente -> sem decisão -- prova que o guard casa pelo NOME do alvo, não por um
     projeto Supabase específico (ver docstring do guard).
  5. Tool fora de `Bash` (ex.: `Edit`) com `agent_type` presente -> sem decisão, mesmo
     com comando de produção no payload (o guard só existe para `Bash`).
  6. Payload malformado (JSON inválido, campos ausentes) -> exit 0, sem crash, sem
     decisão -- nunca trava o harness.
  7. `matched_signal` isolado (sem subprocess) para as bordas (comando vazio/None,
     substring que não é o var exato, alvo make dentro de uma linha maior).

Sem dependências externas (stdlib apenas: subprocess, json, sys).

Uso:
    python3 test_prod_deploy_guard.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GUARD_SCRIPT = HERE / "prod_deploy_guard.py"

sys.path.insert(0, str(HERE))
import prod_deploy_guard as guard  # noqa: E402  (import after sys.path tweak)

PASS = 0
FAIL = 0


def check(label: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ok   {label}")
    else:
        FAIL += 1
        print(f"  FAIL {label}  {detail}")


def run_guard(payload: dict | None, raw_stdin: str | None = None) -> subprocess.CompletedProcess:
    stdin_text = raw_stdin if raw_stdin is not None else json.dumps(payload)
    return subprocess.run(
        [sys.executable, str(GUARD_SCRIPT)],
        input=stdin_text,
        capture_output=True,
        text=True,
    )


def decision_of(proc: subprocess.CompletedProcess) -> dict | None:
    out = proc.stdout.strip()
    if not out:
        return None
    return json.loads(out)


def make_payload(agent_type: str | None, command: str, tool_name: str = "Bash") -> dict:
    payload = {"tool_name": tool_name, "tool_input": {"command": command}, "cwd": "/repo"}
    if agent_type is not None:
        payload["agent_type"] = agent_type
    return payload


def main() -> int:
    print("\n[1] alvos make de producao, agent_type presente -> deny")
    for cmd in (
        "make deploy-frontend-production",
        "make deploy-backend-production",
        "make migrate-production",
        "cd /repo && make migrate-production && echo done",
    ):
        proc = run_guard(make_payload("gerente-geral", cmd))
        d = decision_of(proc)
        check(
            f"deny: {cmd!r}",
            d is not None and d["hookSpecificOutput"]["permissionDecision"] == "deny",
            detail=str(d),
        )

    print("\n[2] referencia a SUPABASE_PROD_DB_URL, agent_type presente -> deny")
    for cmd in (
        "echo $SUPABASE_PROD_DB_URL",
        "npx supabase db push --db-url \"$SUPABASE_PROD_DB_URL\" --include-all --yes",
    ):
        proc = run_guard(make_payload("general-purpose", cmd))
        d = decision_of(proc)
        check(f"deny: {cmd!r}", d is not None, detail=str(d))

    print("\n[3] mesmos comandos, sem agent_type (dono interativo) -> sem decisao")
    for cmd in ("make deploy-frontend-production", "make migrate-production", "echo $SUPABASE_PROD_DB_URL"):
        proc = run_guard(make_payload(None, cmd))
        d = decision_of(proc)
        check(f"sem decisao (dono): {cmd!r}", d is None, detail=str(d))

    print("\n[4] alvos staging/dev, agent_type presente -> sem decisao")
    for cmd in ("make deploy-frontend-staging", "make migrate-staging", "make deploy-backend-dev"):
        proc = run_guard(make_payload("gerente-geral", cmd))
        d = decision_of(proc)
        check(f"sem decisao (staging/dev): {cmd!r}", d is None, detail=str(d))

    print("\n[5] tool fora de Bash, agent_type presente -> sem decisao")
    proc = run_guard(make_payload("gerente-geral", "make migrate-production", tool_name="Edit"))
    d = decision_of(proc)
    check("sem decisao (tool=Edit)", d is None, detail=str(d))

    print("\n[6] payload malformado -> exit 0, sem crash, sem decisao")
    proc = run_guard(None, raw_stdin="{nao e json valido")
    check("exit 0 em JSON invalido", proc.returncode == 0, detail=f"returncode={proc.returncode}")
    check("sem decisao em JSON invalido", decision_of(proc) is None)

    proc = run_guard(None, raw_stdin="")
    check("exit 0 em stdin vazio", proc.returncode == 0, detail=f"returncode={proc.returncode}")

    proc = run_guard({"agent_type": "gerente-geral"})
    check("exit 0 sem tool_name/tool_input", proc.returncode == 0, detail=f"returncode={proc.returncode}")

    print("\n[7] matched_signal isolado (sem subprocess) -- bordas")
    check("comando vazio nunca bloqueia", guard.matched_signal("") == "")
    check("comando None-like (str vazia) nunca bloqueia", guard.matched_signal("") == "")
    check(
        "substring 'production' sem alvo make exato nao bloqueia",
        guard.matched_signal("echo production is cool") == "",
    )
    check(
        "alvo make dentro de linha maior ainda bloqueia",
        bool(guard.matched_signal("set -e && make deploy-backend-production 2>&1 | tee log")),
    )
    check(
        "SUPABASE_PROD_DB_URL como substring de outro nome nao falso-positiva ao contrario (var exato ainda bate)",
        bool(guard.matched_signal("export SUPABASE_PROD_DB_URL=postgres://...")),
    )

    print(f"\nPASS: {PASS}  FAIL: {FAIL}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
