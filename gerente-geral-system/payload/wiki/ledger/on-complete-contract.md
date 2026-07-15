---
title: Contrato do hook `on_complete` — gravação no Ledger na conclusão do trabalho
tipo: reference
created: 2026-07-11
status: living-document
source_prd: "ideias/prd-01-wiki-ledger.md"
source_epic: "ideias/epics.md — Epic E4"
source_story: "ideias/sistema-artifacts/E4-5-gravacao-conclusao.md"
extends: "wiki/ledger/README.md"
---

# Contrato do hook `on_complete` — gravação no Ledger na conclusão do trabalho

## O que é este documento

Este é o **contrato canônico** (PRD 01 §4.3, FR-10, Story E4.5) de como uma skill de
execução BMad grava entradas de Ledger **por construção**, na conclusão do seu próprio
trabalho — a "Rule Zero estruturalizada": em vez de depender de o agente "lembrar" de
atualizar `_bmad-output/decisions.md`/`anti-patterns.md`/`product-decisions.md`/`notes.md`
manualmente (o mecanismo hoje em AGENTS.md § "RULE ZERO", que é uma instrução em prosa,
não uma fiação verificável), a conclusão da skill **emite** as entradas pertinentes no
formato do Ledger (schema de [`E4.1`](./README.md), ciclo de vida de
[`E4.2`](./scripts/transition_ledger_entry.py)), como consequência mecânica de terminar,
não como um passo extra que pode ser esquecido.

Este contrato **não inventa um novo hook** — ele documenta e especializa um mecanismo
**já existente e já em uso** neste projeto: o campo `on_complete` do bloco `[workflow]`
de `customize.toml`, resolvido via
`python3 _bmad/scripts/resolve_customization.py --skill {skill-root} --key workflow.on_complete`
e executado como a **última instrução terminal** do passo final da skill (ver
`.claude/skills/bmad-dev-story/SKILL.md` último passo, `.claude/skills/bmad-retrospective/SKILL.md`
Step 13, `.claude/skills/bmad-code-review` — todos já chamam esse resolver hoje). O que
faltava, e este documento define, é **o que colocar dentro desse campo** quando o
trabalho concluído produziu conhecimento reusável — não a mecânica de disparo em si, que
já existe.

## 1. Assinatura

`on_complete` é uma **string de instrução** (não um script, não uma função — o mesmo
formato textual que `bmad-dev-story.toml` já usa) resolvida no momento em que a skill
termina seu último passo. Uma skill produtora de conhecimento (ver §2) define, no seu
override `_bmad/custom/{skill-name}.toml`, um `on_complete` cujo texto instrui o agente a:

```
on_complete = "<instrução em prosa: classificar itens Ledger-worthy do trabalho concluído
                per on-complete-contract.md §2-3, emitir 1 arquivo por item em
                wiki/ledger/<tipo-slug>/, estado: candidata, rodar
                validate_ledger.py como self-check, reportar N entradas emitidas>"
```

Não há parâmetros posicionais nem retorno estruturado — o "contrato" é behavioral
(prosa executada pelo agente), o mesmo formato que todo `on_complete` existente neste
projeto já usa. Uma skill pode complementar isso com `persistent_facts` (ver
`bmad-retrospective.toml`, §5 abaixo) quando a classificação precisa acontecer **antes**
do passo final (ex.: durante a síntese de action items), não só no próprio `on_complete`.

## 2. O que conta como "Ledger-worthy" — critério de emissão

**Nem toda conclusão de trabalho emite uma entrada.** A maioria das stories/tarefas
termina sem produzir conhecimento novo reusável — só código. `on_complete` só emite
quando o trabalho concluído produziu pelo menos um item que se encaixa numa das 6
gramáticas do Ledger ([`document-types.md`](../document-types.md) § "Entradas de Ledger"):

| Sinal observado no trabalho concluído | Tipo-de-Ledger candidato |
|---|---|
| Uma escolha entre alternativas foi feita e vale para o futuro (não só para esta story) | `decisão-técnica` / `decisão-de-arquitetura` |
| Uma escolha sobre COMPORTAMENTO DO PRODUTO foi feita/confirmada (visível a stakeholder) | `decisão-de-produto` |
| Uma convenção acionável e verificável foi estabelecida ("sempre/nunca fazer X") | `regra` |
| Um jeito de fazer algo se repetiu ≥2x de forma consistente e vale consolidar | `padrão` |
| Um erro/gotcha recorrente foi identificado, com um jeito certo de evitá-lo | `anti-pattern` |
| Nenhum dos acima — só execução, sem generalização nova | **nada é emitido** |

Este critério é deliberadamente **mais estrito** que "toda lição vira uma entrada" — o
mesmo espírito do guardrail F8/§1 do `curation-guide.md` ("nunca apaga sem causa"),
aplicado do lado da criação: emitir demais infla o Ledger com ruído, tornando a curadoria
(E3.4) mais cara sem ganho real. Quando em dúvida, a skill prefere **não emitir** — o
custo de perder uma lição pontual é menor que o custo de poluir o Ledger com entradas
triviais que a bibliotecária depois precisa podar.

## 3. O que emite — schema e local de gravação

Para cada item Ledger-worthy identificado:

1. **Classificar o `tipo`** (um dos 6 slugs de §2).
2. **Escrever o front-matter completo** do schema de E4.1 (README.md §1):
   `tipo`, `estado: candidata` (**sempre** `candidata`, nunca `ativa` — ver §4), `causa-da-morte: null`,
   `contador-de-utilidade: 0`, `areas: [...]` (as áreas/features tocadas pelo trabalho,
   se determináveis — vazio é aceitável), `reverte: null`, `created`/`updated` = data de
   hoje. `anti-pattern` ganha também `selo` (🟢/🟡/🔴, julgamento do agente emissor) e
   `automatizado: false`.
3. **Escrever o corpo em gramática MADR completa** (README.md §2): `## Contexto`,
   `## Decisão`, `## Alternativas consideradas e rejeitadas` (mesmo que seja só "nenhuma
   alternativa real foi considerada — a decisão nasceu como consequência direta de X",
   nunca omitir a seção), `## Consequências`; `regra` ganha também `## Enforcement`.
4. **Gravar em** `wiki/ledger/<tipo-slug-ascii>/<slug-descritivo>.md`, onde
   `<tipo-slug-ascii>` segue o mapeamento **já em uso** pelas 3 pastas reais existentes
   (`ledger/decisao-tecnica/`, `ledger/regra/`, `ledger/anti-pattern/`):

   | `tipo` (front-matter) | pasta (ascii, sem acento) |
   |---|---|
   | `decisão-técnica` | `decisao-tecnica/` |
   | `decisão-de-produto` | `decisao-de-produto/` |
   | `decisão-de-arquitetura` | `decisao-de-arquitetura/` |
   | `regra` | `regra/` |
   | `padrão` | `padrao/` |
   | `anti-pattern` | `anti-pattern/` |

5. **Colisão de nome de arquivo** — se `<slug-descritivo>.md` já existir na pasta alvo
   (dois produtores concorrentes, ou reexecução), o emissor acrescenta um sufixo numérico
   (`-2`, `-3`, ...) **nunca sobrescreve** um arquivo existente às cegas — uma entrada de
   Ledger é conteúdo autoral, não um log append-only genérico (diferente de `memlog.py`,
   que é sempre-anexa a um único arquivo por definição).

## 4. Por que sempre `candidata`, nunca `ativa`

Uma entrada emitida por `on_complete` nasce **sem revisão humana** — é a leitura do
próprio agente executor sobre o que acabou de fazer, no calor da conclusão. O Ledger
README (§2.1) já reserva exatamente este caso: *"`decisão-*`/`regra`/`anti-pattern`
também podem nascer `candidata` quando gravadas por `on_complete` (E4.5) antes de
ratificação humana."* Promover `candidata → ativa` é uma decisão consciente de alguém
(o dono, ou um sub-agente com mandato explícito de ratificar) que a entrada é, de fato,
prática corrente — não uma mudança automática que `on_complete` executa sozinho. Até lá,
a entrada já é **consultável** (não fica escondida esperando ratificação — só carrega o
selo "ainda não ratificada" via `estado: candidata`), o que já cumpre o objetivo central
de FR-10 ("o Gerente descarta uma abordagem já tentada em vez de re-tentá-la cegamente").
A ratificação em si (Briefing da Manhã, Story E8.7, ainda não implementada) fica fora do
escopo deste contrato.

## 5. Validação — self-check obrigatório, não corretivo

Depois de escrever cada entrada, o emissor roda:

```
python3 wiki/ledger/scripts/validate_ledger.py --ledger-root wiki/ledger --json
```

e confirma que a entrada recém-escrita **não** aparece na lista de violações. Isto é
diferente do papel da bibliotecária (`curation-guide.md` §2.2, "a bibliotecária nunca
corrige uma violação encontrada") — aqui o emissor é o **autor** da própria entrada, não
um terceiro editando conteúdo alheio; se a validação falha (ex.: esqueceu uma seção MADR),
o emissor **corrige a própria entrada recém-criada antes de terminar**, porque ainda é o
dono do rascunho. Isso nunca se estende a corrigir entradas pré-existentes de outros
autores — só a que acabou de escrever, na mesma execução.

## 6. Concorrência

Cada Entrada de Ledger é **um arquivo próprio** (ao contrário do log plano único de
`memlog.py`) — dois produtores concorrentes gravando tipos/slugs diferentes nunca colidem
por construção (arquivos diferentes). A escrita de cada arquivo individual usa a mesma
primitiva atômica (`temp` + `flush` + `fsync` + `rename`) que `transition_ledger_entry.py`
já usa para mutações — reaplicada aqui para a criação inicial, não só para transições
subsequentes.

## 7. Produtores registrados

| Skill | Como emite | Status |
|---|---|---|
| `bmad-retrospective` | Override `_bmad/custom/bmad-retrospective.toml` — `persistent_facts` redireciona a síntese de action items (Step 9) para classificar Ledger-worthy vs. tarefa-de-execução-pura, `on_complete` executa a emissão + self-check no fechamento (Step 13) | **Implementado nesta story (E4.5)** |
| Skills de execução em geral (`bmad-dev-story`, `bmad-quick-dev`, `bagual-bmad-implement-quick-epic`, ...) | Cada uma ganharia seu próprio `on_complete`/`persistent_facts` seguindo este mesmo contrato | **Fora de escopo desta story** — é o trabalho da Story E6.6 ("`on_complete` grava no Ledger e no Ticket"), que **reusa** este contrato em vez de redefini-lo. E4.5 entrega o contrato + a primeira implementação concreta (o principal produtor de matéria-prima cross-story, per PRD 01 §6 "Consome"); E6.6 generaliza a fiação para as demais skills de execução. |

## 8. Fora de escopo deste contrato

- **Ratificação `candidata → ativa`** — Briefing da Manhã, Story E8.7.
- **Escalonamento do que fazer quando o emissor não tem certeza da classificação** — na
  dúvida, não emite (§2); não há um caminho de "emitir mas marcar incerto" neste
  contrato — incerteza é motivo de omissão, não de emissão degradada.
- **Gravação no Ticket** — Story E6.6 também menciona "grava... no Ticket"; este
  documento cobre só o lado Ledger. A gravação em Ticket é mecanismo separado
  (`bagual-tickets`, Epic E5), fora do escopo de E4.5.
- **Wiring em todas as demais skills de execução** — ver §7.
