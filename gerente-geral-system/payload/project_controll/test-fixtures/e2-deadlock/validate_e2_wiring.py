#!/usr/bin/env python3
"""
validate_e2_wiring.py — Story E2.4 structural deadlock-fix validation.

Proves STRUCTURALLY (without running a full autonomous `/bmad-code-review`
pipeline) that all three mechanisms E2.1/E2.2/E2.3 wired into
`_bmad/custom/bmad-code-review.toml` are actually present and textually
verifiable in `persistent_facts`:

  (a) E2.1 — FILE-MEDIATED DISPATCH: each layer writes findings-{layer}.md +
      a DONE-{layer}.marker instead of returning via SendMessage; SendMessage
      is explicitly forbidden as the findings transport (kills the Epic 32
      deadlock: SendMessage to a spawned agent's TYPE LABEL, e.g.
      "general-purpose", never routes back to the parent).
  (b) E2.2 — DUAL COMPLETION DETECTION: the Agent tool call's own return is
      the PRIMARY/blocking completion signal; the disk marker is only a
      SECONDARY signal used to fetch the payload after (1) already fired —
      never polled on its own, never used as a standalone/first-checked
      signal.
  (c) E2.3 — PER-LAYER TIMEOUT + failed_layers convergence: an explicit,
      configurable wall-clock timeout per layer, and confirmation that all
      failure paths (Agent-tool failure, missing marker, timeout) converge
      on the same {failed_layers} list so structured triage always proceeds
      even with 1-2 layers missing.

This is a structural/static check over the override file — it does not spawn
subagents or exercise a real pipeline run. See the story's "Cenários de
regressão (verificação e2e manual)" section for the two manual procedures
that close the AC against a real `/bmad-code-review` run: (i) reproducing
the historical Epic 32 SendMessage-to-type-label deadlock, and (ii)
simulating a layer that dies without ever writing its marker.

Prints PASS/FAIL per check. Exits 0 iff every check passes, else 1.
"""

from __future__ import annotations

import pathlib
import re
import sys
import subprocess
import tomllib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]

OVERRIDE_TOML = REPO_ROOT / "_bmad" / "custom" / "bmad-code-review.toml"
SHIPPED_SKILL_DIR = REPO_ROOT / ".claude" / "skills" / "bmad-code-review"

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
    """Print the SUMMARY line from the actual RESULTS tally (never hardcoded) and
    return the matching exit code. `aborted`, when set, notes why main() returned early."""
    print()
    total = len(RESULTS)
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    failed = total - passed
    suffix = f" (aborted early — {aborted})" if aborted else ""
    print(f"SUMMARY: {passed}/{total} checks passed, {failed} failed{suffix}")
    return 0 if failed == 0 else 1


def main() -> int:
    print(f"Repo root resolved as: {REPO_ROOT}")
    print()

    # ------------------------------------------------------------------
    # Load + parse the override
    # ------------------------------------------------------------------
    print("-- override .toml loads and parses --")
    if not check("override .toml exists", OVERRIDE_TOML.is_file(), str(OVERRIDE_TOML)):
        return summarize(aborted="override missing")

    try:
        raw_text = OVERRIDE_TOML.read_text(encoding="utf-8")
    except OSError as exc:
        check("override .toml is readable", False, str(exc))
        return summarize(aborted="override unreadable")

    try:
        data = tomllib.loads(raw_text)
    except Exception as exc:  # noqa: BLE001 - want a PASS/FAIL line either way
        check("override .toml parses as valid TOML", False, str(exc))
        return summarize(aborted="TOML invalid")
    check("override .toml parses as valid TOML", True)

    workflow = data.get("workflow", {})
    persistent_facts = workflow.get("persistent_facts", data.get("persistent_facts", []))
    check(
        "[workflow].persistent_facts is a non-empty list",
        isinstance(persistent_facts, list) and len(persistent_facts) > 0,
        f"{len(persistent_facts) if isinstance(persistent_facts, list) else 'n/a'} entries",
    )
    joined_facts = "\n".join(persistent_facts) if isinstance(persistent_facts, list) else str(persistent_facts)

    # Informational only (not a PASS/FAIL tally item): the override had 8 entries when E2.3
    # closed (6 from E2.1/E2.2 + 2 from E2.3), but persistent_facts is expected to keep growing
    # as future stories touch this override — a hard len() == 8 assertion would misleadingly
    # flip to FAIL on any unrelated future addition, reading as "deadlock fix regressed" when
    # it isn't. Print the count for visibility without gating pass/fail on it.
    print(
        f"[INFO] persistent_facts entry count: "
        f"{len(persistent_facts) if isinstance(persistent_facts, list) else 'n/a'} "
        f"(8 = E2.1/E2.2/E2.3 baseline; higher is expected as the override evolves further)"
    )

    # ------------------------------------------------------------------
    # (a) E2.1 — file-mediated dispatch, SendMessage forbidden
    # ------------------------------------------------------------------
    print()
    print("-- (a) E2.1: file-mediated dispatch (findings-{layer}.md + marker), SendMessage forbidden --")

    check(
        "dispatch instruction writes findings-{layer}.md per layer",
        bool(re.search(r"findings-\{layer\}\.md", joined_facts)),
    )
    check(
        "dispatch instruction emits a DONE-{layer}.marker completion marker",
        bool(re.search(r"DONE-\{layer\}\.marker", joined_facts)),
    )
    check(
        "the 3 concrete per-layer filenames are named (blind-hunter / edge-case-hunter / acceptance-auditor)",
        all(
            name in joined_facts
            for name in (
                "findings-blind-hunter.md",
                "findings-edge-case-hunter.md",
                "findings-acceptance-auditor.md",
            )
        ),
    )
    check(
        "SendMessage is explicitly forbidden as the findings transport",
        bool(re.search(r"NEVER\s+attempt\s+to\s+SendMessage", joined_facts, re.IGNORECASE)),
    )
    check(
        "Epic 32 is named in persistent_facts as the deadlock this dispatch kills",
        bool(re.search(r"Epic 32", joined_facts)),
    )
    # The "SendMessage routed to a TYPE LABEL, not the concrete instance" root-cause detail lives in
    # this override file's header comment (loaded by every consumer of the file, not just the
    # `persistent_facts` array the workflow ingests as facts) — check the raw file text for it.
    check(
        "the override file documents the exact root cause (SendMessage routed to a type label, not the instance)",
        bool(re.search(r"Epic 32", raw_text)) and bool(re.search(r"type label", raw_text, re.IGNORECASE)),
    )

    # ------------------------------------------------------------------
    # (b) E2.2 — dual completion detection
    # ------------------------------------------------------------------
    print()
    print("-- (b) E2.2: dual completion detection (Agent tool return = primary, marker = secondary) --")

    check(
        "a DUAL COMPLETION DETECTION entry exists",
        bool(re.search(r"DUAL COMPLETION DETECTION", joined_facts)),
    )
    check(
        "Agent tool return is declared the PRIMARY / blocking completion signal",
        bool(re.search(r"PRIMARY\s*/\s*blocking signal", joined_facts, re.IGNORECASE))
        and bool(re.search(r"Agent tool", joined_facts)),
    )
    check(
        "disk marker is declared a SECONDARY / payload-only signal, checked only after the primary",
        bool(re.search(r"SECONDARY\s*/\s*payload signal", joined_facts, re.IGNORECASE))
        and bool(re.search(r"used ONLY after", joined_facts, re.IGNORECASE)),
    )
    check(
        "marker is explicitly barred from being a standalone/first-checked signal (no infinite poll on it alone)",
        bool(re.search(r"never.*standalone.*first-checked", joined_facts, re.IGNORECASE))
        or bool(re.search(r"never enters? a loop", joined_facts, re.IGNORECASE)),
    )
    check(
        "a layer dying without a marker is caught by the Agent-tool-return signal (no silent hang)",
        bool(re.search(r"a layer that dies.*marker or no marker.*caught here", joined_facts, re.IGNORECASE))
        or bool(re.search(r"dies for any reason.*caught", joined_facts, re.IGNORECASE)),
    )

    # ------------------------------------------------------------------
    # (c) E2.3 — per-layer timeout + failed_layers as convergence point
    # ------------------------------------------------------------------
    print()
    print("-- (c) E2.3: per-layer timeout + failed_layers as the single convergence point --")

    check(
        "a PER-LAYER TIMEOUT entry exists",
        bool(re.search(r"PER-LAYER TIMEOUT", joined_facts)),
    )
    check(
        "the timeout is configurable with a stated default (20 minutes)",
        bool(re.search(r"20 minutes", joined_facts)) and bool(re.search(r"CONFIGURABLE", joined_facts, re.IGNORECASE)),
    )
    timeout_names_failed_layers = bool(re.search(r"\{failed_layers\}", joined_facts))
    timeout_condition_stated = bool(
        re.search(r"neither.*Agent tool call.*returned.*existing.*marker", joined_facts, re.IGNORECASE)
    ) or bool(
        re.search(r"EITHER the Agent tool call having returned OR.*marker", joined_facts, re.IGNORECASE)
    )
    check(
        "timeout expiry (no Agent tool return AND no marker) converges into failed_layers",
        timeout_names_failed_layers and timeout_condition_stated,
    )
    check(
        "failed_layers is declared the single convergence point for all failure sources",
        bool(re.search(r"SINGLE CONVERGENCE POINT", joined_facts, re.IGNORECASE)),
    )
    check(
        "structured triage always proceeds even with 1-2 layers missing (never blocked/infinite poll)",
        bool(re.search(r"STRUCTURED TRIAGE ALWAYS PROCEEDS", joined_facts, re.IGNORECASE))
        and bool(re.search(r"1-2 LAYERS MISSING", joined_facts, re.IGNORECASE)),
    )
    check(
        "no retry/re-invocation is introduced when a layer times out",
        bool(re.search(r"Do NOT re-invoke the layer", joined_facts, re.IGNORECASE)),
    )

    # ------------------------------------------------------------------
    # Bonus — isolation: no shipped bmad-code-review file was edited
    # ------------------------------------------------------------------
    print()
    print("-- bonus: no shipped bmad-code-review/ file touched by any of E2.1-E2.3 --")
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", str(SHIPPED_SKILL_DIR)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=15,
        )
        git_ok = result.returncode == 0
        dirty = result.stdout.strip()
        check(
            "git status --porcelain .claude/skills/bmad-code-review/ is empty",
            git_ok and dirty == "",
            dirty if dirty else "clean",
        )
    except Exception as exc:  # noqa: BLE001
        check("git status --porcelain .claude/skills/bmad-code-review/ is empty", False, f"git unavailable: {exc}")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    return summarize()


if __name__ == "__main__":
    sys.exit(main())
