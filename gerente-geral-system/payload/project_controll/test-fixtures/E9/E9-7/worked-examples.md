# E9.7 — Worked examples (prova de execução, não hipotéticos)

Story `ideias/sistema-artifacts/E9-7-design-artifacts-wiki.md`. Todos os comandos abaixo
foram rodados de verdade contra o repositório real (`wiki/`,
`_bmad-output/product-decisions.md`), depois de registrar os 10 documentos-ponteiro
`design-doc` em `wiki/design-artifacts/`. Saída completa em JSON salva ao
lado (`retrieve-slice-*.json`, `product-decisions-grep-proposals.txt`).

## 1. `design-artifacts` é discoverável por `retrieve_slice.py` — área `proposals`

```
python3 wiki/scripts/retrieve_slice.py --wiki-root wiki --feature proposals --json
```

Saída completa em [`retrieve-slice-proposals.json`](./retrieve-slice-proposals.json).
Resumo: `incompleto: false`, **5 docs diretos** (todos `tipo: design-doc`):
`scenario-01-parceiro-primeira-venda.md`, `scenario-03-operador-proposta-ted360.md`,
`scenario-05-operador-negocio-proprio.md`, `scenario-evolucao-wizard-criar-proposta.md`,
`trigger-map.md`; + 3 docs por expansão adjacente (`scenario-02-...`,
`scenario-04-...`, `scenario-evolucao-carrossel-banners.md`, via `dashboard`/`credits`).

**Contraste com o snapshot da Story E6.1** (`E6-1-grounding-spec-time.md`, Dev Agent
Record): naquela story, o mesmo comando para `proposals` retornava `direct: []`,
`incompleto: true` — porque a Wiki não tinha nenhum documento de conhecimento de domínio
ainda. Esta story (E9.7) é a primeira a popular a Wiki com documentos reais e
descobríveis — via o Documento-tipo `design-doc`, sem esperar a migração completa dos 4
monólitos (E3.6, ainda deferida ao dono). `wiki/retrieval-guide.md` §4 foi
atualizado para refletir este novo estado (ver Change Log da story).

## 2. Discoverável para TODAS as áreas cobertas por algum cenário WDS — área `billing`

```
python3 wiki/scripts/retrieve_slice.py --wiki-root wiki --feature billing --json
```

Saída completa em [`retrieve-slice-billing.json`](./retrieve-slice-billing.json).
`incompleto: false`, 4 docs diretos (`scenario-02-parceiro-vira-pro.md`,
`scenario-04-operador-capta-parceiros.md`,
`scenario-evolucao-programa-indicacao-ciclo2.md`, `trigger-map.md`).

## 3. Degradação graciosa — área `chat` (sem cobertura WDS real)

```
python3 wiki/scripts/retrieve_slice.py --wiki-root wiki --feature chat --json
```

Saída completa em [`retrieve-slice-chat.json`](./retrieve-slice-chat.json). `direct: []`
(nenhum documento `design-doc` declara `chat` em `areas:` — gap real do corpus WDS, não
um bug de indexação, documentado em `design-artifacts/index.md` § "Gap real conhecido").
`incompleto: true`, `incompleto_reason: "cobertura direta rasa (0 doc(s) direto(s) <
limiar 2)"`. Nota: a expansão adjacente (`chat → dashboard`, `area-adjacency.json`)
ainda traz 5 docs "adjacentes" — prova de que o flag `incompleto` corretamente NÃO se
deixa mascarar por cobertura só-adjacente (mesmo comportamento já provado pelo Caso 2 de
`retrieval-guide.md` §5 para `billing` antes desta story). O passo de grounding (item 3
do sub-procedimento em `bmad-create-story.toml`) instrui, neste caso, registrar
explicitamente "Sem design-artifacts/regras de produto conhecidas para a área chat" —
**nunca** fabricar um cenário para essa área.

## 4. Grounding também lê `product-decisions.md` — grep por área `proposals`

```
grep -n '^## \[PRODUCT\]' _bmad-output/product-decisions.md | grep -i "proposta"
```

Saída completa em
[`product-decisions-grep-proposals.txt`](./product-decisions-grep-proposals.txt) — 5
entradas reais encontradas, incluindo duas diretamente relevantes para uma story
hipotética que toca `proposals`:
- `## [PRODUCT] Wizard "Criar Proposta" coexiste com o picker simples — ...` (2026-07-03)
- `## [PRODUCT] Paridade Teddy360 (proposta admin) escopada só ao produto "Financiamento de veículos" — ...` (2026-07-01)

Isto prova mecanicamente que o sub-passo 2 do procedimento novo em
`bmad-create-story.toml` (Story E9.7) encontra conteúdo real em `product-decisions.md`
por área tocada — necessário porque essas decisões nasceram (ou seriam roteadas) pela
via (ii) do roteamento de produto (Story E9.6), que só escreve em
`product-decisions.md`, nunca em `00-ux-scenarios.md`. Sem este passo, o grounding
ficaria cego a exatamente essa classe de regra — o furo que PRD 05 FR-1b/FR-4 aponta
("o grounding lê também product-decisions.md, não só scenarios").

## 5. Simulação do output — "### Grounding da Wiki (fatia)" para uma story hipotética tocando `proposals`

O procedimento em `bmad-create-story.toml` é executado por um agente LLM durante a
criação de uma story real (não um script) — a mesma natureza prompt-driven de E6.1 (ver
`E6-1-grounding-spec-time.md`, que também validou por comando+leitura, não por teste
automatizado). Este é o texto que o procedimento, seguido literalmente contra os
resultados acima, produziria nas Dev Notes de uma story hipotética que toca `proposals`
(ex.: "adicionar campo X à tela de detalhe de proposta"):

```markdown
### Grounding da Wiki (fatia)

Área(s) consultada(s): proposals (+ expansão adjacente: vehicles, clients, credits,
simulation, dashboard)

**Design/produto (WDS, Story E9.7):**
- Cenário 01 (O Parceiro fecha sua primeira venda com financiamento) — persona A (O
  Parceiro); páginas: Dashboard Parceiro, Clientes, Veículos, Simulação, Proposta
  (nova/lista/detalhe); user value: fecha a venda inteira sem repassar. Fonte:
  `_bmad-output/C-UX-Scenarios/00-ux-scenarios.md` § Cenário 01 +
  `01-parceiro-primeira-venda/01-parceiro-primeira-venda.md`.
- Cenário 03 (O Operador transforma uma proposta em financiamento na TED 360) — persona
  D (O Operador); páginas: Dashboard Admin, Propostas Admin; user value: fecha a
  proposta rápido, sem perder nenhuma. Fonte: `00-ux-scenarios.md` § Cenário 03 +
  `03-operador-proposta-ted360/03-operador-proposta-ted360.md`.
- Cenário de evolução "Wizard Criar Proposta" (Epic 32, já implementado; furo PRD 05
  §4.2 — não refletido na Coverage Matrix canônica ainda): substitui a tela única por um
  wizard guiado com paridade TED 360; coexiste com o picker simples (ver regra de
  produto abaixo). Fonte: `_bmad-output/evolution/scenarios/2026-07-01-wizard-criar-proposta.md`.
- Trigger Map (cross-cutting): força negativa nº1 do Parceiro é o medo de a Dômus reter
  a comissão — qualquer mudança na tela de proposta deve preservar a transparência do
  repasse. Fonte: `_bmad-output/B-Trigger-Map/trigger-map.md`.

  Regras de produto (`_bmad-output/product-decisions.md`):
- "Wizard 'Criar Proposta' coexiste com o picker simples — duas rotas para o mesmo
  resultado, não é duplicação a remover" (2026-07-03): as duas rotas de criação de
  proposta continuam existindo lado a lado; não consolidar sem decisão explícita.
- "Paridade Teddy360 (proposta admin) escopada só ao produto 'Financiamento de
  veículos'" (2026-07-01): não expandir paridade de campos para outros produtos
  financeiros sem decisão nova.

Incompleto: nenhuma área consultada veio `incompleto: true` (proposals: incompleto=false).
Gap de curadoria: nenhum (monólitos de decisão/anti-pattern/nota ainda não migrados —
comportamento esperado pré Story E3.6, coberto separadamente pelos `persistent_facts`
de `bmad-dev-story.toml`/`bmad-quick-dev.toml`).
```

## 6. Simulação do output — degradação graciosa para uma story hipotética tocando `chat`

```markdown
### Grounding da Wiki (fatia)

Área(s) consultada(s): chat (+ expansão adjacente: dashboard)

**Design/produto (WDS, Story E9.7):** Sem design-artifacts/regras de produto conhecidas
para a área chat.

Incompleto: chat — cobertura direta rasa (0 doc(s) direto(s) < limiar 2).
Gap de curadoria: nenhum documento sem `areas:` bateu diretamente nesta consulta
(os 3 gaps listados por `retrieve_slice.py` — `_migration-staging/notes/...`,
`changelog.md`, `recall-audit-log.md` — são meta-documentos sem relação com `chat`).
```

## Conclusão

Os 6 casos acima provam, contra o repositório real (sem fixture sintética necessária —
o corpus WDS real do Dômus já é rico o suficiente): (1) `design-artifacts` é um
Documento-tipo real e descoberto pelo mapa feature→documento; (2) a mesma fonte
canônica (nunca copiada) alimenta os três usos sem divergência; (3) o grounding embute
cenários/regras de produto reais quando existem; (4) o grounding lê `product-decisions.md`
além de scenarios; (5) a ausência de cobertura degrada graciosamente, sem fabricar
conteúdo.
