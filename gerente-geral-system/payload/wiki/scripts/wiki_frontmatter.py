"""wiki_frontmatter.py — parser minimalista de front-matter YAML dos docs da Wiki.

Extraído de `retrieve_slice.py` (E3.3) quando a máquina de retrieval por script foi
aposentada (Epic E17, decisão de arquitetura 2026-07-13 — retrieval agora é grep-native
via harness). Este parser NÃO é retrieval — é só um utilitário de leitura de front-matter,
reusado por scripts que ficam (ex.: `generate_recursive_index.py`). stdlib puro.

Suporta: escalares, listas em fluxo (`key: [a, b, c]`) e listas em bloco (`key:` seguido
de linhas `- item`). Qualquer outra coisa fica como string crua. Retorna {} se não houver
bloco de front-matter.
"""

from __future__ import annotations

from typing import Any

FRONT_MATTER_DELIM = "---"


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
