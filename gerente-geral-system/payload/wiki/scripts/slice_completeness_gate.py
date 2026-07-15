#!/usr/bin/env python3
"""slice_completeness_gate.py — E3.5 gate mecânico de completude de fatiamento.

Story E3.5 (ideias/sistema-artifacts/E3-5-gate-completude-fatiamento.md),
PRD 01 §6.3 (endurecimento F25), ideias/epics.md Epic E3.

Todo fatiamento de monólito (Story E3.6: `notes.md`, `decisions.md`,
`anti-patterns.md`, `product-decisions.md` → árvore tipada da Wiki) DEVE
passar por este gate antes do cutover. "Reversível" (mantém o monólito
intacto) protege os bytes, mas não a PERDA SILENCIOSA — um sub-agente LLM
fatiando por `## H2` pode dropar, truncar, resumir ou mis-taggear texto, e
com cutover-por-arquivo o monólito para de ser lido -> a perda vira
invisível. Este script mecaniza as duas metades do gate:

  (a) COBERTURA H2 1:1 — todo `## H2` do monólito velho mapeia para
      EXATAMENTE UM documento na árvore nova. Falha lista H2 órfãos (sem
      nenhum mapeamento) e H2 duplicados (mapeados mais de uma vez).

  (b) CHECKSUM/DIFF TEXTUAL old<->new — todo texto de cada seção do
      monólito deve aparecer, na mesma ordem, no documento novo mapeado.
      "Reformatação declarada" (front-matter YAML adicionado, mudança de
      nível de heading, linhas que batem num allowlist de regex) é
      normalizada antes da comparação — não conta como perda. Qualquer
      outro texto do monólito ausente no novo é reportado como PERDIDO,
      com o trecho exato.

MECANISMO DE MAPEAMENTO ESCOLHIDO: manifesto explícito
(`slice-manifest.json`), não heurística de título. Um manifesto é mais
robusto: sobrevive a títulos reformatados/traduzidos entre o H2 velho e o
título do documento novo, é auditável por humano antes do gate rodar, e
não depende de fuzzy-matching que poderia mascarar exatamente o tipo de
perda silenciosa que este gate existe para pegar. O trade-off é que quem
fatia (bibliotecária/sub-agente) precisa escrever o manifesto — aceitável,
é um artefato pequeno e explícito.

READ-THROUGH: este script NUNCA apaga, move ou edita o monólito nem a
árvore nova — é só leitura + relatório. O cutover (parar de ler o
monólito em favor da árvore nova) só é liberado quando (1) este gate
retorna PASS (exit 0) E (2) o recall da área (SM-5, auditoria amostral —
ver `retrieval-guide.md` §SM-5 / `E3-3-mapa-feature-documento.md`) também
passa. Este script não roda SM-5 — SM-5 é julgamento humano/oráculo sobre
retrieval, não mecanizável por checksum (mesmo racional documentado em
`curation-guide.md` para "não mecanizar julgamento semântico").

Idempotente: rodar duas vezes sobre os mesmos arquivos produz o mesmo
resultado (só leitura, sem estado mutável entre execuções).
Reversível: nada é escrito; não há o que reverter.

Uso:
    python3 slice_completeness_gate.py --monolith old.md --tree-root novo/
    python3 slice_completeness_gate.py --monolith old.md --tree-root novo/ \\
        --manifest novo/slice-manifest.json --json

Exit code: 0 se o gate PASSA (cobertura 1:1 + zero texto perdido).
           1 se o gate FALHA (órfão, duplicata, arquivo ausente, ou perda
             textual detectada).
           2 erro de uso (arquivo/diretório não encontrado, manifesto
             inválido).

Só biblioteca padrão (stdlib) — nenhuma dependência externa. Mesma
convenção de `retrieve_slice.py` (E3.3) / `validate_wiki_docs.py` (E3.4):
argparse, `--json`, relatório humano por padrão.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path
from typing import Any

H2_PATTERN = re.compile(r"^##\s+(.+?)\s*$")
ANY_HEADING_PATTERN = re.compile(r"^#{1,6}\s+.*$")
FRONT_MATTER_DELIM = "---"

DEFAULT_REFORMATTING: dict[str, Any] = {
    # Front-matter YAML adicionado no topo do doc novo (E3.1 convention) é
    # reformatação declarada — nunca existiu no monólito, não pode ser
    # cobrado como "texto que deveria estar lá" nem contar como perda.
    "strip_frontmatter": True,
    # Marcadores de heading (#, ##, ###...) podem mudar de nível entre o
    # monólito (sempre ## no nível de seção) e o doc novo (costuma virar #
    # de topo de documento) — o TEXTO do título é conteúdo e continua
    # comparado; só o prefixo `#` é ignorado.
    "strip_heading_markers": True,
    # Diferenças de espaço em branco (indentação, linhas em branco extras,
    # quebras de linha) não são perda de conteúdo.
    "normalize_whitespace": True,
    # Linhas inteiras que batem em algum destes regexes são descartadas de
    # ambos os lados antes da comparação — para outra reformatação
    # declarada específica do fatiamento (ex.: uma linha "Ver também:"
    # injetada pelo índice recursivo). Vazio por padrão: nada extra é
    # perdoado além do front-matter e dos headings.
    "ignore_line_patterns": [],
}


def _clean_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1]
    return value


def strip_frontmatter(text: str) -> str:
    """Remove a block YAML front-matter (--- ... ---) do topo, se houver."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != FRONT_MATTER_DELIM:
        return text
    for i in range(1, len(lines)):
        if lines[i].strip() == FRONT_MATTER_DELIM:
            return "\n".join(lines[i + 1 :])
    return text  # front-matter aberto e nunca fechado — não mexe, deixa como está


def extract_h2_sections(monolith_text: str) -> list[tuple[str, str]]:
    """Extrai seções `## H2` do monólito, ignorando headings dentro de fences.

    Retorna lista ordenada de (título, corpo_da_secao). O corpo vai da
    linha seguinte ao H2 até o próximo H2 (ou EOF), headings de nível 3+
    incluídos no corpo (não geram nova seção).
    """
    lines = monolith_text.splitlines()
    sections: list[tuple[str, list[str]]] = []
    in_fence = False
    current_title: str | None = None
    current_body: list[str] = []

    for line in lines:
        if line.strip().startswith("```"):
            in_fence = not in_fence
            if current_title is not None:
                current_body.append(line)
            continue
        if not in_fence:
            m = H2_PATTERN.match(line)
            if m:
                if current_title is not None:
                    sections.append((current_title, current_body))
                current_title = m.group(1).strip()
                current_body = []
                continue
        if current_title is not None:
            current_body.append(line)

    if current_title is not None:
        sections.append((current_title, current_body))

    return [(title, "\n".join(body)) for title, body in sections]


def normalize(text: str, cfg: dict[str, Any]) -> str:
    """Normaliza texto para comparação, aplicando a reformatação declarada."""
    if cfg.get("strip_frontmatter", True):
        text = strip_frontmatter(text)

    ignore_patterns = [re.compile(p) for p in cfg.get("ignore_line_patterns", [])]

    out_lines: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue  # marcador de fence em si nunca é "conteúdo"
        if any(p.search(line) for p in ignore_patterns):
            continue
        if not in_fence and cfg.get("strip_heading_markers", True) and ANY_HEADING_PATTERN.match(line):
            line = re.sub(r"^#{1,6}\s+", "", line)
        out_lines.append(line)

    text = "\n".join(out_lines)

    if cfg.get("normalize_whitespace", True):
        text = re.sub(r"\s+", " ", text).strip()

    return text


def load_manifest(manifest_path: Path) -> dict[str, Any]:
    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    raw.setdefault("mappings", [])
    reformatting = dict(DEFAULT_REFORMATTING)
    reformatting.update(raw.get("reformatting", {}))
    raw["reformatting"] = reformatting
    return raw


def find_source_duplicates(h2_titles: list[str]) -> list[str]:
    """Detecta títulos de `## H2` repetidos DENTRO do próprio monólito.

    `run_gate()` faz lookup de seção por título (`dict(sections_list)`),
    então dois H2 com o mesmo título no arquivo velho colidiriam
    silenciosamente — só a última ocorrência sobreviveria ao dict, e a
    checagem (b) compararia a seção errada sem avisar. Isso é reportado
    como falha antes de qualquer comparação textual ser feita, em vez de
    deixar a colisão silenciosa comparar a seção errada sem avisar.
    """
    seen: dict[str, int] = {}
    for t in h2_titles:
        seen[t] = seen.get(t, 0) + 1
    return sorted(t for t, n in seen.items() if n > 1)


def check_coverage(
    h2_titles: list[str], mappings: list[dict[str, Any]]
) -> dict[str, Any]:
    """Checagem (a): cobertura H2 1:1 monólito -> árvore nova."""
    h2_set = set(h2_titles)
    mapped_titles = [m["h2"] for m in mappings]

    count_by_title: dict[str, int] = {}
    for t in mapped_titles:
        count_by_title[t] = count_by_title.get(t, 0) + 1

    orphans = [t for t in h2_titles if count_by_title.get(t, 0) == 0]
    duplicates = sorted(t for t, n in count_by_title.items() if n > 1 and t in h2_set)
    dangling = sorted(t for t in count_by_title if t not in h2_set)
    source_duplicates = find_source_duplicates(h2_titles)

    return {
        "orphans": orphans,
        "duplicates": duplicates,
        "dangling_mappings": dangling,
        "source_duplicates": source_duplicates,
    }


def check_textual(
    sections: dict[str, str],
    mappings: list[dict[str, Any]],
    tree_root: Path,
    reformatting: dict[str, Any],
) -> dict[str, Any]:
    """Checagem (b): checksum/diff textual old<->new por mapeamento."""
    results: list[dict[str, Any]] = []
    for m in mappings:
        title = m["h2"]
        if title not in sections:
            continue  # já reportado como dangling_mapping pela checagem (a)

        rel_file = m["file"]
        target_path = tree_root / rel_file
        if not target_path.exists():
            results.append(
                {
                    "h2": title,
                    "file": rel_file,
                    "status": "arquivo_ausente",
                    "lost_snippets": [],
                }
            )
            continue

        old_text = normalize(sections[title], reformatting)
        new_text = normalize(target_path.read_text(encoding="utf-8"), reformatting)

        old_tokens = old_text.split(" ") if old_text else []
        new_tokens = new_text.split(" ") if new_text else []

        matcher = difflib.SequenceMatcher(a=old_tokens, b=new_tokens, autojunk=False)
        lost_snippets: list[str] = []
        for tag, i1, i2, _j1, _j2 in matcher.get_opcodes():
            if tag in ("delete", "replace"):
                snippet = " ".join(old_tokens[i1:i2])
                if snippet.strip():
                    if len(snippet) > 200:
                        snippet = snippet[:200] + " …[truncado no relatório]"
                    lost_snippets.append(snippet)

        results.append(
            {
                "h2": title,
                "file": rel_file,
                "status": "ok" if not lost_snippets else "texto_perdido",
                "lost_snippets": lost_snippets,
            }
        )
    return {"per_mapping": results}


def run_gate(monolith_path: Path, tree_root: Path, manifest_path: Path) -> dict[str, Any]:
    monolith_text = monolith_path.read_text(encoding="utf-8")
    sections_list = extract_h2_sections(monolith_text)
    sections = dict(sections_list)
    h2_titles = [t for t, _ in sections_list]

    manifest = load_manifest(manifest_path)
    mappings = manifest["mappings"]
    reformatting = manifest["reformatting"]

    coverage = check_coverage(h2_titles, mappings)
    textual = check_textual(sections, mappings, tree_root, reformatting)

    textual_failures = [
        r for r in textual["per_mapping"] if r["status"] != "ok"
    ]

    passed = (
        not coverage["orphans"]
        and not coverage["duplicates"]
        and not coverage["dangling_mappings"]
        and not coverage["source_duplicates"]
        and not textual_failures
    )

    return {
        "monolith": str(monolith_path),
        "tree_root": str(tree_root),
        "manifest": str(manifest_path),
        "h2_count": len(h2_titles),
        "mapping_count": len(mappings),
        "coverage": coverage,
        "textual": textual,
        "passed": passed,
        "read_through_note": (
            "Este script não apaga nem move o monólito. Cutover só é "
            "liberado após este gate PASS + recall SM-5 da área PASS."
        ),
    }


def _print_human(result: dict[str, Any]) -> None:
    print(f"Monólito: {result['monolith']}")
    print(f"Árvore nova: {result['tree_root']}")
    print(f"Manifesto: {result['manifest']}")
    print(f"H2 no monólito: {result['h2_count']}  |  Mapeamentos no manifesto: {result['mapping_count']}")
    print()

    cov = result["coverage"]
    print("=== Checagem (a) — cobertura H2 1:1 ===")
    if cov["source_duplicates"]:
        print(
            f"✗ H2 DUPLICADOS NO PRÓPRIO MONÓLITO ({len(cov['source_duplicates'])}) — "
            "título repetido no arquivo velho, comparação textual não é confiável até "
            "isso ser corrigido (renomeie um dos dois H2 antes de refatiar):"
        )
        for t in cov["source_duplicates"]:
            print(f"    - {t!r}")
    else:
        print("✓ nenhum H2 duplicado no próprio monólito")
    if cov["orphans"]:
        print(f"✗ H2 ÓRFÃOS — sem nenhum mapeamento ({len(cov['orphans'])}):")
        for t in cov["orphans"]:
            print(f"    - {t!r}")
    else:
        print("✓ nenhum H2 órfão")
    if cov["duplicates"]:
        print(f"✗ H2 DUPLICADOS — mapeados mais de uma vez ({len(cov['duplicates'])}):")
        for t in cov["duplicates"]:
            print(f"    - {t!r}")
    else:
        print("✓ nenhum H2 duplicado")
    if cov["dangling_mappings"]:
        print(f"✗ mapeamentos ÓRFÃOS — referenciam H2 inexistente no monólito ({len(cov['dangling_mappings'])}):")
        for t in cov["dangling_mappings"]:
            print(f"    - {t!r}")
    else:
        print("✓ nenhum mapeamento órfão (todo mapeamento referencia um H2 real)")
    print()

    print("=== Checagem (b) — checksum/diff textual old↔new ===")
    per_mapping = result["textual"]["per_mapping"]
    if not per_mapping:
        print("  (nenhum mapeamento válido para comparar)")
    for r in per_mapping:
        if r["status"] == "ok":
            print(f"  ✓ {r['h2']!r} -> {r['file']} — texto integralmente preservado")
        elif r["status"] == "arquivo_ausente":
            print(f"  ✗ {r['h2']!r} -> {r['file']} — ARQUIVO AUSENTE na árvore nova")
        else:
            print(f"  ✗ {r['h2']!r} -> {r['file']} — TEXTO PERDIDO/TRUNCADO:")
            for snippet in r["lost_snippets"]:
                print(f"      · \"{snippet}\"")
    print()

    if result["passed"]:
        print("✓✓ GATE PASS — cobertura 1:1 e zero texto perdido.")
        print(f"  {result['read_through_note']}")
    else:
        print("✗✗ GATE FAIL — cutover NÃO liberado. Ver detalhes acima.")
        print(f"  {result['read_through_note']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--monolith", required=True, type=Path, help="Path do monólito velho (o .md sendo fatiado)")
    parser.add_argument("--tree-root", required=True, type=Path, help="Diretório raiz da árvore nova (fatiada)")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Path do slice-manifest.json (default: <tree-root>/slice-manifest.json)",
    )
    parser.add_argument("--json", action="store_true", help="Emite JSON em vez de texto legível")
    args = parser.parse_args(argv)

    if not args.monolith.exists():
        print(f"erro: monólito não encontrado: {args.monolith}", file=sys.stderr)
        return 2
    if not args.tree_root.exists() or not args.tree_root.is_dir():
        print(f"erro: tree-root não é um diretório existente: {args.tree_root}", file=sys.stderr)
        return 2

    manifest_path = args.manifest or (args.tree_root / "slice-manifest.json")
    if not manifest_path.exists():
        print(f"erro: manifesto não encontrado: {manifest_path}", file=sys.stderr)
        return 2

    try:
        result = run_gate(args.monolith, args.tree_root, manifest_path)
    except json.JSONDecodeError as exc:
        print(f"erro: manifesto inválido (JSON malformado): {exc}", file=sys.stderr)
        return 2
    except KeyError as exc:
        print(f"erro: manifesto inválido (campo ausente em um mapeamento: {exc}): cada item de "
              "'mappings' precisa de 'h2' e 'file'", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        _print_human(result)

    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
