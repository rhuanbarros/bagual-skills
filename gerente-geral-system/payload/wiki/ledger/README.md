---
title: Ledger — schema, gramática MADR e ciclo de vida
tipo: reference
created: 2026-07-11
status: living-document
source_prd: "ideias/prd-01-wiki-ledger.md"
source_epic: "ideias/epics.md — Epic E4"
source_stories:
  - "ideias/sistema-artifacts/E4-1-schema-gramatica-madr.md"
  - "ideias/sistema-artifacts/E4-2-ciclo-vida-causa-morte.md"
  - "ideias/sistema-artifacts/E4-3-contador-utilidade.md"
  - "ideias/sistema-artifacts/E4-4-selo-maturidade.md"
extends: "wiki/document-types.md"
---

# Ledger — schema, gramática MADR e ciclo de vida

## O que é este documento

Este é o **spec canônico do Ledger** (PRD 01 §4.2, Epic E4): o front-matter YAML, a
gramática MADR, a máquina de estados com causa-da-morte, o contador de utilidade e o
selo de maturidade que toda **Entrada de Ledger** carrega. Não recria o catálogo geral
de Documento-tipos da Wiki (isso é [`document-types.md`](../document-types.md), Story
E3.1) — **estende** especificamente a seção "Entradas de Ledger — tipos que seguem a
gramática MADR" daquele catálogo com o schema *implementado* (front-matter parseável +
scripts de validação/query), que ali estava explicitamente marcado como fora de escopo
("Front-matter YAML parseável e schema de campos do Ledger como *implementação* rodando
(script) — Story E4.1").

**Escopo: só Entradas de Ledger.** A gramática MADR descrita aqui aplica-se **apenas**
aos 6 tipos-de-Ledger — `decisão-técnica`, `decisão-de-produto`, `decisão-de-arquitetura`,
`regra`, `padrão`, `anti-pattern` — nunca aos outros 7 Documento-tipos da Wiki
(`nota-operacional`, `spec`, `ticket`, `design-doc`, `changelog`, `timeline`,
`reference`), que seguem seu próprio padrão (FR-6, endurecido F26). Forçar MADR neles
produz campos-ritual vazios; o script de validação (`scripts/validate_ledger.py`) reflete
essa exceção mecanicamente — ver §5.

## 1. Front-matter canônico de uma Entrada de Ledger

```yaml
---
tipo: decisão-técnica        # decisão-técnica | decisão-de-produto | decisão-de-arquitetura
                              # | regra | padrão | anti-pattern
estado: ativa                 # candidata | ativa | aposentada
causa-da-morte: null          # obrigatória (string não-vazia) quando estado == aposentada;
                               # null/ausente em qualquer outro estado
contador-de-utilidade: 0      # inteiro >= 0; ver §3 (incremento e isenção por tipo)
areas: []                     # tags de feature/área (FR-2/E3.3) — multi-área, não 1:feature
reverte: null                 # path relativo (dentro da árvore do Ledger) para a entrada
                               # original, SÓ quando esta entrada nasce de uma reversão — ver §2.3
created: 2026-07-11            # data de criação (YYYY-MM-DD)
updated: 2026-07-11            # data da última transição de estado (YYYY-MM-DD)
---
```

Campo extra, só para `anti-pattern` (FR-8):

```yaml
selo: 🟢                # 🟢 automatizável mecanicamente | 🟡 híbrido | 🔴 só-humano
automatizado: false      # true quando uma regra Semgrep já foi autorada para este anti-pattern
                          # (PRD 04/E7) — o ÚNICO jeito de sair da fila de candidatos SEM aposentar
                          # a entrada; ver §4
```

**Por que `automatizado` é um campo próprio, distinto de "aposentada por redundância com
ferramenta nativa"** (decisão desta story, resolvendo uma ambiguidade que o PRD deixa
implícita em FR-8): existem duas formas legítimas e **semanticamente diferentes** de um
`🟢` sair da fila de candidatos a Semgrep —
1. **Já tem uma regra Semgrep autorada** (PRD 04/E7 rodou e escreveu a regra) — a entrada
   continua **viva** (`estado` não muda), só marca `automatizado: true`. Ela continua
   sendo conhecimento ativo (o anti-pattern ainda existe, só passou a ser enforced).
2. **Nunca vai precisar de Semgrep** porque uma ferramenta nativa mais barata já cobre o
   caso (ESLint/pyright) — a entrada é **aposentada** com
   `causa-da-morte: "redundante com ferramenta nativa"` (convenção herdada literalmente
   de `document-types.md`, entrada `anti-pattern`). Ela sai da fila porque está morta
   para fins de enforcement Semgrep, não porque ganhou uma regra.

Misturar os dois num único campo booleano perderia essa distinção (ver Dev Notes da
Story E4.4 para o raciocínio completo).

## 2. Gramática MADR (corpo do documento)

Toda Entrada de Ledger segue a gramática única de FR-6:

```
contexto → decisão → alternativas mortas (com causa) → consequências → estado → contador-de-utilidade
```

Estrutura de corpo (seções nomeadas, nesta ordem):

```markdown
# <Título da entrada>

## Contexto
<o que motivou a decisão/regra/padrão — o problema, não a solução>

## Decisão
<a decisão/regra/padrão em si, formulada de forma acionável>

## Alternativas consideradas e rejeitadas
- (a) <alternativa> — rejeitada porque <causa>
- (b) <alternativa> — rejeitada porque <causa>

## Consequências
<impacto, trade-off aceito, o que passa a valer a partir daqui>

## Enforcement          <!-- SÓ para tipo: regra -->
<como a regra é/seria verificada — manual hoje, Semgrep candidato via selo, PRD 04>
```

`estado` e `contador-de-utilidade` **não** são seções de corpo — vivem só no
front-matter (§1); a gramática MADR do PRD lista-os na cadeia conceitual, mas
estruturalmente são metadado parseável, não prosa.

### 2.1 Ciclo de vida — `candidata → ativa → aposentada`

```
   candidata ──(ratificada)──▶ ativa ──(aposentada, com causa)──▶ aposentada
       │                                                              ▲
       └──────────────(aposentada direto, com causa)──────────────────┘
```

- **`candidata`** — nasceu, ainda não ratificada como prática corrente. `padrão` nasce
  aqui quando a bibliotecária observa repetição (E3.4); `decisão-*`/`regra`/`anti-pattern`
  também podem nascer `candidata` quando gravadas por `on_complete` (E4.5) antes de
  ratificação humana.
- **`ativa`** — em uso corrente; o estado normal de uma entrada consultável e citável.
- **`aposentada`** — morta. **Exige `causa-da-morte` não-vazia** (FR-5) — nunca é possível
  marcar `aposentada` sem preencher o motivo. Uma entrada aposentada continua
  **consultável** (é o "cemitério" — UJ-2 do PRD: o Gerente descarta uma abordagem já
  tentada e morta em vez de re-tentá-la cegamente). Aposentada ≠ apagada.

Toda transição registra **data** (`updated:` no front-matter) **e motivo** — para
`aposentada`, o motivo É o `causa-da-morte`; para `candidata → ativa`, o motivo vive no
corpo (ex.: uma linha em `## Consequências` ou uma seção `## Transições`, ver
`scripts/transition_ledger_entry.py`).

### 2.2 Causas da morte — vocabulário aberto, mas com convenções recorrentes

`causa-da-morte` é texto livre, mas os scripts (e a bibliotecária) reconhecem estas
convenções ao interpretar/relatar:

- `"revertida por <path>"` — a entrada foi superada por uma decisão nova (ver §2.3).
- `"redundante com ferramenta nativa"` — só para `anti-pattern`/`regra`: um lint/type
  checker nativo (ESLint, pyright) já cobre o caso; não precisa de Semgrep nem de
  rastreio próprio continuado.
- `"falso-positivo alto"` — só para `regra`/`anti-pattern`: o enforcement gerou ruído
  demais em relação ao problema real que barrava.
- Qualquer outro texto descritivo — livre, desde que não-vazio.

### 2.3 Reversão — nunca uma entrada solta

Reverter uma decisão/regra/padrão **nunca** é só marcar a entrada velha como aposentada
solta no ar. A convenção:

1. A **entrada nova** (a decisão que substitui a velha) nasce com o campo
   `reverte: <path relativo à entrada original>` no front-matter, e cita a reversão em
   `## Contexto` ("Esta decisão reverte X porque...").
2. A **entrada original** é marcada `estado: aposentada` com
   `causa-da-morte: "revertida por <path da entrada nova>"`.

Os dois passos são a **mesma transição**, olhada de dois lados — nunca só um dos dois.
`scripts/validate_ledger.py` verifica que todo `reverte:` preenchido resolve para um
arquivo `.md` existente dentro da raiz do Ledger (link não pode apontar para o nada).
`scripts/transition_ledger_entry.py revert` automatiza os dois passos atomicamente (ver
§6).

## 3. Contador de utilidade — isenção de `decisão-*` e `padrão` (FR-7)

`contador-de-utilidade` é um inteiro incrementado por um **evento externo** de "esta
entrada pegou algo de verdade":

- **`regra`** — o **único** tipo-de-Ledger com esse evento de fato instrumentável: o
  enforcement mecânico (PRD 04/E7, ainda não construído) incrementa o contador toda vez
  que a regra barra um problema real. `scripts/validate_ledger.py` já expõe o **ponto de
  extensão** (`scripts/transition_ledger_entry.py bump-utilidade`) para quando o
  enforcement existir — nesta story o incremento é manual/simulado, não automático.
- **`anti-pattern`** — mesmo racional de `regra` quando `automatizado: true` (uma regra
  Semgrep gerada a partir dele passa a incrementar seu contador também).
- **`decisão-técnica`/`decisão-de-produto`/`decisão-de-arquitetura`** — **isentas da
  poda-por-utilidade.** Não existe hoje nenhum evento de "esta decisão foi consultada"
  instrumentado — sem isso, o contador ficaria permanentemente zero, e uma poda ingênua
  por utilidade proporia aposentar **todo o Ledger de decisões**, o oposto do desejado.
  Uma `decisão-*` só morre por **reversão explícita** (§2.3), nunca por desuso.
- **`padrão`** — **isento pelo mesmo racional**, por extensão consistente do FR-7
  aplicada por `document-types.md` (o PRD não cita `padrão` explicitamente em FR-7, mas
  o mesmo problema — nenhum evento de "foi reaproveitado" instrumentado — se aplica
  ponto por ponto). Um `padrão` morre por reversão/obsolescência, não por contador zero.

`scripts/validate_ledger.py` materializa essa regra: só entradas `tipo: regra` (ou
`tipo: anti-pattern` com `automatizado: true`) com `contador-de-utilidade == 0` e
`estado != aposentada` entram na lista `poda_candidatos`; `decisão-*`/`padrão` com
contador zero são listados à parte, em `isentos_baixa_utilidade`, e **nunca**
misturados com os candidatos reais — ver Validação da Story E4.3 para prova.

`[NOTE FOR PM]` opcional/futuro (herdado do PRD, §4.2 FR-7): instrumentar "decisão
consultada" (o Gerente/sub-agente loga quais docs injetou na curadoria de contexto)
daria um sinal real de utilidade para `decisão-*`/`padrão`; até lá, a isenção acima é a
proteção.

## 4. Selo de maturidade — só `anti-pattern` (FR-8)

`selo` marca o quão mecanicamente detectável um anti-pattern é:

| Selo | Significado | Ação |
|---|---|---|
| 🟢 | Automatizável mecanicamente (AST-decidível) | candidato a regra Semgrep (PRD 04), se ainda não `automatizado` |
| 🟡 | Híbrido (parte mecânica, parte julgamento) | fora da fila Semgrep; pode virar pré-filtro determinístico depois |
| 🔴 | Só-humano (contexto/semântica de produto) | fora da fila Semgrep; permanece revisão manual |

**A fila de candidatos a Semgrep é uma QUERY, nunca uma lista mantida à mão** (FR-8,
consequência testável). `scripts/query_semgrep_candidates.py` deriva a fila com o
filtro exato do PRD:

```
candidato a Semgrep  ⟺  selo == 🟢  ∧  estado != aposentada  ∧  automatizado != true
```

- `selo != 🟢` → nunca candidato (🟡/🔴 saem do filtro, mesmo se `automatizado` estiver
  ausente/false).
- `estado == aposentada` → nunca candidato, **mesmo se `selo == 🟢`** — cobre tanto a
  causa `"redundante com ferramenta nativa"` quanto qualquer outra aposentadoria (a
  entrada está morta; morta não gera trabalho de enforcement novo).
- `automatizado == true` → já tem regra Semgrep autorada; sai da fila sem precisar
  aposentar a entrada (§1).

## 5. Regras de validação mecânica (`scripts/validate_ledger.py`)

Por entrada (arquivo `.md`, front-matter YAML no topo, excluindo `index.md`):

1. **Tipo válido** — `tipo` presente e ∈ aos 6 slugs-de-Ledger. Um doc com `tipo` de
   fora do Ledger (`nota-operacional`, `changelog`, `timeline`, etc.) é reconhecido e
   **explicitamente isento** das checagens 2-6 abaixo (relatado como "fora do escopo do
   Ledger", nunca como violação) — a prova mecânica de FR-6/F26.
2. **MADR presente** — `## Contexto`, `## Decisão`, `## Alternativas...`,
   `## Consequências` (por prefixo, tolera título completo da seção de alternativas);
   `regra` exige também `## Enforcement`. Só roda para os 6 tipos-de-Ledger (checagem 1).
3. **`estado` válido** — ∈ {candidata, ativa, aposentada}.
4. **`aposentada` exige `causa-da-morte`** não-vazia; qualquer outro estado com
   `causa-da-morte` preenchida é uma inconsistência sinalizada (nunca corrigida
   automaticamente — mesma filosofia read-only de `validate_wiki_docs.py`).
5. **Reversão com link** — se `reverte` preenchido, resolve para um `.md` existente
   dentro da raiz escaneada.
6. **Selo válido em `anti-pattern`** — presente e ∈ {🟢, 🟡, 🔴}.
7. **`contador-de-utilidade`** — inteiro quando presente; e a derivação de
   `poda_candidatos` vs. `isentos_baixa_utilidade` de §3.

Este script **nunca corrige nada** — só reporta (mesma filosofia de
`validate_wiki_docs.py`, E3.4, `curation-guide.md` §2.2: a bibliotecária nunca conserta
um documento sozinha).

## 6. Scripts desta pasta

- **`scripts/validate_ledger.py`** — validação mecânica de §5. `--ledger-root <pasta>`
  `[--json]`.
- **`scripts/query_semgrep_candidates.py`** — deriva a fila de §4. `--ledger-root <pasta>`
  `[--json]`.
- **`scripts/transition_ledger_entry.py`** — escreve transições de estado
  (`retire`/`revert`/`bump-utilidade`/`mark-automated`) com escrita atômica (temp +
  `fsync` + rename — mesma primitiva de `_bmad/scripts/memlog.py`, adaptada para mutar
  o front-matter de um arquivo de entrada individual em vez de um log plano único por
  workspace; ver Dev Notes da Story E4.2 para o porquê de não reusar o CLI de
  `memlog.py` literalmente). `mark-automated` (Story E7.4, PRD 04 FR-4) seta
  `automatizado: true` numa entrada `tipo: anti-pattern` quando uma regra Semgrep é
  autorada a partir dela — o elo que fecha o loop com `query_semgrep_candidates.py`
  (a entrada sai da fila sem ser aposentada, `estado` permanece inalterado). Recusa
  (`exit 2`) qualquer entrada que não seja `tipo: anti-pattern`, porque o campo
  `automatizado` só existe nesse schema (§1). Idempotente: rodar duas vezes na mesma
  entrada não duplica a nota de transição.

## 7. Fora de escopo desta story (E4.1-E4.4) vs. próximas

- **Gravação automática na conclusão do trabalho (`on_complete`)** — Story E4.5.
- **`timeline`/`changelog` como Documento-tipo formal na árvore** — Story E4.6/E4.7.
- **Enforcement Semgrep de fato** (que consome o selo 🟢 e escreve `automatizado: true`
  de verdade) — PRD 04 / Epic E7.
- **Migração completa dos monólitos reais (`decisions.md`, `anti-patterns.md`,
  `product-decisions.md`) para esta árvore** — Story E3.6/E4.6, hoje deferida ao dono
  (ver `deferred-work.md`); esta story só migra 2-3 entradas reais como exemplo
  (`decisao-tecnica/`, `regra/`, `anti-pattern/` abaixo), sem apagar as fontes.
