#!/usr/bin/env python3
"""gerente_dispatch.py — E8.4 contrato de despacho via marcador em disco.

Story E8.4 (ideias/sistema-artifacts/E8-4-contrato-despacho.md), PRD 00 FR-8 (+ lado
Sonnet do FR-7), ideias/epics.md Epic E8. Formaliza a interface pela qual o Gerente Geral
(`.claude/skills/bagual-gerente-geral/SKILL.md`, fase "despachar"/"revisar") entrega UMA unidade de
trabalho (epic/multi-epic/Ticket avulso) ao Orquestrador de Execução (hoje
`bagual-epic-runner`/`bmad-quick-dev`/etc., PRD 03 quando existir) e recolhe o RESULTADO
de volta — sempre por MARCADOR EM DISCO, nunca por valor de retorno de função — resiliente
a compactação de contexto no meio do despacho. Mesmo padrão de dispatch file-mediated já
provado em `_bmad/custom/bmad-code-review.toml` (Epic E2, o "kill" do deadlock do
code-review) e usado pelo QA gate (`bagual-qa-run`): um arquivo de PAYLOAD (aqui,
`request.yaml`/`result.yaml`) + um marcador de CONCLUSÃO vazio (`DONE.marker`) escrito
como ÚLTIMA ação, depois que o payload já está durável em disco.

Layout em disco (por despacho, sob `project_controll/gerente/dispatches/{dispatch_id}/`):
  request.yaml   escrito por `open-dispatch` — a UNIDADE, o(s) Ticket(s), a trilha, o
                 worktree alvo, o skill mapeado, o modelo do executor (sempre `sonnet`).
  result.yaml    escrito por `close-dispatch` — outcome (sucesso|falhou|pendencias),
                 veredito em texto, pendências, evidência (commit/story-file/etc).
  DONE.marker    escrito por `close-dispatch` DEPOIS de `result.yaml` já estar durável
                 (write_atomic = temp+flush+fsync+rename) — a GARANTIA DE ORDEM que torna
                 o contrato seguro: um leitor nunca deve observar DONE.marker sem um
                 result.yaml completo atrás dele.

DETECÇÃO DUAL DE CONCLUSÃO (mesma lição do E2.2/F5, aplicada aqui ao despacho de execução
em vez das 3 camadas do code-review): o marcador em disco (`DONE.marker`) é o sinal
SECUNDÁRIO/payload — nunca usado como único sinal, nunca poll infinito. O sinal
PRIMÁRIO/bloqueante é o retorno da própria tool `Agent` que a persona usa para spawnar o
sub-agente executor — isso é responsabilidade da PERSONA (`gerente-geral.md`), não deste
script: este módulo só fornece `read-result` (lê o marcador, nunca espera por ele) e
`reconcile-orphan-dispatch` (para o caso em que o Agent tool já retornou/morreu MAS o
DONE.marker nunca apareceu — executor morto/compactação no meio do despacho, sem ter
chegado a chamar `close-dispatch`). Ver `project_controll/gerente/dispatch-contract.md`
para o contrato completo (schema, wiring da persona, garantia de ordem, forward-compat
com o supervisor multi-epic do E10).

Comandos:
  open-dispatch             abre um despacho: escreve request.yaml, devolve `dispatch_entry`
                             pronto para a persona repassar ao PRÓXIMO
                             `gerente_state.py write-snapshot --dispatches-json` (mesmo
                             padrão de E8.3: quem escreve `estado-atual.yaml` inteiro
                             continua sendo só `write-snapshot`, nunca um segundo dono).
                             Story E15.4 — EXIGE um sentinela de crash-check já gravado
                             para `--cycle-id` (`gerente_state.py detect-crash`/
                             `reconcile --cycle-id`, ou `gerente_wake.py wake-attempt` no
                             caminho de wake); recusa (ok:false, exit 1, nada escrito) se
                             ausente — nunca despacha em nome de um ciclo que ainda não
                             passou pelo crash-check.
  close-dispatch             fecha um despacho: escreve result.yaml (durável) e SÓ DEPOIS
                             DONE.marker — garantia de ordem, nunca o inverso.
  read-result                lê o resultado de um despacho: `done` é decidido SÓ pela
                             presença do DONE.marker, nunca por poll — chamada única,
                             sem retry embutido (quem decide esperar ou não é a persona).
  list-inflight               lista despachos com request.yaml presente e DONE.marker
                             ausente (opcionalmente filtrado por --cycle-id).
  reconcile-orphan-dispatch  diagnostica UM despacho suspeito de órfão (sem DONE.marker) —
                             cruza contra board.yaml/worktree, nunca move Ticket sozinho
                             (recomenda `bagual-tickets`, mesma disciplina de
                             `gerente_state.py reconcile`, que TAMBÉM foi estendido nesta
                             story para cruzar o DONE.marker de cada despacho rastreado em
                             `estado-atual.yaml` — os dois caminhos convergem no mesmo
                             sinal de disco, não são mecanismos paralelos divergentes).

Escrita atômica: reusa `write_atomic`/`now_iso`/`yaml_scalar`/`dump_flat_dict_item`/
`parse_estado`/`ticket_status_in_board` de `gerente_state.py` (E8.2) por IMPORT direto do
arquivo irmão — mesmo padrão de reuso que `gerente_quota.py` (E8.3) já usa. Nenhuma
duplicação de primitiva de escrita atômica ou de parser YAML — só o pequeno wrapper de
DUMP (`_dump_doc`) é próprio deste módulo, porque `dump_estado` de `gerente_state.py` é
hardcoded para o schema de `estado-atual.yaml` (ordem de campos fixa via
`ESTADO_TOP_KEYS`); o parser (`parse_estado`) já é genérico o bastante para ler
`request.yaml`/`result.yaml` sem nenhuma mudança.

Só biblioteca padrão (stdlib) — nenhuma dependência externa, mesma convenção dos scripts
irmãos deste diretório.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Optional

SCRIPT_DIR = Path(__file__).resolve().parent

DISPATCHES_DIRNAME = "dispatches"

# `dispatch_id` vira diretamente um componente de path (`root / "dispatches" /
# dispatch_id`) — achado de auto-revisão adversarial (Story E8.4): um `--dispatch-id`
# explícito malformado (ex.: "../../etc") poderia escapar do diretório pretendido. O
# id AUTO-GERADO (`_gen_dispatch_id`) já é seguro por construção; esta regex só existe
# para blindar o caminho de `--dispatch-id` explícito (usado por retomadas/testes).
DISPATCH_ID_RE = re.compile(r"^[A-Za-z0-9_.-]+$")
REQUEST_FILENAME = "request.yaml"
RESULT_FILENAME = "result.yaml"
DONE_FILENAME = "DONE.marker"

VALID_TRILHAS = ["rapida", "spec", "epic", "wds", "correct-course"]
VALID_OUTCOMES = ["sucesso", "falhou", "pendencias"]


# ---------------------------------------------------------------------------
# Reuso de gerente_state.py (import direto do arquivo irmão — não cópia colada, mesmo
# padrão que gerente_quota.py já usa para reusar E8.2).
# ---------------------------------------------------------------------------
def _gerente_state():
    path = SCRIPT_DIR / "gerente_state.py"
    if not path.exists():
        print(f"erro: gerente_state.py não encontrado em {path} — não é possível reusar write_atomic/parse_estado", file=sys.stderr)
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


# Reuso de gerente_quota.py (import direto do arquivo irmão — mesmo padrão de
# `_gerente_state()` acima, e o mesmo padrão que `gerente_quota.py` já usa para reusar
# `gerente_state.py`). Story E15.2: `close-dispatch --tokens-used` chama `record_usage()`
# por IMPORT DIRETO (nunca subprocess) para que a acumulação de cota aconteça na mesma
# transação de processo que fecha o despacho — ver `cmd_close_dispatch`.
def _gerente_quota():
    path = SCRIPT_DIR / "gerente_quota.py"
    if not path.exists():
        print(f"erro: gerente_quota.py não encontrado em {path} — não é possível reusar record_usage/resolve_safety_multiplier", file=sys.stderr)
        sys.exit(2)
    spec = importlib.util.spec_from_file_location("gerente_quota", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_GQ = None


def _gq():
    global _GQ
    if _GQ is None:
        _GQ = _gerente_quota()
    return _GQ


def now_iso() -> str:
    return _gs().now_iso()


def write_atomic(path: Path, text: str) -> None:
    _gs().write_atomic(path, text)


def _dispatch_dir(root: Path, dispatch_id: str) -> Path:
    return root / DISPATCHES_DIRNAME / dispatch_id


def _gen_dispatch_id() -> str:
    ts = time.strftime("%Y%m%d-%H%M%S")
    return f"dispatch-{ts}-{uuid.uuid4().hex[:8]}"


def _validate_dispatch_id(dispatch_id: str) -> Optional[str]:
    """Devolve uma mensagem de erro se `dispatch_id` não for seguro para virar um
    componente de path, ou None se for válido. `..` sozinho passaria pela classe de
    caracteres de DISPATCH_ID_RE (só contém '.'), por isso é checado à parte."""
    if not dispatch_id or dispatch_id in (".", ".."):
        return "dispatch_id vazio ou igual a '.'/'..' — inválido"
    if not DISPATCH_ID_RE.match(dispatch_id):
        return "dispatch_id contém caracteres não permitidos (só [A-Za-z0-9_.-])"
    if ".." in dispatch_id:
        return "dispatch_id não pode conter '..' (risco de path traversal)"
    return None


def _load_json_list(raw: str, flag: str) -> list:
    try:
        v = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(json.dumps({"ok": False, "error": f"{flag} não é JSON válido: {exc}"}))
        sys.exit(2)
    if not isinstance(v, list):
        print(json.dumps({"ok": False, "error": f"{flag} deve ser uma lista JSON"}))
        sys.exit(2)
    return v


def _load_json_dict(raw: str, flag: str) -> dict:
    try:
        v = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(json.dumps({"ok": False, "error": f"{flag} não é JSON válido: {exc}"}))
        sys.exit(2)
    if not isinstance(v, dict):
        print(json.dumps({"ok": False, "error": f"{flag} deve ser um objeto JSON"}))
        sys.exit(2)
    return v


# ---------------------------------------------------------------------------
# Dump YAML mínimo (mesmo estilo de dump_estado, mas parametrizado por top_keys — não
# hardcoded ao schema de estado-atual.yaml). Reusa yaml_scalar/dump_flat_dict_item de
# gerente_state.py — só o laço de composição é próprio deste módulo.
# ---------------------------------------------------------------------------
def _dump_doc(doc: dict, top_keys: list[str], header: str) -> str:
    gs = _gs()
    lines = [header.rstrip("\n"), ""]
    for key in top_keys:
        if key not in doc:
            continue
        v = doc[key]
        if isinstance(v, dict):
            if not v:
                lines.append(f"{key}: {{}}")
            else:
                lines.append(f"{key}:")
                for k2, v2 in v.items():
                    lines.append(f"  {k2}: {gs.yaml_scalar(v2)}")
        elif isinstance(v, list):
            if not v:
                lines.append(f"{key}: []")
            else:
                lines.append(f"{key}:")
                for item in v:
                    if isinstance(item, dict):
                        lines.extend(gs.dump_flat_dict_item(item, 1))
                    else:
                        lines.append(f"  - {gs.yaml_scalar(item)}")
        else:
            lines.append(f"{key}: {gs.yaml_scalar(v)}")
    return "\n".join(lines) + "\n"


REQUEST_TOP_KEYS = [
    "schema_version", "dispatch_id", "opened_at", "cycle_id",
    "tickets", "unit", "trilha", "worktree", "skill", "model", "status", "note",
]
REQUEST_HEADER = """\
# request.yaml — despacho ABERTO (Story E8.4, PRD 00 FR-8)
# Escrito por gerente_dispatch.py open-dispatch (escrita atômica). NUNCA editado à mão.
# `tickets` é sempre lista (mesmo para 1 Ticket só) — forward-compat com despacho
# multi-epic/multi-Ticket do supervisor E10, que este contrato NÃO implementa ainda.
# Ver project_controll/gerente/dispatch-contract.md para o contrato completo.
"""

RESULT_TOP_KEYS = [
    "schema_version", "dispatch_id", "closed_at", "outcome", "verdict",
    "pending_items", "evidence", "closed_by",
]
RESULT_HEADER = """\
# result.yaml — resultado do despacho (Story E8.4, PRD 00 FR-8)
# Escrito por gerente_dispatch.py close-dispatch ANTES de DONE.marker (garantia de
# ordem — um leitor nunca deve ver DONE.marker sem este arquivo já durável atrás dele).
# `outcome` ∈ sucesso|falhou|pendencias. Ver dispatch-contract.md para o contrato completo.
"""


# ---------------------------------------------------------------------------
# open-dispatch
# ---------------------------------------------------------------------------
def cmd_open_dispatch(args: argparse.Namespace) -> int:
    root = Path(args.root)
    tickets = _load_json_list(args.tickets_json, "--tickets-json")
    if args.trilha not in VALID_TRILHAS:
        print(json.dumps({"ok": False, "error": f"--trilha deve ser um de {VALID_TRILHAS}"}))
        return 2

    # ------------------------------------------------------------------
    # Story E15.4 — guard mecânico: nenhuma decisão nova (nenhum despacho) antes de
    # detect-crash/reconcile. O gap real NUNCA foi `acquire-lock` (E8.2 rejeitou
    # corretamente bloqueá-lo — quebraria inspeção de estado); era este passo seguinte:
    # nada impedia a persona de pular de "adquiri o lock" direto para `open-dispatch` sem
    # nunca ter rodado `gerente_state.py detect-crash`/`reconcile` (ou, no caminho de
    # wake, `gerente_wake.py wake-attempt`, que grava o mesmo sentinela por composição).
    # Checagem ANTES de qualquer escrita — nem `dispatch_id` é gerado/validado ainda, nem
    # `request.yaml` é tocado; recusa limpa (ok:false, exit 1), nunca meio-aberto.
    if not _gs().has_crash_check_sentinel(root, args.cycle_id):
        print(json.dumps({
            "ok": False,
            "error": (
                "open-dispatch recusado (Story E15.4): nenhum sentinela de crash-check "
                f"encontrado para cycle_id={args.cycle_id!r}. Rode "
                "`gerente_state.py detect-crash --cycle-id <este-cycle-id>` (ou "
                "`reconcile --cycle-id <este-cycle-id>` se um crash foi encontrado, ou "
                "confie no sentinela já gravado por `gerente_wake.py wake-attempt` no "
                "caminho de wake) ANTES de abrir qualquer despacho novo para este ciclo "
                "— nunca pule direto de 'adquiri o lock' para 'despachei'."
            ),
            "cycle_id": args.cycle_id,
        }, ensure_ascii=False))
        return 1

    dispatch_id = args.dispatch_id or _gen_dispatch_id()
    err = _validate_dispatch_id(dispatch_id)
    if err:
        print(json.dumps({"ok": False, "error": err, "dispatch_id": dispatch_id}))
        return 2
    ddir = _dispatch_dir(root, dispatch_id)
    req_path = ddir / REQUEST_FILENAME
    if req_path.exists():
        print(json.dumps({
            "ok": False,
            "error": "dispatch_id já existe — nunca reusar um dispatch_id vivo/antigo (mesma regra do E2.1 para review-run-dir); gere um novo (omita --dispatch-id)",
            "dispatch_id": dispatch_id,
        }))
        return 1

    ts = now_iso()
    doc = {
        "schema_version": 1,
        "dispatch_id": dispatch_id,
        "opened_at": ts,
        "cycle_id": args.cycle_id,
        "tickets": tickets,
        "unit": args.unit,
        "trilha": args.trilha,
        "worktree": args.worktree,
        "skill": args.skill,
        "model": args.model,
        "status": "aberto",
        "note": args.note,
    }
    write_atomic(req_path, _dump_doc(doc, REQUEST_TOP_KEYS, REQUEST_HEADER))

    # Pronto para a persona repassar ao PRÓXIMO `gerente_state.py write-snapshot
    # --dispatches-json` — mesmo padrão de write_snapshot_quota_args do E8.3: este script
    # NUNCA escreve estado-atual.yaml diretamente (write-snapshot continua sendo o único
    # dono do arquivo inteiro, evitando o bug de dois-escritores documentado em
    # decisions.md § E8.3). NÃO inclui `tickets` (lista) aqui de propósito — achado real
    # de auto-revisão: o mini-serializer YAML de estado-atual.yaml só suporta
    # dict-de-escalares em 1 nível (ESTADO_TOP_KEYS/dump_flat_dict_item), então uma lista
    # aninhada dentro de um item de `dispatches[]` seria serializada incorretamente como
    # `str(list)`. A lista COMPLETA de tickets já vive, autoritativa, em request.yaml —
    # `dispatch_id` é o ponteiro que `gerente_state.py::reconcile` resolve para recuperá-la
    # quando precisar (ver a extensão dessa função nesta mesma story). `ticket` (singular,
    # o primeiro/primário) continua no retrato só para leitura humana rápida/back-compat.
    dispatch_entry = {
        "dispatch_id": dispatch_id,
        "ticket": tickets[0] if tickets else None,
        "unit": args.unit,
        "trilha": args.trilha,
        "worktree": args.worktree,
        "status": "em-voo",
        "started_at": ts,
    }
    print(json.dumps({
        "ok": True,
        "dispatch_id": dispatch_id,
        "request_path": str(req_path),
        "dispatch_entry": dispatch_entry,
        "dispatch_entry_json": json.dumps(dispatch_entry, ensure_ascii=False),
    }, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------------------
# close-dispatch
# ---------------------------------------------------------------------------
def cmd_close_dispatch(args: argparse.Namespace) -> int:
    root = Path(args.root)
    err = _validate_dispatch_id(args.dispatch_id)
    if err:
        print(json.dumps({"ok": False, "error": err, "dispatch_id": args.dispatch_id}))
        return 2
    ddir = _dispatch_dir(root, args.dispatch_id)
    req_path = ddir / REQUEST_FILENAME
    if not req_path.exists():
        print(json.dumps({
            "ok": False,
            "error": "request.yaml ausente — dispatch nunca foi aberto (open-dispatch) ou --dispatch-id errado",
            "dispatch_id": args.dispatch_id,
        }))
        return 1
    request = _gs().parse_estado(req_path.read_text(encoding="utf-8"))

    done_path = ddir / DONE_FILENAME
    if done_path.exists() and not args.force:
        print(json.dumps({
            "ok": False,
            "error": "DONE.marker já existe — dispatch já fechado; use --force para sobrescrever (não recomendado, quebra a semântica write-once do marcador)",
            "dispatch_id": args.dispatch_id,
        }))
        return 1
    # RISCO RESIDUAL (E15.2, aceito, não bloqueado mecanicamente): `--force` sobre um
    # dispatch já fechado, combinado com `--tokens-used`, conta a cota UMA SEGUNDA VEZ
    # (record_usage() roda de novo mais abaixo). Fora de escopo bloquear isso aqui — é a
    # mesma classe de "não recomendado" já documentada para `--force` isoladamente, e o
    # double-count erra na direção SEGURA (superestima cota, nunca subestima), mesmo
    # espírito do multiplicador de segurança de E8.3.

    if args.outcome not in VALID_OUTCOMES:
        print(json.dumps({"ok": False, "error": f"--outcome deve ser um de {VALID_OUTCOMES}"}))
        return 2

    # ------------------------------------------------------------------
    # E15.2 — cota mecanizada como efeito colateral de close-dispatch.
    #
    # GARANTIA DE ORDEM (o ponto central desta story, mesma família de raciocínio do
    # comentário "GARANTIA DE ORDEM" mais abaixo para result.yaml/DONE.marker): quando
    # `--tokens-used` é passado, `record_usage()` é chamado AQUI — ANTES de result.yaml
    # e DONE.marker serem escritos. Isso garante, por construção, que `DONE.marker` (o
    # sinal definitivo de "despacho fechado" no contrato — ver `read-result`/
    # `dispatch-contract.md`) NUNCA é observável sem que a cota já tenha sido contada em
    # `quota-ciclo.json`: não existe um estado "dispatch fechado, cota não contada"
    # (half-closed, exatamente o que a story proíbe) alcançável por este caminho, porque
    # a escrita da cota sempre precede as duas escritas que tornam o fechamento visível.
    #
    # A janela de risco simétrica (processo morre ENTRE a escrita da cota e a escrita de
    # result.yaml) é segura na direção oposta: `quota-ciclo.json` fica "adiantado"
    # (cota já contada) mas `DONE.marker` nunca aparece — o despacho continua
    # corretamente detectável como órfão via `reconcile-orphan-dispatch`/`list-inflight`,
    # exatamente como hoje. Nunca existe "despacho fechado sem cota"; na pior hipótese
    # existe "cota contada sem despacho (ainda) fechado", que nunca é o problema que esta
    # story precisa evitar — e enviesa para SUPERESTIMAR, nunca subestimar, cota (mesma
    # filosofia do multiplicador de segurança de E8.3: "an approximation error never
    # causes an overrun").
    #
    # Import direto de `record_usage()` (nunca subprocess) — fica na mesma transação de
    # processo que o resto de `close-dispatch`, sem o custo/risco de spawnar um processo
    # Python extra a cada fechamento de despacho.
    quota_info: Optional[dict] = None
    if args.tokens_used is not None:
        cycle_id = request.get("cycle_id")
        if not cycle_id:
            print(json.dumps({
                "ok": False,
                "error": "--tokens-used passado mas request.yaml não tem cycle_id gravado — dispatch corrompido/incompatível",
                "dispatch_id": args.dispatch_id,
            }))
            return 1
        gq = _gq()
        multiplier = gq.resolve_safety_multiplier(root, args.tokens_multiplier)
        note = args.tokens_note or f"close-dispatch:{args.dispatch_id}"
        quota_doc = gq.record_usage(root, cycle_id, args.tokens_used, note, multiplier, False)
        quota_info = {
            "quota_recorded": True,
            "quota_cycle_id": quota_doc["cycle_id"],
            "self_tracked_tokens_total": quota_doc["self_tracked_tokens_total"],
            "tokens_used_raw": args.tokens_used,
            "multiplier_applied": multiplier,
        }

    pending = _load_json_list(args.pending_json, "--pending-json")
    evidence = _load_json_dict(args.evidence_json, "--evidence-json")
    ts = now_iso()
    doc = {
        "schema_version": 1,
        "dispatch_id": args.dispatch_id,
        "closed_at": ts,
        "outcome": args.outcome,
        "verdict": args.verdict,
        "pending_items": pending,
        "evidence": evidence,
        "closed_by": args.closed_by,
    }
    result_path = ddir / RESULT_FILENAME

    # GARANTIA DE ORDEM (a parte central da story E8.4): result.yaml precisa estar
    # DURÁVEL (write_atomic = temp + flush + fsync + os.replace, já concluído) antes de
    # DONE.marker ser criado. As duas chamadas write_atomic abaixo são sequenciais e
    # cada uma só retorna depois do próprio rename atômico — não há como DONE.marker
    # aparecer em disco antes de result.yaml estar completo, mesmo que o processo morra
    # entre as duas chamadas (nesse caso, DONE.marker simplesmente nunca é escrito, e o
    # despacho fica corretamente detectável como órfão via reconcile-orphan-dispatch).
    # NOTA (E15.2): se --tokens-used foi passado, a cota já foi contada ACIMA, antes
    # deste ponto — ver o comentário "cota mecanizada" acima para a garantia de ordem
    # completa (cota -> result.yaml -> DONE.marker).
    write_atomic(result_path, _dump_doc(doc, RESULT_TOP_KEYS, RESULT_HEADER))
    write_atomic(done_path, f"# DONE — dispatch {args.dispatch_id} fechado em {ts} (outcome={args.outcome})\n")

    out = {
        "ok": True,
        "dispatch_id": args.dispatch_id,
        "result_path": str(result_path),
        "done_marker_path": str(done_path),
        "outcome": args.outcome,
    }
    if quota_info is not None:
        out.update(quota_info)
    print(json.dumps(out, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------------------
# read-result — done é decidido SÓ pela presença do DONE.marker; nunca faz poll.
# ---------------------------------------------------------------------------
def cmd_read_result(args: argparse.Namespace) -> int:
    root = Path(args.root)
    err = _validate_dispatch_id(args.dispatch_id)
    if err:
        print(json.dumps({"ok": False, "known": False, "done": False, "error": err, "dispatch_id": args.dispatch_id}))
        return 2
    ddir = _dispatch_dir(root, args.dispatch_id)
    req_path = ddir / REQUEST_FILENAME
    result_path = ddir / RESULT_FILENAME
    done_path = ddir / DONE_FILENAME

    if not req_path.exists():
        print(json.dumps({
            "ok": False, "known": False, "done": False,
            "error": "dispatch desconhecido — request.yaml ausente",
            "dispatch_id": args.dispatch_id,
        }))
        return 1

    try:
        request = _gs().parse_estado(req_path.read_text(encoding="utf-8"))
    except OSError as exc:
        request = {"parse_error": str(exc)}

    done = done_path.exists()
    out: dict[str, Any] = {"ok": True, "known": True, "dispatch_id": args.dispatch_id, "done": done, "request": request}

    if not done:
        out["reason"] = (
            "sem DONE.marker em disco — despacho ainda em voo, OU o executor morreu/a "
            "compactação perdeu o fio antes de chamar close-dispatch. Este comando NUNCA "
            "espera pelo marcador (sem poll) — quem decide aguardar mais ou tratar como "
            "órfão é a persona, via o retorno do Agent tool (sinal primário) + "
            "reconcile-orphan-dispatch (diagnóstico secundário)."
        )
        print(json.dumps(out, ensure_ascii=False))
        return 0

    if not result_path.exists():
        # Nunca deveria acontecer dado o ordering de close-dispatch (result antes de
        # DONE) — mas se acontecer (corrupção externa, edição manual proibida), trata
        # defensivamente como estado inconsistente, nunca lança exceção.
        out["corrupt"] = True
        out["error"] = "DONE.marker presente mas result.yaml ausente — estado inconsistente; tratar como despacho falho, nunca como sucesso silencioso"
        print(json.dumps(out, ensure_ascii=False))
        return 0

    try:
        result = _gs().parse_estado(result_path.read_text(encoding="utf-8"))
    except OSError as exc:
        out["corrupt"] = True
        out["error"] = f"result.yaml ilegível: {exc}"
        print(json.dumps(out, ensure_ascii=False))
        return 0

    out["result"] = result
    print(json.dumps(out, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------------------
# list-inflight
# ---------------------------------------------------------------------------
def cmd_list_inflight(args: argparse.Namespace) -> int:
    root = Path(args.root)
    base = root / DISPATCHES_DIRNAME
    inflight = []
    if base.exists():
        for d in sorted(base.iterdir()):
            if not d.is_dir():
                continue
            req_path = d / REQUEST_FILENAME
            if not req_path.exists():
                continue
            if (d / DONE_FILENAME).exists():
                continue
            try:
                request = _gs().parse_estado(req_path.read_text(encoding="utf-8"))
            except OSError:
                request = {}
            if args.cycle_id and request.get("cycle_id") != args.cycle_id:
                continue
            entry = {"dispatch_id": d.name}
            for k in ("cycle_id", "tickets", "unit", "trilha", "worktree", "opened_at"):
                entry[k] = request.get(k)
            inflight.append(entry)
    print(json.dumps({"ok": True, "inflight": inflight, "count": len(inflight)}, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------------------
# reconcile-orphan-dispatch — diagnóstico de UM despacho suspeito; nunca escreve Ticket.
# ---------------------------------------------------------------------------
def cmd_reconcile_orphan_dispatch(args: argparse.Namespace) -> int:
    root = Path(args.root)
    err = _validate_dispatch_id(args.dispatch_id)
    if err:
        print(json.dumps({"ok": False, "error": err, "dispatch_id": args.dispatch_id}))
        return 2
    ddir = _dispatch_dir(root, args.dispatch_id)
    req_path = ddir / REQUEST_FILENAME
    done_path = ddir / DONE_FILENAME

    if not req_path.exists():
        print(json.dumps({"ok": False, "error": "dispatch desconhecido — request.yaml ausente", "dispatch_id": args.dispatch_id}))
        return 1

    request = _gs().parse_estado(req_path.read_text(encoding="utf-8"))

    if done_path.exists():
        print(json.dumps({
            "ok": True, "dispatch_id": args.dispatch_id, "orphan": False,
            "reason": "DONE.marker presente — despacho foi fechado normalmente (ver read-result para o outcome)",
        }, ensure_ascii=False))
        return 0

    board_path = Path(args.board_path) if args.board_path else (root.parent / "tickets" / "board.yaml")
    board_text = board_path.read_text(encoding="utf-8") if board_path.exists() else ""

    tickets = request.get("tickets") or ([request.get("ticket")] if request.get("ticket") else [])
    reasons = [
        "sem DONE.marker em disco — o despacho não foi fechado (executor pode ter "
        "morrido, sido interrompido, ou uma compactação de contexto perdeu o fio antes "
        "de chamar close-dispatch)",
    ]
    for t in tickets:
        if not t:
            continue
        status = _gs().ticket_status_in_board(board_text, t) if board_text else None
        if status == "em-implementacao":
            reasons.append(f"ticket {t} ainda em 'em-implementacao' no board.yaml")
        elif board_text and status is None:
            reasons.append(f"ticket {t} não encontrado no board.yaml (pode já ter sido movido/removido por outro fluxo)")

    worktree = request.get("worktree")
    if worktree not in (None, "null", ""):
        wt_path = Path(str(worktree))
        if not wt_path.exists():
            reasons.append(f"worktree registrado não existe mais em disco: {worktree}")
        else:
            reasons.append(f"worktree ainda presente em disco: {worktree} (verificar manualmente se é órfão/mergeável)")

    out = {
        "ok": True,
        "dispatch_id": args.dispatch_id,
        "orphan": True,
        "tickets": tickets,
        "reasons": reasons,
        "recommended_next_step": (
            "Para cada ticket listado: mover para um estado explícito via `bagual-tickets` "
            "(nunca editar board.yaml à mão) — 'triado' com nota de despacho órfão, ou "
            "'precisa-de-info' se o bloqueio for de informação. Nunca deixar o Ticket em "
            "'em-implementacao'/'concluido' silencioso sem verificação real."
        ),
    }
    print(json.dumps(out, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def add_root_arg(sp: argparse.ArgumentParser) -> None:
    sp.add_argument("--root", default="project_controll/gerente", help="diretório de estado do Gerente (default: project_controll/gerente)")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    po = sub.add_parser("open-dispatch", help="abre um despacho: escreve request.yaml")
    add_root_arg(po)
    po.add_argument("--dispatch-id", default=None, help="default: gerado (dispatch-YYYYMMDD-HHMMSS-hex8)")
    po.add_argument("--cycle-id", required=True)
    po.add_argument("--tickets-json", required=True, help="lista JSON de ids de Ticket, ex.: '[\"TCK-123\"]'")
    po.add_argument("--unit", required=True, help="ex.: epic-E8, ticket:TCK-123, multi-epic:[E10,E11] (forward-compat E10)")
    po.add_argument("--trilha", required=True, choices=VALID_TRILHAS)
    po.add_argument("--worktree", default=None)
    po.add_argument("--skill", required=True, help="skill mapeada pela trilha, ex.: bagual-epic-runner, bmad-quick-dev")
    po.add_argument("--model", default="sonnet", help="modelo do sub-agente executor (default: sonnet — FR-7)")
    po.add_argument("--note", default=None)
    po.set_defaults(func=cmd_open_dispatch)

    pc = sub.add_parser("close-dispatch", help="fecha um despacho: escreve result.yaml e SÓ DEPOIS DONE.marker")
    add_root_arg(pc)
    pc.add_argument("--dispatch-id", required=True)
    pc.add_argument("--outcome", required=True, choices=VALID_OUTCOMES)
    pc.add_argument("--verdict", required=True, help="resumo em texto do resultado")
    pc.add_argument("--pending-json", default="[]", help="lista JSON de pendências, ex.: '[{\"ticket\":\"TCK-1\",\"note\":\"...\"}]'")
    pc.add_argument("--evidence-json", default="{}", help="objeto JSON, ex.: '{\"commit\":\"abc123\",\"story_file\":\"...\"}'")
    pc.add_argument("--closed-by", default="gerente-geral")
    pc.add_argument("--force", action="store_true", help="sobrescreve mesmo se DONE.marker já existir (não recomendado)")
    pc.add_argument("--tokens-used", type=int, default=None, help="E15.2: estimativa BRUTA de tokens gastos neste despacho — acumulada em quota-ciclo.json via record_usage() (import direto), ANTES de result.yaml/DONE.marker, na MESMA chamada de close-dispatch (mesma semântica de 'gerente_quota.py record-usage --tokens', multiplicador de segurança aplicado igual). Omitido (default): nenhuma cota é registrada, comportamento idêntico ao anterior a E15.2.")
    pc.add_argument("--tokens-note", default=None, help="nota da entrada de cota (default: 'close-dispatch:<dispatch_id>')")
    pc.add_argument("--tokens-multiplier", type=float, default=None, help="override do multiplicador de segurança para --tokens-used (default resolvido: mesma precedência de gerente_quota.py resolve_safety_multiplier)")
    pc.set_defaults(func=cmd_close_dispatch)

    pr = sub.add_parser("read-result", help="lê o resultado de um despacho (done só via DONE.marker, sem poll)")
    add_root_arg(pr)
    pr.add_argument("--dispatch-id", required=True)
    pr.set_defaults(func=cmd_read_result)

    pl = sub.add_parser("list-inflight", help="lista despachos sem DONE.marker")
    add_root_arg(pl)
    pl.add_argument("--cycle-id", default=None)
    pl.set_defaults(func=cmd_list_inflight)

    prd = sub.add_parser("reconcile-orphan-dispatch", help="diagnostica um despacho suspeito de órfão (sem DONE.marker)")
    add_root_arg(prd)
    prd.add_argument("--dispatch-id", required=True)
    prd.add_argument("--board-path", default=None, help="default: <root>/../tickets/board.yaml")
    prd.set_defaults(func=cmd_reconcile_orphan_dispatch)

    return p


def main(argv: Optional[list] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
