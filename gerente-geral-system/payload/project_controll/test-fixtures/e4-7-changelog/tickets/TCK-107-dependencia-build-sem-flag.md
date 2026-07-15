---
id: TCK-107
title: "Atualizar dependência interna do build (sem flag ainda triada)"
status: concluido
priority: baixa
category: chore
area: build
expanded: false
updated: 2026-07-07
---

## Descrição
Ticket antigo, criado antes de `visivel_pro_cliente` existir no schema (E5.3 ainda não
implementada no board real) — fixture prova que a AUSÊNCIA do campo (não só
`false`/`pendente`) também é tratada como "sem entrada de changelog", nunca como
"pendente" nem "erro".

## Verificação
- Confirmado: sim
- Evidência: package.json

## Checagem de decisão de produto
Nenhum conflito encontrado.

## Log
- 2026-07-06: criado
- 2026-07-07: concluído
