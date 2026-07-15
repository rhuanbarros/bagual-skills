---
tipo: decisão-técnica
estado: ativa
causa-da-morte: null
contador-de-utilidade: 0
areas: [sistema-orquestrador, oraculo]
reverte: null
created: 2026-07-10
updated: 2026-07-10
---

# Fixture E9 — precedente válido (ativa, nunca corrigido)

Entrada de fixture para os testes de `gerente_oracle.py` (Story E9.1). Representa um
padrão já estabelecido e vivo que uma decisão de ALTA confiança pode citar via
`--precedent`.

## Contexto
Fixture de teste — nenhum contexto de produto real.

## Decisão
Fixture de teste — nenhuma decisão de produto real.

## Alternativas consideradas e rejeitadas
- (a) Nenhuma alternativa real foi considerada — esta é uma fixture sintética.

## Consequências
Usada exclusivamente por `test_gerente_oracle.py` para provar que um precedente
`estado: ativa` sem `ratification: corrected` sustenta `--confidence high`.
