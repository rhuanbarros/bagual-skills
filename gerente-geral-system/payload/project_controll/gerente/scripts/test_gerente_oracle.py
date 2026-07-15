#!/usr/bin/env python3
"""test_gerente_oracle.py — provas reais (subprocessos, não mocks) dos invariantes de E9.1.

Story E9.1 (ideias/sistema-artifacts/E9-1-oraculo-decisao-delegada.md) — roda
`gerente_oracle.py` como subprocessos de verdade contra um ledger-root TEMPORÁRIO
(nunca escreve na árvore real `wiki/ledger/`) para provar:

  1. `record-decision` escreve uma Entrada de Ledger válida (front-matter completo +
     as 3 seções MADR que carregam decisão/justificativa/contexto), com
     `oracle: true`, `ratification: pending` — e passa no self-check
     (`validate_ledger.py`) sem violações.
  2. **O CASO CENTRAL (F10):** o gate de confiança é mecânico, nunca confia na
     alegação do chamador — `--confidence high` só é honrada quando `--precedent`
     resiste à verificação (vivo, `estado != aposentada`, `ratification != corrected`);
     em QUALQUER outro caso (sem precedente, precedente ausente/aposentado/corrigido)
     a confiança é rebaixada para `low` e `proceed_dispatch` é sempre `false`.
  3. Baixa confiança nunca seta `proceed_dispatch: true` — prova direta de que uma
     decisão de baixa confiança PROVAVELMENTE não pode vazar para auto-merge.
  4. `list-pending` enxerga só entradas `oracle: true` + `ratification: pending`,
     filtráveis por ticket.
  5. `set-ratification` flipa `pending -> ratified` (promovendo `candidata -> ativa`)
     ou `pending -> corrected` (estado inalterado) — e uma entrada `corrected` NUNCA
     mais sustenta `--confidence high` como precedente de uma decisão futura (fecha o
     loop: um erro corrigido não se perpetua).
  6. Persistência em disco: cada asserção relê o arquivo do zero via um subprocess
     NOVO (nunca estado em memória) — a prova de que o registro sobrevive a qualquer
     perda de contexto do processo que o escreveu.
  7. Colisão de slug nunca sobrescreve um arquivo existente (sufixo numérico).

Sem dependências externas (stdlib apenas).

Uso:
    python3 test_gerente_oracle.py
"""
from __future__ import annotations

import concurrent.futures
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "gerente_oracle.py"
REPO_ROOT = HERE.resolve().parents[2]
VALIDATE_LEDGER = REPO_ROOT / "wiki" / "ledger" / "scripts" / "validate_ledger.py"
FIXTURES = REPO_ROOT / "project_controll" / "test-fixtures" / "E9"


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)


def run_json(args: list[str]) -> dict:
    p = run(args)
    out = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else "{}"
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        print("STDOUT:", p.stdout, file=sys.stderr)
        print("STDERR:", p.stderr, file=sys.stderr)
        raise


def run_validate(ledger_root: Path) -> dict:
    p = subprocess.run(
        [sys.executable, str(VALIDATE_LEDGER), "--ledger-root", str(ledger_root), "--json"],
        capture_output=True, text=True,
    )
    return json.loads(p.stdout.strip())


PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        PASS.append(name)
        print(f"  PASS  {name}")
    else:
        FAIL.append(name)
        print(f"  FAIL  {name}  {detail}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="gerente-oracle-test-") as tmp:
        tmp_path = Path(tmp)
        ledger_root = tmp_path / "ledger"

        # ------------------------------------------------------------------
        print("\n[1] record-decision — entrada válida, 3 campos (decisão/justificativa/contexto), self-check limpo")
        r = run_json([
            "record-decision", "--ledger-root", str(ledger_root),
            "--ticket", "TCK-900", "--tipo", "decisao-tecnica",
            "--question", "Qual formato de export usar para o relatório de indicações?",
            "--decision", "Usar CSV com separador vírgula e cabeçalho em português.",
            "--justification", "CSV é o formato que a Central já consome hoje em outras exportações.",
            "--context", "Sub-agente despachado para a feature de indicações não encontrou um padrão de export documentado.",
        ])
        check("ok=true, sem violações de self-check", r.get("ok") is True, str(r))
        ledger_path_1 = Path(r["ledger_path"])
        check("arquivo foi escrito em disco", ledger_path_1.exists(), str(r))
        content_1 = ledger_path_1.read_text(encoding="utf-8")
        check("front-matter: oracle: true", "oracle: true" in content_1)
        check("front-matter: ticket: TCK-900", "ticket: TCK-900" in content_1)
        check("front-matter: estado: candidata (nunca ativa ao nascer)", "estado: candidata" in content_1)
        check("front-matter: ratification: pending", "ratification: pending" in content_1)
        check("corpo: seção ## Contexto presente (campo 'contexto')", "## Contexto" in content_1)
        check("corpo: seção ## Decisão presente (campo 'decisão')", "## Decisão" in content_1)
        check("corpo: seção ## Consequências presente (carrega 'justificativa')", "## Consequências" in content_1)
        check("corpo: justificativa de fato gravada", "CSV é o formato que a Central já consome" in content_1)
        check("corpo: contexto de fato gravado", "não encontrou um padrão de export" in content_1)

        # ------------------------------------------------------------------
        print("\n[2] Default conservador — sem --confidence explícito, é LOW; proceed_dispatch=false; blast_radius=parked")
        r2 = run_json([
            "record-decision", "--ledger-root", str(ledger_root),
            "--ticket", "TCK-901",
            "--question", "Pergunta sem confiança declarada.",
            "--decision", "Decisão qualquer.",
            "--justification", "Justificativa qualquer.",
            "--context", "Contexto qualquer.",
        ])
        check("confidence default = low", r2.get("confidence") == "low", str(r2))
        check("proceed_dispatch = false por default", r2.get("proceed_dispatch") is False, str(r2))
        check("blast_radius = parked por default", r2.get("blast_radius") == "parked", str(r2))

        # ------------------------------------------------------------------
        print("\n[3] F10 — 'high' pedido SEM --precedent é SEMPRE rebaixado para low")
        r3 = run_json([
            "record-decision", "--ledger-root", str(ledger_root),
            "--ticket", "TCK-902", "--confidence", "high",
            "--question", "q", "--decision", "d", "--justification", "j", "--context", "c",
        ])
        check("confidence final = low (rebaixada)", r3.get("confidence") == "low", str(r3))
        check("confidence_requested preservado = high (auditável)", r3.get("confidence_requested") == "high", str(r3))
        check("downgrade_reason explica a ausência de precedente", "precedent" in (r3.get("downgrade_reason") or ""), str(r3))
        check("proceed_dispatch = false mesmo com high pedido", r3.get("proceed_dispatch") is False, str(r3))

        # ------------------------------------------------------------------
        print("\n[4] F10 — 'high' pedido com --precedent INEXISTENTE é rebaixado para low")
        r4 = run_json([
            "record-decision", "--ledger-root", str(ledger_root),
            "--ticket", "TCK-903", "--confidence", "high",
            "--precedent", str(tmp_path / "nao-existe.md"),
            "--question", "q", "--decision", "d", "--justification", "j", "--context", "c",
        ])
        check("confidence final = low (precedente inexistente)", r4.get("confidence") == "low", str(r4))
        check("proceed_dispatch = false", r4.get("proceed_dispatch") is False, str(r4))

        # ------------------------------------------------------------------
        print("\n[5] F10 — 'high' pedido com --precedent APOSENTADO é rebaixado para low")
        r5 = run_json([
            "record-decision", "--ledger-root", str(ledger_root),
            "--ticket", "TCK-904", "--confidence", "high",
            "--precedent", str(FIXTURES / "precedent-aposentada.md"),
            "--question", "q", "--decision", "d", "--justification", "j", "--context", "c",
        ])
        check("confidence final = low (precedente aposentado)", r5.get("confidence") == "low", str(r5))
        check("downgrade_reason cita 'aposentada'", "aposentada" in (r5.get("downgrade_reason") or ""), str(r5))
        check("proceed_dispatch = false", r5.get("proceed_dispatch") is False, str(r5))

        # ------------------------------------------------------------------
        print("\n[6] F10 — 'high' pedido com --precedent CORRIGIDO (ratification: corrected) é rebaixado para low")
        r6 = run_json([
            "record-decision", "--ledger-root", str(ledger_root),
            "--ticket", "TCK-905", "--confidence", "high",
            "--precedent", str(FIXTURES / "precedent-corrected.md"),
            "--question", "q", "--decision", "d", "--justification", "j", "--context", "c",
        ])
        check("confidence final = low (precedente corrigido)", r6.get("confidence") == "low", str(r6))
        check("downgrade_reason cita 'corrected'", "corrected" in (r6.get("downgrade_reason") or ""), str(r6))
        check("proceed_dispatch = false", r6.get("proceed_dispatch") is False, str(r6))

        # ------------------------------------------------------------------
        print("\n[7] CASO POSITIVO — 'high' pedido com --precedent VÁLIDO (ativo, nunca corrigido) É honrado")
        r7 = run_json([
            "record-decision", "--ledger-root", str(ledger_root),
            "--ticket", "TCK-906", "--confidence", "high",
            "--precedent", str(FIXTURES / "precedent-ativa.md"),
            "--question", "q", "--decision", "d", "--justification", "j", "--context", "c",
        ])
        check("confidence final = high", r7.get("confidence") == "high", str(r7))
        check("downgrade_reason = null (nenhum rebaixamento)", r7.get("downgrade_reason") is None, str(r7))
        check("blast_radius = auto-merge", r7.get("blast_radius") == "auto-merge", str(r7))
        check("proceed_dispatch = true", r7.get("proceed_dispatch") is True, str(r7))
        content_7 = Path(r7["ledger_path"]).read_text(encoding="utf-8")
        check("front-matter grava confidence: high", "confidence: high" in content_7)
        check("front-matter grava blast_radius: auto-merge", "blast_radius: auto-merge" in content_7)

        # ------------------------------------------------------------------
        print("\n[8] list-pending — enxerga só oracle:true + ratification:pending, filtrável por ticket")
        lp_all = run_json(["list-pending", "--ledger-root", str(ledger_root)])
        check("todas as 7 decisões gravadas acima aparecem como pending", lp_all.get("count") == 7, str(lp_all))
        lp_900 = run_json(["list-pending", "--ledger-root", str(ledger_root), "--ticket", "TCK-900"])
        check("filtro por ticket retorna só 1 entrada", lp_900.get("count") == 1, str(lp_900))
        check("entrada filtrada é a do ticket certo", lp_900["entries"][0]["ticket"] == "TCK-900", str(lp_900))

        # ------------------------------------------------------------------
        print("\n[9] set-ratification — ratified promove candidata -> ativa e some de list-pending")
        sr_ratified = run_json(["set-ratification", "--entry", str(ledger_path_1), "--status", "ratified", "--note", "confirmado pelo dono"])
        check("ok=true", sr_ratified.get("ok") is True, str(sr_ratified))
        check("new_ratification = ratified", sr_ratified.get("new_ratification") == "ratified", str(sr_ratified))
        check("estado promovido candidata -> ativa", sr_ratified.get("estado_after") == "ativa", str(sr_ratified))
        content_1_after = ledger_path_1.read_text(encoding="utf-8")
        check("arquivo em disco reflete ratification: ratified", "ratification: ratified" in content_1_after)
        check("arquivo em disco reflete estado: ativa", "estado: ativa" in content_1_after)
        check("nota do dono anexada ao corpo (## Transições)", "confirmado pelo dono" in content_1_after)
        lp_after = run_json(["list-pending", "--ledger-root", str(ledger_root), "--ticket", "TCK-900"])
        check("ticket ratificado não aparece mais em list-pending", lp_after.get("count") == 0, str(lp_after))

        # ------------------------------------------------------------------
        print("\n[10] set-ratification — corrected mantém estado mas marca o sinal de aprendizado (E9.2)")
        ledger_path_2 = Path(r2["ledger_path"])
        sr_corrected = run_json(["set-ratification", "--entry", str(ledger_path_2), "--status", "corrected", "--note", "dono queria XML, não CSV"])
        check("ok=true", sr_corrected.get("ok") is True, str(sr_corrected))
        check("new_ratification = corrected", sr_corrected.get("new_ratification") == "corrected", str(sr_corrected))
        check("estado NÃO promovido (fica como estava)", sr_corrected.get("estado_after") == sr_corrected.get("estado_before"), str(sr_corrected))
        content_2_after = ledger_path_2.read_text(encoding="utf-8")
        check("arquivo em disco reflete ratification: corrected", "ratification: corrected" in content_2_after)
        check("nota de correção do dono anexada", "dono queria XML" in content_2_after)

        print("\n[10b] Fechando o loop do F10 — uma entrada corrigida NUNCA sustenta 'high' como precedente futuro")
        r10b = run_json([
            "record-decision", "--ledger-root", str(ledger_root),
            "--ticket", "TCK-907", "--confidence", "high",
            "--precedent", str(ledger_path_2),  # a entrada que ACABAMOS de corrigir acima
            "--question", "q", "--decision", "d", "--justification", "j", "--context", "c",
        ])
        check("confidence final = low — decisão corrigida não se perpetua como precedente", r10b.get("confidence") == "low", str(r10b))
        check("proceed_dispatch = false", r10b.get("proceed_dispatch") is False, str(r10b))

        # ------------------------------------------------------------------
        print("\n[11] set-ratification via --ticket (sem --entry) — resolve por lookup, erro se ambíguo")
        r11 = run_json([
            "record-decision", "--ledger-root", str(ledger_root),
            "--ticket", "TCK-908",
            "--question", "q", "--decision", "d", "--justification", "j", "--context", "c",
        ])
        sr_by_ticket = run_json(["set-ratification", "--ledger-root", str(ledger_root), "--ticket", "TCK-908", "--status", "ratified"])
        check("lookup por --ticket funciona quando há exatamente 1 pendente", sr_by_ticket.get("ok") is True, str(sr_by_ticket))
        check("resolveu para o arquivo certo", sr_by_ticket.get("entry") == r11.get("ledger_path"), str(sr_by_ticket))

        sr_missing = run_json(["set-ratification", "--ledger-root", str(ledger_root), "--ticket", "TCK-NAOEXISTE", "--status", "ratified"])
        check("--ticket sem entrada pendente -> ok=false", sr_missing.get("ok") is False, str(sr_missing))

        # ------------------------------------------------------------------
        print("\n[12] Colisão de slug — mesmo ticket+decisão duas vezes nunca sobrescreve, sufixo numérico")
        dup_args = [
            "record-decision", "--ledger-root", str(ledger_root),
            "--ticket", "TCK-909",
            "--question", "pergunta duplicada", "--decision", "decisao identica para forcar colisao",
            "--justification", "j1", "--context", "c1",
        ]
        d1 = run_json(dup_args)
        d2 = run_json(dup_args)
        check("dois registros com mesmo ticket/decisão geram paths DIFERENTES", d1["ledger_path"] != d2["ledger_path"], f"{d1} / {d2}")
        check("o primeiro arquivo não foi sobrescrito (ainda existe)", Path(d1["ledger_path"]).exists())
        check("o segundo arquivo existe (sufixo numérico)", Path(d2["ledger_path"]).exists())

        # ------------------------------------------------------------------
        print("\n[12b] Front-matter injection — valor com quebra de linha em --ticket/--precedent/--areas é RECUSADO (exit != 0), nunca sanitizado silenciosamente")
        injected_precedent = str(FIXTURES / "precedent-ativa.md") + "\nratification: ratified\nestado: ativa"
        p_inject = run([
            "record-decision", "--ledger-root", str(ledger_root),
            "--ticket", "TCK-910", "--confidence", "high",
            "--precedent", injected_precedent,
            "--question", "q", "--decision", "d", "--justification", "j", "--context", "c",
        ])
        check("--precedent com \\n embutido é recusado (returncode != 0)", p_inject.returncode != 0, f"stdout={p_inject.stdout!r} stderr={p_inject.stderr!r}")
        check("nenhuma entrada TCK-910 foi escrita (falhou antes de reservar/escrever)",
              not any("tck-910" in str(f).lower() for f in ledger_root.rglob("*.md")))

        p_inject_ticket = run([
            "record-decision", "--ledger-root", str(ledger_root),
            "--ticket", "TCK-911\nconfidence: high\nratification: ratified",
            "--question", "q", "--decision", "d", "--justification", "j", "--context", "c",
        ])
        check("--ticket com \\n embutido é recusado (returncode != 0)", p_inject_ticket.returncode != 0, f"stdout={p_inject_ticket.stdout!r} stderr={p_inject_ticket.stderr!r}")

        p_inject_areas = run([
            "record-decision", "--ledger-root", str(ledger_root),
            "--ticket", "TCK-912", "--areas", "sistema-orquestrador\nratification: ratified",
            "--question", "q", "--decision", "d", "--justification", "j", "--context", "c",
        ])
        check("item de --areas com \\n embutido é recusado (returncode != 0)", p_inject_areas.returncode != 0, f"stdout={p_inject_areas.stdout!r} stderr={p_inject_areas.stderr!r}")

        # ------------------------------------------------------------------
        print("\n[12c] Concorrência real — N processos paralelos com slug idêntico: nenhum arquivo perdido, nenhum crash")
        concurrency_args = [
            "record-decision", "--ledger-root", str(ledger_root),
            "--ticket", "TCK-CONC",
            "--question", "pergunta concorrente", "--decision", "decisao identica sob concorrencia real",
            "--justification", "j", "--context", "c",
        ]
        N = 20
        with concurrent.futures.ThreadPoolExecutor(max_workers=N) as pool:
            futures = [pool.submit(run, concurrency_args) for _ in range(N)]
            results = [f.result() for f in futures]
        check("todos os N processos retornam com returncode 0 (nenhum crash/traceback cru)",
              all(p.returncode == 0 for p in results),
              "; ".join(f"rc={p.returncode} stderr={p.stderr[:200]!r}" for p in results if p.returncode != 0))
        conc_paths = set()
        for p in results:
            try:
                obj = json.loads(p.stdout.strip().splitlines()[-1])
                conc_paths.add(obj["ledger_path"])
            except Exception:
                pass
        check(f"cada processo recebeu um path ÚNICO ({len(conc_paths)}/{N})", len(conc_paths) == N, str(conc_paths))
        existing_conc_files = [p for p in conc_paths if Path(p).exists()]
        check(f"TODOS os {N} arquivos existem em disco (nenhum silenciosamente sobrescrito)", len(existing_conc_files) == N, f"{len(existing_conc_files)}/{N} sobreviveram")

        # ------------------------------------------------------------------
        print("\n[13] validate_ledger.py --json contra a árvore inteira — zero violações")
        validation = run_validate(ledger_root)
        check("nenhuma violação em nenhuma entrada emitida por gerente_oracle.py", validation.get("violation_count") == 0, str(validation))
        check(f"{validation.get('ok_count')} entradas conformes (>= 9 esperadas)", validation.get("ok_count", 0) >= 9, str(validation))

        # ------------------------------------------------------------------
        print("\n[14] Persistência em disco / sobrevivência a 'compactação' — reler do zero num processo NOVO")
        # Cada chamada acima já era um subprocess novo (sem estado compartilhado em memória
        # com o processo de teste) — esta chamada final é só a prova mais explícita: um
        # terceiro processo, sem qualquer contexto prévio, lê e confirma o estado final.
        final_check = run_json(["list-pending", "--ledger-root", str(ledger_root)])
        remaining_pending_tickets = {e["ticket"] for e in final_check["entries"]}
        check("TCK-900 (ratificado) não está mais pendente", "TCK-900" not in remaining_pending_tickets, str(final_check))
        check("TCK-901 (corrigido) não está mais pendente", "TCK-901" not in remaining_pending_tickets, str(final_check))
        check("TCK-908 (ratificado via --ticket) não está mais pendente", "TCK-908" not in remaining_pending_tickets, str(final_check))
        check("TCK-902 (nunca ratificado) continua pendente", "TCK-902" in remaining_pending_tickets, str(final_check))

    print(f"\n{'='*60}\nPASS: {len(PASS)}  FAIL: {len(FAIL)}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
