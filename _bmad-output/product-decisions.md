# Decisões de Produto — NovoEPA Portal de Acessos

> Decisões sobre **como o produto deve se comportar** — vindas de stakeholders, chefia, ou do time ao perceber que uma funcionalidade funciona melhor de outra forma.
> **Carregado obrigatoriamente pelas skills de desenvolvimento** — não reverta comportamentos documentados aqui sem decisão explícita.
> Ao mudar como uma feature funciona (por qualquer motivo), registre aqui.
>
> Formato: `## [TAG] Título — YYYY-MM-DD HH:MM` | **Comportamento** | **Motivação** | **Origem** | **Desde** | **Cuidado**

---

## [ESCOPO] Features Malote Digital, PJe e Efetivação estão fora do escopo desta migração — 2026-04-14 00:00

**Comportamento:** O Portal de Acessos não migra nem mantém as features Malote Digital, PJe e Efetivação. Essas features existem no código legado mas não são parte do produto que está sendo construído aqui.
**Motivação:** O escopo desta migração é exclusivamente as features de AI (Knowledge Base + Chat RAG) do trt-aios para o portal-acessos. As demais features têm suas próprias equipes e roadmap.
**Origem:** Definição de escopo do projeto de migração.
**Desde:** Início do projeto (Epic 1)
**Cuidado:** Não implementar novas funcionalidades para Malote/PJe/Efetivação neste repositório. Os ~12 testes dessas features falham intencionalmente (dependências externas) — não tentar corrigir.

---

## [CHAMADOS-MIRROR] Entradas privadas do histórico de chamados não são indexadas — 2026-05-28

**Comportamento:** Ao indexar o histórico de acompanhamentos de chamados Qualitor para busca semântica, entradas com `idprivado=Y` são ignoradas e não entram em nenhum chunk de embedding.
**Motivação:** Entradas privadas são anotações internas dos atendentes (diagnósticos, contatos de telefone, informações pessoais), não destinadas a ser expostas em buscas. Indexá-las criaria risco de vazar informações que o atendente marcou como restritas.
**Origem:** Decisão do time em 2026-05-28 durante análise da API do Qualitor.
**Desde:** Planejamento do epic de mirror de chamados (antes da implementação).
**Cuidado:** Mesmo que a entrada privada contenha a solução técnica, ela não é indexada. Se isso gerar perda de recall relevante no futuro, revisar com o time antes de mudar.

---

## [KNOWLEDGE] Busca na Knowledge Base retorna resultados do Python AI service diretamente — 2026-04-14 00:00

**Comportamento:** A página de pesquisa da Knowledge Base envia queries diretamente ao Python AI service (trt-aios-ai) via `IKnowledgeSearchService`. Não há camada intermediária via .NET API entre o Blazor Web e o Python.
**Motivação:** Evitar proxy duplo desnecessário (Web → .NET API → Python AI). O resultado é mais direto e arquiteturalmente mais correto — Web é cliente do AI service.
**Origem:** Decisão do time durante implementação (story 2-3), após perceber que a spec original descrevia um proxy desnecessário.
**Desde:** 2026-04-15, story 2-3-pagina-blazor-pesquisa-knowledge-base
**Cuidado:** Não adicionar endpoint no .NET API como proxy para as chamadas de Knowledge/Chat do Blazor Web. O endpoint `.NET API GET /api/knowledge/search` existe mas é para clients externos, não para o Web Blazor.
