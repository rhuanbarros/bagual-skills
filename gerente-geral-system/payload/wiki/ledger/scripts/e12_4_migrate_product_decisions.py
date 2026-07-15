#!/usr/bin/env python3
"""e12_4_migrate_product_decisions.py -- E12.4 one-off migration: product-decisions.md
(49 `## H2`) -> Ledger MADR entries (`decisao-de-produto/`).

Story E12.4 (ideias/sistema-artifacts/E12-4-product-decisions-madr.md), PRD 01 §6.3
(plano de migração), ideias/epics-onda-5.md Epic E12.

NON-DESTRUTIVO: nunca escreve em `_bmad-output/product-decisions.md` (só leitura).
Escreve documentos NOVOS em `wiki/ledger/decisao-de-produto/`, mais um
manifesto DEDICADO (`slice-manifest-product-decisions.json`, não o `slice-manifest.json`
genérico nem os manifestos de E12.2/E12.3 -- para nunca colidir) consumido por
`../../scripts/slice_completeness_gate.py` (E3.5, reusado SEM modificação).

Reusa `extract_h2_sections()`/`find_source_duplicates()` de `slice_completeness_gate.py`
(E3.5) -- mesmo parser H2-aware-de-fences que `slice_monolith.py` (E3.6/E12.1) e as
migrações irmãs (E12.2/E12.3) já usam.

## A tensão transformação-vs-gate -- reusada de E12.2/E12.3, não redescoberta

Mesma técnica já provada e documentada por E12.2 (e reaplicada por E12.3): o corpo
ORIGINAL de cada seção é embutido VERBATIM, ÍNTEGRO, como bloco contíguo dentro de
`## Contexto` ("Texto original (verbatim, íntegro)"). `slice_completeness_gate.py`
compara texto por TOKEN via `difflib.SequenceMatcher` (`check_textual()`) -- só reporta
perda para tokens do lado velho sem correspondência, NA ORDEM CERTA, no lado novo; texto
novo do lado direito é sempre "insert", nunca perda. Logo o gate PASSA por construção,
independente de quanta estrutura MADR adicional exista ao redor. `## Decisão`/
`## Alternativas`/`## Consequências` são preenchidas por EXTRAÇÃO pura dos rótulos reais
do monólito -- nunca parafraseadas; quando um rótulo não existe na seção original, a
seção MADR aponta de volta para `## Contexto` em vez de inventar conteúdo.

## Vocabulário PRÓPRIO de product-decisions.md (diferente de decisions.md/anti-patterns.md)

`product-decisions.md` usa seus próprios rótulos bold (ver cabeçalho do próprio arquivo,
linha 7): `**Comportamento:**` (decisão de produto observável, textualmente equivalente a
`**Decisão:**` em decisions.md -- algumas seções usam a variante
`**Decisão (stakeholder ...):**`), `**Motivação:**`, `**Origem:**`, `**Desde:**`, e o par
que é o CRUX desta story: `**Cuidado:**` (41/49 seções) e `**A revisitar (...):**` (1/49
seção -- só a primeira, sobre o modelo de receita). Mapeamento desta migração:

- `**Comportamento:**`/`**Decisão (stakeholder...):**`  -> `## Decisão`
- `**Cuidado:**`                                         -> `## Consequências`
  (subseção rotulada "Cuidado (preservado do original)")
- `**A revisitar...:**`                                  -> `## Consequências`
  (subseção rotulada "A revisitar (preservado do original)") + front-matter
  `revisitar-pendente: true` (metadado de proveniência da migração, análogo ao
  `tipo_ratificacao_pendente` que E12.2 já usa para sinalizar revisão humana futura --
  NÃO é um valor novo do enum oficial `estado` do schema E4.1, que continua
  candidata/ativa/aposentada; é só um marcador extra que aponta de volta para a mesma
  seção `## Consequências` onde o texto real "A revisitar" foi preservado).
- `**Mantido intacto:**` (1/49 seção -- Cadastro de conta fechado) -> `## Consequências`
  também (mesma forma: descreve o que continua valendo/não muda, semanticamente uma
  consequência do lado "o que NÃO foi decidido nesta entrada").
- Texto rejeitado/supersedido (`SUPERSEDE`/`SUPERSEDIDO`/`REJEITADO`/`wontfix`/
  `revertid[ao]`/`descartad[ao]`, presente em algumas seções que documentam decisões
  anteriores explicitamente revertidas/rejeitadas) -> `## Alternativas consideradas e
  rejeitadas` (extração por palavra-chave, mesmo padrão de `ALT_KEYWORDS` em
  `e12_2_migrate_decisions.py`).

Nenhum destes 4/5 rótulos é garantido presente em toda seção (`**Cuidado:**` falta em
8/49, `**Comportamento:**`-like falta em 5/49) -- quando ausente, a seção MADR
correspondente usa o mesmo texto-honesto-de-lacuna que E12.2/E12.3 já usam ("nenhum
parágrafo rotulado encontrado... ver o texto verbatim completo em `## Contexto`"), nunca
inventa conteúdo. A garantia de "Cuidado/A revisitar preservados semanticamente" nunca
depende dessa extração -- o bloco verbatim em `## Contexto` já preserva os dois campos
por completo, sempre; a extração para `## Consequências` é uma CAMADA A MAIS de
legibilidade estruturada, não a única cópia.

Uso (script standalone, não parametrizado por monólito -- a classificação de área abaixo
é curatorial e específica das 49 seções reais de `product-decisions.md` no momento em que
esta story rodou; um chamador futuro migrando outro monólito com este MESMO padrão de
restruturação MADR deve copiar `segment_body()`/`build_entry()` como ponto de partida, não
importar este arquivo como biblioteca genérica):

    python3 e12_4_migrate_product_decisions.py

Idempotente-com-força: rodar de novo detecta slugs já usados (inclusive os desta própria
execução anterior) e não sobrescreve nada -- aplica sufixo numérico (`-2`, `-3`...) em
qualquer colisão, nunca `overwrite` (mesma regra do `on-complete-contract.md` §3.5).

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

MONOLITH = REPO / "_bmad-output/product-decisions.md"
LEDGER_ROOT = REPO / "wiki/ledger"
FOLDER = "decisao-de-produto"
TIPO = "decisão-de-produto"
TODAY = "2026-07-12"

# ---------------------------------------------------------------------------
# Classificação curatorial de área (por ÍNDICE 0-based, mesma ordem de
# extract_h2_sections -- nunca por re-digitar título, para não arriscar erro de
# transcrição num título com aspas/backticks/emoji). Vocabulário reusado de
# E12.2 (mesmas 49 áreas de produto já em uso na árvore real do Ledger); "simulation"
# é adicionado por ser um módulo de feature real (frontend/src/app/pages/SimulationPage
# + features/simulation) sem tag própria ainda usada nas migrações anteriores.
# ---------------------------------------------------------------------------
AREAS = [
    ["billing"],                                   # 1 modelo de receita subscription-led
    ["proposals"],                                 # 2 repasse marcacao parceiro
    ["landing"],                                   # 3 escopo WDS landing excluida
    ["simulation"],                                # 4 simulacao ferramenta do parceiro
    ["admin", "proposals", "billing", "frontend"],  # 5 correcoes P0 UX
    ["clients", "frontend"],                       # 6 botao salvar cliente disabled
    ["clients", "frontend"],                       # 7 upload CNH PDF
    ["simulation", "frontend"],                    # 8 simulacao botoes removidos definitivamente
    ["simulation", "frontend"],                    # 9 simulacao botoes adicionados (superseded)
    ["simulation", "frontend"],                    # 10 rota /app/simulation redirect
    ["billing", "landing", "frontend"],            # 11 precificacao planos
    ["billing", "backend", "proposals"],           # 12 plano basico vs pro gating
    ["proposals", "backend"],                      # 13 internal notes isolamento
    ["proposals", "frontend"],                     # 14 labels status unificados
    ["proposals", "backend", "frontend"],          # 15 nomenclatura status v2
    ["admin", "proposals", "backend"],             # 16 admin status update bypass
    ["proposals", "backend", "frontend"],          # 17 status transitions machine
    ["simulation", "frontend"],                    # 18 simulacao parte4 ano editavel
    ["clients", "simulation", "admin", "frontend"],  # 19 QA 2026-06-16
    ["clients", "frontend"],                       # 20 formulario cliente sem LGPD checkbox
    ["simulation", "frontend"],                    # 21 simulacao direto resultados + mascara
    ["simulation", "frontend"],                    # 22 simulacao parte2 calculo automatico
    ["simulation", "frontend"],                    # 23 simulacao parte3 compartilhar removido
    ["billing", "frontend", "landing"],            # 24 assinatura whatsapp
    ["simulation", "billing", "auth", "frontend"],  # 25 simulacao/assinatura exigem login
    ["simulation", "proposals", "frontend"],       # 26 bancos parceiros faixa logos
    ["clients", "frontend"],                       # 27 formulario cliente ocupacao parte2
    ["clients", "frontend"],                       # 28 cadastro cliente botao salvar habilitado
    ["clients", "frontend"],                       # 29 cadastro PJ paridade teddy360
    ["frontend", "admin"],                         # 30 sistema de tema
    ["vehicles", "clients", "admin", "frontend"],  # 31 QA re-run BUG-C/BUG-B
    ["vehicles", "frontend"],                      # 32 UF licenciamento parceiro editavel
    ["auth", "frontend"],                          # 33 cadastro conta fechado
    ["proposals", "admin"],                        # 34 paridade teddy360 admin escopo
    ["proposals", "frontend"],                     # 35 botao cancelamento vermelho
    ["admin", "backend"],                          # 36 banners inativos por padrao
    ["landing", "frontend"],                       # 37 landing page substituida
    ["admin", "frontend", "backend"],              # 38 habilitar e salvar banner
    ["admin", "auth"],                             # 39 UI criar/convidar parceiro reaberta
    ["proposals", "frontend"],                     # 40 wizard criar proposta coexiste
    ["admin", "billing", "backend"],               # 41 controle pagamento parceiro stripe/manual
    ["admin", "backend"],                          # 42 programa indicacao falha nao reverte
    ["sistema-meta"],                              # 43 depende epic X producao (processo)
    ["vehicles", "frontend", "backend"],           # 44 UF licenciamento removido
    ["vehicles", "frontend"],                      # 45 valor venda veiculo regra >=0
    ["vehicles", "clients", "frontend", "backend"],  # 46 proprietario/combustivel removidos
    ["clients", "frontend"],                       # 47 cliente casado sem trava conjuge
    ["clients", "frontend"],                       # 48 visualizacao readonly cliente
    ["proposals", "vehicles", "frontend", "backend"],  # 49 valor entrada por proposta
]

DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")

COMPORTAMENTO_PREFIXES = ("**Comportamento", "**Decisão (stakeholder", "**Decisão:**")
CUIDADO_PREFIXES = ("**Cuidado",)
REVISITAR_PREFIXES = ("**A revisitar",)
MANTIDO_PREFIXES = ("**Mantido intacto",)
ALT_KEYWORDS = ("SUPERSEDE", "SUPERSEDID", "supersedid", "REJEITADO", "wontfix",
                "revertid", "Revertid", "descartad", "Descartad")


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
    """Segmenta o corpo em blocos por linha-em-branco E por início de novo parágrafo
    `**Rótulo:**` na MESMA linha de continuação -- técnica idêntica à de
    `e12_2_migrate_decisions.py`/`e12_3_migrate_antipatterns.py`, reusada sem
    modificação (mesmo gotcha real: várias seções de `product-decisions.md` têm
    múltiplos rótulos bold seguidos sem linha em branco entre eles, ex.: seção 5
    ("Comportamento (3 mudanças...)" seguido de "1./2./3." e depois "Motivação:"/
    "Origem:" tudo no mesmo bloco de texto contíguo)."""
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


def collect(paras: list[str], prefixes: tuple[str, ...]) -> list[str]:
    return [p for p in paras if p.startswith(prefixes)]


def collect_alt(paras: list[str]) -> list[str]:
    out = []
    for p in paras:
        if any(k in p for k in ALT_KEYWORDS):
            out.append(p)
    return out


def build_entry(title: str, body: str, areas: list[str]) -> tuple[str, bool]:
    """Retorna (conteúdo_md, revisitar_pendente)."""
    created = extract_created(title, body)
    paras = segment_body(body)

    decisao = collect(paras, COMPORTAMENTO_PREFIXES)
    cuidado = collect(paras, CUIDADO_PREFIXES)
    revisitar = collect(paras, REVISITAR_PREFIXES)
    mantido = collect(paras, MANTIDO_PREFIXES)
    alternativas = collect_alt(paras)

    decisao_text = "\n\n".join(decisao) if decisao else (
        "Nenhum parágrafo rotulado `**Comportamento:**`/`**Decisão (stakeholder...):**` "
        "foi encontrado nesta seção original — ver o texto verbatim completo em "
        "`## Contexto` abaixo para o comportamento de produto real, descrito em prosa "
        "livre no monólito de origem."
    )

    consequencia_blocks: list[str] = []
    if cuidado:
        consequencia_blocks.append(
            "**Cuidado (preservado do original):**\n\n" + "\n\n".join(cuidado)
        )
    if revisitar:
        consequencia_blocks.append(
            "**A revisitar (preservado do original):**\n\n" + "\n\n".join(revisitar)
        )
    if mantido:
        consequencia_blocks.append(
            "**Mantido intacto (preservado do original):**\n\n" + "\n\n".join(mantido)
        )
    consequencias_text = "\n\n".join(consequencia_blocks) if consequencia_blocks else (
        "Nenhum parágrafo rotulado `**Cuidado:**`/`**A revisitar:**` foi encontrado "
        "nesta seção original — ver o texto verbatim completo em `## Contexto` abaixo "
        "(esta seção do monólito não registrava ressalva/pendência de revisão explícita)."
    )

    alternativas_text = "\n\n".join(alternativas) if alternativas else (
        "Nenhuma alternativa/decisão anterior explicitamente rejeitada ou supersedida foi "
        "encontrada nesta seção original — a decisão, tal como registrada no monólito, "
        "não documentava alternativas rejeitadas em um parágrafo separado. Lacuna "
        "estrutural aceita (não uma invenção): ver o texto verbatim completo em "
        "`## Contexto` para o raciocínio completo tal como foi originalmente registrado."
    )

    revisitar_pendente = bool(revisitar)
    revisitar_fm = "revisitar-pendente: true\n" if revisitar_pendente else ""
    revisitar_note = ""
    if revisitar_pendente:
        revisitar_note = (
            "\n> ⚠️ **Sinal de revisão futura (Story E12.4, preservado do "
            "`**A revisitar:**` original):** esta entrada tem uma condição de "
            "revisão explícita registrada pelo stakeholder no monólito de origem — "
            "ver o texto completo em `## Consequências` abaixo (subseção "
            "\"A revisitar\"). Marcado `revisitar-pendente: true` no front-matter "
            "(metadado de proveniência desta migração, não um valor do enum oficial "
            "`estado` de E4.1) para que a bibliotecária/dono consiga filtrar esta "
            "entrada numa curadoria futura sem precisar reler o corpo inteiro do "
            "Ledger.\n"
        )

    front_matter = (
        "---\n"
        f"tipo: {TIPO}\n"
        "estado: candidata\n"
        "causa-da-morte: null\n"
        "contador-de-utilidade: 0\n"
        f"areas: {yaml_list(areas)}\n"
        "reverte: null\n"
        f"created: {created}\n"
        f"updated: {TODAY}\n"
        f"{revisitar_fm}"
        "# proveniência da migração (Story E12.4) — NÃO são campos oficiais do schema E4.1,\n"
        "# só metadado de rastreio da migração; convenção idêntica a e12_2_migrate_decisions.py/\n"
        "# e12_3_migrate_antipatterns.py\n"
        "source_monolith: _bmad-output/product-decisions.md\n"
        f"source_h2: {json.dumps(title, ensure_ascii=False)}\n"
        "migration_status: migrado-madr-e12-4\n"
        "---\n"
    )

    verbatim_intro = (
        "Seção original de `_bmad-output/product-decisions.md` (H2: "
        f"{json.dumps(title, ensure_ascii=False)}), reescrita nesta entrada em gramática "
        "MADR (Story E12.4). O texto abaixo é o corpo ORIGINAL da seção, **verbatim, "
        "íntegro, sem edição** — a garantia mecânica de que nada foi perdido na "
        "restruturação (ver `slice_completeness_gate.py`, que compara este bloco "
        "token-a-token contra o monólito real). Isto inclui, sem qualquer resumo/perda, "
        "os campos `**Cuidado:**`/`**A revisitar:**` quando presentes na seção — a "
        "extração estruturada abaixo (`## Decisão`/`## Consequências`) é uma camada a "
        "mais de legibilidade, nunca a única cópia dessa informação."
    )

    body_md = (
        f"# {title}\n\n"
        f"## Contexto\n{revisitar_note}\n{verbatim_intro}\n\n"
        f"**Texto original (verbatim, íntegro):**\n\n{body.strip()}\n\n"
        f"## Decisão\n{decisao_text}\n\n"
        f"## Alternativas consideradas e rejeitadas\n{alternativas_text}\n\n"
        f"## Consequências\n{consequencias_text}\n"
    )

    return front_matter + "\n" + body_md, revisitar_pendente


def main() -> None:
    monolith_text = MONOLITH.read_text(encoding="utf-8")
    sections = extract_h2_sections(monolith_text)
    titles = [t for t, _ in sections]

    assert len(sections) == len(AREAS), (
        f"contagem real ({len(sections)}) difere da classificação de área preparada "
        f"({len(AREAS)}) -- reconferir AREAS antes de gerar"
    )
    dupes = find_source_duplicates(titles)
    assert not dupes, f"H2 duplicados no monólito: {dupes}"

    used_slugs: set[str] = set()
    target_dir = LEDGER_ROOT / FOLDER
    if target_dir.exists():
        for f in target_dir.glob("*.md"):
            used_slugs.add(f.stem)

    mappings = []
    written = []
    collisions = []
    revisitar_list = []

    for (title, body), areas in zip(sections, AREAS):
        base_slug = slugify(title)
        slug = base_slug
        n = 2
        collided = base_slug in used_slugs
        while slug in used_slugs:
            slug = f"{base_slug}-{n}"
            n += 1
        used_slugs.add(slug)
        if collided:
            collisions.append({"title": title, "base_slug": base_slug, "final_slug": slug})

        content, revisitar_pendente = build_entry(title, body, areas)
        out_path = target_dir / f"{slug}.md"
        out_path.write_text(content, encoding="utf-8")
        written.append(str(out_path))
        mappings.append({"h2": title, "file": f"{FOLDER}/{slug}.md"})
        if revisitar_pendente:
            revisitar_list.append({"title": title, "file": f"{FOLDER}/{slug}.md"})

    manifest = {
        "generated_by": "e12_4_migrate_product_decisions.py (Story E12.4, reusa extract_h2_sections de E3.5)",
        "source_monolith": str(MONOLITH),
        "mappings": mappings,
    }
    manifest_path = LEDGER_ROOT / "slice-manifest-product-decisions.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    report = {
        "h2_total": len(sections),
        "entries_written": len(written),
        "revisitar_pendente_count": len(revisitar_list),
        "revisitar_pendente": revisitar_list,
        "collisions_with_pre_existing": collisions,
        "manifest": str(manifest_path),
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
