# Bloco D2 — Autocorreção (self-heal)

> A skill não só **detecta** defeitos na própria máquina — ela **conserta**, sozinha, num
> sub-agente de contexto limpo, com freio e escalonamento obrigatório no núcleo.

## O que é (em uma frase)

Quando um defeito está na **máquina da própria skill** (seus scripts, sua config, sua persona) — e
não no trabalho de domínio que ela produz — a skill despacha um sub-agente de contexto **limpo** que
conserta o defeito, prova o conserto, e ou landa (fora do núcleo, com teste verde) ou escala pro
dono; e aprende com o conserto via o sidecar (Bloco D1).

## Por que serve para qualquer projeto/assunto

Toda skill autônoma não-trivial acumula uma **máquina própria**: scripts auxiliares, arquivos de
config, o texto da própria persona. Essa máquina quebra — um caminho relativo que deriva, um limiar
mal calibrado, uma instrução ambígua. Sem self-heal, cada defeito da ferramenta vira uma parada que
exige o dono no teclado. Isto é ortogonal ao assunto da skill (jurídico, pesquisa, ops, código) —
qualquer skill que tenha uma máquina que possa quebrar e valha consertar se beneficia. O princípio
que sustenta tudo — **quem conserta/reflete nunca é quem executou** (contra o *false-pass*, o ator
que se convence do próprio sucesso) — é universal.

## Como implementar

### Quando disparar (e quando NÃO)

Trate self-heal como uma **tarefa nomeada**, não como algo difuso no meio do trabalho. Dispare-a:

- Numa **fronteira** — o fim de uma sessão/invocação de trabalho, depois de concluir o trabalho de
  domínio, antes de parar. (Esta versão do kit é **desacoplada de loop/wake** — cortados na
  curadoria; "fronteira" aqui é o fim de uma invocação, **não** um "cycle boundary" de um loop
  agendado.)
- Ou quando um **despacho voltar falho por defeito da PRÓPRIA máquina** da skill (não do trabalho de
  domínio) e destravar exigir consertar a ferramenta.

**NUNCA no meio de um processo**, a não ser que consertar seja essencial pra destravar o que está
rodando. Um self-heal oportunista no meio de uma tarefa de domínio corrompe o foco e o contexto.

### O freio: capture-only vs auto-fix

Leia `selfheal_mode` da config (`templates/config.template.json`). Ele governa **tudo**:

- **`capture-only`** → NÃO conserte. Registre o defeito (um ticket / uma nota `<COMO-VOCÊ-REGISTRA>`)
  e **espere a ratificação do dono**. Relate e siga. É o **default de fábrica** — comece aqui.
- **`auto-fix`** → prossiga com o despacho de conserto abaixo.

Começar em `capture-only` é deliberado: você acumula um histórico de que consertos a skill *teria*
feito antes de deixá-la agir sozinha na própria máquina.

### Escalonamento obrigatório no núcleo

Um conserto que toca qualquer `core_path` (a persona, o contrato de despacho do Bloco A, os
scripts-núcleo) **SEMPRE escala pro dono — mesmo com testes verdes**. Um fix ruim no núcleo quebra o
próprio agente que faria o próximo conserto; teste verde não cobre esse risco sistêmico. Declare
esses caminhos no campo `core_paths` da config; o dono ratifica antes de qualquer coisa no núcleo
virar permanente.

### O despacho de conserto (contexto limpo)

Sob `auto-fix`, e para um defeito **fora** do núcleo:

1. Despache um sub-agente de **contexto limpo** (via o contrato de despacho do Bloco A — marcador em
   disco, bloqueia até o veredito). Escopo **restrito** aos arquivos da própria máquina da skill
   (`<CAMINHOS-DA-MÁQUINA-DA-SKILL>`). **Nunca** deixe o sub-agente tocar máquina de terceiros
   (frameworks de skill vendorizados — P6).
2. O sub-agente conserta o defeito e reporta os **arquivos tocados** + a **evidência** (o teste que
   rodou, o diff, o comportamento antes/depois).
3. **Decida com o DIFF + a evidência — nunca confie na alegação** do sub-agente. Um ator que diz
   "consertei" sem diff verificável é exatamente o *false-pass* que o contexto limpo existe para
   evitar.

### O que "verde" significa (script vs instrução)

O sentido de "verde" **depende do tipo de conserto** — não invente um teste que não existe:

- **Conserto em SCRIPT** (arquivo executável, com teste) → o sub-agente **roda o teste** do
  subsistema tocado. Verde = todos passam. Se **verde E nenhum `core_path` tocado** → **landa** (já
  está no disco); marque o defeito resolvido; emita Ledger (Bloco E) se for decisão durável.
- **Conserto em INSTRUÇÃO** (`SKILL.md` / persona / config / roteamento — **SEM** teste unitário) →
  **não existe "verde de teste".** Default: **ESCALA** (o dono ratifica). **Nunca auto-lande uma
  mudança de instrução alegando um "teste verde" que não existe.** (Só afrouxe se a config
  explicitamente permitir um bar fraco: aditivo/reversível E um verificador adversário separado
  concorda — mesmo assim, prefira escalar.)

Resumo da decisão: **script + testes verdes + fora do núcleo → landa; instrução, OU testes
vermelhos, OU tocou `core_path` → escala** (deixe o defeito registrado, reverta o diff se ele deixou
a máquina quebrada, e relate ao dono com o diagnóstico).

### Aprendizado + reload

**Aprendizado (depende do Bloco D1):** ao fim de um self-heal, o sub-agente — no papel **Reflector**
(Bloco D1: reflete quem não executou) — faz **append** no `lessons-log` e **cura** (refine/deprecate,
nunca sobrescreve) o `playbook` do **sidecar de self-heal** — lições sobre consertos de máquina (o
que reincide, o que dava false-pass). No início do próximo self-heal, leia esse playbook
(feed-forward) antes de despachar.

**Reload:** um sub-agente despachado e **cada invocação** leem o disco **fresh** — um conserto vale
no próximo despacho/invocação **automaticamente**, sem reload manual. Scripts são subprocessos →
sempre fresh. O **único** caso que precisa de ação é uma **sessão interativa única** em que a skill
se auto-modificou (ex.: editou a própria persona) e **segue no mesmo contexto** — a versão nova só
vale ao **re-invocar a skill** (ela relê a persona do disco). Nesse caso, avise o dono ao fim:
"me auto-modifiquei em `<arquivo>` — pra valer nesta sessão, re-invoque a skill ou comece uma nova".

## Templates usados

- `templates/config.template.json`:
  - **`selfheal_mode`** — `capture-only` (só registra, espera ratificação) vs `auto-fix` (conserta
    sozinho, com escalonamento obrigatório no núcleo). Comece em `capture-only`.
  - **`core_paths`** — lista dos arquivos-núcleo (persona, contrato de despacho, scripts centrais)
    cujo conserto SEMPRE escala pro dono, mesmo com testes verdes.
- O sidecar de aprendizado reutiliza os templates do Bloco D1 (`sidecar-lessons-log.template.md`,
  `sidecar-playbook.template.md`), num caminho próprio do loop de self-heal.

## Armadilhas

- **Confiar na alegação em vez do diff** — o motivo inteiro do contexto limpo é não deixar o ator se
  auto-aprovar. Sempre verifique diff + evidência.
- **Inventar "teste verde" para uma mudança de instrução** — instrução não tem teste unitário; o
  default é escalar, não landar.
- **Deixar o sub-agente vagar** — escopo restrito aos arquivos da própria máquina; nunca a máquina
  de terceiros nem código de domínio.
- **Rodar self-heal no meio de uma tarefa de domínio** — só na fronteira, ou para destravar algo
  essencial.
- **Pular o escalonamento no núcleo porque "o teste passou"** — teste verde não cobre o risco de um
  fix ruim no núcleo quebrar o próprio agente.
- **Esquecer que a máquina pode estar quebrada após um conserto reprovado** — se escalou por teste
  vermelho, reverta o diff antes de seguir.

## Quando NÃO usar

- A skill **não tem máquina própria** que possa quebrar (uma skill de tarefa pura, sem scripts nem
  config próprios) — não há o que auto-consertar.
- A skill **não é de TOPO** — self-heal pressupõe a capacidade de despachar um sub-agente de contexto
  limpo (Bloco A). Uma skill de tarefa que não despacha não tem o isolamento que impede o false-pass.
- Você **não instalou o Bloco D1** — sem sidecar, o self-heal não aprende; instale D1 antes.
- O dono **não quer** autonomia na própria máquina — deixe em `capture-only` permanente (ainda útil:
  registra os defeitos), ou não instale o bloco.

## Fonte

Destilado da seção "Self-healing das meta-skills" da persona do agente de topo de origem
(`.claude/agents/gerente-geral.md`), generalizada: cortados os nomes de scripts concretos, os
caminhos do projeto, a fila de tickets específica e o acoplamento a loop/wake. Depende do **Bloco A**
(contrato de despacho por marcador) e do **Bloco D1** (aprende com os consertos via sidecar).
