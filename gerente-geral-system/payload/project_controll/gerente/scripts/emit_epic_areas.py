#!/usr/bin/env python3
"""emit_epic_areas.py — bridge-declaracao-areas: the E9.3 → E10.3/E10.4 bridge.

PROBLEM THIS CLOSES: the Gerente's planning brain (Story E9.3,
`project_controll/gerente/planning-brain.md` §3 Passo 2) already declares each
epic's área/arquivos/depende-de — but in PROSE, written to a
`project_controll/gerente/planning/<slug>-plano.md` file. `compute_execution_graph.py`
(Story E10.3/E10.4, `.claude/skills/bagual-epic-runner/scripts/`) computes the REAL
paralela/sequencial Execution Graph, but only from a MECHANICAL `epic_areas:` block
embedded in `sprint-status.yaml` (`epic_key: {single-line-JSON}` per line — see that
script's own module docstring). Nothing translated prose → that mechanical block, so
every real epic run fell back to `mode: "trivial-placeholder"`-equivalent fail-safe
(missing declaration ⇒ every pair `sequencial`) — E10/E11's parallelism machinery was
built but structurally inert. This script is that translation.

TWO HALVES, NO NLP (deliberate — the established "judgment in prose, gate in script"
Ledger regra, and PRD 03's own "conflito zero por construção" thesis both require the
VALUES to be a human/Opus judgment call, never guessed by parsing prose):
  1. The Gerente (Opus, in-thread, already writing the plano.md in prose per
     planning-brain.md §3 Passo 2) ALSO emits a structured, single-line JSON sentinel
     per epic — see "SENTINEL FORMAT" below. This is not a second, independent
     artifact to keep in sync: it is the SAME declaration the Gerente is already
     making in prose, restated once in a form a script can extract mechanically.
  2. This script (stdlib-only, zero NLP, zero prose parsing) extracts every sentinel
     from a plano.md and writes/updates the `epic_areas:` block of a target
     sprint-status.yaml, in EXACTLY the format `compute_execution_graph.py` already
     parses (`_EPIC_AREAS_BLOCK_RE` / `_EPIC_AREAS_LINE_RE` there) — never inventing a
     new format compute_execution_graph.py would need to learn.

════════════════════════════════════════════════════════════════════════════════
SENTINEL FORMAT (what this script extracts from a plano.md)
════════════════════════════════════════════════════════════════════════════════
A single line, anywhere in the plano.md (by convention: immediately under the
`## Epic N — <título>` heading of the epic it describes, but this script does not
depend on position — it scans the whole file):

    <!-- epic-decl: {"epic_key": "epic-E12", "epic_type": "feature",
                     "areas": ["frontend/src/features/x/"],
                     "touches_shared": ["supabase/migrations"],
                     "depends_on": ["epic-E11"]} -->

An HTML comment (renders invisibly in a normal Markdown read of the plano — the human
still reads the prose declaration right above it) wrapping ONE JSON object on ONE
line — the same "JSON is a valid YAML/Markdown-embeddable flow value, parse with a
per-line regex + `json.loads`, never a general parser" trick
`compute_execution_graph.py` already uses for its OWN `epic_areas:` block. This is a
deliberate mirror, not a coincidence: the two scripts speak the same wire format at
both ends of the bridge.

**`epic_key` is REQUIRED inside the JSON object and is NOT optional convenience** — it
is the target `sprint-status.yaml` key the runner will actually iterate (e.g.
`epic-42`, `epic-E12`). The plano's own `## Epic N` heading number is a document
section number, NOT necessarily the sprint-status key (a plan may propose "Epic 3" for
what ends up dispatched as `epic-57` once Tickets are materialized against a live
board) — so this script never tries to infer the key from the heading; the Gerente
states it explicitly, because only the Gerente (which already knows the target board)
can know it correctly. `epic_key` is the only field NOT copied verbatim into the
`epic_areas:` value (see EXTRACTION below) — it becomes the YAML *key*, mirroring
exactly how `compute_execution_graph.py` keys its own `epic_areas:` entries.

The remaining fields (`epic_type`, `areas`, `touches_shared`, `depends_on`) are
EXACTLY `compute_execution_graph.py`'s own declaration schema (see that script's
module docstring, "DECLARATION FORMAT") — this script does not add, rename, or
reinterpret any of them. Their VALUES are the Gerente's judgment (Opus): this script
never infers `areas`/`touches_shared`/`depends_on` from the prose plan text — it only
mechanically carries whatever the Gerente already wrote into the sentinel.

════════════════════════════════════════════════════════════════════════════════
FAIL-SAFE POSTURE (mirrors compute_execution_graph.py's own constitution)
════════════════════════════════════════════════════════════════════════════════
A sentinel that is malformed (invalid JSON, missing/empty `epic_key`, invalid
`epic_type`, `areas`/`touches_shared`/`depends_on` not a JSON array of strings) is
SKIPPED — never guessed, never partially written, never coerced into "closest valid
shape". A warning is printed to stderr and the affected epic simply gets NO entry in
`epic_areas:` — which is not an error state for `compute_execution_graph.py`: absent
declaration is its own documented fail-safe (every pair involving that epic ⇒
`sequencial`). A wrong "paralela" is the catastrophic failure this whole system is
built to avoid (PRD 03); skipping a bad sentinel costs only schedule time, never
correctness — same trade-off `compute_execution_graph.py` itself makes.

════════════════════════════════════════════════════════════════════════════════
WRITE SEMANTICS
════════════════════════════════════════════════════════════════════════════════
`from-plan` performs an ATOMIC (temp-file + os.replace), PRESERVE-THE-REST write into
the target sprint-status.yaml's `epic_areas:` block — mirrors
`compute_execution_graph.py::splice_execution_graph_into_sprint_status`'s own
insert-or-replace-the-named-block pattern (insert before the `development_status:`
anchor if the block does not exist yet; otherwise splice only the block's own text
range). Every OTHER top-level key (`generated`, `last_updated`, `development_status`,
comments, story entries, an `execution_graph:` block if already present) is left
byte-for-byte untouched. Existing `epic_areas:` entries for epics NOT mentioned by this
plano.md's sentinels are left untouched too (never deleted) — this script only ever
ADDS or UPDATES entries for epic_keys it found a valid sentinel for in THIS plan.

Idempotent: re-running `from-plan` against the same plano.md + already-updated
sprint-status.yaml is a no-op (the computed new text compares byte-equal to the
existing text, so no write happens and no duplicate entries are ever produced).

Full story spec, design rationale, and fixture-based end-to-end proof (a synthetic
plano.md whose bridged declarations make the REAL compute_execution_graph.py compute
2 parallel Tracks): `ideias/sistema-artifacts/bridge-declaracao-areas.md`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

# ──────────────────────────────────────────────────────────────────────────
# Sentinel extraction (producer-side format, this script's own)
# ──────────────────────────────────────────────────────────────────────────

_EPIC_DECL_RE = re.compile(r"^<!--\s*epic-decl:\s*(\{.*\})\s*-->\s*$")

VALID_EPIC_TYPES = frozenset({"feature", "refactor", "other"})
_ARRAY_OF_STRINGS_FIELDS = ("areas", "touches_shared", "depends_on")
# Must mirror compute_execution_graph.py's own `_EPIC_AREAS_LINE_RE` key group
# exactly — an epic_key outside this charset would be written as a YAML line
# compute_execution_graph.py's parser can never match, silently going inert.
_EPIC_KEY_CHARSET_RE = re.compile(r"^[A-Za-z0-9_.\-]+$")


def _validate_declaration(obj: Any) -> tuple[bool, str]:
    """Structural validation only — never a judgment call on the VALUES (that is the
    Gerente's job). Returns (is_valid, reason_if_not)."""
    if not isinstance(obj, dict):
        return False, "sentinel JSON is not an object"

    epic_key = obj.get("epic_key")
    if not isinstance(epic_key, str) or not epic_key.strip():
        return False, "missing or empty 'epic_key'"
    if not _EPIC_KEY_CHARSET_RE.match(epic_key):
        return (
            False,
            f"'epic_key' {epic_key!r} contains characters outside "
            "compute_execution_graph.py's own key charset [A-Za-z0-9_.-] — it would "
            "be written but never re-parsed, silently going inert",
        )

    epic_type = obj.get("epic_type", "other")
    if epic_type not in VALID_EPIC_TYPES:
        return False, f"invalid epic_type '{epic_type}' (must be one of {sorted(VALID_EPIC_TYPES)})"

    if "areas" not in obj:
        return False, "missing 'areas' (required — may be an empty list, but the key must be present)"

    for field in _ARRAY_OF_STRINGS_FIELDS:
        if field not in obj:
            continue
        val = obj[field]
        if not isinstance(val, list) or not all(isinstance(x, str) for x in val):
            return False, f"'{field}' must be a JSON array of strings"

    return True, ""


def extract_declarations_from_plan(plan_text: str) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Scan every line of a plano.md for `<!-- epic-decl: {...} -->` sentinels.

    Returns (declarations, warnings). `declarations` is keyed by `epic_key` with
    `epic_key` itself STRIPPED from the value (it becomes the YAML map key, not a
    field inside the value — mirrors compute_execution_graph.py's own schema, which
    has no `epic_key` field inside the value). `warnings` is a list of human-readable
    strings for every sentinel that was skipped (malformed JSON, failed structural
    validation, or a duplicate epic_key within the same plan — last occurrence wins,
    each duplicate is still reported).
    """
    declarations: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []

    for lineno, raw_line in enumerate(plan_text.splitlines(), start=1):
        match = _EPIC_DECL_RE.match(raw_line.strip())
        if not match:
            continue

        blob = match.group(1)
        try:
            obj = json.loads(blob)
        except json.JSONDecodeError as exc:
            warnings.append(f"line {lineno}: invalid JSON in epic-decl sentinel ({exc}) — skipped (fail-safe)")
            continue

        ok, reason = _validate_declaration(obj)
        if not ok:
            hint = obj.get("epic_key", "?") if isinstance(obj, dict) else "?"
            warnings.append(f"line {lineno} (epic_key={hint!r}): {reason} — skipped (fail-safe)")
            continue

        epic_key = obj["epic_key"]
        if epic_key in declarations:
            warnings.append(
                f"line {lineno}: duplicate epic-decl sentinel for '{epic_key}' in this plan "
                "— later occurrence overwrites the earlier one"
            )
        declarations[epic_key] = {k: v for k, v in obj.items() if k != "epic_key"}

    return declarations, warnings


# ──────────────────────────────────────────────────────────────────────────
# sprint-status.yaml `epic_areas:` block — read/merge/write
#
# The two regexes below MUST mirror compute_execution_graph.py's own
# `_EPIC_AREAS_BLOCK_RE` / `_EPIC_AREAS_LINE_RE` byte-for-byte — this script writes
# what that script reads. Kept as an independent literal copy (not a cross-module
# import) so this bridge has no runtime dependency on the bagual-epic-runner skill
# directory's layout; the fixture end-to-end test
# (project_controll/test-fixtures/bridge/validate_bridge.py) round-trips through
# the REAL compute_execution_graph.py to catch any drift empirically, rather than
# trusting this comment alone.
# ──────────────────────────────────────────────────────────────────────────

_EPIC_AREAS_BLOCK_RE = re.compile(r"^epic_areas:\s*$", re.MULTILINE)
_EPIC_AREAS_LINE_RE = re.compile(r"^\s+([A-Za-z0-9_.\-]+):\s*(\{.*\})\s*$")
_TOP_LEVEL_KEY_RE = re.compile(r"^[A-Za-z0-9_.\-]+:", re.MULTILINE)
_DEVELOPMENT_STATUS_ANCHOR_RE = re.compile(r"^development_status:\s*$", re.MULTILINE)


def _render_entry_line(epic_key: str, decl: dict[str, Any]) -> str:
    return f"  {epic_key}: {json.dumps(decl, ensure_ascii=False)}"


def _locate_epic_areas_block(text: str) -> tuple[list[str], int | None, int | None]:
    """Return (body_lines, block_start, block_end).

    `block_start` is the text offset of the `epic_areas:` header line itself;
    `block_end` is the offset where the block's body ends (start of the next
    top-level key, or EOF). Both are None if no `epic_areas:` block exists yet.
    `body_lines` are the raw lines strictly AFTER the header line, unmodified.
    """
    header_match = _EPIC_AREAS_BLOCK_RE.search(text)
    if not header_match:
        return [], None, None

    rest = text[header_match.end() :]
    next_key_match = _TOP_LEVEL_KEY_RE.search(rest)
    body_end_rel = next_key_match.start() if next_key_match else len(rest)
    body = rest[:body_end_rel]
    # `rest` always starts with the "\n" that terminates the "epic_areas:" header
    # line itself (the regex `$` matches before that "\n", never consuming it) —
    # that leading "\n" is a header/body separator artifact, NOT a blank content
    # line, so it is stripped before splitting (otherwise every round-trip would
    # grow one spurious blank line, breaking idempotency). Symmetrically, `body`
    # always ends at a "\n" boundary (either EOF or right before the next
    # top-level key), so splitting on "\n" produces exactly one trailing ""
    # artifact that is dropped the same way — any REMAINING blank line in
    # between (e.g. the deliberate blank separator this script's own renderer
    # inserts before the next key) is real content and is preserved.
    if body.startswith("\n"):
        body = body[1:]
    body_lines = body.split("\n") if body else []
    if body_lines and body_lines[-1] == "":
        body_lines = body_lines[:-1]
    return body_lines, header_match.start(), header_match.end() + body_end_rel


def _merge_epic_areas_lines(
    existing_lines: list[str], new_declarations: dict[str, dict[str, Any]]
) -> list[str]:
    """Update entries for epic_keys present in `new_declarations`, preserve every
    other existing line byte-for-byte (including malformed/foreign lines — never
    clobber content this script does not understand), and append brand-new
    epic_keys (not previously present) at the end, in `new_declarations`'s
    insertion order (== the order their sentinels appeared in the plano.md)."""
    existing_keys: set[str] = set()
    output: list[str] = []

    for line in existing_lines:
        if line.strip() == "":
            output.append(line)
            continue
        line_match = _EPIC_AREAS_LINE_RE.match(line)
        if not line_match:
            output.append(line)  # unrecognized line inside the block — preserve verbatim
            continue
        epic_key = line_match.group(1)
        existing_keys.add(epic_key)
        if epic_key in new_declarations:
            output.append(_render_entry_line(epic_key, new_declarations[epic_key]))
        else:
            output.append(line)  # untouched entry for an epic this plan didn't declare

    for epic_key, decl in new_declarations.items():
        if epic_key not in existing_keys:
            output.append(_render_entry_line(epic_key, decl))

    return output


def splice_epic_areas_into_sprint_status(text: str, new_declarations: dict[str, dict[str, Any]]) -> str:
    """Return the FULL new sprint-status.yaml text with `epic_areas:` inserted or
    updated. Never touches any byte outside the `epic_areas:` block's own range."""
    existing_lines, block_start, block_end = _locate_epic_areas_block(text)
    merged_lines = _merge_epic_areas_lines(existing_lines, new_declarations)
    new_block = "epic_areas:\n" + "\n".join(merged_lines) if merged_lines else "epic_areas:"
    new_block = new_block.rstrip("\n")

    if block_start is not None:
        assert block_end is not None
        return text[:block_start] + new_block + "\n\n" + text[block_end:]

    anchor_match = _DEVELOPMENT_STATUS_ANCHOR_RE.search(text)
    if not anchor_match:
        raise ValueError(
            "no existing `epic_areas:` block and no `development_status:` anchor to "
            "insert before — refusing to guess a location."
        )
    return text[: anchor_match.start()] + new_block + "\n\n" + text[anchor_match.start() :]


def atomic_write(path: Path, content: str) -> None:
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.remove(tmp_name)
        except OSError:
            pass
        raise


# ──────────────────────────────────────────────────────────────────────────
# Subcommands
# ──────────────────────────────────────────────────────────────────────────


def cmd_from_plan(args: argparse.Namespace) -> int:
    plan_path: Path = args.plan
    sprint_status_path: Path = args.sprint_status

    plan_text = plan_path.read_text(encoding="utf-8")
    declarations, warnings = extract_declarations_from_plan(plan_text)
    for warning in warnings:
        print(f"[warn] {warning}", file=sys.stderr)

    if not declarations:
        print(
            "[emit_epic_areas] no valid epic-decl sentinel found in "
            f"{plan_path} — nothing to write (sprint-status.yaml left untouched).",
            file=sys.stderr,
        )
        return 0

    original_text = sprint_status_path.read_text(encoding="utf-8")
    new_text = splice_epic_areas_into_sprint_status(original_text, declarations)

    epic_keys_str = ", ".join(sorted(declarations))
    if new_text == original_text:
        print(
            f"[emit_epic_areas] {sprint_status_path}: epic_areas: block already up to "
            f"date (idempotent no-op) for {len(declarations)} epic(s): {epic_keys_str}",
            file=sys.stderr,
        )
        return 0

    atomic_write(sprint_status_path, new_text)
    print(
        f"[emit_epic_areas] {sprint_status_path}: wrote/updated epic_areas: for "
        f"{len(declarations)} epic(s): {epic_keys_str}",
        file=sys.stderr,
    )
    return 0


def _project_root() -> Path:
    # project_controll/gerente/scripts/emit_epic_areas.py -> repo root is 3 parents up.
    return Path(__file__).resolve().parents[3]


def _compute_execution_graph_script() -> Path:
    return _project_root() / ".claude/skills/bagual-epic-runner/scripts/compute_execution_graph.py"


def cmd_validate(args: argparse.Namespace) -> int:
    plan_path: Path = args.plan
    plan_text = plan_path.read_text(encoding="utf-8")
    declarations, warnings = extract_declarations_from_plan(plan_text)
    for warning in warnings:
        print(f"[warn] {warning}", file=sys.stderr)

    epic_keys = sorted(declarations)
    print(f"[validate] {len(epic_keys)} valid epic-decl sentinel(s) parsed: {', '.join(epic_keys) or '(none)'}")

    if not declarations:
        return 1 if warnings else 0

    compute_script = _compute_execution_graph_script()
    if not compute_script.is_file():
        print(f"[validate] cannot round-trip — compute_execution_graph.py not found at {compute_script}", file=sys.stderr)
        return 1

    fd, tmp_name = tempfile.mkstemp(suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(declarations, handle)
        result = subprocess.run(
            [sys.executable, str(compute_script), "--epics", *epic_keys, "--declarations", tmp_name],
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        try:
            os.remove(tmp_name)
        except OSError:
            pass

    # exit 0 = graph computed; exit 3 = HALT on a real dependency cycle (still a
    # successful PARSE of this script's output — a cycle is a planning error in the
    # declared data, not a format mismatch between the two scripts).
    if result.returncode not in (0, 3):
        print(
            f"[validate] compute_execution_graph.py round-trip FAILED (exit {result.returncode}):\n{result.stderr}",
            file=sys.stderr,
        )
        return 1

    print(f"[validate] compute_execution_graph.py round-trip OK (exit {result.returncode}).")
    print(result.stdout)
    return 1 if warnings else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bridge: extract structured epic-decl sentinels from a Gerente "
        "planning-brain plano.md and write/update the epic_areas: block a "
        "sprint-status.yaml so compute_execution_graph.py (E10.3/E10.4) can compute a "
        "real (non-fail-safe) Execution Graph."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    from_plan_parser = subparsers.add_parser(
        "from-plan",
        help="Extract epic-decl sentinels from a plano.md and write/update the "
        "epic_areas: block of a sprint-status.yaml (atomic, idempotent, preserves "
        "all other content).",
    )
    from_plan_parser.add_argument("--plan", type=Path, required=True, help="Path to the plano.md")
    from_plan_parser.add_argument(
        "--sprint-status", type=Path, required=True, help="Path to the target sprint-status.yaml"
    )
    from_plan_parser.set_defaults(func=cmd_from_plan)

    validate_parser = subparsers.add_parser(
        "validate",
        help="Parse a plano.md's epic-decl sentinels, report validity, and round-trip "
        "through the REAL compute_execution_graph.py to prove format compatibility. "
        "Never writes anything.",
    )
    validate_parser.add_argument("--plan", type=Path, required=True, help="Path to the plano.md")
    validate_parser.set_defaults(func=cmd_validate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
