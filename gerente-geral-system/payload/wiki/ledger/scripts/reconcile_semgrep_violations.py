#!/usr/bin/env python3
"""reconcile_semgrep_violations.py — E7.5 curadoria noturna consome o log (PRD 04 FR-5).

Story E7.5 (ideias/sistema-artifacts/E7-5-contador-via-log.md), PRD 04 FR-5,
ideias/epics.md Epic E7. Rodado pela bibliotecária (E3.4, `curation-guide.md`)
como parte da curadoria noturna — NUNCA pelo Semgrep/hook em si, que só
apenda ao log (`semgrep/scripts/log_violations.py`), nunca escreve no Ledger
(dono único de escrita das transições é este script/a bibliotecária).

O que faz:
  1. Lê `project_controll/semgrep-violations.jsonl` a partir de um checkpoint
     (linha/byte-offset da última reconciliação — `--checkpoint`), nunca
     reprocessando as mesmas linhas duas vezes (idempotência entre execuções
     noturnas, mesma lógica de "não perde, não duplica" do changelog E4.7).
  2. Para cada violação cujo `rule_id` tem `metadata.ledger_entry` declarado em
     `semgrep/rules.yaml` (link introduzido por esta story) E cujo `rule_status`
     era `active` no momento do achado (só violações em modo GATE contam como
     "a regra pegou um problema real" — achados em modo `report` alimentam
     calibração, não o contador de utilidade, per FR-5 lido em conjunto com
     FR-1b): agrupa por `ledger_entry` e chama
     `transition_ledger_entry.py bump-utilidade --entry <path> --by <N>`.
  3. Achados sem `ledger_entry` mapeado, ou em modo `report`, são listados à
     parte no resumo ("sem link ao Ledger" / "modo report — não conta") —
     nunca descartados silenciosamente, só não incrementam contador.
  4. Avança o checkpoint só depois de todos os `bump-utilidade` terem
     sucesso (nunca avança sobre uma reconciliação parcialmente falha —
     próxima execução reprocessa as mesmas linhas em vez de perder achados).

Este script NÃO decide "utilidade persistentemente zero → aposentar" — essa
derivação já existe em `scripts/validate_ledger.py` (`poda_candidatos`, E4.3);
a curadoria noturna roda esse script de novo DEPOIS de reconciliar (contadores
atualizados) e usa `poda_candidatos` para popular a seção "Aposentadorias
propostas" do Relatório de Curadoria (`curation-guide.md` §5) — proposal-only,
nunca executado por este script (guardrail F8, `curation-guide.md` §1).

Uso:
    python3 reconcile_semgrep_violations.py \
        --log project_controll/semgrep-violations.jsonl \
        --rules semgrep/rules.yaml \
        --checkpoint project_controll/semgrep-violations-reconciled.checkpoint \
        [--dry-run]

Só biblioteca padrão (stdlib) — nenhuma dependência externa (mesma convenção
de independência entre scripts já usada em E3.3/E3.4/E3.5/E4.x — o parser de
`rules.yaml` abaixo é uma cópia minimalista, deliberadamente NÃO importada de
`semgrep/scripts/rules_yaml_lite.py`, pelo mesmo motivo).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
TRANSITION_SCRIPT = Path(__file__).resolve().parent / "transition_ledger_entry.py"

_RULE_START = re.compile(r"^  - id:\s*(.+?)\s*$")
_META_START = re.compile(r"^    metadata:\s*$")
_KV = re.compile(r"^      ([a-zA-Z_\-]+):\s*(.*)$")


def _strip(raw: str) -> str:
    raw = raw.split("  #")[0].strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
        raw = raw[1:-1]
    return raw


def parse_rules_minimal(rules_yaml_path: Path) -> dict[str, dict[str, str]]:
    """{rule_id: {"status": ..., "ledger_entry": ...}} — cópia minimalista, ver docstring."""
    rules: dict[str, dict[str, str]] = {}
    current_id: str | None = None
    in_metadata = False
    for line in rules_yaml_path.read_text(encoding="utf-8").splitlines():
        m = _RULE_START.match(line)
        if m:
            current_id = m.group(1)
            rules[current_id] = {"status": "report", "ledger_entry": ""}
            in_metadata = False
            continue
        if current_id is None:
            continue
        if _META_START.match(line):
            in_metadata = True
            continue
        if re.match(r"^    [a-zA-Z_\-]+:", line):
            in_metadata = False
            continue
        if in_metadata:
            kv = _KV.match(line)
            if kv:
                key, value = kv.group(1), _strip(kv.group(2))
                if key in ("status", "ledger_entry") and value:
                    rules[current_id][key] = value
    return rules


def read_checkpoint(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return int(path.read_text(encoding="utf-8").strip() or "0")
    except ValueError:
        return 0


def write_checkpoint(path: Path, line_count: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(str(line_count), encoding="utf-8")


def read_new_lines(log_path: Path, since_line: int) -> tuple[list[dict[str, Any]], int]:
    if not log_path.exists():
        return [], 0
    lines = log_path.read_text(encoding="utf-8").splitlines()
    new_lines = lines[since_line:]
    entries: list[dict[str, Any]] = []
    for line in new_lines:
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries, len(lines)


def reconcile(entries: list[dict[str, Any]], rules: dict[str, dict[str, str]]) -> dict[str, Any]:
    counted_by_entry: dict[str, int] = {}
    unlinked: list[dict[str, Any]] = []
    report_mode: list[dict[str, Any]] = []

    for e in entries:
        rule = rules.get(e.get("rule_id", ""), {})
        ledger_entry = rule.get("ledger_entry", "")
        status = rule.get("status", e.get("rule_status", "unknown"))

        if status != "active":
            report_mode.append(e)
            continue
        if not ledger_entry:
            unlinked.append(e)
            continue
        counted_by_entry[ledger_entry] = counted_by_entry.get(ledger_entry, 0) + 1

    return {"counted_by_entry": counted_by_entry, "unlinked": unlinked, "report_mode": report_mode}


def apply_bumps(counted_by_entry: dict[str, int], dry_run: bool) -> list[tuple[str, int, bool]]:
    results: list[tuple[str, int, bool]] = []
    for ledger_entry, count in counted_by_entry.items():
        candidate = Path(ledger_entry)
        entry_path = candidate if candidate.is_absolute() else REPO_ROOT / ledger_entry
        if dry_run:
            print(f"[dry-run] bump-utilidade --entry {ledger_entry} --by {count}")
            results.append((ledger_entry, count, True))
            continue
        proc = subprocess.run(
            [sys.executable, str(TRANSITION_SCRIPT), "bump-utilidade", "--entry", str(entry_path), "--by", str(count)],
            capture_output=True, text=True, check=False,
        )
        ok = proc.returncode == 0
        print(proc.stdout.strip() if ok else f"ERRO ao aplicar bump em {ledger_entry}: {proc.stderr.strip()}")
        results.append((ledger_entry, count, ok))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--rules", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if not args.log.exists():
        print(f"Log não existe ainda ({args.log}) — nada para reconciliar.")
        return 0
    if not args.rules.exists():
        print(f"erro: rules file não encontrado: {args.rules}", file=sys.stderr)
        return 2

    since_line = read_checkpoint(args.checkpoint)
    entries, total_lines = read_new_lines(args.log, since_line)

    if not entries:
        print(f"Nenhuma linha nova desde o checkpoint (linha {since_line}) — nada a reconciliar.")
        return 0

    rules = parse_rules_minimal(args.rules)
    result = reconcile(entries, rules)

    print(f"{len(entries)} violação(ões) nova(s) desde o checkpoint (linha {since_line} -> {total_lines}):")
    print(f"  contáveis (rule status=active, com ledger_entry): {sum(result['counted_by_entry'].values())} em {len(result['counted_by_entry'])} entrada(s)")
    print(f"  modo report (não contam, calibração): {len(result['report_mode'])}")
    print(f"  sem ledger_entry mapeado (não contam, gap registrado): {len(result['unlinked'])}")

    bump_results = apply_bumps(result["counted_by_entry"], args.dry_run)
    all_ok = all(ok for _, _, ok in bump_results)

    if all_ok and not args.dry_run:
        write_checkpoint(args.checkpoint, total_lines)
        print(f"Checkpoint avançado para linha {total_lines}.")
    elif args.dry_run:
        print("(dry-run: checkpoint NÃO avançado)")
    else:
        print("AVISO: algum bump-utilidade falhou — checkpoint NÃO avançado (próxima execução reprocessa).", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
