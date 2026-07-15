#!/usr/bin/env python3
"""test_gerente_product_routing.py — provas reais (subprocessos) da Story E9.6.

Story E9.6 (ideias/sistema-artifacts/E9-6-roteamento-produto.md), PRD 05 FR-1/FR-1b.

Roda `gerente_product_routing.py check-coverage-touch` como subprocesso de verdade
(nunca mock/import direto da função) contra duas fontes:
  (a) a fixture sintética e determinística
      `project_controll/test-fixtures/E9/E9-6/coverage-matrix-fixture.md` (2
      cenários, páginas conhecidas) — cobre o mecanismo em isolamento;
  (b) o documento REAL de produto
      `_bmad-output/C-UX-Scenarios/00-ux-scenarios.md` — os "worked examples" da story,
      provando que o detector funciona contra o dado de produto de verdade, não só
      contra a fixture (mesma disciplina de calibração-contra-dado-real de E9.4/E9.5).

Prova, nesta ordem:
  [1] Match exato de página ("Clientes") bate com "Clientes (lista/novo/detalhe-editar)"
      -> `forced_route_i: true`, cenário 01 citado.
  [2] Termo que não aparece em nenhuma página -> `forced_route_i: false`, nenhum match,
      termo cai em `unmatched_touched_terms`.
  [3] Match tolerante a acento/maiúscula ("propostas admin" minúsculo/sem acento) bate
      com "Propostas Admin (lista/detalhe)" -> cenário 02.
  [4] Múltiplos termos tocados: um bate, outro não -> ambos aparecem corretamente
      classificados (`matches` vs `unmatched_touched_terms`), nunca um mascarando o
      outro.
  [5] Coverage matrix inexistente -> erro explícito, `forced_route_i: false` (nunca
      finge sucesso).
  [6] Contra o documento REAL: um termo de página real (`Propostas Admin`, cenário 03)
      força via (i); um termo que não é página nenhuma (`Relatório financeiro
      trimestral`, inventado) não força.
  [7] Regressão de um achado real de auto-revisão: termos curtos demais (artigos/
      preposições "a"/"de"/"e") NÃO geram match algum — sem o guardrail de tamanho
      mínimo, cada um desses bateria como substring em quase toda página do documento
      (achado confirmado manualmente antes da correção: `forced_route_i: true` com
      dezenas de matches espúrios para "a,de,e").

Sem dependências externas (stdlib apenas).

Uso:
    python3 test_gerente_product_routing.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = Path(__file__).resolve().parent
SCRIPT = SCRIPTS_DIR / "gerente_product_routing.py"
FIXTURE_MATRIX = (
    REPO_ROOT
    / "project_controll" / "test-fixtures"
    / "E9"
    / "E9-6"
    / "coverage-matrix-fixture.md"
)
REAL_MATRIX = REPO_ROOT / "_bmad-output" / "C-UX-Scenarios" / "00-ux-scenarios.md"

PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASS.append(name)
    else:
        FAIL.append(f"{name} :: {detail}")


def run_check(matrix_path: Path, touched: str) -> dict:
    proc = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "check-coverage-touch",
            "--coverage-matrix-path",
            str(matrix_path),
            "--touched",
            touched,
        ],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert proc.returncode == 0, f"exit != 0: {proc.stderr}"
    return json.loads(proc.stdout)


def main() -> int:
    # [1] Match exato contra a fixture.
    r1 = run_check(FIXTURE_MATRIX, "Clientes")
    check(
        "[1] 'Clientes' força via (i) contra a fixture",
        r1["forced_route_i"] is True,
        json.dumps(r1),
    )
    check(
        "[1] cenário 01 citado no match",
        any(m["scenario_id"] == "01" for m in r1["matches"]),
        json.dumps(r1),
    )

    # [2] Termo ausente.
    r2 = run_check(FIXTURE_MATRIX, "Auditoria de Compliance Regulatório")
    check(
        "[2] termo inexistente NÃO força via (i)",
        r2["forced_route_i"] is False,
        json.dumps(r2),
    )
    check(
        "[2] termo cai em unmatched_touched_terms",
        r2["unmatched_touched_terms"] == ["Auditoria de Compliance Regulatório"],
        json.dumps(r2),
    )

    # [3] Tolerância a acento/maiúscula.
    r3 = run_check(FIXTURE_MATRIX, "propostas admin")
    check(
        "[3] match tolerante a acento/caixa força via (i)",
        r3["forced_route_i"] is True and any(m["scenario_id"] == "02" for m in r3["matches"]),
        json.dumps(r3),
    )

    # [4] Múltiplos termos: um bate, outro não.
    r4 = run_check(FIXTURE_MATRIX, "Veículos,Departamento Jurídico")
    check(
        "[4] um termo bate (Veículos)",
        any(m["touched_term"] == "Veículos" for m in r4["matches"]),
        json.dumps(r4),
    )
    check(
        "[4] outro termo não bate e aparece em unmatched",
        "Departamento Jurídico" in r4["unmatched_touched_terms"],
        json.dumps(r4),
    )
    check(
        "[4] forced_route_i ainda true (basta 1 match)",
        r4["forced_route_i"] is True,
        json.dumps(r4),
    )

    # [5] Coverage matrix inexistente.
    r5 = run_check(REPO_ROOT / "project_controll" / "test-fixtures" / "E9" / "E9-6" / "nao-existe.md", "Clientes")
    check(
        "[5] matrix inexistente -> erro explícito, nunca finge sucesso",
        "error" in r5 and r5["forced_route_i"] is False,
        json.dumps(r5),
    )

    # [6] Contra o documento REAL de produto (worked examples da story).
    if REAL_MATRIX.exists():
        r6a = run_check(REAL_MATRIX, "Propostas Admin")
        check(
            "[6a] 'Propostas Admin' (página real, cenário 03) força via (i)",
            r6a["forced_route_i"] is True
            and any(m["scenario_id"] == "03" for m in r6a["matches"]),
            json.dumps(r6a),
        )
        r6b = run_check(REAL_MATRIX, "Relatório financeiro trimestral inventado")
        check(
            "[6b] termo inventado (não é página real) NÃO força via (i)",
            r6b["forced_route_i"] is False,
            json.dumps(r6b),
        )
    else:
        # Starter kit (template): sem conteúdo de produto real. O bloco [6] é uma checagem-bônus
        # de integração contra o 00-ux-scenarios.md REAL — pula limpo num checkout sem esse doc.
        # A lógica de roteamento em si já é provada de forma determinística por [1]-[5] e [7]
        # (via FIXTURE_MATRIX). Ver Onda 2 / backport: máquina self-contained.
        print(f"  SKIP  [6] documento real de produto ausente ({REAL_MATRIX}) — checkout sem conteúdo de produto")

    # [7] Guardrail de tamanho mínimo — termos curtos (artigos/preposições) não geram
    # match espúrio (achado real de auto-revisão, corrigido antes de fechar a story).
    r7 = run_check(REAL_MATRIX if REAL_MATRIX.exists() else FIXTURE_MATRIX, "a,de,e")
    check(
        "[7] termos curtos (a/de/e) não forçam via (i) — sem match espúrio",
        r7["forced_route_i"] is False and r7["matches"] == [],
        json.dumps(r7),
    )

    print(f"\n{len(PASS)} PASS, {len(FAIL)} FAIL\n")
    for name in PASS:
        print(f"  ok   {name}")
    for name in FAIL:
        print(f"  FAIL {name}")

    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
