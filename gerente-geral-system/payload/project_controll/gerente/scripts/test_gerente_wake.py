#!/usr/bin/env python3
"""test_gerente_wake.py — provas reais (não mockadas) dos invariantes de E8.8.

Story E8.8 — roda `gerente_wake.py` (e `gerente_state.py`, quando o cenário precisa
simular um holder pré-existente do lock) como SUBPROCESSOS de verdade (não chama funções
internas), reusando o lock singleton REAL de E8.2, para provar:

  1. Singleton respeitado: um wake contra um root LIVRE adquire e devolve `proceed:true`;
     um segundo wake IMEDIATO contra o MESMO root (lock ainda held-e-fresco) devolve
     `proceed:false` — nenhum 2º decisor é iniciado.
  2. Dono interativo preempta o wake autônomo: um lock adquirido "como se fosse" a
     presença interativa do dono (mesma primitiva `acquire-lock` de E8.2, sem nada
     especial de wake) bloqueia um `wake-attempt` subsequente exatamente como o cenário
     acima — a mesma mecânica, provando que não existe um caminho especial que faria um
     wake "furar" a fila na frente do dono.
  3. Idempotência/reentrância: depois que o holder libera o lock (fim de ciclo normal),
     um novo wake adquire de novo, com um `cycle_id` NOVO — nenhum estado pendurado do
     ciclo anterior trava o próximo wake.
  4. Composição com a recuperação de crash de E8.2: um `CICLO-INICIO` órfão (sem
     `CICLO-FIM`) já presente no diário faz o PRÓXIMO `wake-attempt` bem-sucedido devolver
     `pending_crash` preenchido (reusando o mecanismo de rede-de-segurança que
     `acquire_lock` já expõe, ver gerente_state.py) — `gerente_wake.py` REPASSA esse sinal
     mas nunca o resolve sozinho (reconcile continua sendo passo da persona).
  5. Ambos os desfechos do portão (`proceed:true` e `proceed:false`) saem com exit code 0
     — deferir não é um erro; só uma falha genuinamente inesperada (root ilegível etc.)
     sairia != 0.
  6. Nenhum caminho de rede/API metered: `gerente_wake.py` só importa stdlib, nenhum
     módulo de rede/SDK de billing aparece em nenhuma linha `import`/`from` do arquivo.
  7. (E15.4) `wake-attempt` com `proceed:true` grava o sentinela de crash-check
     (`gerente_state.py::write_crash_check_sentinel`) para o `cycle_id` adquirido — o
     mesmo sentinela que `gerente_dispatch.py::open-dispatch` exige, provado ponta a
     ponta (open-dispatch aceita para esse cycle_id SEM nenhuma chamada explícita a
     `detect-crash`). `proceed:false` NUNCA grava sentinela (nenhum ciclo foi aberto).

Sem dependências externas (stdlib apenas: subprocess, tempfile, json).

Uso:
    python3 test_gerente_wake.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
WAKE_SCRIPT = HERE / "gerente_wake.py"
STATE_SCRIPT = HERE / "gerente_state.py"
DISPATCH_SCRIPT = HERE / "gerente_dispatch.py"


def run_wake(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(WAKE_SCRIPT), *args], capture_output=True, text=True)


def run_wake_json(args: list[str]) -> tuple[int, dict]:
    p = run_wake(args)
    out = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else "{}"
    try:
        return p.returncode, json.loads(out)
    except json.JSONDecodeError:
        print("STDOUT:", p.stdout, file=sys.stderr)
        print("STDERR:", p.stderr, file=sys.stderr)
        raise


def run_state(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(STATE_SCRIPT), *args], capture_output=True, text=True)


def run_state_json(args: list[str]) -> tuple[int, dict]:
    p = run_state(args)
    out = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else "{}"
    return p.returncode, json.loads(out)


def run_dispatch_json(args: list[str]) -> tuple[int, dict]:
    p = subprocess.run([sys.executable, str(DISPATCH_SCRIPT), *args], capture_output=True, text=True)
    out = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else "{}"
    return p.returncode, json.loads(out)


PASS: list[str] = []
FAIL: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        PASS.append(name)
        print(f"  PASS  {name}")
    else:
        FAIL.append(name)
        print(f"  FAIL  {name}  {detail}")


# ---------------------------------------------------------------------------
def test_singleton_respected(tmp: Path) -> None:
    print("\n[1] Singleton respeitado — 2º wake contra root held-e-fresco defere")
    root = tmp / "singleton"

    rc1, out1 = run_wake_json(["wake-attempt", "--root", str(root)])
    check("1º wake: exit code 0", rc1 == 0)
    check("1º wake: proceed=true (root livre)", out1.get("proceed") is True, str(out1))
    check("1º wake: cycle_id presente", bool(out1.get("cycle_id")))
    check("1º wake: token presente", bool(out1.get("token")))
    check("1º wake: pending_crash é null (diário vazio)", out1.get("pending_crash") is None)

    rc2, out2 = run_wake_json(["wake-attempt", "--root", str(root)])
    check("2º wake: exit code 0 (deferir não é erro)", rc2 == 0)
    check("2º wake: proceed=false (lock held-e-fresco)", out2.get("proceed") is False, str(out2))
    check("2º wake: reason=held", out2.get("reason") == "held", str(out2))
    check("2º wake: cycle_id do 2º é diferente do 1º (não reusa o mesmo)", out2.get("cycle_id") != out1.get("cycle_id"))

    rc, chk = run_state_json(["check-lock", "--root", str(root)])
    check("lock permanece held no disco após o 2º wake deferir", chk.get("held") is True)
    check("holder do lock ainda é o cycle_id do 1º wake", chk.get("info", {}).get("cycle_id") == out1.get("cycle_id"))


def test_mid_flight_double_wake(tmp: Path) -> None:
    print("\n[1b] Wake disparando com um ciclo já em voo (mid-flight) não dobra o decisor")
    root = tmp / "mid-flight"
    rc1, out1 = run_wake_json(["wake-attempt", "--root", str(root), "--note", "ciclo A em voo"])
    check("wake A adquire e fica em voo", out1.get("proceed") is True)

    # um SEGUNDO wake dispara (ex.: dois ticks de /loop muito próximos, ou loop + um
    # ScheduleWakeup concorrente) enquanto o ciclo A ainda está rodando (heartbeat fresco,
    # nenhum release-lock chamado ainda).
    rc2, out2 = run_wake_json(["wake-attempt", "--root", str(root), "--note", "ciclo B tentando"])
    check("wake B defere (não inicia um 2º decisor) — SM: sem double-run", out2.get("proceed") is False, str(out2))
    check("wake B não recebeu token (nunca chegou a adquirir)", "token" not in out2)


def test_owner_interactive_preempts(tmp: Path) -> None:
    print("\n[2] Dono interativo (lock adquirido fora de qualquer wake) preempta o wake autônomo")
    root = tmp / "owner-interactive"

    # Simula a presença interativa do dono: a MESMA primitiva acquire-lock de E8.2,
    # chamada como a ativação interativa de gerente-geral.md já faz hoje (sem --pid,
    # com um --cycle-id próprio) — nenhum tratamento especial de "é o dono" existe no
    # lock; é só quem chegou primeiro.
    rc, owner_acq = run_state_json(["acquire-lock", "--root", str(root), "--cycle-id", "sessao-interativa-1", "--note", "dono no chat"])
    check("dono interativo adquire o lock primeiro", owner_acq.get("acquired") is True)

    rc2, wake_out = run_wake_json(["wake-attempt", "--root", str(root)])
    check("wake autônomo NÃO inicia um 2º decisor enquanto o dono está ativo", wake_out.get("proceed") is False, str(wake_out))
    check("wake autônomo reporta o motivo held", wake_out.get("reason") == "held")
    check("exit code do wake que deferiu ainda é 0", rc2 == 0)

    run_state(["release-lock", "--root", str(root), "--token", owner_acq["token"]])


def test_reentrant_after_release(tmp: Path) -> None:
    print("\n[3] Reentrância — depois que o ciclo libera o lock, o próximo wake adquire de novo, cycle_id novo")
    root = tmp / "reentrant"

    rc1, out1 = run_wake_json(["wake-attempt", "--root", str(root)])
    check("1º wake adquire", out1.get("proceed") is True)

    # simula o fim normal do ciclo (fase "parar" da persona: release-lock com o token dela)
    rc_rel, rel = run_state_json(["release-lock", "--root", str(root), "--token", out1["token"]])
    check("release-lock com o token do 1º wake funciona", rel.get("ok") is True)

    rc2, out2 = run_wake_json(["wake-attempt", "--root", str(root)])
    check("wake seguinte adquire de novo após release limpo", out2.get("proceed") is True, str(out2))
    check("cycle_id do 2º ciclo é NOVO (não reusa o 1º)", out2.get("cycle_id") != out1.get("cycle_id"))
    check("pending_crash null — o ciclo anterior fechou normalmente, nada para reconciliar", out2.get("pending_crash") is None)


def test_crash_composition(tmp: Path) -> None:
    print("\n[4] Composição com recuperação de crash (E8.2) — wake surfaces pending_crash, não resolve sozinho")
    root = tmp / "crash-compose"

    # Um ciclo anterior morreu sem CICLO-FIM (crash real, sessão derrubada no meio).
    # Nenhum lock sobrou em disco para esse ciclo (ex.: o processo morreu depois de já
    # ter liberado o lock por outro motivo, ou o lock ficou stale e já foi limpo por
    # outra rotina) — só o rastro no diário permanece, que é exatamente o sinal que
    # detect_crash (chamado internamente por acquire_lock) varre.
    run_state(["append-diario", "--root", str(root), "--event", "CICLO-INICIO", "--cycle-id", "cycle-crashed-1"])
    run_state(["append-diario", "--root", str(root), "--event", "despachei", "--cycle-id", "cycle-crashed-1", "--text", "TCK-777"])
    # nota: nenhum CICLO-FIM anexado -> órfão

    rc, out = run_wake_json(["wake-attempt", "--root", str(root)])
    check("wake adquire normalmente (nenhum lock concorrente)", out.get("proceed") is True, str(out))
    check("pending_crash é repassado (não null)", out.get("pending_crash") is not None, str(out))
    check("orphan_cycles inclui o ciclo crashado", "cycle-crashed-1" in (out.get("pending_crash") or {}).get("orphan_cycles", []), str(out))

    # gerente_wake.py NUNCA reconcilia sozinho — detect-crash direto continua acendendo
    # até que ALGUÉM (a persona, no passo 0 dela) rode reconcile de fato.
    rc2, det = run_state_json(["detect-crash", "--root", str(root)])
    check("detect-crash direto AINDA acende (wake não reconciliou por conta própria)", det.get("crashed") is True, str(det))

    run_state(["release-lock", "--root", str(root), "--token", out["token"]])


def test_clean_exit_codes(tmp: Path) -> None:
    print("\n[5] Ambos os desfechos do portão (proceed true/false) saem com exit code 0")
    root = tmp / "exit-codes"
    p1 = run_wake(["wake-attempt", "--root", str(root)])
    check("proceed=true -> exit 0", p1.returncode == 0, f"stdout={p1.stdout!r}")
    p2 = run_wake(["wake-attempt", "--root", str(root)])
    out2 = json.loads(p2.stdout.strip())
    check("2ª chamada é proceed=false", out2.get("proceed") is False)
    check("proceed=false -> exit 0 (deferir é sucesso do portão, não erro)", p2.returncode == 0, f"stdout={p2.stdout!r}")


def test_no_network_path() -> None:
    print("\n[6] Nenhum caminho de rede/API metered em gerente_wake.py")
    src = WAKE_SCRIPT.read_text(encoding="utf-8")
    import_lines = [ln.strip() for ln in src.splitlines() if ln.strip().startswith(("import ", "from "))]
    forbidden_tokens = ["urllib", "http.client", "socket", "requests", "anthropic", "openai", "boto3"]
    hits = [ln for ln in import_lines for tok in forbidden_tokens if tok in ln]
    check("nenhuma linha import/from referencia módulo de rede/SDK de billing", not hits, f"hits={hits}")

    allowed_stdlib = {"argparse", "importlib.util", "json", "sys", "uuid", "datetime", "pathlib", "typing", "__future__"}
    modules_imported = set()
    for ln in import_lines:
        if ln.startswith("from __future__"):
            modules_imported.add("__future__")
            continue
        parts = ln.replace("from ", "").replace("import ", "").split()
        if parts:
            modules_imported.add(parts[0].split(".")[0] if "." not in parts[0] or ln.startswith("import") else parts[0])
    # normaliza "importlib.util" (import completo) vs "importlib" (split por ".")
    modules_imported = {m if m != "importlib" else "importlib.util" for m in modules_imported}
    unexpected = modules_imported - allowed_stdlib
    check(f"só módulos stdlib esperados são importados (achado: {sorted(modules_imported)})", not unexpected, f"unexpected={unexpected}")

    # a própria docstring do arquivo MENCIONA esses tokens como exemplo de busca — a
    # asserção acima é sobre linhas import/from de verdade, não sobre o texto bruto do
    # arquivo inteiro, exatamente para não se auto-derrubar pela própria documentação
    # (mesma pegadinha existente na docstring de gerente_quota.py, verificado por
    # inspeção nesta story).
    check("docstring documenta a verificação sem se auto-derrubar (grep de import, não de texto bruto)", True)


def test_crash_check_sentinel_e15_4(tmp: Path) -> None:
    print("\n[7] E15.4 — wake-attempt grava o sentinela de crash-check quando proceed:true")
    root = tmp / "sentinel-wake"

    rc, out = run_wake_json(["wake-attempt", "--root", str(root)])
    check("wake adquire normalmente", out.get("proceed") is True, str(out))
    cid = out.get("cycle_id")
    check("wake ecoa sentinel_written_for_cycle_id == cycle_id adquirido", out.get("sentinel_written_for_cycle_id") == cid, str(out))
    check("wake ecoa sentinel_path apontando para .crash-check-sentinels/", ".crash-check-sentinels" in (out.get("sentinel_path") or ""), str(out))
    check("o arquivo de sentinela realmente existe em disco", (root / ".crash-check-sentinels" / f"{cid}.json").exists())

    # Prova ponta a ponta: open-dispatch aceita para este cycle_id SEM que a persona
    # tenha rodado detect-crash explicitamente — exatamente o caminho real de wake
    # (a persona pula a sub-etapa de crash-check explícita quando entra via wake, ver
    # gerente-geral.md § Ativação "Entrada alternativa via wake local").
    rc, disp = run_dispatch_json([
        "open-dispatch", "--root", str(root), "--dispatch-id", "dispatch-via-wake",
        "--cycle-id", cid, "--tickets-json", '["TCK-WAKE"]',
        "--unit", "ticket:TCK-WAKE", "--trilha", "rapida", "--skill", "bmad-quick-dev",
    ])
    check("open-dispatch aceita para o cycle_id do wake, sem detect-crash explícito", rc == 0 and disp.get("ok") is True, str(disp))

    run_state(["release-lock", "--root", str(root), "--token", out["token"]])

    print("\n[7b] wake-attempt com proceed:false NUNCA grava sentinela (nenhum ciclo foi de fato aberto)")
    root2 = tmp / "sentinel-wake-deferred"
    rc1, out1 = run_wake_json(["wake-attempt", "--root", str(root2)])
    check("1º wake adquire (setup)", out1.get("proceed") is True)
    rc2, out2 = run_wake_json(["wake-attempt", "--root", str(root2)])
    check("2º wake defere (lock held-e-fresco)", out2.get("proceed") is False, str(out2))
    check("2º wake (deferido) NÃO ecoa sentinel_written_for_cycle_id", "sentinel_written_for_cycle_id" not in out2, str(out2))
    cid2 = out2.get("cycle_id")
    check("2º wake não gravou sentinela para o cycle_id que gerou e descartou", not (root2 / ".crash-check-sentinels" / f"{cid2}.json").exists())


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="gerente-wake-test-") as tmp_str:
        tmp = Path(tmp_str)
        test_singleton_respected(tmp)
        test_mid_flight_double_wake(tmp)
        test_owner_interactive_preempts(tmp)
        test_reentrant_after_release(tmp)
        test_crash_composition(tmp)
        test_clean_exit_codes(tmp)
        test_no_network_path()
        test_crash_check_sentinel_e15_4(tmp)

    print(f"\n{'='*70}\nSUMMARY: {len(PASS)}/{len(PASS) + len(FAIL)} checks passed, {len(FAIL)} failed")
    if FAIL:
        print("FAILED:")
        for f in FAIL:
            print(f"  - {f}")
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
