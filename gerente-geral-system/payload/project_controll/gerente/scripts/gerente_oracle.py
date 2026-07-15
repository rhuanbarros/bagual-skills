#!/usr/bin/env python3
"""gerente_oracle.py — E9.1 Oráculo: decisão delegada com rastro + raio de estrago por confiança.

Story E9.1 (ideias/sistema-artifacts/E9-1-oraculo-decisao-delegada.md), PRD 00 FR-5
(§4.3, UJ-3), ideias/epics.md Epic E9. Dá ao Gerente Geral (`.claude/agents/gerente-geral.md`)
a faculdade de ORÁCULO: quando uma camada abaixo (sub-agente despachado, ou o próprio
Gerente durante "priorizar") levanta uma decisão ambígua/de escopo, o Gerente decide
AGORA (em vez de escalar ao dono e travar o ciclo), grava o rastro completo — decisão,
justificativa, contexto — como uma Entrada de Ledger (`wiki/ledger/`,
gramática MADR de E4.1), e o RAIO DE ESTRAGO dessa decisão é gatilhado por confiança
(F10, PRD 00 §4.3 hardening):

  * **Alta confiança** (a decisão CITA um precedente — `--precedent`, um Entrada de
    Ledger existente, viva e nunca corrigida, do mesmo padrão) → `proceed_dispatch: true`
    — o trabalho dependente segue liberado nesta mesma execução.
  * **Baixa confiança** (qualquer outro caso — inclusive `--confidence high` pedido SEM
    um precedente que resista à verificação mecânica abaixo) → `proceed_dispatch: false`
    — o trabalho dependente fica PARQUEADO (o Ticket correspondente deve ser movido para
    `triado` pela persona, via `bagual-tickets`, nunca despachado neste ciclo) até
    ratificação do dono.

**A verificação de "precedente" é mecânica, nunca no calor da alegação do chamador** —
é isso que torna a garantia "baixa confiança não vaza para auto-merge" PROVÁVEL, não só
prometida em prosa: `record-decision` SEMPRE recusa `--confidence high` (rebaixando para
`low` com `downgrade_reason` explicado) a menos que `--precedent` aponte para um arquivo
que EXISTE, tem front-matter de Entrada de Ledger válida, com `estado: ativa` (não basta
"não aposentada" — uma entrada `candidata`/pendente, inclusive uma emitida pelo próprio
oráculo minutos antes, NUNCA sustenta alta confiança; exigir `ativa` fecha o encadeamento
"decisão de baixa confiança vira precedente de outra decisão de alta confiança", achado
real em auto-revisão adversarial desta story) e `ratification` ausente ou `ratified`
(nunca `corrected`/`pending`). Nenhum caminho no código aceita "high" só porque o
chamador disse "high" — ver `_resolve_confidence()`. Valores destinados ao front-matter
(`--ticket`, `--precedent`, cada item de `--areas`) são validados contra quebras de
linha antes de qualquer interpolação — um valor com `\n` embutido poderia, em outro
desenho, forjar campos extras dentro do bloco `---...---` (front-matter injection); este
script recusa (`exit 2`) em vez de sanitizar silenciosamente.

Toda entrada nasce `estado: candidata` (nunca `ativa` — mesma disciplina do
`on-complete-contract.md` §4: só o dono ratifica) e `ratification: pending` — um campo
NOVO desta story, específico de entradas de oráculo (`oracle: true`), que rastreia o
ciclo de vida `pending -> ratified | corrected` (AC5 — uma decisão corrigida pelo dono
vira sinal consultável para a Story E9.2, aprendizado de estilo).

Comandos:
  record-decision   grava uma nova decisão do oráculo como Entrada de Ledger candidata
  list-pending       lista entradas de oráculo com `ratification: pending`
  set-ratification   dono ratifica (`ratified`) ou corrige (`corrected`) uma decisão

Story E15.3 (ideias/sistema-artifacts/E15-3-mecanizar-correcao-estilo.md, T2.3) extraiu o
núcleo de `record-decision`/`set-ratification` para as funções PURAS `record_decision()`/
`set_ratification()` (nunca `sys.exit`/`print` — levantam `OracleOperationError`), para
que `gerente_escalation.py::record-sample-review --verdict corrigido` possa IMPORTAR
diretamente este módulo (nunca subprocess) e chamar as duas na MESMA invocação de
processo que grava `sampled-decisions.json` — uma correção de amostragem (E9.5) passa a
alimentar o Ledger (E9.2) atomicamente, em vez de depender de dois comandos manuais
separados. `cmd_record_decision`/`cmd_set_ratification` continuam sendo os únicos pontos
de entrada da CLI, agora wrappers finos dessas funções — comportamento externo da CLI
inalterado.

Story E9.2 (ideias/sistema-artifacts/E9-2-aprendizado-estilo.md, PRD 00 FR-6) torna o
gate de confiança de `record-decision` HISTORY-AWARE: além dos 4 checks mecânicos do
`--precedent` citado (F10, acima), uma solicitação de `--confidence high` agora TAMBÉM é
vetada (rebaixada para `low`) se existir, na mesma árvore do Ledger, uma decisão do
MESMO `tipo` com `ratification: corrected` cujas `areas` tenham overlap suficiente
(limiar configurável por categoria — ver `oracle.config.json`) com as `--areas` do
candidato. "Similar" é definido OPERACIONALMENTE como essa interseção de tags — nunca
correspondência semântica/fuzzy. O limiar de SUPORTE (quantas `areas` em comum um
precedente ratificado precisa ter) também é configurável por categoria — uma categoria
mais sensível (ex. `decisao-de-produto`) pode exigir mais overlap que uma técnica. Ver
`gerente_style.py` (sibling, Story E9.2) para os subcomandos `consult-precedent`
(inspeção pré-decisão, sem gravar nada) e `sm2` (percentual ratificado, derivado do
rastro real). `find_corrected_contradictions()`/`find_ratified_support()`/
`get_category_threshold()`/`load_oracle_config()` abaixo são as primitivas que ambos os
scripts compartilham (import direto, mesma técnica de reuso já usada nesta story para
`transition_ledger_entry.py`/`validate_ledger.py`).

Reuso deliberado (nunca reimplementação) das primitivas já existentes neste projeto:
  * `transition_ledger_entry.py` — `split_front_matter`/`set_front_matter_field`/
    `get_front_matter_field`/`append_transition_note`/`write_atomic`/`render` (import
    direto do arquivo, mesma técnica de `_memlog()` em `gerente_state.py`).
  * `validate_ledger.py` — `parse_front_matter`/`scan_and_validate`, usado tanto para
    ler entradas existentes (precedente, list-pending) quanto como self-check
    obrigatório (§5 do `on-complete-contract.md`) depois de `record-decision`.

Só biblioteca padrão (stdlib) — nenhuma dependência externa, mesma convenção dos
scripts irmãos em `project_controll/gerente/scripts/`.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Reuso por import direto do arquivo (não cópia colada) — mesma técnica de
# `_memlog()` em gerente_state.py.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[3]
_TLE_PATH = _REPO_ROOT / "wiki" / "ledger" / "scripts" / "transition_ledger_entry.py"
_VAL_PATH = _REPO_ROOT / "wiki" / "ledger" / "scripts" / "validate_ledger.py"


def _load_module(path: Path, name: str):
    if not path.exists():
        print(f"erro: módulo não encontrado em {path} — não é possível reusar suas primitivas", file=sys.stderr)
        sys.exit(2)
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_TLE = None
_VAL = None


def tle():
    global _TLE
    if _TLE is None:
        _TLE = _load_module(_TLE_PATH, "transition_ledger_entry")
    return _TLE


def val():
    global _VAL
    if _VAL is None:
        _VAL = _load_module(_VAL_PATH, "validate_ledger")
    return _VAL


def today() -> str:
    return date.today().isoformat()


# ---------------------------------------------------------------------------
# Mapeamento tipo (slug ascii, argumento de CLI/pasta) <-> tipo (display, front-matter)
# — mesma tabela de `on-complete-contract.md` §3, restrita aos 3 tipos-de-decisão
# (o oráculo só decide, nunca cria `regra`/`padrão`/`anti-pattern` — isso é trabalho de
# retrospectiva/curadoria, fora do escopo de E9.1).
# ---------------------------------------------------------------------------
TIPO_SLUG_TO_DISPLAY = {
    "decisao-tecnica": "decisão-técnica",
    "decisao-de-produto": "decisão-de-produto",
    "decisao-de-arquitetura": "decisão-de-arquitetura",
}
TIPO_DISPLAY_TO_SLUG = {v: k for k, v in TIPO_SLUG_TO_DISPLAY.items()}
LEDGER_DECISAO_TIPOS = set(TIPO_SLUG_TO_DISPLAY.values())


def slugify(text: str, max_words: int = 8) -> str:
    """ascii kebab-case a partir de texto livre (PT-BR com acento incluso)."""
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    words = re.findall(r"[A-Za-z0-9]+", normalized.lower())
    return "-".join(words[:max_words]) or "decisao"


class OracleOperationError(RuntimeError):
    """Erro operacional de `record_decision`/`set_ratification` (Story E15.3) —
    substitui os antigos `print(...)+sys.exit(...)` espalhados pelo corpo de
    `cmd_record_decision`/`cmd_set_ratification` para que o NÚCLEO dessas duas
    operações (extraído nesta story em `record_decision()`/`set_ratification()`, funções
    puras) possa ser reusado por IMPORT DIRETO de outro script no mesmo processo
    (`gerente_escalation.py record-sample-review --verdict corrigido`) sem que uma
    validação recusada mate o processo do CHAMADOR de forma não capturável, nem imprima
    um segundo JSON solto no stdout por cima do que o chamador já está montando. Carrega
    `exit_code`/`candidates` para que os wrappers de CLI (`cmd_record_decision`/
    `cmd_set_ratification`) reconstruam a saída (JSON/stderr/exit code) BYTE-A-BYTE
    idêntica à de antes desta story — nenhum comportamento externo da CLI muda."""

    def __init__(self, message: str, exit_code: int = 2, candidates: Optional[list[str]] = None):
        super().__init__(message)
        self.exit_code = exit_code
        self.candidates = candidates


def _reject_newlines(flag: str, value: Optional[str]) -> Optional[str]:
    """Recusa (levanta `OracleOperationError`, exit_code 2) qualquer valor destinado ao
    front-matter que contenha quebras de linha — auto-revisão adversarial da Story E9.1:
    sem esta guarda, um valor com `\\n` embutido em `--ticket`/`--precedent`/um item de
    `--areas` poderia forjar linhas de front-matter extras (ex.: injetar `confidence:
    high`/`ratification: ratified` dentro do mesmo bloco `---...---`), já que `fm_lines`
    é montado por interpolação literal, não por um serializador YAML que escapa
    newlines. Nunca sanitiza silenciosamente — recusa alto e explícito, porque qualquer
    "correção automática" (ex.: substituir por espaço) esconderia o problema real do
    chamador. Story E15.3: levanta exceção em vez de `sys.exit` direto — permite reuso
    desta validação por um chamador em processo (nunca mata o processo do chamador sem
    dar a ele a chance de reportar a falha do jeito que quiser)."""
    if value is None:
        return None
    if "\n" in value or "\r" in value:
        raise OracleOperationError(
            f"--{flag} não pode conter quebra de linha — corromperia o front-matter "
            "YAML (front-matter injection). Recusando.",
            exit_code=2,
        )
    return value


SLUG_ALLOWED_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def reserve_path(dir_path: Path, slug: str, max_attempts: int = 1000) -> Path:
    """Reserva atomicamente um path único dentro de `dir_path` — vencedor único entre
    processos concorrentes via `O_CREAT|O_EXCL` (a mesma garantia de exclusão mútua do
    filesystem que o lock singleton de `gerente_state.py` usa para `os.mkdir`), nunca só
    um `path.exists()` seguido de escrita mais tarde. Auto-revisão adversarial desta
    story: um `unique_path()` ingênuo (check-then-write sem reserva atômica) permite que
    dois processos concorrentes computem o MESMO próximo sufixo livre e colidam no mesmo
    arquivo `.tmp` intermediário de `write_atomic` — reproduzido com 25 chamadas paralelas
    de slug idêntico (até 22 entradas "gravadas com sucesso" silenciosamente sobrescritas,
    17 processos crashando com `FileNotFoundError` não tratado). Cria um placeholder VAZIO
    no path vencedor (preenchido pelo `write_atomic` real logo em seguida, na mesma
    função chamadora) — nunca sobrescreve um arquivo já reservado por outro processo."""
    n: Optional[int] = None
    for _ in range(max_attempts):
        name = f"{slug}.md" if n is None else f"{slug}-{n}.md"
        candidate = dir_path / name
        try:
            fd = os.open(str(candidate), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return candidate
        except FileExistsError:
            n = 2 if n is None else n + 1
            continue
    raise RuntimeError(f"não foi possível reservar um path único sob {dir_path} para slug '{slug}' após {max_attempts} tentativas")


# ---------------------------------------------------------------------------
# E9.2 — aprendizado de estilo: config por categoria + "similar" operacional
# (overlap de `areas`, nunca correspondência semântica/fuzzy).
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
ORACLE_CONFIG_FILENAME = "oracle.config.json"

# Defaults hardcoded — usados quando o arquivo de config está ausente/malformado, ou
# quando uma categoria não tem entrada própria nele (cai no `default` do arquivo, e se
# nem esse existir, cai aqui). Conservador por construção: contradição é mais fácil de
# provar que suporte em TODA categoria (nunca o contrário).
CATEGORY_THRESHOLD_DEFAULTS: dict[str, dict[str, int]] = {
    "decisao-tecnica": {"min_shared_areas_support": 1, "min_shared_areas_contradict": 1},
    "decisao-de-arquitetura": {"min_shared_areas_support": 1, "min_shared_areas_contradict": 1},
    "decisao-de-produto": {"min_shared_areas_support": 2, "min_shared_areas_contradict": 1},
}
FALLBACK_THRESHOLD_DEFAULT: dict[str, int] = {"min_shared_areas_support": 1, "min_shared_areas_contradict": 1}


def load_oracle_config(config_path: Optional[Path] = None) -> dict:
    """Carrega `oracle.config.json` (default: sibling deste script). Nunca lança —
    arquivo ausente/malformado/JSON inválido degrada silenciosamente para `{}` (o
    chamador então cai nos defaults hardcoded via `get_category_threshold`), mesma
    filosofia tolerante de `gerente_quota.py::_load_config_file`."""
    path = config_path if config_path is not None else (SCRIPT_DIR / ORACLE_CONFIG_FILENAME)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def get_category_threshold(config: dict, tipo_slug: str) -> dict[str, int]:
    """Resolve o limiar (`min_shared_areas_support`/`min_shared_areas_contradict`) da
    categoria `tipo_slug`. Precedência: `categories.<tipo_slug>` no arquivo -> `default`
    no arquivo -> `CATEGORY_THRESHOLD_DEFAULTS[tipo_slug]` hardcoded ->
    `FALLBACK_THRESHOLD_DEFAULT` hardcoded. Cada campo é resolvido INDEPENDENTEMENTE
    (um arquivo que só sobrescreve um dos dois campos não perde o outro)."""
    hardcoded = CATEGORY_THRESHOLD_DEFAULTS.get(tipo_slug, FALLBACK_THRESHOLD_DEFAULT)
    categories = config.get("categories") if isinstance(config.get("categories"), dict) else {}
    file_default = config.get("default") if isinstance(config.get("default"), dict) else {}
    file_category = categories.get(tipo_slug) if isinstance(categories.get(tipo_slug), dict) else {}

    resolved: dict[str, int] = {}
    for field in ("min_shared_areas_support", "min_shared_areas_contradict"):
        for source in (file_category, file_default, hardcoded, FALLBACK_THRESHOLD_DEFAULT):
            if field in source:
                try:
                    resolved[field] = int(source[field])
                    break
                except (TypeError, ValueError):
                    continue
    return resolved


def _normalize_area(value: str) -> str:
    return value.strip().lower()


def shared_areas(candidate_areas: list[str], other_areas: list[str]) -> list[str]:
    """Interseção case-insensitive/trimmed entre duas listas de `areas` — a definição
    OPERACIONAL de "similar" desta story (E9.2): nunca NLP/embeddings/keyword-fuzzy,
    sempre correspondência exata de tag (normalizada). Preserva a grafia original (e a
    ordem) de `candidate_areas` no retorno, para exibição."""
    other_normalized = {_normalize_area(a) for a in other_areas if a and a.strip()}
    return [a for a in candidate_areas if a and a.strip() and _normalize_area(a) in other_normalized]


def _ledger_entries(ledger_root: Path):
    """Itera (path, front_matter) de todo `.md` sob `ledger_root`, pulando os arquivos
    de infraestrutura (mesmo filtro de `list-pending`/`set-ratification` acima)."""
    if not ledger_root.exists():
        return
    for path in sorted(ledger_root.rglob("*.md")):
        if path.name in ("index.md", "template-entrada.md", "README.md"):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        yield path, val().parse_front_matter(text)


def find_corrected_contradictions(
    ledger_root: Path, tipo_display: str, candidate_areas: list[str], min_shared: int,
) -> list[dict[str, Any]]:
    """Decisões do MESMO `tipo`, `ratification: corrected`, com overlap de `areas`
    (>= `min_shared`) contra `candidate_areas` — o sinal de "o dono já corrigiu algo
    parecido com isto" que E9.2 usa para VETAR `--confidence high`, mesmo com um
    `--precedent` válido citado. Só olha `oracle: true` (o único tipo de entrada que
    pode carregar `ratification` — decisões humanas pré-existentes nunca têm este
    campo, então nunca aparecem aqui, por desenho)."""
    if min_shared <= 0:
        return []
    hits: list[dict[str, Any]] = []
    for path, fm in _ledger_entries(ledger_root):
        if str(fm.get("oracle", "")).strip().lower() != "true":
            continue
        if fm.get("tipo") != tipo_display:
            continue
        if fm.get("ratification") != "corrected":
            continue
        overlap = shared_areas(candidate_areas, fm.get("areas") or [])
        if len(overlap) >= min_shared:
            hits.append({"path": str(path), "ticket": fm.get("ticket"), "shared_areas": overlap})
    return hits


def find_ratified_support(
    ledger_root: Path, tipo_display: str, candidate_areas: list[str], min_shared: int,
) -> list[dict[str, Any]]:
    """Decisões do MESMO `tipo`, `estado: ativa`, `ratification` ausente/`ratified`
    (nunca `corrected`/`pending` — mesmos 2 checks finais de `validate_precedent_fm`),
    com overlap de `areas` (>= `min_shared`) contra `candidate_areas` — usado por
    `consult-precedent` (gerente_style.py) para sugerir confiança ANTES de decidir, sem
    exigir que o chamador já tenha adivinhado um `--precedent` exato."""
    if min_shared <= 0:
        return []
    hits: list[dict[str, Any]] = []
    for path, fm in _ledger_entries(ledger_root):
        ok, _ = validate_precedent_fm(fm)
        if not ok or fm.get("tipo") != tipo_display:
            continue
        overlap = shared_areas(candidate_areas, fm.get("areas") or [])
        if len(overlap) >= min_shared:
            hits.append({"path": str(path), "ticket": fm.get("ticket"), "shared_areas": overlap})
    return hits


# ---------------------------------------------------------------------------
# Gate de confiança — o núcleo do F10 (mecânica do `--precedent` citado) + E9.2
# (history-aware: contradição por decisão `corrected` similar). Nunca aceita "high" só
# pela alegação do chamador; sempre verifica mecanicamente contra o Ledger.
# ---------------------------------------------------------------------------
def validate_precedent_fm(fm: dict[str, Any]) -> tuple[bool, Optional[str]]:
    """Os 3 checks de conteúdo do front-matter de um precedente candidato (tipo válido +
    `estado: ativa` + `ratification` ausente/`ratified`) — extraído de `_resolve_confidence`
    nesta story (E9.2) para ser reusado por `find_ratified_support` (consulta, sem exigir
    um `--precedent` explícito). Retorna (ok, motivo_se_recusado)."""
    prec_tipo = fm.get("tipo")
    if prec_tipo not in LEDGER_DECISAO_TIPOS:
        return False, f"não é uma Entrada de Ledger de decisão válida (tipo: {prec_tipo!r})"

    # Exige ESTADO ATIVA — não basta "!= aposentada". Uma entrada `candidata` (inclusive
    # uma emitida pelo próprio oráculo minutos antes, ainda `ratification: pending`) NUNCA
    # sustenta alta confiança; senão duas chamadas comuns e não-adversariais encadeariam
    # "decisão de baixa confiança" -> "precedente de uma segunda decisão de alta
    # confiança" — achado real em auto-revisão adversarial da Story E9.1, fechado aqui.
    prec_estado = fm.get("estado")
    if prec_estado != "ativa":
        return False, (
            f"não está em `estado: ativa` (estado: {prec_estado!r}) — só uma decisão viva "
            "E já ratificada/em uso corrente sustenta alta confiança, nunca uma "
            "candidata/pendente"
        )

    prec_ratification = fm.get("ratification")
    if prec_ratification not in (None, "", "null", "ratified"):
        return False, (
            f"tem `ratification: {prec_ratification}` (precisa estar ausente ou "
            "'ratified') — não sustenta alta confiança"
        )

    return True, None


def _resolve_confidence(
    requested: str,
    precedent: Optional[str],
    *,
    areas: Optional[list[str]] = None,
    ledger_root: Optional[Path] = None,
    tipo_display: Optional[str] = None,
    threshold: Optional[dict[str, int]] = None,
) -> tuple[str, Optional[str], list[dict[str, Any]]]:
    """Retorna (confidence_final, downgrade_reason, contradicting_corrected). Default
    conservador: qualquer ambiguidade ou falha de verificação SEMPRE resulta em 'low' —
    nunca em 'high' por omissão/dúvida (AC3/F10: "incerto" é tratado como baixa
    confiança, nunca alta). `contradicting_corrected` (Story E9.2) é sempre `[]` exceto
    no único caso em que efetivamente vetou um `high` que o precedente teria sustentado —
    devolvido para auditabilidade (o chamador grava/expõe, nunca decide de novo)."""
    if requested != "high":
        return "low", None, []  # 'low' explícito ou qualquer valor fora de {high,low} (defensivo)

    if not precedent or not precedent.strip():
        return "low", "confidence 'high' pedida sem --precedent — nenhum padrão anterior citado", []

    prec_path = Path(precedent)
    if not prec_path.exists():
        return "low", f"--precedent aponta para arquivo inexistente: {prec_path}", []

    if prec_path.is_dir():
        return "low", f"--precedent aponta para um diretório, não um arquivo: {prec_path}", []

    try:
        text = prec_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return "low", f"--precedent ilegível: {exc}", []

    fm = val().parse_front_matter(text)
    ok, reason = validate_precedent_fm(fm)
    if not ok:
        return "low", f"--precedent {reason}", []

    # E9.2 — history-aware: mesmo com um --precedent mecanicamente válido, uma decisão
    # `corrected` SIMILAR (mesmo tipo + overlap de `areas` >= limiar da categoria) VETA
    # o `high` — "o dono já corrigiu algo parecido com isto" down-weighta sempre, nunca
    # é ofuscado por um precedente favorável isolado (conservador: contradição > suporte).
    if ledger_root is not None and tipo_display is not None and areas is not None:
        min_contradict = (threshold or FALLBACK_THRESHOLD_DEFAULT)["min_shared_areas_contradict"]
        contradictions = find_corrected_contradictions(ledger_root, tipo_display, areas, min_contradict)
        if contradictions:
            paths = ", ".join(c["path"] for c in contradictions)
            return "low", (
                f"--precedent seria válido, mas {len(contradictions)} decisão(ões) "
                f"`ratification: corrected` do mesmo tipo com `areas` similares "
                f"(overlap >= {min_contradict}) contradiz(em): {paths} — aprendizado de "
                "estilo (E9.2) veta alta confiança quando existe correção similar"
            ), contradictions

    return "high", None, []


# ---------------------------------------------------------------------------
# record-decision
# ---------------------------------------------------------------------------
def record_decision(
    ledger_root: Path,
    tipo_slug: str,
    ticket: str,
    question: str,
    decision: str,
    justification: str,
    context: str,
    alternatives: Optional[str] = None,
    areas_csv: str = "sistema-orquestrador,gerente-geral,oraculo",
    confidence_requested: str = "low",
    precedent: Optional[str] = None,
    oracle_config: Optional[dict] = None,
    slug: Optional[str] = None,
) -> dict:
    """Núcleo de `record-decision` — extraído para função PURA nesta story (E15.3) a
    partir do que antes era só o corpo de `cmd_record_decision` (argparse.Namespace ->
    print(JSON) -> exit code). Nunca usa `sys.exit`/`print` — levanta
    `OracleOperationError` em qualquer validação recusada — para poder ser IMPORTADA
    diretamente por outro script no MESMO PROCESSO (`gerente_escalation.py
    record-sample-review --verdict corrigido`, Story E15.3) sem matar o processo do
    chamador de forma não capturável nem imprimir um segundo JSON solto por cima do que
    o chamador já está montando. `cmd_record_decision` (abaixo) é agora um wrapper fino
    de CLI: traduz `argparse.Namespace` -> esta função -> stdout/stderr/exit code,
    comportamento externo idêntico ao pré-E15.3."""
    tipo_display = TIPO_SLUG_TO_DISPLAY[tipo_slug]
    dir_path = ledger_root / tipo_slug
    dir_path.mkdir(parents=True, exist_ok=True)

    # Recusa (OracleOperationError, exit_code 2) qualquer valor destinado ao
    # front-matter que contenha quebra de linha, ANTES de qualquer outro processamento —
    # nunca sanitiza silenciosamente.
    ticket = _reject_newlines("ticket", ticket)
    precedent = _reject_newlines("precedent", precedent)
    areas = [_reject_newlines("areas", a.strip()) for a in areas_csv.split(",") if a.strip()]

    # E9.2 — gate history-aware: limiar por categoria (arquivo commitado, editável pelo
    # dono; `oracle_config` já resolvido pelo chamador — ver `load_oracle_config`).
    oracle_config = oracle_config if oracle_config is not None else {}
    threshold = get_category_threshold(oracle_config, tipo_slug)

    confidence, downgrade_reason, contradicting_corrected = _resolve_confidence(
        confidence_requested, precedent,
        areas=areas, ledger_root=ledger_root, tipo_display=tipo_display, threshold=threshold,
    )
    blast_radius = "auto-merge" if confidence == "high" else "parked"

    if slug:
        slug = slug.strip()
        if not SLUG_ALLOWED_RE.match(slug):
            raise OracleOperationError(
                f"--slug '{slug}' inválido — só minúsculas/dígitos/hífen, começando "
                "por letra/dígito (evita path traversal e colisão com a convenção de nome)",
                exit_code=2,
            )
    else:
        slug = slugify(f"{ticket}-{decision}")

    # Reserva atômica (O_CREAT|O_EXCL) — nunca um check-then-write ingênuo — é o que
    # torna "nunca sobrescreve, mesmo sob concorrência real" uma garantia do filesystem,
    # não uma esperança (achado de auto-revisão adversarial: ver docstring de `reserve_path`).
    entry_path = reserve_path(dir_path, slug)

    ts = today()
    fm_lines = [
        f"tipo: {tipo_display}",
        "estado: candidata",
        "causa-da-morte: null",
        "contador-de-utilidade: 0",
        f"areas: [{', '.join(areas)}]" if areas else "areas: []",
        "reverte: null",
        f"created: {ts}",
        f"updated: {ts}",
        "oracle: true",
        f"ticket: {ticket}",
        f"confidence: {confidence}",
        f"blast_radius: {blast_radius}",
        "ratification: pending",
        f"precedent: {precedent}" if precedent else "precedent: null",
    ]

    title = decision.strip().splitlines()[0][:120]
    alternatives = alternatives.strip() if alternatives and alternatives.strip() else (
        "- Escalar a decisão ao dono e pausar o Ticket até resposta — rejeitada porque o "
        "protocolo do oráculo (E9.1, PRD 00 FR-5) existe exatamente para evitar travar o "
        "ciclo esperando o dono; a decisão é tomada agora, com rastro completo, sujeita a "
        "ratificação assíncrona (não bloqueante)."
    )

    if confidence == "high":
        gating_note = (
            "Confiança **alta** — cita o precedente `" + str(precedent) + "`, verificado "
            "mecanicamente (estado: ativa, ratification ausente/ratified). O trabalho "
            "dependente deste Ticket segue liberado para prosseguir/auto-mergear nesta "
            "mesma execução."
        )
    else:
        reason_suffix = f" ({downgrade_reason})" if downgrade_reason else ""
        gating_note = (
            f"Confiança **baixa**{reason_suffix} — o trabalho dependente deste Ticket fica "
            "PARQUEADO (não despachado/mergeado nesta execução; o Ticket deve ser movido para "
            "`triado` com nota apontando para esta entrada) até ratificação do dono na próxima "
            "sessão interativa."
        )

    body_lines = [
        "",
        f"# Oráculo — decisão para {ticket}: {title}",
        "",
        "## Contexto",
        context.strip(),
        "",
        f'Pergunta originada do Ticket `{ticket}`: "{question.strip()}"',
        "",
        "## Decisão",
        decision.strip(),
        "",
        "## Alternativas consideradas e rejeitadas",
        alternatives,
        "",
        "## Consequências",
        justification.strip(),
        "",
        gating_note,
        "",
        "Ratificação: `ratification: pending` — aguardando o dono confirmar (`ratified`) ou "
        "corrigir (`corrected`) esta decisão na próxima sessão interativa; ver "
        "`gerente_oracle.py set-ratification`. Uma decisão `corrected` é o sinal de "
        "aprendizado de estilo consumido pela Story E9.2 — nunca apagada, nunca reescrita "
        "silenciosamente.",
        "",
    ]

    tle().write_atomic(entry_path, tle().render(fm_lines, body_lines))

    # Self-check obrigatório (on-complete-contract.md §5) — nunca corretivo para
    # entradas alheias, mas aqui somos o autor da própria entrada recém-criada.
    validation = val().scan_and_validate(ledger_root)
    rel = str(entry_path.relative_to(ledger_root))
    self_violations = validation["violations"].get(rel, [])

    # `proceed_dispatch` é SEMPRE também condicionado ao self-check ter passado — uma
    # entrada malformada (self_violations não-vazio) nunca deve liberar auto-merge, mesmo
    # que a confiança calculada tenha sido 'high' (achado de auto-revisão adversarial: sem
    # este AND, um caller que só lê `proceed_dispatch`, sem checar `ok`/exit code, poderia
    # despachar em cima de uma entrada de Ledger provadamente inválida).
    proceed_dispatch = (confidence == "high") and not self_violations

    ticket_note = (
        f'Decisão do oráculo (confiança: {confidence}, raio: {blast_radius}) para "{question.strip()}": '
        f"{decision.strip()} — ver {entry_path} (ratification: pending)."
    )

    return {
        "ok": not self_violations,
        "ledger_path": str(entry_path),
        "ticket": ticket,
        "confidence": confidence,
        "confidence_requested": confidence_requested,
        "downgrade_reason": downgrade_reason,
        "blast_radius": blast_radius,
        "proceed_dispatch": proceed_dispatch,
        "ratification": "pending",
        "category_threshold": threshold,
        "contradicting_corrected": contradicting_corrected,
        "pending_entry": {"ticket": ticket, "note": f"oráculo ({confidence}): {decision.strip()[:200]} — ver {entry_path}"},
        "ticket_note": ticket_note,
        "self_check_violations": self_violations,
    }


def cmd_record_decision(args: argparse.Namespace) -> int:
    oracle_config = load_oracle_config(Path(args.oracle_config) if args.oracle_config else None)
    try:
        result = record_decision(
            Path(args.ledger_root), args.tipo, args.ticket,
            args.question, args.decision, args.justification, args.context,
            alternatives=args.alternatives, areas_csv=args.areas,
            confidence_requested=args.confidence, precedent=args.precedent,
            oracle_config=oracle_config, slug=args.slug,
        )
    except OracleOperationError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return exc.exit_code
    print(json.dumps(result, ensure_ascii=False))
    return 0 if not result["self_check_violations"] else 1


# ---------------------------------------------------------------------------
# list-pending
# ---------------------------------------------------------------------------
def cmd_list_pending(args: argparse.Namespace) -> int:
    ledger_root = Path(args.ledger_root)
    entries: list[dict[str, Any]] = []
    if ledger_root.exists():
        for path in sorted(ledger_root.rglob("*.md")):
            if path.name in ("index.md", "template-entrada.md", "README.md"):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            fm = val().parse_front_matter(text)
            if str(fm.get("oracle", "")).strip().lower() != "true":
                continue
            if fm.get("ratification") != "pending":
                continue
            ticket = fm.get("ticket")
            if args.ticket and ticket != args.ticket:
                continue
            entries.append({
                "path": str(path),
                "tipo": fm.get("tipo"),
                "ticket": ticket,
                "confidence": fm.get("confidence"),
                "blast_radius": fm.get("blast_radius"),
                "created": fm.get("created"),
                "ratification": fm.get("ratification"),
            })
    print(json.dumps({"count": len(entries), "entries": entries}, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------------------
# set-ratification
# ---------------------------------------------------------------------------
def set_ratification(
    ledger_root: Path,
    status: str,
    entry: Optional[Path] = None,
    ticket: Optional[str] = None,
    note: Optional[str] = None,
) -> dict:
    """Núcleo de `set-ratification` — extraído para função PURA nesta story (E15.3),
    mesma motivação de `record_decision()` acima: reuso por IMPORT DIRETO em
    `gerente_escalation.py` (`record-sample-review --verdict corrigido` chama
    `set_ratification(..., status="corrected")` na MESMA invocação de processo que
    gravou a decisão via `record_decision`, logo antes da escrita que finaliza a
    operação — mesmo padrão de E15.2, ver Entrada de Ledger
    `mecanizar-efeito-colateral-antes-da-escrita-que-finaliza-a-operacao`). Levanta
    `OracleOperationError` (nunca `sys.exit`/`print`) em qualquer caso de erro — esta
    função pura SEMPRE retorna `{"ok": True, ...}` em sucesso; os antigos casos
    `{"ok": False, ...}` de `cmd_set_ratification` viram exceção aqui, e o wrapper de
    CLI (abaixo) as recaptura para reconstruir a saída pré-E15.3 byte-a-byte."""
    entry_path = entry

    if entry_path is None:
        if not ticket:
            raise OracleOperationError(
                "informe --entry <path> ou --ticket <id> (para localizar a entrada pendente)",
                exit_code=2,
            )
        matches: list[Path] = []
        if ledger_root.exists():
            for path in sorted(ledger_root.rglob("*.md")):
                if path.name in ("index.md", "template-entrada.md", "README.md"):
                    continue
                try:
                    text = path.read_text(encoding="utf-8")
                except OSError:
                    continue
                fm = val().parse_front_matter(text)
                if str(fm.get("oracle", "")).strip().lower() != "true":
                    continue
                if fm.get("ticket") == ticket and fm.get("ratification") == "pending":
                    matches.append(path)
        if not matches:
            raise OracleOperationError(
                f"nenhuma entrada de oráculo pendente encontrada para o ticket {ticket}",
                exit_code=1,
            )
        if len(matches) > 1:
            raise OracleOperationError(
                "múltiplas entradas pendentes para este ticket — desambigue com --entry",
                exit_code=1,
                candidates=[str(p) for p in matches],
            )
        entry_path = matches[0]

    if not entry_path.exists():
        raise OracleOperationError(f"entrada não encontrada: {entry_path}", exit_code=2)

    tle_mod = tle()
    text = entry_path.read_text(encoding="utf-8")
    fm_lines, body_lines, _ = tle_mod.split_front_matter(text)

    if tle_mod.get_front_matter_field(fm_lines, "oracle") != "true":
        raise OracleOperationError(f"{entry_path} não é uma entrada de oráculo (sem oracle: true)", exit_code=2)

    previous_ratification = tle_mod.get_front_matter_field(fm_lines, "ratification")
    estado_before = tle_mod.get_front_matter_field(fm_lines, "estado")

    fm_lines = tle_mod.set_front_matter_field(fm_lines, "ratification", status)
    fm_lines = tle_mod.set_front_matter_field(fm_lines, "updated", today())

    estado_after = estado_before
    if status == "ratified" and estado_before == "candidata":
        fm_lines = tle_mod.set_front_matter_field(fm_lines, "estado", "ativa")
        estado_after = "ativa"

    note_suffix = f" — {note.strip()}" if note and note.strip() else ""
    if status == "ratified":
        transition_text = f"ratificada pelo dono{note_suffix}"
    else:
        transition_text = f"corrigida pelo dono{note_suffix} — sinal de aprendizado de estilo (E9.2)"
    body_lines = tle_mod.append_transition_note(body_lines, transition_text)

    tle_mod.write_atomic(entry_path, tle_mod.render(fm_lines, body_lines))

    return {
        "ok": True,
        "entry": str(entry_path),
        "previous_ratification": previous_ratification,
        "new_ratification": status,
        "estado_before": estado_before,
        "estado_after": estado_after,
    }


def cmd_set_ratification(args: argparse.Namespace) -> int:
    # Preservado FORA da função pura: a mensagem original deste caso específico vai só
    # para stderr em texto simples (nunca JSON) — comportamento externo pré-E15.3
    # mantido byte-a-byte.
    if not args.entry and not args.ticket:
        print("erro: informe --entry <path> ou --ticket <id> (para localizar a entrada pendente)", file=sys.stderr)
        return 2

    try:
        result = set_ratification(
            Path(args.ledger_root),
            args.status,
            entry=Path(args.entry) if args.entry else None,
            ticket=args.ticket,
            note=args.note,
        )
    except OracleOperationError as exc:
        payload: dict[str, Any] = {"ok": False, "error": str(exc)}
        if exc.candidates is not None:
            payload["candidates"] = exc.candidates
        print(json.dumps(payload, ensure_ascii=False))
        return exc.exit_code

    print(json.dumps(result, ensure_ascii=False))
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    prd = sub.add_parser("record-decision", help="grava uma nova decisão do oráculo como Entrada de Ledger candidata")
    prd.add_argument("--ledger-root", default="wiki/ledger")
    prd.add_argument("--tipo", choices=sorted(TIPO_SLUG_TO_DISPLAY), default="decisao-tecnica")
    prd.add_argument("--ticket", required=True, help="id do Ticket que originou a pergunta (ex.: TCK-042)")
    prd.add_argument("--question", required=True, help="a pergunta levantada pela camada de execução")
    prd.add_argument("--decision", required=True, help="a decisão em si, formulada de forma acionável")
    prd.add_argument("--justification", required=True, help="o porquê — vira ## Consequências")
    prd.add_argument("--context", required=True, help="o que motivou a pergunta — vira ## Contexto")
    prd.add_argument("--alternatives", default=None, help="alternativas consideradas e rejeitadas (opcional; default genérico se omitido)")
    prd.add_argument("--areas", default="sistema-orquestrador,gerente-geral,oraculo")
    prd.add_argument("--confidence", choices=["high", "low"], default="low", help="pedido do chamador — 'high' só é honrado se --precedent resistir à verificação mecânica (default conservador: low)")
    prd.add_argument("--precedent", default=None, help="path de uma Entrada de Ledger existente do mesmo padrão — obrigatório para tentar 'high'")
    prd.add_argument("--oracle-config", default=None, help="path de oracle.config.json (default: sibling deste script, project_controll/gerente/oracle.config.json) — limiar por categoria do gate history-aware (E9.2)")
    prd.add_argument("--slug", default=None, help="slug do arquivo (default: derivado de --ticket + --decision)")
    prd.set_defaults(func=cmd_record_decision)

    plp = sub.add_parser("list-pending", help="lista entradas de oráculo com ratification: pending")
    plp.add_argument("--ledger-root", default="wiki/ledger")
    plp.add_argument("--ticket", default=None, help="filtra por ticket")
    plp.set_defaults(func=cmd_list_pending)

    psr = sub.add_parser("set-ratification", help="dono ratifica ou corrige uma decisão pendente")
    psr.add_argument("--ledger-root", default="wiki/ledger", help="usado só quando --entry é omitido (localiza via --ticket)")
    psr.add_argument("--entry", default=None, help="path exato da entrada (recomendado quando conhecido)")
    psr.add_argument("--ticket", default=None, help="localiza a entrada pendente deste ticket (erro se houver mais de uma — use --entry)")
    psr.add_argument("--status", choices=["ratified", "corrected"], required=True)
    psr.add_argument("--note", default=None, help="nota livre do dono, anexada à seção ## Transições")
    psr.set_defaults(func=cmd_set_ratification)

    return p


def main(argv: Optional[list] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
