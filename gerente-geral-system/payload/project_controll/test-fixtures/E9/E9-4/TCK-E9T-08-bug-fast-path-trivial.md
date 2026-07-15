---
id: TCK-E9T-08
title: "[FIXTURE E9.4] Trivial cosmético via fast-path (F22) — sem verificação formal"
status: triado
priority: baixa
category: bug
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
Fixture sintética de teste (Story E9.4) — NÃO é um ticket real. Simula um ticket que
passou pelo fast-path trivial (F22, `## Log` registra "fast-path trivial") — não tem
`## Verificação` formal (`Confirmado: sim`), mas o marcador de fast-path substitui esse
sinal. Deve bater na Regra A (rapida) mesmo sem `Confirmado: sim` explícito.

## Checagem de decisão de produto
Nenhum conflito encontrado em `product-decisions.md`.

## Log
- 2026-07-11: fast-path trivial — verificação/dedup pulados (fixture de teste, Story E9.4).
