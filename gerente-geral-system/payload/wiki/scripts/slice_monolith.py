#!/usr/bin/env python3
"""slice_monolith.py — E3.6 máquina de migração: fatiamento PROPOSTO (staging), não destrutivo.

Story E3.6 (ideias/sistema-artifacts/E3-6-migracao-monolitos.md),
PRD 01 §6.3 (plano de migração ordenado por risco), ideias/epics.md Epic E3.

Dado um monólito (`notes.md`, `decisions.md`, `anti-patterns.md`,
`product-decisions.md`), este script PROPÕE a fatiação por `## H2` em
documentos-tipo da Wiki: gera os arquivos novos numa pasta de STAGING de
migração (nunca dentro da árvore "oficial" da Wiki até um cutover manual
e supervisionado) + o `slice-manifest.json` que
`wiki/scripts/slice_completeness_gate.py` (Story E3.5)
consome para provar cobertura H2 1:1 + zero perda textual antes de
qualquer cutover.

NUNCA escreve no monólito de origem — abre em modo leitura, ponto final.
Reversível trivialmente: apagar a pasta de staging não afeta o monólito
em nada (o monólito nunca foi tocado para começo de conversa).

Reusa `extract_h2_sections()` de `slice_completeness_gate.py` (E3.5) —
as duas metades da máquina (propor a fatiação aqui, verificar lá) usam o
mesmo parser H2-aware-de-fences, para nunca divergirem silenciosamente
sobre "o que é uma seção".

Dois usos:

  1. **Fatiamento completo** (produção real da migração — ainda NÃO
     executado por esta story, ver PRD 01 §6.3 "preferencialmente
     supervisionada" e o Change Log de E3.6): omitir `--select-h2`, todo
     `## H2` do monólito vira um documento novo em `--out-dir`.

  2. **Piloto parcial** (o que a Story E3.6 de fato executa contra
     `notes.md`): `--select-h2 "Título exato"` (repetível) restringe a
     fatiação a um subconjunto de seções, para provar a máquina + o gate
     numa amostra pequena e revisável, sem tocar as ~200+ seções
     restantes de `notes.md` (esse fatiamento completo fica deferido).
     Quando `--select-h2` é usado, o script também escreve
     `pilot-subset-monolith.md` em `--out-dir` — uma cópia FIEL (texto
     idêntico, não uma referência) de só as seções selecionadas, na
     forma `## H2` original, na ordem em que aparecem no monólito. Serve
     como o `--monolith` de entrada para `slice_completeness_gate.py`
     provar PASS num subconjunto delimitado — rodar o gate contra o
     monólito completo relataria as ~200+ seções não selecionadas como
     órfãs, um falso positivo esperado (não fatiadas ainda, de propósito)
     e não um bug do gate.

Cada documento novo recebe front-matter mínimo (`tipo`, `areas: []` —
gap de curadoria deliberado, ver Dev Notes de E3.6/`retrieval-guide.md`
F6: atribuir área exige julgamento humano/bibliotecária, não inferido
aqui —, `created`, `source_monolith`, `source_h2`, e o marcador informal
`migration_status: staging-piloto`, que NÃO é campo oficial do schema de
`document-types.md` — é só um marcador local desta pasta de staging para
quem for revisar não confundir com conteúdo já cortado sobre a Wiki
oficial).

Uso:
    # Piloto: 3 seções de notes.md -> nota-operacional, staging dir
    python3 slice_monolith.py \\
        --monolith _bmad-output/notes.md \\
        --doc-type nota-operacional \\
        --out-dir wiki/_migration-staging/notes \\
        --select-h2 "Título A" --select-h2 "Título B" --select-h2 "Título C"

    # Fatiamento completo (fora do escopo desta story — deferido ao dono)
    python3 slice_monolith.py --monolith _bmad-output/notes.md \\
        --doc-type nota-operacional \\
        --out-dir wiki/_migration-staging/notes

Exit code: 0 sucesso; 2 erro de uso (monólito ausente, H2 pedido não
existe no monólito, out-dir já tem uma execução anterior sem --force).

Só biblioteca padrão (stdlib) — nenhuma dependência externa. Mesma
convenção de `retrieve_slice.py`/`validate_wiki_docs.py`/
`slice_completeness_gate.py`: argparse, stdlib puro, relatório humano.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

# Reusa o parser H2-aware-de-fences de E3.5 em vez de reimplementar —
# garante que "o que conta como seção" nunca diverge entre propor (este
# script) e verificar (slice_completeness_gate.py). Reusa também
# find_source_duplicates(): o mesmo dict-lookup-por-título que a Story
# E3.5 identificou como um furo de colisão silenciosa (dois `## H2` com
# o mesmo título no monólito -> só o último sobrevive ao dict) existe
# aqui também (`sections_by_title = dict(all_sections)` abaixo) — em vez
# de reintroduzir o mesmo furo e esperar o gate pegar depois, este
# script recusa fatiar um título duplicado na origem antes de gerar
# qualquer arquivo (ver `run()`).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from slice_completeness_gate import extract_h2_sections, find_source_duplicates  # noqa: E402

# Catálogo canônico (document-types.md, Story E3.1) — só para um aviso
# amigável se `--doc-type` não bater com nenhum slug conhecido; este
# script não é o validador oficial (isso é validate_wiki_docs.py, E3.4).
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


def slugify(title: str) -> str:
    """Converte um título de H2 num nome de arquivo estável e legível."""
    normalized = unicodedata.normalize("NFKD", title)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_only.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    if not slug:
        slug = "secao"
    return slug[:80].rstrip("-")


def dedupe_slugs(titles: list[str]) -> dict[str, str]:
    """Mapeia título -> slug de arquivo, desambiguando colisões com sufixo -2, -3…"""
    used: dict[str, int] = {}
    result: dict[str, str] = {}
    for title in titles:
        base = slugify(title)
        used[base] = used.get(base, 0) + 1
        if used[base] == 1:
            result[title] = base
        else:
            result[title] = f"{base}-{used[base]}"
    return result


def yaml_escape_scalar(value: str) -> str:
    """Escapa um valor string para uso seguro em front-matter YAML simples."""
    if any(c in value for c in [":", "#", '"', "'", "\n"]) or value.strip() != value:
        escaped = value.replace('"', '\\"')
        return f'"{escaped}"'
    return value


def build_new_doc(
    title: str,
    body: str,
    doc_type: str,
    source_monolith: str,
    created: str,
    areas: list[str] | None,
    migration_status: str,
) -> str:
    # E12.1 (ideias/sistema-artifacts/E12-1-fatiar-notes.md): quando o chamador
    # fornece `--areas-map` com um julgamento curatorial real para este título,
    # a área vai preenchida (nunca []) — sem isso, preserva o comportamento
    # original de E3.6 (areas: [] como gap de curadoria deliberado).
    #
    # ACHADO DA AUTO-REVISÃO DE E12.1 (patch aplicado, ver Dev Notes da story):
    # o parser minimalista de `retrieve_slice.py` (E3.3) NÃO ignora comentário
    # `# ...` no final de uma linha `chave: valor` — ele só reconhece uma lista
    # em fluxo se `value.strip()` TERMINAR em `]`. Um comentário inline
    # ("areas: [x]  # nota") quebra essa checagem e faz `areas` virar uma
    # STRING crua (não uma lista), corrompendo silenciosamente todo doc para
    # retrieval — inclusive o `areas: []  # gap...` original de E3.6, nunca
    # exercitado contra retrieve_slice.py em anger porque o piloto ficou em
    # `_migration-staging/` (fora do fluxo real). Por isso todo comentário
    # explicativo do front-matter vai em linha PRÓPRIA (sem `:` no texto, para
    # não virar uma chave espúria), nunca na mesma linha de uma chave real.
    if areas:
        areas_yaml = "[" + ", ".join(yaml_escape_scalar(a) for a in areas) + "]"
        areas_line = (
            "# curadoria real (Story E12.1/E3.3) — nunca inferência por palavra-chave\n"
            f"areas: {areas_yaml}\n"
        )
    else:
        areas_line = (
            "# gap de curadoria deliberado — atribuir área exige julgamento humano/bibliotecária (retrieval-guide.md F6), não inferido por este script\n"
            "areas: []\n"
        )
    front_matter = (
        "---\n"
        f"tipo: {doc_type}\n"
        f"{areas_line}"
        f"created: {created}\n"
        f"source_monolith: {yaml_escape_scalar(source_monolith)}\n"
        f"source_h2: {yaml_escape_scalar(title)}\n"
        "# marcador informal (Story E3.6/E12.1) — NÃO é campo oficial de document-types.md; some no cutover real\n"
        f"migration_status: {migration_status}\n"
        "---\n"
    )
    heading = f"# {title}\n"
    body_stripped = body.strip("\n")
    return f"{front_matter}\n{heading}\n{body_stripped}\n"


def run(
    monolith_path: Path,
    doc_type: str,
    out_dir: Path,
    select_h2: list[str] | None,
    force: bool,
    areas_map: dict[str, list[str]] | None = None,
    migration_status: str = "staging-piloto",
) -> dict[str, Any]:
    monolith_text = monolith_path.read_text(encoding="utf-8")
    all_sections = extract_h2_sections(monolith_text)
    all_titles = [t for t, _ in all_sections]
    sections_by_title = dict(all_sections)

    source_duplicates = set(find_source_duplicates(all_titles))
    if select_h2:
        dup_hit = sorted(set(select_h2) & source_duplicates)
        if dup_hit:
            raise ValueError(
                "título(s) pedido(s) são duplicados NO PRÓPRIO MONÓLITO "
                f"(mais de um `## H2` com o mesmo texto): {dup_hit!r} — fatiar um título "
                "ambíguo escolheria silenciosamente uma das ocorrências (dict por título). "
                "Renomeie um dos dois H2 no monólito antes de selecioná-lo para fatiamento "
                "(mesma proteção de find_source_duplicates() usada por slice_completeness_gate.py)."
            )
    elif source_duplicates:
        raise ValueError(
            "fatiamento completo pedido (sem --select-h2), mas o monólito tem título(s) de "
            f"`## H2` duplicado(s): {sorted(source_duplicates)!r} — resolva as duplicatas na "
            "origem antes do fatiamento completo (o gate slice_completeness_gate.py também "
            "falharia nesta condição)."
        )

    if select_h2:
        missing = [t for t in select_h2 if t not in sections_by_title]
        if missing:
            raise ValueError(
                "H2 pedido(s) não encontrado(s) no monólito (confira o título exato, "
                f"caractere a caractere): {missing!r}"
            )
        # Preserva a ORDEM de aparição no monólito, não a ordem do CLI.
        selected_titles = [t for t in all_titles if t in set(select_h2)]
    else:
        selected_titles = all_titles

    manifest_path = out_dir / "slice-manifest.json"
    if manifest_path.exists() and not force:
        raise ValueError(
            f"{manifest_path} já existe (execução anterior de slice_monolith.py) — "
            "use --force para sobrescrever a pasta de staging."
        )

    out_dir.mkdir(parents=True, exist_ok=True)

    slug_by_title = dedupe_slugs(selected_titles)
    created_today = date.today().isoformat()
    mappings: list[dict[str, str]] = []
    areas_gaps: list[str] = []

    for title in selected_titles:
        body = sections_by_title[title]
        filename = f"{slug_by_title[title]}.md"
        doc_areas = (areas_map or {}).get(title)
        if not doc_areas:
            areas_gaps.append(title)
        content = build_new_doc(
            title=title,
            body=body,
            doc_type=doc_type,
            source_monolith=str(monolith_path),
            created=created_today,
            areas=doc_areas,
            migration_status=migration_status,
        )
        (out_dir / filename).write_text(content, encoding="utf-8")
        mappings.append({"h2": title, "file": filename})

    manifest = {
        "generated_by": "slice_monolith.py (Story E3.6/E12.1)",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_monolith": str(monolith_path),
        "doc_type": doc_type,
        "partial_selection": bool(select_h2),
        "mappings": mappings,
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    pilot_subset_path: Path | None = None
    if select_h2:
        pilot_subset_path = out_dir / "pilot-subset-monolith.md"
        chunks = []
        for title in selected_titles:
            body = sections_by_title[title].strip("\n")
            chunks.append(f"## {title}\n\n{body}\n")
        pilot_subset_path.write_text("\n".join(chunks) + "\n", encoding="utf-8")

    return {
        "monolith": str(monolith_path),
        "monolith_h2_total": len(all_titles),
        "selected_count": len(selected_titles),
        "out_dir": str(out_dir),
        "manifest": str(manifest_path),
        "pilot_subset_monolith": str(pilot_subset_path) if pilot_subset_path else None,
        "files": [str(out_dir / m["file"]) for m in mappings],
        "partial_selection": bool(select_h2),
        "areas_gaps": areas_gaps,
    }


def _print_human(result: dict[str, Any]) -> None:
    print(f"Monólito (só leitura, nunca modificado): {result['monolith']}")
    print(f"Total de ## H2 no monólito: {result['monolith_h2_total']}")
    print(f"Seções selecionadas para esta execução: {result['selected_count']}"
          + (" (SUBCONJUNTO — piloto)" if result["partial_selection"] else " (TODAS — fatiamento completo)"))
    print(f"Pasta de staging: {result['out_dir']}")
    print(f"Manifesto: {result['manifest']}")
    if result["pilot_subset_monolith"]:
        print(f"Sub-monólito do piloto (para rodar o gate num subconjunto): {result['pilot_subset_monolith']}")
    print()
    print("Documentos novos gerados:")
    for f in result["files"]:
        print(f"  - {f}")
    print()
    if result["areas_gaps"]:
        print(f"⚠ GAPS DE CURADORIA — {len(result['areas_gaps'])} seção(ões) sem área real atribuída (areas: [], --areas-map não cobriu):")
        for t in result["areas_gaps"]:
            print(f"  - {t!r}")
    else:
        print("✓ nenhum gap de curadoria de área (todo documento recebeu areas: real)")
    print()
    print("PRÓXIMO PASSO (não executado por este script): rodar")
    print("  slice_completeness_gate.py --monolith <monólito-ou-subconjunto> "
          f"--tree-root {result['out_dir']}")
    print("e só liberar cutover se o gate PASS + recall SM-5 da área também passarem.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--monolith", required=True, type=Path, help="Path do monólito velho (só leitura)")
    parser.add_argument("--doc-type", required=True, help="Documento-tipo alvo (ex.: nota-operacional) — ver document-types.md")
    parser.add_argument("--out-dir", required=True, type=Path, help="Pasta de STAGING de migração onde os docs novos + manifesto são escritos")
    parser.add_argument(
        "--select-h2",
        action="append",
        default=None,
        metavar="TÍTULO",
        help="Título exato de um ## H2 a incluir (repetível). Omitir = fatiamento completo (todas as seções).",
    )
    parser.add_argument("--force", action="store_true", help="Sobrescreve uma execução anterior na mesma --out-dir")
    parser.add_argument("--json", action="store_true", help="Emite JSON em vez de texto legível")
    parser.add_argument(
        "--areas-map",
        type=Path,
        default=None,
        help=(
            "Path de um JSON {\"título H2 exato\": [\"area1\", \"area2\"], ...} com o "
            "julgamento curatorial de área por seção (Story E12.1) — NUNCA gerado por "
            "inferência automática deste script. Título ausente do mapa (ou lista vazia) "
            "fica com areas: [] (gap de curadoria, reportado em 'areas_gaps')."
        ),
    )
    parser.add_argument(
        "--migration-status",
        default="staging-piloto",
        help=(
            "Valor do marcador informal 'migration_status:' no front-matter de cada doc novo "
            "(default: 'staging-piloto', o valor histórico de E3.6). Story E12.1 usa um valor "
            "próprio para o modo completo na árvore oficial, ainda não indexado/cutover."
        ),
    )
    args = parser.parse_args(argv)

    if not args.monolith.exists():
        print(f"erro: monólito não encontrado: {args.monolith}", file=sys.stderr)
        return 2

    if args.doc_type not in CANONICAL_TIPOS:
        print(
            f"aviso: --doc-type {args.doc_type!r} não é um dos 13 slugs canônicos de "
            "document-types.md — prosseguindo mesmo assim (este script não é o validador oficial; "
            "rode validate_wiki_docs.py depois para checagem completa).",
            file=sys.stderr,
        )

    areas_map: dict[str, list[str]] | None = None
    if args.areas_map is not None:
        if not args.areas_map.exists():
            print(f"erro: --areas-map não encontrado: {args.areas_map}", file=sys.stderr)
            return 2
        try:
            areas_map = json.loads(args.areas_map.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"erro: --areas-map inválido (JSON malformado): {exc}", file=sys.stderr)
            return 2

    try:
        result = run(
            monolith_path=args.monolith,
            doc_type=args.doc_type,
            out_dir=args.out_dir,
            select_h2=args.select_h2,
            force=args.force,
            areas_map=areas_map,
            migration_status=args.migration_status,
        )
    except ValueError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        _print_human(result)

    return 0


if __name__ == "__main__":
    sys.exit(main())
