#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest"]
# ///
"""Tests for pool_registry.py (Story E11.2 — lease + heartbeat registry, F16
orphan-by-heartbeat-silence hardening).

Covers, in isolation and fast:
  - YAML round-trip (dump_registry/parse_registry) for the exact nested shape
    this script produces.
  - Config parsing of the new 3-level `bagual_worktree.pool.lease.*` block,
    against a CUSTOM (non-default) config file — a gate only tested against
    defaults never proves the reader actually reads a file (see notes.md,
    E9.2's own lesson, repeated deliberately here).
  - The mutex's TOCTOU-safety: many *real OS processes* (not just threads —
    this must hold across separate CLI invocations, since that's how
    concurrent Tracks will actually call `allocate`) racing `allocate` against
    a small free pool NEVER produce a duplicate winner.
  - `lease_is_stale`/F16: a fresh heartbeat is never reclaimed no matter how
    OLD `lease_acquired_at` is (a long healthy epic surviving); a silent
    heartbeat past the threshold IS flagged stale regardless of how recently
    the lease was acquired.
  - `reclaim_orphan`'s destructive path only fires on entries proven stale by
    heartbeat, never touching fresh em-uso entries (dry-run and real).

The real end-to-end proof against actual throwaway pool worktrees (3 real
concurrent `pool_manager.py allocate` processes, a real fresh-heartbeat lease
surviving reclaim, a real stale-heartbeat lease being destructively reclaimed)
is run manually against the real repo and reported in
ideias/sistema-artifacts/E11-2-lease-heartbeat.md — this file proves the
mechanism in isolation, fast and repeatable.

Run with: uv run --with pytest pytest scripts/tests/test_pool_registry.py
"""

import importlib.util
import json
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "pool_registry.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("pool_registry_under_test", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


pool_registry = _load_module()


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args], capture_output=True, text=True
    )


# ---------------------------------------------------------------------------
# YAML round-trip
# ---------------------------------------------------------------------------
def test_dump_and_parse_registry_round_trips():
    doc = {
        "schema_version": 1,
        "worktrees": {
            "pool-1": {
                "path": "/tmp/pool-1", "branch": "worktree-pool-pool-1", "estado": "em-uso",
                "owner": "track-A", "token": "abc123",
                "created_at": "2026-07-12T10:00:00+00:00",
                "lease_acquired_at": "2026-07-12T10:05:00+00:00",
                "heartbeat_at": "2026-07-12T10:10:00+00:00",
                "returned_at": None, "label": "epic 42",
            },
            "pool-2": {
                "path": "/tmp/pool-2", "branch": "worktree-pool-pool-2", "estado": "livre",
                "owner": None, "token": None,
                "created_at": "2026-07-12T09:00:00+00:00",
                "lease_acquired_at": None, "heartbeat_at": None,
                "returned_at": "2026-07-12T09:50:00+00:00", "label": None,
            },
        },
    }
    text = pool_registry.dump_registry(doc)
    parsed = pool_registry.parse_registry(text)
    assert parsed["schema_version"] == 1
    assert parsed["worktrees"]["pool-1"] == doc["worktrees"]["pool-1"]
    assert parsed["worktrees"]["pool-2"] == doc["worktrees"]["pool-2"]


def test_empty_registry_round_trips():
    doc = {"schema_version": 1, "worktrees": {}}
    parsed = pool_registry.parse_registry(pool_registry.dump_registry(doc))
    assert parsed["worktrees"] == {}


def test_load_registry_missing_file_returns_empty_doc(tmp_path):
    doc = pool_registry.load_registry(tmp_path / "does-not-exist")
    assert doc == {"schema_version": 1, "worktrees": {}}


def test_load_registry_corrupted_file_is_resilient_not_fatal(tmp_path):
    pool_dir = tmp_path / "pool"
    pool_dir.mkdir()
    (pool_dir / pool_registry.REGISTRY_FILENAME).write_text("not: [valid: yaml: at all: {{{\n")
    doc = pool_registry.load_registry(pool_dir)  # must not raise
    assert "worktrees" in doc


# ---------------------------------------------------------------------------
# config — 3-level bagual_worktree.pool.lease.* block, custom file (not just
# defaults — see module docstring)
# ---------------------------------------------------------------------------
def test_read_pool_config_defaults_when_no_file(tmp_path):
    config = pool_registry.read_pool_config(tmp_path)
    assert config["size"] == pool_registry.DEFAULT_POOL_SIZE
    assert config["lease"]["heartbeat_interval_minutes"] == pool_registry.DEFAULT_HEARTBEAT_INTERVAL_MINUTES
    assert config["lease"]["stale_after_minutes"] == pool_registry.DEFAULT_STALE_AFTER_MINUTES


def test_read_pool_config_reads_custom_lease_values(tmp_path):
    (tmp_path / "_bmad").mkdir()
    (tmp_path / "_bmad" / "config.yaml").write_text(
        "bagual_worktree:\n"
        "  pool:\n"
        "    size: 5\n"
        "    location: some/other/pool/dir\n"
        "    lease:\n"
        "      heartbeat_interval_minutes: 3\n"
        "      stale_after_minutes: 45\n"
    )
    config = pool_registry.read_pool_config(tmp_path)
    assert config["size"] == 5
    assert config["location"] == "some/other/pool/dir"
    assert config["lease"]["heartbeat_interval_minutes"] == 3.0
    assert config["lease"]["stale_after_minutes"] == 45.0


def test_read_pool_config_lease_block_absent_falls_back_to_defaults(tmp_path):
    # pool.size/location customized WITHOUT a lease: sub-block — lease defaults
    # must survive untouched (no accidental cross-contamination between
    # sibling scalar keys and a nested mapping under the same parent).
    (tmp_path / "_bmad").mkdir()
    (tmp_path / "_bmad" / "config.yaml").write_text(
        "bagual_worktree:\n  pool:\n    size: 7\n"
    )
    config = pool_registry.read_pool_config(tmp_path)
    assert config["size"] == 7
    assert config["lease"]["stale_after_minutes"] == pool_registry.DEFAULT_STALE_AFTER_MINUTES


def test_read_pool_config_defaults_include_health_block(tmp_path):
    config = pool_registry.read_pool_config(tmp_path)
    assert config["health"]["max_allocation_attempts"] == pool_registry.DEFAULT_MAX_ALLOCATION_ATTEMPTS
    assert config["health"]["smoke"]["frontend_command"] == pool_registry.DEFAULT_SMOKE_FRONTEND_COMMAND
    assert config["health"]["smoke"]["backend_import"] == pool_registry.DEFAULT_SMOKE_BACKEND_IMPORT
    assert config["health"]["smoke"]["timeout_seconds"] == pool_registry.DEFAULT_SMOKE_TIMEOUT_SECONDS


def test_read_pool_config_reads_custom_health_block_a_4th_nesting_level_deep(tmp_path):
    # Story E11.3 (F17) — `pool.health.smoke.*` is a 4th nesting level under
    # `bagual_worktree:` (bagual_worktree -> pool -> health -> smoke), one
    # deeper than `pool.lease.*` — proves the stack-of-sections parser
    # generalizes past the 3 levels E11.2 exercised, with a REAL custom file
    # (not just defaults — see module docstring's cited lesson).
    (tmp_path / "_bmad").mkdir()
    (tmp_path / "_bmad" / "config.yaml").write_text(
        "bagual_worktree:\n"
        "  pool:\n"
        "    size: 4\n"
        "    lease:\n"
        "      stale_after_minutes: 12\n"
        "    health:\n"
        "      max_allocation_attempts: 5\n"
        "      smoke:\n"
        "        frontend_command: npm run lint\n"
        "        backend_import: agents\n"
        "        timeout_seconds: 42\n"
    )
    config = pool_registry.read_pool_config(tmp_path)
    # sibling sections (size, lease) must survive untouched alongside health —
    # proves the 4th-level section pop/push doesn't corrupt its siblings.
    assert config["size"] == 4
    assert config["lease"]["stale_after_minutes"] == 12.0
    assert config["health"]["max_allocation_attempts"] == 5
    assert config["health"]["smoke"]["frontend_command"] == "npm run lint"
    assert config["health"]["smoke"]["backend_import"] == "agents"
    assert config["health"]["smoke"]["timeout_seconds"] == 42.0


def test_read_pool_config_health_block_absent_falls_back_to_defaults(tmp_path):
    (tmp_path / "_bmad").mkdir()
    (tmp_path / "_bmad" / "config.yaml").write_text(
        "bagual_worktree:\n  pool:\n    size: 9\n    lease:\n      stale_after_minutes: 30\n"
    )
    config = pool_registry.read_pool_config(tmp_path)
    assert config["size"] == 9
    assert config["health"]["max_allocation_attempts"] == pool_registry.DEFAULT_MAX_ALLOCATION_ATTEMPTS
    assert config["health"]["smoke"]["frontend_command"] == pool_registry.DEFAULT_SMOKE_FRONTEND_COMMAND


# ---------------------------------------------------------------------------
# F16 — heartbeat-silence staleness, NEVER lease age
# ---------------------------------------------------------------------------
def test_fresh_heartbeat_is_not_stale_even_with_very_old_lease_acquired_at():
    entry = {
        "lease_acquired_at": "2020-01-01T00:00:00+00:00",  # 6 years "old" lease
        "heartbeat_at": pool_registry.now_iso(),  # just touched
    }
    stale, why = pool_registry.lease_is_stale(entry, stale_after_seconds=900)
    assert stale is False, f"a fresh heartbeat must never be reclaimed regardless of lease age: {why}"


def test_silent_heartbeat_past_threshold_is_stale_even_with_recent_lease_acquired_at():
    stale_ts = pool_registry.now_iso()
    # simulate: heartbeat_at recorded, then time passes without another touch.
    entry = {
        "lease_acquired_at": stale_ts,  # lease acquired "recently"
        "heartbeat_at": "2020-01-01T00:00:00+00:00",  # but heartbeat went silent long ago
    }
    stale, why = pool_registry.lease_is_stale(entry, stale_after_seconds=900)
    assert stale is True
    assert "heartbeat" in why or "silen" in why


def test_heartbeat_within_stale_after_window_is_not_stale():
    entry = {"lease_acquired_at": pool_registry.now_iso(), "heartbeat_at": pool_registry.now_iso()}
    stale, _ = pool_registry.lease_is_stale(entry, stale_after_seconds=5)
    assert stale is False


# ---------------------------------------------------------------------------
# mutex TOCTOU-safety — concurrent allocate() calls from SEPARATE OS PROCESSES
# (subprocess, not threads: this must hold across real process boundaries,
# since that's how concurrent Tracks will actually invoke `allocate`).
# ---------------------------------------------------------------------------
def _worker_allocate(args) -> dict:
    pool_dir_str, owner = args
    import importlib.util as _ilu
    from pathlib import Path as _Path

    spec = _ilu.spec_from_file_location("pool_registry_worker", _Path(__file__).resolve().parents[1] / "pool_registry.py")
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    result = mod.allocate(_Path(pool_dir_str), owner=owner)
    return result


def test_concurrent_allocate_from_separate_processes_never_duplicates(tmp_path):
    pool_dir = tmp_path / "pool"
    doc = {"schema_version": 1, "worktrees": {}}
    for i in range(1, 4):
        doc["worktrees"][f"pool-{i}"] = pool_registry._blank_entry("livre")
        doc["worktrees"][f"pool-{i}"]["path"] = f"/fake/pool-{i}"
        doc["worktrees"][f"pool-{i}"]["branch"] = f"worktree-pool-pool-{i}"
    pool_registry.save_registry(pool_dir, doc)

    owners = [f"track-{i}" for i in range(3)]
    with ProcessPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(_worker_allocate, [(str(pool_dir), owner) for owner in owners]))

    names = [r["name"] for r in results if r is not None]
    assert len(names) == 3, f"expected all 3 concurrent allocates to succeed against 3 free worktrees, got {results}"
    assert len(set(names)) == 3, f"THE catastrophic failure: two concurrent allocates got the same worktree — {names}"

    final = pool_registry.load_registry(pool_dir)
    em_uso = [n for n, e in final["worktrees"].items() if e["estado"] == "em-uso"]
    assert sorted(em_uso) == ["pool-1", "pool-2", "pool-3"]
    # every leased entry has a DISTINCT token
    tokens = {final["worktrees"][n]["token"] for n in em_uso}
    assert len(tokens) == 3


def test_reserve_pending_avoids_stray_directory_not_in_registry(tmp_path):
    """Self-review finding: a directory can exist on disk (e.g. leftover from a
    crashed prior run) without being tracked in the registry. reserve_pending()
    must not hand out that name again — `git worktree add` would then refuse
    because the destination already exists."""
    pool_dir = tmp_path / "pool"
    pool_dir.mkdir()
    (pool_dir / "pool-1").mkdir()  # stray directory, NOT in the registry
    name = pool_registry.reserve_pending(pool_dir)
    assert name == "pool-2"


def test_reclaim_orphan_reverifies_staleness_before_destroying(tmp_path, monkeypatch):
    """Self-review finding: reclaim_orphan must re-check heartbeat staleness
    IMMEDIATELY before the destructive cleanup, not only from the initial scan
    snapshot — if the owner's heartbeat lands in the gap between the scan and
    the destroy, the entry must be spared. Proven by making `load_registry`
    return a STALE snapshot on its first call (the initial scan) and a
    FRESH-heartbeat snapshot on its second call (the pre-destroy re-check),
    and asserting `cleanup_worktree` is never reached — if the code only
    checked staleness once (from the initial scan), it would call
    cleanup_worktree and this test would fail."""
    import argparse

    pool_dir = tmp_path / "pool"
    entry = pool_registry._blank_entry("em-uso")
    entry.update({
        "path": str(pool_dir / "pool-1"), "branch": "worktree-pool-pool-1",
        "owner": "track-racy", "token": "tok-racy",
        "lease_acquired_at": pool_registry.now_iso(),
        "heartbeat_at": "2020-01-01T00:00:00+00:00",  # stale in the FIRST snapshot
    })
    stale_doc = {"schema_version": 1, "worktrees": {"pool-1": dict(entry)}}
    fresh_doc = {"schema_version": 1, "worktrees": {"pool-1": dict(entry)}}
    fresh_doc["worktrees"]["pool-1"]["heartbeat_at"] = pool_registry.now_iso()  # fresh in the SECOND snapshot

    calls = {"n": 0}

    def fake_load_registry(_pool_dir):
        calls["n"] += 1
        return stale_doc if calls["n"] == 1 else fresh_doc

    def fail_if_called(*_a, **_k):
        pytest.fail("cleanup_worktree must never run once the re-check sees a fresh heartbeat")

    monkeypatch.setattr(pool_registry, "load_registry", fake_load_registry)
    monkeypatch.setattr(pool_registry, "cleanup_worktree", fail_if_called)

    args = argparse.Namespace(
        project_root=tmp_path, pool_dir=str(pool_dir), name=None,
        stale_after_seconds=900.0, base_branch="staging", dry_run=False,
    )
    rc = pool_registry.cmd_reclaim_orphan(args)
    assert rc == 0
    assert calls["n"] == 2, "expected exactly 2 load_registry calls: initial scan + pre-destroy re-check"


def test_allocate_returns_none_when_pool_exhausted(tmp_path):
    pool_dir = tmp_path / "pool"
    doc = {"schema_version": 1, "worktrees": {"pool-1": pool_registry._blank_entry("em-uso")}}
    pool_registry.save_registry(pool_dir, doc)
    result = pool_registry.allocate(pool_dir, owner="track-x")
    assert result is None


# ---------------------------------------------------------------------------
# Story E16.5 (T3.8) — optional `health_check_fn` injection on `allocate()`.
# Dependency injection only: this test file never imports `pool_health.py`,
# proving the feature works with ANY callable matching the `{"healthy": ...}`
# contract, not specifically `pool_health.run_health_check`.
# ---------------------------------------------------------------------------
def test_allocate_without_health_check_fn_preserves_current_behavior(tmp_path):
    """Backward-compat: omitting `health_check_fn` (the default) must behave
    IDENTICALLY to before this story — first free worktree leased, returned
    with no `health_check` key, no extra calls."""
    pool_dir = tmp_path / "pool"
    _seed_free_worktree(pool_dir, "pool-1")

    leased = pool_registry.allocate(pool_dir, owner="track-A")

    assert leased is not None
    assert leased["name"] == "pool-1"
    assert "health_check" not in leased
    final = pool_registry.load_registry(pool_dir)
    assert final["worktrees"]["pool-1"]["estado"] == "em-uso"
    assert final["worktrees"]["pool-1"]["owner"] == "track-A"


def test_allocate_with_healthy_check_fn_returns_immediately(tmp_path):
    pool_dir = tmp_path / "pool"
    _seed_free_worktree(pool_dir, "pool-1")
    calls = []

    def fake_health_check(entry):
        calls.append(entry["name"])
        return {"healthy": True, "detail": "all good"}

    leased = pool_registry.allocate(pool_dir, owner="track-A", health_check_fn=fake_health_check)

    assert leased is not None
    assert leased["name"] == "pool-1"
    assert leased["health_check"] == {"healthy": True, "detail": "all good"}
    assert calls == ["pool-1"]
    final = pool_registry.load_registry(pool_dir)
    assert final["worktrees"]["pool-1"]["estado"] == "em-uso"


def test_allocate_with_unhealthy_candidate_marks_suja_and_tries_next_free(tmp_path):
    pool_dir = tmp_path / "pool"
    doc = {"schema_version": 1, "worktrees": {}}
    for n in ("pool-1", "pool-2"):
        e = pool_registry._blank_entry("livre")
        e["path"], e["branch"] = str(pool_dir / n), f"worktree-pool-{n}"
        doc["worktrees"][n] = e
    pool_registry.save_registry(pool_dir, doc)

    calls = []

    def fake_health_check(entry):
        calls.append(entry["name"])
        # pool-1 is sorted first and is the one tried first — make it fail,
        # so the retry loop must pick pool-2 next.
        return {"healthy": entry["name"] != "pool-1", "detail": entry["name"]}

    leased = pool_registry.allocate(pool_dir, owner="track-A", health_check_fn=fake_health_check)

    assert leased is not None
    assert leased["name"] == "pool-2"
    assert calls == ["pool-1", "pool-2"], "expected pool-1 tried and rejected before pool-2 succeeded"

    final = pool_registry.load_registry(pool_dir)
    assert final["worktrees"]["pool-1"]["estado"] == "suja", "unhealthy candidate must be marked suja, reusing mark_returned"
    assert final["worktrees"]["pool-2"]["estado"] == "em-uso"
    assert final["worktrees"]["pool-2"]["owner"] == "track-A"


def test_allocate_returns_none_when_every_candidate_is_unhealthy(tmp_path):
    pool_dir = tmp_path / "pool"
    _seed_free_worktree(pool_dir, "pool-1")

    def always_unhealthy(entry):
        return {"healthy": False, "detail": "broken"}

    leased = pool_registry.allocate(pool_dir, owner="track-A", health_check_fn=always_unhealthy)

    assert leased is None
    final = pool_registry.load_registry(pool_dir)
    assert final["worktrees"]["pool-1"]["estado"] == "suja"


def test_cmd_allocate_forwards_health_check_fn_without_duplicating_logic(tmp_path, capsys):
    """`pool_registry.py::cmd_allocate` must delegate the health-check-call +
    suja-retry loop entirely to `allocate()` — proven here by injecting a
    fake `health_check_fn` straight into `cmd_allocate` (never through a CLI
    flag, since a real health primitive can't cross the CLI boundary) and
    asserting the SAME retry behavior as calling `allocate()` directly."""
    import argparse

    pool_dir = tmp_path / "pool"
    doc = {"schema_version": 1, "worktrees": {}}
    for n in ("pool-1", "pool-2"):
        e = pool_registry._blank_entry("livre")
        e["path"], e["branch"] = str(pool_dir / n), f"worktree-pool-{n}"
        doc["worktrees"][n] = e
    pool_registry.save_registry(pool_dir, doc)

    def fake_health_check(entry):
        return {"healthy": entry["name"] != "pool-1", "detail": entry["name"]}

    args = argparse.Namespace(project_root=tmp_path, pool_dir=str(pool_dir), owner="track-cli", label=None)
    rc = pool_registry.cmd_allocate(args, health_check_fn=fake_health_check)

    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["allocated"]["name"] == "pool-2"
    assert out["allocated"]["health_check"] == {"healthy": True, "detail": "pool-2"}

    final = pool_registry.load_registry(pool_dir)
    assert final["worktrees"]["pool-1"]["estado"] == "suja"


def test_cmd_allocate_without_health_check_fn_is_unchanged(tmp_path, capsys):
    """CLI callers (`main()`'s `args.func(args)`, which never passes
    `health_check_fn`) must be byte-for-byte unaffected by this story."""
    import argparse

    pool_dir = tmp_path / "pool"
    _seed_free_worktree(pool_dir, "pool-1")
    args = argparse.Namespace(project_root=tmp_path, pool_dir=str(pool_dir), owner="track-cli", label=None)

    rc = pool_registry.cmd_allocate(args)

    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["allocated"]["name"] == "pool-1"
    assert "health_check" not in out["allocated"]


def _worker_reserve(pool_dir_str: str) -> str:
    import importlib.util as _ilu
    from pathlib import Path as _Path

    spec = _ilu.spec_from_file_location("pool_registry_reserve_worker", _Path(__file__).resolve().parents[1] / "pool_registry.py")
    mod = _ilu.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.reserve_pending(_Path(pool_dir_str))


def test_reserve_pending_claims_distinct_names_under_concurrency(tmp_path):
    pool_dir = tmp_path / "pool"

    with ProcessPoolExecutor(max_workers=4) as executor:
        names = list(executor.map(_worker_reserve, [str(pool_dir)] * 4))

    assert len(set(names)) == 4, f"copy-on-demand reservations collided: {names}"


# ---------------------------------------------------------------------------
# lifecycle transitions — heartbeat / return / reclaim-orphan
# ---------------------------------------------------------------------------
def _seed_free_worktree(pool_dir, name="pool-1"):
    doc = {"schema_version": 1, "worktrees": {name: pool_registry._blank_entry("livre")}}
    doc["worktrees"][name]["path"] = str(pool_dir / name)
    doc["worktrees"][name]["branch"] = f"worktree-pool-{name}"
    pool_registry.save_registry(pool_dir, doc)


def test_heartbeat_requires_correct_token(tmp_path):
    pool_dir = tmp_path / "pool"
    _seed_free_worktree(pool_dir)
    leased = pool_registry.allocate(pool_dir, owner="track-A")

    ok = pool_registry.heartbeat(pool_dir, leased["name"], leased["token"])
    assert ok["ok"] is True

    bad = pool_registry.heartbeat(pool_dir, leased["name"], "wrong-token")
    assert bad["ok"] is False
    assert bad["reason"] == "not-owner"


def test_mark_returned_livre_vs_suja(tmp_path):
    pool_dir = tmp_path / "pool"
    doc = {"schema_version": 1, "worktrees": {}}
    for n in ("pool-1", "pool-2"):
        e = pool_registry._blank_entry("livre")
        e["path"], e["branch"] = str(pool_dir / n), f"worktree-pool-{n}"
        doc["worktrees"][n] = e
    pool_registry.save_registry(pool_dir, doc)

    leased1 = pool_registry.allocate(pool_dir, owner="track-A")
    leased2 = pool_registry.allocate(pool_dir, owner="track-B")

    ok_result = pool_registry.mark_returned(pool_dir, leased1["name"], leased1["token"], cleanup_ok=True, require_token=True)
    assert ok_result["estado"] == "livre"

    dirty_result = pool_registry.mark_returned(pool_dir, leased2["name"], leased2["token"], cleanup_ok=False, require_token=True)
    assert dirty_result["estado"] == "suja"

    final = pool_registry.load_registry(pool_dir)
    assert final["worktrees"][leased1["name"]]["owner"] is None
    assert final["worktrees"][leased1["name"]]["token"] is None
    assert final["worktrees"][leased2["name"]]["estado"] == "suja"


def test_find_orphans_only_flags_stale_heartbeat_em_uso_entries(tmp_path):
    pool_dir = tmp_path / "pool"
    doc = {"schema_version": 1, "worktrees": {}}

    fresh = pool_registry._blank_entry("em-uso")
    fresh.update({"path": "/fake/fresh", "branch": "b1", "owner": "track-fresh", "token": "t1",
                  "lease_acquired_at": "2020-01-01T00:00:00+00:00", "heartbeat_at": pool_registry.now_iso()})
    doc["worktrees"]["pool-fresh"] = fresh

    stale = pool_registry._blank_entry("em-uso")
    stale.update({"path": "/fake/stale", "branch": "b2", "owner": "track-stale", "token": "t2",
                  "lease_acquired_at": pool_registry.now_iso(), "heartbeat_at": "2020-01-01T00:00:00+00:00"})
    doc["worktrees"]["pool-stale"] = stale

    livre = pool_registry._blank_entry("livre")
    doc["worktrees"]["pool-free"] = livre

    pool_registry.save_registry(pool_dir, doc)

    orphans = pool_registry.find_orphans(pool_dir, stale_after_seconds=900)
    orphan_names = [o["name"] for o in orphans]
    assert orphan_names == ["pool-stale"]  # NEVER pool-fresh (long-healthy-epic safety), NEVER the livre entry


def test_reclaim_orphan_cli_dry_run_reports_without_mutating(tmp_path):
    pool_dir = tmp_path / "pool"
    doc = {"schema_version": 1, "worktrees": {}}
    stale = pool_registry._blank_entry("em-uso")
    stale.update({"path": str(pool_dir / "pool-1"), "branch": "worktree-pool-pool-1", "owner": "track-dead", "token": "t1",
                  "lease_acquired_at": pool_registry.now_iso(), "heartbeat_at": "2020-01-01T00:00:00+00:00"})
    doc["worktrees"]["pool-1"] = stale
    pool_registry.save_registry(pool_dir, doc)

    result = _run("reclaim-orphan", "--project-root", str(tmp_path), "--pool-dir", str(pool_dir), "--stale-after-seconds", "900", "--dry-run")
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert len(report["reclaimed"]) == 1
    assert report["reclaimed"][0]["dry_run"] is True

    # dry-run must NOT have mutated the registry
    unchanged = pool_registry.load_registry(pool_dir)
    assert unchanged["worktrees"]["pool-1"]["estado"] == "em-uso"


def test_reclaim_orphan_skips_fresh_heartbeat_entries(tmp_path):
    pool_dir = tmp_path / "pool"
    doc = {"schema_version": 1, "worktrees": {}}
    fresh = pool_registry._blank_entry("em-uso")
    fresh.update({"path": str(pool_dir / "pool-1"), "branch": "worktree-pool-pool-1", "owner": "track-alive", "token": "t1",
                  "lease_acquired_at": "2020-01-01T00:00:00+00:00", "heartbeat_at": pool_registry.now_iso()})
    doc["worktrees"]["pool-1"] = fresh
    pool_registry.save_registry(pool_dir, doc)

    result = _run("reclaim-orphan", "--project-root", str(tmp_path), "--pool-dir", str(pool_dir), "--stale-after-seconds", "900")
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["reclaimed"] == []
    assert len(report["skipped_fresh"]) == 1

    unchanged = pool_registry.load_registry(pool_dir)
    assert unchanged["worktrees"]["pool-1"]["estado"] == "em-uso"  # a long healthy epic is NEVER reclaimed
    assert unchanged["worktrees"]["pool-1"]["owner"] == "track-alive"


# ---------------------------------------------------------------------------
# mutex crash-safety valve (distinct from lease staleness — see module
# docstring point 1)
# ---------------------------------------------------------------------------
def test_mutex_reclaims_a_stale_lock_left_by_a_dead_process(tmp_path):
    pool_dir = tmp_path / "pool"
    pool_dir.mkdir()
    lock_path = pool_registry._mutex_path(pool_dir)
    lock_path.write_text("99999999 0\n")  # simulate a lock left by a process that died
    old_time = time.time() - 120
    import os
    os.utime(lock_path, (old_time, old_time))

    # should reclaim (age > MUTEX_STALE_AFTER_SECONDS) and succeed quickly, not
    # time out waiting for a lock nobody will ever release
    pool_registry.acquire_mutex(pool_dir, timeout_seconds=5, stale_after_seconds=30)
    pool_registry.release_mutex(pool_dir)


def test_mutex_times_out_on_a_genuinely_held_fresh_lock(tmp_path):
    pool_dir = tmp_path / "pool"
    pool_dir.mkdir()
    pool_registry.acquire_mutex(pool_dir)  # held, never released in this test
    with pytest.raises(TimeoutError):
        pool_registry.acquire_mutex(pool_dir, timeout_seconds=0.3, stale_after_seconds=30)
