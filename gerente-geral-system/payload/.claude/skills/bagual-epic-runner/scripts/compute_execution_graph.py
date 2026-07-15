#!/usr/bin/env python3
"""
compute_execution_graph.py — Story E10.3 (bagual-epic-runner, PRD 03 FR-3) +
Story E10.4 (PRD 03 FR-4: dependency ordering + cycle detection).

Computes the Execution Graph's `paralela` vs `sequencial` pairwise relation from
epics' DECLARED areas, including the mandatory shared-touchpoints declaration
(F2 hardening — "conflito zero por construção" was FALSE without them:
`ideias/revisao-adversarial-furos.md` § F2), THEN layers a declared `depends_on`
dependency graph on top (Story E10.4): a dependency edge between two epics forces
them `sequencial` — and into the SAME Track — even when their declared areas are
fully disjoint ("dependency beats disjunction"). Each Track's epic order is a
deterministic topological sort of that Track's dependency edges. A dependency
CYCLE anywhere in the requested `--epics` set is detected before any graph is
emitted or written — the script HALTs (non-zero exit, `"halt": true` in the JSON
output, no `--write`) rather than ever guessing or producing a partial order.
stdlib-only (json/re/argparse/itertools/pathlib/datetime — no PyYAML, no
third-party deps).

FAIL-SAFE BIAS (constitutional for this script): any missing declaration, any
shared-touchpoint overlap, any code-area overlap, or any declared dependency
edge => sequencial. A wrong "paralela" is the catastrophic failure (a merge
conflict reaching the owner, or a dependency violated); a wrong "sequencial"
only costs time. A dependency CYCLE is a planning error, not a schedule to
approximate — it HALTs instead of producing any order at all. When in doubt,
this script is WRONG in the sequential/HALT direction, never the parallel one.

Full spec, declaration-format rationale, and fixture-based proof runs:
`ideias/sistema-artifacts/E10-3-grafo-disjuncao.md` (disjunction) and
`ideias/sistema-artifacts/E10-4-dependencias-ciclo.md` (dependencies + cycles).

════════════════════════════════════════════════════════════════════════════════
DECLARATION FORMAT (what this script consumes)
════════════════════════════════════════════════════════════════════════════════
A JSON object, one entry per epic key (matching sprint-status.yaml's `epic-N` /
`epic-EN` keys). Each value:

    {
      "epic_type":      "feature" | "refactor" | "other",   # optional, default "other"
      "areas":          ["<path-or-directory-prefix>", ...],
      "touches_shared": ["<path-or-directory-prefix>", ...], # optional
      "depends_on":     ["<epic-key>", ...]                  # optional (Story E10.4)
    }

- `areas` is the epic's own code footprint. Initial granularity is FEATURE FOLDER
  (conservative, tunable): a directory prefix such as
  "frontend/src/features/proposals/" or a single file such as
  "backend/domain/vehicles/services.py".
- `touches_shared` is where the epic explicitly declares it touches one of the
  FIXED shared-touchpoint categories below (SHARED_TOUCHPOINT_CATALOG). It is
  purely additive convenience — a shared-touchpoint path dropped directly into
  `areas` is matched identically; the two lists are merged before classification.
- `epic_type: "feature"` auto-injects `frontend/src/App.tsx` +
  `backend/api/index.py` into the epic's touched paths EVEN IF NOT DECLARED —
  per the AC ("epic de feature nova, por definição, toca App.tsx/api/index.py"),
  a feature epic touching the router/App shell is true by construction, so the
  declarer does not have to remember to restate the obvious. This is a safety
  net on top of the declaration, never a substitute for declaring the rest of
  the epic's real footprint.
- **A missing declaration for an epic in the requested `--epics` set is not an
  error — it fail-safes.** Every pair involving that epic is `sequencial`,
  reason `"missing declaration for {epic} (fail-safe)"`. This mirrors FR-3's own
  documented fail-safe rule verbatim ("declaração ausente → par tratado como
  não-disjunto"). A missing declaration also means that epic's `depends_on` (if
  any was intended) is invisible to this script — same fail-safe posture.
- `depends_on` (Story E10.4) is a list of OTHER epic keys that must run and
  finish BEFORE this epic starts — i.e. `"epic-B": {"depends_on": ["epic-A"]}`
  means "A → B" (A must complete before B). Only entries that are ALSO present
  in the requested `--epics` set are honored: a `depends_on` reference to an
  epic outside the current invocation is treated as already satisfied (e.g. it
  finished in a prior invocation) and is silently ignored — this script only
  orders epics within the set it was asked to schedule. A dependency, once
  honored, is an ADDITIONAL sequencing constraint layered on top of the
  disjunction check from Story E10.3, never a replacement for it — an epic pair
  with disjoint areas AND no dependency is still `paralela`, unchanged from
  E10.3.

Two sources for this JSON object:
  (a) `--declarations FILE.json` — a standalone file (used by fixtures/tests, and
      by any caller that already has the declarations in hand).
  (b) `--sprint-status FILE.yaml` — this script extracts a top-level `epic_areas:`
      block from the sprint-status.yaml itself. That block is a restricted YAML
      subset by construction: each line under `epic_areas:` is
      `  <epic_key>: <JSON-OBJECT>` — i.e. JSON flow-mapping values (JSON is a
      valid YAML subset), so no general YAML parser is needed, just a per-line
      regex + `json.loads`. This is the format the Gerente's planning brain
      (Story E9.3, `project_controll/gerente/planning-brain.md`) is expected to
      populate per epic when it declares area/files/dependencies — today (E10.4)
      no real epic in either sprint-status.yaml carries this block yet, so every
      real-epic run fails safe to all-sequential until a producer starts writing
      it.

════════════════════════════════════════════════════════════════════════════════
SHARED TOUCHPOINT CATALOG (fixed set — ideias/epics.md Story E10.3 AC bullets +
PRD 03 FR-3 + ideias/revisao-adversarial-furos.md F2)
════════════════════════════════════════════════════════════════════════════════
    app_tsx        frontend/src/App.tsx
    api_index      backend/api/index.py
    package_json   package.json / package-lock.json / pnpm-lock.yaml / yarn.lock
    pyproject      pyproject.toml / uv.lock
    migrations     supabase/migrations/**
    process_files  sprint-status.yaml, anti-patterns.md, decisions.md,
                   product-decisions.md, notes.md, projects-history.md,
                   board.yaml — matched by BASENAME regardless of directory, so
                   both the product tree (`_bmad-output/...`) and the
                   meta-system tree (`ideias/sistema-artifacts/...`) match the
                   same category.

A declared path is classified into a category by prefix/basename match (see
`classify_shared_touchpoint`). A path matching no category is a plain code area,
still subject to the area-overlap check.

════════════════════════════════════════════════════════════════════════════════
ALGORITHM
════════════════════════════════════════════════════════════════════════════════
Phase 1 — pairwise relation (Story E10.3, extended by E10.4's dependency check):
For every unordered pair (A, B) of epics in the requested `--epics` set:
  1. If A or B has no declaration at all -> NON-DISJOINT (fail-safe).
  2. Else, if a `depends_on` edge exists between A and B (either direction) ->
     NON-DISJOINT ("declared dependency"). This is checked BEFORE the area/
     shared-touchpoint comparison below — a dependency is decisive regardless of
     what the two epics' areas look like ("dependency beats disjunction").
  3. Else classify every declared path of A (areas ∪ touches_shared, epic_type
     auto-injection applied) and of B into shared-touchpoint categories. If the
     two category sets intersect -> NON-DISJOINT ("shared touchpoint overlap").
  4. Else compare the remaining plain code-area paths of A vs B pairwise for
     path containment (equal, or one is a directory-prefix of the other) ->
     NON-DISJOINT if any pair overlaps ("overlapping declared area").
  5. Else -> DISJOINT ("paralela").

Tracks = connected components of the "sequencial" graph (union-find over
NON-DISJOINT pairs, including dependency-forced pairs). Epics inside the same
Track must run in series — even a pair that does not directly conflict but is
transitively linked through a third epic (by area/touchpoint OR dependency) in
the same component still shares a Track, because Track is the atomic unit of
ordering, not the pairwise relation itself. A declared dependency edge always
forces both endpoints into the SAME Track (never leaves them as separate Tracks
that merely need cross-Track ordering) — this keeps ordering entirely intra-
Track, so Track-to-Track order (still "first-epic-in-`--epics`-order", unchanged
from E10.3) never needs to account for a dependency that spans two Tracks; by
construction, no dependency ever does.

Phase 2 — per-Track topological sort + cycle detection (Story E10.4):
Within each Track (connected component), the `depends_on` edges restricted to
that Track's members form a directed graph. This script runs Kahn's algorithm
over that subgraph to produce the Track's final `epics` order:
  - Deterministic tie-break: whenever more than one epic is simultaneously
    "ready" (all its declared in-Track dependencies already ordered), the one
    that appears EARLIEST in the original `--epics` invocation order is chosen
    next. This is a stable topological sort: when a Track has NO dependency
    edges at all (the common case, and the entirety of Story E10.3's behavior),
    every epic is always "ready", so this tie-break alone determines the order
    — which is exactly `--epics` order, i.e. byte-identical to Story E10.3's
    Track member order. Dependencies only ever reorder a Track relative to that
    baseline when they must.
  - If Kahn's algorithm cannot order every member of a Track (some members never
    become "ready"), those members are on a dependency CYCLE. This script does
    not guess an order for them, or for anything else in the run: it aborts the
    ENTIRE computation (every Track, every pair), returns `"halt": true` with
    the concrete cycle path(s) (e.g. `["epic-A", "epic-B", "epic-A"]`), exits
    non-zero, and — critically — never calls `--write`, so a pre-existing
    `execution_graph:` block in `--sprint-status` is left untouched rather than
    being overwritten with anything derived from the cyclic input. A cycle
    anywhere in the requested set is a global HALT (consistent with this
    chassis's current global-HALT semantics elsewhere — Track-scoped failure
    isolation is Story E10.5, not this one).

Epics in different Tracks are pairwise disjoint (by area/touchpoint AND by
dependency) and are the only candidates Story E11 may eventually execute in
parallel (this script only COMPUTES the graph; execution stays serial in E10 —
workflow.md's Step 0 still iterates Tracks in series).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from itertools import combinations
from pathlib import Path
from typing import Any


# ──────────────────────────────────────────────────────────────────────────
# Shared touchpoint catalog
# ──────────────────────────────────────────────────────────────────────────

PROCESS_FILE_BASENAMES = frozenset(
    {
        "sprint-status.yaml",
        "anti-patterns.md",
        "decisions.md",
        "product-decisions.md",
        "notes.md",
        "projects-history.md",
        "board.yaml",
    }
)

PACKAGE_JSON_BASENAMES = frozenset(
    {"package.json", "package-lock.json", "pnpm-lock.yaml", "yarn.lock"}
)

PYPROJECT_BASENAMES = frozenset({"pyproject.toml", "uv.lock"})


def classify_shared_touchpoint(raw_path: str) -> str | None:
    """Return the canonical shared-touchpoint category for raw_path, or None if
    raw_path is not one of the fixed shared touchpoints (i.e. it is a plain code
    area path)."""
    normalized = raw_path.strip().replace("\\", "/")
    basename = Path(normalized).name

    if normalized == "frontend/src/App.tsx" or normalized.endswith("/frontend/src/App.tsx"):
        return "app_tsx"
    if normalized == "backend/api/index.py" or normalized.endswith("/backend/api/index.py"):
        return "api_index"
    if basename in PACKAGE_JSON_BASENAMES:
        return "package_json"
    if basename in PYPROJECT_BASENAMES:
        return "pyproject"
    if normalized.startswith("supabase/migrations") or "/supabase/migrations/" in normalized:
        return "migrations"
    if basename in PROCESS_FILE_BASENAMES:
        return "process_files"
    return None


FEATURE_TYPE_AUTO_TOUCHPOINTS = ("frontend/src/App.tsx", "backend/api/index.py")


# ──────────────────────────────────────────────────────────────────────────
# Declaration loading
# ──────────────────────────────────────────────────────────────────────────


def load_declarations_from_json(path: Path) -> dict[str, dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: declarations JSON must be a top-level object")
    return data


_EPIC_AREAS_BLOCK_RE = re.compile(r"^epic_areas:\s*$", re.MULTILINE)
_EPIC_AREAS_LINE_RE = re.compile(r"^\s+([A-Za-z0-9_.\-]+):\s*(\{.*\})\s*$")


def load_declarations_from_sprint_status(path: Path) -> dict[str, dict[str, Any]]:
    """Extract the `epic_areas:` block from a sprint-status.yaml file.

    The block is a restricted YAML subset by construction: every entry under
    `epic_areas:` is `  <epic_key>: <JSON-OBJECT>` on a single line (JSON is a
    valid YAML flow-mapping), so this needs only a per-line regex + json.loads,
    never a general YAML parser. Returns {} (empty — everything fails safe) if
    the block is absent, which is the expected/normal case until a producer
    (Story E9.3's planning brain) starts writing it.
    """
    text = path.read_text(encoding="utf-8")
    match = _EPIC_AREAS_BLOCK_RE.search(text)
    if not match:
        return {}

    declarations: dict[str, dict[str, Any]] = {}
    for line in text[match.end() :].splitlines():
        if line.strip() == "":
            continue
        if re.match(r"^\S", line):  # next top-level key — block ended
            break
        line_match = _EPIC_AREAS_LINE_RE.match(line)
        if not line_match:
            # Not a recognized `key: {json}` line inside the block — ignore
            # rather than crash; a malformed line degrades to "no declaration"
            # for that epic (fail-safe), never a hard parse error.
            continue
        epic_key, json_blob = line_match.group(1), line_match.group(2)
        try:
            declarations[epic_key] = json.loads(json_blob)
        except json.JSONDecodeError:
            continue
    return declarations


def touched_paths(declaration: dict[str, Any]) -> tuple[frozenset[str], frozenset[str]]:
    """Return (shared_categories, plain_code_areas) for one epic's declaration."""
    areas = list(declaration.get("areas") or [])
    touches_shared = list(declaration.get("touches_shared") or [])
    epic_type = declaration.get("epic_type", "other")

    all_paths = list(areas) + list(touches_shared)
    if epic_type == "feature":
        all_paths.extend(FEATURE_TYPE_AUTO_TOUCHPOINTS)

    shared_categories: set[str] = set()
    plain_areas: set[str] = set()
    for raw_path in all_paths:
        category = classify_shared_touchpoint(raw_path)
        if category is not None:
            shared_categories.add(category)
        else:
            plain_areas.add(raw_path.strip().replace("\\", "/").rstrip("/"))
    return frozenset(shared_categories), frozenset(plain_areas)


def _paths_overlap(a: str, b: str) -> bool:
    """True if path/prefix a and b are equal or one directory-contains the other
    (feature-folder granularity: a directory prefix "conflicts" with anything
    nested under it, not just an exact-string match)."""
    if a == b:
        return True
    return a.startswith(b + "/") or b.startswith(a + "/")


# ──────────────────────────────────────────────────────────────────────────
# Dependency edges (Story E10.4, PRD 03 FR-4)
# ──────────────────────────────────────────────────────────────────────────


def build_dependency_edges(
    epic_set: list[str],
    declarations: dict[str, dict[str, Any]],
) -> tuple[dict[str, set[str]], list[tuple[str, str]]]:
    """Return (predecessors, edges).

    `predecessors[epic]` is the set of OTHER epics (restricted to `epic_set`)
    that `epic` depends on, i.e. that must run before it. `edges` is the flat
    list of (predecessor, dependent) tuples in declaration order, for reporting.

    A `depends_on` entry naming an epic outside `epic_set` is silently dropped
    (treated as already satisfied — see module docstring). An epic depending on
    itself is kept as a degenerate 1-node cycle (`predecessors[epic] ⊇ {epic}`),
    which `topo_sort_component` below correctly reports as a cycle rather than
    silently ignoring.
    """
    epic_set_members = set(epic_set)
    predecessors: dict[str, set[str]] = {epic: set() for epic in epic_set}
    edges: list[tuple[str, str]] = []

    for epic in epic_set:
        decl = declarations.get(epic)
        if not decl:
            continue
        for dep in decl.get("depends_on") or []:
            if dep not in epic_set_members:
                # Dependency on an epic outside this invocation's --epics set:
                # out of scope for this script, assumed already satisfied.
                continue
            predecessors[epic].add(dep)
            edges.append((dep, epic))

    return predecessors, edges


# ──────────────────────────────────────────────────────────────────────────
# Pairwise disjointness + graph construction
# ──────────────────────────────────────────────────────────────────────────


def compute_pair_relation(
    epic_a: str,
    epic_b: str,
    declarations: dict[str, dict[str, Any]],
    dependency_pair_reasons: dict[frozenset[str], str],
) -> tuple[str, str]:
    """Return (relation, reason) for one unordered pair. relation is
    "sequencial" or "paralela"."""
    decl_a = declarations.get(epic_a)
    decl_b = declarations.get(epic_b)

    if decl_a is None or decl_b is None:
        missing = epic_a if decl_a is None else epic_b
        return "sequencial", f"missing declaration for {missing} (fail-safe)"

    dependency_reason = dependency_pair_reasons.get(frozenset((epic_a, epic_b)))
    if dependency_reason is not None:
        # Story E10.4: a declared dependency beats disjunction — decisive
        # regardless of what the two epics' areas look like, checked before
        # the area/shared-touchpoint comparison below.
        return "sequencial", dependency_reason

    shared_a, areas_a = touched_paths(decl_a)
    shared_b, areas_b = touched_paths(decl_b)

    shared_overlap = shared_a & shared_b
    if shared_overlap:
        return (
            "sequencial",
            "shared touchpoint overlap: " + ", ".join(sorted(shared_overlap)),
        )

    for pa in areas_a:
        for pb in areas_b:
            if _paths_overlap(pa, pb):
                return "sequencial", f"overlapping declared area: '{pa}' vs '{pb}'"

    return "paralela", "disjoint (no shared touchpoint, no area overlap, no dependency)"


class _UnionFind:
    def __init__(self, items: list[str]) -> None:
        self._parent = {item: item for item in items}

    def find(self, x: str) -> str:
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, x: str, y: str) -> None:
        rx, ry = self.find(x), self.find(y)
        if rx != ry:
            self._parent[ry] = rx


def topo_sort_component(
    members: list[str],
    predecessors: dict[str, set[str]],
    epic_set_index: dict[str, int],
) -> tuple[list[str] | None, list[str] | None]:
    """Deterministic topological sort of one Track's `depends_on` subgraph,
    restricted to `members`.

    Returns (order, None) if the subgraph is acyclic — `order` is a permutation
    of `members` respecting every in-Track dependency edge, with ties (multiple
    simultaneously-"ready" epics) broken by ascending `epic_set_index` (i.e. the
    epic that appears earliest in the original `--epics` invocation order). When
    a Track has NO dependency edges among its members, every epic is always
    "ready" and this reduces to plain `--epics` order — byte-identical to Story
    E10.3's insertion-order Track member list.

    Returns (None, cycle_path) if one or more members never become "ready"
    (Kahn's algorithm stalls) — those members are on a dependency cycle.
    `cycle_path` is a concrete example cycle, e.g. ["epic-A", "epic-B",
    "epic-A"], found by walking `depends_on` edges from an unresolved member
    until a node repeats.
    """
    members_set = set(members)
    local_preds: dict[str, set[str]] = {m: set() for m in members}
    for m in members:
        for p in predecessors.get(m, ()):
            if p in members_set:
                local_preds[m].add(p)

    successors: dict[str, set[str]] = {m: set() for m in members}
    for m in members:
        for p in local_preds[m]:
            successors.setdefault(p, set()).add(m)

    indeg = {m: len(local_preds[m]) for m in members}
    ready = [m for m in members if indeg[m] == 0]

    order: list[str] = []
    while ready:
        ready.sort(key=lambda e: epic_set_index[e])
        node = ready.pop(0)
        order.append(node)
        for succ in successors.get(node, ()):
            indeg[succ] -= 1
            if indeg[succ] == 0:
                ready.append(succ)

    if len(order) == len(members):
        return order, None

    remaining = [m for m in members if m not in order]
    cycle_path = _find_cycle_path(remaining, local_preds, epic_set_index)
    return None, cycle_path


def _find_cycle_path(
    remaining: list[str],
    local_preds: dict[str, set[str]],
    epic_set_index: dict[str, int],
) -> list[str]:
    """Walk `depends_on` edges (m -> one of local_preds[m], i.e. "m depends on
    this") starting from a deterministic member of `remaining` until a node
    repeats, and return the closed cycle path from that repeat onward (e.g.
    ["epic-A", "epic-B", "epic-A"]). Every node in `remaining` is known (by
    construction — Kahn's algorithm in `topo_sort_component` could not resolve
    it) to be part of at least one cycle, so this walk is guaranteed to find a
    repeat. Deterministic: ties broken by `epic_set_index`, same convention as
    the rest of this script."""
    remaining_set = set(remaining)
    node = min(remaining, key=lambda e: epic_set_index[e])
    path = [node]
    seen_index = {node: 0}
    while True:
        preds = sorted(
            (p for p in local_preds[node] if p in remaining_set),
            key=lambda e: epic_set_index[e],
        )
        if not preds:
            # Defensive only — every member of `remaining` is provably on a
            # cycle, so this should be unreachable; fail soft rather than
            # crash if it ever is.
            return path
        nxt = preds[0]
        if nxt in seen_index:
            path.append(nxt)
            return path[seen_index[nxt] :]
        seen_index[nxt] = len(path)
        path.append(nxt)
        node = nxt


def build_execution_graph(
    epic_set: list[str],
    declarations: dict[str, dict[str, Any]],
    computed_at: str,
) -> dict[str, Any]:
    predecessors, dep_edges = build_dependency_edges(epic_set, declarations)

    dependency_pair_reasons: dict[frozenset[str], str] = {}
    for pred, dependent in dep_edges:
        pair_key = frozenset((pred, dependent))
        reason = f"declared dependency: {dependent} depends_on {pred}"
        # If both directions were declared (A depends_on B AND B depends_on A),
        # keep the first reason seen — cycle detection below is what actually
        # catches and HALTs on this case; the pairwise reason text is only
        # diagnostic, never load-bearing for correctness.
        dependency_pair_reasons.setdefault(pair_key, reason)

    pairs: list[dict[str, Any]] = []
    uf = _UnionFind(epic_set)

    for epic_a, epic_b in combinations(epic_set, 2):
        relation, reason = compute_pair_relation(
            epic_a, epic_b, declarations, dependency_pair_reasons
        )
        pairs.append({"epics": [epic_a, epic_b], "relation": relation, "reason": reason})
        if relation == "sequencial":
            uf.union(epic_a, epic_b)

    components: dict[str, list[str]] = {}
    for epic in epic_set:  # preserves epic_set order within each component
        root = uf.find(epic)
        components.setdefault(root, []).append(epic)

    epic_set_index = {epic: idx for idx, epic in enumerate(epic_set)}

    cycles: list[dict[str, Any]] = []
    tracks: list[dict[str, Any]] = []
    for idx, members in enumerate(components.values(), start=1):
        order, cycle_path = topo_sort_component(members, predecessors, epic_set_index)
        if cycle_path is not None:
            cycles.append({"track_members": members, "cycle_path": cycle_path})
            continue
        assert order is not None
        tracks.append(
            {
                "track_id": f"track-{idx}",
                "epics": order,
                "epic_status": {epic: "pending" for epic in order},
                "status": "pending",
            }
        )

    if cycles:
        # Story E10.4: a cycle anywhere in the requested set HALTs the ENTIRE
        # computation — never a partial/guessed order for the Tracks that
        # happen to be acyclic. Caller (main()) must not --write this result.
        return {
            "computed_at": computed_at,
            "mode": "disjunction-v1",
            "halt": True,
            "reason": "dependency cycle detected — refusing to produce a runnable order",
            "cycles": cycles,
            "pairs": pairs,
        }

    return {
        "computed_at": computed_at,
        "mode": "disjunction-v1",
        "tracks": tracks,
        "pairs": pairs,
    }


# ──────────────────────────────────────────────────────────────────────────
# YAML emission (hand-rolled, JSON-flow-scalar trick — no external deps)
# ──────────────────────────────────────────────────────────────────────────


def render_execution_graph_yaml(graph: dict[str, Any]) -> str:
    lines = ["execution_graph:"]
    lines.append(f'  computed_at: "{graph["computed_at"]}"')
    lines.append(f'  mode: "{graph["mode"]}"')
    lines.append("  tracks:")
    for track in graph["tracks"]:
        lines.append(f'    - track_id: "{track["track_id"]}"')
        lines.append(f"      epics: {json.dumps(track['epics'])}")
        lines.append(f"      epic_status: {json.dumps(track['epic_status'])}")
        lines.append(f'      status: "{track["status"]}"')
    if not graph["pairs"]:
        lines.append("  pairs: []")
    else:
        lines.append("  pairs:")
        for pair in graph["pairs"]:
            lines.append(f"    - epics: {json.dumps(pair['epics'])}")
            lines.append(f'      relation: "{pair["relation"]}"')
            lines.append(f"      reason: {json.dumps(pair['reason'])}")
    return "\n".join(lines) + "\n"


_TOP_LEVEL_KEY_RE = re.compile(r"^[A-Za-z0-9_.\-]+:", re.MULTILINE)


def splice_execution_graph_into_sprint_status(sprint_status_path: Path, graph: dict[str, Any]) -> None:
    text = sprint_status_path.read_text(encoding="utf-8")
    new_block = render_execution_graph_yaml(graph).rstrip("\n")

    existing_match = re.search(r"^execution_graph:\s*$", text, re.MULTILINE)
    if existing_match:
        # Find the end of the existing block: next top-level (col-0) key after it.
        rest = text[existing_match.end() :]
        next_key_match = re.search(r"^[A-Za-z0-9_.\-]+:", rest, re.MULTILINE)
        end = existing_match.end() + (next_key_match.start() if next_key_match else len(rest))
        new_text = text[: existing_match.start()] + new_block + "\n\n" + text[end:]
    else:
        # Insert right before the top-level `development_status:` anchor, which
        # exists in both the product and meta-system sprint-status.yaml files.
        anchor_match = re.search(r"^development_status:\s*$", text, re.MULTILINE)
        if not anchor_match:
            raise ValueError(
                f"{sprint_status_path}: no existing `execution_graph:` block and no "
                "`development_status:` anchor to insert before — refusing to guess "
                "a location."
            )
        new_text = text[: anchor_match.start()] + new_block + "\n\n" + text[anchor_match.start() :]

    sprint_status_path.write_text(new_text, encoding="utf-8")


# ──────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────

HALT_EXIT_CODE = 3


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compute the Execution Graph (paralela/sequencial) from epics' "
        "declared areas, including mandatory shared touchpoints (Story E10.3) and "
        "declared dependencies with cycle detection (Story E10.4)."
    )
    parser.add_argument(
        "--epics",
        nargs="+",
        required=True,
        help="Epic keys in invocation order, e.g. epic-E12 epic-E13 (or epic-38).",
    )
    parser.add_argument(
        "--declarations",
        type=Path,
        default=None,
        help="Standalone declarations JSON file (fixtures/tests). Takes precedence "
        "over --sprint-status's embedded epic_areas: block if both are given.",
    )
    parser.add_argument(
        "--sprint-status",
        type=Path,
        default=None,
        help="Path to a sprint-status.yaml to read epic_areas: from (and, with "
        "--write, to splice the computed execution_graph: block into).",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Splice the computed graph into --sprint-status's execution_graph: "
        "block in place. Requires --sprint-status. Never runs if a dependency "
        "cycle is detected (see HALT_EXIT_CODE below).",
    )
    parser.add_argument(
        "--date",
        default=None,
        help="computed_at override (YYYY-MM-DD). Default: today.",
    )
    args = parser.parse_args(argv)

    if args.write and args.sprint_status is None:
        parser.error("--write requires --sprint-status")

    if args.declarations is not None:
        declarations = load_declarations_from_json(args.declarations)
    elif args.sprint_status is not None:
        declarations = load_declarations_from_sprint_status(args.sprint_status)
    else:
        declarations = {}

    computed_at = args.date or date.today().isoformat()
    graph = build_execution_graph(list(args.epics), declarations, computed_at)

    print(json.dumps(graph, indent=2, ensure_ascii=False))

    if graph.get("halt"):
        print(
            "\n[HALT] dependency cycle detected — refusing to produce or write an "
            "execution graph. Do not run any story for this invocation.",
            file=sys.stderr,
        )
        for cyc in graph["cycles"]:
            print(f"  cycle: {' -> '.join(cyc['cycle_path'])}", file=sys.stderr)
        return HALT_EXIT_CODE

    if args.write:
        splice_execution_graph_into_sprint_status(args.sprint_status, graph)
        print(f"\n[written] {args.sprint_status}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
