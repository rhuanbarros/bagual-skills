#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest"]
# ///
"""Tests for heartbeat_daemon.py — Story E16.6 (T3.9): periodic wall-clock heartbeat
for a Track-Agent's pool lease, run as a detached background process.

Covers, in isolation and fast (never a real multi-minute wait):
  - CADENCE: `run_daemon()`'s loop calls `heartbeat_fn` once per injected `sleep_fn`
    tick, via a completely FAKE/injected clock (`sleep_fn` never actually sleeps in
    these tests) — proves the loop's pacing logic without any real elapsed time.
  - STOP FILE: the loop exits gracefully the moment the stop file appears, checked
    both before AND after each sleep.
  - ORPHAN AVOIDANCE (the actual F16/T3.9 payoff): using the SAME crafted-timestamp
    idiom `test_pool_registry.py`'s own F16 tests already use (never a real multi-
    minute wait), proves that a lease touched periodically throughout a "long epic"
    is NOT flagged orphaned by a concurrent `find_orphans` scan, in a scenario where
    the OLD (pre-E16.6) once-per-epic-end heartbeat model WOULD have been flagged.
  - NON-BLOCKING / REAL CONCURRENCY: a real, detached `subprocess.Popen` (never
    `subprocess.run`, which would block) with small real intervals, proving the
    daemon actually ticks the registry while the test's own "foreground" code keeps
    running immediately after spawning it — the same real-OS-process idiom
    `test_pool_registry.py::test_concurrent_allocate_from_separate_processes_never_duplicates`
    already established for a different primitive.

Run with: uv run --with pytest pytest scripts/tests/test_heartbeat_daemon.py
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import time
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "heartbeat_daemon.py"
POOL_REGISTRY_PATH = Path(__file__).resolve().parents[1] / "pool_registry.py"


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


heartbeat_daemon = _load_module(SCRIPT_PATH, "heartbeat_daemon_under_test")
pool_registry = _load_module(POOL_REGISTRY_PATH, "pool_registry_under_test_hbd")


# ---------------------------------------------------------------------------
# CADENCE — fully mocked clock (sleep_fn is injected and never really sleeps),
# no stop file involved (bounded by max_iterations instead).
# ---------------------------------------------------------------------------
def test_run_daemon_calls_heartbeat_once_per_tick(tmp_path: Path):
    sleep_calls: list[float] = []
    heartbeat_calls: list[tuple] = []

    def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)  # never actually sleeps

    def fake_heartbeat(pool_dir: Path, name: str, token: str) -> dict:
        heartbeat_calls.append((pool_dir, name, token))
        return {"ok": True, "name": name, "heartbeat_at": f"tick-{len(heartbeat_calls)}"}

    stop_file = tmp_path / "stop.marker"  # never created in this test
    results = heartbeat_daemon.run_daemon(
        pool_dir=tmp_path / "pool",
        name="pool-1",
        token="tok",
        interval_seconds=300.0,  # 5 real minutes — irrelevant, sleep_fn is fake
        stop_file=stop_file,
        sleep_fn=fake_sleep,
        heartbeat_fn=fake_heartbeat,
        max_iterations=4,
    )

    assert len(results) == 4, "must call heartbeat exactly once per tick, bounded by max_iterations"
    assert len(sleep_calls) == 4
    assert all(s == 300.0 for s in sleep_calls), "must sleep the CONFIGURED interval every tick"
    assert [r["ok"] for r in results] == [True, True, True, True]


def test_run_daemon_forwards_correct_pool_dir_name_token_every_call(tmp_path: Path):
    calls = []

    def fake_heartbeat(pool_dir, name, token):
        calls.append((pool_dir, name, token))
        return {"ok": True}

    heartbeat_daemon.run_daemon(
        pool_dir=tmp_path / "pool",
        name="pool-3",
        token="secret-token",
        interval_seconds=0.0,
        stop_file=tmp_path / "never.marker",
        sleep_fn=lambda _s: None,
        heartbeat_fn=fake_heartbeat,
        max_iterations=2,
    )
    assert calls == [(tmp_path / "pool", "pool-3", "secret-token")] * 2


# ---------------------------------------------------------------------------
# STOP FILE — exits gracefully, checked before AND after sleeping.
# ---------------------------------------------------------------------------
def test_run_daemon_stops_when_stop_file_already_exists_before_first_sleep(tmp_path: Path):
    stop_file = tmp_path / "stop.marker"
    stop_file.write_text("done")

    calls = {"heartbeat": 0, "sleep": 0}

    def fake_sleep(_s):
        calls["sleep"] += 1

    def fake_heartbeat(*_a):
        calls["heartbeat"] += 1
        return {"ok": True}

    results = heartbeat_daemon.run_daemon(
        pool_dir=tmp_path / "pool", name="n", token="t",
        interval_seconds=1.0, stop_file=stop_file,
        sleep_fn=fake_sleep, heartbeat_fn=fake_heartbeat,
    )
    assert results == []
    assert calls == {"heartbeat": 0, "sleep": 0}, "a stop file present BEFORE the loop starts must skip sleeping and heartbeating entirely"


def test_run_daemon_stops_mid_loop_when_stop_file_appears_during_sleep(tmp_path: Path):
    stop_file = tmp_path / "stop.marker"
    tick_count = {"n": 0}

    def fake_sleep(_seconds):
        tick_count["n"] += 1
        if tick_count["n"] == 3:
            stop_file.write_text("done")  # simulates the Track-Agent finishing mid-sleep

    def fake_heartbeat(*_a):
        return {"ok": True}

    results = heartbeat_daemon.run_daemon(
        pool_dir=tmp_path / "pool", name="n", token="t",
        interval_seconds=1.0, stop_file=stop_file,
        sleep_fn=fake_sleep, heartbeat_fn=fake_heartbeat,
        max_iterations=100,  # would run "forever" without the stop file catching it
    )
    assert len(results) == 2, "the 3rd tick's sleep is when the stop file appears — no heartbeat call after that"
    assert tick_count["n"] == 3


# ---------------------------------------------------------------------------
# ORPHAN AVOIDANCE — the actual F16/T3.9 payoff, proven via crafted timestamps
# (the SAME idiom test_pool_registry.py's own F16 tests use), never a real
# multi-minute wait.
# ---------------------------------------------------------------------------
def test_periodic_heartbeat_keeps_a_long_epic_from_being_flagged_orphan(tmp_path: Path):
    """Simulates a 20-minute epic (longer than a 15-minute stale-after
    threshold) under the NEW (E16.6) periodic-heartbeat model: the daemon
    ticks pool_registry.heartbeat() for REAL (not faked) every simulated
    interval; `sleep_fn` is a no-op (so this test runs in real milliseconds),
    but each `heartbeat_fn` call is a REAL `pool_registry.heartbeat()` call,
    which stamps `heartbeat_at` with the REAL current wall-clock time. Since
    every call happens within real milliseconds of each other (sleep_fn is
    instant), the entry's `heartbeat_at` is ALWAYS fresh by the time a
    concurrent `find_orphans` scan runs — proving the mechanism keeps a lease
    fresh regardless of how many simulated intervals have "passed"."""
    pool_dir = tmp_path / "pool"
    pool_registry.register_new_entry(pool_dir, "pool-1", path="/fake/pool-1", branch="worktree-pool-pool-1", estado="livre")
    leased = pool_registry.allocate(pool_dir, owner="track-long-epic")
    assert leased is not None
    token = leased["token"]

    # Simulate a 20-minute epic as 4 heartbeat ticks (as if heartbeat_interval_minutes=5).
    heartbeat_daemon.run_daemon(
        pool_dir=pool_dir, name="pool-1", token=token,
        interval_seconds=0.0,  # sleep_fn below is instant regardless
        stop_file=tmp_path / "never.marker",
        sleep_fn=lambda _s: None,
        max_iterations=4,
    )

    # A concurrent scan, using a stale_after threshold representing 15 minutes
    # (900s) — the epic's SIMULATED total duration (20 min) exceeds this, but
    # since real elapsed time here is milliseconds, the heartbeat is fresh.
    orphans = pool_registry.find_orphans(pool_dir, stale_after_seconds=900.0)
    assert orphans == [], "a periodically-heartbeated lease must never be flagged orphan by a concurrent scan"

    entry = pool_registry.load_registry(pool_dir)["worktrees"]["pool-1"]
    stale, why = pool_registry.lease_is_stale(entry, stale_after_seconds=900.0)
    assert stale is False, why


def test_contrast_old_once_per_epic_end_model_WOULD_have_been_flagged_orphan(tmp_path: Path):
    """Contrast case, proving the OLD (pre-E16.6, E11.4) model's documented
    residual is real: a lease heartbeated only ONCE, at epic START, with NO
    further touches for the rest of a 20-minute epic, IS flagged orphan by a
    concurrent scan using a 15-minute stale-after threshold — via a crafted
    `heartbeat_at` 20 simulated minutes in the past (the exact idiom
    `test_pool_registry.py`'s own F16 tests use for this)."""
    pool_dir = tmp_path / "pool"
    pool_registry.register_new_entry(pool_dir, "pool-1", path="/fake/pool-1", branch="worktree-pool-pool-1", estado="livre")
    leased = pool_registry.allocate(pool_dir, owner="track-long-epic")
    assert leased is not None

    doc = pool_registry.load_registry(pool_dir)
    doc["worktrees"]["pool-1"]["heartbeat_at"] = "2020-01-01T00:00:00+00:00"  # silent for "20 minutes" (in spirit — actually years, same mechanism)
    pool_registry.save_registry(pool_dir, doc)

    orphans = pool_registry.find_orphans(pool_dir, stale_after_seconds=900.0)  # 15 min
    assert len(orphans) == 1
    assert orphans[0]["name"] == "pool-1"


# ---------------------------------------------------------------------------
# NON-BLOCKING — real detached subprocess, real (small) intervals, proving
# the daemon ticks concurrently with the "foreground" without ever being
# awaited inline.
# ---------------------------------------------------------------------------
def test_daemon_runs_as_a_real_detached_process_without_blocking_the_caller(tmp_path: Path):
    pool_dir = tmp_path / "pool"
    pool_registry.register_new_entry(pool_dir, "pool-1", path="/fake/pool-1", branch="worktree-pool-pool-1", estado="livre")
    leased = pool_registry.allocate(pool_dir, owner="track-nonblocking-test")
    assert leased is not None
    token = leased["token"]
    stop_file = tmp_path / "stop.marker"

    spawn_started_at = time.monotonic()
    proc = subprocess.Popen(
        [
            sys.executable, str(SCRIPT_PATH), "run",
            "--pool-dir", str(pool_dir),
            "--name", "pool-1",
            "--token", token,
            "--stop-file", str(stop_file),
            "--interval-minutes", str(0.05 / 60.0),  # 50ms real interval
        ],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    spawn_returned_at = time.monotonic()
    # Popen() itself must return near-instantly — this IS the "non-blocking"
    # property: spawning the daemon never makes the caller wait for even one
    # heartbeat tick, let alone the whole daemon lifetime.
    assert spawn_returned_at - spawn_started_at < 0.5, "Popen() must return immediately, never block on the daemon's own loop"

    try:
        # "Foreground work" continues here, concurrently with the daemon.
        initial_heartbeat_at = pool_registry.load_registry(pool_dir)["worktrees"]["pool-1"]["heartbeat_at"]

        deadline = time.monotonic() + 5.0
        ticked_at_least_twice = False
        seen_heartbeats: set = {initial_heartbeat_at}
        while time.monotonic() < deadline:
            current = pool_registry.load_registry(pool_dir)["worktrees"]["pool-1"]["heartbeat_at"]
            seen_heartbeats.add(current)
            if len(seen_heartbeats) >= 3:  # initial + at least 2 real ticks
                ticked_at_least_twice = True
                break
            time.sleep(0.05)

        assert ticked_at_least_twice, f"expected the detached daemon to tick the registry at least twice within 5s; saw {seen_heartbeats}"
    finally:
        stop_file.write_text("done")
        try:
            proc.wait(timeout=5.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5.0)

    assert proc.returncode == 0, proc.stderr.read() if proc.stderr else None
