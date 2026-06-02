# Projects History — NovoEPA Portal de Acessos

> Timeline de stories concluídas: o quê foi feito, quando e por quê.
> Para detalhes técnicos, decisões e anti-patterns consulte `decisions.md` e `anti-patterns.md`.

---

## 2026-04-14 — 1-1-postgresql-pgvector-docker
**O que:** Docker setup pgvector/pg16; container `novoepa-postgres`; porta loopback; init SQL com extensões vector/pg_trgm/unaccent
**Por que:** Epic 1 — fundação local dev; qualquer dev precisa rodar PostgreSQL+pgvector localmente para o portal AI

## 2026-04-14 — 1-2-aidbcontext-dual-database
**O que:** `AiDbContext` + 4 entidades AI (KnowledgeDocument, KnowledgeChunk, Conversation, Message); dual-database pattern ao lado do AppDbContext SQL Server
**Por que:** Epic 1 — PostgreSQL AI coexistindo com SQL Server existente sem modificar infraestrutura legada

## 2026-04-14 — 1-3-fake-auth-dev-e-testes
**O que:** `FakeSignInManager` (USE_FAKE_AUTH=true), `TestAuthHandler`, `FakeAiServiceHandler`, `ApiAppFixture` (WebApplicationFactory + InMemory)
**Por que:** Epic 1 — desenvolver sem AD e testar sem serviços externos reais

## 2026-04-14 — 1-4-script-dev-local-e-bmad-config
**O que:** `dev.ps1` com ações start/stop/status para o container PostgreSQL; instruções numeradas para rodar o stack completo
**Por que:** Epic 1 — onboarding de devs: um comando para subir o ambiente local

## 2026-04-14 — 2-1-entidades-migrations-knowledge-base
**O que:** Migration `AddKnowledgeBaseSchema` com tabelas knowledge_documents/knowledge_chunks, índice HNSW, índice GIN FTS português, trigger tsvector
**Por que:** Epic 2 — persistência para busca semântica e por palavras-chave no Knowledge Base

## 2026-04-14 — 2-2-knowledge-search-service-e-controller
**O que:** `KnowledgeSearchService`, `KnowledgeController`, DTOs, `KnowledgeServiceUnavailableException`; portados do trt-aios com namespaces NovoEPA
**Por que:** Epic 2 — backend de busca no Knowledge Base expondo endpoints autenticados

## 2026-04-14 — 2-3-pagina-blazor-pesquisa-knowledge-base
**O que:** `KnowledgeSearchPage.razor/.cs` com campo de busca, toggle semântica/keywords/híbrida, drawer de visualização; MudNavLink no MainLayout
**Por que:** Epic 2 — UI de pesquisa de documentos para funcionários do TRT

## 2026-05-25 — 2-4-verificacao-e2e-pesquisa-documento-real
**O que:** Infraestrutura Playwright portada; doc de teste ingerido; 3 smoke tests com graceful skip; fix `HasColumnName()` snake_case no AiDbContext
**Por que:** Epic 2 — validação ponta-a-ponta do fluxo de busca com dado real no PostgreSQL

## 2026-05-25 — 3-3-pagina-blazor-chat
**O que:** `ChatPage.razor/.cs` portado com sidebar 280px, optimistic UI, chip Fontes(N), scroll JS, MudDrawer para documentos; `Rotas.chat` adicionado
**Por que:** Epic 3 — UI de chat com o assistente AI (RAG) para funcionários do TRT

## 2026-05-25 — 4-4-e2e-fluxos-funcionais-console-log-monitoring
**O que:** `ChatSmokeTest.cs` (4 testes), `ChatPage.cs` (POM), `ServerLogMonitor.cs` stub, warm-up AI, truncagem de tabelas via docker exec psql
**Por que:** Epic 4 — cobertura E2E dos fluxos funcionais de chat com captura de console errors

## 2026-05-25 — 4-5-suite-visual-analise-ia-e-correcoes
**O que:** `VisualTestSuite.cs`, `Scripts/analyze-screenshots.py` (Claude Haiku), `Scripts/visual-correction-loop.ps1`
**Por que:** Epic 4 — validação visual automatizada das páginas Knowledge Search e Chat via Vision AI

## 2026-05-27 — 5-3-endpoint-fastapi-sync-qualitor
**O que:** `api/routers/admin.py` com `POST /v1/admin/sync/qualitor`; `api/schemas/admin.py` com `KnowledgeSyncResult`; router registrado em `main.py`; `asyncio.Lock()` módulo-singleton para controle de concorrência; 7 testes unitários cobrindo HTTP 200/409/500/503 e liberação do lock
**Por que:** Epic 5 — endpoint FastAPI que aciona a sincronização Qualitor (via `run_sync()` da story 5-2) e retorna contadores; permite que o .NET API acione o pipeline sem executar scripts diretamente

## 2026-05-27 — 6-1-endpoint-dotnet-sync-qualitor
**O que:** `KnowledgeSyncResultDto` em Shared; `KnowledgeAdminService` + `SyncAlreadyRunningException` em Services; `KnowledgeAdminController` com `[Authorize(Roles = "administradores")]` em Api; named HttpClient "trt-aios-ai" (20min timeout) registrado; 7 testes unitários cobrindo HTTP 200/409/5xx/timeout/connection refused
**Por que:** Epic 6 — endpoint .NET seguro `POST /api/admin/knowledge/sync-qualitor` que delega ao FastAPI com autenticação de role administradores, HTTP 502 para AI indisponível, HTTP 409 repassado para sync já em andamento

## 2026-05-27 — 6-2-pagina-blazor-admin-sync-qualitor
**O que:** `KnowledgeAdminPage.razor/.cs` em `Views/Admin/` com rota `/admin/knowledge`; botão "Sincronizar com Qualitor" com spinner e estado desabilitado durante sync; exibição de contadores (Inseridos/Atualizados/Sem alteração/Erros); mensagens de erro amigáveis para 409 e falha genérica; `ScopedServiceProvider<KnowledgeAdminService>` para DI; `AuthHelper.EnsureAnyRoleAsync` para guard de role administradores; named HttpClient "trt-aios-ai" e `KnowledgeAdminService` registrados no Web Program.cs; `Rotas.admin_knowledge` adicionado; nav link "Knowledge Base — Sync" no grupo Configurações do MainLayout; `KnowledgeAdminPage.cs` (POM) e `KnowledgeAdminSyncTests.cs` (3 testes E2E Playwright: page load, sync completa, AI indisponível)
**Por que:** Epic 6 — UI administrativa para que admins do portal acionem a sync Qualitor manualmente e visualizem os resultados imediatamente, com feedback de loading e tratamento de erros amigável

## 2026-05-28 — 7-1-schema-postgresql-sync-python-indexacao-chamados
**O que:** Entidades EF Core `TicketRecord` + `TicketChunk` com migration `AddTicketMirrorTables` (índices HNSW cosine m=16, GIN tsvector português, FK ON DELETE CASCADE); módulo Python `sync_chamados.py` com loop sobre 26 equipes TI, hash SHA-256 para deduplicação, geração de 4 tipos de chunk (problem/solution/followup/combined), rate limiting e retry com backoff; 27 testes unitários cobrindo todos os ACs
**Por que:** Epic 7 — fundação do mirror de chamados: schema PostgreSQL e pipeline de sync idempotente necessários para todas as outras stories do epic

## 2026-05-28 — 7-2-endpoints-dotnet-admin-sync-chamados
**O que:** FastAPI `POST /v1/admin/sync/qualitor-tickets` + `GET /v1/admin/sync/qualitor-tickets/status` com asyncio.Lock singleton; DTOs .NET `TicketSyncResultDto`/`TicketSyncStatusDto`; `TicketSyncService`; `TicketAdminController` com `[Authorize(Roles="administradores")]`; `TicketSyncJob` Quartz.NET com cron `0 0 2 * * ?` configurável via `TicketSync:CronExpression`; 8 testes .NET + 6 testes Python
**Por que:** Epic 7 — endpoints de administração para disparar sync manual e monitorar status, mais job cron para sync automática diária de chamados

## 2026-05-28 — 7-3-endpoint-busca-chamados-python-proxy-dotnet
**O que:** FastAPI `POST /v1/tickets/search` com busca híbrida RRF(HNSW cosine semântico + FTS tsvector português) sobre `ticket_chunks`/`ticket_records`; filtros pré-busca para `team_name`, `status`, `full_category` (ILIKE), `chunk_source`; top_k clamp max 50; snippet truncado em 300 chars; prefixo `"query: "` no embedding; schemas Pydantic `TicketSearchRequest`/`TicketSearchFilters`/`TicketSearchResult`; proxy .NET `KnowledgeTicketsController` `POST /api/knowledge/tickets/search` com `[Authorize]` e HTTP 502 para falha do Python; `TicketSearchService` com mapeamento snake_case↔PascalCase; DTOs `TicketSearchRequestDto`/`TicketSearchResultDto`/`TicketSearchFiltersDto`; 29 testes Python + 10 testes .NET (189 total passando)
**Por que:** Epic 7 — endpoint de busca semântica de chamados que permite ao Blazor e clientes externos consultar o acervo indexado via query em linguagem natural com filtragem por equipe/status/categoria/tipo de chunk

## 2026-05-28 — 7-4-interface-unificada-busca-kb-chamados
**O que:** Python `POST /v1/unified/search` com two-stage RRF (Stage 1: RRF interno por fonte; Stage 2: `1/(60+rank)` cross-source sem normalização); `UnifiedSearchService` .NET injetado direto no Web; redesign de `KnowledgeSearchPage.razor` com seletor de fonte (3 botões HTML), painel de facets contextual server-side, badges CSS `.badge-kb`/`.badge-chamado`, source persistido via `?source=` URL param; 5 testes E2E Playwright; 179 testes unitários passando
**Por que:** Epic 7 — interface unificada que permite buscar em KB, Chamados ou ambos com facets contextuais e resultados misturados ranqueados por relevância

## 2026-05-28 — 7-5-pagina-detalhe-chamado
**O que:** `TicketDetailDto` (13 campos); `TicketDetailPage.razor/.cs` na rota `/chamados/{TicketId:guid}` com auth guard EnsureAnyRoleAsync, ScopedServiceProvider DI, seção Solução condicional, datas dd/MM/yyyy HH:mm, 404 amigável; `TicketSearchService.GetByIdAsync` lendo AiDbContext diretamente; `GET /api/knowledge/tickets/{id:guid}` no KnowledgeTicketsController; 7 testes unitários + 186 total passando
**Por que:** Epic 7 — página de detalhe que mostra problema e solução consolidada de um chamado indexado, acessível via clique nos resultados de busca

## 2026-05-28 — 7-6-secao-admin-sync-chamados-painel
**O que:** `TicketAdminPage.razor/.cs` em `/admin/tickets` análogo a `KnowledgeAdminPage`; botão "Sincronizar Agora" com spinner HTML, polling de status a cada 5s, contadores (Inseridos/Atualizados/Sem mudança/Erros/Duração), lista de erros detalhada; mensagens amigáveis 409/502; `Rotas.admin_tickets`; nav link "Chamados Qualitor" no grupo Configurações; 3 testes E2E Playwright; 186 testes passando
**Por que:** Epic 7 — painel admin para administradores do portal acionarem e monitorarem a sync de chamados sem ferramentas externas
