#!/usr/bin/env python3
"""e12_2_migrate_decisions.py -- E12.2 one-off migration: decisions.md (117 `## H2`)
-> Ledger MADR entries (`decisao-tecnica/` / `decisao-de-arquitetura/`).

Story E12.2 (ideias/sistema-artifacts/E12-2-decisions-madr.md), PRD 01 §6.3
(plano de migração), ideias/epics-onda-5.md Epic E12.

NON-DESTRUTIVO: nunca escreve em `_bmad-output/decisions.md` (só leitura).
Escreve documentos NOVOS em `wiki/ledger/decisao-tecnica/` ou
`decisao-de-arquitetura/`, mais um manifesto DEDICADO
(`slice-manifest-decisions.json`, não o `slice-manifest.json` genérico --
para não colidir com o que E12.3/E12.4 escreverão para seus próprios
monólitos na mesma raiz do Ledger) consumido por
`../../scripts/slice_completeness_gate.py` (E3.5, reusado SEM modificação).

Reusa `extract_h2_sections()`/`find_source_duplicates()` de
`slice_completeness_gate.py` (E3.5) -- mesmo parser H2-aware-de-fences que
`slice_monolith.py` (E3.6/E12.1) já usa, para "o que é uma seção" nunca
divergir entre os três scripts.

## A tensão transformação-vs-gate, e como este script a resolve

`slice_completeness_gate.py` foi desenhado para fatiamento QUASE-VERBATIM
(monólito -> um documento por seção, front-matter adicionado, mas o corpo
continua sendo basicamente o texto original). MADR é uma RESTRUTURAÇÃO --
o corpo vira `## Contexto`/`## Decisão`/`## Alternativas`/`## Consequências`,
não mais um blob único. Rodar o gate ingenuamente contra um corpo
reescrito/resumido apagaria a garantia mecânica de "nada foi perdido".

A solução escolhida (documentada na Story E12.2) evita precisar tocar o
gate: o gate compara texto por TOKEN via `difflib.SequenceMatcher`
(`check_textual()`) -- ele só reporta perda quando um token do lado velho
não aparece, NA ORDEM CERTA, em algum lugar do lado novo (opcodes
"delete"/"replace"); tokens novos do lado direito são sempre "insert",
NUNCA contam como perda. Logo: se o corpo ORIGINAL da seção aparece
VERBATIM, ÍNTEGRO, como um bloco contíguo em algum lugar do documento novo
(aqui: dentro de `## Contexto`, rotulado "Texto original (verbatim,
íntegro)"), o gate PASSA por construção, não importa quanta estrutura MADR
adicional seja adicionada ao redor. As seções `## Decisão`/`## Alternativas
consideradas e rejeitadas`/`## Consequências` deste script são preenchidas
por EXTRAÇÃO (sub-parágrafos rotulados `**Decisão:**`/`**Impacto:**`/
`**Por quê:**`/etc. do próprio texto original, nunca reescritos/parafraseados)
-- quando a seção original não tinha um rótulo correspondente, a seção MADR
aponta explicitamente de volta para `## Contexto` em vez de inventar
conteúdo. Resultado: MADR real (não just campos-ritual vazios) + zero risco
de perda semântica, porque a garantia de completude nunca depende da
qualidade da extração -- só do bloco verbatim, que é mecânico.

Uso (script standalone, não parametrizado por monólito -- a classificação
CLASSIFICATION abaixo é curatorial e específica das 117 seções reais de
`decisions.md` no momento em que esta story rodou; um chamador futuro
migrando outro monólito com este MESMO padrão de restruturação MADR deve
copiar `segment_body()`/`build_entry()`/o layout de `CLASSIFICATION` como
ponto de partida, não importar este arquivo como biblioteca genérica):

    python3 e12_2_migrate_decisions.py

Idempotente-com-força: rodar de novo detecta slugs já usados (inclusive
os desta própria execução anterior) e não sobrescreve nada -- aplica
sufixo numérico (`-2`, `-3`...) em qualquer colisão, nunca `overwrite`
(mesma regra do `on-complete-contract.md` §3.5).

Só biblioteca padrão (stdlib) -- nenhuma dependência externa.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "wiki/scripts"))
from slice_completeness_gate import extract_h2_sections, find_source_duplicates  # noqa: E402

MONOLITH = REPO / "_bmad-output/decisions.md"
LEDGER_ROOT = REPO / "wiki/ledger"
TODAY = "2026-07-12"

TIPO_FOLDER = {
    "decisão-técnica": "decisao-tecnica",
    "decisão-de-arquitetura": "decisao-de-arquitetura",
}

# ---------------------------------------------------------------------------
# Classificação curatorial (título -> tipo, áreas, ambíguo) por ÍNDICE (0-based,
# mesma ordem de extract_h2_sections -- nunca por re-digitar o título, para não
# arriscar erro de transcrição num título de 100+ caracteres com backticks).
# tipo: "T" = decisão-técnica, "A" = decisão-de-arquitetura
# ambiguous: True -> tipo_ratificacao_pendente: true no front-matter + nota no corpo
# ---------------------------------------------------------------------------
CLASSIFICATION = [
    ("A", ["sistema-meta"], True),                                   # 1 bridge-declaracao-areas
    ("A", ["sistema-meta"], False),                                  # 2 E10.3 execution graph
    ("T", ["proposals", "frontend"], False),                         # 3 38.3 followup CreateProposalPage
    ("T", ["proposals", "vehicles", "frontend"], False),             # 4 38.3 Proposal.downPayment
    ("T", ["proposals", "frontend", "backend"], False),              # 5 38.2 wizard downPayment
    ("T", ["proposals", "backend"], False),                          # 6 38.1 down_payment coluna
    ("T", ["vehicles", "backend"], False),                           # 7 retro 36/37 VehicleService.update
    ("T", ["backend"], False),                                       # 8 37.1 model_fields_set
    ("T", ["qa"], False),                                            # 9 35.6 QA rotulo
    ("T", ["qa"], False),                                            # 10 35.5 QA traceability
    ("T", ["qa"], False),                                            # 11 35.4 QA carve-out
    ("T", ["qa"], False),                                            # 12 35.3 QA duplicacao mutacoes
    ("T", ["backend"], False),                                       # 13 34.5 referral orchestration
    ("T", ["admin", "frontend"], False),                             # 14 33.1 duas stacks isoladas
    ("T", ["frontend"], False),                                      # 15 epic32 batch-fix
    ("T", ["frontend"], False),                                      # 16 SubmitEvent.submitter
    ("T", ["landing", "frontend"], False),                           # 17 landing redesign fixup
    ("T", ["proposals", "frontend"], False),                         # 18 32.3 wizard
    ("T", ["proposals", "frontend"], False),                         # 19 32.2 sub-navegacao
    ("T", ["clients", "frontend"], False),                           # 20 32.2 findClientByDocument
    ("T", ["admin", "frontend", "backend"], False),                  # 21 31.2 carrossel banners
    ("T", ["admin", "frontend", "backend"], False),                  # 22 31.1 banners pillow
    ("T", ["frontend", "admin"], False),                             # 23 tokens tema
    ("T", ["frontend"], False),                                      # 24 D-24-2 as never
    ("T", ["clients", "frontend"], False),                           # 25 D-24-3 signed urls
    ("A", ["clients", "vehicles", "frontend", "backend"], False),    # 26 D-24-1 [ARCHITECTURE] explicit
    ("T", ["vehicles", "frontend"], False),                          # 27 D-23-4 VehicleForm condition
    ("T", ["clients", "frontend"], False),                           # 28 D-23-3 ClientForm legacy
    ("T", ["landing", "frontend"], False),                           # 29 D1 landing identidade
    ("A", ["auth", "frontend", "backend"], False),                   # 30 guard componente+backend fail-closed
    ("T", ["backend"], False),                                       # 31 app_settings fonte unica
    ("T", ["admin", "backend"], False),                              # 32 PUT admin settings
    ("T", ["auth", "frontend"], False),                              # 33 closeLoginModal
    ("T", ["proposals", "backend"], False),                          # 34 escritas atomicas RPC
    ("T", ["sistema-meta"], False),                                  # 35 audit-first approach
    ("T", ["clients", "frontend", "backend"], False),                # 36 CNPJ dual-written
    ("T", ["clients", "frontend"], False),                           # 37 ClientForm dual-mode
    ("T", ["backend"], False),                                       # 38 hasKey() pattern
    ("T", ["dashboard", "backend"], False),                          # 39 dashboard fan-out
    ("T", ["backend"], False),                                       # 40 async sem bloquear event loop
    ("T", ["auth", "backend"], False),                               # 41 JWT verification cache
    ("T", ["auth", "backend"], False),                               # 42 erro auth vs infra
    ("T", ["clients", "backend"], False),                            # 43 soft-delete clients
    ("T", ["vehicles", "proposals", "backend"], False),              # 44 soft-delete vehicles
    ("T", ["admin", "backend"], False),                              # 45 UserProfilesRepository
    ("T", ["frontend"], False),                                      # 46 double-filter listas
    ("T", ["proposals", "backend"], False),                          # 47 get_stalled_proposals
    ("T", ["testing"], False),                                       # 48 E2E stack real
    ("T", ["backend", "infra"], False),                              # 49 pyproject extraPaths
    ("T", ["clients", "backend"], False),                            # 50 ClientsDatabaseRepository
    ("T", ["frontend"], False),                                      # 51 config.apiUrl
    ("T", ["clients", "frontend"], False),                           # 52 onSubmit union type
    ("A", ["proposals", "backend", "frontend"], False),              # 53 status machine SSOT
    ("T", ["admin", "backend"], False),                              # 54 metodos *_any
    ("T", ["admin", "auth", "backend"], True),                       # 55 admin auth app_metadata.role
    ("T", ["proposals", "backend"], False),                          # 56 pipeline summary agent layer
    ("T", ["proposals", "frontend"], False),                         # 57 ProposalPipeline shared
    ("T", ["admin", "proposals", "backend"], False),                 # 58 admin list proposals filter
    ("T", ["dashboard", "frontend"], False),                         # 59 auto-refresh setInterval
    ("T", ["proposals", "frontend"], False),                         # 60 labels status adaptativos
    ("T", ["frontend"], False),                                      # 61 formularios edit dirty
    ("T", ["billing", "backend"], False),                            # 62 stripe_enabled fail-safe
    ("T", ["auth", "frontend"], False),                              # 63 mapUserToProfile
    ("T", ["infra"], False),                                         # 64 migrations filho do template
    ("T", ["admin", "dashboard", "backend"], False),                 # 65 AdminDashboardService
    ("T", ["admin", "dashboard", "backend"], False),                 # 66 AdminDashboardAgent standalone
    ("T", ["dashboard", "frontend"], False),                         # 67 MetricCard skeleton
    ("T", ["auth", "frontend"], False),                              # 68 signOut scope local
    ("T", ["clients", "backend"], False),                            # 69 ClientCreate model_validator
    ("T", ["clients", "backend"], False),                            # 70 validacao CNPJ domain model
    ("T", ["infra"], False),                                         # 71 supabase db push include-all
    ("T", ["clients", "frontend"], False),                           # 72 dois formularios cliente
    ("T", ["proposals", "frontend"], False),                         # 73 duas telas nova proposta
    ("T", ["auth", "frontend"], False),                              # 74 D-fix24-1 getAuthUserId
    ("T", ["vehicles", "clients", "frontend"], False),               # 75 D-fix24-2 IDOR guard
    ("T", ["admin", "backend", "frontend"], False),                  # 76 D-verbose-logging
    ("T", ["clients", "frontend"], False),                           # 77 formulario PJ compartilhado
    ("T", ["clients", "backend", "frontend"], False),                # 78 D-uf-licenciamento
    ("T", ["auth", "frontend"], False),                              # 79 authService primitivas deletadas
    ("A", ["auth", "backend"], True),                                # 80 CAP-3 before-user-created hook
    ("T", ["admin", "frontend"], False),                             # 81 NavItem.external
    ("T", ["frontend"], False),                                      # 82 CAP-3 boot skeleton
    ("T", ["frontend"], False),                                      # 83 CAP-2 lazy supabase client
    ("T", ["infra"], False),                                         # 84 template-sync 2026-06-29
    ("A", ["infra"], False),                                         # 85 ambiente staging
    ("T", ["infra", "qa"], False),                                   # 86 qa_readonly RLS
    ("T", ["frontend"], False),                                      # 87 fix contraste AlertDialogAction
    ("T", ["admin", "backend"], False),                              # 88 package banners location
    ("T", ["qa", "testing"], False),                                 # 89 legado visual QA removido
    ("T", ["qa", "sistema-meta"], False),                            # 90 bagual-test-pipeline deletado
    ("T", ["landing", "frontend"], False),                           # 91 landing redesign hero
    ("T", ["infra"], False),                                         # 92 migrations via db-url
    ("T", ["frontend"], False),                                      # 93 shadcn Tabs forceMount
    ("T", ["admin", "backend", "frontend"], False),                  # 94 AC4 nome administradores
    ("T", ["admin", "backend"], False),                              # 95 convite pendente
    ("T", ["admin", "backend"], False),                              # 96 DELETE users sem corpo
    ("T", ["admin", "billing", "backend"], False),                   # 97 bloquear/desbloquear ban_duration
    ("T", ["admin", "backend"], False),                              # 98 34.1 full_name server-side
    ("T", ["auth", "backend", "testing"], False),                    # 99 RealUserDep/AdminUserDep testes
    ("T", ["credits", "admin", "backend"], False),                   # 100 template-exception credits/user
    ("T", ["vehicles", "admin", "frontend"], False),                 # 101 36.2 fusao VehicleForm
    ("T", ["clients", "admin", "frontend"], False),                  # 102 37.3 fusao ClientForm
    ("T", ["clients", "frontend"], False),                           # 103 37.4 visualizacao read-only
    ("T", ["frontend", "qa"], False),                                # 104 MaskedDateInput
    ("T", ["qa"], False),                                            # 105 35.2 qa-pack doc types
    ("T", ["sistema-meta"], False),                                  # 106 lock singleton
    ("T", ["sistema-meta"], False),                                  # 107 guardrail cota
    ("T", ["sistema-meta"], True),                                   # 108 AGENTS.md indice-raiz
    ("T", ["sistema-meta"], False),                                  # 109 briefing da manha
    ("T", ["sistema-meta"], False),                                  # 110 aprendizado estilo oraculo
    ("T", ["sistema-meta"], False),                                  # 111 E9.7 design-doc reaproveitado
    ("T", ["sistema-meta"], False),                                  # 112 E10.1 grafo execucao persistido
    ("T", ["sistema-meta"], False),                                  # 113 E10.4 dependencia mesmo track
    ("A", ["sistema-meta"], True),                                   # 114 E10.5 HALT global -> isolamento
    ("A", ["sistema-meta"], False),                                  # 115 E11.1 bagual-worktree pool manager
    ("T", ["sistema-meta"], False),                                  # 116 E11.2 registry.yaml
    ("T", ["sistema-meta"], False),                                  # 117 E11.3 health-check allocate
]

TIPO_NAME = {"T": "decisão-técnica", "A": "decisão-de-arquitetura"}

DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


def slugify(title: str) -> str:
    normalized = unicodedata.normalize("NFKD", title)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_only.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    if not slug:
        slug = "secao"
    return slug[:80].rstrip("-")


def yaml_list(items: list[str]) -> str:
    return "[" + ", ".join(items) + "]"


LABEL_LINE_RE = re.compile(r"^\*\*[^*\n]+?:\*\*")


def segment_body(body: str) -> list[str]:
    """Segmenta o corpo em blocos por linha-em-branco E por início de novo
    parágrafo `**Rótulo:**` na MESMA linha de continuação (o padrão real de
    decisions.md tem vários rótulos em bold seguidos sem linha em branco
    entre eles -- ver `**Decisão:** ... **Por quê:** ... **Impacto:** ...`
    todos dentro do que `\\n\\s*\\n`-split trataria como um único parágrafo).
    Puramente extrativo -- nunca reescreve texto, só decide onde cortar."""
    blocks: list[str] = []
    current: list[str] = []
    for line in body.splitlines():
        if not line.strip():
            if current:
                blocks.append("\n".join(current).strip())
                current = []
            continue
        if LABEL_LINE_RE.match(line) and current:
            blocks.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append("\n".join(current).strip())
    return [b for b in blocks if b]


def extract_created(title: str, body: str) -> str:
    m = DATE_RE.findall(title)
    if m:
        return m[-1]
    m = DATE_RE.findall(body)
    if m:
        return m[0]
    return TODAY


DECISAO_PREFIXES = ("**Decisão:**", "**Decisao:**")
IMPACTO_PREFIXES = ("**Impacto", "**Consequ", "**Trade-off")
ALT_PREFIXES = ("**Rationale", "**Por qu", "**Alternativa", "**Judgment call")
ALT_KEYWORDS = ("rejeitad", "Rejeitada", "em vez de", "alternativa")


def collect(paras: list[str], prefixes: tuple[str, ...]) -> list[str]:
    return [p for p in paras if p.startswith(prefixes)]


def collect_alt(paras: list[str]) -> list[str]:
    out = []
    for p in paras:
        if p.startswith(ALT_PREFIXES) or any(k in p for k in ALT_KEYWORDS):
            out.append(p)
    return out


def build_entry(title: str, body: str, tipo_code: str, areas: list[str], ambiguous: bool) -> str:
    tipo = TIPO_NAME[tipo_code]
    created = extract_created(title, body)
    paras = segment_body(body)

    decisao = collect(paras, DECISAO_PREFIXES)
    impacto = collect(paras, IMPACTO_PREFIXES)
    alternativas = collect_alt(paras)

    decisao_text = "\n\n".join(decisao) if decisao else (
        "Nenhum parágrafo rotulado `**Decisão:**` foi encontrado nesta seção original — "
        "ver o texto verbatim completo em `## Contexto` abaixo para a decisão real, "
        "descrita em prosa livre no monólito de origem."
    )
    consequencias_text = "\n\n".join(impacto) if impacto else (
        "Nenhum parágrafo rotulado `**Impacto:**`/`**Consequências:**` foi encontrado "
        "nesta seção original — ver o texto verbatim completo em `## Contexto` abaixo."
    )
    alternativas_text = "\n\n".join(alternativas) if alternativas else (
        "Nenhuma alternativa explicitamente rotulada foi encontrada nesta seção original "
        "— a decisão, tal como registrada no monólito, não documentava alternativas "
        "rejeitadas em um parágrafo separado. Lacuna estrutural aceita (não uma "
        "invenção): ver o texto verbatim completo em `## Contexto` para o raciocínio "
        "completo tal como foi originalmente registrado."
    )

    ambiguous_note = ""
    ambiguous_fm = ""
    if ambiguous:
        ambiguous_fm = "tipo_ratificacao_pendente: true\n"
        ambiguous_note = (
            "\n> ⚠️ **Sinal para ratificação humana (Story E12.2):** a classificação "
            f"`{tipo}` para esta entrada é um julgamento curatorial de fronteira "
            "(técnica vs. arquitetura) — não uma leitura inequívoca do texto original. "
            "Marcado `tipo_ratificacao_pendente: true` no front-matter; um humano (ou o "
            "dono, na curadoria) deve confirmar ou corrigir o `tipo` antes de tratar esta "
            "classificação como definitiva.\n"
        )

    front_matter = (
        "---\n"
        f"tipo: {tipo}\n"
        "estado: candidata\n"
        "causa-da-morte: null\n"
        "contador-de-utilidade: 0\n"
        f"areas: {yaml_list(areas)}\n"
        "reverte: null\n"
        f"created: {created}\n"
        f"updated: {TODAY}\n"
        f"{ambiguous_fm}"
        "# proveniência da migração (Story E12.2) — NÃO são campos oficiais do schema E4.1,\n"
        "# só metadado de rastreio da migração; convenção idêntica a slice_monolith.py/E12.1\n"
        "source_monolith: _bmad-output/decisions.md\n"
        f"source_h2: {json.dumps(title, ensure_ascii=False)}\n"
        "migration_status: migrado-madr-e12-2\n"
        "---\n"
    )

    verbatim_intro = (
        "Seção original de `_bmad-output/decisions.md` (H2: "
        f"{json.dumps(title, ensure_ascii=False)}), reescrita nesta entrada em gramática "
        "MADR (Story E12.2). O texto abaixo é o corpo ORIGINAL da seção, **verbatim, "
        "íntegro, sem edição** — a garantia mecânica de que nada foi perdido na "
        "restruturação (ver `slice_completeness_gate.py`, que compara este bloco "
        "token-a-token contra o monólito real)."
    )

    body_md = (
        f"# {title}\n\n"
        f"## Contexto\n{ambiguous_note}\n{verbatim_intro}\n\n"
        f"**Texto original (verbatim, íntegro):**\n\n{body.strip()}\n\n"
        f"## Decisão\n{decisao_text}\n\n"
        f"## Alternativas consideradas e rejeitadas\n{alternativas_text}\n\n"
        f"## Consequências\n{consequencias_text}\n"
    )

    return front_matter + "\n" + body_md


def main() -> None:
    monolith_text = MONOLITH.read_text(encoding="utf-8")
    sections = extract_h2_sections(monolith_text)
    titles = [t for t, _ in sections]

    assert len(sections) == len(CLASSIFICATION), (
        f"contagem real ({len(sections)}) difere da classificação preparada "
        f"({len(CLASSIFICATION)}) -- reconferir CLASSIFICATION antes de gerar"
    )
    dupes = find_source_duplicates(titles)
    assert not dupes, f"H2 duplicados no monólito: {dupes}"

    # slugs já em uso na árvore real do Ledger (evita sobrescrever qualquer
    # entrada pré-existente -- ex.: uma "lock-singleton" já migrada por outro
    # mecanismo, ver Dev Notes da story) + slugs já usados NESTA execução.
    used_slugs: dict[str, set[str]] = {"decisao-tecnica": set(), "decisao-de-arquitetura": set()}
    for folder in used_slugs:
        d = LEDGER_ROOT / folder
        if d.exists():
            for f in d.glob("*.md"):
                used_slugs[folder].add(f.stem)

    mappings = []
    written = []
    collisions = []
    ambiguous_list = []
    type_counts = {"decisão-técnica": 0, "decisão-de-arquitetura": 0}

    for (title, body), (tipo_code, areas, ambiguous) in zip(sections, CLASSIFICATION):
        folder = TIPO_FOLDER[TIPO_NAME[tipo_code]]
        base_slug = slugify(title)
        slug = base_slug
        n = 2
        collided = base_slug in used_slugs[folder]
        while slug in used_slugs[folder]:
            slug = f"{base_slug}-{n}"
            n += 1
        used_slugs[folder].add(slug)
        if collided:
            collisions.append({"title": title, "folder": folder, "base_slug": base_slug, "final_slug": slug})

        content = build_entry(title, body, tipo_code, areas, ambiguous)
        out_path = LEDGER_ROOT / folder / f"{slug}.md"
        out_path.write_text(content, encoding="utf-8")
        written.append(str(out_path))
        mappings.append({"h2": title, "file": f"{folder}/{slug}.md"})
        type_counts[TIPO_NAME[tipo_code]] += 1
        if ambiguous:
            ambiguous_list.append({"title": title, "tipo": TIPO_NAME[tipo_code], "file": f"{folder}/{slug}.md"})

    manifest = {
        "generated_by": "e12_2_migrate_decisions.py (Story E12.2, reusa extract_h2_sections de E3.5)",
        "source_monolith": str(MONOLITH),
        "mappings": mappings,
    }
    manifest_path = LEDGER_ROOT / "slice-manifest-decisions.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    report = {
        "h2_total": len(sections),
        "entries_written": len(written),
        "type_counts": type_counts,
        "ambiguous_count": len(ambiguous_list),
        "ambiguous": ambiguous_list,
        "collisions_with_pre_existing": collisions,
        "manifest": str(manifest_path),
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
