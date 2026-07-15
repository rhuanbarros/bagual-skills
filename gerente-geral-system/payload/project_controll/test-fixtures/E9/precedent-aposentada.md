---
tipo: decisão-técnica
estado: aposentada
causa-da-morte: "fixture de teste — revertida por decisão posterior fictícia"
contador-de-utilidade: 0
areas: [sistema-orquestrador, oraculo]
reverte: null
created: 2026-07-10
updated: 2026-07-10
---

# Fixture E9 — precedente aposentado (NÃO sustenta alta confiança)

Entrada de fixture para os testes de `gerente_oracle.py` (Story E9.1). Representa um
padrão morto — mesmo que `estado: aposentada` sozinho não implique erro, uma decisão
morta nunca deve sustentar `--confidence high` de uma decisão nova.

## Contexto
Fixture de teste — nenhum contexto de produto real.

## Decisão
Fixture de teste — nenhuma decisão de produto real.

## Alternativas consideradas e rejeitadas
- (a) Nenhuma alternativa real foi considerada — esta é uma fixture sintética.

## Consequências
Usada exclusivamente por `test_gerente_oracle.py` para provar que um precedente
`estado: aposentada` SEMPRE rebaixa `--confidence high` para `low`.
