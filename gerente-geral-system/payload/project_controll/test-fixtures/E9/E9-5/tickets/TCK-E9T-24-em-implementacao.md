---
id: TCK-E9T-24
title: "Fixture E9.5 — ticket em-implementacao (candidato a órfão)"
status: em-implementacao
priority: alta
category: bug
area: dashboard
expanded: false
created: 2020-01-03
updated: 2020-01-03
origem: manual
visivel_pro_cliente: false
trilha: rapida
escalonar: false
design_confirmado: false
ledger_refs: []
---

## Descrição
Fixture sintética — ticket que ficou em `em-implementacao` (despacho em voo). Usado por
`orphan-sweep` (E9.5): revertido para `pronto-para-implementar` quando não existe lock
do Gerente vivo (heartbeat parado/ausente), preservado quando existe.

## Verificação
- Confirmado: sim
- Evidência: fixture sintética, sem arquivo real

## Checagem de decisão de produto
nenhum conflito encontrado

## Log
- 2020-01-03: trilha `rapida` comitada pela skill — Regra A
- 2020-01-03: despachado pelo Gerente (fixture sintética)
