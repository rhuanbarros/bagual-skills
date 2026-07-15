---
id: TCK-90001
title: "Wizard de proposta: alternar perfil PF/PJ não limpa o veículo já selecionado, gerando registro órfão"
status: concluido
priority: alta
category: bug
area: proposals/wizard
expanded: false
created: 2026-06-01
updated: 2026-06-05
origem: proativo
visivel_pro_cliente: false
trilha: rapida
ledger_refs: []
---

## Descrição
Ao trocar o perfil (Pessoa Física / Pessoa Jurídica) no Passo 1 do wizard de criação de
proposta depois de já ter avançado até o Passo 4 e criado um veículo, o campo `vehicleId`
da store permanece setado com o veículo antigo. Reentrar no Passo 4 sob o novo perfil cria
um SEGUNDO veículo, deixando o primeiro órfão (nunca referenciado por nenhuma proposta).

## Verificação
- Confirmado: sim
- Evidência: proposalWizardStore.ts (achado por análise adversarial proativa)

## Log
- 2026-06-01: criado (fixture E8.5 — achado proativo fechado, usado para provar dedup contra histórico)
- 2026-06-05: concluido — corrigido em `setProfile` limpando `vehicleType`/`vehicleId`

## Fechamento
abc1234fixture
