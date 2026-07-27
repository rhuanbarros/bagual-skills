#!/usr/bin/env python3
"""test_classify_trilha.py — provas reais (subprocessos) do gate mecânico da Story E9.4.

Story E9.4 (ideias/sistema-artifacts/E9-4-escalonamento-skill.md), PRD 02 FR-5.

Roda `classify_trilha.py` como subprocesso de verdade (nunca mock/import direto da
função) contra:
  1. As 8 fixtures sintéticas em `project_controll/test-fixtures/E9/E9-4/` — provam
     as duas regras "óbvias" (rapida/wds) e os motivos específicos de cada caso de
     escalonamento (bug expandido, não verificado, feature sem design, conflito de
     produto, categoria fora das regras).
  2. Uma amostra de tickets REAIS (`project_controll/tickets/TCK-*.md`, só leitura —
     nunca escreve neles) — prova que o gate produz decisões coerentes/conservadoras
     também fora das fixtures sintéticas, sem exigir migração dos 26 tickets legados.
  3. `rebuild_board.py` contra os 26 tickets reais — prova que o campo `escalonar` novo
     é reconstruído com o default retrocompatível (`false`) e que a reconstrução segue
     batendo 0 mismatches nos campos originais (mesmo invariante da Story E5.2).

Sem dependências externas (stdlib apenas).

Uso:
    python3 test_classify_trilha.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = Path(__file__).resolve().parent
CLASSIFY = SCRIPTS_DIR / "classify_trilha.py"
REBUILD = SCRIPTS_DIR / "rebuild_board.py"
FIXTURES = REPO_ROOT / "project_controll" / "test-fixtures" / "E9" / "E9-4"
REAL_TICKETS_DIR = REPO_ROOT / "project_controll" / "tickets"
REAL_BOARD = REAL_TICKETS_DIR / "board.yaml"

PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASS.append(name)
        print(f"  PASS  {name}")
    else:
        FAIL.append(name)
        print(f"  FAIL  {name}  {detail}")


def run_classify(ticket_path: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, str(CLASSIFY), "--ticket", str(ticket_path)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(proc.stdout)


def run_rebuild(tickets_dir: Path, out_path: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, str(REBUILD), "--tickets-dir", str(tickets_dir), "--out", str(out_path), "--json"],
        capture_output=True, text=True, check=True,
    )
    return json.loads(proc.stdout)


def main() -> int:
    # ------------------------------------------------------------------
    print("\n[1] Fixtures sintéticas — Regra A (rapida)")
    r = run_classify(FIXTURES / "TCK-E9T-01-bug-obvio.md")
    check("bug claro, confirmado, único local, sem conflito => rapida", r["trilha"] == "rapida", str(r))
    check("escalonar=false", r["escalonar"] is False, str(r))
    check("rule=A", r["rule"] == "A", str(r))

    r8 = run_classify(FIXTURES / "TCK-E9T-08-bug-fast-path-trivial.md")
    check("fast-path trivial (F22) substitui 'Confirmado: sim' => rapida", r8["trilha"] == "rapida", str(r8))
    check("escalonar=false (fast-path)", r8["escalonar"] is False, str(r8))

    # ------------------------------------------------------------------
    print("\n[2] Fixture sintética — Regra B (wds)")
    r2 = run_classify(FIXTURES / "TCK-E9T-02-feature-design-confirmado.md")
    check("feature + design_confirmado:true + sem conflito => wds", r2["trilha"] == "wds", str(r2))
    check("escalonar=false", r2["escalonar"] is False, str(r2))
    check("rule=B", r2["rule"] == "B", str(r2))

    # ------------------------------------------------------------------
    print("\n[3] Fixtures sintéticas — casos ambíguos, TODOS devem escalar (trilha=null)")
    ambiguous_cases = [
        ("TCK-E9T-03-bug-expandido.md", "expandido"),
        ("TCK-E9T-04-bug-nao-verificado.md", "confirmado"),
        ("TCK-E9T-05-feature-sem-design.md", "design"),
        ("TCK-E9T-06-bug-conflito-produto.md", "conflito"),
        ("TCK-E9T-07-chore.md", "categoria"),
    ]
    for filename, motivo_esperado in ambiguous_cases:
        rc = run_classify(FIXTURES / filename)
        check(f"{filename}: trilha=null", rc["trilha"] is None, str(rc))
        check(f"{filename}: escalonar=true", rc["escalonar"] is True, str(rc))
        check(f"{filename}: motivo cita '{motivo_esperado}'", motivo_esperado in rc["reason"].lower(), str(rc))

    # ------------------------------------------------------------------
    print("\n[4] Nunca guessa — nenhum caso ambíguo recebe uma trilha não-null")
    for filename, _ in ambiguous_cases:
        rc = run_classify(FIXTURES / filename)
        check(f"{filename}: trilha nunca chutada (deve ser None)", rc["trilha"] is None, str(rc))

    # ------------------------------------------------------------------
    # [5] e [6] rodam contra tickets REAIS do projeto (conteúdo, não fixture). Num starter kit /
    # checkout sem esses tickets (ex.: o template do backport da Onda 2), pulam limpo — a lógica
    # de classify/rebuild já é provada de forma determinística por [1]-[4] (fixtures) e [7]
    # (sintético). No <PROJETO>, onde os tickets existem, rodam normalmente.
    print("\n[5] Contra tickets REAIS (só leitura, nunca escreve) — decisões coerentes")
    real_004 = REAL_TICKETS_DIR / "TCK-004-lentidao-detalhe-proposta.md"
    real_001 = REAL_TICKETS_DIR / "TCK-001-feedback-visual-toque.md"
    real_023 = REAL_TICKETS_DIR / "TCK-023-chat-admin-parceiro-por-proposta.md"
    if real_004.exists() and real_001.exists() and real_023.exists():
        r004 = run_classify(real_004)
        check("TCK-004 real (bug confirmado, único local, sem conflito) => rapida", r004["trilha"] == "rapida", str(r004))
        r001 = run_classify(real_001)
        check("TCK-001 real (bug expanded:true) => escalonar (nunca chuta escopo maior)", r001["escalonar"] is True, str(r001))
        check("TCK-001 real: trilha=null", r001["trilha"] is None, str(r001))
        r023 = run_classify(real_023)
        check("TCK-023 real (feature grande, sem design_confirmado) => escalonar", r023["escalonar"] is True, str(r023))
        check(
            "Nenhum arquivo real foi modificado por classify_trilha.py (script é read-only)",
            real_004.read_text(encoding="utf-8").count("design_confirmado") == 0
            and "escalonar:" not in real_004.read_text(encoding="utf-8"),
            "classify_trilha.py não deve escrever nos .md",
        )
    else:
        print("  SKIP  [5] tickets reais do projeto ausentes — checkout sem conteúdo (starter kit)")

    # ------------------------------------------------------------------
    print("\n[6] rebuild_board.py carrega `escalonar` — round-trip contra os tickets reais")
    import tempfile
    if list(REAL_TICKETS_DIR.glob("TCK-*.md")):
        with tempfile.TemporaryDirectory(prefix="e9-4-rebuild-test-") as tmp:
            out_path = Path(tmp) / "board-rebuilt.yaml"
            # A fila de tickets reais CRESCE ao longo do tempo (o Gerente materializa débitos de
            # retro como tickets). O invariante que este bloco prova não é uma contagem mágica e
            # sim "TODO TCK-*.md real foi reconstruído, zero warnings" — então derivamos o esperado
            # do próprio diretório (mesmo glob que o loader usa) em vez de hardcodar um número que
            # apodrece a cada ticket novo. `total < esperado` ainda reprova (ticket dropado), e
            # qualquer warning ainda reprova.
            expected_total = len(list(REAL_TICKETS_DIR.glob("TCK-*.md")))
            result = run_rebuild(REAL_TICKETS_DIR, out_path)
            check(f"{expected_total} tickets reais reconstruídos, sem warnings", result["stats"]["total"] == expected_total and not result["warnings"], str(result))
            rendered = out_path.read_text(encoding="utf-8")
            check("`escalonar` aparece no board reconstruído (índice carrega o campo)", "escalonar: false" in rendered, "campo escalonar ausente do board reconstruído")
            # Retrocompat conservador: nenhum ticket LEGADO (schema antigo, id sequencial
            # `TCK-NNN`) deveria nascer `escalonar: true` por um default incorreto do
            # rebuild. Escopado ao FRONT-MATTER dos próprios arquivos legados — não mais
            # uma busca de substring no board inteiro, que quebra assim que o Gerente cria
            # (legitimamente) um ticket NOVO (schema `TCK-<timestamp>-<hex>`) já escalado
            # (ex.: os tickets GERAIS do feedback da Laura). Ver TCK-20260717212601-da07.
            # Nota: o padrão `TCK-NNN-*.md` (3 dígitos) nunca casa com o schema novo
            # (`TCK-<14 dígitos>-<hex>-*.md`), porque o 4º caractere após `TCK-` num id
            # novo é sempre um dígito do timestamp, nunca o `-` literal que o glob exige.
            legacy_ticket_files = sorted(REAL_TICKETS_DIR.glob("TCK-[0-9][0-9][0-9]-*.md"))
            legacy_escalonados = [
                f.name for f in legacy_ticket_files
                if "escalonar: true" in f.read_text(encoding="utf-8")
            ]
            check(
                f"Nenhum dos {len(legacy_ticket_files)} tickets legados (TCK-NNN) aparece com escalonar:true (retrocompat conservador)",
                not legacy_escalonados,
                f"tickets legados com escalonar:true incorreto: {legacy_escalonados}",
            )
    else:
        print("  SKIP  [6] tickets reais do projeto ausentes — checkout sem conteúdo (starter kit)")

    # ------------------------------------------------------------------
    print("\n[7] rebuild_board.py — round-trip do campo `escalonar` a partir de um .md sintético que o declara true")
    import tempfile as tempfile2
    with tempfile2.TemporaryDirectory(prefix="e9-4-escalonar-roundtrip-") as tmp2:
        tmp2_path = Path(tmp2)
        synthetic = tmp2_path / "TCK-E9T-99-escalado.md"
        synthetic.write_text(
            "---\n"
            "id: TCK-E9T-99\n"
            "title: \"[FIXTURE] ticket escalado sintético\"\n"
            "status: pronto-para-implementar\n"
            "priority: media\n"
            "category: feature\n"
            "area: fixture-teste\n"
            "expanded: false\n"
            "created: 2026-07-11\n"
            "updated: 2026-07-11\n"
            "origem: manual\n"
            "visivel_pro_cliente: false\n"
            "trilha: null\n"
            "escalonar: true\n"
            "ledger_refs: []\n"
            "---\n\n## Descrição\nsintético\n",
            encoding="utf-8",
        )
        out_path2 = tmp2_path / "board.yaml"
        result2 = run_rebuild(tmp2_path, out_path2)
        check("1 ticket sintético reconstruído", result2["stats"]["total"] == 1, str(result2))
        rendered2 = out_path2.read_text(encoding="utf-8")
        check("escalonar:true do .md sintético sobrevive no board reconstruído", "escalonar: true" in rendered2, rendered2)
        check("trilha:null preservado junto com escalonar:true", "trilha: null" in rendered2, rendered2)

    # ------------------------------------------------------------------
    # [8] Regressão TCK-20260717162048-a7f8: `_yaml_scalar` deve citar um título que
    # COMEÇA com um indicador YAML (ex.: `[GERAL] ...`) — sem isso, `render_board_yaml`
    # emite `title: [GERAL] ...` sem aspas, que o YAML lê como flow-sequence e quebra o
    # parse do board (reproduzido ao vivo em 2026-07-17, ver ticket).
    # ------------------------------------------------------------------
    print("\n[8] rebuild_board.py — título começando com indicador YAML (`[`) sai citado no board reconstruído")
    import tempfile as tempfile3
    with tempfile3.TemporaryDirectory(prefix="e5-2-leading-indicator-quoting-") as tmp3:
        tmp3_path = Path(tmp3)
        synthetic3 = tmp3_path / "TCK-E9T-98-titulo-colchete.md"
        synthetic3.write_text(
            "---\n"
            "id: TCK-E9T-98\n"
            'title: "[GERAL] status geral sintético"\n'
            "status: pronto-para-implementar\n"
            "priority: media\n"
            "category: meta-bug\n"
            "area: fixture-teste\n"
            "expanded: false\n"
            "created: 2026-07-17\n"
            "updated: 2026-07-17\n"
            "origem: manual\n"
            "visivel_pro_cliente: false\n"
            "trilha: null\n"
            "escalonar: false\n"
            "ledger_refs: []\n"
            "---\n\n## Descrição\nsintético\n",
            encoding="utf-8",
        )
        out_path3 = tmp3_path / "board.yaml"
        result3 = run_rebuild(tmp3_path, out_path3)
        check("1 ticket sintético (título colchete) reconstruído", result3["stats"]["total"] == 1, str(result3))
        rendered3 = out_path3.read_text(encoding="utf-8")
        title_line = next((line for line in rendered3.splitlines() if line.strip().startswith("title:")), "")
        check(
            "título começando com `[` sai CITADO (entre aspas) no board reconstruído",
            title_line.strip() == 'title: "[GERAL] status geral sintético"',
            title_line,
        )
        try:
            import yaml as _yaml_check  # PyYAML já é dependência do projeto (ver requirements do backend)
            parsed3 = _yaml_check.safe_load(rendered3)
            check(
                "board reconstruído com título `[GERAL]...` é parseável por yaml.safe_load",
                parsed3["tickets"]["TCK-E9T-98"]["title"] == "[GERAL] status geral sintético",
                str(parsed3),
            )
        except ImportError:
            print("  SKIP  yaml.safe_load indisponível neste ambiente — validação estrutural acima (title_line) já cobre o bug")

    # ------------------------------------------------------------------
    print(f"\n{'='*60}\nPASS: {len(PASS)}  FAIL: {len(FAIL)}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
