---
name: bagual-bmad-worktree-setup
description: 'Creates isolated git worktree for a parallel BMAD session. Use when the user wants to run multiple BMAD plans at the same time.'
---

# BMAD Worktree Setup

## Conventions
- `{project-root}`-prefixed paths resolve from the project working directory.
- `{skill-root}` resolves to this skill's installed directory.

## Overview

Create an isolated git worktree so a parallel Claude Code session can work on a separate plan without conflicting with the current session's BMAD artifacts.

## Steps

### Step 1 — Load config

Load config from `{project-root}/_bmad/bmm/config.yaml`. Store:
- `{user_name}`, `{communication_language}`, `{output_folder}`, `{project-root}`

Detect the project folder name from the last segment of `{project-root}` (e.g. `trt-aios`).

### Step 2 — Ask for session name

Ask the user in `{communication_language}` for a short session name (lowercase, no spaces, e.g. `frontend`, `api`, `novo-plano`). Sanitize the answer: lowercase, replace spaces with hyphens, remove special characters. Store as `{session-name}`.

### Step 3 — Determine paths

Calculate:
- `{worktree-path}` = `{project-root}/../{project-folder-name}-{session-name}`
  (sibling folder next to the current project)
- `{new-branch}` = `worktree/{session-name}`
- `{isolated-output}` = `_bmad-output/{session-name}`

Confirm the paths with the user before proceeding.

### Step 4 — Create git worktree

Run the following command:

```bash
git -C {project-root} worktree add -b {new-branch} {worktree-path}
```

If the branch already exists, ask the user whether to reuse it (`--force`) or choose a different name.

Confirm success before continuing.

### Step 5 — Update BMAD config inside the worktree

Read `{worktree-path}/_bmad/bmm/config.yaml`.

Update `planning_artifacts` and `implementation_artifacts` to use the isolated subfolder:

```yaml
planning_artifacts: "{project-root}/_bmad-output/{session-name}/planning-artifacts"
implementation_artifacts: "{project-root}/_bmad-output/{session-name}/implementation-artifacts"
```

**Important:** The `{project-root}` token inside the worktree config will resolve to `{worktree-path}` when the worktree session loads it — so the artifacts will be written to `{worktree-path}/_bmad-output/{session-name}/`. This keeps them fully isolated from the main session.

Write the updated file back.

### Step 6 — Commit the config change

Run:

```bash
git -C {worktree-path} add _bmad/bmm/config.yaml
git -C {worktree-path} commit -m "bmad: isolate output to {session-name} subfolder for parallel session"
```

### Step 7 — Provide instructions

Inform the user in `{communication_language}` of:

1. Worktree path: `{worktree-path}`
2. Branch: `{new-branch}`
3. BMAD artifacts will go to: `{worktree-path}/_bmad-output/{session-name}/`
4. How to open in VS Code: `code {worktree-path}`
5. How to open in Claude Code: open a new Claude Code window pointing to `{worktree-path}`
6. When done with the parallel session, to clean up:
   ```bash
   git worktree remove {worktree-path}
   git branch -d {new-branch}
   ```

## Notes

- Subagents spawned inside the worktree session (without `isolation: worktree`) operate on the worktree's filesystem paths and do NOT create additional worktrees. No cascading worktree chains.
- Subagents spawned with `isolation: worktree` create temporary worktrees from the main repo HEAD — they will not see uncommitted changes in the parent worktree. Commit config changes before delegating to such subagents.
- Never modify `_bmad/bmm/config.yaml` in the **main** project during a parallel session — changes there affect all worktrees that haven't overridden the file.

## Constraints

- Validate that `git` is available before running any git commands
- Never force-push or modify the main branch
- If the worktree path already exists, warn the user and stop
