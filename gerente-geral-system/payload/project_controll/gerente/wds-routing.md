---
title: "Execução da via (i) — wds-8 nunca headless (E9.8)"
tipo: reference
created: 2026-07-12
status: living-document
source_prd: "ideias/prd-05-wds.md — FR-6 (§4.1); ideias/fase-0-spikes.md — S3"
source_epic: "ideias/epics.md — Epic E9 (última story, fecha a epic)"
source_story: "ideias/sistema-artifacts/E9-8-wds8-in-thread-ou-dono.md"
---

# Execução da via (i) — wds-8 nunca headless (E9.8)

Contrato canônico do sub-protocolo que `.claude/agents/gerente-geral.md` invoca na fase
**"despachar"** sempre que o `trilha` de um Ticket é `wds` — a decisão de classificação
em si (é via (i)? qual ticket?) já foi tomada por `product-routing.md` (E9.6); este
documento decide **como essa via (i) já roteada é executada**, dado que `wds-8` foi
**provado inviável headless** (spike S3, testado ao vivo — travou no primeiro passo do
Analyze). Leia por inteiro antes da primeira vez que um Ticket com `trilha: wds` chegar
à fase "despachar".

## 1. O fato que ancora este protocolo (S3, testado ao vivo)

`ideias/fase-0-spikes.md` § S3: o `wds-8` é uma skill **facilitadora** com travas duras
— `🛑 NEVER generate content without user input` / `📋 YOU ARE A FACILITATOR, not a
content generator` / `WAIT FOR INPUT` — presentes em **todo** `step-*.md` de **todas**
as suas fases (`steps-a/` Analyze, `steps-d/` Design, `steps-p/` Publish/handoff,
`steps-t/` Test). Um sub-agente autônomo spawnado com instrução explícita de
"auto-approve, yolo, não pergunte" travou mesmo assim no `step-01-identify.md` (Analyze)
— essas travas são **turn-yields semânticos**, não diálogos de permissão que
auto-approve resolve. **Confirmado, não hipotético: nenhum caminho autônomo deste
sistema pode invocar `wds-8` (ou qualquer `wds-*` que componha o mesmo pipeline) como
sub-agente headless.**

## 2. Regra dura, sem exceção

**Nenhum fluxo autônomo deste sistema — o Gerente, nem qualquer sub-agente que ele
despache — spawna `wds-8` (nem `Skill(wds-8-product-evolution)`, nem qualquer dos seus
`workflow-*.md`: `workflow-analyze.md`, `workflow-scope.md`, `workflow-design.md`,
`workflow-implement.md`, `workflow-test.md`, `workflow-deploy.md`) como sub-agente
headless.** Isto vale mesmo que a instrução pareça "só o Analyze, que é leve" — S3
travou exatamente aí. Não há uma versão "parcial" segura de rodar `wds-8` autônomo.

Os arquivos do `wds-8` (`.claude/skills/wds-8-product-evolution/**`) **nunca são
editados** por este sistema — nem para tentar contornar as travas, nem por qualquer
outro motivo (regra geral do projeto, "nunca forkar `bmad-*`/`wds-*`"). A resposta a S3
não é "consertar o wds-8" — é rotear ao redor dele.

## 3. Quando este protocolo dispara

Na fase "despachar" (`.claude/agents/gerente-geral.md` § "3. despachar"), passo 1
(mapear `trilha` → skill): quando o Ticket em mãos tem `trilha: wds` (decidido por
`product-routing.md` §6 via (i) — precisa de design, ou tocou a Coverage Matrix, regra
dura de E9.6), **pare antes de montar qualquer `open-dispatch`**. Não existe uma linha
"a etapa que o Ticket indicar → spawne o `wds-*` correspondente" — essa seria
exatamente a invocação headless que a §2 proíbe. Em vez disso, siga os passos 4-7
abaixo.

## 4. As duas opções — tabela

| # | Opção | Quem faz o A/S/D | Gatilho | Default? |
|---|---|---|---|---|
| **(a)** | Oráculo in-thread | O próprio Gerente, no seu contexto Opus, aplicando o método WDS (Analyze/Scope/Design) como conhecimento — **nunca invocando `Skill(wds-8)`** | Só quando o Protocolo do Oráculo (E9.1) atinge `--confidence high` para esta decisão específica (§6) | **Não** — gateado, evolução futura |
| **(b)** | Espera o dono | O dono, interativo, rodando `wds-8` ele mesmo, com presença humana real para honrar as travas `WAIT FOR INPUT` | Sempre que (a) não atingir alta confiança — o caso normal/inicial | **Sim** — caminho padrão |

Design novo é justamente a classe de trabalho que **vale a atenção humana** (PRD 05
FR-6, Notes) — por isso o padrão é (b), não (a). (a) existe para quando o oráculo já
tiver acumulado estilo suficiente (E9.2) sobre decisões de design in-thread — não no dia
1.

## 5. O gate de (a) — reuso do Protocolo do Oráculo, nenhuma máquina nova

Não há config novo, nem script novo, para decidir (a) vs (b). O gate é literalmente o
mecanismo de confiança que o Protocolo do Oráculo (E9.1) já tem — reaproveitado, nunca
reimplementado:

1. O Gerente roda o Protocolo do Oráculo (`.claude/agents/gerente-geral.md` § "Protocolo
   do Oráculo (E9.1)") com `--tipo decisao-de-produto`, `--areas` incluindo a área do
   Ticket **e** a tag fixa `wds8-design-in-thread` (para que precedentes desta MESMA
   classe de decisão — "o oráculo pode fazer design in-thread?" — sejam encontráveis
   por `consult-precedent`/o gate history-aware de E9.2, sem se confundir com outras
   decisões de produto da mesma área).
2. `--context` = o que o Ticket pede (design novo); `--decision` = "executar via (i) no
   modo (a) in-thread" (a alternativa sendo, implicitamente, (b)); `--justification` = o
   porquê desta escolha ser segura agora.
3. `--confidence high` só é honrado (mecanicamente, por `record-decision`, nunca por
   alegação) se existir um `--precedent` real: uma Entrada de Ledger `decisao-de-produto`
   `estado: ativa`, `ratification: ratified` (ou ausente), de uma execução **anterior**
   do modo (a) que o dono já revisou e aprovou. **No início da vida deste protocolo, tal
   precedente não existe** — logo `record-decision` rebaixa mecanicamente para `low`
   (`downgrade_reason` explicado), `proceed_dispatch: false`, e a via cai em (b) por
   construção, não por convenção. Isso é o que torna "(b) é o padrão" uma garantia
   mecânica (F10), não só uma frase de protocolo que a persona poderia esquecer de
   seguir.
4. Só depois que o dono ratificar (`set-ratification --status ratified`) pelo menos uma
   execução do modo (a) — e desde que nenhuma correção conflitante exista para a mesma
   `--areas` (o mesmo veto history-aware de E9.2) — uma decisão FUTURA e similar pode
   legitimamente pedir `high` citando esse precedente, destravando (a) para aquele
   Ticket específico.

**Isto é a "evolução futura" da Ficha de Build da Story E9.8 ("Autonomia: (a) in-thread
OU (b) espera o dono; padrão (b)") tornada mecânica**: não é um interruptor manual que
alguém liga um dia — é o mesmo aprendizado de estilo (E9.2) que já governa toda decisão
do oráculo, aplicado a esta decisão específica.

## 6. Mecânica de (b) — DEFAULT, "espera o dono"

Quando `record-decision` devolve `proceed_dispatch: false` (o caso normal, §5.3):

1. **Não** mova o Ticket para `triado` (o destino genérico de baixa confiança do
   Protocolo do Oráculo) — mova para **`precisa-de-info`**, via `bagual-tickets`. Isto é
   uma especialização deliberada, não um desvio acidental do protocolo geral: `triado`
   pressupõe que ratificar a decisão já destrava o trabalho (o Ticket volta para
   `pronto-para-implementar` e o Gerente redespacha sozinho); aqui, o desbloqueio
   genuíno não é "o dono confirma uma frase escrita" — é **o dono precisar
   fisicamente/interativamente rodar `wds-8`**, exatamente a classe de bloqueio que
   `precisa-de-info` já é reservada para ("Ativação"/"Quem você é" em
   `gerente-geral.md`: "exige uma ação literal do dono").
2. A nota do Ticket (`## Log`, via `bagual-tickets`) cita o `ledger_path` da decisão
   parqueada **e** uma instrução legível por humano: *"Aguardando o dono: rode `wds-8`
   interativamente (Analyze → Scope → Design) para este Ticket — o fluxo autônomo não
   pode passar pelas travas WAIT-FOR-INPUT do wds-8 (spike S3, ver `wds-routing.md`)."*
3. Inclua o `pending_entry` em `decisions_pending` no próximo `write-snapshot
   --pending-json` — mesmo mecanismo já usado por qualquer decisão do oráculo baixa-
   confiança (E9.1/E8.7); isso é o que faz o Briefing da Manhã (E8.7) surfaçar este
   Ticket para o dono na próxima sessão interativa, sem nenhum wiring novo.
4. **O que o dono faz depois é fora do escopo deste protocolo.** Ele roda `wds-8`
   interativamente na SUA PRÓPRIA sessão (não uma dispatch do Gerente) — pode ir até
   onde quiser, inclusive `[I]/[T]/[P]` se decidir implementar/publicar ele mesmo como
   humano ao teclado. Quando terminar, se restar trabalho de código para o fluxo
   autônomo retomar, ele mesmo atualiza o Ticket (via `bagual-tickets`, ou diretamente)
   — `trilha` re-decidida normalmente (`rapida`/`spec`/`epic`, o design já está feito) e
   status de volta a `pronto-para-implementar`. Nada disto precisa de um mecanismo do
   Gerente — é o dono usando o sistema como sempre pôde usar.

## 7. Mecânica de (a) — GATED, "oráculo in-thread"

Só quando `proceed_dispatch: true` (§5, precedente real e ratificado):

1. O Gerente **não invoca nenhuma skill** — nem `wds-8`, nem um sub-agente `Agent` para
   fazer o trabalho. Ele mesmo, no seu próprio contexto Opus, aplica o método WDS
   (Analyze → Scope → Design) como conhecimento — **exatamente o mesmo padrão já
   estabelecido no "Cérebro de Planejamento (E9.3)"** para `bmad-create-epics-and-
   stories`/`bmad-check-implementation-readiness`/`bmad-correct-course` (skills
   facilitador-only, S2/S3): "o que elas fariam, você faz in-thread". `wds-8` entra na
   MESMA classe — este protocolo é a aplicação concreta dessa classe ao design de
   produto.
2. **Analyze:** entenda o pedido do Ticket contra os documentos canônicos já existentes
   (Coverage Matrix, trigger-map, product-decisions — a mesma "verdade de produto
   documentada" que `product-routing.md` §1 já usa).
3. **Scope:** decida o tamanho da mudança de design (novo cenário? cenário existente
   mudado? novo trigger?) sem gerar conteúdo especulativo além do que o Ticket pede.
4. **Design:** escreva a atualização direto nos **três documentos canônicos** — e SÓ
   estes três, nunca um quarto lugar:
   - `_bmad-output/C-UX-Scenarios/00-ux-scenarios.md` (Coverage Matrix/cenário)
   - `_bmad-output/B-Trigger-Map/trigger-map.md` (se a mudança afeta meta→persona→força)
   - `_bmad-output/product-decisions.md` (a regra de comportamento resultante, mesmo
     formato `## [PRODUCT] Título — YYYY-MM-DD` já usado por todas as entradas
     existentes)
5. **Exceção explícita à seção "Quem você é" de `gerente-geral.md`:** estes três
   arquivos são a ÚNICA superfície de escrita direta de produto que o Gerente tem — e
   só quando executando o modo (a) deste protocolo especificamente (nunca como hábito
   geral). Eles não são código de produto (`frontend/**`/`backend/**`/`supabase/**`) nem
   uma skill `bmad-*`/`bagual-*` — são os mesmos documentos canônicos que o WDS em si
   produziria via `steps-d/step-01-design-update.md`, só que escritos pelo oráculo em
   vez de por um facilitador interativo.
6. Registre a conclusão: uma nota no `## Log` do Ticket (via `bagual-tickets`) citando o
   `ledger_path` da decisão (a) e um resumo do que mudou nos 3 documentos.
7. **Pare aqui.** Ver §8 — nada além de Analyze/Scope/Design acontece neste protocolo,
   em nenhum modo.

## 8. Fronteira A/S/D-only — `[I]/[T]/[P]` sempre fora do fluxo autônomo

**Sem exceção, em QUALQUER modo (a) ou (b):** o fluxo autônomo (o Gerente e qualquer
sub-agente que ele despache) **nunca** avança para `[I]/[T]/[P]` (Implement/Test/Publish
— branch, PR, deploy) do pipeline `wds-8` (`workflow-implement.md`/`workflow-test.md`/
`workflow-deploy.md`). Isto é reforçado em três camadas independentes, não uma promessa
solitária de prosa:

1. **Estrutural (já existente):** o Gerente já nunca executa código de produto
   (`frontend/**`/`backend/**`/`supabase/**`) — `[I]/[T]/[P]` do `wds-8` tocam
   exatamente essa superfície. A regra "Gerente nunca executa código" (seção "Quem você
   é") já barra isso por construção, mesmo sem este protocolo.
2. **Explícito neste protocolo (§7.7):** o modo (a) para no Design — nenhuma instrução
   deste documento leva o Gerente além disso.
3. **Não-objetivo do PRD (ideias/prd-05-wds.md § "Não-Objetivos"):** "Não usa o WDS como
   motor de implementação/teste — é lente; Implement/Test/Deploy são BMad." Se a
   decisão de design (modo (a)) revelar trabalho de código real
   necessário, isso vira um Ticket/decisão de `trilha` **normal** (`rapida`/`spec`/
   `epic`), dispatched pelo pipeline BMad já existente (`bagual-epic-runner`/
   `bmad-quick-dev`) — nunca pelo `workflow-implement.md` do `wds-8`. Os dois pipelines
   nunca se tocam.

Quando o dono roda `wds-8` interativamente (modo (b), §6.4), ele PODE ir até
`[I]/[T]/[P]` como qualquer humano ao teclado — isso não é "o fluxo autônomo fazendo
`[I]/[T]/[P]`", é o dono usando a ferramenta como sempre pôde. O guardrail é sobre o que
o **sistema autônomo** (Gerente + despachos) faz sozinho, nunca sobre o que o dono faz
interativamente.

## 9. Via leve (ii) segue autônoma — nunca toca wds-8

Nenhuma parte deste protocolo se aplica à **via (ii)** (`product-routing.md` §6) —
"regra pequena já decidida" registra a mudança como uma decisão-de-produto no Ledger
(`wiki/ledger/decisao-de-produto/`), que **nunca** invoca `wds-8` nem qualquer `wds-*`.
Continua 100% autônoma, sem gate, sem espera do dono.

Ela continua exatamente como era antes desta story — este protocolo não a toca.

## 10. Composição — nada reimplementado

- **Protocolo do Oráculo (E9.1)** — `gerente_oracle.py record-decision`/
  `set-ratification`: reaproveitado integralmente como o gate de (a) vs (b) (§5). Nenhum
  script/config novo.
- **`bagual-tickets`** — composição para mover o Ticket a `precisa-de-info` (§6) ou
  anotar a conclusão de (a) (§7.6). Nunca edite `board.yaml`/o `.md` do Ticket à mão.
- **Cérebro de Planejamento (E9.3)** — o padrão "in-thread para skill facilitador-only"
  já estabelecido é reaplicado ao `wds-8` (§7.1), não reinventado.
- **`write-snapshot --pending-json`/Briefing (E8.7)** — reaproveitado para surfaçar o
  parqueamento (b) ao dono, sem wiring novo.

## 11. Prova — nenhum caminho spawna `wds-8` headless

Verificável por grep, sempre que este protocolo for revisado: nenhuma instrução em
`.claude/agents/gerente-geral.md`, `project_controll/gerente/**`, ou qualquer
`gerente_*.py` contém uma chamada a `Skill(wds-8`/`Agent(...wds-8...)`/"invoque o
wds-8"/"spawn wds-8" fora do contexto explícito de "isto é proibido" (§2 acima). Ver
Dev Agent Record da Story E9.8 para os comandos exatos rodados e a saída confirmando
zero hits.

## 12. Exemplos trabalhados

Ver `ideias/sistema-artifacts/E9-8-wds8-in-thread-ou-dono.md` § Validação para os casos
completos: (1) Ticket via (i) com design novo → sem precedente → (b) default, `record-
decision` rebaixa para `low`, Ticket parqueado em `precisa-de-info`; (2) o MESMO Ticket
depois de um precedente ratificado existir → (a) gated, `high` honrado, A/S/D in-thread
sobre documentos-fixture, `[I]/[T]/[P]` nunca alcançado; (3) Ticket via (ii) → nunca toca
este protocolo; (4) grep de zero ocorrências de invocação headless do `wds-8`.
