# Anti-Patterns — NovoEPA Portal de Acessos

> Padrões problemáticos identificados em code reviews deste projeto.
> **Carregado obrigatoriamente pelas skills de desenvolvimento** — leia antes de implementar.
> Ao encontrar um novo padrão recorrente, adicione aqui.
>
> Formato: `## [TAG] Título — YYYY-MM-DD HH:MM` | **Problema** | **Risco** | **Como evitar** | **Onde apareceu**

---

## [TEST] Static shared state em test fakes — 2026-05-25 00:00

**Problema:** `FakeAiChatHandler` e `FakeAiServiceHandler` usam campos `static` (`NextResponse`, `SimulateError`, `InvokeCallCount`, `NextKnowledgeResponse`, `SearchCallCount`) compartilhados entre todos os testes no mesmo processo.
**Risco:** xUnit executa classes de teste sequencialmente por padrão — ok hoje. Se paralelismo a nível de classe for habilitado, haverá interferência entre testes. O `finally { Reset(); }` mitiga mas não elimina o risco em cenários de timeout ou exception.
**Como evitar:** Prefira instance-based fakes com DI per-test. Se precisar de shared state, use `[Collection]` para forçar serialização.
**Stories onde apareceu:** 4-1 (origem), 4-2 (reincidência)
**Arquivos:** `FakeAiChatHandler.cs`, `FakeAiServiceHandler.cs`

---

## [E2E] Playwright: WaitForTimeoutAsync como guard de estabilidade — 2026-05-25 00:00

**Problema:** `WaitForSearchToSettleAsync` usa `WaitForTimeoutAsync(250)` antes do `WaitForFunctionAsync`.
**Risco:** Hardcoded sleep adiciona latência sem garantia real de estabilidade. Pode ser insuficiente em máquinas lentas ou CI.
**Como evitar:** Use `WaitForFunctionAsync` diretamente com uma condição determinística. Substitua timeouts por sinais observáveis (botão re-habilitado, atributo `data-state`, ausência de spinner).
**Story onde apareceu:** 2-4
**Arquivo:** `KnowledgeSearchPage.cs:124`

---

## [FRONTEND] JSInterop eval para scroll suave — risco CSP — 2026-05-25 00:00

**Problema:** `ChatPage` usa `JS eval` via JSInterop para scroll suave.
**Risco:** Bloqueado por CSP que não inclua `unsafe-eval` em `script-src`. Failure capturada em Warning — sem crash, mas scroll não funciona.
**Como evitar:** Funções JS dedicadas em `wwwroot/js/` (ex: `chat-scroll.js`) chamadas via referência de função, não eval.
**Story onde apareceu:** 3-3
**Arquivo:** `ChatPage.razor.cs:242`

---

## [FRONTEND] Blazor: dead guard code `if (service is null) return` em código-behind — 2026-04-14 00:00

**Problema:** Guards `if (Http is null) return` e `if (KnowledgeService is null) return` dentro de `SearchAsync` são dead code — `OnInitializedAsync` já lança `InvalidOperationException` antes do render se os serviços forem nulos.
**Risco:** Zero funcional, mas polui o código e pode enganar futuros devs sobre o real caminho de falha.
**Como evitar:** Confie no DI — se o serviço é required, não adicione guards redundantes no método. Reserve guards para cenários onde o serviço é realmente opcional.
**Story onde apareceu:** 2-3
**Arquivo:** `KnowledgeSearchPage.razor.cs:74-75`

---

## [ARCH] Tipos EF Core / pgvector na camada Shared — 2026-04-14 00:00

**Problema:** `KnowledgeChunk.cs` usa `Vector` (pgvector) e `NpgsqlTsVector` diretamente em `PortalAcessos.Shared`, violando isolamento de camadas (Shared deveria ser DTOs/contratos puros).
**Risco:** Shared passa a depender de `Npgsql` e `Pgvector` — qualquer projeto que referencia Shared carrega essas dependências pesadas.
**Como evitar:** Entidades EF Core com tipos de banco devem ficar em `PortalAcessos.Services` ou em uma camada `PortalAcessos.Domain` dedicada. Shared deve conter apenas tipos neutros.
**Story onde apareceu:** 2-1 (origem), 2-2 (identificado formalmente)
**Arquivo:** `PortalAcessos.Shared/PortalAcessos.Shared.csproj`

---

## [BACKEND] EF Core: entidade sem HasDefaultValueSql para campos obrigatórios com default de negócio — 2026-05-25 00:00

**Problema:** `Conversation.Title` tem default C# `"Nova conversa"` na entidade mas sem `HasDefaultValue("Nova conversa")` no mapeamento EF Core → banco não tem `DDL DEFAULT` para a coluna.
**Risco:** Se inserção vier do Python sem informar o título, gera erro de banco (NOT NULL sem valor). Application code precisa sempre definir o campo.
**Como evitar:** Para campos com default de negócio: defina `HasDefaultValue()` ou `HasDefaultValueSql()` no `OnModelCreating` além do default C# na entidade.
**Story onde apareceu:** 3-1
**Arquivo:** `AiDbContext.cs:113`

---

## [BACKEND] KnowledgeSearchService: leitura de config no construtor vs em tempo de chamada — 2026-04-14 00:00

**Problema:** `_apiKey` é lido no construtor. Dev Notes intencionavam "at call time" para suportar atualizações de config em runtime.
**Risco:** Funcional para serviço Scoped (fresh por request). Tornaria-se bug se o lifetime mudar para Singleton.
**Como evitar:** Se config pode mudar em runtime e o serviço pode ser Singleton no futuro, use `IOptionsMonitor<T>` (leitura dinâmica) em vez de ler no construtor.
**Story onde apareceu:** 2-2
**Arquivo:** `KnowledgeSearchService.cs:26`

---

## [TEST] FakeAiServiceHandler retornando JSON incompatível com o DTO esperado — 2026-04-14 00:00

**Problema:** `FakeAiServiceHandler` estava retornando `{"results": []}` mas o desserializador esperava `[]` diretamente.
**Como evitar:** Ao criar um fake handler, sempre verifique o formato exato que o `HttpClient` deserializa — use o mesmo DTO do código de produção como referência.
**Story onde apareceu:** 2-2
**Arquivo:** `FakeAiServiceHandler.cs`
