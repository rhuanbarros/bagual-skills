# UX Scenarios: Dômus (FIXTURE — E9.8, nunca o documento real)

> Cópia-fixture reduzida de `_bmad-output/C-UX-Scenarios/00-ux-scenarios.md`, usada
> SOMENTE para demonstrar o modo (a) (oráculo in-thread) da Story E9.8 sem escrever no
> documento canônico real. Formato idêntico ao real (bloco `### [NN: Título]` com
> `**Pages:**`).

## Scenario Summary

| ID | Scenario | Persona | Pages | Priority | Status |
|----|----------|---------|-------|----------|--------|
| 01 | O Parceiro fecha sua primeira venda com financiamento | A — O Parceiro | 9 | ⭐ P1 | ✅ Outlined |
| 02 | O Parceiro tira uma dúvida com a Central direto na proposta (DEMO E9.8, modo a) | A — O Parceiro | 1 | P2 | ✅ Outlined (in-thread, TCK-E98-DEMO-2) |

---

### [01: O Parceiro fecha sua primeira venda com financiamento]

**Persona:** A — O Parceiro
**Pages:** Clientes (lista/novo/detalhe-editar), Veículos (lista/novo/detalhe), Simulação, Proposta (nova/lista/detalhe)
**Priority:** P1

### [02: O Parceiro tira uma dúvida com a Central direto na proposta] (DEMO E9.8, modo a — escrito pelo oráculo in-thread, não pelo wds-8)

**Persona:** A — O Parceiro
**Pages:** Propostas Admin (chat por proposta)
**Priority:** P2
**Origem:** TCK-E98-DEMO-2 (worked example da Story E9.8) — escrito in-thread pelo
Gerente após `record-decision` retornar `proceed_dispatch: true` (precedente
TCK-E98-DEMO-1 ratificado), nunca invocando `wds-8`.
