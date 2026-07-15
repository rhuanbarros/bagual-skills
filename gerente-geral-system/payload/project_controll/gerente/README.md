# `project_controll/gerente/` — Estado operacional persistente do Gerente Geral

Story E8.2 (`ideias/sistema-artifacts/E8-2-estado-operacional.md`), PRD 00 FR-11 (§4.8),
`ideias/epics.md` Epic E8. Materializa a consciência situacional que a persona
`.claude/agents/gerente-geral.md` (Story E8.1) lê **antes de decidir qualquer coisa** ao
ser ativada. Este documento é o contrato canônico do schema/CLI — a persona e stories
futuras (E8.5-E8.7-E8.8, o oráculo de E9) devem tratá-lo como fonte de verdade, não
duplicar o schema em prosa em outro lugar. A partir da Story E8.3, este README também é o
contrato canônico do guardrail de cota (`gerente_quota.py`) — ver § Cota (E8.3) abaixo. A
partir da Story E8.4, o contrato de despacho via marcador em disco (o que o Gerente
entrega ao Orquestrador de Execução e como recolhe o resultado) tem contrato PRÓPRIO em
`dispatch-contract.md` (não duplicado aqui) — ver § Despacho (E8.4) abaixo para o
ponteiro + o resumo do que integra com este arquivo.

## O que vive aqui

| Arquivo | Papel | Escrito por |
|---|---|---|
| `estado-atual.yaml` | Retrato do CICLO ATUAL — **sobrescrito** a cada ciclo, nunca histórico | `gerente_state.py write-snapshot` |
| `estado-atual.example.yaml` | Exemplo documentado do schema (não é estado real, sempre presente no repo) | mantido manualmente |
| `diario.md` | Diário append-only, legível por humano — mesma filosofia flat-log de `_bmad/scripts/memlog.py` | `gerente_state.py append-diario` |
| `diario.jsonl` | Espelho JSON-lines do mesmo diário, para reconciliação mecânica (detect-crash) | `gerente_state.py append-diario` |
| `.lock/` | Lock singleton (diretório, não arquivo — ver §Lock) | `gerente_state.py acquire-lock` |
| `quota-ciclo.json` | Auto-rastreio do CICLO ATUAL (Story E8.3) — acumulador de tokens estimados, **sobrescrito**/resetado a cada `--cycle-id` novo | `gerente_quota.py record-usage` (residual: turno-Opus avulso) **ou** `gerente_dispatch.py close-dispatch --tokens-used` (Story E15.2 — caminho mecanizado, todo despacho) |
| `quota.config.json` | Config commitada do guardrail de cota (limiar, orçamento de auto-rastreio, multiplicador) — editável pelo dono | mantido manualmente |
| `dispatches/{dispatch_id}/request.yaml` | Despacho ABERTO (Story E8.4) — unidade, Ticket(s), trilha, worktree, skill, modelo | `gerente_dispatch.py open-dispatch` |
| `dispatches/{dispatch_id}/result.yaml` | Resultado do despacho (Story E8.4) — outcome/veredito/pendências/evidência, escrito ANTES do marcador | `gerente_dispatch.py close-dispatch` |
| `dispatches/{dispatch_id}/DONE.marker` | Marcador de conclusão vazio (Story E8.4) — escrito por ÚLTIMO, só depois de `result.yaml` durável | `gerente_dispatch.py close-dispatch` |
| `dispatch-contract.md` | Contrato canônico do despacho via marcador em disco (Story E8.4) — schema completo, garantia de ordem, detecção dual, forward-compat E10 | mantido manualmente |
| `proactive-catalog.md` | Catálogo restrito de trabalho proativo (Story E8.5) — conteúdo/guardrails das 4 categorias (fila vazia) | mantido manualmente |
| `proactive-ciclo.json` | Acumulador de iterações do catálogo consumidas no CICLO ATUAL (Story E8.5) — **sobrescrito**/resetado a cada `--cycle-id` novo | `gerente_proactive.py record-proactive` |
| `proactive.config.json` | Config commitada do teto duro + limiar de dedup do trabalho proativo (Story E8.5) — editável pelo dono | mantido manualmente |
| `scripts/gerente_state.py` | CLI stdlib-only com todos os subcomandos de estado operacional | — |
| `scripts/gerente_quota.py` | CLI stdlib-only do guardrail de cota (Story E8.3) | — |
| `scripts/gerente_dispatch.py` | CLI stdlib-only do contrato de despacho (Story E8.4) | — |
| `scripts/gerente_proactive.py` | CLI stdlib-only do trabalho proativo — teto duro + dedup histórico (Story E8.5) | — |
| `scripts/gerente_oracle.py` | CLI stdlib-only do Protocolo do Oráculo (Story E9.1) — `record-decision`/`list-pending`/`set-ratification`; escreve/muta Entradas de Ledger `oracle: true` sob `wiki/ledger/`, fora desta pasta (ver § Oráculo (E9.1) abaixo). Desde a Story E9.2, `record-decision` também aplica o gate history-aware (§ Aprendizado de estilo (E9.2) abaixo) | — |
| `scripts/gerente_style.py` | CLI stdlib-only do Aprendizado de Estilo (Story E9.2) — `consult-precedent` (consulta pura, nunca grava)/`sm2` (SM-2 derivado do rastro real); importa `gerente_oracle.py` por reuso direto (ver § Aprendizado de estilo (E9.2) abaixo) | — |
| `oracle.config.json` | Config commitada do limiar de suporte/contradição do gate history-aware, POR CATEGORIA de decisão (`decisao-tecnica`/`decisao-de-produto`/`decisao-de-arquitetura`) — editável pelo dono | mantido manualmente |
| `scripts/test_gerente_state.py` | Suíte de provas reais (subprocessos concorrentes) dos invariantes de E8.2 | — |
| `scripts/test_gerente_quota.py` | Suíte de provas reais (subprocessos) dos invariantes de E8.3 | — |
| `scripts/test_gerente_dispatch.py` | Suíte de provas reais (subprocessos) dos invariantes de E8.4, incluindo integração ponta-a-ponta com `detect-crash`/`reconcile` de E8.2 | — |
| `scripts/test_gerente_proactive.py` | Suíte de provas reais (subprocessos) dos invariantes de E8.5, contra fixtures reais em `ideias/sistema-artifacts/fixtures/E8/proactive-tickets/` | — |
| `scripts/test_gerente_oracle.py` | Suíte de provas reais (subprocessos, incluindo concorrência real via `ThreadPoolExecutor`) dos invariantes de E9.1, contra fixtures reais em `ideias/sistema-artifacts/fixtures/E9/` — 68 asserções | — |
| `scripts/test_gerente_style.py` | Suíte de provas reais (subprocessos) dos invariantes de E9.2 — consulta de precedente, down-weight por decisão corrigida, limiar por categoria (incluindo `--oracle-config` custom), SM-2 derivado do rastro real — 52 asserções | — |

**`estado-atual.yaml`, `diario.md`, `diario.jsonl`, `.lock/`, `quota-ciclo.json`,
`proactive-ciclo.json` e `dispatches/` não são commitados em repouso** — só existem em
disco durante/depois de um ciclo real. Antes do primeiro ciclo de sempre, a ausência deles
é esperada e é exatamente o caminho de degradação graciosa que
`.claude/agents/gerente-geral.md` § Ativação já documenta — não é erro, e nenhuma story
deve criá-los preventivamente "só para não aparecerem ausentes". `quota.config.json`,
`proactive.config.json`, `proactive-catalog.md`, `estado-atual.example.yaml`,
`dispatch-contract.md` e `oracle.config.json` são a exceção — são CONFIG/doc/CONTRATO,
não estado de ciclo, e por isso **são** commitados.

## Schema de `estado-atual.yaml`

Ver `estado-atual.example.yaml` para um exemplo completo. Campos de topo:

| Campo | Tipo | Descrição |
|---|---|---|
| `schema_version` | int | Versão do schema (hoje `1`) |
| `written_at` | ISO8601 | Timestamp da própria escrita (diagnóstico) |
| `marker` | `start` \| `end` | **O campo-chave da recuperação de crash (F23).** `start` = escrito no início do ciclo (otimista); `end` = escrito no fim (confirmado). Um `marker: start` sobrevivente no wake seguinte, junto com um `CICLO-INICIO` sem `CICLO-FIM` correspondente no diário, é o sinal de crash. |
| `cycle.id` | string | Identificador do ciclo (`cycle-YYYYMMDD-HHMMSS` por convenção — não enforçado mecanicamente, só uma convenção de legibilidade) |
| `cycle.started_at` / `cycle.ended_at` | ISO8601 \| null | `ended_at` só é não-nulo em `marker: end` |
| `cycle.phase` | string | Uma das 6 fases do loop (`ler-estado\|priorizar\|despachar\|revisar\|registrar\|parar`) — a fase em que o retrato foi tirado |
| `cycle.stop_reason` | `cota\|fila-vazia\|bloqueio` \| null | Só preenchido em `marker: end` |
| `dispatches` | lista de objetos | Despachos em voo: `{ticket, unit, trilha, worktree, status, started_at, dispatch_id}`. `status` ∈ `em-voo\|concluido\|falhou\|reconciliado` — **é este array que `reconcile` lê para saber o que verificar após um crash.** `dispatch_id` (Story E8.4, opcional/aditivo — despachos anteriores a E8.4 nunca terão essa chave) é o ponteiro para `dispatches/{dispatch_id}/` (ver `dispatch-contract.md`); quando presente, `reconcile` resolve a lista COMPLETA de tickets lendo `request.yaml` (nunca embutida aqui — o mini-serializer YAML deste arquivo só suporta dict-de-escalares em 1 nível, ver `dispatch-contract.md` § Integração) e cruza a ausência de `DONE.marker` como mais um motivo de órfão. |
| `decisions_pending` | lista de `{ticket, note}` | Decisões aguardando ratificação/info |
| `decisions_escalated` | lista de `{ticket, note}` | Tickets movidos para `precisa-de-info` neste ciclo |
| `semgrep_fp_pending` | lista de `{fingerprint, rule_id, file, line, reason, status, timestamp}` | Suspeitas de falso-positivo de Semgrep (`flag_suspected_fp.py`, E7.3) ainda `pending_ratification` — populado por `read_fp_suspects.py list-pending` e repassado aqui pela persona (Story E13.4, PRD 04 FR-2, ver § Suspeitas de falso-positivo (Semgrep) (E13.4) abaixo). Aditivo/opcional, mesmo espírito de `escalation_sample_review`/`escalation_dead_letter` — ausente ou `[]` renderiza frase neutra no Briefing, nunca quebra um estado de antes desta story. |
| `priorities` | lista de `{ticket, priority}` | Ordem de priorização decidida neste ciclo |
| `quota.*` | — | Retrato de cota — `five_hour_used_pct`/`seven_day_used_pct`/`source`/`read_at` (bruto, lido de `~/.claude/rate-limits-state.json`) **+** `self_tracked_tokens`/`self_tracked_pct`/`stronger_signal_pct`/`stronger_signal_source` (Story E8.3 — ver § Cota (E8.3) abaixo). Os 4 campos novos são opcionais/`null` até a persona passar `check`'s `write_snapshot_quota_args` para `write-snapshot`. |
| `last_briefing_at` | ISO8601 \| null | Timestamp do último Briefing entregue. Informativo — a fonte de verdade de "lido/não-lido" é o frontmatter do próprio `briefing-YYYYMMDD.md` (`status:`), lido diretamente por `gerente_briefing.py detect-unread`, nunca só este campo (ver § Briefing (E8.7)) |

**O parser/serializador é um subconjunto mínimo de YAML fechado** (`yaml_scalar` /
`dump_estado` / `parse_estado` em `gerente_state.py`) — dict-de-escalares em 1 nível e
listas-de-dict-de-escalares, exatamente o suficiente para este schema. Não é um YAML
genérico; não use estes arquivos como base para um parser YAML de propósito geral.

## Diário (`diario.md` + `diario.jsonl`)

Log **plano, cronológico, só-anexa** — mesma filosofia de `_bmad/scripts/memlog.py`
("A memlog is... kept minimal like human memory... no sections or grouping. Every entry
is one line, recorded at the END"). `diario.md` é a superfície legível por
humano/persona; `diario.jsonl` é o espelho estruturado que `detect-crash` varre
mecanicamente (evita fazer parsing de markdown livre para uma decisão crítica de
recuperação).

Cada ciclo é delimitado por um par:
```
## CICLO-INICIO <ts> <cycle-id>
...entradas do ciclo (acordei, li-estado, decidi, despachei, revisei, parei)...
## CICLO-FIM <ts> <cycle-id>
```
Eventos válidos (`--event`): `CICLO-INICIO`, `CICLO-FIM`, `acordei`, `li-estado`,
`decidi`, `despachei`, `revisei`, `parei` — os 6 nomes de fase do loop de
`gerente-geral.md` mais os dois marcadores de ciclo. Um `CICLO-FIM` de fechamento por
recuperação de crash carrega `--reconciled` (aparece como `(reconciled)` no `.md` e
`"reconciled": true` no `.jsonl`).

**Escrita atômica**: toda mutação (write-snapshot, append-diario, lock) usa
`write_atomic` **importada diretamente de `_bmad/scripts/memlog.py`** (import do
arquivo, não cópia colada — ver `_memlog()` em `gerente_state.py`) — temp + flush +
`fsync` + `os.replace` — a mesma primitiva usada por `transition_ledger_entry.py` e
`rebuild_board.py`. Cada `append` faz um **rewrite atômico do arquivo inteiro**, igual
`memlog.py` — não é um `open(..., "a")` incremental (que poderia deixar uma linha
truncada se o processo morrer no meio do `write()`).

## Cota (E8.3)

Story E8.3 (`ideias/sistema-artifacts/E8-3-consciencia-cota.md`), PRD 00 FR-2, §4.1. O
guardrail que impede o Gerente de estourar a cota da assinatura: antes de iniciar uma
nova unidade de trabalho, ele lê `~/.claude/rate-limits-state.json` **como um insumo**,
mas — porque esse arquivo é escrito pelo hook de statusline de uma sessão INTERATIVA e
pode ficar **congelado** num ciclo headless (sem sessão interativa viva escrevendo nele)
— ele TAMBÉM auto-rastreia os tokens gastos no próprio ciclo e usa o **sinal mais forte**
(mais conservador) entre os dois. `scripts/gerente_quota.py` implementa isto — nenhum
subcomando faz uma chamada de rede: `read-limits` só lê um arquivo local, `record-usage`/
`check` só leem/escrevem arquivos locais em `project_controll/gerente/`. Cota é
**só de assinatura** — não há caminho para uma API metered neste módulo.

### Schema real de `~/.claude/rate-limits-state.json` (verificado, não assumido)

```json
{"updated_at": 1783807722, "model": "Opus 4.8 (1M context)",
 "five_hour": {"used_percentage": 9, "resets_at": 1783822800},
 "seven_day": {"used_percentage": 25, "resets_at": 1783843200}}
```

`updated_at`/`resets_at` são epoch seconds. `read-limits` parseia exatamente este schema
e é **defensivo por construção** — arquivo ausente, JSON malformado ou schema inesperado
(chaves faltando) nunca lançam exceção: devolvem `ok: false` + `error` descritivo, com
todos os campos numéricos em `null`. `check` trata esse caso como sinal **indisponível**
(`degraded_rate_limit_signal`), nunca como "0% usado" nem como "100% usado" — um primeiro
ciclo de sempre (sem o arquivo ainda, ou máquina nova) não gera nem falso-`start` por
otimismo indevido nem falso-`stop` por pessimismo indevido; ele só perde a corroboração
do rate-limit e passa a depender inteiramente do auto-rastreio (que também começa
zerado), o que é o comportamento correto para essa situação.

### Auto-rastreio local — o que ele conta, e os limites honestos disso

`record-usage --cycle-id ID --tokens N [--note TXT]` acumula uma estimativa BRUTA de
tokens numa contagem por-ciclo em `quota-ciclo.json` (reseta automaticamente quando
`--cycle-id` muda em relação ao gravado — não existe um subcomando `reset-cycle`
separado porque o Gerente já sempre chama isto com o `cycle_id` do ciclo atual).

**Story E15.2 — o caso "depois de cada despacho" agora é MECANIZADO, não mais
disciplina comportamental.** Até E15.2, esta seção instruía a persona a lembrar de
chamar `record-usage` manualmente depois de cada despacho retornar — um concern
residual real (ver item 4 abaixo, hoje reescrito). Desde E15.2, `gerente_dispatch.py
close-dispatch` aceita `--tokens-used N` e, **na mesma chamada que fecha o despacho**,
chama `record_usage()` (de `gerente_quota.py`, por import direto — nunca subprocess)
ANTES de gravar `result.yaml`/`DONE.marker` — ver § Despacho (E8.4) abaixo para o
mecanismo de ordem completo. **O que deve ser contado, por convenção operacional da
persona:**
- **Depois de CADA despacho (`Agent`/`Skill`) retornar** — passe `--tokens-used
  <estimativa>` na própria chamada de `close-dispatch` que fecha o despacho (fase
  "despachar" da persona), não mais uma chamada separada de `record-usage`. A estimativa
  é a mesma de sempre: idealmente o uso reportado pelo próprio sub-agente na resposta,
  ou, na ausência disso, uma estimativa grosseira (ex.: proporcional ao tamanho da
  transcrição devolvida, ou um valor fixo por tipo de despacho).
- **`record-usage` manual continua existindo (backward-compat) e fica restrito ao
  residual aceito: turnos-Opus avulsos do próprio Gerente** dentro do ciclo (ex.: a cada
  transição de fase, uma análise longa feita sem despachar sub-agente nenhum) — nunca
  mais para cobrir um despacho, que já é coberto automaticamente por `close-dispatch
  --tokens-used`.

Cada valor passado em `--tokens` é multiplicado por um **multiplicador de segurança**
(`--multiplier`, default resolvido `1.15`) e arredondado **para cima** antes de somar —
enviesado deliberadamente para superestimar, nunca subestimar, o gasto real.

**Limites honestos (documentados, não escondidos):** isto é uma APROXIMAÇÃO sem
contagem real de tokens — não existe, neste ambiente, uma API local que devolva o
consumo exato de tokens de um turno/despacho (e não vamos criar uma, porque isso exigiria
API metered, proibida por construção). A contagem só é tão boa quanto o que é
efetivamente reportado — desde E15.2, o caso de despacho é mecanizado (`close-dispatch
--tokens-used`, sempre roda quando o despacho fecha), então o risco de esquecimento fica
restrito ao residual explícito abaixo (turno-Opus avulso via `record-usage` manual); se a
persona **esquecer** de passar `--tokens-used` num `close-dispatch`, ou esquecer de
chamar `record-usage` num turno avulso, aquele consumo fica invisível ao auto-rastreio,
na direção PERIGOSA (subestimação). Mitigações aplicadas:
1. O multiplicador de segurança enviesa cada entrada registrada para cima.
2. O orçamento de auto-rastreio (`self_tracked_budget_tokens`, default conservador
   `300000`) é deliberadamente pequeno/pessimista — um ciclo real tende a bater o teto
   de auto-rastreio bem antes de bater um teto real de tokens da assinatura, o que
   antecipa a parada em vez de atrasá-la.
3. **`check` sempre usa o MÁXIMO entre os dois sinais**, nunca só o auto-rastreio — se o
   `rate-limits-state.json` estiver fresco (sessão interativa viva escrevendo nele), o
   sinal autoritativo da própria Anthropic domina independentemente de qualquer lacuna
   no auto-rastreio. A janela de risco real é especificamente "ciclo headless + snapshot
   congelado + persona esqueceu de chamar record-usage" — um caso composto, não o caminho
   comum.
4. **Concern residual, aceito e não "corrigido", MAS ESTREITADO pela Story E15.2**: até
   E15.2, este item cobria "não há enforcement mecânico que force a persona a chamar
   `record-usage` depois de todo despacho" — esse caso específico (o mais comum, um
   despacho por vez) agora É mecanizado: `close-dispatch --tokens-used` é passado na
   MESMA chamada que já fecha o despacho (a persona já é obrigada a chamar
   `close-dispatch`; passar `--tokens-used` junto é uma flag a mais na mesma chamada, não
   um passo extra separável de esquecer). O concern residual que sobra é mais estreito:
   não há enforcement mecânico que force a persona a chamar `record-usage` manual para os
   próprios turnos-Opus avulsos (transições de fase, análises sem despacho) — isso
   continua sendo disciplina comportamental documentada aqui e em
   `.claude/agents/gerente-geral.md`, da mesma classe de outras disciplinas já aceitas
   neste sistema (ex.: "sempre invocar `bagual-tickets` em vez de editar `board.yaml` à
   mão"). Fechar isto por completo exigiria instrumentar a própria execução do agente
   (fora do alcance de um script stdlib local) — território de uma story futura, não
   desta.
5. **Concern residual sobre concorrência**: `record-usage` faz um ciclo
   ler-modificar-escrever (lê `quota-ciclo.json`, soma, escreve atomicamente) — a
   ESCRITA em si nunca corrompe o arquivo (mesma primitiva atômica de E8.2), mas duas
   chamadas *concorrentes* de `record-usage` no mesmo ciclo poderiam perder um incremento
   (a última escrita vence). Não é um problema hoje porque o despacho desta fase do
   sistema é estritamente sequencial — "nunca despache mais de um Ticket em paralelo"
   (E8.1) — só voltaria a importar quando paralelismo real existir (E10/E11), fora do
   escopo desta story.

`self_tracked_pct = teto(min(100, self_tracked_tokens / self_tracked_budget_tokens * 100))`
— arredondado para CIMA (não para o inteiro mais próximo), enviesado a favor de "parar
cedo" em vez de subestimar por causa de arredondamento (constraint explícita da story:
"an approximation error never causes an overrun").

### `check` — o sinal mais forte + veredito

`check --cycle-id ID [--limits-path PATH] [--threshold-pct N] [--self-tracked-budget-tokens N] [--stop-diario]`
lê os dois sinais (`read-limits` + `quota-ciclo.json`), normaliza ambos em percentuais
comparáveis (rate-limit = pior das janelas 5h/7d; self-tracked = tokens acumulados /
orçamento configurado), pega o **máximo** dos dois (`stronger_signal_pct` +
`stronger_signal_source`), e compara contra o limiar configurável (comparação `>=`, sem
off-by-one — no limiar exato já é `stop`). Devolve também `write_snapshot_quota_args`: os
argumentos exatos para repassar a `gerente_state.py write-snapshot` no fechamento do
ciclo, para a persona não precisar recompor os nomes de flag na mão. Com `--stop-diario`,
se o veredito for `stop`, grava `parei-por-cota: <razão>` em `diario.md`/`diario.jsonl`
com `--event parei` **via o mesmo mecanismo `append-diario` de E8.2** (import direto de
`gerente_state.py`, não uma reimplementação).

### Config — precedência (a mais alta vence)

1. Flag de CLI (`--threshold-pct`, `--self-tracked-budget-tokens`, `--multiplier`,
   `--stale-snapshot-seconds`).
2. Variável de ambiente (`GERENTE_QUOTA_THRESHOLD_PCT`,
   `GERENTE_QUOTA_SELF_TRACKED_BUDGET_TOKENS`, `GERENTE_QUOTA_SAFETY_MULTIPLIER`,
   `GERENTE_QUOTA_STALE_SNAPSHOT_SECONDS`).
3. `project_controll/gerente/quota.config.json` (commitado com defaults — o dono edita
   diretamente para calibrar ao seu plano real).
4. Default hardcoded em `gerente_quota.py`: `threshold_pct=85.0`,
   `self_tracked_budget_tokens=300000`, `safety_multiplier=1.15`,
   `stale_snapshot_seconds=900`, `per_dispatch_inflight_estimate_tokens=200000`,
   `inflight_grace_seconds=600`.

**Calibração recomendada (não automática):** `self_tracked_budget_tokens=300000` é um
chute conservador de partida, não um número medido — o dono pode, depois de observar
alguns ciclos reais com `rate-limits-state.json` fresco (sessão interativa), comparar
`self_tracked_pct` contra o `five_hour_used_pct`/`seven_day_used_pct` real reportados
para o mesmo volume de trabalho, e ajustar `self_tracked_budget_tokens` em
`quota.config.json` para que os dois sinais fiquem na mesma ordem de grandeza.

**Kill-switch do guardrail (flag `enabled`, decisão do dono 2026-07-14).** `enabled: false` em
`quota.config.json` **desliga o guardrail inteiro**: o `check` ainda calcula e reporta os dois
sinais (diagnóstico segue útil — `natural_verdict` mostra o que ele SERIA), mas o `verdict` é
forçado a `start`, então **o Gerente nunca para por cota**. Está DESLIGADO agora (o dono acompanha
o throughput manualmente). Para reativar o controle: `enabled: true`. Precedência: `--no-enabled`
(CLI) > `GERENTE_QUOTA_ENABLED` (env) > `enabled` (config) > default `true`. Isto NÃO é o mesmo que
aumentar `self_tracked_budget_tokens` — é o desligamento explícito do controle, não um teto maior.

**Estimativa de despacho in-flight (E19.2, Furo 2 — cota não fica cega no meio da árvore):**
o acumulador `self_tracked_tokens_total` só avança no `close-dispatch`. Enquanto a árvore de
um despacho executa (executor → sub-fluxo que confirma por marcador), ele fica congelado — então o
`check` reportava folga falsa no meio da árvore (incidente `cycle-20260713-202850`: 44%
enquanto ~1M queimava). O `check` agora soma ao sinal auto-rastreado uma estimativa por
despacho ainda ABERTO (`request.yaml` presente, `DONE.marker` ausente) do ciclo atual que já
passou de `inflight_grace_seconds` (default 600s) — `per_dispatch_inflight_estimate_tokens`
(default 200000) cada. Assim o guardrail dispara mesmo antes do close-dispatch e mesmo se ele
nunca rodar (órfão), sem falso-abortar um despacho recém-aberto (dentro da graça). Um "stop"
daí NÃO mata a árvore em voo — leva o Gerente à fase 'parar' (reconcilia/aguarda os despachos
em voo). Ponha `per_dispatch_inflight_estimate_tokens=0` no `quota.config.json` para desligar.

## Despacho (E8.4)

Story E8.4 (`ideias/sistema-artifacts/E8-4-contrato-despacho.md`), PRD 00 FR-8 (+ lado
Sonnet do FR-7). Contrato COMPLETO em `dispatch-contract.md` (não duplicado aqui, mesma
disciplina de "um contrato, um dono" já usada por este README) — leia lá o schema de
`request.yaml`/`result.yaml`, a garantia de ordem (result durável ANTES de DONE.marker), a
detecção dual de conclusão (retorno do Agent tool = sinal primário; `DONE.marker` = sinal
secundário/payload, nunca poll), e o forward-compat com o supervisor multi-epic do E10.
Resumo do que importa para ESTE arquivo: `scripts/gerente_dispatch.py` nunca escreve
`estado-atual.yaml` diretamente (mesma regra de "um dono só" já aplicada a
`quota-ciclo.json` em E8.3) — `open-dispatch` devolve um `dispatch_entry` pronto para a
persona repassar ao próximo `write-snapshot --dispatches-json`, e `gerente_state.py
reconcile` (E8.2) foi estendido para cruzar `DONE.marker` de cada despacho que carrega
`dispatch_id` (ver checklist de reconciliação acima, item 4b).

### `close-dispatch --tokens-used` — cota mecanizada como efeito colateral (E15.2)

Story E15.2 (`ideias/sistema-artifacts/E15-2-mecanizar-record-usage.md`), Epic E15
(hardening comportamental→mecânico), T2.2. `close-dispatch` aceita `--tokens-used N
[--tokens-note TXT] [--tokens-multiplier F]` — quando passado, ANTES de escrever
`result.yaml`/`DONE.marker` (a garantia de ordem já documentada acima e em
`dispatch-contract.md`), o script chama `gerente_quota.py::record_usage()` **por import
direto** (nunca subprocess — mesma técnica de reuso já usada para `gerente_state.py`),
lendo `cycle_id` do próprio `request.yaml` do despacho, aplicando o mesmo multiplicador de
segurança resolvido por `resolve_safety_multiplier()`. **Garantia central**: `DONE.marker`
(o sinal definitivo de "despacho fechado" no contrato) nunca é observável sem que a cota
já tenha sido contada — não existe estado half-closed onde o despacho está fechado mas a
cota não foi contabilizada. A janela simétrica (processo morre ENTRE a escrita da cota e a
escrita de `result.yaml`) é segura na direção oposta: a cota fica "adiantada", mas o
despacho continua detectável como órfão via `reconcile-orphan-dispatch`/`list-inflight`
como sempre — nunca "despacho fechado, cota esquecida". Omitir `--tokens-used` preserva o
comportamento anterior a E15.2 (nenhuma escrita em `quota-ciclo.json`) — backward-compat
total; `record-usage` standalone continua funcionando sem nenhuma mudança, agora restrito
ao residual de turno-Opus avulso (ver § Cota acima).

## Trabalho proativo (E8.5)

Story E8.5 (`ideias/sistema-artifacts/E8-5-trabalho-proativo.md`), PRD 00 FR-3, UJ-4,
hardening F24. Quando `project_controll/tickets/board.yaml` não tem nenhum Ticket
`pronto-para-implementar`, o Gerente não fica ocioso — mas escolhe de um catálogo
RESTRITO de baixíssimo risco (`proactive-catalog.md`, conteúdo/guardrails das 4
categorias, não duplicados aqui). A mecânica (teto + dedup) vive em
`scripts/gerente_proactive.py`:

- **`next-task`** — teto duro por ciclo, configurável (`proactive.config.json`
  `cap_per_cycle`, default 3). Cada chamada com `count_so_far < cap_per_cycle` devolve
  `"verdict": "go"` + a categoria da rotação round-robin determinística (`count_so_far %
  4`); ao atingir o teto, devolve `"verdict": "cap-reached"` (`category: null`) — sem
  off-by-one, provado em `test_gerente_proactive.py` [1]/[1b] para N=1 e N=3. **A unidade
  de custo é a ITERAÇÃO do catálogo** (um despacho de sub-agente Sonnet de análise), não o
  número de Tickets que ela produz — ver `proactive-catalog.md` § "Unidade de custo".
- **`dedup-check`** — varre TODOS os `TCK-*.md` de `--tickets-dir` com `origem: proativo`
  (default; `--include-non-proactive` amplia), **em qualquer status, incluindo
  `concluido`/`descartado`** — a dimensão que o dedup nativo de `bagual-tickets` não cobre
  (ele só compara contra tickets ABERTOS, ver `.claude/skills/bagual-tickets/SKILL.md` §
  Adicionar passo 2). Heurística: Jaccard de tokens (normalizados, sem acento, stopwords
  PT/EN removidas) entre `--title`/`--description` do achado candidato e
  `título + seção "## Descrição"` de cada ticket do histórico (não o corpo inteiro — isso
  dilui o overlap real com ruído de `## Verificação`/`## Log`/hashes de commit). Acima do
  limiar configurável (`dedup_similarity_threshold`, default `0.30` — calibrado
  empiricamente contra achados parafraseados nos testes reais, mesmo caveat de "chute
  calibrável, não medido" documentado para `self_tracked_budget_tokens` em E8.3),
  `"duplicate": true` aponta o `best_match`. **Isto é candidato-retrieval + heurística
  para o chamador (LLM) revisar, não um veredito algorítmico infalível** — mesmo espírito
  do dedup por leitura humana/LLM que a própria skill `bagual-tickets` já usa contra
  tickets abertos; aqui só a dimensão do corpus muda (histórico completo vs. abertos).
- **`record-proactive`** — incrementa `proactive-ciclo.json` (auto-reset por
  `--cycle-id` novo, mesma filosofia "um dono só"/"sobrescrito por ciclo" de
  `quota-ciclo.json`/E8.3), chamado **uma vez por iteração** do catálogo (nunca uma vez
  por achado/Ticket).

**Composição, nunca reimplementação:** este módulo NUNCA cria/edita um Ticket
diretamente — a materialização de um achado não-duplicado é sempre `bagual-tickets
--headless` (que já grava `origem: proativo` por padrão em modo headless, ver `SKILL.md` §
Headless Mode), invocado pela persona depois que `dedup-check` devolve `duplicate: false`.
O sub-agente de análise despachado pela categoria escolhida é **somente-leitura** por
contrato (`proactive-catalog.md` § "Regra de ouro") — nunca chama `Edit`/`Write` sobre
código de produto; o único artefato de saída aceito é uma lista de achados em texto.

## Briefing (E8.7)

Story E8.7 (`ideias/sistema-artifacts/E8-7-briefing-manha.md`), PRD 00 FR-10, §4.7. O
ciclo do Gerente roda **headless** — não existe "mensagem no chat" nenhuma para entregar
ao fim de um ciclo autônomo sem dono presente. `scripts/gerente_briefing.py` resolve isso
tornando o Briefing um **artefato persistido**, derivado de `diario.jsonl` (E8.2) +
`estado-atual.yaml` (E8.2), que a PRÓXIMA sessão interativa detecta como não-lido e
renderiza na ativação:

- **`write-briefing`** — chamado pela persona na fase "parar" (passo 6 do loop), depois
  de `append-diario --event CICLO-FIM` e antes de `release-lock`. Lê `diario.jsonl`
  filtrando pelas entradas do `--cycle-id` dado (evento `despachei`/`revisei` → "o que foi
  feito", `decidi` → "decisões tomadas (rastro)") e `estado-atual.yaml` (`decisions_pending`
  + `decisions_escalated` → "precisa de atenção/ratificação"), e escreve/atualiza
  `briefing-YYYYMMDD.md`. `--stop-reason cota|fila-vazia|bloqueio` mapeia para o rótulo
  legível `cota|conclusão|bloqueio` do AC (`fila-vazia` → "conclusão"); um
  `--stop-detail teto-proativo` opcional anota a nuance do guardrail de trabalho proativo
  (E8.5) sem inventar um 4º valor de `stop_reason` — a mesma distinção que já vivia só na
  prosa do "Relato final" da persona (ver `gerente-geral.md` fase "parar").
- **Data do arquivo** vem da data-calendário de `--ended-at` (o fim do CICLO real), nunca
  do relógio de quando o script roda — um ciclo que termina 23:58 e cujo `write-briefing`
  só é chamado depois da virada do dia ainda produz o `briefing-<data-do-ended_at>.md`
  correto. Só cai para o relógio do próprio script (`now_iso()`) quando `--ended-at` não é
  fornecido (`used_fallback_date: true` na resposta — degradação documentada, não o
  caminho primário).
- **Idempotência por `--cycle-id`**: o arquivo é `YAML frontmatter (status/written_at/
  last_cycle_id/read_at) + uma seção Markdown "## Ciclo <cycle_id>" por ciclo`. Rodar
  `write-briefing` de novo para o MESMO `--cycle-id` (ex.: retomando a fase "parar" depois
  de uma compactação de contexto no meio dela) **substitui** a seção existente em vez de
  duplicá-la. Um SEGUNDO ciclo terminando no mesmo dia calendário **acrescenta** uma nova
  seção ao mesmo arquivo, preservando a(s) anterior(es) — nunca sobrescreve o dia inteiro.
  Cada nova escrita marca o arquivo inteiro como `status: unread` de novo (conteúdo novo =
  evento novo de leitura pendente), mesmo que uma seção anterior já tivesse sido lida.
- **Forward-dep E9.1 (oráculo)**: a seção "precisa de atenção/ratificação" já lê
  `decisions_pending`/`decisions_escalated` de `estado-atual.yaml` com `.get(..., [])`
  defensivo — hoje sempre `[]` (ou a chave ausente, tratada igual), então a seção sempre
  renderiza "nenhuma decisão pendente de ratificação". Quando a Story E9.1 popular esses
  campos de verdade, o Briefing passa a listar as entradas sem nenhum rework deste script.
- **`detect-unread`** — somente-leitura, varre `briefing-*.md` e lista os que têm
  `status: unread` no frontmatter (ausência de frontmatter reconhecível conta como
  não-lido — nunca perde um Briefing por engano). Chamado pela persona no passo 5 da
  "Ativação", só quando a sessão é interativa (não durante um ciclo headless — não há
  dono para ler).
- **`mark-read`** — `--date YYYYMMDD` (ou `--path`), seta `status: read` + `read_at`.
  Idempotente: marcar um Briefing já lido de novo não é erro (`already_read: true` na
  resposta, sem duplicar nem corromper o arquivo). A persona chama isto logo depois de
  renderizar o conteúdo — nunca deixe um Briefing renderizado sem `mark-read`, senão a
  PRÓXIMA ativação o renderiza de novo (double-render).
- **Race entre `detect-unread` e `mark-read` (achado real em auto-revisão adversarial
  desta story)**: uma sessão interativa pode `detect-unread` → começar a renderizar →
  enquanto isso um ciclo headless CONCORRENTE roda `write-briefing` de novo (acrescentando
  uma seção nova, marcando o arquivo `unread` outra vez) → se a sessão interativa então
  chamasse `mark-read` cegamente, ela clobbaria esse `unread` recém-escrito para `read`, e
  a seção nova nunca seria renderizada em NENHUMA sessão futura — perda silenciosa de
  Briefing. `mark-read --expected-last-cycle-id <valor devolvido por detect-unread>` é o
  compare-and-swap que fecha isso: se o `last_cycle_id` do arquivo já não bate mais
  (alguém escreveu no meio-tempo), `mark-read` recusa (`ok: false`, `error: "stale"`,
  devolvendo o `actual_last_cycle_id` atual) em vez de marcar como lido — o chamador deve
  re-`detect-unread`/re-renderizar antes de tentar de novo. Sem `--expected-last-cycle-id`
  (omitido), o comportamento antigo (marca sempre) continua disponível para chamadas
  fora desta race (ex.: teste/depuração manual), mas a persona SEMPRE passa o parâmetro.
- **Diário torn/parcial nunca derruba o Briefing**: se o par `CICLO-INICIO`/`CICLO-FIM` do
  `--cycle-id` não é encontrado completo em `diario.jsonl` (crash no meio do ciclo, ou
  `write-briefing` chamado antes do `append-diario CICLO-FIM` normal — não deveria
  acontecer no fluxo correto, mas é tratado mesmo assim), o Briefing ainda é escrito com o
  que existe, com a seção "Diagnóstico" sinalizando `diário: incompleto`. Uma linha
  individual malformada em `diario.jsonl` (JSON inválido isolado) é ignorada, não aborta o
  arquivo inteiro.
- **`--root` PRÓPRIO em cada chamada**: nunca escreva/detecte contra `project_controll/
  gerente/` de um teste — sempre um `--root` de diretório temporário (ver
  `test_gerente_briefing.py` e as fixtures em `ideias/sistema-artifacts/fixtures/E8/`).
- **`PushNotification`** — opcional, best-effort: se a ferramenta estiver disponível na
  sessão que roda o ciclo, a persona PODE chamá-la depois de `write-briefing` para
  avisar o dono fora da sessão; a AUSÊNCIA dela nunca impede a renderização do próximo
  `detect-unread`/`mark-read` — é só um sinal extra, não um pré-requisito. Este módulo não
  a invoca diretamente (não é uma dependência hard-wired).

## Wake local (E8.8)

Story E8.8 (`ideias/sistema-artifacts/E8-8-wake-local.md`), PRD 00 FR-1/§8-Q2. Contrato
completo, os dois mecanismos locais disponíveis (`loop`/`CronCreate`), o
`PROMPT-DE-WAKE` exato e o micro-teste manual de 60s vivem em
[`project_controll/gerente/wake.md`](./wake.md) — este parágrafo é só o resumo mecânico
para quem já leu a seção "Lock singleton" abaixo:

`scripts/gerente_wake.py wake-attempt` reusa `gerente_state.py::acquire_lock` (a mesma
função, importada, não uma cópia) para decidir — SEM spawnar nenhum sub-agente — se um
tick de `loop`/`CronCreate` deve acordar a persona (`Agent(subagent_type:
"gerente-geral")`). `proceed: true` devolve `cycle_id`/`token` já adquiridos (a persona
pula a sub-etapa `acquire-lock` do seu próprio passo 0, ver `gerente-geral.md` §
"Ativação" bullet "Entrada alternativa via wake local"); `proceed: false` (lock
held-e-fresco) faz o wake deferir sem custo, `exit 0` em ambos os casos. `pending_crash`
é repassado tal e qual quando `acquire_lock` reclama um lock stale com um `CICLO-INICIO`
órfão associado — `gerente_wake.py` nunca reconcilia sozinho, isso continua sendo
julgamento da persona. 100% local: `loop`/`CronCreate` são primitivas nativas da SESSÃO
ABERTA (nunca cron do SO, nunca a skill `schedule`/routines cloud — proibidas por
§8-Q2/F1), e `gerente_wake.py` só importa stdlib (verificado mecanicamente por
`test_gerente_wake.py::test_no_network_path`).

## Oráculo (E9.1)

Story E9.1 (`ideias/sistema-artifacts/E9-1-oraculo-decisao-delegada.md`), PRD 00 FR-5
(§4.3, UJ-3), `ideias/epics.md` Epic E9. Contrato canônico do gate de confiança; o
protocolo operacional (quando dispara, passo a passo, ratificação) vive em
`.claude/agents/gerente-geral.md` § "Protocolo do Oráculo (E9.1)" — este README documenta
só a mecânica do script (`scripts/gerente_oracle.py`).

**Onde grava:** ao contrário de todo o resto desta pasta, uma decisão de oráculo é
gravada como Entrada de Ledger em `wiki/ledger/{decisao-tecnica,decisao-de-
produto,decisao-de-arquitetura}/*.md` (fora de `project_controll/gerente/`) — front-matter
completo do schema de `wiki/ledger/README.md` §1 **mais** 5 campos próprios
de entradas de oráculo: `oracle: true`, `ticket: <id>`, `confidence: high|low`,
`blast_radius: auto-merge|parked`, `ratification: pending|ratified|corrected`,
`precedent: <path>|null`. O corpo segue MADR completo (`## Contexto`/`## Decisão`/
`## Alternativas...`/`## Consequências`) — os 3 campos do rastro exigido pela AC1
(decisão, justificativa, contexto) mapeiam 1:1 para `## Decisão`/`## Consequências`/
`## Contexto`.

**O gate de confiança — núcleo do hardening F10 ("raio de estrago").** `record-decision`
só concede `confidence: high` (e `proceed_dispatch: true` na resposta JSON) quando
**todas** as condições abaixo são verificadas MECANICAMENTE contra `--precedent <path>`
(nunca aceitas pela alegação do chamador):

1. `--precedent` foi passado, aponta para um arquivo (não diretório) que existe e é
   legível como UTF-8.
2. O front-matter tem `tipo` ∈ {decisão-técnica, decisão-de-produto,
   decisão-de-arquitetura}.
3. `estado: ativa` — **não basta "diferente de aposentada"**; uma entrada `candidata`
   (inclusive uma emitida pelo próprio oráculo minutos antes, ainda `ratification:
   pending`) nunca sustenta alta confiança. Sem esta exigência, duas chamadas comuns e
   não-adversariais poderiam encadear "decisão de baixa confiança" → "precedente de uma
   segunda decisão de alta confiança" (achado real de auto-revisão adversarial desta
   story — ver `## Consequências` da fixture correspondente e os testes `[1]`-`[7]` de
   `test_gerente_oracle.py`).
4. `ratification` ausente ou `ratified` — nunca `corrected`/`pending`. Uma entrada que o
   dono corrigiu **nunca volta** a servir de precedente, mesmo que `estado` continue
   `ativa` (o `set-ratification --status corrected` não reverte `estado` — só marca o
   sinal; ver abaixo).

Qualquer falha em 1-4 rebaixa a confiança para `low` com `downgrade_reason` explicado na
resposta — **nunca** um `exit`/exceção que deixe o chamador sem saber o veredito. O
default sem `--confidence` explícito, ou com qualquer valor fora de `{high, low}`, já é
`low` (conservador por construção — "incerto" nunca vira "high" por omissão). Além disso,
`proceed_dispatch` é sempre também condicionado ao self-check (`validate_ledger.py`) ter
passado — uma entrada malformada nunca libera auto-merge, mesmo com `confidence: high`
calculada.

**Escrita atômica sob concorrência real:** `record-decision` reserva o path do arquivo via
`os.open(..., O_CREAT|O_EXCL)` **antes** de escrever o conteúdo (nunca um
`path.exists()` seguido de escrita mais tarde) — a mesma garantia de exclusão mútua do
filesystem que o lock singleton (`os.mkdir`, § abaixo) usa. Provado com 20 processos
reais concorrentes gravando o MESMO ticket/decisão (`test_gerente_oracle.py` `[12c]`):
20 paths únicos, 20 arquivos sobreviventes em disco, zero crash. Um `unique_path()`
ingênuo anterior (check-then-write) permitia colisão de `.tmp` intermediário entre dois
processos e sobrescrita silenciosa — corrigido nesta mesma story antes do fechamento.

**Front-matter injection.** `--ticket`, `--precedent` e cada item de `--areas` são
recusados (`exit 2`) se contiverem `\n`/`\r` — como o front-matter é montado por
interpolação literal (não um serializador YAML que escapa newlines), um valor com
quebra de linha embutida poderia, sem esta guarda, forjar linhas extras dentro do mesmo
bloco `---...---` (ex.: injetar `ratification: ratified` via um `--precedent`
malicioso/malformado). Nunca sanitiza silenciosamente — sempre recusa alto e explícito.

**Ciclo de vida `ratification`:** `pending` (ao nascer, sempre) → `ratified` (dono
confirma; `set-ratification` promove `estado: candidata -> ativa` automaticamente, se
ainda `candidata`) | `corrected` (dono corrige; `estado` permanece como estava — o campo
é só o sinal, consumido pela Story E9.2 de aprendizado de estilo; a entrada nunca é
apagada/reescrita). `list-pending` enxerga só `oracle: true` + `ratification: pending` —
é a fonte de verdade persistente (sobrevive a qualquer reinício/compactação de contexto,
ao contrário de `estado-atual.yaml`, que é sobrescrito a cada ciclo); o `pending_entry`
devolvido por `record-decision` é o que a persona repassa a
`write-snapshot --pending-json` para a visibilidade do Briefing (E8.7), mas o rastro
canônico e durável é sempre o arquivo de Ledger em si.

**Reuso, nunca reimplementação:** `gerente_oracle.py` importa diretamente (mesma técnica
de `_memlog()` em `gerente_state.py`) as primitivas de
`wiki/ledger/scripts/transition_ledger_entry.py`
(`split_front_matter`/`set_front_matter_field`/`get_front_matter_field`/
`append_transition_note`/`write_atomic`/`render`) e de `validate_ledger.py`
(`parse_front_matter`/`scan_and_validate`) — nenhuma reimplementação paralela do parser
de front-matter nem do self-check.

## Aprendizado de estilo (E9.2)

Story E9.2 (`ideias/sistema-artifacts/E9-2-aprendizado-estilo.md`), PRD 00 FR-6 (§4.3,
Fase 2). Torna o gate de confiança de `record-decision` **history-aware**: antes de
decidir, o oráculo consulta o histórico de decisões — ratificadas E corrigidas — e
ajusta o raio de confiança de acordo. O "estilo" continua sendo **entradas de Ledger +
`product-decisions.md`/`decisions.md` consultadas em spec-time**, NUNCA um modelo
treinado (`[ASSUNÇÃO]` do PRD 00 §9, ratificada por esta story).

**"Similar" — definição OPERACIONAL, nunca por sensação/NLP:** mesmo `tipo` (categoria)
**+** N tags de `areas` em comum (interseção exata, case-insensitive/trimmed —
`gerente_oracle.py::shared_areas`) entre o candidato e uma Entrada de Ledger existente.
N é o **limiar** — configurável **por categoria** em `oracle.config.json` (sibling deste
README, mesmo padrão commitado/editável de `quota.config.json`, E8.3):
`min_shared_areas_support` (quanto overlap um precedente **ratificado** precisa ter para
sustentar `high`) e `min_shared_areas_contradict` (quanto overlap uma decisão
**corrigida** precisa ter para VETAR `high`). O default commitado é
`decisao-de-produto: support=2` (categoria mais sensível — exige precedente mais forte)
vs. `decisao-tecnica`/`decisao-de-arquitetura: support=1`; `contradict=1` em toda
categoria (é sempre mais fácil provar contradição que provar suporte — nunca o
contrário, conservador por desenho).

**O gate history-aware, dentro de `record-decision`:** mesmo quando um `--precedent`
citado passa nos 4 checks mecânicos de F10 (Oráculo (E9.1) acima), `record-decision`
AINDA escaneia o Ledger por uma decisão do MESMO `tipo`, `ratification: corrected`, com
overlap de `areas` >= `min_shared_areas_contradict` contra o `--areas` do candidato
(`gerente_oracle.py::find_corrected_contradictions`). Se encontrar alguma, rebaixa para
`low` de qualquer forma — **a correção do dono sempre vence um precedente favorável
concorrente**, nunca o contrário (provado por `test_gerente_style.py [C]`/`[D]`: um
cenário com AMBOS um precedente ratificado similar E uma correção similar coexistindo
sempre resolve para `low`). A resposta JSON de `record-decision` ganhou dois campos
novos: `category_threshold` (o limiar resolvido, para auditoria) e
`contradicting_corrected` (a lista de decisões corrigidas que vetaram, vazia no caminho
feliz).

**`gerente_style.py` (sibling script, nunca escreve nada) — 2 subcomandos:**

- **`consult-precedent --tipo <slug> --areas "a,b"`** — a mesma consulta que
  `record-decision` faz internamente, mas ANTES de decidir e sem efeito colateral:
  devolve `matches_ratified`/`matches_corrected`/`suggested_confidence`/`reason`. Uma
  contradição encontrada SEMPRE resulta em `suggested_confidence: low`, mesmo que
  `matches_ratified` também venha não-vazio — down-weight nunca é ofuscado por suporte
  concorrente. Também varre `product-decisions.md`/`decisions.md` (paths configuráveis,
  default os arquivos reais do projeto) por seção `## [TAG] Título` cujo título
  mencione as mesmas `areas`/keywords extras (`--keywords`) — **puramente
  informacional** (`product_decisions_hits`/`decisions_hits` na resposta), nunca parte
  do cálculo mecânico de `suggested_confidence` (esses dois monólitos não têm
  `tipo`/`areas`/`estado`/`ratification` estruturados para sustentar uma verificação
  mecânica real — só o Ledger tem).
- **`sm2 [--tipo <slug>] [--verbose]`** — computa SM-2 (PRD 00 §7: "% de decisões do
  oráculo ratificadas, não corrigidas, subindo ao longo do tempo") **a partir do rastro
  real** (escaneia `wiki/ledger/` por `oracle: true`, conta
  `ratification` ∈ {ratified, corrected, pending}) — nunca um valor hardcoded.
  `pct_ratified = ratified / (ratified + corrected) * 100`, excluindo `pending` do
  denominador (uma decisão ainda não ratificada/corrigida não é evidência a favor nem
  contra); `null` quando `decided == 0` (SM-2 indefinido — nunca `0`/`100` por
  omissão). `--tipo` filtra por categoria; sem filtro, agrega todas.

**Config — mesmo padrão de `quota.config.json` (E8.3):** `oracle.config.json`
(commitado, editável pelo dono) resolve por categoria; `--oracle-config <path>` (em
ambos os scripts) escolhe QUAL arquivo carregar — testado ponta-a-ponta em
`test_gerente_style.py [G]`: um `oracle.config.json` custom muda de fato o veredito de
`consult-precedent` **e** o gate real de `record-decision`, não só os defaults
hardcoded. Arquivo ausente/malformado degrada silenciosamente para os defaults
hardcoded (`CATEGORY_THRESHOLD_DEFAULTS` em `gerente_oracle.py`) — nunca lança.

**Reuso, nunca reimplementação:** `gerente_style.py` importa `gerente_oracle.py`
diretamente (mesma técnica de import-direto-de-arquivo já usada por este último para
`transition_ledger_entry.py`/`validate_ledger.py`) — reusa as tabelas de tipo,
`shared_areas`, `load_oracle_config`/`get_category_threshold`,
`find_ratified_support`/`find_corrected_contradictions`, `validate_precedent_fm`.
Dependência é unidirecional (`gerente_style.py` -> `gerente_oracle.py`, nunca o
contrário) — o gate real vive em `gerente_oracle.py` porque é ele quem grava; a consulta
pura vive em `gerente_style.py` porque não deveria poder gravar nada.

**Limitação conhecida (residual, documentada — não corrigida nesta story):** se o
chamador passar `--areas ""` (vazio) — nunca acontece com o default do CLI
(`sistema-orquestrador,gerente-geral,oraculo`), mas é possível overridar
explicitamente — nenhum overlap é computável contra nada, então o gate history-aware
nunca encontra suporte nem contradição, e o comportamento cai de volta ao gate F10
puro (E9.1), sem o benefício de E9.2. O protocolo do Gerente (`.claude/agents/
gerente-geral.md` § Protocolo do Oráculo) instrui a sempre formular `areas` reais —
mas o script em si não recusa `areas` vazio (decisão deliberada: um `--areas` vazio
ainda é uma chamada válida sob F10 puro, e recusar aumentaria o escopo desta story
além do necessário).

## Escalonamento decidido pelo Gerente (E9.5)

Story E9.5 (PRD 02 FR-6), `scripts/gerente_escalation.py` + `escalation.config.json`.
Fecha o outro lado do contrato aberto pela Story E9.4: `bagual-tickets` já comita a
`trilha` dos casos óbvios (mecânico, via `classify_trilha.py`) e marca
`escalonar: true` no ÍNDICE `board.yaml` para os ambíguos (F20 — o Gerente varre os
escalados numa leitura só, sem abrir cada `.md`). Este script dá ao Gerente as
primitivas MECÂNICAS para o resto — a decisão de QUAL trilha e SE promover ao Ledger
continua sendo julgamento puro (Protocolo do Oráculo, E9.1/E9.2, sem heurística fixa —
decidido 2026-07-10, PRD 02 §4.4/FR-6).

**`list-escalated`** — lê só `board.yaml`, devolve os tickets com `escalonar: true`.
Como a skill (E9.4) desmarca `escalonar: false` no exato momento em que uma trilha é
comitada (pela própria skill OU, a partir desta story, pelo Gerente), este comando
nunca relista um ticket já decidido — a exclusão de "já resolvido" é uma propriedade
do próprio estado, não um filtro adicional.

**Commit da trilha decidida — via `bagual-tickets` (composição, não um script novo):**
depois de decidir via o Protocolo do Oráculo (`.claude/agents/gerente-geral.md`, seção
homônima), a persona invoca `bagual-tickets` (Resolver) para gravar `trilha: <decidida>`
+ `escalonar: false` + uma linha em `## Log` citando o rastro (Ledger path se houver) +
`ledger_refs` quando promovida — a skill NUNCA é reeditada por esta story (E9.4 já é o
lado dela do contrato); o mesmo mecanismo genérico de "atualizar campos de um ticket"
que Resolver já expõe é reusado, sem exigir uma seção nova documentada no `SKILL.md`.

**`dead-letter-check`** — dos escalados, quantos dias desde `updated` (ou `created`)
sem nenhuma atualização; `>= dead_letter_limit_days` (default 3, `escalation.config.json`)
vira dead-letter, exposto no Briefing (F20 hardening — "escalado nunca-decidido não
apodrece"). Data ilegível/ausente NUNCA vira dead-letter por omissão (fica de fora com
aviso — conservador: idade indeterminada não é prova de estar parado).

**`sample-decisions` / `record-sample-review`** — amostra tickets com `trilha` comitada
automaticamente pela skill (`trilha` != null + `escalonar: false`) ainda não revisados
pelo Gerente, para ratificação/correção **por amostragem** no Briefing (AC2 — nunca
100%). "Já revisado" é rastreado em `sampled-decisions.json` (artefato operacional do
PRÓPRIO Gerente, análogo a `estado-atual.yaml`/`diario.md` — nunca um campo novo no
ticket/board, então não exige reeditar `bagual-tickets`). Ordem determinística
(mais antigo primeiro, por `updated`/`created`) — nunca deixa o mesmo ticket velho
esperando pra sempre atrás de tickets novos.

**Uma correção alimenta E9.2 — mecanizado num único comando desde a Story E15.3 (T2.3).**
`record-sample-review --verdict corrigido` EXIGE os campos de rastro de decisão
(`--trilha-auto`/`--trilha-corrigida`/`--question`/`--justification`/`--context`;
`--tipo`/`--areas`/`--ledger-root`/`--oracle-config` opcionais) e, na MESMA invocação,
chama internamente `gerente_oracle.py::record_decision()` +
`set_ratification(status="corrected")` — por IMPORT DIRETO (`importlib.util`, nunca
subprocess), reusando as mesmas funções PURAS que a CLI de `gerente_oracle.py` usa
internamente (extraídas nesta story a partir do que antes eram só os corpos de
`cmd_record_decision`/`cmd_set_ratification`). Uma chamada produz, por construção, os
DOIS artefatos — `sampled-decisions.json` **e** a Entrada de Ledger `ratification:
corrected` — nunca um sem o outro; a entrada já nasce `ratification: corrected` (nunca
passa por um estado intermediário `pending` observável de fora). O Gerente NUNCA mais
precisa rodar `record-decision`/`set-ratification` manualmente para uma correção de
amostragem — a antiga instrução "sempre rode os dois comandos, nunca só um" (contrato
comportamental pré-E15.3) virou uma garantia mecânica de um único comando.

**Ordem de escrita + tudo-ou-nada** (mesma disciplina de E15.2 — Entrada de Ledger
`mecanizar-efeito-colateral-antes-da-escrita-que-finaliza-a-operacao`): o efeito
colateral novo (a Entrada de Ledger) é gravado **antes** da escrita que finaliza a
operação (`sampled-decisions.json`). Se os campos de rastro estiverem incompletos, o
comando recusa (exit != 0, erro claro citando os campos ausentes) sem escrever nada. Se
`record_decision`/`set_ratification` falhar depois de validar os campos, a operação
inteira aborta e `sampled-decisions.json` NÃO é tocado — nunca existe um estado
"amostra marcada como revisada, sem a Entrada de Ledger correspondente". A janela
residual simétrica e segura (Ledger já gravado como `pending`, `sampled-decisions.json`
ainda não) fica visível via `gerente_oracle.py list-pending` para retry manual de
`set-ratification`, exatamente como qualquer outra decisão pendente do oráculo.
`--verdict ratificado` é inalterado — nunca toca o Ledger.

**`orphan-sweep`** — reverte `em-implementacao -> pronto-para-implementar` para tickets
órfãos, usando **exatamente** a mesma definição de staleness (heartbeat do lock
singleton) que `gerente_state.py` (E8.2) já usa em `detect-crash`/`reconcile`
(`_read_lock_info`/`lock_is_stale`/`DEFAULT_STALE_AFTER_SECONDS`, importados por
arquivo — nunca um timeout paralelo reinventado). A varredura inteira é **pulada** (zero
tickets tocados) sempre que existe QUALQUER lock held-e-fresco em disco — conservador
por construção: só varre quando é objetivamente seguro assumir "nenhum ciclo do Gerente
está vivo agora". Diferente de `reconcile()` (que exige um `--cycle-id` de um crash já
detectado e itera só os despachos rastreados em `estado-atual.yaml`), este comando é um
complementar mais amplo: varre `board.yaml` inteiro por `status: em-implementacao`, sem
depender de nenhum despacho ter sido registrado — rede de segurança para quando o
próprio rastro de despacho se perdeu. É o único comando deste script que ESCREVE (muta
o campo `status:` do `.md` + anexa uma linha em `## Log`, depois regenera `board.yaml`
reusando `rebuild_board.py::load_tickets`/`render_board_yaml` por import direto) —
deliberado: é uma correção mecânica de um único campo sob uma condição objetiva e
auditável, a mesma categoria de exceção que `transition_ledger_entry.py` já é para
Entradas de Ledger (mutação direta, não uma skill conversacional).

`escalation.config.json` (commitado, editável pelo dono): `dead_letter_limit_days`
(default 3), `sample_size` (default 3), `orphan_stale_after_seconds` (default 900 —
mesmo valor de `DEFAULT_STALE_AFTER_SECONDS`, repetido aqui só para ficar editável sem
tocar `gerente_state.py`; ausente cai para o valor de `gerente_state.py` em runtime,
nunca um número diferente).

## Suspeitas de falso-positivo (Semgrep) (E13.4)

Story E13.4 (`ideias/sistema-artifacts/E13-4-loop-fp-briefing.md`), PRD 04 FR-2. Fecha
o loop aberto pela Story E7.3: `flag_suspected_fp.py` (`semgrep/scripts/`) já escreve
uma entrada JSON em `project_controll/semgrep-fp-suspects.jsonl` toda vez que um agente
headless usa a válvula de escape do hook de pre-commit para deixar um commit prosseguir
apesar de uma violação `status: active` — mas até esta story ninguém lia esse log de
volta; a única forma de descobrir uma suspeita era abrir o `.jsonl` manualmente.

**`read_fp_suspects.py list-pending`** — leitor **estritamente somente-leitura**
(nenhum `open(..., "w"/"a")` no script inteiro): lê o `.jsonl` inteiro, agrupa por
`fingerprint` (`rule_id::file::line`, o mesmo formato de `flag_suspected_fp.py`)
mantendo só a entrada MAIS RECENTE de cada um (o log é append-only e cronológico — a
última linha de um fingerprint é sempre o status mais atual conhecido), e devolve as
que ainda estão `status: pending_ratification`. Nunca muta `rules.yaml`, nunca muta o
próprio `.jsonl` — a ratificação de uma suspeita (aceitar como FP de verdade, rejeitar,
promover a regra em `rules.yaml`) é gesto de **outro fluxo** (dono/oráculo), fora do
escopo desta story: ela é representada, para este leitor, como uma nova linha
append-only no MESMO `.jsonl` com o MESMO fingerprint e `status` diferente de
`pending_ratification` (ex.: `ratified`) — assim que essa linha existir, o fingerprint
desaparece de `pending` na próxima leitura, sem que nenhuma linha anterior seja apagada
ou reescrita (log inteiro continua auditável e git-trackable).

A persona repassa a saída (`pending`) como `--semgrep-fp-pending-json` ao próximo
`write-snapshot`, populando `semgrep_fp_pending` em `estado-atual.yaml` (ver Schema
acima) — de onde `gerente_briefing.py` (write-briefing) lê e renderiza a seção
"Suspeitas de falso-positivo (Semgrep)" (fingerprint + rule_id/file:line + reason +
status) sem nenhum rework, mesmo padrão aditivo já usado por `escalation_sample_review`/
`escalation_dead_letter` (E9.5).

## Roteamento de produto (E9.6)

Story E9.6 (PRD 05 FR-1/FR-1b), `product-routing.md` (protocolo completo — o teste de 3
perguntas, as exclusões duras, o viés de segurança "na dúvida, roteia", a tabela de 3
vias, a regra dura da Coverage Matrix e o caso combinado — leia-o por inteiro antes da
primeira vez que este sub-passo disparar) + `scripts/gerente_product_routing.py`
(detector mecânico, comando único). Dentro do sub-passo 1 (`list-escalated`) de
"Escalonamento decidido pelo Gerente (E9.5)" acima, ANTES de decidir a `trilha`: o
Gerente classifica se o ticket **altera o produto** (teste ancorado em `trigger-map` +
Coverage Matrix `_bmad-output/C-UX-Scenarios/00-ux-scenarios.md` + `product-decisions.md`
— a "verdade de produto documentada") e, se sim, escolhe entre 3 vias:

- **(i) precisa de design** (ou toca uma página/cenário da Coverage Matrix — regra dura,
  sem exceção) → `trilha: wds` (execução real do Pass `wds-8` é E9.8, fora desta story).
- **(ii) regra pequena já decidida** (sem tocar Coverage Matrix) → ortogonal à `trilha`;
  registra a mudança como uma decisão-de-produto no Ledger (`wiki/ledger/decisao-de-produto/`,
  via o contrato `on_complete`). *(O registro via QA-builder foi removido deste kit — a
  via (ii) agora registra direto no Ledger.)*
- **(iii) não altera produto** → nenhuma ação de documento; `trilha` segue decidida
  normalmente pelo trabalho real do ticket.

**Caso combinado** (toca Coverage Matrix **e** bate uma decisão registrada) → via (i)
**domina**; o enrich de `product-decisions.md` acontece como efeito colateral do mesmo
ticket, nunca como via (ii) isolada em paralelo.

**`gerente_product_routing.py check-coverage-touch`** — único comando, só-leitura,
stdlib only. Mecaniza SÓ a sub-pergunta objetiva "o ticket toca uma página/cenário da
Coverage Matrix?" (a regra dura §5 de `product-routing.md`) — parseia os blocos
`**Pages:**` de cada cenário de `00-ux-scenarios.md` e compara (normalizado: minúsculas,
sem acento, substring em qualquer direção, com um guardrail de tamanho mínimo de 3
caracteres — achado real de auto-revisão: sem ele, termos curtos como "a"/"de"/"e"
batiam como substring em quase toda página do documento, produzindo `forced_route_i:
true` espúrio em qualquer ticket) contra os termos tocados que o Gerente extrai do
`area`/`## Locais afetados`/descrição do ticket. Um match POSITIVO **força**
mecanicamente a via (i) — é o único ponto deste protocolo em que o script decide, porque
a regra em si É mecânica (via ii é contratualmente read-only da design truth, nunca
poderia corrigir a Coverage Matrix mesmo que tentasse). Um resultado NEGATIVO nunca prova
"não altera" — é só ausência de match textual; o teste de 3 perguntas por julgamento
continua obrigatório antes de concluir via (iii). O restante da classificação (altera ou
não, via i vs. ii) permanece 100% julgamento — mesma disciplina de "gate de confiança
nunca por sensação" (E9.1)/"promoção ao Ledger é julgamento" (E9.5): o que é
objetivamente verificável vira mecânica testável, o que é julgamento nunca ganha
heurística fixa.

## Execução da via (i) — wds-8 nunca headless (E9.8)

Story E9.8 (PRD 05 FR-6, `ideias/fase-0-spikes.md` § S3 — **testado ao vivo: `wds-8`
travou headless**, não é hipótese). Fecha a **última story do Epic E9**. Contrato
completo em `wds-routing.md` (protocolo, o gate mecânico de (a), a fronteira A/S/D-only)
— leia-o por inteiro antes da primeira vez que um Ticket com `trilha: wds` chegar à fase
"despachar" de `.claude/agents/gerente-geral.md`.

**Regra dura, sem exceção:** nenhum fluxo autônomo (o Gerente, nem qualquer sub-agente
que ele despache) invoca `wds-8` (ou qualquer `workflow-*.md` dele) como headless — as
travas `WAIT FOR INPUT`/`NEVER generate content without user input` são turn-yields
semânticos, não diálogos de permissão que auto-approve resolve (S3, reproduzido ao vivo).

**A decisão, quando `trilha: wds` chega à fase "despachar":** (a) oráculo in-thread —
você mesmo aplica Analyze/Scope/Design como conhecimento (nunca invocando `Skill(wds-8)`)
e escreve direto nos três documentos canônicos (`00-ux-scenarios.md`/`trigger-map.md`/
`product-decisions.md`); OU (b) espera o dono — o Ticket vai para `precisa-de-info`,
citando que só o dono, interativo, pode honrar as travas do `wds-8`. **(b) é o padrão.**
(a) é **gateado**, não um interruptor manual — reaproveita o PRÓPRIO Protocolo do
Oráculo (E9.1): `record-decision --tipo decisao-de-produto` só honra `--confidence high`
para "executar (a)" se existir um `--precedent` real (uma execução anterior de (a) já
ratificada pelo dono). Sem precedente — o caso inicial/normal — o script rebaixa
mecanicamente para `low`, `proceed_dispatch: false`, e a via cai em (b) **por
construção**, não por convenção. Nenhum config novo, nenhum script novo — o mesmo
mecanismo de confiança de E9.1/E9.2 é a máquina de gate inteira.

**Fronteira A/S/D-only:** `[I]/[T]/[P]` (Implement/Test/Publish — branch/PR/deploy) do
`wds-8` **nunca** acontecem no fluxo autônomo, em nenhum modo — já barrado
estruturalmente ("Gerente nunca executa código"), reforçado explicitamente no modo (a)
("pare no Design"), e confirmado pelo Não-Objetivo do PRD 05 ("Implement/Test/Deploy são
BMad", nunca `wds-8`). A via (ii) (registro leve no Ledger) segue 100% autônoma — nunca
toca este protocolo.

## Lock singleton (F9)

`.lock/` é um **diretório**, não um arquivo — `os.mkdir()` é atômico no nível do
filesystem (falha com `FileExistsError` se já existir), a mesma garantia que
`open(..., O_CREAT|O_EXCL)` daria para um arquivo, sem TOCTOU entre "checar se existe" e
"criar". Dentro dele, `info.json` carrega `{token, pid, acquired_at, heartbeat_at,
note}`.

### Por que não é baseado em PID sozinho

Não há um único processo de SO de vida longa que represente "o Gerente" neste harness —
cada chamada de `gerente_state.py` via `Bash` tool é um processo curto que morre ao
retornar; o "Gerente" de verdade é uma sessão/agente LLM orquestrando chamadas de tool.
Por isso:
- **`--pid` é opcional e best-effort** (default `null`). Quando informado com um PID que
  de fato representa algo de vida longa (ex.: um processo `sleep`/daemon de teste, ou
  futuramente o processo raiz da sessão headless), um PID morto é um atalho de detecção
  **mais rápido** — a checagem `os.kill(pid, 0)` já marca o lock como reclamável mesmo
  antes do silêncio de heartbeat atingir o limiar (provado em
  `test_gerente_state.py::test_dead_pid_shortcut`).
- **O sinal primário e obrigatório é o SILÊNCIO de heartbeat**, não idade fixa do ciclo:
  `stale = (pid não está vivo) OU (agora - heartbeat_at > --stale-after-seconds)`. Um
  ciclo longo que segue chamando `refresh-lock` periodicamente nunca fica "velho" por si
  só — só fica reclamável se **parar** de dar heartbeat. Isso alinha com o modelo de
  heartbeat que E11.2 vai generalizar depois (não uma decisão isolada desta story).
  `DEFAULT_STALE_AFTER_SECONDS = 900` (15min) — quem segura o lock por um ciclo longo
  **deve** chamar `refresh-lock` com intervalo menor que isso (ex.: a cada transição de
  fase do loop de 6 fases).

### Reclaim sem TOCTOU

Quando `acquire-lock` encontra o diretório já existente e o considera stale, ele **não**
apaga e recria diretamente (isso seria uma janela TOCTOU: dois processos podendo os dois
decidir "stale" e os dois tentarem apagar/recriar). Em vez disso, ele tenta
`os.rename(lock_dir, nome_temporário_único)` — `rename` é atômico no filesystem: **só um
processo pode vencer** um rename de um dado nome de origem (os outros recebem
`FileNotFoundError` e voltam para o topo do loop, disputando de novo via `mkdir`, dessa
vez contra um path livre). Quem venceu o rename limpa o diretório roubado e também volta
a disputar via `mkdir` normalmente — **não força a própria vitória**, só remove o lock
morto da disputa. Provado em `test_gerente_state.py::test_mutual_exclusion` (25
concorrentes → exatamente 1 vencedor) e `::test_stale_vs_fresh_heartbeat` (reclaim só
depois do silêncio, nunca antes).

### Posse via token, não via PID

`acquire-lock` gera um `token` (`uuid4`) e o devolve ao chamador — `refresh-lock` e
`release-lock` exigem esse `--token` e recusam (`reason: not-owner`) se não bater com o
holder atual. Isso desacopla "prova de posse" (o token) de "sinal de liveness" (PID/
heartbeat) — um holder legítimo sempre consegue provar posse mesmo que seu PID nominal
não seja rastreável neste ambiente.

### `--cycle-id` no lock — evita um falso-positivo de crash

O lock também carrega o `cycle_id` do ciclo que está abrindo (`acquire-lock --cycle-id
...`). Isso existe para um caso adversarial real encontrado em auto-revisão: um scanner
ingênuo de `diario.jsonl` (só olhando `CICLO-INICIO` sem `CICLO-FIM`) confundiria um
**ciclo longo e saudável rodando em outra sessão** — que por definição tem um início
aberto até terminar — com um crash. `detect-crash` cruza o `cycle_id` de qualquer início
órfão contra o `cycle_id` de um lock **held e não-stale** no momento da checagem; se
baterem, aquele "início órfão" é excluído dos órfãos reportados (é só um ciclo em
andamento, não um crash) — ver `excluded_active_cycle_id` na saída e o teste
`test_no_false_positive_for_healthy_long_cycle`. Assim que o heartbeat desse lock parar
(silêncio > `--stale-after-seconds`), a exclusão deixa de se aplicar e o mesmo ciclo
volta a acender corretamente como crash.

### Rede de segurança em `acquire-lock`

Toda `acquire-lock` bem-sucedida também roda a checagem de `detect-crash` internamente
(excluindo o `cycle_id` que acabou de ser adquirido) e anexa `pending_crash` à resposta
quando encontra algo — mesmo que o chamador esqueça de rodar `detect-crash`
explicitamente antes, o sinal de "há um crash não reconciliado" é impossível de passar
despercebido na própria resposta do `acquire-lock`. Isso não bloqueia a aquisição (a
reconciliação em si continua sendo uma decisão da persona, não uma trava mecânica) — é
um reforço estrutural, não uma garantia de enforcement total (ver Concern residual no
Dev Agent Record da story).

### Guard mecânico de `open-dispatch` (Story E15.4)

A "rede de segurança" acima (`acquire-lock` roda `detect-crash` internamente e anexa
`pending_crash` à resposta) é deliberadamente **não-bloqueante** — E8.2 rejeitou
corretamente gatear `acquire-lock`, porque ele é usado também para inspeção pura de
estado (`check-lock` chama a mesma primitiva de leitura, e travar a aquisição do lock em
si quebraria esse uso). O gap real nunca foi `acquire-lock` — era o passo SEGUINTE: nada
impedia a persona de pular de "adquiri o lock" direto para
`gerente_dispatch.py open-dispatch` sem nunca ter rodado `detect-crash`/`reconcile` de
fato (a rede de segurança só *reporta*, nunca *impede*).

Story E15.4 fecha esse gap com um **sentinela leve por `cycle_id`**:
`detect-crash --cycle-id X`/`reconcile --cycle-id X` (e, por composição,
`gerente_wake.py wake-attempt` quando `proceed: true`) gravam, ao rodar — mesmo quando
não encontram nada para reconciliar —, um arquivo `<root>/.crash-check-sentinels/
<cycle_id>.json` (`{cycle_id, source, checked_at[, detail]}`, escrita atômica, mesma
primitiva `write_atomic` de sempre). `gerente_dispatch.py::open-dispatch --cycle-id X`
passa a EXIGIR esse sentinela: se ausente, recusa (`ok:false`, exit 1) ANTES de qualquer
escrita — `request.yaml` nunca chega a ser criado. O sentinela é escopado estritamente
por `cycle_id` (nunca global) — o de um ciclo A nunca libera `open-dispatch` de um ciclo
B. `acquire-lock`/`check-lock`/qualquer leitura continuam **livres**, sem exigir nenhum
sentinela — o guard é só sobre `open-dispatch`.

`--cycle-id` em `detect-crash` é **opcional e retrocompatível**: omitido, o comando
continua em modo diagnóstico puro (nenhum sentinela gravado) — só a persona, no seu passo
0 da Ativação, decide o `cycle_id` do ciclo novo com antecedência e o passa
explicitamente. `reconcile --cycle-id` já era obrigatório e sempre grava o sentinela para
o `cycle_id` que reconciliou. Ver `.claude/agents/gerente-geral.md` § Ativação (passo 0)
para a sequência exata que a persona segue, e `test_gerente_state.py` §[6]/
`test_gerente_dispatch.py` §[13]/`test_gerente_wake.py` §[7] para as provas mecânicas
(bloqueio, liberação, escopo por `cycle_id`, e que `acquire-lock`/`check-lock` continuam
livres).

### Preempção pela presença interativa do dono

FR-11/F9: *"se o dono abre o chat interativamente enquanto o Gerente noturno roda, a
presença do dono preempta/pausa o loop autônomo"*. Esta story (E8.2) entrega o
**mecanismo observável** (`acquire-lock`/`check-lock` recusam corretamente quando já há
um holder vivo) — a **ação** de parar/ceder o loop autônomo ao detectar isso é
comportamento da persona (`gerente-geral.md` § Ativação, já atualizado por esta story
para chamar `check-lock` antes de decidir iniciar um ciclo). Matar/sinalizar um processo
autônomo em execução (supervisão de processo) é fora de escopo de E8.2 — este diretório é
uma camada de *estado*, não um supervisor; isso é território de E8.8 (wake local).

## Recuperação de crash (F23)

`diario.md`/`diario.jsonl` são a **fonte de verdade primária** para detectar um crash —
`estado-atual.yaml` é só corroborativo, nunca confiado cegamente (é exatamente o texto
do PRD 00 §4.8: *"não confia no estado-atual.yaml cegamente"*). Algoritmo de
`detect-crash`: varre `diario.jsonl` inteiro, empilha `CICLO-INICIO` por `cycle_id`,
desempilha em `CICLO-FIM`; qualquer `cycle_id` que sobra no fim é um ciclo que começou e
nunca terminou → `crashed: true`.

### Checklist de reconciliação (o que `reconcile` faz, na ordem)

1. Lê `estado-atual.yaml`; só usa o array `dispatches` se `cycle.id` bater com o
   `cycle_id` órfão detectado (senão registra a discrepância em `notes` e segue sem
   despachos rastreáveis — não inventa dados).
2. Para cada despacho em voo: verifica se `status` já é terminal
   (`concluido|falhou|reconciliado`); se não, é suspeito.
3. Cruza o(s) `ticket(s)` do despacho contra `project_controll/tickets/board.yaml`
   (leitura, **nunca escrita** — `reconcile` é puramente diagnóstico) — um ticket ainda
   `em-implementacao` é um forte sinal de órfão. Quando o despacho carrega `dispatch_id`
   (Story E8.4), a lista COMPLETA de tickets é resolvida lendo
   `dispatches/{dispatch_id}/request.yaml` (fonte de verdade), não só o `ticket` singular
   do retrato.
4. Se o despacho registrou um `worktree`, verifica se o path ainda existe em disco
   (órfão removido) ou ainda existe (precisa de verificação manual — pode estar
   mergeável ou pode ser lixo).
4b. **(Story E8.4)** Se o despacho carrega `dispatch_id`, verifica se
   `dispatches/{dispatch_id}/DONE.marker` existe — sua ausência é mais um motivo de
   órfão, cruzando diretamente o contrato de despacho em disco (`dispatch-contract.md`)
   com este checklist. Os dois mecanismos convergem aqui: o `dispatch_id` é o elo que
   liga o retrato de E8.2 ao contrato file-mediated de E8.4.
5. Reporta `orphans` (lista) + `recommended_next_step` — **nunca move o Ticket sozinho**;
   a recomendação é sempre invocar `bagual-tickets` (composição, nunca editar
   `board.yaml` à mão — mesma regra que `gerente-geral.md` já segue para toda escrita de
   Ticket).
6. Anexa um resumo ao diário (`reconciliei: N despacho(s) verificado(s), M órfão(s)`) e
   um `CICLO-FIM ... (reconciled)` sintético para o `cycle_id` órfão — fechando o ciclo
   no diário para que `detect-crash` pare de acender para ele. **Isto acontece antes de
   qualquer decisão nova do ciclo seguinte**, por construção: a persona chama
   `detect-crash` → se `crashed: true`, chama `reconcile` → só então prossegue para
   `priorizar`/`despachar` do ciclo novo (ver `gerente-geral.md` § Ativação).

## Referência de CLI

```
python3 project_controll/gerente/scripts/gerente_state.py write-snapshot \
  --root project_controll/gerente --marker start|end --cycle-id ID --started-at ISO \
  [--ended-at ISO] --phase FASE [--stop-reason cota|fila-vazia|bloqueio] \
  [--dispatches-json '[...]'] [--pending-json '[...]'] [--escalated-json '[...]'] \
  [--sample-review-json '[...]'] [--dead-letter-json '[...]'] \
  [--semgrep-fp-pending-json '[...]']   # Story E13.4, saída de read_fp_suspects.py list-pending \
  [--priorities-json '[...]'] [--quota-five-hour N] [--quota-seven-day N] \
  [--quota-source STR] [--quota-read-at ISO] \
  [--quota-self-tokens N] [--quota-self-pct N] [--quota-stronger-pct N] \
  [--quota-stronger-source STR]   # 4 últimos: Story E8.3, ver `check`'s write_snapshot_quota_args \
  [--last-briefing-at ISO]

python3 project_controll/gerente/scripts/gerente_state.py append-diario \
  --root project_controll/gerente --event EVENTO --cycle-id ID [--text STR] [--ts ISO] \
  [--reconciled]   # só --event CICLO-FIM

python3 project_controll/gerente/scripts/gerente_state.py acquire-lock \
  --root project_controll/gerente [--pid N] [--note STR] [--cycle-id ID] \
  [--stale-after-seconds N=900]

python3 project_controll/gerente/scripts/gerente_state.py refresh-lock \
  --root project_controll/gerente --token TOKEN [--pid N] [--cycle-id ID]

python3 project_controll/gerente/scripts/gerente_state.py release-lock \
  --root project_controll/gerente --token TOKEN

python3 project_controll/gerente/scripts/gerente_state.py check-lock \
  --root project_controll/gerente [--stale-after-seconds N=900]

python3 project_controll/gerente/scripts/gerente_state.py detect-crash \
  --root project_controll/gerente [--stale-after-seconds N=900] \
  [--cycle-id ID]   # Story E15.4 — se informado, grava o sentinela de crash-check para ID
                    # (guard de open-dispatch); omitido: modo diagnóstico puro, retrocompat

python3 project_controll/gerente/scripts/gerente_state.py reconcile \
  --root project_controll/gerente --cycle-id ID [--board-path PATH]
  # sempre grava o sentinela de crash-check (E15.4) para --cycle-id, além do trabalho
  # de reconciliação de sempre

python3 project_controll/gerente/scripts/gerente_quota.py read-limits \
  [--root project_controll/gerente] [--path ~/.claude/rate-limits-state.json] \
  [--stale-snapshot-seconds N=900]

python3 project_controll/gerente/scripts/gerente_quota.py record-usage \
  --root project_controll/gerente --cycle-id ID --tokens N [--note STR] \
  [--multiplier N=1.15] [--reset]

python3 project_controll/gerente/scripts/gerente_quota.py check \
  --root project_controll/gerente --cycle-id ID \
  [--limits-path ~/.claude/rate-limits-state.json] [--threshold-pct N=85.0] \
  [--self-tracked-budget-tokens N=300000] [--stale-snapshot-seconds N=900] \
  [--stop-diario]

python3 project_controll/gerente/scripts/gerente_dispatch.py open-dispatch \
  --root project_controll/gerente [--dispatch-id ID] --cycle-id ID \
  --tickets-json '["TCK-123"]' --unit epic-E8 --trilha rapida|spec|epic|wds|correct-course \
  [--worktree PATH] --skill bagual-epic-runner [--model sonnet=default] [--note STR]
  # Story E15.4 — EXIGE um sentinela de crash-check já gravado para --cycle-id
  # (detect-crash/reconcile --cycle-id, ou wake-attempt no caminho de wake); recusa
  # (ok:false, exit 1, nada escrito) se ausente — ver § Guard mecânico acima

python3 project_controll/gerente/scripts/gerente_dispatch.py close-dispatch \
  --root project_controll/gerente --dispatch-id ID --outcome sucesso|falhou|pendencias \
  --verdict STR [--pending-json '[...]'] [--evidence-json '{...}'] [--closed-by STR] [--force]

python3 project_controll/gerente/scripts/gerente_dispatch.py read-result \
  --root project_controll/gerente --dispatch-id ID

python3 project_controll/gerente/scripts/gerente_dispatch.py list-inflight \
  --root project_controll/gerente [--cycle-id ID]

python3 project_controll/gerente/scripts/gerente_dispatch.py reconcile-orphan-dispatch \
  --root project_controll/gerente --dispatch-id ID [--board-path PATH]

python3 project_controll/gerente/scripts/gerente_proactive.py next-task \
  --root project_controll/gerente --cycle-id ID [--cap-per-cycle N=3]

python3 project_controll/gerente/scripts/gerente_proactive.py dedup-check \
  --root project_controll/gerente [--tickets-dir project_controll/tickets] \
  --title STR [--description STR] [--threshold N=0.30] [--top-n N=5] \
  [--include-non-proactive]

python3 project_controll/gerente/scripts/gerente_proactive.py record-proactive \
  --root project_controll/gerente --cycle-id ID \
  --category analise-adversarial-feature|completude-de-testes|descoberta-de-padroes|refino-de-tickets \
  --outcome STR [--tickets-filed-json '["TCK-..."]'] [--duplicates-skipped N=0] \
  [--note STR] [--cap-per-cycle N=3] [--reset]

python3 project_controll/gerente/scripts/gerente_briefing.py write-briefing \
  --root project_controll/gerente --cycle-id ID [--started-at ISO] [--ended-at ISO] \
  --stop-reason cota|fila-vazia|bloqueio [--stop-detail teto-proativo] \
  [--diario-jsonl-path PATH] [--estado-path PATH] [--ts ISO]

python3 project_controll/gerente/scripts/gerente_briefing.py detect-unread \
  --root project_controll/gerente

python3 project_controll/gerente/scripts/gerente_briefing.py mark-read \
  --root project_controll/gerente (--date YYYYMMDD | --path PATH) [--ts ISO]

python3 project_controll/gerente/scripts/gerente_wake.py wake-attempt \
  --root project_controll/gerente [--note STR] [--cycle-id ID] \
  [--stale-after-seconds N=900]   # default = DEFAULT_STALE_AFTER_SECONDS de gerente_state.py

python3 project_controll/gerente/scripts/gerente_oracle.py record-decision \
  --ledger-root wiki/ledger [--tipo decisao-tecnica=default|decisao-de-produto|decisao-de-arquitetura] \
  --ticket TCK-123 --question STR --decision STR --justification STR --context STR \
  [--alternatives STR] [--areas "sistema-orquestrador,gerente-geral,oraculo"=default] \
  [--confidence low=default|high] [--precedent PATH] [--slug STR]

python3 project_controll/gerente/scripts/gerente_oracle.py list-pending \
  --ledger-root wiki/ledger [--ticket TCK-123]

python3 project_controll/gerente/scripts/gerente_oracle.py set-ratification \
  (--entry PATH | [--ledger-root wiki/ledger] --ticket TCK-123) \
  --status ratified|corrected [--note STR]

python3 project_controll/gerente/scripts/gerente_style.py consult-precedent \
  --ledger-root wiki/ledger \
  --tipo decisao-tecnica=default|decisao-de-produto|decisao-de-arquitetura \
  --areas "a,b" [--keywords "c,d"] [--oracle-config PATH] \
  [--product-decisions-path PATH] [--decisions-path PATH]

python3 project_controll/gerente/scripts/gerente_style.py sm2 \
  --ledger-root wiki/ledger \
  [--tipo decisao-tecnica|decisao-de-produto|decisao-de-arquitetura] [--verbose]

python3 project_controll/gerente/scripts/gerente_escalation.py list-escalated \
  [--board-path project_controll/tickets/board.yaml] [--pretty]

python3 project_controll/gerente/scripts/gerente_escalation.py dead-letter-check \
  [--board-path project_controll/tickets/board.yaml] [--limit-days N] [--config PATH] [--pretty]

python3 project_controll/gerente/scripts/gerente_escalation.py sample-decisions \
  [--board-path project_controll/tickets/board.yaml] \
  [--state-path project_controll/gerente/sampled-decisions.json] \
  [--sample-size N] [--config PATH] [--pretty]

python3 project_controll/gerente/scripts/gerente_escalation.py record-sample-review \
  [--state-path project_controll/gerente/sampled-decisions.json] \
  --ticket TCK-123 --verdict ratificado|corrigido \
  [--trilha-auto STR] [--trilha-corrigida STR] [--note STR] \
  # --verdict corrigido (E15.3, T2.3): EXIGE, além de --trilha-auto/--trilha-corrigida,
  # os campos de rastro de decisão abaixo — grava record_decision + set_ratification
  # (status: corrected) na MESMA invocação (import direto de gerente_oracle.py):
  [--question STR] [--justification STR] [--context STR] \
  [--decision STR] [--tipo decisao-tecnica=default|decisao-de-produto|decisao-de-arquitetura] \
  [--areas "a,b"=escalonamento,gerente-geral,trilha] \
  [--ledger-root wiki/ledger] [--oracle-config PATH]

python3 project_controll/gerente/scripts/gerente_escalation.py orphan-sweep \
  [--gerente-root project_controll/gerente] [--tickets-dir project_controll/tickets] \
  [--board-path project_controll/tickets/board.yaml] \
  [--stale-after-seconds N=900] [--config PATH] [--dry-run] [--pretty]

python3 project_controll/gerente/scripts/read_fp_suspects.py list-pending \
  [--log project_controll/semgrep-fp-suspects.jsonl] [--pretty]

python3 project_controll/gerente/scripts/gerente_product_routing.py check-coverage-touch \
  [--coverage-matrix-path _bmad-output/C-UX-Scenarios/00-ux-scenarios.md] \
  --touched "termo1,termo2,..."
```
Ver `dispatch-contract.md` para o contrato completo dos 5 comandos `gerente_dispatch.py`
(schema de `request.yaml`/`result.yaml`, garantia de ordem, detecção dual). Ver
`proactive-catalog.md` para o conteúdo/guardrails das 4 categorias dos 3 comandos
`gerente_proactive.py` acima. Ver § Oráculo (E9.1) acima para o gate de confiança
completo dos 3 comandos `gerente_oracle.py`, e § Aprendizado de estilo (E9.2) para os 2
comandos `gerente_style.py` + o `--oracle-config`/histórico que agora também gateia
`record-decision`.

Todos os comandos imprimem uma linha de JSON (`ok`/`acquired`/`held`/`crashed` conforme
o comando) — o mesmo espírito "write-only, echo o novo estado" de `memlog.py`, para que
quem chama nunca precise reler o arquivo para saber onde está.

## Como a persona usa isto (ver `.claude/agents/gerente-geral.md` § Ativação)

**Wake local (Story E8.8) — só quando esta ativação foi disparada por `loop`/
`CronCreate`, ver `wake.md` e § Wake local (E8.8) acima:**
0. ANTES de tudo abaixo, `gerente_wake.py wake-attempt` já rodou (fora do agente, pelo
   `PROMPT-DE-WAKE`) e só invocou `Agent(subagent_type: "gerente-geral")` quando
   `proceed: true` — a persona recebe `cycle_id`/`token` já prontos no prompt de
   despacho. Nesse caso, os passos 1-2 abaixo são PULADOS (o wake já fez o
   crash-check por composição via `acquire_lock`, e já é o holder do lock) — chame
   `reconcile --cycle-id <órfão>` só se o wake sinalizou `pending_crash`. O passo 3
   (`acquire-lock`) também é PULADO — o wake já é o holder. Fora desse caminho
   (ativação interativa direta, ou headless sem ter passado por um wake), ignore este
   bullet e siga 1-4 normalmente. **Guard de `open-dispatch` (E15.4):** `wake-attempt`
   já gravou o sentinela de crash-check para este `cycle_id` — a persona nunca precisa
   rodar `detect-crash --cycle-id` de novo só por causa do guard neste caminho.

Na ativação, antes de decidir qualquer coisa:
1. `check-lock` — se `held: true` e não `stale`, outra instância (ou o dono) está ativa;
   não inicia um ciclo novo.
2. Decide `<novo-id>` (o cycle_id do ciclo que vai abrir) e roda
   `detect-crash --cycle-id <novo-id>` — se `crashed: true`, chama
   `reconcile --cycle-id <órfão>` **antes** de prosseguir. **Guard de `open-dispatch`
   (E15.4):** passar `--cycle-id <novo-id>` aqui grava o sentinela que `open-dispatch`
   exigirá na fase "despachar" — sem ele, todo despacho deste ciclo é recusado mesmo
   com o lock já adquirido (ver § Guard mecânico de `open-dispatch` acima).
3. `acquire-lock --cycle-id <novo-id>` — o MESMO id do passo 2, só então adquire o lock
   para o ciclo novo; guarda o `token`. Passar `--cycle-id` aqui é o que permite a um
   wake FUTURO distinguir "este ciclo está só em andamento" de "isto é um crash" (ver
   §`--cycle-id` no lock acima).
4. `write-snapshot --marker start` no início do ciclo (otimista); `refresh-lock`
   periodicamente durante; `write-snapshot --marker end` + `append-diario --event
   CICLO-FIM` + `release-lock --token ...` ao encerrar.

**Cota (Story E8.3), durante o ciclo e na fase "parar":**
5. Depois de CADA despacho retornar (e periodicamente para os próprios turnos), chama
   `gerente_quota.py record-usage --cycle-id <mesmo id do ciclo> --tokens N --note ...`
   com uma estimativa do consumo (ver § Cota (E8.3) acima para o que contar).
6. Antes de iniciar uma NOVA unidade de trabalho (voltar à fase "priorizar"), chama
   `gerente_quota.py check --cycle-id <mesmo id> --stop-diario`. Se `verdict: "stop"`,
   **não inicia** a nova unidade — o `--stop-diario` já grava `parei-por-cota` no
   diário; a persona segue para a fase "parar" normalmente (write-snapshot end,
   CICLO-FIM, release-lock).
7. Ao escrever o `write-snapshot` final do ciclo, repassa os campos de
   `check`'s `write_snapshot_quota_args` como argumentos extras (`--quota-self-tokens`,
   `--quota-self-pct`, `--quota-stronger-pct`, `--quota-stronger-source`, além dos 4 já
   existentes de E8.2) — assim o retrato de cota do ciclo carrega os dois sinais e qual
   venceu, não só o insumo bruto.

**Despacho (Story E8.4), fases "despachar"/"revisar" — ver `dispatch-contract.md` para o
contrato completo:**
8. Fase "despachar": `open-dispatch` (exige o sentinela de crash-check do passo 2/0
   acima para este `cycle_id` — Story E15.4, ver § Guard mecânico acima) → inclui o
   `dispatch_entry` devolvido no próximo `write-snapshot --dispatches-json` → spawna o
   sub-agente executor (tool `Agent`, `model: "sonnet"`, em foreground) instruído a
   chamar `close-dispatch` como última ação.
9. Fase "revisar": o retorno do Agent tool já é o sinal primário; `read-result
   --dispatch-id ID` lê o payload (só quando `done: true`). Se `done: false` apesar do
   Agent tool ter retornado, `reconcile-orphan-dispatch --dispatch-id ID` diagnostica —
   tratado como despacho falho, Ticket nunca vira `concluido` silencioso.

**Trabalho proativo (Story E8.5), fase "priorizar" quando a fila está vazia — ver §
Trabalho proativo (E8.5) acima e `proactive-catalog.md` para o contrato completo:**
10. `next-task --cycle-id <mesmo id>` → se `cap-reached`, encerra o ramo proativo (segue
    para "parar", relatando "parei por teto proativo"); se `go`, despacha UM sub-agente
    Sonnet somente-leitura para a categoria devolvida.
11. Para cada achado do sub-agente: `dedup-check --title ... --description ...` → só
    invoca `bagual-tickets --headless` quando `duplicate: false`; sempre
    `record-proactive` uma vez ao fim da iteração, então volta ao passo 10.

**Briefing (Story E8.7) — ativação (passo 5, só sessão interativa) e fase "parar" (passo
6) — ver § Briefing (E8.7) acima para o contrato completo:**
12. Ativação, depois dos passos 1-4: `detect-unread` — para cada entrada `status: unread`,
    lê o arquivo e renderiza o conteúdo inteiro na resposta, depois `mark-read --date
    <data> --expected-last-cycle-id <last_cycle_id devolvido por detect-unread>` (o
    compare-and-swap que evita clobbrar uma seção nova escrita por um ciclo headless
    concorrente — ver § Briefing (E8.7) acima "Race entre detect-unread e mark-read"; se
    vier `error: "stale"`, re-detecta e re-renderiza antes de tentar de novo). Pulado
    silenciosamente em ciclos headless/proativos (sem dono para ler) ou quando `count: 0`.
13. Fase "parar", logo após `append-diario --event CICLO-FIM` e antes de `release-lock`:
    `write-briefing --cycle-id <mesmo id> --started-at <ts início> --ended-at <agora>
    --stop-reason cota|fila-vazia|bloqueio [--stop-detail teto-proativo]` — idempotente
    por `--cycle-id`, seguro de repetir se a fase "parar" for retomada após uma
    compactação de contexto.

**Escalonamento decidido pelo Gerente (Story E9.5) — fase "priorizar", antes de tratar a
fila `pronto-para-implementar` normal — ver § Escalonamento decidido pelo Gerente (E9.5)
acima para o contrato completo:**
14. `list-escalated` — para CADA escalado devolvido, primeiro classifica o Roteamento de
    produto (E9.6, seção acima — `check-coverage-touch` para a regra dura + o teste de 3
    perguntas por julgamento), depois decide a `trilha` via o Protocolo do Oráculo (seção
    acima — via (i) força `trilha: wds`; via (ii) registra a mudança como
    decisão-de-produto no Ledger como ação ortogonal; via (iii) não muda nada aqui), e por fim
    invoca `bagual-tickets` (Resolver) para comitar `trilha`/`escalonar: false`/`## Log`/
    `ledger_refs` — nunca reimplementa essa escrita fora da skill. Um `trilha: wds`
    comitado aqui **não** dispara `wds-8` ainda — a execução real (E9.8, seção "Execução
    da via (i)" acima) só acontece depois, quando o Ticket chega à fase "despachar".
15. `sample-decisions --sample-size N` — para cada amostra devolvida, ratifica ou
    corrige (julgamento); `record-sample-review --verdict ratificado|corrigido` grava o
    veredito; uma correção também vira `gerente_oracle.py record-decision` + `set-
    ratification --status corrected` (alimenta E9.2, ver seção acima). Inclui o
    resultado no próximo `write-snapshot --sample-review-json '[...]'`.
16. `dead-letter-check` — inclui o resultado no próximo `write-snapshot --dead-letter-
    json '[...]'`, para que `write-briefing` (passo 13) renderize os dois no Briefing.

**Suspeitas de falso-positivo (Semgrep) (Story E13.4)** — em qualquer ponto do ciclo
antes do `write-snapshot --marker end` (passo 4), tipicamente junto dos passos 15-16
acima — ver § Suspeitas de falso-positivo (Semgrep) (E13.4) acima para o contrato
completo:
17. `read_fp_suspects.py list-pending` — inclui o campo `pending` devolvido no próximo
    `write-snapshot --semgrep-fp-pending-json '[...]'`, para que `write-briefing` (passo
    13) renderize a seção "Suspeitas de falso-positivo (Semgrep)" no Briefing. Este
    passo nunca escreve nada — só lê `project_controll/semgrep-fp-suspects.jsonl` e
    repassa o JSON adiante; a ratificação de uma suspeita continua fora do escopo do
    ciclo do Gerente (gesto do dono/oráculo em outro fluxo).

**`orphan-sweep` NÃO vive na fase "priorizar"** — ele roda no passo 0 da "Ativação"
(seção acima), JUNTO de `detect-crash`/`list-inflight`, mas **sempre ANTES** do próprio
`acquire-lock` do ciclo novo. Achado real de auto-revisão adversarial desta story:
`orphan-sweep` só reverte quando NENHUM lock estiver held-e-fresco em disco; se rodasse
DEPOIS de `acquire-lock` (ex.: aqui na fase "priorizar"), o PRÓPRIO lock recém-adquirido
já estaria fresco, e a varredura nunca reverteria nada — o lock representa "existe algum
ciclo vivo agora", e a persona rodando este comando já É esse ciclo depois de adquirir o
lock. Antes de `acquire-lock`, held-e-fresco só pode ser OUTRA instância genuinamente
viva (o `check-lock` do topo do passo 0 já teria bloqueado o ciclo antes de chegar
aqui). Órfãos revertidos ali entram no diário (`append-diario --event decidi`, já na
fase "priorizar", depois do lock adquirido) e, se relevantes, no Briefing via nota
livre.

## Rodando os testes

```
python3 project_controll/gerente/scripts/test_gerente_state.py
python3 project_controll/gerente/scripts/test_gerente_quota.py
python3 project_controll/gerente/scripts/test_gerente_dispatch.py
python3 project_controll/gerente/scripts/test_gerente_proactive.py
python3 project_controll/gerente/scripts/test_gerente_briefing.py
python3 project_controll/gerente/scripts/test_gerente_wake.py
python3 project_controll/gerente/scripts/test_gerente_oracle.py
python3 project_controll/gerente/scripts/test_gerente_style.py
python3 project_controll/gerente/scripts/test_gerente_escalation.py
python3 project_controll/gerente/scripts/test_gerente_product_routing.py
python3 project_controll/gerente/scripts/test_read_fp_suspects.py
```

28 + 33 + 42 + 31 + 71 + 33 + 68 + 52 + 31 + 12 + 24 = 425 asserções (71 em
`test_gerente_briefing.py` já inclui as 12 novas checagens de E13.4; 24 em
`test_read_fp_suspects.py`, novo), todas contra subprocessos reais (concorrência real
de SO via `multiprocessing` nos testes de E8.2, subprocessos simples nos demais — não
mocks): exclusão mútua do lock, reclaim por silêncio de heartbeat (nunca por idade fixa),
atalho de PID morto, detecção+reconciliação de crash, não-confusão entre ciclo saudável
ativo e crash, ausência de leitura torn durante escritas concorrentes de
`estado-atual.yaml`, sinal-mais-forte de cota nos dois sentidos, (E8.4) garantia de ordem
result-antes-de-DONE.marker, round-trip de listas de escalares puros, detecção de
despacho órfão, integração ponta-a-ponta com `detect-crash`/`reconcile` de E8.2, e (E8.5)
teto duro sem off-by-one (N=1 e N=3), dedup batendo contra histórico `concluido`/
`descartado` mas nunca contra achados genuinamente novos, e exclusão de tickets
`origem: manual` do scan por padrão. (E8.7) os 3 rótulos de `stop_reason` derivados
corretamente, nuance `teto-proativo` sem inventar um 4º valor, forward-dep E9.1 populado
vs. vazio vs. chave ausente, diário torn/linha malformada isolada sem crash, ciclo
detect-unread → mark-read idempotente → some da lista, idempotência de `write-briefing`
por `--cycle-id` (substitui, não duplica) e acréscimo de seção para um 2º ciclo no mesmo
dia calendário, data do arquivo derivada de `--ended-at` (nunca do relógio do sistema,
salvo fallback documentado), ausência de traceback para `mark-read`/`detect-unread`
contra um `--root` vazio/ausente, e o compare-and-swap de `mark-read
--expected-last-cycle-id` recusando marcar como lido quando um `write-briefing`
concorrente já acrescentou uma seção nova no meio-tempo (sem perder a seção nova). As
fixtures usadas vivem em
`ideias/sistema-artifacts/fixtures/E8/` (nunca escrevem em `project_controll/gerente/`
real — sempre um `--root` de `tempfile.TemporaryDirectory()`).

(E8.8) singleton respeitado (2º `wake-attempt` imediato sobre lock held-e-fresco defere,
`proceed:false`), wake mid-flight não dobra o decisor, dono interativo (lock adquirido
fora de qualquer wake) preempta um `wake-attempt` subsequente exatamente como qualquer
outro holder, reentrância após `release-lock` (novo `cycle_id`, `pending_crash: null`),
composição com crash-recovery de E8.2 (`CICLO-INICIO` órfão pré-existente → `wake-attempt`
seguinte devolve `pending_crash` preenchido, mas `gerente_wake.py` nunca reconcilia
sozinho — `detect-crash` direto continua acendendo depois), exit code 0 em `proceed:true`
E `proceed:false`, e ausência de qualquer import de módulo de rede/SDK de billing (varredura
mecânica das linhas `import`/`from` reais do arquivo, não do texto bruto — a própria
docstring cita os tokens como exemplo de busca). `test_gerente_wake.py` usa
`tempfile.TemporaryDirectory()` (nunca `project_controll/gerente/` real).

(E9.1) o CASO CENTRAL do F10 provado dos dois lados — `high` honrado só com precedente
`estado: ativa` + `ratification` ausente/`ratified` (`[7]`), e rebaixado para `low` em
TODOS os outros casos: sem `--precedent` (`[3]`), precedente inexistente (`[4]`),
aposentado (`[5]`), corrigido pelo dono (`[6]`), e — o teste que fecha o loop — uma
entrada que ACABOU de ser corrigida (`set-ratification --status corrected`) nunca mais
sustenta `high` como precedente de uma decisão seguinte (`[10b]`); `proceed_dispatch`
sempre `false` em todo caso de baixa confiança, nunca só um campo textual desacompanhado
de efeito real; front-matter injection recusada (`exit != 0`, nunca sanitização
silenciosa) em `--ticket`/`--precedent`/item de `--areas` com quebra de linha embutida
(`[12b]`); concorrência real com 20 processos simultâneos gravando o mesmo
ticket/decisão — 20 paths únicos, 20 arquivos sobreviventes, zero crash (`[12c]`);
`set-ratification` promovendo `candidata -> ativa` só em `ratified` (nunca em
`corrected`) e resolvendo por `--ticket` com erro explícito em ambiguidade/ausência;
`list-pending` refletindo o estado real após cada mutação, relido por um subprocess NOVO
a cada chamada (prova de persistência em disco, não de estado em memória); e
`validate_ledger.py --json` contra a árvore inteira gerada pelos testes sem nenhuma
violação. Fixtures reais (precedente `ativa`/`aposentada`/`corrected`) vivem em
`ideias/sistema-artifacts/fixtures/E9/`; o ledger-root de trabalho é sempre um
`tempfile.TemporaryDirectory()` — nunca escreve em `wiki/ledger/` real.

(E9.2) `consult-precedent` sugerindo `high` quando um precedente ratificado similar
existe, `low` quando não há overlap suficiente de `areas` (`[A]`); o MESMO overlap
absoluto (1 tag) sustentando `decisao-tecnica` (limiar 1) mas NÃO `decisao-de-produto`
(limiar 2, categoria mais sensível) — só com 2 tags é que a categoria mais estrita
também sustenta (`[B]`); **o caso central da story**: um precedente ratificado E uma
decisão corrigida similares coexistindo no mesmo Ledger sempre resolvem para `low` —
a correção nunca é ofuscada por suporte concorrente (`[C]`); o MESMO invariante dentro
do gate real de `record-decision` (não só na sugestão de `consult-precedent`) — um
`--precedent` explícito e mecanicamente válido (F10) ainda é vetado quando existe uma
`corrected` similar, com `contradicting_corrected` preenchido na resposta para
auditoria; controle positivo provando que o veto é seletivo por overlap real, não um
bloqueio cego pós-primeira-correção (`[D]`); `sm2` computando `ratified`/`corrected`/
`pending`/`decided`/`pct_ratified` a partir de uma contagem construída e conferida por
aritmética simples (nunca hardcoded no script), com e sem `--tipo`, `null` sobre um
ledger-root vazio/inexistente (nunca crash), e o `pct` mudando corretamente quando uma
NOVA ratificação real é adicionada no meio do teste (`[E]`); a varredura informacional
de `product-decisions.md`/`decisions.md` por título de seção encontrando/filtrando
corretamente, sem nunca influenciar `suggested_confidence` (`[F]`); e um
`oracle.config.json` CUSTOM (via `--oracle-config`) de fato mudando o veredito tanto de
`consult-precedent` quanto do gate real de `record-decision` — prova de que a
configurabilidade por categoria é real, não só os defaults hardcoded funcionando por
coincidência (`[G]`). Todos os ledger-roots de trabalho são `tempfile.TemporaryDirectory()`
— `wiki/ledger/` real nunca é escrita (`git status --short` conferido antes/
depois de cada rodada).

(E9.5) `list-escalated` devolve só o `escalonar: true`, nunca os auto-comitados nem o de
controle (`[1]`); `dead-letter-check` classifica corretamente um escalado com `updated`
muito antigo como dead-letter e — provado com a data REAL de hoje da máquina rodando o
teste, não uma data fixa que quebraria no futuro — um escalado atualizado agora não é
dead-letter (`[2]`); `sample-decisions` amostra só `trilha` != null + `escalonar: false`
(nunca o escalado nem o de controle), e um ticket já revisado (`record-sample-review`)
NUNCA reaparece numa amostra seguinte, provado com uma segunda chamada real (`[3]`); e
`orphan-sweep` provado nos 3 cenários que fecham o AC ("não reverte um ticket
genuinamente em voo"): nenhum lock em disco → reverte (`[4a]`); lock held-e-fresco
adquirido de VERDADE via `gerente_state.py acquire-lock` (não simulado) → NÃO reverte,
ticket órfão preservado intacto no `.md` e no `board.yaml` regenerado (`[4b]`); lock
presente mas com heartbeat artificialmente antigo (>900s, o mesmo
`DEFAULT_STALE_AFTER_SECONDS` de E8.2, citado na razão devolvida) → reverte (`[4c]`).
Todos os testes operam sobre uma CÓPIA das fixtures em `tempfile.mkdtemp()` — nunca
escrevem nas fixtures reais em `ideias/sistema-artifacts/fixtures/E9/E9-5/tickets/`,
provado por um snapshot de conteúdo byte-a-byte antes/depois da rodada inteira (`[5]`).
