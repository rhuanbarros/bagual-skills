#!/usr/bin/env python3
"""gerente_proactive.py — E8.5 trabalho proativo com teto duro + dedup histórico.

Story E8.5 (ideias/sistema-artifacts/E8-5-trabalho-proativo.md), PRD 00 FR-3, UJ-4,
hardening F24, ideias/epics.md Epic E8. Quando a fila de Tickets `pronto-para-implementar`
está vazia, o Gerente Geral escolhe uma tarefa de um catálogo RESTRITO de baixíssimo risco
(`project_controll/gerente/proactive-catalog.md`, conteúdo/guardrails de cada categoria) e
usa este módulo para (a) decidir qual categoria roda a seguir respeitando um TETO DURO por
ciclo (`next-task`), (b) verificar se um achado já é conhecido no HISTÓRICO PROATIVO
completo — incluindo tickets `concluido`/`descartado`, não só os abertos
(`dedup-check`) — e (c) registrar que uma iteração do catálogo foi consumida
(`record-proactive`).

Composição, não reimplementação: este módulo NUNCA cria/edita um Ticket diretamente em
`project_controll/tickets/` — quem faz isso é sempre a skill `bagual-tickets`
(`--headless`), invocada pelo Gerente depois que `dedup-check` devolve `duplicate: false`.
`dedup-check` também não substitui o dedup da própria skill (que compara contra tickets
ABERTOS, ver `SKILL.md` § Adicionar passo 2) — ele cobre a dimensão ADICIONAL que a skill
não cobre: o histórico proativo FECHADO (`concluido`/`descartado`), exatamente o que o
hardening F24 exige ("não virar máquina de redescobrir e re-arquivar os mesmos achados
toda noite").

Comandos:
  next-task        decide se uma nova iteração do catálogo pode rodar (teto por ciclo) e,
                    se sim, qual categoria (rotação round-robin determinística)
  dedup-check       varre TODOS os tickets `origem: proativo` em disco (qualquer status,
                    incluindo concluido/descartado por padrão) e devolve o(s) candidato(s)
                    mais similares a um achado novo, com veredito duplicate true/false
                    contra um limiar configurável — heurística de overlap de tokens
                    (Jaccard), não um julgamento definitivo: o chamador (Gerente/sub-agente,
                    ambos LLMs) ainda pode revisar `candidates` antes de decidir
  record-proactive  incrementa o acumulador de iterações do ciclo atual (proactive-ciclo.json),
                    reset automático quando --cycle-id muda (mesma filosofia de
                    quota-ciclo.json/E8.3)

Escrita atômica: reusa `write_atomic`/`now_iso` de `gerente_state.py` (E8.2) por IMPORT
direto do arquivo irmão — mesmo padrão de reuso que `gerente_quota.py`/`gerente_dispatch.py`
já usam. O parser de front-matter de ticket (`parse_front_matter`) é reusado por IMPORT
direto de `project_controll/tickets/scripts/rebuild_board.py` — mesma técnica, evitando uma
segunda cópia colada do parser.

Config (teto + limiar de dedup) — ordem de precedência (a mais alta vence):
  1. flag de CLI (ex.: --cap-per-cycle)
  2. variável de ambiente (ex.: GERENTE_PROACTIVE_CAP_PER_CYCLE)
  3. `project_controll/gerente/proactive.config.json` (commitado, editável pelo dono)
  4. default hardcoded neste arquivo (documentado abaixo)

100% local — nenhuma chamada de rede/API neste módulo (grep por
`urllib`/`http`/`socket`/`requests` dá zero resultados). Só biblioteca padrão (stdlib),
mesma convenção dos scripts irmãos.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
TICKETS_SCRIPTS_DIR = SCRIPT_DIR.parent.parent / "tickets" / "scripts"

# ---------------------------------------------------------------------------
# Defaults de configuração — documentados, deliberadamente conservadores.
# ---------------------------------------------------------------------------
# Quantas ITERAÇÕES do catálogo (não quantos Tickets — ver proactive-catalog.md
# § "Unidade de custo") o Gerente pode rodar por ciclo antes de parar o trabalho
# proativo. Pequeno de propósito: cada iteração despacha um sub-agente Sonnet inteiro.
CAP_PER_CYCLE_DEFAULT = 3

# Limiar de similaridade (Jaccard de tokens, 0.0-1.0) acima do qual um achado é
# considerado duplicata de um ticket proativo já existente (aberto ou fechado). Calibrado
# empiricamente (não medido — mesmo caveat de "chute calibrável" já documentado para
# `self_tracked_budget_tokens` em gerente_quota.py/E8.3): 0.30 foi o menor valor que ainda
# reconhece dois achados PARAFRASEADOS (mesma ideia, palavras diferentes) como a mesma
# coisa nos testes reais (`test_gerente_proactive.py` [3]/[3b], score ~0.29-0.31) sem
# capturar um achado genuinamente não relacionado (score observado <0.02 no mesmo teste).
DEDUP_SIMILARITY_THRESHOLD_DEFAULT = 0.30

# Quantos candidatos (ordenados por score decrescente) retornar em `candidates`, além do
# veredito duplicate/best_match.
DEDUP_TOP_N_DEFAULT = 5

CONFIG_FILENAME = "proactive.config.json"

# Catálogo — enum de rotação (ordem estável e determinística). O CONTEÚDO/guardrails de
# cada categoria é documentado em proactive-catalog.md; esta lista é só a chave + label
# curta usada para decidir a rotação round-robin em `next-task`. Mantida deliberadamente
# em paridade 1:1 com as 4 seções "### N. `<id>`" do doc — se uma categoria for
# adicionada/removida lá, espelhar aqui.
CATALOG = [
    {"id": "analise-adversarial-feature", "label": "Análise adversarial de uma feature"},
    {"id": "completude-de-testes", "label": "Aumento de completude de testes"},
    {"id": "descoberta-de-padroes", "label": "Descoberta de padrões a consolidar"},
    {"id": "refino-de-tickets", "label": "Refino de tickets mal-elucidados"},
]


# ---------------------------------------------------------------------------
# Reuso por import direto (mesmo padrão de gerente_quota.py/gerente_dispatch.py)
# ---------------------------------------------------------------------------
def _load_module(path: Path, name: str):
    if not path.exists():
        print(f"erro: {name} não encontrado em {path} — não é possível reusar", file=sys.stderr)
        sys.exit(2)
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_GS = None
_RB = None


def _gs():
    global _GS
    if _GS is None:
        _GS = _load_module(SCRIPT_DIR / "gerente_state.py", "gerente_state")
    return _GS


def _rb():
    """Módulo rebuild_board.py (project_controll/tickets/scripts/) — reusado só pelo
    `parse_front_matter`, o parser minimalista de front-matter de ticket já validado por
    E5.2/E5.5. Não copiado/colado aqui."""
    global _RB
    if _RB is None:
        _RB = _load_module(TICKETS_SCRIPTS_DIR / "rebuild_board.py", "rebuild_board")
    return _RB


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


def resolve_cap_per_cycle(root: Path, cli_value: Optional[int]) -> int:
    if cli_value is not None:
        return cli_value
    env = os.environ.get("GERENTE_PROACTIVE_CAP_PER_CYCLE")
    if env:
        try:
            return int(env)
        except ValueError:
            pass
    cfg = _load_config_file(root)
    if "cap_per_cycle" in cfg:
        try:
            return int(cfg["cap_per_cycle"])
        except (TypeError, ValueError):
            pass
    return CAP_PER_CYCLE_DEFAULT


def resolve_dedup_threshold(root: Path, cli_value: Optional[float]) -> float:
    if cli_value is not None:
        return cli_value
    env = os.environ.get("GERENTE_PROACTIVE_DEDUP_THRESHOLD")
    if env:
        try:
            return float(env)
        except ValueError:
            pass
    cfg = _load_config_file(root)
    if "dedup_similarity_threshold" in cfg:
        try:
            return float(cfg["dedup_similarity_threshold"])
        except (TypeError, ValueError):
            pass
    return DEDUP_SIMILARITY_THRESHOLD_DEFAULT


def resolve_dedup_top_n(root: Path, cli_value: Optional[int]) -> int:
    if cli_value is not None:
        return cli_value
    env = os.environ.get("GERENTE_PROACTIVE_DEDUP_TOP_N")
    if env:
        try:
            return int(env)
        except ValueError:
            pass
    cfg = _load_config_file(root)
    if "dedup_top_n" in cfg:
        try:
            return int(cfg["dedup_top_n"])
        except (TypeError, ValueError):
            pass
    return DEDUP_TOP_N_DEFAULT


# ---------------------------------------------------------------------------
# next-task — teto duro por ciclo + rotação round-robin determinística
# ---------------------------------------------------------------------------
# proactive-ciclo.json — estado do CICLO ATUAL, sobrescrito a cada ciclo novo (mesma
# filosofia de quota-ciclo.json em E8.3), NUNCA histórico entre ciclos.
# Schema:
#   {"cycle_id": str, "count": int, "updated_at": ISO,
#    "entries": [{"ts": ISO, "category": str, "outcome": str, "tickets_filed": [str],
#                 "duplicates_skipped": int, "note": str|null}]}
# `count` é o contador AUTORITATIVO de iterações consumidas (nunca derivado por
# len(entries), mesma disciplina de `self_tracked_tokens_total` em E8.3 — aparar a cauda
# de entries nunca deve poder afetar o teto).
ENTRIES_TAIL_MAX = 200


def _proactive_ciclo_path(root: Path) -> Path:
    return root / "proactive-ciclo.json"


def _load_proactive_ciclo(root: Path) -> dict:
    path = _proactive_ciclo_path(root)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _effective_count(root: Path, cycle_id: str) -> tuple[int, bool]:
    """Devolve (count, same_cycle). Ciclo novo (ou nenhum estado anterior) sempre conta
    como 0 — mesmo auto-reset-por-mudança-de-cycle_id que quota-ciclo.json já usa, sem
    subcomando `reset` dedicado."""
    existing = _load_proactive_ciclo(root)
    same_cycle = existing.get("cycle_id") == cycle_id
    count = int(existing.get("count") or 0) if same_cycle else 0
    return count, same_cycle


def compute_next_task(root: Path, cycle_id: str, cap_per_cycle: int) -> dict:
    count, same_cycle = _effective_count(root, cycle_id)
    if count >= cap_per_cycle:
        return {
            "ok": True,
            "verdict": "cap-reached",
            "cycle_id": cycle_id,
            "count_so_far": count,
            "cap_per_cycle": cap_per_cycle,
            "same_cycle": same_cycle,
            "category": None,
            "catalog": CATALOG,
        }
    category = CATALOG[count % len(CATALOG)]
    return {
        "ok": True,
        "verdict": "go",
        "cycle_id": cycle_id,
        "count_so_far": count,
        "cap_per_cycle": cap_per_cycle,
        "same_cycle": same_cycle,
        "category": category,
        "catalog": CATALOG,
    }


def cmd_next_task(args: argparse.Namespace) -> int:
    root = Path(args.root)
    cap = resolve_cap_per_cycle(root, args.cap_per_cycle)
    result = compute_next_task(root, args.cycle_id, cap)
    print(json.dumps(result, ensure_ascii=False))
    return 0


def record_proactive(
    root: Path,
    cycle_id: str,
    category: str,
    outcome: str,
    tickets_filed: list[str],
    duplicates_skipped: int,
    note: Optional[str],
    reset: bool,
) -> dict:
    existing = {} if reset else _load_proactive_ciclo(root)
    same_cycle = existing.get("cycle_id") == cycle_id
    if not same_cycle:
        count = 0
        entries: list[dict] = []
    else:
        count = int(existing.get("count") or 0)
        entries = list(existing.get("entries") or [])

    count += 1
    ts = now_iso()
    entries.append({
        "ts": ts,
        "category": category,
        "outcome": outcome,
        "tickets_filed": tickets_filed,
        "duplicates_skipped": duplicates_skipped,
        "note": note,
    })
    if len(entries) > ENTRIES_TAIL_MAX:
        entries = entries[-ENTRIES_TAIL_MAX:]

    doc = {
        "cycle_id": cycle_id,
        "count": count,
        "updated_at": ts,
        "entries": entries,
    }
    write_atomic(_proactive_ciclo_path(root), json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
    return doc


def cmd_record_proactive(args: argparse.Namespace) -> int:
    root = Path(args.root)
    cap = resolve_cap_per_cycle(root, args.cap_per_cycle)
    tickets_filed = _load_json_list(args.tickets_filed_json) if args.tickets_filed_json else []
    doc = record_proactive(
        root, args.cycle_id, args.category, args.outcome,
        tickets_filed, args.duplicates_skipped, args.note, args.reset,
    )
    print(json.dumps({
        "ok": True,
        "path": str(_proactive_ciclo_path(root)),
        "cycle_id": doc["cycle_id"],
        "count": doc["count"],
        "cap_per_cycle": cap,
        "cap_reached": doc["count"] >= cap,
        "updated_at": doc["updated_at"],
    }, ensure_ascii=False))
    return 0


def _load_json_list(raw: str) -> list:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"erro: --tickets-filed-json inválido: {exc}", file=sys.stderr)
        sys.exit(2)
    if not isinstance(data, list):
        print("erro: --tickets-filed-json deve ser uma lista JSON", file=sys.stderr)
        sys.exit(2)
    return data


# ---------------------------------------------------------------------------
# dedup-check — histórico proativo completo (incl. concluido/descartado)
# ---------------------------------------------------------------------------
_WORD_RE = re.compile(r"[a-z0-9]+", re.UNICODE)

# Palavras curtas/genéricas demais para carregar sinal de similaridade neste domínio
# (PT-BR) — remove ruído sem tentar ser um stopword-list linguisticamente completo.
_STOPWORDS = {
    "a", "o", "e", "de", "da", "do", "em", "um", "uma", "para", "com", "no", "na",
    "os", "as", "que", "por", "se", "ao", "aos", "das", "dos", "nao", "sem", "sao",
    "the", "and", "or", "of", "to", "in", "on", "is", "it", "at",
}


def _normalize_tokens(text: str) -> set[str]:
    """Minúsculas, remove acentos, tokeniza em [a-z0-9]+, descarta stopwords/tokens de
    1 char. Heurística deliberadamente simples (Jaccard de bag-of-words) — não é NLP
    semântico; serve como candidato-retrieval para o chamador (LLM) revisar, não como
    veredito definitivo sozinho (ver docstring do módulo)."""
    if not text:
        return set()
    decomposed = unicodedata.normalize("NFKD", text)
    ascii_only = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    tokens = _WORD_RE.findall(ascii_only.lower())
    return {t for t in tokens if t not in _STOPWORDS and len(t) > 1}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _ticket_body_after_frontmatter(text: str) -> str:
    rb = _rb()
    lines = text.splitlines()
    if not lines or lines[0].strip() != rb.FRONT_MATTER_DELIM:
        return text
    for i in range(1, len(lines)):
        if lines[i].strip() == rb.FRONT_MATTER_DELIM:
            return "\n".join(lines[i + 1:])
    return text


_SECTION_HEADER_RE = re.compile(r"^##\s+(.+?)\s*$", re.M)


def _extract_section(body: str, header_name: str) -> Optional[str]:
    """Extrai o conteúdo de UMA seção `## <header_name>` do corpo de um ticket (até o
    próximo `## ` ou fim do texto). Devolve None se a seção não existir (tickets legados
    podem não ter `## Descrição` explícita)."""
    headers = list(_SECTION_HEADER_RE.finditer(body))
    for idx, m in enumerate(headers):
        if m.group(1).strip().lower() != header_name.strip().lower():
            continue
        start = m.end()
        end = headers[idx + 1].start() if idx + 1 < len(headers) else len(body)
        return body[start:end].strip()
    return None


def _ticket_signature_text(title: str, body: str) -> str:
    """Texto usado para comparar um ticket existente contra um achado candidato: título +
    a seção `## Descrição` quando presente (o conteúdo semanticamente comparável ao
    par título/descrição de um achado novo) — NUNCA o corpo inteiro, que dilui o overlap
    real com ruído de `## Verificação`/`## Log`/hashes de commit/datas. Cai para o corpo
    inteiro só quando não há `## Descrição` (ticket legado/formato atípico), para nunca
    perder sinal por ausência da seção."""
    descricao = _extract_section(body, "Descrição")
    return f"{title}\n{descricao}" if descricao is not None else f"{title}\n{body}"


def load_proactive_tickets(tickets_dir: Path, include_non_proactive: bool) -> list[dict]:
    """Carrega todos os TCK-*.md do diretório, extrai front-matter + corpo, filtra por
    `origem: proativo` (default retrocompatível: ausência de `origem` no front-matter é
    `manual`, ver SKILL.md § Retrocompatibilidade F9 — nunca tratado como proativo por
    omissão). Devolve TODOS os status, incluindo `concluido`/`descartado` — é exatamente
    essa a dimensão que este comando adiciona sobre o dedup nativo da skill (que só olha
    tickets abertos)."""
    rb = _rb()
    out: list[dict] = []
    if not tickets_dir.exists():
        return out
    for path in sorted(tickets_dir.glob("TCK-*.md")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        fm = rb.parse_front_matter(text)
        ticket_id = fm.get("id") or path.stem
        origem = fm.get("origem") or "manual"
        if origem != "proativo" and not include_non_proactive:
            continue
        title = fm.get("title", "")
        status = fm.get("status", "novo")
        body = _ticket_body_after_frontmatter(text)
        signature = _ticket_signature_text(title, body)
        tokens = _normalize_tokens(signature)
        out.append({
            "ticket_id": ticket_id,
            "title": title,
            "status": status,
            "origem": origem,
            "source": path.name,
            "tokens": tokens,
        })
    return out


def compute_dedup_check(
    tickets_dir: Path,
    title: str,
    description: str,
    threshold: float,
    top_n: int,
    include_non_proactive: bool,
) -> dict:
    candidate_tokens = _normalize_tokens(title) | _normalize_tokens(description)
    corpus = load_proactive_tickets(tickets_dir, include_non_proactive)

    scored = []
    for entry in corpus:
        score = _jaccard(candidate_tokens, entry["tokens"])
        scored.append({
            "ticket_id": entry["ticket_id"],
            "title": entry["title"],
            "status": entry["status"],
            "origem": entry["origem"],
            "score": round(score, 4),
        })
    scored.sort(key=lambda e: e["score"], reverse=True)

    top = scored[:top_n]
    best = top[0] if top else None
    duplicate = bool(best and best["score"] >= threshold)

    return {
        "ok": True,
        "duplicate": duplicate,
        "threshold": threshold,
        "best_match": best if best and best["score"] > 0 else None,
        "candidates": top,
        "scanned_count": len(corpus),
        "scanned_scope": "origem=proativo, todos os status (incl. concluido/descartado)" if not include_non_proactive else "todos os tickets, todos os status",
    }


def cmd_dedup_check(args: argparse.Namespace) -> int:
    root = Path(args.root)
    tickets_dir = Path(args.tickets_dir)
    threshold = resolve_dedup_threshold(root, args.threshold)
    top_n = resolve_dedup_top_n(root, args.top_n)
    result = compute_dedup_check(
        tickets_dir, args.title, args.description or "", threshold, top_n,
        args.include_non_proactive,
    )
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

    pn = sub.add_parser("next-task", help="decide se uma nova iteração do catálogo pode rodar (teto por ciclo) e qual categoria")
    add_root_arg(pn)
    pn.add_argument("--cycle-id", required=True)
    pn.add_argument("--cap-per-cycle", type=int, default=None, help=f"override do teto (default resolvido: {CAP_PER_CYCLE_DEFAULT})")
    pn.set_defaults(func=cmd_next_task)

    pd = sub.add_parser("dedup-check", help="varre o histórico proativo (incl. concluido/descartado) por achados similares")
    add_root_arg(pd)
    pd.add_argument("--tickets-dir", default="project_controll/tickets", help="diretório de tickets (default: project_controll/tickets)")
    pd.add_argument("--title", required=True, help="título do achado candidato")
    pd.add_argument("--description", default="", help="descrição do achado candidato")
    pd.add_argument("--threshold", type=float, default=None, help=f"override do limiar de similaridade 0-1 (default resolvido: {DEDUP_SIMILARITY_THRESHOLD_DEFAULT})")
    pd.add_argument("--top-n", type=int, default=None, help=f"override de quantos candidatos retornar (default resolvido: {DEDUP_TOP_N_DEFAULT})")
    pd.add_argument("--include-non-proactive", action="store_true", help="também escaneia tickets origem=manual (default: só origem=proativo, ver F24)")
    pd.set_defaults(func=cmd_dedup_check)

    pr = sub.add_parser("record-proactive", help="incrementa o acumulador de iterações do catálogo consumidas neste ciclo")
    add_root_arg(pr)
    pr.add_argument("--cycle-id", required=True)
    pr.add_argument("--category", required=True, choices=[c["id"] for c in CATALOG])
    pr.add_argument("--outcome", required=True, help="ex.: 'ticket-filed', 'duplicate-skipped', 'no-finding', 'ticket-refined'")
    pr.add_argument("--tickets-filed-json", default=None, help="JSON list de ids de Ticket criados/tocados nesta iteração (ex.: '[\"TCK-...\"]')")
    pr.add_argument("--duplicates-skipped", type=int, default=0, help="quantos achados desta iteração foram pulados por já serem conhecidos (dedup-check)")
    pr.add_argument("--note", default=None)
    pr.add_argument("--cap-per-cycle", type=int, default=None, help="override do teto, só para o campo informativo cap_reached na resposta")
    pr.add_argument("--reset", action="store_true", help="força zerar o acumulador antes de incrementar, mesmo que --cycle-id bata com o gravado")
    pr.set_defaults(func=cmd_record_proactive)

    return p


def main(argv: Optional[list] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
