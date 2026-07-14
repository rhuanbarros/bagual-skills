# Catálogo de técnicas — o menu curado

> Os blocos que este kit sabe instalar numa skill nova. Cada bloco tem um doc próprio em
> `references/` com o "como fazer" completo e os templates correspondentes. Este arquivo é só o
> **menu**: o que cada bloco é, quando serve, e do que ele depende. Na geração, o usuário escolhe
> os blocos; você lê **só** os docs escolhidos (P1 — progressive disclosure).

Esta é a lista **curada** — várias técnicas do sistema de origem foram deliberadamente cortadas
(wake/scheduling instável, consciência de cota, guards mecânicos, roteamento de produto, gates de
QA, pipeline de epic/story). Ver `principios.md` P0. Não reintroduza o que foi cortado.

| Bloco | Técnica | Para skill de… | Depende de |
|---|---|---|---|
| **A** | Arquitetura de agentes | TOPO | — (base) |
| **B** | Estado persistente & retomar | TOPO | A |
| **D1** | Autoaprendizado (sidecar) | TOPO ou TAREFA | — |
| **D2** | Autocorreção (self-heal) | TOPO | A, D1 |
| **E** | Captura de conhecimento (Ledger) | TOPO ou TAREFA | — |
| **G** | Aprendizado de estilo do dono | TOPO ou TAREFA | E (recomendado) |

---

## Bloco A — Arquitetura de agentes  → `bloco-a-arquitetura.md`

O esqueleto de um agente autônomo. Quatro peças:
- **3 camadas** — topo (decide/despacha) · orquestrador (executa 1 unidade) · sub-agente (1 tarefa).
- **Topo nunca executa** (P4) — o topo só decide e despacha; código roda no sub-agente.
- **Persona-como-arquivo** (P2) — a definição vive em `.claude/agents/<nome>.md`.
- **Contrato de despacho por marcador em disco** — o topo despacha e espera um **marcador em
  arquivo** (não um valor de retorno), pra sobreviver a crash/compactação de contexto.

Instale quando: a skill nova é um **agente de topo** que coordena trabalho. Dispense para skills de
tarefa pura.

## Bloco B — Estado persistente & retomar  → `bloco-b-estado-retomar.md`

Como o agente "sabe onde parou" entre ativações. Peças **mantidas** na curadoria:
- **`estado-atual.yaml`** — um snapshot legível do estado operacional, lido no início da fase que
  precisa dele (não tudo na ativação — P1).
- **Diário append-only** (`diario.md` humano + `diario.jsonl` máquina) — trilha do que aconteceu.
- **Lock singleton** — impede dois decisores concorrentes (duas sessões manuais), com reclaim
  sem-TOCTOU e posse por token.
- **Recuperação de crash** — reconcilia despachos órfãos após uma queda no meio do trabalho.

**Cortado deste bloco:** wake local / loop / cron / scheduling (instável — não instale). Sem o
wake, lock+crash continuam válidos (protegem contra sessões concorrentes e crash), só **desacoplados**
de qualquer ciclo agendado.

Instale quando: a skill de topo roda em sessões separadas e precisa retomar; ou pode ter mais de
uma instância viva.

## Bloco D1 — Autoaprendizado (padrão "sidecar memory")  → `bloco-d-autoaprendizado.md`

A skill **melhora a si mesma** run após run. Núcleo:
- **`lessons-log.md`** (append-only) — reflexões cruas ao fim de cada run.
- **`playbook.md`** (curado, feed-forward) — regras destiladas, lidas no **início** de cada run.
- **Reflector ≠ executor** — quem reflete nunca é quem agiu (anti-autoengano).
- **Curator** — destila lessons→playbook; **deprecar, nunca deletar** (evita "context collapse").
- **Graduation** — a regra madura migra pro prompt permanente da skill.

Instale quando: **quase sempre** — é o coração do valor deste kit. Serve para topo e tarefa.
Já existe um manual longo de origem (`bloco-d-autoaprendizado.md` credita a fonte).

## Bloco D2 — Autocorreção (self-heal)  → `bloco-d-selfheal.md`

A skill não só detecta defeitos na própria máquina — **conserta**, num sub-agente de contexto
limpo, com freio (`capture-only` vs `auto-fix`) e **escalonamento obrigatório** quando o conserto
toca o núcleo. Desacoplado de loop (roda sob invocação ou no fim de uma sessão de trabalho).

Instale quando: a skill de topo tem uma **máquina própria** (scripts/configs) que pode quebrar e
que vale consertar sozinha. Depende de A (despacho) e D1 (aprende com os consertos).

## Bloco E — Captura de conhecimento (Ledger tipado)  → `bloco-e-captura-conhecimento.md`

A **memória do projeto** entre sessões (distinta da memória da própria skill, que é o Bloco D):
- **RULE ZERO / on-complete** — ao fim de toda tarefa, registrar o que foi aprendido.
- **Ledger tipado grep-native** — decisões/regras/padrões/anti-patterns como arquivos `.md`
  tipados, pesquisáveis por grep, com uma gramática **simplificada** (a versão MADR completa da
  origem foi enxugada pro genérico).
- **nota-operacional** — o que não encaixa num tipo de Ledger.

Instale quando: **quase sempre**. Gera o esqueleto mínimo da Wiki/Ledger se o projeto destino ainda
não tiver.

## Bloco G — Aprendizado de estilo do dono  → `bloco-g-estilo.md`

A skill aprende as **preferências e o estilo do dono** ao longo do tempo (tom, formato de entrega,
decisões recorrentes de gosto) e as aplica nas próximas execuções. Distinto do Bloco D (que aprende
sobre *operar a skill*) e do Bloco E (que registra conhecimento *do projeto*) — aqui o alvo é a
**pessoa**. Recomenda-se apoiá-lo no Bloco E para persistir os fatos de estilo.

Instale quando: a skill produz saída que o dono consome (relatórios, decisões, texto) e o gosto
dele importa.
