#!/usr/bin/env python3
"""validate_ledger.py — E4.1/E4.2/E4.3/E4.4 validação mecânica de Entradas de Ledger.

Stories E4.1 (ideias/sistema-artifacts/E4-1-schema-gramatica-madr.md),
E4.2 (E4-2-ciclo-vida-causa-morte.md), E4.3 (E4-3-contador-utilidade.md),
E4.4 (E4-4-selo-maturidade.md) — PRD 01 FR-4..FR-8, ideias/epics.md Epic E4.

Dado a raiz de uma árvore do Ledger (ou de toda a Wiki), valida cada documento
mecanicamente contra o schema publicado em `../README.md` (este mesmo diretório):

  1. TIPO — `tipo` presente e é um dos 6 slugs-de-Ledger canônicos (senão: violação
     "sem tipo"/"tipo inválido"). Um `tipo` VÁLIDO mas FORA do Ledger (`nota-operacional`,
     `spec`, `ticket`, `design-doc`, `changelog`, `timeline`, `reference` — os outros 7
     do catálogo de 13 tipos de document-types.md) é reconhecido e explicitamente
     ISENTO das checagens 2-6 abaixo — não é violação, é a prova mecânica de FR-6/F26
     ("MADR só p/ decisão/regra/padrão/anti-pattern; nota/changelog/timeline não").
  2. MADR — `## Contexto`, `## Decisão`, `## Alternativas...`, `## Consequências`
     presentes no corpo (por prefixo); `regra` exige também `## Enforcement`. Só roda
     para os 6 tipos-de-Ledger (E4.1).
  3. ESTADO — `estado` presente e válido (candidata/ativa/aposentada) (E4.2).
  4. CAUSA DA MORTE — `aposentada` exige `causa-da-morte` não-vazia; qualquer outro
     estado com `causa-da-morte` preenchida é uma inconsistência sinalizada (E4.2).
  5. REVERSÃO — se `reverte` preenchido, resolve para um `.md` existente dentro da
     raiz escaneada (E4.2 — "reversão com link", nunca solta).
  6. SELO — `anti-pattern` exige `selo` ∈ {🟢, 🟡, 🔴} (E4.4).
  7. CONTADOR — `contador-de-utilidade`, quando presente, é um inteiro; entradas
     `tipo: regra` (ou `anti-pattern` com `automatizado: true`) com contador 0 e
     `estado != aposentada` viram `poda_candidatos`; `decisão-*`/`padrão` com contador
     0 vão para `isentos_baixa_utilidade` — NUNCA misturados (E4.3, isenção de FR-7).

Este script NUNCA corrige nada — só reporta violações (mesma filosofia read-only de
`validate_wiki_docs.py`, E3.4: a bibliotecária nunca conserta um documento sozinha).
Não duplica a checagem de schema geral de 13 tipos (isso é `validate_wiki_docs.py`,
E3.4) — este script é específico do Ledger, com checagens mais profundas (MADR,
reversão, poda por utilidade) que aquele script não cobre.

Uso:
    python3 validate_ledger.py --ledger-root wiki/ledger
    python3 validate_ledger.py --ledger-root wiki/ledger --json

Só biblioteca padrão (stdlib) — nenhuma dependência externa. Reusa o mesmo parser de
front-matter minimalista de `retrieve_slice.py`/`validate_wiki_docs.py` (E3.3/E3.4) —
subconjunto de YAML: escalar, lista em fluxo, lista em bloco.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

FRONT_MATTER_DELIM = "---"

LEDGER_TIPOS = {
    "decisão-técnica",
    "decisão-de-produto",
    "decisão-de-arquitetura",
    "regra",
    "padrão",
    "anti-pattern",
}

# Os outros 7 slugs canônicos de document-types.md (E3.1) — válidos, mas fora do
# escopo MADR/estado do Ledger (FR-6, endurecido F26).
NON_LEDGER_TIPOS_CONHECIDOS = {
    "nota-operacional",
    "spec",
    "ticket",
    "design-doc",
    "changelog",
    "timeline",
    "reference",
}

VALID_ESTADOS = {"candidata", "ativa", "aposentada"}
VALID_SELOS = {"🟢", "🟡", "🔴"}

MADR_REQUIRED_PREFIXES = (
    "## Contexto",
    "## Decisão",
    "## Alternativas",
    "## Consequências",
)
REGRA_EXTRA_PREFIX = "## Enforcement"


def _clean(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1]
    return value


def parse_front_matter(text: str) -> dict[str, Any]:
    """Parse a YAML front-matter block. Mesmo parser minimalista de retrieve_slice.py."""
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
            continue  # linha de comentário dentro do front-matter (ex.: template-entrada.md)

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


def body_after_front_matter(text: str) -> str:
    lines = text.splitlines()
    if not lines or lines[0].strip() != FRONT_MATTER_DELIM:
        return text
    for i in range(1, len(lines)):
        if lines[i].strip() == FRONT_MATTER_DELIM:
            return "\n".join(lines[i + 1 :])
    return ""


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip().lower() in ("", "null"):
        return True
    return False


def check_madr(body: str, tipo: str) -> list[str]:
    """Checagem 2: seções MADR presentes, só para tipos-de-Ledger."""
    if tipo not in LEDGER_TIPOS:
        return []  # fora do escopo — nota-operacional/changelog/timeline etc. não são cobrados

    lines = [ln.strip() for ln in body.splitlines()]
    violations: list[str] = []
    for prefix in MADR_REQUIRED_PREFIXES:
        if not any(ln.startswith(prefix) for ln in lines):
            violations.append(f"gramática MADR: seção '{prefix}' ausente")
    if tipo == "regra" and not any(ln.startswith(REGRA_EXTRA_PREFIX) for ln in lines):
        violations.append(f"tipo 'regra' exige seção '{REGRA_EXTRA_PREFIX}' ausente")
    return violations


def check_estado_causa(fm: dict[str, Any]) -> list[str]:
    """Checagens 3-4: estado válido + aposentada exige causa-da-morte."""
    violations: list[str] = []
    estado = fm.get("estado")
    if _is_missing(estado):
        violations.append("Entrada de Ledger sem `estado` no front-matter")
        return violations
    if estado not in VALID_ESTADOS:
        violations.append(f"`estado: {estado}` inválido (esperado um de {sorted(VALID_ESTADOS)})")
        return violations

    causa = fm.get("causa-da-morte")
    if estado == "aposentada" and _is_missing(causa):
        violations.append("`estado: aposentada` sem `causa-da-morte` (obrigatória)")
    elif estado != "aposentada" and not _is_missing(causa):
        violations.append(
            f"`causa-da-morte` presente ('{causa}') mas `estado: {estado}` != aposentada "
            "(inconsistência — deveria ser null/ausente)"
        )
    return violations


def check_reversao(fm: dict[str, Any], doc_path: Path, ledger_root: Path) -> list[str]:
    """Checagem 5: `reverte`, quando preenchido, resolve para um .md existente."""
    reverte = fm.get("reverte")
    if _is_missing(reverte):
        return []
    target = (doc_path.parent / reverte).resolve()
    if not target.exists():
        target = (ledger_root / reverte).resolve()
    if not target.exists():
        return [f"`reverte: {reverte}` — link de reversão quebrado (arquivo não encontrado)"]
    if target.suffix != ".md":
        return [f"`reverte: {reverte}` — não aponta para um documento .md"]
    return []


def check_selo(fm: dict[str, Any], tipo: str) -> list[str]:
    """Checagem 6: selo válido, só para anti-pattern."""
    if tipo != "anti-pattern":
        return []
    selo = fm.get("selo")
    if _is_missing(selo):
        return ["tipo `anti-pattern` sem `selo` (obrigatório: 🟢, 🟡 ou 🔴)"]
    if selo not in VALID_SELOS:
        return [f"`selo: {selo}` inválido (esperado um de {sorted(VALID_SELOS)})"]
    return []


def check_contador_type(fm: dict[str, Any]) -> list[str]:
    """Parte da checagem 7: contador-de-utilidade é um inteiro quando presente."""
    contador = fm.get("contador-de-utilidade")
    if _is_missing(contador):
        return []
    try:
        int(str(contador))
    except ValueError:
        return [f"`contador-de-utilidade: {contador}` não é um inteiro"]
    return []


# Tipos sujeitos à poda-por-utilidade quando o contador fica em zero (E4.3, FR-7):
# só `regra` tem evento de "foi aplicada" de fato instrumentável (o enforcement do
# PRD 04). `anti-pattern` com automatizado:true entra pelo mesmo racional (a regra
# Semgrep derivada dele passa a incrementar seu contador também).
PODA_ELEGIVEL_TIPOS = {"regra"}
# Isentos por desenho (FR-7 + extensão documentada em document-types.md p/ `padrão`):
# nunca aparecem em poda_candidatos, mesmo com contador 0.
ISENTOS_POR_TIPO = {"decisão-técnica", "decisão-de-produto", "decisão-de-arquitetura", "padrão"}


def validate_doc(fm: dict[str, Any], body: str, doc_path: Path, ledger_root: Path) -> dict[str, Any]:
    """Valida um único documento; retorna {tipo, violations, escopo}."""
    tipo = fm.get("tipo")

    if _is_missing(tipo):
        return {"tipo": None, "escopo": "sem-tipo", "violations": ["sem `tipo` no front-matter"]}

    if tipo in NON_LEDGER_TIPOS_CONHECIDOS:
        return {"tipo": tipo, "escopo": "fora-do-ledger", "violations": []}

    if tipo not in LEDGER_TIPOS:
        return {
            "tipo": tipo,
            "escopo": "tipo-invalido",
            "violations": [f"`tipo: {tipo}` não é um dos 6 slugs-de-Ledger nem um dos 7 tipos gerais da Wiki"],
        }

    violations: list[str] = []
    violations += check_madr(body, tipo)
    violations += check_estado_causa(fm)
    violations += check_reversao(fm, doc_path, ledger_root)
    violations += check_selo(fm, tipo)
    violations += check_contador_type(fm)

    return {"tipo": tipo, "escopo": "ledger", "violations": violations}


def scan_and_validate(ledger_root: Path) -> dict[str, Any]:
    ok: list[str] = []
    violations: dict[str, list[str]] = {}
    fora_do_ledger: list[str] = []
    poda_candidatos: list[dict[str, Any]] = []
    isentos_baixa_utilidade: list[dict[str, Any]] = []

    for path in sorted(ledger_root.rglob("*.md")):
        if path.name in ("index.md", "template-entrada.md", "README.md"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue

        fm = parse_front_matter(text)
        body = body_after_front_matter(text)
        rel = str(path.relative_to(ledger_root))

        result = validate_doc(fm, body, path, ledger_root)

        if result["escopo"] == "fora-do-ledger":
            fora_do_ledger.append(rel)
            continue

        if result["violations"]:
            violations[rel] = result["violations"]
        else:
            ok.append(rel)

        tipo = result["tipo"]
        estado = fm.get("estado")
        contador = fm.get("contador-de-utilidade")
        automatizado = str(fm.get("automatizado", "false")).strip().lower() == "true"
        try:
            contador_int = int(str(contador)) if not _is_missing(contador) else None
        except ValueError:
            contador_int = None

        if contador_int == 0 and estado != "aposentada":
            elegivel = tipo in PODA_ELEGIVEL_TIPOS or (tipo == "anti-pattern" and automatizado)
            if elegivel:
                poda_candidatos.append({"path": rel, "tipo": tipo, "contador": contador_int})
            elif tipo in ISENTOS_POR_TIPO:
                isentos_baixa_utilidade.append({"path": rel, "tipo": tipo, "contador": contador_int})

    return {
        "ledger_root": str(ledger_root),
        "ok_count": len(ok),
        "ok": ok,
        "violation_count": len(violations),
        "violations": violations,
        "fora_do_ledger_count": len(fora_do_ledger),
        "fora_do_ledger": fora_do_ledger,
        "poda_candidatos": poda_candidatos,
        "isentos_baixa_utilidade": isentos_baixa_utilidade,
    }


def _print_human(result: dict[str, Any]) -> None:
    print(f"Ledger root: {result['ledger_root']}")
    print(f"Entradas conformes: {result['ok_count']}")
    for p in result["ok"]:
        print(f"  ✓ {p}")
    print()
    print(f"Entradas com violação ({result['violation_count']}):")
    if not result["violations"]:
        print("  (nenhuma)")
    for path, reasons in result["violations"].items():
        print(f"  ✗ {path}")
        for r in reasons:
            print(f"      - {r}")
    print()
    print(f"Documentos fora do escopo do Ledger (tipo válido, mas não é Entrada de Ledger) ({result['fora_do_ledger_count']}):")
    if not result["fora_do_ledger"]:
        print("  (nenhum)")
    for p in result["fora_do_ledger"]:
        print(f"  · {p}  — MADR/estado/causa-da-morte NÃO cobrados (FR-6/F26)")
    print()
    print(f"Candidatos a aposentar por baixa utilidade — contador 0, tipo elegível ({len(result['poda_candidatos'])}):")
    if not result["poda_candidatos"]:
        print("  (nenhum)")
    for c in result["poda_candidatos"]:
        print(f"  ⚠ {c['path']}  [tipo:{c['tipo']}]")
    print()
    print(f"Isentos de poda por utilidade (decisão-*/padrão com contador 0 — NUNCA candidatos, FR-7) ({len(result['isentos_baixa_utilidade'])}):")
    if not result["isentos_baixa_utilidade"]:
        print("  (nenhum)")
    for c in result["isentos_baixa_utilidade"]:
        print(f"  ○ {c['path']}  [tipo:{c['tipo']}]  — isenta, nunca listada como candidata")
    print()
    print("Nota: violações são REPORTADAS, nunca corrigidas por este script.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ledger-root", required=True, type=Path, help="Raiz da árvore do Ledger (ou da Wiki) a escanear")
    parser.add_argument("--json", action="store_true", help="Emite JSON em vez de texto legível")
    args = parser.parse_args(argv)

    if not args.ledger_root.exists():
        print(f"erro: ledger-root não existe: {args.ledger_root}", file=sys.stderr)
        return 2

    result = scan_and_validate(args.ledger_root)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        _print_human(result)

    # Exit code reflete violações — senão um gate futuro `validate_ledger.py && cutover`
    # passaria verde COM violações. Consumidores que leem o resultado estruturado (ex.:
    # gerente_oracle.py) não são afetados (leem stdout JSON, não o rc).
    return 0 if result["violation_count"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
