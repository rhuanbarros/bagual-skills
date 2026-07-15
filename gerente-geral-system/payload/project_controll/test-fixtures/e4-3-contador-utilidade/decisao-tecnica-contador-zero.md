---
tipo: decisão-técnica
estado: ativa
causa-da-morte: null
contador-de-utilidade: 0
areas: [backend]
---

# Decisão técnica de brinquedo com utilidade zero — NUNCA deve virar candidata a poda

## Contexto
Fixture: `decisão-técnica` não tem evento de "foi consultada" instrumentado — o
contador ficaria sempre zero, e isso é esperado, não sinal de desuso (FR-7).

## Decisão
Fazer EE.

## Alternativas consideradas e rejeitadas
- (a) não fazer EE — rejeitada porque FF.

## Consequências
Nenhuma real.
