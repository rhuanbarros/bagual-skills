# Wake local do Gerente Geral (Story E8.8)

> Story `ideias/sistema-artifacts/E8-8-wake-local.md` (Epic E8, última story — fecha a
> Epic). Cobre PRD 00 FR-1 (mecanismo) e §8-Q2 (decisão do dono, 2026-07-10: LOCAL, sem
> cron do SO, sem cloud). Ver também `ideias/fase-0-spikes.md` § S4 e
> `ideias/revisao-adversarial-furos.md` § F1 (resolução completa).

## O que é isto

O gatilho da "janela ociosa" do Gerente Geral — a máquina/sessão sendo aproveitada à
noite sem o dono presente. **Não existe cron do SO nem rotina cloud neste mecanismo.** O
gatilho é: **uma sessão local do Claude Code deixada aberta e rodando**, dentro da qual o
próprio harness paceia um wake — via a skill `loop` ou via `CronCreate` (agendamento
nativo, **session-only**, nunca escrito em disco, nunca persistido fora da sessão).
Quando o wake dispara, ele chama `gerente_wake.py wake-attempt` (este diretório,
`scripts/`) — um portão barato que decide, SEM spawnar nenhum sub-agente, se vale a pena
acordar o Gerente Geral (persona Opus, `.claude/agents/gerente-geral.md`) agora.

## Por que não cron do SO / não cloud (a decisão §8-Q2, resumida)

- **Cota só de assinatura, API metered proibida** (`AGENTS.md`, `ideias/prd-00-sistema-orquestrador.md`
  § Constraints). Um wake que dependesse de infraestrutura cloud (a skill `schedule` deste
  harness, que cria "routines" executadas remotamente) rodaria FORA da sessão local — sem
  garantia de que o billing continua sendo só de assinatura, e o dono foi explícito: "nunca
  passou pela minha cabeça, é local mesmo".
- **Cron do SO** (`crontab`, Task Scheduler, etc.) exigiria um processo/daemon de fora do
  harness invocando o Claude Code de forma não-interativa — infraestrutura nova, fora do
  espírito "nativo > genérico" já estabelecido (`bagual-epic-runner` já spawna sub-agentes
  localmente sem nenhum orquestrador de processo externo; este projeto não usa
  `tmux`/subprocess de orquestração em lugar nenhum).
- **Único resíduo aceito (constraint, não bug):** a sessão/máquina precisa ficar viva para
  o Gerente trabalhar de noite. Se a sessão fecha, o wake simplesmente não dispara mais —
  isso é esperado, não um caso de erro a tratar.

## Pré-requisito: sessão local viva

Este mecanismo só funciona **dentro** de uma sessão do Claude Code aberta e ociosa (REPL
livre — nenhuma consulta em andamento). Não há wake "fantasma" fora de uma sessão real:
fechar a sessão (ou a máquina) para o wake. O dono decide quando manter a sessão viva (ex.:
antes de dormir, deixar o terminal aberto).

## Os dois mecanismos locais disponíveis neste harness

Ambos rodam **dentro** da sessão aberta, nenhum escreve em cron do SO, nenhum é uma
"routine" cloud.

### Mecanismo A — skill `loop` (recomendado, mais simples de operar)

`loop` roda um prompt (ou slash command) num intervalo recorrente, ou se auto-paceia se o
intervalo for omitido — "Run a prompt or slash command on a recurring interval... Omit the
interval to let the model self-pace" (descrição nativa da skill). Fica vivo enquanto a
sessão estiver aberta; termina quando a sessão termina.

**Iniciar:**
```
/loop 15m {PROMPT-DE-WAKE abaixo}
```
(15 minutos é um ponto de partida razoável — ajuste conforme o ritmo desejado; um
intervalo menor gasta mais turnos do `wake-attempt`, mas cada tentativa que defere
(`proceed:false`) é barata: só um `os.mkdir`/leitura de arquivo local, nenhum sub-agente.)

**Parar:** peça para interromper o loop na própria sessão (ex.: "pare o loop do Gerente")
— ou simplesmente feche a sessão.

### Mecanismo B — `CronCreate` (o análogo mais próximo de "ScheduleWakeup" neste harness)

`CronCreate` agenda um prompt para ser reenfileirado num horário futuro, com semântica
**session-only**: "Jobs live only in this Claude session — nothing is written to disk, and
the job is gone when Claude exits" e "Jobs only fire while the REPL is idle" (descrição
nativa da tool). Isso é exatamente o "auto-pausando/acordando dentro da sessão aberta" que
o PRD pede — sem persistência em disco, sem execução fora da sessão viva, e com o limite
de 7 dias documentado pela própria tool (reagenda-se rodando `CronCreate` de novo se
precisar de mais tempo).

**Iniciar** (exemplo, a cada 15 min, recorrente):
```
CronCreate(cron="7,22,37,52 * * * *", recurring=true, prompt="{PROMPT-DE-WAKE abaixo}")
```
(minutos fora de `:00`/`:30` de propósito, seguindo a orientação nativa da tool para não
alinhar com o instante cheio da hora — sem efeito prático aqui, já que é 100% local e não
compete por uma janela compartilhada, mas custa nada seguir a convenção.)

**Parar:** `CronDelete(id="<id devolvido por CronCreate>")` — ou `CronList()` para
recuperar o id se perdido, ou simplesmente fechar a sessão (os jobs morrem com ela).

### Por que não confundir com a skill `schedule`

Este harness também expõe uma skill `schedule` ("Create, update, list, or run scheduled
**cloud** agents (routines) that execute on a cron schedule") — isso é exatamente o que
§8-Q2/F1 proíbe: execução fora da sessão local, potencialmente fora da cota de assinatura.
`schedule`/routines **nunca** são usados por este mecanismo, propositalmente. Se um agente
futuro considerar usar `schedule` "para automatizar melhor o wake", isso é um retrocesso à
constraint já decidida — pare e use `/loop` ou `CronCreate` em vez disso.

## O PROMPT-DE-WAKE (o texto exato que cada tick roda)

```
Rode: python3 project_controll/gerente/scripts/gerente_wake.py wake-attempt --root project_controll/gerente

Leia o JSON de saída.
- Se "proceed": true — invoque a tool Agent com subagent_type: "gerente-geral" (model
  sonnet NÃO — a persona roda em Opus, config nativa do próprio arquivo de agente), com um
  prompt que inclui literalmente: "Você foi acordado via wake local (Story E8.8,
  loop/ScheduleWakeup). cycle_id=<cycle_id>, token=<token>, pending_crash=<pending_crash
  ou null — cole o JSON aqui>. No passo 0 da sua Ativação, use a entrada alternativa via
  wake: pule a sub-etapa acquire-lock (já feita por gerente_wake.py) e, se pending_crash
  não for null, reconcilie normalmente antes de priorizar." Aguarde o retorno do Agent
  (foreground) antes de considerar este tick concluído.
- Se "proceed": false — não invoque nada. O motivo (out["reason"], geralmente "held") já
  significa que o dono está interativo ou outro ciclo está em voo; este tick termina aqui,
  sem custo adicional. Não é um erro.
```

Este é o mesmo texto, cole literalmente, para `/loop` ou para `CronCreate(prompt=...)` —
os dois mecanismos só diferem em COMO agendam, não no que cada tick faz.

## `gerente_wake.py` — o portão de entrada do ciclo

`project_controll/gerente/scripts/gerente_wake.py` (stdlib-only, reusa
`gerente_state.py::acquire_lock` por IMPORT direto do arquivo irmão — mesmo padrão de
reuso que `gerente_quota.py`/`gerente_briefing.py` já usam, não uma cópia colada).

### `wake-attempt`

```
python3 project_controll/gerente/scripts/gerente_wake.py wake-attempt \
  --root project_controll/gerente \
  [--note "texto livre"] [--cycle-id <id>] [--stale-after-seconds N]
```

Tenta `acquire_lock` (a MESMA primitiva atômica de E8.2 — `mkdir` + reclaim de stale via
`rename`, nunca uma reimplementação) em nome do wake, com um `cycle_id` gerado
automaticamente (`wake-<timestamp>-<hex>`, rotulagem só para leitura humana no diário —
não é consumido mecanicamente por nenhum outro script).

**Saída `proceed: true`** (lock livre ou stale-reclamado):
```json
{
  "ok": true, "proceed": true,
  "cycle_id": "wake-20260711T221149-068e47",
  "token": "<uuid do holder>",
  "acquired_at": "2026-07-11T22:11:49-03:00",
  "pending_crash": null,
  "note": "wake local (E8.8 — loop/ScheduleWakeup)",
  "guidance": "..."
}
```
`pending_crash` vem preenchido (não `null`) quando o lock reclamado era stale E existe um
`CICLO-INICIO` órfão no diário — o mesmo campo que `acquire_lock` já expõe como rede de
segurança desde E8.2, aqui só repassado tal e qual (`gerente_wake.py` NUNCA chama
`reconcile` sozinho — reconciliar é julgamento da persona, no passo 0 da Ativação).

**Saída `proceed: false`** (lock held-e-fresco — dono interativo OU outro ciclo em voo):
```json
{
  "ok": true, "proceed": false,
  "cycle_id": "wake-20260711T221149-9dfbe5",
  "reason": "held",
  "detail": null,
  "holder": {"token": "...", "pid": null, "acquired_at": "...", "heartbeat_at": "...", "note": "...", "cycle_id": "..."},
  "guidance": "..."
}
```
**Ambos os desfechos saem com `exit code 0`** — deferir é um resultado limpo do portão,
não um erro. Só uma falha genuinamente inesperada (`ok: false`) sai `1`.

### Por que o portão importa (não é só "chamar acquire-lock direto")

O ganho de ter `gerente_wake.py` como uma etapa separada, ANTES de invocar
`Agent(subagent_type="gerente-geral")`, é que a decisão "vale a pena acordar o Gerente
agora?" é tomada por um script stdlib de milissegundos — nenhum turno do agente caro
(Opus) é gasto quando o dono está interativo ou outro ciclo já está rodando. Um `/loop`
de 15 em 15 minutos rodando a noite toda, na maior parte das vezes, vai encontrar o lock
livre (trabalho real acontecendo) ou vai encontrar o lock held-e-fresco por um ciclo que
ele mesmo iniciou pouco antes e que ainda não terminou — em nenhum dos dois casos vale a
pena reimplementar a decisão dentro do próprio Agent Opus.

## Composição com o lock singleton (E8.2) — sem 2º decisor

O ponto central desta story: **o wake usa o MESMO lock, a MESMA primitiva atômica, que
qualquer outra ativação (interativa ou headless direta) já usava desde E8.2.** Não existe
um caminho especial de "prioridade de wake" nem um "force" que fure a fila —
`acquire_lock` é `mkdir` atômico, quem chega primeiro (dono interativo, outro wake, ou
este wake) vence; os demais veem `held: true`/`stale: false` e defletem.

- **`gerente_wake.py wake-attempt`** é a PRIMEIRA metade do que seria o passo 0 da
  Ativação (`acquire-lock`) — só que rodada FORA do agente caro, antes de decidir se vale
  a pena sequer invocá-lo.
- **`.claude/agents/gerente-geral.md` passo 0** ganhou uma entrada alternativa (ver o
  arquivo, bullet "Entrada alternativa via wake local (Story E8.8)"): quando a persona é
  invocada com um `cycle_id`/`token` já prontos (repassados pelo `PROMPT-DE-WAKE` acima),
  ela **pula a sub-etapa `acquire-lock`** (o wake já a fez) mas continua tratando
  `pending_crash` exatamente como se tivesse rodado `detect-crash` ela mesma — nenhuma
  etapa de segurança é pulada, só a chamada duplicada de `acquire-lock` (que aliás
  FALHARIA se tentada de novo — o próprio wake já é o holder).
- Isso significa que **não há dois pontos de decisão independentes que possam divergir**:
  o `wake-attempt` e o passo 0 da persona usam literalmente a mesma função Python
  (`acquire_lock` de `gerente_state.py`, importada por ambos), não duas implementações
  paralelas que precisariam ser mantidas sincronizadas.

### "Dono interativo preempta o wake" — o que isso significa mecanicamente

A frase (já usada em `gerente-geral.md`, "a presença interativa do dono sempre tem
precedência") **não** é um force-kill de um ciclo já em voo — não existe, neste harness,
um mecanismo para uma sessão interativa nova encerrar à força um `Agent` de outra sessão
já em execução. O que de fato acontece, e é o que está provado headlessly (ver
"Resultados dos testes headless" abaixo): **quem adquire o lock primeiro, prossegue; quem
chega depois, vê o lock held e desiste.** Se o dono abre uma sessão interativa ENQUANTO um
ciclo disparado por wake já está em voo, a sessão interativa (via o mesmo passo 0 de
`check-lock`) vê o lock held-e-fresco e não inicia um ciclo próprio em paralelo — ela
simplesmente aguarda ou trabalha em outra coisa; o ciclo do wake continua e termina
normalmente, liberando o lock ao final. Simétrico, não um privilégio hard-coded — mas o
efeito prático (nunca dois decisores ao mesmo tempo) é exatamente o que a AC pede.

## Nenhum wake incorre em API metered

Toda a cadeia do wake roda dentro da cota de assinatura, 100% local:
- `/loop`/`CronCreate` são primitivas nativas do harness da sessão atual — nenhuma delas
  faz uma chamada de rede própria; `CronCreate` é explicitamente descrita como
  session-only/in-memory, nada escrito em disco.
- `gerente_wake.py` só importa stdlib (`argparse`, `importlib.util`, `json`, `sys`,
  `uuid`, `datetime`, `pathlib`, `typing`) — nenhum SDK de rede, nenhuma chamada HTTP.
  Verificado mecanicamente (não só alegado em prosa) por
  `test_gerente_wake.py::test_no_network_path`, que varre as linhas `import`/`from` reais
  do arquivo (não o texto bruto — a própria docstring MENCIONA os tokens proibidos como
  exemplo de busca, então uma checagem de texto bruto se auto-derrubaria).
- Quando `proceed: true`, o único "custo" adicional é invocar `Agent(subagent_type:
  "gerente-geral")` — a MESMA chamada nativa que uma ativação interativa/headless direta
  já fazia antes desta story; o wake não introduz nenhum provedor novo, nenhuma chave de
  API, nenhuma rota de billing.
- Quando `proceed: false`, nenhum `Agent` é invocado — zero custo além do `wake-attempt`
  em si (um `os.mkdir`/leitura de JSON local).

## Micro-teste manual de 60s (requer sessão interativa real — não executável headless)

Assim como `E1-4-validacao-round-trip.md` e `E2-4-validacao-deadlock.md` documentaram seus
procedimentos de verificação e2e como passos manuais (operações que exigem um ambiente
real que uma story headless não pode exercitar sozinha), o mesmo vale aqui: agendar um
`ScheduleWakeup`/`loop` de verdade que dispara 60s depois e re-invoca o Gerente **não pode
ser exercitado de dentro de um sub-agente headless** — ninguém pode agendar o próprio wake
e bloquear esperando por ele no mesmo turno em que o agenda. Quando o dono quiser
confirmar isto ao vivo, o procedimento é:

1. Abra uma sessão interativa do Claude Code neste repositório, branch `staging`.
2. Rode:
   ```
   /loop 1m Rode: python3 project_controll/gerente/scripts/gerente_wake.py wake-attempt --root project_controll/gerente; imprima o JSON de saída literalmente na resposta (não invoque o Agent gerente-geral neste micro-teste — só confirme que o wake dispara e o portão decide).
   ```
   (1 minuto — o menor intervalo prático para observar em tempo real; para produção use
   um intervalo maior, ver "Mecanismo A" acima.)
3. **Critério de sucesso:** dentro de ~60-90s (o próprio `/loop` já embute alguma
   variação de agendamento), uma nova resposta aparece na sessão com o JSON de
   `wake-attempt` — confirmando que o wake disparou de fato dentro da sessão viva, sem
   nenhuma ação manual do dono além de ter deixado a sessão aberta.
4. Rode `python3 project_controll/gerente/scripts/gerente_state.py check-lock --root
   project_controll/gerente` na mesma sessão para confirmar que o `wake-attempt` do
   passo 2 de fato criou/manteve o lock em disco (`held: true`), fechando o elo entre "o
   wake disparou" e "o wake tocou o mecanismo real de E8.2", não um mock.
5. Pare o loop ("pare o loop do Gerente") e, se um lock ficou held pelo teste, libere-o:
   `python3 project_controll/gerente/scripts/gerente_state.py release-lock --root
   project_controll/gerente --token <token do wake-attempt do passo 2>` — para não deixar
   um lock de teste bloqueando um ciclo real depois.
6. **Variante completa** (opcional, mais realista): repita com o `PROMPT-DE-WAKE`
   completo (não a versão "só imprima o JSON" do passo 2) para confirmar que um
   `proceed: true` de fato invoca `Agent(subagent_type: "gerente-geral")` e que a persona
   reconhece a entrada alternativa via wake (passo 0 de `gerente-geral.md`) sem tentar
   `acquire-lock` de novo.

Quando este procedimento for executado, seu resultado deve ser anexado ao Dev Agent
Record de `ideias/sistema-artifacts/E8-8-wake-local.md` como a prova e2e final — mesmo
padrão de "prova estrutural + procedimento manual documentado" já usado por E1.4/E2.4.

## Resultados dos testes headless (o que É provado sem sessão ao vivo)

`project_controll/gerente/scripts/test_gerente_wake.py` — 33 asserções via subprocesso
real (não mockado), contra o lock REAL de `gerente_state.py`, em diretórios temporários
isolados (nunca toca `project_controll/gerente/` real):

1. **Singleton respeitado:** 1º `wake-attempt` contra um root livre adquire
   (`proceed:true`); 2º `wake-attempt` IMEDIATO contra o mesmo root (lock ainda
   held-e-fresco) defere (`proceed:false`, `reason:held`) — nenhum 2º decisor.
2. **Mid-flight:** um wake "A" em voo (lock held, heartbeat fresco, nenhum release
   ainda) faz um wake "B" concorrente deferir sem token — prova direta do requisito "um
   wake que fira com um ciclo em voo não dobra o decisor".
3. **Dono interativo preempta:** um lock adquirido do jeito que a ativação interativa já
   adquire hoje (`gerente_state.py acquire-lock`, sem nada especial de wake) bloqueia um
   `wake-attempt` subsequente exatamente como o cenário 1 — confirma que não existe
   nenhum caminho que faria um wake "furar" a fila na frente do dono.
4. **Reentrância:** depois que o holder libera o lock (fim normal de ciclo), o próximo
   `wake-attempt` adquire de novo com um `cycle_id` NOVO, `pending_crash: null` — nenhum
   estado do ciclo anterior prende o próximo wake.
5. **Composição com crash-recovery (E8.2):** um `CICLO-INICIO` órfão pré-existente no
   diário faz o `wake-attempt` seguinte (bem-sucedido, sem lock concorrente) devolver
   `pending_crash` preenchido com o `cycle_id` órfão — e confirma que `gerente_wake.py`
   NUNCA reconcilia sozinho (`detect-crash` direto continua acendendo depois do
   `wake-attempt`, provando que a resolução real fica para a persona).
6. **Exit codes limpos:** `proceed:true` e `proceed:false` saem ambos com `exit 0` —
   deferir não é tratado como erro em lugar nenhum da cadeia.
7. **Nenhum caminho de rede:** varredura das linhas `import`/`from` reais do arquivo
   confirma zero módulo de rede/SDK de billing; só stdlib.

**Achado real de auto-revisão (corrigido nesta sessão, antes de qualquer teste
externo):** a primeira versão de `wake-attempt` auto-preenchia `--pid` com
`os.getpid()` do próprio script. Como `gerente_wake.py` é um processo CURTO-VIVIDO
(termina assim que imprime o JSON), na hora de um SEGUNDO `wake-attempt` rodar, o PID do
primeiro já estava morto — `pid_alive()` o via como `False` e `lock_is_stale()`
reclamava o lock IMEDIATAMENTE, quebrando a exclusão mútua na prática (reproduzido:
`proceed:true` no 2º wake, deveria ser `false`). **Corrigido** removendo o
auto-preenchimento de `--pid` (default permanece `None`), alinhando com a convenção que
`.claude/agents/gerente-geral.md` já usa — nunca passar `--pid` a `acquire-lock`, porque
"nenhum processo de SO único representa 'o Gerente' de forma confiável neste harness de
agente/tool-calls" (comentário original de `gerente_state.py::lock_is_stale`, Story
E8.2). Ver Dev Agent Record da story para o antes/depois completo.

## Auto-revisão adversarial (cenários considerados)

- **Wake disparando enquanto um ciclo segura o lock:** DEFERE (não dobra) — provado no
  teste 2 acima.
- **Wake depois de um crash:** o `pending_crash` é repassado, mas a RESOLUÇÃO (reconcile)
  continua sendo passo da persona, não do script do portão — evita que `gerente_wake.py`
  vire um segundo lugar onde a lógica de reconciliação precisa ser mantida em sincronia
  com `gerente_state.py`/`gerente-geral.md`.
- **Dono interativo vs. autônomo — ordem:** simétrico por construção (quem adquire
  primeiro vence); não existe um "force" do dono sobre um ciclo de wake já em voo — ver
  seção dedicada acima. Isto é uma característica herdada de E8.2, não uma lacuna nova
  desta story.
- **Caminho acidental de cron/cloud:** nenhum. `gerente_wake.py` não agenda nada sozinho
  (não é ele quem decide QUANDO rodar — isso é `/loop`/`CronCreate`, escolhidos pelo dono
  na sessão); o script em si só reage a UMA invocação síncrona por vez. Nenhuma referência
  a `crontab`, `at`, `systemd`, ou à skill `schedule` (cloud) em `gerente_wake.py` nem
  neste documento, fora da seção que explica por que ela é proibida.
- **O doc realmente permite iniciar/parar?** Sim — "Mecanismo A"/"Mecanismo B" acima têm
  o comando exato de início e o de parada para os dois mecanismos disponíveis.
- **`--stale-after-seconds` do wake divergindo do usado pela persona:** ambos usam o
  default `DEFAULT_STALE_AFTER_SECONDS` de `gerente_state.py` (900s) quando não
  especificado — a mesma constante importada, não um valor duplicado hardcoded em dois
  lugares.
