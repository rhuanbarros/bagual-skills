#!/usr/bin/env python3
"""e12_3_migrate_antipatterns.py -- E12.3 one-off migration: anti-patterns.md
(92 `## H2`) -> Ledger `anti-pattern` entries (MADR + selo de maturidade).

Story E12.3 (ideias/sistema-artifacts/E12-3-antipatterns-madr.md), PRD 01 §6.3
(plano de migração) + FR-8 (selo), ideias/epics-onda-5.md Epic E12.

NON-DESTRUTIVO: nunca escreve em `_bmad-output/anti-patterns.md` (só leitura).
Escreve documentos NOVOS em `wiki/ledger/anti-pattern/`, mais um
manifesto DEDICADO (`slice-manifest-anti-patterns.json`, não o
`slice-manifest.json` genérico nem os manifestos de E12.2/E12.4 -- para não
colidir na mesma raiz do Ledger) consumido por
`../../scripts/slice_completeness_gate.py` (E3.5, reusado SEM modificação).

Reusa `extract_h2_sections()`/`find_source_duplicates()`/`segment_body()` de
`e12_2_migrate_decisions.py` (E12.2) -- mesmo parser H2-aware-de-fences e
mesma técnica de segmentação por linha-em-branco + início de rótulo bold.

## A mesma tensão transformação-vs-gate de E12.2, resolvida da MESMA forma
(ver `ideias/sistema-artifacts/E12-2-decisions-madr.md` Dev Notes para a
análise completa de `check_textual()`; não repetida aqui em detalhe): o corpo
ORIGINAL de cada seção é embutido VERBATIM, ÍNTEGRO, dentro de `## Contexto`
(rotulado "Texto original (verbatim, íntegro)") -- o gate compara token-a-
token via `difflib.SequenceMatcher`, então esse bloco garante PASS por
construção, independente de quanta estrutura MADR adicional exista ao redor.

## Gramática MADR para `anti-pattern` (extensão sobre `decisão-*`)
`anti-patterns.md` usa rótulos bold `**Problema:**`/`**Risco:**`/
`**Como evitar:**`/`**Onde apareceu:**` (não `**Decisão:**`/`**Impacto:**`
como em `decisions.md`). Mapeamento usado por este script:
  - `## Contexto`      <- bloco verbatim íntegro (garantia de completude) +
                          framing; inclui o `**Problema:**` original dentro
                          do próprio verbatim (não duplicado à parte).
  - `## Decisão`       <- `**Como evitar:**` (a regra/prática a seguir).
  - `## Alternativas
     consideradas e
     rejeitadas`       <- anti-patterns.md normalmente não documenta
                          alternativas rejeitadas explicitamente; fallback
                          honesto apontando para `## Contexto`, a menos que
                          um parágrafo mencione "alternativa"/"rejeitad[a/o]".
  - `## Consequências`  <- `**Risco:**` (o dano concreto do anti-pattern).
  - `## Selo de
     maturidade`        <- 🟢/🟡/🔴 (E4.4) + racional curatorial explícito
                          (recorrência/severidade/decidibilidade mecânica do
                          texto original) -- NUNCA 🟡 por omissão; ver
                          CLASSIFICATION abaixo, um racional por entrada.
  - `## Contador de
     utilidade`         <- `0` -- entrada nova, `candidata`, sem enforcement
                          mecânico instrumentado ainda (mesmo padrão de
                          E4.1/E4.4 e da migração-irmã E12.2).

Front-matter: `estado: candidata`, `causa-da-morte: null`,
`contador-de-utilidade: 0`, `selo: <🟢|🟡|🔴>`, `automatizado: false` (nenhuma
regra Semgrep foi autorada por esta migração -- decidir isso é escopo do PRD
04/Epic E7, não desta story), `areas: [...]` (julgamento curatorial), nunca
`reverte`/lifecycle retroativo (decidir `aposentada`/`redundante com
ferramenta nativa` é trabalho de curadoria futura, fora do escopo mecânico
desta migração -- mesma disciplina de E12.2 Decisão 8/Dev Notes "fora de
escopo").

Uso (script standalone, não parametrizado por monólito -- a classificação
CLASSIFICATION abaixo é curatorial e específica das 92 seções reais de
`anti-patterns.md` no momento em que esta story rodou):

    python3 e12_3_migrate_antipatterns.py

Idempotente-com-força: rodar de novo detecta slugs já usados (inclusive os
desta própria execução anterior) e não sobrescreve nada -- aplica sufixo
numérico (`-2`, `-3`...) em qualquer colisão, nunca `overwrite` (mesma regra
de `on-complete-contract.md` §3.5 e de `e12_2_migrate_decisions.py`).

Só biblioteca padrão (stdlib) -- nenhuma dependência externa.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "wiki/scripts"))
from slice_completeness_gate import extract_h2_sections, find_source_duplicates  # noqa: E402

MONOLITH = REPO / "_bmad-output/anti-patterns.md"
LEDGER_ROOT = REPO / "wiki/ledger"
FOLDER = "anti-pattern"
TODAY = "2026-07-12"

DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
LABEL_LINE_RE = re.compile(r"^\*\*[^*\n]+?:\*\*")


def slugify(title: str) -> str:
    normalized = unicodedata.normalize("NFKD", title)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_only.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    if not slug:
        slug = "secao"
    return slug[:80].rstrip("-")


def yaml_list(items: list[str]) -> str:
    return "[" + ", ".join(items) + "]"


def segment_body(body: str) -> list[str]:
    """Idêntico a `e12_2_migrate_decisions.py::segment_body()` -- reusado por
    cópia (não import) porque este script é standalone por design (mesma
    convenção documentada em `e12_2_migrate_decisions.py`, "não importar este
    arquivo como biblioteca genérica"). Segmenta por linha-em-branco E por
    início de rótulo `**Rótulo:**` na mesma linha de continuação."""
    blocks: list[str] = []
    current: list[str] = []
    for line in body.splitlines():
        if not line.strip():
            if current:
                blocks.append("\n".join(current).strip())
                current = []
            continue
        if LABEL_LINE_RE.match(line) and current:
            blocks.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)
    if current:
        blocks.append("\n".join(current).strip())
    return [b for b in blocks if b]


def extract_created(title: str, body: str) -> str:
    m = DATE_RE.findall(title)
    if m:
        return m[0]
    m = DATE_RE.findall(body)
    if m:
        return m[0]
    return TODAY


EVITAR_PREFIXES = ("**Como evitar", "**Como corrigir")
RISCO_PREFIXES = ("**Risco",)
ALT_KEYWORDS = ("rejeitad", "alternativa consider", "em vez de alternativa")


def collect(paras: list[str], prefixes: tuple[str, ...]) -> list[str]:
    return [p for p in paras if p.startswith(prefixes)]


def collect_alt(paras: list[str]) -> list[str]:
    out = []
    for p in paras:
        low = p.lower()
        if any(k in low for k in ALT_KEYWORDS):
            out.append(p)
    return out


# ---------------------------------------------------------------------------
# Classificação curatorial (título -> areas, selo, racional) por ÍNDICE
# (0-based, mesma ordem de extract_h2_sections -- nunca por re-digitar o
# título, mesma disciplina de e12_2_migrate_decisions.py). Selo NUNCA
# omitido/default -- cada linha carrega seu próprio racional de
# recorrência/severidade/decidibilidade mecânica lido do texto original.
# ---------------------------------------------------------------------------
CLASSIFICATION: list[tuple[list[str], str, str]] = [
    (["sistema-meta"], "🟡",
     "Exige entender estrutura semântica de markdown (rótulo bold vs. limite de parágrafo), não é puramente sintático — mesma classe da técnica irmã (#2)."),
    (["sistema-meta"], "🟡",
     "DUPLICATA CONCEITUAL de entrada pré-existente `ledger/anti-pattern/gerador-de-front-matter-com-comentario-inline-na-linha-de-lista-em-fluxo.md` (emitida via on_complete da Story E12.1) — mesmo racional herdado sem reabrir: condição sintática detectável mas com risco de falso-positivo alto sem contexto semântico (distinguir front-matter real de qualquer outra f-string com `#`/`[...]`)."),
    (["proposals", "frontend"], "🔴",
     "Requer rastrear dependência cross-file de um dado (fallback implícito de uma tela em outra) e julgar se ainda resta caminho de UI — julgamento de arquitetura/produto, não redutível a AST."),
    (["frontend"], "🟡",
     "O padrão (guard `useState` perde eficácia ao remover `await`) é replicável como checagem 'handler síncrono com guard useState', mas confirmar que é de fato um guard de reentrância exige leitura semântica do handler."),
    (["frontend"], "🔴",
     "Julgamento visual de contraste em dark theme — não redutível a AST/regra estática."),
    (["frontend"], "🟡",
     "Reconhecível por grep (formatter que colapsa falsy aplicado a valor já carregado), mas decidir 'já carregado vs. campo vazio de formulário' exige contexto semântico da chamada."),
    (["frontend"], "🟡",
     "Checar só 1 de N campos de erro de um validador multi-campo é grep-ável no padrão do handler, mas requer saber que o validador retorna objeto com múltiplas chaves independentes."),
    (["frontend"], "🟡",
     "Requer correlacionar dois elementos radio do mesmo grupo semântico sem `aria-label` distinto entre si — não é uma checagem de 1 elemento isolado."),
    (["clients", "frontend"], "🟡",
     "Mapeador campo-a-campo é comparável mecanicamente contra o tipo de origem (diff de chaves), mas o achado real também exigiu comparar formulário de criação vs. tela de leitura — parte humana."),
    (["supabase", "backend"], "🟡",
     "`select('*')` é grep-ável, mas saber que a tabela tem column-level GRANTs (em vez de table-level) exige contexto do schema real, não só do código Python/TS."),
    (["frontend"], "🟡",
     "Uso de `location.pathname` para decidir comportamento é grep-ável, mas nem todo uso é anti-pattern (roteamento legítimo existe) — exige julgamento por chamada."),
    (["frontend"], "🟡",
     "Padrão `setTimeout` + `setState` para controlar loading de botão é replicável, mas exige saber que já existe um `isLoading` de hook disponível como alternativa mais simples."),
    (["frontend"], "🟡",
     "Prop opcional nunca recebida via rota lazy-loaded exige correlacionar a definição da rota (router) com o uso do componente — dois arquivos, julgamento semântico."),
    (["frontend"], "🟢",
     "Regra de camada já documentada (pages nunca chamam o cliente Supabase direto) é mecanicamente checável por grep/import de `createClient`/`.channel(` dentro de `pages/`."),
    (["dashboard", "frontend"], "🔴",
     "Bug de dado específico (arrays vazios mascarados por `as any` alimentando um mapper) — julgamento semântico do fluxo de dados entre componentes."),
    (["clients", "frontend"], "🔴",
     "Exige conhecimento de domínio (quais campos são condicionalmente dependentes de qual campo-pai) — não é um padrão sintático genérico."),
    (["clients", "frontend"], "🟡",
     "Mesma classe do #9 (mapper incompleto) — diffável mecanicamente contra o tipo de origem, mas o achado real também exigiu auditar os write paths (create/update), não só o mapper de leitura."),
    (["backend"], "🟡",
     "'Grep por todas as factories que instanciam o Service' é mecânico, mas decidir QUAL dependency injetada é de segurança (vs. incidental) exige julgamento."),
    (["backend", "auth"], "🔴",
     "Segurança de ownership cross-tenant sob service-role/RLS bypass é raciocínio de domínio de segurança, não um padrão AST isolado."),
    (["backend", "proposals"], "🔴",
     "Corretude de concorrência (CAS/lost-update) é semântica de negócio sobre transições de estado, não sintaxe local."),
    (["product"], "🔴",
     "Puro julgamento de produto/nomenclatura de domínio — não é um padrão de código."),
    (["frontend"], "🟢",
     "Fetch dentro de `useEffect` sem `AbortController` é um padrão bem estabelecido e mecanicamente detectável (classe de regra já coberta por linters de React para efeitos assíncronos)."),
    (["frontend"], "🟡",
     "Closure leak em callback de subscription exige entender que a variável é lida após um possível re-render — não é só sintaxe de captura de closure."),
    (["backend", "credits"], "🔴",
     "Guards de transição de estado são regra de negócio específica do domínio (créditos), não AST genérica."),
    (["frontend"], "🟢",
     "Já mecanicamente barrado pela regra ESLint `react-hooks/set-state-in-effect` (citada em `frontend/agents.md`) — violação é detectada no lint, não depende de julgamento humano."),
    (["backend"], "🟢",
     "Já mecanicamente barrado por pyright: `response.data` tipado `JSON | Unknown` sem `cast` explícito falha o type-check (modo `standard`)."),
    (["testing"], "🟢",
     "Uso de `localhost` (resolve IPv6) em vez de `127.0.0.1` em specs/scripts de teste E2E é grep-ável mecanicamente."),
    (["frontend", "testing"], "🟡",
     "`<Skeleton>` condicional dentro de `<h1>` é um padrão JSX específico, plausível de regra Semgrep, mas a condicionalidade (só durante loading) exige leitura de contexto além de casamento de árvore simples."),
    (["infra"], "🔴",
     "Regra operacional ('nunca rodar este comando neste projeto') é julgamento de processo, não um padrão de código estático."),
    (["clients", "frontend"], "🟡",
     "Mesma classe dos mappers incompletos (#9/#17) — diff mecânico possível contra o tipo, mas exige contexto de qual mapper é o 'producer' oficial do campo."),
    (["infra"], "🟡",
     "Padrão SQL (`INSERT INTO storage.buckets` sem `ON CONFLICT`) é grep-ável, mas exige conhecimento de que o schema `storage` sobrevive a `db reset` (contexto de infraestrutura, não só sintaxe SQL)."),
    (["vehicles", "frontend"], "🔴",
     "Julgamento de produto (undo deve restaurar o original, não recriar) cruzado com conhecimento de FK `ON DELETE CASCADE` — não é AST puro."),
    (["backend"], "🟡",
     "Chamada síncrona dentro de `async def` sem `run_in_threadpool` é parcialmente grep-ável, mas identificar 'cliente Supabase síncrono' (vs. outra chamada bloqueante) exige contexto de tipagem."),
    (["backend"], "🟢",
     "Interpolação de input do usuário numa string de filtro (`f\"...{search}...\"` passada a `.or_(`) é um padrão clássico de injection — fonte tainted → sink de query, AST-detectável (classe já coberta por regras genéricas de Semgrep)."),
    (["backend", "auth"], "🟡",
     "Fail-open num campo de segurança (`.get(key, False)`) é replicável mecanicamente para ESSE campo específico, mas exige saber que o campo é security-gating (não qualquer `.get` com default)."),
    (["backend", "auth"], "🟡",
     "Vazamento de `str(e)` no response é grep-ável (`detail=str(e)`), mas 'mascarar falha de infra como 401' exige julgamento semântico sobre a árvore de exceções capturadas."),
    (["frontend", "auth"], "🔴",
     "Interação entre abrir modal e navegar no mesmo ciclo é um bug de composição entre dois componentes — requer entendimento de efeitos, não AST de 1 arquivo."),
    (["frontend", "auth"], "🟡",
     "'Loading que só sai por evento externo' é replicável via padrão (`setLoading` fora de `try/finally`), mas exige seguir o fluxo assíncrono completo até o fim para confirmar."),
    (["backend"], "🟢",
     "`dict.get(key, \"\")` vs. `dict.get(key) or \"\"` é um padrão sintático puro (o default só se aplica a chave ausente, nunca a valor `None`) — plenamente AST-checkable."),
    (["frontend"], "🔴",
     "Reverse-lookup por nome com fallback silencioso para um default é julgamento semântico (saber que É um fallback perigoso vs. um default legítimo), não sintaxe isolada."),
    (["backend"], "🟡",
     "Empty string violando `CHECK` constraint é conhecimento de schema (requer correlacionar a migration SQL com o código Python), não puro AST do lado da aplicação."),
    (["backend"], "🔴",
     "Ordem de validação Pydantic-vs-exceção-de-domínio é raciocínio sobre fluxo de execução entre camadas (agent constrói o model antes do service validar) — não sintaxe local de 1 arquivo."),
    (["backend"], "🟢",
     "`except Exception: return []` mascarando falha de infra como sucesso vazio é um padrão AST clássico, já coberto por classes genéricas de regras Semgrep (broad-except + silent-fallback)."),
    (["testing", "auth"], "🟡",
     "Fixture de teste faltando um campo específico (`is_anonymous: False`) é grep-ável para ESSE caso, mas o diagnóstico (403 mascarando 422 esperado) exige entender a ordem do gate de auth."),
    (["frontend"], "🟡",
     "`String(obj)` sobre um valor potencialmente estruturado é parcialmente grep-ável (`String(errorBody...)`), mas exige saber o tipo real de `detail` no contrato de erro do backend."),
    (["testing"], "🟢",
     "Mutação de `os.environ` sem `patch.dict`/restauração no teardown é um padrão AST bem definido, coberto por classes de regras de linters de teste (mutação de estado global sem isolamento)."),
    (["frontend"], "🟡",
     "Duplicação de helper entre features é detectável por ferramenta de similaridade de código (ex.: jscpd), mas confirmar 'mesmo bug, correção pendente nas cópias irmãs' exige leitura humana do diff semântico."),
    (["frontend"], "🟡",
     "`preventDefault()` num handler de botão é sintaticamente localizável, mas exige saber se o botão está dentro de um `<form>` (contexto de árvore, não só o nó do evento)."),
    (["frontend", "auth"], "🔴",
     "Bug de dependência de effect com timing sutil (estado que se auto-referencia na lista de deps) — requer raciocínio sobre ordem de renders/effects, não AST simples de 1 linha."),
    (["backend"], "🟡",
     "Geração de recurso externo (signed URL) dentro de loop/list-comprehension num endpoint de lista é um padrão N+1 replicável mecanicamente, mas exige saber que é round-trip de rede (não uma chamada local barata)."),
    (["frontend"], "🟡",
     "Padrão de 'reset-on-open' via previous-prop-como-state é uma técnica React específica, replicável como regra de estilo, mas com nuance de interação com outras regras de lint concorrentes (`react-hooks/refs`)."),
    (["frontend"], "🔴",
     "Correção de dado estático (listas de referência) contra um spec de negócio é validação de CONTEÚDO, não um padrão sintático de código."),
    (["clients", "frontend"], "🔴",
     "Paridade de validação entre formulários irmãos é julgamento semântico de equivalência funcional entre dois arquivos, não AST de 1 arquivo isolado."),
    (["clients", "backend"], "🟡",
     "Campo Pydantic sem espelho no dict de create/update é diffável mecanicamente contra o schema do model — mesma classe dos mappers frontend incompletos (#9/#17/#30)."),
    (["frontend"], "🟡",
     "`parseInt(digits)/100` é sintaticamente grep-ável, mas saber que a interpretação (centavos vs. reais inteiros) é 'surpreendente' para o usuário é julgamento de UX."),
    (["db", "backend"], "🟢",
     "`CREATE VIEW` sem `WITH (security_invoker = true)` é um padrão SQL mecanicamente checável — candidato natural a linter de migration (grep de `CREATE VIEW` sem a cláusula)."),
    (["frontend"], "🟡",
     "`<select required>` nativo coexistindo com validação React controlada é grep-ável (atributo `required` no JSX), mas exige saber que há validação JS paralela cujo erro nunca aparece."),
    (["clients", "frontend"], "🟡",
     "Parser de data sem round-trip de validação de calendário é um padrão de função específica, replicável como caso de teste dedicado, mas não uma regra AST genérica aplicável a qualquer parser."),
    (["frontend"], "🟢",
     "Export nunca importado/consumido em produção é mecanicamente detectável por ferramentas padrão (`ts-prune`/`eslint no-unused-vars`) — código morto é uma classe clássica de detecção automática."),
    (["clients", "frontend"], "🔴",
     "Mapeamento de campo de negócio (`fullName` ← `representanteLegalNome` para PJ) é julgamento de domínio específico do produto."),
    (["clients", "frontend"], "🔴",
     "Comportamento de browser específico (`<datalist>` + `autocomplete=off` suprime sugestões no Chrome) é conhecimento empírico de produto/compatibilidade, não AST."),
    (["backend", "admin"], "🔴",
     "Contrato cross-layer entre os campos retornados pela API de lista e o filtro client-side exige correlacionar dois arquivos (backend+frontend) com julgamento semântico."),
    (["backend", "credits"], "🟡",
     "Dois writes sequenciais sem transação é um padrão replicável (grep de duas chamadas de repositório em sequência dentro do mesmo método), mas decidir 'isto precisa ser atômico' é julgamento de negócio."),
    (["backend", "dashboard"], "🔴",
     "Escolha de coluna de métrica (`updated_at` vs. `created_at`/`changed_at` de histórico) é julgamento analítico/de negócio, não um padrão de código."),
    (["frontend", "admin"], "🟡",
     "`?? {}` alimentando um mapper é um padrão sintático específico plausível de regra estática, mas exige saber que o resultado alimenta um guard de not-found (não qualquer uso de `?? {}`)."),
    (["testing"], "🟢",
     "Secret hardcoded (`service_role`) em arquivo commitado é o caso clássico de detecção mecânica — exatamente o que scanners de segredo (gitleaks/trufflehog/regras Semgrep de secrets) fazem por construção."),
    (["process", "infra"], "🔴",
     "Comportamento do `git merge` em relação a builds/imports/testes é julgamento de processo sobre um workflow, não um padrão AST de código-fonte."),
    (["client", "frontend"], "🔴",
     "Julgamento de UX (esconder vs. explicar um bloco vazio numa tela read-only) é puramente de produto/design, não redutível a AST."),
    (["infra", "qa"], "🟡",
     "`GRANT` sem `CREATE POLICY` correspondente sob RLS é um padrão SQL replicável (correlacionar GRANT+policy por tabela numa migration), mas exige entendimento de RLS para saber que o GRANT sozinho é insuficiente."),
    (["frontend"], "🟡",
     "`className` de cor sem `variant` em wrapper `asChild` é replicável (grep de `className` com prefixo `bg-`/`text-` em `AlertDialogAction`/`Cancel`), mas exige conhecer o merge de props do Radix `Slot` para saber que produz conflito."),
    (["frontend"], "🟢",
     "`<div onClick>` sem `role`/`tabIndex`/`onKeyDown` é coberto por regras padrão de `eslint-plugin-jsx-a11y` (`click-events-have-key-events`/`no-static-element-interactions`), mecanicamente checável."),
    (["proposals", "frontend"], "🔴",
     "Clamp de state machine (`nextStep` sem teto) + `reset()` em TODOS os caminhos de cancelamento são regras de negócio específicas do wizard, não AST genérica."),
    (["admin", "frontend"], "🔴",
     "Replicar o mesmo indicador visual de gating num item de nav irmão é julgamento de paridade de produto (perguntar 'este item leva à mesma capability restrita?'), não sintaxe."),
    (["clients", "frontend"], "🔴",
     "'Porte parcial' de um padrão de autofill (copiar só parte dos campos que uma API expõe) é julgamento de completude semântica entre dois componentes, não AST."),
    (["simulation", "frontend"], "🟡",
     "`useState` inicializado de uma prop sem `useEffect` de resync é um padrão React conhecido ('derived state sem sincronização'), replicável como regra de estilo com boa precisão, mas ainda exige contexto do ciclo de vida do componente."),
    (["admin", "frontend"], "🔴",
     "Ordem de branches 'vazio genuíno' vs. 'vazio filtrado' é lógica de negócio específica da tela (depende de saber que a lista já vem pré-filtrada do servidor), não AST."),
    (["admin", "frontend"], "🟡",
     "Atribuir `''` a um campo não-nullable para satisfazer o compilador é um padrão replicável (campo obrigatório recebendo placeholder vazio), mas exige saber que esse valor alimenta um formatador sem guard."),
    (["admin", "frontend"], "🟡",
     "`disabled` dentro de `AlertDialogAction` como tentativa de mostrar loading é um padrão específico do comportamento do componente Radix — replicável por quem conhece o componente, não um AST genérico de qualquer `disabled`."),
    (["backend", "infra"], "🔴",
     "Forense de merge do git (linha removida sem diff claro no histórico) é investigação de processo/git internals, não um padrão de código estático."),
    (["process"], "🔴",
     "Governança de sub-agentes paralelos num pipeline (violação de instrução 'só testes') é julgamento de processo/confiança, não um padrão de código."),
    (["backend"], "🟡",
     "Dict-based rate limiter sem eviction de chave vazia é um padrão replicável (bucket nunca removido do dict externo), mas exige entender o ciclo de vida completo da estrutura de dados."),
    (["backend", "infra"], "🔴",
     "Comportamento de proxy/IP real por trás da Vercel depende de verificação EMPÍRICA contra o deploy real — não é decidível por análise estática do código."),
    (["admin", "frontend"], "🟡",
     "Mesma classe do #78 (`AlertDialogAction` sempre fecha, independente do resultado do `onClick` assíncrono) — replicável por quem conhece o comportamento do componente Radix."),
    (["frontend"], "🔴",
     "Layout responsivo sem teto de itens (overflow em mobile) é julgamento de design/UX, não redutível a um padrão de código."),
    (["vehicles", "frontend"], "🟡",
     "Ternário que usa só `isLoading` (ignorando `error`) de um hook `{isLoading, error}` é um padrão razoavelmente replicável (candidato a regra: consumidor de hook fetch que checa só 1 de 2 campos de estado), mas exige saber a forma exata do hook."),
    (["frontend", "testing"], "🟢",
     "`let` de escopo de módulo referenciado (atribuído) dentro do corpo de uma factory `vi.mock` é um padrão sintático muito específico e mecanicamente detectável (hoisting de `vi.mock` + TDZ de `let`/`const`) — candidato direto a regra Semgrep/ESLint."),
    (["clients", "frontend"], "🟡",
     "`useState` sem `useEffect` chaveado no id da entidade é um padrão razoavelmente replicável (estado local que nunca reseta ao trocar de entidade sob a mesma instância de componente), mas exige saber que a rota não remonta o componente entre navegações."),
    (["sistema-meta"], "🟡",
     "Depende de correlacionar o log de início/fim contra um segundo sinal de liveness (lock/heartbeat) — não é puramente sintático, exige contexto operacional de dois mecanismos distintos."),
    (["sistema-meta"], "🔴",
     "Julgamento arquitetural sobre confiabilidade de uma fonte de estado externa escrita por um processo de terceiros — decisão de design, não AST."),
    (["sistema-meta"], "🔴",
     "Julgamento de design de um gate de confiança (proxy positivo vs. negativo) é abstrato demais para reduzir a um padrão de código — aplica-se a qualquer gate de aprovação, não a uma sintaxe específica."),
    (["sistema-meta"], "🟢",
     "Interpolação literal de string (f-string) construindo front-matter/YAML linha-a-linha sem escaping é um padrão clássico de 'string building para formato estruturado' — mesma classe mecanicamente detectável de injection via f-string (fonte não validada → sink de formato line-delimited)."),
    (["sistema-meta"], "🟡",
     "Seção combinada: a lógica de exclusão-por-prefixo-exato é replicável mecanicamente (candidato a regra sobre correspondência de path), mas o achado embutido sobre `git checkout --ours` (NO-OP em caminho não-conflitado) exige entendimento semântico do modelo de stages do git — tratado como híbrido pelo conjunto da seção."),
]


def build_entry(title: str, body: str, areas: list[str], selo: str, rationale: str) -> str:
    created = extract_created(title, body)
    paras = segment_body(body)

    evitar = collect(paras, EVITAR_PREFIXES)
    risco = collect(paras, RISCO_PREFIXES)
    alternativas = collect_alt(paras)

    decisao_text = "\n\n".join(evitar) if evitar else (
        "Nenhum parágrafo rotulado `**Como evitar:**`/`**Como corrigir:**` foi "
        "encontrado nesta seção original — ver o texto verbatim completo em "
        "`## Contexto` abaixo para a orientação real, descrita em prosa livre "
        "no monólito de origem."
    )
    consequencias_text = "\n\n".join(risco) if risco else (
        "Nenhum parágrafo rotulado `**Risco:**` foi encontrado nesta seção "
        "original — ver o texto verbatim completo em `## Contexto` abaixo."
    )
    alternativas_text = "\n\n".join(alternativas) if alternativas else (
        "Nenhuma alternativa explicitamente rotulada foi encontrada nesta "
        "seção original — anti-patterns.md normalmente documenta só "
        "Problema/Risco/Como evitar/Onde apareceu, não um leque de "
        "alternativas rejeitadas. Lacuna estrutural aceita (não uma "
        "invenção): ver o texto verbatim completo em `## Contexto` para o "
        "raciocínio completo tal como foi originalmente registrado."
    )

    front_matter = (
        "---\n"
        "tipo: anti-pattern\n"
        "estado: candidata\n"
        "causa-da-morte: null\n"
        "contador-de-utilidade: 0\n"
        f"selo: {selo}\n"
        "automatizado: false\n"
        f"areas: {yaml_list(areas)}\n"
        "reverte: null\n"
        f"created: {created}\n"
        f"updated: {TODAY}\n"
        "# proveniência da migração (Story E12.3) — NÃO são campos oficiais do schema E4.1,\n"
        "# só metadado de rastreio da migração; convenção idêntica a e12_2_migrate_decisions.py/E12.2\n"
        "source_monolith: _bmad-output/anti-patterns.md\n"
        f"source_h2: {json.dumps(title, ensure_ascii=False)}\n"
        "migration_status: migrado-madr-e12-3\n"
        "---\n"
    )

    verbatim_intro = (
        "Seção original de `_bmad-output/anti-patterns.md` (H2: "
        f"{json.dumps(title, ensure_ascii=False)}), reescrita nesta entrada em "
        "gramática MADR (Story E12.3). O texto abaixo é o corpo ORIGINAL da "
        "seção, **verbatim, íntegro, sem edição** — a garantia mecânica de que "
        "nada foi perdido na restruturação (ver `slice_completeness_gate.py`, "
        "que compara este bloco token-a-token contra o monólito real)."
    )

    body_md = (
        f"# {title}\n\n"
        f"## Contexto\n{verbatim_intro}\n\n"
        f"**Texto original (verbatim, íntegro):**\n\n{body.strip()}\n\n"
        f"## Decisão\n{decisao_text}\n\n"
        f"## Alternativas consideradas e rejeitadas\n{alternativas_text}\n\n"
        f"## Consequências\n{consequencias_text}\n\n"
        f"## Selo de maturidade\n`{selo}` — {rationale}\n\n"
        "## Contador de utilidade\n"
        "`0` — entrada nova, `candidata`, ainda sem enforcement mecânico "
        "instrumentado (migração Story E12.3).\n"
    )

    return front_matter + "\n" + body_md


def main() -> None:
    monolith_text = MONOLITH.read_text(encoding="utf-8")
    sections = extract_h2_sections(monolith_text)
    titles = [t for t, _ in sections]

    assert len(sections) == len(CLASSIFICATION), (
        f"contagem real ({len(sections)}) difere da classificação preparada "
        f"({len(CLASSIFICATION)}) -- reconferir CLASSIFICATION antes de gerar"
    )
    dupes = find_source_duplicates(titles)
    assert not dupes, f"H2 duplicados no monólito: {dupes}"

    used_slugs: set[str] = set()
    d = LEDGER_ROOT / FOLDER
    if d.exists():
        for f in d.glob("*.md"):
            used_slugs.add(f.stem)

    mappings = []
    written = []
    collisions = []
    selo_counts = {"🟢": 0, "🟡": 0, "🔴": 0}

    for (title, body), (areas, selo, rationale) in zip(sections, CLASSIFICATION):
        base_slug = slugify(title)
        slug = base_slug
        n = 2
        collided = base_slug in used_slugs
        while slug in used_slugs:
            slug = f"{base_slug}-{n}"
            n += 1
        used_slugs.add(slug)
        if collided:
            collisions.append({"title": title, "base_slug": base_slug, "final_slug": slug})

        content = build_entry(title, body, areas, selo, rationale)
        out_path = LEDGER_ROOT / FOLDER / f"{slug}.md"
        out_path.write_text(content, encoding="utf-8")
        written.append(str(out_path))
        mappings.append({"h2": title, "file": f"{FOLDER}/{slug}.md"})
        selo_counts[selo] += 1

    manifest = {
        "generated_by": "e12_3_migrate_antipatterns.py (Story E12.3, reusa extract_h2_sections de E3.5)",
        "source_monolith": str(MONOLITH),
        "mappings": mappings,
    }
    manifest_path = LEDGER_ROOT / "slice-manifest-anti-patterns.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    report = {
        "h2_total": len(sections),
        "entries_written": len(written),
        "selo_counts": selo_counts,
        "collisions_with_pre_existing": collisions,
        "manifest": str(manifest_path),
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
