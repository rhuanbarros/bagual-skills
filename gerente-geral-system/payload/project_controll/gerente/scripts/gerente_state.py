#!/usr/bin/env python3
"""gerente_state.py — E8.2 estado operacional persistente do Gerente Geral.

Story E8.2 (ideias/sistema-artifacts/E8-2-estado-operacional.md), PRD 00 FR-11 (§4.8),
ideias/epics.md Epic E8. Materializa a consciência situacional do Gerente Geral
(`.claude/agents/gerente-geral.md`, Story E8.1) em `project_controll/gerente/`:

  * `estado-atual.yaml` — retrato do ciclo ATUAL, sobrescrito a cada ciclo (write-snapshot).
  * `diario.md` (+ `diario.jsonl` irmão, mesma disciplina de append) — diário append-only
    com marcadores explícitos de início/fim de ciclo (append-diario).
  * `.lock/` — lock singleton (PID+timestamp+heartbeat), garantindo um Gerente por vez
    (acquire-lock / refresh-lock / release-lock / check-lock).
  * Recuperação de crash — um ciclo com início sem fim correspondente no diário é
    detectado (detect-crash) e reconciliado (reconcile) ANTES de qualquer nova decisão.

Escrita atômica em TODA mutação de estado (temp + flush + fsync + rename) — reusa
literalmente a primitiva `write_atomic` de `_bmad/scripts/memlog.py` via import direto
do arquivo (não uma cópia colada — ver `_memlog()` abaixo), a mesma primitiva que
`wiki/ledger/scripts/transition_ledger_entry.py` e
`project_controll/tickets/scripts/rebuild_board.py` já reusam/replicam neste projeto.
O CLI `init`/`append`/`set` do próprio `memlog.py` NÃO é chamado diretamente (aquele
formato é frontmatter+corpo-de-um-log-só, desenhado para o caso de uso de skill única);
`diario.md`/`diario.jsonl` têm campos estruturados por entrada (`cycle_id`, `event`,
`text`) que não cabem nesse molde — mesma decisão de adaptar-em-vez-de-reusar-a-CLI já
tomada por `transition_ledger_entry.py` (ver seu docstring). O que É reusado — e é a
parte que importa para a garantia de não-corrupção — é a PRIMITIVA de escrita atômica
em si, não a CLI de alto nível. A DISCIPLINA de append (só-anexa, cronológico, nunca
reordena/edita/remove retroativamente) é seguida à risca por `_append_md`/`_append_jsonl`
abaixo, mesmo sem invocar o subcomando `append` do memlog.py.

O parser/serializador YAML aqui NÃO é um YAML genérico — é um subconjunto mínimo e
fechado (escalar / dict-de-escalares em 1 nível / lista-de-dict-de-escalares) desenhado
para o schema exato que este script produz. Não use para ler YAML arbitrário.

Ver `project_controll/gerente/README.md` para o contrato completo (schema, semântica de
staleness do lock, checklist de reconciliação).

Comandos:
  write-snapshot   escreve estado-atual.yaml atomicamente (retrato do ciclo)
  append-diario    anexa uma entrada (ou marcador CICLO-INICIO/CICLO-FIM) ao diário
  acquire-lock     tenta adquirir o lock singleton (mkdir atômico + reclaim por rename)
  refresh-lock     atualiza o heartbeat do lock (requer --token do holder)
  release-lock     libera o lock (requer --token do holder)
  check-lock       relatório somente-leitura do estado do lock (sem mutação)
  detect-crash     varre diario.jsonl por CICLO-INICIO sem CICLO-FIM correspondente
  reconcile        reconcilia despachos em voo de um ciclo detectado como morto

Só biblioteca padrão (stdlib) — nenhuma dependência externa (mesma convenção dos scripts
irmãos em `project_controll/tickets/scripts/` e `wiki/ledger/scripts/`).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

DEFAULT_STALE_AFTER_SECONDS = 900.0  # 15min de silêncio de heartbeat — não timeout fixo por idade do ciclo
LOCK_DIRNAME = ".lock"
LOCK_INFO_FILE = "info.json"

# Story E15.4 — guard mecânico: sentinela de crash-check por `cycle_id`. O gap real (não
# `acquire-lock`, que E8.2 corretamente rejeitou bloquear — quebraria inspeção de estado)
# era o passo SEGUINTE: nada impedia a persona de pular de "adquiri o lock" direto para
# `gerente_dispatch.py open-dispatch` sem nunca ter rodado `detect-crash`/`reconcile`.
# `detect-crash`/`reconcile` (e `gerente_wake.py::wake-attempt`, que hoje faz o crash-check
# por composição via `acquire_lock`) passam a gravar, aqui, um sentinela leve por
# `cycle_id` — um arquivo `.json` write-once (write_atomic, mesma primitiva de sempre) sob
# `<root>/.crash-check-sentinels/<cycle_id>.json` — sempre que rodam, mesmo quando não há
# nada para reconciliar. `gerente_dispatch.py::open-dispatch --cycle-id X` (E15.4) EXIGE
# esse sentinela para X antes de escrever `request.yaml`; `acquire-lock`/`check-lock`/
# leituras continuam livres (nunca gateadas por isto — o guard é só sobre `open-dispatch`).
CRASH_CHECK_SENTINEL_DIRNAME = ".crash-check-sentinels"
# Mesma regex de segurança de path já usada por `gerente_dispatch.py::DISPATCH_ID_RE` —
# um `cycle_id` vira diretamente um nome de arquivo (`<cycle_id>.json`); sem esta validação
# um `--cycle-id` malformado (ex.: "../../etc") poderia escapar do diretório pretendido.
CYCLE_ID_SENTINEL_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


# ---------------------------------------------------------------------------
# Reuso da primitiva atômica de memlog.py (import direto do arquivo — não cópia colada)
# ---------------------------------------------------------------------------
def _memlog():
    """Importa `_bmad/scripts/memlog.py` pelo caminho e devolve o módulo carregado.

    Reuso literal (import), não reimplementação: `write_atomic` (temp + flush + fsync +
    rename) usada abaixo é exatamente a função definida em memlog.py, não uma cópia.
    """
    memlog_path = Path(__file__).resolve().parents[3] / "_bmad" / "scripts" / "memlog.py"
    if not memlog_path.exists():
        print(f"erro: memlog.py não encontrado em {memlog_path} — não é possível reusar write_atomic", file=sys.stderr)
        sys.exit(2)
    spec = importlib.util.spec_from_file_location("memlog", memlog_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MEMLOG = None


def write_atomic(path: Path, text: str) -> None:
    global _MEMLOG
    if _MEMLOG is None:
        _MEMLOG = _memlog()
    path.parent.mkdir(parents=True, exist_ok=True)
    _MEMLOG.write_atomic(path, text)


# ---------------------------------------------------------------------------
# Utilidades de tempo
# ---------------------------------------------------------------------------
def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def parse_iso(ts: str) -> datetime:
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def seconds_since(ts: str) -> float:
    try:
        return (datetime.now().astimezone() - parse_iso(ts)).total_seconds()
    except (ValueError, TypeError):
        return float("inf")


# ---------------------------------------------------------------------------
# Serialização YAML mínima (subconjunto fechado — ver docstring do módulo)
# ---------------------------------------------------------------------------
def yaml_scalar(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if s == "":
        return '""'
    needs_quotes = (
        any(ch in s for ch in ':#"\'{}[]')
        or s.strip() != s
        or s.lower() in ("null", "true", "false", "~")
        or re.fullmatch(r"-?\d+(\.\d+)?", s) is not None
    )
    if needs_quotes:
        escaped = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return s


def unquote(s: str) -> Any:
    s = s.strip()
    if s == "null" or s == "":
        return None
    if s == "true":
        return True
    if s == "false":
        return False
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        inner = s[1:-1]
        if s[0] == '"':
            inner = inner.replace('\\"', '"').replace("\\\\", "\\")
        return inner
    return s


# Ordem canônica dos campos de topo do estado-atual.yaml (também usada como grade de
# parsing — ver `parse_estado`).
ESTADO_TOP_KEYS = [
    "schema_version", "written_at", "marker", "cycle", "dispatches",
    "decisions_pending", "decisions_escalated",
    "escalation_sample_review", "escalation_dead_letter",  # Story E9.5, PRD 02 FR-6
    "semgrep_fp_pending",  # Story E13.4, PRD 04 FR-2 — populado por read_fp_suspects.py list-pending
    "priorities", "quota", "last_briefing_at",
]
ESTADO_HEADER_COMMENT = """\
# estado-atual.yaml — retrato do CICLO ATUAL do Gerente Geral (Story E8.2, PRD 00 FR-11)
# Sobrescrito a cada ciclo — NÃO é histórico (isso é diario.md). Escrito por
# project_controll/gerente/scripts/gerente_state.py write-snapshot (escrita atômica).
# `marker: start` = escrito no INÍCIO do ciclo (otimista, pode estar desatualizado se o
#   ciclo morreu no meio — ver detect-crash/reconcile, F23).
# `marker: end`   = escrito no FIM do ciclo (confirmado).
# Ver README.md deste diretório para o contrato completo do schema.
"""


def dump_flat_dict_item(d: dict, indent: int) -> list[str]:
    pad = "  " * indent
    keys = list(d.keys())
    if not keys:
        return [f"{pad}- {{}}"]
    lines = [f"{pad}- {keys[0]}: {yaml_scalar(d[keys[0]])}"]
    for k in keys[1:]:
        lines.append(f"{pad}  {k}: {yaml_scalar(d[k])}")
    return lines


def dump_estado(doc: dict) -> str:
    lines = [ESTADO_HEADER_COMMENT.rstrip("\n"), ""]
    for key in ESTADO_TOP_KEYS:
        if key not in doc:
            continue
        v = doc[key]
        if isinstance(v, dict):
            if not v:
                lines.append(f"{key}: {{}}")
            else:
                lines.append(f"{key}:")
                for k2, v2 in v.items():
                    lines.append(f"  {k2}: {yaml_scalar(v2)}")
        elif isinstance(v, list):
            if not v:
                lines.append(f"{key}: []")
            else:
                lines.append(f"{key}:")
                for item in v:
                    if isinstance(item, dict):
                        lines.extend(dump_flat_dict_item(item, 1))
                    else:
                        lines.append(f"  - {yaml_scalar(item)}")
        else:
            lines.append(f"{key}: {yaml_scalar(v)}")
    return "\n".join(lines) + "\n"


def parse_estado(text: str) -> dict:
    """Parser mínimo casado com `dump_estado` — não é YAML genérico (ver docstring)."""
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith("#")]
    doc: dict[str, Any] = {}
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith(" "):
            # linha órfã fora de um bloco reconhecido — ignora defensivamente
            i += 1
            continue
        key, _, rest = line.partition(":")
        key = key.strip()
        rest = rest.strip()
        if rest and rest not in ("{}", "[]"):
            doc[key] = unquote(rest)
            i += 1
            continue
        if rest == "{}":
            doc[key] = {}
            i += 1
            continue
        if rest == "[]":
            doc[key] = []
            i += 1
            continue
        # bloco (dict de escalares em 1 nível OU lista de dict-de-escalares)
        block: list[str] = []
        i += 1
        while i < n and lines[i].startswith("  "):
            block.append(lines[i])
            i += 1
        if not block:
            doc[key] = None
            continue
        if block[0].lstrip().startswith("- "):
            # Lista-de-dict-de-escalares OU lista-de-escalares-puros — decidido UMA VEZ
            # pelo primeiro item, olhando se ele tem a forma "chave: valor" com uma
            # CHAVE BARE (identificador sem aspas) seguida de ":". `_dump_doc`/`dump_estado`
            # só emitem "- chave: valor" (chave bare) para itens de dict; um item escalar é
            # o próprio `yaml_scalar(item)` — se o valor precisasse literalmente de um ':',
            # `yaml_scalar` já teria colocado aspas nele, então um prefixo
            # "identificador-bare:" aqui é inequívoco sinal de item-de-dict, nunca um
            # escalar (bug real encontrado na Story E8.4: `tickets: [- TCK-1]`, uma lista
            # de escalares puros, virava incorretamente `[{"TCK-1": None}]` antes desta
            # correção — nenhum schema anterior a E8.4 usava lista de escalares puros, por
            # isso o defeito nunca tinha sido exercitado).
            first_rest = block[0].lstrip()[2:]
            is_dict_list = re.match(r"^[A-Za-z_][A-Za-z0-9_]*:(\s|$)", first_rest) is not None
            if is_dict_list:
                items: list[dict] = []
                cur: Optional[dict] = None
                for bl in block:
                    stripped = bl.strip()
                    if stripped.startswith("- "):
                        if cur is not None:
                            items.append(cur)
                        cur = {}
                        stripped = stripped[2:]
                    k2, _, v2 = stripped.partition(":")
                    if cur is not None and k2:
                        cur[k2.strip()] = unquote(v2)
                if cur is not None:
                    items.append(cur)
                doc[key] = items
            else:
                scalars: list[Any] = []
                for bl in block:
                    stripped = bl.strip()
                    if stripped.startswith("- "):
                        scalars.append(unquote(stripped[2:]))
                doc[key] = scalars
        else:
            d2: dict[str, Any] = {}
            for bl in block:
                k2, _, v2 = bl.strip().partition(":")
                if k2:
                    d2[k2.strip()] = unquote(v2)
            doc[key] = d2
    return doc


# ---------------------------------------------------------------------------
# write-snapshot
# ---------------------------------------------------------------------------
def cmd_write_snapshot(args: argparse.Namespace) -> int:
    root = Path(args.root)
    estado_path = root / "estado-atual.yaml"

    def load_json_list(raw: str, flag: str) -> list:
        try:
            v = json.loads(raw)
        except json.JSONDecodeError as exc:
            print(f"erro: {flag} não é JSON válido: {exc}", file=sys.stderr)
            sys.exit(2)
        if not isinstance(v, list):
            print(f"erro: {flag} deve ser uma lista JSON", file=sys.stderr)
            sys.exit(2)
        return v

    doc = {
        "schema_version": 1,
        "written_at": now_iso(),
        "marker": args.marker,
        "cycle": {
            "id": args.cycle_id,
            "started_at": args.started_at,
            "ended_at": args.ended_at,
            "phase": args.phase,
            "stop_reason": args.stop_reason,
        },
        "dispatches": load_json_list(args.dispatches_json, "--dispatches-json"),
        "decisions_pending": load_json_list(args.pending_json, "--pending-json"),
        "decisions_escalated": load_json_list(args.escalated_json, "--escalated-json"),
        # Story E9.5 (PRD 02 FR-6) — amostragem de decisões automáticas (AC2) e
        # dead-letter de escalados presos (AC4), populados por
        # `gerente_escalation.py sample-decisions`/`dead-letter-check` e repassados
        # aqui pela persona; consumidos por `gerente_briefing.py` (write-briefing) sem
        # nenhum rework — mesmo padrão aditivo de `decisions_pending`/`decisions_escalated`.
        "escalation_sample_review": load_json_list(args.sample_review_json, "--sample-review-json"),
        "escalation_dead_letter": load_json_list(args.dead_letter_json, "--dead-letter-json"),
        # Story E13.4 (PRD 04 FR-2) — suspeitas de falso-positivo de Semgrep ainda
        # `pending_ratification`, populadas por `read_fp_suspects.py list-pending`
        # (leitor read-only de project_controll/semgrep-fp-suspects.jsonl, escrito por
        # `flag_suspected_fp.py`/E7.3) e repassadas aqui pela persona; consumido por
        # `gerente_briefing.py` (write-briefing) sem nenhum rework — mesmo padrão
        # aditivo de `escalation_sample_review`/`escalation_dead_letter` acima:
        # ausente/`[]` renderiza frase neutra, nunca quebra um Briefing de estado antigo.
        "semgrep_fp_pending": load_json_list(args.semgrep_fp_pending_json, "--semgrep-fp-pending-json"),
        "priorities": load_json_list(args.priorities_json, "--priorities-json"),
        "quota": {
            "five_hour_used_pct": args.quota_five_hour,
            "seven_day_used_pct": args.quota_seven_day,
            "source": args.quota_source,
            "read_at": args.quota_read_at,
            # Campos de auto-rastreio (Story E8.3, gerente_quota.py) — opcionais,
            # preenchidos pelo `check` de gerente_quota.py e repassados pela persona
            # como args extras deste mesmo write-snapshot. `null` até E8.3 rodar no
            # ciclo (ou em ciclos anteriores a esta story). Ver
            # project_controll/gerente/README.md § Cota (E8.3) para o contrato.
            "self_tracked_tokens": args.quota_self_tokens,
            "self_tracked_pct": args.quota_self_pct,
            "stronger_signal_pct": args.quota_stronger_pct,
            "stronger_signal_source": args.quota_stronger_source,
        },
        "last_briefing_at": args.last_briefing_at,
    }
    write_atomic(estado_path, dump_estado(doc))
    print(json.dumps({"ok": True, "path": str(estado_path), "marker": args.marker, "cycle_id": args.cycle_id}))
    return 0


# ---------------------------------------------------------------------------
# append-diario
# ---------------------------------------------------------------------------
DIARIO_HEADER = """\
# diario.md — diário append-only do Gerente Geral (Story E8.2, PRD 00 FR-11)
#
# Log plano, cronológico, só-anexa (mesma filosofia de _bmad/scripts/memlog.py: sem
# seções, sem reordenação, sem edição retroativa). Cada ciclo é delimitado por um par de
# entradas `## CICLO-INICIO ...` / `## CICLO-FIM ...` — um início sem fim correspondente
# é o sinal de crash recovery (F23, ver detect-crash/reconcile em gerente_state.py).
# Escrito por project_controll/gerente/scripts/gerente_state.py append-diario.

"""

VALID_EVENTS = [
    "CICLO-INICIO", "CICLO-FIM",
    "acordei", "li-estado", "decidi", "despachei", "revisei", "parei",
]


def _append_md(path: Path, line: str) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else DIARIO_HEADER
    existing = existing.rstrip("\n")
    write_atomic(path, existing + "\n" + line + "\n")


def _append_jsonl(path: Path, obj: dict) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    existing = existing.rstrip("\n")
    new_line = json.dumps(obj, ensure_ascii=False)
    combined = (existing + "\n" + new_line) if existing else new_line
    write_atomic(path, combined + "\n")


def cmd_append_diario(args: argparse.Namespace) -> int:
    if args.event not in VALID_EVENTS:
        print(f"erro: --event deve ser um de {VALID_EVENTS}", file=sys.stderr)
        return 2
    root = Path(args.root)
    md_path = root / "diario.md"
    jsonl_path = root / "diario.jsonl"
    ts = args.ts or now_iso()

    if args.event in ("CICLO-INICIO", "CICLO-FIM"):
        suffix = " (reconciled)" if (args.event == "CICLO-FIM" and args.reconciled) else ""
        md_line = f"## {args.event} {ts} {args.cycle_id}{suffix}"
    else:
        hhmm = ts[11:16] if len(ts) >= 16 else ts
        text = f": {args.text}" if args.text else ""
        md_line = f"- [{hhmm}] {args.event}{text}"

    _append_md(md_path, md_line)

    jsonl_obj = {"ts": ts, "cycle_id": args.cycle_id, "event": args.event}
    if args.text:
        jsonl_obj["text"] = args.text
    if args.event == "CICLO-FIM" and args.reconciled:
        jsonl_obj["reconciled"] = True
    _append_jsonl(jsonl_path, jsonl_obj)

    print(json.dumps({"ok": True, "md": str(md_path), "jsonl": str(jsonl_path), "event": args.event, "cycle_id": args.cycle_id}))
    return 0


# ---------------------------------------------------------------------------
# Lock singleton — F9. mkdir atômico (O_EXCL-equivalente) + reclaim de stale via
# os.rename atômico (só um contendor pode renomear um dado nome com sucesso — a mesma
# garantia do filesystem que torna `os.mkdir` seguro para exclusão mútua é reusada aqui
# para tornar o RECLAIM também livre de TOCTOU: nunca sobrescreve um lock possivelmente
# vivo, só rouba o NOME através de um rename que só um processo pode vencer).
# ---------------------------------------------------------------------------
def _lock_dir(root: Path) -> Path:
    return root / LOCK_DIRNAME


def _read_lock_info(lock_dir: Path) -> Optional[dict]:
    info_path = lock_dir / LOCK_INFO_FILE
    try:
        return json.loads(info_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None  # dir existe mas info ainda não foi escrito (janela transiente do acquire) ou corrompido


def _write_lock_info(lock_dir: Path, info: dict) -> None:
    write_atomic(lock_dir / LOCK_INFO_FILE, json.dumps(info, ensure_ascii=False, indent=2) + "\n")


def pid_alive(pid: Optional[int]) -> Optional[bool]:
    """True/False se determinável; None se o PID não foi informado (sem sinal)."""
    if pid is None:
        return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # existe, dono de outro usuário — conservador: trata como vivo
    except OSError:
        return None
    else:
        return True


def lock_is_stale(info: dict, stale_after_seconds: float) -> tuple[bool, str]:
    """Staleness é baseada em SILÊNCIO de heartbeat (não idade fixa do ciclo — um ciclo
    longo que segue chamando refresh-lock nunca fica "velho" por si só). PID morto é um
    atalho de detecção mais rápido quando um --pid significativo foi informado; PID
    ausente (o caso comum — nenhum processo de SO único representa "o Gerente" de forma
    confiável neste harness de agente/tool-calls) cai só no critério de heartbeat."""
    pid = info.get("pid")
    alive = pid_alive(pid)
    if alive is False:
        return True, f"pid {pid} não está mais vivo"
    heartbeat_at = info.get("heartbeat_at") or info.get("acquired_at")
    age = seconds_since(heartbeat_at) if heartbeat_at else float("inf")
    if age > stale_after_seconds:
        return True, f"heartbeat silencioso há {age:.0f}s (> {stale_after_seconds:.0f}s)"
    return False, ""


def acquire_lock(root: Path, stale_after_seconds: float, pid: Optional[int], note: Optional[str], cycle_id: Optional[str] = None, max_retries: int = 8) -> dict:
    lock_dir = _lock_dir(root)
    root.mkdir(parents=True, exist_ok=True)
    for _ in range(max_retries):
        try:
            os.mkdir(lock_dir)
        except FileExistsError:
            info = _read_lock_info(lock_dir)
            if info is None:
                return {"ok": False, "acquired": False, "reason": "held", "detail": "lock dir existe, info ainda não escrito (acquire concorrente em andamento)"}
            stale, why = lock_is_stale(info, stale_after_seconds)
            if not stale:
                return {"ok": False, "acquired": False, "reason": "held", "holder": info}
            # tenta reclaim atômico via rename — só UM contendor vence este rename
            stale_name = root / f".lock.stale-{os.getpid()}-{time.time_ns()}"
            try:
                os.rename(lock_dir, stale_name)
            except FileNotFoundError:
                continue  # outro processo já reclamou; volta ao topo e tenta mkdir de novo
            except OSError as exc:
                return {"ok": False, "acquired": False, "reason": "error", "detail": str(exc)}
            shutil.rmtree(stale_name, ignore_errors=True)
            continue  # lock agora livre; disputa de novo via mkdir (justo — quem chegar primeiro vence)
        else:
            token = uuid.uuid4().hex
            ts = now_iso()
            info = {"token": token, "pid": pid, "acquired_at": ts, "heartbeat_at": ts, "note": note, "cycle_id": cycle_id}
            _write_lock_info(lock_dir, info)
            result: dict[str, Any] = {"ok": True, "acquired": True, "token": token, "info": info}
            # Rede de segurança (self-review E8.2): mesmo que o chamador esqueça de rodar
            # `detect-crash` explicitamente antes de adquirir, a própria resposta de
            # acquire-lock já expõe qualquer crash pendente (excluindo o cycle_id que
            # acabamos de adquirir, que ainda não tem CICLO-INICIO no diário).
            pending = detect_crash(root, exclude_cycle_id=cycle_id, active_lock_info=info)
            if pending.get("crashed"):
                result["pending_crash"] = pending
            return result
    return {"ok": False, "acquired": False, "reason": "contended", "detail": f"desistiu após {max_retries} tentativas"}


def cmd_acquire_lock(args: argparse.Namespace) -> int:
    root = Path(args.root)
    result = acquire_lock(root, args.stale_after_seconds, args.pid, args.note, args.cycle_id)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("acquired") else 1


def cmd_refresh_lock(args: argparse.Namespace) -> int:
    root = Path(args.root)
    lock_dir = _lock_dir(root)
    info = _read_lock_info(lock_dir)
    if info is None:
        print(json.dumps({"ok": False, "reason": "no-lock", "detail": "nenhum lock (ou info) presente"}))
        return 1
    if info.get("token") != args.token:
        print(json.dumps({"ok": False, "reason": "not-owner", "detail": "token não confere com o holder atual"}))
        return 1
    info["heartbeat_at"] = now_iso()
    if args.pid is not None:
        info["pid"] = args.pid
    if args.cycle_id is not None:
        info["cycle_id"] = args.cycle_id
    _write_lock_info(lock_dir, info)
    print(json.dumps({"ok": True, "info": info}))
    return 0


def cmd_release_lock(args: argparse.Namespace) -> int:
    root = Path(args.root)
    lock_dir = _lock_dir(root)
    info = _read_lock_info(lock_dir)
    if info is None:
        print(json.dumps({"ok": False, "reason": "no-lock", "detail": "nenhum lock (ou info) presente"}))
        return 1
    if info.get("token") != args.token:
        print(json.dumps({"ok": False, "reason": "not-owner", "detail": "token não confere com o holder atual"}))
        return 1
    shutil.rmtree(lock_dir, ignore_errors=True)
    print(json.dumps({"ok": True, "released": True}))
    return 0


def cmd_check_lock(args: argparse.Namespace) -> int:
    root = Path(args.root)
    lock_dir = _lock_dir(root)
    if not lock_dir.exists():
        print(json.dumps({"held": False}))
        return 0
    info = _read_lock_info(lock_dir)
    if info is None:
        print(json.dumps({"held": True, "info": None, "detail": "lock dir existe, info ilegível/ausente (transiente ou corrompido)"}))
        return 0
    stale, why = lock_is_stale(info, args.stale_after_seconds)
    heartbeat_at = info.get("heartbeat_at") or info.get("acquired_at")
    age = seconds_since(heartbeat_at) if heartbeat_at else None
    print(json.dumps({
        "held": True,
        "stale": stale,
        "stale_reason": why if stale else None,
        "heartbeat_age_seconds": age,
        "info": info,
    }))
    return 0


# ---------------------------------------------------------------------------
# Sentinela de crash-check por cycle_id — Story E15.4 (guard mecânico de open-dispatch)
# ---------------------------------------------------------------------------
def _validate_cycle_id_for_sentinel(cycle_id: Optional[str]) -> Optional[str]:
    """Devolve uma mensagem de erro se `cycle_id` não for seguro para virar o nome de um
    arquivo de sentinela, ou None se for válido. Mesma disciplina de
    `gerente_dispatch.py::_validate_dispatch_id` (não uma cópia colada — a regex é
    reexportada como `CYCLE_ID_SENTINEL_RE` para quem quiser reusar por import)."""
    if not cycle_id or cycle_id in (".", ".."):
        return "cycle_id vazio ou igual a '.'/'..' — inválido para sentinela de crash-check"
    if not CYCLE_ID_SENTINEL_RE.match(cycle_id):
        return "cycle_id contém caracteres não permitidos para sentinela de crash-check (só [A-Za-z0-9_.-])"
    if ".." in cycle_id:
        return "cycle_id não pode conter '..' (risco de path traversal) na sentinela de crash-check"
    return None


def _crash_check_sentinel_dir(root: Path) -> Path:
    return root / CRASH_CHECK_SENTINEL_DIRNAME


def _crash_check_sentinel_path(root: Path, cycle_id: str) -> Path:
    return _crash_check_sentinel_dir(root) / f"{cycle_id}.json"


def write_crash_check_sentinel(root: Path, cycle_id: str, source: str, detail: Optional[dict] = None) -> Path:
    """Grava (escrita atômica) o sentinela de crash-check para `cycle_id` — Story E15.4.
    `source` é sempre um de `detect-crash`/`reconcile`/`wake-attempt` (os três pontos de
    chamada mecânicos; nunca escrito por `acquire-lock`, que permanece deliberadamente de
    fora do guard, ver comentário de `CRASH_CHECK_SENTINEL_DIRNAME` acima). Sobrescreve se
    já existir (idempotente — rodar `detect-crash --cycle-id X` mais de uma vez para o
    mesmo X é seguro e comum, ex.: ao reprocessar depois de compactação). Levanta
    `ValueError` para um `cycle_id` que falhe a validação de path (nunca escreve fora do
    diretório de sentinelas)."""
    err = _validate_cycle_id_for_sentinel(cycle_id)
    if err:
        raise ValueError(err)
    payload = {"cycle_id": cycle_id, "source": source, "checked_at": now_iso()}
    if detail is not None:
        payload["detail"] = detail
    path = _crash_check_sentinel_path(root, cycle_id)
    write_atomic(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return path


def has_crash_check_sentinel(root: Path, cycle_id: Optional[str]) -> bool:
    """True somente se um sentinela válido já foi gravado para `cycle_id` — a checagem que
    `gerente_dispatch.py::open-dispatch` (E15.4) consulta antes de qualquer escrita. Um
    `cycle_id` que falha a validação de path nunca é tratado como "tem sentinela" (devolve
    False, nunca lança) — o chamador (`open-dispatch`) decide como reportar o erro."""
    if _validate_cycle_id_for_sentinel(cycle_id) is not None:
        return False
    assert cycle_id is not None
    return _crash_check_sentinel_path(root, cycle_id).exists()


def read_crash_check_sentinel(root: Path, cycle_id: str) -> Optional[dict]:
    if _validate_cycle_id_for_sentinel(cycle_id) is not None:
        return None
    path = _crash_check_sentinel_path(root, cycle_id)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


# ---------------------------------------------------------------------------
# detect-crash / reconcile — F23
# ---------------------------------------------------------------------------
def detect_crash(root: Path, exclude_cycle_id: Optional[str] = None, active_lock_info: Optional[dict] = None, stale_after_seconds: float = DEFAULT_STALE_AFTER_SECONDS) -> dict:
    """Varre diario.jsonl por CICLO-INICIO sem CICLO-FIM correspondente.

    Auto-revisão adversarial (E8.2): um scanner ingênuo do diário sozinho confundiria um
    ciclo LONGO E SAUDÁVEL (rodando em outra sessão/processo, com lock ativo e heartbeat
    fresco) com um crash — ele tem um CICLO-INICIO aberto por definição, até terminar.
    Por isso cruza com o lock: se HOJE existe um lock held-e-não-stale cujo `cycle_id`
    bate com um "início órfão", esse não é um crash — é um ciclo em andamento, e é
    excluído dos órfãos reportados. `exclude_cycle_id`/`active_lock_info` permitem ao
    chamador (acquire-lock, ver acima) informar o holder recém-adquirido sem reler o
    lock do disco duas vezes.
    """
    jsonl_path = root / "diario.jsonl"
    if not jsonl_path.exists():
        return {"crashed": False, "reason": "diario.jsonl ausente — primeira ativação, nada para detectar"}

    entries = []
    for ln in jsonl_path.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        try:
            entries.append(json.loads(ln))
        except json.JSONDecodeError:
            continue  # linha corrompida isolada não derruba a varredura inteira

    open_cycles: dict[str, dict] = {}
    for e in entries:
        ev = e.get("event")
        cid = e.get("cycle_id")
        if ev == "CICLO-INICIO" and cid:
            open_cycles[cid] = e
        elif ev == "CICLO-FIM" and cid:
            open_cycles.pop(cid, None)

    # exclui o cycle_id que o PRÓPRIO chamador acabou de adquirir (ainda sem CICLO-INICIO
    # no diário, então nunca apareceria aqui mesmo — guarda defensiva) e qualquer ciclo
    # cujo lock ainda está held-e-fresco (outro processo legitimamente em andamento).
    active_cycle_id = None
    if active_lock_info is None:
        lock_dir = _lock_dir(root)
        info = _read_lock_info(lock_dir) if lock_dir.exists() else None
        if info is not None:
            stale, _why = lock_is_stale(info, stale_after_seconds)
            if not stale:
                active_lock_info = info
    if active_lock_info is not None:
        active_cycle_id = active_lock_info.get("cycle_id")

    excluded = {c for c in (exclude_cycle_id, active_cycle_id) if c}
    open_cycles = {cid: e for cid, e in open_cycles.items() if cid not in excluded}

    if not open_cycles:
        return {
            "crashed": False,
            "reason": "todo CICLO-INICIO tem um CICLO-FIM correspondente (ou o único aberto é um ciclo ativo com lock fresco, não um crash)",
            "excluded_active_cycle_id": active_cycle_id,
        }

    estado_path = root / "estado-atual.yaml"
    estado_marker = None
    estado_cycle_id = None
    if estado_path.exists():
        estado = parse_estado(estado_path.read_text(encoding="utf-8"))
        estado_marker = estado.get("marker")
        cycle = estado.get("cycle") or {}
        estado_cycle_id = cycle.get("id")

    orphans = list(open_cycles.values())
    orphan_ids = [o.get("cycle_id") for o in orphans]
    return {
        "crashed": True,
        "orphan_cycles": orphan_ids,
        "detail": orphans,
        "estado_atual_marker": estado_marker,
        "estado_atual_cycle_id": estado_cycle_id,
        "estado_confirms": estado_marker == "start" and estado_cycle_id in orphan_ids,
        "excluded_active_cycle_id": active_cycle_id,
        "note": "diario.md é a fonte de verdade primária para crash (F23) — estado-atual.yaml é só corroborativo, nunca confiado cegamente.",
    }


def cmd_detect_crash(args: argparse.Namespace) -> int:
    root = Path(args.root)
    result = detect_crash(root, stale_after_seconds=args.stale_after_seconds)
    # Story E15.4 — grava o sentinela SEMPRE que `--cycle-id` é passado, inclusive quando
    # `crashed: false` (nada para reconciliar): o sentinela testemunha "o crash-check
    # rodou para este cycle_id", não "um crash foi encontrado". `--cycle-id` é OPCIONAL e
    # retrocompatível de propósito — chamadas de diagnóstico ad-hoc (sem um cycle_id novo
    # em mãos) continuam funcionando exatamente como antes, sem gravar nada; é a persona
    # (gerente-geral.md) que agora sempre passa `--cycle-id` no seu passo 0.
    if args.cycle_id:
        try:
            sentinel_path = write_crash_check_sentinel(root, args.cycle_id, source="detect-crash", detail={"crashed": result.get("crashed")})
        except ValueError as exc:
            result["sentinel_error"] = str(exc)
        else:
            result["sentinel_written_for_cycle_id"] = args.cycle_id
            result["sentinel_path"] = str(sentinel_path)
    print(json.dumps(result, ensure_ascii=False))
    return 0


def ticket_status_in_board(board_text: str, ticket: str) -> Optional[str]:
    """Extrai o campo `status:` de UM ticket dentro de board.yaml (regex simples, mesmo
    formato de convenção usado por rebuild_board.py). Devolve None se o ticket não for
    encontrado no texto. Extraído de `reconcile` (era inline) para ser reusável por
    `gerente_dispatch.py::cmd_reconcile_orphan_dispatch` (Story E8.4) sem duplicar a
    regex — mesma técnica de reuso-por-import já usada em todo este módulo."""
    m = re.search(rf"^  {re.escape(str(ticket))}:\n((?:    .+\n?)*)", board_text, re.M)
    if not m:
        return None
    status_m = re.search(r"status:\s*(\S+)", m.group(1))
    return status_m.group(1) if status_m else None


def reconcile(root: Path, cycle_id: str, board_path: Path) -> dict:
    estado_path = root / "estado-atual.yaml"
    findings: dict[str, Any] = {"cycle_id": cycle_id, "dispatches_checked": 0, "orphans": [], "notes": []}

    dispatches: list[dict] = []
    if estado_path.exists():
        estado = parse_estado(estado_path.read_text(encoding="utf-8"))
        cycle = estado.get("cycle") or {}
        if cycle.get("id") == cycle_id:
            dispatches = estado.get("dispatches") or []
        else:
            findings["notes"].append(
                "estado-atual.yaml não corresponde ao cycle_id do crash detectado — "
                "não confiado cegamente (FR-11); nenhum despacho lido do retrato."
            )
    else:
        findings["notes"].append("estado-atual.yaml ausente — reconciliação baseada só no diário (sem despachos rastreáveis via retrato).")

    board_text = board_path.read_text(encoding="utf-8") if board_path.exists() else ""

    for d in dispatches:
        findings["dispatches_checked"] += 1
        ticket = d.get("ticket")
        tickets_list = d.get("tickets") or ([ticket] if ticket else [])
        dispatch_id = d.get("dispatch_id")
        if dispatch_id:
            # Story E8.4: a lista COMPLETA de tickets de um despacho vive em
            # request.yaml (fonte de verdade em disco) — NUNCA em estado-atual.yaml,
            # cujo mini-serializer YAML só suporta dict-de-escalares em 1 nível (uma
            # lista aninhada dentro de um item de `dispatches[]` seria serializada
            # incorretamente como `str(list)`, achado real na auto-revisão desta
            # story). `estado-atual.yaml` carrega só `ticket` (singular, primário) +
            # `dispatch_id` (ponteiro); quando o ponteiro resolve, prefere a lista
            # completa e autoritativa do request.yaml.
            req_path = root / "dispatches" / str(dispatch_id) / "request.yaml"
            if req_path.exists():
                try:
                    req_doc = parse_estado(req_path.read_text(encoding="utf-8"))
                    req_tickets = req_doc.get("tickets")
                    if isinstance(req_tickets, list) and req_tickets:
                        tickets_list = req_tickets
                except OSError:
                    pass
        status = d.get("status")
        reasons = []
        if status not in ("concluido", "falhou", "reconciliado"):
            reasons.append(f"status do despacho ainda '{status}' no retrato (não confirmado concluído)")
        if board_text:
            for t in tickets_list:
                if not t:
                    continue
                t_status = ticket_status_in_board(board_text, t)
                if t_status == "em-implementacao":
                    reasons.append(f"ticket {t} ainda em 'em-implementacao' no board.yaml")
        worktree = d.get("worktree")
        if worktree not in (None, "null", ""):
            wt_path = Path(str(worktree))
            if not wt_path.exists():
                reasons.append(f"worktree registrado não existe mais em disco: {worktree}")
            else:
                reasons.append(f"worktree ainda presente em disco: {worktree} (verificar manualmente se é órfão/mergeável)")
        # Story E8.4 — cruza o marcador DONE.marker do contrato de despacho em disco,
        # quando o despacho carrega um `dispatch_id` (campo aditivo/opcional, retrocompatível
        # com despachos anteriores a esta story que nunca terão essa chave). Fecha o elo
        # explícito que a story pede: "reconciliável por E8.2's crash-recovery" — os dois
        # mecanismos (detect-crash/reconcile de E8.2 e o marcador de E8.4) convergem aqui,
        # não são caminhos paralelos divergentes.
        if dispatch_id:
            done_marker = root / "dispatches" / str(dispatch_id) / "DONE.marker"
            if not done_marker.exists():
                reasons.append(
                    f"despacho {dispatch_id} sem DONE.marker em disco (E8.4) — executor "
                    "pode ter morrido sem fechar o despacho; ver gerente_dispatch.py "
                    "reconcile-orphan-dispatch para diagnóstico detalhado"
                )
        if reasons:
            findings["orphans"].append({"ticket": ticket, "unit": d.get("unit"), "reasons": reasons})

    findings["needs_attention"] = len(findings["orphans"]) > 0
    findings["recommended_next_step"] = (
        "Para cada órfão: mover o Ticket para um estado explícito via `bagual-tickets` "
        "(nunca editar board.yaml à mão) — 'triado' com nota de recuperação de crash, ou "
        "'precisa-de-info' se o bloqueio for de informação. Nunca deixar 'em-implementacao' "
        "silenciosamente. Ver README.md § Checklist de reconciliação."
        if findings["needs_attention"]
        else "Nenhum despacho órfão encontrado; seguro prosseguir com o ciclo novo."
    )
    return findings


def cmd_reconcile(args: argparse.Namespace) -> int:
    root = Path(args.root)
    board_path = Path(args.board_path) if args.board_path else (root.parent / "tickets" / "board.yaml")
    findings = reconcile(root, args.cycle_id, board_path)

    ts = now_iso()
    summary = f"reconciliação de crash: {findings['dispatches_checked']} despacho(s) verificado(s), {len(findings['orphans'])} órfão(s)"
    _append_md(root / "diario.md", f"- [{ts[11:16]}] reconciliei: {summary}")
    _append_jsonl(root / "diario.jsonl", {"ts": ts, "cycle_id": args.cycle_id, "event": "reconciliei", "text": summary})
    _append_md(root / "diario.md", f"## CICLO-FIM {ts} {args.cycle_id} (reconciled)")
    _append_jsonl(root / "diario.jsonl", {"ts": ts, "cycle_id": args.cycle_id, "event": "CICLO-FIM", "reconciled": True})

    # Story E15.4 — `reconcile` também grava o sentinela para o `cycle_id` que reconciliou
    # (sempre — `--cycle-id` já é obrigatório nesta subcomando, diferente de detect-crash).
    try:
        sentinel_path = write_crash_check_sentinel(root, args.cycle_id, source="reconcile", detail={"needs_attention": findings.get("needs_attention")})
    except ValueError as exc:
        findings["sentinel_error"] = str(exc)
    else:
        findings["sentinel_written_for_cycle_id"] = args.cycle_id
        findings["sentinel_path"] = str(sentinel_path)

    print(json.dumps(findings, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def add_root_arg(sp: argparse.ArgumentParser) -> None:
    sp.add_argument("--root", default="project_controll/gerente", help="diretório de estado do Gerente (default: project_controll/gerente)")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    ps = sub.add_parser("write-snapshot", help="escreve estado-atual.yaml atomicamente")
    add_root_arg(ps)
    ps.add_argument("--marker", required=True, choices=["start", "end"])
    ps.add_argument("--cycle-id", required=True)
    ps.add_argument("--started-at", required=True)
    ps.add_argument("--ended-at", default=None)
    ps.add_argument("--phase", required=True, help="ler-estado|priorizar|despachar|revisar|registrar|parar")
    ps.add_argument("--stop-reason", default=None, help="cota|fila-vazia|bloqueio|null")
    ps.add_argument("--dispatches-json", default="[]")
    ps.add_argument("--pending-json", default="[]")
    ps.add_argument("--escalated-json", default="[]")
    ps.add_argument("--sample-review-json", default="[]", help="Story E9.5 — amostra de decisões automáticas p/ ratificação/correção no Briefing (AC2)")
    ps.add_argument("--dead-letter-json", default="[]", help="Story E9.5 — escalados parados além do limite (AC4)")
    ps.add_argument("--semgrep-fp-pending-json", default="[]", help="Story E13.4 — saída de read_fp_suspects.py list-pending (suspeitas de FP Semgrep pending_ratification)")
    ps.add_argument("--priorities-json", default="[]")
    ps.add_argument("--quota-five-hour", type=float, default=None)
    ps.add_argument("--quota-seven-day", type=float, default=None)
    ps.add_argument("--quota-source", default="rate-limits-state.json")
    ps.add_argument("--quota-read-at", default=None)
    ps.add_argument("--quota-self-tokens", type=int, default=None, help="Story E8.3 — tokens auto-rastreados acumulados no ciclo (ver gerente_quota.py check)")
    ps.add_argument("--quota-self-pct", type=float, default=None, help="Story E8.3 — self_tracked_tokens expresso como %% do orçamento configurado")
    ps.add_argument("--quota-stronger-pct", type=float, default=None, help="Story E8.3 — max(rate-limit pct, self-tracked pct), o sinal mais conservador")
    ps.add_argument("--quota-stronger-source", default=None, help="Story E8.3 — 'rate-limit' ou 'self-tracked', qual sinal venceu")
    ps.add_argument("--last-briefing-at", default=None)
    ps.set_defaults(func=cmd_write_snapshot)

    pa = sub.add_parser("append-diario", help="anexa uma entrada (ou marcador de ciclo) ao diário")
    add_root_arg(pa)
    pa.add_argument("--event", required=True, choices=VALID_EVENTS)
    pa.add_argument("--cycle-id", required=True)
    pa.add_argument("--text", default=None)
    pa.add_argument("--ts", default=None)
    pa.add_argument("--reconciled", action="store_true", help="só para --event CICLO-FIM: marca fechamento por crash-recovery")
    pa.set_defaults(func=cmd_append_diario)

    pal = sub.add_parser("acquire-lock", help="tenta adquirir o lock singleton")
    add_root_arg(pal)
    pal.add_argument("--pid", type=int, default=None, help="PID significativo do holder (opcional — best-effort, ver README)")
    pal.add_argument("--note", default=None)
    pal.add_argument("--cycle-id", default=None, help="cycle_id que este holder vai abrir — usado por detect-crash para não confundir um ciclo ativo com um crash")
    pal.add_argument("--stale-after-seconds", type=float, default=DEFAULT_STALE_AFTER_SECONDS)
    pal.set_defaults(func=cmd_acquire_lock)

    prl = sub.add_parser("refresh-lock", help="atualiza o heartbeat do lock (requer --token)")
    add_root_arg(prl)
    prl.add_argument("--token", required=True)
    prl.add_argument("--pid", type=int, default=None)
    prl.add_argument("--cycle-id", default=None)
    prl.set_defaults(func=cmd_refresh_lock)

    prel = sub.add_parser("release-lock", help="libera o lock (requer --token)")
    add_root_arg(prel)
    prel.add_argument("--token", required=True)
    prel.set_defaults(func=cmd_release_lock)

    pcl = sub.add_parser("check-lock", help="relatório somente-leitura do lock")
    add_root_arg(pcl)
    pcl.add_argument("--stale-after-seconds", type=float, default=DEFAULT_STALE_AFTER_SECONDS)
    pcl.set_defaults(func=cmd_check_lock)

    pdc = sub.add_parser("detect-crash", help="varre diario.jsonl por início sem fim")
    add_root_arg(pdc)
    pdc.add_argument("--stale-after-seconds", type=float, default=DEFAULT_STALE_AFTER_SECONDS, help="usado para não confundir um ciclo ativo (lock fresco) com um crash")
    pdc.add_argument("--cycle-id", default=None, help="Story E15.4 — cycle_id do ciclo NOVO em nome de quem este crash-check está rodando; se informado, grava o sentinela que gerente_dispatch.py::open-dispatch exige para este cycle_id (omitido: modo diagnóstico puro, retrocompatível, sem sentinela)")
    pdc.set_defaults(func=cmd_detect_crash)

    prc = sub.add_parser("reconcile", help="reconcilia despachos em voo de um ciclo morto")
    add_root_arg(prc)
    prc.add_argument("--cycle-id", required=True)
    prc.add_argument("--board-path", default=None, help="default: <root>/../tickets/board.yaml")
    prc.set_defaults(func=cmd_reconcile)

    return p


def main(argv: Optional[list] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
