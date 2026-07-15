---
tipo: decisão-técnica          # decisão-técnica | decisão-de-produto | decisão-de-arquitetura | regra | padrão | anti-pattern
estado: candidata                # candidata | ativa | aposentada
causa-da-morte: null              # obrigatória (string não-vazia) SÓ quando estado == aposentada
contador-de-utilidade: 0          # inteiro >= 0 — ver README.md §3 (isenção de decisão-*/padrão)
areas: []                          # tags de feature/área, ex.: [proposals, credits] — E3.3
reverte: null                      # path relativo p/ a entrada original, SÓ se esta entrada é uma reversão
created: YYYY-MM-DD
updated: YYYY-MM-DD
# --- campos extras, SÓ para tipo: anti-pattern (remover para os demais tipos) ---
# selo: 🟢                        # 🟢 automatizável mecanicamente | 🟡 híbrido | 🔴 só-humano
# automatizado: false              # true quando uma regra Semgrep já existe para este anti-pattern (PRD 04/E7)
---

# <Título curto e específico da entrada>

## Contexto
<O que motivou esta decisão/regra/padrão — o problema observado, não a solução. Cite a
story/ticket/incidente de origem quando houver.>

## Decisão
<A decisão/regra/padrão em si, formulada de forma concreta e acionável. Para `regra`,
formule de um jeito verificável (o que especificamente é proibido/exigido).>

## Alternativas consideradas e rejeitadas
- (a) <alternativa considerada> — rejeitada porque <causa concreta>
- (b) <alternativa considerada> — rejeitada porque <causa concreta>

## Consequências
<Impacto da decisão, trade-off aceito conscientemente, o que passa a valer a partir
daqui, o que fica proibido/permitido.>

<!-- SÓ para tipo: regra — remover para os demais tipos -->
<!--
## Enforcement
<Como a regra é/seria verificada hoje (manual, code review) e o caminho para
enforcement mecânico (candidata a Semgrep via selo, PRD 04/E7).>
-->
