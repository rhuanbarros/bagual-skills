#!/usr/bin/env python3
"""classify_trilha.py — E9.4 classificação mecânica: comita o óbvio, escala o ambíguo.

🔴 APOSENTADO como decisor de trilha (TCK-20260727143826-7573, 2026-07-27) — ver
`wiki/ledger/decisao-tecnica/roteamento-de-trilha-e-plano-antes-da-execucao.md`.
`bagual-tickets` NÃO chama mais este script; a decisão de `trilha` passou a ser
julgamento do Gerente/dono (ver `dispatch-and-review.md` step 1 +
`spec-epic-routing-execution.md`), nunca mais uma regra fixa de script. Motivo: os
dados reais do board mostraram que as 2 regras abaixo só cobriam o óbvio — TODO bug
confirmado caía em `rapida` (um typo e um fix de segurança na MESMA trilha leve) e
`spec`/`epic` nunca eram atribuídos automaticamente, afunilando trabalho substancial
pro caminho leve. **Este arquivo e seu teste (`test_classify_trilha.py`) NÃO foram
apagados** — mantidos só para histórico/consulta; nenhum hook/cron/CI os invoca mais.
O código abaixo continua funcional (não foi alterado), só não é mais chamado por
ninguém no fluxo real.

Story E9.4 (ideias/sistema-artifacts/E9-4-escalonamento-skill.md), PRD 02 FR-5,
ideias/epics.md Epic E9.

`bagual-tickets` (`.claude/skills/bagual-tickets/SKILL.md` § Resolver, "Escalonamento de
trilha") chamava este script na transição de um ticket para `pronto-para-implementar`, em
vez de decidir a `trilha` por "vibe"/leitura livre do texto — mesma filosofia de gate
mecânico já usada pelo Oráculo (`gerente_oracle.py::_resolve_confidence`, Story E9.1):
"na dúvida, escalar" tem que ser uma propriedade PROVÁVEL do código, não uma promessa de
prompt. Este script nunca escreve nada — só lê um `.md` de ticket e devolve a decisão
(`trilha` a comitar, ou `escalonar: true` + motivo) em JSON. Quem grava a decisão de
volta no `.md`/`board.yaml` é a skill (ou quem estiver chamando), exatamente como
devolvido — nunca sobrescrita por um palpite.

Regras (só duas, deliberadamente estreitas — ver PRD 02 FR-5 / epics.md Story E9.4):

  Regra A ("bug claro" → `rapida`) — TODAS as condições:
    - `category: bug`
    - Verificação confirmada (`## Verificação` → `- Confirmado: sim`) OU o ticket veio
      do fast-path trivial (F22 — `## Log` contém "fast-path trivial")
    - `expanded: false` (um único local — escopo não é maior que uma correção pontual)
    - `## Checagem de decisão de produto` afirma explicitamente "nenhum conflito"

  Regra B ("feature com design confirmado" → `wds`) — TODAS as condições:
    - `category: feature`
    - `design_confirmado: true` no front-matter (campo novo desta story — só é `true`
      quando quem triou já concluiu, de forma inequívoca, que a resolução exige uma
      tela/componente visual novo; nunca inferido por palavra-chave em texto livre aqui)
    - `## Checagem de decisão de produto` afirma explicitamente "nenhum conflito"

Qualquer ticket que não bata 100% em uma das duas regras é ESCALADO (`trilha` continua
`null`, `escalonar: true`, com o(s) motivo(s) específico(s) da não-classificação) — nunca
uma classificação "aproximada". Isso cobre deliberadamente `chore`/`duvida`, bugs
expandidos/não verificados, features sem design confirmado, e qualquer conflito de
decisão de produto não resolvido.

Uso:
    python3 classify_trilha.py --ticket project_controll/tickets/TCK-004-foo.md
    python3 classify_trilha.py --ticket <path> --json

Só biblioteca padrão (stdlib) — mesma convenção dos scripts irmãos
(`rebuild_board.py`), inclusive o parser de front-matter mantido standalone de
propósito (sem import cruzado entre scripts irmãos, mesma decisão documentada em
`rebuild_board.py`).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

FRONT_MATTER_DELIM = "---"


# ---------------------------------------------------------------------------
# Front-matter parsing (cópia standalone do parser minimalista de rebuild_board.py —
# mesmo subconjunto de YAML: escalar, lista em fluxo, lista em bloco).
# ---------------------------------------------------------------------------
def _clean(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        quote = value[0]
        value = value[1:-1]
        if quote == '"':
            value = value.replace('\\"', '"').replace("\\\\", "\\")
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


def body_after_front_matter(text: str) -> str:
    lines = text.splitlines()
    if not lines or lines[0].strip() != FRONT_MATTER_DELIM:
        return text
    for i in range(1, len(lines)):
        if lines[i].strip() == FRONT_MATTER_DELIM:
            return "\n".join(lines[i + 1:])
    return text


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "sim", "yes")


# ---------------------------------------------------------------------------
# Extração de seções do corpo (Markdown nível 2, `## Título` até o próximo `## `)
# ---------------------------------------------------------------------------
def extract_section(body: str, heading: str) -> str | None:
    pattern = re.compile(
        rf"^##\s+{re.escape(heading)}\s*$(.*?)(?=^##\s+|\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(body)
    if not m:
        return None
    return m.group(1).strip()


def get_confirmado(body: str) -> str | None:
    sec = extract_section(body, "Verificação")
    if not sec:
        return None
    for line in sec.splitlines():
        stripped = line.strip().lstrip("-").strip()
        if stripped.lower().startswith("confirmado:"):
            return stripped.split(":", 1)[1].strip().lower()
    return None


def has_fast_path_trivial(body: str) -> bool:
    log = extract_section(body, "Log") or ""
    return "fast-path trivial" in log.lower()


# Veredito afirmativo de "sem conflito de produto": uma linha que COMEÇA com "nenhum conflito"
# (ex.: "Nenhum conflito encontrado em `product-decisions.md`."), tolerando um marcador de
# lista/checkbox à frente ("- [x] nenhum conflito"). Ancorado em ^ de propósito — nunca casa a
# frase enterrada no meio de uma sentença que a nega.
_CLEAR_VERDICT_RE = re.compile(r"^\s*(?:[-*+]\s+)?(?:\[[ xX]\]\s+)?nenhum conflito", re.IGNORECASE)


def conflict_status(body: str) -> str:
    """Retorna 'clear' | 'conflict' | 'unknown'.

    'unknown' (seção ausente/vazia) NUNCA vale como 'clear' — ausência de checagem não é
    prova de ausência de conflito, é falta de informação (escala, não assume).
    """
    sec = extract_section(body, "Checagem de decisão de produto")
    if not sec:
        return "unknown"
    # 'clear' SÓ quando alguma LINHA é o veredito afirmativo "nenhum conflito" (ancorado no
    # início da linha, tolerando marcador de lista/checkbox). Substring livre era fail-open: uma
    # seção que NEGA a liberação ("é falso dizer que há nenhum conflito", "não afirmo que há
    # 'nenhum conflito'") continha a frase e virava 'clear' → auto-comitava em vez de escalar,
    # invertendo o invariante "na dúvida, escala".
    for line in sec.splitlines():
        if _CLEAR_VERDICT_RE.match(line):
            return "clear"
    return "conflict"


# ---------------------------------------------------------------------------
# Classificação
# ---------------------------------------------------------------------------
def classify(fm: dict[str, Any], body: str) -> dict[str, Any]:
    category = str(fm.get("category") or "").strip().lower()
    expanded = _truthy(fm.get("expanded", False))
    design_confirmado = _truthy(fm.get("design_confirmado", False))
    confirmado = get_confirmado(body)
    fast_path = has_fast_path_trivial(body)
    conflict = conflict_status(body)

    verified_or_trivial = fast_path or (confirmado == "sim")

    # Regra A — bug claro → rapida
    if category == "bug" and verified_or_trivial and not expanded and conflict == "clear":
        return {
            "trilha": "rapida",
            "escalonar": False,
            "rule": "A",
            "reason": "bug claro: verificação confirmada (ou fast-path trivial), único local, sem conflito de decisão de produto",
        }

    # Regra B — feature com design confirmado → wds
    if category == "feature" and design_confirmado and conflict == "clear":
        return {
            "trilha": "wds",
            "escalonar": False,
            "rule": "B",
            "reason": "alteração de produto com necessidade de design já confirmada explicitamente na triagem (design_confirmado: true), sem conflito de decisão de produto",
        }

    # Nenhuma regra bateu 100% — escala, sempre com motivo explícito e específico
    motivos: list[str] = []
    if category not in ("bug", "feature"):
        motivos.append(
            f"categoria '{category or '(vazia)'}' fora das regras óbvias — só bug (regra A) e feature (regra B) têm regra de commit direto"
        )
    elif category == "bug":
        if not verified_or_trivial:
            motivos.append("bug não confirmado em código (nem fast-path trivial) — Confirmado="
                            f"{confirmado!r}")
        if expanded:
            motivos.append("bug expandido em múltiplos locais (expanded: true) — escopo não é um único ponto")
    elif category == "feature":
        if not design_confirmado:
            motivos.append("feature sem necessidade de design confirmada explicitamente (design_confirmado ausente/false)")

    if conflict != "clear":
        motivos.append(f"checagem de decisão de produto: {conflict} (precisa ser 'clear' — seção com 'nenhum conflito' explícito)")

    if not motivos:
        motivos.append("sinal insuficiente para bater 100% em Regra A ou Regra B")

    return {
        "trilha": None,
        "escalonar": True,
        "rule": None,
        "reason": "; ".join(motivos),
    }


def classify_ticket_file(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    fm = parse_front_matter(text)
    body = body_after_front_matter(text)
    result = classify(fm, body)
    result["ticket"] = fm.get("id") or path.stem
    result["source"] = str(path)
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ticket", required=True, type=Path, help="Path do .md do ticket a classificar")
    parser.add_argument("--json", action="store_true", help="Emite JSON (default já é JSON — flag mantida por simetria com rebuild_board.py)")
    args = parser.parse_args(argv)

    if not args.ticket.exists():
        print(json.dumps({"error": f"ticket não encontrado: {args.ticket}"}, ensure_ascii=False))
        return 2

    result = classify_ticket_file(args.ticket)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
