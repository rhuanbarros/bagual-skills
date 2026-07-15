#!/usr/bin/env python3
"""semgrep/scripts/flag_suspected_fp.py — E7.3 "FP não congela a noite" (PRD 04 FR-2).

Story E7.3 (ideias/sistema-artifacts/E7-3-gate-git-hook.md), PRD 04 FR-2,
ideias/epics.md Epic E7.

Quando o hook de pre-commit (`hooks/pre-commit`) bloqueia um commit por causa de
uma violação de regra `status: active`, o agente headless (rodando de madrugada,
sem humano) tem UM caminho de saída que não é "silenciosamente ignorar a regra":
registrar, com justificativa obrigatória, que a violação é uma SUSPEITA de
falso-positivo. Isso NUNCA aceita a violação em silêncio — grava uma entrada
auditável, rebaixando aquele achado específico (não a regra inteira, não o
projeto inteiro) para "aceito-pendente-de-ratificação", permitindo o commit
prosseguir, e deixa um rastro para o dono revisar de manhã (o mecanismo real
de "Briefing" que ratificaria isso, Epic E8, ainda não existe — até lá, o
log é o rastro; ver Dev Notes da story para a limitação registrada
explicitamente).

Isso é DIFERENTE de aceitar a violação de vez: nenhuma entrada aqui muda
`rules.yaml` nem promove/despromove uma regra. Uma flag mal-julgada (era uma
violação real, não um FP) fica visível no log para o dono reverter — nunca é
apagada, só se acumula (mesmo espírito append-only do log de violações, E7.5).

Uso:
    python3 semgrep/scripts/flag_suspected_fp.py \
        --rule-id no-import-meta-env --file frontend/src/main.tsx --line 10 \
        --reason "Sentry precisa ler import.meta.env antes do React montar — \
mesmo padrão já aceito no Spike S1/E7.1 para este arquivo especificamente"

Cada chamada appenda UMA linha JSON a
`project_controll/semgrep-fp-suspects.jsonl` (append + flush + fsync — mesma
disciplina de escrita das demais partes do Cerco). O hook
(`hooks/pre-commit`) consulta esse log antes de bloquear: se já existe uma
entrada com o mesmo fingerprint (rule_id + file + line) para o commit atual,
o achado é tratado como aceito-pendente-de-ratificação e NÃO bloqueia —
mas continua aparecendo no relatório do hook como "flagueado, aguardando
ratificação", nunca some silenciosamente.

Só biblioteca padrão (stdlib) — nenhuma dependência externa.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_LOG = REPO_ROOT / "project_controll" / "semgrep-fp-suspects.jsonl"


def fingerprint(rule_id: str, file: str, line: int) -> str:
    return f"{rule_id}::{file}::{line}"


def append_flag(log_path: Path, rule_id: str, file: str, line: int, reason: str) -> dict:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fingerprint": fingerprint(rule_id, file, line),
        "rule_id": rule_id,
        "file": file,
        "line": line,
        "reason": reason,
        "status": "pending_ratification",
    }
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
    return entry


def load_pending_fingerprints(log_path: Path) -> set[str]:
    """Lê o log inteiro e retorna o conjunto de fingerprints já flagueados.

    Usado pelo hook para decidir se um achado bloqueado pode prosseguir. Não
    há "revogação" mecanizada ainda (isso dependeria do Briefing/E8, fora de
    escopo desta story) — uma vez flagueado, o fingerprint fica
    permanentemente pending_ratification neste log; o dono pode auditar
    `project_controll/semgrep-fp-suspects.jsonl` a qualquer momento (é texto
    plano, append-only, git-trackable) e decidir separadamente (revert do
    código, ajuste do pattern da regra, ou aceitar de fato).
    """
    if not log_path.exists():
        return set()
    fingerprints: set[str] = set()
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        fp = entry.get("fingerprint")
        if fp:
            fingerprints.add(fp)
    return fingerprints


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rule-id", required=True, help="check_id da regra Semgrep (ex.: no-import-meta-env)")
    parser.add_argument("--file", required=True, help="path (relativo ao repo) do arquivo com a violação")
    parser.add_argument("--line", required=True, type=int, help="linha da violação")
    parser.add_argument("--reason", required=True, help="justificativa obrigatória, não-vazia — por que é suspeita de FP")
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG, help="path do log (default: project_controll/semgrep-fp-suspects.jsonl)")
    args = parser.parse_args(argv)

    if not args.reason or not args.reason.strip():
        print("erro: --reason é obrigatória e não pode ser vazia (FP não congela, mas também não é silencioso)", file=sys.stderr)
        return 2

    entry = append_flag(args.log, args.rule_id, args.file, args.line, args.reason.strip())
    print(f"OK: flagueado como suspeita-de-FP (pending_ratification): {entry['fingerprint']}")
    print(f"Registrado em: {args.log}")
    print("O commit pode ser tentado novamente — o hook agora trata este achado específico como aceito-pendente-de-ratificação.")
    print("Isto NÃO desativa a regra nem aceita violações futuras deste mesmo padrão em outros arquivos/linhas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
