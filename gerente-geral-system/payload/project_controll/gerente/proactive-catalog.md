---
title: Catálogo de trabalho proativo do Gerente Geral — fila vazia
tipo: reference
created: 2026-07-11
status: living-document
source_prd: "ideias/prd-00-sistema-orquestrador.md — FR-3, UJ-4"
source_epic: "ideias/epics.md — Epic E8, Story E8.5"
source_story: "ideias/sistema-artifacts/E8-5-trabalho-proativo.md"
extends: ".claude/agents/gerente-geral.md"
---

# Catálogo de trabalho proativo — fila vazia

## O que é este documento

Quando o Gerente Geral (`.claude/agents/gerente-geral.md`) acorda e `project_controll/tickets/board.yaml`
não tem nenhum ticket em `pronto-para-implementar`, ele não fica ocioso — mas também não
inventa trabalho arbitrário. Este é o **catálogo restrito** (PRD 00 FR-3) de tarefas
proativas de **baixíssimo risco** que o Gerente pode escolher nesse momento. É restrito de
propósito: cada categoria abaixo é **somente-leitura/investigação** — nunca gera uma
mudança de código commitada diretamente. Todo achado vira um **Ticket rastreável**
(`origem: proativo`), nunca uma correção silenciosa.

Mecânica de rotação/teto/dedup: ver `project_controll/gerente/scripts/gerente_proactive.py`
(`next-task`/`dedup-check`/`record-proactive`) e a fase 2 (priorizar) de
`.claude/agents/gerente-geral.md`. Este documento é só o **conteúdo** do catálogo — a
mecânica de "quantas vezes por ciclo" e "como evitar redescobrir o mesmo achado" vive nos
scripts, não aqui.

## Regra de ouro — nunca commita código, só investiga e relata

Toda tarefa deste catálogo é despachada como um **sub-agente Sonnet somente-leitura**: ele
pode usar `Read`/`Grep`/`Glob`/`Bash` de leitura (ex.: `git log`, `grep`, rodar suíte de
testes existente para medir cobertura), mas **nunca** `Edit`/`Write` sobre código de
produto (`frontend/**`, `backend/**`, `supabase/**`) nem sobre skills `bmad-*`/`bagual-*`.
O único artefato de saída aceito é um **relatório de achados** (lista de findings, cada um
com título curto + descrição + evidência `arquivo:linha` quando aplicável) — nunca um
diff. O Gerente pega esse relatório e, para cada achado, roda o fluxo de dedup +
`bagual-tickets --headless` (ver "Como um achado vira Ticket" abaixo) — o sub-agente de
análise em si nunca chama `bagual-tickets` nem grava em `project_controll/tickets/`
diretamente (evita um segundo escritor concorrente do board).

Nenhuma categoria abaixo autoriza decidir uma questão de produto/comportamento ambígua —
se a investigação esbarra numa dessas (ex.: "isso parece um bug, mas pode ser intencional
por `product-decisions.md`"), o achado ainda vira Ticket, mas com `category: duvida` e a
suspeita registrada — nunca uma correção proposta como certeza.

## Categorias (mínimo 4, PRD 00 FR-3)

Rotação round-robin entre as 4 (`gerente_proactive.py next-task` decide a ordem — a lista
abaixo é a fonte de verdade do CONTEÚDO/guardrails de cada uma; a ordem de rotação em si é
um detalhe de implementação do script, não deste doc).

### 1. `analise-adversarial-feature` — Análise adversarial de uma feature

Escolha **uma** feature `[CLIENT]` já em produção (ver `AGENTS.md` § "Template features vs
Client features" — nunca uma feature `[TEMPLATE]`, que é mantida upstream) que não tenha
sido revisada adversarialmente recentemente (checar `_bmad-output/projects-history.md`
para a última menção). Leia o código-fonte da feature (não só a spec) e procure por bugs
reais: edge cases não tratados, validação ausente, estado inconsistente — o mesmo tipo de
achado que `/bmad-code-review` (Blind Hunter/Edge Case Hunter) já produz para código
recém-alterado, aqui aplicado a código **já estável**, sem diff recente para ancorar.
Cada bug real confirmado no código (nunca hipotético — cite `arquivo:linha`) vira um
achado `category: bug`.

### 2. `completude-de-testes` — Aumento de completude de testes

Escolha um módulo/feature com sinais de cobertura fraca (ex.: `grep` por arquivos de
código sem arquivo de teste correspondente, ou um fluxo crítico — pagamento, IDOR,
transição de estado — sem teste que o exercite). O achado não é "escrever o teste" (isso
seria código) — é um Ticket `category: chore` descrevendo o gap ("função X em
`arquivo.py` sem teste que cubra o branch Y") para que uma trilha normal
(`/bmad-quick-dev` ou `/bmad-testarch-*`) o feche depois.

### 3. `descoberta-de-padroes` — Descoberta de padrões a consolidar

Vasculhe `_bmad-output/anti-patterns.md`/`decisions.md` e o código-fonte em busca de um
padrão que se repete **≥2 vezes** de forma consistente mas ainda não foi consolidado (ex.:
a mesma lógica de validação copiada em 2+ lugares, um utilitário candidato a extração). O
achado vira Ticket `category: chore` propondo a consolidação — nunca a consolidação em si.

### 4. `refino-de-tickets` — Refino de tickets mal-elucidados

Releia tickets em `precisa-de-info` ou `triado` com descrição rasa em
`project_controll/tickets/board.yaml`. Investigue o código relacionado para preencher a
lacuna (confirmar se o bug existe, achar `arquivo:linha`, checar se bate com uma decisão
de produto já registrada). **Este é o único caso do catálogo que não necessariamente cria
um Ticket NOVO** — o resultado normalmente é enriquecer o Ticket já existente via a ação
"Triar" do `bagual-tickets` (mover pra `triado`, preencher `## Verificação`), composição
igual às demais. Se a investigação revela que o ticket antigo é, na verdade, dois
problemas distintos, aí sim pode gerar um Ticket adicional novo (`origem: proativo`) — mas
o caso comum é enriquecer, não duplicar.

## Como um achado vira Ticket (composição — nunca reimplementada aqui)

Para cada achado do relatório do sub-agente de análise:

1. `python3 project_controll/gerente/scripts/gerente_proactive.py dedup-check --root
   project_controll/gerente --tickets-dir project_controll/tickets --title "<título do
   achado>" --description "<descrição do achado>"` — varre o **histórico proativo
   completo**, incluindo `concluido`/`descartado` (a dimensão que `bagual-tickets` sozinho
   não cobre — ele só dedupa contra tickets abertos, ver `SKILL.md` § Adicionar, passo 2).
2. Se `"duplicate": true` — **não crie o Ticket**; registre no diário do ciclo
   (`gerente_state.py append-diario`) que o achado já é conhecido (aponte o
   `best_match.ticket_id`). Isto é exatamente o comportamento que o F24 exige: nunca
   re-arquivar os mesmos achados toda noite.
3. Se `"duplicate": false` — invoque a skill `bagual-tickets` em modo `--headless` para
   **Adicionar** (ou, no caso da categoria 4, **Triar**/**Resolver** sobre o ticket
   existente) — a skill roda seu próprio pipeline completo (raw-check, dedup contra
   tickets ABERTOS, checagem de `product-decisions.md`, verificação/expansão) por conta
   própria; não pule nem reimplemente esses passos aqui. Em modo headless, um ticket novo
   já nasce `origem: proativo` por padrão (ver `SKILL.md` § Headless Mode) — não é preciso
   passar o campo explicitamente.
4. Depois de processar TODOS os achados de uma iteração do catálogo, chame
   `gerente_proactive.py record-proactive` **uma única vez** (consome 1 unidade do teto
   por-ciclo — ver abaixo, "Unidade de custo").

## Teto duro por ciclo (F24) — o que conta como 1 unidade

O `cap_per_cycle` (configurável em `project_controll/gerente/proactive.config.json`,
default 3) limita quantas **iterações do catálogo** (não quantos Tickets) o Gerente roda
por ciclo — uma iteração é "escolher uma categoria (`next-task`) → despachar UM sub-agente
Sonnet de análise → processar os achados dele (dedup + Ticket, 0 a N achados possíveis) →
`record-proactive` uma vez". A unidade de custo real é o **despacho do sub-agente de
análise** (o que queima cota), não o número de Tickets que ele produz — uma análise que
não encontra nada ainda consumiu um despacho e conta como 1 unidade igual a uma que
encontrou 3 bugs. Ao atingir o teto, `next-task` retorna `"verdict": "cap-reached"` — o
Gerente para o trabalho proativo e segue para a fase "parar" do ciclo (relatando "parei
por teto proativo", não "parei por cota" — são guardrails distintos).
