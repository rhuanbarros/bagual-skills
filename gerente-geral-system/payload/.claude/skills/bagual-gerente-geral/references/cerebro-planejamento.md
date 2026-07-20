> **Referência sob demanda.** Extraído verbatim de `.claude/agents/gerente-geral.md` §
> "Cérebro de Planejamento (E9.3)" na decomposição do `SKILL.md` de `bagual-gerente-geral`
> para progressive disclosure. Único lugar onde este contrato vive. Leia por inteiro antes
> da primeira vez que o dono lhe delegar um esforço grande/multi-epic sem detalhar, ou você
> mesmo perceber que um Ticket é grande demais para mapear direto para uma trilha.

## Cérebro de Planejamento (E9.3)

Referência canônica: `ideias/prd-00-sistema-orquestrador.md` §4.2 (FR-4), UJ-2. Contrato
completo (as duas classes de skill, o schema exato do plano, o smoke test que confirmou a
visibilidade da skill para um sub-agente) em `project_controll/gerente/planning-brain.md`
— leia-o por inteiro antes da primeira vez que o dono lhe delegar um esforço grande sem
detalhar (aqui só o passo a passo operacional, resumido).

**Quando dispara:** o dono lhe entrega um intent grande/multi-epic sem já vir decomposto
em Tickets (UJ-2 — "reforce a cobertura de testes e a acessibilidade do app"), OU você
mesmo, durante "priorizar", percebe que um Ticket é grande demais para mapear direto para
uma trilha (`rapida | spec | epic | wds | correct-course`) sem primeiro virar um plano de
múltiplos epics.

**As duas classes de skill (spike S2/S3 — nunca esqueça esta distinção):**
- **`bmad-prd`** tem modo headless formal (`references/headless.md`) → você o roda como
  sub-agente Sonnet headless (Passo 1 abaixo).
- **`bmad-create-epics-and-stories` / `bmad-check-implementation-readiness` /
  `bmad-correct-course`** são facilitador-only (travas `WAIT FOR INPUT`/`YOU ARE A
  FACILITATOR`, testadas ao vivo contra a skill-irmã `wds-8` no spike S3 — travou no
  primeiro passo) → você **nunca** as spawna como sub-agente. O que elas fariam, você
  faz **in-thread**, no seu próprio contexto Opus, aplicando o método delas como
  conhecimento — nunca invocando `Skill(bmad-create-epics-and-stories)`/
  `Skill(bmad-check-implementation-readiness)`/`Skill(bmad-correct-course)` num
  sub-agente autônomo. Isso não é um atalho — é a única forma de não travar o ciclo
  esperando um humano que não está lá.

### Passo a passo

1. **`bmad-prd` headless (sub-agente Sonnet, foreground):** spawne um `Agent`
   (`model: "sonnet"`) instruído a invocar explicitamente a skill `bmad-prd` (nomeie a
   skill no prompt — nunca deixe implícito) com o payload headless de
   `.claude/skills/bmad-prd/references/headless.md` (`headless: true`, `intent`,
   `brief` = o intent do dono + contexto relevante que você já tenha, `doc_workspace`).
   Leia o JSON terminal: `status: "complete"` ou `"partial"` → siga para o Passo 2 (todo
   `open_questions[]` de um `"partial"` vira ambiguidade tratada no Passo 4, não trava o
   plano inteiro); `status: "blocked"` → **não** prompte, **não** invente — o `reason` é
   a ambiguidade e vai direto para o Passo 4 (Protocolo do Oráculo) para esta frente de
   trabalho especificamente.
2. **Decomponha em epics/stories IN-THREAD** (sem spawnar `bmad-create-epics-and-stories`):
   leia o PRD do Passo 1 + o grounding do projeto (os arquivos de conhecimento + Ledger +
   padrões existentes), e grave o plano em
   `project_controll/gerente/planning/<slug-do-intent>-plano.md`, uma seção `## Epic N`
   por epic, **cada uma declarando obrigatoriamente**: título/descrição, `área` (mesma
   tag usada em Tickets/Ledger), `arquivos/diretórios prováveis` (o insumo de entrada
   para o grafo de paralelismo do PRD 03 — você NÃO calcula o grafo aqui, só declara),
   e `depende-de` (outros epics do mesmo plano, se houver). **Cada seção também carrega
   um sentinel estruturado da MESMA declaração** — Story `bridge-declaracao-areas`, a
   ponte que liga o paralelismo de E10/E11 —, uma linha
   `<!-- epic-decl: {"epic_key": "...", "epic_type": "...", "areas": [...],
   "touches_shared": [...], "depends_on": [...]} -->` logo abaixo da seção.
   `epic_key` é a chave REAL do `sprint-status.yaml` (nunca o número `## Epic N` da
   seção, que é só um índice de documento — a chave real só existe quando o Ticket é
   materializado). Formato completo + rationale:
   `project_controll/gerente/planning-brain.md` §3 Passo 2.
3. **Checagem de prontidão IN-THREAD** (sem spawnar
   `bmad-check-implementation-readiness`): releia o plano contra o PRD aplicando o
   checklist de prontidão como conhecimento — escopo claro? dependência circular? epic
   grande demais? Anote o veredito (`pronto` / `precisa de ajuste`) por epic na mesma
   seção `## Checagem de prontidão` do arquivo de plano. Um epic `precisa de ajuste` não
   é despachado nesta rodada.
4. **Ambiguidade de produto → Protocolo do Oráculo (E9.1), nunca bloqueio do plano
   inteiro:** qualquer `open_questions[]`/`reason` do Passo 1 ou dúvida de escopo
   percebida nos Passos 2-3 segue o "Protocolo do Oráculo" (`references/protocolo-oraculo.md`) por epic
   afetado — decide com rastro se a confiança permitir (`high`, precedente real), ou
   registra a pergunta no Ticket daquele epic e segue com os demais epics do plano, que
   não ficam bloqueados pela dúvida de um irmão (UJ-2, "Edge case").
5. **Materialize Tickets + despache via o contrato já existente (E8.4):** para cada epic
   `pronto`, invoque `bagual-tickets` (nunca edite `board.yaml` à mão) para criar um
   Ticket com `trilha: epic`, `area:` a declarada no plano, `## Locais afetados`
   preenchido com os arquivos/diretórios do Passo 2, `## Descrição` citando o path do
   plano. A partir daqui **não há mecanismo novo** — o Ticket entra na fila
   `pronto-para-implementar` normal e segue as fases "priorizar"/"despachar" já
   descritas acima (`trilha: epic` → `/bagual-epic-runner {N}`, `gerente_dispatch.py
   open-dispatch`). Continue despachando **um Ticket por vez** — paralelismo entre os
   epics deste mesmo plano é território do PRD 03/E10-E11, fora de escopo aqui.
   **Antes de despachar o conjunto de epics deste plano, rode a ponte**
   (`python3 project_controll/gerente/scripts/emit_epic_areas.py from-plan --plan
   <plano.md> --sprint-status <alvo>`) para popular o `epic_areas:` que
   `compute_execution_graph.py` lê no início de toda invocação do
   `bagual-epic-runner` — sem isso, o grafo continua caindo no fail-safe sequencial
   mesmo com epics de áreas disjuntas. Detalhe em `planning-brain.md` §3 Passo 4.

**Visibilidade da skill no sub-agente (nota de tooling — mantenha a defesa em
profundidade):** um sub-agente `general-purpose` pode, dependendo do harness/versão, não
enxergar skills `bmad-*` no seu registro. Sempre **nomeie a skill explicitamente** no
prompt do sub-agente (nunca deixe implícito) — se algum dia um sub-agente reportar que a
skill não apareceu, trate como falha do Passo 1 (equivalente a `blocked`) e registre a
recorrência na sua nota-operacional/notes do projeto, nunca contorne inventando uma
chamada direta sem passar pela skill.
