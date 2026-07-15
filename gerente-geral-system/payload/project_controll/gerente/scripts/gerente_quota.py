#!/usr/bin/env python3
"""gerente_quota.py — E8.3 consciência de cota + auto-rastreio local do Gerente Geral.

Story E8.3 (ideias/sistema-artifacts/E8-3-consciencia-cota.md), PRD 00 FR-2,
ideias/epics.md Epic E8. Implementa o guardrail de cota: o Gerente lê
`~/.claude/rate-limits-state.json` como *um* insumo de cota, mas esse arquivo é escrito
pelo hook de statusline de uma sessão INTERATIVA — num ciclo headless ele pode ficar
CONGELADO (nunca atualizado) enquanto o ciclo continua consumindo cota de verdade. Por
isso este módulo também mantém um **auto-rastreio local** dos tokens gastos no próprio
ciclo (`record-usage`, alimentado explicitamente pela persona a cada despacho/turno) e o
`check` final sempre usa o **sinal mais forte** (mais conservador — o de percentual mais
alto) entre os dois, nunca só o snapshot potencialmente congelado.

100% local, cota só de assinatura — nenhum caminho deste módulo faz uma chamada de rede
ou invoca uma API metered. `read-limits` só LÊ um arquivo local
(`~/.claude/rate-limits-state.json`, o mesmo que o statusline nativo do Claude Code já
escreve); `record-usage`/`check` só leem/escrevem arquivos locais em
`project_controll/gerente/`. Não há SDK de billing, não há chamada HTTP em lugar nenhum
deste arquivo (grep por `urllib`/`http`/`socket`/`requests` neste módulo dá zero
resultados, verificado na auto-revisão — ver Dev Notes da story).

Comandos:
  read-limits    lê e normaliza ~/.claude/rate-limits-state.json (read-only, tolerante a
                 ausência/malformação — nunca lança exceção não tratada)
  record-usage   acumula uma estimativa de tokens gastos no ciclo atual em
                 quota-ciclo.json (reset automático quando o --cycle-id muda)
  check          combina os dois sinais (rate-limit lido + auto-rastreio acumulado),
                 devolve o sinal mais forte (mais conservador) e um veredito
                 start|stop contra o limiar configurável; opcionalmente grava
                 `parei-por-cota` no diario.md (via o mecanismo append-diario de E8.2)
                 quando o veredito é `stop`

Escrita atômica: reusa `write_atomic`/`_append_md`/`_append_jsonl`/`now_iso` de
`gerente_state.py` (E8.2) por IMPORT direto do arquivo irmão — não uma cópia colada, o
mesmo padrão de reuso que `gerente_state.py` já usa para `_bmad/scripts/memlog.py`.

Config (limiar + orçamento de auto-rastreio) — ordem de precedência (a mais alta vence):
  1. flag de CLI (ex.: --threshold-pct)
  2. variável de ambiente (ex.: GERENTE_QUOTA_THRESHOLD_PCT)
  3. `project_controll/gerente/quota.config.json` (commitado, editável pelo dono)
  4. default hardcoded neste arquivo (documentado abaixo)

Só biblioteca padrão (stdlib) — nenhuma dependência externa, mesma convenção dos scripts
irmãos deste diretório e de `project_controll/tickets/scripts/`.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

SCRIPT_DIR = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Defaults de configuração — documentados, deliberadamente conservadores.
# ---------------------------------------------------------------------------
# Limiar de uso (%) acima do qual o Gerente NÃO inicia nova unidade de trabalho.
# 85% deixa ~15 pontos percentuais de margem antes do limite real da assinatura —
# folga para o próprio despacho em andamento terminar sem estourar.
THRESHOLD_PCT_DEFAULT = 85.0

# Orçamento de tokens auto-rastreados que representa "100% consumido" para fins do
# SINAL AUTO-RASTREADO (não é o orçamento real da assinatura, que não é exposto por
# nenhuma API local — é um teto operacional deliberadamente conservador/pequeno,
# calibrável pelo dono via quota.config.json depois de observar alguns ciclos reais
# comparando self_tracked_pct vs. o rate-limit real quando o snapshot está fresco).
SELF_TRACKED_BUDGET_TOKENS_DEFAULT = 300_000

# Multiplicador de segurança aplicado a CADA estimativa registrada via record-usage,
# antes de somar ao acumulador — arredonda para cima propositalmente (constraint da
# story: "an approximation error never causes an overrun").
SAFETY_MULTIPLIER_DEFAULT = 1.15

# Idade (segundos) acima da qual o snapshot de rate-limits-state.json é sinalizado como
# possivelmente congelado (informativo — não muda o veredito por si só, porque o `check`
# já sempre usa o sinal mais forte; serve para o relato/diagnóstico).
STALE_SNAPSHOT_SECONDS_DEFAULT = 900.0  # 15min

# Kill-switch do guardrail inteiro (decisão do dono 2026-07-14). Quando False, o `check`
# ainda calcula/reporta os sinais mas FORÇA veredito "start" — o Gerente nunca para por cota.
# Default True (guardrail ligado). Desligado momentaneamente via quota.config.json enabled=false.
ENABLED_DEFAULT = True

# --- Estimativa pessimista de despachos in-flight (Epic E19.2, Furo 2) ---------------
# O acumulador `self_tracked_tokens_total` só avança quando `close-dispatch --tokens-used`
# roda (uma vez, no fim do despacho). Enquanto a ÁRVORE de um despacho executa (executor ->
# bagual-qa-run -> charters), o acumulador fica CONGELADO — então o `check` reportava folga
# falsa no meio da árvore (o incidente cycle-20260713-202850: 44% enquanto ~1M queimava, só
# visível na reconciliação manual). Fix: o `check` soma, ao sinal auto-rastreado, uma
# ESTIMATIVA por despacho ainda ABERTO (request.yaml presente, DONE.marker ausente) do ciclo
# atual que já passou de um PERÍODO DE GRAÇA — assim o guardrail dispara no meio da árvore
# mesmo com zero heartbeats e mesmo se o close-dispatch nunca rodar, sem falso-abortar um
# despacho recém-aberto (que ainda está dentro da graça). "stop" aqui não mata a árvore em
# voo — só impede INICIAR nova unidade e leva o Gerente à fase 'parar' (reconcilia/aguarda os
# despachos em voo), que é exatamente o cerco que faltava no incidente.
#
# Estimativa por despacho aberto (tokens) que "vale" como consumido enquanto ele está em voo
# além da graça. ~2/3 do orçamento default: um único despacho longo + trabalho prévio modesto
# cruza o limiar de 85%, mas um despacho rápido (que fecha dentro da graça) nunca dispara.
PER_DISPATCH_INFLIGHT_ESTIMATE_TOKENS_DEFAULT = 200_000

# Período de graça (segundos) antes de um despacho aberto passar a contar na estimativa acima.
# Abaixo disso ele é considerado "em andamento normal" e não infla a cota — evita o Gerente
# abortar um despacho que ele mesmo acabou de abrir. Acima disso, é "longo/suspeito" e entra
# na conta. 600s = 10min: mais que a maioria dos despachos saudáveis, menos que um runaway.
INFLIGHT_GRACE_SECONDS_DEFAULT = 600.0

# Layout do subtree de despachos (espelha gerente_dispatch.py — não importado para manter o
# acoplamento mínimo; só leitura de presença de arquivo + o campo cycle_id/opened_at).
DISPATCHES_DIRNAME = "dispatches"
REQUEST_FILENAME = "request.yaml"
DONE_FILENAME = "DONE.marker"

DEFAULT_LIMITS_PATH = "~/.claude/rate-limits-state.json"
CONFIG_FILENAME = "quota.config.json"


# ---------------------------------------------------------------------------
# Reuso de gerente_state.py (import direto do arquivo irmão — não cópia colada)
# ---------------------------------------------------------------------------
def _gerente_state():
    path = SCRIPT_DIR / "gerente_state.py"
    if not path.exists():
        print(f"erro: gerente_state.py não encontrado em {path} — não é possível reusar write_atomic/append-diario", file=sys.stderr)
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


def now_iso() -> str:
    return _gs().now_iso()


def write_atomic(path: Path, text: str) -> None:
    _gs().write_atomic(path, text)


# ---------------------------------------------------------------------------
# Config resolution
# ---------------------------------------------------------------------------
def _load_config_file(root: Path) -> dict:
    cfg_path = root / CONFIG_FILENAME
    if not cfg_path.exists():
        return {}
    try:
        data = json.loads(cfg_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def resolve_threshold_pct(root: Path, cli_value: Optional[float]) -> float:
    if cli_value is not None:
        return cli_value
    env = os.environ.get("GERENTE_QUOTA_THRESHOLD_PCT")
    if env:
        try:
            return float(env)
        except ValueError:
            pass
    cfg = _load_config_file(root)
    if "threshold_pct" in cfg:
        try:
            return float(cfg["threshold_pct"])
        except (TypeError, ValueError):
            pass
    return THRESHOLD_PCT_DEFAULT


def resolve_self_tracked_budget(root: Path, cli_value: Optional[int]) -> int:
    if cli_value is not None:
        return cli_value
    env = os.environ.get("GERENTE_QUOTA_SELF_TRACKED_BUDGET_TOKENS")
    if env:
        try:
            return int(env)
        except ValueError:
            pass
    cfg = _load_config_file(root)
    if "self_tracked_budget_tokens" in cfg:
        try:
            return int(cfg["self_tracked_budget_tokens"])
        except (TypeError, ValueError):
            pass
    return SELF_TRACKED_BUDGET_TOKENS_DEFAULT


def resolve_safety_multiplier(root: Path, cli_value: Optional[float]) -> float:
    if cli_value is not None:
        return cli_value
    env = os.environ.get("GERENTE_QUOTA_SAFETY_MULTIPLIER")
    if env:
        try:
            return float(env)
        except ValueError:
            pass
    cfg = _load_config_file(root)
    if "safety_multiplier" in cfg:
        try:
            return float(cfg["safety_multiplier"])
        except (TypeError, ValueError):
            pass
    return SAFETY_MULTIPLIER_DEFAULT


def resolve_stale_snapshot_seconds(root: Path, cli_value: Optional[float]) -> float:
    if cli_value is not None:
        return cli_value
    env = os.environ.get("GERENTE_QUOTA_STALE_SNAPSHOT_SECONDS")
    if env:
        try:
            return float(env)
        except ValueError:
            pass
    cfg = _load_config_file(root)
    if "stale_snapshot_seconds" in cfg:
        try:
            return float(cfg["stale_snapshot_seconds"])
        except (TypeError, ValueError):
            pass
    return STALE_SNAPSHOT_SECONDS_DEFAULT


def resolve_enabled(root: Path, cli_value: Optional[bool]) -> bool:
    if cli_value is not None:
        return cli_value
    env = os.environ.get("GERENTE_QUOTA_ENABLED")
    if env is not None:
        return env.strip().lower() not in ("0", "false", "no", "off", "")
    cfg = _load_config_file(root)
    if "enabled" in cfg:
        return bool(cfg["enabled"])
    return ENABLED_DEFAULT


def resolve_per_dispatch_inflight_estimate(root: Path, cli_value: Optional[int]) -> int:
    if cli_value is not None:
        return cli_value
    env = os.environ.get("GERENTE_QUOTA_PER_DISPATCH_INFLIGHT_ESTIMATE_TOKENS")
    if env:
        try:
            return int(env)
        except ValueError:
            pass
    cfg = _load_config_file(root)
    if "per_dispatch_inflight_estimate_tokens" in cfg:
        try:
            return int(cfg["per_dispatch_inflight_estimate_tokens"])
        except (TypeError, ValueError):
            pass
    return PER_DISPATCH_INFLIGHT_ESTIMATE_TOKENS_DEFAULT


def resolve_inflight_grace_seconds(root: Path, cli_value: Optional[float]) -> float:
    if cli_value is not None:
        return cli_value
    env = os.environ.get("GERENTE_QUOTA_INFLIGHT_GRACE_SECONDS")
    if env:
        try:
            return float(env)
        except ValueError:
            pass
    cfg = _load_config_file(root)
    if "inflight_grace_seconds" in cfg:
        try:
            return float(cfg["inflight_grace_seconds"])
        except (TypeError, ValueError):
            pass
    return INFLIGHT_GRACE_SECONDS_DEFAULT


# ---------------------------------------------------------------------------
# Estimativa de despachos in-flight (E19.2) — leitura só-presença do subtree
# ---------------------------------------------------------------------------
def _read_request_field(req_path: Path, field: str) -> Optional[str]:
    """Lê um campo escalar de topo do request.yaml sem dependência de YAML — o arquivo é
    escrito por gerente_dispatch.py open-dispatch num formato controlado (uma chave por
    linha no topo). Só campos escalares simples (cycle_id, opened_at)."""
    try:
        for line in req_path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith(f"{field}:"):
                val = stripped.split(":", 1)[1].strip()
                return val.strip('"').strip("'") or None
    except OSError:
        return None
    return None


def count_inflight_dispatches(root: Path, cycle_id: str, grace_seconds: float, now_epoch: Optional[float] = None) -> dict:
    """Conta despachos ABERTOS (request.yaml presente, DONE.marker ausente) do ciclo atual que
    já passaram do período de graça. Devolve {count, ids, total_open, within_grace}. Nunca
    levanta — um subtree ausente/ilegível resulta em count 0 (degrada seguro, nunca falso-stop)."""
    ddir = root / DISPATCHES_DIRNAME
    result = {"count": 0, "ids": [], "total_open": 0, "within_grace": 0}
    if not ddir.is_dir():
        return result
    now = now_epoch if now_epoch is not None else time.time()
    for sub in sorted(ddir.iterdir()):
        if not sub.is_dir():
            continue
        req = sub / REQUEST_FILENAME
        done = sub / DONE_FILENAME
        if not req.is_file() or done.exists():
            continue  # não aberto, ou já fechado
        # Filtra pelo ciclo atual: um órfão de ciclo anterior não conta na cota DESTE ciclo
        # (o reconcile trata órfãos antigos; a cota é por-ciclo).
        req_cycle = _read_request_field(req, "cycle_id")
        if req_cycle is not None and req_cycle != cycle_id:
            continue
        result["total_open"] += 1
        # Idade: usa opened_at do request.yaml; se ilegível, trata como ALÉM da graça
        # (pessimista — um despacho cuja idade não dá pra provar conta como suspeito).
        opened_at = _read_request_field(req, "opened_at")
        age_ok = True  # default: conta (pessimista)
        if opened_at:
            try:
                dt = datetime.fromisoformat(opened_at.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                age = now - dt.timestamp()
                age_ok = age >= grace_seconds
            except (ValueError, OverflowError):
                age_ok = True  # data malformada -> pessimista
        if age_ok:
            result["count"] += 1
            result["ids"].append(sub.name)
        else:
            result["within_grace"] += 1
    return result


# ---------------------------------------------------------------------------
# read-limits — parser real de ~/.claude/rate-limits-state.json
# ---------------------------------------------------------------------------
# Formato observado em produção (lido diretamente do arquivo real na Story E8.3):
#   {"updated_at": 1783807722, "model": "Opus 4.8 (1M context)",
#    "five_hour": {"used_percentage": 9, "resets_at": 1783822800},
#    "seven_day": {"used_percentage": 25, "resets_at": 1783843200}}
# `updated_at`/`resets_at` são epoch seconds (int). Este parser é DEFENSIVO por
# construção — nunca lança para fora de `read_limits`: arquivo ausente, JSON malformado,
# ou chaves faltando resultam em `ok: False` com `five_hour_used_pct`/`seven_day_used_pct`
# = None, nunca num crash. `check` trata None como sinal indisponível (não como 0 — ver
# `check`) e sinaliza `degraded_rate_limit_signal: True`.
def read_limits(path: Path, stale_after_seconds: float) -> dict:
    result: dict[str, Any] = {
        "ok": False,
        "path": str(path),
        "five_hour_used_pct": None,
        "seven_day_used_pct": None,
        "updated_at_epoch": None,
        "updated_at_iso": None,
        "age_seconds": None,
        "stale": None,
        "model": None,
        "error": None,
    }
    if not path.exists():
        result["error"] = "missing"
        return result
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        result["error"] = f"unreadable: {exc}"
        return result
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        result["error"] = f"malformed: {exc}"
        return result
    if not isinstance(data, dict):
        result["error"] = "unexpected-schema: top-level is not an object"
        return result

    result["model"] = data.get("model")

    updated_at = data.get("updated_at")
    if isinstance(updated_at, (int, float)):
        result["updated_at_epoch"] = updated_at
        try:
            result["updated_at_iso"] = datetime.fromtimestamp(updated_at, tz=timezone.utc).astimezone().isoformat(timespec="seconds")
        except (OSError, OverflowError, ValueError):
            result["updated_at_iso"] = None
        age = time.time() - updated_at
        result["age_seconds"] = age
        result["stale"] = age > stale_after_seconds

    five_hour = data.get("five_hour")
    if isinstance(five_hour, dict) and isinstance(five_hour.get("used_percentage"), (int, float)):
        result["five_hour_used_pct"] = float(five_hour["used_percentage"])
        result["five_hour_resets_at_epoch"] = five_hour.get("resets_at")

    seven_day = data.get("seven_day")
    if isinstance(seven_day, dict) and isinstance(seven_day.get("used_percentage"), (int, float)):
        result["seven_day_used_pct"] = float(seven_day["used_percentage"])
        result["seven_day_resets_at_epoch"] = seven_day.get("resets_at")

    if result["five_hour_used_pct"] is None and result["seven_day_used_pct"] is None:
        result["error"] = "unexpected-schema: nem 'five_hour.used_percentage' nem 'seven_day.used_percentage' presentes/numéricos"
        return result

    result["ok"] = True
    return result


def cmd_read_limits(args: argparse.Namespace) -> int:
    root = Path(args.root)
    path = Path(args.path).expanduser()
    stale_after = resolve_stale_snapshot_seconds(root, args.stale_snapshot_seconds)
    result = read_limits(path, stale_after)
    print(json.dumps(result, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------------------
# record-usage — auto-rastreio local dos tokens do ciclo atual
# ---------------------------------------------------------------------------
# quota-ciclo.json — estado do CICLO ATUAL, sobrescrito a cada ciclo (mesma filosofia de
# estado-atual.yaml em E8.2), NUNCA histórico entre ciclos. Reseta automaticamente
# quando --cycle-id muda em relação ao que está gravado (um ciclo novo começa do zero).
# Schema:
#   {"cycle_id": str, "self_tracked_tokens_total": int, "updated_at": ISO,
#    "entries": [{"ts": ISO, "tokens_raw": int, "tokens_adjusted": int, "note": str|null}]}
# `entries` é só diagnóstico (cauda limitada a ENTRIES_TAIL_MAX) — o total autoritativo é
# sempre `self_tracked_tokens_total`, mantido como contador explícito (nunca derivado por
# soma de `entries`), para que aparar a cauda nunca perca precisão do total.
ENTRIES_TAIL_MAX = 200


def _quota_ciclo_path(root: Path) -> Path:
    return root / "quota-ciclo.json"


def _load_quota_ciclo(root: Path) -> dict:
    path = _quota_ciclo_path(root)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def record_usage(root: Path, cycle_id: str, tokens: int, note: Optional[str], multiplier: float, reset: bool) -> dict:
    if tokens < 0:
        raise ValueError("--tokens deve ser >= 0")

    existing = {} if reset else _load_quota_ciclo(root)
    same_cycle = existing.get("cycle_id") == cycle_id
    if not same_cycle:
        # Ciclo novo (ou nenhum estado anterior, ou reset explícito) — reinicia do zero.
        # Este é o único mecanismo de "reset": não há subcomando `reset-cycle` separado
        # porque o Gerente já sempre chama record-usage com o cycle_id do ciclo atual;
        # o auto-reset por mudança de cycle_id cobre o caso real sem estado extra.
        total = 0
        entries: list[dict] = []
    else:
        total = int(existing.get("self_tracked_tokens_total") or 0)
        entries = list(existing.get("entries") or [])

    adjusted = math.ceil(tokens * multiplier)
    total += adjusted
    ts = now_iso()
    entries.append({"ts": ts, "tokens_raw": tokens, "tokens_adjusted": adjusted, "note": note})
    if len(entries) > ENTRIES_TAIL_MAX:
        entries = entries[-ENTRIES_TAIL_MAX:]

    doc = {
        "cycle_id": cycle_id,
        "self_tracked_tokens_total": total,
        "updated_at": ts,
        "entries": entries,
    }
    write_atomic(_quota_ciclo_path(root), json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
    return doc


def cmd_record_usage(args: argparse.Namespace) -> int:
    root = Path(args.root)
    multiplier = resolve_safety_multiplier(root, args.multiplier)
    try:
        doc = record_usage(root, args.cycle_id, args.tokens, args.note, multiplier, args.reset)
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps({
        "ok": True,
        "path": str(_quota_ciclo_path(root)),
        "cycle_id": doc["cycle_id"],
        "self_tracked_tokens_total": doc["self_tracked_tokens_total"],
        "multiplier_applied": multiplier,
        "updated_at": doc["updated_at"],
    }, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------------------
# check — combina os dois sinais, devolve o mais forte + veredito start|stop
# ---------------------------------------------------------------------------
def compute_check(
    root: Path,
    cycle_id: str,
    limits_path: Path,
    threshold_pct: float,
    self_tracked_budget_tokens: int,
    stale_after_seconds: float,
    per_dispatch_inflight_estimate_tokens: int = PER_DISPATCH_INFLIGHT_ESTIMATE_TOKENS_DEFAULT,
    inflight_grace_seconds: float = INFLIGHT_GRACE_SECONDS_DEFAULT,
    enabled: bool = ENABLED_DEFAULT,
) -> dict:
    limits = read_limits(limits_path, stale_after_seconds)

    # Sinal de rate-limit: pior das duas janelas (5h/7d) — se o arquivo estiver
    # ausente/malformado, o sinal fica indisponível (None), NUNCA tratado como 0 de
    # forma silenciosa: sinalizamos degraded_rate_limit_signal e seguimos confiando no
    # auto-rastreio (que também começa em 0 num ciclo novo — primeira ativação de
    # sempre passa normalmente, sem falso-stop).
    degraded_rate_limit = not limits["ok"]
    five = limits.get("five_hour_used_pct")
    seven = limits.get("seven_day_used_pct")
    candidates = [v for v in (five, seven) if isinstance(v, (int, float))]
    rate_limit_pct = max(candidates) if candidates else 0.0

    quota_ciclo = _load_quota_ciclo(root)
    same_cycle = quota_ciclo.get("cycle_id") == cycle_id
    recorded_tokens = int(quota_ciclo.get("self_tracked_tokens_total") or 0) if same_cycle else 0

    # E19.2 (Furo 2): fecha a cegueira temporal — soma ao acumulado uma estimativa por
    # despacho ainda ABERTO (do ciclo atual, além da graça). Sem isso, o `check` no meio da
    # árvore de um despacho reportava folga falsa (o acumulador só avança no close-dispatch).
    inflight = count_inflight_dispatches(root, cycle_id, inflight_grace_seconds)
    inflight_estimate_tokens = inflight["count"] * max(0, per_dispatch_inflight_estimate_tokens)
    self_tracked_tokens = recorded_tokens + inflight_estimate_tokens
    # Arredonda para CIMA e limita a 100 — enviesado propositalmente para "parar cedo"
    # (constraint da story) em vez de subestimar por causa de arredondamento.
    self_tracked_pct = min(100.0, math.ceil((self_tracked_tokens / self_tracked_budget_tokens) * 100.0)) if self_tracked_budget_tokens > 0 else 0.0

    if rate_limit_pct >= self_tracked_pct:
        stronger_pct = rate_limit_pct
        stronger_source = "rate-limit"
    else:
        stronger_pct = self_tracked_pct
        stronger_source = "self-tracked"

    natural_verdict = "stop" if stronger_pct >= threshold_pct else "start"

    # Kill-switch (flag `enabled`, default true): quando DESLIGADO, o guardrail continua
    # COMPUTANDO e reportando os dois sinais (diagnóstico segue útil) mas o veredito é
    # FORÇADO a "start" — o Gerente nunca para por cota. Decisão do dono (2026-07-14):
    # desligar momentaneamente para destravar throughput; reversível pondo enabled=true de
    # volta em quota.config.json. NÃO é o mesmo que orçamento alto — é o desligamento
    # explícito do controle, marcado como tal em todo lugar.
    verdict = natural_verdict if enabled else "start"

    inflight_note = (
        f", +{inflight_estimate_tokens} estimados de {inflight['count']} despacho(s) in-flight além da graça"
        if inflight["count"] > 0 else ""
    )
    disabled_note = (
        ""
        if enabled
        else f" ⚠️ GUARDRAIL DESLIGADO (flag enabled=false) — veredito natural seria '{natural_verdict}', forçado a 'start' (nunca para por cota); reative com enabled=true em quota.config.json."
    )
    reasoning = (
        f"sinal rate-limit={rate_limit_pct:.1f}% (fonte: {limits.get('path')}, "
        f"{'INDISPONÍVEL/degradado' if degraded_rate_limit else ('congelado há ' + str(int(limits.get('age_seconds') or 0)) + 's' if limits.get('stale') else 'fresco')}); "
        f"sinal auto-rastreado={self_tracked_pct:.1f}% ({recorded_tokens} tokens registrados{inflight_note} / orçamento {self_tracked_budget_tokens}, "
        f"ciclo {'confere' if same_cycle else 'novo/zerado'}); "
        f"mais forte = {stronger_source} ({stronger_pct:.1f}%) vs. limiar {threshold_pct:.1f}% -> {verdict}{disabled_note}"
    )

    return {
        "ok": True,
        "cycle_id": cycle_id,
        "verdict": verdict,
        "guardrail_enabled": enabled,
        "natural_verdict": natural_verdict,
        "threshold_pct": threshold_pct,
        "stronger_signal_pct": stronger_pct,
        "stronger_signal_source": stronger_source,
        "rate_limit": {
            "pct": rate_limit_pct,
            "five_hour_used_pct": five,
            "seven_day_used_pct": seven,
            "degraded": degraded_rate_limit,
            "stale": limits.get("stale"),
            "age_seconds": limits.get("age_seconds"),
            "source_path": limits.get("path"),
            "error": limits.get("error"),
        },
        "self_tracked": {
            "pct": self_tracked_pct,
            "tokens_total": self_tracked_tokens,
            "recorded_tokens": recorded_tokens,
            "inflight_estimate_tokens": inflight_estimate_tokens,
            "inflight_dispatches_counted": inflight["count"],
            "inflight_dispatches_within_grace": inflight["within_grace"],
            "inflight_dispatch_ids": inflight["ids"],
            "budget_tokens": self_tracked_budget_tokens,
            "budget_is_estimate": True,
            "same_cycle": same_cycle,
        },
        "reasoning": reasoning,
        # Args prontos para repassar a `gerente_state.py write-snapshot` no fechamento
        # do ciclo (fase "parar") — evita a persona recompor os nomes de flag na mão.
        "write_snapshot_quota_args": {
            "--quota-five-hour": five,
            "--quota-seven-day": seven,
            "--quota-source": "rate-limits-state.json",
            "--quota-read-at": limits.get("updated_at_iso"),
            "--quota-self-tokens": recorded_tokens,
            "--quota-self-pct": self_tracked_pct,
            "--quota-stronger-pct": stronger_pct,
            "--quota-stronger-source": stronger_source,
        },
    }


def cmd_check(args: argparse.Namespace) -> int:
    root = Path(args.root)
    limits_path = Path(args.limits_path).expanduser()
    threshold_pct = resolve_threshold_pct(root, args.threshold_pct)
    budget = resolve_self_tracked_budget(root, args.self_tracked_budget_tokens)
    stale_after = resolve_stale_snapshot_seconds(root, args.stale_snapshot_seconds)
    inflight_estimate = resolve_per_dispatch_inflight_estimate(root, args.per_dispatch_inflight_estimate_tokens)
    inflight_grace = resolve_inflight_grace_seconds(root, args.inflight_grace_seconds)
    enabled = resolve_enabled(root, args.enabled)

    result = compute_check(root, args.cycle_id, limits_path, threshold_pct, budget, stale_after, inflight_estimate, inflight_grace, enabled)

    if result["verdict"] == "stop" and args.stop_diario:
        gs = _gs()
        text = f"parei-por-cota: {result['reasoning']}"
        gs._append_md(root / "diario.md", f"- [{now_iso()[11:16]}] parei: {text}")
        gs._append_jsonl(root / "diario.jsonl", {"ts": now_iso(), "cycle_id": args.cycle_id, "event": "parei", "text": text})
        result["diario_recorded"] = True
    else:
        result["diario_recorded"] = False

    print(json.dumps(result, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def add_root_arg(sp: argparse.ArgumentParser) -> None:
    sp.add_argument("--root", default="project_controll/gerente", help="diretório de estado do Gerente (default: project_controll/gerente)")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("read-limits", help="lê e normaliza ~/.claude/rate-limits-state.json (read-only)")
    add_root_arg(pr)
    pr.add_argument("--path", default=DEFAULT_LIMITS_PATH, help=f"caminho do snapshot (default: {DEFAULT_LIMITS_PATH})")
    pr.add_argument("--stale-snapshot-seconds", type=float, default=None, help=f"idade (s) acima da qual o snapshot é sinalizado como possivelmente congelado (default: {STALE_SNAPSHOT_SECONDS_DEFAULT})")
    pr.set_defaults(func=cmd_read_limits)

    pu = sub.add_parser("record-usage", help="acumula uma estimativa de tokens gastos no ciclo atual")
    add_root_arg(pu)
    pu.add_argument("--cycle-id", required=True)
    pu.add_argument("--tokens", type=int, required=True, help="estimativa BRUTA de tokens gastos nesta unidade (sub-agente/turno) — o multiplicador de segurança é aplicado aqui dentro")
    pu.add_argument("--note", default=None, help="ex.: 'sub-agent:TCK-xxxx dispatch' ou 'turn-estimate:fase-despachar'")
    pu.add_argument("--multiplier", type=float, default=None, help=f"override do multiplicador de segurança (default resolvido: {SAFETY_MULTIPLIER_DEFAULT})")
    pu.add_argument("--reset", action="store_true", help="força zerar o acumulador antes de somar, mesmo que --cycle-id bata com o gravado")
    pu.set_defaults(func=cmd_record_usage)

    pc = sub.add_parser("check", help="combina rate-limit + auto-rastreio, devolve o sinal mais forte e um veredito start|stop")
    add_root_arg(pc)
    pc.add_argument("--cycle-id", required=True)
    pc.add_argument("--limits-path", default=DEFAULT_LIMITS_PATH)
    pc.add_argument("--threshold-pct", type=float, default=None, help=f"override do limiar (default resolvido: {THRESHOLD_PCT_DEFAULT})")
    pc.add_argument("--self-tracked-budget-tokens", type=int, default=None, help=f"override do orçamento de auto-rastreio (default resolvido: {SELF_TRACKED_BUDGET_TOKENS_DEFAULT})")
    pc.add_argument("--stale-snapshot-seconds", type=float, default=None)
    pc.add_argument("--per-dispatch-inflight-estimate-tokens", type=int, default=None, help=f"E19.2: tokens estimados por despacho in-flight (além da graça) somados ao sinal auto-rastreado (default resolvido: {PER_DISPATCH_INFLIGHT_ESTIMATE_TOKENS_DEFAULT}; 0 desliga a estimativa)")
    pc.add_argument("--inflight-grace-seconds", type=float, default=None, help=f"E19.2: período de graça (s) antes de um despacho aberto contar na estimativa (default resolvido: {INFLIGHT_GRACE_SECONDS_DEFAULT})")
    pc.add_argument("--enabled", action=argparse.BooleanOptionalAction, default=None, help=f"liga/desliga o guardrail inteiro (--no-enabled força veredito sempre 'start', nunca para por cota; default resolvido: {ENABLED_DEFAULT}, override principal é 'enabled' em quota.config.json)")
    pc.add_argument("--stop-diario", action="store_true", help="se o veredito for 'stop', grava 'parei-por-cota' em diario.md/.jsonl (evento 'parei', via o mecanismo append-diario de E8.2)")
    pc.set_defaults(func=cmd_check)

    return p


def main(argv: Optional[list] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
