#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest"]
# ///
"""Tests for copy_ignored_artifacts.py.

Run with: uv run --with pytest pytest scripts/tests/test_copy_ignored_artifacts.py
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import copy_ignored_artifacts as cia  # noqa: E402

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "copy_ignored_artifacts.py"


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    )
    return result.stdout


@pytest.fixture
def source_repo(tmp_path):
    repo = tmp_path / "source"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")

    (repo / ".gitignore").write_text(
        "node_modules/\n__pycache__/\n*.log\n.env.local\n"
    )
    (repo / "tracked.txt").write_text("original content\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "initial")

    # gitignored runtime artifact that SHOULD be copied
    (repo / "node_modules" / "pkg").mkdir(parents=True)
    (repo / "node_modules" / "pkg" / "index.js").write_text("module.exports = {}\n")

    # gitignored noise that should NOT be copied
    (repo / "__pycache__").mkdir()
    (repo / "__pycache__" / "mod.pyc").write_text("junk\n")
    (repo / "run.log").write_text("log noise\n")

    # gitignored env file that SHOULD be copied
    (repo / ".env.local").write_text("SECRET=1\n")

    return repo


def _make_dest_worktree(source: Path, dest: Path) -> Path:
    _git(source, "worktree", "add", str(dest), "-b", "wt-test", "HEAD")
    return dest


def test_copies_ignored_artifact_and_skips_noise(tmp_path, source_repo):
    dest = tmp_path / "dest"
    _make_dest_worktree(source_repo, dest)

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), str(source_repo), str(dest)],
        capture_output=True,
        text=True,
        check=True,
    )
    summary = json.loads(result.stdout)

    assert (dest / "node_modules" / "pkg" / "index.js").read_text() == "module.exports = {}\n"
    assert (dest / ".env.local").read_text() == "SECRET=1\n"
    assert not (dest / "__pycache__").exists()
    assert not (dest / "run.log").exists()

    copied_paths = {entry["path"] for entry in summary["ignored"]["copied"]}
    assert "node_modules" in copied_paths
    assert ".env.local" in copied_paths
    skipped = set(summary["ignored"]["skipped_excluded"])
    assert "__pycache__" in skipped
    assert "run.log" in skipped


def test_hardlinks_when_same_filesystem(tmp_path, source_repo):
    dest = tmp_path / "dest"
    _make_dest_worktree(source_repo, dest)

    subprocess.run(
        [sys.executable, str(SCRIPT_PATH), str(source_repo), str(dest)],
        capture_output=True,
        text=True,
        check=True,
    )

    src_file = source_repo / ".env.local"
    dst_file = dest / ".env.local"
    assert src_file.stat().st_ino == dst_file.stat().st_ino


def test_copies_untracked_not_ignored_file(tmp_path, source_repo):
    (source_repo / "new_idea.md").write_text("not committed, not ignored\n")
    dest = tmp_path / "dest"
    _make_dest_worktree(source_repo, dest)

    subprocess.run(
        [sys.executable, str(SCRIPT_PATH), str(source_repo), str(dest)],
        capture_output=True,
        text=True,
        check=True,
    )

    assert (dest / "new_idea.md").read_text() == "not committed, not ignored\n"


def test_applies_uncommitted_tracked_change(tmp_path, source_repo):
    (source_repo / "tracked.txt").write_text("modified, not committed\n")
    dest = tmp_path / "dest"
    _make_dest_worktree(source_repo, dest)

    subprocess.run(
        [sys.executable, str(SCRIPT_PATH), str(source_repo), str(dest)],
        capture_output=True,
        text=True,
        check=True,
    )

    assert (dest / "tracked.txt").read_text() == "modified, not committed\n"


def test_skip_uncommitted_flag_leaves_dest_at_head(tmp_path, source_repo):
    (source_repo / "tracked.txt").write_text("modified, not committed\n")
    dest = tmp_path / "dest"
    _make_dest_worktree(source_repo, dest)

    subprocess.run(
        [sys.executable, str(SCRIPT_PATH), str(source_repo), str(dest), "--skip-uncommitted"],
        capture_output=True,
        text=True,
        check=True,
    )

    assert (dest / "tracked.txt").read_text() == "original content\n"


def test_is_excluded_matches_prefix_and_basename():
    assert cia.is_excluded(".claude/worktrees/foo", [])
    assert cia.is_excluded(".claude/worktrees", [])
    assert cia.is_excluded("backend/__pycache__", [])
    assert cia.is_excluded("a/b/thing.pyc", [])
    assert not cia.is_excluded("backend/.venv", [])
    assert cia.is_excluded("custom/skip-me", ["custom/skip-me"])


def test_is_excluded_recognizes_ancestor_of_excluded_prefix():
    """Story E16.5 (T3.6): `is_excluded()` must also exclude a path that is an
    ANCESTOR of an excluded prefix — not just an exact match or a descendant.
    `.claude` is the ancestor of the default `.claude/worktrees` exclude; a
    caller that never passes `--exclude` must still be protected (see the
    recursion regression test below for the end-to-end proof)."""
    assert cia.is_excluded(".claude", [])  # ancestor of default ".claude/worktrees"
    # a sibling of the excluded prefix (same parent, not an ancestor/descendant) stays eligible
    assert not cia.is_excluded(".claude/skills", [])
    # ancestor of a caller-supplied `--exclude` prefix is excluded too
    assert cia.is_excluded("custom", ["custom/skip-me"])
    # an unrelated tree (no excluded prefix anywhere underneath it) stays eligible
    assert not cia.is_excluded("other-dir", ["custom/nested/skip-me"])
    # a multi-level ancestor (two directories up from the excluded prefix) is excluded too
    assert cia.is_excluded("a", ["a/b/c/skip-me"])


def test_no_recursion_error_when_ancestor_of_pool_dir_is_fully_untracked(tmp_path):
    """Regression for the real bug found while writing E11.1's `fake_project`
    test fixture (see test_pool_manager.py's comment): if `.claude/` has ZERO
    tracked content, `git status --porcelain` collapses it into a single
    `?? .claude/` line instead of enumerating inside it. Before this story,
    `is_excluded(".claude", [])` did not match the default
    `.claude/worktrees` exclude (exact/descendant match only), so the script
    tried to `shutil.copytree` `.claude` wholesale INTO a destination living
    under `.claude/worktrees/...` — a self-referential copy that raises
    `RecursionError`. This reproduces the exact scenario WITHOUT passing
    `--exclude` (the call-site mitigation E11.1 applied only inside
    `pool_manager.py::hydrate()`), proving the fix now lives in
    `is_excluded()` itself and protects ANY caller, not just that one call
    site."""
    repo = tmp_path / "source"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / ".gitignore").write_text("node_modules/\n")
    (repo / "tracked.txt").write_text("hello\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "initial")

    # `.claude/` has ZERO tracked content -> `git status` collapses it to one
    # untracked line, exactly the collapse behavior that triggers the bug.
    (repo / ".claude" / "worktrees" / "pool").mkdir(parents=True)
    (repo / ".claude" / "marker-untracked.md").write_text("not tracked\n")

    dest = repo / ".claude" / "worktrees" / "pool" / "pool-1"
    _git(repo, "worktree", "add", str(dest), "-b", "wt-nested-test", "HEAD")

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), str(repo), str(dest)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
    assert "RecursionError" not in result.stderr


def test_errors_when_dest_is_not_a_worktree(tmp_path, source_repo):
    dest = tmp_path / "not-a-worktree"
    dest.mkdir()

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), str(source_repo), str(dest)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "not a git worktree" in result.stderr
