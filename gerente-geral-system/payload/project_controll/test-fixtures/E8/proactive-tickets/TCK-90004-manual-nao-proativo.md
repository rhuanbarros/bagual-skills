---
id: TCK-90004
title: "Wizard de proposta: alternar perfil PF/PJ não limpa o veículo já selecionado, gerando registro órfão duplicado manualmente"
status: triado
priority: alta
category: bug
area: proposals/wizard
expanded: false
created: 2026-06-06
updated: 2026-06-06
origem: manual
visivel_pro_cliente: false
trilha: null
ledger_refs: []
---

## Descrição
Fixture de controle: ticket com texto MUITO parecido com TCK-90001, mas `origem: manual`
(reportado pelo dono, não achado proativo). Deve ser EXCLUÍDO do scan por padrão
(`--include-non-proactive` ausente) — prova que o filtro por `origem` funciona.

## Log
- 2026-06-06: criado (fixture E8.5 — controle de origem=manual)
