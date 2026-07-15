# Contrato de despacho via marcador em disco (Story E8.4)

Story E8.4 (`ideias/sistema-artifacts/E8-4-contrato-despacho.md`), PRD 00 FR-8 (+ lado
Sonnet do FR-7), `ideias/epics.md` Epic E8. Este documento é o contrato canônico da
interface pela qual o Gerente Geral (`.claude/agents/gerente-geral.md`, fases
"despachar"/"revisar") entrega **uma unidade de trabalho** (epic, multi-epic — quando o
supervisor do E10 existir —, ou Ticket avulso via `trilha: rapida|spec|correct-course`)
ao Orquestrador de Execução e recolhe o **resultado** de volta. Mesmo padrão de dispatch
file-mediated já provado em `_bmad/custom/bmad-code-review.toml` (Epic E2 — o "kill" do
deadlock do code-review): um arquivo de **payload** + um
**marcador de conclusão** vazio, escrito por último. Script: `scripts/gerente_dispatch.py`
(stdlib-only, `--help` em cada subcomando para a referência completa de flags).

## Por que marcador em disco, nunca valor de retorno

Um despacho de execução real (`bagual-epic-runner` de uma epic inteira, por exemplo) pode
levar muito tempo e atravessar uma **compactação de contexto** da sessão do Gerente no
meio do caminho — se o resultado só existisse como um valor de retorno da tool `Agent`
guardado na memória da conversa, ele desapareceria junto com o contexto compactado. O
contrato deste documento garante que o despacho é **reconstruível puramente a partir do
disco**: mesmo que a sessão do Gerente seja inteiramente perdida e reaberta do zero, uma
nova ativação consegue, olhando só para `project_controll/gerente/dispatches/` +
`estado-atual.yaml`, saber que despacho estava em voo, se terminou, e com qual resultado
— sem depender de nenhuma memória de conversa.

## Layout em disco

```
project_controll/gerente/dispatches/{dispatch_id}/
  request.yaml    # escrito por `open-dispatch` — a unidade, o(s) Ticket(s), a trilha,
                   # o worktree alvo, o skill mapeado, o modelo do executor.
  result.yaml     # escrito por `close-dispatch` — outcome, veredito, pendências,
                   # evidência (commit/story-file/etc).
  DONE.marker     # escrito por `close-dispatch` DEPOIS de result.yaml já estar
                   # DURÁVEL em disco — o sinal de conclusão.
```

`dispatch_id` por convenção: `dispatch-{YYYYMMDD-HHMMSS}-{hex8}` (gerado por
`open-dispatch` quando `--dispatch-id` não é passado explicitamente). Um `dispatch_id` é
**write-once**: `open-dispatch` recusa reabrir um id cujo `request.yaml` já existe (mesma
regra do E2.1 para `review_run_dir` — nunca reusar um diretório de run vivo/antigo);
`close-dispatch` recusa reescrever um `result.yaml`/`DONE.marker` já presentes, salvo
`--force` explícito (não recomendado — quebra a semântica write-once do marcador).

## Schema de `request.yaml`

```yaml
schema_version: 1
dispatch_id: dispatch-20260711-030500-8a5d03a0
opened_at: "2026-07-11T03:05:00-03:00"
cycle_id: cycle-20260711-030000
tickets:
  - TCK-1720670000-ab12
unit: epic-E8
trilha: epic
worktree: null
skill: bagual-epic-runner
model: sonnet
status: aberto
note: null
```

- `tickets` é **sempre lista** (mesmo para 1 Ticket só) — forward-compat direto com um
  despacho multi-epic/multi-Ticket do supervisor do E10, que este contrato **não**
  implementa (só não fecha a porta). Hoje (E8.1) a persona nunca despacha mais de um
  Ticket em paralelo — a lista tem sempre exatamente 1 item na prática atual.
- `unit`: identificador livre da unidade despachada (`epic-E8`, `ticket:TCK-123`, ou —
  quando o E10 existir — algo como `multi-epic:[E10,E11]`).
- `trilha`: um de `rapida|spec|epic|wds|correct-course` (glossário do PRD 00 §3), a mesma
  tabela trilha→skill já usada pela fase "despachar" de `gerente-geral.md`.
- `skill`: o nome da skill efetivamente invocada pelo sub-agente executor
  (`bagual-epic-runner`, `bmad-quick-dev`, `bmad-create-story`+`bmad-dev-story`,
  `bmad-correct-course`, ou o pipeline `wds-*` relevante).
- `model`: sempre `sonnet` por default (consolida o lado executor do FR-7 — "gerência em
  Opus, execução em Sonnet"). O campo existe para tornar o contrato auto-descritivo, não
  porque outro valor seja esperado hoje.

## Schema de `result.yaml`

```yaml
schema_version: 1
dispatch_id: dispatch-20260711-030500-8a5d03a0
closed_at: "2026-07-11T03:20:00-03:00"
outcome: sucesso
verdict: "epic E8 story E8-4 implementada, commit abc123"
pending_items:
  - ticket: TCK-1720670000-ab12
    note: "verificação final ainda não rodou"
evidence:
  commit: abc123
  story_file: ideias/sistema-artifacts/E8-4-contrato-despacho.md
closed_by: gerente-geral
```

- `outcome` ∈ `sucesso | falhou | pendencias` — nunca um booleano solto; `pendencias`
  existe especificamente para o caso "terminou mas ficou algo para resolver" (distinto de
  `falhou`, que é "não terminou/quebrou").
- `pending_items`: lista de `{ticket, note}` — o que falta, sempre associado a um Ticket
  quando possível, para a fase "revisar" saber exatamente o que registrar.
- `evidence`: objeto livre (hoje: `commit`, `story_file`; pode crescer aditivamente —
  `sprint_status_entry`, `pr_url`, etc. — sem quebrar leitores existentes, que só leem as
  chaves que conhecem).

## A garantia de ordem — o núcleo do contrato

`close-dispatch` executa, sempre nesta ordem, e nunca a inverte:

1. `write_atomic(result.yaml, ...)` — bloqueia até o arquivo estar **durável** (temp +
   flush + fsync + `os.replace`, a mesma primitiva de `_bmad/scripts/memlog.py` reusada
   por toda a Story E8.2).
2. **Só então** `write_atomic(DONE.marker, ...)`.

Consequência prática: **um leitor nunca deve observar `DONE.marker` sem um `result.yaml`
completo e válido atrás dele.** Se o processo que roda `close-dispatch` morrer entre os
passos 1 e 2 (ex.: a própria sessão do Gerente sendo interrompida no meio da chamada),
`DONE.marker` simplesmente nunca chega a existir — o despacho fica corretamente
detectável como **órfão** (ver § Detecção de órfão abaixo), nunca como um falso-sucesso
com resultado incompleto. `read-result` também se defende do caso teoricamente
impossível-mas-verificado (`DONE.marker` presente e `result.yaml` ausente/ilegível por
alguma corrupção externa) tratando-o explicitamente como inconsistente — nunca como
sucesso silencioso.

## Detecção DUAL de conclusão (mesma lição do E2.2/F5)

Migrar o transporte do resultado para arquivo + marcador **não é, por si só, suficiente**
— a lição do E2.2 (documentada em `_bmad/custom/bmad-code-review.toml`) é que a raiz do
problema nunca é *onde* o resultado é escrito, é *como quem despachou sabe que o
despachado terminou*. Confiar só em `DONE.marker` (um loop que fica re-checando o disco
até o arquivo aparecer) trocaria um deadlock por um HANG silencioso: se o sub-agente
executor morre antes de chamar `close-dispatch`, nenhum poll no disco jamais termina.

Por isso, a detecção de conclusão de um despacho combina DOIS sinais, nesta ordem, nunca
intercambiáveis:

1. **PRIMÁRIO / bloqueante — o retorno da própria tool `Agent`.** A persona
   (`gerente-geral.md`, fase "despachar") spawna o sub-agente executor em **foreground**
   (aguarda o retorno da chamada `Agent`, não `run_in_background` sem um plano explícito
   de esperar por ele depois). Esse retorno — sucesso, falha, timeout, ou morte do
   sub-agente — é o sinal que SEMPRE resolve, por construção do harness (não há nada para
   fazer poll: a própria chamada de tool é o mecanismo de espera). É este sinal que
   detecta um executor morto mesmo que ele nunca tenha chegado perto de
   `close-dispatch`.
2. **SECUNDÁRIO / payload — o `DONE.marker`, checado SÓ depois que (1) já disse que o
   Agent tool retornou.** Neste ponto, e só neste ponto, `read-result` é chamado: se
   `done: true`, o `result.yaml` é o payload confiável (por causa da garantia de ordem
   acima). Se o Agent tool retornou mas `done: false` (marcador ausente) — o caso "o
   sub-agente disse que terminou, mas nunca chamou `close-dispatch`" — isso é tratado
   **exatamente como uma falha**: a persona chama `reconcile-orphan-dispatch` para
   diagnóstico e o Ticket vai para um estado explícito (ver § Ticket nunca fica
   "concluido" silencioso), nunca é assumido como sucesso.

`DONE.marker` nunca é, sob nenhuma circunstância, usado como sinal único ou
checado-primeiro — e a persona nunca entra num loop que re-checa o disco esperando o
marcador aparecer na ausência de um retorno do Agent tool. Esse é exatamente o padrão de
hang que esta seção existe para excluir (mesma frase de guarda do E2.2, aplicada aqui ao
despacho de execução em vez das 3 camadas do code-review).

### Regra E19.1 — o executor resolve em UM turno foreground; nada de sub-árvore `idle` em voo

O contrato acima assume que o retorno do Agent tool (sinal PRIMÁRIO) **sempre resolve
limpo** — sucesso, falha ou morte. O primeiro ciclo ao vivo (`cycle-20260713-202850`,
despacho do Epic 38) expôs um terceiro caso que quebra essa premissa: o executor spawnava
um sub-fluxo que, por design, confirma por **marcadores em disco** e não bloqueia pelo
retorno — e essa sub-árvore ia **quiescente**, fazendo o turno do executor voltar `idle`
(nem sucesso nem falha, `done: false`) em vez de alcançar `close-dispatch`. O Gerente precisou de 3 hops de
retomada e corte manual; a cota queimou invisível porque `close-dispatch --tokens-used` (a
contabilização mecânica) é justamente a chamada que nunca aconteceu.

Regra normativa, herdada por qualquer skill despachada:

1. **Um executor despachado alcança `close-dispatch` como sua ÚLTIMA ação foreground, no
   MESMO turno.** É proibido um executor terminar seu turno deixando uma sub-árvore
   background/idle em voo. Se ele spawna qualquer gate ou sub-fluxo que confirma por
   marcador (um sub-fluxo de execução confirmado por marcador é o caso canônico), esse
   gate **tem que resolver a um veredito
   terminal in-turn** (bloquear até o marcador de veredito existir no disco) **antes** do
   executor retornar — nunca "ainda explorando", nunca `run_in_background` sem o executor
   esperar por ele no mesmo turno.
2. **Um turno de executor que volta `idle`/sem-veredito é tratado como falha**, idêntico ao
   caso `done: false` de (2) acima: `reconcile-orphan-dispatch` + Ticket em estado explícito,
   nunca assumido sucesso, nunca um loop de re-hop babysitando a árvore.
3. A aplicação mecânica desta regra vive na camada de execução: qualquer skill despachada
   que spawne um sub-fluxo confirmado por marcador deve fazê-lo em foreground e guardar
   "sem veredito → HALT" (bloquear até o marcador terminal existir no disco, nunca retornar
   idle). Este contrato é a declaração normativa que esses edits fazem cumprir.
   Complementarmente, a Story E19.2 fecha a janela de cota invisível
   mesmo que um despacho ainda escape órfão (estimativa de despacho in-flight no
   `gerente_quota.py check`).

## Integração com `estado-atual.yaml` (E8.2) — quem é dono de quê

`gerente_dispatch.py` **nunca** escreve `estado-atual.yaml` diretamente — o único dono do
arquivo inteiro continua sendo `gerente_state.py write-snapshot` (mesma decisão já tomada
para `quota-ciclo.json` na Story E8.3, documentada em `decisions.md`: dois escritores do
mesmo arquivo inteiro é fonte real de bugs de lost-update, porque `write-snapshot`
reescreve o documento inteiro a cada chamada, não faz append incremental).

Em vez disso:

1. `open-dispatch` devolve um `dispatch_entry` (JSON) — exatamente o formato que o campo
   `dispatches[]` de `estado-atual.yaml` já espera (`{ticket, unit, trilha, worktree,
   status, started_at}`, ver README.md § Schema) **mais** o campo novo `dispatch_id`
   (aditivo, sem bump de `schema_version`). A persona inclui esse objeto no PRÓXIMO
   `write-snapshot --dispatches-json` (que já ia rodar de qualquer forma).
2. **`dispatch_entry` deliberadamente NÃO inclui a lista completa `tickets`** — achado
   real de auto-revisão desta story: o mini-serializer YAML de `estado-atual.yaml`
   (`dump_estado`/`dump_flat_dict_item`) só suporta dict-de-escalares em **1 nível**; uma
   lista aninhada dentro de um item de `dispatches[]` seria serializada incorretamente
   como a *string* `"['TCK-1']"` em vez de uma lista de verdade (reproduzido e corrigido
   nesta story — ver Change Log). A lista completa de tickets já vive, autoritativa, em
   `request.yaml`; `estado-atual.yaml` carrega só `ticket` (singular, primário, para
   leitura humana rápida) + `dispatch_id` (o ponteiro).
3. `gerente_state.py::reconcile` (E8.2) foi ESTENDIDO nesta story: para cada despacho do
   retrato que carrega `dispatch_id`, ele (a) resolve a lista completa de tickets lendo
   `dispatches/{dispatch_id}/request.yaml` quando disponível (preferindo-a à `tickets`/
   `ticket` do retrato, que pode estar desatualizado) e (b) checa se
   `dispatches/{dispatch_id}/DONE.marker` existe — sua ausência vira mais um motivo de
   órfão na lista `orphans[].reasons`, lado a lado com o cruzamento pré-existente contra
   `board.yaml`/worktree. Os dois mecanismos (crash-recovery de E8.2, marcador de E8.4)
   **convergem no mesmo `reconcile`**, não são caminhos paralelos divergentes.

## Ticket nunca fica `concluido` silencioso num despacho que falha

Quando um despacho fecha com `outcome: falhou` ou `outcome: pendencias`, ou quando é
detectado como órfão (sem `DONE.marker`), a fase "revisar" de `gerente-geral.md` **nunca**
invoca `bagual-tickets` para marcar o Ticket como `concluido`. Em vez disso:

- `outcome: falhou` → Ticket volta para `triado` (com nota do motivo) ou
  `precisa-de-info` (se o bloqueio for de informação), via `bagual-tickets` — nunca
  editando `board.yaml` à mão.
- `outcome: pendencias` → Ticket permanece num estado que reflita "quase lá" (ex.: mantém
  `em-implementacao` só se há uma continuação clara já planejada no próximo ciclo, ou
  `triado` com os `pending_items` anotados) — a decisão exata é da persona, mas
  `concluido` está sempre fora de questão até os `pending_items` serem resolvidos.
- Despacho órfão (sem `DONE.marker`, `reconcile-orphan-dispatch` ou `reconcile` de E8.2
  reportando) → mesmo tratamento de `falhou`: o Ticket vai para um estado explícito,
  nunca fica preso em `em-implementacao` esquecido nem é promovido a `concluido` por
  suposição.

## Forward-compat com o supervisor multi-epic (E10) — o que este contrato NÃO faz

Esta story entrega o contrato para o Orquestrador de Execução **sequencial de hoje**
(`bagual-epic-runner` single-epic, `workflow.md`/`story-processor.md`) — o supervisor
multi-epic real (PRD 03, Epic E10: grafo por disjunção de arquivos, sequenciamento por
dependência, isolamento de falha por Track) **não existe ainda**. O contrato foi
desenhado para não precisar mudar quando o E10 chegar:

- `tickets` já é lista (não um singular hardcoded) — um despacho multi-epic do E10 só
  precisa passar mais de um item em `--tickets-json`; nenhuma migração de schema.
- `unit` é uma string livre — já hoje aceita `epic-E8`; o E10 pode passar
  `multi-epic:[E10,E11]` ou uma representação de grafo sem quebrar o parser (que não
  interpreta `unit`, só a propaga).
- Um `dispatch_id` por unidade despachada generaliza sem mudança para "vários despachos
  em voo simultaneamente" — `list-inflight`/`reconcile-orphan-dispatch` já operam por
  `dispatch_id` individual, não assumem que existe só um despacho por vez (a restrição de
  "nunca mais de um Ticket em paralelo" é uma regra da PERSONA em E8.1, não deste
  contrato — o E10 remove essa regra na camada de cima, não neste script).
- **O que o E10 PRECISA adicionar** (fora de escopo aqui, nomeado para não ser
  reimplementado cedo demais): paralelismo real de execução (spawns concorrentes, não só
  o schema aceitando múltiplos tickets), isolamento de falha por Track (um despacho
  falhar não deve travar os outros), e possivelmente um `close-dispatch` parcial (um
  Track concluído dentro de um despacho multi-epic maior ainda em voo) — este contrato
  hoje só modela "aberto" → "um único fechamento terminal", não fechamentos parciais.

## Achados de auto-revisão adversarial (corrigidos nesta story)

- **Gap de compactação entre `open-dispatch` e o `write-snapshot` seguinte** — o achado
  mais importante desta story. `gerente_state.py::reconcile` (E8.2) só enxerga despachos
  já gravados no array `dispatches` de `estado-atual.yaml`. Se uma compactação de contexto
  acontecer exatamente entre `open-dispatch` (que só escreve `request.yaml`) e o
  `write-snapshot --dispatches-json` seguinte (que registraria o `dispatch_entry`), o
  despacho fica com `request.yaml` em disco e sem `DONE.marker`, mas `reconcile` reporta
  `needs_attention: false` — um falso-negativo real, reproduzido e confirmado em
  `test_gerente_dispatch.py` [11a]. **Corrigido** fiando `gerente_dispatch.py
  list-inflight` (que varre `dispatches/` diretamente, sem depender de
  `estado-atual.yaml`) como checagem INCONDICIONAL na Ativação de `gerente-geral.md`
  (passo 0, sempre, mesmo quando `detect-crash` não acendeu) — ver `test_gerente_dispatch.py`
  [11b] provando que `list-inflight` encontra o mesmo despacho que `reconcile` sozinho
  perdeu. Isto é o que torna o contrato **reconstruível puramente do disco de verdade**
  (não só na maioria dos casos) — sem essa checagem incondicional, um despacho aberto e
  imediatamente seguido de uma compactação ficaria invisível a QUALQUER mecanismo de
  recuperação, o oposto do que a story pede.
- **`dispatch_id` como componente de path sem validação (risco de path traversal)** — um
  `--dispatch-id` explícito malformado (ex.: `../../etc`) seria usado diretamente para
  construir `root / "dispatches" / dispatch_id`, podendo escapar do diretório pretendido.
  O id AUTO-GERADO é seguro por construção (`dispatch-{timestamp}-{hex8}`), mas o caminho
  de override explícito (usado por retomadas/testes) não era validado. **Corrigido**:
  `_validate_dispatch_id` (regex `^[A-Za-z0-9_.-]+$` + rejeição explícita de `.`/`..`,
  que passariam pela classe de caracteres) é chamado no início de `open-dispatch`,
  `close-dispatch`, `read-result` e `reconcile-orphan-dispatch` — provado em
  `test_gerente_dispatch.py` [10a]-[10e].
- **Round-trip de lista de escalares puros em `parse_estado`** — bug pré-existente em
  `gerente_state.py` (E8.2), nunca antes exercitado porque nenhum schema anterior a E8.4
  usava uma lista de escalares puros (`tickets: [- TCK-1]`) dentro do mini-YAML —
  `parse_estado` tratava TODO item de lista como dict, produzindo `[{"TCK-1": None}]` em
  vez de `["TCK-1"]`. **Corrigido** em `gerente_state.py::parse_estado` (decide
  dict-list vs. escalar-list pelo primeiro item do bloco, olhando se tem a forma
  `identificador-bare: valor`) — ver `test_gerente_dispatch.py` [2a] e a regressão
  completa de `test_gerente_state.py` (28/28 continua verde).
- **Lista aninhada dentro de um item de `dispatches[]` de `estado-atual.yaml`** —
  descoberto ao tentar incluir `tickets` (lista) no `dispatch_entry` devolvido por
  `open-dispatch`: o serializador (`dump_estado`/`dump_flat_dict_item`) só suporta
  dict-de-escalares em 1 nível; uma lista aninhada virava a string literal
  `"['TCK-1']"`. **Corrigido** removendo `tickets` do `dispatch_entry` (a lista completa
  já vive em `request.yaml`; `estado-atual.yaml` carrega só `ticket` singular +
  `dispatch_id` como ponteiro) — ver § Integração acima.
- **Ordem result-antes-de-DONE** — verificada não só por leitura de código (duas chamadas
  `write_atomic` sequenciais, cada uma bloqueante até o próprio rename atômico) mas por
  comparação real de `mtime_ns` dos dois arquivos em disco (`test_gerente_dispatch.py`
  [3d]).
- **Concern residual, aceito sem correção**: `estado-atual.yaml` continua sem validar o
  valor de `dispatch_id` (ou qualquer outro campo) quando embutido via
  `write-snapshot --dispatches-json` pela persona — mesmo nível de confiança já aplicado
  a todos os outros campos desse array (`ticket`, `worktree`, etc.) desde E8.2. Não é um
  vetor de risco real neste sistema (agente único confiável operando localmente, não uma
  superfície adversarial de rede) — validar ali seria escopo maior que esta story e
  inconsistente com o modelo de confiança já estabelecido no resto do módulo.

## Referência de CLI

```
python3 project_controll/gerente/scripts/gerente_dispatch.py open-dispatch \
  --root project_controll/gerente [--dispatch-id ID] --cycle-id ID \
  --tickets-json '["TCK-123"]' --unit epic-E8 --trilha rapida|spec|epic|wds|correct-course \
  [--worktree PATH] --skill bagual-epic-runner [--model sonnet] [--note STR]

python3 project_controll/gerente/scripts/gerente_dispatch.py close-dispatch \
  --root project_controll/gerente --dispatch-id ID --outcome sucesso|falhou|pendencias \
  --verdict STR [--pending-json '[{"ticket":"TCK-1","note":"..."}]'] \
  [--evidence-json '{"commit":"...","story_file":"..."}'] [--closed-by STR] [--force]

python3 project_controll/gerente/scripts/gerente_dispatch.py read-result \
  --root project_controll/gerente --dispatch-id ID

python3 project_controll/gerente/scripts/gerente_dispatch.py list-inflight \
  --root project_controll/gerente [--cycle-id ID]

python3 project_controll/gerente/scripts/gerente_dispatch.py reconcile-orphan-dispatch \
  --root project_controll/gerente --dispatch-id ID [--board-path PATH]
```

## Como a persona usa isto (ver `.claude/agents/gerente-geral.md` fases 3-4)

**Fase "despachar":**
1. `open-dispatch` com a `trilha`/Ticket(s) escolhidos na fase "priorizar" → guarda
   `dispatch_id` e `dispatch_entry_json`.
2. Chama `write-snapshot --dispatches-json '[...]'` incluindo o `dispatch_entry` recém
   aberto (junto com quaisquer outros despachos ainda em voo do mesmo ciclo).
3. Spawna a tool `Agent` (**`model: "sonnet"`**, sempre em **foreground** — aguarda o
   retorno) com um prompt que instrui o sub-agente a: (a) invocar a skill mapeada pela
   `trilha` (mesma tabela trilha→skill já documentada em `gerente-geral.md`), passando o
   conteúdo do Ticket; e (b) como ÚLTIMA ação, chamar `close-dispatch` com o
   `--dispatch-id` deste despacho e o outcome real observado.

**Fase "revisar":**
4. O retorno do Agent tool (sucesso/falha/timeout) já chegou — sinal PRIMÁRIO.
5. `read-result --dispatch-id ID`. Se `done: true`, usa `result.yaml` como a verdade
   (outcome/verdict/pending_items/evidence). Se `done: false` apesar do Agent tool ter
   retornado, chama `reconcile-orphan-dispatch --dispatch-id ID` para diagnóstico e trata
   como despacho falho.
6. Registra o Ticket no estado observado (nunca `concluido` num despacho `falhou`/
   `pendencias`/órfão — ver seção acima), via `bagual-tickets`.
