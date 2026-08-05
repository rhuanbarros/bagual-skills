# Research 2/3 — BMad deterministic infrastructure

> Full source read of `_bmad/scripts/{resolve_customization,resolve_config,memlog}.py`, all config
> layers, 14 project overrides, `.bmad-loop/bmad_loop_hook.py` and `policy.toml`. 2026-08-04.

## The customization system

**Two resolvers, same algorithm, different scope.**

| Script | Scope | Layers |
|---|---|---|
| `resolve_customization.py` | per skill | skill `customize.toml` → `_bmad/custom/{skill}.toml` → `_bmad/custom/{skill}.user.toml` |
| `resolve_config.py` | project-wide | `_bmad/config.toml` → `config.user.toml` → `custom/config.toml` → `custom/config.user.toml` |

**Merge rules — structural, never name-aware:**
- Scalar → override wins outright.
- Dict + dict → recursive deep merge.
- List + list → shape-aware: if *every* item is a dict sharing one identifier field (`code`, then
  `id`), merge by that key — matches replace **in place, preserving base position**, new keys append.
  Otherwise plain append, base first.
- Mixing identifier keys in one array is treated as a schema smell; append-fallback is chosen over
  guessing.

🔴 **No removal primitive, by design.** An override can never delete a base item. To suppress a
default you fork the skill or neutralize the keyed entry. This keeps overrides additive and forks
rare.

**Consumption:** the skill's activation step literally shells out to the script with a dotted-path
`--key` filter. Output is JSON on stdout, UTF-8 forced (so persona emoji survive Windows cp1252).

**Fallback is written into every consuming skill, verbatim:**
> "If the script fails, resolve the block yourself by reading these three files in base → team →
> user order and applying the same structural merge rules as the resolver. Any missing file is
> skipped."

The model is the fallback interpreter of the same rules. The contract is redundant on purpose —
script preferred, but the skill never blocks on tooling absence.

## The override surface, ranked by leverage

| Surface | Merge | Leverage |
|---|---|---|
| `activation_steps_prepend` / `append` | append | **Highest.** Free-text prose spliced into the activation sequence as real instructions. This is how the whole grep-native wiki-grounding procedure was injected without forking a single step file. |
| `agent.menu` (keyed by `code`) | keyed merge | **High.** Replace a menu item's target in place, or append a new one, by re-declaring its `code`. |
| `persistent_facts` | append | **High.** `file:`-prefixed entries load whole files as always-on context. Glob-capable. |
| `on_complete` | override | High. One instruction executed at workflow end. |
| workflow scalars (paths, URLs, sources) | override | Re-point a generic skill's paths at this project's real layout. |
| `icon`/`role`/`identity`/`communication_style`/`principles` | override / append | Persona tone. |
| `name`, `title` | — | **Explicitly non-configurable.** "Create a custom agent if you need a new name." |

## Config layering — a system mid-migration

Two parallel systems coexist:
- **Legacy per-module YAML** (`_bmad/core/config.yaml`, `_bmad/bmm/config.yaml`), read directly by
  skills, no resolver. **44 skills still use this.**
- **New 4-layer TOML** via `resolve_config.py`. **6 skills use it.**

`config.toml`'s own header: *"Installer-managed. Regenerated on every install — treat as read-only.
To pin a value regardless of install answers, use `_bmad/custom/config.toml`."* The escape hatch is
structurally identical to the customize.toml pattern.

**The "load if present, sensible default, never block" contract is stated verbatim in at least three
independent skills** — it is house style, enforced textually rather than mechanically. The scripts
themselves return `{}` for a missing optional layer rather than erroring.

## Script craft

**`memlog.py` invariants:**
1. **Append-only.** There is no edit or delete subcommand at all.
2. **Write-only / blind.** Each command re-reads the file itself and echoes new state as one JSON
   line, so the caller never round-trips a read after writing.
3. **No lifecycle status field.** Completion is just another appended entry, never mutated
   frontmatter.

**Atomic write, identical in `memlog.py` and the loop hook:** temp file → `flush()` → `fsync()` →
`os.replace()`. Crash safety is a house convention, not a one-off.

**Defensive frontmatter parsing:** hand-rolled, not YAML. The closing fence is the *first line that
is exactly `---`*, so a `---` inside free text cannot truncate parsing. Embedded newlines in
frontmatter values are neutralized on write so a multi-line value can never re-break the fence.

**Shared conventions across all three scripts:**
- stdlib-only; PEP 723 `# /// script` header so `uv run` picks the interpreter; bare `python3` still
  works as transitional fallback.
- **stdout = machine contract (JSON). stderr = diagnostics.** Strictly separated.
- **Meaningful, distinct exit codes:** `0` success · `1` required input missing/unparseable · `2` CLI
  usage or state error · `3` environment failure (e.g. no `tomllib`). A caller can branch on failure
  *kind*.
- **Fail soft on optional layers, fail loud on required ones** — every loader takes `required: bool`.
- `init` is deliberately **not** idempotent (errors on existing file, to prevent data loss);
  `append`/`set` are safe to retry because each call is atomic.

## The hook — how an out-of-process orchestrator talks to an in-session agent

🔴 **This is the mechanism our loop-runner needs.** Worth reading closely.

- Registered under each CLI's native hook names (Claude: `SessionStart`/`Stop`; Gemini:
  `AfterAgent`; Copilot: `agentStop`) but the CLI always passes **one canonical event name** as
  `argv[1]`. The orchestrator never sees CLI-specific vocabulary — it is a **normalization shim**.
- **No-op guard by environment-variable tagging:** the hook checks `BMAD_LOOP_RUN_DIR` and
  `BMAD_LOOP_TASK_ID`, which are set *only* on tmux windows spawned by the orchestrator. A normal
  interactive session returns immediately. **The hook is silently inert for every ordinary session.**
  This is the actual coordination trick — no Claude-Code-specific API involved.
- When active it **atomically drops one event file** into `{run_dir}/events/{ts_ns}-{task_id}-{event}.json`.
  No stdout, no return value. Pure side-effecting file drop.
- **Coordination model:** the orchestrator never talks to the agent directly. It polls a directory of
  timestamped event files, and separately drives the session's *input* via tmux send-keys. One-way,
  write-only, stateless per invocation.

## `policy.toml` as a config-design model

**What to copy:**
- Every value commented **in place, with the why** — not just the what.
- Dangerous options guarded by inline warnings, not a separate danger-zone doc.
- Every enum lists its legal values inline right after the key.
- Escape hatches shown **commented-out and copy-paste-ready**, not merely described.
- Numeric defaults justified by observed behaviour, with issue-number provenance — e.g. "healthy
  sessions run 1–2.5M weighted, so the default trips only true runaways (#158)".
- 🔴 **Best pattern in the file: a config that explains, at the point of override, why it disagrees
  with its own tool's convention.** This repo's `.gitignore` carries a comment overriding
  bmad-loop's default gitignore of `policy.toml`, because the pinned `model = sonnet` key is
  cost-critical and a reinstall would silently revert it to Opus.

**What not to copy:** one flat 200-line file mixing genuinely user-tunable knobs with internal engine
constants. No visual separation between "read this" and "you'll never touch this". A newcomer must
read the whole file once to build a mental map.

## The 12 transferable rules

1. Three-layer override with one shared structural algorithm — never bespoke per-skill merge logic.
2. Structural merge, not name-aware: a config author predicts the outcome without knowing internals.
3. No removal primitive — overrides only add or replace.
4. Every script documents an in-agent manual fallback for its own failure, inside the consuming
   skill's instructions.
5. stdout is the sole machine contract; stderr is diagnostics only.
6. Distinct exit codes so callers branch on failure kind.
7. Atomic writes everywhere state persists.
8. Write-only/blind logging: echo new state so the caller never re-reads what it just wrote.
9. Highest-leverage overrides are free-text instruction injection plus keyed-array menu entries.
10. "Load if present, sensible default, never block" — stated every time config is touched, so the
    model does not invent stricter behaviour under ambiguity.
11. Config files justify their own deviations from tool defaults at the point of override.
12. stdlib-only + PEP 723 headers for any script meant to survive tool churn.
