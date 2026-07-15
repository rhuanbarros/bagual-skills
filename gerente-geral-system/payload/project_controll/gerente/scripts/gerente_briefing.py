#!/usr/bin/env python3
"""gerente_briefing.py — E8.7 Briefing da Manhã como artefato persistido.

Story E8.7 (ideias/sistema-artifacts/E8-7-briefing-manha.md), PRD 00 FR-10 (§4.7),
ideias/epics.md Epic E8. O ciclo do Gerente Geral roda headless (sem chat) — não existe
"mensagem no chat" nenhuma para entregar ao fim de um ciclo autônomo. Este módulo faz o
Briefing ser um ARTEFATO PERSISTIDO em disco (`briefing-YYYYMMDD.md`, derivado de
`diario.md`/`diario.jsonl` (Story E8.2) + `estado-atual.yaml`), para que a PRÓXIMA sessão
interativa que o dono abrir detecte-o como não-lido e o renderize no chat na ativação.

Comandos:
  write-briefing   deriva o Briefing do ciclo (diario.jsonl + estado-atual.yaml) e
                    escreve/atualiza project_controll/gerente/briefing-YYYYMMDD.md,
                    marcando-o como `status: unread` (idempotente por --cycle-id: rodar
                    de novo para o MESMO ciclo substitui a seção existente em vez de
                    duplicá-la; um segundo ciclo no MESMO dia calendário ACRESCENTA uma
                    nova seção, preservando a(s) anterior(es)).
  detect-unread    varre project_controll/gerente/briefing-*.md e lista os que estão
                    com `status: unread` (somente-leitura, sem mutação).
  mark-read        marca um Briefing como lido (`status: read` + `read_at`), idempotente
                    (marcar um já-lido de novo não é erro nem duplica nada). Aceita
                    `--expected-last-cycle-id` opcional (compare-and-swap contra uma
                    escrita concorrente de `write-briefing` entre o `detect-unread` do
                    chamador e este `mark-read` — recusa em vez de clobbrar conteúdo novo
                    não-lido).

Data do arquivo (`YYYYMMDD`): derivada da data-calendário de `--ended-at` (o instante em
que o CICLO terminou), NUNCA da data-de-relógio de quando este script roda — um ciclo que
termina às 23:58 e cujo write-briefing só é chamado (por qualquer atraso) já em outro dia
ainda produz `briefing-<data-do-ended_at>.md`, preservando a correspondência 1:1 entre
Briefing e ciclo real. Só cai para a data-de-relógio do PRÓPRIO script (`now_iso()`) no
caso degradado em que `--ended-at` não foi fornecido — documentado como fallback, nunca
como comportamento primário (ver README § Briefing (E8.7) "Data do arquivo").

Escrita atômica: reusa `write_atomic`/`now_iso`/`parse_estado` de `gerente_state.py`
(E8.2) por IMPORT direto do arquivo irmão — não uma cópia colada, o mesmo padrão de reuso
que `gerente_quota.py` (E8.3) já usa.

Só biblioteca padrão (stdlib) — nenhuma dependência externa, mesma convenção dos scripts
irmãos deste diretório.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

SCRIPT_DIR = Path(__file__).resolve().parent

STOP_REASON_LABELS = {
    "cota": "cota",
    "fila-vazia": "conclusão",
    "bloqueio": "bloqueio",
}
VALID_STOP_REASONS = tuple(STOP_REASON_LABELS.keys())

# Story E13.4 — mesmo literal de `flag_suspected_fp.py`/`read_fp_suspects.py`
# (status default de uma suspeita ainda não ratificada); usado só como fallback textual
# se uma entrada de `semgrep_fp_pending` vier sem `status` (nunca deveria acontecer, mas
# o Briefing nunca deixa de renderizar por um campo individual faltando).
PENDING_RATIFICATION_LABEL = "pending_ratification"


# ---------------------------------------------------------------------------
# Reuso de gerente_state.py (import direto do arquivo irmão — não cópia colada)
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


def now_iso() -> str:
    return _gs().now_iso()


def write_atomic(path: Path, text: str) -> None:
    _gs().write_atomic(path, text)


def parse_iso_safe(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return _gs().parse_iso(ts)
    except (ValueError, TypeError):
        return None


def date_component(ts: Optional[str]) -> Optional[str]:
    """'2026-07-11T07:00:00-03:00' -> '2026-07-11'. Tolerante a formatos curtos/inválidos."""
    if not ts or len(ts) < 10:
        return None
    candidate = ts[:10]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", candidate):
        return candidate
    return None


def human_duration(started_at: Optional[str], ended_at: Optional[str]) -> str:
    start = parse_iso_safe(started_at)
    end = parse_iso_safe(ended_at)
    if start is None or end is None:
        return "duração desconhecida (timestamp ausente/malformado)"
    seconds = (end - start).total_seconds()
    if seconds < 0:
        return "duração desconhecida (ended_at anterior a started_at)"
    total_minutes = int(seconds // 60)
    hours, minutes = divmod(total_minutes, 60)
    if hours and minutes:
        return f"{hours}h{minutes:02d}min"
    if hours:
        return f"{hours}h"
    return f"{minutes}min"


# ---------------------------------------------------------------------------
# Leitura tolerante de estado-atual.yaml (nunca lança exceção não tratada)
# ---------------------------------------------------------------------------
def read_estado(estado_path: Path) -> dict:
    if not estado_path.exists():
        return {}
    try:
        text = estado_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        return _gs().parse_estado(text)
    except Exception:
        # Nunca deixe um estado-atual.yaml malformado derrubar o Briefing — degrada para
        # "sem dados de estado", igual a um arquivo ausente.
        return {}


# ---------------------------------------------------------------------------
# Leitura tolerante de diario.jsonl, filtrada por cycle_id
# ---------------------------------------------------------------------------
def read_diario_entries_for_cycle(diario_jsonl_path: Path, cycle_id: str) -> tuple[list[dict], bool]:
    """Devolve (entradas do ciclo em ordem, bloco_completo).

    bloco_completo é False se o arquivo está ausente, se nenhuma entrada do cycle_id foi
    encontrada, ou se um CICLO-INICIO foi encontrado sem o CICLO-FIM correspondente
    (diário truncado/parcial) — nunca lança exceção, cada linha malformada é ignorada
    individualmente.
    """
    if not diario_jsonl_path.exists():
        return [], False
    try:
        raw = diario_jsonl_path.read_text(encoding="utf-8")
    except OSError:
        return [], False
    entries: list[dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue  # linha torta isolada — ignora, não aborta o diário inteiro
        if not isinstance(obj, dict):
            continue
        if obj.get("cycle_id") == cycle_id:
            entries.append(obj)
    if not entries:
        return [], False
    has_start = any(e.get("event") == "CICLO-INICIO" for e in entries)
    has_end = any(e.get("event") == "CICLO-FIM" for e in entries)
    complete = has_start and has_end
    return entries, complete


# ---------------------------------------------------------------------------
# Renderização do corpo do Briefing (Markdown) — uma seção por ciclo
# ---------------------------------------------------------------------------
def render_cycle_section(
    cycle_id: str,
    started_at: Optional[str],
    ended_at: Optional[str],
    stop_reason: str,
    stop_detail: Optional[str],
    diario_entries: list[dict],
    diario_complete: bool,
    decisions_pending: list[dict],
    decisions_escalated: list[dict],
    escalation_sample_review: Optional[list[dict]] = None,
    escalation_dead_letter: Optional[list[dict]] = None,
    semgrep_fp_pending: Optional[list[dict]] = None,
) -> str:
    lines: list[str] = [f"## Ciclo {cycle_id}", ""]

    lines.append(f"**Período:** {started_at or 'desconhecido'} → {ended_at or 'desconhecido'} ({human_duration(started_at, ended_at)})")

    stop_label = STOP_REASON_LABELS.get(stop_reason, stop_reason)
    stop_line = f"**Parou por:** {stop_label}"
    if stop_reason == "fila-vazia" and stop_detail == "teto-proativo":
        stop_line += " — teto de trabalho proativo atingido (não é conclusão total da fila, é o guardrail de proativo)"
    lines.append(stop_line)
    lines.append("")

    despachei = [e.get("text") for e in diario_entries if e.get("event") == "despachei" and e.get("text")]
    revisei = [e.get("text") for e in diario_entries if e.get("event") == "revisei" and e.get("text")]
    lines.append("### O que foi feito")
    if despachei or revisei:
        for t in despachei:
            lines.append(f"- despachei: {t}")
        for t in revisei:
            lines.append(f"- revisei: {t}")
    else:
        lines.append("- nenhum registro de despacho/revisão encontrado no diário para este ciclo")
    lines.append("")

    decidi = [e.get("text") for e in diario_entries if e.get("event") == "decidi" and e.get("text")]
    lines.append("### Decisões tomadas (rastro)")
    if decidi:
        for t in decidi:
            lines.append(f"- {t}")
    else:
        lines.append("- nenhuma decisão registrada no diário para este ciclo")
    lines.append("")

    lines.append("### Precisa de atenção / ratificação")
    # Forward-dep E9.1 (oráculo — decisões delegadas que precisam de ratificação do dono):
    # decisions_pending/decisions_escalated já existem no schema de estado-atual.yaml
    # desde a Story E8.2, mas ainda são sempre `[]` até E9.1 popular. Lemos o campo aqui
    # com .get() defensivo (ausente OU [] rendem a mesma frase) para que, quando E9.1
    # existir, o Briefing passe a listar as entradas sem nenhum rework deste script.
    if decisions_pending or decisions_escalated:
        for d in decisions_pending:
            ticket = d.get("ticket", "?")
            note = d.get("note", "")
            lines.append(f"- [{ticket}] {note} (aguardando ratificação)")
        for d in decisions_escalated:
            ticket = d.get("ticket", "?")
            note = d.get("note", "")
            lines.append(f"- [{ticket}] {note} (escalado para precisa-de-info)")
    else:
        lines.append("- nenhuma decisão pendente de ratificação")
    lines.append("")

    # Story E9.5 (PRD 02 FR-6, AC2) — amostragem das trilhas AUTO-comitadas pela skill
    # (bagual-tickets, E9.4), populada por `gerente_escalation.py sample-decisions`/
    # `record-sample-review` e repassada aqui via `escalation_sample_review` em
    # estado-atual.yaml (mesmo padrão aditivo de `decisions_pending`, ver docstring do
    # módulo). `verdict` ausente = ainda aguardando revisão do Gerente/dono.
    lines.append("### Amostragem de decisões automáticas (trilha)")
    sample_review = escalation_sample_review or []
    if sample_review:
        for s in sample_review:
            ticket = s.get("ticket", "?")
            trilha = s.get("trilha", "?")
            verdict = s.get("verdict")
            if verdict:
                lines.append(f"- [{ticket}] trilha `{trilha}` (auto-comitada pela skill) — {verdict}")
            else:
                lines.append(f"- [{ticket}] trilha `{trilha}` (auto-comitada pela skill) — aguardando ratificação/correção por amostragem")
    else:
        lines.append("- nenhuma decisão automática amostrada neste ciclo")
    lines.append("")

    # Story E9.5 (PRD 02 FR-6, AC4, F20 hardening) — escalados parados além do limite
    # configurado (`gerente_escalation.py dead-letter-check`), nunca deixados invisíveis.
    lines.append("### Dead-letter (escalados presos)")
    dead_letter = escalation_dead_letter or []
    if dead_letter:
        for d in dead_letter:
            ticket = d.get("ticket", "?")
            days = d.get("days_stuck", "?")
            lines.append(f"- [{ticket}] escalado há {days} dia(s) sem decisão do Gerente — precisa de atenção")
    else:
        lines.append("- nenhum escalado em dead-letter neste ciclo")
    lines.append("")

    # Story E13.4 (PRD 04 FR-2) — suspeitas de falso-positivo de Semgrep flagueadas por
    # `flag_suspected_fp.py` (E7.3, válvula de escape do hook de pre-commit) e ainda
    # `pending_ratification`, populadas por `read_fp_suspects.py list-pending` e
    # repassadas aqui via `semgrep_fp_pending` em estado-atual.yaml — mesmo padrão
    # aditivo de `escalation_sample_review`/`escalation_dead_letter` acima: campo
    # ausente OU `[]` rendem a mesma frase neutra, nunca crasham um Briefing de estado
    # anterior a esta story.
    lines.append("### Suspeitas de falso-positivo (Semgrep)")
    fp_pending = semgrep_fp_pending or []
    if fp_pending:
        for s in fp_pending:
            fingerprint = s.get("fingerprint", "?")
            reason = s.get("reason", "")
            status = s.get("status", PENDING_RATIFICATION_LABEL)
            rule_id = s.get("rule_id")
            file_ = s.get("file")
            line_no = s.get("line")
            location = f" ({rule_id} @ {file_}:{line_no})" if rule_id and file_ else ""
            lines.append(f"- [{fingerprint}]{location} — {reason} ({status})")
    else:
        lines.append("- nenhuma suspeita de falso-positivo pendente")
    lines.append("")

    lines.append("### Diagnóstico")
    diag = "completo" if diario_complete else "incompleto — bloco do ciclo não encontrado ou parcial em diario.jsonl (nunca bloqueia a escrita do Briefing, só sinaliza a lacuna)"
    lines.append(f"- diário: {diag}")

    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Parser/serializador mínimo do arquivo de Briefing — frontmatter + seções `## Ciclo X`
# ---------------------------------------------------------------------------
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n(.*)\Z", re.DOTALL)
CYCLE_HEADER_RE = re.compile(r"^## Ciclo (\S+)\s*$", re.MULTILINE)


def parse_briefing(text: str) -> tuple[dict, str, list[tuple[str, str]]]:
    """Devolve (frontmatter, title_line, [(cycle_id, section_text), ...])."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, "", []
    fm_text, body = m.group(1), m.group(2)
    fm: dict[str, Any] = {}
    for line in fm_text.splitlines():
        if not line.strip():
            continue
        key, _, val = line.partition(":")
        fm[key.strip()] = val.strip()

    headers = list(CYCLE_HEADER_RE.finditer(body))
    title_line = body[: headers[0].start()].strip("\n") if headers else body.strip("\n")
    sections: list[tuple[str, str]] = []
    for i, hm in enumerate(headers):
        start = hm.start()
        end = headers[i + 1].start() if i + 1 < len(headers) else len(body)
        sections.append((hm.group(1), body[start:end].rstrip("\n")))
    return fm, title_line, sections


def render_briefing(fm: dict, title_line: str, sections: list[tuple[str, str]]) -> str:
    fm_lines = ["---"]
    for k in ("status", "written_at", "last_cycle_id", "read_at"):
        if k in fm:
            fm_lines.append(f"{k}: {fm[k]}")
    fm_lines.append("---")
    fm_block = "\n".join(fm_lines)
    body_parts = [title_line.rstrip("\n")] if title_line.strip() else []
    body_parts.extend(sec.rstrip("\n") for _, sec in sections)
    body = "\n\n".join(p for p in body_parts if p.strip())
    return fm_block + "\n\n" + body.rstrip() + "\n"


# ---------------------------------------------------------------------------
# write-briefing
# ---------------------------------------------------------------------------
def cmd_write_briefing(args: argparse.Namespace) -> int:
    root = Path(args.root)
    root.mkdir(parents=True, exist_ok=True)

    if args.stop_reason not in VALID_STOP_REASONS:
        print(f"erro: --stop-reason deve ser um de {VALID_STOP_REASONS}", file=sys.stderr)
        return 2

    diario_jsonl_path = Path(args.diario_jsonl_path) if args.diario_jsonl_path else root / "diario.jsonl"
    estado_path = Path(args.estado_path) if args.estado_path else root / "estado-atual.yaml"

    estado = read_estado(estado_path)
    decisions_pending = estado.get("decisions_pending") or []
    decisions_escalated = estado.get("decisions_escalated") or []
    if not isinstance(decisions_pending, list):
        decisions_pending = []
    if not isinstance(decisions_escalated, list):
        decisions_escalated = []
    escalation_sample_review = estado.get("escalation_sample_review") or []
    escalation_dead_letter = estado.get("escalation_dead_letter") or []
    if not isinstance(escalation_sample_review, list):
        escalation_sample_review = []
    if not isinstance(escalation_dead_letter, list):
        escalation_dead_letter = []
    # Story E13.4 — mesmo padrão defensivo: ausente OU [] OU tipo inesperado colapsam
    # para lista vazia, nunca lançam exceção (ver docstring do módulo).
    semgrep_fp_pending = estado.get("semgrep_fp_pending") or []
    if not isinstance(semgrep_fp_pending, list):
        semgrep_fp_pending = []

    diario_entries, diario_complete = read_diario_entries_for_cycle(diario_jsonl_path, args.cycle_id)

    date_str = date_component(args.ended_at)
    used_fallback_date = False
    if date_str is None:
        date_str = date_component(now_iso())
        used_fallback_date = True
    date_compact = date_str.replace("-", "")

    briefing_path = root / f"briefing-{date_compact}.md"

    section_text = render_cycle_section(
        cycle_id=args.cycle_id,
        started_at=args.started_at,
        ended_at=args.ended_at,
        stop_reason=args.stop_reason,
        stop_detail=args.stop_detail,
        diario_entries=diario_entries,
        diario_complete=diario_complete,
        decisions_pending=decisions_pending,
        decisions_escalated=decisions_escalated,
        escalation_sample_review=escalation_sample_review,
        escalation_dead_letter=escalation_dead_letter,
        semgrep_fp_pending=semgrep_fp_pending,
    )

    if briefing_path.exists():
        try:
            existing_text = briefing_path.read_text(encoding="utf-8")
        except OSError:
            existing_text = ""
        fm, title_line, sections = parse_briefing(existing_text)
        if not title_line.strip():
            title_line = f"# Briefing — {date_str}"
    else:
        fm, title_line, sections = {}, f"# Briefing — {date_str}", []

    replaced = False
    new_sections: list[tuple[str, str]] = []
    for cid, sec in sections:
        if cid == args.cycle_id:
            new_sections.append((cid, section_text))
            replaced = True
        else:
            new_sections.append((cid, sec))
    if not replaced:
        new_sections.append((args.cycle_id, section_text))

    ts = args.ts or now_iso()
    fm["status"] = "unread"
    fm["written_at"] = ts
    fm["last_cycle_id"] = args.cycle_id
    # read_at é limpo a cada nova escrita: uma seção nova torna o arquivo inteiro
    # não-lido de novo, então um `read_at` de uma leitura anterior ficaria enganoso.
    fm.pop("read_at", None)

    out_text = render_briefing(fm, title_line, new_sections)
    write_atomic(briefing_path, out_text)

    print(json.dumps({
        "ok": True,
        "path": str(briefing_path),
        "date": date_str,
        "used_fallback_date": used_fallback_date,
        "cycle_id": args.cycle_id,
        "section_replaced": replaced,
        "diario_complete": diario_complete,
        "decisions_pending_count": len(decisions_pending),
        "decisions_escalated_count": len(decisions_escalated),
        "escalation_sample_review_count": len(escalation_sample_review),
        "escalation_dead_letter_count": len(escalation_dead_letter),
        "semgrep_fp_pending_count": len(semgrep_fp_pending),
        "status": "unread",
    }))
    return 0


# ---------------------------------------------------------------------------
# detect-unread
# ---------------------------------------------------------------------------
def cmd_detect_unread(args: argparse.Namespace) -> int:
    root = Path(args.root)
    results: list[dict] = []
    if root.exists():
        for path in sorted(root.glob("briefing-*.md")):
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            fm, _title, sections = parse_briefing(text)
            status = fm.get("status", "unread")  # ausência de frontmatter reconhecível = trata como não-lido, nunca perde um Briefing
            if status != "unread":
                continue
            m = re.match(r"briefing-(\d{8})\.md$", path.name)
            date_compact = m.group(1) if m else None
            date_str = f"{date_compact[0:4]}-{date_compact[4:6]}-{date_compact[6:8]}" if date_compact else None
            results.append({
                "path": str(path),
                "date": date_str,
                "status": status,
                "written_at": fm.get("written_at"),
                "last_cycle_id": fm.get("last_cycle_id"),
                "cycle_ids": [cid for cid, _ in sections],
            })
    print(json.dumps({"ok": True, "unread": results, "count": len(results)}))
    return 0


# ---------------------------------------------------------------------------
# mark-read
# ---------------------------------------------------------------------------
def cmd_mark_read(args: argparse.Namespace) -> int:
    root = Path(args.root)
    if args.path:
        briefing_path = Path(args.path)
    elif args.date:
        date_compact = args.date.replace("-", "")
        briefing_path = root / f"briefing-{date_compact}.md"
    else:
        print(json.dumps({"ok": False, "error": "forneça --date YYYYMMDD ou --path"}))
        return 2

    if not briefing_path.exists():
        print(json.dumps({"ok": False, "error": f"briefing não encontrado: {briefing_path}"}))
        return 1

    try:
        text = briefing_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(json.dumps({"ok": False, "error": f"falha ao ler {briefing_path}: {exc}"}))
        return 1

    fm, title_line, sections = parse_briefing(text)

    # Compare-and-swap opcional (corrige uma race real encontrada em auto-revisão: uma
    # sessão interativa chama detect-unread, começa a renderizar, e ANTES dela chamar
    # mark-read um ciclo headless concorrente roda write-briefing de novo — acrescentando
    # uma seção nova e marcando o arquivo como unread outra vez. Sem este check, o
    # mark-read da sessão interativa clobbra esse `status: unread` recém-escrito para
    # `read`, e a seção nova nunca é renderizada em nenhuma sessão futura — perda
    # silenciosa de Briefing. Com --expected-last-cycle-id, o chamador prova que está
    # marcando como lido exatamente o `last_cycle_id` que ele observou em detect-unread;
    # se o arquivo mudou nesse meio-tempo, recusa e devolve o `last_cycle_id` atual para
    # o chamador re-detectar/re-renderizar em vez de perder a seção nova.
    if args.expected_last_cycle_id is not None and fm.get("last_cycle_id") != args.expected_last_cycle_id:
        print(json.dumps({
            "ok": False,
            "error": "stale",
            "detail": "last_cycle_id mudou desde a leitura — não marcado como lido, re-rode detect-unread e re-renderize",
            "expected_last_cycle_id": args.expected_last_cycle_id,
            "actual_last_cycle_id": fm.get("last_cycle_id"),
            "path": str(briefing_path),
        }))
        return 1

    already_read = fm.get("status") == "read"
    fm["status"] = "read"
    fm["read_at"] = args.ts or now_iso()
    out_text = render_briefing(fm, title_line, sections)
    write_atomic(briefing_path, out_text)

    print(json.dumps({
        "ok": True,
        "path": str(briefing_path),
        "status": "read",
        "already_read": already_read,
        "read_at": fm["read_at"],
    }))
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def add_root_arg(sp: argparse.ArgumentParser) -> None:
    sp.add_argument("--root", default="project_controll/gerente", help="raiz do estado do Gerente (default: project_controll/gerente)")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    pw = sub.add_parser("write-briefing", help="deriva e escreve/atualiza briefing-YYYYMMDD.md para um ciclo")
    add_root_arg(pw)
    pw.add_argument("--cycle-id", required=True)
    pw.add_argument("--started-at", default=None)
    pw.add_argument("--ended-at", default=None, help="usado para derivar a data do arquivo (YYYYMMDD) — ver docstring do módulo")
    pw.add_argument("--stop-reason", required=True, choices=list(VALID_STOP_REASONS))
    pw.add_argument("--stop-detail", default=None, help="ex.: teto-proativo — nuance opcional quando --stop-reason fila-vazia")
    pw.add_argument("--diario-jsonl-path", default=None, help="default: <root>/diario.jsonl")
    pw.add_argument("--estado-path", default=None, help="default: <root>/estado-atual.yaml")
    pw.add_argument("--ts", default=None, help="override de written_at — só para testes determinísticos")
    pw.set_defaults(func=cmd_write_briefing)

    pd = sub.add_parser("detect-unread", help="lista briefing-*.md com status: unread (somente-leitura)")
    add_root_arg(pd)
    pd.set_defaults(func=cmd_detect_unread)

    pm = sub.add_parser("mark-read", help="marca um briefing como lido (idempotente)")
    add_root_arg(pm)
    pm.add_argument("--date", default=None, help="YYYYMMDD ou YYYY-MM-DD")
    pm.add_argument("--path", default=None, help="caminho direto, alternativa a --date")
    pm.add_argument("--ts", default=None, help="override de read_at — só para testes determinísticos")
    pm.add_argument("--expected-last-cycle-id", default=None, help="compare-and-swap: só marca como lido se last_cycle_id do arquivo ainda for este (protege contra escrita concorrente entre detect-unread e mark-read — ver docstring do módulo)")
    pm.set_defaults(func=cmd_mark_read)

    return p


def main(argv: Optional[list] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
