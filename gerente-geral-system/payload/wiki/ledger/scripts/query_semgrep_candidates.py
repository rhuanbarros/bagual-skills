#!/usr/bin/env python3
"""query_semgrep_candidates.py — E4.4 derivação da fila de candidatos a Semgrep.

Story E4.4 (ideias/sistema-artifacts/E4-4-selo-maturidade.md),
PRD 01 FR-8, ideias/epics.md Epic E4.

A fila de candidatos a regra Semgrep (PRD 04/Epic E7) NUNCA é uma lista mantida à mão
em paralelo — é uma QUERY sobre o selo de maturidade das entradas `anti-pattern` do
Ledger:

    candidato a Semgrep  <=>  selo == 🟢  AND  estado != aposentada  AND  automatizado != true

  - selo != 🟢               -> nunca candidato (🟡 híbrido, 🔴 só-humano ficam fora,
                                 mesmo que `automatizado` esteja ausente/false).
  - estado == aposentada     -> nunca candidato, MESMO com selo 🟢 — cobre tanto a causa
                                 "redundante com ferramenta nativa" (ESLint/pyright já
                                 cobre, não precisa de Semgrep) quanto qualquer outra
                                 aposentadoria (entrada morta não gera enforcement novo).
  - automatizado == true     -> já existe uma regra Semgrep autorada para este
                                 anti-pattern (PRD 04/E7 já rodou) — a entrada continua
                                 VIVA (não aposentada), só sai da fila porque já foi
                                 atendida.

Este script só LÊ entradas `tipo: anti-pattern` (outros tipos-de-Ledger não têm `selo`
nem participam desta fila — `regra` tem seu próprio ciclo de utilidade, ver E4.3). Não
escreve nada; a autoria da regra Semgrep em si é o PRD 04/Epic E7, fora de escopo aqui.

Uso:
    python3 query_semgrep_candidates.py --ledger-root wiki/ledger
    python3 query_semgrep_candidates.py --ledger-root wiki/ledger --json

Só biblioteca padrão (stdlib) — nenhuma dependência externa. Reusa o parser de
front-matter minimalista de `validate_ledger.py` (mantido standalone aqui de propósito,
mesma convenção de independência entre scripts já usada em E3.3/E3.4/E3.5).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

FRONT_MATTER_DELIM = "---"
VALID_SELOS = {"🟢", "🟡", "🔴"}


def _clean(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1]
    return value


def parse_front_matter(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != FRONT_MATTER_DELIM:
        return {}

    fm: dict[str, Any] = {}
    current_list_key: str | None = None
    i = 1
    while i < len(lines):
        line = lines[i]
        if line.strip() == FRONT_MATTER_DELIM:
            break
        stripped = line.strip()

        if stripped.startswith("#"):
            i += 1
            continue

        if stripped.startswith("- ") and current_list_key is not None:
            fm.setdefault(current_list_key, [])
            fm[current_list_key].append(_clean(stripped[2:]))
            i += 1
            continue

        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.split("#")[0].strip() if not value.strip().startswith('"') else value.strip()
            if value == "":
                current_list_key = key
                fm.setdefault(key, [])
            elif value.startswith("[") and value.endswith("]"):
                inner = value[1:-1].strip()
                fm[key] = [_clean(v) for v in inner.split(",") if v.strip()] if inner else []
                current_list_key = None
            else:
                fm[key] = _clean(value)
                current_list_key = None
        i += 1
    return fm


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip().lower() in ("", "null"):
        return True
    return False


def _is_true(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def scan_anti_patterns(ledger_root: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in sorted(ledger_root.rglob("*.md")):
        if path.name in ("index.md", "template-entrada.md", "README.md"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        fm = parse_front_matter(text)
        if fm.get("tipo") != "anti-pattern":
            continue
        entries.append(
            {
                "path": str(path.relative_to(ledger_root)),
                "selo": fm.get("selo"),
                "estado": fm.get("estado"),
                "causa_da_morte": fm.get("causa-da-morte"),
                "automatizado": _is_true(fm.get("automatizado", "false")),
            }
        )
    return entries


def classify(entry: dict[str, Any]) -> tuple[bool, str]:
    """Retorna (é_candidato, motivo_de_exclusão_ou_'candidato')."""
    selo = entry["selo"]
    estado = entry["estado"]
    automatizado = entry["automatizado"]

    if selo not in VALID_SELOS:
        return False, f"selo inválido/ausente ('{selo}') — não classificável"
    if selo != "🟢":
        return False, f"selo '{selo}' != 🟢 (híbrido/só-humano, fora da fila Semgrep)"
    if estado == "aposentada":
        causa = entry.get("causa_da_morte") or "(sem causa registrada)"
        return False, f"estado aposentada (causa: '{causa}') — morta, não gera trabalho de enforcement novo"
    if automatizado:
        return False, "automatizado:true — regra Semgrep já autorada para este anti-pattern (PRD 04/E7)"
    return True, "candidato"


def run_query(ledger_root: Path) -> dict[str, Any]:
    entries = scan_anti_patterns(ledger_root)
    candidates: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for e in entries:
        is_candidate, reason = classify(e)
        row = {"path": e["path"], "selo": e["selo"], "estado": e["estado"], "reason": reason}
        (candidates if is_candidate else excluded).append(row)

    return {
        "ledger_root": str(ledger_root),
        "anti_pattern_count": len(entries),
        "candidate_count": len(candidates),
        "candidates": candidates,
        "excluded_count": len(excluded),
        "excluded": excluded,
        "filter": "selo == 🟢 AND estado != aposentada AND automatizado != true",
    }


def _print_human(result: dict[str, Any]) -> None:
    print(f"Ledger root: {result['ledger_root']}")
    print(f"Entradas anti-pattern escaneadas: {result['anti_pattern_count']}")
    print(f"Filtro: {result['filter']}")
    print()
    print(f"Candidatos a regra Semgrep ({result['candidate_count']}):")
    if not result["candidates"]:
        print("  (nenhum)")
    for c in result["candidates"]:
        print(f"  🎯 {c['path']}")
    print()
    print(f"Excluídos da fila, com motivo ({result['excluded_count']}):")
    if not result["excluded"]:
        print("  (nenhum)")
    for c in result["excluded"]:
        print(f"  · {c['path']}  — {c['reason']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ledger-root", required=True, type=Path, help="Raiz da árvore do Ledger (ou da Wiki) a escanear")
    parser.add_argument("--json", action="store_true", help="Emite JSON em vez de texto legível")
    args = parser.parse_args(argv)

    if not args.ledger_root.exists():
        print(f"erro: ledger-root não existe: {args.ledger_root}", file=sys.stderr)
        return 2

    result = run_query(args.ledger_root)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        _print_human(result)

    return 0


if __name__ == "__main__":
    sys.exit(main())
