# Research 1/3 — BMad skill-authoring craft

> Source: read of ~12 `bmad-*` skills in `.claude/skills/`, centred on `bmad-workflow-builder` and
> `bmad-agent-builder` (the meta-skills that document the craft). 2026-08-04.

## The headline

**BMad has a written doctrine for skill quality, and a meta-skill that enforces it.**

- Doctrine: `.claude/skills/bmad-workflow-builder/references/skill-quality-principles.md`
- Build procedure: `.claude/skills/bmad-workflow-builder/references/build-process.md`
- Field schema: `.claude/skills/bmad-workflow-builder/references/standard-fields.md`
- Skeleton: `.claude/skills/bmad-workflow-builder/assets/SKILL-template.md`

The same file is loaded both when building a skill and when auditing one, so author and auditor
share one bar instead of drifting apart. **Implication for v2: the skills should be built through
`bmad-workflow-builder`, not hand-rolled.**

## The single test that drives every editorial decision

> "Would an LLM do this correctly without being told? If yes, cut it. The instruction must earn its
> place by preventing a failure that would otherwise happen."

Applied uniformly. This one test replaces a pile of ad hoc style rules.

## Size targets (production targets, not hard limits)

| Kind | Target | Ceiling |
|---|---|---|
| `SKILL.md` | ~80 lines | ~130 |
| Multi-branch `SKILL.md` | — | ~250 |
| Single-purpose focused | — | ~500 (~5000 tokens) |

Past that, lift into `references/`. **Our current `bagual-gerente-geral` is far past this** — 1732
words in `SKILL.md` plus eleven reference files.

## Structure

```
{skill-name}/
├── SKILL.md        # frontmatter, overview, conventions, activation, workflow OR routing
├── customize.toml   # only if the author opted into customization
├── references/      # carved-out workflow sections, descriptive names, NO numbered prefixes
├── assets/          # templates and static content transformed into output
└── scripts/         # deterministic code, with tests/
```

- **Never** put workflow `*.md` at skill root — that is `SKILL.md`'s job.
- `references/` = prompt content the model reads. `assets/` = things consumed/transformed into
  output. Distinct.
- Carve out on **size**, not on stage count.
- Each carved file must **work standalone** — compaction can drop `SKILL.md` mid-flow, so no "as
  described in the overview".
- **One level deep only**: `SKILL.md` → reference. Never reference → reference chains.
- Numbered filenames (`step-01-...`) are reserved for genuine linear step-machines, not for
  addressable reference sections.

## The `SKILL.md` contract

Recurring order: frontmatter → title → overview/role → `## Conventions` → `## On Activation` → body.

**Description formula:** `[What it does, 5-8 words]. [Use when user says 'X' or 'Y'.]` — the trigger
clause quotes literal phrases. Flagged bad example: *"Helps with PRDs and product requirements"* —
too vague, fires on any passing mention.

**The Conventions block is copy-pasted verbatim across skills** — a deliberate consistency device
that kills a whole class of path bugs.

**The activation close-out gate** appears verbatim in at least five skills:

> "Activation is complete. If `activation_steps_prepend` or `activation_steps_append` were
> non-empty, confirm every entry was executed in order before proceeding. Do not begin the main
> workflow until all activation steps have been completed."

A hard checkpoint against silently skipping org-mandated hooks.

## Two dialects, chosen deliberately

| Dialect | Used for | Shape |
|---|---|---|
| **Prose workflow** | Judgment-heavy work (PRD, spec, review) | Dense paragraphs, each sentence a rule. Deliberately *not* decomposed into micro-steps. |
| **XML step-machine** | Fragile operations (destructive git, mandatory gates, YAML mutation) | `<step n goal>`, `<check if>`, `<action>`, `<critical>`, `<goto>`, `<ask>` |

Freedom is graded per instruction — High / Medium / Low — not uniform across a skill. Mixing them
on purpose is the actual craft.

## Headless contract

Carved into its own reference file, never inline. Detection is OR-ed conditions, defaulting to
interactive when ambiguous.

- **Never invent to fill a gap** — record it as `assumptions[]` / `open_questions[]`.
- **Never block on input it cannot get** — halt with `status: blocked` + `reason`. Do not prompt, do
  not greet.
- **Tri-state vocabulary, defined precisely**: `complete` (stands alone) · `partial` (artifact
  produced but has open questions / inferred critical inputs) · `blocked` (no artifact).
- **Return the smallest set of paths the caller needs.** The log carries the detail.

## State and handoff — two generations

**Older:** `sprint-status.yaml` as shared status ledger, with strict expected-previous-state checks
before transitions.

**Newer — the Decision-Log Workspace**, and this is the load-bearing idea:

> "The decision log is the load-bearing artifact, not the document. The document is what the user
> takes; the decision log is what carries identity across sessions, prevents the agent from
> railroading the user, surfaces conflicts on update, and creates an audit trail when the user
> overrides their own past calls."

- `.memlog.md` — append-only, one line per decision/change/override/assumption/event, written **only**
  through the shared script.
- `addendum.md` — overflow that earned a place but doesn't fit the primary doc. Created only when
  earned, never scaffolded empty.
- Resume: on activation, look for an existing workspace, surface it, offer to resume. Reading the log
  recovers full context regardless of compaction.
- `bmad-spec` goes furthest: `SPEC.md` is **derived** from `.memlog.md` and never hand-edited. The
  rendered doc is disposable; the log is not.

## Exemplar instruction lines (verbatim)

1. *"Absolutely DO NOT stop because of 'milestones', 'significant progress', or 'session boundaries'."*
2. *"NEVER mark a task complete unless ALL conditions are met - NO LYING OR CHEATING"*
3. *"When you find yourself naming wedges, picking MVP cuts, or proposing phases, stop — you have
   crossed from elicitation into authoring. Hand the pen back."*
4. *"'Anything else, or shall we move on?' at natural transitions. Users always remember one more
   thing when given a graceful exit."*
5. *"Subagent prompt without explicit return format → Verbose prose responses. Fix: 'Return ONLY
   {schema}. No other output.'"*
6. *"The implicit-read trap: language like 'review', 'acknowledge', 'summarize what you have' causes
   the parent to read files even when you didn't ask for it."*
7. *"Never run a subagent in the background / detached / async... there is no event loop to resume a
   yielded turn, so a backgrounded subagent never hands control back and the run stalls."* (specific
   to unattended loops)

## The 12 transferable techniques

1. One litmus test ("would an LLM do this unprompted?") drives every editorial decision.
2. Freedom graded per instruction (High/Medium/Low), never uniform.
3. A fixed copy-pasted Conventions block makes path resolution a system-wide contract.
4. The activation close-out gate is a hard checkpoint, repeated verbatim across skills.
5. Decision-Log Workspace externalizes memory to disk instead of trusting context to survive
   compaction — the single biggest reliability lever for multi-session work.
6. Named, catalogued failure modes with a one-line fix each, in one table — naming makes them
   searchable and re-teachable.
7. Subagent contracts treated as a distinct engineering surface (sync vs background, "return ONLY X",
   documented degradation when subagents are unavailable).
8. Headless is never bolted on — own file, own detection, strict tri-state status.
9. Tiered fallback cascades with an explicit stop rule replace open-ended "figure it out" reasoning.
10. Customization is opt-in via one question at build time, not a speculative surface in every skill
    (prevents boolean-toggle permutation forests).
11. Institutional patterns get **names** (Open-floor opening, Soft-gate elicitation,
    Intent-before-ingestion, Capture-don't-interrupt, Dual-output, Parallel review lenses,
    Three-mode architecture) so they are referenceable shorthand suite-wide.
12. A meta-skill enforces the same bar it teaches, from the identical file.

## Documented failure modes worth stealing

- Hardcoded path in `SKILL.md` while `customize.toml` declares the scalar → the override silently
  does nothing.
- Arrays-of-tables without a `code`/`id` key → resolver falls back to append-only.
- Description over-broadens → skill fires on passing mentions.
- Subagent without explicit return format → verbose prose floods the parent.
