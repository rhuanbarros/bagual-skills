---
title: "Cenário — Reabrir proposta recusada"
created: 2026-07-11
updated: 2026-07-11
status: approved
analysis_ref: evolution/analysis/2026-07-11-reabrir-proposta-recusada.md
---

# Reabrir proposta recusada

> **FIXTURE — story E1.4.** Este arquivo é uma fixture de teste, não um cenário real do produto. Ele existe
> apenas para provar estruturalmente que o `bagual-qa-builder` enxerga uma evolução de design nova (E1.1),
> a normaliza em linha de Coverage Matrix (E1.2) e reconcilia o trigger-map associado por união (E1.3).
> NÃO copiar para `_bmad-output/evolution/scenarios/` real nem tratar como spec de produto.

## Target

Permitir que o Parceiro reabra uma proposta com status "Recusada" — reaproveitando cliente/veículo/simulação já
cadastrados — em vez de recomeçar o wizard de proposta do zero, quando a recusa foi por um motivo sanável
(ex: documentação incompleta) e não por reprovação de crédito definitiva.

## Current State

- Proposta recusada fica somente-leitura na tela de detalhe (`ProposalDetailPage`); o único caminho seguinte é
  criar uma proposta nova do zero pelo wizard, re-digitando cliente/veículo/simulação já existentes.
- Não existe nenhum botão/ação de "reabrir" em nenhuma tela do pipeline.

## Desired State

- Na tela de detalhe de uma proposta com status "Recusada", aparece um botão "Reabrir proposta".
- Ao clicar, o sistema cria uma nova proposta em status "Rascunho" pré-preenchida com o mesmo cliente, veículo
  e valores de simulação da proposta recusada, e leva o Parceiro direto ao Passo final do wizard para revisão
  antes de reenviar.
- A proposta original recusada permanece no histórico, agora com um rótulo "Reaberta como #<id-nova>".

## User Journey

**UJ-A. Parceiro reabre uma proposta recusada por documentação incompleta.**
- **Entry:** Parceiro abre o detalhe de uma proposta com status "Recusada" (`/app/propostas/:id`).
- **Path:** Lê o motivo da recusa (comentário da Central), clica "Reabrir proposta". Sistema confirma ("Isso vai
  criar uma nova proposta com os mesmos dados — continuar?"). Parceiro confirma.
- **Climax:** Nova proposta em "Rascunho" abre no wizard, Passo final, com cliente/veículo/simulação já
  preenchidos — só falta revisar e reenviar.
- **Resolution:** Parceiro corrige o que causou a recusa (ex: reenvia CNH legível) e reenvia a proposta.
- **Edge case:** Se o cliente ou veículo da proposta original foi excluído (soft delete) entre a recusa e a
  reabertura, o sistema avisa e pede para o Parceiro escolher outro cliente/veículo antes de prosseguir.

## Success Criteria

- Parceiro consegue reabrir uma proposta recusada em menos cliques que recriar do zero (sem redigitar
  cliente/veículo/simulação).
- Toda proposta reaberta preserva rastreabilidade para a proposta original recusada (auditoria).

## Scope

**Pages affected:**
- `frontend/src/features/proposals/pages/ProposalDetailPage.tsx` — novo botão "Reabrir proposta" (visível só
  quando `status === 'recusada'`)
- `frontend/src/features/proposals/pages/ProposalWizardPage.tsx` — suporte a abrir já no passo final, pré-
  preenchido a partir de uma proposta de origem

**Components touched:**
- Novo modal de confirmação "Reabrir proposta"

**Data changes:**
- Nova coluna `reopened_from_proposal_id` (nullable, FK para `proposals.id`) via migration
- Backend: novo endpoint/RPC atômico `reopen_proposal` (cria proposta + status_history numa transação, mesmo
  padrão de `create_proposal`)

**Risk level:** Low — feature aditiva, não altera o fluxo existente de criação/análise de proposta.
