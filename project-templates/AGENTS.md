# {NOME_DO_PROJETO} — Contexto do Projeto

> Arquivo de contexto para assistentes AI (Claude Code, Cursor, GitHub Copilot, Gemini, etc.).
> Leia este arquivo antes de qualquer implementação.
> **Substitua todos os campos {ENTRE_CHAVES} antes de usar.**

---

## O que é este projeto

{DESCRIÇÃO_DO_PROJETO — o que faz, para quem, contexto de negócio}

---

## Stack tecnológica

| Camada | Tecnologia |
|---|---|
| {camada1} | {tecnologia1} |
| {camada2} | {tecnologia2} |
| Testes | {framework_de_testes} |

---

## Estrutura de artefatos BMad

```
_bmad-output/
├── projects-history.md          ← Timeline de stories concluídas
├── anti-patterns.md             ← Padrões a EVITAR (leitura obrigatória)
├── decisions.md                 ← Decisões técnicas de implementação (não desfazer)
├── product-decisions.md         ← Decisões sobre comportamento do produto (não reverter sem decisão explícita)
├── notes.md                     ← Conhecimento operacional e insights acumulados em sessões
├── planning-artifacts/          ← PRD, arquitetura, epics, UX design
└── implementation-artifacts/    ← Story files + sprint tracking
    ├── sprint-status.yaml
    └── N-M-story-name.md
```

---

## Regras críticas — leia antes de implementar

### ❌ {REGRA_CRITICA_1}
{descrição da regra}

### ❌ {REGRA_CRITICA_2}
{descrição da regra}

### ✅ Ao implementar qualquer coisa: use as skills BMad e leia os arquivos de conhecimento
Não implemente código diretamente. Use `/bmad-quick-dev` para mudanças ad-hoc, `/bmad-dev-story` para stories, `/bagual-bmad-implement-quick-epic` para epics completos. As skills carregam automaticamente `anti-patterns.md`, `decisions.md`, `product-decisions.md` e `notes.md` como contexto.

---

## Como rodar o stack local

```bash
# {passo 1}
{comando}

# {passo 2}
{comando}
```

---

## Skills disponíveis (BMad)

Instaladas em `.claude/skills/`. Requerem Claude Code.

| Skill | Quando usar |
|---|---|
| `/bagual-bmad-implement-quick-epic {N}` | Implementar um epic completo (modo normal, com code review) |
| `/bagual-bmad-implement-quick-epic {N} fast` | Implementar epic em modo rápido (sem loop de review) |
| `/bmad-quick-dev` | Mudança ad-hoc (bug fix, feature pontual, refactor) |
| `/bmad-dev-story {story-file}` | Implementar uma story específica |
| `/bmad-code-review` | Revisar código uncommitted |
| `/bagual-test-pipeline high yolo` | Rodar suite de testes completa com auto-fix |
| `/bmad-sprint-status` | Ver status atual do sprint |
| `/bmad-create-story {N-M}` | Criar arquivo de story a partir dos epics |

---

## Estado atual do projeto

{descreva o estado atual — ex: "Em desenvolvimento inicial", "Epics 1-2 concluídos", etc.}
