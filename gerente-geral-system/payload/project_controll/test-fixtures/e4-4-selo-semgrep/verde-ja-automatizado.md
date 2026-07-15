---
tipo: anti-pattern
estado: ativa
causa-da-morte: null
contador-de-utilidade: 2
selo: 🟢
automatizado: true
areas: [backend]
---

# Anti-pattern de brinquedo 🟢 já automatizado — NÃO deve ser candidato

## Contexto
Fixture: uma regra Semgrep já foi autorada para este anti-pattern (PRD 04/E7
simulado) — a entrada continua VIVA (não aposentada), só sai da fila.

## Decisão
Não fazer KK; fazer LL.

## Alternativas consideradas e rejeitadas
- (a) manter KK — rejeitada porque causa bug real.

## Consequências
Regra Semgrep já em produção; contador incrementado 2x.
