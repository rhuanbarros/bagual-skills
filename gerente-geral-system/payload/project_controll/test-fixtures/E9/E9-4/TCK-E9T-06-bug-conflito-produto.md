---
id: TCK-E9T-06
title: "[FIXTURE E9.4] Bug claro, mas colide com decisão de produto registrada"
status: triado
priority: media
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
Fixture sintética de teste (Story E9.4) — NÃO é um ticket real. Simula um bug com
verificação confirmada e único local (bateria na Regra A), mas com um conflito real
registrado em `## Checagem de decisão de produto` — deve ESCALAR mesmo assim (o
conflito veta a Regra A).

## Verificação
- Confirmado: sim
- Evidência: `fixture/D.tsx:1` (sintético)

## Checagem de decisão de produto
Conflito: este comportamento parece intencional — ver `product-decisions.md`, entrada
sintética "[FIXTURE] comportamento X é decisão de produto" (fabricado só para o teste).

## Log
- 2026-07-11: fixture criada para teste de `classify_trilha.py` (Story E9.4).
