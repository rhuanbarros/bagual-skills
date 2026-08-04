#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pytest"]
# ///
"""Tests for inventory_sweep.py (bagual-spec-gate, workflow.md Step 2).

Covers: cross-file-kind detection, the fixed exclude set (.git/node_modules/dist/.venv),
--json output shape, and — the one that matters most — that the script has NO --include /
path-filter flag. That absence is a deliberate mechanical lock (see the script's module
docstring): a scoped grep is exactly what let two live columns slip through review in Story
22.1. This test protects the lock from a well-meaning "just add --include for convenience"
regression.

Run with: uv run --with pytest pytest scripts/tests/test_inventory_sweep.py
"""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = SCRIPTS_DIR / "inventory_sweep.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("inventory_sweep_under_test", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


inventory_sweep = _load_module()


def _make_repo(tmp_path: Path) -> Path:
    """Builds a small synthetic repo with occurrences of `legacy_col` across every file kind
    the classifier recognizes, plus decoys inside every excluded directory."""
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)

    (repo / "supabase" / "migrations").mkdir(parents=True)
    (repo / "supabase" / "migrations" / "20260101000000_old_table.sql").write_text(
        "create table t (legacy_col text);\n", encoding="utf-8"
    )

    (repo / "backend" / "scripts").mkdir(parents=True)
    (repo / "backend" / "scripts" / "seed_finance_fixtures_dev.py").write_text(
        "row = {'legacy_col': 'x'}\n", encoding="utf-8"
    )

    (repo / "frontend" / "tests" / "e2e").mkdir(parents=True)
    (repo / "frontend" / "tests" / "e2e" / "property-media.spec.ts").write_text(
        "expect(row.legacy_col).toBe('x');\n", encoding="utf-8"
    )

    (repo / "docs").mkdir(parents=True)
    (repo / "docs" / "notes.md").write_text("`legacy_col` is mentioned here.\n", encoding="utf-8")

    (repo / "frontend" / "src").mkdir(parents=True)
    (repo / "frontend" / "src" / "component.tsx").write_text(
        "const x = row.legacy_col;\n", encoding="utf-8"
    )

    # Decoys inside every excluded dir — must NEVER show up in results.
    for excluded in (".git", "node_modules", "dist", ".venv"):
        d = repo / excluded / "sub"
        d.mkdir(parents=True, exist_ok=True)
        (d / "decoy.txt").write_text("legacy_col\n", encoding="utf-8")

    # Substring decoy — must NOT match (whole-word only).
    (repo / "docs" / "unrelated.md").write_text("old_legacy_col_backup should not match\n", encoding="utf-8")

    return repo


def test_finds_occurrences_across_all_file_kinds(tmp_path):
    repo = _make_repo(tmp_path)
    occurrences = inventory_sweep.sweep("legacy_col", repo)
    kinds = {occ["kind"] for occ in occurrences}
    assert kinds == {"migration", "seed", "test", "doc", "code"}
    assert len(occurrences) == 5  # one real hit per file kind, decoys excluded


def test_excludes_git_node_modules_dist_venv(tmp_path):
    repo = _make_repo(tmp_path)
    occurrences = inventory_sweep.sweep("legacy_col", repo)
    for occ in occurrences:
        top = occ["path"].split("/")[0]
        assert top not in {".git", "node_modules", "dist", ".venv"}


def test_whole_word_match_does_not_false_positive_on_substring(tmp_path):
    repo = _make_repo(tmp_path)
    occurrences = inventory_sweep.sweep("legacy_col", repo)
    assert not any("unrelated.md" in occ["path"] for occ in occurrences)


def test_zero_occurrences_is_a_clean_empty_result(tmp_path):
    repo = _make_repo(tmp_path)
    occurrences = inventory_sweep.sweep("nonexistent_entity_xyz", repo)
    assert occurrences == []


def test_json_output_shape(tmp_path, capsys):
    repo = _make_repo(tmp_path)
    exit_code = inventory_sweep.main(["legacy_col", "--repo-root", str(repo), "--json"])
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["entity"] == "legacy_col"
    assert payload["occurrence_count"] == 5
    assert set(payload["excluded_dirs"]) == {".git", "node_modules", "dist", ".venv"}
    assert all({"path", "line", "kind", "snippet"} <= occ.keys() for occ in payload["occurrences"])


def test_empty_entity_name_is_a_usage_error(tmp_path):
    repo = _make_repo(tmp_path)
    exit_code = inventory_sweep.main(["  ", "--repo-root", str(repo)])
    assert exit_code == 2


def test_missing_repo_root_is_a_usage_error(tmp_path):
    missing = tmp_path / "does-not-exist"
    exit_code = inventory_sweep.main(["legacy_col", "--repo-root", str(missing)])
    assert exit_code == 2


def test_no_include_or_path_filter_flag_exists():
    """MECHANICAL LOCK regression guard: the parser must NOT accept --include or any
    path-filter flag. A scoped sweep is exactly the failure mode this script exists to
    prevent (see module docstring) — this test fails loudly if that flag is ever added back."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "legacy_col", "--include", "*.py"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "unrecognized arguments" in result.stderr


def test_help_output_options_list_has_no_include_flag():
    """The docstring is allowed to explain the lock (mentions "--include" in prose); the
    actual `options:`/`positional arguments:` listing generated by argparse must not."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH), "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "MECHANICAL LOCK" in result.stdout
    options_section = result.stdout.split("options:", 1)[-1]
    assert "--include" not in options_section


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))


def test_sweeping_a_subdirectory_of_a_repo_is_flagged_as_narrowed(tmp_path):
    """`--repo-root` is the one way a caller could re-open the hole this script closes:
    the original investigation missed `expense_type` by scoping its grep to `frontend/src`.
    Sweeping below a real repo root must never pass silently."""
    repo = _make_repo(tmp_path)
    subdir = repo / "frontend"
    result = inventory_sweep.build_result("legacy_col", subdir, [])
    assert result["scope_warning"] is not None
    assert "NARROWED SCOPE" in result["scope_warning"]
    assert "PARTIAL" in result["scope_warning"]
    # and it must be visible in the human report, not just the JSON
    assert "NARROWED SCOPE" in inventory_sweep.format_human(result)


def test_sweeping_the_repo_root_itself_is_not_flagged(tmp_path):
    repo = _make_repo(tmp_path)
    result = inventory_sweep.build_result("legacy_col", repo, [])
    assert result["scope_warning"] is None
    assert "NARROWED SCOPE" not in inventory_sweep.format_human(result)
