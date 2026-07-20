> **Referência sob demanda.** Extraído verbatim de `.claude/agents/gerente-geral.md` §
> "Execução da via (i) — wds-8 nunca headless (E9.8)" na decomposição do `SKILL.md` de
> `bagual-gerente-geral` para progressive disclosure. Único lugar onde este protocolo
> vive. Leia por inteiro antes da primeira vez que um Ticket com `trilha: wds` chegar à
> fase "despachar".

## Execução da via (i) — wds-8 nunca headless (E9.8)

Referência canônica: `ideias/prd-05-wds.md` FR-6 e `ideias/fase-0-spikes.md` § S3 (o
`wds-8` foi **testado ao vivo** e travou no primeiro passo do Analyze mesmo com
auto-approve — não é hipótese, é fato confirmado). Contrato completo, com o mecanismo
exato do gate e os três documentos canônicos, em `project_controll/gerente/
wds-routing.md` — leia-o por inteiro antes da primeira vez que um Ticket com `trilha:
wds` chegar à fase "despachar". Aqui só o resumo operacional.

**Quando dispara:** fase "3. despachar" (`references/ciclo-operacional.md`), passo 1 (mapear `trilha` → skill),
quando `trilha == wds` (decidido por "Roteamento de produto (Story E9.6)" — sub-passo a. da
fase "2. priorizar" em `references/ciclo-operacional.md`, via
(i)). **Regra dura, sem exceção:** você nunca invoca `wds-8` (nem qualquer `workflow-
*.md` dele) como sub-agente headless — nem "só o Analyze". Não há uma linha de despacho
"trilha wds → spawne o wds-* correspondente" — pare antes de montar qualquer
`open-dispatch` para este Ticket e siga o sub-passo abaixo em vez disso.

**A decisão — (a) vs (b), (b) é o padrão:**
1. Rode o "Protocolo do Oráculo (E9.1)" (`references/protocolo-oraculo.md`) para ESTA pergunta específica —
   `--tipo decisao-de-produto`, `--areas` = área do Ticket + a tag fixa
   `wds8-design-in-thread`, `--decision` = "executar via (i) no modo (a) in-thread".
2. `--confidence high` só é honrado se você citar `--precedent` de uma Entrada de
   Ledger `decisao-de-produto` `estado: ativa`, `ratification: ratified` (ou ausente)
   de uma execução **anterior** do modo (a) já revisada pelo dono. **No início, tal
   precedente não existe** — `record-decision` rebaixa mecanicamente para `low`,
   `proceed_dispatch: false`. Isso é o que torna "(b) é o padrão" uma garantia mecânica
   (F10), não uma promessa de prosa.
3. **`proceed_dispatch: false` (o caso normal) → modo (b), espera o dono:** mova o
   Ticket para **`precisa-de-info`** (não `triado` — especialização deliberada, ver
   `wds-routing.md` §6: o desbloqueio real exige o dono rodar `wds-8` interativamente,
   não só ratificar uma frase escrita) via `bagual-tickets`, citando o `ledger_path` +
   a instrução "aguardando o dono rodar wds-8 interativamente". Inclua o
   `pending_entry` em `decisions_pending` no próximo `write-snapshot --pending-json`
   (mesmo mecanismo de qualquer decisão de baixa confiança — surfaça no Briefing,
   E8.7, sem wiring novo). O que o dono faz depois (até onde ele leva o `wds-8`,
   inclusive `[I]/[T]/[P]` se ele mesmo decidir) é fora do escopo deste protocolo — é a
   sessão interativa dele, não um despacho seu.
4. **`proceed_dispatch: true` (raro, precedente real e ratificado) → modo (a), oráculo
   in-thread:** você mesmo — nunca um sub-agente, nunca `Skill(wds-8)` — aplica
   Analyze/Scope/Design como conhecimento (mesmo padrão do "Cérebro de Planejamento
   (E9.3)" para skills facilitador-only) e escreve a atualização direto nos três
   documentos canônicos (ver exceção (d) em "Quem você é" em `.claude/agents/gerente-geral.md`):
   `design-process/C-UX-Scenarios/00-ux-scenarios.md`, `design-process/B-Trigger-Map/
   00-trigger-map.md`, `_bmad-output/product-decisions.md`. Registre a conclusão no `##
   Log` do Ticket (via `bagual-tickets`), citando o `ledger_path`. **Pare aí.**

**Fronteira A/S/D-only, sem exceção — `[I]/[T]/[P]` nunca no fluxo autônomo, em nenhum
modo:** você já nunca executa código de produto (`frontend/**`/`backend/**`/
`supabase/**` — "Quem você é" em `.claude/agents/gerente-geral.md`), o que já barra `[I]/[T]/[P]` do `wds-8` por
construção; o modo (a) para explicitamente no Design (passo 4 acima, nunca avança); e
`ideias/prd-05-wds.md` § "Não-Objetivos" confirma que Implement/Test/Deploy são
território do BMad (`bagual-epic-runner`/`bmad-quick-dev`), nunca do `wds-8` — se o
design revelar trabalho de código, isso vira um Ticket/`trilha` **normal**
(`rapida`/`spec`/`epic`), nunca o `workflow-implement.md` do `wds-8`.

**A via (ii) segue 100% autônoma — nunca toca este protocolo, nunca invoca `wds-8`.**
Nenhuma mudança para ela.
