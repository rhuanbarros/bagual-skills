---
name: bagual-worktree
description: Creates a git worktree with full environment parity to its source checkout, and manages a reusable POOL of N pre-warmed worktrees (create/warm, allocate, return/clean) for parallel epic execution. Use when the user says 'create a worktree', 'new worktree', 'spin off a worktree', wants a worktree pool warmed/allocated/returned, or wants to continue work in a separate VS Code window/session with everything already set up.
---

# bagual-worktree

## Overview

This skill creates a new git worktree that an agent or developer can start working in immediately — no `npm install`, no `uv sync`, no hunting for missing env files. `git worktree add` alone only carries committed history; everything gitignored (env files, `node_modules`, virtualenvs, local secrets, generated project links) and anything uncommitted in the source checkout is silently left behind. This skill pins the new worktree to the source's exact current commit, then replicates both categories — while skipping known noise (build/test caches, prior session logs, other worktrees) — so the new worktree is a working replica of the source, not just a git-history replica.

It has two modes: **single ad hoc worktree** (below, unchanged — for a person or agent to keep working in a new VS Code window) and **pool manager** (Story E11.1, own section further down — for the `bagual-epic-runner` supervisor to allocate/return reusable worktrees to genuinely parallel Tracks). Same hydration machinery underneath (`copy_ignored_artifacts.py`), different lifecycle around it.

## Conventions

- Bare paths (e.g. `scripts/copy_ignored_artifacts.py`) resolve from the skill root.
- `{skill-root}` resolves to this skill's installed directory.
- `{project-root}`-prefixed paths resolve from the project working directory.

## On Activation

Load available config from `{project-root}/_bmad/config.yaml` and `{project-root}/_bmad/config.user.yaml` if present. Use sensible defaults for anything not configured.

## Gather Inputs

The source is the git checkout the user is currently working in (its repo root, found via `git rev-parse --show-toplevel`) — if that checkout is itself a worktree, it's still a valid source; its own already-copied artifacts carry forward. Get a short purpose/name for the new worktree from the user if not already given — it becomes both the directory name and the branch name. Destination defaults to `{project-root}/.claude/worktrees/{name}`, matching this project's existing convention; only deviate if the user asks for a different location.

## Create the Worktree

Pin the new branch to the source's exact current commit — never a remote ref. Tools like the harness's own worktree-creation helper can default to branching from `origin/<default-branch>`, which silently diverges from local state whenever the source has unpushed commits; pinning to the literal local `HEAD` sidesteps that entirely and is what "a worktree identical to what I have right now" actually requires:

```bash
git worktree add {dest} -b {branch-name} $(git -C {source} rev-parse HEAD)
```

If `{source}` has uncommitted changes, mention that now — the next step forks that working state into two places, which the user should be aware of before it happens silently.

## Replicate Everything the Original Has

```bash
uv run scripts/copy_ignored_artifacts.py {source} {dest}
```

This hardlink-copies every gitignored path except a built-in noise list, applies the source's uncommitted tracked-file diff to `{dest}`, and copies untracked-but-not-ignored files. Read the JSON summary from stdout and report: what was copied (group by top-level path — e.g. "node_modules, .venv, 4 env files" rather than every individual file), whether uncommitted changes applied cleanly, and anything in `skipped_excluded` only if the user asks what was left out. If `uncommitted.applied` is `false` with a `patch_saved_at`, surface that plainly — the user's uncommitted work needs manual attention, not a silent drop.

Pass `--exclude {path}` (repeatable) for anything project-specific the user wants left out of this particular worktree; pass `--skip-uncommitted` only if the user explicitly wants a clean-HEAD worktree despite having local changes.

## Verify

Spot-check that what got copied actually runs — invoke a binary or interpreter the copy just placed (a copied virtualenv's `python --version`, a copied `node_modules/.bin` tool's `--version`, etc. — whatever runtime artifacts are actually present in this repo). A failure here is usually a stale absolute path baked into the copy (most common with Python virtualenvs); the fix is re-running that environment's own setup command (`uv sync`, `npm install`) inside `{dest}`, not re-copying the files.

## Report, Then Stop

Give the user the worktree's absolute path, its branch name, and how to open it: a new VS Code window with `{dest}` as its folder (`code {dest}`, or File → Open Folder). A new session started there has the full environment already in place — flag explicitly if verification found something that still needs a manual install.

**Do not continue implementation work in this conversation after this point — hand off explicitly instead.** `cd`ing into `{dest}` from this session does not move the session into the worktree: this session's other tools (file edits, subsequent shell calls) can keep resolving paths against the original checkout regardless of the shell's current directory, so work meant for `{dest}` can silently land in the wrong checkout instead — confirmed firsthand building this very skill. The only reliable way to actually work in the new worktree is a fresh session rooted there.

State this plainly to the user, then give them a ready-to-paste prompt for that new window's session — summarize whatever task was in progress in this conversation (the concrete next step, and any command/story/identifier needed to resume it) so pasting it into the new window continues exactly where this one left off. If nothing was in progress (the worktree was created standalone), skip the prompt.

---

## Pool Mode (Story E11.1 — PRD 03 FR-5b)

The single-worktree flow above creates ONE ad hoc worktree and hands it off — right for a person opening a new VS Code window. Real parallelism (`bagual-epic-runner` running disjoint Tracks concurrently, Epic E11) instead needs a **reusable pool**: N worktrees kept hydrated and ready, checked out (`allocate`) to a Track for the duration of its work, and cleaned + checked back in (`return`) when it finishes — so hydration cost is paid once per pool worktree's lifetime, not once per epic.

**This is deliberately NOT the Agent tool's native `isolation: worktree`.** That mode is auto-disposable — it destroys the worktree when the sub-agent exits, which is incompatible with a pool meant to survive and be reused across many epics. The pool is built on the same `git worktree add` + `copy_ignored_artifacts.py` primitives as the single-worktree flow above, just with a persistent lifecycle wrapped around them.

**Pool is owned by this skill; the supervisor only requests/returns.** `bagual-epic-runner` (wired in Story E11.4) never creates or cleans a worktree itself — it calls `allocate` when a Track needs one and `return` when the Track finishes, full stop. Deciding **when** to call `allocate` is the supervisor's job, not this script's: **sequential epics within the same Track do NOT get their own worktree** (they keep running in the root checkout, exactly as today) — only genuinely parallel Tracks pay the worktree cost. This script has no notion of "Track" at all; it only serves requests.

### Script: `scripts/pool_manager.py` (+ `scripts/pool_registry.py`, Story E11.2; `scripts/pool_health.py`, Story E11.3)

Stdlib-only. Subcommands (each prints a JSON report to stdout). State ownership
since Story E11.2: `pool_manager.py` still owns git worktree creation and
hydration; ALL state (`registry.yaml`, the lease/heartbeat model, the
TOCTOU-safe mutex, orphan reclaim) lives in `pool_registry.py`, imported
directly by `pool_manager.py` — a single source of truth, never two copies of
the state logic. Since Story E11.3, `pool_manager.py`'s `allocate` also runs
the MANDATORY health-check (`pool_health.py`, see next section) on every
candidate before returning it. `heartbeat`/`return`/`reclaim-orphan`/`list`/
`status` below are thin CLI wrappers on `pool_manager.py` that delegate
straight to `pool_registry.py`; you can also invoke `pool_registry.py`
directly for those five (same behavior, one file fewer in the call chain) —
**but NOT for `allocate`**: `pool_registry.py`'s own `allocate` is the raw,
UN-health-checked lease primitive (no dep-hash comparison, no `.venv`
revalidation, no smoke build) — `pool_manager.py allocate` is the only
supported entry point for a caller that needs a worktree it can trust.

| Subcommand | Does |
|---|---|
| `create` (alias `warm`) | Create + hydrate N new pool worktree(s). `--count N` (default 1) or `--fill` (top up to configured pool size). `--from-scratch` skips hydration entirely (strategy 1 fallback — see below). Registers each as `livre`. |
| `allocate` | **Lease + health-check** one worktree: a free pre-warmed one if available (TOCTOU-safe `livre -> em-uso`), else hydrate one on the spot (copy-on-demand, still TOCTOU-safe). Requires `--owner` (the Track/epic identity); `--label` is a free-text tag; `--base-branch` (default `staging`) is what dep hashes are compared against and re-hydration resets onto. Runs the MANDATORY health-check (Story E11.3, F17 — see next section) on the candidate; if it fails and can't be sanitized, the candidate is marked `suja` and another is tried, up to `health.max_allocation_attempts` (config, or `--max-attempts`). Returns a `token` the caller MUST hold onto — `heartbeat`/`return` require it — plus a `health_check` object reporting what the gate found/did. |
| `heartbeat` (alias `refresh-lease`) | A live Track touches its lease (`name`, `--token`). Call this every `lease.heartbeat_interval_minutes` (config, see below) for as long as the Track is alive — **this is what keeps a long epic from ever being mistaken for a crash**. |
| `return` (alias `clean`) | Deterministically reset a worktree and mark it `livre` again (or `suja` if cleanup failed). Requires `--token` (the lease holder) unless `--force` (manual admin override). |
| `reclaim-orphan` | Scan for `em-uso` entries whose heartbeat has gone **silent** past `lease.stale_after_minutes` — reclaim (destroy + free/suja) ONLY those. `--dry-run` reports without mutating. Omit `name` to scan the whole pool; pass a name to target one. |
| `list` / `status` | Show every pool worktree + its state, with live staleness computed for every `em-uso` entry. `status --name X` scopes to one. |
| `remove` | Permanently delete a pool worktree (git worktree remove + branch delete + registry row removal). Refuses on a leased (`em-uso`) worktree unless `--force`. |

All subcommands accept `--project-root` (default: `git rev-parse --show-toplevel` of cwd) and `--pool-dir` (default: from config, see below).

### Lease + heartbeat model (Story E11.2 — PRD 03 FR-5c, hardening F16)

Allocation is an **exclusive lease**, not just a state flag: `allocate` mints a
fresh `token` bound to an `owner` (the Track/epic identity) and stamps
`lease_acquired_at` + `heartbeat_at`. Two epics running in parallel can never
receive the same worktree — the pick-a-free-worktree + mark-it-leased sequence
happens under ONE mutex acquisition (`registry.yaml`'s own lock file,
O_CREAT|O_EXCL), so two concurrent `allocate` calls are fully serialized
around that decision; whichever wins the mutex always sees the other's write
first. Proven with 3 REAL concurrent OS processes racing `allocate` against a
3-worktree pool: 3 distinct worktrees, every time (see
`ideias/sistema-artifacts/E11-2-lease-heartbeat.md` for the actual run).

**Orphan detection is heartbeat-silence, NEVER lease age (F16, the reason this
story exists).** A Track that keeps calling `heartbeat` every few minutes can
run for hours without ever being mistaken for a crash — `reclaim-orphan` only
flags (and only ever destroys) an `em-uso` entry whose heartbeat has gone
silent longer than `lease.stale_after_minutes`. This reuses `gerente_state.py`'s
`lock_is_stale` (Story E8.2, PRD 00 F9) UNMODIFIED, via the same direct-file-
import technique `gerente_state.py` itself uses to reuse `memlog.py` — the
SAME heartbeat-silence primitive, not a second timeout model. Destructive
cleanup (`git reset --hard` + `git clean -fd`) only ever runs on an entry
`reclaim-orphan` has independently proven stale — twice, in fact: once from
the initial scan and once again immediately before the destructive step, to
narrow the window against a heartbeat landing mid-reclaim.

```
uv run scripts/pool_manager.py allocate --owner track-A --label "epic 42"
# → {"name": "pool-1", "token": "…", "path": "…", …}
# ... Track does its work, calling every N minutes: ...
uv run scripts/pool_manager.py heartbeat pool-1 --token <token>
# ... Track finishes: ...
uv run scripts/pool_manager.py return pool-1 --token <token>

# Reaper/supervisor sweep (nightly, or before allocating if the pool looks tight):
uv run scripts/pool_manager.py reclaim-orphan --dry-run   # report only
uv run scripts/pool_manager.py reclaim-orphan             # actually reclaim silent leases
```

### Config — `_bmad/config.yaml`

```yaml
bagual_worktree:
  pool:
    size: 2                              # default if unset
    location: .claude/worktrees/pool      # default if unset, relative to project root
    lease:
      heartbeat_interval_minutes: 5       # default if unset — how often a live Track should call `heartbeat`
      stale_after_minutes: 20             # default if unset — heartbeat silence threshold before reclaim-orphan will touch a lease
    health:                               # Story E11.3 (F17) — health-check on allocation
      max_allocation_attempts: 3          # default if unset — bounds the suja-and-retry loop in `allocate`
      smoke:
        frontend_command: "npm run build:client"  # default if unset — fast client-only build, no SSR/prerender
        backend_import: "ai_update"                # default if unset — the real local editable package (F17's confirmed subject)
        timeout_seconds: 300               # default if unset — per smoke-command timeout
```

Same "load if present, sensible defaults otherwise" contract every other
bagual-*/bmad-* skill follows — this repo does not have a `_bmad/config.yaml`
yet, so all keys currently run on defaults.

### 3 strategies by preference (PRD 03 FR-5b)

1. **(3) Pre-warmed pool — preferred.** `allocate` hands out an already-hydrated free worktree. Zero hydration cost paid at allocation time.
2. **(2) Copy-on-demand — pool exhaustion only.** No free worktree exists: `allocate` hydrates one right now via `copy_ignored_artifacts.py`, same as `create` does. Cost is paid only when the graph's parallelism exceeds the pool size, never for every epic.
3. **(1) From-scratch — manual correction fallback.** `create --from-scratch` skips the hardlink-copy entirely, leaving a bare `git worktree add` for a real `npm install`/`uv sync`. Never the default for `create` or `allocate` — reach for it only if the hydration copy itself is somehow unusable.

### Lifecycle

```
uv run scripts/pool_manager.py create --fill                       # top up pool to configured size
uv run scripts/pool_manager.py allocate --owner track-A --label epic-track-A
# ... Track does its work in the returned {path}, heartbeating every N min ...
uv run scripts/pool_manager.py return pool-1 --token <token>        # or: clean pool-1 --token <token>
uv run scripts/pool_manager.py list
uv run scripts/pool_manager.py remove pool-1                        # shrink pool / teardown
```

**`return` cleans deterministically**, so a returned worktree is truly reusable, never dirty for the next allocation:
1. `git reset --hard {tip of local staging}` — discards any commits made on the worktree's own branch during the allocation AND re-points that branch at the current `staging` tip.
2. `git clean -fd` — removes untracked, non-ignored cruft. Deliberately **not** `-x`: gitignored artifacts (`node_modules`, `.venv`, env files, and anything else generated during the allocation, e.g. a fresh `frontend/dist/` from a build) are preserved on purpose — destroying them would defeat the entire point of a pre-warmed pool.
3. State flips `em-uso → livre` (or `→ suja` if either cleanup step fails — pulled out of rotation until reaped/removed, never silently handed out dirty).

**Why not literally `git checkout staging`** (the PRD's shorthand wording): git refuses to check out a branch that's already checked out in another worktree, and the root checkout already has `staging` checked out. Every pool worktree instead carries its own dedicated branch (`worktree-pool-{name}`) that gets hard-reset onto staging's current tip on return — same end state (worktree content == current staging), no branch collision.

### F17 — the `.venv` caveat (read before assuming the pool is free for Python too)

The hardlink copy of a Python virtualenv carries **absolute paths** that still point at the SOURCE checkout — most visibly, `uv`-installed console-script shebangs (e.g. `.venv/bin/pytest`) and, for a project with an editable local package, `uv`'s own record of where that package lives. `node_modules` has no equivalent problem (node resolves relative to the requiring file, not a recorded absolute prefix) — **the pool's unconditional real win is `node_modules`**; for `.venv` it's partial.

Confirmed by running this script for real against this repo (Story E11.1 testing, see `ideias/sistema-artifacts/E11-1-pool-gerente.md`): a freshly hydrated worktree's `.venv/bin/python --version` and even `import fastapi` worked immediately (the interpreter binary itself is a symlink to a stable, external `uv`-cached Python, unaffected by the copy). But `uv run python ...` from inside the copied worktree **did** trigger a real rebuild step ("Building ai-backend @ file:///.../pool-1/backend", "Uninstalled 1 package", "Installed 1 package") — `uv` detected the local package's install record still pointed at the source path and re-synced it. **`uv sync` (or the implicit resync `uv run` performs) on allocation is the common path, not a rare fallback** — this is exactly F17 as hardened in `ideias/revisao-adversarial-furos.md` and `ideias/prd-03-execucao-epics.md` §FR-5c. `pool_manager.py`'s `create`-time `smoke_check` reports the copied interpreter's basic health (best-effort, non-fatal, informational only); the MANDATORY revalidation gate is `pool_health.py`, run on every `allocate` — see next section.

### Health-check on allocation (Story E11.3 — PRD 03 FR-5c hardening F17: "the pool goes stale")

`allocate` runs `scripts/pool_health.py`'s `run_health_check` on EVERY candidate — prewarmed or copy-on-demand — before handing it back. Three checks, always in this order, never skipped:

1. **Dep-hash vs `staging` HEAD.** Hashes `frontend/package.json` + lockfile(s) + `backend/pyproject.toml` + `uv.lock` as they exist in the worktree right now against the SAME files' content at the current `staging` HEAD (`git show <sha>:<path>`, never touching the worktree until a real divergence is confirmed — a manifest's absence counts as part of the hash too, not silently skipped). Diverged → re-hydrate: `pool_registry.cleanup_worktree` (the SAME `git reset --hard <staging tip>` + `git clean -fd` primitive `return`/`reclaim-orphan` already use) brings the tracked manifests current, then the hydration copy (`copy_ignored_artifacts.py`, via the same `hydrate()` wrapper `create`/copy-on-demand already use) re-runs to refresh the gitignored `node_modules`/`.venv` copies to match.
2. **`.venv` revalidation — ALWAYS, unconditionally**, dep-hash divergent or not. Runs `uv run python -c "import <backend_import>"` for REAL inside `backend/` — the real invocation path, never the naive `.venv/bin/python` direct-binary shortcut (which is a documented false positive, see the F17 section above and `notes.md`). On failure, runs `uv sync` once and retries the same import once more — F17's documented common path. This call also satisfies the "Python import" half of the smoke check (running it a second time would repeat the identical signal for no additional confidence).
3. **Frontend smoke build.** A real `npm run build:client` (configurable) inside `frontend/`.

Any irrecoverable failure → the candidate is marked `suja` (via the existing `mark_returned(cleanup_ok=False)` — no new registry state) and pulled out of rotation; `allocate` tries another candidate, up to `health.max_allocation_attempts` (config, default 3, or `--max-attempts`) — bounded, never infinite, so a genuinely broken `staging` fails loudly instead of silently manufacturing broken worktrees forever. `allocate` never returns an unchecked worktree.

Real run against this repo (throwaway scratch pool, never `.claude/worktrees/`): a freshly-created prewarmed worktree allocated cleanly in ~10s with `venv.attempts: 1, resynced: true` (the F17 resync happened via plain `uv run`, no explicit `uv sync` needed this time) and a real `npm run build:client` finishing in ~5s. A worktree deliberately pinned behind a fabricated commit with a modified `backend/pyproject.toml` (built via `git commit-tree`/`git mktree` plumbing only — no working-tree mutation of the real repo) was correctly flagged `dep_hash.diverged: true`, re-hydrated, and its `backend/pyproject.toml` on disk verified to match the new target content afterward — full details in `ideias/sistema-artifacts/E11-3-health-check.md`.

### Seams left for later stories (do not build ahead of them)

- **E11.4 (wiring the supervisor) — DONE.** `bagual-epic-runner/workflow.md`'s Step 0P now calls `allocate` per parallel Track (deciding *when* a Track gets a worktree), instructs each Track-Agent to call `heartbeat` itself at the end of every epic it finishes, and runs `reclaim-orphan` once before dispatching a batch of parallel Tracks. One finding from E11.4's own testing worth flagging here: this skill's docs (and the PRD) assumed a background Agent could be **rooted** at an existing pool worktree via the harness's `EnterWorktree(path=...)` tool — real adversarial testing showed this does NOT work for a pre-existing, externally-created worktree (refused outright from an unpinned session; split-brained from an `isolation: worktree`-pinned one). `bagual-epic-runner` works around this with strict absolute-path discipline instead (every tool call fully-qualified at `{dest}`, never a bare `cd`) — proven with zero leakage across 3 real concurrent background Agents. See `ideias/sistema-artifacts/E11-4-ancoragem-paralelismo.md` for the full probe transcripts. This skill's own `allocate`/`heartbeat`/`return` contract did not need to change because of this — the gap was purely in how the CALLER roots itself, not in anything this skill exposes.
- **E11.5 (merge automático) — DONE.** `bagual-epic-runner/workflow.md`'s new Step 0P.5 is the "later process" the note above pointed to: it merges each successful Track's branch (read from `allocate`'s own `branch` field, not re-derived) into `staging`, one at a time, then calls `pool_manager.py return --base-branch staging` for each Track ONLY after that Track's merge is durably confirmed by the post-merge integrated gate (never before — a `return` before the gate would `git reset --hard` a worktree whose commits might still need a closer look if the gate fails). A Track whose merge conflicts unexpectedly, or whose contribution the post-merge gate reverts, is left allocated/un-returned on purpose, same as an E11.4 FAILURE report — nothing new asked of this skill's own `allocate`/`heartbeat`/`return` contract. See `ideias/sistema-artifacts/E11-5-merge-automatico.md` for the merge mechanism itself (a new script, `bagual-epic-runner/scripts/merge_manager.py` — owned by the epic-runner skill, not this one, since merging is orchestration, not worktree lifecycle).
- **E11.6 (conflito residual) — DONE.** `merge_manager.py merge-track` gained a conservative, all-or-nothing conflict-resolution ladder: before aborting an unexpected conflict, it now tries ONE more documented-safe class — import-reorder-only conflicts (every non-blank line on both sides of every hunk in a `.py`/`.ts`/`.tsx`/`.js`/`.jsx`/`.mjs` file is an import statement) — and only if EVERY unexpectedly-conflicted path in that merge qualifies; a single non-qualifying path means nothing is touched and the merge aborts exactly as before. A new `assert-clean` subcommand adds a raw textual scan (independent of git's own conflict bookkeeping) for the SM-2=0 guardrail (owner never sees a `<<<<<<<` marker), called by `merge-track` itself right before every commit, and again by Step 0P.5 as a second, independent checkpoint after every merge attempt. See `ideias/sistema-artifacts/E11-6-conflito-residual.md` for the full mechanism and real-branch test proof (a real safe-class auto-resolve, a real non-safe abort with zero marker ever committed, a real "mixed resolvable+non-resolvable" merge aborting entirely, and a positive control proving `assert-clean` actually detects an injected marker).
- **E11.7 (isolamento de dados no QA paralelo) — DONE, LAST story of Epic E11.** A new orchestrator-owned script, `bagual-epic-runner/scripts/track_qa_isolation.py`, derives each Track's QA identity (MCP slot, dev ports, `QA-T{i}-` data prefix, `qa.{pro,admin}.t{i}@domus.test` logins, `local-t{i}` target/marker name) from `dispatch_index` — the Track's POSITION in the flattened `{parallel_tracks}` list, never its `track_id` (which restarts per `sprint_status_group` and can repeat once 2+ groups are combined — the adversarial finding this story's own tests exist to prove against). Nothing changed in THIS skill's own `allocate`/`heartbeat`/`return` contract or pool registry — the worktree it already hands out is, by construction, already a distinct filesystem path per Track, which is what per-Track `qa-pack` isolation piggybacks on; the gap this story closed lived entirely in the gitignored `qa-pack/access/` content the hydration step hardlinks (would otherwise share one test identity across every Track) and in the QA skills' own MCP-slot/target defaults (would otherwise assume it owns the whole pool). See `ideias/sistema-artifacts/E11-7-isolamento-dados-qa.md` for the full mechanism, the cross-group collision test (25 entries / 5 fake groups, zero collision across 11 derived fields), and the pool-exhaustion HALT guard. **Epic E11 (real parallelism) is now 7/7 — closed. This also closes the whole meta-orchestrator system, Epics E1–E11.**
