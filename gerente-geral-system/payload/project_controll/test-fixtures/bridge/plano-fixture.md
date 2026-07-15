# Plano — FIXTURE (bridge-declaracao-areas end-to-end proof)

> THROWAWAY fixture — synthetic plano.md in the shape
> `project_controll/gerente/planning-brain.md` §3 Passo 2 produces, used only by
> `ideias/sistema-artifacts/fixtures/bridge/validate_bridge.py`. 4 epics:
> `epic-90`/`epic-91` are disjoint (should compute `paralela`); `epic-92`
> `depende-de` `epic-91` (should force them into the same Track, ordered); `epic-93`
> carries a deliberately MALFORMED sentinel (invalid `epic_type`) to prove the
> fail-safe path — a bad declaration must never produce a wrong "paralela".

## Epic 1 — Feature A (fixture)

**Descrição:** entrega fictícia A, isolada em seu próprio diretório de feature.
**Área:** fixture-feature-a
**Arquivos/diretórios prováveis:** `ideias/sistema-artifacts/fixtures/bridge/fake-tree/feature-a/`
**Depende-de:** (nenhum)

<!-- epic-decl: {"epic_key": "epic-90", "epic_type": "other", "areas": ["ideias/sistema-artifacts/fixtures/bridge/fake-tree/feature-a/"]} -->

## Epic 2 — Feature B (fixture)

**Descrição:** entrega fictícia B, isolada em seu próprio diretório de feature —
disjunta de A.
**Área:** fixture-feature-b
**Arquivos/diretórios prováveis:** `ideias/sistema-artifacts/fixtures/bridge/fake-tree/feature-b/`
**Depende-de:** (nenhum)

<!-- epic-decl: {"epic_key": "epic-91", "epic_type": "other", "areas": ["ideias/sistema-artifacts/fixtures/bridge/fake-tree/feature-b/"]} -->

## Epic 3 — Feature C (fixture, depende de Epic 2)

**Descrição:** entrega fictícia C — área também disjunta de A e B, mas só pode
começar depois que a Feature B (Epic 2 / `epic-91`) estiver pronta.
**Área:** fixture-feature-c
**Arquivos/diretórios prováveis:** `ideias/sistema-artifacts/fixtures/bridge/fake-tree/feature-c/`
**Depende-de:** Epic 2 (`epic-91`)

<!-- epic-decl: {"epic_key": "epic-92", "epic_type": "other", "areas": ["ideias/sistema-artifacts/fixtures/bridge/fake-tree/feature-c/"], "depends_on": ["epic-91"]} -->

## Epic 4 — Declaração malformada (fixture, prova de fail-safe)

**Descrição:** epic cujo sentinel estruturado é intencionalmente inválido
(`epic_type` fora do enum aceito) — prova que o bridge NUNCA escreve uma declaração
malformada no `epic_areas:` (skip + warning), deixando este epic no fail-safe
`sequencial` do `compute_execution_graph.py` (declaração ausente).
**Área:** fixture-feature-d
**Arquivos/diretórios prováveis:** `ideias/sistema-artifacts/fixtures/bridge/fake-tree/feature-d/`
**Depende-de:** (nenhum)

<!-- epic-decl: {"epic_key": "epic-93", "epic_type": "not-a-real-type", "areas": ["ideias/sistema-artifacts/fixtures/bridge/fake-tree/feature-d/"]} -->

## Checagem de prontidão

- Epic 1 (`epic-90`): pronto.
- Epic 2 (`epic-91`): pronto.
- Epic 3 (`epic-92`): pronto (depende de `epic-91` — ordenação, não bloqueio).
- Epic 4 (`epic-93`): pronto na prosa, mas o sentinel estruturado é deliberadamente
  inválido para esta fixture — ver "Descrição" acima.
