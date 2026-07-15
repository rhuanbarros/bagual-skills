#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest"]
# ///
"""Tests for merge_manager.py — Story E16.6 (T3.7): post-merge integrated-gate
BISECTION. Before this story, `merge_manager.py` had NO pytest suite at all (its
E11.5/E11.6 predecessors were proven with real, manual `git`-CLI runs documented in
their own story files, not an automated suite) — this file is the first one, scoped
to the NEW `revert-track` / `restore-track` / `bisect_revert()` surface this story
adds, plus a light regression check that the pre-existing `revert-commit` subcommand
(refactored to share `_do_revert` with the new code, but not otherwise changed) keeps
its exact original JSON contract.

Every test below drives a REAL git repository (`tmp_path`), real `git commit`/`git
revert` calls — never a mocked git — the same "real subprocess, small/fast, fully
deterministic" idiom `bagual-worktree/scripts/tests/test_pool_registry.py` already
established (e.g. its real concurrent-process `allocate` test). `bisect_revert()`'s
`gate_fn` parameter is a plain Python callable injected by each test (never a real
Agent — the actual build gate spawned by workflow.md's Step 0P.5 is inherently
LLM-driven and cannot run inside a fast unit test); this is exactly the "mock de
tempo"-equivalent injection point the story's own constraints call for: the SLOW/
external part (the gate) is a seam, injectable and swappable for a fast deterministic
fake, while the git-level bisection LOOP itself runs for real.

Run with: uv run --with pytest pytest scripts/tests/test_merge_manager.py
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "merge_manager.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("merge_manager_under_test", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


merge_manager = _load_module()


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *args], capture_output=True, text=True
    )


# ---------------------------------------------------------------------------
# Fixture: a real, throwaway git repo with 3 sequential "Track contributions"
# already committed onto it — mirrors the SHAPE Step 0P.5 already builds
# (each Track = a merge-ish commit + a delta-reapply commit, optionally a
# migration-renumber commit), without needing a real `git merge`/worktree
# pool (plain sequential commits exercise `_do_revert`'s revert logic
# identically — it auto-detects merge-vs-plain by parent count, and every
# commit here is deliberately plain/single-parent, the common case).
# ---------------------------------------------------------------------------
def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True
    )
    assert result.returncode == 0, f"git {args} failed: {result.stderr}"
    return result


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    (repo / "base.txt").write_text("base\n")
    _git(repo, "add", "base.txt")
    (repo / "sprint-status.yaml").write_text("")
    _git(repo, "add", "sprint-status.yaml")
    _git(repo, "commit", "-q", "-m", "chore: base commit")


def _commit_file(repo: Path, name: str, content: str, message: str) -> str:
    (repo / name).parent.mkdir(parents=True, exist_ok=True)
    (repo / name).write_text(content)
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _append_line(repo: Path, name: str, line: str, message: str) -> str:
    """Appends one line to `name` and commits."""
    path = repo / name
    path.write_text(path.read_text() + line + "\n")
    _git(repo, "add", name)
    _git(repo, "commit", "-q", "-m", message)
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _make_track(repo: Path, track_id: str, poison: bool = False) -> dict:
    """Builds one Track's `{merge_commit, delta_commit}` pair (mirrors
    `_track_commit_list`'s expected shape). Each Track's delta commit targets
    its OWN dedicated file (`status-{track_id}.yaml`) rather than a file
    shared across Tracks — see
    `test_bisect_revert_halts_on_genuine_git_level_conflict_during_trial`
    below for why a SHARED small file with adjacent single-line appends is
    deliberately tested SEPARATELY rather than baked into every test here:
    reverting a middle commit while a later, unrelated commit on the SAME
    tiny file sits on top can hit a genuine git 3-way-merge conflict purely
    from insufficient context lines (reproduced with real git — see that
    test) — a real, structural git limitation orthogonal to this Track's own
    bisection-ALGORITHM correctness, which is what `_make_track`'s dedicated
    per-Track files let the tests below isolate cleanly. If `poison=True`,
    the merge commit ALSO writes `BUG_MARKER` into its own file — the fake
    "gate" in the tests below fails whenever `BUG_MARKER` is present anywhere
    in the working tree."""
    own_file = f"{track_id}.txt"
    content = f"content from {track_id}\n"
    if poison:
        content += "BUG_MARKER\n"
    merge_commit = _commit_file(repo, own_file, content, f"merge: Track {track_id} into staging")
    delta_commit = _commit_file(
        repo, f"status-{track_id}.yaml", f"{track_id}: done\n", f"chore: reapply status delta for Track {track_id}"
    )
    return {"track_id": track_id, "merge_commit": merge_commit, "delta_commit": delta_commit}


def _has_bug_marker(repo: Path) -> bool:
    for path in repo.iterdir():
        if path.is_file() and path.name != ".git":
            try:
                if "BUG_MARKER" in path.read_text():
                    return True
            except UnicodeDecodeError:
                continue
    return False


@pytest.fixture
def repo3(tmp_path: Path) -> Path:
    """3 Tracks merged in order track-1, track-2, track-3 — none poisoned by
    default; each test poisons whichever Track(s) it needs."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    return repo


# ---------------------------------------------------------------------------
# revert_track_commits / restore_track_commits — round trip
# ---------------------------------------------------------------------------
def test_revert_track_then_restore_track_round_trips(repo3: Path):
    track = _make_track(repo3, "track-1", poison=True)
    assert _has_bug_marker(repo3)

    result = merge_manager.revert_track_commits(repo3, merge_manager._track_commit_list(track))
    assert result["status"] == "reverted"
    assert len(result["reverts"]) == 2  # delta_commit, merge_commit — newest-first
    assert result["reverts"][0]["label"] == "delta_commit"
    assert result["reverts"][1]["label"] == "merge_commit"
    assert not _has_bug_marker(repo3), "reverting the poisoned Track's own commits must remove the marker"

    revert_shas = [r["revert_commit"] for r in result["reverts"]]
    restore_result = merge_manager.restore_track_commits(repo3, revert_shas)
    assert restore_result["status"] == "restored"
    assert len(restore_result["restores"]) == 2
    assert _has_bug_marker(repo3), "restoring must bring the Track's original contribution back"


def test_revert_track_commits_newest_first_order(repo3: Path):
    track = _make_track(repo3, "track-1", poison=False)
    track["migration_commit"] = _commit_file(
        repo3, "supabase/migrations/x.sql", "-- migration\n", "chore: renumber migration for Track track-1"
    )
    commits = merge_manager._track_commit_list(track)
    labels = [c[0] for c in commits]
    assert labels == ["migration_commit", "delta_commit", "merge_commit"], (
        "migration (if present) must be reverted FIRST (newest), merge LAST (oldest) — "
        "mirrors the exact commit order Step 0P.5 creates them in"
    )


# ---------------------------------------------------------------------------
# revert-commit CLI — regression check: the refactor (extracting _do_revert)
# must not change the pre-existing subcommand's external JSON contract.
# ---------------------------------------------------------------------------
def test_revert_commit_cli_unchanged_contract(repo3: Path):
    track = _make_track(repo3, "track-1", poison=False)
    result = _run("revert-commit", "--project-root", str(repo3), "--commit", track["merge_commit"])
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "reverted"
    assert "revert_commit" in payload
    assert len(payload) == 2, f"unexpected extra keys in revert-commit's JSON contract: {payload}"


def test_revert_commit_cli_on_bad_commit_fails_loudly_pre_existing_behavior(repo3: Path):
    """Pre-existing behavior (unchanged by this story's `_do_revert` refactor):
    `rev-list --parents` on a nonexistent commit raises (default `run_git`
    `check=True`), so the CLI exits non-zero with a traceback rather than a
    graceful JSON error — this was already true before E16.6 (same
    `run_git(...)` call, no try/except around it then either); this test
    only pins that the refactor did not change it either way, not that it is
    the ideal behavior."""
    result = _run("revert-commit", "--project-root", str(repo3), "--commit", "not-a-real-sha")
    assert result.returncode != 0
    with pytest.raises(json.JSONDecodeError):
        json.loads(result.stdout)


# ---------------------------------------------------------------------------
# revert-track / restore-track CLI
# ---------------------------------------------------------------------------
def test_revert_track_cli_and_restore_track_cli_round_trip(repo3: Path):
    track = _make_track(repo3, "track-1", poison=True)
    result = _run(
        "revert-track",
        "--project-root", str(repo3),
        "--track-id", "track-1",
        "--merge-commit", track["merge_commit"],
        "--delta-commit", track["delta_commit"],
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "reverted"
    assert not _has_bug_marker(repo3)
    revert_shas = [r["revert_commit"] for r in payload["reverts"]]

    restore = _run(
        "restore-track",
        "--project-root", str(repo3),
        "--track-id", "track-1",
        "--revert-commits", *revert_shas,
    )
    assert restore.returncode == 0, restore.stderr
    restore_payload = json.loads(restore.stdout)
    assert restore_payload["status"] == "restored"
    assert _has_bug_marker(repo3)


# ---------------------------------------------------------------------------
# bisect_revert — the 3 core AC scenarios
# ---------------------------------------------------------------------------
def _gate_fn_no_bug_marker(repo: Path):
    return lambda: not _has_bug_marker(repo)


def test_bisect_revert_base_case_culprit_is_last_track_no_regression(repo3: Path):
    """Caso simples (culpado = último) — deve resolver na 1a tentativa, ZERO
    reverts extras além do necessário (o comportamento pré-E16.6: reverter só
    o último Track)."""
    t1 = _make_track(repo3, "track-1", poison=False)
    t2 = _make_track(repo3, "track-2", poison=False)
    t3 = _make_track(repo3, "track-3", poison=True)  # culprit

    result = merge_manager.bisect_revert(repo3, [t1, t2, t3], _gate_fn_no_bug_marker(repo3))

    assert result["status"] == "found"
    assert result["blamed_track_id"] == "track-3"
    assert len(result["tried"]) == 1, f"base case must resolve on the FIRST trial, got {result['tried']}"
    assert result["tried"][0] == {"track_id": "track-3", "reverted": True, "gate_passed": True}
    # track-1/track-2's own files must be untouched — never reverted
    assert (repo3 / "track-1.txt").exists()
    assert (repo3 / "track-2.txt").exists()
    assert not (repo3 / "track-3.txt").exists() or "BUG_MARKER" not in (repo3 / "track-3.txt").read_text()
    assert not _has_bug_marker(repo3)


def test_bisect_revert_culprit_is_first_of_three_never_over_reverts(repo3: Path):
    """Culpado = 1o de 3 Tracks: bisecção reverte em ordem reversa (3, 2, 1),
    restaura os 2 primeiros trials (saudáveis) antes de achar o real
    culpado (track-1) — no ESTADO FINAL, só track-1 fica revertido."""
    t1 = _make_track(repo3, "track-1", poison=True)  # real culprit
    t2 = _make_track(repo3, "track-2", poison=False)
    t3 = _make_track(repo3, "track-3", poison=False)

    result = merge_manager.bisect_revert(repo3, [t1, t2, t3], _gate_fn_no_bug_marker(repo3))

    assert result["status"] == "found"
    assert result["blamed_track_id"] == "track-1"
    assert len(result["tried"]) == 3, f"must try track-3, track-2 (both restored), then track-1: {result['tried']}"
    assert result["tried"][0] == {"track_id": "track-3", "reverted": False, "gate_passed": False}
    assert result["tried"][1] == {"track_id": "track-2", "reverted": False, "gate_passed": False}
    assert result["tried"][2] == {"track_id": "track-1", "reverted": True, "gate_passed": True}

    # FINAL state: track-2 and track-3's own contributions are FULLY intact
    # (never left reverted just because they were tried) — "sem reverter
    # sadios além do necessário".
    assert (repo3 / "track-2.txt").read_text() == "content from track-2\n"
    assert (repo3 / "track-3.txt").read_text() == "content from track-3\n"
    # track-1 (the real culprit) IS reverted in the final state.
    assert not (repo3 / "track-1.txt").exists()
    assert not _has_bug_marker(repo3)


def test_bisect_revert_no_individual_revert_resolves_halts_without_reverting_everyone(repo3: Path):
    """Se NENHUM revert individual resolve (o "bug" não está isolado a um
    único Track — aqui, simulado como pré-existente na base, antes de
    qualquer Track), a bisecção deve fazer HALT com motivo, e o estado final
    deve ter TODOS os 3 Tracks intactos (nunca um revert-tudo silencioso)."""
    (repo3 / "base.txt").write_text("base\nBUG_MARKER\n")
    _git(repo3, "commit", "-q", "-am", "chore: base already broken (pre-existing, not any Track's fault)")

    t1 = _make_track(repo3, "track-1", poison=False)
    t2 = _make_track(repo3, "track-2", poison=False)
    t3 = _make_track(repo3, "track-3", poison=False)

    head_before = _git(repo3, "rev-parse", "HEAD").stdout.strip()
    result = merge_manager.bisect_revert(repo3, [t1, t2, t3], _gate_fn_no_bug_marker(repo3))

    assert result["status"] == "halt"
    assert "reason" in result and result["reason"]
    assert len(result["tried"]) == 3, f"must have tried all 3 Tracks individually before halting: {result['tried']}"
    assert all(not trial["reverted"] for trial in result["tried"]), (
        "every trial must have been restored — none may remain reverted after a HALT "
        f"(never a silent revert-all): {result['tried']}"
    )
    # every Track's own file is still present — nothing was left reverted.
    assert (repo3 / "track-1.txt").exists()
    assert (repo3 / "track-2.txt").exists()
    assert (repo3 / "track-3.txt").exists()
    # HEAD is back to the EXACT same SHA as before bisection started — every
    # trial was reverted then discarded via `git reset --hard` to a
    # previously-recorded SHA, never a 2nd revert-commit pair, so nothing
    # AT ALL is left behind in history, not even a byte of it.
    head_after = _git(repo3, "rev-parse", "HEAD").stdout.strip()
    assert head_after == head_before, "HEAD must be byte-identical to before bisection — every trial was discarded, not committed"
    assert _git(repo3, "status", "--porcelain").stdout == ""


def test_bisect_revert_bounded_by_number_of_tracks(repo3: Path):
    """Bounded: for N tracks, at most N trials are ever attempted, even when
    none resolves."""
    tracks = [_make_track(repo3, f"track-{i}", poison=False) for i in range(1, 6)]
    result = merge_manager.bisect_revert(repo3, tracks, lambda: False)
    assert result["status"] == "halt"
    assert len(result["tried"]) == len(tracks) == 5


# ---------------------------------------------------------------------------
# A genuine git-level conflict during a bisection trial — proven safe
# (HALT, never a guess, never a corrupted tree), never worked around.
# ---------------------------------------------------------------------------
def test_bisect_revert_halts_on_genuine_git_level_conflict_during_trial(repo3: Path):
    """Reproduces a REAL git limitation with real git (not a hypothetical):
    reverting an OLDER commit that appended a line to a SMALL shared file,
    while a LATER, unrelated commit's own appended line to that SAME file
    still sits on top (un-reverted, since bisection only ever reverts ONE
    candidate at a time), can hit a genuine `CONFLICT (content)` purely from
    insufficient context lines around the target hunk — proven below with 2
    plain sequential commits on a near-empty file, no bisection trickery
    involved at all. `bisect_revert()` must treat this exactly like any
    other git-level revert failure: HALT immediately, `git_error` populated,
    the tree reset back to its pre-trial state (never left half-reverted,
    never silently skipped to try a DIFFERENT resolution)."""
    (repo3 / "shared.yaml").write_text("")
    _git(repo3, "add", "shared.yaml")
    _git(repo3, "commit", "-q", "-m", "chore: shared file baseline")

    older = _append_line(repo3, "shared.yaml", "older: done", "chore: older commit touches shared.yaml")
    _append_line(repo3, "shared.yaml", "newer: done", "chore: newer commit ALSO touches shared.yaml")

    # Sanity: confirm this really is a git-level conflict, independent of
    # this project's own code, before asserting bisect_revert's reaction to it.
    probe = subprocess.run(["git", "-C", str(repo3), "revert", "--no-edit", "--no-commit", older], capture_output=True, text=True)
    is_real_git_conflict = probe.returncode != 0
    subprocess.run(["git", "-C", str(repo3), "revert", "--abort"], capture_output=True, text=True, cwd=str(repo3))
    assert is_real_git_conflict, "test setup assumption failed — this git version did not reproduce the adjacency conflict; test needs a different repro"

    head_before = _git(repo3, "rev-parse", "HEAD").stdout.strip()
    fake_track = {"track_id": "shared-track", "merge_commit": older, "delta_commit": older}
    result = merge_manager.bisect_revert(repo3, [fake_track], lambda: True)

    assert result["status"] == "halt"
    assert "git_error" in result
    assert result["tried"] == []
    head_after = _git(repo3, "rev-parse", "HEAD").stdout.strip()
    assert head_after == head_before, "a failed git-level revert during a trial must leave HEAD untouched (reset to pre-trial SHA)"
    assert _git(repo3, "status", "--porcelain").stdout == "", "no leftover conflict-marker state / dirty index after the halt"
