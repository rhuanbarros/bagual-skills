# PRD Quality Review — Bagual Skills v2 (bagual-bmad-loop-runner + bagual-manager)

## Overall verdict

This PRD has a real thesis ("if the night is literal, the day must be complete"), earns it with a
concrete incident (Story 22.1's schema-inventory gap), and traces every major requirement group back
to that thesis without padding — decision-readiness, substance, and strategic coherence are all
strong. What's at risk is downstream mechanics rather than content: there is no Glossary despite the
document explicitly feeding nine skills' construction, the Assumptions Index doesn't round-trip
cleanly, and one requirement (FR42) lives entirely outside the numbered Functional Requirements
section where a downstream scan would miss it. None of this is a content defect — it's the kind of
mechanical debt that costs a build session an hour, not a redesign.

## Decision-readiness — strong

Decisions are stated as decisions, not softened into "considerations." Non-Goals (§3) each carry a
reason, not just a label — e.g. "Becoming a `bmad-loop` plugin. Explicit owner decision: this is a
separate skill that invokes `bmad-loop run`, not a manifest dropped into `.bmad-loop/plugins/`."
FR42 (§2.2) is the strongest instance of a real trade-off in the document: it names the rejected
alternatives (index + lock; append-only journal) and says why each loses, rather than presenting the
chosen design as the only option considered. FR13's worktree-isolation mandate is grounded the same
way — cites the actual Epic 22 collision and explicitly notes "a passing suite is not evidence of no
collision," which is an objection acknowledged, not dodged.

The one place decision-readiness wobbles: the document's own front-matter says `status: final`, but
§10 Open Question 4 states plainly "Reviewer pass on this PRD. Not run... an adversarial review
remains available and unspent." A PRD can legitimately ship un-reviewed by choice, but "final" reads
as "ready to build from" while the document itself flags that no adversarial pass has touched it.
That's an honest disclosure, not a smoothing-over — but the status label doesn't match what's
disclosed two sections later.

### Findings
- **medium** Status/review mismatch (front-matter `status: final` vs. § 10 item 4) — the header claims finality while the body admits the reviewer pass "was not run" and is "unspent." *Fix:* either drop `status: final` to `status: draft-pending-review`, or fold this rubric pass's outcome into the status before the doc is treated as build-ready.

## Substance over theater — strong

No persona theater (§4 correctly uses "a single user in two shapes," never invents named personas
for a one-operator tool). No innovation-differentiation section written for its own sake — the
Context (§1) does the job a Vision statement usually does, and it is fully non-swappable: it names a
row count (950), the two dropped-but-live columns, and the exact hours (~six overnight) from Epic 22.
No NFR boilerplate — §8's "Portability," "Thin management," and "Unattended safety" are each tied to
a named product concern in §5, not copy-pasted "must be scalable/secure" filler. The research
grounding (§12) is earned, not decorative: it names two findings that actually changed a decision
(FR25a's wiki-as-liability model, FR14's wake mechanism), rather than padding the document with
research for the appearance of rigor.

## Strategic coherence — strong

The thesis is explicit and load-bearing: "if the night is literal, the day must be complete" (§1,
line 40-42). Every FR group traces back to it — the planning gate (7.2) makes the day complete, run
supervision (7.3) keeps literalism from compounding silently, closure (7.4) is framed explicitly as
"the gap this skill exists to fill," and the knowledge loop (7.5) is the mechanism that keeps the next
day's completeness from starting at zero. Success Metrics (§9) validate the thesis rather than
measuring activity — "Overnight escalations caused by spec gaps: falling toward 0" is a thesis-test,
not a vanity count — and counter-metrics are named for every metric that could be gamed (e.g. "Gate
`PASS` verdicts followed by CRITICAL escalations... manufactures false confidence"). This reads as an
argued position, not a backlog with headings.

## Done-ness clarity — adequate

Most FRs are unusually well operationalized for a PRD at this altitude — FR40's exit-code contract
(0/1/2/3, stdout=JSON/stderr=diagnostics, atomic writes) and FR38's `complete`/`partial`/`blocked`
tri-state are genuinely testable, not adjectives. But a few requirements state an intent without a
bound where the document elsewhere shows it knows how to write one:

### Findings
- **medium** FR27 (Communication contract, §7.6) has no size/format bound. It says "Objective and short by default" and "Detail on demand only" but never states a bound the way FR36 does for `SKILL.md` (~80 lines, ceiling ~130, up to ~250). Given FR27 is explicitly justified as *functional* ("an unreadable report... is functionally equivalent to no report"), it deserves the same numeric discipline FR36 applies to skill files. *Fix:* give the manager's default report a length ceiling (e.g., N lines/words) the way FR36 bounds SKILL.md.
- **medium** The "Thin management" NFR (§8) asserts "Orchestration overhead stays small" with no bound — no token budget, no ratio against execution spend. FR14 gives a mechanism (event-driven wake, not polling) but the NFR itself is unfalsifiable as written. *Fix:* attach a number (e.g., idle-window token ceiling per run) or explicitly say the mechanism (zero-poll wake) is the acceptance criterion and drop the adjective.
- **low** Portability (§8, and repeated across §1/§4/§5) is asserted as a first-class constraint — "must run unmodified against a project it has never seen, after init" — but no FR or Success Metric names a concrete validation step against the second-company project the PRD itself says exists (§1, §4). Everything else in this document is unusually rigorous about turning claims into checks; this one claim isn't. *Fix:* add an AC or Success Metric: v2 is validated against the other-company project before being called portable, not just "assumed to run" from the design.

## Scope honesty — adequate

Non-Goals (§3) does real work — six items, each with a one-line reason, not a bare list. Assumptions
are explicitly tagged inline and indexed (§11). Deferred items are named as deferred with the reason
(§10: gorioapp's own migration, the 54 mis-triaged tickets, template skills). This is a well-disclosed
document. Two mechanical gaps pull it down from "strong":

### Findings
- **medium** Assumptions Index doesn't round-trip. §11 lists three assumptions, but only one (the "copy into place" wording, FR32) has a matching inline `[ASSUMPTION]` tag. The other two indexed assumptions ("`bmad-loop`'s stories mode is production-ready," "one epic at a time / `max_parallel` clamps to 1") have no inline tag anywhere near FR8 or the Non-Goals parallelism line where they'd naturally sit. Conversely, FR12's inline `[ASSUMPTION]` ("The re-run is scoped to the affected stories rather than the whole epic," line 236) is never indexed in §11 at all. *Fix:* true up the index — tag FR8 and the parallelism Non-Goal inline, and add FR12's assumption to §11.
- **low** Zero `[NOTE FOR PM]` callouts anywhere in the document, despite several places carrying real unresolved tension that the rubric's convention exists for — e.g. FR12's re-run-scope assumption, or the reliance on a wake mechanism (§10 "Resolved during discovery") that is described as researched but not yet exercised end-to-end in this project. The document surfaces these honestly through prose and `[ASSUMPTION]` tags instead, so nothing is actually hidden — this is a missed convention, not a missed disclosure. *Fix:* optional; low cost either way given the prose already carries the caveat.

## Downstream usability — thin

This is a chain-top document by its own admission (§7.8/FR34: v2 skills are built *through*
`bmad-workflow-builder`, and this PRD is the input). That raises the bar on traceability, and two
things fall short of it.

### Findings
- **high** No Glossary anywhere in the document. Load-bearing project-specific vocabulary — ".bagual/", "the gate" vs. "the loop" vs. "the manager", "resident but idle", "the closure checklist", "spec debt" — is used consistently in prose but never formally defined in one place. For a document that hands off to nine separate skill builds (§2.3), each of which will pull sections in isolation, a missing Glossary means each downstream reader has to reconstruct the vocabulary from context instead of citing a single defined term. *Fix:* add a short Glossary — even 10-15 terms would cover the load-bearing nouns used repeatedly across §2, §6, §7.
- **medium** FR42 is defined in §2.2, entirely outside §7 "Functional Requirements" where the other 41 IDs live in ascending, contiguous order. A downstream reader or tool scanning §7 for "the full FR set" will not find FR42 there at all. Relatedly, §2.3 cites `(FR5)` and `(FR22)` before either is defined (both live later, inside §7) — those two references work fine once the reader reaches §7, but §2.3 does not stand alone on a first read, which the rubric flags as a downstream-usability cost. *Fix:* either renumber FR42 into its natural place in §7 (it's a ticketing/concurrency requirement, so it plausibly belongs near FR29's `bagual-tickets` material), or add an explicit note in §7's header that FR42 lives in §2.2 by design.
- **low** FR25a is placed *before* FR25 in reading order (line 305 vs. 327) despite the "a"-suffix convention normally signaling an insertion after the numbered item it's named for. Not confusing once read, but it inverts the convention the suffix implies.

## Shape fit — strong

This is correctly shaped as a capability spec for a single-operator internal tool: no personas, no
UJs, no market sizing, no GTM — exactly what the rubric calls for at this shape, and the PRD does not
manufacture any of it for the sake of looking complete. The brownfield grounding (§6 "what already
exists," §1's Epic 22 citation) is unusually concrete for this altitude — real row counts, real
`policy.toml` keys already present in the installed tool, not a generic "leverage existing
infrastructure" gesture. The two-anchor-skill split (§2.1) is exactly the right amount of structure
for a document covering two skills that share infrastructure — it does not over-formalize the
relationship, just tables who drives what.

## Mechanical notes

- **FR4 vs. FR39 duplication risk.** Both describe the customize.toml-style config merge algorithm — FR4 in general terms ("entries keyed by id replace and extend"), FR39 with more precision ("arrays-of-tables merge by a shared `code`/`id` key... No removal primitive"). They're consistent today, but two independent statements of one algorithm in a 42-FR document is exactly the pattern FR22 calls out and fixes for the grounding rule ("Three texts of one rule will diverge"). Consider making FR39 the sole authority and having FR4 reference it.
- **ID continuity**: FR1–FR41 (plus FR25a) are contiguous and correctly ordered within §7. FR42 is the outlier — see Downstream usability above. No duplicate IDs found.
- **Assumptions Index roundtrip**: fails in both directions — see Scope honesty findings above (2 of 3 indexed assumptions have no inline tag; 1 inline assumption is unindexed).
- **No UJ protagonist check applies** — this PRD correctly carries no UJs (single-operator capability spec; see Shape fit).
- **Glossary**: absent — see Downstream usability.
