#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""copy_ignored_artifacts.py — replicate everything `git worktree add` leaves behind.

`git worktree add` only carries committed history. A freshly created worktree is
missing: gitignored runtime artifacts (env files, node_modules, virtualenvs, local
secrets, generated project links) AND any uncommitted work in the source checkout
(staged/unstaged changes to tracked files, untracked-but-not-ignored new files).

This script closes both gaps for one (source, dest) worktree pair:
  1. Copies every git-ignored path (via `git status --ignored`) except a built-in
     noise list (build/test caches, prior session logs, other worktrees).
  2. Applies the source's uncommitted tracked-file diff (`git diff HEAD`) to dest.
  3. Copies untracked-but-not-ignored files (`git status` `??` entries) to dest.

Copies hardlink when source and dest share a filesystem (instant, zero extra disk)
and fall back to a real copy otherwise (e.g. cross-device).

Run with: uv run scripts/copy_ignored_artifacts.py <source> <dest>
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Matched against the basename of every path component along a candidate path.
BASENAME_EXCLUDES = [
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "*.pyc",
    "*.pyo",
    "*.log",
    ".DS_Store",
    "._*",
    ".coverage",
    "*-results.xml",
    "Thumbs.db",
]

# Matched as an exact relative path or a path prefix (path == p or path startswith p + "/").
PATH_PREFIX_EXCLUDES = [
    ".claude/worktrees",  # never recurse other worktrees into this one
    ".claude/scheduled_tasks.lock",
    ".playwright-mcp",
]

# Matched against any single path component, anywhere in the relative path.
COMPONENT_EXCLUDES = {"test-artifacts", "playwright-report", "playwright-artifacts"}


def is_excluded(relpath: str, extra_prefixes: list[str]) -> bool:
    for prefix in PATH_PREFIX_EXCLUDES + extra_prefixes:
        if relpath == prefix or relpath.startswith(prefix + "/"):
            return True
        # Story E16.5 (T3.6): `relpath` is an ANCESTOR of an excluded prefix
        # (e.g. relpath == ".claude" while ".claude/worktrees" is excluded).
        # Without this, a caller relying only on the built-in defaults (no
        # `--exclude`) copies the excluded subtree wholesale whenever `git
        # status` collapses a fully-untracked ancestor into a single "??"/"!!"
        # line instead of enumerating inside it — the exact recursion bug
        # found while writing E11.1's `fake_project` test fixture (see
        # test_pool_manager.py): a destination worktree living under that
        # collapsed ancestor (e.g. `.claude/worktrees/pool/pool-1`) gets
        # copied INTO ITSELF, raising `RecursionError`. E11.1 mitigated this
        # only at the call site (`pool_manager.py::hydrate()` always passes
        # `--exclude {pool_dir}`), leaving the function itself fragile for any
        # OTHER caller. Excluding the ancestor too is the safe, conservative
        # fix — it may skip copying unrelated content that happens to share an
        # ancestor with an excluded path, but it can never recurse into
        # itself. This is a segment-boundary check (`prefix.startswith(relpath
        # + "/")`), never a bare substring match.
        if prefix.startswith(relpath + "/"):
            return True
    parts = relpath.split("/")
    if COMPONENT_EXCLUDES & set(parts):
        return True
    basename = parts[-1]
    return any(fnmatch.fnmatch(basename, pattern) for pattern in BASENAME_EXCLUDES)


def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "core.quotePath=false", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def parse_porcelain_paths(output: str, statuses: tuple[str, ...]) -> list[str]:
    paths = []
    for line in output.splitlines():
        if len(line) < 3:
            continue
        status, rest = line[:2], line[3:]
        if status not in statuses:
            continue
        path = rest.rstrip("/")
        if " -> " in path:  # rename entries: "old -> new"
            path = path.split(" -> ", 1)[1]
        paths.append(path)
    return paths


def copy_path(source: Path, dest: Path, relpath: str) -> dict:
    src = source / relpath
    dst = dest / relpath
    if not os.path.lexists(src):
        return {"path": relpath, "status": "missing-in-source"}

    dst.parent.mkdir(parents=True, exist_ok=True)
    if os.path.lexists(dst):
        if dst.is_dir() and not dst.is_symlink():
            shutil.rmtree(dst)
        else:
            dst.unlink()

    if src.is_symlink():
        os.symlink(os.readlink(src), dst)
        return {"path": relpath, "status": "symlinked"}

    if src.is_dir():
        try:
            shutil.copytree(src, dst, copy_function=os.link, symlinks=True)
            return {"path": relpath, "status": "hardlinked"}
        except OSError:
            if dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(src, dst, symlinks=True)
            return {"path": relpath, "status": "copied"}

    try:
        os.link(src, dst)
        return {"path": relpath, "status": "hardlinked"}
    except OSError:
        shutil.copy2(src, dst)
        return {"path": relpath, "status": "copied"}


def replicate_ignored(source: Path, dest: Path, extra_excludes: list[str]) -> dict:
    output = run_git(source, "status", "--ignored=matching", "--porcelain=v1")
    ignored = parse_porcelain_paths(output, ("!!",))
    copied, skipped = [], []
    for relpath in ignored:
        if is_excluded(relpath, extra_excludes):
            skipped.append(relpath)
        else:
            copied.append(copy_path(source, dest, relpath))
    return {"copied": copied, "skipped_excluded": skipped}


def replicate_untracked(source: Path, dest: Path, extra_excludes: list[str]) -> dict:
    output = run_git(source, "status", "--porcelain=v1")
    untracked = parse_porcelain_paths(output, ("??",))
    copied = [
        copy_path(source, dest, relpath)
        for relpath in untracked
        if not is_excluded(relpath, extra_excludes)
    ]
    return {"copied": copied}


def replicate_uncommitted(source: Path, dest: Path) -> dict:
    diff = run_git(source, "diff", "HEAD", "--binary")
    if not diff.strip():
        return {"applied": False, "reason": "no uncommitted tracked changes"}

    patch_path = dest / ".worktree-creator-uncommitted.patch"
    patch_path.write_text(diff)
    try:
        subprocess.run(
            ["git", "-C", str(dest), "apply", "--binary", str(patch_path)],
            capture_output=True,
            text=True,
            check=True,
        )
        patch_path.unlink()
        return {"applied": True}
    except subprocess.CalledProcessError as exc:
        return {
            "applied": False,
            "reason": exc.stderr.strip(),
            "patch_saved_at": str(patch_path),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=Path, help="Path to the source git checkout")
    parser.add_argument("dest", type=Path, help="Path to the destination worktree")
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Extra relative path prefix to exclude from the ignored/untracked copy (repeatable)",
    )
    parser.add_argument(
        "--skip-uncommitted",
        action="store_true",
        help="Do not replicate the source's uncommitted tracked-file changes",
    )
    args = parser.parse_args()

    source = args.source.resolve()
    dest = args.dest.resolve()
    if not (source / ".git").exists():
        print(f"error: {source} is not a git checkout", file=sys.stderr)
        return 2
    if not (dest / ".git").exists():
        print(
            f"error: {dest} is not a git worktree — create it first with `git worktree add`",
            file=sys.stderr,
        )
        return 2

    summary = {
        "source": str(source),
        "dest": str(dest),
        "ignored": replicate_ignored(source, dest, args.exclude),
        "untracked": replicate_untracked(source, dest, args.exclude),
        "uncommitted": (
            {"applied": False, "reason": "skipped by --skip-uncommitted"}
            if args.skip_uncommitted
            else replicate_uncommitted(source, dest)
        ),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
