#!/usr/bin/env python3
"""validate_wiki_docs.py — E3.4 validação mecânica contra o catálogo de tipos.

Story E3.4 (ideias/sistema-artifacts/E3-4-bibliotecaria-proposal-only.md),
PRD 01 FR-9 (endurecido F8), ideias/epics.md Epic E3.

Dado a raiz da Wiki, valida cada documento mecanicamente contra o schema
publicado por wiki/document-types.md (Story E3.1):

  1. `tipo` presente e é um dos 13 slugs canônicos do catálogo (senão:
     "sem tipo" — mesmo critério de document-types.md § "Documento sem
     tipo declarado", com o mesmo carve-out para index.md/`tipo: reference`).
  2. Para os 6 tipos de gramática Ledger (decisão-técnica, decisão-de-produto,
     decisão-de-arquitetura, regra, padrão, anti-pattern): `estado` presente
     e válido; se `aposentada`, `causa-da-morte` obrigatória e não-vazia;
     se não `aposentada`, `causa-da-morte` presente é uma inconsistência
     sinalizável (não corrigida).
  3. `anti-pattern`: `selo` presente e um de 🟢/🟡/🔴.
  4. `contador-de-utilidade`, quando presente, é um inteiro (checagem de
     tipo leve; a mecânica completa de incremento é da Story E4.3).

Este script NUNCA corrige nada — só reporta violações (a bibliotecária
nunca conserta um documento sozinha, ver curation-guide.md §2.2). Não
duplica a checagem de `areas:` (isso é papel de retrieve_slice.py, Story
E3.3) nem julga duplicação semântica entre entradas (julgamento humano/LLM,
ver curation-guide.md §3) nem verifica o link de reversão (Story E4.2,
ainda não construída).

Uso:
    python3 validate_wiki_docs.py --wiki-root wiki
    python3 validate_wiki_docs.py --wiki-root wiki --json

Só biblioteca padrão (stdlib) — nenhuma dependência externa. Reusa o mesmo
parser de front-matter minimalista de retrieve_slice.py (subconjunto de
YAML: escalar, lista em fluxo, lista em bloco) — não é um parser YAML
completo.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

FRONT_MATTER_DELIM = "---"

CANONICAL_TIPOS = {
    "decisão-técnica",
    "decisão-de-produto",
    "decisão-de-arquitetura",
    "regra",
    "padrão",
    "anti-pattern",
    "nota-operacional",
    "spec",
    "ticket",
    "design-doc",
    "changelog",
    "timeline",
    "reference",
}

LEDGER_TIPOS = {
    "decisão-técnica",
    "decisão-de-produto",
    "decisão-de-arquitetura",
    "regra",
    "padrão",
    "anti-pattern",
}

VALID_ESTADOS = {"candidata", "ativa", "aposentada"}
VALID_SELOS = {"🟢", "🟡", "🔴"}


def _clean(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1]
    return value


def parse_front_matter(text: str) -> dict[str, Any]:
    """Parse the YAML front-matter block at the top of a markdown doc.

    Same minimalist parser as retrieve_slice.py (kept standalone here on
    purpose — this script has no import-time dependency on that one, so
    it can be run/tested in isolation).
    """
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

        if stripped.startswith("- ") and current_list_key is not None:
            fm.setdefault(current_list_key, [])
            fm[current_list_key].append(_clean(stripped[2:]))
            i += 1
            continue

        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
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
    """True for None, empty string, the literal string 'null', or absence."""
    if value is None:
        return True
    if isinstance(value, str) and value.strip().lower() in ("", "null"):
        return True
    return False


def validate_doc(rel_path: str, fm: dict[str, Any]) -> list[str]:
    """Return a list of violation strings for one document's front-matter.

    Empty list = no violations found by this script (does not mean the
    document is fully conformant to every rule in document-types.md —
    only to the mechanically-checkable subset this script covers).
    """
    violations: list[str] = []

    tipo = fm.get("tipo")
    if _is_missing(tipo):
        violations.append("sem `tipo` no front-matter")
        return violations  # nothing else to check without a known tipo
    if tipo not in CANONICAL_TIPOS:
        violations.append(f"`tipo: {tipo}` não é um dos 13 slugs canônicos de document-types.md")
        return violations

    if tipo not in LEDGER_TIPOS:
        return violations  # non-Ledger types: no MADR-state checks apply

    estado = fm.get("estado")
    if _is_missing(estado):
        violations.append(f"tipo `{tipo}` é Entrada de Ledger mas não declara `estado`")
    elif estado not in VALID_ESTADOS:
        violations.append(f"`estado: {estado}` inválido (esperado um de {sorted(VALID_ESTADOS)})")
    else:
        causa = fm.get("causa-da-morte")
        if estado == "aposentada" and _is_missing(causa):
            violations.append("`estado: aposentada` sem `causa-da-morte` (obrigatória)")
        elif estado != "aposentada" and not _is_missing(causa):
            violations.append(
                f"`causa-da-morte` presente ('{causa}') mas `estado: {estado}` != aposentada "
                "(inconsistência — deveria ser null/ausente)"
            )

    if tipo == "anti-pattern":
        selo = fm.get("selo")
        if _is_missing(selo):
            violations.append("tipo `anti-pattern` sem `selo` (obrigatório: 🟢, 🟡 ou 🔴)")
        elif selo not in VALID_SELOS:
            violations.append(f"`selo: {selo}` inválido (esperado um de {sorted(VALID_SELOS)})")

    contador = fm.get("contador-de-utilidade")
    if not _is_missing(contador):
        try:
            int(str(contador))
        except ValueError:
            violations.append(f"`contador-de-utilidade: {contador}` não é um inteiro")

    return violations


def scan_and_validate(wiki_root: Path) -> dict[str, Any]:
    """Walk wiki_root, validate every doc, return an OK/violations report.

    Excludes `index.md` (navigation, not knowledge) — same carve-out as
    document-types.md § "Documento sem tipo declarado" and
    retrieve_slice.py's scan. Docs with `tipo: reference` ARE included
    here (unlike retrieve_slice.py) because reference docs still have a
    `tipo` that can be mis-set — this script validates schema conformance,
    not feature-retrieval relevance.

    Also excludes any doc under a folder whose name starts with `_` (the
    project's non-canonical/staging convention — e.g. `_migration-staging/`),
    same exclusion `retrieve_slice.py` applies (Story E12.5, see
    `ideias/sistema-artifacts/E12-5-indice-mapa-pos-migracao.md`). Before
    this fix, this script scanned `_migration-staging/` and reported a
    schema violation for `_migration-staging/notes/pilot-subset-monolith.md`
    (a superseded E3.6 pilot doc, not part of the official tree) —
    consistent with `wiki/index.md`'s own declaration that `_`-prefixed
    folders "are not part of the official navigable tree, must not be
    indexed/read as ready knowledge". Applying the same exclusion here
    makes the convention hold across the whole toolchain, not just
    `retrieve_slice.py`.
    """
    ok: list[str] = []
    violations: dict[str, list[str]] = {}
    for path in sorted(wiki_root.rglob("*.md")):
        if path.name == "index.md":
            continue
        rel_parts = path.relative_to(wiki_root).parts
        if any(part.startswith("_") for part in rel_parts[:-1]):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        fm = parse_front_matter(text)
        rel = str(path.relative_to(wiki_root))
        doc_violations = validate_doc(rel, fm)
        if doc_violations:
            violations[rel] = doc_violations
        else:
            ok.append(rel)
    return {
        "wiki_root": str(wiki_root),
        "ok_count": len(ok),
        "ok": ok,
        "violation_count": len(violations),
        "violations": violations,
    }


def _print_human(result: dict[str, Any]) -> None:
    print(f"Wiki root: {result['wiki_root']}")
    print(f"Docs conformes: {result['ok_count']}")
    for p in result["ok"]:
        print(f"  ✓ {p}")
    print()
    print(f"Docs com violação ({result['violation_count']}):")
    if not result["violations"]:
        print("  (nenhuma)")
    for path, reasons in result["violations"].items():
        print(f"  ✗ {path}")
        for r in reasons:
            print(f"      - {r}")
    print()
    print(
        "Nota: violações são REPORTADAS, nunca corrigidas por este script "
        "nem pela bibliotecária (curation-guide.md §2.2)."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--wiki-root", required=True, type=Path, help="Raiz da árvore da Wiki a escanear")
    parser.add_argument("--json", action="store_true", help="Emite JSON em vez de texto legível")
    args = parser.parse_args(argv)

    if not args.wiki_root.exists():
        print(f"erro: wiki-root não existe: {args.wiki_root}", file=sys.stderr)
        return 2

    result = scan_and_validate(args.wiki_root)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        _print_human(result)

    # Exit code reflete violações — senão um gate futuro `validate_wiki_docs.py && ...`
    # passaria verde COM violações. Consumidores que leem o resultado estruturado não são afetados.
    return 0 if result["violation_count"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
