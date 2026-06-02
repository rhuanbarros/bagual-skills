# Decisões Técnicas — NovoEPA Portal de Acessos

> Decisões tomadas DURANTE a implementação que não estavam na arquitetura original.
> **Carregado obrigatoriamente pelas skills de desenvolvimento** — não desfaça estas escolhas sem entender o contexto.
> Ao tomar uma decisão significativa durante uma story, registre aqui.
>
> Formato: `## [TAG] Título — YYYY-MM-DD HH:MM` | **Decisão** | **Por quê** | **Impacto** | **Story**

---

## [INFRA] PostgreSQL: porta loopback-only (127.0.0.1:5432) — 2026-04-14 00:00

**Decisão:** `docker-compose.postgres.yml` expõe PostgreSQL em `127.0.0.1:5432` (loopback), não em `0.0.0.0:5432`.
**Por quê:** Segurança — banco acessível apenas localmente. Container nomeado `novoepa-postgres` para coexistir com `trt-aios-postgres` na mesma máquina sem conflito de porta.
**Impacto:** Desenvolvedores precisam rodar os serviços localmente (não de dentro de outros containers via hostname). Se comunicação cross-compose for necessária no futuro, precisará de named network explícita.
**Story:** 1-1-postgresql-pgvector-docker

---

## [BACKEND] AiDbContext: branch InMemory com conversão Vector↔CSV string — 2026-04-14 00:00

**Decisão:** `AiDbContext.OnModelCreating` detecta `Database.ProviderName` e aplica conversão `Vector → string (CSV)` para o provider InMemory.
**Por quê:** InMemory provider do EF Core não suporta o tipo `Vector` do pgvector. Testes unitários precisam de InMemory sem dependência de PostgreSQL real.
**Impacto:** Testes que usam InMemory recebem embeddings como strings CSV — conversão é automática. Nunca use assertions sobre o valor bruto do campo Vector em testes InMemory.
**Cuidado:** `Database.ProviderName` é avaliado em `OnModelCreating` que é cacheado por EF Core. Em testes que registram o mesmo context com providers diferentes no mesmo processo, o cache pode não refletir o provider atual.
**Story:** 1-2-aidbcontext-dual-database

---

## [BACKEND] FakeSignInManager: habilitado via USE_FAKE_AUTH=true com guard de produção obrigatório — 2026-04-14 00:00

**Decisão:** `FakeSignInManager` substitui AD auth apenas quando `USE_FAKE_AUTH=true` em `appsettings.Development.json`. Guard em produção: lança `InvalidOperationException` se ativado fora de Development.
**Por quê:** Desenvolvedores não têm acesso ao AD do TRT no ambiente local. Guard de produção é crítico — sem ele qualquer deploy com a flag ativa bypassaria autenticação.
**Impacto:** Nunca remova o guard de produção. Nunca comite `USE_FAKE_AUTH=true` em `appsettings.json` (só em `appsettings.Development.json`).
**Story:** 1-3-fake-auth-dev-e-testes

---

## [ARCH] KnowledgeService: DI direto ao Python AI service, não via proxy HttpClient "Api" — 2026-04-14 00:00

**Decisão:** `KnowledgeSearchPage` e `ChatPage` injetam `IKnowledgeSearchService` e `IChatService` diretamente (via DI no projeto Web), que chamam o Python AI service. A spec original descrevia uma chamada via `HttpClient "Api"` (Web → .NET API → Python AI).
**Por quê:** Evita proxy duplo desnecessário (Web → API → AI). Mais correto arquiteturalmente — Web já é um cliente do AI service. O correct-course de 2026-04-15 documentou esta decisão formalmente.
**Impacto:** O endpoint `.NET API` (`GET /api/knowledge/search`) existe mas não é usado pelo Blazor Web — é para clients externos. A spec dos stories 2-2 e 2-3 está desatualizada neste ponto.
**Stories:** 2-2-knowledge-search-service-e-controller, 2-3-pagina-blazor-pesquisa-knowledge-base

---

## [BACKEND] AiDbContext: colunas snake_case com HasColumnName() explícito — 2026-05-25 00:00

**Decisão:** Todas as propriedades das entidades AI (`KnowledgeDocument`, `KnowledgeChunk`, `Conversation`, `Message`) têm `HasColumnName()` explícito com snake_case no mapeamento EF Core.
**Por quê:** O Python CLI (`ingest_test_docs.py`) e o trt-aios-ai criaram tabelas com snake_case. EF Core por padrão usa PascalCase para nomes de colunas → incompatibilidade de schema. `HasColumnName()` explícito garante consistência independente de convenções do provider.
**Impacto:** Sempre adicione `HasColumnName()` ao mapear novas propriedades nas entidades AI. Migrations serão recriadas se isso for omitido.
**Story:** 2-4-verificacao-e2e-pesquisa-documento-real

---

## [FRONTEND] MessageDto.Sources: List<ChatSource>? (não string JSON raw) — 2026-05-25 00:00

**Decisão:** `MessageDto.Sources` é `List<ChatSource>?` em NovoEPA (tipo forte), não `string? JSON raw` como no trt-aios-webapp original.
**Por quê:** NovoEPA configurou `jsonb` para a coluna `Sources` no EF Core + desserialização direta — não precisa de `ParseSources()` manual. Simplifica o código do ChatPage.
**Impacto:** Se portar código do trt-aios-webapp que chama `ParseSources()` ou trata Sources como string, remova esse código — em NovoEPA o DTO já vem deserializado.
**Story:** 3-3-pagina-blazor-chat

---

## [TEST] E2E: graceful skip quando stack não está rodando — 2026-05-25 00:00

**Decisão:** Testes E2E verificam `IsAppRunningAsync()` antes de executar e retornam skip implícito (sem Assert.Skip — xUnit v2 não tem) usando `return` precoce.
**Por quê:** xUnit v2 não tem `Assert.Skip()` nativo. Testes E2E não devem falhar em ambientes sem o stack completo (CI de build, máquinas sem Docker). O skip gracioso mantém o build verde e a cobertura condicional.
**Impacto:** Testes E2E sempre passam "graciosamente" em CI de build. Para validação E2E real, rodar localmente com o stack completo: `dev.ps1 start` + trt-aios-ai + `dotnet run` API + Web.
**Stories:** 2-4-verificacao-e2e-pesquisa-documento-real, 4-4-e2e-fluxos-funcionais-console-log-monitoring

---

## [TEST] Testes Malote, PJe e Efetivação: NÃO executar — 2026-04-14 00:00

**Decisão:** Excluir da execução os testes das features Malote Digital, PJe e Efetivação.
**Por quê:** São features pré-existentes não relacionadas à migração AI. Possuem ~12 falhas conhecidas que interagem com sistemas externos (produção/staging). Executar esses testes introduz ruído e pode causar efeitos em sistemas reais.
**Como excluir:** Use `--filter "FullyQualifiedName!~Malote&FullyQualifiedName!~PJe&FullyQualifiedName!~Efetivacao"` ou filtre por categoria.
**Permanente:** Esta decisão é permanente enquanto as features legadas não forem migradas para o novo sistema.
**Story:** N/A — decisão de escopo do projeto
