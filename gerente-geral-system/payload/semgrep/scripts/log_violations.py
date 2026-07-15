#!/usr/bin/env python3
"""semgrep/scripts/log_violations.py — E7.5 log→bibliotecária (PRD 04 FR-5).

Story E7.5 (ideias/sistema-artifacts/E7-5-contador-via-log.md), PRD 04 FR-5,
ideias/epics.md Epic E7.

Roda o Semgrep e appenda CADA achado, um por linha JSON, em
`project_controll/semgrep-violations.jsonl` — NUNCA escreve direto no Ledger
(dono único de escrita das transições/incrementos é a bibliotecária noturna,
E3.4/`curation-guide.md`). Isso resolve a contradição "sinal de CI" (PRD 01)
vs. "CLI local" (PRD 04, este script): a violação das 2h da manhã não muta
nenhum front-matter — ela vira log; `reconcile_semgrep_violations.py`
(rodado pela curadoria noturna) é quem, mais tarde e sob um único dono,
incrementa `contador-de-utilidade` via `transition_ledger_entry.py
bump-utilidade`.

Cada linha logada carrega `rule_id` + `rule_status` (report/active, lido de
`rules.yaml` no momento do achado) — NÃO resolve o link pra Ledger aqui (isso
é responsabilidade do reconciliador, que lê `rules.yaml` de novo no momento
da curadoria; um rule_id pode ganhar/perder seu `metadata.ledger_entry` entre
o momento do achado e o da curadoria, e queremos sempre o link mais atual).

Uso:
    python3 semgrep/scripts/log_violations.py                    # frontend/src + backend
    python3 semgrep/scripts/log_violations.py --diff              # só o diff
    python3 semgrep/scripts/log_violations.py --paths semgrep/fixtures
    python3 semgrep/scripts/log_violations.py --log /outro/path.jsonl

Escrita: append (`"a"`) + `flush()` + `os.fsync()` por chamada — não é a
primitiva de temp+rename de `transition_ledger_entry.py` (essa é para
REESCREVER um arquivo inteiro; aqui só ANEXAMOS linhas a um log
append-only, onde não há "versão anterior" para preservar atomicamente — o
único requisito de FR-5 é "nenhuma violação se perde", que append+fsync já
garante mesmo sob um crash logo após a escrita).

Degradação: se `uvx` estiver ausente, nada é logado (não há achado real para
registrar) — evento é appendado a `project_controll/semgrep-degraded-log.jsonl`
(mesmo log/formato de E7.2/E7.3), ruidosamente, nunca em silêncio.

Só biblioteca padrão (stdlib) — nenhuma dependência externa.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from compute_covered_manifest import append_degraded_log, uvx_available  # noqa: E402
from rules_yaml_lite import parse_rules  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "rules.yaml"
DEFAULT_PATHS = ["frontend/src", "backend"]
DEFAULT_LOG = REPO_ROOT / "project_controll" / "semgrep-violations.jsonl"
DEFAULT_DEGRADED_LOG = REPO_ROOT / "project_controll" / "semgrep-degraded-log.jsonl"


def git_changed_paths(repo_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACMR", "HEAD"],
        cwd=repo_root, capture_output=True, text=True, check=False,
    )
    staged = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACMR", "--cached"],
        cwd=repo_root, capture_output=True, text=True, check=False,
    )
    changed = set(result.stdout.splitlines()) | set(staged.stdout.splitlines())
    return sorted(p for p in changed if (repo_root / p).is_file())


def run_semgrep_json(config_path: Path, target_paths: list[str]) -> dict:
    cmd = ["uvx", "semgrep", "--config", str(config_path), "--json", *target_paths]
    proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, check=False)
    if proc.returncode not in (0, 1):
        raise RuntimeError(f"semgrep terminou com código {proc.returncode}: {proc.stderr}")
    return json.loads(proc.stdout)


def build_log_entries(payload: dict, rules: dict) -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    entries: list[dict] = []
    for r in payload.get("results", []):
        check_id = r.get("check_id", "?")
        rule_id = check_id.rsplit(".", 1)[-1] if "." in check_id else check_id
        rule = rules.get(rule_id, {})
        entries.append({
            "timestamp": now,
            "rule_id": rule_id,
            "rule_status": rule.get("status", "unknown"),
            "path": r.get("path", "?"),
            "line": r.get("start", {}).get("line", 0),
            "message": r.get("extra", {}).get("message", rule.get("message", "")),
        })
    return entries


def append_entries(log_path: Path, entries: list[dict]) -> None:
    if not entries:
        return
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        for entry in entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--paths", nargs="*", default=None)
    parser.add_argument("--diff", action="store_true")
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--degraded-log", type=Path, default=DEFAULT_DEGRADED_LOG)
    args = parser.parse_args(argv)

    if args.diff:
        target_paths = git_changed_paths(REPO_ROOT)
        if not target_paths:
            print("Nenhum arquivo modificado/staged — nada para escanear/logar.")
            return 0
    else:
        target_paths = args.paths if args.paths else DEFAULT_PATHS

    if not uvx_available():
        append_degraded_log(args.degraded_log, {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "degraded_reason": (
                "binário `uvx` ausente do PATH — log_violations.py (E7.5) não pôde "
                "rodar; nenhuma violação foi logada nesta invocação (não há achado "
                "real sem o binário rodando)."
            ),
        })
        print("AVISO (ruidoso): uvx ausente — nada logado, evento registrado em semgrep-degraded-log.jsonl", file=sys.stderr)
        return 2

    try:
        payload = run_semgrep_json(args.config, target_paths)
    except RuntimeError as exc:
        print(f"ERRO de ferramenta: {exc}", file=sys.stderr)
        return 2

    rules = parse_rules(args.config)
    entries = build_log_entries(payload, rules)
    append_entries(args.log, entries)

    print(f"{len(entries)} violação(ões) appendada(s) a {args.log}")
    for e in entries:
        print(f"  {e['rule_id']} [{e['rule_status']}]: {e['path']}:{e['line']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
