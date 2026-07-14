---
name: <NOME-SKILL>
description: <UMA-FRASE-DO-QUE-A-SKILL-FAZ>. Use quando o usuário disser <GATILHOS-SEPARADOS-POR-VIRGULA>.
---

# <NOME-SKILL> — <TÍTULO-CURTO>

> Invocador fino. <SE-TOPO: Adote a persona de `.claude/agents/<NOME-SKILL>.md`.> Este SKILL.md é
> curto de propósito (ativação enxuta) — os detalhes de cada técnica ficam em `references/` e são
> lidos sob demanda.

## Regras invioláveis
- <LIMITE-1 — ex.: nunca executa código de produto; despacha para sub-agente>
- <LIMITE-2 — ex.: ações irreversíveis/de produção só com autorização expressa do dono>
- <LIMITE-3>

## Ao ser invocada
<SE-TOPO:>
1. **Adote a persona:** leia `.claude/agents/<NOME-SKILL>.md` (o esqueleto de decisão + limites).
2. **Reconstrua a consciência mínima** só do que a fase precisa (não leia todo o estado de uma vez):
   <LISTE-OS-ARQUIVOS-DE-ESTADO-ESSENCIAIS-DO-BLOCO-B-SE-INSTALADO>.
3. **Rode o que o usuário pediu** — uma tarefa específica dada na invocação, ou um ciclo do loop
   operacional descrito na persona.
<SE-TAREFA:>
1. **Leia o feed-forward** (se Bloco D1 instalado): `<CAMINHO-SIDECAR>/playbook.md` — as regras
   destiladas de runs anteriores.
2. **Execute a tarefa** seguindo as etapas de `references/<DOC-DE-DOMÍNIO>.md`.
3. **Ao terminar**, cumpra os hooks de fim: reflita no sidecar (D1) e registre conhecimento durável
   (RULE ZERO — Bloco E).

## Roteador de referências (leia sob demanda)
- Para <ASSUNTO-A> → `references/<a>.md`
- Para <ASSUNTO-B> → `references/<b>.md`
