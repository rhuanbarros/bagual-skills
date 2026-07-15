---
id: TCK-90002
title: "Admin parece poder mover proposta para qualquer status, suspeita de falta de validação de transição"
status: descartado
priority: media
category: duvida
area: proposals/admin
expanded: false
created: 2026-06-02
updated: 2026-06-03
origem: proativo
visivel_pro_cliente: false
trilha: null
ledger_refs: []
---

## Descrição
Análise adversarial proativa encontrou que `AdminProposalService.update_status_any()`
permite mover uma proposta entre quaisquer status não-terminais livremente, sem seguir a
máquina de transições usada pelo parceiro. Suspeita inicial de bug de validação ausente.

## Checagem de decisão de produto
Bate com `product-decisions.md` — "[PRODUCT] Admin status update — bypass da máquina
mantido" (2026-06-10): é comportamento intencional (liberdade operacional da Central), não
um bug.

## Verificação
- Confirmado: não — comportamento intencional, ver checagem acima
- Evidência: N/A

## Log
- 2026-06-02: criado (fixture E8.5 — achado proativo descartado, usado para provar dedup contra histórico)
- 2026-06-03: descartado — bate com decisão de produto já registrada, não é bug
