#!/usr/bin/env python3
"""test_gerente_briefing.py — provas reais (subprocessos, não mocks) dos invariantes de E8.7.

Story E8.7 — roda `gerente_briefing.py` como subprocessos de verdade contra fixtures reais
de diario.jsonl/estado-atual.yaml (`project_controll/test-fixtures/E8/`) para provar:

  1. write-briefing deriva corretamente o Briefing de um ciclo com stop_reason=fila-vazia
     ("parou por conclusão"), incluindo "o que foi feito" e "decisões" extraídos do
     diario.jsonl e "nenhuma decisão pendente de ratificação" quando estado-vazio.yaml.
  2. Idem para stop_reason=cota ("parou por cota") e stop_reason=bloqueio ("parou por
     bloqueio").
  3. Nuance --stop-detail teto-proativo aparece no texto sem inventar um 4º valor de
     stop_reason.
  4. Forward-dep E9.1: com estado-populado.yaml, a seção de ratificação lista as
     entradas reais (ticket + nota); com estado-vazio.yaml OU estado-sem-campo.yaml
     (chave ausente), renderiza "nenhuma decisão pendente de ratificação" igualmente.
  5. Diário torn (CICLO-INICIO sem CICLO-FIM) e linha JSON malformada isolada nunca
     derrubam o script — diagnóstico sinaliza "incompleto", nunca crasha.
  6. detect-unread encontra um Briefing recém-escrito; mark-read o marca como lido
     (idempotente — marcar de novo não é erro); detect-unread deixa de listá-lo.
  7. Idempotência: escrever o MESMO --cycle-id duas vezes substitui a seção (não
     duplica); um segundo --cycle-id no MESMO dia ACRESCENTA uma seção nova preservando
     a anterior.
  8. Data do arquivo vem de --ended-at, não do relógio do sistema; ausência de
     --ended-at cai para o fallback do relógio do próprio script (documentado,
     `used_fallback_date: true`).
  9. detect-unread/mark-read nunca lançam exceção não tratada quando o diretório está
     vazio/ausente ou o briefing pedido não existe.

Sem dependências externas (stdlib apenas). NUNCA escreve em project_controll/gerente/
real — tudo roda contra `tempfile.TemporaryDirectory()`.

Uso:
    python3 test_gerente_briefing.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "gerente_briefing.py"
FIXTURES = HERE.parents[2] / "project_controll" / "test-fixtures" / "E8"


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True,
    )


def run_json(args: list[str]) -> dict:
    p = run(args)
    out = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else "{}"
    try:
        return json.loads(out)
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


def seed_root(tmp_root: Path, diario_fixture: str, estado_fixture: str | None) -> Path:
    tmp_root.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(FIXTURES / diario_fixture, tmp_root / "diario.jsonl")
    if estado_fixture:
        shutil.copyfile(FIXTURES / estado_fixture, tmp_root / "estado-atual.yaml")
    return tmp_root


def main() -> int:
    if not SCRIPT.exists():
        print(f"erro: {SCRIPT} não encontrado", file=sys.stderr)
        return 2
    if not FIXTURES.exists():
        print(f"erro: fixtures não encontradas em {FIXTURES}", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="gerente-briefing-test-") as tmp:
        tmp_path = Path(tmp)

        # ------------------------------------------------------------------
        print("\n[1] write-briefing — stop_reason=fila-vazia (\"parou por conclusão\")")
        root1 = seed_root(tmp_path / "root-conclusao", "diario-conclusao.jsonl", "estado-vazio.yaml")
        r = run_json(["write-briefing", "--root", str(root1), "--cycle-id", "cycle-fx-001",
                      "--started-at", "2026-07-11T03:00:00-03:00", "--ended-at", "2026-07-11T04:15:05-03:00",
                      "--stop-reason", "fila-vazia"])
        check("ok=true", r.get("ok") is True, str(r))
        check("data do arquivo vem do ended-at (2026-07-11)", r.get("date") == "2026-07-11", str(r))
        check("used_fallback_date=false (ended-at fornecido)", r.get("used_fallback_date") is False, str(r))
        check("diario_complete=true (CICLO-INICIO + CICLO-FIM presentes)", r.get("diario_complete") is True, str(r))
        briefing_path = Path(r["path"])
        check("arquivo escrito com nome briefing-20260711.md", briefing_path.name == "briefing-20260711.md", str(r))
        text = briefing_path.read_text(encoding="utf-8")
        check("frontmatter status: unread", "status: unread" in text, text)
        check("seção do ciclo presente", "## Ciclo cycle-fx-001" in text, text)
        check("stop label = conclusão", "**Parou por:** conclusão" in text, text)
        check("despachei extraído do diário", "despachei: TCK-1720670000-ab12 via epic-runner" in text, text)
        check("decidi extraído do diário", "priorizar TCK-1720670000-ab12" in text, text)
        check("decisões pendentes vazio -> 'nenhuma decisão pendente'", "nenhuma decisão pendente de ratificação" in text, text)
        check("duração calculada (1h15min)", "1h15min" in text, text)

        # ------------------------------------------------------------------
        print("\n[2] write-briefing — stop_reason=cota (\"parou por cota\")")
        root2 = seed_root(tmp_path / "root-cota", "diario-cota.jsonl", "estado-vazio.yaml")
        r = run_json(["write-briefing", "--root", str(root2), "--cycle-id", "cycle-fx-002",
                      "--started-at", "2026-07-11T05:00:00-03:00", "--ended-at", "2026-07-11T06:45:05-03:00",
                      "--stop-reason", "cota"])
        text = Path(r["path"]).read_text(encoding="utf-8")
        check("stop label = cota", "**Parou por:** cota" in text, text)
        check("despachei do ciclo cota extraído", "TCK-1720672000-zz99" in text, text)

        # ------------------------------------------------------------------
        print("\n[3] write-briefing — stop_reason=bloqueio (\"parou por bloqueio\")")
        root3 = seed_root(tmp_path / "root-bloqueio", "diario-bloqueio.jsonl", "estado-vazio.yaml")
        r = run_json(["write-briefing", "--root", str(root3), "--cycle-id", "cycle-fx-003",
                      "--started-at", "2026-07-11T07:00:00-03:00", "--ended-at", "2026-07-11T07:20:05-03:00",
                      "--stop-reason", "bloqueio"])
        text = Path(r["path"]).read_text(encoding="utf-8")
        check("stop label = bloqueio", "**Parou por:** bloqueio" in text, text)

        # ------------------------------------------------------------------
        print("\n[3b] write-briefing — fila-vazia + --stop-detail teto-proativo (nuance, sem 4º valor)")
        root3b = seed_root(tmp_path / "root-teto", "diario-conclusao.jsonl", "estado-vazio.yaml")
        r = run_json(["write-briefing", "--root", str(root3b), "--cycle-id", "cycle-fx-001",
                      "--ended-at", "2026-07-11T04:15:05-03:00",
                      "--stop-reason", "fila-vazia", "--stop-detail", "teto-proativo"])
        text = Path(r["path"]).read_text(encoding="utf-8")
        check("rótulo topo continua 'conclusão' (só 3 categorias do AC)", "**Parou por:** conclusão" in text, text)
        check("nuance de teto proativo aparece no texto", "teto de trabalho proativo atingido" in text, text)

        # ------------------------------------------------------------------
        print("\n[4] Forward-dep E9.1 — decisions_pending/escalated populado vs. vazio vs. ausente")
        root4a = seed_root(tmp_path / "root-populado", "diario-cota.jsonl", "estado-populado.yaml")
        r = run_json(["write-briefing", "--root", str(root4a), "--cycle-id", "cycle-fx-002",
                      "--ended-at", "2026-07-11T06:45:05-03:00", "--stop-reason", "cota"])
        text = Path(r["path"]).read_text(encoding="utf-8")
        check("populado: lista o ticket pendente", "TCK-1720660000-cd34" in text and "aguardando ratificação" in text, text)
        check("populado: lista o ticket escalado", "TCK-1720650000-ef56" in text and "escalado para precisa-de-info" in text, text)
        check("populado: NÃO renderiza 'nenhuma decisão pendente'", "nenhuma decisão pendente de ratificação" not in text, text)
        check("contadores no JSON batem (1 pending, 1 escalated)", r.get("decisions_pending_count") == 1 and r.get("decisions_escalated_count") == 1, str(r))

        root4b = seed_root(tmp_path / "root-sem-campo", "diario-bloqueio.jsonl", "estado-sem-campo.yaml")
        r = run_json(["write-briefing", "--root", str(root4b), "--cycle-id", "cycle-fx-003",
                      "--ended-at", "2026-07-11T07:20:05-03:00", "--stop-reason", "bloqueio"])
        text = Path(r["path"]).read_text(encoding="utf-8")
        check("chave AUSENTE (não [] explícito) também renderiza 'nenhuma decisão pendente'", "nenhuma decisão pendente de ratificação" in text, text)
        check("chave ausente não derruba o script (ok=true)", r.get("ok") is True, str(r))

        # ------------------------------------------------------------------
        print("\n[5] Diário torn / linha malformada — nunca crasha, diagnóstico sinaliza incompleto")
        root5a = seed_root(tmp_path / "root-torn", "diario-torn.jsonl", "estado-vazio.yaml")
        r = run_json(["write-briefing", "--root", str(root5a), "--cycle-id", "cycle-fx-004",
                      "--ended-at", "2026-07-11T08:30:00-03:00", "--stop-reason", "bloqueio"])
        check("torn: ok=true mesmo sem CICLO-FIM", r.get("ok") is True, str(r))
        check("torn: diario_complete=false", r.get("diario_complete") is False, str(r))
        text = Path(r["path"]).read_text(encoding="utf-8")
        check("torn: diagnóstico textual = incompleto", "diário: incompleto" in text, text)
        check("torn: ainda extrai o que deu (despachei presente)", "TCK-1720674000-cc22" in text, text)

        root5b = seed_root(tmp_path / "root-malformed-linha", "diario-malformed-linha.jsonl", "estado-vazio.yaml")
        r = run_json(["write-briefing", "--root", str(root5b), "--cycle-id", "cycle-fx-005",
                      "--ended-at", "2026-07-11T09:20:05-03:00", "--stop-reason", "fila-vazia"])
        check("linha malformada isolada: ok=true (não aborta o arquivo inteiro)", r.get("ok") is True, str(r))
        check("linha malformada isolada: diario_complete=true (INICIO+FIM válidos sobrevivem)", r.get("diario_complete") is True, str(r))
        text = Path(r["path"]).read_text(encoding="utf-8")
        check("linha malformada isolada: entrada boa seguinte ainda aparece", "TCK-1720675000-dd33" in text, text)

        no_diario_root = tmp_path / "root-sem-diario"
        no_diario_root.mkdir()
        r = run_json(["write-briefing", "--root", str(no_diario_root), "--cycle-id", "cycle-fx-999",
                      "--ended-at", "2026-07-11T10:00:00-03:00", "--stop-reason", "fila-vazia"])
        check("diario.jsonl totalmente ausente: ok=true, diario_complete=false", r.get("ok") is True and r.get("diario_complete") is False, str(r))
        check("estado-atual.yaml totalmente ausente: contadores zerados, não crasha", r.get("decisions_pending_count") == 0, str(r))

        # ------------------------------------------------------------------
        print("\n[6] detect-unread + mark-read (idempotente) + volta a não listar")
        root6 = seed_root(tmp_path / "root-unread", "diario-conclusao.jsonl", "estado-vazio.yaml")
        run(["write-briefing", "--root", str(root6), "--cycle-id", "cycle-fx-001",
             "--ended-at", "2026-07-11T04:15:05-03:00", "--stop-reason", "fila-vazia"])
        r = run_json(["detect-unread", "--root", str(root6)])
        check("detect-unread encontra 1 briefing não-lido", r.get("count") == 1 and len(r.get("unread", [])) == 1, str(r))
        check("entrada tem date=2026-07-11", r["unread"][0].get("date") == "2026-07-11", str(r))

        r_mark = run_json(["mark-read", "--root", str(root6), "--date", "20260711"])
        check("mark-read ok=true", r_mark.get("ok") is True, str(r_mark))
        check("mark-read: already_read=false na primeira vez", r_mark.get("already_read") is False, str(r_mark))

        r = run_json(["detect-unread", "--root", str(root6)])
        check("depois de mark-read: detect-unread não lista mais nada", r.get("count") == 0, str(r))

        r_mark2 = run_json(["mark-read", "--root", str(root6), "--date", "20260711"])
        check("mark-read chamado DE NOVO no mesmo dia é idempotente (ok=true)", r_mark2.get("ok") is True, str(r_mark2))
        check("mark-read repetido: already_read=true na segunda vez", r_mark2.get("already_read") is True, str(r_mark2))

        # ------------------------------------------------------------------
        print("\n[7] Idempotência de write-briefing — mesmo cycle-id 2x substitui, cycle-id novo mesmo-dia acrescenta")
        root7 = seed_root(tmp_path / "root-idempotente", "diario-conclusao.jsonl", "estado-vazio.yaml")
        run(["write-briefing", "--root", str(root7), "--cycle-id", "cycle-fx-001",
             "--ended-at", "2026-07-11T04:15:05-03:00", "--stop-reason", "fila-vazia"])
        r2 = run_json(["write-briefing", "--root", str(root7), "--cycle-id", "cycle-fx-001",
                       "--ended-at", "2026-07-11T04:15:05-03:00", "--stop-reason", "fila-vazia"])
        check("segunda escrita MESMO cycle-id: section_replaced=true", r2.get("section_replaced") is True, str(r2))
        text = Path(r2["path"]).read_text(encoding="utf-8")
        check("mesmo cycle-id 2x: exatamente 1 ocorrência do header do ciclo (não duplicou)", text.count("## Ciclo cycle-fx-001") == 1, text)

        # ciclo novo, MESMO dia (26/07/11), no mesmo root -- usa fixture de cota mas
        # com ended_at no mesmo dia calendário do cycle-fx-001 acima.
        shutil.copyfile(FIXTURES / "diario-cota.jsonl", root7 / "diario.jsonl")
        # concatena o diario da conclusão (para manter ambos os ciclos rastreáveis no jsonl real)
        combined = (FIXTURES / "diario-conclusao.jsonl").read_text(encoding="utf-8") + (FIXTURES / "diario-cota.jsonl").read_text(encoding="utf-8")
        (root7 / "diario.jsonl").write_text(combined, encoding="utf-8")
        r3 = run_json(["write-briefing", "--root", str(root7), "--cycle-id", "cycle-fx-002",
                       "--ended-at", "2026-07-11T06:45:05-03:00", "--stop-reason", "cota"])
        check("segundo ciclo mesmo dia: mesmo arquivo (briefing-20260711.md)", Path(r3["path"]).name == "briefing-20260711.md", str(r3))
        text = Path(r3["path"]).read_text(encoding="utf-8")
        check("segundo ciclo mesmo dia: seção do PRIMEIRO ciclo preservada", "## Ciclo cycle-fx-001" in text, text)
        check("segundo ciclo mesmo dia: seção do SEGUNDO ciclo acrescentada", "## Ciclo cycle-fx-002" in text, text)
        check("write-briefing subsequente marca o arquivo como unread de novo (novo conteúdo)", "status: unread" in text, text)

        # ------------------------------------------------------------------
        print("\n[8] Data do arquivo vem de --ended-at, não do relógio do sistema; fallback documentado")
        root8 = seed_root(tmp_path / "root-data", "diario-conclusao.jsonl", "estado-vazio.yaml")
        r = run_json(["write-briefing", "--root", str(root8), "--cycle-id", "cycle-fx-001",
                      "--ended-at", "2020-01-05T23:58:00-03:00", "--stop-reason", "fila-vazia"])
        check("data do arquivo = data do ended-at (2020-01-05), mesmo sendo passado", r.get("date") == "2020-01-05", str(r))
        check("used_fallback_date=false quando ended-at é válido", r.get("used_fallback_date") is False, str(r))

        root8b = seed_root(tmp_path / "root-sem-ended-at", "diario-conclusao.jsonl", "estado-vazio.yaml")
        r = run_json(["write-briefing", "--root", str(root8b), "--cycle-id", "cycle-fx-001", "--stop-reason", "fila-vazia"])
        check("sem --ended-at: cai para o fallback do relógio do próprio script", r.get("used_fallback_date") is True, str(r))
        check("sem --ended-at: mesmo assim ok=true (nunca crasha)", r.get("ok") is True, str(r))

        # ------------------------------------------------------------------
        print("\n[9] detect-unread/mark-read nunca lançam exceção em diretório vazio/ausente")
        empty_root = tmp_path / "root-vazio-de-verdade"
        r = run_json(["detect-unread", "--root", str(empty_root)])
        check("detect-unread em raiz inexistente: ok=true, count=0 (não crasha)", r.get("ok") is True and r.get("count") == 0, str(r))

        r = run_json(["mark-read", "--root", str(empty_root), "--date", "20990101"])
        check("mark-read para briefing inexistente: ok=false (erro tratado, não traceback)", r.get("ok") is False, str(r))
        p_traceback = run(["mark-read", "--root", str(empty_root), "--date", "20990101"])
        check("mark-read inexistente: código de saída != 0, mas SEM traceback no stderr", p_traceback.returncode != 0 and "Traceback" not in p_traceback.stderr, p_traceback.stderr)

        # ------------------------------------------------------------------
        print("\n[10] mark-read --expected-last-cycle-id — CAS contra race detect-unread/write-briefing concorrente")
        root10 = seed_root(tmp_path / "root-cas", "diario-conclusao.jsonl", "estado-vazio.yaml")
        run(["write-briefing", "--root", str(root10), "--cycle-id", "cycle-fx-001",
             "--ended-at", "2026-07-11T04:15:05-03:00", "--stop-reason", "fila-vazia"])
        r_du = run_json(["detect-unread", "--root", str(root10)])
        observed_cycle_id = r_du["unread"][0]["last_cycle_id"]
        check("detect-unread devolve last_cycle_id observado", observed_cycle_id == "cycle-fx-001", str(r_du))

        # Simula um ciclo headless concorrente escrevendo uma seção NOVA entre o
        # detect-unread acima e o mark-read abaixo (a race real que o CAS existe pra
        # fechar) -- muda diario.jsonl para incluir também o ciclo de cota e escreve
        # write-briefing para o cycle-fx-002 no MESMO arquivo/dia.
        combined = (FIXTURES / "diario-conclusao.jsonl").read_text(encoding="utf-8") + (FIXTURES / "diario-cota.jsonl").read_text(encoding="utf-8")
        (root10 / "diario.jsonl").write_text(combined, encoding="utf-8")
        run(["write-briefing", "--root", str(root10), "--cycle-id", "cycle-fx-002",
             "--ended-at", "2026-07-11T06:45:05-03:00", "--stop-reason", "cota"])

        r_stale = run_json(["mark-read", "--root", str(root10), "--date", "20260711",
                             "--expected-last-cycle-id", observed_cycle_id])
        check("mark-read com --expected-last-cycle-id DESATUALIZADO: ok=false, error=stale (não clobbra)", r_stale.get("ok") is False and r_stale.get("error") == "stale", str(r_stale))
        check("resposta stale devolve o last_cycle_id ATUAL para o chamador re-detectar", r_stale.get("actual_last_cycle_id") == "cycle-fx-002", str(r_stale))

        text_after_stale_attempt = (root10 / "briefing-20260711.md").read_text(encoding="utf-8")
        check("arquivo continua status: unread depois da tentativa recusada (nada foi clobbado)", "status: unread" in text_after_stale_attempt, text_after_stale_attempt)
        check("seção nova (cycle-fx-002) continua presente e não foi perdida", "## Ciclo cycle-fx-002" in text_after_stale_attempt, text_after_stale_attempt)

        r_du2 = run_json(["detect-unread", "--root", str(root10)])
        fresh_cycle_id = r_du2["unread"][0]["last_cycle_id"]
        r_ok = run_json(["mark-read", "--root", str(root10), "--date", "20260711",
                          "--expected-last-cycle-id", fresh_cycle_id])
        check("mark-read com --expected-last-cycle-id ATUALIZADO (re-detectado): ok=true", r_ok.get("ok") is True, str(r_ok))

        r_no_cas = run_json(["mark-read", "--root", str(root10), "--date", "20260711"])
        check("mark-read SEM --expected-last-cycle-id continua funcionando (compat, marca sempre)", r_no_cas.get("ok") is True, str(r_no_cas))

        # ------------------------------------------------------------------
        print("\n[11] Story E13.4 — semgrep_fp_pending: populado vs. ausente (padrão aditivo)")
        root11a = seed_root(tmp_path / "root-semgrep-fp-populado", "diario-conclusao.jsonl", "estado-semgrep-fp-populado.yaml")
        r = run_json(["write-briefing", "--root", str(root11a), "--cycle-id", "cycle-fx-001",
                      "--ended-at", "2026-07-11T04:15:05-03:00", "--stop-reason", "fila-vazia"])
        check("populado: ok=true", r.get("ok") is True, str(r))
        check("populado: semgrep_fp_pending_count=1", r.get("semgrep_fp_pending_count") == 1, str(r))
        text = Path(r["path"]).read_text(encoding="utf-8")
        check("populado: seção 'Suspeitas de falso-positivo (Semgrep)' presente", "### Suspeitas de falso-positivo (Semgrep)" in text, text)
        check("populado: fingerprint aparece na seção", "no-import-meta-env::frontend/src/main.tsx::10" in text, text)
        check("populado: reason aparece na seção", "Sentry precisa ler import.meta.env antes do React montar" in text, text)
        check("populado: status pending_ratification aparece na seção", "(pending_ratification)" in text, text)
        check("populado: NÃO renderiza a frase neutra", "nenhuma suspeita de falso-positivo pendente" not in text, text)

        # estado-vazio.yaml / estado-sem-campo.yaml (fixtures E8.7 pré-existentes, NUNCA
        # tiveram a chave semgrep_fp_pending) provam por construção o padrão aditivo:
        # um Briefing de um estado "antigo" (anterior a esta story) nunca quebra.
        root11b = seed_root(tmp_path / "root-semgrep-fp-ausente", "diario-conclusao.jsonl", "estado-vazio.yaml")
        r = run_json(["write-briefing", "--root", str(root11b), "--cycle-id", "cycle-fx-001",
                      "--ended-at", "2026-07-11T04:15:05-03:00", "--stop-reason", "fila-vazia"])
        check("chave AUSENTE (estado-vazio.yaml, anterior a E13.4): ok=true, nunca crasha", r.get("ok") is True, str(r))
        check("chave AUSENTE: semgrep_fp_pending_count=0", r.get("semgrep_fp_pending_count") == 0, str(r))
        text = Path(r["path"]).read_text(encoding="utf-8")
        check("chave AUSENTE: seção ainda aparece, com frase neutra", "### Suspeitas de falso-positivo (Semgrep)" in text and "nenhuma suspeita de falso-positivo pendente" in text, text)

        root11c = seed_root(tmp_path / "root-semgrep-fp-sem-campo", "diario-bloqueio.jsonl", "estado-sem-campo.yaml")
        r = run_json(["write-briefing", "--root", str(root11c), "--cycle-id", "cycle-fx-003",
                      "--ended-at", "2026-07-11T07:20:05-03:00", "--stop-reason", "bloqueio"])
        check("estado-sem-campo.yaml (outras chaves ausentes também): ok=true", r.get("ok") is True, str(r))
        text = Path(r["path"]).read_text(encoding="utf-8")
        check("estado-sem-campo.yaml: frase neutra do semgrep FP também presente", "nenhuma suspeita de falso-positivo pendente" in text, text)

    print(f"\n{'='*60}\nPASS: {len(PASS)}  FAIL: {len(FAIL)}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
