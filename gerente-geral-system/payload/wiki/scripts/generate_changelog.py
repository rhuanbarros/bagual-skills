#!/usr/bin/env python3
"""generate_changelog.py — E4.7 changelog derivado de Tickets `concluido` + `visivel_pro_cliente`.

Story E4.7 (ideias/sistema-artifacts/E4-7-changelog-tickets.md), PRD 01 §4.4 (FR-12),
ideias/epics.md Epic E4.

Dado o board de Tickets (`bagual-tickets`, `.claude/skills/bagual-tickets/SKILL.md`) e
o log de deploys (`deploy-log.jsonl`), deriva as entradas do Documento-tipo `changelog`
(audiência cliente, `document-types.md` § `changelog`) SEM escrita à mão:

  1. Lê todo ticket `.md` em `--tickets-dir` (fonte de verdade — o `board.yaml` é só
     índice, mesma convenção que a Story E5.5 formaliza para o board em geral).
  2. Determina o corte "desde o último deploy" a partir de `--deploy-log`
     (`deploy-log.jsonl`, já em uso neste projeto pelos `make deploy-*`) — por padrão,
     o último `deploy-frontend-production`/`deploy-backend-production` com
     `stage: deploy` e `result: success` (changelog é audiência CLIENTE; só deploys de
     Produção contam como "o cliente já viu isto"; deploys de staging não avançam o
     corte). Pode ser sobrescrito com `--since <ISO8601>`.
  3. Classifica cada ticket com `status: concluido`:
       - `visivel_pro_cliente: true` (ou `"true"`/`True`), fechado dentro da janela
         (>= corte, ou sem corte disponível) → **gera exatamente 1 entrada de
         changelog**, em `changelog_text` (linguagem de usuário, se o ticket já a
         carrega — convenção antecipada de E5.4, "Fechamento com rastro de commit")
         ou, na ausência desse campo, o `title` do ticket com um aviso explícito de que
         precisa de revisão humana/LLM para virar linguagem de cliente (este script é
         stdlib determinístico — não paraphraseia).
       - `visivel_pro_cliente: pendente` → entra em `pendentes_a_resolver`, NUNCA vira
         changelog nesta execução (AC: "resolvidos pela bibliotecária/Gerente ANTES do
         changelog").
       - `visivel_pro_cliente` ausente/false (ex.: `chore`) → nenhuma entrada.
       - fechado antes do corte → `fora_da_janela` (não é erro, só fora do período
         deste changelog; fica disponível para uma próxima execução's contexto).
  4. Com `--append-to <changelog.md>`, anexa as novas entradas (dedup por ticket id via
     marcador `<!-- ticket: TCK-NNN -->`, nunca reescreve o arquivo inteiro nem duplica
     uma entrada já presente) usando escrita atômica (temp + `fsync` + rename, mesma
     primitiva de `_bmad/scripts/memlog.py` / `transition_ledger_entry.py`). Sem
     `--append-to`, só imprime (stdout/--json) — não escreve nada por padrão.

Nenhuma entrada de changelog é escrita à mão por este script no fluxo normal — ele só
DERIVA a partir do estado já registrado nos Tickets (FR-12).

Renderização no app: fora de escopo (este script produz o texto/markdown das entradas,
nunca decide como o app exibe changelog para o cliente).

Uso:
    python3 generate_changelog.py --tickets-dir project_controll/tickets
    python3 generate_changelog.py --tickets-dir project_controll/tickets --deploy-log deploy-log.jsonl
    python3 generate_changelog.py --tickets-dir project_controll/tickets --since 2026-07-01 --json
    python3 generate_changelog.py --tickets-dir project_controll/tickets --append-to wiki/changelog.md

Só biblioteca padrão (stdlib) — nenhuma dependência externa.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

FRONT_MATTER_DELIM = "---"


# ---------------------------------------------------------------------------
# Front-matter parsing (mesmo parser minimalista reusado por retrieve_slice.py /
# validate_wiki_docs.py — subconjunto de YAML: escalar, lista em fluxo, lista em bloco.
# Mantido standalone aqui de propósito, sem import cruzado entre scripts irmãos.)
# ---------------------------------------------------------------------------
def _clean(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        value = value[1:-1]
    return value


def parse_front_matter(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != FRONT_MATTER_DELIM:
        return {}
    fm: dict[str, Any] = {}
    current_list_key: str | None = None
    i = 1
    while i < len(lines):
        line = lines[i]
        if line.strip() == FRONT_MATTER_DELIM:
            break
        stripped = line.strip()
        if stripped.startswith("- ") and current_list_key is not None:
            fm.setdefault(current_list_key, [])
            fm[current_list_key].append(_clean(stripped[2:]))
            i += 1
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if value == "":
                current_list_key = key
                fm.setdefault(key, [])
            elif value.startswith("[") and value.endswith("]"):
                inner = value[1:-1].strip()
                fm[key] = [_clean(v) for v in inner.split(",") if v.strip()] if inner else []
                current_list_key = None
            else:
                fm[key] = _clean(value)
                current_list_key = None
        i += 1
    return fm


def _body_text(text: str) -> str:
    """Corpo do markdown, depois do front-matter (se houver)."""
    lines = text.splitlines()
    if lines and lines[0].strip() == FRONT_MATTER_DELIM:
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == FRONT_MATTER_DELIM), None)
        if end is not None:
            return "\n".join(lines[end + 1 :])
    return text


def _truthy(value: Any) -> bool:
    """True para `true`/`True`/`sim`/`yes` (case-insensitive); False caso contrário."""
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "sim", "yes")


def _is_pendente(value: Any) -> bool:
    return str(value).strip().lower() == "pendente"


# ---------------------------------------------------------------------------
# Corte "desde o último deploy"
# ---------------------------------------------------------------------------
PRODUCTION_TARGETS = ("deploy-frontend-production", "deploy-backend-production")


def latest_production_deploy_ts(deploy_log_path: Path) -> str | None:
    """Retorna o `ts` (ISO8601) do deploy de Produção bem-sucedido mais recente.

    Só conta entradas com `stage: deploy` e `result: success` para um dos
    PRODUCTION_TARGETS — `stage: build`/`migrate` não significa "o cliente já viu isto";
    deploys de staging (banco Dev) nunca avançam o corte do changelog (audiência
    cliente = Produção). Retorna None se o arquivo não existir ou não tiver nenhuma
    entrada qualificada (nesse caso o chamador trata como "sem corte" — inclui tudo).
    """
    if not deploy_log_path.exists():
        return None
    latest: str | None = None
    with open(deploy_log_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if entry.get("stage") != "deploy" or entry.get("result") != "success":
                continue
            if entry.get("target") not in PRODUCTION_TARGETS:
                continue
            ts = entry.get("ts")
            if not ts:
                continue
            if latest is None or ts > latest:
                latest = ts
    return latest


def _ticket_closed_at(fm: dict[str, Any]) -> str | None:
    """Data de fechamento do ticket, com fallback documentado.

    `closed_at` (ISO8601 completo) é o campo esperado da Story E5.4 ("Fechamento com
    rastro de commit"), ainda não implementada neste projeto — quando ausente, cai para
    `updated` (YYYY-MM-DD, já existente em todo ticket via `bagual-tickets`), tratado
    como meia-noite UTC daquele dia para efeito de comparação de janela.
    """
    closed_at = fm.get("closed_at")
    if closed_at:
        return str(closed_at)
    updated = fm.get("updated")
    if updated:
        return f"{updated}T00:00:00Z"
    return None


# ---------------------------------------------------------------------------
# Classificação
# ---------------------------------------------------------------------------
def load_tickets(tickets_dir: Path) -> list[dict[str, Any]]:
    tickets: list[dict[str, Any]] = []
    for path in sorted(tickets_dir.glob("TCK-*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        fm = parse_front_matter(text)
        fm["_path"] = str(path)
        fm["_body"] = _body_text(text)
        tickets.append(fm)
    return tickets


def classify_tickets(tickets: list[dict[str, Any]], since: str | None) -> dict[str, Any]:
    """Classifica cada ticket em 1 de 4 buckets. Retorna o relatório completo.

    Regras (AC de E4.7, PRD 01 FR-12):
      - status != concluido            -> ignorado (nem sequer listado)
      - concluido + pendente           -> pendentes_a_resolver (NUNCA vira changelog)
      - concluido + visivel_pro_cliente ausente/false -> ignorado (ex.: chore)
      - concluido + visivel_pro_cliente true + dentro da janela -> changelog_entries
      - concluido + visivel_pro_cliente true + fora da janela   -> fora_da_janela
    """
    changelog_entries: list[dict[str, Any]] = []
    pendentes_a_resolver: list[dict[str, Any]] = []
    fora_da_janela: list[dict[str, Any]] = []
    ignorados_sem_flag: list[dict[str, Any]] = []

    for fm in tickets:
        if str(fm.get("status", "")).strip() != "concluido":
            continue

        ticket_id = fm.get("id", Path(fm["_path"]).stem)
        visivel = fm.get("visivel_pro_cliente")

        if _is_pendente(visivel):
            pendentes_a_resolver.append(
                {
                    "id": ticket_id,
                    "title": fm.get("title", ""),
                    "path": fm["_path"],
                    "motivo": "visivel_pro_cliente: pendente (headless, F21) — resolver antes do changelog",
                }
            )
            continue

        if not _truthy(visivel):
            ignorados_sem_flag.append({"id": ticket_id, "title": fm.get("title", "")})
            continue

        closed_at = _ticket_closed_at(fm)
        in_window = since is None or closed_at is None or closed_at >= since

        entry = {
            "id": ticket_id,
            "closed_at": closed_at,
            "text": fm.get("changelog_text") or fm.get("title", ""),
            "text_is_fallback_title": "changelog_text" not in fm,
            "source_ticket": fm["_path"],
        }

        if in_window:
            changelog_entries.append(entry)
        else:
            fora_da_janela.append(entry)

    changelog_entries.sort(key=lambda e: e["closed_at"] or "")
    return {
        "since": since,
        "changelog_entries": changelog_entries,
        "pendentes_a_resolver": pendentes_a_resolver,
        "fora_da_janela": fora_da_janela,
        "ignorados_sem_flag": ignorados_sem_flag,
    }


# ---------------------------------------------------------------------------
# Render + append
# ---------------------------------------------------------------------------
def render_entry_markdown(entry: dict[str, Any]) -> str:
    date_part = (entry["closed_at"] or "")[:10] or "????-??-??"
    warning = "" if not entry["text_is_fallback_title"] else "  ⚠️ _texto derivado do título — revisar linguagem de cliente_"
    return f"<!-- ticket: {entry['id']} -->\n- **{date_part}** — {entry['text']}{warning}"


def write_atomic(path: Path, text: str) -> None:
    """Temp + flush + fsync + rename atômico — mesma primitiva de memlog.py / transition_ledger_entry.py."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def append_to_changelog(target: Path, entries: list[dict[str, Any]]) -> list[str]:
    """Anexa entradas novas a `target`, dedup por marcador `<!-- ticket: ID -->`.

    Retorna a lista de ids efetivamente anexados (já existentes são pulados, nunca
    duplicados nem reescritos).
    """
    existing = target.read_text(encoding="utf-8") if target.exists() else (
        "---\ntipo: changelog\n---\n\n# Changelog\n\n"
        "Gerado automaticamente por `generate_changelog.py` a partir de Tickets "
        "`concluido` + `visivel_pro_cliente: true` (Story E4.7). Nenhuma entrada "
        "escrita à mão no fluxo normal (FR-12).\n"
    )
    appended: list[str] = []
    new_blocks: list[str] = []
    for entry in entries:
        marker = f"<!-- ticket: {entry['id']} -->"
        if marker in existing:
            continue
        new_blocks.append(render_entry_markdown(entry))
        appended.append(entry["id"])
    if new_blocks:
        text = existing.rstrip("\n") + "\n\n" + "\n".join(new_blocks) + "\n"
        write_atomic(target, text)
    return appended


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _print_human(result: dict[str, Any]) -> None:
    print(f"Corte (desde o último deploy de Produção): {result['since'] or '(nenhum — inclui tudo)'}")
    print()
    print(f"Entradas de changelog geradas ({len(result['changelog_entries'])}):")
    if not result["changelog_entries"]:
        print("  (nenhuma)")
    for e in result["changelog_entries"]:
        print(f"  {render_entry_markdown(e)}")
    print()
    print(f"Pendentes a resolver ANTES do changelog ({len(result['pendentes_a_resolver'])}):")
    if not result["pendentes_a_resolver"]:
        print("  (nenhum)")
    for p in result["pendentes_a_resolver"]:
        print(f"  · {p['id']} — {p['title']} ({p['motivo']})")
    print()
    print(f"Fora da janela do corte ({len(result['fora_da_janela'])}):")
    for e in result["fora_da_janela"]:
        print(f"  · {e['id']} — fechado {e['closed_at']}")
    print()
    print(f"Ignorados (sem visivel_pro_cliente/false, ex.: chore) ({len(result['ignorados_sem_flag'])}):")
    for i in result["ignorados_sem_flag"]:
        print(f"  · {i['id']} — {i['title']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tickets-dir", required=True, type=Path, help="Pasta com os TCK-NNN-*.md")
    parser.add_argument("--deploy-log", type=Path, default=None, help="Path do deploy-log.jsonl (opcional)")
    parser.add_argument("--since", default=None, help="Sobrescreve o corte (ISO8601), ignora --deploy-log")
    parser.add_argument("--append-to", type=Path, default=None, help="Anexa as novas entradas a este changelog.md (dedup por ticket id)")
    parser.add_argument("--json", action="store_true", help="Emite JSON em vez de texto legível")
    args = parser.parse_args(argv)

    if not args.tickets_dir.exists():
        print(f"erro: tickets-dir não existe: {args.tickets_dir}", file=sys.stderr)
        return 2

    since = args.since
    if since is None and args.deploy_log is not None:
        since = latest_production_deploy_ts(args.deploy_log)

    tickets = load_tickets(args.tickets_dir)
    result = classify_tickets(tickets, since)

    appended: list[str] = []
    if args.append_to is not None:
        appended = append_to_changelog(args.append_to, result["changelog_entries"])
        result["appended_to"] = str(args.append_to)
        result["appended_ids"] = appended

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        _print_human(result)
        if args.append_to is not None:
            print()
            print(f"Anexado a {args.append_to}: {len(appended)} entrada(s) nova(s) {appended}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
