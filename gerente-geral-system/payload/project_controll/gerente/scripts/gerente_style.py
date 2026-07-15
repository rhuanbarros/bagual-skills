#!/usr/bin/env python3
"""gerente_style.py — E9.2 Aprendizado de estilo de decisão.

Story E9.2 (ideias/sistema-artifacts/E9-2-aprendizado-estilo.md), PRD 00 FR-6 (§4.3,
Fase 2), ideias/epics.md Epic E9. Antes de decidir, o Gerente CONSULTA o histórico de
decisões do oráculo — ratificadas E corrigidas — no Ledger (mais o corpus de contexto
`product-decisions.md`/`decisions.md`), ajustando o raio de confiança da decisão que
está prestes a tomar. O "estilo de decisão" é entradas de Ledger + `product-decisions.md`
consultadas em spec-time — NUNCA um modelo treinado (PRD 00 §9, índice de assunções,
"§4.3 / FR-6"). Este script é o meio mecânico dessa consulta; o gate de confiança real
que ele alimenta (`--confidence high` só honrada quando nenhuma decisão `corrected`
similar contradiz) vive em `gerente_oracle.py::_resolve_confidence` (import direto
deste script, mesma técnica de reuso já usada nesta árvore de scripts).

"Similar" é definido OPERACIONALMENTE (nunca por "sensação"/NLP semântico): mesmo
`tipo` (categoria) + N tags de `areas` em comum (interseção exata, case-insensitive/
trimmed) entre o candidato e uma Entrada de Ledger existente — a mesma definição usada
pelo gate history-aware de `gerente_oracle.py` (Story E9.2). N (o limiar) é configurável
POR CATEGORIA via `oracle.config.json` (sibling deste script) — reuso do padrão de
`quota.config.json`/E8.3: arquivo commitado com defaults conservadores, editável pelo
dono. Uma categoria mais sensível (ex. `decisao-de-produto`) pode exigir mais overlap
de `areas` do que uma técnica para sustentar suporte — nunca o contrário para
CONTRADIÇÃO (é sempre mais fácil provar que uma decisão parecida foi corrigida do que
provar que uma parecida foi ratificada — conservador por desenho, downgrade nunca
upgrade em evidência fraca).

Comandos:
  consult-precedent   dado tipo+areas (e opcionalmente um resumo livre), retorna as
                       decisões RATIFICADAS que sustentam confiança alta e as
                       CORRIGIDAS que a contradizem, mais uma confiança sugerida —
                       NUNCA grava nada (é consulta pura, sem efeito colateral); usar
                       ANTES de `gerente_oracle.py record-decision --confidence high`
  sm2                 calcula SM-2 (% de decisões do oráculo ratificadas, não
                       corrigidas) a partir do rastro REAL do Ledger — nunca hardcoded

`product-decisions.md`/`decisions.md` são monólitos em prosa (sem `tipo`/`areas`
estruturados) — por isso participam desta consulta só como sinal INFORMACIONAL
(ocorrências de keyword por seção `## [TAG] Título`), nunca como parte do cálculo
MECÂNICO de confiança sugerida (que fica inteiramente restrito ao corpo estruturado do
Ledger, onde "similar" é verificável, não estimado). Ver Dev Notes da story para o
racional completo desta divisão.

Só biblioteca padrão (stdlib) — nenhuma dependência externa, mesma convenção dos
scripts irmãos em `project_controll/gerente/scripts/`.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = SCRIPT_DIR.resolve().parents[2]


def _load_module(path: Path, name: str):
    if not path.exists():
        print(f"erro: módulo não encontrado em {path} — não é possível reusar suas primitivas", file=sys.stderr)
        sys.exit(2)
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_ORACLE = None


def oracle():
    """`gerente_oracle.py` (sibling, mesmo diretório) — reuso por import direto (nunca
    cópia colada) das primitivas de E9.1/E9.2: tabelas de tipo, `shared_areas`,
    `load_oracle_config`/`get_category_threshold`, `find_ratified_support`/
    `find_corrected_contradictions`, `validate_precedent_fm`."""
    global _ORACLE
    if _ORACLE is None:
        _ORACLE = _load_module(SCRIPT_DIR / "gerente_oracle.py", "gerente_oracle")
    return _ORACLE


def today_iso() -> str:
    from datetime import date
    return date.today().isoformat()


# ---------------------------------------------------------------------------
# consult-precedent
# ---------------------------------------------------------------------------
def _parse_areas_csv(raw: str) -> list[str]:
    return [a.strip() for a in raw.split(",") if a.strip()]


def _scan_prose_corpus(path: Path, tokens: list[str]) -> list[dict[str, Any]]:
    """Varredura keyword INFORMACIONAL (nunca gating) de um monólito
    `decisions.md`/`product-decisions.md`: para cada seção `## [TAG] Título — data`,
    verifica se algum token (área/palavra do resumo) aparece no TÍTULO da seção
    (case-insensitive, substring) — um sinal barato de "pode haver contexto relevante
    aqui", não uma prova. Nunca usado para calcular `suggested_confidence`."""
    if not path.exists() or not tokens:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    hits: list[dict[str, Any]] = []
    normalized_tokens = [t.strip().lower() for t in tokens if t.strip()]
    for match in re.finditer(r"^## (.+)$", text, flags=re.MULTILINE):
        title = match.group(1).strip()
        title_lower = title.lower()
        matched = [t for t in normalized_tokens if t and t in title_lower]
        if matched:
            hits.append({"title": title, "matched_tokens": matched})
    return hits


def cmd_consult_precedent(args: argparse.Namespace) -> int:
    oc = oracle()
    ledger_root = Path(args.ledger_root)
    tipo_slug = args.tipo
    tipo_display = oc.TIPO_SLUG_TO_DISPLAY[tipo_slug]
    areas = _parse_areas_csv(args.areas)

    config = oc.load_oracle_config(Path(args.oracle_config) if args.oracle_config else None)
    threshold = oc.get_category_threshold(config, tipo_slug)

    contradicting = oc.find_corrected_contradictions(
        ledger_root, tipo_display, areas, threshold["min_shared_areas_contradict"],
    )
    supporting = oc.find_ratified_support(
        ledger_root, tipo_display, areas, threshold["min_shared_areas_support"],
    )

    # Conservador: contradição SEMPRE vence, mesmo havendo suporte — nunca "upgrade" em
    # evidência mista/fraca (constraint explícita da story: default toward LOW).
    if contradicting:
        suggested_confidence = "low"
        reason = (
            f"{len(contradicting)} decisão(ões) `ratification: corrected` do mesmo tipo "
            f"('{tipo_display}') com `areas` similares (overlap >= "
            f"{threshold['min_shared_areas_contradict']}) — down-weight conservador, "
            "mesmo que haja precedente ratificado também similar"
        )
    elif supporting:
        suggested_confidence = "high"
        reason = (
            f"{len(supporting)} decisão(ões) `ratification: ratified`/ausente, "
            f"`estado: ativa`, do mesmo tipo, com overlap de `areas` >= "
            f"{threshold['min_shared_areas_support']} (limiar da categoria "
            f"'{tipo_slug}') — sustenta confiança alta; cite um dos `path` abaixo como "
            "--precedent em record-decision"
        )
    else:
        suggested_confidence = "low"
        reason = (
            "nenhum precedente ratificado com overlap suficiente de `areas` foi "
            f"encontrado para o tipo '{tipo_display}' (limiar da categoria: "
            f"{threshold['min_shared_areas_support']}) — ausência/fraqueza de "
            "evidência NUNCA sustenta alta confiança (default conservador)"
        )

    keyword_tokens = areas + (_parse_areas_csv(args.keywords) if args.keywords else [])
    product_decisions_path = Path(args.product_decisions_path)
    decisions_path = Path(args.decisions_path)

    result = {
        "tipo": tipo_display,
        "tipo_slug": tipo_slug,
        "areas": areas,
        "category_threshold": threshold,
        "matches_corrected": contradicting,
        "matches_ratified": supporting,
        "suggested_confidence": suggested_confidence,
        "reason": reason,
        "product_decisions_hits": _scan_prose_corpus(product_decisions_path, keyword_tokens),
        "decisions_hits": _scan_prose_corpus(decisions_path, keyword_tokens),
        "note": (
            "product_decisions_hits/decisions_hits são INFORMACIONAIS (varredura de "
            "keyword no título de seção) — nunca usados para calcular "
            "suggested_confidence, que fica restrito ao Ledger estruturado."
        ),
    }
    print(json.dumps(result, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------------------
# sm2 — % de decisões do oráculo ratificadas (SM-2, PRD 00 §7)
# ---------------------------------------------------------------------------
def cmd_sm2(args: argparse.Namespace) -> int:
    oc = oracle()
    ledger_root = Path(args.ledger_root)
    tipo_display = oc.TIPO_SLUG_TO_DISPLAY[args.tipo] if args.tipo else None

    counts = {"ratified": 0, "corrected": 0, "pending": 0}
    entries: list[dict[str, Any]] = []
    for path, fm in oc._ledger_entries(ledger_root):
        if str(fm.get("oracle", "")).strip().lower() != "true":
            continue
        if tipo_display is not None and fm.get("tipo") != tipo_display:
            continue
        ratification = fm.get("ratification")
        if ratification not in ("ratified", "corrected", "pending"):
            continue  # entrada de oráculo malformada/sem o campo — não conta no SM-2, não trava o cálculo
        counts[ratification] += 1
        if args.verbose:
            entries.append({
                "path": str(path), "tipo": fm.get("tipo"), "ticket": fm.get("ticket"),
                "ratification": ratification,
            })

    decided = counts["ratified"] + counts["corrected"]
    total = decided + counts["pending"]
    pct_ratified = (counts["ratified"] / decided * 100.0) if decided > 0 else None

    result: dict[str, Any] = {
        "ledger_root": str(ledger_root),
        "tipo_filter": tipo_display,
        "ratified": counts["ratified"],
        "corrected": counts["corrected"],
        "pending": counts["pending"],
        "decided": decided,
        "total": total,
        "pct_ratified": pct_ratified,
        "note": (
            "pct_ratified = ratified / (ratified + corrected) * 100 — exclui `pending` "
            "do denominador (uma decisão ainda não ratificada/corrigida não é evidência "
            "nem a favor nem contra o oráculo); null quando decided == 0 (nenhuma "
            "decisão do oráculo foi ratificada ou corrigida ainda — SM-2 indefinido, "
            "nunca 0/100 por omissão)."
        ),
    }
    if args.verbose:
        result["entries"] = entries
    print(json.dumps(result, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    cp = sub.add_parser("consult-precedent", help="consulta o Ledger+product-decisions ANTES de decidir (nunca grava nada)")
    cp.add_argument("--ledger-root", default="wiki/ledger")
    cp.add_argument("--tipo", choices=sorted(("decisao-tecnica", "decisao-de-produto", "decisao-de-arquitetura")), default="decisao-tecnica")
    cp.add_argument("--areas", default="", help="areas do candidato (mesma lista que iria em record-decision --areas) — substrato da definição operacional de 'similar'")
    cp.add_argument("--keywords", default=None, help="tokens extra (além de --areas) usados só na varredura INFORMACIONAL de product-decisions.md/decisions.md, nunca no cálculo mecânico")
    cp.add_argument("--oracle-config", default=None, help="path de oracle.config.json (default: sibling, project_controll/gerente/oracle.config.json)")
    cp.add_argument("--product-decisions-path", default=str(_REPO_ROOT / "_bmad-output" / "product-decisions.md"))
    cp.add_argument("--decisions-path", default=str(_REPO_ROOT / "_bmad-output" / "decisions.md"))
    cp.set_defaults(func=cmd_consult_precedent)

    sm2 = sub.add_parser("sm2", help="calcula % de decisões do oráculo ratificadas (SM-2, PRD 00 §7) a partir do rastro real")
    sm2.add_argument("--ledger-root", default="wiki/ledger")
    sm2.add_argument("--tipo", choices=sorted(("decisao-tecnica", "decisao-de-produto", "decisao-de-arquitetura")), default=None, help="filtra por categoria (default: todas)")
    sm2.add_argument("--verbose", action="store_true", help="inclui a lista de entradas contadas na resposta")
    sm2.set_defaults(func=cmd_sm2)

    return p


def main(argv: Optional[list] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
