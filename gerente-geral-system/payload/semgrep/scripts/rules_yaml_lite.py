#!/usr/bin/env python3
"""semgrep/scripts/rules_yaml_lite.py — E7.2/E7.5 parser minimalista de `rules.yaml`.

`rules.yaml` é YAML de verdade, mas este projeto evita depender de PyYAML nos
scripts stdlib-only da fiação nativa (mesma convenção deliberada usada em
`wiki/ledger/scripts/*.py` — ver `query_semgrep_candidates.py`,
"mesma convenção de independência entre scripts"). Este módulo faz o mesmo
para `semgrep/rules.yaml`: um parser por indentação, tolerante, que extrai
SÓ os campos que os scripts de E7.2/E7.5 precisam — não é um parser YAML
genérico (não lida com todo o espaço de sintaxe YAML, só a forma real que
`rules.yaml` usa, escrita por E7.1).

Campos extraídos por regra:
  - id                       (`- id: <valor>`, início do bloco de uma regra)
  - status                   (`metadata.status`, default "report" se ausente)
  - author                   (`metadata.author`, default "" se ausente)
  - ledger_entry             (`metadata.ledger_entry`, opcional — path relativo
                               ao repo-root para a Entrada de Ledger `tipo: regra`
                               ou `tipo: anti-pattern` de onde a regra nasceu;
                               convenção introduzida por E7.5 — nenhuma das 4
                               regras originais de E7.1 tinha esse campo)
  - message                  (primeira linha não-vazia do bloco `message:`, para
                               logs/relatórios legíveis — best-effort)

Uso (como módulo, não como CLI — importado por compute_covered_manifest.py e
log_violations.py):
    from rules_yaml_lite import parse_rules
    rules = parse_rules(Path("semgrep/rules.yaml"))   # -> {rule_id: {...}}
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_RULE_START = re.compile(r"^  - id:\s*(.+?)\s*$")
_META_START = re.compile(r"^    metadata:\s*$")
_MESSAGE_START = re.compile(r"^    message:\s*(.*)$")
_KV = re.compile(r"^      ([a-zA-Z_\-]+):\s*(.*)$")


def _strip_value(raw: str) -> str:
    raw = raw.split("  #")[0].strip()  # strip trailing inline comment (2+ spaces before #)
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in ("'", '"'):
        raw = raw[1:-1]
    return raw


def parse_rules(rules_yaml_path: Path) -> dict[str, dict[str, Any]]:
    """Retorna {rule_id: {"status": str, "author": str, "ledger_entry": str|None, "message": str}}."""
    text = rules_yaml_path.read_text(encoding="utf-8")
    lines = text.splitlines()

    rules: dict[str, dict[str, Any]] = {}
    current_id: str | None = None
    in_metadata = False
    in_message = False

    for line in lines:
        rule_match = _RULE_START.match(line)
        if rule_match:
            current_id = rule_match.group(1)
            rules[current_id] = {"status": "report", "author": "", "ledger_entry": None, "message": ""}
            in_metadata = False
            in_message = False
            continue

        if current_id is None:
            continue

        if _META_START.match(line):
            in_metadata = True
            in_message = False
            continue

        if _MESSAGE_START.match(line):
            in_message = True
            in_metadata = False
            inline = _MESSAGE_START.match(line).group(1).strip()
            if inline and inline not in (">-", "|", ">", "|-"):
                rules[current_id]["message"] = _strip_value(inline)
            continue

        # A line at 4-space indent that isn't metadata/message starts a new
        # top-level rule key (patterns, paths, languages, ...) -> leave both blocks.
        if re.match(r"^    [a-zA-Z_\-]+:", line):
            in_metadata = False
            in_message = False
            continue

        if in_metadata:
            kv = _KV.match(line)
            if kv:
                key, value = kv.group(1), _strip_value(kv.group(2))
                if key == "status" and value:
                    rules[current_id]["status"] = value
                elif key == "author" and value:
                    rules[current_id]["author"] = value
                elif key == "ledger_entry" and value:
                    rules[current_id]["ledger_entry"] = value
            continue

        if in_message:
            stripped = line.strip()
            if stripped and not rules[current_id]["message"]:
                rules[current_id]["message"] = stripped
                in_message = False

    return rules


if __name__ == "__main__":
    import json
    import sys

    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "rules.yaml"
    print(json.dumps(parse_rules(path), indent=2, ensure_ascii=False))
