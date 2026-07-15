#!/usr/bin/env python3
"""test_gerente_escalation.py — provas reais (subprocessos) das Stories E9.5 e E15.3.

Story E9.5 (ideias/sistema-artifacts/E9-5-gerente-decide-escalados.md), PRD 02 FR-6.
Story E15.3 (ideias/sistema-artifacts/E15-3-mecanizar-correcao-estilo.md), T2.3, estende
`record-sample-review --verdict corrigido` (seção [5] abaixo).

Roda `gerente_escalation.py` como subprocesso de verdade (nunca mock/import direto da
função) contra uma CÓPIA em `tempfile.mkdtemp()` das fixtures sintéticas em
`project_controll/test-fixtures/E9/E9-5/tickets/` — as fixtures em disco nunca são
mutadas (`orphan-sweep`/`record-sample-review` escrevem; por isso o teste sempre copia
para um diretório descartável antes de qualquer operação que escreve).

Prova, nesta ordem:
  [1] `list-escalated` devolve só o ticket com `escalonar: true` (nunca os
      auto-comitados nem o de controle).
  [2] `dead-letter-check` classifica o escalado antigo (`updated: 2020-01-01`) como
      dead-letter e não teria classificado um escalado recente (prova via
      `dead_letter_check()` com uma data de "hoje" injetada, cobrindo o limite exato).
  [3] `sample-decisions`/`record-sample-review`: amostra só os auto-comitados
      (`trilha` != null + `escalonar: false`), nunca re-amostra um já revisado, e o
      veredito "corrigido" fica persistido — inclusive a Entrada de Ledger `corrected`
      que a mesma invocação já grava (E15.3, ver [5]).
  [4] `orphan-sweep` — três cenários com o MESMO mecanismo de heartbeat de
      `gerente_state.py` (Story E8.2): (a) nenhum lock em disco -> reverte; (b) lock
      held-e-fresco (adquirido de verdade via `gerente_state.py acquire-lock`) -> NÃO
      reverte, ticket órfão preservado intacto; (c) lock presente mas com heartbeat
      artificialmente antigo (>900s, o mesmo `DEFAULT_STALE_AFTER_SECONDS`) -> reverte,
      citando a staleness na razão. Depois do revert, confirma que `board.yaml` foi
      regenerado (status refletido no índice) e que o `.md` ganhou uma linha nova em
      `## Log`.
  [5] Story E15.3 — `record-sample-review --verdict corrigido`: (a)/(b) rejeição clara
      (exit != 0, nada escrito) quando os campos de rastro de decisão estão ausentes,
      total ou parcial; (c) uma invocação completa produz `sampled-decisions.json` E a
      Entrada de Ledger `ratification: corrected`, JÁ corrected na primeira leitura
      (nunca passa por `pending`); (d) ordem de escrita (Ledger antes do state, por
      mtime); (e) falha em `record_decision` (front-matter injection) aborta a operação
      inteira, `sampled-decisions.json` nunca tocado — tudo-ou-nada; (f) TESTE PONTA A
      PONTA: a entrada `corrected` gravada em (c) é efetivamente consumida por
      `find_corrected_contradictions` (via `gerente_oracle.py record-decision
      --confidence high`) num "ciclo seguinte" simulado, vetando o auto-merge; (g)
      `--verdict ratificado` continua bit-a-bit idêntico ao pré-E15.3 (nunca toca o
      Ledger, nunca cria `--ledger-root`).

Sem dependências externas (stdlib apenas).

Uso:
    python3 test_gerente_escalation.py
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = Path(__file__).resolve().parent
ESCALATION = SCRIPTS_DIR / "gerente_escalation.py"
GERENTE_STATE = SCRIPTS_DIR / "gerente_state.py"
GERENTE_ORACLE = SCRIPTS_DIR / "gerente_oracle.py"
REBUILD_BOARD = REPO_ROOT / "project_controll" / "tickets" / "scripts" / "rebuild_board.py"
FIXTURES_TICKETS = REPO_ROOT / "project_controll" / "test-fixtures" / "E9" / "E9-5" / "tickets"

PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASS.append(name)
        print(f"  PASS  {name}")
    else:
        FAIL.append(name)
        print(f"  FAIL  {name}  {detail}")


def run(argv: list[str]) -> dict:
    proc = subprocess.run([sys.executable, *argv], capture_output=True, text=True)
    if proc.returncode not in (0, 1):
        raise RuntimeError(f"comando falhou (rc={proc.returncode}): {argv}\nstderr={proc.stderr}")
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"stdout não é JSON: {proc.stdout!r} ({exc})") from exc


def run_any(argv: list[str]) -> tuple[int, dict]:
    """Como `run()`, mas aceita QUALQUER returncode (inclusive 2) — usado pelos casos de
    rejeição da Story E15.3 (`--verdict corrigido` sem campos de rastro devolve exit 2),
    onde `run()` levantaria RuntimeError por assumir só {0, 1}. Devolve
    (returncode, json_stdout)."""
    proc = subprocess.run([sys.executable, *argv], capture_output=True, text=True)
    try:
        return proc.returncode, json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"stdout não é JSON: {proc.stdout!r} (rc={proc.returncode}) ({exc})") from exc


def make_scratch_tickets_dir() -> Path:
    """Copia as fixtures (nunca mutadas em disco) para um dir descartável + reconstrói
    board.yaml a partir da cópia (nunca copia o board.yaml da fixture — prova que o
    índice é sempre derivável, mesma disciplina de E5.2)."""
    scratch = Path(tempfile.mkdtemp(prefix="e9-5-tickets-"))
    for md in FIXTURES_TICKETS.glob("*.md"):
        shutil.copy(md, scratch / md.name)
    proc = subprocess.run(
        [sys.executable, str(REBUILD_BOARD), "--tickets-dir", str(scratch), "--out", str(scratch / "board.yaml")],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"rebuild_board.py falhou: {proc.stderr}")
    return scratch


def snapshot_fixtures() -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in sorted(FIXTURES_TICKETS.glob("*.md"))}


def main() -> int:
    fixtures_before = snapshot_fixtures()

    # ------------------------------------------------------------------
    print("\n[1] list-escalated — só o escalonar: true, nunca os auto-comitados/controle")
    scratch1 = make_scratch_tickets_dir()
    r = run([str(ESCALATION), "list-escalated", "--board-path", str(scratch1 / "board.yaml")])
    ids = [e["ticket"] for e in r["escalated"]]
    check("count == 1", r["count"] == 1, str(r))
    check("só TCK-E9T-20 (o escalado)", ids == ["TCK-E9T-20"], str(ids))
    check("TCK-E9T-22 (auto rapida) nunca aparece", "TCK-E9T-22" not in ids, str(ids))
    check("TCK-E9T-23 (auto wds) nunca aparece", "TCK-E9T-23" not in ids, str(ids))
    check("TCK-E9T-25 (controle, triado) nunca aparece", "TCK-E9T-25" not in ids, str(ids))

    # ------------------------------------------------------------------
    print("\n[2] dead-letter-check — escalado antigo vira dead-letter; recente não")
    r_old = run([str(ESCALATION), "dead-letter-check", "--board-path", str(scratch1 / "board.yaml"), "--limit-days", "3"])
    check("escalado antigo (2020-01-01) vira dead-letter", any(d["ticket"] == "TCK-E9T-20" for d in r_old["dead_letter"]), str(r_old))
    check("days_stuck reportado é grande (não um número inventado pequeno)", r_old["dead_letter"][0]["days_stuck"] > 300, str(r_old))

    # Fixture "escalado recente" gerada dinamicamente (updated = hoje) — não pode ser um
    # arquivo estático (quebraria em execuções futuras) — prova o limite pelo lado "não
    # deve dead-letrar" com uma data que É a real data de hoje da máquina rodando o teste.
    scratch2 = make_scratch_tickets_dir()
    recent_md = scratch2 / "TCK-E9T-20-escalado-antigo.md"
    text = recent_md.read_text(encoding="utf-8")
    today_str = date.today().isoformat()
    text = text.replace("updated: 2020-01-01", f"updated: {today_str}")
    recent_md.write_text(text, encoding="utf-8")
    subprocess.run([sys.executable, str(REBUILD_BOARD), "--tickets-dir", str(scratch2), "--out", str(scratch2 / "board.yaml")], check=True, capture_output=True)
    r_recent = run([str(ESCALATION), "dead-letter-check", "--board-path", str(scratch2 / "board.yaml"), "--limit-days", "3"])
    check("escalado atualizado HOJE não é dead-letter", r_recent["dead_letter_count"] == 0, str(r_recent))

    # ------------------------------------------------------------------
    print("\n[3] sample-decisions / record-sample-review — amostra só auto-comitados, nunca re-amostra")
    scratch3 = make_scratch_tickets_dir()
    state_path = scratch3 / "sampled-decisions.json"
    r_sample = run([
        str(ESCALATION), "sample-decisions",
        "--board-path", str(scratch3 / "board.yaml"), "--state-path", str(state_path), "--sample-size", "10",
    ])
    sampled_ids = {c["ticket"] for c in r_sample["sample"]}
    check("amostra inclui os 2 auto-comitados (rapida + wds)", {"TCK-E9T-22", "TCK-E9T-23"} <= sampled_ids, str(r_sample))
    check("amostra NUNCA inclui o escalado (TCK-E9T-20, trilha ainda null)", "TCK-E9T-20" not in sampled_ids, str(r_sample))
    check("amostra NUNCA inclui o de controle (TCK-E9T-25, trilha null)", "TCK-E9T-25" not in sampled_ids, str(r_sample))

    ledger_root_3 = scratch3.parent / f"{scratch3.name}-ledger"
    r_review = run([
        str(ESCALATION), "record-sample-review",
        "--state-path", str(state_path), "--ticket", "TCK-E9T-22",
        "--verdict", "corrigido", "--trilha-auto", "rapida", "--trilha-corrigida", "spec",
        "--note", "escopo maior que a Regra A capturou",
        "--question", "A trilha rapida cobre um ticket que precisa de spec?",
        "--justification", "O escopo do ticket exigia decisão de arquitetura, não só um patch pontual.",
        "--context", "Amostragem do Briefing sinalizou trilha rapida auto-comitada para TCK-E9T-22.",
        "--ledger-root", str(ledger_root_3),
    ])
    check("record-sample-review grava ok", r_review["ok"] is True, str(r_review))
    check("state persistido em disco", state_path.exists(), "")
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    check("veredito persistido == corrigido", persisted["TCK-E9T-22"]["verdict"] == "corrigido", str(persisted))
    check("E15.3: entrada persistida referencia a Entrada de Ledger (ledger_entry)", "ledger_entry" in persisted["TCK-E9T-22"], str(persisted))
    check("E15.3: ledger_entry.ratification == corrected", persisted["TCK-E9T-22"].get("ledger_entry", {}).get("ratification") == "corrected", str(persisted))
    ledger_entry_path_3 = Path(persisted["TCK-E9T-22"]["ledger_entry"]["ledger_path"])
    check("E15.3: o arquivo do Ledger citado em sampled-decisions.json existe de fato", ledger_entry_path_3.exists(), str(ledger_entry_path_3))
    ledger_content_3 = ledger_entry_path_3.read_text(encoding="utf-8")
    check("E15.3: front-matter do Ledger reflete ratification: corrected", "ratification: corrected" in ledger_content_3, ledger_content_3)
    check("E15.3: front-matter do Ledger reflete oracle: true", "oracle: true" in ledger_content_3, ledger_content_3)
    check("E15.3: front-matter do Ledger reflete ticket: TCK-E9T-22", "ticket: TCK-E9T-22" in ledger_content_3, ledger_content_3)

    r_sample_again = run([
        str(ESCALATION), "sample-decisions",
        "--board-path", str(scratch3 / "board.yaml"), "--state-path", str(state_path), "--sample-size", "10",
    ])
    sampled_ids_2 = {c["ticket"] for c in r_sample_again["sample"]}
    check("ticket já revisado NUNCA reaparece na amostra seguinte", "TCK-E9T-22" not in sampled_ids_2, str(r_sample_again))
    check("ticket ainda não revisado (wds) continua aparecendo", "TCK-E9T-23" in sampled_ids_2, str(r_sample_again))

    # ------------------------------------------------------------------
    print("\n[4a] orphan-sweep — nenhum lock em disco => reverte o órfão")
    scratch4a = make_scratch_tickets_dir()
    gerente_root_4a = scratch4a.parent / f"{scratch4a.name}-gerente-a"
    gerente_root_4a.mkdir()
    r_sweep_a = run([
        str(ESCALATION), "orphan-sweep",
        "--gerente-root", str(gerente_root_4a), "--tickets-dir", str(scratch4a), "--board-path", str(scratch4a / "board.yaml"),
    ])
    check("swept == true (nenhum lock => varredura roda)", r_sweep_a["swept"] is True, str(r_sweep_a))
    check("TCK-E9T-24 revertido", any(o["ticket"] == "TCK-E9T-24" for o in r_sweep_a["orphans_reverted"]), str(r_sweep_a))
    board_after_a = (scratch4a / "board.yaml").read_text(encoding="utf-8")
    check("board.yaml regenerado reflete pronto-para-implementar", "TCK-E9T-24:\n    title:" in board_after_a and "status: pronto-para-implementar" in board_after_a.split("TCK-E9T-24:")[1].split("TCK-E9T-25:")[0], board_after_a)
    md_after_a = next(scratch4a.glob("TCK-E9T-24-*.md")).read_text(encoding="utf-8")
    check("status: pronto-para-implementar no .md", "\nstatus: pronto-para-implementar\n" in md_after_a, md_after_a)
    check("## Log ganhou linha citando a varredura de órfãos (E9.5)", "varredura de órfãos do Gerente (E9.5)" in md_after_a, md_after_a)

    # ------------------------------------------------------------------
    print("\n[4b] orphan-sweep — lock held-e-FRESCO (adquirido de verdade) => NÃO reverte")
    scratch4b = make_scratch_tickets_dir()
    gerente_root_4b = scratch4b.parent / f"{scratch4b.name}-gerente-b"
    gerente_root_4b.mkdir()
    acquire = run([str(GERENTE_STATE), "acquire-lock", "--root", str(gerente_root_4b), "--cycle-id", "ciclo-vivo-teste"])
    check("acquire-lock (setup) funcionou", acquire.get("acquired") is True, str(acquire))
    r_sweep_b = run([
        str(ESCALATION), "orphan-sweep",
        "--gerente-root", str(gerente_root_4b), "--tickets-dir", str(scratch4b), "--board-path", str(scratch4b / "board.yaml"),
    ])
    check("swept == false (lock vivo => varredura pulada)", r_sweep_b["swept"] is False, str(r_sweep_b))
    check("nenhum órfão revertido", r_sweep_b["orphans_reverted"] == [], str(r_sweep_b))
    md_after_b = next(scratch4b.glob("TCK-E9T-24-*.md")).read_text(encoding="utf-8")
    check("status continua em-implementacao (ticket genuinamente em voo preservado)", "\nstatus: em-implementacao\n" in md_after_b, md_after_b)
    board_after_b = (scratch4b / "board.yaml").read_text(encoding="utf-8")
    check("board.yaml também preservado (em-implementacao)", "status: em-implementacao" in board_after_b.split("TCK-E9T-24:")[1].split("TCK-E9T-25:")[0], board_after_b)

    # ------------------------------------------------------------------
    print("\n[4c] orphan-sweep — lock presente mas heartbeat STALE (>900s) => reverte")
    scratch4c = make_scratch_tickets_dir()
    gerente_root_4c = scratch4c.parent / f"{scratch4c.name}-gerente-c"
    gerente_root_4c.mkdir()
    run([str(GERENTE_STATE), "acquire-lock", "--root", str(gerente_root_4c), "--cycle-id", "ciclo-morto-teste"])
    lock_info_path = gerente_root_4c / ".lock" / "info.json"
    info = json.loads(lock_info_path.read_text(encoding="utf-8"))
    info["heartbeat_at"] = "2020-01-01T00:00:00-03:00"
    info["acquired_at"] = "2020-01-01T00:00:00-03:00"
    lock_info_path.write_text(json.dumps(info), encoding="utf-8")
    r_sweep_c = run([
        str(ESCALATION), "orphan-sweep",
        "--gerente-root", str(gerente_root_4c), "--tickets-dir", str(scratch4c), "--board-path", str(scratch4c / "board.yaml"),
    ])
    check("swept == true (heartbeat stale => varredura roda)", r_sweep_c["swept"] is True, str(r_sweep_c))
    check("stale_reason cita heartbeat silencioso (mesma primitiva de gerente_state.py)", "heartbeat" in r_sweep_c.get("stale_reason", ""), str(r_sweep_c))
    check("TCK-E9T-24 revertido (heartbeat morto)", any(o["ticket"] == "TCK-E9T-24" for o in r_sweep_c["orphans_reverted"]), str(r_sweep_c))

    # ------------------------------------------------------------------
    print("\n[5] Story E15.3 — record-sample-review --verdict corrigido mecaniza record_decision + set_ratification(corrected) na MESMA invocação")
    scratch5 = make_scratch_tickets_dir()
    state_path_5 = scratch5 / "sampled-decisions.json"
    ledger_root_5 = scratch5.parent / f"{scratch5.name}-ledger5"

    print("\n[5a] --verdict corrigido SEM os campos de rastro é rejeitado (exit 2), nada escrito")
    rc_5a, r_5a = run_any([
        str(ESCALATION), "record-sample-review",
        "--state-path", str(state_path_5), "--ticket", "TCK-E9T-22",
        "--verdict", "corrigido", "--trilha-auto", "rapida", "--trilha-corrigida", "spec",
        "--ledger-root", str(ledger_root_5),
        # --question/--justification/--context deliberadamente OMITIDOS
    ])
    check("exit code != 0 (rejeitado)", rc_5a != 0, str((rc_5a, r_5a)))
    check("ok == false", r_5a.get("ok") is False, str(r_5a))
    check("erro cita os campos ausentes (--question/--justification/--context)", {"--question", "--justification", "--context"} <= set(r_5a.get("missing_fields", [])), str(r_5a))
    check("nada foi escrito — sampled-decisions.json NÃO existe", not state_path_5.exists(), "")
    check("nada foi escrito — ledger-root NÃO existe", not ledger_root_5.exists(), "")

    print("\n[5b] --verdict corrigido com campos parciais (falta --context) também é rejeitado, nada escrito")
    rc_5b, r_5b = run_any([
        str(ESCALATION), "record-sample-review",
        "--state-path", str(state_path_5), "--ticket", "TCK-E9T-22",
        "--verdict", "corrigido", "--trilha-auto", "rapida", "--trilha-corrigida", "spec",
        "--question", "q", "--justification", "j",
        "--ledger-root", str(ledger_root_5),
    ])
    check("exit code != 0 (rejeitado)", rc_5b != 0, str((rc_5b, r_5b)))
    check("erro cita só --context como ausente", r_5b.get("missing_fields") == ["--context"], str(r_5b))
    check("ainda nada escrito", not state_path_5.exists() and not ledger_root_5.exists(), "")

    print("\n[5c] --verdict corrigido COMPLETO — uma invocação produz sampled-decisions.json E a Entrada de Ledger corrected")
    r_5c = run([
        str(ESCALATION), "record-sample-review",
        "--state-path", str(state_path_5), "--ticket", "TCK-E9T-22",
        "--verdict", "corrigido", "--trilha-auto", "rapida", "--trilha-corrigida", "spec",
        "--note", "escopo maior que a Regra A capturou",
        "--question", "A trilha rapida cobre um ticket que precisa de spec?",
        "--justification", "O escopo do ticket exigia decisão de arquitetura.",
        "--context", "Amostragem do Briefing sinalizou trilha rapida auto-comitada para TCK-E9T-22.",
        "--areas", "escalonamento,trilha-corrigida-teste",
        "--ledger-root", str(ledger_root_5),
    ])
    check("ok == true", r_5c.get("ok") is True, str(r_5c))
    check("(a) sampled-decisions.json foi escrito", state_path_5.exists(), "")
    ledger_path_5c = Path(r_5c["entry"]["ledger_entry"]["ledger_path"])
    check("(b) Entrada de Ledger foi escrita", ledger_path_5c.exists(), str(r_5c))
    content_5c = ledger_path_5c.read_text(encoding="utf-8")
    check("Ledger: oracle: true", "oracle: true" in content_5c, content_5c)
    check("Ledger: ratification: corrected (já na primeira leitura, sem passo manual extra)", "ratification: corrected" in content_5c, content_5c)
    # Checa o CAMPO de front-matter (linha exata `ratification: pending`, sem os
    # crases/backticks da prosa do corpo) — o corpo cita `` `ratification: pending` ``
    # (com crases) como texto ESTÁTICO explicativo de `record_decision` (não reescrito
    # por `set_ratification`, que só ANEXA uma nota em `## Transições`; comportamento
    # herdado de E9.1/E9.2, não uma regressão desta story) — checar a substring "solta"
    # sem os delimitadores de linha pegaria esse texto estático por engano.
    check("Ledger: front-matter NUNCA fica em ratification: pending (set_ratification já rodou na mesma invocação)", "\nratification: pending\n" not in content_5c, content_5c)

    print("\n[5d] Ordem de escrita: Entrada de Ledger existe ANTES (ou no mesmo instante) que sampled-decisions.json (mtime)")
    state_mtime = state_path_5.stat().st_mtime_ns
    ledger_mtime = ledger_path_5c.stat().st_mtime_ns
    check("ledger_mtime <= state_mtime (Ledger gravado antes da escrita que finaliza a operação)", ledger_mtime <= state_mtime, f"ledger={ledger_mtime} state={state_mtime}")

    print("\n[5e] Falha em record_decision (front-matter injection no --ticket) aborta a operação INTEIRA — sampled-decisions.json não é tocado")
    state_path_5e = scratch5 / "sampled-decisions-5e.json"
    ledger_root_5e = scratch5.parent / f"{scratch5.name}-ledger5e"
    ticket_with_newline = "TCK-BAD\nratification: ratified"
    rc_5e, r_5e = run_any([
        str(ESCALATION), "record-sample-review",
        "--state-path", str(state_path_5e), "--ticket", ticket_with_newline,
        "--verdict", "corrigido", "--trilha-auto", "rapida", "--trilha-corrigida", "spec",
        "--question", "q", "--justification", "j", "--context", "c",
        "--ledger-root", str(ledger_root_5e),
    ])
    check("exit code != 0 (record_decision recusou a injeção)", rc_5e != 0, str((rc_5e, r_5e)))
    check("ok == false, stage == record_decision", r_5e.get("stage") == "record_decision", str(r_5e))
    check("tudo-ou-nada: sampled-decisions.json NÃO foi criado", not state_path_5e.exists(), "")

    print("\n[5f] find_corrected_contradictions consome a entrada `corrected` de [5c] no CICLO SEGUINTE — teste ponta a ponta")
    prec = run([
        str(GERENTE_ORACLE), "record-decision", "--ledger-root", str(ledger_root_5),
        "--tipo", "decisao-tecnica", "--ticket", "TCK-E9T-PREC",
        "--question", "q-prec", "--decision", "d-prec", "--justification", "j-prec", "--context", "c-prec",
        "--areas", "escalonamento,trilha-corrigida-teste",
    ])
    check("setup: precedente candidato gravado", prec.get("ok") is True, str(prec))
    ratify_prec = run([str(GERENTE_ORACLE), "set-ratification", "--entry", prec["ledger_path"], "--status", "ratified"])
    check("setup: precedente ratificado (estado: ativa)", ratify_prec.get("estado_after") == "ativa", str(ratify_prec))

    r_next_cycle = run([
        str(GERENTE_ORACLE), "record-decision", "--ledger-root", str(ledger_root_5),
        "--tipo", "decisao-tecnica", "--ticket", "TCK-E9T-NEXT",
        "--question", "Outro ticket parecido também deveria usar a trilha rapida?",
        "--decision", "Usar trilha rapida de novo.", "--justification", "j", "--context", "c",
        "--areas", "escalonamento,trilha-corrigida-teste",
        "--confidence", "high", "--precedent", prec["ledger_path"],
    ])
    check("E9.2 history-aware: 'high' pedido COM precedente válido é rebaixado para 'low' — a entrada corrected de [5c] contradiz", r_next_cycle.get("confidence") == "low", str(r_next_cycle))
    check("downgrade_reason cita 'corrected'", "corrected" in (r_next_cycle.get("downgrade_reason") or ""), str(r_next_cycle))
    check("contradicting_corrected referencia o path exato de [5c]", any(c.get("path") == str(ledger_path_5c) for c in r_next_cycle.get("contradicting_corrected", [])), str(r_next_cycle))
    check("proceed_dispatch == false (auto-merge vetado)", r_next_cycle.get("proceed_dispatch") is False, str(r_next_cycle))

    print("\n[5g] --verdict ratificado continua INALTERADO — nunca toca o Ledger")
    state_path_5g = scratch5 / "sampled-decisions-5g.json"
    ledger_root_5g = scratch5.parent / f"{scratch5.name}-ledger5g"
    r_5g = run([
        str(ESCALATION), "record-sample-review",
        "--state-path", str(state_path_5g), "--ticket", "TCK-E9T-23",
        "--verdict", "ratificado", "--trilha-auto", "wds",
        "--ledger-root", str(ledger_root_5g),  # passado mas nunca deveria ser usado
    ])
    check("ok == true", r_5g.get("ok") is True, str(r_5g))
    check("entry NUNCA tem ledger_entry para ratificado", "ledger_entry" not in r_5g.get("entry", {}), str(r_5g))
    check("--ledger-root passado mas NUNCA criado (ratificado não toca o Ledger)", not ledger_root_5g.exists(), "")
    persisted_5g = json.loads(state_path_5g.read_text(encoding="utf-8"))
    check("shape do state idêntico ao pré-E15.3 (sem ledger_entry)", set(persisted_5g["TCK-E9T-23"].keys()) == {"verdict", "reviewed_at", "trilha_auto", "trilha_corrigida", "note"}, str(persisted_5g))

    # ------------------------------------------------------------------
    print("\n[6] fixtures em disco nunca foram mutadas (conteúdo byte-a-byte idêntico ao início)")
    fixtures_after = snapshot_fixtures()
    check("mesmo conjunto de arquivos (nenhum criado/removido)", set(fixtures_before) == set(fixtures_after), f"antes={sorted(fixtures_before)} depois={sorted(fixtures_after)}")
    check("conteúdo idêntico byte-a-byte (orphan-sweep/record-sample-review só tocaram as CÓPIAS em tempfile)", fixtures_before == fixtures_after, "diff encontrado nas fixtures reais")

    # ------------------------------------------------------------------
    print(f"\n{len(PASS)} PASS, {len(FAIL)} FAIL")
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
