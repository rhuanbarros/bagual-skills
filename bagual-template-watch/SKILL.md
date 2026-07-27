---
name: bagual-template-watch
description: Checa o repositório template_fullstack_app_supabase (branch dev) por atualizações às skills/componentes que este repositório já importou dele (gerente-geral-system, bagual-skill-forge, ...), usando manifest.yaml para saber o que está no escopo e sync-log.md para lembrar até que commit já foi analisado — nunca re-varre tudo do zero. Diffs desde o último commit logado, propõe a adaptação (genericização, sem conteúdo de produto), aplica, roda os self-tests do componente, e atualiza o log com o novo commit. Use quando o usuário disser "checar atualizações do template", "sincronizar com o template", "trazer novidades do template", ou "bagual-template-watch".
---

# bagual-template-watch — sentinela de atualizações do template

> Skill de **manutenção deste repositório**: não se instala em outro projeto (não tem `payload/`).
> Roda aqui mesmo, comparando este repo com um clone local do
> `template_fullstack_app_supabase`.

## Fluxo

### 1. Localize o template
Clone local esperado: `../template_fullstack_app_supabase` (sibling deste repo). Se não existir
nesse caminho, pergunte o caminho ao dono. Confirme que a branch é `dev` (`git -C <path> branch
--show-current`) — se o dono quiser incluir commits mais novos que ainda não chegaram no clone
local, pergunte se deve rodar `git -C <path> pull` antes (ação de rede — não rode sem confirmar).

### 2. Leia `manifest.yaml`
Cada item é um **componente** já portado para este repo: caminhos-fonte no template
(`include_paths`/`exclude_paths`) e o mapeamento para o destino aqui. `exclude_paths` já encapsula
o porquê de cada exclusão (estado vivo, mecanismo fora do escopo do kit, conteúdo de produto) —
não redescubra isso analisando o histórico de novo a cada rodada.

### 3. Leia `sync-log.md`
Pra cada componente, pegue `último commit sincronizado`. Esse é o ponto de partida do diff — nunca
compare a árvore inteira do zero.

### 4. Para cada componente, calcule o que mudou
```
git -C <template_repo> diff --stat <last_synced_commit>..dev -- <include_paths...>
```
Descarte do resultado qualquer caminho batendo em `exclude_paths`. Se sobrar vazio, componente está
em dia — só atualize o commit no log (passo 7) e siga pro próximo.

### 5. Avalie cada arquivo que mudou
Leia `git -C <template_repo> diff <last_synced_commit>..dev -- <arquivo>`. Antes de portar, cheque
contra as regras de genericização (herdadas do `bagual-skill-forge/references/principios.md`,
P0/P6): sem nome de produto/projeto específico, sem mecanismo fora do escopo do kit (QA gate,
template-push, rotas de projeto-filho), sem estado vivo. Se a mudança for específica de produto ou
de um mecanismo que o `README.md` do componente já lista como removido de propósito, **não porte** —
anote no relatório final por quê.

### 6. Aplique a mudança adaptada
Localize o ponto correspondente no arquivo de destino (o destino pode já ter sido genericizado —
não sobrescreva o arquivo inteiro, edite o trecho equivalente, como uma pessoa faria revisando um
patch). Preserve o texto/estilo do template quando ele já é genérico; troque qualquer placeholder de
produto que ainda apareça.

### 7. Verifique e registre
Rode o self-test do componente se existir (ex.: `gerente-geral-system/verify.sh`). Depois, atualize
`sync-log.md`: novo commit sincronizado (HEAD atual do template), data, e um resumo de uma linha do
que foi trazido (ou "checado, sem mudanças aplicáveis").

### 8. Entregue
Relatório curto: por componente, commit antigo → novo, arquivos alterados aqui, e o que foi
descartado (com o motivo).

## Limites
- Não adiciona componentes novos ao `manifest.yaml` sozinha — se aparecer no template uma skill que
  este repo nunca importou, pergunte ao dono se ele quer passar a rastreá-la antes de criar a
  entrada.
- Não roda `git push`/PR nem mexe no clone do template — via de mão única, template → aqui.
