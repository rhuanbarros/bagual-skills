---
title: Catálogo de Documento-tipos da Wiki
tipo: reference
created: 2026-07-11
status: living-document
source_prd: "ideias/prd-01-wiki-ledger.md"
source_story: "ideias/sistema-artifacts/E3-1-catalogo-documento-tipos.md"
extends: "_bmad/_memory/tech-writer-sidecar/documentation-standards.md"
---

# Catálogo de Documento-tipos

## O que é este documento

Este é o **catálogo canônico de Documento-tipos** da Wiki do <PROJETO> (PRD 01, FR-3). A Wiki é o repositório único de conhecimento do projeto — uma árvore recursiva de índices — e vive em **`wiki/`**. Todo documento gravado nessa árvore pertence a exatamente um dos 13 Documento-tipos catalogados abaixo (os 12 do domínio de conhecimento do projeto + `reference`, o tipo meta/índice deste próprio catálogo — ver [§ Documento sem tipo declarado](#documento-sem-tipo-declarado)); cada tipo tem um padrão de escrita próprio (estrutura, audiência, ciclo de vida, gramática, regras de validação).

**Este catálogo é a fonte única de padrões** para:
- `bmad-index-docs` (Story E3.2) — ao gerar/validar `index.md`, valida cada documento contra o padrão do seu tipo declarado aqui.
- A **bibliotecária** (`bmad-agent-tech-writer`/Paige, Story E3.4) — ao curar a Wiki (fundir, aposentar, promover, fatiar), usa este catálogo como critério de conformidade e como referência para o mecanismo de "documento sem tipo" (ver [§ Documento sem tipo declarado](#documento-sem-tipo-declarado)).
- Qualquer skill/agente que **escreve** um novo documento de conhecimento — antes de escrever, verifica aqui a estrutura/audiência/gramática esperada do tipo pretendido, em vez de inventar um padrão ad-hoc.

**Relação com `documentation-standards.md`:** este catálogo **estende**, não substitui, `_bmad/_memory/tech-writer-sidecar/documentation-standards.md`. Aquele documento cobre convenções de formatação genéricas de documentação técnica (CommonMark, tom, estrutura de README/API-reference/Architecture-doc). Este catálogo é específico do domínio de conhecimento do projeto (decisão, regra, anti-pattern, nota-operacional, spec, ticket, design-doc, changelog, timeline) e assume as regras de formatação daquele documento como base — não as repete. Ver a decisão de integração registrada no Change Log da story E3.1.

**Terminologia:** os termos usados aqui (Documento-tipo, Entrada de Ledger, Estado, Causa da morte, Contador de utilidade, Selo de maturidade, Changelog, Timeline) são herdados **verbatim** do §3 Glossário de `ideias/prd-01-wiki-ledger.md` — não parafraseados.

## Tabela-resumo

| Documento-tipo | Audiência principal | Segue MADR (Ledger)? | Ciclo de vida |
|---|---|---|---|
| `decisão-técnica` | Agente executor / Gerente | ✅ Sim | candidata → ativa → aposentada; isenta de poda por desuso (FR-7), só morre por reversão |
| `decisão-de-produto` | Rhuan (dono) + agentes; consumida por `bagual-tickets` | ✅ Sim | candidata → ativa → aposentada; isenta de poda por desuso (FR-7), só morre por reversão |
| `decisão-de-arquitetura` | Arquiteto (`bmad-agent-architect`) / IA dev | ✅ Sim | candidata → ativa → aposentada; isenta de poda por desuso (FR-7), só morre por reversão |
| `regra` | Agente executor + enforcement automatizado (PRD 04) | ✅ Sim | candidata → ativa → aposentada; **sujeita** a poda por utilidade zero (contador incrementado pelo enforcement) |
| `padrão` | IA dev | ✅ Sim | candidata → ativa → aposentada; **isenta de poda-por-utilidade** (extensão consistente da decisão de FR-7 — sem evento de "foi consultado" instrumentado, mesmo racional de contador sempre zero que isenta `decisão-*`; morre por reversão/obsolescência, não por desuso); promovido pela bibliotecária a partir de repetição observada |
| `anti-pattern` | IA dev / enforcement (PRD 04) | ✅ Sim (ver nota¹) | candidata → ativa → aposentada, análogo ao Ledger; carrega selo de maturidade 🟢/🟡/🔴 |
| `nota-operacional` | IA dev / agente executor | ❌ Não — padrão próprio | append-only; sem estado formal candidata/ativa/aposentada |
| `spec` | IA dev (grounding em spec-time, PRD 03) | ❌ Não — padrão próprio (`bmad-spec`) | pontual; atualizada/substituída via fluxo do `bmad-spec`, não é append-only |
| `ticket` | Rhuan + agente executor | ❌ Não — padrão próprio (`bagual-tickets`) | aberto → triado → em-andamento → concluído (não é o ciclo do Ledger) |
| `design-doc` (= `design-artifacts`, PRD 05) | UX / IA dev / grounding em spec-time (Story E9.7) | ❌ Não — padrão próprio, documento-PONTEIRO (PRD 05) | pontual; atualizado conforme o design evolui; nunca copia o conteúdo canônico WDS |
| `changelog` | Cliente final | ❌ Não — padrão próprio | append-only; gerado automaticamente a partir de Tickets (FR-12), nunca escrito à mão no fluxo normal |
| `timeline` (`projects-history.md`) | IA dev | ❌ Não — padrão próprio | append-only; formato atual preservado (FR-11) |
| `reference` | Qualquer agente/skill que consulta a Wiki | ❌ Não — padrão próprio | meta/pontual; documentos de referência-índice (este catálogo, `index.md` de pasta) — isentos do carve-out de "documento sem tipo" (ver [§ Documento sem tipo declarado](#documento-sem-tipo-declarado)) |

¹ `anti-pattern` não está listado em FR-4 entre os tipos-de-Ledger explícitos (`decisão-*`, `regra`, `padrão`), mas o §3 Glossário e FR-8 (selo de maturidade) tratam anti-pattern com ciclo de vida análogo ao Ledger. Este catálogo resolve a ambiguidade explicitamente: **`anti-pattern` segue a gramática do Ledger** (mais próximo de `regra`/`padrão` que de `nota-operacional`), com uma extensão própria — o selo de maturidade — que os demais tipos-de-Ledger não têm. Ver detalhe na entrada de `anti-pattern` abaixo.

---

## Entradas de Ledger — tipos que seguem a gramática MADR

Os seis tipos abaixo (os cinco tipos-de-Ledger de FR-4 — `decisão-técnica`, `decisão-de-produto`, `decisão-de-arquitetura`, `regra`, `padrão` — mais `anti-pattern`, ver nota¹) são **Entradas de Ledger** (PRD 01 §3): seguem a gramática única definida em FR-6 —

```
contexto → decisão → alternativas mortas (com causa) → consequências → estado → contador-de-utilidade
```

Front-matter mínimo comum a toda Entrada de Ledger:

```yaml
---
tipo: decisão-técnica   # um dos: decisão-técnica | decisão-de-produto | decisão-de-arquitetura | regra | padrão | anti-pattern
estado: ativa            # candidata | ativa | aposentada
causa-da-morte: null      # obrigatório (string) quando estado == aposentada; null/ausente caso contrário
contador-de-utilidade: 0  # inteiro; regra/anti-pattern: incrementado pelo enforcement (PRD 04); decisão-*: isenta de poda-por-utilidade (FR-7 — sem evento "foi consultada" instrumentado); padrão: isenta pelo mesmo racional, por extensão consistente de FR-7 (o PRD não cita `padrão` — ver nota na entrada `padrão` abaixo)
areas: []                  # tags de feature/área (FR-2, formalizado na Story E3.3 — ver `retrieval-guide.md` para a convenção completa de multi-área e o algoritmo de retrieval)
---
```

### `decisão-técnica`

- **Estrutura:** front-matter comum de Ledger + corpo em 4 seções nomeadas: `## Contexto`, `## Decisão`, `## Alternativas consideradas e rejeitadas` (cada uma com `rejeitada porque…`), `## Consequências`. Estilo de referência real já em uso: `.claude/skills/bagual-tickets/.decision-log.md` ("Considered and rejected: (a)… rejected because…").
- **Audiência:** agente executor (IA dev) implementando trabalho relacionado; o Gerente ao decidir se uma abordagem já foi tentada.
- **Ciclo de vida:** `candidata → ativa → aposentada` (FR-5). **Isenta da poda-por-utilidade** (FR-7, endurecido) — decisões técnicas não têm evento de "foi consultada" instrumentado, então seu contador ficaria sempre zero; a bibliotecária nunca propõe aposentar uma `decisão-técnica` por baixa utilidade, só por **reversão explícita** (nova decisão que a substitui, linkada).
- **Gramática:** MADR completa (ver bloco acima).
- **Regras de validação:** (a) front-matter tem `tipo`, `estado`, `contador-de-utilidade`; (b) se `estado: aposentada`, `causa-da-morte` é obrigatório e não-vazio; (c) toda reversão cria uma nova entrada com link explícito para a entrada original — nunca uma entrada solta desconectada da anterior; (d) a bibliotecária **nunca** lista esta entrada como candidata a aposentar por utilidade zero (checagem de exceção FR-7).

### `decisão-de-produto`

- **Estrutura:** idêntica à de `decisão-técnica` (front-matter comum + Contexto/Decisão/Alternativas/Consequências). Continua legível pelo fluxo de checagem de produto do `bagual-tickets` (FR-4, consequência testável: "uma `decisão-de-produto` continua legível pela `bagual-tickets` na sua checagem de produto").
- **Audiência:** Rhuan (dono do produto) primariamente; agentes (em especial `bagual-tickets` na checagem de conflito com decisão de produto registrada, e `bmad-correct-course`) secundariamente.
- **Ciclo de vida:** igual a `decisão-técnica` — `candidata → ativa → aposentada`, isenta de poda por desuso (FR-7), só morre por reversão explícita com decisão substituta linkada.
- **Gramática:** MADR completa.
- **Regras de validação:** as mesmas (a)-(d) de `decisão-técnica`, mais: (e) o campo `tipo: decisão-de-produto` precisa continuar parseável pelo fluxo hoje informal do `bagual-tickets` (não quebrar essa integração ao migrar `product-decisions.md`, Story E3.6/E4.6).

### `decisão-de-arquitetura`

- **Estrutura:** idêntica à de `decisão-técnica` (front-matter comum + Contexto/Decisão/Alternativas/Consequências).
- **Audiência:** arquiteto (`bmad-agent-architect`/Winston) e IA dev implementando sobre a arquitetura decidida.
- **Ciclo de vida:** igual a `decisão-técnica` — `candidata → ativa → aposentada`, isenta de poda por desuso (FR-7), só morre por reversão explícita.
- **Gramática:** MADR completa.
- **Regras de validação:** as mesmas (a)-(d) de `decisão-técnica`.

### `regra` (candidata a enforcement)

- **Estrutura:** front-matter comum de Ledger + `## Contexto` (o que motivou a regra) + `## Decisão` (a regra em si, formulada de forma acionável/verificável) + `## Alternativas consideradas e rejeitadas` + `## Consequências` + `## Enforcement` (como a regra é/seria verificada — manual hoje, Semgrep candidato via selo, PRD 04).
- **Audiência:** agente executor (segue a regra ao implementar) e a máquina de enforcement (PRD 04, quando aplicável).
- **Ciclo de vida:** `candidata → ativa → aposentada` (FR-5). **Ao contrário de `decisão-*` e `padrão` (ambos isentos, ver suas entradas), é sujeita à poda-por-utilidade** (FR-7): o enforcement do PRD 04 incrementa `contador-de-utilidade` quando a regra barra um problema real; uma `regra` com utilidade persistentemente zero é candidata a aposentar. `regra` é o **único** tipo-de-Ledger com evento de "foi consultada/aplicada" de fato instrumentado — daí ser o único sujeito à poda.
- **Gramática:** MADR completa, com a seção extra `## Enforcement`.
- **Regras de validação:** (a)-(c) de `decisão-técnica`; mais (d) uma `regra` com `contador-de-utilidade` zero por um período de curadoria é sinalizada como candidata a aposentar (proposal-only, FR-9 endurecido — a bibliotecária **propõe**, não executa a aposentadoria sozinha).

### `padrão` (a consolidar)

- **Estrutura:** front-matter comum de Ledger + `## Contexto` (onde o padrão foi observado repetir) + `## Decisão` (o padrão consolidado, com exemplo de código/estrutura) + `## Alternativas consideradas e rejeitadas` + `## Consequências`.
- **Audiência:** IA dev implementando algo semelhante no futuro.
- **Ciclo de vida:** `candidata → ativa → aposentada` (FR-5). Normalmente nasce `candidata` quando a bibliotecária observa repetição (FR-9, "promover padrões repetidos") e é promovida a `ativa` — a promoção em si é uma operação **não-destrutiva** e pode rodar autônoma na curadoria noturna; fundir/aposentar um `padrão` já existente é destrutivo e cai na regra proposal-only (FR-9 endurecido).
- **Poda-por-utilidade:** **isenta**, assim como `decisão-*`. **Decisão do oráculo (iteração 2 deste review):** o FR-7 do PRD 01 instrumenta o contador só para `regra` (o enforcement do PRD 04 incrementa quando a regra barra um problema real) e isenta explicitamente só `decisão-*` da poda — o PRD **não menciona `padrão`**. Esta entrada resolve a lacuna: `padrão`, assim como `decisão-*`, não tem nenhum evento de "foi consultado/reaproveitado" instrumentado, então seu `contador-de-utilidade` ficaria permanentemente zero pelo mesmo motivo que motivou a isenção de `decisão-*` em FR-7 — aplicar a poda-por-utilidade a `padrão` proporia aposentar todo padrão consolidado por "desuso" nunca real. Isto é uma **extensão consistente** da decisão de FR-7 aplicada a `padrão` por analogia direta — não uma citação literal de FR-7, que não cobre este tipo. Um `padrão` morre por **reversão/obsolescência** (nova prática que o substitui, com causa registrada), nunca por contador zero.
- **Gramática:** MADR completa.
- **Regras de validação:** as mesmas (a)-(c) de `decisão-técnica`; mais (d) a bibliotecária **nunca** lista um `padrão` como candidato a aposentar por utilidade zero (mesma checagem de exceção FR-7 aplicada a `decisão-técnica`, por extensão).

### `anti-pattern`

- **Estrutura:** front-matter comum de Ledger **+ campo extra `selo: 🟢`** (um de `🟢`/`🟡`/`🔴`, FR-8 — significado herdado verbatim do §3: `🟢` automatizável mecanicamente (AST-decidível), `🟡` híbrido, `🔴` só-humano) + `## Contexto` (onde o anti-pattern apareceu) + `## Decisão` (o que é o anti-pattern e o que fazer em vez dele) + `## Alternativas consideradas e rejeitadas` (se aplicável) + `## Consequências`.
- **Audiência:** IA dev (evita repetir o anti-pattern) e a máquina de enforcement (PRD 04 — deriva candidatos a regra Semgrep do filtro `🟢 ∧ ¬automatizado`).
- **Ciclo de vida:** `candidata → ativa → aposentada`, análogo ao Ledger — mas com uma leitura própria por causa do selo: uma entrada 🟢 já coberta por ferramenta nativa (ESLint/pyright) recebe `causa-da-morte: "redundante com ferramenta nativa"` e sai da fila de candidatos a Semgrep, mesmo continuando catalogada como conhecimento (aposentada ≠ apagada).
- **Gramática:** segue a gramática do Ledger (ver nota¹ na tabela-resumo) — **decisão explícita desta story**, já que o PRD não resolve a ambiguidade FR-4 vs. §3/FR-8 de forma unívoca. `anti-pattern` não é `nota-operacional`: tem estado com transições e causa-da-morte, o que uma nota não tem.
- **Regras de validação:** (a)-(c) de `decisão-técnica`; mais (d) toda entrada tem `selo` preenchido com um dos 3 valores; (e) a lista de candidatos a regra Semgrep é **derivada** por query sobre `selo: 🟢` + `estado != aposentada` + ainda não automatizado — nunca uma lista mantida à mão em paralelo (FR-8).

---

## Documento-tipos com padrão próprio (não seguem MADR)

Os sete tipos abaixo (os seis de conhecimento do projeto — `nota-operacional`, `spec`, `ticket`, `design-doc`, `changelog`, `timeline` — mais `reference`, o tipo meta/índice adicionado na iteração 2 deste review para cobrir documentos como este próprio catálogo) **não** são Entradas de Ledger — não têm "alternativas mortas" nem o ciclo `candidata → ativa → aposentada` do Ledger (FR-6, endurecido F26). Forçar a gramática MADR neles produziria campos-ritual vazios ("alternativas mortas: nenhuma") e ruído de checagem perpétuo.

### `nota-operacional`

- **Estrutura:** título curto descrevendo o gotcha/observação + corpo livre (1 a poucos parágrafos) descrevendo o comportamento do sistema, a interação entre partes, ou o gotcha operacional aprendido. Sem seções obrigatórias tipo MADR. Front-matter mínimo: `tipo: nota-operacional`, `areas: [...]` — convenção formalizada na Story E3.3 (ver [`retrieval-guide.md`](./retrieval-guide.md)): toda `nota-operacional` declara **todas** as áreas que toca, não uma única.
- **Audiência:** agente executor / IA dev em sessões futuras que tocam a mesma área.
- **Ciclo de vida:** **append-only** — é o formato herdado de `notes.md` hoje (295 KB, o mais urgente de explodir por área na migração §6.3 do PRD). Sem estado formal `candidata/ativa/aposentada`; a bibliotecária pode fatiar (documento grande demais) ou fundir notas duplicadas (operação destrutiva → proposal-only, FR-9), mas não "aposenta com causa" no sentido do Ledger.
- **Gramática:** padrão próprio, sem MADR.
- **Regras de validação:** (a) `tipo: nota-operacional` presente no front-matter; (b) não tem `estado`/`causa-da-morte` (se presentes, é sinal de confusão de tipo — a bibliotecária sinaliza para reclassificação).

### `spec`

- **Estrutura:** própria do fluxo `bmad-spec` (kernel + companions) — este catálogo não recria essa estrutura interna, só reconhece `spec` como um Documento-tipo de primeira classe da Wiki quando um SPEC kernel é gravado nela. Front-matter mínimo: `tipo: spec`.
- **Audiência:** IA dev, especialmente no grounding em spec-time (PRD 03, que **lê** a Wiki/Ledger para injetar padrões nas specs).
- **Ciclo de vida:** **pontual** — reflete o estado de uma feature/mudança no momento em que foi escrita; é atualizada/substituída via o próprio fluxo `bmad-spec update`, não é append-only nem tem estado Ledger.
- **Gramática:** padrão próprio (definido por `bmad-spec`), sem MADR.
- **Regras de validação:** (a) `tipo: spec` presente; (b) uma spec desatualizada em relação ao código correspondente é sinal de gap de curadoria (fora do escopo desta story detalhar a mecânica de detecção).

### `ticket`

- **Estrutura:** própria de `bagual-tickets` (`.claude/skills/bagual-tickets/SKILL.md` § Armazenamento) — front-matter (`id`, `title`, `status`, `priority`, `category`, `area`, `expanded`, `created`, `updated`, `origem`, `visivel_pro_cliente`, `trilha`, `ledger_refs`) + corpo em seções nomeadas (`## Descrição`, `## Verificação`, `## Locais afetados`, `## Checagem de decisão de produto`, `## Fechamento`, `## Log`). **Formalização completa entregue pela Story E5.5** (schema real dos campos aditivos de E5.2-E5.4, antecipados aqui desde a Story E5.5 nesta iteração de review).
- **Audiência:** Rhuan (relator/priorizador) e agente executor (resolve o ticket).
- **Ciclo de vida:** `novo → precisa-de-info → triado → pronto-para-implementar → em-implementacao → concluido | duplicado | descartado` — um ciclo de estado próprio de gestão de trabalho (nomes exatos usados pela skill; preservados verbatim), **não** o ciclo `candidata/ativa/aposentada` do Ledger; não tem "causa da morte" nem "alternativas mortas".
- **Gramática:** padrão próprio (`bagual-tickets`), sem MADR.
- **`board.yaml` como índice nativo do subtree (FR-7).** `project_controll/tickets/board.yaml` é referenciado diretamente pelo índice-raiz da Wiki (`wiki/index.md`) — sem `index.md` paralelo duplicando a mesma informação (status/prioridade/área). Os `.md` por-ticket são a fonte de verdade; `board.yaml` é reconstruível a partir deles (`project_controll/tickets/scripts/rebuild_board.py`, stdlib) — corromper o índice nunca é fatal. `project_controll/tickets/` continua sendo o único local físico (fora de `wiki/`, decisão já tomada).
- **Regras de validação:** (a) `tipo: ticket` reconhecido implicitamente pelo padrão de nome `TCK-*.md` dentro de `project_controll/tickets/` (a skill não grava `tipo: ticket` no front-matter — o reconhecimento é por localização/convenção de arquivo, não por chave `tipo`, mesmo carve-out estrutural de `index.md`/`reference` da seção [§ Documento sem tipo declarado](#documento-sem-tipo-declarado)); (b) um ticket `concluido` com `visivel_pro_cliente: true` deve gerar exatamente uma entrada de `changelog` (FR-12) — checagem de consistência entre os dois tipos, feita por `wiki/scripts/generate_changelog.py` (E4.7); (c) um ticket `concluido` por mudança de código sem `## Fechamento` preenchida é um sinal a checar pela bibliotecária nas suas varreduras (FR-8), não um erro automático (o campo não é obrigatório, ver E5.4); (d) `visivel_pro_cliente: pendente` nunca é resolvido pela bibliotecária sozinha — é sempre escalado (E4.7 § `curation-guide.md`).

### `design-doc` (= `design-artifacts` do PRD 05 — detalhado pela Story E3.1/E9.7)

**Nomenclatura:** o PRD 05 (§3 Glossário, FR-3/FR-4) usa o termo `design-artifacts` para os documentos canônicos que o WDS mantém (trigger map, cenários UX/Coverage Matrix). Este catálogo reserva o **slug de Wiki** `design-doc` para esse mesmo conceito (já registrado como stub pela Story E3.1, antes do PRD 05 existir) — não introduz um 14º slug canônico. `design-artifacts` é o nome do *conceito de produto*; `design-doc` é o *Documento-tipo da Wiki* que o representa. Ambos os termos aparecem lado a lado na literatura do projeto; tratar como sinônimos.

- **Estrutura — documento-PONTEIRO, nunca cópia de conteúdo (regra central, F-E9.7):** um documento `design-doc` na Wiki **não contém** o cenário/trigger-map/regra em si — ele é um front-matter + um corpo curto que **referencia** a fonte canônica WDS por caminho relativo. A fonte canônica permanece fora da árvore da Wiki, nos locais que o `bagual-qa-builder` já lê (PRD 05 §1 "uma fonte, três usos"):
  - `_bmad-output/C-UX-Scenarios/00-ux-scenarios.md` (Scenario Summary + Page Coverage Matrix) e as pastas `NN-slug/NN-slug.md` com o outline completo de cada cenário.
  - `_bmad-output/B-Trigger-Map/trigger-map.md` (trigger map canônico — personas, forças, objetivos).
  - `_bmad-output/B-Trigger-Map/focused-trigger-map.md` e `_bmad-output/evolution/scenarios/*.md` — o tree paralelo que `wds-8-product-evolution` grava (PRD 05 §4.2, "furo wds-8→QA"; a correção do lado do `bagual-qa-builder`, FR-2, já está `done` desde a Epic E1 — o builder lê `evolution/scenarios/` + `focused-trigger-map.md` como fontes suplementares. Desde a Story E16.3 (T3.2 + T3.4, 2026-07-12), `focused-trigger-map.md` **existe de fato** (conteúdo real derivado dos 4 cenários de evolução) e a Coverage Matrix canônica **também** ganhou um write-back idempotente e aditivo (`00-ux-scenarios.md` § "Evolution-sourced additions", via `wiki/scripts/reconcile_evolution_coverage.py`, invocado por `wds-8-product-evolution` (via i, reformulado 2026-07-12 — ver `_bmad/custom/wds-8-product-evolution.toml`) — nunca reescreve os 5 cenários hand-authored; `bagual-qa-builder` permanece read-only da fonte canônica, ver `_bmad/custom/bagual-qa-builder.toml`). Um documento `design-doc` só referencia um caminho quando ele existir de fato; nunca fabricar o ponteiro para um arquivo ausente.
  Front-matter mínimo:
  ```yaml
  ---
  tipo: design-doc
  areas: [proposals, clients]   # convenção de retrieval-guide.md §1 — lista, não valor único
  canonical:                     # caminho(s) relativo(s) da fonte canônica WDS (NUNCA copiada aqui)
    - "_bmad-output/C-UX-Scenarios/00-ux-scenarios.md#01-..."
  ---
  ```
  O corpo é um resumo curto e estável (persona, páginas/fluxo tocados, user/business value, ou o `Target`/`Desired State` de um cenário de evolução) — o suficiente para o grounding decidir relevância e localizar a seção certa da fonte canônica; **nunca** o texto integral do cenário (isso seria a cópia divergente que este Documento-tipo existe para evitar).
- **Localização física na árvore da Wiki:** `wiki/design-artifacts/` (pasta introduzida pela Story E9.7; ver `index.md` daquela pasta para o índice completo). Documentos reais registrados nesta story: 5 ponteiros para os cenários canônicos (`00-ux-scenarios.md`), 1 ponteiro para o `trigger-map.md`, e 4 ponteiros para cenários de evolução (`evolution/scenarios/*.md`) — cuja correção mecânica do lado do `qa-builder` (FR-2) era `done` desde a Epic E1 (grounding, terceiro uso, já os enxergava via este Documento-tipo desde E9.7) e cuja reflexão na Coverage Matrix canônica (o furo PRD 05 §4.2/T3.4 então residual) foi fechada pela Story E16.3 (write-back idempotente e aditivo em `00-ux-scenarios.md` § "Evolution-sourced additions").
- **Audiência:** UX (`bmad-agent-ux-designer`/Sally, WDS Freya) e IA dev implementando a partir do design — em particular o grounding em spec-time (PRD 03 FR-9/Story E6.1), que é o **terceiro uso** da fonte WDS (PRD 05 FR-4, Story E9.7): ao criar o spec de uma story que toca uma área com `design-doc`, o procedimento de grounding segue o ponteiro, lê a fonte canônica, e embute o resumo relevante nas Dev Notes.
- **Ciclo de vida:** **pontual** — atualizado quando o cenário/trigger-map canônico muda (o ponteiro é reescrito só se o `canonical:`/resumo ficar desatualizado; a fonte em si evolui pelo fluxo `wds-8`/Fase 2-4 do WDS, fora deste Documento-tipo). Não é append-only nem segue o ciclo `candidata/ativa/aposentada` do Ledger.
- **Gramática:** padrão próprio (ponteiro + resumo curado), sem MADR.
- **Regras de validação:** (a) `tipo: design-doc` presente; (b) `areas:` presente e não-vazia (mesma regra de gap de curadoria de `retrieval-guide.md` §1 — um `design-doc` sem área é invisível ao mapa feature→documento por construção); (c) todo caminho listado em `canonical:` deve apontar para um arquivo que **existe** no momento da escrita — nunca referenciar um artefato WDS ainda não produzido (ex.: `focused-trigger-map.md` antes de existir); (d) o corpo não deve conter a reprodução integral de uma seção com múltiplos parágrafos da fonte canônica — sinal de cópia divergente, não resumo.

### `changelog`

- **Estrutura:** lista append-only de entradas em **linguagem de usuário** (não jargão técnico), cada entrada derivada de exatamente um Ticket `concluído + visível-pro-cliente` (FR-12). Front-matter mínimo: `tipo: changelog`.
- **Audiência:** **cliente final** — é o único Documento-tipo deste catálogo voltado a audiência externa ao time/agentes.
- **Ciclo de vida:** append-only; **gerado automaticamente**, nunca escrito à mão no fluxo normal (FR-12, consequência testável).
- **Gramática:** padrão próprio (linguagem de usuário, sem jargão), sem MADR — não tem contexto/alternativas/estado.
- **Regras de validação:** (a) toda entrada de changelog rastreia o Ticket de origem; (b) um Ticket concluído com a flag e **sem** entrada de changelog correspondente é um gap sinalizável; (c) uma entrada de changelog escrita manualmente (sem Ticket de origem rastreável) é sinal de desvio do fluxo (FR-12).

### `timeline` (`projects-history.md`)

- **Estrutura:** a já existente em `projects-history.md` — preservada **sem mudança de formato** (FR-11): entradas append-only de conclusão de story/epic, formato atual do arquivo.
- **Audiência:** IA dev (histórico técnico do que já foi implementado).
- **Ciclo de vida:** append-only; formalizado como Documento-tipo `timeline` da Wiki na Story E4.6, mas o formato de escrita não muda aqui.
- **Gramática:** padrão próprio (o formato já em uso em `projects-history.md`), sem MADR.
- **Regras de validação:** (a) `tipo: timeline` reconhecido quando o arquivo for migrado para dentro da árvore da Wiki (Story E4.6); até lá, é consultado pelo caminho atual (`backend/projects-history.md`, `frontend/projects-history.md`, `_bmad-output/projects-history.md`) sem exigir front-matter retroativo.

### `reference`

- **Estrutura:** front-matter mínimo `tipo: reference` + conteúdo livre orientado a servir de meta-conhecimento — referência ou índice sobre a própria Wiki/o próprio conhecimento do projeto, não conhecimento de domínio em si. Exemplos: este catálogo (`document-types.md`), um `index.md` de pasta da Wiki, um futuro guia de convenções da árvore. Sem seções obrigatórias tipo MADR.
- **Audiência:** qualquer agente/skill que consulta a Wiki como fonte de padrão ou navegação (`bmad-index-docs`, a bibliotecária, qualquer skill que "desce a árvore") — não é audiência de conhecimento de feature, é meta-audiência de "como a Wiki está organizada".
- **Ciclo de vida:** vive enquanto a estrutura/documento que referencia existir; atualizado conforme a própria Wiki evolui (não é append-only nem segue o ciclo `candidata/ativa/aposentada` do Ledger).
- **Gramática:** padrão próprio, sem MADR.
- **Regras de validação:** (a) `tipo: reference` presente quando o documento carrega front-matter (ex.: este catálogo); (b) `index.md` de pasta é reconhecido como `reference` mesmo quando gerado sem front-matter explícito — ver o carve-out em [§ Documento sem tipo declarado](#documento-sem-tipo-declarado), que isenta índices e este catálogo de serem sinalizados por "sem tipo" mesmo sem a chave presente.

**Adicionado na iteração 2 deste review (2026-07-11):** o critério original de "documento sem tipo" (ver seção abaixo) auto-sinalizaria o próprio catálogo e os `index.md` da Wiki, que são estruturalmente meta-documentos, não conhecimento de domínio. `reference` formaliza esse tipo de primeira classe em vez de deixar um buraco no catálogo que ele mesmo preencheria com um falso-positivo.

---

## Documento sem tipo declarado

Critério de "sem tipo" que a bibliotecária (e qualquer validação futura de `bmad-index-docs`) usa para sinalizar um documento:

1. O documento não tem front-matter YAML, **ou**
2. O front-matter existe mas não tem a chave `tipo`, **ou**
3. A chave `tipo` existe mas seu valor **não é exatamente um** dos 13 slugs canônicos desta tabela-resumo (`decisão-técnica`, `decisão-de-produto`, `decisão-de-arquitetura`, `regra`, `padrão`, `anti-pattern`, `nota-operacional`, `spec`, `ticket`, `design-doc`, `changelog`, `timeline`, `reference`) — inclui erros de grafia, sinônimos não-canônicos, ou valores em outro idioma/formato.

**Carve-out explícito (documentos meta/índice/legado — adicionado na iteração 2 deste review, 2026-07-11):** os três critérios acima aplicam-se a **documentos de conteúdo comum** da Wiki (Entradas de Ledger e os demais tipos de conhecimento de domínio). As categorias abaixo são **estruturalmente diferentes** e **não** são sinalizadas por falta de front-matter/`tipo`, mesmo que não declarem a chave:

- **Arquivos de índice** (`index.md`, em qualquer pasta da Wiki) — são meta-navegação gerada/curada (`bmad-index-docs`, Story E3.2), não conhecimento de projeto; reconhecidos implicitamente como `reference` pelo próprio nome do arquivo, sem exigir front-matter.
- **Este catálogo** (`document-types.md`) — carrega `tipo: reference` no front-matter (ver topo deste documento), mas mesmo que uma edição futura remova a chave, não é sinalizado: é a fonte da checagem, não seu alvo.
- **Docs de tipos append-only já isentos de front-matter retroativo** — hoje só `timeline`/`projects-history.md` (a própria entrada `timeline` acima já isenta esse arquivo de exigir front-matter até a migração da Story E4.6); não seria coerente isentar o requisito ali e sinalizar o mesmo arquivo por este critério aqui.

Fora desse carve-out, todo documento de conteúdo comum (`decisão-*`, `regra`, `padrão`, `anti-pattern`, `nota-operacional`, `spec`, `ticket`, `design-doc`, `changelog`) segue os três critérios normalmente — o carve-out não isenta conhecimento de domínio, só meta-documentos e o legado já explicitamente isento em sua própria entrada.

Um documento sinalizado por qualquer um dos três critérios (fora do carve-out acima) entra no relatório de gaps de curadoria (o mesmo relatório de FR-2 para documentos sem metadado de área) até que alguém (a bibliotecária, proposta; ou o dono, na ratificação) atribua um `tipo` válido. **A mecânica de execução dessa checagem** (script/rotina rodando de fato dentro de `bmad-index-docs`/da bibliotecária) é implementada nas Stories E3.2/E3.4 — este catálogo define apenas o **critério**, para que essas stories tenham contra o que implementar.

## Escopo desta story vs. próximas

Fora do escopo deste catálogo (ver Dev Notes da story E3.1 para o detalhamento completo):
- Front-matter YAML parseável e schema de campos do Ledger como *implementação* rodando (script) — Story E4.1, formalizado em [`ledger/README.md`](./ledger/README.md) + [`ledger/template-entrada.md`](./ledger/template-entrada.md) + [`ledger/scripts/validate_ledger.py`](./ledger/scripts/validate_ledger.py). Ciclo de vida com causa-da-morte e reversão linkada — Story E4.2, script [`ledger/scripts/transition_ledger_entry.py`](./ledger/scripts/transition_ledger_entry.py). Contador de utilidade com isenção de decisão-*/padrão — Story E4.3 (mecanizado no relatório `poda_candidatos`/`isentos_baixa_utilidade` do próprio `validate_ledger.py`). Selo de maturidade + derivação de candidatos a Semgrep — Story E4.4, [`ledger/scripts/query_semgrep_candidates.py`](./ledger/scripts/query_semgrep_candidates.py). 3 entradas reais migradas como exemplo em `ledger/decisao-tecnica/`, `ledger/regra/`, `ledger/anti-pattern/` (fontes originais preservadas intactas).
- Integração real de `bmad-index-docs` validando documentos contra este catálogo — Story E3.2.
- A bibliotecária validando documentos contra o catálogo em produção — Story E3.4, formalizado em [`curation-guide.md`](./curation-guide.md) + [`scripts/validate_wiki_docs.py`](./scripts/validate_wiki_docs.py).
- O gate mecânico de completude que todo fatiamento de monólito deve passar antes do cutover (cobertura H2 1:1 + checksum/diff textual + read-through até o recall SM-5 passar) — Story E3.5, formalizado em [`scripts/slice_completeness_gate.py`](./scripts/slice_completeness_gate.py).
- Migração dos monólitos existentes (`anti-patterns.md`, `decisions.md`, `notes.md`, `product-decisions.md`, `projects-history.md`) para os novos tipos, usando o gate acima antes de cada cutover-por-arquivo — Story E3.6/E4.6/E12.1-E12.6. **Status (E3.6):** a máquina (`scripts/slice_monolith.py`) e um piloto parcial existiram — 3/219 `## H2` de `notes.md` fatiados em `nota-operacional` na pasta de staging não-canônica `scripts/../_migration-staging/notes/`, gate E3.5 PASS nesse subconjunto; `projects-history.md` reconhecido como `timeline` por ponteiro (`timeline.md`), sem cópia/fatiamento. **Status (E12.1, `ideias/sistema-artifacts/E12-1-fatiar-notes.md`):** o piloto foi superado pelo fatiamento COMPLETO — os 250 `## H2` reais de `notes.md` no momento do 1º fatiamento (a seção cresceu de 219 para 250 entre E3.6 e E12.1; o total FINAL entregue é 251 — a 251ª é a própria seção RULE ZERO desta story, harmonizada numa 2ª passada, ver `E12-1-fatiar-notes.md`) foram fatiados em `nota-operacional` na árvore OFICIAL (`wiki/nota-operacional/`, fora de `_migration-staging/`), cada um com `areas:` real (julgamento curatorial, zero gaps), gate E3.5 PASS 251/251 (estado final) contra `notes.md` inteiro, `notes.md` byte-a-byte idêntico antes/depois. Ainda **não indexada** (Story E12.5) nem **cutover** (Story E12.6, owner-gated — `area-cutover-status.json` permanece 100% `monolito`). **Status (E12.2, `ideias/sistema-artifacts/E12-2-decisions-madr.md`):** `decisions.md` (117 `## H2` reais, não os ~103 estimados no epic) migrado 117/117 para `ledger/decisao-tecnica/` (108) e `ledger/decisao-de-arquitetura/` (9, pasta nova), cada seção reescrita em gramática MADR completa preservando o texto original **verbatim** dentro de `## Contexto` (garantia mecânica de zero perda sob a restruturação — `## Decisão`/`## Alternativas`/`## Consequências` extraem sub-parágrafos rotulados do próprio texto original, nunca parafraseiam), gate E3.5 PASS 117/117 sem nenhuma modificação ao gate (ver Dev Notes da story para como a restruturação MADR convive com um gate desenhado para fatiamento quase-verbatim), `validate_ledger.py` 0 violações, `decisions.md` byte-a-byte idêntico antes/depois. 5 entradas com `tipo_ratificacao_pendente: true` (fronteira técnica/arquitetura, sinal para ratificação humana). **Status (E12.3, `ideias/sistema-artifacts/E12-3-antipatterns-madr.md`):** `anti-patterns.md` (92 `## H2` reais, não os ~85 estimados no epic) migrado 92/92 para `ledger/anti-pattern/`, cada seção reescrita em gramática MADR completa reusando a mesma técnica de bloco verbatim de E12.2 (`## Decisão` extrai `**Como evitar:**`, `## Consequências` extrai `**Risco:**`), gate E3.5 PASS 92/92 sem nenhuma modificação ao gate, `validate_ledger.py` 0 violações, `anti-patterns.md` byte-a-byte idêntico antes/depois. Cada entrada recebe `selo: 🟢/🟡/🔴` (E4.4) com racional individual registrado no corpo (`## Selo de maturidade`) — nunca 🟡 por omissão; distribuição real: 15 🟢, 45 🟡, 32 🔴. Achado real (não corrigido, curadoria futura): 5/92 seções duplicam conceitualmente uma entrada `anti-pattern` pré-existente emitida via `on_complete` por uma story anterior (mesmo slugs distintos, mesma lição) — ver Dev Notes da story. **Status (E12.4, `ideias/sistema-artifacts/E12-4-product-decisions-madr.md`):** `product-decisions.md` (49 `## H2` reais, número igual ao estimado no epic) migrado 49/49 para `ledger/decisao-de-produto/` (pasta nova — antes só um slug reservado no schema E4.1, sem nenhuma entrada real), cada seção reescrita em gramática MADR completa reusando a mesma técnica de bloco verbatim de E12.2/E12.3 (`## Decisão` extrai `**Comportamento:**`/`**Decisão (stakeholder...):**`, `## Alternativas` extrai texto marcado `SUPERSEDE`/`REJEITADO`/`wontfix`/revertido). O par `**Cuidado:**`/`**A revisitar:**` (proto-estado já presente no monólito, crux desta story) foi mapeado semanticamente para `## Consequências` em subseções próprias, preservado sem perda; a única seção com `**A revisitar:**` recebeu `revisitar-pendente: true` no front-matter (metadado de proveniência, fora do enum oficial `estado`). Gate E3.5 PASS 49/49 sem nenhuma modificação ao gate, `validate_ledger.py` 0 violações nas 303 entradas da árvore, `product-decisions.md` byte-a-byte idêntico antes/depois. `bagual-tickets` (checagem de decisão de produto) continua lendo o monólito diretamente, sem quebra. Com E12.4 concluída, os 4 monólitos-alvo de FR-4..FR-8 (`decisions.md`/`anti-patterns.md`/`notes.md`/`product-decisions.md`) estão todos migrados para a árvore oficial da Wiki/Ledger — `projects-history.md` continua coberto só por ponteiro `timeline` (E3.6), sem cópia/fatiamento (não é um monólito prosa-append-only do mesmo tipo). Índice recursivo (E12.5) e cutover real (E12.6, owner-gated) permanecem pendentes para os 4.
- A Ficha de Build (PRD 03 FR-11b, Story E6.4) — convenção separada de metadado estrutural, não confundir com este catálogo.
