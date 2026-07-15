#!/usr/bin/env python3
"""read_fp_suspects.py — E13.4 leitor de `semgrep-fp-suspects.jsonl` → Briefing.

Story E13.4 (ideias/sistema-artifacts/E13-4-loop-fp-briefing.md), PRD 04 FR-2,
ideias/epics-onda-5.md. `flag_suspected_fp.py` (E7.3, semgrep/scripts/) já escreve
suspeitas de falso-positivo em `project_controll/semgrep-fp-suspects.jsonl` toda vez que
um agente headless usa a válvula de escape do hook de pre-commit — mas até esta story
NINGUÉM lia esse log de volta. Este script fecha o loop do lado da LEITURA: consome o
`.jsonl`, filtra as suspeitas ainda `pending_ratification`, e devolve JSON pronto para a
persona repassar a `gerente_state.py write-snapshot --semgrep-fp-pending-json` — o mesmo
padrão de composição já usado por `gerente_escalation.py sample-decisions`/
`dead-letter-check` (Story E9.5) alimentando `write-snapshot`.

Este módulo é ESTRITAMENTE SOMENTE-LEITURA: nunca escreve em
`semgrep-fp-suspects.jsonl`, nunca escreve em `rules.yaml`, nunca escreve em
`estado-atual.yaml` diretamente (isso é responsabilidade de `write-snapshot`, chamado
separadamente pela persona com a saída deste script). Não existe nenhum `open(...,
"w"/"a")` neste arquivo — a ratificação de uma suspeita (aceitar como FP de verdade,
rejeitar, promover a regra) é gesto de OUTRO fluxo (dono/oráculo), fora do escopo desta
story — ver Dev Notes de E13.4 para a decisão registrada.

Dedup por fingerprint (`rule_id::file::line`, o mesmo definido em
`flag_suspected_fp.py::fingerprint`): o log é append-only e cronológico (cada chamada de
`flag_suspected_fp.py` só ANEXA), então a ÚLTIMA linha de um fingerprint é sempre o
status mais recente conhecido para aquele achado. Um fingerprint cuja última entrada NÃO
é `pending_ratification` (ex.: uma entrada posterior com `status: ratified` — escrita por
outro fluxo, nunca por este script) desaparece da lista de PENDENTES sem que nenhuma
linha do arquivo seja apagada ou reescrita — o log inteiro continua auditável e
git-trackable.

Comandos:
  list-pending   lê o log inteiro, agrupa por fingerprint mantendo só a entrada mais
                 recente de cada um, e devolve as que ainda estão `pending_ratification`.

Só biblioteca padrão (stdlib) — nenhuma dependência externa, mesma convenção dos scripts
irmãos deste diretório.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[2]  # scripts/ -> gerente/ -> project_controll/ -> raiz
DEFAULT_LOG = REPO_ROOT / "project_controll" / "semgrep-fp-suspects.jsonl"

PENDING_STATUS = "pending_ratification"


def read_entries(log_path: Path) -> tuple[list[dict[str, Any]], int, int]:
    """Lê o `.jsonl` inteiro, tolerante a arquivo ausente e a linhas malformadas
    isoladas (cada linha torta é ignorada individualmente — nunca aborta o arquivo
    inteiro, mesma disciplina de `gerente_briefing.py::read_diario_entries_for_cycle`).

    Devolve (entradas válidas em ordem de arquivo, total_de_linhas_nao_vazias,
    linhas_malformadas_ignoradas).
    """
    if not log_path.exists():
        return [], 0, 0
    try:
        text = log_path.read_text(encoding="utf-8")
    except OSError:
        return [], 0, 0
    entries: list[dict[str, Any]] = []
    total = 0
    malformed = 0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        total += 1
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            malformed += 1
            continue
        if not isinstance(obj, dict):
            malformed += 1
            continue
        entries.append(obj)
    return entries, total, malformed


def latest_by_fingerprint(entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Reduz a lista (em ordem de arquivo, append-only) para a última entrada de cada
    fingerprint — o log inteiro nunca é mutado, só esta view em memória é."""
    latest: dict[str, dict[str, Any]] = {}
    for entry in entries:
        fp = entry.get("fingerprint")
        if not fp:
            continue
        latest[fp] = entry  # sobrescreve — a entrada mais recente do MESMO fingerprint sempre vence
    return latest


def pending_suspects(latest: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Das entradas mais recentes por fingerprint, só as ainda `pending_ratification`.
    Ordem determinística: por fingerprint (string), para uma saída estável entre rodadas
    (o dict de entrada preserva ordem de inserção, mas não é a chave de ordenação certa
    — dois fingerprints diferentes não têm relação de precedência entre si)."""
    out: list[dict[str, Any]] = []
    for fp in sorted(latest.keys()):
        entry = latest[fp]
        if entry.get("status") != PENDING_STATUS:
            continue
        out.append({
            "fingerprint": fp,
            "rule_id": entry.get("rule_id"),
            "file": entry.get("file"),
            "line": entry.get("line"),
            "reason": entry.get("reason"),
            "status": entry.get("status"),
            "timestamp": entry.get("timestamp"),
        })
    return out


def cmd_list_pending(args: argparse.Namespace) -> int:
    log_path = Path(args.log)
    entries, total_lines, malformed = read_entries(log_path)
    latest = latest_by_fingerprint(entries)
    pending = pending_suspects(latest)
    result = {
        "ok": True,
        "log_path": str(log_path),
        "log_exists": log_path.exists(),
        "total_lines_read": total_lines,
        "malformed_lines_skipped": malformed,
        "unique_fingerprints": len(latest),
        "pending_count": len(pending),
        "pending": pending,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("list-pending", help="lista suspeitas de FP Semgrep ainda pending_ratification (somente-leitura)")
    pl.add_argument("--log", default=str(DEFAULT_LOG), help=f"path do log (default: {DEFAULT_LOG})")
    pl.add_argument("--pretty", action="store_true")
    pl.set_defaults(func=cmd_list_pending)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
