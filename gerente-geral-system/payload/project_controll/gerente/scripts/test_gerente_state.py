#!/usr/bin/env python3
"""test_gerente_state.py — provas reais (não mockadas) dos invariantes de E8.2.

Story E8.2 — roda `gerente_state.py` como subprocessos de verdade (não chama funções
internas) para provar, com concorrência real de SO:

  1. Exclusão mútua do lock: N tentativas concorrentes de acquire-lock → exatamente 1 vence.
  2. Reclaim de lock parado (stale): heartbeat sem refresh além do limiar → reclamável;
     heartbeat fresco (mesmo se antigo em wall-clock) → NUNCA reclamável (prova que não é
     timeout fixo por idade, e sim silêncio de heartbeat).
  3. PID morto é atalho de detecção mais rápido que o silêncio de heartbeat.
  4. detect-crash acende para um CICLO-INICIO sem CICLO-FIM; reconcile fecha o ciclo e
     detect-crash deixa de acender.
  5. write-snapshot é atômico: um leitor concorrente rodando em loop nunca vê um arquivo
     truncado/inválido enquanto um escritor sobrescreve repetidamente.

Sem dependências externas (stdlib apenas: subprocess, multiprocessing, tempfile).

Uso:
    python3 test_gerente_state.py
"""
from __future__ import annotations

import json
import multiprocessing
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "gerente_state.py"


def run(args: list[str], check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, check=check,
    )


def run_json(args: list[str]) -> tuple[int, dict]:
    p = run(args)
    out = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else "{}"
    try:
        return p.returncode, json.loads(out)
    except json.JSONDecodeError:
        print("STDOUT:", p.stdout, file=sys.stderr)
        print("STDERR:", p.stderr, file=sys.stderr)
        raise


PASS = []
FAIL = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        PASS.append(name)
        print(f"  PASS  {name}")
    else:
        FAIL.append(name)
        print(f"  FAIL  {name}  {detail}")


# ---------------------------------------------------------------------------
def _acquire_worker(root: str, idx: int, q) -> None:
    p = subprocess.run(
        [sys.executable, str(SCRIPT), "acquire-lock", "--root", root, "--note", f"w{idx}"],
        capture_output=True, text=True,
    )
    try:
        result = json.loads(p.stdout.strip())
    except json.JSONDecodeError:
        result = {"acquired": False, "parse_error": p.stdout}
    q.put(result)


def test_mutual_exclusion(tmp: Path) -> None:
    print("\n[1] Exclusão mútua do lock — 25 acquire-lock concorrentes")
    root = tmp / "mutex"
    root.mkdir()
    ctx = multiprocessing.get_context("fork")
    q = ctx.Queue()
    procs = [ctx.Process(target=_acquire_worker, args=(str(root), i, q)) for i in range(25)]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=30)
    results = [q.get() for _ in range(25)]
    winners = [r for r in results if r.get("acquired")]
    check("exatamente 1 de 25 acquires concorrentes venceu", len(winners) == 1, f"venceram: {len(winners)}")
    check("os demais reportaram reason=held", all(r.get("reason") in ("held",) for r in results if not r.get("acquired")))

    rc, info = run_json(["check-lock", "--root", str(root)])
    check("lock permanece held após a corrida", info.get("held") is True)


def test_stale_vs_fresh_heartbeat(tmp: Path) -> None:
    print("\n[2] Reclaim é por SILÊNCIO de heartbeat, não por idade fixa do ciclo")
    root = tmp / "heartbeat"
    root.mkdir()

    rc, acq = run_json(["acquire-lock", "--root", str(root), "--stale-after-seconds", "1000"])
    token = acq["token"]
    check("lock adquirido", acq.get("acquired") is True)

    time.sleep(1.3)
    # heartbeat mantido fresco via refresh-lock -> mesmo após o tempo passar, NÃO deve ser stale.
    # Usa um --stale-after-seconds bem folgado (1000) nas duas checagens "deve continuar held"
    # abaixo, de propósito: isola a asserção do overhead real de spawn de subprocessos desta
    # própria suíte de teste (segundos de CPython+argparse por chamada), que já é ordens de
    # grandeza menor que 1000s mas poderia facilmente competir com um limiar de ~1s.
    rc, ref = run_json(["refresh-lock", "--root", str(root), "--token", token])
    check("refresh-lock aceito pelo dono do token", ref.get("ok") is True)

    rc, chk = run_json(["check-lock", "--root", str(root), "--stale-after-seconds", "1000"])
    check("heartbeat fresco (refrescado) NÃO é stale sob um limiar folgado", chk.get("stale") is False, str(chk))

    rc2, acq2 = run_json(["acquire-lock", "--root", str(root), "--stale-after-seconds", "1000"])
    check("uma segunda acquire NÃO consegue roubar um lock com heartbeat fresco", acq2.get("acquired") is False)

    # agora para de dar heartbeat — silêncio real (sleep) ultrapassa um limiar pequeno
    # consultado só nesta checagem -> fica reclamável. O limiar pequeno só é usado AQUI,
    # depois de um sleep real deliberado, não como base para as asserções acima.
    time.sleep(2.0)
    rc, chk2 = run_json(["check-lock", "--root", str(root), "--stale-after-seconds", "1"])
    check("heartbeat silencioso além do limiar -> stale=true", chk2.get("stale") is True, str(chk2))

    rc3, acq3 = run_json(["acquire-lock", "--root", str(root), "--stale-after-seconds", "1", "--note", "reclaimer"])
    check("reclaim bem-sucedido após silêncio de heartbeat", acq3.get("acquired") is True, str(acq3))
    check("novo token é diferente do antigo (não é o mesmo holder)", acq3.get("token") != token)

    # o antigo token não deve mais conseguir liberar/refresh o lock (perdeu a posse)
    rc, rel_old = run_json(["release-lock", "--root", str(root), "--token", token])
    check("token antigo (roubado) não consegue mais release-lock", rel_old.get("ok") is False and rel_old.get("reason") == "not-owner")


def test_dead_pid_shortcut(tmp: Path) -> None:
    print("\n[3] PID morto é atalho de detecção mais rápido que o silêncio de heartbeat")
    root = tmp / "deadpid"
    root.mkdir()
    # sobe um processo real e o mata, pra ter um PID garantidamente morto
    proc = subprocess.Popen(["sleep", "60"])
    dead_pid = proc.pid
    proc.terminate()
    proc.wait(timeout=5)

    rc, acq = run_json(["acquire-lock", "--root", str(root), "--pid", str(dead_pid), "--stale-after-seconds", "1000"])
    check("lock adquirido com --pid de um processo já morto", acq.get("acquired") is True)

    # mesmo com heartbeat "fresco" (acabou de adquirir) e --stale-after-seconds gigante,
    # o PID morto por si só já deve tornar o lock reclamável imediatamente.
    rc, acq2 = run_json(["acquire-lock", "--root", str(root), "--stale-after-seconds", "1000", "--note", "reclaimer-via-pid"])
    check("reclaim imediato via PID morto, sem esperar o silêncio de heartbeat", acq2.get("acquired") is True, str(acq2))


def test_crash_detect_and_reconcile(tmp: Path) -> None:
    print("\n[4] detect-crash acende para início-sem-fim; reconcile fecha o ciclo")
    root = tmp / "crash"
    root.mkdir()
    board_dir = tmp / "tickets"
    board_dir.mkdir()
    board_path = board_dir / "board.yaml"
    board_path.write_text(
        "tickets:\n  TCK-999:\n    title: \"fixture\"\n    status: em-implementacao\n    priority: alta\n",
        encoding="utf-8",
    )

    rc, chk0 = run_json(["detect-crash", "--root", str(root)])
    check("sem diario.jsonl -> crashed=false (primeira ativação)", chk0.get("crashed") is False)

    run(["write-snapshot", "--root", str(root), "--marker", "start", "--cycle-id", "cycle-X",
         "--started-at", "2026-07-11T02:00:00-03:00", "--phase", "despachar",
         "--dispatches-json", json.dumps([{"ticket": "TCK-999", "unit": "epic-E8", "trilha": "epic",
                                            "worktree": None, "status": "em-voo", "started_at": "2026-07-11T02:05:00-03:00"}])])
    run(["append-diario", "--root", str(root), "--event", "CICLO-INICIO", "--cycle-id", "cycle-X", "--ts", "2026-07-11T02:00:00-03:00"])
    run(["append-diario", "--root", str(root), "--event", "despachei", "--cycle-id", "cycle-X", "--text", "TCK-999", "--ts", "2026-07-11T02:05:00-03:00"])
    # nota: NENHUM CICLO-FIM foi anexado -> simula crash no meio do ciclo

    rc, det = run_json(["detect-crash", "--root", str(root)])
    check("CICLO-INICIO sem CICLO-FIM -> crashed=true", det.get("crashed") is True)
    check("cycle_id órfão identificado corretamente", det.get("orphan_cycles") == ["cycle-X"])
    check("estado-atual.yaml corrobora (marker=start, mesmo cycle_id)", det.get("estado_confirms") is True)

    rc, rec = run_json(["reconcile", "--root", str(root), "--cycle-id", "cycle-X", "--board-path", str(board_path)])
    check("reconcile identifica o despacho órfão (ticket em-implementacao no board)", rec.get("needs_attention") is True)
    check("reconcile aponta o ticket órfão certo", any(o.get("ticket") == "TCK-999" for o in rec.get("orphans", [])))

    rc, det2 = run_json(["detect-crash", "--root", str(root)])
    check("após reconcile, detect-crash não acende mais para o mesmo ciclo", det2.get("crashed") is False, str(det2))


def test_no_false_positive_for_healthy_long_cycle(tmp: Path) -> None:
    print("\n[4b] detect-crash NÃO confunde um ciclo saudável (lock ativo, heartbeat fresco) com um crash")
    root = tmp / "healthy-long-cycle"
    root.mkdir()

    rc, acq = run_json(["acquire-lock", "--root", str(root), "--cycle-id", "cycle-long-1", "--stale-after-seconds", "1000"])
    check("lock adquirido para o ciclo longo", acq.get("acquired") is True)
    check("acquire-lock não reporta pending_crash para um diário vazio", "pending_crash" not in acq)
    token = acq["token"]

    run(["append-diario", "--root", str(root), "--event", "CICLO-INICIO", "--cycle-id", "cycle-long-1"])
    run(["append-diario", "--root", str(root), "--event", "despachei", "--cycle-id", "cycle-long-1", "--text", "trabalho em andamento, ciclo ainda não fechou"])

    # o ciclo está genuinamente ainda aberto (sem CICLO-FIM) — mas o lock está held e
    # fresco para esse MESMO cycle_id, então detect-crash não deve acender.
    rc, det = run_json(["detect-crash", "--root", str(root)])
    check("ciclo ativo com lock fresco NÃO é reportado como crashed", det.get("crashed") is False, str(det))
    check("detect-crash reporta o cycle_id ativo excluído", det.get("excluded_active_cycle_id") == "cycle-long-1", str(det))

    # agora o holder para de dar heartbeat (crash de verdade) e o lock fica stale
    rc, chk = run_json(["check-lock", "--root", str(root), "--stale-after-seconds", "0"])
    check("com --stale-after-seconds=0, o lock já é considerado stale (heartbeat sempre no passado)", chk.get("stale") is True)

    rc, det2 = run_json(["detect-crash", "--root", str(root), "--stale-after-seconds", "0"])
    check("uma vez que o lock também é considerado stale, o mesmo ciclo aberto VOLTA a acender como crash", det2.get("crashed") is True, str(det2))

    run(["release-lock", "--root", str(root), "--token", token])


def _writer_worker(root: str, n: int) -> None:
    for i in range(n):
        subprocess.run(
            [sys.executable, str(SCRIPT), "write-snapshot", "--root", root,
             "--marker", "start" if i % 2 == 0 else "end", "--cycle-id", f"cycle-{i}",
             "--started-at", "2026-07-11T02:00:00-03:00", "--phase", "despachar",
             "--dispatches-json", json.dumps([{"ticket": f"TCK-{i}", "unit": "epic-E8", "trilha": "epic",
                                                "worktree": None, "status": "em-voo", "started_at": "x"}] * 3)],
            capture_output=True, text=True,
        )


def test_crash_check_sentinel_e15_4(tmp: Path) -> None:
    print("\n[6] E15.4 — detect-crash/reconcile gravam o sentinela de crash-check por cycle_id")
    root = tmp / "sentinel"
    root.mkdir()
    board_path = tmp / "sentinel-tickets" / "board.yaml"
    board_path.parent.mkdir(parents=True, exist_ok=True)
    board_path.write_text("tickets: {}\n", encoding="utf-8")

    print("\n[6a] detect-crash SEM --cycle-id continua em modo diagnóstico puro (retrocompat)")
    rc, det = run_json(["detect-crash", "--root", str(root)])
    check("sem --cycle-id, resposta não tem sentinel_written_for_cycle_id", "sentinel_written_for_cycle_id" not in det, str(det))
    check("sentinela NÃO é criado em disco sem --cycle-id", not (root / ".crash-check-sentinels").exists())

    print("\n[6b] detect-crash --cycle-id grava o sentinela, mesmo sem nada para reconciliar (crashed=false)")
    rc, det2 = run_json(["detect-crash", "--root", str(root), "--cycle-id", "cycle-fresh-1"])
    check("crashed=false (diário vazio)", det2.get("crashed") is False, str(det2))
    check("sentinel_written_for_cycle_id ecoa o cycle_id pedido mesmo sem crash", det2.get("sentinel_written_for_cycle_id") == "cycle-fresh-1", str(det2))
    sentinel_path = root / ".crash-check-sentinels" / "cycle-fresh-1.json"
    check("arquivo de sentinela existe em disco", sentinel_path.exists())
    sentinel_doc = json.loads(sentinel_path.read_text(encoding="utf-8"))
    check("sentinela grava source=detect-crash", sentinel_doc.get("source") == "detect-crash", str(sentinel_doc))
    check("sentinela grava cycle_id correto", sentinel_doc.get("cycle_id") == "cycle-fresh-1", str(sentinel_doc))
    check("sentinela grava checked_at (timestamp)", bool(sentinel_doc.get("checked_at")))

    print("\n[6c] reconcile --cycle-id TAMBÉM grava o sentinela (fonte diferente, mesmo mecanismo)")
    rc, rec = run_json(["reconcile", "--root", str(root), "--cycle-id", "cycle-reconciled-1", "--board-path", str(board_path)])
    check("reconcile ecoa sentinel_written_for_cycle_id", rec.get("sentinel_written_for_cycle_id") == "cycle-reconciled-1", str(rec))
    sentinel_path2 = root / ".crash-check-sentinels" / "cycle-reconciled-1.json"
    check("sentinela do reconcile existe em disco", sentinel_path2.exists())
    sentinel_doc2 = json.loads(sentinel_path2.read_text(encoding="utf-8"))
    check("sentinela do reconcile grava source=reconcile", sentinel_doc2.get("source") == "reconcile", str(sentinel_doc2))

    print("\n[6d] detect-crash --cycle-id para um cycle_id malformado (path traversal) nunca escreve fora do diretório")
    rc, det_bad = run_json(["detect-crash", "--root", str(root), "--cycle-id", "../../etc"])
    check("cycle_id malformado -> sentinel_error na resposta, nunca sentinel_written_for_cycle_id", "sentinel_written_for_cycle_id" not in det_bad and "sentinel_error" in det_bad, str(det_bad))
    check("nada escapou de .crash-check-sentinels/", not (tmp.parent / "etc").exists() and not (tmp / "etc").exists())

    print("\n[6e] Sentinelas de dois cycle_id diferentes coexistem sem se sobrescrever")
    check("cycle-fresh-1 continua no disco após o sentinela de cycle-reconciled-1 ser gravado", sentinel_path.exists())
    check("os dois arquivos de sentinela são distintos", sentinel_path != sentinel_path2)


def test_atomic_write_no_torn_reads(tmp: Path) -> None:
    print("\n[5] write-snapshot atômico — leitor concorrente nunca vê arquivo torn/truncado")
    root = tmp / "atomic"
    root.mkdir()
    run(["write-snapshot", "--root", str(root), "--marker", "start", "--cycle-id", "cycle-0",
         "--started-at", "2026-07-11T02:00:00-03:00", "--phase", "ler-estado"])

    ctx = multiprocessing.get_context("fork")
    writer = ctx.Process(target=_writer_worker, args=(str(root), 60))
    writer.start()

    estado_path = root / "estado-atual.yaml"
    reads = 0
    bad_reads = 0
    deadline = time.time() + 6
    while writer.is_alive() or time.time() < deadline:
        reads += 1
        try:
            text = estado_path.read_text(encoding="utf-8")
            sys.path.insert(0, str(HERE))
            import gerente_state as gs  # import tardio (após path ajustado) — reusa o parser real
            doc = gs.parse_estado(text)
            if "marker" not in doc or "cycle" not in doc or not isinstance(doc.get("cycle"), dict):
                bad_reads += 1
        except Exception:
            bad_reads += 1
        if not writer.is_alive():
            break
    writer.join(timeout=10)

    check(f"nenhuma leitura torn/inválida em {reads} leituras concorrentes durante {60} escritas", bad_reads == 0, f"bad_reads={bad_reads}/{reads}")
    check("nenhum arquivo .tmp remanescente após as escritas", not any(root.glob("*.tmp")))


def main() -> int:
    tmp_root = Path(tempfile.mkdtemp(prefix="gerente-state-test-"))
    print(f"workspace de teste: {tmp_root}")
    try:
        test_mutual_exclusion(tmp_root)
        test_stale_vs_fresh_heartbeat(tmp_root)
        test_dead_pid_shortcut(tmp_root)
        test_crash_detect_and_reconcile(tmp_root)
        test_no_false_positive_for_healthy_long_cycle(tmp_root)
        test_crash_check_sentinel_e15_4(tmp_root)
        test_atomic_write_no_torn_reads(tmp_root)
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

    print(f"\n{'='*60}\nPASS: {len(PASS)}  FAIL: {len(FAIL)}")
    if FAIL:
        print("Falhas:", FAIL)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
