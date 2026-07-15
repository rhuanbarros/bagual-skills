---
id: TCK-105
title: "Corrigir paginação da lista de parceiros"
status: concluido
priority: alta
category: bug
area: partners
expanded: false
visivel_pro_cliente: true
changelog_text: "A lista de parceiros agora pagina corretamente ao passar de 20 itens."
closed_at: "2026-07-03T10:00:00Z"
updated: 2026-07-03
---

## Descrição
Paginação parava de avançar depois da página 2.

## Verificação
- Confirmado: sim
- Evidência: frontend/src/features/admin-partners/pages/AdminPartnersPage.tsx:88

## Checagem de decisão de produto
Nenhum conflito encontrado.

## Log
- 2026-07-01: criado
- 2026-07-03: concluído e já publicado num deploy de Produção ANTERIOR ao corte deste
  changelog (fixture: prova que o script não duplica entregas já anunciadas)
