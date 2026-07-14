# Bloco B — Estado persistente & retomar

> Como uma skill de topo "sabe onde parou" entre ativações separadas — e como impedir que duas
> instâncias decidam ao mesmo tempo ou que um crash deixe trabalho pela metade sem ninguém notar.

## O que é (em uma frase)

Quatro peças de estado em disco — um snapshot legível (`estado-atual.yaml`), um diário append-only,
um lock singleton e uma rotina de recuperação de crash — que juntas deixam o agente parar, morrer ou
ser reativado numa nova sessão sem perder o fio do que estava fazendo.

## Por que serve para qualquer projeto/assunto

Um agente de topo (Bloco A) roda em **sessões descartáveis**: cada ativação é um processo novo, sem
memória da anterior. Sem estado em disco, toda ativação começa do zero e não há como saber se um
trabalho já foi despachado, se outra sessão está mexendo no mesmo estado, ou se a última sessão
caiu no meio de algo. Isso vale para qualquer domínio — não só código: pesquisa, curadoria de
conteúdo, gestão de uma fila, moderação. O padrão é agnóstico de assunto; só os campos de `domain:`
mudam.

## Como implementar

### estado-atual.yaml (o "onde parei")

Um **snapshot** do estado operacional atual — não um histórico. É **sobrescrito** a cada mudança
relevante (nunca acumula), e é lido **pela fase que precisa dele, quando precisa**, nunca inteiro na
ativação (princípio P1 — ativação enxuta). Campos essenciais: `last_cycle` (id/quando/desfecho do
último ciclo concluído), `in_progress` (o que estava sendo feito + o próximo passo concreto ao
retomar), `dispatches` (despachos abertos, cada um apontando para seu diretório de marcador — Bloco
A), e um bloco `domain:` livre para o estado específico de `<NOME-SKILL>`. Este arquivo é
**corroborativo**, nunca a fonte de verdade cega da recuperação de crash — o diário é primário
(ver abaixo). Use um serializador simples (dict-de-escalares em 1 nível + listas-de-dict); não
precisa ser YAML de propósito geral. Escreva sempre de forma **atômica** (temp + `fsync` +
`os.replace`) para nunca deixar um arquivo meio-escrito se o processo morrer no meio da gravação.

### Diário append-only

Um log **plano, cronológico, só-anexa** — a mesma filosofia de uma memlog humana: cada entrada é uma
linha, gravada no fim de cada ação, sem seções nem agrupamento. Mantenha **duas superfícies da mesma
trilha**: `diario.md` (legível por humano/persona) e `diario.jsonl` (espelho estruturado que a
recuperação de crash varre mecanicamente — evita fazer parsing de markdown livre para uma decisão
crítica). Cada ciclo é delimitado por um par de marcadores:

```
## CICLO-INICIO <ISO-UTC> <cycle-id>
- <o que decidi / despachei / observei>
## CICLO-FIM <ISO-UTC> <cycle-id>
- desfecho: <resumo em uma linha>
```

Um `CICLO-INICIO` sem o `CICLO-FIM` correspondente é **o sinal de crash**. Grave cada append como um
**rewrite atômico do arquivo inteiro** (não `open(..., "a")` incremental, que pode deixar uma linha
truncada se o processo morrer no meio do `write()`).

### Lock singleton (sem PID-só, reclaim sem TOCTOU, posse por token)

Impede **dois decisores concorrentes** (duas sessões manuais abertas ao mesmo tempo). Use um
**diretório** de lock (`os.mkdir()` é atômico no filesystem — falha com `FileExistsError` se já
existir, sem janela TOCTOU entre "checar" e "criar"). Dentro dele, um `info.json` com
`{token, pid, acquired_at, heartbeat_at, cycle_id, note}`.

- **Não baseie a posse em PID sozinho.** Neste tipo de harness não existe um processo de SO de vida
  longa que represente "o agente" — cada chamada de tool é um processo curto que morre ao retornar.
  Então: `--pid` é **opcional/best-effort** (um PID comprovadamente morto é só um atalho de detecção
  mais rápido); o **sinal primário é o SILÊNCIO de heartbeat**:
  `stale = (pid não vivo) OU (agora − heartbeat_at > stale_after_seconds)`. Quem segura o lock por um
  ciclo longo **deve** chamar `refresh-lock` periodicamente (intervalo < `stale_after_seconds`, ex.:
  a cada transição de fase). Um default de ~900s (15 min) é razoável.
- **Reclaim sem TOCTOU.** Ao encontrar um lock stale, **não** apague-e-recrie direto (dois processos
  poderiam ambos decidir "stale" e ambos apagar). Em vez disso, tente
  `os.rename(lock_dir, nome_temporário_único)` — só um processo vence um rename de um dado nome de
  origem; os perdedores recebem `FileNotFoundError` e voltam a disputar via `mkdir` contra um path
  livre. Quem venceu limpa o diretório roubado e **também** volta a disputar via `mkdir` normal — não
  força a própria vitória, só remove o lock morto da disputa.
- **Posse por token, não por PID.** `acquire-lock` gera um `token` (uuid4) e o devolve;
  `refresh-lock`/`release-lock` exigem `--token` e recusam (`not-owner`) se não bater. Isso desacopla
  **prova de posse** (token) de **sinal de liveness** (heartbeat) — o holder legítimo sempre prova
  posse mesmo que seu PID não seja rastreável.
- **`cycle_id` no lock evita um falso-positivo de crash.** Um scanner ingênuo do diário confundiria um
  ciclo longo e saudável rodando em **outra** sessão (que por definição tem um início aberto até
  terminar) com um crash. Guarde o `cycle_id` no lock e, na detecção, exclua qualquer início órfão
  cujo `cycle_id` bata com um lock **held e não-stale** — é um ciclo em andamento, não um crash.

### Recuperação de crash (reconciliar órfãos)

O diário é a **fonte de verdade primária**; `estado-atual.yaml` é só corroborativo (nunca confiado
cegamente). **Detecção:** varra o `diario.jsonl` inteiro, empilhando `CICLO-INICIO` por `cycle_id` e
desempilhando em `CICLO-FIM`; qualquer `cycle_id` que sobra é um ciclo que começou e nunca terminou →
crash. **Reconciliação** (o que fazer com os despachos órfãos, na ordem — tudo **leitura/diagnóstico,
nunca escreve estado de terceiros por conta própria**):

1. Leia `estado-atual.yaml`; só use o array `dispatches` se o `cycle.id` bater com o `cycle_id` órfão
   (senão registre a discrepância e siga sem despachos rastreáveis — não invente dados).
2. Para cada despacho: se o `status` não é terminal (`done|failed|reconciliado`), é suspeito.
3. Para cada despacho suspeito, varra `dispatches/` procurando um `request.yaml` **sem** o
   `DONE.marker` correspondente — a ausência do marcador é o sinal direto de órfão (cruza o contrato
   de despacho do Bloco A com esta rotina).
4. Se o despacho registrou um artefato externo (worktree, arquivo de saída), verifique se ainda
   existe em disco — removido = órfão limpo; presente = precisa de verificação manual.
5. Reporte os `orphans` + um `recommended_next_step` — **nunca conclua/mova o trabalho sozinho**; a
   ação fica a cargo da persona (ou da via canônica de escrita do projeto).
6. Anexe um resumo ao diário e um `CICLO-FIM ... (reconciled)` sintético para o `cycle_id` órfão —
   fechando o ciclo para que a detecção pare de acender para ele. Isso acontece **antes** de qualquer
   decisão nova: a persona detecta → se crashed, reconcilia → só então prossegue.

## O que foi cortado (não instale)

**Wake local / loop / cron / scheduling** foi **removido** na curadoria (instável e acoplado ao
sistema de origem) — **não instale nem recomende** nenhum mecanismo que acorde a skill sozinha num
intervalo. Não descreva "como agendar um tick". O ponto crítico: **sem o wake, o lock e a
recuperação de crash continuam plenamente válidos** — o lock protege contra duas sessões **manuais**
concorrentes, e o crash-recovery protege contra uma queda no meio do trabalho. Eles apenas ficam
**desacoplados** de qualquer ciclo agendado: valem para ativações disparadas por uma pessoa, não por
um scheduler. Estado persistente ≠ execução agendada.

## Templates usados

- **`templates/estado-atual.template.yaml`** — preencha `<NOME-SKILL>` e o bloco `domain:` com o
  estado específico do projeto destino. Mantenha `schema_version`, `last_cycle`, `in_progress`,
  `dispatches`.
- **`templates/diario.template.md`** — o scaffold do diário humano; preencha `<NOME-SKILL>`. Gere um
  `diario.jsonl` vazio ao lado (mesma trilha, formato máquina).
- **Lock e crash-recovery não têm template pronto** — não presuma um script existente. Descreva ao
  dono o mecanismo a implementar/adaptar: um **lock por diretório** com `info.json`
  (`{token, pid, acquired_at, heartbeat_at, cycle_id}`), **stale por idade de heartbeat, não por PID
  vivo**, **reclaim via `os.rename` que relê-e-compara antes de agir** (evita TOCTOU), e um
  **reconcile** que varre `dispatches/` cruzando `request.yaml` sem `DONE.marker`. Toda escrita de
  estado é atômica (temp + `fsync` + `os.replace`).

## Armadilhas

- **Ler tudo na ativação** viola P1 — leia `estado-atual.yaml` só na fase que precisa; não despeje
  diário inteiro no contexto sem necessidade.
- **Append incremental no diário** pode truncar uma linha num crash — sempre rewrite atômico.
- **Confiar no `estado-atual.yaml` como fonte de verdade** do crash — ele é sobrescrito e pode estar
  desatualizado; a fonte é o diário.
- **Lock por PID** falha neste harness (processos curtos) — use heartbeat + token.
- **Reclaim por delete-e-recria** abre janela TOCTOU — use o rename atômico.
- **Reconcile que muta estado de terceiros** (fecha ticket, mergeia worktree) — reconcile só
  diagnostica e recomenda; a ação é da persona.

## Quando NÃO usar

- Skill de **tarefa pura** que roda do início ao fim numa só invocação, sem sessões separadas nem
  possibilidade de duas instâncias — não precisa de lock, crash-recovery nem snapshot persistente
  (talvez só um diário, se auditoria importar).
- Skill que **nunca despacha** trabalho assíncrono e cujo estado cabe inteiro no contexto de uma
  ativação.
- Se o projeto destino tem uma única sessão sempre garantida e nenhum risco de concorrência, o lock
  é peso morto — mantenha só o diário + snapshot para retomar.

## Fonte

Destilado de um sistema real de orquestração de agentes (a camada de estado operacional de um agente
de topo autônomo): snapshot de ciclo sobrescrito, diário `.md`+`.jsonl` com marcadores
CICLO-INICIO/CICLO-FIM, lock singleton por diretório com heartbeat/token/reclaim-por-rename, e
recuperação de crash por reconciliação de despachos órfãos. Wake/scheduling do original foi cortado
(ver `catalogo.md` Bloco B e `principios.md` P0).
