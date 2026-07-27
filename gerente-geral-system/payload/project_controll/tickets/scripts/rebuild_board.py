#!/usr/bin/env python3
"""rebuild_board.py — E5.2 board.yaml reconstruível a partir dos .md por-ticket.

Story E5.2 (ideias/sistema-artifacts/E5-2-campos-id-sem-colisao.md), PRD 02
§4.2/NFR "ID livre de colisão + board reconstruível (F9)", ideias/epics.md Epic E5.

`bagual-tickets` (`.claude/skills/bagual-tickets/SKILL.md`) grava um `.md` por ticket em
`project_controll/tickets/` e mantém `board.yaml` como ÍNDICE derivado. Este script prova
(e mecaniza) que o índice é reconstruível: dado só os `.md`, ele reescreve `board.yaml`
do zero — corromper/perder o índice nunca é fatal, é recuperável.

Fonte de verdade: os arquivos `TCK-*.md`. `board.yaml` nunca é lido por este script (só
escrito) — reconstrução é sempre "de baixo para cima", nunca "corrige o índice a partir
de si mesmo".

Campos do índice por ticket (mesmo schema do front-matter, ver SKILL.md § Armazenamento):
  title, status, priority, category, area, expanded, created, updated,
  origem, visivel_pro_cliente, trilha, escalonar, ledger_refs

Retrocompatibilidade (F9): tickets gravados antes desta story não têm
`origem`/`visivel_pro_cliente`/`trilha`/`ledger_refs` no front-matter — o rebuild aplica
os mesmos defaults que a skill aplica na leitura (`origem: manual`,
`visivel_pro_cliente: false`, `trilha: null`, `ledger_refs: []`), nunca falha por
ausência. Tickets legados também não têm `created`/`updated` no `.md` (só existiam no
`board.yaml` até agora) — o rebuild cai para a data de modificação do arquivo (`mtime`)
nesse caso, e reporta quantos tickets usaram esse fallback (nunca finge que é a data
original real).

`escalonar` (Story E9.4, PRD 02 FR-5 endurecido F20): marcador booleano de
"escalonamento de trilha" — `true` quando `classify_trilha.py` (ou o Gerente, a partir
da E9.5) determinou que a `trilha` deste ticket é ambígua/de baixa confiança e precisa de
decisão humana/do Oráculo, em vez da skill comitar um palpite. Exposto no ÍNDICE
`board.yaml` (não só no corpo do `.md`) de propósito — o Gerente varre os escalados numa
única leitura do índice, sem abrir O(N) arquivos. Retrocompatível como os demais campos
desta família: ausente no `.md` → default `false` (nunca finge que um ticket legado, já
resolvido antes desta story existir, está escalado).

Uso:
    python3 rebuild_board.py --tickets-dir project_controll/tickets
    python3 rebuild_board.py --tickets-dir project_controll/tickets --out /tmp/board.yaml
    python3 rebuild_board.py --tickets-dir project_controll/tickets --dry-run --json

Só biblioteca padrão (stdlib) — nenhuma dependência externa (mesma convenção dos scripts
irmãos em `wiki/scripts/`).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FRONT_MATTER_DELIM = "---"


# ---------------------------------------------------------------------------
# Front-matter parsing (mesmo parser minimalista reusado por generate_changelog.py /
# validate_wiki_docs.py / retrieve_slice.py — subconjunto de YAML: escalar, lista em
# fluxo, lista em bloco. Mantido standalone aqui de propósito, sem import cruzado entre
# scripts irmãos.)
# ---------------------------------------------------------------------------
def _clean(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        quote = value[0]
        value = value[1:-1]
        if quote == '"':
            # Desfaz o escaping padrão de YAML double-quoted scalar (ex.: título com
            # aspas internas, `\"...\"`) — sem isso, o re-round-trip para YAML na
            # serialização (ver _yaml_scalar) duplicaria o escaping e quebraria o parse.
            value = value.replace('\\"', '"').replace("\\\\", "\\")
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


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "sim", "yes")


# ---------------------------------------------------------------------------
# Defaults retrocompatíveis (F9) — mesmos que a skill aplica na leitura de um ticket
# legado sem os campos novos.
# ---------------------------------------------------------------------------
DEFAULT_ORIGEM = "manual"
DEFAULT_VISIVEL_PRO_CLIENTE = False
DEFAULT_TRILHA = None
DEFAULT_ESCALONAR = False
DEFAULT_LEDGER_REFS: list[str] = []


def _file_mtime_date(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%d")


def build_entry(fm: dict[str, Any], path: Path) -> tuple[dict[str, Any], dict[str, bool]]:
    """Deriva a entrada de índice de um ticket + quais campos usaram fallback."""
    fallback_used = {"created": False, "updated": False}

    created = fm.get("created")
    if not created:
        created = _file_mtime_date(path)
        fallback_used["created"] = True

    updated = fm.get("updated")
    if not updated:
        updated = _file_mtime_date(path)
        fallback_used["updated"] = True

    visivel = fm.get("visivel_pro_cliente")
    if visivel is None or visivel == "":
        visivel_out: Any = DEFAULT_VISIVEL_PRO_CLIENTE
    elif str(visivel).strip().lower() == "pendente":
        visivel_out = "pendente"
    else:
        visivel_out = _truthy(visivel)

    trilha = fm.get("trilha")
    if trilha in (None, "", "null", "None"):
        trilha = DEFAULT_TRILHA

    escalonar_raw = fm.get("escalonar")
    if escalonar_raw is None or escalonar_raw == "":
        escalonar = DEFAULT_ESCALONAR
    else:
        escalonar = _truthy(escalonar_raw)

    entry = {
        "title": fm.get("title", ""),
        "status": fm.get("status", "novo"),
        "priority": fm.get("priority", "media"),
        "category": fm.get("category", "duvida"),
        "area": fm.get("area", ""),
        "expanded": _truthy(fm.get("expanded", False)),
        "created": created,
        "updated": updated,
        "origem": fm.get("origem") or DEFAULT_ORIGEM,
        "visivel_pro_cliente": visivel_out,
        "trilha": trilha,
        "escalonar": escalonar,
        "ledger_refs": fm.get("ledger_refs") or list(DEFAULT_LEDGER_REFS),
    }
    if fm.get("duplicate_of"):
        entry["duplicate_of"] = fm["duplicate_of"]
    return entry, fallback_used


# ---------------------------------------------------------------------------
# Coleta
# ---------------------------------------------------------------------------
def load_tickets(tickets_dir: Path) -> tuple[dict[str, dict[str, Any]], list[str], dict[str, int]]:
    """Retorna (tickets_por_id, avisos, stats-de-fallback)."""
    tickets: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    stats = {"total": 0, "created_fallback": 0, "updated_fallback": 0, "missing_id_skipped": 0}

    for path in sorted(tickets_dir.glob("TCK-*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            warnings.append(f"não foi possível ler {path}: {exc}")
            continue

        fm = parse_front_matter(text)
        ticket_id = fm.get("id")
        if not ticket_id:
            warnings.append(f"{path.name}: sem `id` no front-matter — ignorado (não pode virar chave do índice)")
            stats["missing_id_skipped"] += 1
            continue
        if ticket_id in tickets:
            warnings.append(f"{ticket_id}: id duplicado — mantendo a primeira ocorrência ({tickets[ticket_id].get('_source')}), ignorando {path.name}")
            continue

        entry, fallback_used = build_entry(fm, path)
        entry["_source"] = path.name
        tickets[ticket_id] = entry
        stats["total"] += 1
        if fallback_used["created"]:
            stats["created_fallback"] += 1
        if fallback_used["updated"]:
            stats["updated_fallback"] += 1

    return tickets, warnings, stats


# ---------------------------------------------------------------------------
# Serialização YAML (subconjunto suficiente para o schema do board — sem dependência
# externa; espelha manualmente o estilo já usado em board.yaml hoje).
# ---------------------------------------------------------------------------
def _yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value)
    if text == "":
        return '""'
    # Indicadores YAML que só são perigosos NO INÍCIO do escalar — um texto começando
    # com `[`/`{` é lido como flow-sequence/flow-mapping, `&`/`*` como âncora/alias,
    # `!` como tag, `|`/`>` como bloco literal/dobrado, `%` como diretiva, `@`/backtick
    # são reservados, `?`/`-`/`:`/`,` são indicadores de estrutura (achado ao vivo:
    # título começando com `[GERAL]` virou flow-sequence e quebrou o parse do board).
    leading_indicator_chars = ("[", "]", "{", "}", "#", "&", "*", "!", "|", ">", "'", '"', "%", "@", "`", "?", "-", ":", ",")
    needs_quotes = (
        any(ch in text for ch in (":", "#", '"', "'"))
        or text != text.strip()
        or text[0] in leading_indicator_chars
        or ": " in text
        or " #" in text
    )
    if needs_quotes:
        # Escapa backslash ANTES de aspas — senão uma aspa já escapada (`\"`) vira
        # dupla-escapada (`\\"`) e quebra o parse ao reabrir o arquivo.
        escaped = text.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return text


def render_board_yaml(tickets: dict[str, dict[str, Any]], legacy_next_id: int | None) -> str:
    lines: list[str] = [
        "# board.yaml — reconstruído por rebuild_board.py (Story E5.2)",
        "# Fonte de verdade = arquivos TCK-*.md; este índice é sempre recuperável a partir deles.",
    ]
    if legacy_next_id is not None:
        lines.append(f"# next_id (legado, ids sequenciais TCK-NNN) — não usado para gerar ids novos, ver SKILL.md § Armazenamento")
        lines.append(f"next_id: {legacy_next_id}")
    lines.append("tickets:")

    field_order = [
        "title", "status", "priority", "category", "area", "expanded",
        "created", "updated", "origem", "visivel_pro_cliente", "trilha", "escalonar",
        "ledger_refs", "duplicate_of",
    ]

    for ticket_id in sorted(tickets.keys()):
        entry = tickets[ticket_id]
        lines.append(f"  {ticket_id}:")
        for field in field_order:
            if field not in entry:
                continue
            value = entry[field]
            if field == "ledger_refs":
                if not value:
                    lines.append(f"    {field}: []")
                else:
                    lines.append(f"    {field}:")
                    for item in value:
                        lines.append(f"      - {_yaml_scalar(item)}")
                continue
            lines.append(f"    {field}: {_yaml_scalar(value)}")

    return "\n".join(lines) + "\n"


def write_atomic(path: Path, text: str) -> None:
    """Temp + flush + fsync + rename atômico. Diferente dos scripts irmãos, o tmp é ÚNICO
    (`mkstemp`) em vez do fixo `<nome>.tmp`: `board.yaml` é um alvo ÚNICO e compartilhado que
    duas sessões concorrentes (repo multi-sessão) podem reconstruir ao mesmo tempo — um tmp
    fixo faria as duas escreverem no mesmo inode e os `os.replace` correrem sobre conteúdo
    parcial. Um tmp por-processo isola cada escrita; o `os.replace` final continua atômico."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--tickets-dir", required=True, type=Path, help="Pasta com os TCK-*.md")
    parser.add_argument("--out", type=Path, default=None, help="Path de saída do board.yaml (default: <tickets-dir>/board.yaml)")
    parser.add_argument("--dry-run", action="store_true", help="Não escreve nada — só reporta o que seria reconstruído")
    parser.add_argument("--json", action="store_true", help="Emite JSON em vez de texto legível")
    args = parser.parse_args(argv)

    if not args.tickets_dir.exists():
        print(f"erro: tickets-dir não existe: {args.tickets_dir}", file=sys.stderr)
        return 2

    tickets, warnings, stats = load_tickets(args.tickets_dir)

    legacy_numeric_ids = [
        int(tid[len("TCK-"):])
        for tid in tickets
        if tid.startswith("TCK-") and tid[len("TCK-"):].isdigit()
    ]
    legacy_next_id = (max(legacy_numeric_ids) + 1) if legacy_numeric_ids else None

    out_path = args.out or (args.tickets_dir / "board.yaml")
    rendered = render_board_yaml(tickets, legacy_next_id)

    result = {
        "tickets_dir": str(args.tickets_dir),
        "out": str(out_path),
        "dry_run": args.dry_run,
        "stats": stats,
        "warnings": warnings,
        "ticket_ids": sorted(tickets.keys()),
    }

    if not args.dry_run:
        write_atomic(out_path, rendered)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Tickets encontrados: {stats['total']} (em {args.tickets_dir})")
        print(f"  created via fallback (mtime, sem front-matter): {stats['created_fallback']}")
        print(f"  updated via fallback (mtime, sem front-matter): {stats['updated_fallback']}")
        print(f"  sem `id` no front-matter (ignorados): {stats['missing_id_skipped']}")
        if warnings:
            print("Avisos:")
            for w in warnings:
                print(f"  - {w}")
        if args.dry_run:
            print(f"[dry-run] board.yaml NÃO escrito. Destino seria: {out_path}")
        else:
            print(f"board.yaml reconstruído em: {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
