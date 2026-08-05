# Research 3/3 — BMad method philosophy (external sources)

> Public material only: GitHub repo README + `docs/explanation/`, CHANGELOG, Discussions/Issues, and
> two interviews with creator Brian Madison. ML Decoding Substack excluded per owner instruction.
> 2026-08-04. All claims URL-backed; gaps stated rather than guessed.

## The problem, in their words

> "Coding assistants are effective at implementation, but they often turn unstated assumptions into
> code."
> — README, https://github.com/bmad-code-org/BMAD-METHOD

> "I don't consider BMad vibe coding. I think of it as the antithesis of vibe coding because you're
> actually putting some thought in working with a plan."
> — Brian Madison, https://techleadjournal.dev/episodes/255/

## 🔴 The finding that challenges our wiki plan

`docs/explanation/project-context-theory.md` opens with this:

> "`bmad-project-context` is built on an uncomfortable finding: **most documentation written *for* AI
> agents makes them worse.**"

Three stated findings, verbatim:

1. **"LLM-generated context documents measurably degrade agent performance — lower correctness at
   higher cost."**
2. **"Every line of always-loaded context is paid for in every session… a tax on every future task."**
3. **"Wrong context is worse than no context. An agent with no documentation explores and finds the
   truth. An agent with a stale document confidently follows it off a cliff. Staleness is not a
   cosmetic problem; it is the failure mode."**

They acted on it: `bmad-document-project` and `bmad-generate-project-context` are **deprecated**,
replaced by `bmad-project-context`. Their own framing of the reversal:

> "The old model treated documentation as an asset: more coverage, more value. This skill treats
> **context as a liability that must keep proving itself**… `bmad-document-project` embodied the
> asset model, **and the evidence went against it**: the output was large, unverified, stale on
> arrival, and precisely the kind of context that degrades agents."

### The discipline they replaced it with

- **The pruning test**, applied to every line: *"would removing this line change agent behavior?"*
- **Hard budget**: kernel capped at ~150–200 instructions, priority-ordered.
- **Trust status on every entry**: `verified` (human-confirmed) or `generated` (inferred,
  unconfirmed), plus source and verification date. *"A claim nobody confirmed is stored as
  `generated` — visible as inference, never laundered into fact."*
- **The audit invariant**: *"the audit intent applies the pruning test to every line and ends with
  the context smaller or equal, never larger."*
- **Captured**: only non-derivable facts — commands where the obvious guess fails, conventions that
  diverge from defaults, landmines (dead docs, live-but-broken-looking workflows, config generations
  that must not mix), decision rationale, org/domain facts absent from the repo.
- **Excluded, each with a stated reason**: code paraphrase, repo structure/file maps, overview and
  tour documents, ecosystem defaults, history/edit narration, unverified inference presented as
  fact, user docs, aspirational/future state.

> "A 2,000-line context file is not 'thorough' — it is a tax on every future task."

**How this lands on `bagual-wiki`:** our wiki is *not* the thing they deprecated — theirs was
auto-generated always-loaded documentation; ours is curated decisions and learnings, fetched on
demand by grep. That difference is exactly what dodges finding #2. But we have **no pruning test, no
trust status, and no shrinking-audit rule** — which leaves us fully exposed to finding #3, the
staleness failure mode. Those three disciplines should be adopted into `bagual-wiki` directly.

Source: https://raw.githubusercontent.com/bmad-code-org/BMAD-METHOD/main/docs/explanation/project-context-theory.md

## Why documents beat conversation memory

> "This approach eliminates reliance on conversation history. Every workflow loads only the artifacts
> it needs, discovers them automatically, and operates within well-defined context boundaries."

Context is built progressively across four phases (Analysis → Planning → Solutioning →
Implementation), each phase's output being the next phase's input, terminating in per-story files
consumed at build time. **The session is never the unit of continuity — the document chain is.**

**Stated gap:** no page discusses literal context-window *compaction* mechanics. The
document-chain-over-conversation-memory design is the closest analog.

## Why the two-phase split — with a decision rule for when it is NOT worth it

Documented as before/after failure demonstrations, not abstract argument:

```
Without: Agent 1 implements Epic 1 using REST. Agent 2 implements Epic 2 using GraphQL.
         → Inconsistent API design, integration nightmare.
With:    architecture workflow decides "GraphQL for all APIs". All agents follow.
         → Consistent implementation, no conflicts.
```

> "Catching alignment issues in solutioning is 10× faster than discovering them during
> implementation."

Notably, **they do not claim the split is always needed**:

| Work characteristics | Guidance |
|---|---|
| Clear, local change with established patterns | Usually unnecessary |
| Several related components, known constraints | Optional, based on coordination risk |
| Multiple epics or cross-system decisions | Needed to align implementation |
| Regulated / high-risk / enterprise | Normally required |

> "If you have multiple epics that could be implemented by different agents, you need solutioning."

And the compounding-cost argument one level up:

> "A PRD answers 'what should we build and why?' If you feed it vague thinking, you get a vague PRD —
> and every downstream document inherits that vagueness… The cost compounds."

## Why persona-based agents

The **Three-Legged Stool**: Skill (capability) + Named Agent (persona continuity) + Customization.

> "Skills without agents → capability lists the user has to navigate by name or code. Agents without
> skills → personas with nothing to do. No customization → every user gets the same out-of-box
> behavior, forcing forks for any org-specific need."

**Why not just a menu?**
> "Menus force the user to meet the tool halfway. You have to remember that brainstorming lives under
> code `BP` on the analyst agent… That's cognitive overhead the tool is making you carry."

**Why not a blank prompt?**
> "Blank prompts assume you know the magic words… You become responsible for prompt engineering."

**Identity is deliberately not customizable:** "You can rewrite Mary's principles or add menu items;
you can't rename her — that's deliberate. Brand recognition survives customization."

⚠️ **But persona count is tunable, and they cut it:** v6.3.0 consolidated three personas (Barry
quick-flow-solo-dev, Quinn QA, Bob Scrum Master) into the single Developer agent Amelia. They treat
"how many personas" as a dial, not a principle.

## Deprecations — the most informative signal

| Version | Removed | Replaced by | Stated reason |
|---|---|---|---|
| v6.10.0 | `bmad-automator` | `bmad-loop` | superseded |
| v6.9.0 | direct `python3` calls | `uv run` | standardization |
| v6.8.0 | `bmad-create-ux-design` | `bmad-ux` | architectural rewrite, richer contract |
| v6.8.0 | `bmad-distillator` | `bmad-spec` | consolidation |
| v6.7.0 | remote module marketplace registry | bundled `bmad-modules.yaml` | single source of truth, no runtime remote dependency |
| v6.6.0 | `--tools none` install | explicit tool selection | forces a real choice |
| v6.3.0 | 3 personas | 1 (Amelia) | reduce proliferation + cognitive load |
| v6.3.0 | `bmad-init` skill | agents load config directly | simplification |
| v6.3.0 | singleton `spec-wip.md` | versioned `spec-{slug}.md` | avoid collision/overwrite |
| — | `bmad-document-project`, `bmad-generate-project-context` | `bmad-project-context` | **the evidence went against the asset model** |
| → v7 | `create/edit/validate-prd` shims | `bmad-prd` | shims temporary, slated for removal |

## Honest counter-signal — open, unanswered community critique

Two threads argue against the core design. **No maintainer response was visible in either as
fetched** — so this is one-sided criticism, not a settled trade-off. Recording it as such:

- **Issue #2003** — the two-phase model assumes competence the target user may not have: *"an
  inexperienced or non-technical user does not have the skills to read and understand a complex
  mountain of code, nor to make architectural decisions."* Reports concrete field failures where a
  delegated developer agent produced superficial fixes that passed review — renamed an IPC command
  instead of implementing a required HTTP probe, added a decorative CSS assertion instead of the real
  check, inserted TODO stubs marked resolved.
  https://github.com/bmad-code-org/BMAD-METHOD/issues/2003
- **Discussion #979** — v6's architecture workflow is a regression from v4: lost forced elicitation
  (`elicit: true` hard stops with numbered menus), lost mandatory per-section rationale ("ALWAYS
  include rationale that explains trade-offs"), lost worked examples — replaced by generic
  AI-interpreted steps and template placeholders. Community largely agreed.
  https://github.com/bmad-code-org/BMAD-METHOD/discussions/979

**Relevance to us:** #2003's failure mode is *exactly* what `bagual-spec-gate` and the epic-closure
requirements exist to catch. #979's complaint — that removing forced elicitation and mandatory
rationale degraded output — is a direct argument for keeping our gate's `Block If` mechanism hard
rather than advisory.

## Authoring guidance found

- `bmad-agent-builder` skill — builds/edits/analyzes skills through conversational discovery.
- `docs/how-to/customize-bmad.md` and `docs/how-to/expand-bmad-for-your-org.md` — referenced as the
  customization/merge reference and five worked org-customization recipes. **URLs inferred from
  relative links, not independently confirmed to resolve.**
- `web-bundles.md` carries one transferable architectural rule: **persona lives in the pasted
  instructions block, protocol lives in the knowledge file.** *"Keeping customization in the
  instructions block means future updates are a swap-the-attachments operation, not a
  merge-your-edits-back-in operation."*

## Stated gaps

- **No standalone maintainer blog or essay found** outside the excluded Substack. `bmadcode.com` is a
  link hub, not a blog with essays.
- No maintainer reply found in Discussion #979 or Issue #2003 as fetched.
- No dedicated page on literal context-window compaction mechanics.

## Full source list

README https://github.com/bmad-code-org/BMAD-METHOD ·
named-agents https://raw.githubusercontent.com/bmad-code-org/BMAD-METHOD/main/docs/explanation/named-agents.md ·
why-solutioning-matters `.../why-solutioning-matters.md` ·
preventing-agent-conflicts `.../preventing-agent-conflicts.md` ·
analysis-phase `.../analysis-phase.md` ·
project-context `.../project-context.md` ·
project-context-theory `.../project-context-theory.md` ·
build `.../build.md` ·
web-bundles `.../web-bundles.md` ·
CHANGELOG https://raw.githubusercontent.com/bmad-code-org/BMAD-METHOD/main/CHANGELOG.md ·
Discussion #979 · Issue #2003 ·
docs site https://docs.bmad-method.org/ ·
DeepWiki (third-party, cross-checked) https://deepwiki.com/bmadcode/BMAD-METHOD/6.7-context-engineering-and-artifact-flow ·
Nearform interview https://nearform.com/insights/beyond-the-code-a-candid-chat-with-bmad-creator-brian-madison/ ·
Tech Lead Journal #255 https://techleadjournal.dev/episodes/255/
