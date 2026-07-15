#!/usr/bin/env python3
"""test_gerente_proactive.py — provas reais (subprocessos, não mocks) dos invariantes de E8.5.

Story E8.5 — roda `gerente_proactive.py` como subprocessos de verdade contra as fixtures
reais de `project_controll/test-fixtures/E8/proactive-tickets/` (copiadas para um
diretório temporário por teste) para provar:

  1. `next-task` — TETO DURO halting: com `cap_per_cycle=N`, exatamente N chamadas
     devolvem `verdict: go` (rotação round-robin determinística pelas 4 categorias) e a
     (N+1)-ésima devolve `verdict: cap-reached` — sem off-by-one (nem para antes nem
     depois de N). Testado para N=1 e N=3.
  2. `record-proactive` incrementa o acumulador do ciclo, reseta automaticamente quando
     `--cycle-id` muda (mesma filosofia de `quota-ciclo.json`/E8.3), e `next-task`
     reflete o incremento na chamada seguinte.
  3. `dedup-check` — CASO CENTRAL: um achado com texto muito similar a um ticket
     `origem: proativo` já `concluido` é sinalizado `duplicate: true` apontando pro
     ticket certo; o mesmo vale para um ticket `descartado`. Um achado genuinamente novo
     (sem overlap relevante) é `duplicate: false`.
  4. `dedup-check` filtra por `origem: proativo` por padrão — um ticket `origem: manual`
     com texto quase idêntico NÃO conta como duplicata a menos que
     `--include-non-proactive` seja passado.
  5. Precedência de config (CLI > env var > proactive.config.json > default hardcoded)
     para `cap_per_cycle` e `dedup_similarity_threshold`.

Sem dependências externas (stdlib apenas).

Uso:
    python3 test_gerente_proactive.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "gerente_proactive.py"
REPO_ROOT = HERE.parent.parent.parent  # project_controll/gerente/scripts -> repo root
FIXTURES_DIR = REPO_ROOT / "project_controll" / "test-fixtures" / "E8" / "proactive-tickets"


def run(args: list[str], env: dict | None = None) -> subprocess.CompletedProcess:
    full_env = dict(os.environ)
    if env:
        full_env.update(env)
    for k in list(full_env):
        if k.startswith("GERENTE_PROACTIVE_") and (not env or k not in env):
            del full_env[k]
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, env=full_env,
    )


def run_json(args: list[str], env: dict | None = None) -> dict:
    p = run(args, env=env)
    out = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else "{}"
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        print("STDOUT:", p.stdout, file=sys.stderr)
        print("STDERR:", p.stderr, file=sys.stderr)
        raise


PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        PASS.append(name)
        print(f"  PASS  {name}")
    else:
        FAIL.append(name)
        print(f"  FAIL  {name}  {detail}")


def copy_fixtures(tickets_dir: Path) -> None:
    tickets_dir.mkdir(parents=True, exist_ok=True)
    for src in FIXTURES_DIR.glob("TCK-*.md"):
        shutil.copy(src, tickets_dir / src.name)


def main() -> int:
    if not FIXTURES_DIR.exists():
        print(f"erro: fixtures não encontradas em {FIXTURES_DIR}", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="gerente-proactive-test-") as tmp:
        tmp_path = Path(tmp)

        # ------------------------------------------------------------------
        print("\n[1] next-task — teto duro halting, N=3, sem off-by-one")
        root_cap3 = tmp_path / "root-cap3"
        seen_categories = []
        for i in range(3):
            r = run_json(["next-task", "--root", str(root_cap3), "--cycle-id", "cycle-cap3", "--cap-per-cycle", "3"])
            check(f"chamada {i+1}/3 -> verdict=go", r.get("verdict") == "go", str(r))
            check(f"chamada {i+1}/3 -> count_so_far == {i}", r.get("count_so_far") == i, str(r))
            seen_categories.append(r.get("category", {}).get("id"))
            run_json(["record-proactive", "--root", str(root_cap3), "--cycle-id", "cycle-cap3",
                      "--category", r["category"]["id"], "--outcome", "no-finding"])
        check("as 3 categorias vistas são as 3 primeiras do catálogo, em ordem round-robin",
              seen_categories == ["analise-adversarial-feature", "completude-de-testes", "descoberta-de-padroes"],
              str(seen_categories))
        r4 = run_json(["next-task", "--root", str(root_cap3), "--cycle-id", "cycle-cap3", "--cap-per-cycle", "3"])
        check("4a chamada (N+1) -> verdict=cap-reached (não antes, não depois)", r4.get("verdict") == "cap-reached", str(r4))
        check("cap-reached -> category=null", r4.get("category") is None, str(r4))

        print("\n[1b] next-task — teto N=1 (caso degenerado, ainda sem off-by-one)")
        root_cap1 = tmp_path / "root-cap1"
        r1 = run_json(["next-task", "--root", str(root_cap1), "--cycle-id", "cycle-cap1", "--cap-per-cycle", "1"])
        check("1a chamada -> go", r1.get("verdict") == "go", str(r1))
        run_json(["record-proactive", "--root", str(root_cap1), "--cycle-id", "cycle-cap1",
                  "--category", r1["category"]["id"], "--outcome", "no-finding"])
        r2 = run_json(["next-task", "--root", str(root_cap1), "--cycle-id", "cycle-cap1", "--cap-per-cycle", "1"])
        check("2a chamada -> cap-reached imediatamente (N=1)", r2.get("verdict") == "cap-reached", str(r2))

        # ------------------------------------------------------------------
        print("\n[2] record-proactive — reset automático de ciclo (mesma filosofia de quota-ciclo.json)")
        root_reset = tmp_path / "root-reset"
        run_json(["record-proactive", "--root", str(root_reset), "--cycle-id", "cycle-A", "--category", "analise-adversarial-feature", "--outcome", "ticket-filed"])
        r_a2 = run_json(["record-proactive", "--root", str(root_reset), "--cycle-id", "cycle-A", "--category", "completude-de-testes", "--outcome", "ticket-filed"])
        check("mesmo ciclo acumula (count=2)", r_a2.get("count") == 2, str(r_a2))
        r_b1 = run_json(["record-proactive", "--root", str(root_reset), "--cycle-id", "cycle-B", "--category", "analise-adversarial-feature", "--outcome", "ticket-filed"])
        check("cycle-id NOVO reseta o acumulador (count=1, não 3)", r_b1.get("count") == 1, str(r_b1))
        check("cap_reached calculado corretamente (1 < default 3)", r_b1.get("cap_reached") is False, str(r_b1))

        # ------------------------------------------------------------------
        print("\n[3] dedup-check — CASO CENTRAL: achado similar a ticket proativo CONCLUIDO")
        tickets_dir = tmp_path / "tickets"
        copy_fixtures(tickets_dir)
        root_dedup = tmp_path / "root-dedup"

        r = run_json([
            "dedup-check", "--root", str(root_dedup), "--tickets-dir", str(tickets_dir),
            "--title", "Trocar perfil PF/PJ no wizard não limpa o veículo selecionado, cria registro duplicado",
            "--description", "No wizard de proposta, ao alternar de Pessoa Física pra Pessoa Jurídica depois de já ter escolhido um veículo, o veiculo antigo fica órfão e um novo é criado.",
        ])
        check("achado batendo com TCK-90001 (concluido) -> duplicate=true", r.get("duplicate") is True, str(r))
        check("best_match aponta para TCK-90001", r.get("best_match", {}).get("ticket_id") == "TCK-90001", str(r))
        check("best_match reporta status=concluido (histórico FECHADO, não só aberto)", r.get("best_match", {}).get("status") == "concluido", str(r))

        print("\n[3b] dedup-check — achado similar a ticket proativo DESCARTADO")
        r = run_json([
            "dedup-check", "--root", str(root_dedup), "--tickets-dir", str(tickets_dir),
            "--title", "Admin consegue mover proposta pra qualquer status, será que falta validação de transição?",
            "--description", "Suspeita de que AdminProposalService.update_status_any() não valida a transição de status corretamente, permitindo mover pra qualquer status não-terminal.",
        ])
        check("achado batendo com TCK-90002 (descartado) -> duplicate=true", r.get("duplicate") is True, str(r))
        check("best_match aponta para TCK-90002", r.get("best_match", {}).get("ticket_id") == "TCK-90002", str(r))
        check("best_match reporta status=descartado (histórico FECHADO)", r.get("best_match", {}).get("status") == "descartado", str(r))

        print("\n[3c] dedup-check — achado GENUINAMENTE NOVO (sem overlap relevante) -> duplicate=false, seria filed")
        r = run_json([
            "dedup-check", "--root", str(root_dedup), "--tickets-dir", str(tickets_dir),
            "--title", "Exportação de relatório de propostas em CSV falha com acentuação corrompida",
            "--description", "Ao exportar a lista de propostas filtradas para CSV, caracteres acentuados (ç, ã, é) aparecem corrompidos no Excel por falta de BOM UTF-8 no arquivo gerado.",
        ])
        check("achado sem overlap real -> duplicate=false", r.get("duplicate") is False, str(r))
        check("scanned_count inclui as 3 fixtures origem=proativo (não a manual)", r.get("scanned_count") == 3, str(r))

        # ------------------------------------------------------------------
        print("\n[4] dedup-check — filtro por origem=proativo (default) exclui ticket manual quase-idêntico")
        r = run_json([
            "dedup-check", "--root", str(root_dedup), "--tickets-dir", str(tickets_dir),
            "--title", "Wizard de proposta: alternar perfil PF/PJ não limpa o veículo já selecionado, gerando registro órfão",
            "--description", "",
        ])
        # TCK-90004 (manual) tem título quase idêntico a este e a TCK-90001 (proativo,
        # concluido) — o match correto e ESPERADO é o proativo, não o manual, mesmo que o
        # manual também bateria por texto.
        check("match aponta para o ticket PROATIVO (TCK-90001), não o manual (TCK-90004)",
              r.get("best_match", {}).get("ticket_id") == "TCK-90001", str(r))
        check("scanned_count NÃO inclui TCK-90004 (origem=manual) por padrão", r.get("scanned_count") == 3, str(r))

        r_incl = run_json([
            "dedup-check", "--root", str(root_dedup), "--tickets-dir", str(tickets_dir),
            "--title", "Wizard de proposta: alternar perfil PF/PJ não limpa o veículo já selecionado, gerando registro órfão",
            "--description", "",
            "--include-non-proactive",
        ])
        check("--include-non-proactive amplia o scan pra 4 tickets (inclui o manual)", r_incl.get("scanned_count") == 4, str(r_incl))

        # ------------------------------------------------------------------
        print("\n[5] Precedência de config: CLI > env var > proactive.config.json > default")
        root_cfg = tmp_path / "root-cfg"
        root_cfg.mkdir()
        (root_cfg / "proactive.config.json").write_text(json.dumps({"cap_per_cycle": 7}), encoding="utf-8")
        r = run_json(["next-task", "--root", str(root_cfg), "--cycle-id", "c-cfg"])
        check("sem CLI/env: usa proactive.config.json (cap=7)", r.get("cap_per_cycle") == 7, str(r))
        r = run_json(["next-task", "--root", str(root_cfg), "--cycle-id", "c-cfg"],
                     env={"GERENTE_PROACTIVE_CAP_PER_CYCLE": "9"})
        check("env var vence o config file (9 > 7 do arquivo)", r.get("cap_per_cycle") == 9, str(r))
        r = run_json(["next-task", "--root", str(root_cfg), "--cycle-id", "c-cfg", "--cap-per-cycle", "11"],
                     env={"GERENTE_PROACTIVE_CAP_PER_CYCLE": "9"})
        check("flag de CLI vence env var e config file (11)", r.get("cap_per_cycle") == 11, str(r))
        r = run_json(["next-task", "--root", str(tmp_path / "root-no-config"), "--cycle-id", "c-nc"])
        check("sem nada: usa o default hardcoded (3)", r.get("cap_per_cycle") == 3, str(r))

        r = run_json(["dedup-check", "--root", str(tmp_path / "root-no-config"), "--tickets-dir", str(tickets_dir),
                      "--title", "x", "--description", "y"])
        check("dedup threshold default hardcoded (0.30)", r.get("threshold") == 0.30, str(r))
        r = run_json(["dedup-check", "--root", str(tmp_path / "root-no-config"), "--tickets-dir", str(tickets_dir),
                      "--title", "x", "--description", "y"], env={"GERENTE_PROACTIVE_DEDUP_THRESHOLD": "0.9"})
        check("env var vence o default (threshold=0.9)", r.get("threshold") == 0.9, str(r))

    print(f"\n{'='*60}\nPASS: {len(PASS)}  FAIL: {len(FAIL)}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
