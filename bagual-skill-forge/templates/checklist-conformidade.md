# Checklist de conformidade — rode contra a skill gerada antes de entregar

Cole mentalmente contra o que você acabou de gerar. Qualquer "não" = corrija antes de entregar.

## Ativação enxuta (P1) — o mais importante
- [ ] O `SKILL.md` gerado tem menos de ~60 linhas e **não** contém o contrato inteiro.
- [ ] Ligar a skill não força ler >~300 linhas antes da 1ª decisão útil.
- [ ] As técnicas estão em `references/` e são lidas **sob demanda**, não eager na ativação.
- [ ] O estado (Bloco B) é lido pela fase que precisa, não tudo na ativação.

## Estrutura
- [ ] Se é skill de TOPO: a persona está em `.claude/agents/<nome>.md`, **fora** do SKILL.md (P2).
- [ ] Se é skill de TAREFA: não foi gerada persona/estado desnecessários.
- [ ] Só os blocos **pedidos** foram instalados — nenhum a mais.
- [ ] Nenhuma técnica **cortada** apareceu (wake/cota/guard-mecânico/roteamento/QA/epic).

## Genérico (P0)
- [ ] Zero placeholder `<ASSIM>` órfão sobrando em qualquer arquivo gerado.
- [ ] Zero nome/tela/entidade do projeto de origem OU do projeto atual vazado para os templates —
      tudo preenchido com o domínio do **destino**.

## Obrigações herdadas
- [ ] RULE ZERO presente (Bloco E) — a skill registra conhecimento ao fim de cada tarefa.
- [ ] Se TOPO: a persona diz "nunca executa, despacha" (P4).
- [ ] Nada forka skills de terceiros (P6).

## Fecho
- [ ] `README.md` da skill gerada lista os arquivos e os próximos passos.
- [ ] A geração foi registrada no Ledger do projeto atual (se houver).
