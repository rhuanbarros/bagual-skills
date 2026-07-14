# Bloco E — Captura de conhecimento (Ledger tipado)

> A memória do **projeto** entre sessões: ao fim de toda tarefa, a skill registra o que aprendeu de
> durável num Ledger tipado grep-native, para o próximo agente não trabalhar às cegas.

## O que é (em uma frase)

Um cofre de arquivos `.md` tipados (um fato por arquivo, pesquisável por grep) mais um gatilho —
"RULE ZERO" — que obriga a skill a depositar nele qualquer conhecimento durável antes de dar a
tarefa por concluída.

## Por que serve para qualquer projeto/assunto

Todo trabalho recorrente produz conhecimento que vale mais que o artefato entregue: por que uma
escolha foi feita, uma regra que se firmou, uma armadilha que voltou a morder. Se isso mora só na
cabeça (ou no contexto) de uma execução, evapora na próxima sessão — e o agente seguinte repete o
erro já pago. O Ledger é o registro persistente disso. Não é específico de código: uma skill de
pesquisa, de redação, de gestão ou de suporte gera decisões e anti-patterns exatamente do mesmo
jeito. O único requisito é um diretório onde escrever e um harness que saiba grepar.

## Memória-do-projeto vs memória-da-skill vs estilo-do-dono

Três memórias distintas, não confunda. O **Bloco E** (aqui) grava conhecimento **do projeto/domínio**
— fatos que valem para qualquer agente que toque o projeto, independentemente de qual skill rodou
("a API `<X>` exige idempotência", "decidimos `<Y>` em vez de `<Z>`"). O **Bloco D** (sidecar) grava
conhecimento sobre **operar esta skill específica** — lições de como a própria máquina funciona
melhor, lidas no início de cada run dela e inúteis para outra skill. O **Bloco G** grava as
**preferências da pessoa** dona (tom, formato, gostos recorrentes). Regra prática: se o fato ajuda
*qualquer* agente do projeto → Bloco E; se só ajuda *esta* skill a rodar → Bloco D; se é sobre *quem*
consome a saída → Bloco G. Bloco G costuma persistir seus fatos usando o próprio Ledger do Bloco E.

## Como implementar

### RULE ZERO — o gatilho de registro ao fim de cada tarefa

A obrigação central: **ao concluir toda tarefa, antes de reportar "pronto", a skill classifica o que
aprendeu de durável e emite uma entrada por item.** Encode isso no passo final da persona/contrato
(um bloco `on_complete` textual, não um script): "classifique itens dignos de Ledger conforme os 5
tipos abaixo; para cada um, escreva um arquivo em `<CAMINHO-WIKI>/ledger/<tipo>/`; se nada for
durável, não emita nada."

Dois freios que impedem o gatilho de virar ruído ou de perder conhecimento:

- **Seja estrito na emissão.** A maioria das tarefas termina **sem** nada digno de Ledger — só
  execução. Emitir demais infla o cofre e encarece qualquer busca futura. Na dúvida, **não emita**:
  o custo de perder uma lição pontual é menor que o de poluir. Só emita quando o item se encaixa
  claramente num dos 5 tipos e vale para *futuras* tarefas, não só para esta.
- **Registre ANTES do risco de perda.** Se há risco de compactação de contexto, troca de agente ou
  fim de sessão, grave a entrada **antes** da transição — contexto perdido é conhecimento perdido
  para sempre. Não deixe a captura para "depois".

### O Ledger tipado grep-native (5 tipos mínimos)

O conhecimento vive como arquivos `.md`, **um fato por arquivo**, nome em kebab-case, cada um sob a
pasta do seu tipo. Cinco tipos — nada além disto:

| tipo | pasta | quando |
|---|---|---|
| `decisao` | `<CAMINHO-WIKI>/ledger/decisao/` | uma escolha entre alternativas foi feita e vale para o futuro |
| `regra` | `<CAMINHO-WIKI>/ledger/regra/` | uma convenção acionável e verificável se firmou ("sempre/nunca X") |
| `padrao` | `<CAMINHO-WIKI>/ledger/padrao/` | um jeito de fazer algo se repetiu ≥2x e vale consolidar |
| `anti-pattern` | `<CAMINHO-WIKI>/ledger/anti-pattern/` | um erro/gotcha recorrente, com o jeito certo de evitá-lo |
| `nota-operacional` | `<CAMINHO-WIKI>/ledger/nota-operacional/` | conhecimento operacional útil que não é nenhum dos 4 acima |

`nota-operacional` é a válvula de escape: como uma parte interage com outra, um comportamento de
sistema, uma pegadinha de ambiente — coisas reais de saber que não são uma decisão/regra/padrão/
anti-pattern tipável. Não force um fato num tipo que não serve; a nota existe justamente para isso.

**A busca é grep-native — não há máquina de tags nem script de retrieval.** Para achar conhecimento,
o harness usa `grep`/`glob`/`read` sobre a árvore `ledger/` mais um `index.md` recursivo, com
julgamento e iteração, no momento em que precisa. Nada de um subsistema que indexa por etiquetas,
nada de um `retrieve.py` de um-tiro: as `tags` no front-matter são só dicas humanas de busca, jamais
um mecanismo. Cada entrada segue o formato mínimo do template (front-matter + Contexto + o
fato + Consequências). Ligue fatos relacionados com `[[nome-do-arquivo]]` no corpo. Ciclo de vida
enxuto: `status: ativa` normalmente; quando um fato é superado, marque `status: superada` e aponte
`superada_por:` para quem o substituiu — o arquivo velho **fica** (consultável, é o cemitério de
abordagens já tentadas), nunca é apagado.

> **Deliberadamente simplificado.** Um sistema maduro pode usar uma gramática de decisão completa
> (MADR), muitos tipos, contadores de utilidade, selos de maturidade e scripts de validação. O kit
> genérico **enxuga tudo isso** para os 5 tipos e o par de estados acima. Não reproduza a maquinaria
> pesada nem scripts de validação — o padrão mínimo viável basta; o projeto destino endurece depois
> se precisar.

### O esqueleto de diretórios

Se o projeto destino ainda não tem um Ledger, gere o esqueleto mínimo na primeira vez:

```
<CAMINHO-WIKI>/ledger/
├── index.md                 # índice-raiz curto: o que é o Ledger + lista das 5 pastas
├── decisao/
├── regra/
├── padrao/
├── anti-pattern/
└── nota-operacional/
```

O `index.md` é uma página curta que explica o cofre e lista as pastas — serve de ponto de entrada
para a busca grep-native e para novos agentes. Uma pasta pode nascer vazia; a primeira entrada de um
tipo a preenche.

## Templates usados

- **`templates/ledger-entry.template.md`** — o esqueleto de uma entrada: front-matter
  (`tipo`/`titulo`/`data`/`status`/`superada_por`/`tags`) + corpo (Contexto → o fato → Consequências).
  Copie-o por entrada emitida, preenchendo os placeholders.
- **`templates/config.template.json` → campo `ledger_root`** — declara a raiz do Ledger
  (`<CAMINHO-WIKI>/ledger`) num só lugar; a skill lê daqui em vez de embutir o caminho no prompt.

## Armadilhas

- **Emitir demais** — transformar toda execução banal em entrada. Isso é o defeito nº 1; seja
  estrito (ver freio acima).
- **Mais de um fato por arquivo** — quebra a busca grep-native. Um fato, um arquivo.
- **Deletar o superado** — apagar em vez de marcar `status: superada` perde o "já tentamos X e não
  deu", que é metade do valor do cofre.
- **Reintroduzir maquinaria** — recriar tags-como-mecanismo, contadores, MADR completo ou um script
  de retrieval. O kit cortou isso de propósito; grep-native basta.
- **Deixar a captura para depois** — pular RULE ZERO sob pressa e perder o conhecimento na próxima
  compactação.

## Quando NÃO usar

Skills de uso único ou puramente interativas, que não acumulam nada entre execuções e cujo valor se
esgota na resposta do momento (ex.: um conversor de formato sem estado, um assistente de uma pergunta
só). Sem tarefas recorrentes que se beneficiem da memória do outro, o Ledger é só overhead. Para
**qualquer** skill que rode repetidamente sobre o mesmo projeto/domínio, instale.

## Fonte

Destilado de um subsistema real de Ledger tipado (gramática MADR + `on_complete` + RULE ZERO) e
enxugado para o mínimo viável genérico: 5 tipos, dois estados, busca grep-native, sem scripts de
validação nem máquina de tags.
