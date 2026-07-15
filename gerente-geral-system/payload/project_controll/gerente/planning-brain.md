# Cérebro de Planejamento (E9.3) — headless onde dá, in-thread onde não dá

> Contrato de referência para o Protocolo "Cérebro de Planejamento" em
> `.claude/agents/gerente-geral.md`. Story: `ideias/sistema-artifacts/E9-3-cerebro-planejamento.md`.
> Canônico: `ideias/prd-00-sistema-orquestrador.md` §4.2 (FR-4), UJ-2. Spike que fundamenta
> o design: `ideias/fase-0-spikes.md` § S2+S3.

## 1. O problema que este documento resolve

UJ-2 (PRD 00): o dono delega um esforço **grande** ("reforce a cobertura de testes e a
acessibilidade do app") sem detalhar em epics/stories, e some. O Gerente precisa
transformar isso num plano de epics/stories **sozinho**, sem travar esperando o dono em
cada micro-decisão, mas também sem inventar escopo por conta própria onde há ambiguidade
de produto real.

A ferramenta óbvia seria reusar as skills de planejamento do John (`bmad-agent-pm`) como
sub-agentes headless — exatamente como o Gerente já faz com `bmad-quick-dev`/
`bmad-dev-story`/`bagual-epic-runner` na fase "despachar". O spike S2/S3
(`ideias/fase-0-spikes.md`) descobriu que **isso só funciona para uma parte delas** —
ver §2.

## 2. Classe 1 vs Classe 2 — a descoberta do spike S2/S3

| Classe | Skills | Comportamento headless | Evidência |
|---|---|---|---|
| **Classe 1 — automatizável** | `bmad-prd` | Tem **modo headless formal**: `.claude/skills/bmad-prd/references/headless.md` + `assets/headless-schemas.md`. Detecta `headless: true` (ou invocação de outra skill/runner não-interativo) na primeira mensagem, nunca pergunta, produz um payload JSON terminal (`status: complete\|partial\|blocked`). | Formal, documentado na própria skill. Reconfirmado ao vivo nesta story (§4 abaixo) — rodou ponta-a-ponta sem nenhum prompt interativo. |
| **Classe 1 — automatizável** (referência, não usada nesta story) | `create-story`/`dev-story`/`code-review` | Sem modo headless formal, mas **sem travas duras de facilitador** — honram "yolo/auto-approve/não pergunte" no prompt de spawn. | `bagual-epic-runner` já roda assim em produção (Epics E1-E8 deste próprio sprint meta). |
| **Classe 2 — facilitador-only** | `bmad-create-epics-and-stories`, `bmad-check-implementation-readiness`, `bmad-correct-course` | **Sem** `references/headless.md`. Têm `🛑 WAIT FOR INPUT` / `YOU ARE A FACILITATOR not a content generator` / menus `[C] Continue` — *turn-yields semânticos*, não diálogos de permissão. Auto-approve **não** resolve isso — são gates que esperam uma resposta humana real de dentro do corpo da skill. | Testado ao vivo no spike S3 contra `wds-8` (mesma classe/mesmas travas): travou no primeiro `step-01-identify`, ≥5 halts duros. Inspecionado (não executado até o fim) em `bmad-create-epics-and-stories`/`bmad-check-implementation-readiness`/`bmad-correct-course` — mesmas travas textuais confirmadas por leitura direta das skills. |

**Regra derivada (a que este protocolo aplica):** o Gerente **nunca spawna** uma skill
Classe 2 como sub-agente headless — isso trava o ciclo autônomo à espera de um humano
que não está lá (exatamente o F5/E2.2 "sub-agente pendurado", só que pela skill em si,
não pelo harness). Para o que essas skills fariam, o Gerente faz o raciocínio **in-thread**
(o próprio Opus do Gerente, dentro do seu contexto, aplica o MÉTODO da skill como
conhecimento — sem invocar `Skill(bmad-create-epics-and-stories)`), ou marca o passo como
pendente do dono quando o julgamento requerido excede o que o oráculo tem confiança para
decidir sozinho (mesmo veto mecânico F10 já usado pelo Protocolo do Oráculo, E9.1).

**Nunca forkar as skills Classe 2** para "consertar" a falta de modo headless — isso
violaria a regra "nativo > genérico; nunca forkar `bmad-*`" (`AGENTS.md`). A skill continua
existindo intacta para o uso interativo normal do dono; o Gerente simplesmente não a chama
quando está sozinho.

## 3. O protocolo — 4 passos

### Passo 1 — `bmad-prd` headless via sub-agente Sonnet

O Gerente despacha um `Agent` (**`model: "sonnet"`**, foreground — mesma disciplina de
"nunca despacho pendurado" das demais fases) instruído a invocar a skill `bmad-prd` com
um payload headless na primeira mensagem, seguindo literalmente
`.claude/skills/bmad-prd/references/headless.md`:

```
headless: true
intent: create   # ou update/validate, conforme o caso
brief: "<o intent grande do dono, verbatim + qualquer contexto que o Gerente já tenha
         (Ledger, tickets relacionados, grounding do projeto)>"
doc_workspace: "<pasta de destino do PRD — NUNCA a pasta de planejamento real do produto
                 sem que o dono tenha pedido isso; para trabalho de rascunho/exploração,
                 usar uma pasta de trabalho dedicada>"
```

Ambiguidade real (o `brief` não dá para inferir um alvo sem inventar detalhe de produto)
→ a skill retorna `status: "blocked"` com `reason` — **nunca** um prompt interativo (é
isto que o modo headless formal garante). O Gerente lê o JSON terminal:

- `status: "complete"` → segue para o Passo 2 com o `prd` produzido.
- `status: "partial"` → segue para o Passo 2, mas cada item de `open_questions[]` vira
  uma pergunta rastreada (ver §"Ambiguidade de produto" abaixo) — não trava o Passo 2
  inteiro por causa disso.
- `status: "blocked"` → **não** segue para o Passo 2. O `reason` vira o registro de
  ambiguidade (mesmo tratamento de "Ambiguidade de produto" abaixo) e o Gerente para essa
  frente de trabalho especificamente, sem travar o ciclo inteiro (outros Tickets da fila
  continuam sendo processados normalmente).

### Passo 2 — Decomposição em epics/stories, IN-THREAD (nunca spawnada)

O Gerente, no seu próprio contexto Opus (sem `Skill(bmad-create-epics-and-stories)`),
aplica o MÉTODO dessa skill como conhecimento: lê o PRD produzido no Passo 1 + o
grounding do projeto (padrões existentes, `_bmad-output/{anti-patterns,decisions,
product-decisions,notes}.md`, Ledger — o mesmo grounding que uma story normal carrega em
spec-time, PRD 03), e decompõe em epics/stories.

**Contrato obrigatório de saída — cada epic do plano DECLARA:**
- `título` + `descrição` (o que entrega).
- `área` — a mesma tag de área/feature usada em `bagual-tickets` (`area:` no
  front-matter do Ticket) e no Ledger (`areas: [...]`).
- `arquivos/diretórios prováveis` — o melhor palpite fundamentado do Gerente sobre onde
  o trabalho vai tocar (ex.: `frontend/src/features/clients/**`,
  `backend/domain/vehicles/**`). Não precisa ser exaustivo nem definitivo — é o insumo
  de ENTRADA para o cálculo do grafo de paralelismo do PRD 03 (disjunção de área/
  arquivos entre epics = paralelizável); **o cálculo do grafo em si não é feito aqui**.
- `depende-de` — outros epics do MESMO plano que precisam terminar antes (se houver).

O plano é gravado em disco (**file-mediated**, mesmo princípio de FR-8): um arquivo
Markdown por plano, `project_controll/gerente/planning/<slug-do-intent>-plano.md`, uma
seção `## Epic N — <título>` por epic com os 4 campos acima. Este arquivo é o artefato
que a fase "despachar" (E8.4) consome depois — nunca um valor de retorno solto no
contexto do Gerente.

**Contrato de saída ADICIONAL (Story `bridge-declaracao-areas` — a ponte que liga o
paralelismo de PRD 03/E10-E11): cada seção `## Epic N` também carrega um sentinel
ESTRUTURADO da MESMA declaração acima**, mecanicamente extraível — nunca uma segunda
fonte de verdade a manter sincronizada à mão, é a mesma declaração que você (Gerente)
já está fazendo em prosa, só restated uma vez em JSON de uma linha só:

```
<!-- epic-decl: {"epic_key": "epic-E12", "epic_type": "feature", "areas": ["frontend/src/features/x/"], "touches_shared": ["supabase/migrations"], "depends_on": ["epic-E11"]} -->
```

Formato: um comentário HTML (invisível numa leitura humana normal do plano) contendo
UM objeto JSON numa linha só, colocado logo abaixo da seção `## Epic N — <título>` que
descreve. Campos — os MESMOS 5 que `compute_execution_graph.py` já consome, nem mais
nem menos (ver o módulo docstring daquele script,
`.claude/skills/bagual-epic-runner/scripts/compute_execution_graph.py`):
- `epic_key` (**obrigatório**) — a chave REAL que `sprint-status.yaml` vai usar
  quando este epic for despachado (ex.: `epic-42`, `epic-E12`). **Nunca infira isto
  do número `## Epic N` da seção** — o número do plano é só um índice de documento; a
  chave real só existe quando o Ticket/epic é materializado contra o board vivo (Passo
  4). Você é quem sabe a chave certa; declare-a explicitamente.
- `epic_type` — `"feature"` (epic que adiciona rota/endpoint — auto-injeta
  `App.tsx`/`api/index.py` no cálculo de disjunção), `"refactor"` ou `"other"`.
- `areas` — os mesmos "arquivos/diretórios prováveis" declarados em prosa acima,
  como array de strings (prefixos de path).
- `touches_shared` (opcional) — quando você já sabe que este epic toca um dos
  touchpoints compartilhados fixos (migrations, `package.json`/`pyproject.toml`,
  arquivos de processo/conhecimento) mesmo fora de `areas`.
- `depends_on` (opcional) — os `epic_key`s (não os números `## Epic N`) de outros
  epics do MESMO plano que precisam terminar antes.

Os VALORES desses campos são seu julgamento (Opus) — a mesma decisão que você já
tomou para a prosa acima, nunca inferida de volta a partir dela por um script. Uma
ponte mecânica (`project_controll/gerente/scripts/emit_epic_areas.py`, subcomando
`from-plan`) extrai esse sentinel e escreve/atualiza o bloco `epic_areas:` de um
`sprint-status.yaml` alvo — sem NLP, sem parsing de prosa, só extração de um JSON já
pronto. Uma declaração ausente ou malformada (JSON inválido, `epic_key`
ausente/inválido, `epic_type` fora do enum) é PULADA pela ponte — fail-safe, o epic
correspondente cai no `sequencial` padrão de `compute_execution_graph.py`, nunca uma
declaração "adivinhada". Detalhe completo do formato + prova end-to-end (fixture
sintética fazendo o `compute_execution_graph.py` real computar 2 Tracks paralelos):
`ideias/sistema-artifacts/bridge-declaracao-areas.md`.

### Passo 3 — Checagem de prontidão, IN-THREAD (nunca spawnada)

Mesma disciplina do Passo 2: sem `Skill(bmad-check-implementation-readiness)`. O Gerente
aplica o checklist de prontidão como conhecimento — releitura do plano contra o PRD:
todo epic tem escopo claro? Há dependência circular? Alguma epic é grande demais e devia
ser quebrada em duas? Anota o veredito (`pronto` / `precisa de ajuste`) no próprio arquivo
de plano, seção `## Checagem de prontidão`. Um epic marcado "precisa de ajuste" não é
despachado nesta rodada — mas **mantém a declaração de área/arquivos do Passo 2 no
arquivo de plano** (a checagem de prontidão acontece DEPOIS da declaração e nunca a
substitui/apaga); fica registrado com a lacuna específica, para o dono resolver ou para
uma rodada futura do Cérebro de Planejamento.

### Passo 4 — Materializar Tickets + despachar via E8.4

Para cada epic `pronto` do plano: o Gerente invoca `bagual-tickets` (composição, nunca
edição direta de `board.yaml`) para criar um Ticket com `trilha: epic`, `area: <a
declarada no plano>`, `## Locais afetados` preenchido com os arquivos/diretórios
declarados no Passo 2, e `## Descrição` citando o path do plano
(`project_controll/gerente/planning/<slug>-plano.md#epic-N`). A partir daqui, o Ticket
entra na fila normal `pronto-para-implementar` e segue o ciclo operacional padrão
(fase "priorizar" → "despachar" via `gerente_dispatch.py open-dispatch --trilha epic
--skill bagual-epic-runner`, ver tabela de mapeamento trilha→skill em
`.claude/agents/gerente-geral.md` § "3. despachar") — **nenhum mecanismo novo de
despacho é inventado aqui**; o Cérebro de Planejamento termina no momento em que os
Tickets existem, um por epic. O paralelismo entre esses Tickets (despachar mais de um
epic ao mesmo tempo, por worktree) é território do PRD 03/Orquestrador de Execução —
fora de escopo desta story, que continua despachando **um Ticket por vez**, como toda
fase "despachar" já faz desde E8.1.

**Antes de despachar o conjunto de epics `pronto` deste plano para o supervisor
multi-epic (Story `bridge-declaracao-areas`):** rode a ponte mecânica para popular o
`epic_areas:` do `sprint-status.yaml` alvo com os sentinels que você já escreveu no
Passo 2 —

```
python3 project_controll/gerente/scripts/emit_epic_areas.py from-plan \
  --plan project_controll/gerente/planning/<slug>-plano.md \
  --sprint-status <sprint-status.yaml alvo>
```

Isso é o que faz o Graph-build step de `workflow.md` (que roda `compute_execution_graph.py
--epics ... --sprint-status ... --write` no início de toda invocação do
`bagual-epic-runner`) parar de cair sempre no fail-safe `sequencial` e computar Tracks
`paralela` reais quando as áreas dos epics deste plano forem de fato disjuntas — sem
essa chamada, o `epic_areas:` fica vazio e o comportamento é idêntico a antes desta
story (correto, só não paraleliza). A ponte é idempotente e nunca falha o Passo 4
inteiro: um sentinel malformado é só pulado (com warning) e aquele epic específico
fica no fail-safe, os demais epics do plano continuam normalmente.

## 4. Ambiguidade de produto que o oráculo não decide → ticket, nunca bloqueio total

Qualquer ponto do protocolo (um `open_questions[]` do Passo 1, uma decisão de escopo
ambígua percebida no Passo 2/3) que exija um julgamento de produto sem precedente
confiável segue o **Protocolo do Oráculo (E9.1)** já existente: o Gerente tenta decidir
com rastro (Ticket + Ledger); se a confiança sair `low` (sem precedente `estado: ativa`
+ `ratification: ratified` que sustente `high` — F10, gate mecânico de
`gerente_oracle.py`), a pergunta fica **registrada no Ticket do epic afetado** e o
Gerente **segue com o que dá** — nunca trava o plano inteiro por causa de uma dúvida
isolada em um dos epics (UJ-2, "Edge case"). Epics não afetados pela ambiguidade
continuam normalmente para o Passo 4.

## 5. Registro de visibilidade da skill (S2, nota de tooling)

O spike S2/S3 registrou uma dúvida de tooling: ao testar via sub-agente
`general-purpose`, o sub-agente **não enxergou** as skills `bmad-*` no seu registro — só
skills genéricas — mesmo o `bagual-epic-runner` provando na prática que sub-agentes
CONSEGUEM invocá-las. Ficou como "provável artefato do harness de spike, a confirmar".

**Confirmado nesta story (E9.3), com um smoke test real e verificável em disco:** um
sub-agente `general-purpose` fresco (sem contexto prévio), spawnado exatamente como o
Gerente spawnaria um despacho, teve `bmad-prd` **listado no seu system-reminder de
skills disponíveis** e invocou-o com sucesso em modo headless — sem prompt interativo,
sem erro, produzindo um `prd.md` real (`ideias/sistema-artifacts/fixtures/E9/
e9-3-headless-smoke/prd.md`, `status: "partial"`, 3 `open_questions`, `.memlog.md` com 4
entradas via o script compartilhado). Ou seja: **hoje, neste harness/versão do projeto,
a visibilidade de `bmad-prd` para um sub-agente `general-purpose` spawnado via `Agent`
não é um problema** — nenhuma medida adicional (namespace explícito, prompt especial,
etc.) foi necessária para o sub-agente encontrar e invocar a skill.

**O que o Gerente deve fazer mesmo assim (defesa em profundidade, já que o S2 registrou
uma falha real em outro contexto de harness):** ao spawnar o sub-agente do Passo 1, o
prompt deve nomear explicitamente a skill (`invoque a skill "bmad-prd" via a tool
Skill`), nunca assumir implicitamente que o sub-agente "vai saber o que fazer" — mesma
disciplina que `bagual-epic-runner` já usa ao nomear `bmad-create-story`/`bmad-dev-story`
explicitamente no prompt de cada despacho. Se um sub-agente reportar que a skill não
apareceu no seu registro (o cenário que S2 viu), o Gerente trata isso como uma falha do
Passo 1 (`status` equivalente a `blocked`) e registra a ocorrência em
`_bmad-output/notes.md` como uma recorrência do gap de tooling — nunca tenta contornar
inventando uma chamada direta ao PRD sem passar pela skill.

## 6. O que este documento NÃO cobre (fora de escopo, deliberado)

- O cálculo do grafo de paralelismo a partir de `área`/`arquivos` declarados — PRD 03.
- Execução paralela por worktree de múltiplos epics do mesmo plano — PRD 03/E10-E11.
- `wds-8` (mudança de produto com design) — mesma Classe 2, mas resolvida por E9.8
  (in-thread OU espera o dono), não por este documento.
- Escalonamento de tickets triviais (`bagual-tickets` decidindo a trilha sozinha) — E9.4.
