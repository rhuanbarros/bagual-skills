#!/usr/bin/env python3
"""reconcile_index_counts.py — Story E16.4: drift de contagem + reconciliação do Ledger.

Story E16.4 (`ideias/sistema-artifacts/E16-4-curadoria-indice-ledger.md`),
`ideias/epics-onda-5.md` § Story E16.4 (T3.3).

**Achado real que motivou esta story:** `generate_recursive_index.py` (E12.5)
regenera o cabeçalho mecânico `## Files (N documentos)` + a listagem de cada
subpasta do Ledger corretamente a cada execução (Story E16.1, por exemplo,
rodou o script e ele escreveu `regra/index.md` com a contagem real, 21) —
mas a FRASE INTRODUTÓRIA de cada subpasta ("122 entradas: 13 pré-existentes
+ 108 migradas...") é **texto hard-coded** na lista `FOLDERS` daquele script,
escrita uma única vez na Story E12.5 e nunca mais atualizada. Toda vez que
uma story nova emite uma Entrada de Ledger (`on_complete`) sem também editar
manualmente essas strings hard-coded, a prosa fica presa no número de E12.5
enquanto o cabeçalho mecânico (que É recalculado) segue crescendo — daí o
drift "índice diz 122, tem 125 de verdade" descrito no epic-fonte. O mesmo
vale para os roll-ups agregados em `ledger/index.md` e na raiz `wiki/index.md`
(nunca recalculados por nenhum script, só editados à mão em cada story que
lembrou de fazê-lo).

Este script NÃO conserta nada — só recalcula as contagens REAIS por
subtipo do Ledger (contra os diretórios de verdade) e compara contra cada
lugar da prosa dos índices que hoje DECLARA uma contagem, reportando
divergência. Mesma filosofia read-only de `validate_wiki_docs.py`/
`validate_ledger.py` (E3.4/E4.x): a bibliotecária nunca conserta um
documento sozinha, só relata — a correção pontual é decisão humana (ou de
uma story dedicada, como esta mesma story fez uma única vez para zerar o
drift acumulado até aqui).

Onde a prosa declara uma contagem (varre 3 lugares, por documento):
  1. O bullet de roll-up por subtipo dentro de `ledger/index.md` §
     Subdirectories (ex.: "**[anti-pattern/](...)** — 104 entradas...").
  2. O parêntese de roll-up por subtipo dentro da raiz `wiki/index.md` §
     Subdirectories, bullet `ledger/` (ex.: "(decisao-tecnica/ 122,
     anti-pattern/ 104, ...) + padrao/ (1)").
  3. Para as 5 subpastas que passaram do limiar e ganharam `index.md`
     próprio (Story E12.5): o cabeçalho mecânico `## Files (N documentos)`
     E a frase de prosa "N entradas" no parágrafo de abertura do próprio
     `index.md` da subpasta.

A extração usa uma âncora mecânica simples e documentada (primeiro inteiro
que aparece na mesma linha, depois da primeira ocorrência do token
`"<subpasta>/"`) — não é um parser de Markdown genérico. Se a prosa mudar de
formato a ponto de a âncora não casar mais, o campo correspondente aparece
como `declared: null` no relatório (nunca finge um número errado silenciosamente).

Uso:
    python3 reconcile_index_counts.py --ledger-root wiki/ledger --wiki-root wiki
    python3 reconcile_index_counts.py --ledger-root wiki/ledger --wiki-root wiki --json

Exit code: 0 se nenhuma divergência encontrada, 1 se houver >=1 divergência
(útil para a curadoria noturna decidir se cita isto no Relatório — ver
`curation-guide.md` § 2.1). O script nunca escreve em nenhum arquivo.

Só biblioteca padrão (stdlib) — nenhuma dependência externa.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# subpasta do Ledger -> tipo canônico esperado (mesmo vocabulário de
# validate_ledger.py / document-types.md).
SUBTYPE_FOLDERS: dict[str, str] = {
    "decisao-tecnica": "decisão-técnica",
    "anti-pattern": "anti-pattern",
    "decisao-de-produto": "decisão-de-produto",
    "decisao-de-arquitetura": "decisão-de-arquitetura",
    "regra": "regra",
    "padrao": "padrão",
}

# Subpastas que passaram do limiar de 5 documentos e ganharam index.md
# próprio (Story E12.5) — só estas têm cabeçalho "## Files (N documentos)"
# + prosa "N entradas" para checar isoladamente; `padrao/` fica sempre
# listada inline em `ledger/index.md` (hoje 5 docs, ainda não > limiar).
FOLDERS_WITH_OWN_INDEX = {
    "decisao-tecnica",
    "anti-pattern",
    "decisao-de-produto",
    "decisao-de-arquitetura",
    "regra",
}


def count_real_entries(ledger_root: Path, folder: str) -> int:
    """Conta .md reais dentro de ledger/<folder>/ (não-recursivo, exclui
    index.md — o mesmo critério de contagem que generate_recursive_index.py
    usa para o cabeçalho `## Files (N documentos)`)."""
    d = ledger_root / folder
    if not d.is_dir():
        return 0
    return sum(1 for p in d.glob("*.md") if p.name != "index.md")


def first_int_after_token(text: str, token: str) -> int | None:
    """Acha a 1a linha contendo `token` e devolve o 1o inteiro que aparece
    nessa linha, depois da 1a ocorrência do token.

    Âncora mecânica simples, documentada em vez de escondida: cobre os 2
    formatos de prosa reais hoje em uso —
      "**[anti-pattern/](./anti-pattern/index.md)** — 104 entradas ..."
      "...( decisao-tecnica/ 122, anti-pattern/ 104, ...) + padrao/ (1)."
    Se a prosa mudar de formato a ponto de não casar, devolve None (o
    chamador reporta `declared: null`, nunca inventa um número)."""
    for line in text.splitlines():
        idx = line.find(token)
        if idx == -1:
            continue
        rest = line[idx + len(token):]
        m = re.search(r"\d+", rest)
        if m:
            return int(m.group(0))
    return None


def subdirectories_section(text: str) -> str:
    """Recorta o texto entre o heading `## Subdirectories` e o próximo
    heading `## `/`### ` (ou o fim do arquivo). Os bullets por subpasta
    vivem exclusivamente aí — recortar a seção ANTES de procurar o
    folder-token evita casar com uma menção solta do mesmo nome de pasta
    num parágrafo de prosa em outro lugar do arquivo (ex.: um parágrafo de
    reconciliação que cita `padrao/` de passagem, sem ser o bullet de
    contagem real)."""
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == "## Subdirectories":
            start = i + 1
            break
    if start is None:
        return ""
    end = len(lines)
    for i in range(start, len(lines)):
        if lines[i].startswith("## ") or lines[i].startswith("### "):
            end = i
            break
    return "\n".join(lines[start:end])


def extract_declared(ledger_root: Path, wiki_root: Path) -> dict[str, dict[str, int | None]]:
    """Para cada subtipo, extrai a contagem DECLARADA em cada local de
    prosa conhecido do sistema de índices. Só leitura — nunca escreve."""
    declared: dict[str, dict[str, int | None]] = {f: {} for f in SUBTYPE_FOLDERS}

    ledger_index_path = ledger_root / "index.md"
    wiki_index_path = wiki_root / "index.md"
    ledger_index_text = ledger_index_path.read_text(encoding="utf-8") if ledger_index_path.exists() else ""
    wiki_index_text = wiki_index_path.read_text(encoding="utf-8") if wiki_index_path.exists() else ""

    # Recorta cada arquivo na sua seção "## Subdirectories" antes de
    # procurar — os bullets de contagem por subpasta vivem só ali; sem
    # isso, qualquer menção solta ao nome de uma subpasta num parágrafo de
    # prosa (histórico ou de reconciliação) em outro lugar do arquivo
    # casaria primeiro e devolveria um número errado.
    ledger_subdirs = subdirectories_section(ledger_index_text)
    wiki_subdirs = subdirectories_section(wiki_index_text)

    # Dentro de wiki/index.md § Subdirectories, o roll-up por subtipo do
    # Ledger vive num único bullet (o link `[ledger/](./ledger/index.md)`)
    # — ancora nele para não colidir com o bullet de `nota-operacional/`
    # ou outra subpasta que por acaso preceda `ledger/` na lista.
    wiki_rollup_line = ""
    for line in wiki_subdirs.splitlines():
        if "[ledger/](./ledger/index.md)" in line:
            wiki_rollup_line = line
            break

    for folder in SUBTYPE_FOLDERS:
        token = f"{folder}/"
        declared[folder]["ledger_index_rollup"] = first_int_after_token(ledger_subdirs, token)
        declared[folder]["wiki_root_index_rollup"] = first_int_after_token(wiki_rollup_line, token)

        if folder in FOLDERS_WITH_OWN_INDEX:
            own_index_path = ledger_root / folder / "index.md"
            if own_index_path.exists():
                own_text = own_index_path.read_text(encoding="utf-8")
                header_m = re.search(r"## Files \((\d+) documentos\)", own_text)
                declared[folder]["own_index_header"] = int(header_m.group(1)) if header_m else None
                # Preferir o marcador explícito de reconciliação ("contagem
                # real atual é **N entradas**"), quando presente, sobre o
                # 1o "N entradas" solto do parágrafo — um index.md pode
                # citar legitimamente o número histórico da migração
                # ANTES do número reconciliado atual na mesma frase (ver
                # `decisao-tecnica/index.md`), e o objetivo aqui é
                # comparar contra o número que o texto afirma ser o ATUAL,
                # não o primeiro número que aparecer.
                current_m = re.search(r"real atual é \*\*(\d+) entradas\*\*", own_text)
                if current_m:
                    declared[folder]["own_index_intro_prose"] = int(current_m.group(1))
                else:
                    intro_m = re.search(r"(\d+)\s+entradas", own_text)
                    declared[folder]["own_index_intro_prose"] = int(intro_m.group(1)) if intro_m else None

    return declared


def reconcile(ledger_root: Path, wiki_root: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ledger_root": str(ledger_root),
        "wiki_root": str(wiki_root),
        "subtypes": {},
        "divergence_count": 0,
    }
    declared_all = extract_declared(ledger_root, wiki_root)

    for folder in SUBTYPE_FOLDERS:
        real = count_real_entries(ledger_root, folder)
        declared = declared_all[folder]
        mismatches = {src: val for src, val in declared.items() if val is not None and val != real}
        result["subtypes"][folder] = {
            "tipo": SUBTYPE_FOLDERS[folder],
            "real": real,
            "declared": declared,
            "mismatches": mismatches,
        }
        result["divergence_count"] += len(mismatches)

    result["real_total"] = sum(v["real"] for v in result["subtypes"].values())
    return result


def _print_human(result: dict[str, Any]) -> None:
    print(f"Ledger root: {result['ledger_root']}")
    print(f"Wiki root:   {result['wiki_root']}")
    print()
    for folder, info in result["subtypes"].items():
        status = "OK" if not info["mismatches"] else "DRIFT"
        print(f"[{status}] {folder}/ (tipo: {info['tipo']}) — real={info['real']}")
        for src, val in info["declared"].items():
            marker = "  " if (val is None or val == info["real"]) else "!!"
            print(f"    {marker} {src}: {val}")
    print()
    print(f"Total real (soma dos 6 subtipos): {result['real_total']}")
    print(f"Divergências encontradas: {result['divergence_count']}")
    print()
    print(
        "Nota: este script é REPORT-ONLY — nunca escreve em nenhum index.md. "
        "Divergências reportadas aqui exigem correção manual (ver curation-guide.md § 2.1)."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ledger-root", required=True, type=Path, help="Raiz do Ledger (ex.: wiki/ledger)")
    parser.add_argument("--wiki-root", required=True, type=Path, help="Raiz da Wiki (ex.: wiki)")
    parser.add_argument("--json", action="store_true", help="Emite JSON em vez de texto legível")
    args = parser.parse_args(argv)

    if not args.ledger_root.exists():
        print(f"erro: ledger-root não existe: {args.ledger_root}", file=sys.stderr)
        return 2
    if not args.wiki_root.exists():
        print(f"erro: wiki-root não existe: {args.wiki_root}", file=sys.stderr)
        return 2

    result = reconcile(args.ledger_root, args.wiki_root)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        _print_human(result)

    return 0 if result["divergence_count"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
