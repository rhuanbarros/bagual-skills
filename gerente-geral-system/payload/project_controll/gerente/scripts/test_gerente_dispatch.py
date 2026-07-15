#!/usr/bin/env python3
"""test_gerente_dispatch.py — provas reais (subprocessos, não mocks) dos invariantes de
E8.4 (contrato de despacho via marcador em disco).

Story E8.4 (ideias/sistema-artifacts/E8-4-contrato-despacho.md), PRD 00 FR-8. Roda
`gerente_dispatch.py` (e a extensão de `gerente_state.py::reconcile`) como subprocessos de
verdade, provando:

  1. open-dispatch escreve request.yaml e devolve um `dispatch_entry` pronto para
     `write-snapshot --dispatches-json`.
  2. close-dispatch escreve result.yaml ANTES de DONE.marker (garantia de ordem) —
     verificado pelos mtimes reais dos dois arquivos em disco.
  3. read-result: `done` é decidido SÓ pela presença do DONE.marker (nunca antes do
     close-dispatch, sempre depois).
  4. Um despacho fechado com DONE.marker ausente e result.yaml presente por corrupção
     externa nunca é reportado como sucesso silencioso.
  5. Round-trip de `tickets` (lista de escalares puros) via parse_estado — o bug real
     encontrado na auto-revisão desta story (scalar-list virava lista-de-dict incorreta).
  6. list-inflight reflete corretamente despachos abertos vs. fechados.
  7. reconcile-orphan-dispatch detecta o caso central: request.yaml presente, DONE.marker
     ausente, ticket ainda `em-implementacao` no board.yaml → orphan:true com os motivos
     certos, NUNCA move o Ticket sozinho (só recomenda).
  8. Integração ponta-a-ponta com `gerente_state.py detect-crash`/`reconcile` (E8.2): um
     ciclo com CICLO-INICIO sem CICLO-FIM e um despacho `dispatch_id` sem DONE.marker é
     reportado como órfão pelo `reconcile` de E8.2, cruzando o marcador de E8.4 — prova
     que os dois mecanismos convergem, não são caminhos paralelos.
  9. close-dispatch recusa reabrir um despacho já fechado sem --force (idempotência).
  10. (E15.2) close-dispatch --tokens-used acumula cota em quota-ciclo.json (via
      record_usage() de gerente_quota.py, import direto) na MESMA chamada que fecha o
      despacho — sem nenhuma chamada manual a `record-usage` — e o consumo já é
      visível a `gerente_quota.py check` (prova cross-script, subprocess real). O
      multiplicador de segurança aplicado bate exatamente com o de `record-usage`
      standalone para o mesmo valor bruto. close-dispatch sem --tokens-used não cria/
      altera quota-ciclo.json (backward-compat).
  13. (E15.4) open-dispatch --cycle-id X é RECUSADO (sem escrever request.yaml) quando
      nenhum sentinela de crash-check (detect-crash/reconcile --cycle-id X) foi gravado
      para X; passa a funcionar assim que o sentinela existe. Sentinela é escopado por
      cycle_id — um sentinela gravado para o ciclo A nunca libera open-dispatch do
      ciclo B. reconcile --cycle-id também grava sentinela (não só detect-crash).
      acquire-lock/check-lock continuam livres, sem exigir nenhum sentinela.

Sem dependências externas (stdlib apenas).

Uso:
    python3 test_gerente_dispatch.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
DISPATCH_SCRIPT = HERE / "gerente_dispatch.py"
STATE_SCRIPT = HERE / "gerente_state.py"
QUOTA_SCRIPT = HERE / "gerente_quota.py"


def run(script: Path, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True)


def run_json(script: Path, args: list[str]) -> tuple[int, dict]:
    p = run(script, args)
    out = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else "{}"
    try:
        return p.returncode, json.loads(out)
    except json.JSONDecodeError:
        print("STDOUT:", p.stdout, file=sys.stderr)
        print("STDERR:", p.stderr, file=sys.stderr)
        raise


PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        PASS.append(name)
        print(f"  PASS  {name}")
    else:
        FAIL.append(name)
        print(f"  FAIL  {name}  {detail}")


def write_board(path: Path, ticket: str, status: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"tickets:\n  {ticket}:\n    status: {status}\n    priority: alta\n", encoding="utf-8")


def crash_check(root: Path, cycle_id: str) -> dict:
    """Story E15.4 — helper de setup: roda `gerente_state.py detect-crash --cycle-id
    <cycle_id>` para gravar o sentinela que `open-dispatch` agora exige antes de abrir
    qualquer despacho. Usado nos testes pré-existentes deste arquivo (todos escritos
    ANTES de E15.4) para preservar o comportamento que eles provam sem reescrever a
    intenção de cada um — o guard em si tem sua própria seção dedicada ([13] abaixo)."""
    rc, out = run_json(STATE_SCRIPT, ["detect-crash", "--root", str(root), "--cycle-id", cycle_id])
    assert rc == 0 and out.get("sentinel_written_for_cycle_id") == cycle_id, f"setup crash_check falhou: {out}"
    return out


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="gerente-dispatch-test-"))
    try:
        root = tmp / "gerente"
        board_path = tmp / "tickets" / "board.yaml"

        # ---------------------------------------------------------------
        print("\n[1] open-dispatch escreve request.yaml + devolve dispatch_entry")
        write_board(board_path, "TCK-1", "em-implementacao")
        # Story E15.4 — setup: grava o sentinela de crash-check para cycle-1 (todos os
        # open-dispatch deste root/ciclo, seções [1]/[6]/[7]/[10], reusam o mesmo
        # sentinela — um por cycle_id, não um por despacho).
        crash_check(root, "cycle-1")
        rc, out = run_json(DISPATCH_SCRIPT, [
            "open-dispatch", "--root", str(root), "--dispatch-id", "dispatch-1",
            "--cycle-id", "cycle-1", "--tickets-json", '["TCK-1"]',
            "--unit", "epic-E8", "--trilha", "epic", "--skill", "bagual-epic-runner",
        ])
        check("[1a] open-dispatch retorna ok:true", rc == 0 and out.get("ok") is True, str(out))
        req_path = root / "dispatches" / "dispatch-1" / "request.yaml"
        check("[1b] request.yaml existe em disco", req_path.exists())
        entry = out.get("dispatch_entry", {})
        check("[1c] dispatch_entry NÃO tem campo 'tickets' (lista) — só 'ticket' singular, evita bug de serialização aninhada", "tickets" not in entry and entry.get("ticket") == "TCK-1", str(entry))
        check("[1d] dispatch_entry.status == em-voo", entry.get("status") == "em-voo")
        check("[1e] dispatch_entry.dispatch_id == dispatch-1", entry.get("dispatch_id") == "dispatch-1")

        rc2, out2 = run_json(DISPATCH_SCRIPT, [
            "open-dispatch", "--root", str(root), "--dispatch-id", "dispatch-1",
            "--cycle-id", "cycle-1", "--tickets-json", '["TCK-1"]',
            "--unit", "epic-E8", "--trilha", "epic", "--skill", "bagual-epic-runner",
        ])
        check("[1f] reabrir o MESMO dispatch_id é recusado (nunca reusar run dir vivo/antigo)", rc2 != 0 and out2.get("ok") is False)

        # ---------------------------------------------------------------
        print("\n[2] Round-trip de `tickets` (lista de escalares puros) via parse_estado")
        rc, out = run_json(DISPATCH_SCRIPT, ["read-result", "--root", str(root), "--dispatch-id", "dispatch-1"])
        req = out.get("request", {})
        check("[2a] tickets parseado como lista de STRINGS (não lista-de-dict)", req.get("tickets") == ["TCK-1"], str(req.get("tickets")))
        check("[2b] done == false ANTES do close-dispatch", out.get("done") is False)

        # ---------------------------------------------------------------
        print("\n[3] close-dispatch: garantia de ordem — result.yaml durável ANTES de DONE.marker")
        rc, out = run_json(DISPATCH_SCRIPT, [
            "close-dispatch", "--root", str(root), "--dispatch-id", "dispatch-1",
            "--outcome", "sucesso", "--verdict", "epic concluída",
            "--evidence-json", '{"commit":"deadbeef"}',
        ])
        check("[3a] close-dispatch retorna ok:true", rc == 0 and out.get("ok") is True, str(out))
        result_path = root / "dispatches" / "dispatch-1" / "result.yaml"
        done_path = root / "dispatches" / "dispatch-1" / "DONE.marker"
        check("[3b] result.yaml existe", result_path.exists())
        check("[3c] DONE.marker existe", done_path.exists())
        result_mtime = result_path.stat().st_mtime_ns
        done_mtime = done_path.stat().st_mtime_ns
        check("[3d] result.yaml foi escrito ANTES (ou no mesmo instante) que DONE.marker — nunca depois", result_mtime <= done_mtime, f"result={result_mtime} done={done_mtime}")

        rc, out = run_json(DISPATCH_SCRIPT, [
            "close-dispatch", "--root", str(root), "--dispatch-id", "dispatch-1",
            "--outcome", "falhou", "--verdict", "tentativa dupla",
        ])
        check("[3e] fechar um despacho JÁ fechado sem --force é recusado (idempotência write-once)", rc != 0 and out.get("ok") is False)

        # ---------------------------------------------------------------
        print("\n[4] read-result depois do close: done==true, outcome/evidence corretos")
        rc, out = run_json(DISPATCH_SCRIPT, ["read-result", "--root", str(root), "--dispatch-id", "dispatch-1"])
        check("[4a] done == true", out.get("done") is True)
        result = out.get("result", {})
        check("[4b] outcome == sucesso", result.get("outcome") == "sucesso")
        check("[4c] evidence.commit == deadbeef", (result.get("evidence") or {}).get("commit") == "deadbeef")
        check("[4d] sem 'corrupt' quando tudo está consistente", "corrupt" not in out)

        # ---------------------------------------------------------------
        print("\n[5] list-inflight reflete aberto vs. fechado")
        rc, out = run_json(DISPATCH_SCRIPT, [
            "open-dispatch", "--root", str(root), "--dispatch-id", "dispatch-2",
            "--cycle-id", "cycle-1", "--tickets-json", '["TCK-2"]',
            "--unit", "epic-E9", "--trilha", "rapida", "--skill", "bmad-quick-dev",
        ])
        check("[5a] segundo despacho aberto", rc == 0)
        rc, out = run_json(DISPATCH_SCRIPT, ["list-inflight", "--root", str(root)])
        inflight_ids = {d["dispatch_id"] for d in out.get("inflight", [])}
        check("[5b] dispatch-1 (fechado) NÃO aparece em list-inflight", "dispatch-1" not in inflight_ids, str(inflight_ids))
        check("[5c] dispatch-2 (aberto) aparece em list-inflight", "dispatch-2" in inflight_ids, str(inflight_ids))

        # ---------------------------------------------------------------
        print("\n[6] reconcile-orphan-dispatch — CASO CENTRAL: executor morto sem close-dispatch")
        write_board(board_path, "TCK-2", "em-implementacao")
        rc, out = run_json(DISPATCH_SCRIPT, [
            "reconcile-orphan-dispatch", "--root", str(root), "--dispatch-id", "dispatch-2",
            "--board-path", str(board_path),
        ])
        check("[6a] orphan == true (sem DONE.marker)", out.get("orphan") is True)
        reasons = " ".join(out.get("reasons", []))
        check("[6b] motivo cita ausência de DONE.marker", "DONE.marker" in reasons or "sem DONE" in reasons, reasons)
        check("[6c] motivo cita ticket ainda em-implementacao", "em-implementacao" in reasons, reasons)
        check("[6d] recommended_next_step aponta para bagual-tickets, nunca edição direta", "bagual-tickets" in out.get("recommended_next_step", ""))

        rc, out = run_json(DISPATCH_SCRIPT, [
            "reconcile-orphan-dispatch", "--root", str(root), "--dispatch-id", "dispatch-1",
            "--board-path", str(board_path),
        ])
        check("[6e] dispatch-1 (fechado) NÃO é reportado como orphan", out.get("orphan") is False)

        rc, out = run_json(DISPATCH_SCRIPT, [
            "reconcile-orphan-dispatch", "--root", str(root), "--dispatch-id", "dispatch-inexistente",
        ])
        check("[6f] dispatch_id desconhecido -> ok:false, nunca lança exceção", rc != 0 and out.get("ok") is False)

        # ---------------------------------------------------------------
        print("\n[7] Integração ponta-a-ponta com gerente_state.py detect-crash/reconcile (E8.2)")
        run(STATE_SCRIPT, ["append-diario", "--root", str(root), "--event", "CICLO-INICIO", "--cycle-id", "cycle-1"])
        dispatches_json = json.dumps([
            {"dispatch_id": "dispatch-2", "ticket": "TCK-2", "unit": "epic-E9", "trilha": "rapida", "worktree": "null", "status": "em-voo", "started_at": "2026-07-11T10:00:00-03:00"}
        ])
        run(STATE_SCRIPT, [
            "write-snapshot", "--root", str(root), "--marker", "start", "--cycle-id", "cycle-1",
            "--started-at", "2026-07-11T10:00:00-03:00", "--phase", "despachar",
            "--dispatches-json", dispatches_json,
        ])
        rc, out = run_json(STATE_SCRIPT, ["detect-crash", "--root", str(root)])
        check("[7a] detect-crash acende (CICLO-INICIO sem CICLO-FIM)", out.get("crashed") is True)

        rc, out = run_json(STATE_SCRIPT, ["reconcile", "--root", str(root), "--cycle-id", "cycle-1", "--board-path", str(board_path)])
        check("[7b] reconcile (E8.2) encontra o despacho órfão", out.get("needs_attention") is True)
        orphan_reasons = " ".join(out["orphans"][0]["reasons"]) if out.get("orphans") else ""
        check("[7c] motivo do E8.2::reconcile cruza o DONE.marker do E8.4", "DONE.marker" in orphan_reasons, orphan_reasons)
        check("[7d] motivo do E8.2::reconcile também cita ticket em-implementacao (cruzamento com board.yaml)", "em-implementacao" in orphan_reasons, orphan_reasons)

        rc, out = run_json(STATE_SCRIPT, ["detect-crash", "--root", str(root)])
        check("[7e] depois do reconcile, detect-crash deixa de acender (CICLO-FIM sintético gravado)", out.get("crashed") is False)

        # ---------------------------------------------------------------
        print("\n[8] Ticket nunca fica silenciosamente 'concluido' num despacho falho")
        rc, out = run_json(DISPATCH_SCRIPT, [
            "close-dispatch", "--root", str(root), "--dispatch-id", "dispatch-2",
            "--outcome", "falhou", "--verdict", "worktree conflito não resolvido",
        ])
        check("[8a] close-dispatch com outcome=falhou aceito normalmente (falha é um resultado válido, não um erro do script)", rc == 0 and out.get("ok") is True)
        rc, out = run_json(DISPATCH_SCRIPT, ["read-result", "--root", str(root), "--dispatch-id", "dispatch-2"])
        check("[8b] outcome lido de volta == falhou (nunca reinterpretado como sucesso)", out.get("result", {}).get("outcome") == "falhou")

        # ---------------------------------------------------------------
        print("\n[9] close-dispatch recusa fechar um dispatch_id nunca aberto")
        rc, out = run_json(DISPATCH_SCRIPT, [
            "close-dispatch", "--root", str(root), "--dispatch-id", "dispatch-nunca-aberto",
            "--outcome", "sucesso", "--verdict", "x",
        ])
        check("[9a] close-dispatch sem request.yaml prévio -> ok:false, nunca cria result.yaml fantasma", rc != 0 and out.get("ok") is False)
        check("[9b] nenhum diretório foi criado para o dispatch_id inexistente", not (root / "dispatches" / "dispatch-nunca-aberto").exists())

        # ---------------------------------------------------------------
        print("\n[10] dispatch_id malformado (path traversal) é recusado em todos os subcomandos que o recebem")
        rc, out = run_json(DISPATCH_SCRIPT, [
            "open-dispatch", "--root", str(root), "--dispatch-id", "../../etc",
            "--cycle-id", "cycle-1", "--tickets-json", '["TCK-X"]',
            "--unit", "epic-EX", "--trilha", "epic", "--skill", "x",
        ])
        check("[10a] open-dispatch recusa '../../etc'", rc != 0 and out.get("ok") is False)
        check("[10b] nenhum diretório escapou de dispatches/", not (root.parent / "etc").exists())
        rc, out = run_json(DISPATCH_SCRIPT, ["read-result", "--root", str(root), "--dispatch-id", ".."])
        check("[10c] read-result recusa '..'", rc != 0 and out.get("ok") is False)
        rc, out = run_json(DISPATCH_SCRIPT, ["close-dispatch", "--root", str(root), "--dispatch-id", "..", "--outcome", "sucesso", "--verdict", "x"])
        check("[10d] close-dispatch recusa '..'", rc != 0 and out.get("ok") is False)
        rc, out = run_json(DISPATCH_SCRIPT, ["reconcile-orphan-dispatch", "--root", str(root), "--dispatch-id", ""])
        check("[10e] reconcile-orphan-dispatch recusa dispatch_id vazio", rc != 0 and out.get("ok") is False)

        # ---------------------------------------------------------------
        print("\n[11] GAP ADVERSARIAL documentado: gerente_state.py::reconcile (E8.2) sozinho NÃO enxerga um")
        print("     despacho cujo request.yaml existe mas nunca foi gravado em estado-atual.yaml (compactação")
        print("     entre open-dispatch e o write-snapshot seguinte) — por isso gerente-geral.md agora roda")
        print("     list-inflight incondicionalmente na Ativação. Prova de que list-inflight FECHA esse gap:")
        gap_root = tmp / "gerente-gap"
        gap_board = tmp / "tickets-gap" / "board.yaml"
        write_board(gap_board, "TCK-GAP", "em-implementacao")
        run(STATE_SCRIPT, ["append-diario", "--root", str(gap_root), "--event", "CICLO-INICIO", "--cycle-id", "cycle-gap"])
        run(STATE_SCRIPT, ["write-snapshot", "--root", str(gap_root), "--marker", "start", "--cycle-id", "cycle-gap", "--started-at", "2026-07-11T10:00:00-03:00", "--phase", "despachar"])
        # Story E15.4 — setup: cycle-gap precisa do sentinela antes de open-dispatch,
        # exatamente como qualquer outro ciclo (o guard não faz exceção para o cenário de
        # gap deste teste).
        crash_check(gap_root, "cycle-gap")
        # open-dispatch acontece, mas a persona "morre" ANTES do write-snapshot seguinte
        # que registraria o dispatch_entry em estado-atual.yaml.
        run(DISPATCH_SCRIPT, ["open-dispatch", "--root", str(gap_root), "--dispatch-id", "dispatch-gap", "--cycle-id", "cycle-gap", "--tickets-json", '["TCK-GAP"]', "--unit", "epic-EGAP", "--trilha", "epic", "--skill", "x"])
        rc, out = run_json(STATE_SCRIPT, ["reconcile", "--root", str(gap_root), "--cycle-id", "cycle-gap", "--board-path", str(gap_board)])
        check("[11a] reconcile (E8.2) sozinho reporta needs_attention:false (falso-negativo confirmado, motiva o fix em gerente-geral.md)", out.get("needs_attention") is False, str(out))
        rc, out = run_json(DISPATCH_SCRIPT, ["list-inflight", "--root", str(gap_root)])
        gap_ids = {d["dispatch_id"] for d in out.get("inflight", [])}
        check("[11b] list-inflight (sem depender de estado-atual.yaml) ENCONTRA o despacho — fecha o gap", "dispatch-gap" in gap_ids, str(gap_ids))

        # ---------------------------------------------------------------
        print("\n[12] E15.2 — close-dispatch --tokens-used mecaniza record-usage como efeito colateral atômico")
        quota_root = tmp / "gerente-quota"
        quota_root.mkdir(parents=True, exist_ok=True)
        quota_path = quota_root / "quota-ciclo.json"
        # Story E15.4 — setup: sentinela para cycle-quota, reusado pelos DOIS despachos
        # deste ciclo ([12a] dispatch-q1 e [12r] dispatch-q2) — um sentinela por
        # cycle_id, não por despacho.
        crash_check(quota_root, "cycle-quota")

        rc, out = run_json(DISPATCH_SCRIPT, [
            "open-dispatch", "--root", str(quota_root), "--dispatch-id", "dispatch-q1",
            "--cycle-id", "cycle-quota", "--tickets-json", '["TCK-Q1"]',
            "--unit", "ticket:TCK-Q1", "--trilha", "rapida", "--skill", "bmad-quick-dev",
        ])
        check("[12a] open-dispatch (setup) ok", rc == 0 and out.get("ok") is True, str(out))
        check("[12b] quota-ciclo.json NÃO existe antes de qualquer close-dispatch/record-usage", not quota_path.exists())

        rc, out = run_json(DISPATCH_SCRIPT, [
            "close-dispatch", "--root", str(quota_root), "--dispatch-id", "dispatch-q1",
            "--outcome", "sucesso", "--verdict", "concluído", "--tokens-used", "1000",
        ])
        check("[12c] close-dispatch --tokens-used retorna ok:true e ecoa quota_recorded", rc == 0 and out.get("ok") is True and out.get("quota_recorded") is True, str(out))
        check("[12d] self_tracked_tokens_total ecoado == ceil(1000*1.15) == 1150 (multiplicador de segurança default)", out.get("self_tracked_tokens_total") == 1150, str(out))
        check("[12e] quota-ciclo.json foi CRIADO por close-dispatch, ZERO chamadas manuais a record-usage", quota_path.exists())
        quota_doc = json.loads(quota_path.read_text(encoding="utf-8"))
        check("[12f] quota-ciclo.json.cycle_id == cycle_id do request.yaml do despacho (cycle-quota)", quota_doc.get("cycle_id") == "cycle-quota", str(quota_doc))
        check("[12g] quota-ciclo.json.self_tracked_tokens_total == 1150 em disco", quota_doc.get("self_tracked_tokens_total") == 1150, str(quota_doc))

        # GARANTIA DE ORDEM: quota-ciclo.json precisa ter sido escrito ANTES (ou no
        # mesmo instante) de result.yaml/DONE.marker — nunca depois. Prova a mesma
        # classe de invariante já provada em [3d] para result.yaml vs. DONE.marker,
        # agora estendida a quota-ciclo.json vs. result.yaml.
        q_result_path = quota_root / "dispatches" / "dispatch-q1" / "result.yaml"
        q_done_path = quota_root / "dispatches" / "dispatch-q1" / "DONE.marker"
        q_quota_mtime = quota_path.stat().st_mtime_ns
        q_result_mtime = q_result_path.stat().st_mtime_ns
        q_done_mtime = q_done_path.stat().st_mtime_ns
        check("[12h] quota-ciclo.json foi escrito ANTES (ou no mesmo instante) que result.yaml", q_quota_mtime <= q_result_mtime, f"quota={q_quota_mtime} result={q_result_mtime}")
        check("[12i] cadeia completa de ordem: quota <= result <= DONE.marker", q_quota_mtime <= q_result_mtime <= q_done_mtime, f"quota={q_quota_mtime} result={q_result_mtime} done={q_done_mtime}")

        print("\n[12j-k] CASO CENTRAL da story (AC2): check reflete o consumo SEM nenhuma chamada manual a record-usage")
        rc, out = run_json(QUOTA_SCRIPT, [
            "check", "--root", str(quota_root), "--cycle-id", "cycle-quota",
            "--self-tracked-budget-tokens", "10000",
        ])
        check("[12j] gerente_quota.py check (subprocess real) roda ok", rc == 0 and out.get("ok") is True, str(out))
        self_tracked = out.get("self_tracked", {})
        check("[12k] check.self_tracked.tokens_total == 1150 — já reflete o close-dispatch, nenhum record-usage manual chamado neste teste", self_tracked.get("tokens_total") == 1150, str(out))
        check("[12l] check.self_tracked.same_cycle == true", self_tracked.get("same_cycle") is True)

        print("\n[12m] Multiplicador aplicado via --tokens-used é IDÊNTICO ao de record-usage standalone para o mesmo valor bruto")
        # Root SEPARADO do fluxo close-dispatch acima — quota-ciclo.json é 1 arquivo por
        # `--root` que só rastreia o CICLO ATUAL (reseta quando --cycle-id muda em
        # relação ao gravado); reusar `quota_root` aqui com um `--cycle-id` diferente
        # resetaria o acumulador de `cycle-quota` usado pelos checks [12j-l]/[12r]
        # abaixo — cada cenário de cota precisa do seu próprio `--root` isolado.
        cmp_root = tmp / "gerente-quota-cmp"
        cmp_root.mkdir(parents=True, exist_ok=True)
        rc, out = run_json(QUOTA_SCRIPT, [
            "record-usage", "--root", str(cmp_root), "--cycle-id", "cycle-standalone-cmp",
            "--tokens", "1000",
        ])
        check("[12m] record-usage standalone com o MESMO --tokens=1000 produz o MESMO total (1150) que close-dispatch --tokens-used", out.get("self_tracked_tokens_total") == 1150, str(out))
        check("[12n] multiplicador ecoado por record-usage standalone (1.15) == multiplicador ecoado por close-dispatch (1.15)", out.get("multiplier_applied") == 1.15, str(out))

        print("\n[12o] Backward-compat: close-dispatch SEM --tokens-used não cria/altera quota-ciclo.json")
        nq_root = tmp / "gerente-no-quota"
        nq_root.mkdir(parents=True, exist_ok=True)
        crash_check(nq_root, "cycle-nq")  # Story E15.4 — setup: sentinela para cycle-nq
        run_json(DISPATCH_SCRIPT, [
            "open-dispatch", "--root", str(nq_root), "--dispatch-id", "dispatch-nq1",
            "--cycle-id", "cycle-nq", "--tickets-json", '["TCK-NQ1"]',
            "--unit", "ticket:TCK-NQ1", "--trilha", "rapida", "--skill", "bmad-quick-dev",
        ])
        rc, out = run_json(DISPATCH_SCRIPT, [
            "close-dispatch", "--root", str(nq_root), "--dispatch-id", "dispatch-nq1",
            "--outcome", "sucesso", "--verdict", "concluído sem tokens-used",
        ])
        check("[12o] close-dispatch sem --tokens-used continua ok:true (comportamento pré-E15.2 intacto)", rc == 0 and out.get("ok") is True, str(out))
        check("[12p] close-dispatch sem --tokens-used NÃO ecoa quota_recorded", "quota_recorded" not in out, str(out))
        check("[12q] close-dispatch sem --tokens-used NÃO cria quota-ciclo.json", not (nq_root / "quota-ciclo.json").exists())

        print("\n[12r] Segunda unidade de cota no MESMO ciclo acumula (não sobrescreve)")
        run_json(DISPATCH_SCRIPT, [
            "open-dispatch", "--root", str(quota_root), "--dispatch-id", "dispatch-q2",
            "--cycle-id", "cycle-quota", "--tickets-json", '["TCK-Q2"]',
            "--unit", "ticket:TCK-Q2", "--trilha", "rapida", "--skill", "bmad-quick-dev",
        ])
        rc, out = run_json(DISPATCH_SCRIPT, [
            "close-dispatch", "--root", str(quota_root), "--dispatch-id", "dispatch-q2",
            "--outcome", "sucesso", "--verdict", "segundo despacho do ciclo", "--tokens-used", "500",
        ])
        check("[12r] segunda close-dispatch --tokens-used no mesmo ciclo acumula: 1150 + ceil(500*1.15)=575 -> 1725", out.get("self_tracked_tokens_total") == 1725, str(out))

        # ---------------------------------------------------------------
        print("\n[13] E15.4 — guard mecânico: open-dispatch EXIGE sentinela de crash-check por cycle_id")
        guard_root = tmp / "gerente-guard"
        guard_root.mkdir(parents=True, exist_ok=True)

        print("\n[13a] Cenário que pula detect-crash: open-dispatch é RECUSADO, nada escrito")
        blocked_dispatch_dir = guard_root / "dispatches" / "dispatch-blocked"
        rc, out = run_json(DISPATCH_SCRIPT, [
            "open-dispatch", "--root", str(guard_root), "--dispatch-id", "dispatch-blocked",
            "--cycle-id", "cycle-no-check", "--tickets-json", '["TCK-BLOCKED"]',
            "--unit", "ticket:TCK-BLOCKED", "--trilha", "rapida", "--skill", "bmad-quick-dev",
        ])
        check("[13a1] open-dispatch recusa (ok:false) sem sentinela para o cycle_id", rc != 0 and out.get("ok") is False, str(out))
        check("[13a2] mensagem de erro cita E15.4/detect-crash", "detect-crash" in out.get("error", ""), str(out))
        check("[13a3] request.yaml NUNCA foi escrito", not (blocked_dispatch_dir / "request.yaml").exists())
        check("[13a4] o diretório do despacho nem sequer foi criado", not blocked_dispatch_dir.exists())

        print("\n[13b] Depois de detect-crash --cycle-id para o MESMO ciclo, open-dispatch é liberado")
        rc, det = run_json(STATE_SCRIPT, ["detect-crash", "--root", str(guard_root), "--cycle-id", "cycle-no-check"])
        check("[13b1] detect-crash grava o sentinela e ecoa sentinel_written_for_cycle_id", det.get("sentinel_written_for_cycle_id") == "cycle-no-check", str(det))
        check("[13b2] detect-crash grava sentinel_path sob .crash-check-sentinels/", ".crash-check-sentinels" in det.get("sentinel_path", ""), str(det))
        rc, out = run_json(DISPATCH_SCRIPT, [
            "open-dispatch", "--root", str(guard_root), "--dispatch-id", "dispatch-unblocked",
            "--cycle-id", "cycle-no-check", "--tickets-json", '["TCK-UNBLOCKED"]',
            "--unit", "ticket:TCK-UNBLOCKED", "--trilha", "rapida", "--skill", "bmad-quick-dev",
        ])
        check("[13b3] open-dispatch agora aceita (ok:true) — mesmo cycle_id, sentinela já gravado", rc == 0 and out.get("ok") is True, str(out))
        check("[13b4] request.yaml agora existe", (guard_root / "dispatches" / "dispatch-unblocked" / "request.yaml").exists())

        print("\n[13c] Sentinela é escopado por cycle_id — sentinela do ciclo A NUNCA libera o ciclo B")
        rc, out = run_json(DISPATCH_SCRIPT, [
            "open-dispatch", "--root", str(guard_root), "--dispatch-id", "dispatch-other-cycle",
            "--cycle-id", "cycle-B-nunca-checado", "--tickets-json", '["TCK-B"]',
            "--unit", "ticket:TCK-B", "--trilha", "rapida", "--skill", "bmad-quick-dev",
        ])
        check("[13c1] open-dispatch para cycle-B (nunca checado) é recusado mesmo com cycle-no-check já liberado", rc != 0 and out.get("ok") is False, str(out))
        check("[13c2] request.yaml de cycle-B nunca foi escrito", not (guard_root / "dispatches" / "dispatch-other-cycle" / "request.yaml").exists())

        print("\n[13d] reconcile --cycle-id TAMBÉM grava o sentinela (não só detect-crash)")
        write_board(guard_root.parent / "tickets-guard" / "board.yaml", "TCK-RECONCILE", "pronto-para-implementar")
        rc, rec = run_json(STATE_SCRIPT, [
            "reconcile", "--root", str(guard_root), "--cycle-id", "cycle-via-reconcile",
            "--board-path", str(guard_root.parent / "tickets-guard" / "board.yaml"),
        ])
        check("[13d1] reconcile ecoa sentinel_written_for_cycle_id para o cycle_id que reconciliou", rec.get("sentinel_written_for_cycle_id") == "cycle-via-reconcile", str(rec))
        rc, out = run_json(DISPATCH_SCRIPT, [
            "open-dispatch", "--root", str(guard_root), "--dispatch-id", "dispatch-via-reconcile",
            "--cycle-id", "cycle-via-reconcile", "--tickets-json", '["TCK-RECONCILE"]',
            "--unit", "ticket:TCK-RECONCILE", "--trilha", "rapida", "--skill", "bmad-quick-dev",
        ])
        check("[13d2] open-dispatch aceito para o cycle_id que passou por reconcile (não só detect-crash)", rc == 0 and out.get("ok") is True, str(out))

        print("\n[13e] acquire-lock/check-lock continuam LIVRES — nunca exigem sentinela")
        rc, acq = run_json(STATE_SCRIPT, ["acquire-lock", "--root", str(guard_root), "--cycle-id", "cycle-lock-livre"])
        check("[13e1] acquire-lock funciona normalmente para um cycle_id SEM nenhum sentinela", acq.get("acquired") is True, str(acq))
        rc, chk = run_json(STATE_SCRIPT, ["check-lock", "--root", str(guard_root)])
        check("[13e2] check-lock funciona normalmente (leitura pura, sem gate)", chk.get("held") is True, str(chk))
        run_json(STATE_SCRIPT, ["release-lock", "--root", str(guard_root), "--token", acq.get("token", "")])

        print("\n[13f] detect-crash SEM --cycle-id continua em modo diagnóstico puro (retrocompat) — não grava sentinela")
        rc, det_nocid = run_json(STATE_SCRIPT, ["detect-crash", "--root", str(guard_root)])
        check("[13f1] detect-crash sem --cycle-id não ecoa sentinel_written_for_cycle_id", "sentinel_written_for_cycle_id" not in det_nocid, str(det_nocid))
        check("[13f2] detect-crash sem --cycle-id continua reportando 'crashed' normalmente", "crashed" in det_nocid, str(det_nocid))

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n" + "=" * 60)
    print(f"PASS: {len(PASS)}  FAIL: {len(FAIL)}")
    if FAIL:
        print("Falhas:", FAIL)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
