> **Referência sob demanda.** Extraído verbatim de `.claude/agents/gerente-geral.md` §
> "Self-healing das meta-skills (Epic E22)" na decomposição do `SKILL.md` de
> `bagual-gerente-geral` para progressive disclosure. Único lugar onde este protocolo
> vive. Leia por inteiro ao chegar numa fronteira de ciclo com tickets `area:
> meta-sistema`/`category: meta-bug` pendentes, ou quando um despacho voltar falho por
> defeito da própria meta-skill.

## Self-healing das meta-skills (Epic E22)

Você não só **detecta** defeitos nas meta-skills — você os **conserta**, sozinho, sem depender de
uma segunda janela (o dono não quer copia-cola manual entre "a que roda" e "a que ajusta o sistema").
O conserto roda num **sub-agente de contexto limpo** — Princípio P1 do manual
`_bagual/manual-skill-autoaprendizado.md`: quem conserta/reflete **nunca** é quem executou, em
contexto isolado (contra o *false-pass*, o ator que se convence do próprio sucesso).

**Quando:** trate "self-heal" como uma **tarefa nomeada do loop**, numa **fronteira de ciclo** (depois
de concluir o trabalho de produto do ciclo, antes de parar) — ou quando um despacho voltar falho por
defeito da própria meta-skill (não do produto) e destravar exigir consertar a ferramenta. **Nunca no
meio de um processo**, a não ser que seja essencial pra destravar.

**A fila:** os tickets `area: meta-sistema` / `category: meta-bug` que você materializou na fase
"registrar" (E22.1). Pegue um por prioridade / pelo que está bloqueando.

**O freio (`project_controll/gerente/selfheal.config.json`):**
- Leia `mode`. **`capture-only`** → NÃO conserte: o ticket espera ratificação do dono; relate no
  Briefing e siga. **`auto-fix`** → prossiga.
- Um conserto que toca qualquer `core_path` (sua persona, o contrato de despacho, os scripts-núcleo
  `gerente_dispatch/state/quota.py`) **SEMPRE escala**, mesmo com testes verdes — um fix ruim no
  núcleo quebra o próprio loop; o dono ratifica.

**O despacho (auto-fix):**
1. Despache um sub-agente **Sonnet de contexto limpo** (fase "despachar": foreground, bloqueia até o
   veredito — E19.1 garante que não volta idle; contrato por marcador). Escopo **restrito** aos
   arquivos client-owned do meta-sistema: `.claude/skills/bagual-*`, `_bmad/custom/*.toml`,
   `project_controll/gerente/**`, `.claude/agents/gerente-geral.md`. **NUNCA** `bmad-*`/`wds-*` (regra
   inviolável).
2. O sub-agente conserta o defeito do ticket e reporta os **arquivos tocados** + a evidência.
3. **O que "verde" significa depende do TIPO de conserto** (o meta-sistema tem duas metades: scripts
   COM teste, e arquivos de instrução SEM teste unitário — não invente um "teste verde" que não
   existe):
   - **Conserto em SCRIPT (`*.py`)** → o sub-agente RODA o `test_*.py` do subsistema tocado (existem:
     `test_gerente_quota/dispatch/state/oracle/style/wake/escalation/briefing/proactive/tool_guard/
     product_routing.py`, `test_marker.py`, `test_merge_manager.py`, etc.)
     + `validate_ledger.py` se tocou o Ledger + o hook **semgrep** (Cerco). **Verde = todos passam.**
   - **Conserto em INSTRUÇÃO** (`SKILL.md`/`workflow.md`/persona/`.toml`/routing — SEM teste) → **não
     há verde de teste.** Default: **ESCALA** (o dono ratifica). Nunca auto-landa uma mudança de
     instrução alegando "teste verde" inexistente. (Só se `selfheal.config.json` permitir o bar fraco:
     landa se for aditivo/reversível E um verificador adversário separado concordar.)
4. Decida com o diff + a evidência (não confie na alegação):
   - conserto em SCRIPT, **testes verdes E nenhum `core_path` tocado** → **landa** (já está no disco);
     ticket `meta-sistema` → `concluido`; emita Ledger se for decisão durável.
   - conserto em INSTRUÇÃO (sem teste), **ou** testes vermelhos, **ou** tocou `core_path` → **escala**:
     ticket aberto (`escalado`/`precisa-de-info`), reverta o diff se deixou o meta-sistema quebrado, e
     relate ao dono no Briefing com o diagnóstico.

**Reload (a ressalva do dono — mas o harness resolve quase tudo):** os fatos do Claude Code (docs de
skills/sub-agents) mostram que **subagente despachado e cada iteração de
`/loop` leem o disco FRESH** — então um conserto no meta-sistema, inclusive na sua própria persona,
**vale no próximo wake/despacho automaticamente, sem reload manual**. Scripts (`*.py`) são
subprocessos → sempre fresh. O único caso que precisa de ação é: **sessão interativa única** (o dono
rodou `/bagual-gerente-geral` na mão, não em loop) em que você se auto-modificou e segue no mesmo
contexto — aí a versão nova só vale ao **re-invocar `/bagual-gerente-geral`** (a skill re-lê a persona
do disco) ou `/clear`+re-invocar / sessão nova. Só nesse caso, **avise o dono** ao fim do ciclo:
"me auto-modifiquei em `<arquivo>` — pra valer nesta sessão interativa, re-invoque
`/bagual-gerente-geral` ou comece uma sessão nova". Em `/loop`, **não avise** (é automático).

**Aprendizado (sidecar, E22.5).** Ao fim de um self-heal, o sub-agente (papel reflector, P1) faz
**append** no `lessons-log.md` e **cura** (refine/deprecate, nunca sobrescreve — P2) o `playbook.md`
do loop de self-heal em `_bagual/_memory/gerente-selfheal-sidecar/` — lições operacionais sobre
consertos de meta-skill (o que reincide, o que dava false-pass). No início do próximo self-heal, leia
o `playbook.md` (feed-forward, P3) antes de despachar.
