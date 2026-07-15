#!/usr/bin/env python3
"""generate_recursive_index.py — Story E12.5: runs the E3.2 recursive-index
algorithm (bmad-index-docs + `_bmad/custom/bmad-index-docs.toml` override)
directly against the real, post-migration Wiki corpus (Stories E12.1-E12.4:
251 `nota-operacional` + 122 `decisao-tecnica` + 104 `anti-pattern` + 49
`decisao-de-produto` + 9 `decisao-de-arquitetura` + 18 `regra` = 553 real
documents, plus the pre-existing 1 `padrao`).

Story E12.5 (`ideias/sistema-artifacts/E12-5-indice-mapa-pos-migracao.md`)
explicitly authorizes this: "if headless-invoking the skill is impractical
here, run its underlying recursive-index logic directly and note that — the
AC is a real recursive index over the corpus, produced by the E3.2
mechanism, not hand-written." A live Agent-tool fan-out (bmad-index-docs'
documented recursion mechanism) at 553 documents would mean hundreds of
subagent invocations for a purely mechanical listing step — impractical at
this scale. This script instead applies the exact override rules
mechanically:

  - threshold = 5 immediate docs (default, `_bmad/custom/bmad-index-docs.toml`)
  - a folder qualifies for its own index.md iff (a) immediate .md count > 5,
    which is the case for every folder this script targets
  - each per-doc curated description is READ FROM THE DOC'S REAL H1 TITLE
    (never inferred from the filename) + a `[tipo: X]` tag read from the
    real front-matter + `areas:` when present (E3.3 formalization)
  - this script only ever WRITES index.md for the leaf/near-leaf folders
    themselves (`nota-operacional/`, `ledger/anti-pattern/`,
    `ledger/decisao-tecnica/`, `ledger/decisao-de-arquitetura/`,
    `ledger/decisao-de-produto/`, `ledger/regra/`) — it never lists a
    grandchild inline and never opens a document outside the folder it is
    indexing. The PARENT-links-CHILD wiring (root index.md ↔ ledger/index.md
    ↔ these folders) is done by hand in the same story, preserving the
    curated migration-warning prose already written by Stories E12.1-E12.4
    instead of overwriting it mechanically.

stdlib-only. Reuses `retrieve_slice.py`'s front-matter parser (E3.3) instead
of re-implementing one.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from wiki_frontmatter import parse_front_matter  # noqa: E402  (shared parser, E17)

WIKI_ROOT = Path(__file__).resolve().parent.parent


def doc_title(path: Path, front_matter_end: int, lines: list[str]) -> str:
    """Real H1 title of a doc — read from content, never from the filename."""
    i = front_matter_end
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
        i += 1
    return path.stem


def load_doc(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    fm = parse_front_matter(text)
    # find where front-matter ends, to search for the H1 after it
    end = 0
    if lines and lines[0].strip() == "---":
        end = 1
        while end < len(lines) and lines[end].strip() != "---":
            end += 1
        end += 1
    areas = fm.get("areas", [])
    if isinstance(areas, str):
        areas = [areas] if areas else []
    return {
        "path": path,
        "name": path.name,
        "tipo": fm.get("tipo", ""),
        "estado": fm.get("estado", ""),
        "areas": areas,
        "title": doc_title(path, end, lines),
    }


def rel_to_doc_types(folder: Path) -> str:
    depth = len(folder.relative_to(WIKI_ROOT).parts)
    return "../" * depth + "document-types.md"


def format_entry(d: dict[str, Any]) -> str:
    tag = f"`[tipo: {d['tipo']}]`" if d["tipo"] else "`[sem tipo — ver document-types.md]`"
    areas_str = f" `areas: [{', '.join(d['areas'])}]`" if d["areas"] else ""
    estado_str = f" (estado: {d['estado']})" if d["estado"] and d["estado"] != "candidata" else ""
    return f"- **[{d['name']}](./{d['name']})** — {d['title']}.{areas_str}{estado_str} {tag}"


def render_flat_folder_index(folder: Path, heading: str, intro: str) -> str:
    """Renders an index.md for a folder whose immediate docs are all leaf
    documents (no qualifying subfolders) — the common case for the 6
    migrated Ledger/nota-operacional folders this script targets."""
    docs = sorted(
        (p for p in folder.glob("*.md") if p.name != "index.md"),
        key=lambda p: p.name,
    )
    entries = [load_doc(p) for p in docs]

    lines: list[str] = []
    lines.append("---")
    lines.append("tipo: reference")
    lines.append("---")
    lines.append("")
    lines.append(heading)
    lines.append("")
    lines.append(f"Documento-tipos: ver [`{rel_to_doc_types(folder)}`]({rel_to_doc_types(folder)}) — catálogo canônico dos padrões de escrita.")
    lines.append("")
    lines.append(intro)
    lines.append("")
    lines.append(f"## Files ({len(entries)} documentos)")
    lines.append("")
    for d in entries:
        lines.append(format_entry(d))
    lines.append("")
    return "\n".join(lines)


FOLDERS = [
    {
        "path": WIKI_ROOT / "nota-operacional",
        "heading": "# nota-operacional/ — notas operacionais migradas de `notes.md` (Story E12.1)",
        "intro": (
            "Árvore **oficial** (fora de `../_migration-staging/`) com os 251 documentos "
            "`nota-operacional` do fatiamento completo de `_bmad-output/notes.md` "
            "(Story E12.1, `ideias/sistema-artifacts/E12-1-fatiar-notes.md`) — cada um com "
            "`areas:` real por julgamento curatorial (vocabulário seed + `frontend`/`backend`/"
            "`testing`/`infra`/`qa`/`sistema-meta`/`landing`, zero gaps) e "
            "`migration_status: migrado-pendente-indexacao-e12-5-cutover-e12-6`. Indexado "
            "recursivamente por esta pasta (Story E12.5) — ainda **fora do cutover** "
            "(`area-cutover-status.json` permanece 100% `monolito`, Story E12.6, "
            "owner-gated). `_bmad-output/notes.md` continua byte-a-byte idêntico e é a fonte "
            "lida por `persistent_facts` em 100% das áreas até o dono ratificar o cutover."
        ),
    },
    {
        "path": WIKI_ROOT / "ledger" / "anti-pattern",
        "heading": "# ledger/anti-pattern/ — Entradas `anti-pattern` do Ledger",
        "intro": (
            "104 entradas na migração original: 12 pré-existentes (exemplos/`on_complete` de "
            "stories anteriores, Ondas 2-4) + 92 migradas de `_bmad-output/anti-patterns.md` "
            "pela Story E12.3 (MADR completo + `## Selo de maturidade` — E4.4 — com racional "
            "individual, nunca 🟡 por omissão; distribuição das 92 novas: 15 🟢, 45 🟡, 32 🔴), "
            "`estado: candidata` salvo indicação em contrário, monólito preservado "
            "intacto/read-through. **Achado real de curadoria (E12.3, não corrigido — fica "
            "para curadoria futura):** 5 destas 104 entradas duplicam conceitualmente uma "
            "lição já registrada por uma entrada `on_complete` anterior "
            "(E8.2/E8.3/E9.1/E11.1/E12.1) sob título diferente — ver "
            "`ideias/sistema-artifacts/E12-3-antipatterns-madr.md` § Dev Notes para a lista "
            "dos 5 pares. **Reconciliado pela Story E16.4 (2026-07-12):** contagem real atual "
            "é **106 entradas** (2 novas via `on_complete` de stories posteriores a E12.5, "
            "incluindo a própria Entrada de Ledger que a Story E16.4 emitiu registrando este "
            "achado) — ver `wiki/scripts/reconcile_index_counts.py`; o cabeçalho "
            "`## Files` abaixo já é sempre a contagem mecânica correta."
        ),
    },
    {
        "path": WIKI_ROOT / "ledger" / "decisao-tecnica",
        "heading": "# ledger/decisao-tecnica/ — Entradas `decisão-técnica` do Ledger",
        "intro": (
            "122 entradas na migração original: 13 pré-existentes (exemplos/`on_complete` de "
            "stories anteriores) + 108 migradas de `_bmad-output/decisions.md` pela Story "
            "E12.2 (MADR completo — `## Contexto` embute o texto original **verbatim, "
            "íntegro**; `## Decisão`/`## Alternativas`/`## Consequências` extraem "
            "sub-parágrafos rotulados, nunca parafraseiam), `estado: candidata` salvo "
            "indicação em contrário, monólito preservado intacto/read-through. 5 entradas "
            "migradas carregam `tipo_ratificacao_pendente: true` (fronteira "
            "técnica/arquitetura — ver `ledger/decisao-de-arquitetura/`). **Reconciliado "
            "pela Story E16.4 (2026-07-12):** contagem real atual é **125 entradas** (3 "
            "novas via `on_complete` de stories posteriores a E12.5) — ver "
            "`wiki/scripts/reconcile_index_counts.py`; o cabeçalho `## Files` "
            "abaixo já é sempre a contagem mecânica correta."
        ),
    },
    {
        "path": WIKI_ROOT / "ledger" / "decisao-de-arquitetura",
        "heading": "# ledger/decisao-de-arquitetura/ — Entradas `decisão-de-arquitetura` do Ledger",
        "intro": (
            "9 entradas, pasta criada pela Story E12.2 (antes só um slug reservado no schema "
            "E4.1, sem nenhuma entrada real) — todas migradas de `_bmad-output/decisions.md`, "
            "mesma técnica MADR verbatim de `decisao-tecnica/`. 5 delas carregam "
            "`tipo_ratificacao_pendente: true` (fronteira técnica/arquitetura — sinal explícito "
            "para ratificação humana, nunca um `tipo` silenciosamente adivinhado pela migração)."
        ),
    },
    {
        "path": WIKI_ROOT / "ledger" / "decisao-de-produto",
        "heading": "# ledger/decisao-de-produto/ — Entradas `decisão-de-produto` do Ledger",
        "intro": (
            "49 entradas na migração original, pasta criada pela Story E12.4 (antes só um "
            "slug reservado no schema E4.1) — todas migradas de "
            "`_bmad-output/product-decisions.md` (MADR completo, mesma técnica verbatim de "
            "`decisao-tecnica/`/`anti-pattern/`; o par `**Cuidado:**`/`**A revisitar:**` do "
            "monólito original foi mapeado para `## Consequências`). 1 entrada carrega "
            "`revisitar-pendente: true` (a única seção original com `**A revisitar:**` — "
            "\"Modelo de receita é subscription-led\"). **Reconciliado pela Story E16.4 "
            "(2026-07-12):** contagem real atual é **50 entradas** (1 nova via `on_complete` "
            "de story posterior a E12.5) — ver "
            "`wiki/scripts/reconcile_index_counts.py`; o cabeçalho `## Files` "
            "abaixo já é sempre a contagem mecânica correta."
        ),
    },
    {
        "path": WIKI_ROOT / "ledger" / "regra",
        "heading": "# ledger/regra/ — Entradas `regra` do Ledger",
        "intro": (
            "18 entradas na contagem de E12.5 (cresceu de 1 exemplo migrado de `AGENTS.md` "
            "para 18 via `on_complete` acumulado das Ondas 3-4, principalmente Epics E9-E11 — "
            "paralelismo real, merge programático, isolamento de dados de QA). `estado: "
            "candidata` salvo indicação em contrário. Reindexado por esta pasta pela primeira "
            "vez desde que cresceu além do limiar de 5 (Story E12.5). **Reconciliado pela "
            "Story E16.4 (2026-07-12):** contagem real atual é **21 entradas** (3 novas via "
            "`on_complete` de stories posteriores a E12.5) — ver "
            "`wiki/scripts/reconcile_index_counts.py`; o cabeçalho `## Files` "
            "abaixo já é sempre a contagem mecânica correta."
        ),
    },
]


def main() -> int:
    for spec in FOLDERS:
        content = render_flat_folder_index(spec["path"], spec["heading"], spec["intro"])
        out = spec["path"] / "index.md"
        out.write_text(content, encoding="utf-8")
        n = content.count("\n- **[")
        print(f"wrote {out.relative_to(WIKI_ROOT.parent.parent)} ({n} docs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
