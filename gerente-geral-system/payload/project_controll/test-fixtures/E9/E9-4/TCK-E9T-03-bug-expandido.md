---
id: TCK-E9T-03
title: "[FIXTURE E9.4] Bug confirmado, mas espalhado por vários componentes"
status: triado
priority: alta
category: bug
area: fixture-teste
expanded: true
created: 2026-07-11
updated: 2026-07-11
origem: manual
visivel_pro_cliente: false
trilha: null
ledger_refs: []
---

## Descrição
Fixture sintética de teste (Story E9.4) — NÃO é um ticket real. Simula um bug
confirmado (`Confirmado: sim`), mas `expanded: true` (encontrado em múltiplos locais) —
escopo maior que um ponto único. Deve ESCALAR (não bate 100% na Regra A: falta
`expanded: false`).

## Verificação
- Confirmado: sim
- Evidência: `fixture/A.tsx:1`, `fixture/B.tsx:1`, `fixture/C.tsx:1` (sintético)

## Locais afetados
- A, B, C (sintético)

## Checagem de decisão de produto
Nenhum conflito encontrado em `product-decisions.md`.

## Log
- 2026-07-11: fixture criada para teste de `classify_trilha.py` (Story E9.4).
