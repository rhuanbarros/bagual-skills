#!/usr/bin/env python3
"""merge_manager.py — Story E11.5 (PRD 03 FR-7): merge-back + serialized process/
knowledge writes + deterministic migration renumbering, one Track at a time. Extended
by Story E11.6 (PRD 03 FR-8): a conservative, all-or-nothing conflict-resolution ladder
tried BEFORE giving up, plus a mechanical, independent textual guardrail for the SM-2=0
requirement (the owner never sees a `<<<<<<<` marker). Extended by Story E16.6 (T3.7):
post-merge integrated-gate BISECTION — until this story, a gate failure after 2+ Tracks
merged blindly blamed only the most-recently-merged one (documented residual, see
`## INVARIANTS (Story E11.5)` in `workflow.md`, "gate-failure root-cause bisection...
remains a documented, un-built residual"). This story closes that residual with
`revert-track`/`restore-track` (below) plus the pure-Python `bisect_revert()` — the
tested algorithm workflow.md's Step 0P.5 now follows: try reverting the LAST merged
Track alone, re-run the gate; if it passes, stop (that Track is blamed, everyone else
stays merged); if it still fails, RESTORE that Track (never leave a healthy Track
reverted while still guessing) and try the NEXT-to-last Track alone, and so on, at
most once per Track in `{merged_tracks}` (never more) — reverting exactly ONE Track's
contribution at a time, never a cumulative "revert everyone tried so far". If NO
individual Track's revert makes the gate pass, every trial is restored (nothing stays
reverted) and the caller (workflow.md) HALTs with an explicit reason — this never
silently reverts every Track as a last-resort guess (PRD 03 FR-8's "the owner never
sees a guessed resolution" discipline, extended here from merge-conflicts to
gate-failures).

Called by the SUPERVISOR (bagual-epic-runner/workflow.md's Step 0P.5), never by a
Track-Agent, never from inside a worktree. Every subcommand assumes {project-root}'s
working tree is currently checked out onto the integration branch (`staging` in real
runs; a throwaway branch in tests) — it never `git checkout`s that branch itself
(callers are responsible for being on the right branch before invoking this).

Design (see ideias/sistema-artifacts/E11-5-merge-automatico.md and
ideias/sistema-artifacts/E11-6-conflito-residual.md for the full stories):
  - Two disjoint classes of shared touchpoint, handled two different ways:
    1. UNION-SAFE files (the append-only knowledge files, projects-history.md,
       Ledger entries) — handled by `.gitattributes` `merge=union` BEFORE this script
       ever runs. `git merge` resolves them natively; this script does not special-case
       them (a leftover conflict on one of them after `git merge` is treated as an
       UNEXPECTED conflict, per the "other conflicted path" branch below).
    2. DELTA-REAPPLY files (sprint-status.yaml, board.yaml) — never merged at the file
       level. `merge-track` always force-resets them to the pre-merge (staging) content
       via a checkout by explicit commit SHA, whether or not git reported a conflict on
       them: this is the "the supervisor does NOT take the worktree's version at merge"
       contract. The caller then runs `reapply-status-delta` to copy over ONLY the
       specific field(s) that the Track's OWN epics/tickets actually changed — a
       scoped, structure-preserving copy, never a blind file merge.
  - Story E11.6 (FR-8): exactly ONE more safe class exists beyond union-safe above —
    IMPORT-REORDER. A path that ends up conflicted OUTSIDE the two classes above (an
    "unexpected" conflict) gets ONE more chance, tried INSIDE `merge-track` itself,
    BEFORE the merge is aborted: if the conflicted file's extension is one of
    `.py`/`.ts`/`.tsx`/`.js`/`.jsx`/`.mjs` AND every non-blank line on BOTH sides of
    EVERY conflict hunk in that file matches an import-statement pattern, the two
    sides' import lines are unioned (deduplicated) and the conflict is resolved.
    **All-or-nothing across the WHOLE merge, never per-file**: if even ONE unexpectedly
    -conflicted path does not qualify, NOTHING is auto-resolved and the merge aborts
    exactly as before this story — never a guessed resolution, never a partial one
    sitting next to an aborted one. Any conflict outside these three total classes
    (union-safe, delta-reapply, import-reorder) means the FR-3 disjunction computation
    (compute_execution_graph.py) missed a real overlap — this script refuses to guess
    any further, aborts the merge, and reports clearly.
  - SM-2=0 is enforced MECHANICALLY, not just by the control flow above: immediately
    before `merge-track` ever runs `git commit`, it runs a raw TEXTUAL scan (`git
    grep`, independent of git's own `--diff-filter=U` index-based conflict detection
    used everywhere else in this file) across every tracked file in the working tree
    for a line starting with a conflict marker. Any hit aborts the merge instead of
    committing — regardless of source (a bug in the ladder above, an unexpected
    union-driver leftover, or anything else). The standalone `assert-clean` subcommand
    exposes the SAME scan for an external, independent second checkpoint (the caller —
    Step 0P.5 — calls it right after every `merge-track` invocation). Never let a
    `<<<<<<<` marker reach a commit on a shared branch (PRD 03 FR-8 — the owner must
    never see one as a task).

Stdlib only. No third-party deps (PyYAML included) — sprint-status.yaml/board.yaml
have hand-authored comments/structure that a round-trip YAML load+dump would mangle,
so status fields are read/written via targeted regex block-splicing, the same
technique compute_execution_graph.py already uses for `execution_graph:`.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Optional


# ──────────────────────────────────────────────────────────────────────────
# git helpers
# ──────────────────────────────────────────────────────────────────────────


def run_git(project_root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(project_root), *args],
        capture_output=True,
        text=True,
        check=check,
    )


def git_current_branch(project_root: Path) -> str:
    return run_git(project_root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()


def git_head_sha(project_root: Path) -> str:
    return run_git(project_root, "rev-parse", "HEAD").stdout.strip()


def git_conflicted_paths(project_root: Path) -> list[str]:
    result = run_git(project_root, "diff", "--name-only", "--diff-filter=U", check=False)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


# ──────────────────────────────────────────────────────────────────────────
# Story E11.6 (PRD 03 FR-8) — the ONE conservative safe class beyond
# union-merge: import-reorder-only conflicts. Deliberately narrow: a hunk
# qualifies only if EVERY non-blank line on BOTH sides is an import
# statement for that file's extension. Anything else (a real code change
# mixed into the same hunk, an extension not in this list, a malformed/
# nested marker structure) means "does not qualify" — never a guess.
# ──────────────────────────────────────────────────────────────────────────

IMPORT_LINE_PATTERNS: dict[str, re.Pattern] = {
    ".py": re.compile(r"^\s*(?:import\s+\S|from\s+\S+\s+import\s+)"),
    ".ts": re.compile(r'^\s*import\s+.*(?:from\s+[\'"]|[\'"])|^\s*import\s*\{'),
    ".tsx": re.compile(r'^\s*import\s+.*(?:from\s+[\'"]|[\'"])|^\s*import\s*\{'),
    ".js": re.compile(r'^\s*import\s+.*(?:from\s+[\'"]|[\'"])|^\s*import\s*\{'),
    ".jsx": re.compile(r'^\s*import\s+.*(?:from\s+[\'"]|[\'"])|^\s*import\s*\{'),
    ".mjs": re.compile(r'^\s*import\s+.*(?:from\s+[\'"]|[\'"])|^\s*import\s*\{'),
}


def _parse_conflict_hunks(text: str) -> Optional[list[dict[str, Any]]]:
    """Split conflict-marked file text into an ordered list of segments —
    `{"type": "text", "content": [lines]}` or `{"type": "conflict", "ours":
    [lines], "theirs": [lines]}` — by scanning for `<<<<<<<`/`=======`/
    `>>>>>>>` markers. Returns None (never a best-effort partial parse) on
    ANY structural irregularity: an unmatched/missing marker, or markers
    nested inside one another. A file that fails to parse cleanly is never
    a candidate for auto-resolution."""
    lines = text.split("\n")
    segments: list[dict[str, Any]] = []
    current_text: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if line.startswith("<<<<<<<"):
            if current_text:
                segments.append({"type": "text", "content": current_text})
                current_text = []
            ours: list[str] = []
            i += 1
            found_mid = False
            while i < n:
                if lines[i] == "=======":
                    found_mid = True
                    i += 1
                    break
                if lines[i].startswith("<<<<<<<") or lines[i].startswith(">>>>>>>"):
                    return None
                ours.append(lines[i])
                i += 1
            if not found_mid:
                return None
            theirs: list[str] = []
            found_end = False
            while i < n:
                if lines[i].startswith(">>>>>>>"):
                    found_end = True
                    i += 1
                    break
                if lines[i].startswith("<<<<<<<") or lines[i] == "=======":
                    return None
                theirs.append(lines[i])
                i += 1
            if not found_end:
                return None
            segments.append({"type": "conflict", "ours": ours, "theirs": theirs})
        else:
            current_text.append(line)
            i += 1
    if current_text:
        segments.append({"type": "text", "content": current_text})
    return segments


def _hunk_is_import_only(hunk: dict[str, Any], pattern: re.Pattern) -> bool:
    for side in (hunk["ours"], hunk["theirs"]):
        for line in side:
            if line.strip() == "":
                continue
            if not pattern.match(line):
                return False
    return True


def _resolve_import_hunk(hunk: dict[str, Any]) -> list[str]:
    """Union of both sides' import lines, deduplicated by exact stripped
    content, ours first (preserves the integration branch's own ordering),
    then any of theirs not already present — never drops a line, never
    reorders within a side."""
    ours: list[str] = hunk["ours"]
    theirs: list[str] = hunk["theirs"]
    seen = {line.strip() for line in ours if line.strip()}
    merged = list(ours)
    for line in theirs:
        stripped = line.strip()
        if not stripped or stripped in seen:
            continue
        merged.append(line)
        seen.add(stripped)
    return merged


def _try_resolve_import_conflict_text(text: str, ext: str) -> Optional[str]:
    """Returns the fully-resolved file text if EVERY conflict hunk in it is
    import-only for `ext`; returns None (never a partial rewrite) the
    moment any hunk does not qualify, or if the file has no conflict
    markers at all, or if the marker structure is malformed."""
    pattern = IMPORT_LINE_PATTERNS.get(ext)
    if pattern is None:
        return None
    segments = _parse_conflict_hunks(text)
    if segments is None:
        return None
    if not any(seg["type"] == "conflict" for seg in segments):
        return None
    out_lines: list[str] = []
    for seg in segments:
        if seg["type"] == "text":
            out_lines.extend(seg["content"])
        else:
            if not _hunk_is_import_only(seg, pattern):
                return None
            out_lines.extend(_resolve_import_hunk(seg))
    return "\n".join(out_lines)


def _attempt_safe_class_ladder(project_root: Path, unexpected_paths: list[str]) -> Optional[dict[str, str]]:
    """Conservative, all-or-nothing (Story E11.6 / FR-8 "outra classe →
    bloqueio, não chute"): try to resolve EVERY path in `unexpected_paths`
    as an import-reorder-only conflict. Returns a `{relative_path:
    resolved_text}` dict ONLY if ALL paths qualify and resolve cleanly;
    returns None the moment even ONE does not — never a partial dict, never
    mutates the filesystem itself (purely a dry computation; the caller
    decides whether and how to apply it)."""
    resolved: dict[str, str] = {}
    for rel_path in unexpected_paths:
        ext = Path(rel_path).suffix
        abs_path = project_root / rel_path
        if ext not in IMPORT_LINE_PATTERNS or not abs_path.exists():
            return None
        try:
            original = abs_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            return None
        new_text = _try_resolve_import_conflict_text(original, ext)
        if new_text is None:
            return None
        resolved[rel_path] = new_text
    return resolved if resolved else None


# ──────────────────────────────────────────────────────────────────────────
# Story E11.6 (PRD 03 FR-8) — SM-2=0 mechanical guardrail: a raw textual
# scan for conflict markers, independent of git's own index-based conflict
# bookkeeping (`git diff --diff-filter=U`) used everywhere else in this
# file. Never trust "git says no conflict" alone for the hard SM-2=0
# requirement — this is the belt to that suspender.
# ──────────────────────────────────────────────────────────────────────────


def _scan_for_conflict_markers(project_root: Path) -> list[str]:
    """Scans every git-tracked file in the current working tree for a line
    starting with a git conflict marker (`<<<<<<<` / `>>>>>>>`). Treated as
    conservatively as possible: any `git grep` exit code OTHER than 0
    (match found) or 1 (no match) is itself treated as "not provably
    clean" — never silently assumed clean on an unexpected error."""
    result = run_git(project_root, "grep", "-n", "--full-name", "-I", "-E", r"^(<<<<<<<|>>>>>>>)", check=False)
    if result.returncode == 1 and not result.stdout.strip():
        return []
    if result.returncode == 0:
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return [f"git grep itself failed unexpectedly (exit {result.returncode}): {result.stderr.strip()}"]


def cmd_assert_clean(args: argparse.Namespace) -> int:
    project_root = args.project_root.resolve()
    markers = _scan_for_conflict_markers(project_root)
    if markers:
        print(json.dumps({"status": "conflict_markers_found", "occurrences": markers}, ensure_ascii=False))
        return 1
    print(json.dumps({"status": "clean"}))
    return 0


# ──────────────────────────────────────────────────────────────────────────
# merge-track — one Track's worktree branch into the currently-checked-out
# integration branch, serialized (caller invokes this once per Track, never
# concurrently — Step 0P.5 processes Track-Agent results one at a time).
# ──────────────────────────────────────────────────────────────────────────

DEFAULT_DELTA_PATHS = [
    "_bmad-output/implementation-artifacts/sprint-status.yaml",
    "ideias/sistema-artifacts/sprint-status.yaml",
    "project_controll/tickets/board.yaml",
]


def cmd_merge_track(args: argparse.Namespace) -> int:
    project_root = args.project_root.resolve()
    base_branch = args.base_branch

    current = git_current_branch(project_root)
    if current != base_branch:
        print(
            json.dumps(
                {
                    "status": "refused",
                    "reason": f"project-root is checked out to '{current}', expected "
                    f"'{base_branch}' — refusing to merge onto the wrong branch",
                }
            )
        )
        return 2

    pre_merge_sha = git_head_sha(project_root)

    merge_result = run_git(
        project_root,
        "merge",
        "--no-ff",
        "--no-commit",
        "--no-log",
        args.track_branch,
        check=False,
    )

    conflicted = git_conflicted_paths(project_root)
    delta_paths = set(args.delta_paths or DEFAULT_DELTA_PATHS)
    unexpected: list[str] = []

    # Force every DELTA-REAPPLY path back to the pre-merge (staging) content,
    # REGARDLESS of whether git flagged it as conflicted — never take the
    # worktree's raw version for these files (contract: reapply-status-delta,
    # called separately by the caller, is the only path a Track's status change
    # reaches these files).
    #
    # IMPORTANT (found + fixed during this story's own testing): `git checkout
    # --ours -- <path>` is a NO-OP for a path git auto-merged WITHOUT a
    # conflict (e.g. only the incoming branch touched it) — `--ours`/`--theirs`
    # only resolve paths that actually have multiple index stages (i.e. are
    # marked conflicted). A clean one-sided change silently keeps the
    # auto-merged ("theirs") content, which is exactly the bug this class of
    # file exists to avoid. The reliable fix is to checkout the path's blob
    # from an explicit commit (`{pre_merge_sha}`) rather than relying on
    # --ours/--theirs staging semantics at all.
    touched_delta_paths: list[str] = []
    for rel_path in delta_paths:
        abs_path = project_root / rel_path
        if not abs_path.exists():
            continue
        # Did the incoming branch touch this path at all? If not, there is
        # nothing to discard/reapply for it in this merge.
        diff_check = run_git(
            project_root, "diff", "--name-only", f"{pre_merge_sha}...{args.track_branch}", "--", rel_path, check=False
        )
        if not diff_check.stdout.strip():
            continue
        run_git(project_root, "checkout", pre_merge_sha, "--", rel_path, check=False)
        run_git(project_root, "add", "--", rel_path, check=False)
        touched_delta_paths.append(rel_path)

    # Re-check conflicts after the forced resolution above.
    still_conflicted = git_conflicted_paths(project_root)
    for path in still_conflicted:
        if path in delta_paths:
            # Should have been resolved by checkout --ours above; if it is
            # STILL conflicted something is structurally odd — treat as
            # unexpected rather than silently retrying.
            unexpected.append(path)
        else:
            unexpected.append(path)

    auto_resolved_paths: list[str] = []
    if unexpected:
        # Story E11.6 (PRD 03 FR-8): one more chance BEFORE giving up — the
        # ONE documented conservative safe class beyond union-merge
        # (already handled upstream by `.gitattributes` before `git merge`
        # even ran). All-or-nothing across every unexpected path: if even
        # ONE does not qualify, this returns None and nothing is touched —
        # falls straight through to the exact same abort this story found
        # here before E11.6.
        ladder_result = _attempt_safe_class_ladder(project_root, unexpected)
        if ladder_result is None:
            run_git(project_root, "merge", "--abort", check=False)
            print(
                json.dumps(
                    {
                        "status": "conflict",
                        "unexpected_conflicts": sorted(set(unexpected)),
                        "safe_class_ladder": "attempted_and_failed",
                        "reason": "conflict outside the known union-safe / delta-reapply / "
                        "import-reorder classes — refusing to guess a resolution (FR-3's "
                        "disjunction computation should have prevented this). Merge "
                        "aborted, nothing committed. PRD 03 FR-8: the owner never sees a "
                        "<<<<<<< marker as a task — this Track is blocked instead (E11.6).",
                    }
                )
            )
            return 3

        for rel_path, new_text in ladder_result.items():
            (project_root / rel_path).write_text(new_text, encoding="utf-8")
            run_git(project_root, "add", "--", rel_path, check=False)
            auto_resolved_paths.append(rel_path)

        # Re-verify against git's OWN conflict bookkeeping: it must now
        # report zero conflicted paths. If it still does, something is
        # structurally odd (e.g. our rewrite didn't fully clear the
        # index's conflict stages for that path) — conservative: abort
        # rather than force a commit over a state we don't fully
        # understand.
        remaining = git_conflicted_paths(project_root)
        if remaining:
            run_git(project_root, "merge", "--abort", check=False)
            print(
                json.dumps(
                    {
                        "status": "conflict",
                        "unexpected_conflicts": sorted(set(remaining)),
                        "safe_class_ladder": "attempted_but_index_still_conflicted",
                        "reason": "safe-class ladder rewrote file content but git still "
                        "reports conflicted path(s) after `git add` — refusing to force "
                        "a commit. Merge aborted, nothing committed.",
                    }
                )
            )
            return 3

    if merge_result.returncode != 0 and not still_conflicted:
        # `git merge` exited non-zero for a reason OTHER than a path conflict
        # (e.g. nothing to commit, nothing to merge) — surface it plainly.
        status = run_git(project_root, "status", "--porcelain", check=False).stdout
        if not status.strip():
            print(json.dumps({"status": "noop", "reason": "nothing to merge (already up to date)"}))
            run_git(project_root, "merge", "--abort", check=False)
            return 0

    # SM-2 guardrail (Story E11.6, PRD 03 FR-8): a raw textual scan,
    # independent of git's own index-based conflict bookkeeping above, run
    # immediately before the commit that would make any of this permanent
    # on a shared branch. If this ever finds a marker — from a bug in the
    # ladder above, a union-merge driver leaving a partial marker, or
    # anything else — refuse to commit. The owner must NEVER see a
    # `<<<<<<<` marker; this is the last mechanical checkpoint before that
    # would become possible.
    pre_commit_markers = _scan_for_conflict_markers(project_root)
    if pre_commit_markers:
        run_git(project_root, "merge", "--abort", check=False)
        print(
            json.dumps(
                {
                    "status": "conflict",
                    "reason": "SM-2 guardrail tripped: conflict marker(s) detected in the "
                    "working tree immediately before commit — refusing to commit. Merge "
                    "aborted, nothing committed.",
                    "marker_occurrences": pre_commit_markers,
                }
            )
        )
        return 3

    commit_msg = args.message or (
        f"merge: Track {args.track_id} ({','.join(args.epics or [])}) into {base_branch} "
        f"(E11.5 serialized merge-back)"
        + (
            f" — auto-resolved import-reorder conflict(s) in {', '.join(auto_resolved_paths)} (E11.6)"
            if auto_resolved_paths
            else ""
        )
    )
    run_git(project_root, "commit", "--no-edit", "-m", commit_msg, check=False)

    new_head = git_head_sha(project_root)
    if new_head == pre_merge_sha:
        print(
            json.dumps(
                {
                    "status": "error",
                    "reason": "merge commit did not advance HEAD — commit likely failed",
                }
            )
        )
        return 4

    print(
        json.dumps(
            {
                "status": "merged",
                "track_id": args.track_id,
                "pre_merge_sha": pre_merge_sha,
                "merge_commit": new_head,
                "delta_reapply_paths": touched_delta_paths,
                "auto_resolved_paths": auto_resolved_paths,
            }
        )
    )
    return 0


# ──────────────────────────────────────────────────────────────────────────
# reapply-status-delta — scoped, structure-preserving copy of specific
# `{field}:` values for specific nested keys, from the Track's OWN
# sprint-status.yaml/board.yaml (as last written inside its worktree, still
# on disk at {track_dest}) onto the integration branch's copy. Never a
# whole-file merge; never touches a key outside `--keys`.
# ──────────────────────────────────────────────────────────────────────────


def _find_nested_block(text: str, key: str) -> Optional[tuple[int, int]]:
    """Find a `  {key}:` block (2-space-indented key, own line) and return
    (start, end) spanning from the key line to just before the next
    2-space-indented `key:` line (or a blank line followed by such, or a
    col-0 top-level key, or EOF) — mirrors compute_execution_graph.py's
    top-level splicer, generalized one indent level in."""
    key_re = re.compile(rf"^  {re.escape(key)}:\s*$", re.MULTILINE)
    match = key_re.search(text)
    if not match:
        return None
    start = match.start()
    rest = text[match.end() :]
    next_key_re = re.compile(r"^(  [A-Za-z0-9_.\-]+:\s*$|[A-Za-z0-9_.\-]+:)", re.MULTILINE)
    next_match = next_key_re.search(rest)
    end = match.end() + (next_match.start() if next_match else len(rest))
    return start, end


def _extract_field(block_text: str, field: str) -> Optional[str]:
    m = re.search(rf"^    {re.escape(field)}:(.*)$", block_text, re.MULTILINE)
    if not m:
        return None
    return m.group(1).strip()


def _set_field_in_block(block_text: str, field: str, value: str) -> str:
    pattern = re.compile(rf"^(    {re.escape(field)}:).*$", re.MULTILINE)
    if pattern.search(block_text):
        return pattern.sub(rf"\g<1> {value}", block_text, count=1)
    # Field absent — insert right after the key line (first line of the block).
    lines = block_text.split("\n")
    lines.insert(1, f"    {field}: {value}")
    return "\n".join(lines)


def cmd_reapply_status_delta(args: argparse.Namespace) -> int:
    target_path: Path = args.target
    source_path: Path = args.source
    fields = args.fields or ["status"]

    target_text = target_path.read_text(encoding="utf-8")
    source_text = source_path.read_text(encoding="utf-8")

    applied: list[dict[str, Any]] = []
    missing_in_source: list[str] = []
    missing_in_target: list[str] = []

    for key in args.keys:
        source_block_span = _find_nested_block(source_text, key)
        if source_block_span is None:
            missing_in_source.append(key)
            continue
        source_block = source_text[source_block_span[0] : source_block_span[1]]

        target_block_span = _find_nested_block(target_text, key)
        if target_block_span is None:
            # Key does not exist yet in the integration branch's copy at all
            # (e.g. a brand-new Ticket entry). Insert the block verbatim right
            # after the file's declared insertion anchor. Documented
            # simplification (see story Dev Notes / self-review): this handles
            # the common "genuinely new entry" case; it does not attempt to
            # preserve the source's original ordering relative to sibling keys.
            missing_in_target.append(key)
            anchor_re = re.compile(rf"^{re.escape(args.anchor)}:\s*$", re.MULTILINE)
            anchor_match = anchor_re.search(target_text)
            if not anchor_match:
                continue
            insert_at = anchor_match.end() + 1
            block_to_insert = source_block if source_block.endswith("\n") else source_block + "\n"
            target_text = target_text[:insert_at] + block_to_insert + target_text[insert_at:]
            applied.append({"key": key, "action": "inserted"})
            continue

        new_target_block = target_text[target_block_span[0] : target_block_span[1]]
        changed_fields: dict[str, str] = {}
        for field in fields:
            value = _extract_field(source_block, field)
            if value is None:
                continue
            new_target_block = _set_field_in_block(new_target_block, field, value)
            changed_fields[field] = value

        if changed_fields:
            target_text = (
                target_text[: target_block_span[0]] + new_target_block + target_text[target_block_span[1] :]
            )
            applied.append({"key": key, "action": "updated", "fields": changed_fields})

    target_path.write_text(target_text, encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "ok",
                "applied": applied,
                "missing_in_source": missing_in_source,
                "missing_in_target_inserted": missing_in_target,
            },
            ensure_ascii=False,
        )
    )
    return 0


# ──────────────────────────────────────────────────────────────────────────
# revert-commit — undo one commit (a merge commit OR a plain follow-up commit
# such as a delta-reapply/migration-renumber commit), via `git revert` (never
# a hard reset — auditable history on a shared branch, safe even if `staging`
# has already been pushed/pulled elsewhere). Auto-detects whether the target
# is a merge commit (2+ parents) and supplies `-m 1` only then — `git revert`
# rejects `-m` on a non-merge commit.
# ──────────────────────────────────────────────────────────────────────────


def _do_revert(project_root: Path, commit: str) -> tuple[Optional[str], Optional[str]]:
    """Core primitive shared by `revert-commit`, `revert-track`, `restore-track`, and
    `bisect_revert()` below: `git revert` ONE commit (auto-detecting merge vs. plain —
    `git revert` rejects `-m` on a non-merge commit), never a hard reset. Returns
    `(revert_commit_sha, None)` on success, or `(None, stderr)` on failure — never
    raises, so every caller can decide how to react (a mid-Track failure aborts that
    Track's own revert-track/restore-track call and reports what succeeded so far,
    rather than crashing)."""
    parents = run_git(project_root, "rev-list", "--parents", "-n", "1", commit).stdout.split()
    is_merge = len(parents) > 2  # [commit, parent1, parent2, ...]
    revert_args = ["revert", "--no-edit"]
    if is_merge:
        revert_args += ["-m", "1"]
    revert_args.append(commit)
    result = run_git(project_root, *revert_args, check=False)
    if result.returncode != 0:
        return None, result.stderr.strip()
    return git_head_sha(project_root), None


def cmd_revert_commit(args: argparse.Namespace) -> int:
    project_root = args.project_root.resolve()
    revert_sha, error = _do_revert(project_root, args.commit)
    if revert_sha is None:
        print(
            json.dumps(
                {
                    "status": "error",
                    "reason": "git revert failed",
                    "stderr": error,
                }
            )
        )
        return 1
    print(json.dumps({"status": "reverted", "revert_commit": revert_sha}))
    return 0


# ──────────────────────────────────────────────────────────────────────────
# revert-track / restore-track — Story E16.6 (T3.7): the per-Track building
# blocks the bisection loop needs. `revert-track` reverts ONE Track's own
# commits (migration-renumber, if any; delta-reapply; merge — in that
# newest-first order, mirroring the exact 3-step sequence Step 0P.5 already
# ran inline before this story) via `_do_revert`, collecting the NEW revert
# commit SHAs it creates as it goes. `restore-track` takes that SAME list of
# revert-commit SHAs (in the order `revert-track` returned them) and undoes
# them in LIFO order — reverting the MOST RECENTLY created revert commit
# first, working backward — which is the correct order to fully restore a
# Track's original contribution: each revert commit was stacked on top of the
# previous one, so undoing them newest-first mirrors how they were built.
# Both are used by `bisect_revert()` below (never re-implemented separately
# there) AND exposed as their own CLI subcommands so workflow.md's Step 0P.5
# can drive the same two operations directly.
# ──────────────────────────────────────────────────────────────────────────


def revert_track_commits(project_root: Path, commits: list[tuple[str, str]]) -> dict[str, Any]:
    """`commits` is `[(label, sha), ...]` in the order they should be reverted
    (newest-first — the caller decides that order; this function does not
    reorder). Reverts each in turn via `_do_revert`; stops at the FIRST
    failure and returns immediately (never partially retries) — the caller
    gets back everything reverted so far (`"reverts"`) so it can call
    `restore_track_commits` on exactly that partial list rather than guessing
    what state the tree is in."""
    reverted: list[dict[str, str]] = []
    for label, commit in commits:
        revert_sha, error = _do_revert(project_root, commit)
        if revert_sha is None:
            return {
                "status": "error",
                "reason": f"git revert failed for {label} ({commit})",
                "stderr": error,
                "reverts": reverted,
            }
        reverted.append({"label": label, "original_commit": commit, "revert_commit": revert_sha})
    return {"status": "reverted", "reverts": reverted}


def restore_track_commits(project_root: Path, revert_shas: list[str]) -> dict[str, Any]:
    """Undo a `revert_track_commits` call by reverting its OWN revert commits,
    in REVERSE (LIFO) order — `revert_shas` must be passed in the SAME order
    `revert_track_commits` returned them (oldest-created first); this
    function reverses that order itself. Stops at the first failure, same
    partial-progress contract as `revert_track_commits`."""
    restored: list[dict[str, str]] = []
    for revert_sha in reversed(revert_shas):
        restore_sha, error = _do_revert(project_root, revert_sha)
        if restore_sha is None:
            return {
                "status": "error",
                "reason": f"git revert failed while restoring {revert_sha}",
                "stderr": error,
                "restores": restored,
            }
        restored.append({"reverted_the_revert": revert_sha, "restore_commit": restore_sha})
    return {"status": "restored", "restores": restored}


def _track_commit_list(track: dict[str, Any]) -> list[tuple[str, str]]:
    """Builds the `[(label, sha), ...]` newest-first list for one Track's
    `{merge_commit, delta_commit, migration_commit}` shape (the same fields
    Step 0P.5 already tracks per-Track) — `migration_commit` is optional
    (many Tracks touch no migration), `delta_commit`/`merge_commit` are not."""
    commits: list[tuple[str, str]] = []
    if track.get("migration_commit"):
        commits.append(("migration_commit", track["migration_commit"]))
    commits.append(("delta_commit", track["delta_commit"]))
    commits.append(("merge_commit", track["merge_commit"]))
    return commits


def cmd_revert_track(args: argparse.Namespace) -> int:
    project_root = args.project_root.resolve()
    commits: list[tuple[str, str]] = []
    if args.migration_commit:
        commits.append(("migration_commit", args.migration_commit))
    commits.append(("delta_commit", args.delta_commit))
    commits.append(("merge_commit", args.merge_commit))
    result = revert_track_commits(project_root, commits)
    result["track_id"] = args.track_id
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "reverted" else 1


def cmd_restore_track(args: argparse.Namespace) -> int:
    project_root = args.project_root.resolve()
    result = restore_track_commits(project_root, args.revert_commits)
    result["track_id"] = args.track_id
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "restored" else 1


# ──────────────────────────────────────────────────────────────────────────
# bisect_revert — Story E16.6 (T3.7): the tested root-cause bisection
# algorithm itself. Pure Python (no CLI subcommand of its own — the
# post-merge gate it needs to re-run after each trial revert is an arbitrary
# check the CALLER owns, e.g. workflow.md's Step 0P.5 spawning a build
# Agent; this function only knows about a `gate_fn: Callable[[], bool]`
# passed in, never about HOW the gate is actually run). workflow.md's Step
# 0P.5 mirrors this EXACT algorithm using `revert-track` (below) plus its own
# Agent-spawning gate — this function is the tested reference implementation
# both share conceptually.
#
# **Adversarial finding, fixed before this function's first version shipped:**
# the first draft discarded a failed trial by calling `restore_track_commits`
# (i.e. reverting the trial's OWN revert commits, chaining a 2nd pair of
# commits on top). That works fine for a Track whose shared-file delta commit
# (`sprint-status.yaml`/`board.yaml`) has no OTHER Track's delta commit
# between it and HEAD — but bisection, by construction, tries candidates
# newest-first and restores each failed one before trying the NEXT (older)
# one. Reproduced with a REAL git repo (3 Tracks, each appending one line to
# the SAME shared file — the exact shape `reapply-status-delta` produces):
# after trying-and-restoring Track 3 (2 revert + 2 reapply commits now sit
# between Track 2's original delta commit and HEAD), attempting to
# `git revert` Track 2's OWN delta commit next hit a genuine
# `CONFLICT (content): Merge conflict in sprint-status.yaml` — git's 3-way
# merge for reverting an OLDER commit gets confused when later, unrelated
# revert/reapply commit PAIRS on the same file sit in between, even though
# every underlying diff is a pure single-line append with no real semantic
# overlap. **Fix:** a failed trial is discarded via `git reset --hard` to the
# SHA captured immediately before that trial started — never a 2nd revert.
# This is NOT the dangerous class of `git reset --hard` the "INVARIANTS
# (Story E11.5)" block warns against (discarding real, already-integrated
# Track work) — it discards only a SCRATCH probe this very function created
# a moment earlier in the same serialized call, to a SHA this function itself
# just recorded; the exact same "reset a worktree back to a known SHA"
# primitive `pool_registry.py::cleanup_worktree()` already uses elsewhere in
# this codebase for disposable state. `revert_track_commits`/
# `restore_track_commits` remain available as general-purpose, real-commit
# primitives (used for the FINAL kept revert once bisection finds the true
# culprit, and exposed as their own `revert-track`/`restore-track` CLI
# subcommands for a human to drive manually) — `bisect_revert()` itself only
# ever uses `revert_track_commits` (never `restore_track_commits`) for its
# internal trial-and-discard loop.
# ──────────────────────────────────────────────────────────────────────────


def bisect_revert(
    project_root: Path,
    tracks: list[dict[str, Any]],
    gate_fn: Callable[[], bool],
) -> dict[str, Any]:
    """`tracks` is `{merged_tracks}` in MERGE ORDER (oldest-merged first —
    the same order Step 0P.5 already builds it in). Tries candidates in
    REVERSE merge order (most-recently-merged first) — the base case
    "culprit is the last Track" resolves on the FIRST trial, zero regression
    vs. the pre-E16.6 single-revert behavior. Each trial reverts EXACTLY ONE
    candidate Track's own commits (never a second one on top — "sem reverter
    sadios além do necessário"), re-runs `gate_fn()`:
      - PASS -> STOP immediately. That candidate is blamed and its revert
        commit(s) STAY (this is the real, kept fix); every OTHER Track
        (including any earlier candidate this loop already tried and
        discarded) stays merged, untouched. Returns `{"status": "found",
        "blamed_track_id": ..., "blamed_track": ..., "tried": [...]}`.
      - FAIL -> DISCARD that trial (`git reset --hard` to the SHA recorded
        immediately before this trial began — see the module-level comment
        above this function for why a 2nd `git revert` is NOT used here)
        before moving to the NEXT candidate — never leaves a healthy Track
        reverted while still guessing, never accumulates reverts across
        trials, and never leaves even a throwaway revert commit in
        `staging`'s history for a Track that turned out healthy.
    Bounded by `len(tracks)` trials, never more (`bisecção limitada ao nº de
    Tracks`). If NO individual trial makes the gate pass, every trial has
    already been discarded by the loop itself — nothing is left reverted —
    and this returns `{"status": "halt", "reason": ..., "tried": [...]}`
    instead of ever falling back to reverting every Track as a guess (`nunca
    revert-tudo silencioso`). A `revert_track_commits` git-level FAILURE, or a
    `git reset --hard` failure while discarding a trial (distinct from a gate
    failure), also halts immediately, surfacing the git error rather than
    continuing to guess against a tree in an unknown state."""
    tried: list[dict[str, Any]] = []
    for track in reversed(tracks):
        track_id = track["track_id"]
        pre_trial_sha = git_head_sha(project_root)
        commits = _track_commit_list(track)
        revert_result = revert_track_commits(project_root, commits)
        if revert_result["status"] != "reverted":
            # A PARTIAL revert may have landed (e.g. delta_commit reverted,
            # merge_commit's own revert then failed) — reset back to the
            # known-clean pre-trial SHA rather than leaving a half-reverted
            # Track sitting on staging.
            run_git(project_root, "reset", "--hard", pre_trial_sha, check=False)
            return {
                "status": "halt",
                "reason": f"git-level failure reverting Track {track_id} during bisection — "
                f"refusing to continue guessing: {revert_result.get('reason')}",
                "tried": tried,
                "git_error": revert_result,
            }

        gate_passed = gate_fn()
        if gate_passed:
            tried.append({"track_id": track_id, "reverted": True, "gate_passed": True})
            return {
                "status": "found",
                "blamed_track_id": track_id,
                "blamed_track": track,
                "tried": tried,
            }

        reset_result = run_git(project_root, "reset", "--hard", pre_trial_sha, check=False)
        if reset_result.returncode != 0:
            return {
                "status": "halt",
                "reason": f"gate still failed after reverting Track {track_id}, AND discarding "
                f"that trial (`git reset --hard`) also failed — the tree is now in an "
                f"inconsistent state, refusing to continue guessing: {reset_result.stderr.strip()}",
                "tried": tried + [{"track_id": track_id, "reverted": True, "gate_passed": False}],
            }
        tried.append({"track_id": track_id, "reverted": False, "gate_passed": False})

    return {
        "status": "halt",
        "reason": f"bisection tried all {len(tracks)} Track(s) individually — none alone made the "
        f"gate pass. Every trial revert was discarded (nothing left reverted); this is NOT "
        f"a signal to revert every Track as a guess. The failure is likely a cross-Track "
        f"interaction, or pre-existing on staging before this batch — needs manual "
        f"inspection.",
        "tried": tried,
    }


# ──────────────────────────────────────────────────────────────────────────
# renumber-migrations — deterministic collision renumbering, post-merge.
# ──────────────────────────────────────────────────────────────────────────

MIGRATION_RE = re.compile(r"^(\d{14})_(.+)\.sql$")


def cmd_renumber_migrations(args: argparse.Namespace) -> int:
    migrations_dir: Path = args.migrations_dir
    files = sorted(p.name for p in migrations_dir.glob("*.sql"))

    by_ts: dict[str, list[str]] = {}
    for name in files:
        m = MIGRATION_RE.match(name)
        if not m:
            continue
        by_ts.setdefault(m.group(1), []).append(name)

    renames: list[dict[str, str]] = []
    used_ts = set(by_ts.keys())

    for ts, names in sorted(by_ts.items()):
        if len(names) <= 1:
            continue
        # Deterministic: keep the alphabetically-first file at its original
        # timestamp; bump every subsequent one by +1 second repeatedly until a
        # free slot is found (alphabetical tie-break — matches how directory
        # listings / `sorted()` are already used elsewhere in this project's
        # scripts, e.g. compute_execution_graph.py's epic_set order).
        for name in names[1:]:
            new_ts = int(ts)
            while str(new_ts).zfill(14) in used_ts:
                new_ts += 1
            new_ts_str = str(new_ts).zfill(14)
            used_ts.add(new_ts_str)
            m = MIGRATION_RE.match(name)
            assert m is not None
            new_name = f"{new_ts_str}_{m.group(2)}.sql"
            (migrations_dir / name).rename(migrations_dir / new_name)
            renames.append({"from": name, "to": new_name})

    print(json.dumps({"status": "ok", "renamed": renames}, ensure_ascii=False))
    return 0


# ──────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p_merge = sub.add_parser("merge-track", help="Merge one Track branch into the currently-checked-out integration branch")
    p_merge.add_argument("--project-root", type=Path, required=True)
    p_merge.add_argument("--base-branch", default="staging")
    p_merge.add_argument("--track-branch", required=True)
    p_merge.add_argument("--track-id", required=True)
    p_merge.add_argument("--epics", nargs="*", default=[])
    p_merge.add_argument("--delta-paths", nargs="*", default=None)
    p_merge.add_argument("--message", default=None)
    p_merge.set_defaults(func=cmd_merge_track)

    p_delta = sub.add_parser("reapply-status-delta", help="Copy specific field(s) for specific keys from a Track's own status file onto the integration branch's copy")
    p_delta.add_argument("--target", type=Path, required=True)
    p_delta.add_argument("--source", type=Path, required=True)
    p_delta.add_argument("--keys", nargs="+", required=True)
    p_delta.add_argument("--fields", nargs="*", default=["status"])
    p_delta.add_argument("--anchor", default="development_status", help="Top-level key to insert brand-new blocks after, if a key exists in --source but not yet in --target")
    p_delta.set_defaults(func=cmd_reapply_status_delta)

    p_revert = sub.add_parser("revert-commit", aliases=["revert-merge"], help="git revert the given commit (auto-detects merge vs plain commit), non-destructively")
    p_revert.add_argument("--project-root", type=Path, required=True)
    p_revert.add_argument("--commit", required=True)
    p_revert.set_defaults(func=cmd_revert_commit)

    p_revert_track = sub.add_parser("revert-track", help="Story E16.6: revert ONE Track's own commits (migration if any, delta, merge — newest-first), used by the post-merge gate bisection")
    p_revert_track.add_argument("--project-root", type=Path, required=True)
    p_revert_track.add_argument("--track-id", required=True)
    p_revert_track.add_argument("--merge-commit", required=True)
    p_revert_track.add_argument("--delta-commit", required=True)
    p_revert_track.add_argument("--migration-commit", default=None)
    p_revert_track.set_defaults(func=cmd_revert_track)

    p_restore_track = sub.add_parser("restore-track", help="Story E16.6: undo a revert-track call by reverting its own revert commits, LIFO order")
    p_restore_track.add_argument("--project-root", type=Path, required=True)
    p_restore_track.add_argument("--track-id", required=True)
    p_restore_track.add_argument("--revert-commits", nargs="+", required=True, help="The revert_commit SHAs revert-track returned, in the SAME order it returned them")
    p_restore_track.set_defaults(func=cmd_restore_track)

    p_renumber = sub.add_parser("renumber-migrations", help="Deterministically renumber colliding migration timestamp prefixes in a directory")
    p_renumber.add_argument("--migrations-dir", type=Path, required=True)
    p_renumber.set_defaults(func=cmd_renumber_migrations)

    p_assert = sub.add_parser("assert-clean", help="Story E11.6 (SM-2=0 guardrail): fail if any git-tracked file in the working tree contains a conflict marker")
    p_assert.add_argument("--project-root", type=Path, required=True)
    p_assert.set_defaults(func=cmd_assert_clean)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
