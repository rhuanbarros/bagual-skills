#!/usr/bin/env python3
"""gerente_wake.py — E8.8 portão de entrada do wake local (loop/ScheduleWakeup).

Story E8.8 (ideias/sistema-artifacts/E8-8-wake-local.md), PRD 00 FR-1 (mecanismo) /
decisão §8-Q2 (LOCAL), ideias/epics.md Epic E8 (última story — fecha o épico). Wake local
significa: dentro de uma SESSÃO local viva e aberta (a máquina/sessão precisa estar
rodando — constraint aceita, ver `wake.md`), o Gerente se auto-pausa/acorda via `loop`
(skill nativa) ou `CronCreate` (agendamento nativo, session-only, in-memory, expira em 7
dias, só dispara com o REPL ocioso) — NUNCA via cron do SO nem via rotina cloud
(`schedule`/routines são explicitamente FORA per F1/§8-Q2, ver `wake.md` § "Por que não
cron/cloud"). Este módulo é o "portão de entrada" que um wake chama ANTES de gastar um
turno inteiro do Gerente (Opus, o mais caro dos dois — a execução roda em Sonnet): decide
BARATO, sem spawnar nenhum sub-agente, se vale a pena acordar o Gerente agora.

Comandos:
  wake-attempt   tenta adquirir o lock singleton (REUSA gerente_state.py::acquire_lock,
                 a mesma primitiva atômica de E8.2 — não uma reimplementação) em nome do
                 wake. `proceed: true` + `cycle_id`/`token` prontos para repassar à
                 ativação de `.claude/agents/gerente-geral.md` (ela pula a sub-etapa
                 `acquire-lock` do seu próprio passo 0 e usa o que já foi adquirido aqui —
                 ver `wake.md` § "Composição com o lock singleton"). `proceed: false`
                 quando o lock já está held-e-fresco (dono interativo OU outro ciclo já em
                 voo) — o wake NÃO spawna o Gerente, DEFERE de forma limpa, sem consumir
                 nenhum turno do agente caro. Sempre exit 0 quando a decisão foi tomada com
                 sucesso (proceed true OU false — ambos são desfechos "limpos" do portão,
                 nunca um erro); exit 1 só em falha genuína e inesperada.

Composição com E8.2 (crash recovery): `acquire_lock` já cruza com `detect_crash`
internamente (ver docstring de `acquire_lock` em `gerente_state.py`) — se o lock que este
wake acabou de adquirir era um lock STALE reclamado (heartbeat morto), a resposta já traz
`pending_crash` preenchido. `wake-attempt` REPASSA esse campo tal e qual (não decide nem
reconcilia sozinho — reconciliar é julgamento do Gerente, feito no passo 0 da sua própria
Ativação, exatamente como já acontece hoje independente de wake).

Composição com E15.4 (guard mecânico de `open-dispatch`): quando `proceed: true`,
`wake-attempt` grava o sentinela de crash-check (`gerente_state.py::
write_crash_check_sentinel`, import direto, mesmo padrão de reuso deste arquivo) para o
`cycle_id` que acabou de adquirir — o mesmo sentinela que `detect-crash`/`reconcile`
gravariam explicitamente no caminho não-wake. Sem isso, o caminho de wake nunca chamaria
`detect-crash` diretamente (a persona pula essa sub-etapa quando entra via wake — ver
`gerente-geral.md` § Ativação), e `gerente_dispatch.py::open-dispatch` recusaria todo
despacho do ciclo apesar do crash-check já ter rodado de fato (dentro de `acquire_lock`).
`proceed: false` NUNCA grava sentinela — nenhum ciclo novo foi de fato aberto nesse ramo
(o `cid` gerado é descartado, `Agent(subagent_type='gerente-geral')` nunca é invocado).

100% local, cota só de assinatura — nenhum caminho deste módulo faz uma chamada de rede ou
invoca uma API metered. `wake-attempt` só chama `acquire_lock`/`now_iso` (funções puras de
arquivo local, reusadas por IMPORT direto de `gerente_state.py`, mesmo padrão que
`gerente_quota.py`/`gerente_briefing.py` já usam) — nenhum SDK de billing, nenhuma chamada
HTTP em lugar nenhum deste arquivo (grep por `urllib`/`http`/`socket`/`requests`/
`anthropic`/`openai`/`api_key` neste módulo dá zero resultados fora deste comentário —
verificado por `test_gerente_wake.py::test_no_network_path`, não só alegado em prosa).

Só biblioteca padrão (stdlib) — nenhuma dependência externa, mesma convenção dos scripts
irmãos deste diretório.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

SCRIPT_DIR = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# Reuso de gerente_state.py (import direto do arquivo irmão — não cópia colada, mesmo
# padrão que gerente_quota.py/gerente_briefing.py já usam para esta mesma composição).
# ---------------------------------------------------------------------------
def _gerente_state():
    path = SCRIPT_DIR / "gerente_state.py"
    if not path.exists():
        print(f"erro: gerente_state.py não encontrado em {path} — não é possível reusar acquire_lock", file=sys.stderr)
        sys.exit(2)
    spec = importlib.util.spec_from_file_location("gerente_state", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_GS = None


def _gs():
    global _GS
    if _GS is None:
        _GS = _gerente_state()
    return _GS


def new_cycle_id(prefix: str = "wake") -> str:
    """Gera um cycle_id único para este wake — mesmo vocabulário `cycle_id` usado por
    todo o resto de `project_controll/gerente/` (write-snapshot/append-diario/dispatch),
    só com um prefixo `wake-` para ficar óbvio, em `diario.md`, que este ciclo específico
    foi disparado por um wake autônomo (loop/ScheduleWakeup), não por ativação
    interativa/headless direta. Não é consumido mecanicamente por nenhum outro script —
    é só uma convenção de rotulagem para leitura humana no diário/Briefing."""
    ts_compact = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S")
    return f"{prefix}-{ts_compact}-{uuid.uuid4().hex[:6]}"


# ---------------------------------------------------------------------------
# wake-attempt
# ---------------------------------------------------------------------------
def wake_attempt(root: Path, note: str, stale_after_seconds: float, pid: Optional[int], cycle_id: Optional[str]) -> dict:
    gs = _gs()
    cid = cycle_id or new_cycle_id()
    result = gs.acquire_lock(root, stale_after_seconds, pid, note, cycle_id=cid)

    if result.get("acquired"):
        # Story E15.4 — guard mecânico de open-dispatch: `acquire_lock` já roda o
        # crash-check internamente (via `detect_crash`, ver docstring dele) em nome deste
        # `cid` — este wake É o ponto em que esse crash-check aconteceu para o ciclo novo,
        # então grava aqui o MESMO sentinela que `detect-crash`/`reconcile` gravariam,
        # reusando `write_crash_check_sentinel` por import direto (nunca reimplementado).
        # Sem isto, o fluxo de wake nunca chamaria `detect-crash` explicitamente (a
        # persona PULA essa sub-etapa no caminho de wake — ver `guidance` abaixo e
        # `gerente-geral.md` § Ativação), e `open-dispatch` recusaria todo despacho do
        # ciclo apesar do crash-check já ter, de fato, rodado.
        sentinel_path = gs.write_crash_check_sentinel(root, cid, source="wake-attempt", detail={"pending_crash": result.get("pending_crash")})
        return {
            "ok": True,
            "proceed": True,
            "cycle_id": cid,
            "token": result["token"],
            "acquired_at": result["info"]["acquired_at"],
            "pending_crash": result.get("pending_crash"),
            "sentinel_written_for_cycle_id": cid,
            "sentinel_path": str(sentinel_path),
            "note": note,
            "guidance": (
                "Lock adquirido pelo wake — proceda a invocar Agent(subagent_type="
                "'gerente-geral') com este cycle_id/token no prompt. A persona PULA a "
                "sub-etapa 'acquire-lock' do passo 0 da Ativação (já feita aqui) mas "
                "continua rodando o resto do passo 0 normalmente — em especial, se "
                "pending_crash não for null, ela reconcilia ANTES de decidir qualquer "
                "trabalho novo, exatamente como faria se tivesse detectado o crash "
                "sozinha. O sentinela de crash-check (E15.4) para este cycle_id já foi "
                "gravado por este wake-attempt — a persona NÃO precisa (nem deve) rodar "
                "`detect-crash --cycle-id` de novo só para satisfazer o guard de "
                "open-dispatch. Ver project_controll/gerente/wake.md."
            ),
        }

    return {
        "ok": True,
        "proceed": False,
        "cycle_id": cid,
        "reason": result.get("reason"),
        "detail": result.get("detail"),
        "holder": result.get("holder"),
        "guidance": (
            "Lock held-e-fresco (dono interativo ou outro ciclo já em voo) — o wake "
            "DEFERE: não invoque Agent(subagent_type='gerente-geral'). Nenhum turno do "
            "agente caro foi consumido; nenhuma chamada de API (metered ou não) "
            "aconteceu — só uma tentativa de mkdir/rename local. Tente de novo no "
            "próximo tick do loop/wake."
        ),
    }


def cmd_wake_attempt(args: argparse.Namespace) -> int:
    root = Path(args.root)
    try:
        out = wake_attempt(root, args.note, args.stale_after_seconds, args.pid, args.cycle_id)
    except Exception as exc:  # defesa: um erro genuíno e inesperado é o único caso não-0
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(out, ensure_ascii=False))
    return 0  # proceed:true e proceed:false são AMBOS desfechos limpos do portão


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    pw = sub.add_parser("wake-attempt", help="tenta adquirir o lock em nome de um wake local; decide proceed true/false")
    pw.add_argument("--root", default="project_controll/gerente", help="diretório de estado do Gerente (default: project_controll/gerente)")
    pw.add_argument("--note", default="wake local (E8.8 — loop/ScheduleWakeup)")
    pw.add_argument("--pid", type=int, default=None, help=(
        "default: None (NÃO auto-preenche com os.getpid() do próprio script — achado "
        "real em teste headless desta story: gerente_wake.py é um processo CURTO-VIVIDO "
        "que já terminou quando um wake seguinte roda; se o lock carregasse esse PID, "
        "pid_alive() o veria morto e lock_is_stale() reclamaria o lock IMEDIATAMENTE, "
        "quebrando a exclusão mútua na prática. Mesma convenção que a persona já usa em "
        "gerente-geral.md passo 0 — nunca passa --pid a acquire-lock — porque nenhum "
        "processo de SO único representa 'o Gerente' de forma confiável neste harness de "
        "agente/tool-calls; staleness cai só no critério de heartbeat, ver "
        "gerente_state.py::lock_is_stale)"
    ))
    pw.add_argument("--cycle-id", default=None, help="default: gerado automaticamente (wake-<ts>-<hex>)")
    pw.add_argument("--stale-after-seconds", type=float, default=None, help="default: DEFAULT_STALE_AFTER_SECONDS de gerente_state.py")
    pw.set_defaults(func=cmd_wake_attempt)

    return p


def main(argv: Optional[list] = None) -> int:
    args = build_parser().parse_args(argv)
    if getattr(args, "stale_after_seconds", None) is None and args.cmd == "wake-attempt":
        args.stale_after_seconds = _gs().DEFAULT_STALE_AFTER_SECONDS
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
