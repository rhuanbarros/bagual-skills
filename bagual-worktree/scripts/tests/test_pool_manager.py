#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest"]
# ///
"""Tests for pool_manager.py (Story E11.1, state layer updated for Story
E11.2's registry.yaml — see test_pool_registry.py for the registry/mutex/
lease/heartbeat logic itself, tested in isolation there).

Uses small synthetic fake git repos under tmp_path — never touches the real
<PROJETO> repo or its real worktrees. The real-repo integration test (with
actual node_modules/.venv hydration + npm run build, and the real-process
concurrency/heartbeat proofs) is run manually and reported in
ideias/sistema-artifacts/E11-1-pool-gerente.md and
ideias/sistema-artifacts/E11-2-lease-heartbeat.md, not here — pytest here
proves the state-machine/CLI logic in isolation, fast and repeatable.

Run with: uv run --with pytest pytest scripts/tests/test_pool_manager.py
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "pool_manager.py"
REGISTRY_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "pool_registry.py"


def _load_pool_registry():
    spec = importlib.util.spec_from_file_location("pool_registry_for_tests", REGISTRY_SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pool_registry = _load_pool_registry()


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    )
    return result.stdout


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args], capture_output=True, text=True
    )


def _registry(pool_dir: Path) -> dict:
    return pool_registry.load_registry(pool_dir)


@pytest.fixture
def fake_project(tmp_path):
    repo = tmp_path / "project"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "staging")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")

    (repo / ".gitignore").write_text("node_modules/\n.venv/\n")
    (repo / "README.md").write_text("hello\n")
    # Mirror the real <PROJETO> repo's setup exactly: `.claude/` itself holds
    # TRACKED content (skills, like `.claude/skills/...` there) and worktree
    # dirs are excluded via a LOCAL (uncommitted) `.git/info/exclude` entry,
    # not a committed `.gitignore` line. This matters mechanically: if `.claude/`
    # had ZERO tracked content, git's porcelain status collapses the whole
    # untracked `.claude/` into a single directory-level "??" line instead of
    # enumerating inside it — and copy_ignored_artifacts.py's exclude list only
    # matches specific path prefixes, not "ancestor of an exclude prefix", so it
    # would try to recursively copy `.claude` wholesale, including the pool
    # worktree being hydrated *inside* it (self-referential copy -> infinite
    # recursion, discovered while writing this fixture). Keeping `.claude/`
    # non-empty-and-tracked here reproduces the real repo faithfully instead of
    # masking that discovery.
    (repo / ".claude").mkdir()
    (repo / ".claude" / "marker.md").write_text("tracked .claude content\n")
    exclude_path = repo / ".git" / "info" / "exclude"
    exclude_path.write_text(exclude_path.read_text() + "**/.claude/worktrees/\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "initial")

    # fake hydration artifacts so copy_ignored_artifacts.py has something real
    # to copy (kept tiny — this is not a real node_modules/.venv)
    (repo / "node_modules").mkdir()
    (repo / "node_modules" / "marker.txt").write_text("present\n")

    return repo


def test_create_registers_livre_worktree(tmp_path, fake_project):
    pool_dir = tmp_path / "pool"
    result = _run("create", "--project-root", str(fake_project), "--pool-dir", str(pool_dir))
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert len(summary["created"]) == 1
    name = summary["created"][0]["name"]
    assert name == "pool-1"
    assert (pool_dir / name / "node_modules" / "marker.txt").exists()

    registry = _registry(pool_dir)
    assert registry["worktrees"][name]["estado"] == "livre"


def test_fill_tops_up_to_configured_size(tmp_path, fake_project):
    (fake_project / "_bmad").mkdir()
    (fake_project / "_bmad" / "config.yaml").write_text(
        "bagual_worktree:\n  pool:\n    size: 3\n    location: .claude/worktrees/pool\n"
    )
    pool_dir = fake_project / ".claude" / "worktrees" / "pool"

    result = _run("create", "--fill", "--project-root", str(fake_project))
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert len(summary["created"]) == 3

    # calling --fill again with a full pool creates nothing more
    result2 = _run("create", "--fill", "--project-root", str(fake_project))
    summary2 = json.loads(result2.stdout)
    assert len(summary2["created"]) == 0


def test_allocate_prefers_prewarmed_pool(tmp_path, fake_project):
    pool_dir = tmp_path / "pool"
    _run("create", "--project-root", str(fake_project), "--pool-dir", str(pool_dir))

    result = _run("allocate", "--project-root", str(fake_project), "--pool-dir", str(pool_dir), "--owner", "track-A", "--label", "track-A")
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["strategy"] == "prewarmed-pool"
    assert summary["name"] == "pool-1"
    assert summary["token"]  # a lease token was minted

    registry = _registry(pool_dir)
    assert registry["worktrees"]["pool-1"]["estado"] == "em-uso"
    assert registry["worktrees"]["pool-1"]["owner"] == "track-A"
    assert registry["worktrees"]["pool-1"]["label"] == "track-A"
    assert registry["worktrees"]["pool-1"]["heartbeat_at"] is not None


def test_allocate_falls_back_to_copy_on_demand_when_pool_empty(tmp_path, fake_project):
    pool_dir = tmp_path / "pool"

    result = _run("allocate", "--project-root", str(fake_project), "--pool-dir", str(pool_dir), "--owner", "track-B")
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["strategy"] == "copy-on-demand"
    assert (Path(summary["path"]) / "node_modules" / "marker.txt").exists()


def test_allocate_does_not_hand_out_same_worktree_twice(tmp_path, fake_project):
    pool_dir = tmp_path / "pool"
    _run("create", "--project-root", str(fake_project), "--pool-dir", str(pool_dir))

    first = json.loads(_run("allocate", "--project-root", str(fake_project), "--pool-dir", str(pool_dir), "--owner", "track-1").stdout)
    # pool had exactly 1 free worktree; a second allocate must NOT reuse it —
    # it must fall through to copy-on-demand instead.
    second = json.loads(_run("allocate", "--project-root", str(fake_project), "--pool-dir", str(pool_dir), "--owner", "track-2").stdout)
    assert first["name"] != second["name"]
    assert second["strategy"] == "copy-on-demand"


def test_return_resets_dirty_worktree_and_marks_livre(tmp_path, fake_project):
    pool_dir = tmp_path / "pool"
    _run("create", "--project-root", str(fake_project), "--pool-dir", str(pool_dir))
    alloc = json.loads(_run("allocate", "--project-root", str(fake_project), "--pool-dir", str(pool_dir), "--owner", "track-1").stdout)
    dest = Path(alloc["path"])

    # dirty the worktree: modify a tracked file, add an untracked file, commit
    # something extra on its branch
    (dest / "README.md").write_text("mutated during allocation\n")
    (dest / "scratch.txt").write_text("leftover junk\n")
    _git(dest, "add", "README.md")
    _git(dest, "commit", "-q", "-m", "work done during allocation")

    result = _run(
        "return", alloc["name"], "--token", alloc["token"], "--project-root", str(fake_project), "--pool-dir", str(pool_dir)
    )
    assert result.returncode == 0, result.stderr

    assert (dest / "README.md").read_text() == "hello\n"  # tracked change reverted
    assert not (dest / "scratch.txt").exists()  # untracked cruft removed
    assert (dest / "node_modules" / "marker.txt").exists()  # gitignored hydration PRESERVED
    log = _git(dest, "log", "--oneline", "-1")
    assert "work done during allocation" not in log  # extra commit discarded

    registry = _registry(pool_dir)
    entry = registry["worktrees"][alloc["name"]]
    assert entry["estado"] == "livre"
    assert entry["owner"] is None
    assert entry["token"] is None
    assert entry["label"] is None


def test_return_without_token_is_refused(tmp_path, fake_project):
    pool_dir = tmp_path / "pool"
    _run("create", "--project-root", str(fake_project), "--pool-dir", str(pool_dir))
    alloc = json.loads(_run("allocate", "--project-root", str(fake_project), "--pool-dir", str(pool_dir), "--owner", "track-1").stdout)

    wrong_token = _run("return", alloc["name"], "--token", "not-the-real-token", "--project-root", str(fake_project), "--pool-dir", str(pool_dir))
    assert wrong_token.returncode == 2

    registry = _registry(pool_dir)
    assert registry["worktrees"][alloc["name"]]["estado"] == "em-uso"  # unchanged — refused before mutation

    forced = _run("return", alloc["name"], "--force", "--project-root", str(fake_project), "--pool-dir", str(pool_dir))
    assert forced.returncode == 0, forced.stderr


def test_return_refuses_when_branch_has_unmerged_commits_ahead_of_dev(tmp_path, fake_project):
    # TCK-20260718135718-c49f: `dev` exists alongside `staging` (the fixture's
    # default branch) and starts at the same commit. The worktree's own branch
    # gets an extra commit that is reachable from neither `dev` nor `staging`
    # — the exact shape of the real incident (executor commits, `return` runs
    # before anyone merges to `dev`).
    _git(fake_project, "branch", "dev")
    pool_dir = tmp_path / "pool"
    _run("create", "--project-root", str(fake_project), "--pool-dir", str(pool_dir))
    alloc = json.loads(_run("allocate", "--project-root", str(fake_project), "--pool-dir", str(pool_dir), "--owner", "track-1").stdout)
    dest = Path(alloc["path"])

    (dest / "work.txt").write_text("unmerged dispatch output\n")
    _git(dest, "add", "work.txt")
    _git(dest, "commit", "-q", "-m", "dispatch work not yet merged to dev")

    result = _run(
        "return", alloc["name"], "--token", alloc["token"], "--project-root", str(fake_project), "--pool-dir", str(pool_dir)
    )
    assert result.returncode != 0
    payload = json.loads(result.stderr)
    assert payload["error"] == "unmerged-commits"
    assert payload["branch"] == alloc["branch"]
    assert payload["merge_target"] == "dev"
    assert payload["unmerged_commit_count"] == 1

    # refused BEFORE any mutation: worktree still em-uso, commit still there,
    # nothing reset.
    registry = _registry(pool_dir)
    assert registry["worktrees"][alloc["name"]]["estado"] == "em-uso"
    log = _git(dest, "log", "--oneline", "-1")
    assert "dispatch work not yet merged to dev" in log

    # --force-discard is the explicit escape hatch: same unmerged state, but
    # now the caller means it.
    forced = _run(
        "return", alloc["name"], "--token", alloc["token"], "--force-discard",
        "--project-root", str(fake_project), "--pool-dir", str(pool_dir),
    )
    assert forced.returncode == 0, forced.stderr
    registry_after = _registry(pool_dir)
    assert registry_after["worktrees"][alloc["name"]]["estado"] == "livre"
    log_after = _git(dest, "log", "--oneline", "-1")
    assert "dispatch work not yet merged to dev" not in log_after


def test_return_succeeds_when_branch_is_merged_into_dev(tmp_path, fake_project):
    # Same setup as above, but the commit gets merged into `dev` (from the
    # main checkout) BEFORE `return` runs — the safe, common case must still
    # work exactly as before this guard existed.
    _git(fake_project, "branch", "dev")
    pool_dir = tmp_path / "pool"
    _run("create", "--project-root", str(fake_project), "--pool-dir", str(pool_dir))
    alloc = json.loads(_run("allocate", "--project-root", str(fake_project), "--pool-dir", str(pool_dir), "--owner", "track-1").stdout)
    dest = Path(alloc["path"])

    (dest / "work.txt").write_text("merged dispatch output\n")
    _git(dest, "add", "work.txt")
    _git(dest, "commit", "-q", "-m", "dispatch work merged to dev")

    commit_sha = _git(dest, "rev-parse", "HEAD").strip()
    _git(fake_project, "checkout", "-q", "dev")
    _git(fake_project, "merge", "-q", "--ff-only", commit_sha)
    _git(fake_project, "checkout", "-q", "staging")

    result = _run(
        "return", alloc["name"], "--token", alloc["token"], "--project-root", str(fake_project), "--pool-dir", str(pool_dir)
    )
    assert result.returncode == 0, result.stderr

    registry = _registry(pool_dir)
    assert registry["worktrees"][alloc["name"]]["estado"] == "livre"
    log = _git(dest, "log", "--oneline", "-1")
    assert "dispatch work merged to dev" not in log  # reset to base-branch tip, as before


def test_return_skips_guard_when_dev_branch_does_not_exist(tmp_path, fake_project):
    # No `dev` branch in this repo at all — the guard must not block the
    # common test/child-project shape where `dev` isn't set up (or is named
    # something else), preserving pre-guard behavior exactly.
    pool_dir = tmp_path / "pool"
    _run("create", "--project-root", str(fake_project), "--pool-dir", str(pool_dir))
    alloc = json.loads(_run("allocate", "--project-root", str(fake_project), "--pool-dir", str(pool_dir), "--owner", "track-1").stdout)
    dest = Path(alloc["path"])

    (dest / "work.txt").write_text("unmerged, but no dev branch to check against\n")
    _git(dest, "add", "work.txt")
    _git(dest, "commit", "-q", "-m", "no dev branch exists")

    result = _run(
        "return", alloc["name"], "--token", alloc["token"], "--project-root", str(fake_project), "--pool-dir", str(pool_dir)
    )
    assert result.returncode == 0, result.stderr


def test_returned_worktree_is_reallocatable(tmp_path, fake_project):
    pool_dir = tmp_path / "pool"
    _run("create", "--project-root", str(fake_project), "--pool-dir", str(pool_dir))
    alloc = json.loads(_run("allocate", "--project-root", str(fake_project), "--pool-dir", str(pool_dir), "--owner", "track-1").stdout)
    _run("return", alloc["name"], "--token", alloc["token"], "--project-root", str(fake_project), "--pool-dir", str(pool_dir))

    realloc = json.loads(_run("allocate", "--project-root", str(fake_project), "--pool-dir", str(pool_dir), "--owner", "track-2").stdout)
    assert realloc["strategy"] == "prewarmed-pool"
    assert realloc["name"] == alloc["name"]
    assert realloc["token"] != alloc["token"]  # a fresh lease token, never reused


def test_heartbeat_requires_owner_token(tmp_path, fake_project):
    pool_dir = tmp_path / "pool"
    _run("create", "--project-root", str(fake_project), "--pool-dir", str(pool_dir))
    alloc = json.loads(_run("allocate", "--project-root", str(fake_project), "--pool-dir", str(pool_dir), "--owner", "track-1").stdout)

    ok = _run("heartbeat", alloc["name"], "--token", alloc["token"], "--project-root", str(fake_project), "--pool-dir", str(pool_dir))
    assert ok.returncode == 0, ok.stderr
    assert json.loads(ok.stdout)["ok"] is True

    bad = _run("heartbeat", alloc["name"], "--token", "wrong", "--project-root", str(fake_project), "--pool-dir", str(pool_dir))
    assert bad.returncode == 1
    assert json.loads(bad.stdout)["reason"] == "not-owner"


def test_remove_cleans_up_git_worktree_and_registry(tmp_path, fake_project):
    pool_dir = tmp_path / "pool"
    created = json.loads(_run("create", "--project-root", str(fake_project), "--pool-dir", str(pool_dir)).stdout)
    name = created["created"][0]["name"]
    dest = Path(created["created"][0]["path"])

    result = _run("remove", name, "--project-root", str(fake_project), "--pool-dir", str(pool_dir))
    assert result.returncode == 0, result.stderr
    assert not dest.exists()

    worktree_list = _git(fake_project, "worktree", "list", "--porcelain")
    assert str(dest) not in worktree_list

    registry = _registry(pool_dir)
    assert name not in registry["worktrees"]


def test_remove_refuses_leased_without_force(tmp_path, fake_project):
    pool_dir = tmp_path / "pool"
    _run("create", "--project-root", str(fake_project), "--pool-dir", str(pool_dir))
    alloc = json.loads(_run("allocate", "--project-root", str(fake_project), "--pool-dir", str(pool_dir), "--owner", "track-1").stdout)

    result = _run("remove", alloc["name"], "--project-root", str(fake_project), "--pool-dir", str(pool_dir))
    assert result.returncode == 2

    result_forced = _run("remove", alloc["name"], "--force", "--project-root", str(fake_project), "--pool-dir", str(pool_dir))
    assert result_forced.returncode == 0, result_forced.stderr


def test_list_reports_state(tmp_path, fake_project):
    pool_dir = tmp_path / "pool"
    _run("create", "--project-root", str(fake_project), "--pool-dir", str(pool_dir))

    result = _run("list", "--project-root", str(fake_project), "--pool-dir", str(pool_dir))
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert "pool-1" in summary["worktrees"]
    assert summary["worktrees"]["pool-1"]["estado"] == "livre"


def test_reconcile_drops_manually_removed_worktree(tmp_path, fake_project):
    pool_dir = tmp_path / "pool"
    created = json.loads(_run("create", "--project-root", str(fake_project), "--pool-dir", str(pool_dir)).stdout)
    name = created["created"][0]["name"]
    dest = Path(created["created"][0]["path"])

    # simulate an operator manually tearing down the worktree outside this script
    _git(fake_project, "worktree", "remove", "--force", str(dest))

    result = _run("list", "--project-root", str(fake_project), "--pool-dir", str(pool_dir))
    summary = json.loads(result.stdout)
    assert name not in summary["worktrees"]
