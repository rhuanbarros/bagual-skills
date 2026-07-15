#!/usr/bin/env python3
"""test_read_fp_suspects.py — provas reais (subprocessos, não mocks) de E13.4.

Story E13.4 (ideias/sistema-artifacts/E13-4-loop-fp-briefing.md) — roda
`flag_suspected_fp.py` (E7.3, o ESCRITOR real) e `read_fp_suspects.py` (E13.4, o
LEITOR) como subprocessos de verdade contra um `.jsonl` temporário, para provar:

  1. Log ausente/vazio: `list-pending` devolve `ok: true`, `pending_count: 0` — nunca
     crasha.
  2. Duas suspeitas flagueadas (fingerprints distintos, via `flag_suspected_fp.py`
     real) aparecem ambas em `pending`, com `status: pending_ratification`.
  3. Dedup por fingerprint: flaguear o MESMO fingerprint duas vezes (append-only) só
     produz UMA entrada em `pending` (a mais recente), nunca duplicada.
  4. Linha JSON malformada isolada no meio do log é ignorada — não derruba o
     `list-pending` inteiro nem some com as entradas válidas ao redor.
  5. Ratificação (gesto de outro fluxo — nunca este leitor) faz o fingerprint
     desaparecer de `pending` SEM apagar nenhuma linha do log: contagem de linhas do
     arquivo cresce (append), a linha ORIGINAL `pending_ratification` continua
     presente via grep, e `unique_fingerprints` conta o fingerprint mas `pending`
     não o lista mais.
  6. `read_fp_suspects.py` nunca escreve no log — confirmado por hash/mtime do
     arquivo antes/depois de rodar `list-pending` (mesmo conteúdo, mesmo mtime).

Sem dependências externas (stdlib apenas). NUNCA escreve no log de produção
(`project_controll/semgrep-fp-suspects.jsonl`) — tudo roda contra
`tempfile.TemporaryDirectory()`.

Uso:
    python3 test_read_fp_suspects.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
READER = HERE / "read_fp_suspects.py"
WRITER = HERE.parents[2] / "semgrep" / "scripts" / "flag_suspected_fp.py"

PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        PASS.append(name)
        print(f"  PASS  {name}")
    else:
        FAIL.append(name)
        print(f"  FAIL  {name}  {detail}")


def run(script: Path, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True)


def run_json(script: Path, args: list[str]) -> dict:
    p = run(script, args)
    out = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else "{}"
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        # list-pending com --pretty não é usado nos testes (JSON de 1 linha por padrão)
        try:
            return json.loads(p.stdout)
        except json.JSONDecodeError:
            print("STDOUT:", p.stdout, file=sys.stderr)
            print("STDERR:", p.stderr, file=sys.stderr)
            raise


def flag(log_path: Path, rule_id: str, file_: str, line: int, reason: str) -> None:
    p = run(WRITER, ["--rule-id", rule_id, "--file", file_, "--line", str(line), "--reason", reason, "--log", str(log_path)])
    assert p.returncode == 0, f"flag_suspected_fp.py falhou: {p.stderr}"


def main() -> int:
    if not READER.exists():
        print(f"erro: {READER} não encontrado", file=sys.stderr)
        return 2
    if not WRITER.exists():
        print(f"erro: {WRITER} (E7.3, escritor real) não encontrado", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="fp-suspects-test-") as tmp:
        tmp_path = Path(tmp)

        # ------------------------------------------------------------------
        print("\n[1] Log ausente — list-pending nunca crasha")
        missing_log = tmp_path / "does-not-exist.jsonl"
        r = run_json(READER, ["list-pending", "--log", str(missing_log)])
        check("ok=true com log ausente", r.get("ok") is True, str(r))
        check("pending_count=0 com log ausente", r.get("pending_count") == 0, str(r))
        check("log_exists=false", r.get("log_exists") is False, str(r))

        # ------------------------------------------------------------------
        print("\n[2] Duas suspeitas REAIS (flag_suspected_fp.py de verdade) — ambas aparecem pending")
        log2 = tmp_path / "two-suspects.jsonl"
        flag(log2, "no-import-meta-env", "frontend/src/main.tsx", 10, "Sentry precisa ler import.meta.env antes do React montar")
        flag(log2, "no-console-log", "backend/api/foo.py", 42, "debug temporario do QA")
        r = run_json(READER, ["list-pending", "--log", str(log2)])
        check("pending_count=2", r.get("pending_count") == 2, str(r))
        fps = {p["fingerprint"] for p in r.get("pending", [])}
        check("fingerprint 1 presente", "no-import-meta-env::frontend/src/main.tsx::10" in fps, str(r))
        check("fingerprint 2 presente", "no-console-log::backend/api/foo.py::42" in fps, str(r))
        check("todas com status pending_ratification", all(p.get("status") == "pending_ratification" for p in r.get("pending", [])), str(r))
        check("reason presente e não-vazio em cada uma", all(p.get("reason") for p in r.get("pending", [])), str(r))

        # ------------------------------------------------------------------
        print("\n[3] Dedup por fingerprint — flaguear o MESMO fingerprint 2x não duplica em pending")
        log3 = tmp_path / "dedup.jsonl"
        flag(log3, "no-any-type", "frontend/src/foo.ts", 5, "primeira flag")
        flag(log3, "no-any-type", "frontend/src/foo.ts", 5, "segunda flag do mesmo achado (reforço)")
        r = run_json(READER, ["list-pending", "--log", str(log3)])
        check("unique_fingerprints=1 (2 linhas, 1 fingerprint)", r.get("unique_fingerprints") == 1, str(r))
        check("pending_count=1 (não duplicou)", r.get("pending_count") == 1, str(r))
        check("total_lines_read=2 (as duas linhas foram lidas)", r.get("total_lines_read") == 2, str(r))
        check("reason da entrada em pending é a MAIS RECENTE (segunda flag)", r["pending"][0]["reason"] == "segunda flag do mesmo achado (reforço)", str(r))

        # ------------------------------------------------------------------
        print("\n[4] Linha malformada isolada — não derruba o list-pending, entradas válidas ao redor sobrevivem")
        log4 = tmp_path / "malformed.jsonl"
        flag(log4, "rule-a", "a.py", 1, "motivo a")
        with open(log4, "a", encoding="utf-8") as f:
            f.write("{isto nao e json valido\n")
        flag(log4, "rule-b", "b.py", 2, "motivo b")
        r = run_json(READER, ["list-pending", "--log", str(log4)])
        check("ok=true mesmo com linha malformada", r.get("ok") is True, str(r))
        check("malformed_lines_skipped=1", r.get("malformed_lines_skipped") == 1, str(r))
        check("pending_count=2 (as duas válidas sobreviveram)", r.get("pending_count") == 2, str(r))

        # ------------------------------------------------------------------
        print("\n[5] Ratificação (gesto de OUTRO fluxo, nunca deste leitor) — some de pending, log intacto")
        log5 = tmp_path / "ratification.jsonl"
        flag(log5, "no-console-log", "backend/api/foo.py", 42, "debug temporario do QA")
        flag(log5, "no-import-meta-env", "frontend/src/main.tsx", 10, "Sentry precisa ler import.meta.env")
        lines_before = log5.read_text(encoding="utf-8").splitlines()
        check("2 linhas antes da ratificação", len(lines_before) == 2, str(lines_before))

        # Simula o gesto de ratificação de outro fluxo (dono/oráculo) — uma nova linha
        # append-only com o MESMO fingerprint e status != pending_ratification. Este
        # teste NUNCA usa read_fp_suspects.py para escrever isto (ele não tem nenhum
        # comando de escrita) — é uma escrita direta simulando o fluxo externo.
        import datetime as _dt
        ratification_entry = {
            "timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat(),
            "fingerprint": "no-console-log::backend/api/foo.py::42",
            "rule_id": "no-console-log",
            "file": "backend/api/foo.py",
            "line": 42,
            "reason": "ratificado pelo dono: debug legitimo, removido no commit seguinte",
            "status": "ratified",
        }
        with open(log5, "a", encoding="utf-8") as f:
            f.write(json.dumps(ratification_entry, ensure_ascii=False) + "\n")

        r = run_json(READER, ["list-pending", "--log", str(log5)])
        check("unique_fingerprints=2 (a ratificada continua existindo como fingerprint)", r.get("unique_fingerprints") == 2, str(r))
        check("pending_count=1 (a ratificada saiu da lista de pendentes)", r.get("pending_count") == 1, str(r))
        remaining_fps = {p["fingerprint"] for p in r.get("pending", [])}
        check("fingerprint ratificado NÃO está mais em pending", "no-console-log::backend/api/foo.py::42" not in remaining_fps, str(r))
        check("fingerprint não-ratificado continua em pending", "no-import-meta-env::frontend/src/main.tsx::10" in remaining_fps, str(r))

        lines_after = log5.read_text(encoding="utf-8").splitlines()
        check("3 linhas depois da ratificação (append, nunca reescreveu/apagou)", len(lines_after) == 3, str(lines_after))
        original_pending_lines = [ln for ln in lines_after if "no-console-log::backend/api/foo.py::42" in ln and "pending_ratification" in ln]
        check("linha ORIGINAL pending_ratification do fingerprint ratificado AINDA presente no log (grep)", len(original_pending_lines) == 1, str(lines_after))

        # ------------------------------------------------------------------
        print("\n[6] read_fp_suspects.py NUNCA escreve no log — mtime/conteúdo inalterados após list-pending")
        log6 = tmp_path / "readonly.jsonl"
        flag(log6, "rule-x", "x.py", 1, "motivo x")
        content_before = log6.read_bytes()
        mtime_before = log6.stat().st_mtime_ns
        run(READER, ["list-pending", "--log", str(log6)])
        run(READER, ["list-pending", "--log", str(log6), "--pretty"])
        content_after = log6.read_bytes()
        mtime_after = log6.stat().st_mtime_ns
        check("conteúdo do log byte-a-byte idêntico após 2 chamadas de list-pending", content_before == content_after, "conteúdo mudou")
        check("mtime do log inalterado após list-pending (nenhuma escrita ocorreu)", mtime_before == mtime_after, f"{mtime_before} != {mtime_after}")

    print(f"\n{'='*60}\nPASS: {len(PASS)}  FAIL: {len(FAIL)}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
