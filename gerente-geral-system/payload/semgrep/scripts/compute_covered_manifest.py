#!/usr/bin/env python3
"""semgrep/scripts/compute_covered_manifest.py — E7.2 manifesto de regras cobertas.

Story E7.2 (ideias/sistema-artifacts/E7-2-pre-filtro.md), PRD 04 FR-1,
ideias/epics.md Epic E7.

O pré-filtro determinístico (FR-1) só pode remover uma regra do prompt das camadas
de LLM (`bmad-code-review`) quando ela está **ativa E autorada** — não basta ser
🟢-candidata, não basta ter fixtures, e não conta em modo degradado (binário do
Semgrep ausente). Este script computa esse manifesto:

    regra coberta  ⟺  metadata.status == "active"  AND  metadata.author não-vazio
                       AND  o binário do Semgrep (via uvx) está disponível nesta
                       invocação (senão: degradação RUIDOSA, nenhuma regra conta
                       como coberta, mesmo que `rules.yaml` tenha regras `active`)

Por que uma regra `status: report` NUNCA é "coberta" (mesmo com autor+fixtures):
report é a política de nascimento de TODA regra (E7.1/FR-1b) — ela ainda não
passou pelo ciclo de calibração sem falso-positivo (Story E7.3). Removê-la do
prompt do LLM antes da calibração real seria "otimismo" exatamente do tipo que
FR-1 proíbe ("uma regra 🟢 ainda sem pattern autorado continua no prompt do
LLM — não é removida por otimismo"; o mesmo raciocínio vale, a fortiori, para uma
regra com pattern mas ainda não calibrada).

Degradação ruidosa (PRD 04 §NFR "produtor externo, degradação RUIDOSA"): se
`uvx` não está no PATH, `degraded: true` é setado, `covered_rule_ids` fica
SEMPRE vazio (mesmo com regras `active` em rules.yaml — sem o binário rodando
de verdade nesta invocação, nada foi mecanicamente verificado, então a checagem
por LLM não pode ser dispensada), e — se `--degraded-log` for passado — uma
linha é appendada nesse log (mesmo padrão append-only de E7.5) para uma futura
curadoria/Briefing (Epic E8, ainda não construído) reconciliar. Nunca falha em
silêncio.

Uso:
    python3 semgrep/scripts/compute_covered_manifest.py
    python3 semgrep/scripts/compute_covered_manifest.py --json
    python3 semgrep/scripts/compute_covered_manifest.py --prompt-note
    python3 semgrep/scripts/compute_covered_manifest.py \
        --out {review_run_dir}/semgrep-manifest.json \
        --degraded-log project_controll/semgrep-degraded-log.jsonl

Consumido por: o dispatch do `bmad-code-review` (via o override
`_bmad/custom/bmad-code-review.toml`, Story E7.2) — roda ANTES do fan-out de
Step 2, escreve `{review_run_dir}/semgrep-manifest.json`, e o texto de
`--prompt-note` é anexado (aditivamente, sem substituir nada) ao prompt de cada
uma das 3 camadas.

Só biblioteca padrão (stdlib) — nenhuma dependência externa (mesma convenção dos
scripts de `wiki/ledger/scripts/`).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rules_yaml_lite import parse_rules  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_RULES = Path(__file__).resolve().parent.parent / "rules.yaml"
DEFAULT_DEGRADED_LOG = REPO_ROOT / "project_controll" / "semgrep-degraded-log.jsonl"


def uvx_available() -> bool:
    return shutil.which("uvx") is not None


def compute_manifest(rules_path: Path) -> dict[str, Any]:
    rules = parse_rules(rules_path)
    degraded = not uvx_available()
    reason = (
        "binário `uvx` ausente do PATH — Cerco mecânico rodou em modo degradado "
        "nesta invocação; nenhuma regra é tratada como coberta, mesmo que "
        "`rules.yaml` tenha regras `active` (sem o binário, nada foi verificado "
        "de verdade)."
        if degraded
        else ""
    )

    active_rules = {rid: r for rid, r in rules.items() if r["status"] == "active"}
    report_rules = {rid: r for rid, r in rules.items() if r["status"] == "report"}

    if degraded:
        covered_ids: list[str] = []
    else:
        covered_ids = sorted(rid for rid, r in active_rules.items() if r["author"].strip())

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "rules_file": str(rules_path),
        "total_rules": len(rules),
        "active_rules_count": len(active_rules),
        "report_rules_count": len(report_rules),
        "covered_rule_ids": covered_ids,
        "covered_rules": [
            {"id": rid, "message": rules[rid]["message"], "author": rules[rid]["author"]}
            for rid in covered_ids
        ],
        "degraded": degraded,
        "degraded_reason": reason,
    }


def render_prompt_note(manifest: dict[str, Any]) -> str:
    """Bloco aditivo para anexar ao prompt de cada camada de revisão (E7.2/FR-1)."""
    if manifest["degraded"]:
        return (
            "CERCO MECÂNICO (Semgrep, Story E7.2) — MODO DEGRADADO: "
            f"{manifest['degraded_reason']} Verifique TODAS as regras AST-decidíveis "
            "de AGENTS.md como de costume (nenhuma foi verificada mecanicamente nesta "
            "revisão)."
        )
    if not manifest["covered_rule_ids"]:
        return (
            "CERCO MECÂNICO (Semgrep, Story E7.2): nenhuma regra está atualmente "
            "`active` (todas nasceram em modo `report`, per PRD 04 FR-1b — ainda em "
            "calibração, Story E7.3). Nenhuma regra foi removida do seu escopo — "
            "verifique TODAS as regras de AGENTS.md como de costume."
        )
    lines = [
        "CERCO MECÂNICO (Semgrep, Story E7.2): as regras abaixo são AST-decidíveis, "
        "estão ATIVAS e AUTORADAS, e já foram checadas mecanicamente pelo Semgrep "
        "nesta revisão — não gaste esforço recaçando estas violações específicas "
        "(elas aparecem, se encontradas, no relatório separado do Semgrep, não aqui):",
    ]
    for rule in manifest["covered_rules"]:
        lines.append(f"  - {rule['id']}: {rule['message']}")
    lines.append(
        "Qualquer violação FORA desta lista (incluindo regras `report`/não-promovidas "
        "e qualquer padrão não-AST-decidível) continua no seu escopo integral."
    )
    return "\n".join(lines)


def append_degraded_log(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": manifest["generated_at"],
        "event": "semgrep_prefiltro_degradado",
        "reason": manifest["degraded_reason"],
        "source": "compute_covered_manifest.py (E7.2)",
    }
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rules", type=Path, default=DEFAULT_RULES, help="Path de semgrep/rules.yaml")
    parser.add_argument("--json", action="store_true", help="Emite o manifesto completo em JSON")
    parser.add_argument("--prompt-note", action="store_true", help="Emite só o bloco de texto p/ anexar ao prompt do LLM")
    parser.add_argument("--out", type=Path, default=None, help="Também escreve o manifesto JSON neste path")
    parser.add_argument(
        "--degraded-log",
        type=Path,
        nargs="?",
        const=DEFAULT_DEGRADED_LOG,
        default=None,
        help="Se setado (com ou sem valor), appenda ao log de degradação quando degraded=true",
    )
    args = parser.parse_args(argv)

    if not args.rules.exists():
        print(f"erro: rules file não encontrado: {args.rules}", file=sys.stderr)
        return 2

    manifest = compute_manifest(args.rules)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    if manifest["degraded"] and args.degraded_log:
        append_degraded_log(args.degraded_log, manifest)
        print(f"AVISO (ruidoso): {manifest['degraded_reason']}", file=sys.stderr)

    if args.prompt_note:
        print(render_prompt_note(manifest))
    elif args.json:
        print(json.dumps(manifest, indent=2, ensure_ascii=False))
    else:
        print(f"Regras totais: {manifest['total_rules']} | active: {manifest['active_rules_count']} | report: {manifest['report_rules_count']}")
        print(f"Degradado: {manifest['degraded']}" + (f" — {manifest['degraded_reason']}" if manifest["degraded"] else ""))
        print(f"Regras cobertas (removíveis do prompt LLM): {manifest['covered_rule_ids'] or '(nenhuma)'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
