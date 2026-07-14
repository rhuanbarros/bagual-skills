# Bloco D1 — Autoaprendizado (padrão sidecar memory)

> Instala numa skill nova a capacidade de **melhorar a si mesma run após run**: lê a memória
> acumulada no início e destila o que aconteceu de volta para ela no fim, por acréscimo — nunca
> por sobrescrita.

## O que é (em uma frase)

Uma skill que aprende com o próprio uso: **no início de cada execução ela lê a memória acumulada
(feed-forward), e no fim um papel SEPARADO destila o que aconteceu de volta para essa memória
(reflect)** — que vive em dois arquivos versionados ("sidecar") ao lado da skill e evolui por
**acréscimo e refinamento, nunca por sobrescrita**.

## Por que serve para qualquer projeto/assunto

O padrão é 100% arquivos-em-disco + disciplina de prompt: sem banco, sem serviço externo, sem
framework. Cada execução torna a próxima mais precisa — erros operacionais viram regras; regras
comprovadamente duráveis "se graduam" para o prompt permanente. Isso vale para qualquer domínio
(não só software): o "rastro" que a execução deixa muda, mas o loop fechado
`playbook → executa → lessons-log → cura → playbook` é idêntico.

## Os princípios (não negocie estes)

Sete invariantes. Remova qualquer um e o autoaprendizado degrada ou vira autoengano.

**P1 — Papéis separados: quem AGE nunca é quem REFLETE.** O papel que executou não pode ser o que
julga como o trabalho correu nem o que grava a lição — senão ele **se convence do próprio sucesso**
(false-pass). O mínimo inegociável: o Reflector é um papel separado do executor (mesmo modelo,
contexto limpo — na prática, um subagente disparado depois).

**P2 — Memória append-only / refine-only, NUNCA overwrite.** `lessons-log.md` é append puro (nunca
editar/apagar entrada passada). `playbook.md` é refinado: adicionar regra, torná-la mais precisa,
ou **deprecar** uma obsoleta (`~~riscar~~` + o motivo). Deletar/reescrever causa **context
collapse** — o modelo perde o *porquê* da regra e re-comete o erro que a originou. Ciclo em duas
fases: (1) deprecar no lugar, deixando a regra riscada **visível**; (2) quando as riscadas
acumulam, realocá-las para `playbook.archive.md` (não carregado no feed-forward). História
preservada, sem pagar token no caminho quente.

**P3 — Feed-forward tem que CHEGAR em quem executa.** Ler o playbook no pai é necessário mas não
suficiente se o trabalho real roda em subagentes de contexto isolado. Quando há subagentes, duas
medidas obrigatórias: (1) todo prompt de dispatch inclui o **caminho** do `playbook.md`; (2) o pai
**cola verbatim** as regras relevantes àquela tarefa dentro do prompt. (Skill de contexto único:
P3 é trivial — mas registre a regra para o dia em que introduzir subagentes.)

**P4 — "Graduação": a regra durável migra pro prompt permanente.** Regra que se provou durável
(reaparece em vários runs) é escrita direto no prompt permanente (`SKILL.md`/referência do papel) e
**marcada** no playbook como `✅ Graduated to skill (<data>) — now permanent in <arquivo>`. Aí ela
não depende mais do feed-forward funcionar. O texto continua no playbook (P2); o marcador é aditivo.
Use `⚠️ Partially graduated` para graduação parcial. Cria uma escada de confiança: log cru → regra
curada → instrução permanente.

**P5 — Memória-da-skill é SEPARADA da memória-do-projeto e das preferências-do-dono.** O sidecar é
memória operacional daquela skill (como *rodá-la bem*) — distinta da captura de conhecimento do
projeto (Bloco E) e do estilo/preferências do dono (Bloco G). Não misture: "o campo X rejeita o
prefixo Y-" é memória da skill; uma decisão de produto é do projeto; "sempre rode <ASSIM> primeiro"
é preferência do dono. Se acumular preferências do operador, guarde-as num `preferences.md` no
próprio sidecar — nunca dissolvidas nas regras de causa-raiz.

**P6 — Regras operacionais e específicas, não vagas.** "A tela X precisa de `<ASSIM>` antes do
passo Y" — sim. "Tomar cuidado com performance" — não. Toda regra cita sua **fonte** (qual run,
qual caso), para ser auditável e reavaliável depois.

**P7 — Só se promove o que é durável.** Um flake de uma vez só **não** vira regra de playbook —
fica no `lessons-log.md` (memória crua e exaustiva). A curadoria exige sinal repetido ou causa-raiz
sólida. O playbook é curado; o log é cru.

## Como implementar

### Os dois arquivos do sidecar

Ficam num diretório sidecar ao lado da skill, fora dela, com caminho declarado na config
(`sidecar_path`). O **núcleo são dois** — bastam para começar:

- **`lessons-log.md` (APPEND-ONLY)** — o diário cru, escrito no fim de cada run pelo Reflector.
  Cabeçalho canônico + uma entrada por run com quatro campos fixos: `worked` / `failed (root
  cause)` (sempre causa-raiz, não sintoma) / `surprise` / `candidate playbook change` (a ponte para
  a curadoria).
- **`playbook.md` (REFINE-ONLY)** — a memória curada, lida no início (feed-forward). Cabeçalho
  canônico + regras numeradas. Três mecanismos de evolução visíveis: **Append** (regra nova no
  fim), **Refine** (linha `**Refined (<data>, run <id>):** ...` colada sob a regra), **Deprecate**
  (`~~riscada~~` + motivo).

Auxiliares que se pagam conforme o sidecar cresce (todos opcionais no começo): `INDEX.md` (mapa do
sidecar — "arquivo não listado é arquivo perdido"), `playbook.archive.md` (arquivo-morto de regras
depreciadas, não carregado no feed-forward), `preferences.md` (preferências do operador, P5). Regra
geral: o que é **carregado a cada run** fica enxuto; o que é **arquivo/auditoria** pode crescer.

### O ciclo: feed-forward no início, reflect no fim

**Início (Stage 0 / pre-check) — FEED-FORWARD:** ler `playbook.md` por inteiro e segurar as Regras
como guia vinculante. Se houver subagentes, aplicar P3 (passar caminho + colar regras relevantes em
cada dispatch). Sem regras ainda → seguir normalmente (primeiro run).

**Fim (última stage) — REFLECT:** disparado como um papel/subagente **separado** (P1), contexto
limpo, que **não** re-executa. Rotina: (1) ler o playbook atual; (2) minerar o **rastro objetivo**
da execução (métricas, log de decisões, diff, contadores de retry — *sem rastro objetivo a reflexão
vira opinião*; persista-o write-ahead); (3) **append** no lessons-log; (4) **curar** o playbook
promovendo só o durável (P7), por append/refine/deprecate (P2); (5) **não** tocar na memória do
projeto (P5); (6) marcar graduações (P4); (7) escrever um **marker em disco** (`reflector.done`).

> **Regra de ouro da durabilidade:** confie sempre no **marker em disco** (`*.done`), nunca no
> valor de retorno do subagente (que se perde numa compactação de contexto). E force a conclusão no
> prompt ("faça o trabalho COMPLETO — todos os artefatos + o marker; NÃO pare depois de planejar")
> — subagentes de reflexão já foram vistos "parando após planejar" com 0 escritas. Redispatch é
> idempotente: se o marker não existe, redisparar produz o que o primeiro nunca produziu.

### O papel Reflector (prompt-modelo)

```text
Você é o REFLECTOR — um papel SEPARADO do que executou (anti-autoconfirmação: o ator
não avalia o próprio aprendizado). Roda depois do entregável, em contexto limpo.
NUNCA re-executa o trabalho. Objetivo: tornar a SKILL melhor em rodar a si mesma na
próxima vez — não re-julgar o resultado.

1. Leia <sidecar_path>/playbook.md POR INTEIRO (para refinar em vez de duplicar, e
   ver o que já se graduou).
2. Minere o rastro desta execução: <descreva o log/métricas/artefatos da sua skill>.
   Extraia: o que funcionou, o que falhou (com CAUSA-RAIZ), o que surpreendeu.
3. APPEND uma entrada em <sidecar_path>/lessons-log.md (nunca edite o passado):
   ## <timestamp UTC> · run <id> / - worked / - failed (root cause) / - surprise /
   - candidate playbook change.
4. CURE <sidecar_path>/playbook.md: promova SÓ lições duráveis (flake de uma vez não
   é durável). Append de regra nova, OU refine uma existente, OU deprece uma obsoleta
   (~~riscar~~ + motivo, deixando-a VISÍVEL). NUNCA sobrescreva/delete. Se as riscadas
   acumularam, mova-as para <sidecar_path>/playbook.archive.md. Regras operacionais,
   específicas, com a fonte (run/caso).
5. NÃO toque na memória do projeto — o sidecar é separado.
6. Se graduar uma regra pro prompt permanente, marque no playbook:
   "✅ Graduated to skill (<data>) — now permanent in <arquivo>".
7. Como ÚLTIMA ação, escreva o marker <run_folder>/reflector.done (YAML: role,
   lessons_appended, playbook_changes, finished_at). Trabalho COMPLETO — todas as
   escritas + o marker; NÃO pare depois de planejar. Sem prosa no output — os
   arquivos do sidecar são o contrato.
```

## Templates usados

- `templates/sidecar-lessons-log.template.md` — o esqueleto do diário cru (cabeçalho canônico +
  formato de entrada com os quatro campos).
- `templates/sidecar-playbook.template.md` — o esqueleto da memória curada (cabeçalho canônico +
  seção de regras vazia + nota de graduation markers).
- `templates/config.template.json` — declare o **`sidecar_path`** (caminho resolvível do diretório
  sidecar) e os **`spine_facts`** (os invariantes P1/P2/P5… como **fatos literais**, não caminhos
  de arquivo — assim são injetados em todo papel/execução e sobrevivem à ausência de qualquer
  arquivo-fonte).

## Armadilhas

- **Deixar o executor refletir sobre si mesmo** (quebra P1 — racionaliza os próprios erros).
- **Sobrescrever/enxugar o playbook "pra ficar limpo"** (quebra P2 — context collapse; deprecar >
  deletar, sempre; a economia de token vem de graduar + arquivo-morto, não de podar).
- **Ler o playbook só no orquestrador quando o trabalho roda em subagentes** (quebra P3 — passe
  caminho + cole verbatim).
- **Regras vagas** (quebra P6 — "seja cuidadoso" não muda comportamento).
- **Promover flakes** (quebra P7 — flake fica no log).
- **Confiar no retorno do subagente em vez do marker em disco** (some numa compactação).
- **Misturar memória da skill com memória do projeto** (quebra P5 — os dois lados se poluem).
- **Regra sem fonte** (não é auditável).

## Quando NÃO usar

Este bloco serve a **quase toda** skill (topo ou tarefa) — é o coração do valor do kit. As únicas
dispensas legítimas: uma skill de execução **única e trivial** que nunca reaparece (não há
"próxima run" para melhorar), ou uma skill puramente determinística sem julgamento (nada a
aprender). No mais, se a skill toma decisões que podem correr melhor da próxima vez, instale.

## Fonte

Condensado de `_bagual/manual-skill-autoaprendizado.md` (486 linhas) do sistema de origem —
consulte o manual completo para o passo-a-passo de implementação, o prompt-modelo do Reflector
completo, a comparação com o modelo "Sanctum" do BMad, e o checklist de conformidade.
