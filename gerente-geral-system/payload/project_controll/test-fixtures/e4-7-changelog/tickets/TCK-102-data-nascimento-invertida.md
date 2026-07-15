---
id: TCK-102
title: "Corrigir data de nascimento invertida no formulário de cliente PF"
status: concluido
priority: alta
category: bug
area: clients
expanded: false
visivel_pro_cliente: true
updated: 2026-07-08
---

## Descrição
Data de nascimento salva como DD/MM trocado com MM/DD em alguns casos.

## Verificação
- Confirmado: sim
- Evidência: frontend/src/features/clients/components/MaskedDateInput.tsx:40

## Checagem de decisão de produto
Nenhum conflito encontrado.

## Log
- 2026-07-07: criado
- 2026-07-08: concluído (fechamento SEM `changelog_text` — ticket fechado antes de
  E5.4 existir; script cai no fallback do título + aviso de revisão)
