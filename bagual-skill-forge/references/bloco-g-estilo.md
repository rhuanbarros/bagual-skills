# Bloco G — Aprendizado de estilo do dono

> Instala numa skill nova a capacidade de **aprender as preferências e o estilo do dono** ao longo
> do tempo — tom, formato de entrega, nível de detalhe, decisões recorrentes de gosto, o que ele
> corrige de novo e de novo — e **aplicá-las** nas próximas execuções, antes de entregar.

## O que é (em uma frase)

Uma skill que observa o **feedback e as correções recorrentes do dono**, destila cada padrão durável
num **fato de estilo** literal e acionável, o persiste, e o **relê no início de cada execução**
(feed-forward) para ajustar tom/formato/detalhe da saída antes de entregar — de modo que a próxima
entrega já chegue do jeito que o dono gosta, sem ele ter que pedir de novo.

## Por que serve para qualquer projeto/assunto

O alvo é a **pessoa**, não o domínio: todo dono tem gostos duráveis sobre como quer receber o
trabalho (bullets vs. prosa, trade-off antes da recomendação, sem emoji, número exato em vez de
"vários"). Isso independe de o assunto ser software, texto, análise ou operação. O mecanismo é
100% arquivos-em-disco + disciplina de prompt: registra-se o que o dono corrige ≥2x, lê-se no
começo, aplica-se no fim. Cada entrega corrigida torna a próxima mais alinhada — a fricção "tive
que pedir a mesma coisa de novo" cai a zero.

## Estilo-do-dono vs memória-da-skill (D) vs conhecimento-do-projeto (E)

Três memórias distintas — **não as misture** (Princípio P5), ou os três lados se poluem:

| Memória | Alvo | Exemplo | Onde |
|---|---|---|---|
| **Bloco D** (sidecar) | como **operar a skill** bem | "o campo `<X>` rejeita o prefixo `<Y>-`" | `sidecar_path` |
| **Bloco E** (Ledger) | conhecimento **do projeto** | "decidiu-se usar `<abordagem>` para `<caso>`" | `ledger_root` |
| **Bloco G** (este) | gosto **do dono** (a pessoa) | "prefere resumo em bullets, nunca prosa corrida" | preferências (abaixo) |

Regra prática: se o fato descreve **como a máquina se comporta**, é D. Se descreve **uma decisão do
produto/projeto**, é E. Se descreve **como o dono quer receber ou o que ele gosta**, é G.

## Como implementar

### O que é um "fato de estilo"

Uma **preferência durável e acionável do dono**, escrita de forma **literal e específica** — nunca
vaga. Ela diz o que fazer/evitar na próxima entrega, sem interpretação:

- ✅ "Sempre apresentar o trade-off ANTES da recomendação, não depois."
- ✅ "Resumos em bullets; nunca parágrafos longos de prosa."
- ✅ "Não usar emoji em nenhuma entrega."
- ✅ "Quando citar quantidade, dar o número exato — não 'vários'/'alguns'."
- ❌ "Ser mais claro" / "escrever melhor" / "capricho" — vago, não muda comportamento, não é fato.

Um fato de estilo tem: o **texto literal**, a **fonte** (quais execuções onde o dono corrigiu isso),
e a **data**. Sem fonte não é auditável nem reavaliável.

### Como coletar (padrão ≥2x, nunca de uma ocorrência)

Observe o **feedback e as correções** do dono ao longo das execuções. Uma correção **isolada** NÃO
vira fato de estilo — pode ser contexto daquela entrega específica, não um gosto durável. Só quando
o **mesmo tipo de correção reaparece ≥2 vezes** (ou o dono a enuncia explicitamente como regra
geral: "de agora em diante, sempre...") você registra o fato. Isto espelha o "só se promove o que é
durável" do Bloco D: correção única fica no rastro cru; padrão repetido vira fato curado. **Nunca
invente** uma preferência a partir de uma leitura sua do que o dono "deve" gostar — só a partir de
evidência real e repetida.

### Onde guardar e como ler (feed-forward)

Persista os fatos de estilo apoiando-se no **Bloco E** (recomendado) ou num arquivo dedicado:

- **Arquivo dedicado `preferencias-do-dono.md`** — o default simples: um `.md` com uma lista de
  fatos de estilo (texto literal + fonte + data), lido inteiro no início. Fica **separado** do
  sidecar da skill (Bloco D) e do Ledger do projeto (Bloco E) — P5.
- **Ou entradas no Ledger (Bloco E)** — um fato de estilo pode virar `tipo: nota-operacional` (gosto
  operacional do dono) ou, quando ele fixa uma preferência como decisão deliberada,
  `decisao-de-produto`. Reusa a infraestrutura grep-native do Bloco E em vez de criar uma paralela.
- **`spine_facts` em `templates/config.template.json`** — os fatos de estilo **mais fundamentais e
  invariantes** (os que valem em TODA entrega, ex. "nunca emoji") entram aqui como **fatos literais**
  (não caminhos de arquivo): assim são injetados em todo papel/execução e sobrevivem mesmo se o
  arquivo de preferências sumir. Reserve `spine_facts` para os poucos universais; o resto vive no
  arquivo/Ledger.

**Leitura (feed-forward):** no início da execução — como o playbook do Bloco D, mas de um lugar
**separado** — leia os fatos de estilo e segure-os como restrições vinculantes da entrega. Se houver
subagentes que produzem saída consumida pelo dono, passe os fatos relevantes verbatim no prompt de
dispatch (mesmo P3 do Bloco D).

### Como aplicar na entrega

**Antes de entregar qualquer saída ao dono**, faça uma passada de conformidade contra os fatos de
estilo: o tom bate? o formato (bullets/prosa/tabela) é o preferido? o nível de detalhe é o que ele
quer? a ordem (ex. trade-off antes da recomendação) está certa? algo que ele "não gosta" vazou?
Ajuste **antes** de emitir, não depois de ele reclamar. A entrega ideal é a que não precisa de
correção porque já nasceu no estilo dele.

## Armadilhas

- **Projetar autorização/decisão a partir de "estilo".** Aprender estilo é sobre **forma e gosto de
  entrega** — NUNCA sobre assumir decisões que são do dono. Jamais infira, de um padrão de estilo,
  permissão para uma **ação irreversível** (deploy de produção, escrita destrutiva, gasto). "O dono
  costuma aprovar X" **não** é autorização para fazer X sozinho — ações irreversíveis exigem o go
  **expresso** dele, todo vez. Estilo ajusta como você entrega; não expande o que você pode fazer.
- **Fato de uma ocorrência** — quebra o ≥2x; vira ruído/superstição.
- **Fato vago** ("ser mais claro") — não muda comportamento; não é acionável.
- **Inventar preferências** que você acha que ele tem, sem evidência real.
- **Misturar com D ou E** — gosto do dono não é memória de operação da skill nem decisão do projeto.
- **Sobrescrever/apagar** um fato antigo em vez de deprecá-lo (`~~riscado~~` + motivo) quando o gosto
  do dono muda — perde-se o *porquê* e o histórico (mesma disciplina do Bloco D).
- **Aplicar estilo a saída que não é para o dono** — se o consumidor é outro agente/sistema, o formato
  dele manda, não o gosto do dono.

## Quando NÃO usar

Dispense se a skill **não produz saída que o dono consome** com gosto relevante — saída puramente
para máquina (JSON de contrato, arquivo lido por outra skill), ou uma tarefa determinística sem
julgamento de forma. Também dispensável se a skill roda **uma vez só** e nunca reaparece (não há
"próxima entrega" para alinhar). No mais, se o dono lê o resultado e o gosto dele importa, instale —
e apoie a persistência no Bloco E.

## Fonte

Destilado do mecanismo de "aprendizado de estilo" do sistema de origem (um gate de decisão
*history-aware* que consultava o histórico de decisões ratificadas/corrigidas do dono antes de
decidir). A versão original era acoplada a um Ledger tipado com gramática MADR e um oráculo de
confiança por categoria; aqui ficou o **núcleo genérico**: observar correções recorrentes → destilar
fatos de estilo literais → feed-forward → aplicar na entrega, com o resto cortado na curadoria (P0).
