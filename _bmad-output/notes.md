# Notes — NovoEPA Portal de Acessos

> Conhecimento acumulado durante sessões que não se encaixa em anti-patterns (problemas de código) nem em decisions (decisões de design/arquitetura).
> **Carregado obrigatoriamente pelas skills de desenvolvimento** — leia como contexto adicional.
> Ao aprender algo relevante em sessão (comportamento do sistema, gotchas operacionais, constraints de ambiente), registre aqui.
>
> Formato: `## [TAG] Título — YYYY-MM-DD HH:MM` | **Nota** | **Impacto** | **Como** (quando aplicável)

---

## [DEP] Python AI service — repositório separado — 2026-05-26 00:00

**Nota:** O `trt-aios-ai` (FastAPI) **não** faz parte deste repositório. Fica em `C:\projetos_gilab\trt-aios\trt-aios-ai\`.
**Impacto:** Para rodar o stack completo localmente, é preciso ter ambos os repositórios clonados. Testes E2E e integração com Knowledge/Chat dependem do serviço Python rodando.
**Como iniciar:** `cd C:\projetos_gilab\trt-aios\trt-aios-ai\ai && uv run uvicorn main:app --reload`

---

## [ENV] Ordem de inicialização do stack local — 2026-05-26 00:00

**Nota:** O stack local precisa ser iniciado nesta ordem para evitar falhas de conexão:
1. PostgreSQL: `.\dev.ps1 start` (na raiz do projeto)
2. .NET API: `cd PortalAcessos.Api && dotnet run`
3. .NET Web Blazor: `cd PortalAcessos.Web && dotnet run`
4. Python AI service: `cd ..\trt-aios\trt-aios-ai\ai && uv run uvicorn main:app --reload`

**Por quê:** A API .NET registra health checks que dependem do PostgreSQL na inicialização. O Web Blazor depende da API. O Python AI pode ser iniciado em qualquer ordem, mas os testes E2E precisam dos 4 serviços ativos.

---

## [SYNC] sync_chamados.py: build_splitter patch target é ai.ingest.build_splitter — 2026-05-28

**Nota:** `build_splitter` é importado dentro de `run_sync_chamados` via `from ai.ingest import build_splitter`. Para mockar em testes, o target correto é `ai.ingest.build_splitter`, não `ai.sync_chamados.build_splitter`.
**Impacto:** Testes que mockam o splitter devem usar `patch("ai.ingest.build_splitter")`.
**Como:** Padrão de importação lazy (import inside function) exige patch no módulo de origem, não no módulo consumidor.

---

## [ENV] Playwright E2E só roda em Linux — 2026-05-27 22:00

**Nota:** O `PortalAcessos.Tests.csproj` tem `<PlaywrightPlatform>linux-x64</PlaywrightPlatform>`. No Windows, o driver node.exe de `win32_x64` fica vazio e todos os 10+ testes Playwright falham com `PlaywrightException: Driver not found`.
**Impacto:** Pipeline de testes no Windows só valida unit/integration (161 testes). E2E via Playwright requer CI Linux.
**Como:** No pipeline CI (GitLab), o runner já é Linux — os testes E2E rodam normalmente lá. Para dev local em Windows, filtrar E2E: `dotnet test --filter "Category!=E2E"`.
