#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""pool_registry.py — lease + heartbeat registry for the bagual-worktree pool
(Story E11.2, PRD 03 FR-5c, hardening F16).

`pool_manager.py` (Story E11.1) tracked pool worktrees in `pool-state.json` with
only two states (`free`/`allocated`) — no owner identity, no heartbeat, no
cross-process locking around the free->allocated transition, no orphan
detection. This script SUPERSEDES that file with `registry.yaml`:

  * Each worktree carries `estado` in {livre, em-uso, aquecendo, suja} + `owner`
    (free-text identity of the Track/epic holding the lease) + `token` (opaque
    secret the holder must present to `heartbeat`/`return`) + `lease_acquired_at`
    + `heartbeat_at` + `returned_at`.
  * `allocate` is a TOCTOU-safe atomic `livre -> em-uso` transition — the
    pick-a-free-worktree + mark-it-leased sequence happens under ONE mutex
    acquisition (`acquire_mutex`/`RegistryLock`, O_CREAT|O_EXCL on a lock FILE —
    same exclusion primitive class as `gerente_state.py`'s `os.mkdir` lock, just
    file-based since this guards a read-modify-write of one shared registry.yaml
    instead of a single-slot singleton). Two concurrent `allocate` calls can
    NEVER both observe "picked, not yet marked" — whichever wins the mutex sees
    the other's write (if any) before picking. This is what makes "3 concurrent
    allocates -> 3 distinct worktrees" hold, the same guarantee E8.2's lock
    proved for a single slot, generalized to N slots in one file.
  * Orphan detection (F16, the hardening this story exists for) is
    HEARTBEAT-SILENCE, never a fixed lease age — reusing
    `gerente_state.py::lock_is_stale` UNMODIFIED via direct file import (not a
    copy, not a second timeout model). A long, healthy epic that keeps calling
    `heartbeat` every N minutes is never confused with a crash, no matter how
    many hours it runs. `reclaim_orphan()` only ever destroys a worktree AFTER
    independently proving heartbeat silence past the configured threshold.

IMPORTANT — two DIFFERENT staleness concepts live in this file, never conflate
them:
  1. The registry MUTEX (`acquire_mutex`, `MUTEX_STALE_AFTER_SECONDS`) guards a
     few milliseconds of file I/O. Its own stale-reclaim threshold is a
     crash-safety valve for "a process died mid-write while holding the mutex",
     completely unrelated to any epic's lifetime.
  2. The LEASE heartbeat (`lease_is_stale`, configured via
     `bagual_worktree.pool.lease.stale_after_minutes`) is F16's actual subject —
     it can legitimately be silent for minutes at a time between an active
     Track's heartbeat touches, and the whole point is that it must NOT be
     confused with a crash until it has been silent past the configured
     threshold.

Subcommands (stdlib-only, each prints a JSON report to stdout):
  allocate                 TOCTOU-safe livre -> em-uso over an EXISTING free
                            worktree. Prints {"allocated": null} if the pool has
                            no free worktree right now (copy-on-demand hydration
                            is pool_manager.py's job, not this script's — see
                            reserve_pending/commit_lease below, used internally
                            by pool_manager.py's `allocate` CLI).
  heartbeat (refresh-lease) A live Track touches its lease — requires --token.
  return                    Cleanup (git reset --hard + clean) + em-uso -> livre
                            (or -> suja if cleanup failed). Requires --token
                            unless --force (manual admin override, distinct
                            from reclaim-orphan's principled heartbeat check).
                            REFUSES the destructive reset (TCK-20260718135718-
                            c49f) when the worktree's own branch has commits
                            not reachable from --merge-target (default `dev`)
                            — pass --force-discard to intentionally discard
                            them anyway.
  reclaim-orphan            Scan for em-uso entries whose heartbeat has gone
                            silent past the stale-after threshold; destroy +
                            free/suja ONLY those. --dry-run reports without
                            mutating (used to prove "fresh heartbeat -> NOT
                            reclaimed").
  list                      Show every registry entry (with staleness reported
                            for every em-uso entry, for auditability).
  status                    Same as list, scoped to one --name.

Run with: uv run scripts/pool_registry.py <subcommand> [options]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

REGISTRY_FILENAME = "registry.yaml"
MUTEX_FILENAME = ".registry.lock"
DEFAULT_POOL_SIZE = 2
DEFAULT_POOL_LOCATION = ".claude/worktrees/pool"
DEFAULT_HEARTBEAT_INTERVAL_MINUTES = 5.0
DEFAULT_STALE_AFTER_MINUTES = 20.0
MUTEX_TIMEOUT_SECONDS = 15.0
# Story E11.3 (F17) health-check-on-allocation defaults. `backend_import`
# deliberately targets the real LOCAL EDITABLE package (`ai_update`), not a
# third-party dep like `fastapi` — F17's confirmed subject is the editable
# package's install record, not the venv's basic existence (see
# pool_health.py's module docstring / notes.md "F17 confirmado na prática").
DEFAULT_MAX_ALLOCATION_ATTEMPTS = 3
DEFAULT_SMOKE_FRONTEND_COMMAND = "npm run build:client"
DEFAULT_SMOKE_BACKEND_IMPORT = "ai_update"
DEFAULT_SMOKE_TIMEOUT_SECONDS = 300.0
# Crash-safety valve for the MUTEX itself (see module docstring point 1) — NOT
# the lease/orphan staleness threshold (point 2, configurable, see
# DEFAULT_STALE_AFTER_MINUTES / read_pool_config()).
MUTEX_STALE_AFTER_SECONDS = 30.0

VALID_ESTADOS = ("livre", "em-uso", "aquecendo", "suja")


# ---------------------------------------------------------------------------
# Reuse gerente_state.py's heartbeat-silence staleness primitive (E8.2, F9) by
# direct file import — the SAME technique gerente_state.py itself uses to reuse
# memlog.py's write_atomic, and the same technique already used a 3rd time by
# gerente_dispatch.py/gerente_wake.py/gerente_quota.py (see notes.md "Reuso de
# primitiva por import direto de arquivo escala para o TERCEIRO módulo..."). NOT
# a copy-paste, NOT a second timeout model — F16 explicitly requires reusing the
# SAME heartbeat-silence model, never inventing a parallel one.
# ---------------------------------------------------------------------------
def _load_module_from_path(name: str, path: Path):
    if not path.exists():
        print(f"erro: {path} não encontrado — não é possível reusar sua primitiva", file=sys.stderr)
        sys.exit(2)
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_GERENTE_STATE = None


def _gs():
    global _GERENTE_STATE
    if _GERENTE_STATE is None:
        # pool_registry.py: .claude/skills/bagual-worktree/scripts/pool_registry.py
        # parents[4] from here is the project root (mirrors gerente_state.py's own
        # parents[3]-from-itself resolution of memlog.py — see its docstring).
        gerente_state_path = (
            Path(__file__).resolve().parents[4]
            / "project_controll" / "gerente" / "scripts" / "gerente_state.py"
        )
        _GERENTE_STATE = _load_module_from_path("gerente_state_for_pool_registry", gerente_state_path)
    return _GERENTE_STATE


def now_iso() -> str:
    return _gs().now_iso()


def seconds_since(ts: str) -> float:
    return _gs().seconds_since(ts)


def write_atomic(path: Path, text: str) -> None:
    _gs().write_atomic(path, text)


def lease_is_stale(entry: dict, stale_after_seconds: float) -> tuple[bool, str]:
    """Heartbeat-silence staleness for a LEASE (F16) — delegates to
    `gerente_state.lock_is_stale` unmodified. No PID concept for a Track (same
    documented caveat gerente_state.py itself carries: no single long-lived OS
    process represents "the Gerente"/"the Track" in this agent/tool-call
    harness — see notes.md "não há um processo de SO de vida longa..."), so
    `pid` is always None here, which makes `lock_is_stale` fall straight
    through to the heartbeat-silence check — its designed behavior for exactly
    this case. This is the ONLY signal ever used to decide a worktree lease is
    orphaned: never `lease_acquired_at` age."""
    info = {"pid": None, "heartbeat_at": entry.get("heartbeat_at") or entry.get("lease_acquired_at")}
    return _gs().lock_is_stale(info, stale_after_seconds)


# ---------------------------------------------------------------------------
# git helpers (small, self-contained — pool_manager.py imports these FROM here
# rather than the reverse, to keep the dependency direction one-way and avoid
# a circular import between the two sibling scripts)
# ---------------------------------------------------------------------------
def run_git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-c", "core.quotePath=false", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def git_out(repo: Path, *args: str) -> str:
    return run_git(repo, *args).stdout.strip()


DEFAULT_MERGE_TARGET_BRANCH = "dev"


def _ref_exists(repo: Path, ref: str) -> bool:
    return run_git(repo, "rev-parse", "--verify", "--quiet", ref, check=False).returncode == 0


def unmerged_commit_count(repo: Path, branch: str, merge_target: str) -> Optional[int]:
    """Counts commits reachable from `branch` but NOT reachable from
    `merge_target` (`git rev-list --count merge_target..branch`) — the guard
    `return`/`clean` uses (TCK-20260718135718-c49f) to refuse a destructive
    hard-reset that would orphan work never merged upstream. This is the exact
    failure mode the ticket documents: an executor commits on its worktree
    branch, `return` hard-resets that SAME branch to `--base-branch` (default
    `staging`) before anyone merged those commits into `dev` — the commits
    become dangling, recoverable only from the object store (see
    `wiki/nota-operacional/worktree-return-hard-resets-branch-merge-before-returning.md`).

    Returns `None` (never `0`) when either ref does not exist in `repo` — e.g.
    a project with no `dev` branch (or a differently-named trunk), or
    (defensively) a worktree branch missing from git despite being in the
    registry. `None` means "cannot verify safely — skip the check", never a
    green light dressed up as `0`. Callers must not conflate the two."""
    if not _ref_exists(repo, merge_target) or not _ref_exists(repo, branch):
        return None
    result = run_git(repo, "rev-list", "--count", f"{merge_target}..{branch}", check=False)
    if result.returncode != 0:
        return None
    text = result.stdout.strip()
    return int(text) if text.isdigit() else None


def cleanup_worktree(dest: Path, project_root: Path, base_branch: str) -> dict:
    """Deterministic destructive cleanup — identical semantics to E11.1's
    `return`: hard-reset the worktree's own dedicated branch to the CURRENT tip
    of `base_branch` (never literal `git checkout staging` — see
    pool_manager.py/SKILL.md for why that's not directly possible), then
    `git clean -fd` (never `-x`, so gitignored node_modules/.venv/env files
    survive — that's the entire point of keeping a pool worktree warm). Used
    by BOTH the graceful `return` path and `reclaim_orphan()` — reclaim_orphan
    only ever calls this AFTER independently proving heartbeat silence.
    Returns a dict instead of raising so the caller can transition the entry
    to `suja` on failure instead of crashing."""
    try:
        staging_sha = git_out(project_root, "rev-parse", base_branch)
        run_git(dest, "reset", "--hard", staging_sha)
        run_git(dest, "clean", "-fd")
        return {"ok": True, "reset_to": staging_sha}
    except subprocess.CalledProcessError as exc:
        return {"ok": False, "detail": (exc.stderr or str(exc))[-500:]}


# ---------------------------------------------------------------------------
# config — `bagual_worktree: pool: {size, location, lease: {heartbeat_interval_
# minutes, stale_after_minutes}}` from `_bmad/config.yaml` (+ `config.user.yaml`
# override). Deliberately NOT a general YAML parser — same restrained-subset
# philosophy as gerente_state.py::parse_estado, extended one level deeper (a
# stack of active sections instead of a flat 2-level tracker) to reach
# `pool.lease.*`.
# ---------------------------------------------------------------------------
def read_pool_config(project_root: Path) -> dict[str, Any]:
    config: dict[str, Any] = {
        "size": DEFAULT_POOL_SIZE,
        "location": DEFAULT_POOL_LOCATION,
        "lease": {
            "heartbeat_interval_minutes": DEFAULT_HEARTBEAT_INTERVAL_MINUTES,
            "stale_after_minutes": DEFAULT_STALE_AFTER_MINUTES,
        },
        # Story E11.3 (F17) — health-check-on-allocation. `max_allocation_
        # attempts` bounds cmd_allocate's suja-and-retry loop (never infinite
        # — if `staging` itself is genuinely broken, retrying forever would
        # just keep manufacturing broken worktrees).
        "health": {
            "max_allocation_attempts": DEFAULT_MAX_ALLOCATION_ATTEMPTS,
            "smoke": {
                "frontend_command": DEFAULT_SMOKE_FRONTEND_COMMAND,
                "backend_import": DEFAULT_SMOKE_BACKEND_IMPORT,
                "timeout_seconds": DEFAULT_SMOKE_TIMEOUT_SECONDS,
            },
        },
    }
    for filename in ("config.yaml", "config.user.yaml"):
        path = project_root / "_bmad" / filename
        if not path.exists():
            continue
        _merge_pool_section(path.read_text(encoding="utf-8"), config)
    return config


def _merge_pool_section(text: str, config: dict[str, Any]) -> None:
    stack: list[tuple[str, int]] = []  # (section name, indent), root -> leaf
    for raw in text.splitlines():
        if not raw.strip() or raw.strip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        stripped = raw.strip()

        while stack and indent <= stack[-1][1]:
            stack.pop()
        path = tuple(name for name, _ in stack)

        if stripped.startswith("bagual_worktree:") and path == ():
            stack.append(("bagual_worktree", indent))
            continue
        if stripped.startswith("pool:") and path == ("bagual_worktree",):
            stack.append(("pool", indent))
            continue
        if stripped.startswith("lease:") and path == ("bagual_worktree", "pool"):
            stack.append(("lease", indent))
            continue
        # Story E11.3 (F17): `pool.health` (+ nested `pool.health.smoke`) —
        # same restrained stack-of-sections technique extended one level
        # deeper, never a general YAML parser.
        if stripped.startswith("health:") and path == ("bagual_worktree", "pool"):
            stack.append(("health", indent))
            continue
        if stripped.startswith("smoke:") and path == ("bagual_worktree", "pool", "health"):
            stack.append(("smoke", indent))
            continue

        match = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.+)$", stripped)
        if not match:
            continue
        key, raw_value = match.group(1), match.group(2).strip().strip("'\"")

        if path == ("bagual_worktree", "pool") and key in ("size", "location"):
            if key == "size":
                try:
                    config["size"] = int(raw_value)
                except ValueError:
                    pass
            else:
                config["location"] = raw_value
        elif path == ("bagual_worktree", "pool", "lease") and key in (
            "heartbeat_interval_minutes",
            "stale_after_minutes",
        ):
            try:
                config["lease"][key] = float(raw_value)
            except ValueError:
                pass
        elif path == ("bagual_worktree", "pool", "health") and key == "max_allocation_attempts":
            try:
                config["health"]["max_allocation_attempts"] = int(raw_value)
            except ValueError:
                pass
        elif path == ("bagual_worktree", "pool", "health", "smoke") and key in (
            "frontend_command",
            "backend_import",
            "timeout_seconds",
        ):
            if key == "timeout_seconds":
                try:
                    config["health"]["smoke"][key] = float(raw_value)
                except ValueError:
                    pass
            else:
                config["health"]["smoke"][key] = raw_value


def pool_dir_for(project_root: Path, config: dict[str, Any]) -> Path:
    return (project_root / config["location"]).resolve()


# ---------------------------------------------------------------------------
# minimal YAML dump/parse for registry.yaml (schema_version: scalar,
# worktrees: dict-of-dict-of-scalars, 2 levels of nesting) — same restrained
# closed-subset philosophy as gerente_state.py::dump_estado/parse_estado, not a
# general YAML parser.
# ---------------------------------------------------------------------------
REGISTRY_HEADER = """\
# registry.yaml — bagual-worktree pool lease + heartbeat registry (Story E11.2)
# PRD 03 FR-5c (lease) + F16 hardening (orphan = heartbeat silence, NEVER a
# fixed lease age). Written atomically by pool_registry.py — do not hand-edit
# while a lease may be active; hand edits bypass the mutex and can corrupt an
# in-flight allocate/return.
#
# estado in {livre, em-uso, aquecendo, suja}:
#   livre     - free, allocable.
#   em-uso    - leased to `owner` (a Track/epic identity); `token` gates
#               heartbeat/return; `heartbeat_at` is the ONLY orphan signal
#               (never `lease_acquired_at` age).
#   aquecendo - being hydrated (copy-on-demand allocate, or `create`); not yet
#               allocable, not yet leased.
#   suja      - cleanup (git reset --hard + clean) failed on return/reclaim;
#               pulled out of rotation until reaped/removed.
"""

ENTRY_FIELDS = (
    "path", "branch", "estado", "owner", "token",
    "created_at", "lease_acquired_at", "heartbeat_at", "returned_at", "label",
)


def _yaml_scalar(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v)
    if s == "":
        return '""'
    needs_quotes = (
        any(ch in s for ch in ':#"\'{}[]')
        or s.strip() != s
        or s.lower() in ("null", "true", "false", "~")
        or re.fullmatch(r"-?\d+(\.\d+)?", s) is not None
    )
    if needs_quotes:
        escaped = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return s


def _unquote(s: str) -> Any:
    s = s.strip()
    if s == "null" or s == "":
        return None
    if s == "true":
        return True
    if s == "false":
        return False
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("'", '"'):
        inner = s[1:-1]
        if s[0] == '"':
            inner = inner.replace('\\"', '"').replace("\\\\", "\\")
        return inner
    return s


def dump_registry(doc: dict[str, Any]) -> str:
    lines = [REGISTRY_HEADER.rstrip("\n"), ""]
    lines.append(f"schema_version: {doc.get('schema_version', 1)}")
    worktrees: dict[str, dict] = doc.get("worktrees", {})
    if not worktrees:
        lines.append("worktrees: {}")
    else:
        lines.append("worktrees:")
        for name in sorted(worktrees.keys()):
            entry = worktrees[name]
            lines.append(f"  {name}:")
            for k in ENTRY_FIELDS:
                if k in entry:
                    lines.append(f"    {k}: {_yaml_scalar(entry[k])}")
            # any extra keys not in the canonical field order (forward-compat)
            for k, v in entry.items():
                if k not in ENTRY_FIELDS:
                    lines.append(f"    {k}: {_yaml_scalar(v)}")
    return "\n".join(lines) + "\n"


def parse_registry(text: str) -> dict[str, Any]:
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith("#")]
    doc: dict[str, Any] = {"schema_version": 1, "worktrees": {}}
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if not line.strip():
            i += 1
            continue
        if line.startswith(" "):
            i += 1  # orphan indented line outside a recognized block — skip defensively
            continue
        key, _, rest = line.partition(":")
        key = key.strip()
        rest = rest.strip()

        if key == "schema_version":
            if rest.isdigit():
                doc["schema_version"] = int(rest)
            else:
                doc["schema_version"] = _unquote(rest) if rest else 1
            i += 1
            continue

        if key == "worktrees":
            i += 1
            if rest == "{}":
                doc["worktrees"] = {}
                continue
            worktrees: dict[str, dict] = {}
            cur_name: Optional[str] = None
            cur_entry: dict[str, Any] = {}
            while i < n and (not lines[i].strip() or lines[i].startswith("  ")):
                if not lines[i].strip():
                    i += 1
                    continue
                indent = len(lines[i]) - len(lines[i].lstrip(" "))
                stripped = lines[i].strip()
                if indent == 2:
                    if cur_name is not None:
                        worktrees[cur_name] = cur_entry
                    cur_name = stripped.rstrip(":").strip()
                    cur_entry = {}
                elif indent >= 4 and cur_name is not None:
                    k2, _, v2 = stripped.partition(":")
                    if k2:
                        cur_entry[k2.strip()] = _unquote(v2)
                i += 1
            if cur_name is not None:
                worktrees[cur_name] = cur_entry
            doc["worktrees"] = worktrees
            continue

        # unrecognized top-level key — skip its value line/block defensively
        i += 1

    return doc


def registry_path(pool_dir: Path) -> Path:
    return pool_dir / REGISTRY_FILENAME


def load_registry(pool_dir: Path) -> dict[str, Any]:
    path = registry_path(pool_dir)
    if not path.exists():
        return {"schema_version": 1, "worktrees": {}}
    try:
        return parse_registry(path.read_text(encoding="utf-8"))
    except Exception:
        # never crash a caller on a corrupted registry — surface an empty one
        # so the caller can decide (list/status show the raw file separately
        # for diagnosis); resilience requirement (AC "registro em disco
        # resiliente, auditável").
        return {"schema_version": 1, "worktrees": {}}


def save_registry(pool_dir: Path, doc: dict[str, Any]) -> None:
    pool_dir.mkdir(parents=True, exist_ok=True)
    write_atomic(registry_path(pool_dir), dump_registry(doc))


def reconcile_registry(project_root: Path, pool_dir: Path, doc: dict[str, Any]) -> dict[str, Any]:
    """Drop entries whose git worktree no longer exists in disk (removed by
    hand outside this script) EXCEPT `aquecendo` placeholders mid-reservation
    (path is None while hydration is in flight — dropping those would corrupt
    a concurrent reserve_pending()/commit_lease() pair). Mirrors E11.1's
    reconcile_state, extended for the registry's richer entry shape. Read-only
    with respect to git — never mutates the worktree itself."""
    live = set(_git_worktree_paths(project_root))
    worktrees = doc.get("worktrees", {})
    for name in list(worktrees.keys()):
        entry = worktrees[name]
        if entry.get("path") is None:
            continue  # in-flight reservation — never garbage-collected here
        if Path(entry["path"]).resolve() not in live:
            del worktrees[name]
    doc["worktrees"] = worktrees
    return doc


def _git_worktree_paths(project_root: Path) -> list[Path]:
    out = git_out(project_root, "worktree", "list", "--porcelain")
    paths = []
    for line in out.splitlines():
        if line.startswith("worktree "):
            paths.append(Path(line[len("worktree "):]).resolve())
    return paths


# ---------------------------------------------------------------------------
# mutex — TOCTOU-safe exclusion around registry.yaml's read-modify-write
# critical section (the crux: two concurrent `allocate` calls must NEVER both
# pick the same free worktree).
# ---------------------------------------------------------------------------
def _mutex_path(pool_dir: Path) -> Path:
    return pool_dir / MUTEX_FILENAME


def acquire_mutex(
    pool_dir: Path,
    timeout_seconds: float = MUTEX_TIMEOUT_SECONDS,
    stale_after_seconds: float = MUTEX_STALE_AFTER_SECONDS,
) -> None:
    """`os.open(..., O_CREAT | O_EXCL)` is atomic at the OS level: exactly one
    concurrent caller's open() succeeds when the lock file does not yet exist,
    every other caller gets FileExistsError — the same exclusivity guarantee
    class as gerente_state.py's `os.mkdir` lock (E8.2, F9), just file-based
    since this guards a read-modify-write of ONE shared registry.yaml (a
    multi-slot resource) rather than a single-slot singleton. On contention,
    busy-waits with a short sleep (the critical section is always a few
    milliseconds of small-file I/O, never a live epic) until acquired or
    `timeout_seconds` elapses. Stale-reclaim (crash-safety valve — see module
    docstring point 1, NOT the lease staleness model) uses the exact same
    rename-to-steal trick as gerente_state.py's lock reclaim: only ONE
    contender can win the `os.rename`, so the reclaim itself is also
    TOCTOU-safe."""
    pool_dir.mkdir(parents=True, exist_ok=True)
    lock_path = _mutex_path(pool_dir)
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(fd, f"{os.getpid()} {time.time()}\n".encode())
            finally:
                os.close(fd)
            return
        except FileExistsError:
            try:
                age = time.time() - lock_path.stat().st_mtime
            except FileNotFoundError:
                continue  # released between our open() attempt and stat() — retry immediately
            if age > stale_after_seconds:
                stale_name = lock_path.with_name(f".registry.lock.stale-{os.getpid()}-{time.time_ns()}")
                try:
                    os.rename(lock_path, stale_name)  # only ONE contender wins this rename
                except FileNotFoundError:
                    continue  # someone else already reclaimed it — retry mkdir
                try:
                    stale_name.unlink()
                except FileNotFoundError:
                    pass
                continue
            if time.monotonic() > deadline:
                raise TimeoutError(f"could not acquire registry mutex ({lock_path}) within {timeout_seconds}s")
            time.sleep(0.02)


def release_mutex(pool_dir: Path) -> None:
    try:
        _mutex_path(pool_dir).unlink()
    except FileNotFoundError:
        pass


class RegistryLock:
    def __init__(self, pool_dir: Path, timeout_seconds: float = MUTEX_TIMEOUT_SECONDS):
        self.pool_dir = pool_dir
        self.timeout_seconds = timeout_seconds

    def __enter__(self) -> "RegistryLock":
        acquire_mutex(self.pool_dir, timeout_seconds=self.timeout_seconds)
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        release_mutex(self.pool_dir)
        return False


# ---------------------------------------------------------------------------
# core state transitions — every mutating function acquires its own mutex, so
# callers never need to (and never should) nest RegistryLock themselves.
# ---------------------------------------------------------------------------
def _blank_entry(estado: str) -> dict[str, Any]:
    return {
        "path": None, "branch": None, "estado": estado,
        "owner": None, "token": None,
        "created_at": now_iso(), "lease_acquired_at": None,
        "heartbeat_at": None, "returned_at": None, "label": None,
    }


def register_new_entry(
    pool_dir: Path, name: str, path: str, branch: str, estado: str = "livre",
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Registers a brand-new pool worktree right after `git worktree add`
    succeeds (E11.1's `create`/`warm` flow). Mutex-protected so it never races
    a concurrent read/write, though the caller (pool_manager.py's batch
    `create`) is itself the only writer touching this name at that point —
    no collision to resolve here, unlike reserve_pending() below."""
    with RegistryLock(pool_dir):
        doc = load_registry(pool_dir)
        entry = _blank_entry(estado)
        entry["path"] = path
        entry["branch"] = branch
        if extra:
            entry.update(extra)
        doc.setdefault("worktrees", {})[name] = entry
        save_registry(pool_dir, doc)
        return {"name": name, **entry}


def reserve_pending(pool_dir: Path) -> str:
    """TOCTOU-safe name reservation for the copy-on-demand `allocate` path:
    claims the next free `pool-N` name by registering an `aquecendo`
    placeholder BEFORE the slow `git worktree add` + hydration happens OUTSIDE
    the mutex — so two concurrent copy-on-demand allocations can never collide
    on the same destination path/branch name (each reserves a DISTINCT name
    under the mutex before starting its own slow work).

    Also avoids a STRAY directory already sitting under `pool_dir` that isn't
    (yet, or anymore) tracked in the registry — e.g. a leftover from a prior
    run whose hydration crashed after `git worktree add` but before this
    reservation could be finalized/abandoned (self-review finding: E11.1's
    original `next_pool_name` scanned both the state file AND the directory
    listing for exactly this reason; a registry-only scan would silently pick
    a name `git worktree add` then refuses because the destination already
    exists)."""
    with RegistryLock(pool_dir):
        doc = load_registry(pool_dir)
        worktrees = doc.setdefault("worktrees", {})
        used = set(worktrees.keys())
        if pool_dir.exists():
            used |= {p.name for p in pool_dir.iterdir() if p.is_dir()}
        n = 1
        while f"pool-{n}" in used:
            n += 1
        name = f"pool-{n}"
        worktrees[name] = _blank_entry("aquecendo")
        save_registry(pool_dir, doc)
        return name


def abandon_reservation(pool_dir: Path, name: str) -> None:
    """Drop a reserve_pending() placeholder whose hydration failed outside the
    mutex — never leave a phantom `aquecendo` entry with no worktree behind
    it."""
    with RegistryLock(pool_dir):
        doc = load_registry(pool_dir)
        doc.get("worktrees", {}).pop(name, None)
        save_registry(pool_dir, doc)


def finalize_created(pool_dir: Path, name: str, path: str, branch: str) -> dict[str, Any]:
    """Finalize a reserve_pending() placeholder for the `create`/`warm` flow
    (E11.1) — `aquecendo -> livre` with the real path/branch filled in, no
    lease fields touched (this worktree isn't leased to anyone, it's just now
    available). Distinct from commit_lease(), which is the `allocate`
    copy-on-demand path and DOES grant a lease in the same step."""
    with RegistryLock(pool_dir):
        doc = load_registry(pool_dir)
        worktrees = doc.setdefault("worktrees", {})
        if name not in worktrees:
            raise KeyError(f"no such pool worktree reservation: {name}")
        worktrees[name].update({"path": path, "branch": branch, "estado": "livre"})
        save_registry(pool_dir, doc)
        return {"name": name, **worktrees[name]}


def remove_entry(pool_dir: Path, name: str) -> dict[str, Any]:
    """Permanently drop a registry entry (E11.1's `remove` — pool shrink/
    teardown). Caller is responsible for the actual `git worktree remove` +
    branch delete; this only removes the bookkeeping row, mutex-protected so
    it can't race a concurrent allocate/list."""
    with RegistryLock(pool_dir):
        doc = load_registry(pool_dir)
        worktrees = doc.get("worktrees", {})
        existed = worktrees.pop(name, None)
        save_registry(pool_dir, doc)
        return {"ok": existed is not None, "removed": name if existed is not None else None}


def commit_lease(pool_dir: Path, name: str, path: str, branch: str, owner: str, label: Optional[str]) -> dict[str, Any]:
    """Finalize a reserve_pending() placeholder into a live lease
    (`aquecendo -> em-uso` with a fresh token + lease/heartbeat timestamps)
    once hydration outside the mutex has completed successfully."""
    with RegistryLock(pool_dir):
        doc = load_registry(pool_dir)
        worktrees = doc.setdefault("worktrees", {})
        if name not in worktrees:
            raise KeyError(f"no such pool worktree reservation: {name}")
        token = uuid.uuid4().hex
        ts = now_iso()
        worktrees[name].update({
            "path": path, "branch": branch, "estado": "em-uso",
            "owner": owner, "token": token, "label": label,
            "lease_acquired_at": ts, "heartbeat_at": ts,
        })
        save_registry(pool_dir, doc)
        return {"name": name, **worktrees[name]}


def allocate(
    pool_dir: Path,
    owner: str,
    label: Optional[str] = None,
    health_check_fn: Optional[Callable[[dict[str, Any]], dict[str, Any]]] = None,
) -> Optional[dict[str, Any]]:
    """TOCTOU-safe atomic `livre -> em-uso` over an EXISTING free worktree.
    Returns None if no free worktree exists right now (caller falls back to
    copy-on-demand via reserve_pending/commit_lease — see pool_manager.py's
    `allocate` CLI, which owns that decision). THE crux operation: the entire
    pick-a-free-name + mark-it-leased sequence happens under ONE mutex
    acquisition.

    NOT HEALTH-CHECKED BY DEFAULT (Story E11.3, F17) — this is the raw lease
    primitive. `pool_manager.py`'s `allocate` CLI remains the sole supported
    entry point for a caller that needs a worktree it can trust without
    wiring anything itself (it wraps `pool_health.run_health_check` +
    dep-hash/`.venv`/smoke-build logic this module deliberately knows nothing
    about). `SKILL.md` still does NOT list `allocate` among the subcommands
    safe to invoke on `pool_registry.py` directly for callers that skip
    `health_check_fn` — no dep-hash-vs-staging comparison, no `.venv`
    revalidation, no smoke build happens here on its own.

    `health_check_fn` (Story E16.5, T3.8) — OPTIONAL dependency injection, no
    import of `pool_health.py` (or any health module) here: that would create
    a real circular import, since `pool_health.py` already imports THIS file
    (direct file import, see its own docstring). A caller that owns both
    modules (e.g. `pool_manager.py`) builds its own closure/partial around
    whatever health primitive it wants and passes the function in from
    outside. When given, `health_check_fn` is called as
    `health_check_fn(leased_entry)` — `leased_entry` is the same
    `{"name": ..., "path": ..., "branch": ..., "token": ..., ...}` shape this
    function returns — for the JUST-LEASED candidate, ALWAYS after the
    mutex-protected lease transition (never while holding `RegistryLock`: a
    real health check does filesystem/subprocess I/O, and holding the mutex
    during that would serialize every concurrent `allocate` behind one slow
    check). It must return a dict with a `"healthy"` key. An unhealthy result
    marks that candidate `suja` (reusing `mark_returned`, never a second
    cleanup path) and tries the NEXT still-free candidate not yet attempted —
    bounded by the number of free worktrees observed across attempts, never
    infinite. Returns `None` if the pool has no free worktree, OR if every
    free candidate failed its health check. When `health_check_fn` is `None`
    (the default), behavior is IDENTICAL to before this story: pick the first
    free worktree, lease it, return it — no extra call, no retry loop."""
    attempted: set[str] = set()
    while True:
        with RegistryLock(pool_dir):
            doc = load_registry(pool_dir)
            worktrees = doc.get("worktrees", {})
            free_names = sorted(
                n for n, e in worktrees.items() if e.get("estado") == "livre" and n not in attempted
            )
            if not free_names:
                return None
            name = free_names[0]
            entry = worktrees[name]
            token = uuid.uuid4().hex
            ts = now_iso()
            entry.update({
                "estado": "em-uso", "owner": owner, "token": token, "label": label,
                "lease_acquired_at": ts, "heartbeat_at": ts,
            })
            save_registry(pool_dir, doc)
            leased = {"name": name, **entry}

        if health_check_fn is None:
            return leased

        health = health_check_fn(leased)
        if health.get("healthy"):
            return {**leased, "health_check": health}

        attempted.add(name)
        mark_returned(pool_dir, name, leased["token"], cleanup_ok=False, require_token=True)


def heartbeat(pool_dir: Path, name: str, token: str) -> dict[str, Any]:
    with RegistryLock(pool_dir):
        doc = load_registry(pool_dir)
        worktrees = doc.get("worktrees", {})
        if name not in worktrees:
            return {"ok": False, "reason": "unknown-worktree"}
        entry = worktrees[name]
        if entry.get("estado") != "em-uso":
            return {"ok": False, "reason": "not-leased", "estado": entry.get("estado")}
        if entry.get("token") != token:
            return {"ok": False, "reason": "not-owner"}
        entry["heartbeat_at"] = now_iso()
        save_registry(pool_dir, doc)
        return {"ok": True, "name": name, "heartbeat_at": entry["heartbeat_at"]}


def mark_returned(pool_dir: Path, name: str, token: Optional[str], cleanup_ok: bool, require_token: bool = True) -> dict[str, Any]:
    """`em-uso -> livre` (cleanup_ok) or `-> suja` (cleanup failed).
    `require_token=True` (the graceful `return` path, and admin `--force`
    bypasses it explicitly at the CLI layer) enforces owner identity, mirroring
    gerente_state.py's `release-lock`. `require_token=False` is used ONLY by
    `reclaim_orphan()`, after it has independently proven heartbeat silence —
    the original owner is presumed dead, so no token can be available to
    check; token identity and heartbeat-silence are two INDEPENDENT proofs of
    "safe to reclaim", never conflated."""
    with RegistryLock(pool_dir):
        doc = load_registry(pool_dir)
        worktrees = doc.get("worktrees", {})
        if name not in worktrees:
            return {"ok": False, "reason": "unknown-worktree"}
        entry = worktrees[name]
        if require_token and entry.get("token") != token:
            return {"ok": False, "reason": "not-owner"}
        entry.update({
            "estado": "livre" if cleanup_ok else "suja",
            "owner": None, "token": None, "label": None,
            "lease_acquired_at": None, "heartbeat_at": None,
            "returned_at": now_iso(),
        })
        save_registry(pool_dir, doc)
        return {"ok": True, "name": name, "estado": entry["estado"]}


def find_orphans(pool_dir: Path, stale_after_seconds: float) -> list[dict[str, Any]]:
    """Read-only scan (no mutation) of every `em-uso` entry whose heartbeat has
    gone silent longer than `stale_after_seconds`. NEVER based on
    `lease_acquired_at` age — F16, the reason this story exists."""
    doc = load_registry(pool_dir)
    orphans = []
    for name, entry in doc.get("worktrees", {}).items():
        if entry.get("estado") != "em-uso":
            continue
        stale, why = lease_is_stale(entry, stale_after_seconds)
        if stale:
            orphans.append({"name": name, "reason": why, **entry})
    return orphans


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _resolve_project_root(args: argparse.Namespace) -> Path:
    if args.project_root is not None:
        return args.project_root.resolve()
    return Path(git_out(Path.cwd(), "rev-parse", "--show-toplevel")).resolve()


def _resolve_pool_dir(args: argparse.Namespace, project_root: Path) -> Path:
    if args.pool_dir:
        return Path(args.pool_dir).resolve()
    config = read_pool_config(project_root)
    return pool_dir_for(project_root, config)


def add_common_args(sub: argparse.ArgumentParser) -> None:
    sub.add_argument("--project-root", type=Path, default=None, help="Defaults to `git rev-parse --show-toplevel` of cwd")
    sub.add_argument("--pool-dir", default=None, help="Override the configured pool location")


def cmd_allocate(
    args: argparse.Namespace,
    health_check_fn: Optional[Callable[[dict[str, Any]], dict[str, Any]]] = None,
) -> int:
    """Story E16.5: `health_check_fn` is forwarded straight to `allocate()` —
    this function never re-implements the health-check-call/suja-retry loop
    itself, it only owns the CLI-shaped concerns (resolving project
    root/pool dir from `args`, JSON printing, exit code). `main()`'s CLI
    dispatch (`args.func(args)`) never passes `health_check_fn`, so real CLI
    invocations (`pool_registry.py allocate ...`) are byte-for-byte unchanged
    from before this story. A caller that owns a health primitive (e.g.
    `pool_manager.py`, or a test) can call `cmd_allocate(args,
    health_check_fn=...)` directly to get the same JSON/exit-code contract
    with health-checked allocation, without duplicating this wrapper."""
    project_root = _resolve_project_root(args)
    pool_dir = _resolve_pool_dir(args, project_root)
    result = allocate(pool_dir, owner=args.owner, label=args.label, health_check_fn=health_check_fn)
    print(json.dumps({"allocated": result}, indent=2))
    return 0 if result is not None else 1


def cmd_heartbeat(args: argparse.Namespace) -> int:
    project_root = _resolve_project_root(args)
    pool_dir = _resolve_pool_dir(args, project_root)
    result = heartbeat(pool_dir, args.name, args.token)
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


def cmd_return(args: argparse.Namespace) -> int:
    project_root = _resolve_project_root(args)
    pool_dir = _resolve_pool_dir(args, project_root)
    doc = load_registry(pool_dir)
    entry = doc.get("worktrees", {}).get(args.name)
    if entry is None:
        print(json.dumps({"error": f"unknown pool worktree: {args.name}"}), file=sys.stderr)
        return 2
    if not args.force and entry.get("token") != args.token:
        print(json.dumps({"error": "not-owner: token does not match current lease holder (pass --force to override)"}), file=sys.stderr)
        return 2
    if entry.get("path") is None:
        print(json.dumps({"error": f"{args.name} has no worktree path yet (still aquecendo/reserved)"}), file=sys.stderr)
        return 2

    # TCK-20260718135718-c49f: refuse the destructive reset if the worktree's
    # own branch carries commits not yet merged into `dev` (or whatever
    # --merge-target names) — this is exactly the "executor committed, return
    # ran before the merge, commits went dangling" incident this guard exists
    # to prevent (see wiki/nota-operacional/worktree-return-hard-resets-branch-
    # merge-before-returning.md). `--force-discard` is the explicit, opt-in
    # escape hatch for the rare case where discarding IS the intent.
    force_discard = getattr(args, "force_discard", False)
    merge_target = getattr(args, "merge_target", None) or DEFAULT_MERGE_TARGET_BRANCH
    branch = entry.get("branch")
    if branch and not force_discard:
        unmerged = unmerged_commit_count(project_root, branch, merge_target)
        if unmerged:
            print(
                json.dumps(
                    {
                        "error": "unmerged-commits",
                        "branch": branch,
                        "merge_target": merge_target,
                        "unmerged_commit_count": unmerged,
                        "detail": (
                            f"branch '{branch}' has {unmerged} commit(s) not reachable from "
                            f"'{merge_target}' — merge it into '{merge_target}' from the main "
                            "checkout BEFORE returning this worktree, or pass --force-discard "
                            "to intentionally discard them."
                        ),
                    }
                ),
                file=sys.stderr,
            )
            return 4

    cleanup = cleanup_worktree(Path(entry["path"]), project_root, args.base_branch)
    result = mark_returned(pool_dir, args.name, args.token, cleanup_ok=cleanup["ok"], require_token=not args.force)
    result["cleanup"] = cleanup
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


def cmd_reclaim_orphan(args: argparse.Namespace) -> int:
    project_root = _resolve_project_root(args)
    pool_dir = _resolve_pool_dir(args, project_root)
    if args.stale_after_seconds is not None:
        stale_after = args.stale_after_seconds
    else:
        stale_after = read_pool_config(project_root)["lease"]["stale_after_minutes"] * 60.0

    doc = load_registry(pool_dir)
    worktrees = doc.get("worktrees", {})
    targets = [args.name] if args.name else sorted(n for n, e in worktrees.items() if e.get("estado") == "em-uso")

    report: dict[str, Any] = {"stale_after_seconds": stale_after, "reclaimed": [], "skipped_fresh": [], "skipped_not_leased": []}
    for name in targets:
        entry = worktrees.get(name)
        if entry is None or entry.get("estado") != "em-uso":
            report["skipped_not_leased"].append(name)
            continue
        stale, why = lease_is_stale(entry, stale_after)
        if not stale:
            report["skipped_fresh"].append({"name": name, "heartbeat_at": entry.get("heartbeat_at")})
            continue
        if args.dry_run:
            report["reclaimed"].append({"name": name, "reason": why, "dry_run": True})
            continue
        # Re-verify staleness IMMEDIATELY before the destructive git cleanup —
        # narrows the window between "read stale" (above, from a snapshot taken
        # before this loop) and "destroy" as tightly as reasonably possible. If
        # the true owner's heartbeat lands in that gap (proving it was NOT
        # actually dead), abort this entry instead of destroying live work.
        # This cannot close the window entirely without running the (slow) git
        # cleanup itself under the registry mutex, which would serialize
        # reclaim behind every live Track's heartbeat call — an unacceptable
        # cost tradeoff for a race this narrow (self-review finding).
        fresh_doc = load_registry(pool_dir)
        fresh_entry = fresh_doc.get("worktrees", {}).get(name)
        if fresh_entry is None or fresh_entry.get("estado") != "em-uso":
            report["skipped_not_leased"].append(name)
            continue
        still_stale, why2 = lease_is_stale(fresh_entry, stale_after)
        if not still_stale:
            report["skipped_fresh"].append({
                "name": name, "heartbeat_at": fresh_entry.get("heartbeat_at"),
                "note": "heartbeat arrived between initial scan and reclaim — aborted",
            })
            continue
        cleanup = cleanup_worktree(Path(fresh_entry["path"]), project_root, args.base_branch)
        result = mark_returned(pool_dir, name, token=None, cleanup_ok=cleanup["ok"], require_token=False)
        report["reclaimed"].append({"name": name, "reason": why2, "cleanup": cleanup, "estado_after": result.get("estado")})

    print(json.dumps(report, indent=2))
    return 0


def _staleness_view(entry: dict[str, Any], stale_after_seconds: float) -> dict[str, Any]:
    if entry.get("estado") != "em-uso":
        return {}
    stale, why = lease_is_stale(entry, stale_after_seconds)
    heartbeat_at = entry.get("heartbeat_at")
    return {
        "heartbeat_age_seconds": seconds_since(heartbeat_at) if heartbeat_at else None,
        "stale": stale,
        "stale_reason": why if stale else None,
    }


def cmd_list(args: argparse.Namespace) -> int:
    project_root = _resolve_project_root(args)
    pool_dir = _resolve_pool_dir(args, project_root)
    stale_after = read_pool_config(project_root)["lease"]["stale_after_minutes"] * 60.0
    doc = load_registry(pool_dir)
    if not args.no_reconcile:
        doc = reconcile_registry(project_root, pool_dir, doc)
    view = {}
    for name, entry in doc.get("worktrees", {}).items():
        view[name] = {**entry, "staleness": _staleness_view(entry, stale_after)}
    print(json.dumps({"pool_dir": str(pool_dir), "worktrees": view}, indent=2))
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    project_root = _resolve_project_root(args)
    pool_dir = _resolve_pool_dir(args, project_root)
    stale_after = read_pool_config(project_root)["lease"]["stale_after_minutes"] * 60.0
    doc = load_registry(pool_dir)
    if args.name:
        entry = doc.get("worktrees", {}).get(args.name)
        if entry is None:
            print(json.dumps({"error": f"unknown pool worktree: {args.name}"}), file=sys.stderr)
            return 2
        print(json.dumps({args.name: {**entry, "staleness": _staleness_view(entry, stale_after)}}, indent=2))
        return 0
    return cmd_list(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p_alloc = sub.add_parser("allocate", help="TOCTOU-safe livre->em-uso over an existing free worktree. NOT health-checked (E11.3) — use pool_manager.py allocate instead unless you specifically want the raw, unchecked primitive")
    add_common_args(p_alloc)
    p_alloc.add_argument("--owner", required=True, help="Identity of the Track/epic acquiring the lease")
    p_alloc.add_argument("--label", default=None, help="Free-text tag for what this allocation is for")
    p_alloc.set_defaults(func=cmd_allocate)

    p_hb = sub.add_parser("heartbeat", aliases=["refresh-lease"], help="A live Track touches its lease (requires --token)")
    add_common_args(p_hb)
    p_hb.add_argument("name")
    p_hb.add_argument("--token", required=True)
    p_hb.set_defaults(func=cmd_heartbeat)

    p_ret = sub.add_parser("return", help="Cleanup + em-uso->livre (or ->suja on cleanup failure)")
    add_common_args(p_ret)
    p_ret.add_argument("name")
    p_ret.add_argument("--token", default=None, help="Required unless --force")
    p_ret.add_argument("--force", action="store_true", help="Manual admin override — bypasses the owner-token check (distinct from reclaim-orphan's heartbeat-based check)")
    p_ret.add_argument("--base-branch", default="staging")
    p_ret.add_argument("--force-discard", action="store_true", help="TCK-20260718135718-c49f: explicitly allow discarding commits on the worktree branch that are not yet merged into --merge-target (default: dev) — bypasses the unmerged-commits guard")
    p_ret.add_argument("--merge-target", default=None, help="Branch to check the worktree branch's commits against before allowing a destructive return (default: dev) — distinct from --base-branch, which is what the worktree gets RESET to")
    p_ret.set_defaults(func=cmd_return)

    p_reclaim = sub.add_parser("reclaim-orphan", help="Destroy + free/suja ONLY em-uso entries whose heartbeat has gone silent past the stale-after threshold")
    add_common_args(p_reclaim)
    p_reclaim.add_argument("name", nargs="?", default=None, help="Reclaim a specific worktree; omit to scan every em-uso entry")
    p_reclaim.add_argument("--stale-after-seconds", type=float, default=None, help="Override configured lease.stale_after_minutes")
    p_reclaim.add_argument("--base-branch", default="staging")
    p_reclaim.add_argument("--dry-run", action="store_true", help="Report what WOULD be reclaimed without mutating anything")
    p_reclaim.set_defaults(func=cmd_reclaim_orphan)

    p_list = sub.add_parser("list", help="Show every registry entry, with staleness reported for em-uso entries")
    add_common_args(p_list)
    p_list.add_argument("--no-reconcile", action="store_true", help="Skip pruning entries whose worktree no longer exists on disk")
    p_list.set_defaults(func=cmd_list)

    p_status = sub.add_parser("status", help="Same as list, optionally scoped to one --name")
    add_common_args(p_status)
    p_status.add_argument("--name", default=None)
    p_status.add_argument("--no-reconcile", action="store_true")
    p_status.set_defaults(func=cmd_status)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
