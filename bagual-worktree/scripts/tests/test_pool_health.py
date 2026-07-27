#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest"]
# ///
"""Tests for pool_health.py (Story E11.3, PRD 03 FR-5c hardening F17 — the
mandatory allocation health-check: dep-hash-vs-staging-HEAD re-hydrate,
ALWAYS `.venv` revalidation via the real `uv run` invocation (falling back to
`uv sync`), and a frontend smoke build).

Two layers:
  1. Unit tests against `pool_health.py`'s functions directly, using small
     synthetic fake git repos under `tmp_path` (never the real <PROJETO> repo)
     and FAKE `uv`/`npm` binaries (tiny shell scripts, controlled by env vars,
     prepended onto PATH) so every scenario (healthy / needs-uv-sync /
     unfixable / smoke-build-fails) is deterministic and fast — no real
     dependency install ever runs here.
  2. End-to-end tests through `pool_manager.py allocate` (the real CLI
     subprocess entry point `bagual-epic-runner` will actually call in
     E11.4), proving the health-check is wired into the allocation path for
     real: a stale prewarmed worktree gets re-hydrated transparently, and an
     unfixable one is marked `suja` and never handed out — another candidate
     is tried instead.

A SEPARATE real run against the actual <PROJETO> repo (real `.venv`, real
`uv run`/`uv sync`, real `npm run build:client`, using throwaway pool
worktrees created + torn down by this session) is reported in
`ideias/sistema-artifacts/E11-3-health-check.md`, not here — pytest here
proves the control-flow/logic in isolation, fast and repeatable.

Run with: uv run --with pytest pytest scripts/tests/test_pool_health.py
"""

import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
POOL_MANAGER_SCRIPT = SCRIPTS_DIR / "pool_manager.py"


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pool_registry = _load("pool_registry_for_health_tests", "pool_registry.py")
pool_health = _load("pool_health_for_health_tests", "pool_health.py")


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    )
    return result.stdout


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(POOL_MANAGER_SCRIPT), *args], capture_output=True, text=True
    )


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


FAKE_UV_SCRIPT = """#!/usr/bin/env bash
# Per-worktree override: if a `.fake-uv-broken` marker sits at the worktree
# root (one level above `backend/`, which is always this script's cwd when
# pool_health.py invokes it), this worktree is permanently unfixable
# regardless of FAKE_UV_MODE — lets a test make ONE specific pool worktree
# broken while leaving its siblings healthy (env vars alone are global to the
# whole test process and cannot distinguish between concurrently-existing
# worktrees).
worktree_root="$(cd "$PWD/.." && pwd)"
if [ -f "$worktree_root/.fake-uv-broken" ]; then
  mode="fail_always"
else
  mode="${FAKE_UV_MODE:-ok}"
fi
marker="${FAKE_UV_SYNCED_MARKER:-/tmp/fake_uv_synced_default}"
if [ "$1" = "sync" ]; then
  if [ "$mode" = "fail_always" ]; then
    echo "fake uv sync: still broken" >&2
    exit 1
  fi
  echo "fake uv sync: resynced ai_update" >&2
  : > "$marker"
  exit 0
fi
if [ "$1" = "run" ]; then
  case "$mode" in
    ok)
      echo "Uninstalled 1 package" >&2
      echo "Installed 1 package" >&2
      exit 0
      ;;
    fail_then_ok)
      if [ -f "$marker" ]; then
        exit 0
      else
        echo "fake uv run: ai_update install record stale" >&2
        exit 1
      fi
      ;;
    fail_always)
      echo "fake uv run: broken beyond uv sync" >&2
      exit 1
      ;;
    *)
      exit 0
      ;;
  esac
fi
exit 0
"""

FAKE_NPM_SCRIPT = """#!/usr/bin/env bash
mode="${FAKE_NPM_MODE:-ok}"
if [ "$1" = "run" ]; then
  if [ "$mode" = "fail" ]; then
    echo "fake npm build: failed" >&2
    exit 1
  fi
  echo "fake npm build: ok"
  exit 0
fi
exit 0
"""


@pytest.fixture
def fake_bin(tmp_path):
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    _write_executable(bin_dir / "uv", FAKE_UV_SCRIPT)
    _write_executable(bin_dir / "npm", FAKE_NPM_SCRIPT)
    return bin_dir


@pytest.fixture
def patched_path(monkeypatch, fake_bin):
    """Prepends the fake uv/npm onto PATH for the CURRENT process (so
    `shutil.which` inside pool_health.py finds the fakes) — subprocess.run
    inherits this PATH by default (no explicit env= override in
    pool_health.py), so any real invocation the module makes hits the fakes,
    never the real `uv`/`npm` on this machine."""
    monkeypatch.setenv("PATH", f"{fake_bin}{os.pathsep}{os.environ.get('PATH', '')}")
    return fake_bin


@pytest.fixture
def fake_project_with_apps(tmp_path):
    """Same base shape as test_pool_manager.py's `fake_project`, extended
    with a `frontend/package.json` + `backend/pyproject.toml` (tracked — real
    dep manifests) and a `frontend/node_modules` marker dir (gitignored, the
    hydration stand-in) so the dep-hash + smoke-check machinery has real
    files to operate on."""
    repo = tmp_path / "project"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "staging")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")

    (repo / ".gitignore").write_text("node_modules/\n.venv/\n")
    (repo / ".claude").mkdir()
    (repo / ".claude" / "marker.md").write_text("tracked .claude content\n")
    exclude_path = repo / ".git" / "info" / "exclude"
    exclude_path.write_text(exclude_path.read_text() + "**/.claude/worktrees/\n")

    (repo / "frontend").mkdir()
    (repo / "frontend" / "package.json").write_text('{"name": "frontend", "version": "v1"}\n')
    (repo / "backend").mkdir()
    (repo / "backend" / "pyproject.toml").write_text('[project]\nname = "ai-backend"\nversion = "v1"\n')
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "initial")

    (repo / "frontend" / "node_modules").mkdir()
    (repo / "frontend" / "node_modules" / "marker.txt").write_text("v1\n")

    return repo


# ── unit tests: dep_hash_diverged ──────────────────────────────────────────


def test_dep_hash_not_diverged_when_worktree_matches_staging_head(tmp_path, fake_project_with_apps):
    repo = fake_project_with_apps
    dest = tmp_path / "wt"
    head = _git(repo, "rev-parse", "HEAD").strip()
    _git(repo, "worktree", "add", str(dest), "-b", "wt-branch", head)

    diverged, detail = pool_health.dep_hash_diverged(dest, repo, head)
    assert diverged is False
    assert detail["per_file"]["backend/pyproject.toml"]["same"] is True


def test_dep_hash_diverges_when_staging_advances_with_a_dep_change(tmp_path, fake_project_with_apps):
    repo = fake_project_with_apps
    dest = tmp_path / "wt"
    old_head = _git(repo, "rev-parse", "HEAD").strip()
    _git(repo, "worktree", "add", str(dest), "-b", "wt-branch", old_head)

    # simulate staging advancing with a dependency bump, worktree left as-is
    (repo / "backend" / "pyproject.toml").write_text('[project]\nname = "ai-backend"\nversion = "v2-new-dep"\n')
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "bump a backend dep")
    new_head = _git(repo, "rev-parse", "HEAD").strip()

    diverged, detail = pool_health.dep_hash_diverged(dest, repo, new_head)
    assert diverged is True
    assert detail["per_file"]["backend/pyproject.toml"]["same"] is False
    assert detail["per_file"]["frontend/package.json"]["same"] is True  # unrelated file untouched

    _git(repo, "worktree", "remove", "--force", str(dest))


def test_dep_hash_treats_absent_manifest_as_a_divergence_signal(tmp_path, fake_project_with_apps):
    repo = fake_project_with_apps
    dest = tmp_path / "wt"
    head = _git(repo, "rev-parse", "HEAD").strip()
    _git(repo, "worktree", "add", str(dest), "-b", "wt-branch", head)

    # A manifest that doesn't exist anywhere is a "same" (ABSENT == ABSENT) —
    # sanity-check the fixed catalog entries that were never created.
    diverged, detail = pool_health.dep_hash_diverged(dest, repo, head)
    assert detail["per_file"]["backend/uv.lock"] == {"worktree": "ABSENT", "staging_head": "ABSENT", "same": True}

    _git(repo, "worktree", "remove", "--force", str(dest))


# ── unit tests: revalidate_venv (F17) ──────────────────────────────────────


def test_revalidate_venv_ok_on_first_uv_run(tmp_path, fake_project_with_apps, patched_path, monkeypatch):
    monkeypatch.setenv("FAKE_UV_MODE", "ok")
    dest = fake_project_with_apps  # backend/pyproject.toml exists at repo root
    result = pool_health.revalidate_venv(dest, {"smoke": {"backend_import": "ai_update"}})
    assert result["ok"] is True
    assert result["attempts"] == 1
    assert result["uv_sync_ran"] is False
    assert result["resynced"] is True  # fake uv printed "Uninstalled ... Installed ..."


def test_revalidate_venv_forces_uv_sync_when_first_run_fails_then_succeeds(
    tmp_path, fake_project_with_apps, patched_path, monkeypatch
):
    monkeypatch.setenv("FAKE_UV_MODE", "fail_then_ok")
    marker = tmp_path / "synced.marker"
    monkeypatch.setenv("FAKE_UV_SYNCED_MARKER", str(marker))
    assert not marker.exists()

    dest = fake_project_with_apps
    result = pool_health.revalidate_venv(dest, {"smoke": {"backend_import": "ai_update"}})

    assert result["ok"] is True
    assert result["attempts"] == 2
    assert result["uv_sync_ran"] is True
    assert marker.exists()  # `uv sync` really ran (F17's documented common path)


def test_revalidate_venv_unfixable_marks_not_ok_even_after_uv_sync(
    tmp_path, fake_project_with_apps, patched_path, monkeypatch
):
    monkeypatch.setenv("FAKE_UV_MODE", "fail_always")
    dest = fake_project_with_apps
    result = pool_health.revalidate_venv(dest, {"smoke": {"backend_import": "ai_update"}})

    assert result["ok"] is False
    assert result["attempts"] == 2
    assert result["uv_sync_ran"] is True
    assert "still broken" in result["reason"]


def test_revalidate_venv_skips_when_no_backend_present(tmp_path):
    empty = tmp_path / "no-backend"
    empty.mkdir()
    result = pool_health.revalidate_venv(empty, {})
    assert result == {"ok": True, "skipped": True, "reason": "no backend/pyproject.toml in this worktree"}


# ── unit tests: smoke_frontend_build ───────────────────────────────────────


def test_smoke_frontend_build_ok(fake_project_with_apps, patched_path, monkeypatch):
    monkeypatch.setenv("FAKE_NPM_MODE", "ok")
    result = pool_health.smoke_frontend_build(fake_project_with_apps, {})
    assert result["ok"] is True
    assert result["command"] == "npm run build:client"


def test_smoke_frontend_build_fails(fake_project_with_apps, patched_path, monkeypatch):
    monkeypatch.setenv("FAKE_NPM_MODE", "fail")
    result = pool_health.smoke_frontend_build(fake_project_with_apps, {})
    assert result["ok"] is False
    assert result["returncode"] != 0


def test_smoke_frontend_build_skips_when_no_frontend_present(tmp_path):
    empty = tmp_path / "no-frontend"
    empty.mkdir()
    result = pool_health.smoke_frontend_build(empty, {})
    assert result == {"ok": True, "skipped": True, "reason": "no frontend/package.json in this worktree"}


# ── integration: run_health_check re-hydrates on dep-hash divergence ──────


def test_run_health_check_rehydrates_and_refreshes_node_modules_on_divergence(
    tmp_path, fake_project_with_apps, patched_path, monkeypatch
):
    monkeypatch.setenv("FAKE_UV_MODE", "ok")
    monkeypatch.setenv("FAKE_NPM_MODE", "ok")
    repo = fake_project_with_apps
    pool_dir = tmp_path / "pool"

    created = json.loads(_run_cli("create", "--project-root", str(repo), "--pool-dir", str(pool_dir)).stdout)
    dest = Path(created["created"][0]["path"])
    assert (dest / "frontend" / "node_modules" / "marker.txt").read_text() == "v1\n"

    # staging advances: a dep bump AND the source's own node_modules gets
    # "reinstalled" (simulating an operator running `npm install` on staging
    # after editing package.json — the assumption hydrate() already makes)
    (repo / "backend" / "pyproject.toml").write_text('[project]\nname = "ai-backend"\nversion = "v2"\n')
    (repo / "frontend" / "node_modules" / "marker.txt").write_text("v2\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "bump dep + reinstall")

    # reuse pool_manager.py's own hydrate() the same way cmd_allocate does
    pool_manager = _load("pool_manager_for_health_tests", "pool_manager.py")
    result = pool_health.run_health_check(
        project_root=repo,
        dest=dest,
        pool_dir=pool_dir,
        base_branch="staging",
        config=pool_registry.read_pool_config(repo),
        hydrate_fn=pool_manager.hydrate,
    )

    assert result["steps"]["dep_hash"]["diverged"] is True
    assert result["healthy"] is True
    assert (dest / "backend" / "pyproject.toml").read_text() == '[project]\nname = "ai-backend"\nversion = "v2"\n'
    assert (dest / "frontend" / "node_modules" / "marker.txt").read_text() == "v2\n"  # re-hydration really ran

    _git(repo, "worktree", "remove", "--force", str(dest))


# ── end-to-end: pool_manager.py allocate wires the mandatory gate in ──────


def test_allocate_rehydrates_a_stale_prewarmed_worktree_transparently(
    tmp_path, fake_project_with_apps, patched_path, monkeypatch
):
    monkeypatch.setenv("FAKE_UV_MODE", "ok")
    monkeypatch.setenv("FAKE_NPM_MODE", "ok")
    repo = fake_project_with_apps
    pool_dir = tmp_path / "pool"

    _run_cli("create", "--project-root", str(repo), "--pool-dir", str(pool_dir))

    (repo / "backend" / "pyproject.toml").write_text('[project]\nname = "ai-backend"\nversion = "v2"\n')
    (repo / "frontend" / "node_modules" / "marker.txt").write_text("v2\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "bump dep")

    result = _run_cli(
        "allocate", "--project-root", str(repo), "--pool-dir", str(pool_dir), "--owner", "track-A", "--base-branch", "staging"
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["health_check"]["healthy"] is True
    assert summary["health_check"]["steps"]["dep_hash"]["diverged"] is True

    dest = Path(summary["path"])
    assert (dest / "backend" / "pyproject.toml").read_text() == '[project]\nname = "ai-backend"\nversion = "v2"\n'
    assert (dest / "frontend" / "node_modules" / "marker.txt").read_text() == "v2\n"


def test_allocate_marks_unfixable_worktree_suja_and_hands_out_a_healthy_one_instead(
    tmp_path, fake_project_with_apps, patched_path, monkeypatch
):
    monkeypatch.setenv("FAKE_UV_MODE", "ok")
    monkeypatch.setenv("FAKE_NPM_MODE", "ok")
    repo = fake_project_with_apps
    pool_dir = tmp_path / "pool"

    # 2 pre-warmed worktrees; `allocate` always picks the lowest free name
    # first (pool_registry.allocate sorts free_names), so marking pool-1
    # permanently broken (via the per-worktree `.fake-uv-broken` marker, see
    # FAKE_UV_SCRIPT) deterministically makes it the FIRST candidate tried —
    # it must fail health forever, pool-2 must succeed — proves suja + retry
    # + a healthy worktree still gets handed out from the same pool.
    created = json.loads(_run_cli("create", "--count", "2", "--project-root", str(repo), "--pool-dir", str(pool_dir)).stdout)
    registry_before = pool_registry.load_registry(pool_dir)
    assert len(registry_before["worktrees"]) == 2
    first_name = sorted(registry_before["worktrees"].keys())[0]
    first_path = next(Path(w["path"]) for w in created["created"] if Path(w["path"]).name == first_name)
    (first_path / ".fake-uv-broken").write_text("permanently broken for this test\n")

    result = _run_cli(
        "allocate", "--project-root", str(repo), "--pool-dir", str(pool_dir),
        "--owner", "track-B", "--base-branch", "staging", "--max-attempts", "3",
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["health_check"]["healthy"] is True
    assert summary["name"] != first_name  # not the permanently-broken one

    registry_after = pool_registry.load_registry(pool_dir)
    assert registry_after["worktrees"][first_name]["estado"] == "suja"
    assert registry_after["worktrees"][first_name]["owner"] is None  # cleared like any other mark_returned


def test_allocate_exhausts_attempts_and_fails_loudly_when_pool_is_entirely_unfixable(
    tmp_path, fake_project_with_apps, patched_path, monkeypatch
):
    monkeypatch.setenv("FAKE_UV_MODE", "ok")
    monkeypatch.setenv("FAKE_NPM_MODE", "ok")
    repo = fake_project_with_apps
    pool_dir = tmp_path / "pool"
    created = json.loads(_run_cli("create", "--count", "2", "--project-root", str(repo), "--pool-dir", str(pool_dir)).stdout)
    for entry in created["created"]:
        (Path(entry["path"]) / ".fake-uv-broken").write_text("permanently broken for this test\n")

    result = _run_cli(
        "allocate", "--project-root", str(repo), "--pool-dir", str(pool_dir),
        "--owner", "track-C", "--base-branch", "staging", "--max-attempts", "2",
    )
    assert result.returncode == 3
    payload = json.loads(result.stderr)
    assert payload["error"] == "no healthy worktree could be allocated"
    assert len(payload["attempts"]) == 2

    registry_after = pool_registry.load_registry(pool_dir)
    assert all(entry["estado"] == "suja" for entry in registry_after["worktrees"].values())


def test_allocate_honors_a_real_custom_config_yaml_for_smoke_and_max_attempts(
    tmp_path, fake_project_with_apps, patched_path, monkeypatch
):
    """A gate that's only ever exercised against DEFAULTS never proves the
    config file is actually read (see `notes.md`'s own lesson on this exact
    class of gap) — this writes a REAL `_bmad/config.yaml` and confirms two
    independent config values took effect through the full `allocate` CLI
    path: a custom `frontend_command` shows up verbatim in the health-check
    report, and a custom `max_allocation_attempts` (smaller than the pool
    size) bounds the suja-and-retry loop without a `--max-attempts` CLI
    override."""
    monkeypatch.setenv("FAKE_UV_MODE", "ok")
    monkeypatch.setenv("FAKE_NPM_MODE", "ok")
    repo = fake_project_with_apps
    pool_dir = tmp_path / "pool"

    (repo / "_bmad").mkdir()
    (repo / "_bmad" / "config.yaml").write_text(
        "bagual_worktree:\n"
        "  pool:\n"
        "    health:\n"
        "      max_allocation_attempts: 1\n"
        "      smoke:\n"
        "        frontend_command: npm run custom-smoke-script\n"
    )

    _run_cli("create", "--project-root", str(repo), "--pool-dir", str(pool_dir))
    result = _run_cli(
        "allocate", "--project-root", str(repo), "--pool-dir", str(pool_dir), "--owner", "track-config", "--base-branch", "staging"
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    # the fake npm script doesn't care about the args past `run`, so a
    # nonsense custom command still "succeeds" — the point is the CONFIGURED
    # command string round-trips into the report, proving it was read.
    assert summary["health_check"]["steps"]["frontend_smoke"]["command"] == "npm run custom-smoke-script"

    # now prove max_allocation_attempts: 1 from config (not --max-attempts)
    # actually bounds the loop, with 2 permanently-broken worktrees available.
    monkeypatch.setenv("FAKE_UV_MODE", "fail_always")
    _run_cli("return", summary["name"], "--token", summary["token"], "--project-root", str(repo), "--pool-dir", str(pool_dir))
    _run_cli("create", "--project-root", str(repo), "--pool-dir", str(pool_dir))  # 2nd worktree, also livre
    result2 = _run_cli(
        "allocate", "--project-root", str(repo), "--pool-dir", str(pool_dir), "--owner", "track-config-2", "--base-branch", "staging"
    )
    assert result2.returncode == 3
    payload = json.loads(result2.stderr)
    assert payload["max_attempts"] == 1
    assert len(payload["attempts"]) == 1  # config's max_allocation_attempts: 1 honored, no CLI override given


def test_allocate_healthy_prewarmed_worktree_runs_full_health_check_and_reports_no_divergence(
    tmp_path, fake_project_with_apps, patched_path, monkeypatch
):
    monkeypatch.setenv("FAKE_UV_MODE", "ok")
    monkeypatch.setenv("FAKE_NPM_MODE", "ok")
    repo = fake_project_with_apps
    pool_dir = tmp_path / "pool"
    _run_cli("create", "--project-root", str(repo), "--pool-dir", str(pool_dir))

    result = _run_cli(
        "allocate", "--project-root", str(repo), "--pool-dir", str(pool_dir), "--owner", "track-D", "--base-branch", "staging"
    )
    assert result.returncode == 0, result.stderr
    summary = json.loads(result.stdout)
    assert summary["health_check"]["healthy"] is True
    assert summary["health_check"]["steps"]["dep_hash"]["diverged"] is False
    assert summary["health_check"]["steps"]["venv"]["ok"] is True
    assert summary["health_check"]["steps"]["frontend_smoke"]["ok"] is True
    assert "attempt" not in summary  # single attempt, no allocation_attempts noise on the happy path
