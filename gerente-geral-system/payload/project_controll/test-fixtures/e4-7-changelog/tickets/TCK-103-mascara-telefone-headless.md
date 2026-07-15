---
id: TCK-103
title: "Fix headless: normalizar máscara de telefone no cadastro de parceiro"
status: concluido
priority: media
category: bug
area: partners
expanded: false
visivel_pro_cliente: pendente
updated: 2026-07-09
---

## Descrição
Criado em lote (F21, criação headless) por um agente ao expandir outro ticket — ainda
não triado quanto a visibilidade pro cliente.

## Verificação
- Confirmado: sim
- Evidência: frontend/src/features/partners/utils/phoneMask.ts:18

## Checagem de decisão de produto
Nenhum conflito encontrado.

## Log
- 2026-07-08: criado (headless, origem: expansão de TCK-101)
- 2026-07-09: concluído — `visivel_pro_cliente` permanece `pendente`; alguém (bibliotecária/Gerente) precisa decidir antes do changelog rodar (AC de E4.7)
