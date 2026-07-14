# Bloco A — Arquitetura de agentes

> Instala o esqueleto de um agente autônomo: 3 camadas, "o topo nunca executa", persona-como-arquivo,
> e um contrato de despacho por marcador em disco que sobrevive a crash e a compactação de contexto.

## O que é (em uma frase)

Uma camada de **topo** que só decide e despacha trabalho para uma camada de **execução**, entregando
cada unidade por um **marcador em arquivo** (não por valor de retorno da tool) — de modo que quem
está no comando sempre consiga reconstruir, olhando só o disco, qual trabalho foi despachado, se
terminou e com qual resultado.

## Por que serve para qualquer projeto/assunto

O padrão não tem nada de específico de software: é como você organiza **qualquer** trabalho
delegado que pode demorar e cujo dono não pode se dar ao luxo de esquecer o que delegou. Vale para
uma skill que gerencia uma pesquisa, uma rotina editorial, um pipeline de dados ou uma operação de
suporte. A única premissa é que exista uma **unidade de trabalho** que uma camada de topo escolhe e
uma camada de baixo executa de ponta a ponta. Preencha os placeholders `<ASSIM>` com o domínio real.

## Como implementar

### As 3 camadas

Separe responsabilidades em três níveis, cada um com um único trabalho:

1. **Topo** — gerencia o *escopo inteiro* (`<ESCOPO>`, ex.: o projeto/fluxo/domínio). Lê o estado,
   prioriza, **despacha**, revisa o que volta, registra decisões, e **para** com segurança. Roda no
   modelo mais forte (tipicamente Opus). **Nunca** executa o trabalho pesado.
2. **Execução (orquestrador)** — recebe **uma** unidade já decidida e a leva do início ao fim: pode
   ela mesma spawnar sub-agentes menores. Roda no modelo de execução (tipicamente Sonnet).
3. **Sub-agente** — uma **tarefa isolada**, com contexto curado pela camada acima. Não decide
   escopo; faz o que lhe foi entregue e reporta.

A unidade que o topo entrega à execução é sempre **uma** por despacho (o schema aceita lista para
não fechar a porta a paralelismo futuro, mas a disciplina da persona hoje é: um por vez).

### Topo nunca executa (P4)

O topo **decide, despacha e cura contexto** — a mudança que altera arquivos ou o mundo roda **sempre**
num sub-agente despachado, nunca na própria camada de topo. Isto é uma **regra da persona** (texto no
arquivo `.claude/agents/`), não um guard mecânico: este kit não gera hooks de bloqueio (cortados na
curadoria como excessivos). As únicas escritas diretas legítimas do topo são seus **próprios
artefatos operacionais** (estado, diário, marcadores de despacho) e o **registro de conhecimento**
(Bloco E) — nunca o produto do trabalho em si.

### Persona-como-arquivo (P2)

A definição do agente de topo — quem é, seus limites invioláveis, seu loop — vive em
**`.claude/agents/<NOME-SKILL>.md`**, não embutida no `SKILL.md`. A skill é só um invocador fino que
diz "adote a persona de `.claude/agents/<NOME-SKILL>.md` e rode o que o usuário pediu". Isso mantém a
definição num lugar só (editável, versionável) e permite despachar o próprio agente headless por
`subagent_type`. Mantenha a persona **curta**: o esqueleto de decisão, não os detalhes de cada
técnica (esses ficam em `references/`, lidos sob demanda — P1).

### Contrato de despacho por marcador em disco

O topo entrega a unidade e recolhe o resultado por **arquivos em disco**, nunca confiando só no
valor de retorno da tool que spawnou o sub-agente. **Por que o marcador, não o valor de retorno:**
um despacho real pode demorar e atravessar uma **compactação de contexto** da sessão do topo no meio
do caminho — se o resultado só existisse como valor de retorno guardado na memória da conversa, ele
sumiria junto com o contexto compactado (ou com a sessão inteira, se ela cair). Com o contrato em
disco, o despacho é **reconstruível puramente do disco**: mesmo que a sessão do topo seja perdida e
reaberta do zero, uma nova ativação sabe, olhando só o diretório de despachos + o estado, qual
trabalho estava em voo, se terminou e com qual resultado.

**Layout do diretório de despacho** — um subdiretório por despacho:

```
<CAMINHO-ESTADO>/dispatches/<dispatch-id>/
  request.yaml    # o pedido: a unidade, a trilha, o skill mapeado, o modelo do executor
  result.yaml     # escrito pelo sub-agente ao terminar: outcome, veredito, pendências, evidência
  DONE.marker     # escrito por ÚLTIMO, só depois de result.yaml estar durável em disco
```

`dispatch-id` por convenção: `dispatch-<AAAAMMDD-HHMMSS>-<hex8>`, e é **write-once** (nunca reabra
um id cujo `request.yaml` já existe; nunca reescreva um `result.yaml`/`DONE.marker` já presentes).

**A garantia de ordem é o núcleo do contrato.** Ao fechar, o sub-agente executa **sempre** nesta
ordem, nunca invertida:

1. escreve `result.yaml` de forma **atômica e durável** (bloqueia até o arquivo estar em disco);
2. **só então** escreve `DONE.marker`.

Consequência: **um leitor nunca observa `DONE.marker` sem um `result.yaml` completo atrás dele.** Se
o processo morre entre os dois passos, o `DONE.marker` simplesmente não chega a existir — o despacho
fica corretamente detectável como **órfão**, nunca como falso-sucesso com resultado incompleto.

**Detecção DUAL de conclusão — não faça poll no marcador.** Confiar só no `DONE.marker` (um loop que
re-checa o disco até o arquivo aparecer) troca um deadlock por um **hang silencioso**: se o sub-agente
morre antes de fechar, nenhum poll termina. Combine dois sinais, nesta ordem:

1. **Primário/bloqueante** — o **retorno da própria tool** que spawnou o sub-agente, em *foreground*.
   Esse retorno (sucesso, falha, timeout, morte) sempre resolve, por construção do harness. É ele que
   detecta um executor morto que nunca chegou a fechar o despacho.
2. **Secundário/payload** — só *depois* que (1) retornou, leia o `result.yaml`. Se `DONE.marker`
   existe, o `result.yaml` é a verdade confiável. Se a tool retornou mas `DONE.marker` **não** existe,
   trate **como falha** (reconcilie o órfão), nunca como sucesso presumido.

**Regra do executor: resolva em UM turno foreground.** O sub-agente executor deve alcançar o
fechamento do despacho como sua **última ação foreground, no mesmo turno** — nunca terminar deixando
uma sub-árvore em background/idle em voo. Se ele spawna um sub-fluxo que confirma por marcador
próprio, esse sub-fluxo tem que **resolver a um veredito terminal in-turn** antes do executor
retornar. Um turno que volta `idle`/sem-veredito é tratado como falha, idêntico ao caso "marcador
ausente" acima.

## Templates usados

- **`templates/persona.template.md`** → o arquivo `.claude/agents/<NOME-SKILL>.md`. O Bloco A
  preenche: `<NOME-PERSONA>`, `<PAPEL>`, `<ESCOPO>`, o `model` (Opus para o topo), a seção "Quem
  você é (e quem você não é)" com o "nunca executa <o-trabalho-de-domínio> — despacha (P4)", e os
  passos de despacho/revisão do ciclo operacional (`<CAMINHO-ESTADO>` para o diretório de estado que
  hospeda `dispatches/`).
- **`templates/skill.template.md`** → o `SKILL.md` invocador fino. O Bloco A preenche a linha
  "Adote a persona de `.claude/agents/<NOME-SKILL>.md`" (P2) e o passo "Adote a persona" de "Ao ser
  invocada". Deixe o SKILL.md enxuto — o contrato de despacho detalhado mora **neste** doc de
  referência, não no SKILL.md.

## Armadilhas

- **Fazer poll no `DONE.marker` como sinal único** — troca deadlock por hang. O retorno da tool é
  sempre o sinal primário; o marcador é só o payload, checado depois.
- **Inverter a ordem de escrita** (`DONE.marker` antes de `result.yaml` durável) — cria a janela de
  falso-sucesso com resultado incompleto. A ordem é inviolável.
- **Deixar o topo "só desta vez" editar o produto** — dissolve a camada. Se precisa executar,
  despacha; sem exceção.
- **Persona gorda no SKILL.md** — viola P1/P2. A definição vai para `.claude/agents/`, curta.
- **Reusar um `dispatch-id`** — quebra a semântica write-once e a reconstrução do disco.
- **Executor que volta `idle` com sub-árvore em voo** — vira órfão invisível. Resolva in-turn.

## Quando NÃO usar

- A skill é de **tarefa pura** (executa uma unidade do início ao fim e não coordena ninguém) — aí
  não há topo, não há despacho; dispense o Bloco A inteiro e use só os blocos de tarefa (D1/E/G).
- O trabalho é **sempre curto e síncrono**, sem risco de compactação/queda entre despacho e
  resultado — o marcador em disco vira cerimônia sem retorno. (Na dúvida, mantenha: o custo é baixo
  e o seguro contra perda de contexto é o ponto inteiro do bloco.)

## Fonte

Destilado de um sistema real de orquestração de agentes autônomos: a persona de topo em
`.claude/agents/` (seção "Quem você é / nunca executa código"), o contrato de despacho por marcador
em disco (`request.yaml` + `result.yaml` + `DONE.marker`, garantia de ordem, detecção dual) e a
regra "executor resolve em um turno foreground". Nomes, telas e entidades do sistema de origem foram
cortados na curadoria (P0) — aqui fica só o padrão.
