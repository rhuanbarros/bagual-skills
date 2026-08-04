#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""inventory_sweep.py — repo-wide, unscoped grep for an old entity name (table/column/symbol).

Part of the bagual-spec-gate skill (workflow.md Step 2, "Inventory (a)"). Exists because a grep
that WAS scoped to one directory/extension is exactly what let two live columns
(`expense_type`, `investor_name`) slip past review in Story 22.1 — they lived in a test file and
a seed script, both outside the `frontend/src --include="*.tsx"` scope the original investigation
used, and the migration that replaced their table dropped both silently. See
`wiki/nota-operacional/bmad-loop-spec-vira-contrato-executavel-coluna-esquecida-vira-coluna-
dropada.md` for the full incident this script exists to stop from repeating.

MECHANICAL LOCK (do not "fix" this by adding it back): this script deliberately has NO
`--include` / path-filter flag. The absence of that parameter is the safety feature itself —
every sweep covers the whole repository, every time, with no scope a caller could narrow by
accident or convenience.

Read-only. Never writes, moves, or edits anything in the repo — it only greps and reports.

Usage:
    python3 inventory_sweep.py expense_type
    python3 inventory_sweep.py property_expenses --json
    python3 inventory_sweep.py investor_name --repo-root /path/to/repo --json -o report.json

Exit codes:
    0 = swept successfully (regardless of whether any occurrence was found — zero hits is a
        real, reportable outcome, not an error).
    2 = usage error (empty entity name, or no repo root could be resolved).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

DEFAULT_EXCLUDED_DIRS = frozenset({".git", "node_modules", "dist", ".venv"})

# Priority order matters: e.g. a migration living under a fixtures/tests folder is still
# reported as "migration" first (the schema-change risk is the dominant fact); a seed script
# named like a test is still "seed" first (it writes real rows — that's what matters here).
_MIGRATION_MARKER = "supabase/migrations/"
_SEED_MARKER = "seed"
_TEST_DIR_NAMES = {"test", "tests", "spec", "specs", "__tests__"}
_TEST_NAME_MARKERS = ("test_", "_test", ".test", "test.", "spec_", "_spec", ".spec", "spec.")
_DOC_SUFFIXES = {".md", ".mdx", ".rst", ".txt"}

# Extensions never worth scanning as text (binary/lockfile noise).
_SKIP_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".pdf",
    ".woff", ".woff2", ".ttf", ".eot", ".zip", ".lock",
}


def classify_file_kind(rel_path: Path) -> str:
    """Labels a file as migration / seed / test / doc / code, in that priority order."""
    posix = rel_path.as_posix().lower()
    path_parts = {p.lower() for p in rel_path.parts}
    name = rel_path.name.lower()
    stem = rel_path.stem.lower()

    if _MIGRATION_MARKER in posix:
        return "migration"
    if _SEED_MARKER in name:
        return "seed"
    if path_parts & _TEST_DIR_NAMES:
        return "test"
    if any(marker in f"{stem}." or marker in name for marker in _TEST_NAME_MARKERS):
        return "test"
    if rel_path.suffix.lower() in _DOC_SUFFIXES:
        return "doc"
    return "code"


def discover_repo_root(start: Path) -> Path | None:
    current = start.resolve()
    for candidate in (current, *current.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def iter_repo_files(repo_root: Path, excluded_dirs: frozenset[str]):
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in excluded_dirs for part in path.parts):
            continue
        if path.suffix.lower() in _SKIP_SUFFIXES:
            continue
        yield path


def sweep(entity: str, repo_root: Path, excluded_dirs: frozenset[str] = DEFAULT_EXCLUDED_DIRS) -> list[dict[str, Any]]:
    """Whole-word search for `entity` across every text file in `repo_root`.

    Whole-word (`\\b...\\b`) so a search for `expense_type` does not false-positive inside a
    longer identifier like `old_expense_type_backup` — but does match every real reference:
    `.expense_type`, `expense_type,`, `"expense_type"`, etc.
    """
    pattern = re.compile(r"\b" + re.escape(entity) + r"\b")
    occurrences: list[dict[str, Any]] = []
    for path in sorted(iter_repo_files(repo_root, excluded_dirs)):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        rel_path = path.relative_to(repo_root)
        kind = classify_file_kind(rel_path)
        for lineno, line in enumerate(text.splitlines(), start=1):
            if pattern.search(line):
                occurrences.append(
                    {
                        "path": rel_path.as_posix(),
                        "line": lineno,
                        "kind": kind,
                        "snippet": line.strip()[:300],
                    }
                )
    return occurrences


def detect_narrowed_scope(repo_root: Path) -> str | None:
    """Return a warning when `repo_root` sits BELOW a real repository root.

    `--repo-root` exists so the tests can sweep a temp tree, but it is also the one
    way a caller could re-open the exact hole this script was written to close: the
    original investigation missed `expense_type` by scoping its grep to
    `frontend/src`. A sweep rooted inside a repository instead of at its top is
    therefore never silently accepted — it is stamped on the result and rendered in
    both output modes, so the gate reading it cannot mistake a partial sweep for a
    complete one.
    """
    for ancestor in repo_root.parents:
        if (ancestor / ".git").exists():
            return (
                f"NARROWED SCOPE: swept {repo_root}, which is inside the repository at "
                f"{ancestor}. This sweep is PARTIAL and cannot prove an entity is retired. "
                f"Re-run without --repo-root before trusting a zero-result or a complete "
                f"consumer inventory."
            )
    return None


def build_result(entity: str, repo_root: Path, occurrences: list[dict[str, Any]]) -> dict[str, Any]:
    by_kind: dict[str, int] = {}
    for occ in occurrences:
        by_kind[occ["kind"]] = by_kind.get(occ["kind"], 0) + 1
    return {
        "entity": entity,
        "repo_root": str(repo_root),
        "excluded_dirs": sorted(DEFAULT_EXCLUDED_DIRS),
        "scope_warning": detect_narrowed_scope(repo_root),
        "occurrence_count": len(occurrences),
        "occurrences_by_kind": by_kind,
        "occurrences": occurrences,
    }


def format_human(result: dict[str, Any]) -> str:
    lines = [
        f"Entity: {result['entity']!r}",
        f"Repo root: {result['repo_root']}",
        f"Excluded dirs: {', '.join(result['excluded_dirs'])}",
        f"Occurrences: {result['occurrence_count']}",
    ]
    if result.get("scope_warning"):
        lines.insert(0, f"⚠️  {result['scope_warning']}")
        lines.insert(1, "")
    if not result["occurrences"]:
        lines.append(
            "  (none found — entity may already be fully retired, or the name doesn't match any "
            "current identifier; a zero-result sweep is still a real finding, not an error)"
        )
        return "\n".join(lines)

    by_kind = result["occurrences_by_kind"]
    lines.append("  By kind: " + ", ".join(f"{k}={v}" for k, v in sorted(by_kind.items())))
    lines.append("")
    for occ in result["occurrences"]:
        lines.append(f"  [{occ['kind']:9s}] {occ['path']}:{occ['line']}  {occ['snippet']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("entity", help="Old table/column/symbol name to sweep the whole repo for")
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root to sweep (default: nearest ancestor directory containing .git)",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a human-readable report")
    parser.add_argument("-o", "--output", type=Path, default=None, help="Write output to this file instead of stdout")
    args = parser.parse_args(argv)

    if not args.entity.strip():
        print("error: entity name must not be empty", file=sys.stderr)
        return 2

    repo_root = args.repo_root.resolve() if args.repo_root else discover_repo_root(Path.cwd())
    if repo_root is None or not repo_root.is_dir():
        print("error: could not resolve a repository root (pass --repo-root explicitly)", file=sys.stderr)
        return 2

    occurrences = sweep(args.entity, repo_root)
    result = build_result(args.entity, repo_root, occurrences)
    out_text = json.dumps(result, indent=2, ensure_ascii=False) if args.json else format_human(result)

    if args.output:
        args.output.write_text(out_text + "\n", encoding="utf-8")
    else:
        print(out_text)

    return 0


if __name__ == "__main__":
    sys.exit(main())
