---
title: "Roteamento de produto (E9.6) — definição operacional de 'alteração de produto' + 3 vias"
tipo: reference
created: 2026-07-12
status: living-document
source_prd: "ideias/prd-05-wds.md — FR-1/FR-1b (§4.1)"
source_epic: "ideias/epics.md — Epic E9"
source_story: "ideias/sistema-artifacts/E9-6-roteamento-produto.md"
---

# Roteamento de produto (E9.6)

Contrato canônico do sub-protocolo que `.claude/agents/gerente-geral.md` invoca dentro
da fase "priorizar" § "Decisão de escalados + reconciliação (E9.5)" — para CADA ticket
escalado, antes/junto de decidir a `trilha` via o Protocolo do Oráculo (E9.1), o Gerente
decide **se o ticket altera o produto** e, se sim, **por qual das 3 vias**. Leia este
documento por inteiro antes da primeira vez que o sub-passo disparar.

Este documento é **prosa/julgamento**, não mecânica — o único componente mecanizado é o
detector de toque na Coverage Matrix (`gerente_product_routing.py`, ver §5). A decisão
em si (altera ou não? qual via?) nunca ganha heurística fixa, mesma disciplina de
"gate de confiança nunca por sensação" (E9.1) e "promoção ao Ledger é julgamento" (E9.5)
— aqui, "classificar altera-produto/não-altera" e "escolher a via" são o julgamento.

## 1. A verdade de produto documentada (o âncora do teste)

Um ticket **altera o produto** se deixaria desatualizado algum dos três documentos
canônicos que o grounding em spec-time deriva:

| Documento | Path | O que ancora |
|---|---|---|
| Trigger Map | `_bmad-output/B-Trigger-Map/trigger-map.md` | Metas de negócio → personas → forças → mudanças de comportamento desejadas |
| Coverage Matrix / UX Scenarios | `_bmad-output/C-UX-Scenarios/00-ux-scenarios.md` | Cenários → páginas/telas → propósito de cada jornada |
| Decisões de produto | `_bmad-output/product-decisions.md` | Regras de comportamento já decididas/confirmadas, com "Cuidado:" marcando o que é intencional |

Nunca use nenhuma outra fonte como "verdade de produto" para este teste (não o código
em si, não a opinião do sub-agente que triou o ticket) — só estes três, e só o que
**neles** estaria desatualizado é que conta.

## 2. O teste de 3 perguntas (qualquer SIM ⇒ altera o produto)

1. **Comportamento/regra observável muda?** Nova capacidade, regra de negócio
   diferente, validação nova, passo adicionado/removido no fluxo.
2. **Fluxo/navegação muda?** Adiciona/remove/reordena tela, rota ou passo de jornada.
3. **Superfície visível com significado de produto muda?** Campo novo, estado novo,
   texto que carrega uma regra (não cosmético puro).

Uma mudança de comportamento **sem UI nenhuma** (ex.: "propostas podem ser reabertas
após recusadas") já é SIM na pergunta 1 — o gatilho é produto, não interface.

## 3. Exclusões duras (NÃOs — não roteiam, mesmo que pareçam mudança)

- **Refatoração com comportamento idêntico** (mesma entrada → mesma saída, só o
  código muda).
- **Performance sem mudança de comportamento observável.**
- **Bugfix que RESTAURA comportamento já documentado** — o doc já está certo, o código
  estava errado. *Exceção dentro da exceção:* se o bugfix revelar que o **documento**
  estava errado/ambíguo (o comportamento "correto" documentado não é o que o produto
  realmente deveria fazer), então ROTEIA — porque agora é o doc que precisa mudar.
- **Cosmético puro** (espaçamento/cor) que nenhum cenário afirma como regra.
- **Infra/tooling/test-only** (nada visível a um usuário/stakeholder).

## 4. Viés de segurança — na dúvida, ROTEIA

**Falso-negativo é pior que falso-positivo.** Se uma mudança de produto escapa do
roteamento, o doc fica velho e o grounding em spec-time (que deriva dele) fica **cego**
— quem consome esses docs não vai nem saber que deveria checar o comportamento novo. Um falso-positivo custa
esforço perdido (roteou à toa), mas o doc segue correto.

Logo: **na dúvida genuína, roteia** — limitado pelas exclusões duras da §3 (que
impedem "rotear tudo por precaução"). Dúvida genuína não é preguiça de aplicar o teste
— é ter aplicado as 3 perguntas + as exclusões e ainda não conseguir decidir com
confiança.

## 5. Regra dura — toque na Coverage Matrix SEMPRE força a via (i)

**Isto não é julgamento fino, é teste duro, sem exceção (PRD 05 FR-1b, "endurecido —
F19"):** se o ticket toca um cenário/página listado na Coverage Matrix
(`_bmad-output/C-UX-Scenarios/00-ux-scenarios.md`), a via é **sempre (i)** — nunca (ii).

**Por quê é mecânico e não fino:** a via (ii) (registrar a mudança como uma
decisão-de-produto no Ledger, `wiki/ledger/decisao-de-produto/`) é **contratualmente
read-only da design truth** — ela só cria uma Entrada de Ledger, nunca reescreve
`scenarios`/Coverage Matrix. Se um ticket toca um cenário e você
tentasse rotear via (ii) mesmo assim, a Coverage Matrix ficaria desatualizada por
CONSTRUÇÃO — a via (ii) não tem como corrigi-la. Por isso a fronteira é mecânica: tocou
página/cenário ⇒ via (i), sempre, sem "mas é uma mudança pequena" como escape.

**Detector mecânico (sinal, não decisor):**
```
python3 project_controll/gerente/scripts/gerente_product_routing.py check-coverage-touch \
  --touched "<termos separados por vírgula — páginas/área do ticket>"
```
Leia `area`/`## Locais afetados`/a descrição do ticket para extrair os termos (páginas,
telas, fluxos nomeados). `forced_route_i: true` (algum `matches`) força
mecanicamente a via (i) — não há espaço de julgamento aqui, é exatamente a regra desta
seção. **`forced_route_i: false` NÃO prova ausência de toque** — é só a ausência de um
match textual (o ticket pode descrever a mesma página com um nome diferente do da
Coverage Matrix, ou ser uma mudança de comportamento sem página nova — pergunta 1 do
teste de 3 perguntas). Um negativo do detector **nunca** dispensa aplicar o teste de 3
perguntas por julgamento antes de concluir "não altera produto" (via iii) — o detector
só adianta o caso fácil (positivo mecânico), nunca decide o caso difícil.

## 6. As 3 vias

| # | Situação | Ação | Produz |
|---|---|---|---|
| **(i)** | Altera produto **e** precisa de design (nova capacidade, cenário novo/mudado, redesenho de fluxo) **OU** toca uma página/cenário da Coverage Matrix (regra dura, §5) | `trilha: wds` no ticket (Pass `wds-8`, execução real é E9.8 — aqui só o roteamento) | Atualiza `scenarios` + `trigger-map` (quando o Pass rodar) |
| **(ii)** | Altera produto mas é **regra pequena já decidida** (sem design, sem tocar Coverage Matrix — só registrar a regra) | Registra a mudança como uma decisão-de-produto no Ledger (`wiki/ledger/decisao-de-produto/`, composição §7) — **ortogonal à `trilha`**, não é um valor do enum | Uma Entrada de Ledger `decisao-de-produto` |
| **(iii)** | **Não** altera produto (nenhuma pergunta da §2 é SIM, ou cai numa exclusão dura da §3) | Nenhuma manutenção de documento | — |

**Via (i) usa a `trilha` do ticket** — é o mesmo campo que o Protocolo do Oráculo
(E9.1) já decide para despacho (`rapida\|spec\|epic\|wds\|correct-course`); quando a via
(i) se aplica, a decisão de trilha É `wds` (não é uma segunda decisão paralela — a
classificação desta seção **é** o motivo de a trilha ser `wds`).

**Via (ii) é ortogonal** — a `trilha` do ticket continua sendo decidida normalmente
pelo Protocolo do Oráculo (pode ser `rapida`/`spec`/`epic`, o que a natureza REAL do
trabalho pedir), e o registro da decisão-de-produto no Ledger acontece como
uma AÇÃO ADICIONAL, "pegando carona" — nunca competindo com a trilha escolhida.

**Via (iii)** não muda nada neste sub-protocolo — a trilha segue sendo decidida
normalmente, sem nenhuma ação de manutenção de documento.

## 7. Caso combinado — via (i) DOMINA + enrich como efeito colateral

Uma mudança que toca **ambos** um cenário/página (§5) **e** bate/atualiza uma decisão
já registrada em `product-decisions.md` nunca dispara as duas vias em paralelo
desordenado. **Via (i) domina**: `trilha: wds` é a decisão de roteamento. O registro da
decisão-de-produto no Ledger (o que a via (ii) faria) acontece como **efeito colateral** do
mesmo ticket — não como uma segunda via independente, mas como parte do mesmo Pass
(quando `wds-8` rodar — E9.8) ou, se a regra em si já está clara antes do Pass, como um
registro adicional da decisão-de-produto no Ledger JUNTO com a marcação de `trilha: wds` (nunca
SUBSTITUINDO-a). O ponto é: **nunca conclua (ii) sozinho quando (i) também se aplica**
— a Coverage Matrix nunca fica órfã de uma atualização que ela precisava.

## 8. Composição — nada disto é reimplementado

- **Pass `wds-8`** (via i): composto como sub-agente. A execução real (`wds-8` não
  roda headless — oráculo in-thread OU espera o dono) é escopo de **E9.8**, não desta
  story/protocolo. Aqui, o resultado da classificação é só `trilha: wds` gravada no
  ticket via `bagual-tickets` — o mesmo mecanismo de commit que E9.5 já usa.
- **Registrar a mudança de produto como decisão-de-produto no Ledger** (via ii):
  registre a mudança como uma Entrada de Ledger `decisao-de-produto` em
  `wiki/ledger/decisao-de-produto/` (via o contrato `on_complete`,
  `wiki/ledger/on-complete-contract.md`), capturando o que mudou (antes→depois), onde
  (páginas/rotas, se determináveis), por quê (a justificativa do ticket) e se é
  bug-ou-não (o comportamento antigo vira bug se reaparecer, ou é só uma diferença
  aditiva). Ao concluir, registre no `## Log` do ticket o path da Entrada de Ledger
  produzida. *(O registro via QA-builder foi removido deste kit — a via (ii) agora
  registra direto no Ledger.)*
  - **Fronteira de composição, não um novo despacho de marcador.** Diferente do
    despacho primário do ticket (`gerente_dispatch.py open-dispatch`/`close-dispatch`,
    E8.4 — que existe para sobreviver a compactação de contexto/crash sobre o
    trabalho PRINCIPAL do ticket), este é um registro leve e IDEMPOTENTE: se a
    sessão morrer antes de a Entrada de Ledger ser gravada, o próximo ciclo
    simplesmente re-detecta o mesmo ticket (se ainda escalado/sem a nota no `## Log`)
    e tenta de novo — não há estado parcial perigoso a reconciliar (a Entrada de
    Ledger só é gravada de uma vez, no fim, nunca fica pela metade).
    Por isso, deliberadamente, **não** usamos o contrato de marcador em disco de E8.4
    para esta ação secundária — ver Review Findings da story para o trade-off
    documentado.
- **Detector de Coverage Matrix** (`gerente_product_routing.py`, §5): mecaniza só a
  sub-pergunta objetiva "bate texto com uma página?" — nunca decide sozinho a
  classificação altera/não-altera nem escolhe entre (ii)/(iii).

## 9. Fronteira com a triagem da `bagual-tickets` (o detector vs. o classificador)

A `bagual-tickets` (Triagem, `.claude/skills/bagual-tickets/SKILL.md` § "Checagem de
decisão de produto") já lê `product-decisions.md` e sinaliza se o pedido bate com algo
marcado como intencional — isso é o **detector**: "isso pode mexer no produto/colidir
com uma decisão registrada". Este protocolo (E9.6) é a **classificação + o
roteamento**: dado esse sinal (ou mesmo na ausência dele, aplicando o teste de 3
perguntas por conta própria), decide SE altera e POR QUAL via. Nunca sobrepõem — a
skill não escolhe via, o Gerente não reimplementa a checagem de `product-decisions.md`
que a skill já faz na triagem.

## 10. Exemplos trabalhados (worked examples)

Ver `ideias/sistema-artifacts/E9-6-roteamento-produto.md` § Validação para os 4 casos
completos (toque em Coverage Matrix → i; regra pequena já decidida → ii; refactor/
cosmético → iii; caso combinado → i domina + enrich) rodados de verdade contra o
detector e o documento de produto real.
