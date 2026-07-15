#!/usr/bin/env python3
"""test_gerente_style.py — provas reais (subprocessos, não mocks) dos invariantes de E9.2.

Story E9.2 (ideias/sistema-artifacts/E9-2-aprendizado-estilo.md) — roda
`gerente_oracle.py` + `gerente_style.py` como subprocessos de verdade contra
ledger-roots TEMPORÁRIOS (nunca escreve na árvore real `wiki/ledger/`)
para provar, na ordem:

  A. `consult-precedent` — um precedente RATIFICADO similar (mesmo tipo + overlap de
     `areas` >= limiar da categoria) sustenta `suggested_confidence: high`.
  B. Limiar por categoria é de fato DIFERENTE: o MESMO overlap absoluto de `areas` (1
     tag em comum) sustenta `decisao-tecnica` (limiar 1) mas NÃO sustenta
     `decisao-de-produto` (limiar 2, categoria mais sensível) — só com 2 tags em comum
     é que `decisao-de-produto` também sustenta.
  C. **O CASO CENTRAL (down-weight):** quando existe TANTO um precedente ratificado
     similar QUANTO uma decisão corrigida similar para o mesmo candidato, o resultado é
     SEMPRE `low` — a correção do dono vence o suporte, nunca o contrário (conservador
     por desenho, nunca "upgrade" em evidência mista).
  D. O gate history-aware de `gerente_oracle.py record-decision` (não só
     `consult-precedent`) de fato VETA `--confidence high` quando existe uma decisão
     `corrected` similar — MESMO com um `--precedent` explícito, individualmente
     válido, citado. Controle positivo: um candidato com `areas` que não colidem com
     nenhuma decisão corrigida ainda recebe `high` normalmente (a exigência é
     seletiva, não um bloqueio cego).
  E. `sm2` — % ratificado é DERIVADO do rastro real (contagem construída e conferida
     por aritmética simples, nunca um valor hardcoded no script), com e sem filtro
     `--tipo`.

Sem dependências externas (stdlib apenas).

Uso:
    python3 test_gerente_style.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORACLE_SCRIPT = HERE / "gerente_oracle.py"
STYLE_SCRIPT = HERE / "gerente_style.py"


def run_oracle(args: list[str]) -> dict:
    p = subprocess.run([sys.executable, str(ORACLE_SCRIPT), *args], capture_output=True, text=True)
    out = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else "{}"
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        print("ORACLE STDOUT:", p.stdout, file=sys.stderr)
        print("ORACLE STDERR:", p.stderr, file=sys.stderr)
        raise


def run_style(args: list[str]) -> dict:
    p = subprocess.run([sys.executable, str(STYLE_SCRIPT), *args], capture_output=True, text=True)
    out = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else "{}"
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        print("STYLE STDOUT:", p.stdout, file=sys.stderr)
        print("STYLE STDERR:", p.stderr, file=sys.stderr)
        raise


def record(ledger_root: Path, ticket: str, tipo: str, areas: str, **extra) -> dict:
    args = [
        "record-decision", "--ledger-root", str(ledger_root),
        "--ticket", ticket, "--tipo", tipo, "--areas", areas,
        "--question", "q", "--decision", f"decisao para {ticket}", "--justification", "j", "--context", "c",
    ]
    for k, v in extra.items():
        args += [f"--{k.replace('_', '-')}", str(v)]
    return run_oracle(args)


def ratify(entry_path: str, status: str = "ratified") -> dict:
    return run_oracle(["set-ratification", "--entry", entry_path, "--status", status, "--note", f"teste E9.2 ({status})"])


PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        PASS.append(name)
        print(f"  PASS  {name}")
    else:
        FAIL.append(name)
        print(f"  FAIL  {name}  {detail}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="gerente-style-test-") as tmp:
        tmp_path = Path(tmp)

        # ==================================================================
        print("\n[A] consult-precedent — precedente RATIFICADO similar sustenta suggested_confidence: high")
        ledger_a = tmp_path / "ledger-a"
        rA1 = record(ledger_a, "TCK-A1", "decisao-tecnica", "area-x,area-y")
        check("TCK-A1 gravado", rA1.get("ok") is True, str(rA1))
        ratify(rA1["ledger_path"], "ratified")

        cpA = run_style([
            "consult-precedent", "--ledger-root", str(ledger_a),
            "--tipo", "decisao-tecnica", "--areas", "area-x",
        ])
        check("suggested_confidence = high (precedente ratificado, overlap 1 >= limiar 1)", cpA.get("suggested_confidence") == "high", str(cpA))
        check("matches_ratified não-vazio", len(cpA.get("matches_ratified") or []) == 1, str(cpA))
        check("matches_corrected vazio", cpA.get("matches_corrected") == [], str(cpA))
        check("matches_ratified aponta para o path certo", cpA["matches_ratified"][0]["path"] == rA1["ledger_path"], str(cpA))
        check("nunca grava nada (é consulta pura) — nenhum novo arquivo no ledger", len(list(ledger_a.rglob('*.md'))) == 1, str(list(ledger_a.rglob('*.md'))))

        # sem overlap nenhum -> não sustenta
        cpA_no = run_style([
            "consult-precedent", "--ledger-root", str(ledger_a),
            "--tipo", "decisao-tecnica", "--areas", "area-completamente-diferente",
        ])
        check("sem overlap de areas -> suggested_confidence = low (default conservador)", cpA_no.get("suggested_confidence") == "low", str(cpA_no))
        check("matches_ratified vazio quando não há overlap", cpA_no.get("matches_ratified") == [], str(cpA_no))

        # ==================================================================
        print("\n[B] Limiar por categoria — MESMO overlap (1 tag) sustenta decisao-tecnica mas NÃO decisao-de-produto (limiar 2)")
        ledger_b = tmp_path / "ledger-b"
        rB_tec = record(ledger_b, "TCK-B-TEC", "decisao-tecnica", "area-x,area-y")
        ratify(rB_tec["ledger_path"], "ratified")
        rB_prod = record(ledger_b, "TCK-B-PROD", "decisao-de-produto", "area-x,area-y")
        ratify(rB_prod["ledger_path"], "ratified")

        cpB_tec = run_style(["consult-precedent", "--ledger-root", str(ledger_b), "--tipo", "decisao-tecnica", "--areas", "area-x"])
        check("decisao-tecnica: overlap=1 >= limiar(1) -> high", cpB_tec.get("suggested_confidence") == "high", str(cpB_tec))
        check("decisao-tecnica: category_threshold.min_shared_areas_support == 1", cpB_tec["category_threshold"]["min_shared_areas_support"] == 1, str(cpB_tec))

        cpB_prod_1 = run_style(["consult-precedent", "--ledger-root", str(ledger_b), "--tipo", "decisao-de-produto", "--areas", "area-x"])
        check("decisao-de-produto: overlap=1 < limiar(2) -> low (categoria mais sensível exige MAIS overlap)", cpB_prod_1.get("suggested_confidence") == "low", str(cpB_prod_1))
        check("decisao-de-produto: category_threshold.min_shared_areas_support == 2", cpB_prod_1["category_threshold"]["min_shared_areas_support"] == 2, str(cpB_prod_1))
        check("decisao-de-produto (overlap insuficiente): matches_ratified vazio", cpB_prod_1.get("matches_ratified") == [], str(cpB_prod_1))

        cpB_prod_2 = run_style(["consult-precedent", "--ledger-root", str(ledger_b), "--tipo", "decisao-de-produto", "--areas", "area-x,area-y"])
        check("decisao-de-produto: overlap=2 >= limiar(2) -> high", cpB_prod_2.get("suggested_confidence") == "high", str(cpB_prod_2))
        check("decisao-de-produto (overlap suficiente): matches_ratified não-vazio", len(cpB_prod_2.get("matches_ratified") or []) == 1, str(cpB_prod_2))

        # ==================================================================
        print("\n[C] Down-weight — precedente RATIFICADO + decisão CORRIGIDA similares coexistindo -> SEMPRE low (correção vence)")
        ledger_c = tmp_path / "ledger-c"
        rC_ratified = record(ledger_c, "TCK-C-RATIFIED", "decisao-tecnica", "area-z")
        ratify(rC_ratified["ledger_path"], "ratified")
        rC_corrected = record(ledger_c, "TCK-C-CORRECTED", "decisao-tecnica", "area-z,area-w")
        ratify(rC_corrected["ledger_path"], "corrected")

        cpC = run_style(["consult-precedent", "--ledger-root", str(ledger_c), "--tipo", "decisao-tecnica", "--areas", "area-z"])
        check("matches_ratified não-vazio (o suporte EXISTE)", len(cpC.get("matches_ratified") or []) == 1, str(cpC))
        check("matches_corrected não-vazio (a contradição EXISTE)", len(cpC.get("matches_corrected") or []) == 1, str(cpC))
        check("suggested_confidence = low MESMO com suporte presente — contradição vence (conservador)", cpC.get("suggested_confidence") == "low", str(cpC))
        check("reason cita 'corrected'", "corrected" in cpC.get("reason", "").lower(), str(cpC))
        check("matches_corrected aponta para TCK-C-CORRECTED", cpC["matches_corrected"][0]["path"] == rC_corrected["ledger_path"], str(cpC))

        # ==================================================================
        print("\n[D] Gate history-aware de gerente_oracle.py record-decision — veta 'high' mesmo com --precedent explícito válido, quando há corrected similar")
        # controle NEGATIVO: mesmo ledger de [C] — --precedent citado é o próprio TCK-C-RATIFIED
        # (mecanicamente válido: estado ativa, ratification ratified), mas TCK-C-CORRECTED
        # (area-z, area-w) contradiz por overlap de 'area-z'.
        rD_vetoed = record(
            ledger_c, "TCK-D-VETOED", "decisao-tecnica", "area-z",
            confidence="high", precedent=rC_ratified["ledger_path"],
        )
        check("confidence final = low (vetada pela corrected similar, apesar do --precedent válido)", rD_vetoed.get("confidence") == "low", str(rD_vetoed))
        check("proceed_dispatch = false", rD_vetoed.get("proceed_dispatch") is False, str(rD_vetoed))
        check("downgrade_reason cita 'corrected'", "corrected" in (rD_vetoed.get("downgrade_reason") or "").lower(), str(rD_vetoed))
        check("contradicting_corrected não-vazio na resposta (auditável)", len(rD_vetoed.get("contradicting_corrected") or []) == 1, str(rD_vetoed))
        check("contradicting_corrected aponta para TCK-C-CORRECTED", rD_vetoed["contradicting_corrected"][0]["path"] == rC_corrected["ledger_path"], str(rD_vetoed))

        # controle POSITIVO: mesmo ledger, mas um precedente + candidato com areas que
        # NUNCA colidem com nenhuma decisão corrigida -> high é honrado normalmente (a
        # exigência é seletiva por overlap real, não um bloqueio cego pós-primeira-correção).
        rD_control_base = record(ledger_c, "TCK-D-CONTROL-BASE", "decisao-tecnica", "area-nao-relacionada")
        ratify(rD_control_base["ledger_path"], "ratified")
        rD_control = record(
            ledger_c, "TCK-D-CONTROL", "decisao-tecnica", "area-nao-relacionada",
            confidence="high", precedent=rD_control_base["ledger_path"],
        )
        check("controle positivo: confidence = high (nenhuma corrected compartilha 'area-nao-relacionada')", rD_control.get("confidence") == "high", str(rD_control))
        check("controle positivo: proceed_dispatch = true", rD_control.get("proceed_dispatch") is True, str(rD_control))
        check("controle positivo: contradicting_corrected vazio", rD_control.get("contradicting_corrected") == [], str(rD_control))

        # ==================================================================
        print("\n[E] sm2 — % ratificado é DERIVADO do rastro real (contagem conferida por aritmética simples)")
        ledger_e = tmp_path / "ledger-e"
        # decisao-tecnica: 3 decididas (2 ratified, 1 corrected) + 2 pending
        tec_r1 = record(ledger_e, "TCK-E-TEC-R1", "decisao-tecnica", "a")
        ratify(tec_r1["ledger_path"], "ratified")
        tec_r2 = record(ledger_e, "TCK-E-TEC-R2", "decisao-tecnica", "a")
        ratify(tec_r2["ledger_path"], "ratified")
        tec_c1 = record(ledger_e, "TCK-E-TEC-C1", "decisao-tecnica", "a")
        ratify(tec_c1["ledger_path"], "corrected")
        record(ledger_e, "TCK-E-TEC-P1", "decisao-tecnica", "a")  # fica pending
        record(ledger_e, "TCK-E-TEC-P2", "decisao-tecnica", "a")  # fica pending
        # decisao-de-produto: 1 ratified (decided=1, pct=100)
        prod_r1 = record(ledger_e, "TCK-E-PROD-R1", "decisao-de-produto", "b")
        ratify(prod_r1["ledger_path"], "ratified")

        sm2_all = run_style(["sm2", "--ledger-root", str(ledger_e)])
        check("sm2 (sem filtro): ratified = 3 (2 tecnica + 1 produto)", sm2_all.get("ratified") == 3, str(sm2_all))
        check("sm2 (sem filtro): corrected = 1", sm2_all.get("corrected") == 1, str(sm2_all))
        check("sm2 (sem filtro): pending = 2", sm2_all.get("pending") == 2, str(sm2_all))
        check("sm2 (sem filtro): decided = 4", sm2_all.get("decided") == 4, str(sm2_all))
        check("sm2 (sem filtro): total = 6", sm2_all.get("total") == 6, str(sm2_all))
        check("sm2 (sem filtro): pct_ratified = 75.0 (3/4)", sm2_all.get("pct_ratified") == 75.0, str(sm2_all))

        sm2_tec = run_style(["sm2", "--ledger-root", str(ledger_e), "--tipo", "decisao-tecnica"])
        check("sm2 (--tipo decisao-tecnica): ratified = 2", sm2_tec.get("ratified") == 2, str(sm2_tec))
        check("sm2 (--tipo decisao-tecnica): corrected = 1", sm2_tec.get("corrected") == 1, str(sm2_tec))
        check("sm2 (--tipo decisao-tecnica): pending = 2", sm2_tec.get("pending") == 2, str(sm2_tec))
        check("sm2 (--tipo decisao-tecnica): decided = 3", sm2_tec.get("decided") == 3, str(sm2_tec))
        expected_pct_tec = round(2 / 3 * 100.0, 6)
        check(f"sm2 (--tipo decisao-tecnica): pct_ratified ≈ {expected_pct_tec}", abs((sm2_tec.get("pct_ratified") or 0) - expected_pct_tec) < 0.001, str(sm2_tec))

        sm2_prod = run_style(["sm2", "--ledger-root", str(ledger_e), "--tipo", "decisao-de-produto"])
        check("sm2 (--tipo decisao-de-produto): ratified = 1, corrected = 0, pct = 100.0", sm2_prod.get("ratified") == 1 and sm2_prod.get("corrected") == 0 and sm2_prod.get("pct_ratified") == 100.0, str(sm2_prod))

        sm2_empty = run_style(["sm2", "--ledger-root", str(tmp_path / "ledger-nunca-existiu")])
        check("sm2 sobre ledger-root inexistente: total=0, pct_ratified=null (nunca crash/exceção)", sm2_empty.get("total") == 0 and sm2_empty.get("pct_ratified") is None, str(sm2_empty))

        # muda a contagem (adiciona mais 1 ratified em decisao-tecnica) e confere que o
        # pct MUDA de acordo — prova de que não é hardcoded, é derivado do estado atual do rastro.
        tec_r3 = record(ledger_e, "TCK-E-TEC-R3", "decisao-tecnica", "a")
        ratify(tec_r3["ledger_path"], "ratified")
        sm2_tec_after = run_style(["sm2", "--ledger-root", str(ledger_e), "--tipo", "decisao-tecnica"])
        expected_pct_tec_after = round(3 / 4 * 100.0, 6)
        check(f"sm2 muda após nova ratificação real: decided 3->4, pct {expected_pct_tec}->{expected_pct_tec_after}",
              sm2_tec_after.get("decided") == 4 and abs((sm2_tec_after.get("pct_ratified") or 0) - expected_pct_tec_after) < 0.001,
              str(sm2_tec_after))

        # ==================================================================
        print("\n[F] consult-precedent também varre product-decisions.md/decisions.md (AC1 — 'Ledger + product-decisions.md') — informacional, NUNCA gating")
        prose_path = tmp_path / "product-decisions.md"
        prose_path.write_text(
            "# Decisões de Produto\n\n"
            "## [PRODUCT] Área-nao-relacionada não tem nada a ver — 2026-01-01\n"
            "Conteúdo irrelevante.\n\n"
            "## [PRODUCT] Regra sobre area-x e pricing — 2026-01-02\n"
            "Conteúdo que menciona area-x no título.\n",
            encoding="utf-8",
        )
        empty_decisions_path = tmp_path / "decisions.md"
        empty_decisions_path.write_text("# Decisões Técnicas\n\n(vazio nesta fixture)\n", encoding="utf-8")

        ledger_f = tmp_path / "ledger-f"  # ledger vazio — sem nenhum precedente estruturado
        cpF = run_style([
            "consult-precedent", "--ledger-root", str(ledger_f),
            "--tipo", "decisao-de-produto", "--areas", "area-x",
            "--product-decisions-path", str(prose_path),
            "--decisions-path", str(empty_decisions_path),
        ])
        check("product_decisions_hits encontra a seção com 'area-x' no título", len(cpF.get("product_decisions_hits") or []) == 1, str(cpF))
        check("product_decisions_hits NÃO inclui a seção irrelevante", "nao-relacionada" not in json.dumps(cpF.get("product_decisions_hits")), str(cpF))
        check("decisions_hits vazio (arquivo sem seções)", cpF.get("decisions_hits") == [], str(cpF))
        check("suggested_confidence continua low (Ledger vazio) — hits de prosa NUNCA viram gating por si só", cpF.get("suggested_confidence") == "low", str(cpF))
        check("matches_ratified vazio (nenhuma Entrada de Ledger estruturada existe)", cpF.get("matches_ratified") == [], str(cpF))

        # ==================================================================
        print("\n[G] --oracle-config custom de verdade MUDA o comportamento do gate (não só os defaults hardcoded funcionam)")
        custom_config_path = tmp_path / "oracle.custom.config.json"
        custom_config_path.write_text(json.dumps({
            "categories": {
                # limiar de SUPORTE muito mais alto (3) — o overlap=1 de [B] não basta mais.
                "decisao-tecnica": {"min_shared_areas_support": 3, "min_shared_areas_contradict": 5},
            },
        }), encoding="utf-8")

        # Reusa o ledger de [B]: TCK-B-TEC (areas [area-x, area-y], ratified) já sustentava
        # 'high' com overlap=1 sob o config DEFAULT (limiar 1). Sob o config CUSTOM (limiar 3),
        # o MESMO overlap=1 deixa de bastar.
        cpG_default = run_style(["consult-precedent", "--ledger-root", str(ledger_b), "--tipo", "decisao-tecnica", "--areas", "area-x"])
        check("[G] sanity — sob config DEFAULT, overlap=1 ainda sustenta high (baseline de [B])", cpG_default.get("suggested_confidence") == "high", str(cpG_default))

        cpG_custom = run_style([
            "consult-precedent", "--ledger-root", str(ledger_b), "--tipo", "decisao-tecnica", "--areas", "area-x",
            "--oracle-config", str(custom_config_path),
        ])
        check("[G] sob config CUSTOM (limiar 3), o MESMO overlap=1 NÃO sustenta mais high", cpG_custom.get("suggested_confidence") == "low", str(cpG_custom))
        check("[G] category_threshold reflete o arquivo custom (3), não o default hardcoded (1)", cpG_custom["category_threshold"]["min_shared_areas_support"] == 3, str(cpG_custom))

        # E o gate real de record-decision (não só consult-precedent) também respeita --oracle-config:
        # ledger_c ([C]/[D]) tem TCK-C-CORRECTED (areas [area-z, area-w], corrected) — sob o
        # limiar DEFAULT de contradição (1), qualquer overlap>=1 já veta. Sob um limiar CUSTOM de
        # contradição=5, esse mesmo overlap=1 deixa de vetar.
        lax_config_path = tmp_path / "oracle.lax.config.json"
        lax_config_path.write_text(json.dumps({
            "categories": {"decisao-tecnica": {"min_shared_areas_support": 1, "min_shared_areas_contradict": 5}},
        }), encoding="utf-8")
        rG_precedent = record(ledger_c, "TCK-G-PRECEDENT", "decisao-tecnica", "area-g-unico")
        ratify(rG_precedent["ledger_path"], "ratified")
        rG_lax = record(
            ledger_c, "TCK-G-LAX", "decisao-tecnica", "area-z",
            confidence="high", precedent=rC_ratified["ledger_path"], oracle_config=str(lax_config_path),
        )
        check("[G] sob limiar de contradição CUSTOM (5), overlap=1 com a corrected NÃO veta mais -> high", rG_lax.get("confidence") == "high", str(rG_lax))
        check("[G] confirma que SEM override (default, limiar 1) o mesmo cenário vetaria (regressão de [D])", rD_vetoed.get("confidence") == "low", str(rD_vetoed))

    print(f"\n{'='*60}\nPASS: {len(PASS)}  FAIL: {len(FAIL)}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
