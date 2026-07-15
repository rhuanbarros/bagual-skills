#!/usr/bin/env python3
"""test_gerente_tool_guard.py — provas reais (subprocess, stdin JSON de verdade) do guard
mecânico de E15.1 (`gerente_tool_guard.py`).

Story E15.1 (T2.1, Epic E15) — testa o hook `PreToolUse` que bloqueia `Edit`/`Write`/
`NotebookEdit` de código de produto quando `agent_type == "gerente-geral"`, exatamente
como o harness o invoca (JSON no stdin, JSON de decisão no stdout, exit 0 sempre que o
input é bem-formado). Cobre:

  1. `Edit`/`Write`/`NotebookEdit` sob `frontend/**`/`backend/**`/`supabase/**` como
     `gerente-geral` -> `permissionDecision: deny`.
  2. `Edit`/`Write` sob `.claude/skills/bmad-*/**`/`.claude/skills/bagual-*/**` como
     `gerente-geral` -> `deny`.
  3. A mesma tentativa exata (mesmo path bloqueado) com `agent_type` ausente (sessão
     interativa do dono) ou com outro `agent_type` (ex.: `general-purpose`, um sub-agente
     despachado pelo próprio Gerente) -> sem decisão (guard nunca se aplica fora de
     `gerente-geral`) -- prova que o escopo é por agente, não global.
  4. Exceção (d) (os 3 documentos canônicos WDS) e a escrita de Ledger não-oráculo, como
     `gerente-geral` -> sem decisão (liberado) -- prova que a exceção sobrevive ao guard.
  5. Tools fora do conjunto guardado (`Bash`, `Read`, `Agent`, `Skill`, `Grep`) como
     `gerente-geral` -> sem decisão, mesmo com path de produto -- o guard só existe para
     `Edit`/`Write`/`NotebookEdit` (nunca amplia escopo silenciosamente).
  6. Payload malformado (JSON inválido, campos ausentes) -> exit 0, sem crash, sem
     decisão -- nunca trava o harness.
  7. `is_blocked_path` isolado (sem subprocess) para as bordas de path (path vazio,
     path relativo, path absoluto fora do `cwd`, `frontend` como substring mas não como
     segmento -- ex. `frontendesign/x.ts` NÃO deve bloquear).

Sem dependências externas (stdlib apenas: subprocess, json, sys).

Uso:
    python3 test_gerente_tool_guard.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
GUARD_SCRIPT = HERE / "gerente_tool_guard.py"
REPO_ROOT = "/home/rhuan/2_temporario/<PROJETO>"

sys.path.insert(0, str(HERE))
import gerente_tool_guard as guard  # noqa: E402  (import after sys.path tweak, mesmo padrão dos irmãos)

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


def make_payload(agent_type: str | None, tool_name: str, file_path: str, cwd: str = REPO_ROOT) -> dict:
    tool_input = {"notebook_path": file_path} if tool_name == "NotebookEdit" else {"file_path": file_path}
    payload = {
        "session_id": "test-session",
        "cwd": cwd,
        "hook_event_name": "PreToolUse",
        "tool_name": tool_name,
        "tool_input": tool_input,
    }
    if agent_type is not None:
        payload["agent_type"] = agent_type
    return payload


def section_1_blocked_frontend_backend_supabase() -> None:
    print("\n[1] gerente-geral + Edit/Write/NotebookEdit sob frontend/backend/supabase -> deny")
    cases = [
        ("Edit", f"{REPO_ROOT}/frontend/src/features/clients/page.tsx"),
        ("Write", f"{REPO_ROOT}/backend/api/clients.py"),
        ("Edit", f"{REPO_ROOT}/supabase/migrations/0099_x.sql"),
        ("NotebookEdit", f"{REPO_ROOT}/frontend/notebooks/scratch.ipynb"),
    ]
    for tool_name, path in cases:
        proc = run_guard(make_payload("gerente-geral", tool_name, path))
        decision = decision_of(proc)
        check(
            f"{tool_name} {path} -> deny",
            proc.returncode == 0
            and decision is not None
            and decision.get("hookSpecificOutput", {}).get("permissionDecision") == "deny",
            detail=f"exit={proc.returncode} decision={decision}",
        )


def section_2_blocked_skill_dirs() -> None:
    print("\n[2] gerente-geral + Edit/Write sob .claude/skills/bmad-*|bagual-*/** -> deny")
    cases = [
        ("Write", f"{REPO_ROOT}/.claude/skills/bmad-quick-dev/SKILL.md"),
        ("Edit", f"{REPO_ROOT}/.claude/skills/bagual-tickets/SKILL.md"),
        ("Edit", f"{REPO_ROOT}/.claude/skills/bagual-epic-runner/references/README.md"),
    ]
    for tool_name, path in cases:
        proc = run_guard(make_payload("gerente-geral", tool_name, path))
        decision = decision_of(proc)
        check(
            f"{tool_name} {path} -> deny",
            decision is not None
            and decision.get("hookSpecificOutput", {}).get("permissionDecision") == "deny",
            detail=f"decision={decision}",
        )


def section_3_scoped_to_gerente_geral_only() -> None:
    print("\n[3] MESMO path bloqueado, agent_type != gerente-geral (ou ausente) -> sem decisão")
    path = f"{REPO_ROOT}/frontend/src/features/vehicles/page.tsx"
    for agent_type in (None, "general-purpose", "bmad-quick-dev-subagent", "Explore"):
        proc = run_guard(make_payload(agent_type, "Edit", path))
        decision = decision_of(proc)
        check(
            f"agent_type={agent_type!r} -> sem decisão (liberado à permission flow normal)",
            proc.returncode == 0 and decision is None,
            detail=f"exit={proc.returncode} decision={decision}",
        )


def section_4_exception_d_and_ledger_survive() -> None:
    print("\n[4] Exceção (d) WDS + Ledger não-oráculo como gerente-geral -> sem decisão (liberado)")
    cases = [
        ("Write", f"{REPO_ROOT}/_bmad-output/C-UX-Scenarios/00-ux-scenarios.md"),
        ("Edit", f"{REPO_ROOT}/_bmad-output/B-Trigger-Map/trigger-map.md"),
        ("Edit", f"{REPO_ROOT}/_bmad-output/product-decisions.md"),
        ("Write", f"{REPO_ROOT}/wiki/ledger/decisao-tecnica/nova-entrada-e15-1.md"),
        ("Write", f"{REPO_ROOT}/project_controll/tickets/TCK-0001.md"),
    ]
    for tool_name, path in cases:
        proc = run_guard(make_payload("gerente-geral", tool_name, path))
        decision = decision_of(proc)
        check(
            f"{tool_name} {path} -> liberado",
            proc.returncode == 0 and decision is None,
            detail=f"decision={decision}",
        )


def section_5_other_tools_never_gated() -> None:
    print("\n[5] gerente-geral + tool fora de {Edit,Write,NotebookEdit} -> sem decisão, mesmo em path de produto")
    path = f"{REPO_ROOT}/backend/api/clients.py"
    for tool_name in ("Bash", "Read", "Agent", "Skill", "Grep", "ToolSearch"):
        payload = make_payload("gerente-geral", "Edit", path)
        payload["tool_name"] = tool_name
        payload["tool_input"] = {"command": "ls"} if tool_name == "Bash" else {"file_path": path}
        proc = run_guard(payload)
        decision = decision_of(proc)
        check(
            f"tool_name={tool_name} -> sem decisão",
            proc.returncode == 0 and decision is None,
            detail=f"decision={decision}",
        )


def section_6_malformed_input_never_crashes() -> None:
    print("\n[6] Payload malformado -> exit 0, sem crash, sem decisão")
    malformed_cases = [
        ("json inválido", "{not json at all"),
        ("stdin vazio", ""),
        ("json válido mas sem campos", "{}"),
        ("agent_type presente, tool_name ausente", json.dumps({"agent_type": "gerente-geral"})),
        (
            "tool_input ausente",
            json.dumps({"agent_type": "gerente-geral", "tool_name": "Edit"}),
        ),
    ]
    for label, raw in malformed_cases:
        proc = run_guard(None, raw_stdin=raw)
        decision = decision_of(proc)
        check(
            f"{label} -> exit 0, sem decisão",
            proc.returncode == 0 and decision is None,
            detail=f"exit={proc.returncode} stdout={proc.stdout!r} stderr={proc.stderr!r}",
        )


def section_7_is_blocked_path_unit() -> None:
    print("\n[7] is_blocked_path isolado (sem subprocess) -- bordas de path")
    cases = [
        ("", REPO_ROOT, False, "path vazio nunca bloqueia"),
        (f"{REPO_ROOT}/frontend/x.ts", REPO_ROOT, True, "frontend/** absoluto sob cwd"),
        ("frontend/x.ts", REPO_ROOT, True, "frontend/** já relativo"),
        (
            f"{REPO_ROOT}/frontendesign/x.ts",
            REPO_ROOT,
            False,
            "prefixo textual 'frontend' mas segmento != 'frontend' -- não bloqueia (evita falso-positivo)",
        ),
        (f"{REPO_ROOT}/backend/x.py", REPO_ROOT, True, "backend/**"),
        (f"{REPO_ROOT}/supabase/migrations/x.sql", REPO_ROOT, True, "supabase/**"),
        (
            f"{REPO_ROOT}/.claude/skills/bmad-dev-story/SKILL.md",
            REPO_ROOT,
            True,
            "segmento bmad-* em qualquer profundidade",
        ),
        (
            f"{REPO_ROOT}/.claude/skills/bagual-qa-run/SKILL.md",
            REPO_ROOT,
            True,
            "segmento bagual-* em qualquer profundidade",
        ),
        (
            f"{REPO_ROOT}/wiki/ledger/regra/foo.md",
            REPO_ROOT,
            False,
            "Ledger não bate nenhum glob bloqueado",
        ),
        (
            "/algum/outro/repo/frontend/x.ts",
            REPO_ROOT,
            True,
            "path absoluto fora do cwd ainda escaneia segmentos (fail-safe: bloqueia)",
        ),
    ]
    for raw_path, cwd, expected_blocked, label in cases:
        blocked, matched = guard.is_blocked_path(raw_path, cwd)
        check(
            f"{label} (path={raw_path!r})",
            blocked == expected_blocked,
            detail=f"got blocked={blocked} matched={matched!r}",
        )


def main() -> int:
    print("=== test_gerente_tool_guard.py (E15.1) ===")
    section_1_blocked_frontend_backend_supabase()
    section_2_blocked_skill_dirs()
    section_3_scoped_to_gerente_geral_only()
    section_4_exception_d_and_ledger_survive()
    section_5_other_tools_never_gated()
    section_6_malformed_input_never_crashes()
    section_7_is_blocked_path_unit()
    print(f"\nPASS: {PASS}  FAIL: {FAIL}")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
