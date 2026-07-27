#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""pool_manager.py — bagual-worktree pool lifecycle manager (Story E11.1,
state layer superseded by `pool_registry.py` in Story E11.2).

Evolves `bagual-worktree` from "create ONE worktree, ad hoc" into a manager for
a **pool** of N pre-warmed worktrees that can be repeatedly allocated to a
parallel Track and returned (cleaned) when the Track finishes — so the cost of
hydration (copying node_modules/.venv/env files) comes out of the execution
critical path instead of being paid by every parallel epic every time.

State ownership (Story E11.2): this script no longer owns `pool-state.json`
(free/allocated only, single-caller-assumed). All state — `registry.yaml`,
lease/heartbeat, the TOCTOU-safe mutex around allocation, and orphan-lease
reclaim (F16, heartbeat-silence not fixed age) — lives in `pool_registry.py`,
imported here directly (same technique gerente_state.py uses to reuse
memlog.py — see pool_registry.py's own docstring). This script keeps owning
what it always owned: git worktree creation and hydration
(`copy_ignored_artifacts.py` + `smoke_check`). `heartbeat`/`return`/
`reclaim-orphan`/`list`/`status` below are thin CLI wrappers that delegate
directly to `pool_registry.py`'s implementation — single source of truth,
never a second copy of the state logic.

Subcommands (stdlib-only, reuses `copy_ignored_artifacts.py` for hydration —
does NOT reimplement it; reuses `pool_registry.py` for all state — does NOT
reimplement that either):
  create / warm     Create + hydrate N new pool worktrees (or top up to the
                     configured pool size with --fill). Registers each as
                     `livre` in registry.yaml.
  allocate          Hand out one pool worktree AS A LEASE (owner + token):
                     prefer a free pre-warmed one (registry.py's TOCTOU-safe
                     `allocate`); if none is free, hydrate one on demand
                     (copy-on-demand, still TOCTOU-safe via
                     reserve_pending/commit_lease); if hydration itself is
                     unusable, `create --from-scratch` is the manual
                     correction fallback (see "3 strategies" below). Runs
                     `pool_health.run_health_check` (Story E11.3, F17) on
                     EVERY candidate before returning it — a candidate that
                     fails the health-check and cannot be sanitized is marked
                     `suja` and another is tried, up to `health.
                     max_allocation_attempts` (config). `allocate` NEVER
                     returns an unchecked worktree.
  heartbeat         Delegates to pool_registry.py — a live Track touches its
                     lease.
  return            Delegates to pool_registry.py — cleanup + em-uso->livre
                     (or ->suja).
  reclaim-orphan    Delegates to pool_registry.py — heartbeat-silence orphan
                     reclaim (F16), never a fixed lease age.
  list / status     Delegates to pool_registry.py.
  remove            Permanently delete a pool worktree (git worktree remove +
                     branch delete + registry row removal) — shrinking the
                     pool or tearing down test worktrees.

3 strategies by preference (PRD 03 FR-5b, `ideias/epics.md` Story E11.1):
  (3) pre-warmed pool  — `allocate` hands out an already-hydrated free worktree.
                          Zero hydration cost at allocation time. Preferred path.
  (2) copy-on-demand   — pool has no free worktree: `allocate` hydrates ONE
                          right now via `copy_ignored_artifacts.py`. Cost is
                          paid only on pool exhaustion, never for every epic.
  (1) from-scratch     — `create --from-scratch` skips the hydration copy and
                          instead leaves the worktree for a real `npm install`/
                          `uv sync`. Manual correction fallback only (e.g. the
                          hardlink copy is somehow unusable) — never the default
                          path for either `create` or `allocate`.

F17 caveat (PRD 03 §FR-5c hardening, `ideias/revisao-adversarial-furos.md`):
the hardlink copy of a Python virtualenv (`.venv`) carries an ABSOLUTE path
baked into `pyvenv.cfg` / console-script shebangs that still points at the
SOURCE checkout, not the new worktree. `node_modules` has no equivalent
problem (node resolves relative to the requiring file, not an absolute prefix
recorded at install time) — the pool's real, unconditional win is
`node_modules`. For `.venv`, re-running `uv sync` inside the worktree is the
**common path, not a rare fallback** — this script's hydration step does NOT
run `uv sync` for you (that revalidation gate is Story E11.3's health-check,
by design — see "Seams" below); it only copies the files and reports whether a
smoke-check of the copied interpreter succeeded, so the caller can decide.

Seams left for later stories (do not build ahead of them here):
  - E11.3 (health-check on allocation, F17): DONE — `allocate` now runs
    `pool_health.run_health_check` (dep-hash-vs-staging-HEAD re-hydrate,
    ALWAYS `.venv` revalidation via real `uv run` + `uv sync` fallback, and a
    frontend smoke build) on every candidate before handing it back, marking
    an unsanitizable candidate `suja` and retrying. See `pool_health.py`.
  - E11.4 (wiring): nothing here decides WHEN to call `allocate` — that policy
    ("sequential epics in the same Track do NOT get their own worktree, only
    parallel Tracks do") lives in the caller (`bagual-epic-runner`'s
    supervisor), wired in E11.4. This script only serves requests.

Run with: uv run scripts/pool_manager.py <subcommand> [options]
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional


# ── reuse pool_registry.py (sibling file, direct import — same technique
#    gerente_state.py uses for memlog.py) — this script never re-implements
#    registry state, mutex, or lease/heartbeat logic ────────────────────────
def _load_pool_registry():
    path = Path(__file__).resolve().parent / "pool_registry.py"
    spec = importlib.util.spec_from_file_location("pool_registry_for_pool_manager", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pool_registry = _load_pool_registry()


def _load_pool_health():
    path = Path(__file__).resolve().parent / "pool_health.py"
    spec = importlib.util.spec_from_file_location("pool_health_for_pool_manager", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pool_health = _load_pool_health()


# ── git / process helpers ──────────────────────────────────────────────────


def run_git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-c", "core.quotePath=false", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def git_out(repo: Path, *args: str) -> str:
    return run_git(repo, *args).stdout.strip()


def now_iso() -> str:
    return pool_registry.now_iso()


# ── hydration (reuses copy_ignored_artifacts.py — never reimplemented) ────


def skill_scripts_dir() -> Path:
    return Path(__file__).resolve().parent


def hydrate(project_root: Path, dest: Path, pool_dir: Path, skip_uncommitted: bool) -> dict[str, Any]:
    script = skill_scripts_dir() / "copy_ignored_artifacts.py"
    # Always exclude the pool dir itself, relative to project_root. The
    # built-in default exclude list in copy_ignored_artifacts.py already
    # covers the conventional `.claude/worktrees` location, but a
    # *configured* (`_bmad/config.yaml`) pool location outside that path
    # would not be — and other worktrees already sitting in the same pool
    # dir show up as untracked/ignored entries from the source repo's point
    # of view, so without this a hydrate() could try to recursively copy a
    # SIBLING pool worktree (or, if the pool dir's own parent has no other
    # tracked content, itself) into the one being created. Found via a real
    # infinite-recursion crash while building this script's tests — see
    # `scripts/tests/test_pool_manager.py`'s `fake_project` fixture comment.
    pool_dir_rel = pool_dir.relative_to(project_root).as_posix() if _is_relative_to(pool_dir, project_root) else None
    cmd = [sys.executable, str(script), str(project_root), str(dest)]
    if pool_dir_rel:
        cmd += ["--exclude", pool_dir_rel]
    if skip_uncommitted:
        cmd.append("--skip-uncommitted")
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def _is_relative_to(path: Path, other: Path) -> bool:
    try:
        path.relative_to(other)
        return True
    except ValueError:
        return False


def smoke_check(dest: Path) -> dict[str, Any]:
    """Best-effort, NON-FATAL verification that copied runtime artifacts still
    run post-copy — mirrors SKILL.md's "Verify" step for the single-worktree
    flow. Reports the F17 `.venv` breakage honestly instead of hiding it;
    never raises, since a broken `.venv` is an expected, documented outcome
    here (E11.3 owns turning this into an enforced re-sync gate).
    """
    checks: dict[str, Any] = {}

    node_bin = dest / "frontend" / "node_modules" / ".bin" / "tsc"
    if node_bin.exists():
        proc = subprocess.run([str(node_bin), "--version"], capture_output=True, text=True)
        checks["node_modules_tsc"] = {
            "ok": proc.returncode == 0,
            "output": (proc.stdout or proc.stderr).strip(),
        }

    venv_python = dest / "backend" / ".venv" / "bin" / "python"
    if venv_python.exists():
        proc = subprocess.run([str(venv_python), "--version"], capture_output=True, text=True)
        checks["venv_python"] = {
            "ok": proc.returncode == 0,
            "output": (proc.stdout or proc.stderr).strip(),
        }
        proc2 = subprocess.run(
            [str(venv_python), "-c", "import fastapi"], capture_output=True, text=True
        )
        checks["venv_import_smoke"] = {
            "ok": proc2.returncode == 0,
            "output": (proc2.stdout or proc2.stderr).strip()[-500:],
            "note": (
                "F17: a non-zero here on a freshly-copied .venv means the "
                "absolute-path breakage happened — `uv sync` inside the "
                "worktree is the documented common-path fix, not a bug."
            ),
        }

    return checks


# ── core lifecycle ─────────────────────────────────────────────────────


def create_one(
    project_root: Path,
    pool_dir: Path,
    name: str,
    skip_uncommitted: bool,
    from_scratch: bool,
) -> dict[str, Any]:
    dest = pool_dir / name
    branch = f"worktree-pool-{name}"
    head = git_out(project_root, "rev-parse", "HEAD")
    run_git(project_root, "worktree", "add", str(dest), "-b", branch, head)

    report: dict[str, Any] = {
        "name": name,
        "path": str(dest),
        "branch": branch,
        "pinned_to": head,
    }

    if from_scratch:
        report["hydration"] = {"strategy": "from-scratch", "note": "no copy performed — run npm install / uv sync manually"}
        report["smoke_check"] = {}
    else:
        report["hydration"] = hydrate(project_root, dest, pool_dir, skip_uncommitted)
        report["smoke_check"] = smoke_check(dest)

    return report


# ── subcommands ─────────────────────────────────────────────────────────


def cmd_create(args: argparse.Namespace) -> int:
    project_root = args.project_root
    config = pool_registry.read_pool_config(project_root)
    pool_dir = Path(args.pool_dir).resolve() if args.pool_dir else pool_registry.pool_dir_for(project_root, config)

    if args.fill:
        current = len(pool_registry.load_registry(pool_dir).get("worktrees", {}))
        count = max(0, config["size"] - current)
    else:
        count = args.count

    created = []
    for _ in range(count):
        name = pool_registry.reserve_pending(pool_dir)
        try:
            report = create_one(
                project_root, pool_dir, name, skip_uncommitted=not args.include_uncommitted, from_scratch=args.from_scratch
            )
        except Exception:
            pool_registry.abandon_reservation(pool_dir, name)
            raise
        pool_registry.finalize_created(pool_dir, name, path=report["path"], branch=report["branch"])
        created.append(report)

    print(json.dumps({"created": created, "pool_dir": str(pool_dir)}, indent=2))
    return 0


def _lease_one_candidate(project_root: Path, pool_dir: Path, owner: str, label: Optional[str]) -> dict[str, Any]:
    """Picks ONE candidate worktree via the existing 2-strategy preference
    (prewarmed pool, else copy-on-demand) — the part of `allocate` that
    predates Story E11.3, unchanged. Returns a dict with `strategy` +
    everything `pool_registry.allocate`/`commit_lease` return (name, path,
    branch, token, ...)."""
    leased = pool_registry.allocate(pool_dir, owner=owner, label=label)
    if leased is not None:
        return {"strategy": "prewarmed-pool", **leased}

    # Strategy (2): copy-on-demand — pool exhausted, hydrate one right now.
    # reserve_pending() atomically claims a DISTINCT name under the registry
    # mutex before the slow hydration starts, so two concurrent copy-on-demand
    # allocates can never collide on the same destination/branch.
    name = pool_registry.reserve_pending(pool_dir)
    try:
        report = create_one(project_root, pool_dir, name, skip_uncommitted=True, from_scratch=False)
    except Exception:
        pool_registry.abandon_reservation(pool_dir, name)
        raise
    leased = pool_registry.commit_lease(pool_dir, name, path=report["path"], branch=report["branch"], owner=owner, label=label)
    return {"strategy": "copy-on-demand", "initial_smoke_check": report["smoke_check"], **leased}


def cmd_allocate(args: argparse.Namespace) -> int:
    """`allocate` is a MANDATORY health-checked handoff (Story E11.3, F17):
    every candidate — prewarmed or copy-on-demand — passes through
    `pool_health.run_health_check` (dep-hash-vs-staging-HEAD re-hydrate,
    unconditional `.venv` revalidation via real `uv run`/`uv sync`, and a
    frontend smoke build) BEFORE this function returns it. A candidate that
    fails and cannot be sanitized is marked `suja` (via the SAME
    `pool_registry.mark_returned(cleanup_ok=False)` primitive `return`/
    `reclaim-orphan` already use for "couldn't get this worktree back to a
    trustworthy state" — no new registry state) and pulled out of rotation;
    another candidate is tried, up to `health.max_allocation_attempts`
    (config) — bounded, never infinite, so a genuinely broken `staging` fails
    loudly instead of silently manufacturing broken worktrees forever."""
    project_root = args.project_root
    config = pool_registry.read_pool_config(project_root)
    pool_dir = Path(args.pool_dir).resolve() if args.pool_dir else pool_registry.pool_dir_for(project_root, config)
    max_attempts = args.max_attempts if args.max_attempts is not None else config["health"]["max_allocation_attempts"]

    attempts: list[dict[str, Any]] = []
    for attempt_number in range(1, max_attempts + 1):
        leased = _lease_one_candidate(project_root, pool_dir, owner=args.owner, label=args.label)
        dest = Path(leased["path"])

        health = pool_health.run_health_check(
            project_root=project_root,
            dest=dest,
            pool_dir=pool_dir,
            base_branch=args.base_branch,
            config=config,
            hydrate_fn=hydrate,
        )
        attempts.append({"attempt": attempt_number, "name": leased["name"], "strategy": leased["strategy"], "health": health})

        if health["healthy"]:
            result = {**leased, "health_check": health}
            if attempt_number > 1:
                result["allocation_attempts"] = attempts
            print(json.dumps(result, indent=2))
            return 0

        # Cannot be sanitized -> suja, pulled out of rotation, try again.
        pool_registry.mark_returned(pool_dir, leased["name"], leased["token"], cleanup_ok=False, require_token=True)

    print(
        json.dumps(
            {"error": "no healthy worktree could be allocated", "max_attempts": max_attempts, "attempts": attempts},
            indent=2,
        ),
        file=sys.stderr,
    )
    return 3


def cmd_heartbeat(args: argparse.Namespace) -> int:
    return pool_registry.cmd_heartbeat(args)


def cmd_return(args: argparse.Namespace) -> int:
    return pool_registry.cmd_return(args)


def cmd_reclaim_orphan(args: argparse.Namespace) -> int:
    return pool_registry.cmd_reclaim_orphan(args)


def cmd_list(args: argparse.Namespace) -> int:
    return pool_registry.cmd_list(args)


def cmd_status(args: argparse.Namespace) -> int:
    return pool_registry.cmd_status(args)


def cmd_remove(args: argparse.Namespace) -> int:
    project_root = args.project_root
    config = pool_registry.read_pool_config(project_root)
    pool_dir = Path(args.pool_dir).resolve() if args.pool_dir else pool_registry.pool_dir_for(project_root, config)

    doc = pool_registry.load_registry(pool_dir)
    worktrees = doc.get("worktrees", {})
    if args.name not in worktrees:
        print(json.dumps({"error": f"unknown pool worktree: {args.name}"}), file=sys.stderr)
        return 2

    info = worktrees[args.name]
    if info.get("estado") == "em-uso" and not args.force:
        print(json.dumps({"error": f"{args.name} is currently leased (em-uso) — pass --force to remove anyway"}), file=sys.stderr)
        return 2

    if info.get("path"):
        run_git(project_root, "worktree", "remove", "--force", info["path"])
    if info.get("branch"):
        run_git(project_root, "branch", "-D", info["branch"], check=False)
    result = pool_registry.remove_entry(pool_dir, args.name)

    print(json.dumps({"removed": args.name, "ok": result["ok"]}, indent=2))
    return 0


# ── argparse wiring ─────────────────────────────────────────────────────


def add_common_args(sub: argparse.ArgumentParser) -> None:
    sub.add_argument("--project-root", type=Path, default=None, help="Defaults to `git rev-parse --show-toplevel` of cwd")
    sub.add_argument("--pool-dir", default=None, help="Override the configured pool location")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p_create = sub.add_parser("create", aliases=["warm"], help="Create + hydrate pool worktree(s), registered as livre")
    add_common_args(p_create)
    p_create.add_argument("--count", type=int, default=1, help="How many to create (ignored if --fill)")
    p_create.add_argument("--fill", action="store_true", help="Top up to the configured pool size instead of --count")
    p_create.add_argument("--include-uncommitted", action="store_true", help="Also carry the project root's uncommitted diff into the pool worktree (off by default — pool worktrees mirror clean staging)")
    p_create.add_argument("--from-scratch", action="store_true", help="Strategy (1) fallback: skip the hydration copy entirely (manual npm install/uv sync needed)")
    p_create.set_defaults(func=cmd_create)

    p_alloc = sub.add_parser("allocate", help="TOCTOU-safe, health-checked lease of one pool worktree (prewarmed, or copy-on-demand if pool is empty)")
    add_common_args(p_alloc)
    p_alloc.add_argument("--owner", required=True, help="Identity of the Track/epic acquiring the lease (E11.2)")
    p_alloc.add_argument("--label", default=None, help="Free-text tag for what this allocation is for")
    p_alloc.add_argument("--base-branch", default="staging", help="Branch to compare dep hashes against / re-hydrate onto if stale (E11.3)")
    p_alloc.add_argument("--max-attempts", type=int, default=None, help="Override configured health.max_allocation_attempts")
    p_alloc.set_defaults(func=cmd_allocate)

    p_hb = sub.add_parser("heartbeat", aliases=["refresh-lease"], help="Delegates to pool_registry.py — a live Track touches its lease")
    add_common_args(p_hb)
    p_hb.add_argument("name")
    p_hb.add_argument("--token", required=True)
    p_hb.set_defaults(func=cmd_heartbeat)

    p_return = sub.add_parser("return", aliases=["clean"], help="Delegates to pool_registry.py — cleanup + em-uso->livre (or ->suja)")
    add_common_args(p_return)
    p_return.add_argument("name")
    p_return.add_argument("--token", default=None, help="Required unless --force")
    p_return.add_argument("--force", action="store_true", help="Manual admin override — bypasses the owner-token check")
    p_return.add_argument("--base-branch", default="staging", help="Branch to reset the returned worktree onto (default: staging)")
    p_return.add_argument("--force-discard", action="store_true", help="TCK-20260718135718-c49f: explicitly allow discarding commits on the worktree branch that are not yet merged into --merge-target (default: dev) — bypasses the unmerged-commits guard that otherwise refuses this return")
    p_return.add_argument("--merge-target", default=None, help="Branch to check the worktree branch's commits against before allowing a destructive return (default: dev) — distinct from --base-branch, which is what the worktree gets RESET to")
    p_return.set_defaults(func=cmd_return)

    p_reclaim = sub.add_parser("reclaim-orphan", help="Delegates to pool_registry.py — heartbeat-silence orphan reclaim (F16), never a fixed lease age")
    add_common_args(p_reclaim)
    p_reclaim.add_argument("name", nargs="?", default=None, help="Reclaim a specific worktree; omit to scan every em-uso entry")
    p_reclaim.add_argument("--stale-after-seconds", type=float, default=None, help="Override configured lease.stale_after_minutes")
    p_reclaim.add_argument("--base-branch", default="staging")
    p_reclaim.add_argument("--dry-run", action="store_true", help="Report what WOULD be reclaimed without mutating anything")
    p_reclaim.set_defaults(func=cmd_reclaim_orphan)

    p_list = sub.add_parser("list", help="Delegates to pool_registry.py — show every pool worktree + its state")
    add_common_args(p_list)
    p_list.add_argument("--no-reconcile", action="store_true", help="Skip pruning entries whose worktree no longer exists on disk")
    p_list.set_defaults(func=cmd_list)

    p_status = sub.add_parser("status", help="Delegates to pool_registry.py — same as list, optionally scoped to one --name")
    add_common_args(p_status)
    p_status.add_argument("--name", default=None)
    p_status.add_argument("--no-reconcile", action="store_true")
    p_status.set_defaults(func=cmd_status)

    p_remove = sub.add_parser("remove", help="Permanently remove a pool worktree")
    add_common_args(p_remove)
    p_remove.add_argument("name")
    p_remove.add_argument("--force", action="store_true", help="Remove even if currently leased (em-uso)")
    p_remove.set_defaults(func=cmd_remove)

    args = parser.parse_args()
    if args.project_root is None:
        args.project_root = Path(git_out(Path.cwd(), "rev-parse", "--show-toplevel")).resolve()
    else:
        args.project_root = args.project_root.resolve()

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
