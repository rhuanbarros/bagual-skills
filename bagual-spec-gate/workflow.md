# bagual-spec-gate — Workflow

Act as a skeptical spec auditor whose only job is to make sure a design-spec + epic document
cannot silently drop something the repository already knows about, or ship an undecided product
call disguised as a decided one. You run ONCE, over ONE shared document, before any story is
sliced from it — never per-story, never after the fact.

## Step 0 — Resolve the target document(s)

**Input resolution.** The invocation (`/bagual-spec-gate <arg>`) accepts:
- A bare epic number (`22`) → resolve to that epic's pair: the design spec under
  `{project-root}/design-process/evolution/specs/*.md` whose content matches the epic (grep the
  epic doc for a spec reference, or vice versa — most epics cite their source spec explicitly),
  and the epic doc itself under `{project-root}/_bmad-output/planning-artifacts/epics-*.md`.
- A direct path to either a design spec or an epic doc — resolve its counterpart the same way
  (follow explicit cross-references in the doc; if none exist, gate the single doc alone and say
  so in the artifact, don't invent a counterpart).

If no target resolves, HALT immediately: `verdict: HALT`, reason "could not resolve a target
document for `<arg>`", no further steps run.

**What "the epic" replaces.** Read the target doc(s) for what existing thing (table, feature,
component, flow) this epic replaces or substantially changes — this drives Steps 2-4. If the epic
is purely additive (new entity, nothing replaced, nothing dropped), Steps 2 and 4 still run but
will typically find nothing to inventory or protect — say so explicitly, don't skip the step.

## Step 1 — Grow the ruler

Grep `{project-root}/wiki/nota-operacional/**` and `{project-root}/wiki/ledger/regra/**` for:
terms drawn from the epic itself (entity names, feature names, domain terms), AND the 5
categories this gate checks — (a) schema/consumer inventory, (b) edge cases, (c) destructive
migrations, (d) undecided product behavior / `Block If`, (e) verifiable Acceptance Criteria.
Fold anything relevant found into this run's checklist for Steps 2-6 — a prior round's spec-debt
lesson (e.g. "grep scoped to `frontend/src` misses backend scripts and E2E helpers") becomes an
explicit check this round, not a thing to rediscover from scratch each time.

**Promote a note.** If, across this run's own findings plus what Step 1 found in the Wiki, the
same pattern now shows up 2 or more times (e.g. two separate spec-gate runs both caught "old
table's ordering index silently dropped"), write or extend a `wiki/ledger/regra/<slug>.md` entry
recording it as a standing rule for the next spec — this is how the ruler actually grows across
runs, not just within one.

## Step 2 — Inventory (a): every column/field/consumer of what's being replaced

**Do not trust a prior analysis document's "before" recap — it is exactly what failed in Story
22.1.** Establish the LIVE schema of whatever is being replaced by reading the actual applied
migrations (`grep -l "create table.*<old_entity>"` and every subsequent `alter table
<old_entity>` across `{project-root}/supabase/migrations/`, in chronological filename order) —
this is the ground truth, not what any spec claims the old schema was.

For every column/field found this way, run:

```
python3 {inventory_sweep_script} <column_or_symbol_name> --json
```

once per column/symbol (never pass `--include` or any path filter — the script has none on
purpose, see its module docstring). **If the result carries a non-null `scope_warning`, the sweep
was rooted below the repository and is PARTIAL — discard it, re-run without `--repo-root`, and
never let a partial sweep support a "this column has no consumers" conclusion.** Ground truth for
scale: a correct repo-wide sweep for `expense_type` returns 405 occurrences across code, tests,
migrations and docs; the scoped grep that missed it returned effectively none.

Read every occurrence's `kind` (migration/code/test/seed/doc)
to judge real consumer vs. incidental mention — a `test`/`seed` hit is still a real consumer that
breaks the moment the old entity disappears, exactly the class of miss that let
`frontend/tests/e2e/**` and `backend/scripts/seed_finance_fixtures_dev.py` slip through in Story
22.1's own spec.

**Diff against the target document.** Every live column/consumer falls into exactly one bucket:
1. Migrates 1:1 into the new schema — confirm the spec's migration step actually carries it.
2. Replaced by an explicit new column/mechanism — confirm the spec names the replacement.
3. Intentionally dropped, with a stated reason — confirm the spec states the reason, not just the
   fact.

Anything not falling cleanly into one of these three (i.e., a live column the spec never
mentions) is a **finding**: auto-fix by adding it to the spec's inventory/migration section with
the correct bucket, following the in-place-correction format in Step 8. Never guess which bucket
— if the correct bucket for a found column is a product decision, it becomes a Step 5 `Block If`
instead of a Step 2 auto-fix.

## Step 3 — Edge cases (b)

Check the target doc against edge cases a schema/behavior change like this typically hits, e.g.:
day-31-in-a-short-month clamping, whether an edit to a recurring rule propagates to already-
generated occurrences or not, catch-up/backfill generation skipping the current period, and
`ON DELETE CASCADE`/`SET NULL` semantics on any new or changed foreign key (does a cascade erase
paid/confirmed history that must survive the parent's deletion?). This is not an exhaustive
checklist to run mechanically — read the actual schema/behavior described and reason about which
edges of it the spec is silent on.

**Auto-fix when the project's existing convention already answers it.** Search for the same shape
elsewhere in the codebase (e.g. how `booking_payment_installments` or a comparable existing table
already handles the same edge) and cite the precedent directly in the fix. When no existing
convention answers it, the edge case becomes a Step 5 `Block If` — never invented.

## Step 4 — Destructive action (c)

Scan the target doc's migration/implementation plan for any `drop table`, physical `delete`
(not soft-delete), or other data-altering statement. Every one of these requires, as an explicit
Acceptance Criterion in the doc:
1. A rollback CSV (or equivalent extractable backup) taken **before** the destructive statement
   runs.
2. A row-count assertion between the data copy/migration step and the destructive statement that
   follows it — so a partial copy is caught before the only surviving copy of the source rows is
   destroyed.

Good precedent to point a spec at: `{project-root}/supabase/migrations/20260731120000_gorioapp_fix_cleaning_fee_double_count.sql`.

**Auto-fix by requiring the AC/assertion to exist as an explicit checklist item — never invent
the CSV's actual content or row values.** If the doc has a destructive statement and ships with no
such AC at all, this is severe enough to combine with Step 5: the missing safeguard is added as a
required AC, AND if any product judgment is needed to fill it in (e.g. which rows specifically
need preserving, or whether the destructive step should even happen before a dependent decision is
made), that part becomes a `Block If`.

## Step 5 — `Block If` (d) — the one check that ASKS, never infers

Every not-yet-made product-behavior decision found by Steps 2-4/6 (or by direct reading — a
mention of a new entity, a new flow, an ambiguous default) becomes an explicit `**Block If:**`
line in the doc. **A spec containing a destructive action (Step 4) or a new entity, and shipping
with `Block If: none`, is rejected outright** — that combination is exactly what happened in
Story 22.1's own spec.

🔴 **Non-negotiable constraint — this skill never invents product behavior to close a gap.** Not a
plausible-sounding inference, not "the obvious default," not silence. Every gap opens a literal
HALT block:

```
## HALT — Block If gap

**Doc:** <path>
**Gap:** <one or two sentences: what decision is undecided, and why Steps 2-4/6 couldn't resolve
it from the repository alone>
**Question to the owner:** <the literal question>
**Answer:** <the owner's literal reply, verbatim, in whatever language they used>
```

**Interactive mode:** ask the question directly, record the literal reply, keep going (the doc's
`Block If` line gets filled in from the recorded answer; the doc's prose is never rewritten to
imply the answer was always known).

**Headless mode:** do not block waiting for a reply that can't arrive. Emit the HALT block with
`**Answer:** (pending — headless run, awaiting owner)`, set the overall `verdict: HALT` in the
artifact frontmatter, and stop the run at the end of the current step group — Steps 6-8 for THIS
gap's doc section are skipped (a HALT'd document does not get a fabricated grounding/verdict
wrapped around an unresolved gap), but if other, independent parts of the doc have no open gap,
their auto-fixes from Steps 2-4/6-7 still apply and get recorded. The artifact and the resulting
in-place doc corrections are exactly what an interactive follow-up run picks up to resolve.

## Step 6 — Verifiable Acceptance Criteria (e)

Every Acceptance Criterion in the target doc must name concrete, checkable proof — a query, a
file existence check, a specific observable state. "Works correctly", "behaves as expected", or
similar unfalsifiable phrasing does not pass.

**Auto-fix when a concrete check is derivable from the doc's own content** (e.g. the doc already
describes the expected row count or table shape elsewhere — restate it as the AC's proof).
**Otherwise it becomes a Step 5 `Block If`** — a vague AC on a behavior nobody has actually pinned
down is itself an undecided-behavior signal, not a wording problem to paper over.

## Step 7 — Wiki grounding

Run an ITERATIVE grep/glob search over `{project-root}/wiki/**` — grep for terms from the target
doc, read the candidates that come back, refine the terms based on what you learn, grep again.
This is judgment-driven search, not a one-shot lookup; mirror the grep-native grounding procedure
already working for stories in `{project-root}/_bmad/custom/bmad-create-story.toml` (its
`activation_steps_append` block documents the exact search loop to reuse here).

Embed the result as a `## Grounding (Wiki)` section in the target doc, in this exact shape (the
precedent already used by hand in `{project-root}/_bmad-output/implementation-artifacts/21-5-friccao-proporcional-ao-risco.md`
lines 284-312 — read it once for the tone before writing this section):

```
## Grounding (Wiki)

- `wiki/ledger/<tipo>/<slug>.md` — <distilled one-to-two sentence summary of the decision/rule/
  pattern actually relevant to this doc, not the full doc text>
- `wiki/nota-operacional/<slug>.md` — <same>
- Sem conhecimento na Wiki para <topic X> — <state this explicitly whenever a topic the doc
  touches has no matching Wiki entry; absence is a signal, never silence>
```

Every item cites the doc's real path plus a distilled summary — never a bare pointer ("see this
file"), never the full source text pasted in.

## Step 8 — Verdict

`verdict: PASS` only when every Step 5 gap opened during this run has a recorded answer (never
"pending"). Any open HALT anywhere in the doc → `verdict: HALT` for the whole run, even if only
one gap out of many is still open.

**In-place corrections in the target document — visible trail, never silent rewrite.** Every fix
from Steps 2-4/6-7 lands directly in the design-spec doc, appended as a dated block in the format
this project already uses by hand — see `{project-root}/design-process/evolution/specs/contas-a-pagar-despesa-com-vencimento-spec.md`
lines 555-633 for the exact precedent shape. This skill's equivalent:

```
## Spec Gate — <YYYY-MM-DD>

<one paragraph: what was missing, per category (a)-(e), and what was added/corrected. Cite the
exact section(s) amended. Never rewrite or delete the doc's prior prose — this block is additive,
appended after it.>
```

**Write the output artifact** to `{spec_gate_output_dir}spec-gate-epic-<N>.md` (or, when the
invocation was a direct path rather than an epic number, name it from the doc's own slug instead
of `<N>`):

```markdown
---
verdict: PASS  # or HALT — literal value, read directly by another workstream's bmad-dev-auto.toml guard; never rename this field
epic: <N or doc slug>
target_docs:
  - <path to design spec>
  - <path to epic doc>
date: <YYYY-MM-DD>
---

# Spec Gate — Epic <N>

## Findings by category

| Category | Finding | Status | Detail |
|---|---|---|---|
| (a) Inventory | ... | auto-fixed / HALT | ... |
| (b) Edge cases | ... | auto-fixed / HALT | ... |
| (c) Destructive action | ... | auto-fixed / HALT | ... |
| (d) Block If | ... | HALT (resolved) / HALT (open) | ... |
| (e) Verifiable AC | ... | auto-fixed / HALT | ... |

## Block If — questions and answers (verbatim)

<every HALT block from Step 5, in full, in the order they were raised>

## Grounding (Wiki)

<the Step 7 slice, embedded here as well as in the target doc, so the artifact is self-contained>
```

A completion marker (an empty `DONE.marker` file, or equivalent, next to the artifact) is not
required by this skill — the artifact's own `verdict` frontmatter field is the machine-readable
signal downstream tooling reads.

## Headless mode

Skip interactive confirmations throughout; log every assumption in the artifact instead of asking
— except Step 5, which NEVER assumes (see Step 5's Headless mode note: it records a pending HALT
and stops for that gap instead). Return only the artifact path and verdict, no prose:

```json
{
  "status": "complete",
  "verdict": "PASS",
  "artifact": "{spec_gate_output_dir}spec-gate-epic-<N>.md"
}
```

On `verdict: HALT`, `status` is still `"complete"` (the gate ran to completion and correctly
produced a HALT verdict — this is not a tooling failure). Use `"status": "blocked"` only when
Step 0 could not resolve a target document at all.
