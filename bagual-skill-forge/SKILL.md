---
name: bagual-skill-forge
description: Forja uma skill nova (para qualquer projeto e qualquer assunto, não só programação) já com as técnicas de agente autônomo destiladas e curadas — arquitetura em camadas, estado persistente/retomar, autoaprendizado (sidecar), autocorreção (self-heal), captura de conhecimento (Ledger) e aprendizado de estilo do dono. Gera um SKILL.md fino + persona em .claude/agents/ + os andaimes escolhidos, com ativação enxuta (progressive disclosure). Use quando o usuário disser "forjar skill", "criar skill nova", "bagual-skill-forge", "nova skill com autoaprendizado", "skill de gerente/topo para outro projeto", ou "montar um agente autônomo".
---

# bagual-skill-forge — forja de skills (kit de técnicas curado)

> Skill **geradora**: cria outra skill, no projeto atual (ou num destino que o usuário indicar), já
> equipada com os padrões de agente autônomo deste kit. **Este `SKILL.md` é deliberadamente fino**
> (Princípio P1 — ativação enxuta): ele só orienta o fluxo; o conteúdo real vive em `references/`
> e `templates/`, lidos **sob demanda**.

## Regras invioláveis (herdadas de `references/principios.md`)

- **Genérico, nunca acoplado** (P0): não copie conteúdo/nome/tela do projeto de origem nem do atual
  para dentro dos templates — preencha placeholders com o domínio do **destino**.
- **Ativação enxuta** (P1): a skill gerada nasce fina — SKILL.md pequeno, persona curta, técnicas em
  `references/` sob demanda. Se ligar a skill gerada exige ler >~300 linhas antes da 1ª decisão, o
  desenho está errado.
- **Persona-como-arquivo** (P2): a definição do agente vai em `.claude/agents/<nome>.md`, **fora** do
  SKILL.md.
- **Não forke skills de terceiros** (P6): componha com BMad/WDS/etc., nunca copie.

## Fluxo (o que fazer ao ser invocada)

### 1. Descoberta (pergunte só o essencial)
Faça as perguntas mínimas para configurar a geração — em uma rodada, não uma de cada vez:
- **Propósito** da skill nova, em uma frase (qual trabalho ela faz, em que projeto/assunto).
- **Natureza** (P3): é uma skill de **TOPO** (decide/despacha/coordena, agente autônomo) ou de
  **TAREFA** (executa uma unidade do início ao fim)? Isso filtra os blocos aplicáveis.
- **Nome** da skill (kebab-case) e **destino** (projeto atual por padrão; ou caminho).
- **Quais blocos** de técnica instalar — apresente o menu de `references/catalogo.md` com a
  recomendação por natureza (TOPO → A, B, D1, D2, E, G conforme o caso; TAREFA → D1, E, G).

### 2. Carregue só o que foi escolhido (P1)
Leia `references/catalogo.md` para o mapa, depois **apenas** os docs dos blocos escolhidos
(`bloco-a-*`, `bloco-b-*`, `bloco-d-*`, `bloco-e-*`, `bloco-g-*`). Não leia os blocos que o usuário
não pediu.

### 3. Gere os arquivos a partir de `templates/`
Cada doc de bloco lista os templates que ele usa e os placeholders a preencher. Produza, no destino:
- `.claude/skills/<nome>/SKILL.md` — a partir de `templates/skill.template.md` (fino).
- `.claude/agents/<nome>.md` — a partir de `templates/persona.template.md` (só se for TOPO, P2).
- Os andaimes de cada bloco (estado, diário, sidecar, ledger, configs) via os templates indicados.
- Um `README.md` da skill gerada via `templates/README-generated.template.md`.
Preencha **todos** os placeholders `<ASSIM>` com o domínio do destino — sem sobras de placeholder.

### 4. Verifique a conformidade
Rode o checklist de `templates/checklist-conformidade.md` contra o que você gerou (ativação enxuta,
persona fora do SKILL, zero placeholder órfão, blocos só os pedidos, RULE ZERO presente). Corrija
antes de entregar.

### 5. Entregue
Liste os arquivos criados, o que cada bloco instalou, e os **próximos passos manuais** (ex.: primeiro
run que popula o sidecar, onde o dono edita a persona). Registre a geração no Ledger do projeto atual
se ele tiver um (RULE ZERO — Bloco E).

## Limites
- Não implemente a lógica de **domínio** da skill nova (o que ela faz de fato) — o kit instala a
  **máquina de agente** (as técnicas); a lógica de domínio o dono/uma sessão de dev preenche depois,
  nos pontos marcados na persona/SKILL gerados.
- Não instale técnicas cortadas na curadoria (wake/scheduling, cota, guards mecânicos, roteamento de
  produto, QA gate, pipeline epic/story) — ver `references/catalogo.md`.
