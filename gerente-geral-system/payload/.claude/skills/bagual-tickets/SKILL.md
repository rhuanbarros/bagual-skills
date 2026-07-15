---
name: bagual-tickets
description: 'Loga, triagem e acompanha tickets de bugs/pedidos ad-hoc como um board leve. Use quando o usuário disser "criar ticket", "novo ticket", "ver o board de tickets", "triar tickets", "resolver ticket [id]", ou pedir pra registrar um bug/pedido para depois em vez de corrigir agora.'
---

# bagual-tickets

## Overview

Este skill loga, triagem e acompanha tickets de bugs e pedidos ad-hoc deste projeto como um board kanban leve, em `{project-root}/project_controll/tickets/`. Ao adicionar um ticket, checa se está minimamente claro, se não é duplicata de um já aberto, se não contradiz uma decisão de produto já registrada, e — para bugs — se o problema realmente existe no código e se o mesmo padrão aparece em outros pontos do projeto (expandindo o ticket em vez de criar duplicatas). Fora isso, é só board + triagem + mudança de status. **Não produz spec nem faz elicitação de requisito** — isso é trabalho de `/bmad-quick-dev`, `/bmad-spec` ou dos skills WDS; este skill recomenda qual deles chamar quando um ticket fica pronto pra implementação.

`Ticket` é um Documento-tipo de primeira classe da Wiki (`wiki/document-types.md` § `ticket`) — `board.yaml` é o índice nativo desse subtree, referenciado direto pelo índice-raiz da Wiki (`wiki/index.md`), sem `index.md` paralelo. `project_controll/tickets/` continua sendo o único local físico dos tickets (fora da árvore `wiki/`, decisão já tomada).

## On Activation

Load available config from `{project-root}/_bmad/config.yaml` and `{project-root}/_bmad/config.user.yaml` if present. Use sensible defaults for anything not configured. Escreva o conteúdo dos tickets em português, independente do que a config disser — é a língua real usada em `_bmad-output/` neste projeto.

`{tickets_dir}` = `{project-root}/project_controll/tickets/`
`{board_file}` = `{tickets_dir}/board.yaml`

Se `{tickets_dir}` não existir, crie-a na primeira ação que precisar gravar algo.

## Dispatch

A partir do pedido do usuário, identifique a ação: **Adicionar**, **Board**, **Triar**, ou **Resolver**. Se a invocação for explícita mas sem ação clara (ex: `/bagual-tickets` sozinho), mostre um menu curto com essas quatro opções e espere a escolha.

## Adicionar

0. **Fast-path para triviais (F22).** Antes de tudo, avalie se o pedido é **trivial**: cosmético ou obviamente correto (ex.: trocar cor/texto/espaçamento, ajuste óbvio de um valor, correção de typo) — nada que exija confirmar comportamento no código ou investigar impacto. Se for trivial: pule os passos 2-4 abaixo (dedup contra os tickets abertos, checagem de `product-decisions.md`, verificação `arquivo:linha` e busca de irmãos) e vá direto ao passo 5 com um **registro mínimo**: descrição do pedido + `## Log` anotando `fast-path trivial — verificação/dedup pulados`. Qualquer `bug`/`feature` real (qualquer coisa que exija confirmar no código ou tenha impacto não-óbvio) **sempre** passa pelo pipeline completo abaixo — a leveza é exclusiva de triviais, nunca vira desculpa para pular a verificação de um bug de verdade. Na dúvida entre trivial e real, trate como real (o pipeline pesado é o padrão; o fast-path é a exceção assumida).
1. **Raw-check.** Um ticket só é aceito com o mínimo: o quê (problema ou pedido, mesmo informal) e onde, aproximado (tela/componente/fluxo). Se faltar, faça 1-2 perguntas diretas — não é uma spec, é só o suficiente pra rotear. Em modo headless, não pergunte: preencha o que der com o payload recebido e registre toda suposição no `## Log` do ticket. Roda mesmo no fast-path — é o único passo que triviais não pulam.
2. **Duplicidade** (fora do fast-path). Compare com os tickets ainda abertos em `{board_file}` (status diferente de `concluido`/`descartado`). Se houver sobreposição plausível, ofereça unir as informações no ticket existente em vez de criar um novo.
3. **Checagem de decisão de produto** (fora do fast-path). Leia `{project-root}/_bmad-output/product-decisions.md`, principalmente as linhas `**Cuidado:**`. Se o problema relatado bater com algo lá marcado como intencional, avise o usuário antes de prosseguir — isso pode ser um comportamento decidido, não um bug.
4. **Verificação e expansão** (categoria bug, fora do fast-path). Confirme no código que o problema é real — cite arquivo:linha como evidência. Depois busque o mesmo padrão em outros pontos do projeto (ex: o mesmo componente reaproveitado em outras features). Se achar mais ocorrências, incorpore todas no mesmo ticket, marcando `expanded: true` e listando os locais — não crie um ticket por local.
5. Grave o ticket (ver Armazenamento) com status inicial `novo` ou `precisa-de-info`, e atualize `{board_file}`. Um trivial fast-path ainda vira ticket rastreável — "tudo é rastreável" continua valendo, só o pedágio de verificação some.

## Triar

Para um ticket em `novo` ou `precisa-de-info`: preencha categoria (`bug`/`feature`/`chore`/`duvida`), área afetada, e sugira prioridade `alta`/`media`/`baixa` — heurística: quebra um fluxo crítico do produto vs. cosmético, quantos locais a expansão encontrou, se está bloqueando outro trabalho. O usuário pode sobrescrever a sugestão.

**Flag `visivel_pro_cliente` (F21).** Categoria `bug`/`feature`: pergunte ao usuário se a resolução deste ticket deve aparecer no changelog do cliente (modo interativo). Categoria `chore`/`duvida`: `visivel_pro_cliente: false` por default, sem perguntar (mudança interna raramente é notícia de cliente) — o usuário pode sobrescrever. **Em modo headless, `bug`/`feature` nunca cai em `false` por omissão:** grave `visivel_pro_cliente: pendente` (sentinela) + registre no `## Log` a heurística aplicada (bug/feature user-facing → candidato a `true`, mas não confirmado) — quem resolve o `pendente` antes de qualquer changelog é a bibliotecária/Gerente (PRD 01 FR-12), nunca esta skill decidindo `true` por otimismo. `chore`/`duvida` headless seguem `false` direto, sem sentinela — a heurística já é segura o bastante para esses.

O campo `trilha` continua `null` ao final desta etapa — Triagem só define categoria/área/prioridade. A decisão de `trilha` (comitar o óbvio ou escalar o ambíguo) acontece só na transição para `pronto-para-implementar`, ver "Escalonamento de trilha (E9.4)" em Resolver — esta etapa nunca decide trilha sozinha.

**Sinal de design para a categoria `feature` (E9.4).** Enquanto ainda estiver em Triagem, se ficar **inequívoco** que a resolução exige uma tela/componente visual novo (não apenas lógica/dado) — ex.: o próprio pedido já descreve uma tela nova, um fluxo visual novo — grave `design_confirmado: true` no front-matter. É a única forma do escalonamento (ver Resolver) comitar `trilha: wds` sem escalar; nunca grave `true` por suposição/plausibilidade — na dúvida, deixe o default (`false`, campo pode ficar ausente) e o ticket escala normalmente quando chegar em `pronto-para-implementar`. Categoria `bug`/`chore`/`duvida` nunca preenche este campo.

Ao concluir a triagem com verificação feita, mova o status para `triado`.

## Board

Leia `{board_file}` e apresente os tickets agrupados por status (`novo`, `precisa-de-info`, `triado`, `pronto-para-implementar`, `em-implementacao`, `concluido`, `duplicado`, `descartado`), ordenados por prioridade dentro de cada grupo.

## Resolver

Atualize o status de um ticket (por id ou descrição).

**Escalonamento de trilha (E9.4, PRD 02 FR-5).** Ao mover um ticket para `pronto-para-implementar`, decida a `trilha` você mesma nos casos **inequívocos** — sem perguntar ao usuário, sem round-trip a um modelo mais caro, e **sem invocar nenhuma skill de implementação** (você só grava uma etiqueta; quem dispara o trabalho é sempre o Gerente ou o dono, nunca esta skill como efeito colateral). A decisão é deliberadamente conservadora: **na dúvida, sempre escale — nunca chute uma trilha**. Um erro de rota comitada é pior que um escalonamento a mais.

A classificação é **mecânica**, não uma leitura livre do texto: rode

```
python3 project_controll/tickets/scripts/classify_trilha.py --ticket {tickets_dir}/TCK-<id>-slug.md
```

e grave exatamente o que o script devolver — nunca substitua a decisão dele por um palpite próprio, mesmo que "pareça óbvio" de outra forma. O script aplica só duas regras estreitas (ver comentário no topo do arquivo para o detalhe completo):

- **Regra A → `trilha: rapida`:** `category: bug` + verificação confirmada (`Confirmado: sim`) ou fast-path trivial (F22) + `expanded: false` (um único local) + `## Checagem de decisão de produto` sem conflito.
- **Regra B → `trilha: wds`:** `category: feature` + `design_confirmado: true` (gravado na Triagem, ver acima) + `## Checagem de decisão de produto` sem conflito.
- **Qualquer outro caso → escala:** `chore`/`duvida`, bug expandido ou não verificado, feature sem `design_confirmado`, ou qualquer conflito/ausência de checagem de decisão de produto.

Aplique o resultado ao `.md` do ticket:
- **Trilha comitada** (`escalonar: false` no JSON devolvido): grave `trilha: <valor>` no front-matter; `escalonar` fica `false` (ou ausente — mesmo default). Anote no `## Log` a regra aplicada (ex.: "trilha `rapida` comitada pela skill — Regra A: bug confirmado, único local, sem conflito").
- **Escalado** (`escalonar: true`): `trilha` continua `null`; grave `escalonar: true` no front-matter **e** no `board.yaml` (campo do índice — o Gerente varre os escalados numa leitura só, sem abrir cada `.md`). Anote no `## Log` o motivo exato devolvido pelo script (nunca um genérico "ambíguo" — o script já entrega a razão específica). Até o Gerente/Oráculo existir (E9.5), um ticket escalado aguarda o dono decidir manualmente — não é um estado travado, é só "ainda sem decisão automática".

Depois de aplicar (comitada ou escalada), **sempre recomende** (nunca invoque) o skill certo pra seguir:

- `trilha: rapida` → `/bmad-quick-dev` (o próprio clarify dele cobre o resto)
- `trilha: spec` → `/bmad-spec` primeiro (ticket expandido em muitos locais, ou entrada bagunçada/multi-fonte — hoje só atribuída pelo Gerente/dono nos escalados, esta skill não comita `spec` sozinha)
- `trilha: wds` → skills WDS (Freya/Saga)
- `trilha: correct-course` → `/bmad-correct-course` (esbarrou numa decisão de produto registrada que precisa ser rediscutida — hoje só atribuída pelo Gerente/dono nos escalados)
- `trilha: epic` → `/bagual-epic-runner` (corpo de trabalho grande demais pra uma story só — hoje só atribuída pelo Gerente/dono nos escalados)
- escalado (`trilha` vazia + `escalonar: true`) → nenhuma recomendação de skill ainda; decisão pendente do Gerente/Oráculo (E9.5) ou do dono

Ao mover para `duplicado`, registre `duplicate_of` apontando pro ticket canônico.

**Fechamento com rastro de commit — não bloqueante (F4).** Ao mover um ticket para `concluido`: se já existir(em) commit(s) relacionado(s) — informado por quem chamou o Resolver, ou encontrado buscando o id do ticket no histórico do repositório (ex.: `git log --oneline -i --grep="<id-do-ticket>"`) — grave o(s) hash(es) numa seção `## Fechamento` no corpo do arquivo do ticket: um hash por linha, lista simples, sem resumo por commit (o resumo já vive na descrição/`## Log`). Se nenhum commit existir ou for encontrado, a transição para `concluido` acontece normalmente, **sem** `## Fechamento` — a ausência da seção nunca bloqueia o fechamento (trabalho solo direto na branch, sem PR). Ao mover para `descartado`, nunca registre commit — só a razão no `## Log`.

Fora do rastro de commit acima, ao mover para `concluido`/`descartado` deixe o ticket como está — não delete arquivos.

## Armazenamento

`{board_file}` — índice **derivado**: a fonte de verdade são os `.md` por-ticket (abaixo), não o `board.yaml`. Se o índice for perdido/corrompido, `board.yaml` é **reconstruível** rodando `project_controll/tickets/scripts/rebuild_board.py` (stdlib, ver Reconstrução do board abaixo) — nenhum dado real fica preso só no índice.

```yaml
tickets:
  TCK-001:
    title: "..."
    status: novo
    priority: alta
    category: bug
    area: clients
    expanded: false
    created: 2026-07-07
    updated: 2026-07-07
    origem: manual
    visivel_pro_cliente: false
    trilha: null
    escalonar: false
    ledger_refs: []
  TCK-20260711143512-9f2a:
    title: "..."
    status: novo
    priority: media
    category: feature
    area: proposals
    expanded: false
    created: 2026-07-11
    updated: 2026-07-11
    origem: proativo
    visivel_pro_cliente: pendente
    trilha: null
    escalonar: false
    ledger_refs: []
  TCK-20260711150000-a1b2:
    title: "..."
    status: pronto-para-implementar
    priority: alta
    category: bug
    area: proposals
    expanded: false
    created: 2026-07-11
    updated: 2026-07-11
    origem: manual
    visivel_pro_cliente: false
    trilha: rapida
    escalonar: false
    ledger_refs: []
  TCK-20260711150500-c3d4:
    title: "..."
    status: pronto-para-implementar
    priority: media
    category: feature
    area: simulation
    expanded: false
    created: 2026-07-11
    updated: 2026-07-11
    origem: manual
    visivel_pro_cliente: false
    trilha: null
    escalonar: true   # ambíguo — Gerente/Oráculo (E9.5) ou o dono decide; a skill nunca chuta
    ledger_refs: []
```

`next_id` (contador sequencial legado dos `TCK-NNN` mais antigos) **não é mais usado para gerar ids novos** — ids novos usam o esquema livre de colisão abaixo. O campo pode continuar aparecendo no `board.yaml` por compatibilidade (ex.: gerado pelo script de reconstrução), mas nunca leia-o nem incremente-o para decidir o próximo id.

`{tickets_dir}/TCK-<id>-slug.md` — um arquivo por ticket:

```markdown
---
id: TCK-001
title: "..."
status: novo
priority: alta
category: bug
area: clients
expanded: false
created: 2026-07-07
updated: 2026-07-07
origem: manual              # manual | proativo — default manual (headless default proativo, ver Headless Mode)
visivel_pro_cliente: false  # false | true | "pendente" — default false (ver Triar)
trilha: null                 # rapida | spec | epic | wds | correct-course | null — comitada pela skill nos casos óbvios, ou pelo Gerente/dono nos escalados (ver Resolver § Escalonamento de trilha)
escalonar: false             # true quando a trilha é ambígua e foi escalada (ver Resolver) — default false
design_confirmado: false     # só relevante p/ category:feature — true só quando a necessidade de design (tela/componente novo) já é inequívoca na Triagem (ver Triar); nunca inferido, sempre default false
ledger_refs: []               # lista de paths de Entradas de Ledger promovidas a partir deste ticket (ex.: ledger/decisao-tecnica/foo.md)
---

## Descrição
(relato original)

## Verificação
- Confirmado: sim | não | não verificado
- Evidência: arquivo:linha

## Locais afetados
(só se expanded: true — lista dos demais pontos com o mesmo padrão)

## Checagem de decisão de produto
(nenhum conflito encontrado, ou referência à entrada de product-decisions.md em conflito)

## Fechamento
(só quando existir commit no momento do fechamento — ver Resolver; lista simples de hashes, um por linha; ausente quando a resolução não envolveu código)

## Log
- 2026-07-07: criado
```

`created`/`updated` no front-matter do `.md` (novo a partir desta versão, F9) são o que permite ao `board.yaml` ser reconstruível sem depender só do índice — grave-os sempre ao criar/atualizar um ticket a partir de agora.

**Retrocompatibilidade (F9).** Os 26 tickets `TCK-001`..`TCK-026` já existentes não têm `origem`/`visivel_pro_cliente`/`trilha`/`escalonar`/`design_confirmado`/`ledger_refs`/`created`/`updated`/`## Fechamento` no `.md` — trate a ausência como `origem: manual`, `visivel_pro_cliente: false`, `trilha: null`, `escalonar: false`, `design_confirmado: false`, `ledger_refs: []`, sem `## Fechamento`; `created`/`updated` ausentes caem para a data de modificação do arquivo. **Nenhum desses 26 tickets precisa ser editado/migrado** — os campos novos só passam a ser gravados em tickets criados ou re-fechados a partir de agora. Nenhum campo novo é obrigatório na criação. `escalonar` default `false` para um ticket legado nunca é lido como "não escalado, decisão automática confirmada" — é só "esta story não existia quando o ticket foi resolvido"; não reabra nem reclassifique os 26 retroativamente.

**Geração de id — livre de colisão (F9).** Não leia/incremente mais um contador compartilhado (`next_id` lido-e-escrito por dois `create` em paralelo é uma corrida TOCTOU clássica: os dois leem o mesmo valor, um dos dois ids some). Gere o id novo como `TCK-<timestamp UTC compacto>-<sufixo aleatório curto>`, por exemplo `TCK-20260711143512-9f2a` — via `date -u +%Y%m%d%H%M%S` combinado com um sufixo hex curto, ou em um único comando:

```
python3 -c "import secrets,datetime;print('TCK-'+datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')+'-'+secrets.token_hex(2))"
```

Timestamp com resolução de segundo + sufixo aleatório nunca colide, mesmo em criação em lote (headless, ver E5.6) — não é preciso reler `{board_file}` para decidir o próximo id. IDs `TCK-NNN` sequenciais antigos continuam válidos para sempre; o esquema novo só vale para tickets criados a partir desta versão.

**Reconstrução do board (F9).** `{board_file}` é um índice derivado; os `.md` por-ticket são a fonte de verdade. Para reconstruí-lo do zero (índice perdido/corrompido, ou só para auditar consistência):

```
python3 project_controll/tickets/scripts/rebuild_board.py --tickets-dir project_controll/tickets --out project_controll/tickets/board.yaml
```

O script é stdlib puro, lê só os `.md`, nunca lê `{board_file}` em si, e escreve atomicamente (temp + fsync + rename). Use `--dry-run` para conferir o resultado sem escrever, e `--json` para saída máquina-legível. O campo `escalonar` (E9.4) é carregado no índice do mesmo jeito que os demais campos aditivos — reconstruível a partir do front-matter do `.md`, default `false` quando ausente.

## Headless Mode

Quando invocado com `--headless`/`-H`: pule toda confirmação (registre a suposição feita no `## Log` do ticket em vez de perguntar) e retorne apenas JSON, sem prosa.

**Origem e criação em lote (F9/E5.6).** Um ticket criado em modo headless recebe `origem: proativo` por padrão — a menos que o payload de entrada declare explicitamente `origem: manual` (ex.: uma importação em lote de itens que o próprio dono já escreveu em outro lugar, colados via automação). Um sub-agente/Gerente que encontra N problemas materializa N tickets invocando esta skill N vezes por composição, um achado por chamada — cada chamada roda o fluxo completo de Adicionar (raw-check/fast-path, dedup, checagem de produto, verificação) normalmente, só sem perguntas interativas; **nunca** reimplemente dedup/raw-check/checagem de decisão de produto fora desta skill para "ir mais rápido" em lote. IDs de chamadas em lote nunca colidem (esquema livre de colisão, ver Armazenamento). Nenhum achado de trabalho proativo vira correção silenciosa — ele sempre vira ticket rastreável primeiro.

```json
{
  "status": "complete",
  "action": "add | board | triage | resolve",
  "ticket_id": "TCK-001",
  "path": "{tickets_dir}/TCK-001-slug.md",
  "board_path": "{board_file}"
}
```

Em bloqueio (ex: raw-check falhou e não há payload suficiente pra inferir), troque `"complete"` por `"blocked"` e adicione `"reason"`.
