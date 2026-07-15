#!/usr/bin/env python3
"""gerente_product_routing.py — E9.6 Roteamento de produto: detector mecânico do toque
na Coverage Matrix.

Story E9.6 (ideias/sistema-artifacts/E9-6-roteamento-produto.md), PRD 05 FR-1/FR-1b,
ideias/epics.md Epic E9. Protocolo completo (o teste de 3 perguntas, as exclusões
duras, o viés de segurança "na dúvida, roteia", a tabela de 3 vias e o caso combinado)
vive em `project_controll/gerente/product-routing.md` — é JULGAMENTO, deliberadamente
NÃO mecanizado aqui (a story pede um helper só onde é genuinamente mecânico, "não force
um script que finja julgamento semântico").

O que ESTE script mecaniza é uma única sub-pergunta objetiva do protocolo (PRD 05 FR-1b,
"endurecido — F19"): **o ticket toca uma página/cenário listado na Coverage Matrix**
(`_bmad-output/C-UX-Scenarios/00-ux-scenarios.md`)? Essa é a REGRA DURA que, quando
verdadeira, força a via (i) sem exceção — "não é julgamento fino, é teste duro" (FR-1b).

  * `check-coverage-touch` — dado uma lista de termos "tocados" (páginas/áreas que o
    Gerente extraiu da descrição/`## Locais afetados`/`area` do ticket), varre os blocos
    `**Pages:**` de cada cenário da Coverage Matrix e devolve os cenários cujo nome de
    página bate (comparação normalizada: minúsculas, sem acento, substring em qualquer
    direção). Um match POSITIVO força mecanicamente `forced_route_i: true` — é o teste
    duro. Um resultado NEGATIVO (`forced_route_i: false`) NÃO prova "não toca a Coverage
    Matrix" — é só a ausência de um match textual; uma mudança de comportamento sem
    página nova (pergunta 1 do teste de 3 perguntas), ou uma página descrita com um nome
    que não bate textualmente com a Coverage Matrix, continuam exigindo o julgamento do
    Gerente via o protocolo completo. Este comando é um DETECTOR de sinal forte, nunca o
    decisor final.

Só leitura (nunca escreve nada). Stdlib only — mesma disciplina de todos os scripts
irmãos deste diretório (`gerente_escalation.py`, `gerente_oracle.py`, ...).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ancorado no repo root via Path(__file__) (como read_fp_suspects.py), NUNCA relativo ao CWD:
# senão, invocado de um worktree/subdiretório sem --coverage-matrix-path explícito, o default
# não resolvia e o gate DURO (FR-1b) caía em fail-open (forced_route_i:false) por acidente de path.
_PR_REPO_ROOT = Path(__file__).resolve().parents[3]  # scripts → gerente → project_controll → repo
DEFAULT_COVERAGE_MATRIX_PATH = str(_PR_REPO_ROOT / "_bmad-output" / "C-UX-Scenarios" / "00-ux-scenarios.md")

_SCENARIO_HEADER_RE = re.compile(
    r"^###\s*\[(?P<id>\d+):\s*(?P<title>[^\]]+)\]"
)
_PAGES_LINE_RE = re.compile(r"^\*\*Pages:\*\*\s*(?P<pages>.+?)\s*$")


def _normalize(text: str) -> str:
    """Lowercase + strip accents + collapse whitespace, for tolerant comparison."""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _strip_parenthetical(page_entry: str) -> str:
    """'Clientes (lista/novo/detalhe-editar)' -> 'Clientes'."""
    return re.sub(r"\s*\([^)]*\)\s*$", "", page_entry).strip()


def parse_coverage_matrix(path: Path) -> List[Dict[str, Any]]:
    """Parse the per-scenario `### [NN: Title](...)` blocks of the Coverage Matrix,
    returning [{id, title, pages: [raw page entries]}] — never touches the Summary
    table (its Pages column is just a count, not names)."""
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    scenarios: List[Dict[str, Any]] = []
    current: Optional[Dict[str, Any]] = None
    for line in lines:
        header_match = _SCENARIO_HEADER_RE.match(line.strip())
        if header_match:
            if current is not None:
                scenarios.append(current)
            current = {
                "id": header_match.group("id"),
                "title": header_match.group("title").strip(),
                "pages": [],
            }
            continue
        if current is not None:
            pages_match = _PAGES_LINE_RE.match(line.strip())
            if pages_match:
                raw_pages = pages_match.group("pages")
                current["pages"] = [p.strip() for p in raw_pages.split(",") if p.strip()]
    if current is not None:
        scenarios.append(current)
    return scenarios


_MIN_MATCH_LEN = 3  # abaixo disso (artigos/preposições: "a", "de", "e") um match de
# substring é ruído, não sinal — "a" bateria em quase toda página do documento inteiro.


def _term_matches_page(term_norm: str, page_norm: str) -> bool:
    if not term_norm or not page_norm:
        return False
    if min(len(term_norm), len(page_norm)) < _MIN_MATCH_LEN:
        return False
    return term_norm in page_norm or page_norm in term_norm


def check_coverage_touch(
    coverage_matrix_path: Path, touched_terms: List[str]
) -> Dict[str, Any]:
    if not coverage_matrix_path.exists():
        return {
            "error": f"coverage matrix not found: {coverage_matrix_path}",
            "forced_route_i": False,
            "matches": [],
            "unmatched_touched_terms": touched_terms,
        }
    scenarios = parse_coverage_matrix(coverage_matrix_path)
    matches: List[Dict[str, Any]] = []
    matched_terms: set = set()
    for scenario in scenarios:
        for raw_page in scenario["pages"]:
            base_page = _strip_parenthetical(raw_page)
            page_norm = _normalize(base_page)
            for term in touched_terms:
                term_norm = _normalize(term)
                if _term_matches_page(term_norm, page_norm):
                    matches.append(
                        {
                            "scenario_id": scenario["id"],
                            "scenario_title": scenario["title"],
                            "matched_page": raw_page,
                            "touched_term": term,
                        }
                    )
                    matched_terms.add(term)
    unmatched = [t for t in touched_terms if t not in matched_terms]
    return {
        "forced_route_i": len(matches) > 0,
        "matches": matches,
        "unmatched_touched_terms": unmatched,
        "scenarios_parsed": len(scenarios),
        "note": (
            "Match textual mecanico apenas (nome de pagina normalizado). Um match "
            "POSITIVO forca via (i) sem excecao (regra dura, PRD 05 FR-1b). Um "
            "resultado NEGATIVO nao prova ausencia de toque na Coverage Matrix - o "
            "Gerente ainda aplica o teste de 3 perguntas por julgamento "
            "(project_controll/gerente/product-routing.md) antes de concluir via (iii)."
        ),
    }


def cmd_check_coverage_touch(args: argparse.Namespace) -> int:
    touched_terms = [t.strip() for t in args.touched.split(",") if t.strip()]
    result = check_coverage_touch(Path(args.coverage_matrix_path), touched_terms)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="E9.6 — detector mecânico de toque na Coverage Matrix (PRD 05 FR-1b)."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    pct = sub.add_parser(
        "check-coverage-touch",
        help="dado termos tocados, sinaliza se batem com uma pagina de cenario da Coverage Matrix (forca via i)",
    )
    pct.add_argument(
        "--coverage-matrix-path",
        default=DEFAULT_COVERAGE_MATRIX_PATH,
        help=f"path do 00-ux-scenarios.md (default: {DEFAULT_COVERAGE_MATRIX_PATH})",
    )
    pct.add_argument(
        "--touched",
        required=True,
        help="lista separada por virgula de termos tocados (area/paginas do ticket)",
    )
    pct.set_defaults(func=cmd_check_coverage_touch)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
