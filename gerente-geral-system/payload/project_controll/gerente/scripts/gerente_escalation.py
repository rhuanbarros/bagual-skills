#!/usr/bin/env python3
"""gerente_escalation.py — E9.5 Gerente decide os escalados + dead-letter + reconciliação de órfãos.

Story E9.5 (ideias/sistema-artifacts/E9-5-gerente-decide-escalados.md), PRD 02 FR-6,
ideias/epics.md Epic E9. `bagual-tickets` (Story E9.4) já comita a `trilha` dos casos
óbvios e marca `escalonar: true` no índice `board.yaml` para os ambíguos. Este script dá
ao Gerente Geral (`.claude/skills/bagual-gerente-geral/SKILL.md`) as primitivas MECÂNICAS de que
precisa para lidar com o outro lado desse contrato — ele mesmo (via Protocolo do
Oráculo, E9.1/E9.2) decide a `trilha` dos escalados, mas a decisão em si (julgamento)
nunca vive aqui; só o que É mecânico/verificável vive aqui:

  * `list-escalated`    — varre `board.yaml` (o ÍNDICE, nunca abre cada `.md` — F20) e
                           devolve só os tickets com `escalonar: true`. Como o SKILL
                           (E9.4) só marca `escalonar: true` quando NÃO comitou uma
                           trilha, e desmarca (`escalonar: false`) no momento em que a
                           trilha É comitada (pela skill OU, a partir desta story, pelo
                           Gerente via `bagual-tickets` Resolver), este comando nunca
                           re-lista um ticket cuja trilha já foi decidida — a exclusão de
                           "já resolvido pela skill" é uma PROPRIEDADE DO ESTADO
                           (escalonar: false), não um filtro adicional que este script
                           precisa reimplementar.
  * `dead-letter-check`  — dos escalados, quais estão parados (sem nenhuma atualização)
                           além de um limite configurável de dias — para forçar o
                           Gerente a olhar via o Briefing (F20 hardening: "escalado
                           nunca-decidido não apodrece").
  * `sample-decisions`   — amostra tickets cuja `trilha` foi comitada AUTOMATICAMENTE
                           pela skill (`trilha` não-nulo + `escalonar: false`) e ainda
                           não foram revisados pelo Gerente, para ratificação/correção
                           por amostragem no Briefing (AC2). Estado de "já amostrado"
                           persistido em `sampled-decisions.json` (artefato operacional
                           do PRÓPRIO Gerente, nunca no ticket/board — não precisa
                           reeditar `bagual-tickets` para isso).
  * `record-sample-review` — grava o veredito (ratificado/corrigido) de uma amostra
                           revisada, atualizando `sampled-decisions.json` atomicamente.
                           Story E15.3 (T2.3): `--verdict corrigido` agora EXIGE os
                           campos de rastro de decisão (`--trilha-auto`/
                           `--trilha-corrigida`/`--question`/`--justification`/
                           `--context`) e, na MESMA invocação, chama
                           `gerente_oracle.py::record_decision()` +
                           `set_ratification(status="corrected")` — por IMPORT DIRETO
                           (nunca subprocess) — ANTES de gravar `sampled-decisions.json`.
                           Isso mecaniza o que antes era um contrato comportamental da
                           persona ("depois de record-sample-review --verdict corrigido,
                           sempre rode record-decision + set-ratification também, nunca só
                           um dos dois" — ver `gerente-geral.md` § "priorizar" pré-E15.3):
                           uma chamada só produz, por construção, os DOIS artefatos
                           (`sampled-decisions.json` + a Entrada de Ledger `ratification:
                           corrected`) — nunca um sem o outro. Mesma disciplina de ordem
                           de E15.2 (`wiki/ledger/padrao/
                           mecanizar-efeito-colateral-antes-da-escrita-que-finaliza-a-
                           operacao.md`): o efeito colateral novo (Ledger) roda ANTES da
                           escrita que finaliza a operação (`sampled-decisions.json`) —
                           se `record_decision`/`set_ratification` falhar, o comando
                           inteiro falha (exit != 0) e `sampled-decisions.json` NUNCA é
                           tocado (tudo-ou-nada: nunca "amostra revisada" sem a Entrada de
                           Ledger correspondente). `--verdict ratificado` é inalterado —
                           continua só gravando `sampled-decisions.json`, sem tocar o
                           Ledger.
  * `orphan-sweep`       — reverte `em-implementacao` -> `pronto-para-implementar` para
                           tickets órfãos, usando EXATAMENTE a mesma definição de
                           staleness (heartbeat do lock singleton) que
                           `gerente_state.py` (Story E8.2) já usa para `detect-crash`/
                           `reconcile` — importado por arquivo (`_read_lock_info`/
                           `lock_is_stale`/`DEFAULT_STALE_AFTER_SECONDS`), nunca um
                           timeout paralelo reinventado. A varredura só roda quando o
                           lock do Gerente NÃO está held-e-fresco (nenhum ciclo vivo) —
                           é o mesmo invariante de singleton que `detect-crash` usa para
                           nunca confundir um ciclo saudável em andamento com um crash;
                           aqui aplicado de forma ainda mais conservadora (a varredura
                           inteira é pulada, sem tocar ticket nenhum, sempre que existe
                           QUALQUER lock vivo — mesmo que ele não esteja "olhando" para
                           o ticket específico). Diferente de `reconcile()` (que exige um
                           `--cycle-id` de um crash já detectado e itera só os despachos
                           rastreados em `estado-atual.yaml`), este comando é um
                           complementar mais amplo: varre `board.yaml` inteiro por
                           `status: em-implementacao`, sem depender de nenhum despacho
                           ter sido registrado — rede de segurança para o caso em que o
                           próprio rastro de despacho se perdeu. Ao contrário de
                           `reconcile` (que é só-leitura e recomenda `bagual-tickets`
                           para a mutação), este comando ESCREVE — é o único ponto deste
                           script que muta um `.md` de ticket diretamente, e é
                           deliberado: a reversão é uma correção mecânica de UM campo
                           (`status`) sob uma condição objetiva e auditável (nenhum lock
                           vivo), sem nenhum julgamento de conteúdo — a mesma categoria
                           de exceção que `transition_ledger_entry.py` já é para Entradas
                           de Ledger (mutação direta e mecânica, não uma skill
                           conversacional). Depois de reverter, regenera `board.yaml`
                           reusando `rebuild_board.py::load_tickets`/`render_board_yaml`
                           (import direto, nunca cópia colada) para manter o índice
                           coerente com a fonte de verdade (os `.md`).

A decisão de QUAL trilha atribuir a um escalado, e SE promover a decisão ao Ledger,
continua sendo julgamento do Gerente via o Protocolo do Oráculo já existente
(`gerente_oracle.py record-decision`/`set-ratification`) — não há heurística fixa aqui
nem em nenhum script novo desta story (PRD 02 FR-6, decidido 2026-07-10: "não há
heurística fixa para promover uma decisão de trilha a entrada de Ledger; é julgamento
autônomo do Gerente/oráculo"). O COMMIT da trilha decidida no `.md`/`board.yaml` do
ticket é feito pela persona invocando `bagual-tickets` (Resolver, composição — nunca
editado nesta story, ver `.claude/skills/bagual-gerente-geral/SKILL.md` § "Decisão de escalados
(E9.5)").

`board.yaml` tem um formato fixo e simples demais para justificar um parser YAML
genérico (mesma decisão já tomada em `gerente_state.py`/`classify_trilha.py`/
`rebuild_board.py` para os respectivos schemas deles) — `parse_board_yaml` abaixo é um
parser minimalista casado EXATAMENTE com o formato que `rebuild_board.py::render_board_yaml`
escreve (2 espaços = id do ticket, 4 espaços = campo, 6 espaços = item de lista).

Só biblioteca padrão (stdlib) — nenhuma dependência externa, mesma convenção dos
scripts irmãos em `project_controll/gerente/scripts/` e `project_controll/tickets/scripts/`.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
GERENTE_DIR = SCRIPT_DIR.parent
PROJECT_CONTROLL_DIR = GERENTE_DIR.parent
REPO_ROOT = PROJECT_CONTROLL_DIR.parent
DEFAULT_BOARD_PATH = PROJECT_CONTROLL_DIR / "tickets" / "board.yaml"
DEFAULT_TICKETS_DIR = PROJECT_CONTROLL_DIR / "tickets"
DEFAULT_GERENTE_ROOT = GERENTE_DIR
DEFAULT_SAMPLED_STATE_PATH = GERENTE_DIR / "sampled-decisions.json"
# Story E15.3 — default do Ledger consumido/gravado por `record-sample-review --verdict
# corrigido` via `gerente_oracle.py::record_decision`/`set_ratification` (mesma árvore
# que `gerente_oracle.py`/`gerente_style.py` usam como default, só que resolvido de forma
# ABSOLUTA a partir de `REPO_ROOT` em vez do default relativo `"wiki/ledger"`
# daqueles scripts — nunca depende do CWD de onde `gerente_escalation.py` foi invocado).
DEFAULT_LEDGER_ROOT = REPO_ROOT / "wiki" / "ledger"
ESCALATION_CONFIG_FILENAME = "escalation.config.json"

DEFAULT_DEAD_LETTER_LIMIT_DAYS = 3
DEFAULT_SAMPLE_SIZE = 3


# ---------------------------------------------------------------------------
# Reuso por import direto do arquivo (não cópia colada) — mesma técnica de
# `_memlog()` em gerente_state.py / `_load_module()` em gerente_oracle.py.
# ---------------------------------------------------------------------------
def _load_module(path: Path, name: str):
    if not path.exists():
        print(f"erro: módulo não encontrado em {path} — não é possível reusar suas primitivas", file=sys.stderr)
        sys.exit(2)
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_GS = None
_RB = None
_OC = None


def gs():
    """gerente_state.py (Story E8.2) — lock singleton/heartbeat/staleness (reusado
    literalmente por `orphan-sweep`, nunca reimplementado) + `write_atomic`."""
    global _GS
    if _GS is None:
        _GS = _load_module(SCRIPT_DIR / "gerente_state.py", "gerente_state")
    return _GS


def rb():
    """rebuild_board.py (Story E5.2/E9.4) — regenera board.yaml a partir dos `.md`
    depois de `orphan-sweep` mutar um ticket, reusando a mesma serialização já provada
    correta (nunca uma cópia colada do writer de board.yaml)."""
    global _RB
    if _RB is None:
        _RB = _load_module(PROJECT_CONTROLL_DIR / "tickets" / "scripts" / "rebuild_board.py", "rebuild_board")
    return _RB


def oc():
    """gerente_oracle.py (Story E9.1/E9.2) — reusado por IMPORT DIRETO (nunca subprocess)
    para que `record-sample-review --verdict corrigido` (Story E15.3) chame
    `record_decision()`/`set_ratification()` na MESMA transação de processo que grava
    `sampled-decisions.json` — ver docstring do módulo, item `record-sample-review`."""
    global _OC
    if _OC is None:
        _OC = _load_module(SCRIPT_DIR / "gerente_oracle.py", "gerente_oracle")
    return _OC


def write_atomic(path: Path, text: str) -> None:
    gs().write_atomic(path, text)


def today() -> str:
    return date.today().isoformat()


# ---------------------------------------------------------------------------
# Config tolerante (mesma filosofia de `gerente_quota.py`/`gerente_oracle.py`:
# arquivo ausente/malformado nunca lança, só cai nos defaults hardcoded).
# ---------------------------------------------------------------------------
def load_escalation_config(config_path: Optional[Path] = None) -> dict:
    path = config_path if config_path is not None else (SCRIPT_DIR / ESCALATION_CONFIG_FILENAME)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def get_dead_letter_limit_days(config: dict) -> int:
    try:
        val = int(config.get("dead_letter_limit_days", DEFAULT_DEAD_LETTER_LIMIT_DAYS))
    except (TypeError, ValueError):
        return DEFAULT_DEAD_LETTER_LIMIT_DAYS
    # Negativo é config inválida (não existe "prazo negativo") — sem guard, `days_stuck >= limit`
    # ficava sempre-verdadeiro e TODO escalado virava dead-letter. Cai no default, como config malformada.
    return val if val >= 0 else DEFAULT_DEAD_LETTER_LIMIT_DAYS


def get_orphan_stale_after_seconds(config: dict) -> float:
    try:
        return float(config.get("orphan_stale_after_seconds", gs().DEFAULT_STALE_AFTER_SECONDS))
    except (TypeError, ValueError):
        return gs().DEFAULT_STALE_AFTER_SECONDS


def get_sample_size(config: dict) -> int:
    try:
        val = int(config.get("sample_size", DEFAULT_SAMPLE_SIZE))
    except (TypeError, ValueError):
        return DEFAULT_SAMPLE_SIZE
    # Negativo é config inválida — sem guard, `candidates[:sample_size]` virava `candidates[:-N]`
    # e amostrava quase TUDO (todos menos os N últimos) em vez de nada. Cai no default.
    return val if val >= 0 else DEFAULT_SAMPLE_SIZE


# ---------------------------------------------------------------------------
# board.yaml — parser minimalista casado com o formato de
# rebuild_board.py::render_board_yaml (2/4/6 espaços de indentação, ver docstring).
# ---------------------------------------------------------------------------
def _clean(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        quote = value[0]
        value = value[1:-1]
        if quote == '"':
            value = value.replace('\\"', '"').replace("\\\\", "\\")
    return value


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "sim", "yes")


TICKET_ID_RE = re.compile(r"^  (\S+):\s*$")
FIELD_RE = re.compile(r"^    (\S+):\s*(.*)$")
LIST_ITEM_RE = re.compile(r"^      - (.*)$")


def parse_board_yaml(text: str) -> dict[str, dict[str, Any]]:
    """Devolve {ticket_id: {campo: valor}} — só leitura, nunca escreve board.yaml.

    Formato fixo esperado (o mesmo que `rebuild_board.py` escreve):
        tickets:
          TCK-001:
            title: "..."
            status: novo
            ledger_refs:
              - foo/bar.md
    Linhas de nível 0 (`next_id:`, `tickets:`, comentários `#`) são ignoradas.
    """
    tickets: dict[str, dict[str, Any]] = {}
    current_id: Optional[str] = None
    current_list_key: Optional[str] = None

    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue

        m_id = TICKET_ID_RE.match(raw_line)
        if m_id:
            current_id = m_id.group(1)
            tickets[current_id] = {}
            current_list_key = None
            continue

        if current_id is None:
            continue  # linha de nível 0 (next_id/tickets:) — nada a fazer

        m_list = LIST_ITEM_RE.match(raw_line)
        if m_list and current_list_key:
            tickets[current_id].setdefault(current_list_key, [])
            tickets[current_id][current_list_key].append(_clean(m_list.group(1)))
            continue

        m_field = FIELD_RE.match(raw_line)
        if m_field:
            key, value = m_field.group(1), m_field.group(2).strip()
            if value == "":
                current_list_key = key
                tickets[current_id].setdefault(key, [])
            else:
                if value == "[]":
                    tickets[current_id][key] = []
                else:
                    tickets[current_id][key] = _clean(value)
                current_list_key = None

    return tickets


def load_board(board_path: Path) -> dict[str, dict[str, Any]]:
    if not board_path.exists():
        return {}
    return parse_board_yaml(board_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# list-escalated
# ---------------------------------------------------------------------------
def list_escalated(tickets: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for tid in sorted(tickets.keys()):
        t = tickets[tid]
        if _truthy(t.get("escalonar")):
            out.append({
                "ticket": tid,
                "title": t.get("title", ""),
                "status": t.get("status", ""),
                "priority": t.get("priority", ""),
                "category": t.get("category", ""),
                "area": t.get("area", ""),
                "created": t.get("created"),
                "updated": t.get("updated"),
            })
    return out


def cmd_list_escalated(args: argparse.Namespace) -> int:
    tickets = load_board(Path(args.board_path))
    escalated = list_escalated(tickets)
    print(json.dumps({"count": len(escalated), "escalated": escalated}, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


# ---------------------------------------------------------------------------
# dead-letter-check
# ---------------------------------------------------------------------------
def _parse_date_safe(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        return None


def dead_letter_check(escalated: list[dict[str, Any]], limit_days: int, today_date: Optional[date] = None) -> tuple[list[dict[str, Any]], list[str]]:
    """Dos escalados, quais estão parados >= limit_days desde `updated` (ou `created`
    se `updated` ausente). Data ilegível/ausente NUNCA vira dead-letter por omissão —
    fica de fora com um aviso explícito (conservador: não sabemos há quanto tempo está
    parado, não inventamos um número)."""
    today_date = today_date or date.today()
    dead_letters: list[dict[str, Any]] = []
    warnings: list[str] = []
    for entry in escalated:
        ref = entry.get("updated") or entry.get("created")
        d = _parse_date_safe(ref)
        if d is None:
            warnings.append(f"{entry['ticket']}: sem `updated`/`created` legível ({ref!r}) — não incluído em dead-letter (idade indeterminada)")
            continue
        days_stuck = (today_date - d).days
        if days_stuck >= limit_days:
            dead_letters.append({
                "ticket": entry["ticket"],
                "title": entry.get("title", ""),
                "days_stuck": days_stuck,
                "reference_date": ref,
                "limit_days": limit_days,
            })
    return dead_letters, warnings


def cmd_dead_letter_check(args: argparse.Namespace) -> int:
    config = load_escalation_config(Path(args.config) if args.config else None)
    limit_days = args.limit_days if args.limit_days is not None else get_dead_letter_limit_days(config)
    tickets = load_board(Path(args.board_path))
    escalated = list_escalated(tickets)
    dead_letters, warnings = dead_letter_check(escalated, limit_days)
    print(json.dumps({
        "limit_days": limit_days,
        "escalated_checked": len(escalated),
        "dead_letter_count": len(dead_letters),
        "dead_letter": dead_letters,
        "warnings": warnings,
    }, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


# ---------------------------------------------------------------------------
# sample-decisions / record-sample-review — amostragem das trilhas AUTO-comitadas
# (E9.4: trilha != null + escalonar == false) para ratificação/correção no Briefing.
# Estado de "já amostrado" fica em sampled-decisions.json (artefato do PRÓPRIO
# Gerente — nunca no ticket/board, nunca exige reeditar bagual-tickets).
# ---------------------------------------------------------------------------
def _load_sampled_state(state_path: Path) -> dict[str, Any]:
    if not state_path.exists():
        return {}
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def auto_committed_tickets(tickets: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """Tickets com `trilha` comitada e `escalonar: false` — candidatos a amostragem.
    Simetricamente ao invariante de `list_escalated`: um ticket nunca aparece nas duas
    listas ao mesmo tempo (trilha comitada implica escalonar: false, ver SKILL.md §
    Resolver "Escalonamento de trilha")."""
    out = []
    for tid in sorted(tickets.keys()):
        t = tickets[tid]
        trilha = t.get("trilha")
        if trilha in (None, "", "null", "None"):
            continue
        if _truthy(t.get("escalonar")):
            continue
        out.append({
            "ticket": tid,
            "title": t.get("title", ""),
            "trilha": trilha,
            "status": t.get("status", ""),
            "created": t.get("created"),
            "updated": t.get("updated"),
        })
    return out


def sample_decisions(tickets: dict[str, dict[str, Any]], sampled_state: dict[str, Any], sample_size: int) -> list[dict[str, Any]]:
    candidates = [c for c in auto_committed_tickets(tickets) if c["ticket"] not in sampled_state]
    # Ordem determinística: mais antigo primeiro (updated -> created -> id), para não
    # deixar um ticket velho nunca ser amostrado enquanto tickets novos chegam sempre
    # na frente da fila (viés de "primeiro a entrar, primeiro a ser revisado").
    candidates.sort(key=lambda c: (c.get("updated") or c.get("created") or "", c["ticket"]))
    return candidates[:sample_size]


def cmd_sample_decisions(args: argparse.Namespace) -> int:
    config = load_escalation_config(Path(args.config) if args.config else None)
    sample_size = args.sample_size if args.sample_size is not None else get_sample_size(config)
    tickets = load_board(Path(args.board_path))
    sampled_state = _load_sampled_state(Path(args.state_path))
    sample = sample_decisions(tickets, sampled_state, sample_size)
    print(json.dumps({
        "sample_size": sample_size,
        "already_sampled_count": len(sampled_state),
        "candidates_total": len(auto_committed_tickets(tickets)),
        "sample": sample,
    }, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


def _missing_correction_trace_fields(args: argparse.Namespace) -> list[str]:
    """Story E15.3 — os campos de rastro de decisão exigidos por `--verdict corrigido`
    (nunca por `--verdict ratificado`): sem eles, `record_decision()` não tem o que
    gravar na Entrada de Ledger (`--question`/`--justification`/`--context` são
    obrigatórios em `gerente_oracle.py record-decision`), e sem `--trilha-auto`/
    `--trilha-corrigida` não há o que descrever como a correção em si. Devolve a lista
    de flags ausentes/vazias (nunca lança — o chamador decide o formato do erro)."""
    required = (
        ("--trilha-auto", args.trilha_auto),
        ("--trilha-corrigida", args.trilha_corrigida),
        ("--question", args.question),
        ("--justification", args.justification),
        ("--context", args.context),
    )
    return [flag for flag, value in required if value is None or not value.strip()]


def cmd_record_sample_review(args: argparse.Namespace) -> int:
    if args.verdict not in ("ratificado", "corrigido"):
        print(json.dumps({"ok": False, "error": "--verdict deve ser 'ratificado' ou 'corrigido'"}))
        return 2

    ledger_entry: Optional[dict[str, Any]] = None

    if args.verdict == "corrigido":
        # E15.3 — falha RÁPIDO e CLARO, antes de qualquer escrita (nem Ledger, nem
        # sampled-decisions.json), quando os campos de rastro de decisão estão
        # incompletos. Nunca aceita `corrigido` "parcial" (só sampled-decisions.json,
        # sem Ledger) — essa era exatamente a lacuna comportamental que esta story fecha.
        missing = _missing_correction_trace_fields(args)
        if missing:
            print(json.dumps({
                "ok": False,
                "error": (
                    "--verdict corrigido exige os campos de rastro de decisão "
                    f"({', '.join(missing)}) — Story E15.3: uma correção nunca é aceita "
                    "sem gravar a Entrada de Ledger `ratification: corrected` "
                    "correspondente na MESMA invocação. Nada foi escrito "
                    "(nem sampled-decisions.json, nem o Ledger)."
                ),
                "missing_fields": missing,
            }, ensure_ascii=False))
            return 2

        oracle = oc()
        decision_text = args.decision.strip() if args.decision and args.decision.strip() else (
            f"Corrigir a trilha do ticket {args.ticket}: de '{args.trilha_auto}' para "
            f"'{args.trilha_corrigida}'."
        )
        ledger_root = Path(args.ledger_root)
        oracle_config = oracle.load_oracle_config(Path(args.oracle_config) if args.oracle_config else None)

        # Efeito colateral novo (Ledger) roda ANTES da escrita que finaliza a operação
        # (sampled-decisions.json, abaixo) — mesma disciplina de ordem já usada por E15.2
        # (`wiki/ledger/padrao/
        # mecanizar-efeito-colateral-antes-da-escrita-que-finaliza-a-operacao.md`): por
        # construção, `sampled-decisions.json` nunca reflete uma "correção revisada" sem
        # que a Entrada de Ledger correspondente já exista. Qualquer exceção aqui aborta
        # a função inteira (nunca captura silenciosamente) — sampled-decisions.json
        # permanece intocado.
        try:
            decision_result = oracle.record_decision(
                ledger_root, args.tipo, args.ticket,
                args.question, decision_text, args.justification, args.context,
                alternatives=None, areas_csv=args.areas,
                confidence_requested="low", precedent=None,
                oracle_config=oracle_config, slug=None,
            )
        except oracle.OracleOperationError as exc:
            print(json.dumps({
                "ok": False,
                "error": f"record_decision recusado — operação abortada, sampled-decisions.json NÃO foi tocado: {exc}",
                "stage": "record_decision",
            }, ensure_ascii=False))
            return exc.exit_code

        if decision_result.get("self_check_violations"):
            print(json.dumps({
                "ok": False,
                "error": (
                    "record_decision gravou uma entrada com violações de self-check — "
                    "operação abortada, sampled-decisions.json NÃO foi tocado"
                ),
                "stage": "record_decision_self_check",
                "self_check_violations": decision_result["self_check_violations"],
                "ledger_path": decision_result.get("ledger_path"),
            }, ensure_ascii=False))
            return 1

        try:
            ratification_result = oracle.set_ratification(
                ledger_root, "corrected",
                entry=Path(decision_result["ledger_path"]), note=args.note,
            )
        except oracle.OracleOperationError as exc:
            # A Entrada de Ledger já foi gravada (candidata, ratification: pending) pelo
            # passo anterior — não há como desfazer isso sem violar "Ledger nunca apagado
            # silenciosamente" (mesma disciplina de E4.2). O que ESTA operação garante é
            # que `sampled-decisions.json` nunca reflete "corrigido" enquanto o Ledger não
            # tiver `ratification: corrected` — por isso aborta aqui, sem escrever
            # sampled-decisions.json, deixando a entrada `pending` visível via
            # `gerente_oracle.py list-pending` para retry manual.
            print(json.dumps({
                "ok": False,
                "error": (
                    f"set_ratification recusado — operação abortada, sampled-decisions.json "
                    f"NÃO foi tocado; a Entrada de Ledger {decision_result['ledger_path']} já "
                    f"foi gravada (candidata, ratification: pending) e precisa de retry manual "
                    f"via 'gerente_oracle.py set-ratification': {exc}"
                ),
                "stage": "set_ratification",
                "ledger_path": decision_result.get("ledger_path"),
            }, ensure_ascii=False))
            return exc.exit_code

        ledger_entry = {
            "ledger_path": decision_result["ledger_path"],
            "ratification": ratification_result["new_ratification"],
        }

    state_path = Path(args.state_path)
    state = _load_sampled_state(state_path)
    entry: dict[str, Any] = {
        "verdict": args.verdict,
        "reviewed_at": today(),
        "trilha_auto": args.trilha_auto,
        "trilha_corrigida": args.trilha_corrigida,
        "note": args.note,
    }
    if ledger_entry is not None:
        entry["ledger_entry"] = ledger_entry
    state[args.ticket] = entry
    # Escrita que FINALIZA a operação — a única que torna "amostra revisada" observável
    # por terceiros (ex.: a próxima chamada de `sample-decisions`, que nunca re-amostra um
    # ticket presente aqui). Roda por último, depois do Ledger já ter sido gravado com
    # sucesso (quando aplicável) — nunca antes.
    write_atomic(state_path, json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"ok": True, "ticket": args.ticket, "state_path": str(state_path), "entry": entry}, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------------------
# orphan-sweep — único comando deste script que ESCREVE (mutação mecânica e
# auditável de UM campo, sob condição objetiva — ver docstring do módulo).
# ---------------------------------------------------------------------------
def _find_ticket_md(tickets_dir: Path, ticket_id: str) -> Optional[Path]:
    exact = tickets_dir / f"{ticket_id}.md"
    if exact.exists():
        return exact
    matches = sorted(tickets_dir.glob(f"{ticket_id}-*.md"))
    return matches[0] if matches else None


def _revert_ticket_status_md(md_path: Path, new_status: str, log_reason: str) -> str:
    """Reverte só o campo `status:` do front-matter (preserva todo o resto do arquivo
    literalmente) e anexa uma linha de `## Log`. Devolve o status anterior. Levanta
    ValueError se o `.md` não tiver front-matter/campo `status` reconhecível — nunca
    escreve um arquivo que não conseguiu interpretar."""
    text = md_path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"{md_path}: sem front-matter (esperava '---' na primeira linha)")
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end_idx = i
            break
    if end_idx is None:
        raise ValueError(f"{md_path}: front-matter sem delimitador de fechamento '---'")

    old_status = None
    for i in range(1, end_idx):
        m = re.match(r"^status:\s*(\S.*)$", lines[i])
        if m:
            old_status = m.group(1).strip()
            lines[i] = f"status: {new_status}\n"
            break
    if old_status is None:
        raise ValueError(f"{md_path}: campo 'status:' não encontrado no front-matter")

    for i in range(1, end_idx):
        if re.match(r"^updated:\s*", lines[i]):
            lines[i] = f"updated: {today()}\n"
            break

    full_text = "".join(lines).rstrip("\n")
    log_line = f"- {today()}: revertido de `{old_status}` para `{new_status}` pela varredura de órfãos do Gerente (E9.5) — {log_reason}"
    new_text = full_text + "\n" + log_line + "\n"
    write_atomic(md_path, new_text)
    return old_status


def _rebuild_board_after_sweep(tickets_dir: Path, board_path: Path) -> dict:
    rb_mod = rb()
    tickets, warnings, stats = rb_mod.load_tickets(tickets_dir)
    legacy_numeric_ids = [
        int(tid[len("TCK-"):])
        for tid in tickets
        if tid.startswith("TCK-") and tid[len("TCK-"):].isdigit()
    ]
    legacy_next_id = (max(legacy_numeric_ids) + 1) if legacy_numeric_ids else None
    rendered = rb_mod.render_board_yaml(tickets, legacy_next_id)
    write_atomic(board_path, rendered)
    return {"stats": stats, "warnings": warnings}


def orphan_sweep(gerente_root: Path, tickets_dir: Path, board_path: Path, stale_after_seconds: float, dry_run: bool = False) -> dict:
    gs_mod = gs()
    lock_dir = gs_mod._lock_dir(gerente_root)
    info = gs_mod._read_lock_info(lock_dir) if lock_dir.exists() else None

    if info is not None:
        stale, why = gs_mod.lock_is_stale(info, stale_after_seconds)
        if not stale:
            return {
                "swept": False,
                "reason": "lock do Gerente held-e-fresco (heartbeat recente) — ciclo genuinamente em andamento, "
                          "varredura pulada por inteiro (conservador: nenhum ticket tocado enquanto QUALQUER lock estiver vivo)",
                "orphans_reverted": [],
                "warnings": [],
                "lock_info": info,
            }
        stale_reason = why
    else:
        stale_reason = "nenhum lock presente em disco — nenhum ciclo do Gerente em andamento"

    tickets = load_board(board_path)
    orphan_ids = sorted(tid for tid, t in tickets.items() if t.get("status") == "em-implementacao")

    reverted: list[dict[str, Any]] = []
    warnings: list[str] = []
    for tid in orphan_ids:
        md_path = _find_ticket_md(tickets_dir, tid)
        if md_path is None:
            warnings.append(f"{tid}: status 'em-implementacao' no board.yaml mas nenhum .md encontrado em {tickets_dir} — não revertido")
            continue
        if dry_run:
            reverted.append({"ticket": tid, "md_path": str(md_path), "reason": stale_reason, "dry_run": True})
            continue
        try:
            old_status = _revert_ticket_status_md(md_path, "pronto-para-implementar", stale_reason)
        except ValueError as exc:
            warnings.append(str(exc))
            continue
        reverted.append({"ticket": tid, "md_path": str(md_path), "old_status": old_status, "new_status": "pronto-para-implementar", "reason": stale_reason})

    rebuild_result = None
    if reverted and not dry_run:
        rebuild_result = _rebuild_board_after_sweep(tickets_dir, board_path)

    return {
        "swept": True,
        "stale_reason": stale_reason,
        "orphans_found": len(orphan_ids),
        "orphans_reverted": reverted,
        "warnings": warnings,
        "dry_run": dry_run,
        "rebuild": rebuild_result,
    }


def cmd_orphan_sweep(args: argparse.Namespace) -> int:
    config = load_escalation_config(Path(args.config) if args.config else None)
    stale_after_seconds = args.stale_after_seconds if args.stale_after_seconds is not None else get_orphan_stale_after_seconds(config)
    result = orphan_sweep(
        Path(args.gerente_root), Path(args.tickets_dir), Path(args.board_path),
        stale_after_seconds, dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    ple = sub.add_parser("list-escalated", help="lista tickets com escalonar: true no board.yaml (índice, F20)")
    ple.add_argument("--board-path", default=str(DEFAULT_BOARD_PATH))
    ple.add_argument("--pretty", action="store_true")
    ple.set_defaults(func=cmd_list_escalated)

    pdl = sub.add_parser("dead-letter-check", help="dos escalados, quais estão parados além do limite configurado")
    pdl.add_argument("--board-path", default=str(DEFAULT_BOARD_PATH))
    pdl.add_argument("--limit-days", type=int, default=None, help="default: escalation.config.json / hardcoded")
    pdl.add_argument("--config", default=None, help="path de escalation.config.json (default: sibling deste script)")
    pdl.add_argument("--pretty", action="store_true")
    pdl.set_defaults(func=cmd_dead_letter_check)

    psd = sub.add_parser("sample-decisions", help="amostra trilhas auto-comitadas pela skill, ainda não revisadas")
    psd.add_argument("--board-path", default=str(DEFAULT_BOARD_PATH))
    psd.add_argument("--state-path", default=str(DEFAULT_SAMPLED_STATE_PATH))
    psd.add_argument("--sample-size", type=int, default=None)
    psd.add_argument("--config", default=None)
    psd.add_argument("--pretty", action="store_true")
    psd.set_defaults(func=cmd_sample_decisions)

    prsr = sub.add_parser("record-sample-review", help="grava o veredito (ratificado/corrigido) de uma amostra revisada; --verdict corrigido também grava a Entrada de Ledger ratification:corrected na mesma invocação (E15.3)")
    prsr.add_argument("--state-path", default=str(DEFAULT_SAMPLED_STATE_PATH))
    prsr.add_argument("--ticket", required=True)
    prsr.add_argument("--verdict", required=True, choices=["ratificado", "corrigido"])
    prsr.add_argument("--trilha-auto", default=None, help="a trilha que a skill comitou automaticamente — obrigatório quando --verdict corrigido (E15.3)")
    prsr.add_argument("--trilha-corrigida", default=None, help="obrigatório quando --verdict corrigido: a trilha certa segundo o Gerente/dono (E15.3)")
    prsr.add_argument("--note", default=None, help="nota livre; quando --verdict corrigido, também vira a nota anexada à Entrada de Ledger via set-ratification")
    # E15.3 (T2.3) — campos de rastro de decisão, exigidos só quando --verdict corrigido
    # (validado em cmd_record_sample_review, não via argparse `required`, porque a
    # obrigatoriedade depende do valor de --verdict, não é incondicional).
    prsr.add_argument("--question", default=None, help="obrigatório quando --verdict corrigido — a pergunta/ambiguidade por trás da trilha auto-comitada (vira --question de gerente_oracle.py record-decision)")
    prsr.add_argument("--justification", default=None, help="obrigatório quando --verdict corrigido — o porquê da trilha corrigida (vira --justification de record-decision)")
    prsr.add_argument("--context", default=None, help="obrigatório quando --verdict corrigido — o que motivou a revisão (vira --context de record-decision)")
    prsr.add_argument("--decision", default=None, help="opcional quando --verdict corrigido — default: derivado de --trilha-auto/--trilha-corrigida")
    prsr.add_argument("--tipo", choices=["decisao-tecnica", "decisao-de-produto", "decisao-de-arquitetura"], default="decisao-tecnica", help="tipo da Entrada de Ledger gravada quando --verdict corrigido (E15.3)")
    prsr.add_argument("--areas", default="escalonamento,gerente-geral,trilha", help="areas da Entrada de Ledger gravada quando --verdict corrigido (E15.3) — consumido por find_corrected_contradictions no gate history-aware de E9.2")
    prsr.add_argument("--ledger-root", default=str(DEFAULT_LEDGER_ROOT), help="raiz do Ledger onde a Entrada corrected é gravada quando --verdict corrigido (E15.3)")
    prsr.add_argument("--oracle-config", default=None, help="path de oracle.config.json (default: sibling de gerente_oracle.py) — usado só quando --verdict corrigido")
    prsr.set_defaults(func=cmd_record_sample_review)

    pos = sub.add_parser("orphan-sweep", help="reverte em-implementacao -> pronto-para-implementar para tickets órfãos (heartbeat do lock, E8.2)")
    pos.add_argument("--gerente-root", default=str(DEFAULT_GERENTE_ROOT))
    pos.add_argument("--tickets-dir", default=str(DEFAULT_TICKETS_DIR))
    pos.add_argument("--board-path", default=str(DEFAULT_BOARD_PATH))
    pos.add_argument("--stale-after-seconds", type=float, default=None, help="default: escalation.config.json / DEFAULT_STALE_AFTER_SECONDS de gerente_state.py")
    pos.add_argument("--config", default=None)
    pos.add_argument("--dry-run", action="store_true", help="reporta os órfãos sem escrever nada")
    pos.add_argument("--pretty", action="store_true")
    pos.set_defaults(func=cmd_orphan_sweep)

    return p


def main(argv: Optional[list] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
