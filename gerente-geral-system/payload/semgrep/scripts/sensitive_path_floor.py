#!/usr/bin/env python3
"""semgrep/scripts/sensitive_path_floor.py — E7.6 piso de path sensível (PRD 04 FR-9).

Story E7.6 (ideias/sistema-artifacts/E7-6-ordem-portoes-piso.md), PRD 04 FR-9,
ideias/epics.md Epic E7. Ver a doc completa:
`wiki/cerco-ordem-portoes.md`.

A Trilha (classificador LLM, PRD 02/00) decide "reduzido vs. completo" — mas
esse classificador pode errar, e é exatamente o tipo de julgamento prosa-que-
promete-obedecer que a tese do sistema combate. Este script é o **piso
mecânico**: um diff que toca qualquer path/padrão abaixo recebe Cerco
COMPLETO sempre, MESMO que a Trilha tenha classificado o ticket como trivial
— checagem por regex/glob, nunca por julgamento de LLM (AC de E7.6: "a Trilha
só pode REDUZIR fora do piso").

Categorias do piso (derivadas de AGENTS.md + backend/agents.md, não
inventadas por esta story):
  - créditos          (backend/agents.md §"Credits Feature Checklist" — RPCs
                        atômicas, CreditService, nunca aritmética em `.update()`)
  - auth               (AGENTS.md — autenticação & roles, TEMPLATE)
  - propostas/pagamento (AGENTS.md — proposals/Stripe, domínio CLIENTE crítico)
  - [TEMPLATE]          (AGENTS.md §"Template features vs Client features" —
                         billing, admin, créditos, auth, infra compartilhada)

Uso:
    python3 semgrep/scripts/sensitive_path_floor.py --diff
    python3 semgrep/scripts/sensitive_path_floor.py --paths backend/api/credits.py foo.ts
    python3 semgrep/scripts/sensitive_path_floor.py --diff --json

Exit code: sempre 0 (este script nunca falha um processo — é uma leitura/
classificação, quem decide o que fazer com o resultado é quem o chama, ex.:
o story-processor/o Orquestrador). `floor_triggered` no output é o sinal.

Só biblioteca padrão (stdlib) — nenhuma dependência externa.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# Cada entrada: (categoria, [padrões glob relativos ao repo-root]).
# Padrões usam fnmatch (`*` não cruza `/` sozinho seguido de outro `*`; `**`
# tratado como "qualquer profundidade" via normalização abaixo).
SENSITIVE_PATH_GROUPS: list[tuple[str, list[str]]] = [
    (
        "creditos",
        [
            "backend/src/credits/**",
            "backend/api/credits.py",
            "backend/api/admin_credits.py",
            "backend/agents/admin_credits_dashboard_agent.py",
            "frontend/src/features/credits/**",
            "frontend/src/features-admin/credits/**",
        ],
    ),
    (
        "auth",
        [
            "backend/api/auth.py",
            "backend/repositories/auth_admin_repository.py",
            "frontend/src/auth/**",
            "frontend/src/lib/auth.ts",
            "frontend/src/store/authStore*.ts",
        ],
    ),
    (
        "propostas-pagamento",
        [
            "backend/domain/proposals/**",
            "backend/api/proposals.py",
            "backend/api/admin_proposals.py",
            "backend/repositories/proposals_repository.py",
            "backend/repositories/proposal_status_history_repository.py",
            "backend/agents/proposals_agent.py",
            "backend/agents/admin_proposals_agent.py",
            "frontend/src/features/proposals/**",
            "backend/src/stripe_billing/**",
            "backend/api/stripe_checkout.py",
            "backend/api/stripe_webhooks.py",
            "frontend/src/features/subscription/**",
        ],
    ),
    (
        "template",
        [
            # AGENTS.md §"Template features vs Client features" — plataforma core
            # mantida upstream: auth/roles, Stripe billing, créditos (já cobertos
            # acima), admin dashboard/user management, app settings/feature
            # flags, observabilidade, infra/scaffolding compartilhado, landing.
            "backend/agents/admin_*.py",
            "backend/api/admin_dashboard.py",
            "frontend/src/features-admin/**",
            "frontend/src/landing/**",
            "backend/src/observability/**",
            "backend/src/app_settings/**",
        ],
    ),
]


def _normalize(path: str) -> str:
    return path.replace("\\", "/")


def matches_any(path: str, patterns: list[str]) -> str | None:
    norm = _normalize(path)
    for pattern in patterns:
        if fnmatch.fnmatch(norm, pattern) or fnmatch.fnmatch(norm, pattern.replace("**/", "*/")):
            return pattern
        # também casa quando o pattern é um prefixo de diretório tipo "a/b/**"
        if pattern.endswith("/**") and norm.startswith(pattern[:-3]):
            return pattern
    return None


def git_changed_paths(repo_root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACMR", "HEAD"],
        cwd=repo_root, capture_output=True, text=True, check=False,
    )
    staged = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=ACMR", "--cached"],
        cwd=repo_root, capture_output=True, text=True, check=False,
    )
    changed = set(result.stdout.splitlines()) | set(staged.stdout.splitlines())
    return sorted(changed)


def evaluate_floor(paths: list[str]) -> dict[str, Any]:
    matched: list[dict[str, str]] = []
    categories_hit: set[str] = set()

    for path in paths:
        for category, patterns in SENSITIVE_PATH_GROUPS:
            pattern = matches_any(path, patterns)
            if pattern:
                matched.append({"path": path, "category": category, "pattern": pattern})
                categories_hit.add(category)

    return {
        "paths_checked": len(paths),
        "floor_triggered": bool(matched),
        "matched_files": matched,
        "categories_hit": sorted(categories_hit),
        "cerco": "completo" if matched else "conforme trilha",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--paths", nargs="*", default=None, help="Lista explícita de paths a checar (ex.: fixture/teste)")
    parser.add_argument("--diff", action="store_true", help="Usa git diff (HEAD ∪ --cached) em vez de --paths")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.diff:
        paths = git_changed_paths(REPO_ROOT)
    elif args.paths:
        paths = args.paths
    else:
        print("erro: forneça --diff ou --paths", file=sys.stderr)
        return 2

    result = evaluate_floor(paths)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Paths checados: {result['paths_checked']}")
        print(f"Piso acionado: {result['floor_triggered']}")
        if result["floor_triggered"]:
            print(f"Categorias: {', '.join(result['categories_hit'])}")
            for m in result["matched_files"]:
                print(f"  [{m['category']}] {m['path']}  (padrão: {m['pattern']})")
            print("=> Cerco COMPLETO obrigatório, independente da classificação da Trilha.")
        else:
            print("=> Nenhum path sensível tocado; a Trilha pode reduzir o Cerco normalmente.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
