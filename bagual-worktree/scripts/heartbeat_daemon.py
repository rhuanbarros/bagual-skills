#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""heartbeat_daemon.py — Story E16.6 (T3.9): periodic wall-clock heartbeat for a
Track-Agent's pool lease, run as a DETACHED background process (via the harness's
Bash tool `run_in_background: true`, or any equivalent OS-level backgrounding —
`nohup ... &`), never inline in the Track-Agent's own foreground tool-call sequence.
This is what makes it non-blocking: `run_daemon()`'s loop below executes in a
SEPARATE OS process from the Track-Agent's own reasoning/tool calls, so it can never
serialize behind (or be serialized by) whatever Steps 1-5 work the Track-Agent is
doing in its own foreground turn, and vice versa.

Today, BEFORE this story (Story E11.4), a Track-Agent only touches its lease's
heartbeat at the END of each epic it completes (see workflow.md's Track-Agent prompt
template, HEARTBEAT section) — documented there as a residual: "An Agent cannot sleep
on a wall-clock timer mid-execution — it can only act between actions... a single
VERY long story inside a Track (longer than `lease.stale_after_minutes`, default 20
min, without finishing any epic) could, in theory, be mistaken for orphaned by
`reclaim-orphan` even while alive." This script closes that gap: it touches the SAME
lease (same `pool_registry.py::heartbeat()` primitive, same `registry.yaml` schema —
E11.2's contract is UNCHANGED, only the FREQUENCY of touches changes) on a wall-clock
cadence (`heartbeat_interval_minutes`, the exact same config key E11.2 already defines
under `bagual_worktree.pool.lease.*`) throughout an epic's execution, independent of
how long any single epic takes to finish.

Stops gracefully the moment a STOP FILE appears at `--stop-file` (the Track-Agent
creates this file, via its own Write tool, once it is done with ALL its epics —
success or failure, the SAME "at the end" moment the pre-existing end-of-epic
heartbeat call already fires at) — never relies on being killed by a signal
(unreliable across this harness's background-process lifecycle; polling a plain file
is the same simple, filesystem-only IPC primitive this whole toolset already leans on
elsewhere, e.g. the registry mutex file in `pool_registry.py`).

Testable without real wall-clock waits: `run_daemon()` accepts an injectable
`sleep_fn` (defaulting to real `time.sleep`) and `heartbeat_fn` (defaulting to
`pool_registry.heartbeat`) — tests inject FAKE versions of both (a no-op/counting
`sleep_fn`, a recording `heartbeat_fn`) to prove the loop's CADENCE and STOP-FILE
logic deterministically, in zero real wall-clock time — never asserting on real
elapsed time for that class of test. A SEPARATE, small class of test proves the
non-blocking / real-concurrency property with a REAL detached `subprocess.Popen` and
small (sub-second) real intervals — the same "real OS process, small/fast, fully
deterministic" idiom `bagual-worktree/scripts/tests/test_pool_registry.py` already
established for its own concurrency proofs.

Run standalone with: `python3 heartbeat_daemon.py run --pool-dir ... --name ...
--token ... --stop-file ... [--interval-minutes N] [--project-root ...]`
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable, Optional

_POOL_REGISTRY = None


def _pool_registry():
    """Reuses `pool_registry.py`'s primitives (`heartbeat`, `read_pool_config`,
    `pool_dir_for`) via the SAME sibling-file direct-import technique
    `pool_registry.py` itself already uses to reuse `gerente_state.py` — not a
    copy, not a second implementation of lease/heartbeat semantics."""
    global _POOL_REGISTRY
    if _POOL_REGISTRY is None:
        path = Path(__file__).resolve().parent / "pool_registry.py"
        spec = importlib.util.spec_from_file_location("pool_registry_for_heartbeat_daemon", path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _POOL_REGISTRY = module
    return _POOL_REGISTRY


# ---------------------------------------------------------------------------
# run_daemon — the core, testable loop.
# ---------------------------------------------------------------------------
def run_daemon(
    pool_dir: Path,
    name: str,
    token: str,
    interval_seconds: float,
    stop_file: Path,
    sleep_fn: Callable[[float], None] = time.sleep,
    heartbeat_fn: Optional[Callable[[Path, str, str], dict[str, Any]]] = None,
    max_iterations: Optional[int] = None,
) -> list[dict[str, Any]]:
    """Loop: sleep `interval_seconds` (via the injectable `sleep_fn` — real
    `time.sleep` by default, a fake/no-op in tests), then — UNLESS `stop_file`
    appeared while sleeping — touch the lease via `heartbeat_fn` (defaults to
    `pool_registry.heartbeat`) and record the result. Repeats until `stop_file`
    exists (checked BOTH before sleeping, so an already-stopped daemon never
    sleeps a full extra interval pointlessly, AND right after waking, so a stop
    requested mid-sleep skips the now-pointless heartbeat call) or
    `max_iterations` is reached (a safety valve for tests only — the real CLI
    entry point below never passes it, so a real daemon run is UNBOUNDED,
    relying entirely on the stop file). Returns the list of every heartbeat
    result observed, in order — used by tests to assert cadence; a real
    standalone run only needs the loop's side effects (the lease's
    `heartbeat_at` field), not this return value, since the process exits
    however the daemon's own supervisor (the Track-Agent that spawned it, or
    the harness) decides to reap it."""
    hb = heartbeat_fn or _pool_registry().heartbeat
    results: list[dict[str, Any]] = []
    iterations = 0
    while not stop_file.exists():
        sleep_fn(interval_seconds)
        if stop_file.exists():
            break
        result = hb(pool_dir, name, token)
        results.append(result)
        iterations += 1
        if max_iterations is not None and iterations >= max_iterations:
            break
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _resolve_project_root(args: argparse.Namespace) -> Path:
    if args.project_root is not None:
        return args.project_root.resolve()
    pr = _pool_registry()
    return Path(pr.git_out(Path.cwd(), "rev-parse", "--show-toplevel")).resolve()


def _resolve_pool_dir(args: argparse.Namespace, project_root: Path) -> Path:
    if args.pool_dir:
        return Path(args.pool_dir).resolve()
    pr = _pool_registry()
    config = pr.read_pool_config(project_root)
    return pr.pool_dir_for(project_root, config)


def cmd_run(args: argparse.Namespace) -> int:
    project_root = _resolve_project_root(args)
    pool_dir = _resolve_pool_dir(args, project_root)
    if args.interval_minutes is not None:
        interval_seconds = args.interval_minutes * 60.0
    else:
        pr = _pool_registry()
        interval_seconds = pr.read_pool_config(project_root)["lease"]["heartbeat_interval_minutes"] * 60.0

    stop_file = args.stop_file.resolve()
    results = run_daemon(
        pool_dir=pool_dir,
        name=args.name,
        token=args.token,
        interval_seconds=interval_seconds,
        stop_file=stop_file,
    )
    print(json.dumps({"status": "stopped", "heartbeats_sent": len(results)}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser(
        "run",
        help="Run the periodic heartbeat loop until --stop-file appears. Intended to be "
        "launched as a DETACHED background process (Bash tool run_in_background: true), "
        "never awaited inline.",
    )
    p_run.add_argument("--project-root", type=Path, default=None, help="Defaults to `git rev-parse --show-toplevel` of cwd")
    p_run.add_argument("--pool-dir", default=None, help="Override the configured pool location")
    p_run.add_argument("--name", required=True, help="The pool worktree's registry name (e.g. pool-1)")
    p_run.add_argument("--token", required=True, help="The lease token this Track-Agent was allocated")
    p_run.add_argument("--stop-file", type=Path, required=True, help="Loop exits gracefully once this file exists")
    p_run.add_argument(
        "--interval-minutes", type=float, default=None,
        help="Defaults to the configured bagual_worktree.pool.lease.heartbeat_interval_minutes (E11.2)",
    )
    p_run.set_defaults(func=cmd_run)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
