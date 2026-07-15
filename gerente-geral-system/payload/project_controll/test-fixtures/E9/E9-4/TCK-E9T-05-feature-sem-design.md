---
id: TCK-E9T-05
title: "[FIXTURE E9.4] Feature pequena, sem design confirmado"
status: triado
priority: baixa
category: feature
area: fixture-teste
expanded: false
created: 2026-07-11
updated: 2026-07-11
origem: manual
visivel_pro_cliente: false
trilha: null
ledger_refs: []
---

## Descrição
Fixture sintética de teste (Story E9.4) — NÃO é um ticket real. Simula uma feature onde
`design_confirmado` está ausente (default false) — a skill não tem sinal explícito de que
é preciso desenho de tela/componente novo. Deve ESCALAR (não bate 100% na Regra B).

## Verificação
- Confirmado: feature nova, nada disso existe hoje no produto (sintético).

## Checagem de decisão de produto
Nenhum conflito encontrado em `product-decisions.md`.

## Log
- 2026-07-11: fixture criada para teste de `classify_trilha.py` (Story E9.4).
