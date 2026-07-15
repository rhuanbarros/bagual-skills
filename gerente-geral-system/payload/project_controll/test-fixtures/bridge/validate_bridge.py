#!/usr/bin/env python3
"""
validate_bridge.py — bridge-declaracao-areas end-to-end proof.

Proves, with REAL subprocess runs (never mocked) against a THROWAWAY copy of the
fixtures in this directory, that:

  (a) `emit_epic_areas.py from-plan` extracts the 3 valid epic-decl sentinels from
      `plano-fixture.md` (epic-90, epic-91, epic-92) and SKIPS the deliberately
      malformed one (epic-93, invalid epic_type) — with a warning, never a guess.
  (b) The written `epic_areas:` block, fed into the REAL
      `compute_execution_graph.py --epics epic-90 epic-91 epic-92`, makes it compute
      2 PARALLEL Tracks: {epic-90} standalone, {epic-91, epic-92} together (forced by
      the declared `depends_on`, topologically ordered epic-91 before epic-92) — this
      is the actual proof that the E9.3→E10.3/E10.4 bridge is "ligado", not just
      "present in code".
  (c) A run that includes the malformed epic (`--epics epic-90 epic-93`) fail-safes
      to 1 Track / sequencial, reason "missing declaration for epic-93 (fail-safe)" —
      never a wrong "paralela".
  (d) Every other top-level key of the fixture sprint-status.yaml (`generated`,
      `last_updated`, the pre-existing `execution_graph:` block, `development_status:`
      and its 4 story entries) is preserved BYTE-FOR-BYTE.
  (e) Re-running `from-plan` against the already-updated file is a byte-identical
      no-op (idempotent — no duplicate entries, no spurious rewrite).

This is a REAL functional test (temp-dir copies of the fixtures, real subprocess
calls to both scripts) — not a static/textual check. It never touches the committed
fixture copies in this directory nor any real product/meta sprint-status.yaml.

Prints PASS/FAIL per check. Exits 0 iff every check passes, else 1.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
FIXTURES_DIR = Path(__file__).resolve().parent

EMIT_SCRIPT = REPO_ROOT / "project_controll/gerente/scripts/emit_epic_areas.py"
COMPUTE_SCRIPT = REPO_ROOT / ".claude/skills/bagual-epic-runner/scripts/compute_execution_graph.py"

PLAN_FIXTURE = FIXTURES_DIR / "plano-fixture.md"
SPRINT_STATUS_FIXTURE = FIXTURES_DIR / "sprint-status-fixture.yaml"

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> bool:
    RESULTS.append((name, condition, detail))
    status = "PASS" if condition else "FAIL"
    line = f"[{status}] {name}"
    if detail:
        line += f" — {detail}"
    print(line)
    return condition


def summarize(aborted: str = "") -> int:
    print()
    total = len(RESULTS)
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    failed = total - passed
    suffix = f" (aborted early — {aborted})" if aborted else ""
    print(f"SUMMARY: {passed}/{total} checks passed, {failed} failed{suffix}")
    return 0 if failed == 0 else 1


def run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, *args], capture_output=True, text=True, check=False)


def main() -> int:
    print(f"Repo root resolved as: {REPO_ROOT}")
    print()

    if not check("emit_epic_areas.py exists", EMIT_SCRIPT.is_file(), str(EMIT_SCRIPT)):
        return summarize(aborted="emit_epic_areas.py missing")
    if not check("compute_execution_graph.py exists", COMPUTE_SCRIPT.is_file(), str(COMPUTE_SCRIPT)):
        return summarize(aborted="compute_execution_graph.py missing")
    if not check("plano-fixture.md exists", PLAN_FIXTURE.is_file(), str(PLAN_FIXTURE)):
        return summarize(aborted="plano-fixture.md missing")
    if not check("sprint-status-fixture.yaml exists", SPRINT_STATUS_FIXTURE.is_file(), str(SPRINT_STATUS_FIXTURE)):
        return summarize(aborted="sprint-status-fixture.yaml missing")

    with tempfile.TemporaryDirectory(prefix="bridge-e2e-") as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        working_sprint_status = tmp_dir / "sprint-status.yaml"
        shutil.copyfile(SPRINT_STATUS_FIXTURE, working_sprint_status)
        original_text = working_sprint_status.read_text(encoding="utf-8")

        # --------------------------------------------------------------
        # (a) from-plan: extraction + skip malformed + write
        # --------------------------------------------------------------
        print()
        print("-- (a) emit_epic_areas.py from-plan: extraction, fail-safe skip, write --")

        result_a = run(
            [
                str(EMIT_SCRIPT),
                "from-plan",
                "--plan",
                str(PLAN_FIXTURE),
                "--sprint-status",
                str(working_sprint_status),
            ]
        )
        check("from-plan exits 0", result_a.returncode == 0, f"exit={result_a.returncode} stderr={result_a.stderr!r}")
        check(
            "from-plan reports writing 3 epics (epic-90, epic-91, epic-92)",
            "epic-90" in result_a.stderr and "epic-91" in result_a.stderr and "epic-92" in result_a.stderr,
            result_a.stderr.strip(),
        )
        check(
            "from-plan warns about the malformed epic-93 sentinel and does NOT report writing it",
            "epic-93" in result_a.stderr
            and "invalid epic_type" in result_a.stderr
            and "wrote/updated epic_areas: for 3 epic(s)" in result_a.stderr,
            result_a.stderr.strip(),
        )

        new_text = working_sprint_status.read_text(encoding="utf-8")
        check("sprint-status.yaml was actually modified on disk", new_text != original_text)

        epic_areas_match = re.search(r"^epic_areas:\s*\n((?:  .+\n?)+)", new_text, re.MULTILINE)
        check("a new epic_areas: block exists after from-plan", epic_areas_match is not None)

        parsed_entries: dict[str, dict] = {}
        if epic_areas_match:
            for line in epic_areas_match.group(1).splitlines():
                m = re.match(r"^\s+([A-Za-z0-9_.\-]+):\s*(\{.*\})\s*$", line)
                if m:
                    parsed_entries[m.group(1)] = json.loads(m.group(2))

        check(
            "epic_areas: contains exactly {epic-90, epic-91, epic-92} — NOT epic-93",
            set(parsed_entries.keys()) == {"epic-90", "epic-91", "epic-92"},
            f"found keys: {sorted(parsed_entries.keys())}",
        )
        check(
            "epic-92's entry carries depends_on: ['epic-91']",
            parsed_entries.get("epic-92", {}).get("depends_on") == ["epic-91"],
            str(parsed_entries.get("epic-92")),
        )

        # --------------------------------------------------------------
        # (d) preserve-the-rest — every other top-level key untouched
        # --------------------------------------------------------------
        print()
        print("-- (d) preserve-the-rest: every OTHER top-level key untouched, byte-for-byte --")

        check(
            "`generated:` line unchanged",
            'generated: "2026-07-12"' in new_text,
        )
        check(
            "`last_updated:` line unchanged",
            'last_updated: "2026-07-12"  # fixture baseline, untouched by the bridge script' in new_text,
        )
        check(
            "pre-existing `execution_graph:` block (mode: trivial-placeholder) untouched",
            'mode: "trivial-placeholder"' in new_text and 'track_id: "track-1"' in new_text,
        )
        check(
            "`development_status:` and all 4 fixture epic entries (90/91/92/93) still present",
            all(f"epic-{n}:" in new_text for n in (90, 91, 92, 93))
            and "development_status:" in new_text,
        )
        # Belt-and-suspenders: everything OUTSIDE the newly-inserted epic_areas: block
        # must be byte-identical to the original file — both the prefix (header
        # comments + the pre-existing execution_graph: block) and the tail
        # (development_status: onward, where the new block was spliced in just
        # before it).
        anchor_original = original_text.index("development_status:")
        prefix_original = original_text[:anchor_original]
        tail_original = original_text[anchor_original:]
        check(
            "the header + pre-existing execution_graph: block (everything before "
            "development_status:) is byte-identical to the original file",
            new_text.startswith(prefix_original),
        )
        check(
            "the entire development_status: tail is byte-identical to the original file",
            new_text.endswith(tail_original),
        )

        # --------------------------------------------------------------
        # (e) idempotency
        # --------------------------------------------------------------
        print()
        print("-- (e) idempotency: re-running from-plan on the already-updated file is a no-op --")

        result_e = run(
            [
                str(EMIT_SCRIPT),
                "from-plan",
                "--plan",
                str(PLAN_FIXTURE),
                "--sprint-status",
                str(working_sprint_status),
            ]
        )
        check("second from-plan run exits 0", result_e.returncode == 0)
        check(
            "second run reports idempotent no-op (not a fresh write)",
            "already up to date (idempotent no-op)" in result_e.stderr,
            result_e.stderr.strip(),
        )
        rerun_text = working_sprint_status.read_text(encoding="utf-8")
        check("file content byte-identical after the second run", rerun_text == new_text)

        # --------------------------------------------------------------
        # (b) REAL compute_execution_graph.py: prove 2 parallel Tracks
        # --------------------------------------------------------------
        print()
        print("-- (b) REAL compute_execution_graph.py: prove 2 PARALLEL Tracks were unlocked --")

        result_graph = run(
            [
                str(COMPUTE_SCRIPT),
                "--epics",
                "epic-90",
                "epic-91",
                "epic-92",
                "--sprint-status",
                str(working_sprint_status),
                "--date",
                "2026-07-12",
            ]
        )
        check("compute_execution_graph.py exits 0", result_graph.returncode == 0, result_graph.stderr.strip())

        graph = None
        if result_graph.returncode == 0:
            try:
                graph = json.loads(result_graph.stdout)
            except json.JSONDecodeError as exc:
                check("compute_execution_graph.py stdout parses as JSON", False, str(exc))

        if graph is not None:
            check("compute_execution_graph.py stdout parses as JSON", True)
            tracks = graph.get("tracks", [])
            check("graph computed exactly 2 Tracks", len(tracks) == 2, json.dumps(tracks, indent=2))

            track_epic_sets = [tuple(t["epics"]) for t in tracks]
            check(
                "one Track is exactly {epic-90} (standalone, disjoint)",
                ("epic-90",) in track_epic_sets,
                str(track_epic_sets),
            )
            check(
                "the other Track is exactly [epic-91, epic-92] IN THAT ORDER (dependency-forced, topo-sorted)",
                ("epic-91", "epic-92") in track_epic_sets,
                str(track_epic_sets),
            )

            pairs_by_key = {tuple(sorted(p["epics"])): p for p in graph.get("pairs", [])}
            pair_90_91 = pairs_by_key.get(("epic-90", "epic-91"))
            check(
                "pair (epic-90, epic-91) relation is 'paralela'",
                pair_90_91 is not None and pair_90_91["relation"] == "paralela",
                str(pair_90_91),
            )
            pair_91_92 = pairs_by_key.get(("epic-91", "epic-92"))
            check(
                "pair (epic-91, epic-92) relation is 'sequencial' (declared dependency)",
                pair_91_92 is not None
                and pair_91_92["relation"] == "sequencial"
                and "dependency" in pair_91_92["reason"],
                str(pair_91_92),
            )
        else:
            check("graph computed exactly 2 Tracks", False, "graph JSON unavailable")
            check("one Track is exactly {epic-90} (standalone, disjoint)", False, "graph JSON unavailable")
            check(
                "the other Track is exactly [epic-91, epic-92] IN THAT ORDER (dependency-forced, topo-sorted)",
                False,
                "graph JSON unavailable",
            )
            check("pair (epic-90, epic-91) relation is 'paralela'", False, "graph JSON unavailable")
            check(
                "pair (epic-91, epic-92) relation is 'sequencial' (declared dependency)",
                False,
                "graph JSON unavailable",
            )

        # --------------------------------------------------------------
        # (c) fail-safe proof: malformed declaration never produces a wrong "paralela"
        # --------------------------------------------------------------
        print()
        print("-- (c) fail-safe proof: epic-93 (malformed) never got written -> forces sequencial --")

        result_failsafe = run(
            [
                str(COMPUTE_SCRIPT),
                "--epics",
                "epic-90",
                "epic-93",
                "--sprint-status",
                str(working_sprint_status),
                "--date",
                "2026-07-12",
            ]
        )
        check("fail-safe compute run exits 0", result_failsafe.returncode == 0, result_failsafe.stderr.strip())
        failsafe_graph = None
        if result_failsafe.returncode == 0:
            try:
                failsafe_graph = json.loads(result_failsafe.stdout)
            except json.JSONDecodeError as exc:
                check("fail-safe run stdout parses as JSON", False, str(exc))
        if failsafe_graph is not None:
            check("fail-safe run stdout parses as JSON", True)
            failsafe_tracks = failsafe_graph.get("tracks", [])
            check(
                "fail-safe run computed exactly 1 Track (never a wrong parallel)",
                len(failsafe_tracks) == 1,
                json.dumps(failsafe_tracks, indent=2),
            )
            failsafe_pairs = failsafe_graph.get("pairs", [])
            pair_90_93 = failsafe_pairs[0] if failsafe_pairs else None
            check(
                "pair (epic-90, epic-93) relation is 'sequencial', reason cites missing declaration for epic-93",
                pair_90_93 is not None
                and pair_90_93["relation"] == "sequencial"
                and "missing declaration for epic-93" in pair_90_93["reason"],
                str(pair_90_93),
            )
        else:
            check("fail-safe run computed exactly 1 Track (never a wrong parallel)", False, "graph JSON unavailable")
            check(
                "pair (epic-90, epic-93) relation is 'sequencial', reason cites missing declaration for epic-93",
                False,
                "graph JSON unavailable",
            )

    # --------------------------------------------------------------
    # Bonus — the committed fixture copies themselves were never mutated
    # --------------------------------------------------------------
    print()
    print("-- bonus: committed fixture files in this directory were never mutated by this run --")
    try:
        git_result = subprocess.run(
            ["git", "status", "--porcelain", str(FIXTURES_DIR)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=15,
        )
        # Only flag MODIFIED (M) tracked files as a violation; untracked (??) files
        # (e.g. this new validate_bridge.py itself, on its very first run before
        # `git add`) are expected and not a sign of destructive mutation.
        modified_lines = [
            line for line in git_result.stdout.splitlines() if line.strip().startswith("M ") or " M " in line[:3]
        ]
        check(
            "no tracked fixture file under fixtures/bridge/ shows as Modified in git status",
            git_result.returncode == 0 and not modified_lines,
            git_result.stdout.strip() or "clean",
        )
    except Exception as exc:  # noqa: BLE001
        check("no tracked fixture file under fixtures/bridge/ shows as Modified in git status", False, f"git unavailable: {exc}")

    return summarize()


if __name__ == "__main__":
    sys.exit(main())
