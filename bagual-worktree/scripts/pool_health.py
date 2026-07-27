#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""pool_health.py — MANDATORY allocation health-check (Story E11.3, PRD 03
FR-5c hardening F17: "the pool goes stale").

`pool_manager.py`'s `allocate` (E11.1/E11.2) hands out a pre-warmed pool
worktree as-is, trusting whatever hydration last put there — documented
explicitly as a seam left for this story in both `pool_manager.py`'s and
`pool_registry.py`'s own docstrings. That trust is wrong in exactly the
scenario the pool exists to serve: `staging` keeps moving between when a
worktree was warmed (or last returned) and when it is allocated hours/days
later — a dependency can be added, a package can be bumped, the local
editable package's install record can drift. A Track that gets handed a stale
worktree fails silently downstream (wrong deps, broken `.venv`) with no signal
at allocation time. This module is the mandatory gate that closes that gap.

Three checks, always run in this order on EVERY `allocate` (never skipped,
never best-effort only) — see `run_health_check()`:

  1. **Dep-hash vs `staging` HEAD.** Hash `frontend/package.json` +
     lockfile(s) + `backend/pyproject.toml` + `uv.lock` as they exist in the
     worktree RIGHT NOW against the same files' content at the CURRENT
     `staging` HEAD (via `git show <sha>:<path>`, never touching the worktree
     until a real divergence is confirmed). A worktree's dep manifests are
     git-TRACKED files — `pool_registry.cleanup_worktree()`'s `git reset
     --hard <staging tip>` (the exact same primitive `return`/`reclaim-orphan`
     already use) already brings those tracked files current; what a plain
     reset does NOT do is refresh the gitignored `node_modules`/`.venv`
     copies to match the new deps, so re-hydration re-runs the hydration copy
     (`copy_ignored_artifacts.py`, via the caller's own `hydrate_fn` — see
     below) right after the reset.
  2. **`.venv` revalidation — ALWAYS, unconditionally, dep-hash divergent or
     not.** Confirmed in Story E11.1 (`notes.md` "F17 confirmado na
     prática..."): a freshly hydrated `.venv` interpreter binary runs FINE in
     isolation (`.venv/bin/python --version` is a false-positive smoke test —
     it never exercises the layer that actually breaks). The layer that
     breaks is `uv`'s own install record for the LOCAL EDITABLE package
     (`ai-backend` in this repo), which still points at the SOURCE checkout's
     absolute path after a hardlink copy. The only test that actually proves
     anything is invoking the SAME real command the product uses — `uv run`
     — which is exactly what triggers `uv`'s automatic resync. If that still
     fails (a genuinely broken `.venv`, not just a stale install record),
     `uv sync` is run explicitly and the import is retried ONCE more. This
     call IS the "run the interpreter" AC and IS the backend half of the
     "smoke check before handover" AC — running the identical real
     invocation twice would just repeat the same signal for zero additional
     confidence, so both ACs are satisfied by this one call (documented here
     explicitly so it does not read as a skipped AC).
  3. **Frontend smoke build.** A fast, configurable `npm run <script>`
     (default `build:client` — the client-only build, no SSR/prerender,
     `frontend/agents.md`/root `AGENTS.md` confirm it is the fast variant)
     run for real inside the worktree's `frontend/`.

Any of the three failing IRRECOVERABLY (re-hydrate itself fails; `.venv`
still broken after `uv sync`; the smoke build fails) means this worktree
cannot be sanitized — the caller (`pool_manager.py`'s `cmd_allocate`) marks it
`suja` via `pool_registry.mark_returned(..., cleanup_ok=False)` (the EXISTING
primitive already used by `return`/`reclaim-orphan` for the identical
"couldn't get this worktree back to a trustworthy state" outcome — no new
registry state, no new primitive) and tries again. `allocate` never returns
an unchecked worktree.

Honesty about cost (F17, restated because it is easy to read past): for the
`.venv`, `uv sync` on allocation is the COMMON path, not a rare fallback —
this module does not pretend the hardlink copy alone is sufficient for
Python. The pool's unconditional, zero-marginal-cost win remains
`node_modules`.

This module is a LIBRARY, not a CLI — it has no `argparse`/`main()`. It is
imported by `pool_manager.py` (the same direct-file-import technique already
used a third time by this same skill for `pool_registry.py`, and documented
in `notes.md` as reusable to a further module — this is that further module)
and takes `hydrate_fn` as a parameter rather than importing `pool_manager.py`
itself, specifically to avoid a two-way import cycle between the two
sibling scripts (`pool_manager` -> `pool_health` -> `pool_manager`) while
still reusing the EXACT SAME hydration wrapper `pool_manager.py`'s `create`/
`allocate` already use (never a second copy of that ~15-line subprocess
wrapper around `copy_ignored_artifacts.py`).
"""

from __future__ import annotations

import hashlib
import importlib.util
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Optional

# ── reuse pool_registry.py (sibling file, direct import — same technique
#    pool_manager.py itself already uses for this exact file) — never a
#    second copy of cleanup_worktree/run_git/git_out ─────────────────────────
def _load_pool_registry():
    path = Path(__file__).resolve().parent / "pool_registry.py"
    spec = importlib.util.spec_from_file_location("pool_registry_for_pool_health", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pool_registry = _load_pool_registry()


# ── dep-hash comparison ────────────────────────────────────────────────────

# Fixed catalog of dependency-manifest files this project actually has.
# A file's ABSENCE is itself part of the hash (a manifest being deleted or
# newly added between warm-time and allocation is a real divergence too) —
# never silently skipped.
DEP_FILES: tuple[str, ...] = (
    "frontend/package.json",
    "frontend/package-lock.json",
    "frontend/pnpm-lock.yaml",
    "frontend/yarn.lock",
    "backend/pyproject.toml",
    "backend/uv.lock",
)

_ABSENT = "ABSENT"


def _digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _digest_worktree_file(dest: Path, relpath: str) -> str:
    p = dest / relpath
    if not p.exists():
        return _ABSENT
    return _digest_bytes(p.read_bytes())


def _digest_git_ref_file(project_root: Path, ref_sha: str, relpath: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(project_root), "show", f"{ref_sha}:{relpath}"],
        capture_output=True,
    )
    if proc.returncode != 0:
        return _ABSENT
    return _digest_bytes(proc.stdout)


def dep_hash_diverged(dest: Path, project_root: Path, ref_sha: str) -> tuple[bool, dict[str, Any]]:
    """Compares `hash(package.json + lockfile + pyproject.toml + uv.lock)` as
    they exist in the worktree right now vs. the SAME files' content at
    `ref_sha` (the current `staging` HEAD, resolved by the caller). Returns
    `(diverged, detail)` — `detail["per_file"]` always lists every DEP_FILES
    entry so a caller/log can see exactly which manifest(s) moved, not just a
    single opaque combined hash."""
    per_file: dict[str, dict[str, Any]] = {}
    any_diff = False
    for relpath in DEP_FILES:
        worktree_digest = _digest_worktree_file(dest, relpath)
        ref_digest = _digest_git_ref_file(project_root, ref_sha, relpath)
        same = worktree_digest == ref_digest
        per_file[relpath] = {
            "worktree": worktree_digest,
            "staging_head": ref_digest,
            "same": same,
        }
        if not same:
            any_diff = True
    return any_diff, {"per_file": per_file, "compared_against": ref_sha}


# ── `.venv` revalidation (F17) — the real `uv run` invocation, never the
#    naive direct-binary shortcut that produces a false positive ───────────

DEFAULT_BACKEND_IMPORT = "ai_update"  # the real local editable package (F17's
# confirmed subject — see module docstring point 2); NOT `fastapi` (a
# third-party dep, whose install record does not carry the source's absolute
# path the way the local editable package's does).
DEFAULT_FRONTEND_SMOKE_COMMAND = "npm run build:client"
DEFAULT_SMOKE_TIMEOUT_SECONDS = 300.0
DEFAULT_MAX_ALLOCATION_ATTEMPTS = 3


def _looks_like_uv_resync(output: str) -> bool:
    """Best-effort detection of uv's own resync chatter (`Uninstalled ...
    Installed ...` / `Building <pkg> @ file://...`), confirmed verbatim in
    Story E11.1's real test — informational only (never gates pass/fail;
    returncode is the only thing that does that)."""
    lowered = (output or "").lower()
    return any(marker in lowered for marker in ("uninstalled", "installed", "building "))


def revalidate_venv(dest: Path, health_config: dict[str, Any]) -> dict[str, Any]:
    """ALWAYS called, unconditionally — dep-hash divergent or not (a `.venv`
    can be stale even when the tracked manifests match, e.g. a fresh
    copy-on-demand hydration that hasn't been exercised via `uv run` yet).
    Runs `uv run python -c "import <backend_import>"` for real inside
    `dest/backend`. On failure, runs `uv sync` once and retries the same
    import once more — F17's documented common path, not a rare fallback.
    Returns `{"ok": bool, ...}`; `ok: False` means the worktree cannot be
    sanitized by this gate."""
    backend_dir = dest / "backend"
    if not (backend_dir / "pyproject.toml").exists():
        return {"ok": True, "skipped": True, "reason": "no backend/pyproject.toml in this worktree"}

    smoke_cfg = health_config.get("smoke", {})
    module = smoke_cfg.get("backend_import", DEFAULT_BACKEND_IMPORT)
    timeout = smoke_cfg.get("timeout_seconds", DEFAULT_SMOKE_TIMEOUT_SECONDS)

    uv_bin = shutil.which("uv")
    if uv_bin is None:
        return {"ok": False, "reason": "`uv` binary not found on PATH — cannot revalidate `.venv` via the real invocation path"}

    def _try_import() -> subprocess.CompletedProcess:
        return subprocess.run(
            [uv_bin, "run", "python", "-c", f"import {module}"],
            cwd=str(backend_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    try:
        first = _try_import()
    except subprocess.TimeoutExpired:
        return {"ok": False, "reason": f"`uv run` import of `{module}` timed out after {timeout}s"}

    if first.returncode == 0:
        return {
            "ok": True,
            "attempts": 1,
            "resynced": _looks_like_uv_resync(first.stderr),
            "uv_sync_ran": False,
            "output": (first.stderr or "")[-500:],
        }

    # F17 common path: the plain `uv run` did not self-heal — force `uv sync`.
    try:
        sync = subprocess.run(
            [uv_bin, "sync"], cwd=str(backend_dir), capture_output=True, text=True, timeout=timeout
        )
        second = _try_import()
    except subprocess.TimeoutExpired:
        return {"ok": False, "reason": f"`uv sync` (or the retry) timed out after {timeout}s"}

    if second.returncode == 0:
        return {
            "ok": True,
            "attempts": 2,
            "resynced": True,
            "uv_sync_ran": True,
            "uv_sync_output": (sync.stdout + sync.stderr)[-500:],
            "output": (second.stderr or "")[-500:],
        }

    return {
        "ok": False,
        "attempts": 2,
        "uv_sync_ran": True,
        "uv_sync_output": (sync.stdout + sync.stderr)[-500:],
        "first_error": (first.stdout + first.stderr)[-500:],
        "second_error": (second.stdout + second.stderr)[-500:],
        "reason": "`.venv` still broken after `uv sync` retry",
    }


# ── frontend smoke build ───────────────────────────────────────────────────


def smoke_frontend_build(dest: Path, health_config: dict[str, Any]) -> dict[str, Any]:
    """The delivered worktree passes a fast `npm run build` (default
    `build:client`, see `DEFAULT_FRONTEND_SMOKE_COMMAND`) BEFORE it is handed
    back to the caller. Configurable via `_bmad/config.yaml`
    (`bagual_worktree.pool.health.smoke.frontend_command`)."""
    frontend_dir = dest / "frontend"
    if not (frontend_dir / "package.json").exists():
        return {"ok": True, "skipped": True, "reason": "no frontend/package.json in this worktree"}

    smoke_cfg = health_config.get("smoke", {})
    command = smoke_cfg.get("frontend_command", DEFAULT_FRONTEND_SMOKE_COMMAND)
    timeout = smoke_cfg.get("timeout_seconds", DEFAULT_SMOKE_TIMEOUT_SECONDS)

    npm_bin = shutil.which("npm")
    if npm_bin is None:
        return {"ok": False, "reason": "`npm` binary not found on PATH"}

    args = shlex.split(command)
    if args and args[0] == "npm":
        args[0] = npm_bin

    try:
        proc = subprocess.run(args, cwd=str(frontend_dir), capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "reason": f"smoke command timed out after {timeout}s", "command": command}

    return {
        "ok": proc.returncode == 0,
        "command": command,
        "returncode": proc.returncode,
        "output": (proc.stdout + proc.stderr)[-1500:],
    }


# ── orchestrator ────────────────────────────────────────────────────────────

HydrateFn = Callable[[Path, Path, Path, bool], dict[str, Any]]


def run_health_check(
    project_root: Path,
    dest: Path,
    pool_dir: Path,
    base_branch: str,
    config: dict[str, Any],
    hydrate_fn: Optional[HydrateFn],
) -> dict[str, Any]:
    """The MANDATORY gate `pool_manager.py`'s `cmd_allocate` runs on every
    single allocation, prewarmed or copy-on-demand, no exceptions. Returns
    `{"healthy": bool, "reason": str|None, "steps": {...}}`. `hydrate_fn`
    matches `pool_manager.hydrate`'s signature
    `(project_root, dest, pool_dir, skip_uncommitted) -> dict` — passed in by
    the caller rather than imported here, to avoid a two-way import cycle
    between `pool_manager.py` and this module (see module docstring)."""
    report: dict[str, Any] = {"steps": {}}

    staging_sha = pool_registry.git_out(project_root, "rev-parse", base_branch)
    report["compared_against"] = staging_sha

    # 1. Dep-hash vs staging HEAD -> re-hydrate on divergence.
    diverged, dep_detail = dep_hash_diverged(dest, project_root, staging_sha)
    report["steps"]["dep_hash"] = {"diverged": diverged, **dep_detail}

    if diverged:
        if hydrate_fn is None:
            report["healthy"] = False
            report["reason"] = "dep hash diverged from staging HEAD but no hydrate_fn was supplied to re-hydrate"
            return report

        cleanup = pool_registry.cleanup_worktree(dest, project_root, base_branch)
        report["steps"]["rehydrate_reset"] = cleanup
        if not cleanup.get("ok"):
            report["healthy"] = False
            report["reason"] = "dep hash diverged and the worktree could not be reset to staging HEAD"
            return report

        try:
            hydration = hydrate_fn(project_root, dest, pool_dir, True)
            report["steps"]["rehydrate_copy"] = {"ok": True, "detail": hydration}
        except Exception as exc:  # noqa: BLE001 — surfaced in the report, not swallowed
            report["steps"]["rehydrate_copy"] = {"ok": False, "detail": str(exc)[-500:]}
            report["healthy"] = False
            report["reason"] = f"re-hydration failed after dep-hash divergence: {exc}"
            return report

    # 2. `.venv` revalidation — ALWAYS, regardless of step 1's outcome. This
    #    invocation IS the backend half of the smoke check (see module
    #    docstring) — not repeated a second time in step 3.
    venv_result = revalidate_venv(dest, config.get("health", {}))
    report["steps"]["venv"] = venv_result
    if not venv_result.get("ok"):
        report["healthy"] = False
        report["reason"] = venv_result.get("reason", "`.venv` revalidation failed")
        return report

    # 3. Frontend smoke build — ALWAYS, before handing the worktree over.
    frontend_result = smoke_frontend_build(dest, config.get("health", {}))
    report["steps"]["frontend_smoke"] = frontend_result
    if not frontend_result.get("ok"):
        report["healthy"] = False
        report["reason"] = frontend_result.get("reason", "frontend smoke build failed")
        return report

    report["healthy"] = True
    report["reason"] = None
    return report
