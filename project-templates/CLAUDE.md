@AGENTS.md

---

## Claude Code — Contexto Adicional

### Regra: use as skills BMad para qualquer implementação

**Não implemente código diretamente** — use as skills disponíveis:

| Situação | Skill |
|---|---|
| Bug fix, feature pontual, refactor, qualquer mudança ad-hoc | `/bmad-quick-dev` |
| Implementar uma story específica do backlog | `/bmad-dev-story {story-file}` |
| Implementar um epic completo (stories sequenciais) | `/bagual-bmad-implement-quick-epic {N}` |

### Arquivos de memória do projeto

Ao iniciar qualquer trabalho de implementação, carregue:
- `_bmad-output/anti-patterns.md` — padrões de código a evitar
- `_bmad-output/decisions.md` — decisões técnicas de implementação (não desfazer sem contexto)
- `_bmad-output/product-decisions.md` — decisões sobre comportamento do produto (não reverter sem decisão explícita)
- `_bmad-output/notes.md` — conhecimento operacional e insights acumulados em sessões

As skills BMad (`bmad-dev-story`, `bmad-quick-dev`) carregam os quatro arquivos automaticamente via `_bmad/custom/`.

### Auto-memory

Ao aprender algo relevante sobre este projeto durante uma sessão, registre nos arquivos apropriados:
- Padrão problemático (código que deu errado, risco identificado em review) → `_bmad-output/anti-patterns.md`
- Decisão de design ou arquitetura (não desfazer sem contexto) → `_bmad-output/decisions.md`
- Mudança em como o produto se comporta (stakeholder, time, percepção funcional) → `_bmad-output/product-decisions.md`
- Qualquer outra coisa aprendida (comportamento do sistema, gotcha operacional, como partes interagem) → `_bmad-output/notes.md`

### Para novos membros do time

1. Leia `AGENTS.md` para entender o projeto, stack e regras críticas
2. Consulte `_bmad-output/projects-history.md` para ver o que foi implementado
3. Se for trabalhar no pipeline de epics/stories: use `/bmad-sprint-status` para ver o estado atual e próximas stories
