# Evidence-verification review — prd-bagual-bmad-loop-runner-2026-08-04

**Lens:** verify every checkable factual claim about tools/history against the actual repository.
**Target:** `_bmad-output/planning-artifacts/prds/prd-bagual-bmad-loop-runner-2026-08-04/prd.md`

---

## 1. Claims about `bmad-loop`

### 1.1 `[stories] source = "stories"` — dispatch by folder+id (FR8, § 6, § 11)
**CONFIRMED.** `.bmad-loop/policy.toml` `[stories]`: `source = "sprint-status"` (current, matches PRD's
"Currently `sprint-status`"), comment confirms `"stories"` mode "reads a typed `stories.yaml`
(Story Breakdown output, sibling of `SPEC.md`) and dispatches each entry by spec-folder + story id."
`bmad-loop run --help` confirms `--spec FOLDER`: "force stories mode: dispatch the epic spec
folder's `stories.yaml` by folder+id (overrides `[stories].source`)" — matches FR8's
`bmad-loop run --spec <folder>` claim exactly.
Caveat already self-flagged by the PRD itself (§ 11 Assumptions): this mode "has never been
exercised in this project" — an honest hedge, not a gap in the review.

### 1.2 `[scm] isolation = "worktree"` — equivalent to `bagual-worktree`, including gitignored-config seeding (§ 6 "Consequence", FR13)
**PARTLY TRUE — the equivalence claim is overstated.** `policy.toml` `[scm]` confirms worktree
isolation, `branch_per = "story"`, `merge_strategy`, `delete_branch` all exist (matches "branch per
story, merge-back"). But the seeding mechanism is narrower than `bagual-worktree`'s:
- `policy.toml` comment: `seed_adapter_defaults` "copies each loaded adapter's own config files
  (claude -> `.mcp.json`/`.claude/settings.json`, codex -> `.codex/config.toml`, etc.)"; `worktree_seed`
  "adds extra project-specific gitignored paths" and defaults to `worktree_seed = []` (empty).
- `bagual-worktree/SKILL.md:10`: "everything gitignored (env files, `node_modules`, virtualenvs,
  local secrets, generated project links) and anything uncommitted in the source checkout is
  silently left behind... This skill pins the new worktree to the source's exact current commit,
  then replicates **both categories**" — i.e. the full gitignored tree (deps, envs, secrets) *and*
  the source's uncommitted diff.
`bmad-loop`'s default seeding covers only CLI/MCP adapter config files, not dependency installs
(`node_modules`/`.venv`), not arbitrary secrets, and not uncommitted-diff replication — those would
require manually populating `worktree_seed` (empty by default) and there is no evidence of automatic
`npm install`/`uv sync` on worktree creation. The PRD's own "Consequence" paragraph ("`bmad-loop`'s
native worktree mode covers the same ground **including the gitignored-config seeding that was
`bagual-worktree`'s main reason to exist**") is the retirement rationale for `bagual-worktree` — and
that rationale rests on a coverage claim this evidence does not support at face value. Worth
re-checking before actually retiring `bagual-worktree`.

### 1.3 `bmad-loop sweep` triages deferred work (FR17, § 6)
**CONFIRMED as designed/documented, unverified in execution (and PRD says so itself).**
`bmad-loop --help`: `sweep — triage + execute open deferred-work.md entries`; `bmad-loop sweep --help`
options (`--decisions-only`, `--dry-run: list open ledger entries, spawn nothing`, `--repeat`,
`--max-bundles`) match the described triage behavior. § 6 itself states "Never run in this project" —
confirmed: no `sweep` references found in `.bmad-loop/runs/20260803-200314-abf1/journal.jsonl` or in
either archived run's tarball contents. The PRD does not overclaim actual execution here.

### 1.4 `retrospective = "auto"` unsupported in v1 (§ 6)
**CONFIRMED, verbatim.** `policy.toml` `[gates]`: `retrospective = "notify"  # never | notify | auto
(auto unsupported in v1)` — the PRD's "Partial — `notify` only; `auto` unsupported in v1" is a direct
paraphrase of the tool's own comment.

### 1.5 Run directory exposes the signals FR14 depends on (status/run dir/ATTENTION)
**CONFIRMED.** `.bmad-loop/runs/20260803-200314-abf1/` contains `ATTENTION`, `state.json`,
`events/`, `logs/`, `tasks/`, `journal.jsonl`. `bmad-loop status --json` emits a structured document
(`status`, `finished`, `stopped`, `crashed`, `paused_reason`, `paused_stage`, `tokens`, `adapters`,
...). `ATTENTION` and `journal.jsonl` (checked directly) carry human-readable budget/finish events.
These are real, inspectable, poll-able surfaces — the factual half of FR14 holds.

### 1.6 Other `[verify]`, `[adapter.*]`, `resolve`/`decisions` claims (§ 6)
**CONFIRMED.** `[verify] commands = []` (empty by default, matches "Exists. Empty."). `[adapter.dev]`
/ `[adapter.review]` / `[adapter.triage]` exist only as commented-out examples (matches "Exists.
Unused."). `bmad-loop --help` lists both `resolve` (`resolve a CRITICAL escalation interactively,
then re-arm + resume`) and `decisions` (`answer deferred-work decisions earlier sweeps left
unanswered`) as real subcommands with working `--help` output — matches "Exists."

---

## 2. The wake mechanism (§ 10, "FR14's mechanism is no longer unknown")

**FALSE — this is the single most important finding in the review; the PRD's own research source
contradicts the claim it is used to support.**

The claim: "`research/02-bmad-infrastructure.md` documents how `bmad-loop` already coordinates an
out-of-process orchestrator with an in-session agent... That is a working model to build against
rather than a mechanism still to be invented."

Read against `.bmad-loop/bmad_loop_hook.py` and the research doc's own § "The hook — how an
out-of-process orchestrator talks to an in-session agent":

- The hook's guard is exactly what the research doc describes: `run_dir =
  os.environ.get("BMAD_LOOP_RUN_DIR")`; `task_id = os.environ.get("BMAD_LOOP_TASK_ID")`; `if not
  run_dir or not task_id: return 0`. These env vars are set **only on tmux windows the orchestrator
  itself spawns** for dev/review sessions.
- `research/02-bmad-infrastructure.md:100-103` states this plainly: "these are set *only* on tmux
  windows spawned by the orchestrator. **A normal interactive session returns immediately. The hook
  is silently inert for every ordinary session.**"
- The coordination direction is one-way and internal to `bmad-loop`'s own engine: "the orchestrator
  never talks to the agent directly. It polls a directory of timestamped event files, and separately
  drives the session's *input* via tmux send-keys" (same file, line 106-108).

FR14 is a different pairing entirely: `bagual-bmad-loop-runner` runs as a skill "in its own dedicated
window" — the owner's **own interactive Claude Code session**, not a tmux window `bmad-loop` spawned.
By the research doc's own words, that is precisely "a normal interactive session" for which "the hook
is silently inert." Nothing in the hook, the run directory, or the coordination model gives that
outside interactive session a push-style wake signal. At best the skill could poll `ATTENTION`/
`status`/the events directory on some cadence — which is a valid design, but it is the skill
re-inventing a polling loop, not "a working model to build against." The PRD's own FR14 text hedges
correctly ("waits on an event — a hook, a completion signal, a marker on disk"), but § 10's framing
— "no longer unknown," "a working model to build against rather than a mechanism still to be
invented" — overstates what was actually found: a mechanism that solves a **different** problem
(orchestrator-core ↔ its own spawned sessions), presented as if it closes the **open** problem
(external interactive supervisor ↔ idle-wake). This is exactly the "laundered inference" pattern the
task asked to catch.

---

## 3. Claims about Epic 22 (vs `_bmad-output/implementation-artifacts/epic-22-retro-2026-08-04.md`)

All **CONFIRMED**:
- **11 stories** — retro table lists 22.1 through 22.11, all `done`.
- **~6 hour overnight window** — retro: "overnight 2026-08-03 20:38 → 2026-08-04 02:34" (5h56m,
  PRD's "roughly six hours" and "2026-08-03 → 2026-08-04" both match); `journal.jsonl` confirms the
  run start `20260803-200314` and finish line at `2026-08-04 02:34:04`.
- **Two dropped columns** — retro item 1: migration "omitting `expense_type`/`investor_name` (2 of
  15 real source columns...)" — matches PRD's "omitting two live columns" exactly.
- **~10 hour open-status gap** — retro: "`epic-22` staying `in-progress` for ~10 hours after all 11
  stories were `done`" — matches PRD's "sat `in-progress` for about ten hours" verbatim in spirit.
- **Four atomicity risks plus one regression** — retro: "triaged `deferred-work.md` and fixed 4 real
  atomicity risks plus one capability regression" — matches exactly.
- **Write collision** — retro item 3 ("A real write collision happened... `scm.isolation: "none"`")
  — matches.
- **QA gate result** — retro: "**Veredito: LIBERADO**... first iteration, zero bugs found, zero
  fixes needed" — matches PRD's implicit characterization in § 7.4 (FR18: "Epic 22's four new screens
  had never been seen in a browser until a human ran the gate manually" — retro confirms: "This was
  the first time any of the 4 new UI screens (22.6–22.9) had ever been seen in a real browser").

---

## 4. Claims about existing skills

### 4.1 `bagual-tickets` — derived index + rebuild script (FR42)
**CONFIRMED.** `.claude/skills/bagual-tickets/SKILL.md:92`: "`{board_file}` — a **derived** index:
the source of truth is the per-ticket `.md` files... reconstructible by running
`project_controll/tickets/scripts/rebuild_board.py`." Lines 197/209/212/215 elaborate the same
mechanism (F9). FR42's claim "already halfway there — its board is documented as a derived index
with a rebuild script" is accurate, not aspirational.

### 4.2 `bagual-*` SKILL.md files already in English
**CONFIRMED, with a caveat.** All 13 `bagual-*/SKILL.md` files under `.claude/skills/` are written in
English prose. A keyword scan for common Portuguese function words found only literal domain/data
values embedded in otherwise-English sentences — ticket status enum values
(`pronto-para-implementar`, `novo`, `triado`, `em-implementacao`, `escalonar`, `trilha`), a
confirmation-field example (`sim | não | não verificado`), and one QA verdict enum
(`LIBERADO`/`COM RESSALVAS`/`BLOQUEADO`, explicitly kept in Portuguese by the skill's own text
because it's a "shared identifier defined by the pack contract"). This is consistent with — not
contradicted by — § 2.3's claim that `bagual-tickets` will be "fully rewritten in English **including
its data files**": the data (ticket statuses in `board.yaml`) is still Portuguese today; the skill
prose already is not. No PRD claim is broken here.

### 4.3 Semgrep subsystem dormant — five scripts, zero rules, no hook, no binary (§ 10 Open Questions #2)
**CONFIRMED.** `semgrep/scripts/` contains exactly five `.py` files (`compute_covered_manifest.py`,
`flag_suspected_fp.py`, `log_violations.py`, `rules_yaml_lite.py`, `sensitive_path_floor.py`) — no
more, no fewer. No `.yml`/`.yaml` rule file exists anywhere under `semgrep/` (a scoped find for
rule-file extensions returned nothing). `which semgrep` fails (binary not installed). No reference to
`semgrep` in `.claude/settings.json` or `.git/hooks`. All four sub-claims hold exactly as stated.

### 4.4 "54 tickets carry a track assigned by a classifier that has since been retired" (§ 10 Open Questions #2)
**CONFIRMED, exact count reproduced.** `project_controll/gerente/README.md:650` confirms the
classifier (`classify_trilha.py`) "is now retired as a trilha decider" since `TCK-20260727143826-7573`
(2026-07-27), and that it "funneled almost everything into `rapida`." Querying `board.yaml`
programmatically for tickets with `trilha == "rapida"` and `created` before 2026-07-27 yields **exactly
54** — an exact match to the PRD's figure. Minor nuance not spelled out in the PRD: of those 54, 50
are already `concluido` and 4 `descartado` — i.e. all closed. The "debt" here is a classification/audit
concern (never independently verified by a human), not an open-work backlog; this doesn't contradict
the PRD's wording ("carry a track... never re-triaged") but a reader could mistake "inherited debt" for
open tickets, so it's worth a one-line clarification if this section gets revised.

---

## 5. Claims about distribution (§ 7.7, FR31)

**PARTLY TRUE.** `/home/rhuanbarros/1_projetos/bagual-skills/` exists, is a real git repo (remote
`github.com/rhuanbarros/bagual-skills`), and its top level contains `bagual-spec-gate/`,
`bagual-worktree/`, `gerente-geral-system/`, `bagual-skill-forge/`, `project-templates/` — consistent
with FR31's "existing skill names are reused inside it" as a forward-looking plan (no `v2/` folder
exists yet, which is fine — FR31 describes what v2 *will* do, not a completed state).

But the payload **is** a materially diverging, stale snapshot, which matters for FR31's "existing
skill names are reused inside it": `bagual-skills/bagual-spec-gate/SKILL.md` is **3.2K**, while the
live, actively-used `gorioapp/.claude/skills/bagual-spec-gate/SKILL.md` is **26.4K** — roughly 8x
larger, reflecting substantial evolution (the gorioapp copy has since absorbed real production
learnings, e.g. the Epic 22 CRITICAL-migration hardening). `.decision-log.md` also differs (9.7K vs
7.1K). Anyone building v2 by "reusing" the bagual-skills repo's current `bagual-spec-gate`/
`bagual-worktree` content as a starting point would be starting from a substantially outdated
baseline, not the mature, battle-tested version actually running in gorioapp today. The PRD doesn't
explicitly claim the snapshot is current, but neither does it flag the drift — worth calling out
before anyone actually begins the v2 build from that repo.

---

## Summary of non-CONFIRMED findings

| # | Claim | Verdict |
|---|---|---|
| 1 | `[scm] isolation="worktree"` gitignored-config seeding is equivalent coverage to `bagual-worktree`, justifying its retirement | **PARTLY TRUE** — `bmad-loop`'s seeding covers only adapter CLI/MCP config files by default; `bagual-worktree` additionally replicates all gitignored deps/env/secrets plus the source's uncommitted diff, none of which `bmad-loop` does without manually populating the empty `worktree_seed` |
| 2 | § 10: "FR14's mechanism is no longer unknown... a working model to build against" (the hook-based wake mechanism) | **FALSE** — the hook is explicitly "silently inert" for ordinary interactive sessions per the PRD's own research source; it coordinates the orchestrator with sessions *it itself spawns*, not with an external interactive supervisor skill in the owner's own window, which is what FR14 actually needs |
| 3 | § 7.7 / FR31: `bagual-skills` repo content is a sound basis to "reuse" skill names/content into v2 | **PARTLY TRUE** — the repo exists as claimed, but its `bagual-spec-gate` payload is ~8x smaller than the live gorioapp version (3.2K vs 26.4K), a genuinely stale/diverging snapshot not flagged in the PRD |
