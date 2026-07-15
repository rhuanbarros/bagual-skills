#!/usr/bin/env python3
"""
validate_e1_wiring.py — Story E1.4 structural round-trip validation.

Proves STRUCTURALLY (without running the full `bagual-qa-builder` derivation)
that the wds-8 -> QA wiring built by E1.1/E1.2/E1.3 is actually in place:

  (a) the override .toml declares both `evolution_scenarios_source` and
      `focused_trigger_map_source` under [workflow];
  (b) `persistent_facts` contains the E1.1 enumeration instruction, the E1.2
      Coverage-Matrix-normalization instruction, and the E1.3 union-
      reconciliation instruction for the trigger-map;
  (c) this story's fixture exists and the evolution scenario file has the
      wds-8 wds-2 shape (Target/Current State/Desired State/User Journey/
      Success Criteria/Scope) plus a distinctive, traceable marker that does
      NOT exist in the canonical sources (00-ux-scenarios.md / trigger-map.md).

This is a structural/static check, not an execution of the builder itself —
see the story's "Verificação e2e manual" section for the procedure that
closes the AC with a real `/bagual-qa-builder` run.

Prints PASS/FAIL per check. Exits 0 iff every check passes, else 1.
"""

from __future__ import annotations

import pathlib
import re
import sys
import tomllib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[4]
FIXTURE_DIR = pathlib.Path(__file__).resolve().parent

OVERRIDE_TOML = REPO_ROOT / "_bmad" / "custom" / "bagual-qa-builder.toml"
CANONICAL_SCENARIOS = REPO_ROOT / "_bmad-output" / "C-UX-Scenarios" / "00-ux-scenarios.md"
CANONICAL_TRIGGER_MAP = REPO_ROOT / "_bmad-output" / "B-Trigger-Map" / "trigger-map.md"

FIXTURE_SCENARIO = FIXTURE_DIR / "evolution" / "scenarios" / "reabrir-proposta-recusada.md"
FIXTURE_FOCUSED_TRIGGER_MAP = FIXTURE_DIR / "focused-trigger-map.md"

DISTINCTIVE_MARKER = "reabrir-proposta-recusada"
DISTINCTIVE_FORCE_SNIPPET = "Recomeçar o cadastro do zero depois de uma recusa evitável"

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> bool:
    RESULTS.append((name, condition, detail))
    status = "PASS" if condition else "FAIL"
    line = f"[{status}] {name}"
    if detail:
        line += f" — {detail}"
    print(line)
    return condition


def main() -> int:
    print(f"Repo root resolved as: {REPO_ROOT}")
    print()

    # ------------------------------------------------------------------
    # (a) override declares both source keys under [workflow]
    # ------------------------------------------------------------------
    print("-- (a) override .toml declares evolution_scenarios_source + focused_trigger_map_source --")
    if not check("override .toml exists", OVERRIDE_TOML.is_file(), str(OVERRIDE_TOML)):
        pass
    else:
        try:
            data = tomllib.loads(OVERRIDE_TOML.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - want a PASS/FAIL line either way
            check("override .toml parses as valid TOML", False, str(exc))
            data = {}
        else:
            check("override .toml parses as valid TOML", True)

        workflow = data.get("workflow", {})
        check(
            "[workflow].evolution_scenarios_source declared",
            "evolution_scenarios_source" in workflow,
            workflow.get("evolution_scenarios_source", "<missing>"),
        )
        check(
            "[workflow].focused_trigger_map_source declared",
            "focused_trigger_map_source" in workflow,
            workflow.get("focused_trigger_map_source", "<missing>"),
        )

        # `persistent_facts` lives under [workflow] in this override (no separate TOML table
        # header follows [workflow], so everything after it — including persistent_facts —
        # parses as workflow.persistent_facts, not a top-level key). Fall back to top-level
        # in case a future edit moves it out from under [workflow].
        persistent_facts = workflow.get("persistent_facts", data.get("persistent_facts", []))
        joined_facts = "\n".join(persistent_facts) if isinstance(persistent_facts, list) else str(persistent_facts)

        # ------------------------------------------------------------------
        # (b) persistent_facts carry the E1.1 / E1.2 / E1.3 instructions
        # ------------------------------------------------------------------
        print()
        print("-- (b) persistent_facts contain the E1.1/E1.2/E1.3 instructions --")

        e11_present = bool(
            re.search(r"evolution_scenarios_source", joined_facts)
            and re.search(r"enumerate every file under", joined_facts, re.IGNORECASE)
        )
        check(
            "E1.1 enumeration instruction present (enumerate evolution_scenarios_source files)",
            e11_present,
        )

        e12_present = bool(
            re.search(r"Coverage Matrix", joined_facts)
            and re.search(r"SCENARIO", joined_facts)
            and re.search(r"PAGE", joined_facts)
            and re.search(r"PURPOSE", joined_facts)
        )
        check(
            "E1.2 normalization instruction present (SCENARIO/PAGE/PURPOSE -> Coverage Matrix row)",
            e12_present,
        )

        e13_present = bool(
            re.search(r"focused_trigger_map_source", joined_facts)
            and re.search(r"UNION not substitution|reconcil", joined_facts, re.IGNORECASE)
            and re.search(r"never\s+\w*\s*(drop|dropped|lost)|nunca (ser )?(perdido|dropado)", joined_facts, re.IGNORECASE)
        )
        check(
            "E1.3 union-reconciliation instruction present (trigger-map union, canonical never dropped)",
            e13_present,
        )

    # ------------------------------------------------------------------
    # (c) fixture exists and has the expected wds-8 scenario shape
    # ------------------------------------------------------------------
    print()
    print("-- (c) fixture exists with the expected wds-8 scenario shape --")

    check("fixture evolution scenario file exists", FIXTURE_SCENARIO.is_file(), str(FIXTURE_SCENARIO))
    check("fixture focused-trigger-map.md exists", FIXTURE_FOCUSED_TRIGGER_MAP.is_file(), str(FIXTURE_FOCUSED_TRIGGER_MAP))

    if FIXTURE_SCENARIO.is_file():
        scenario_text = FIXTURE_SCENARIO.read_text(encoding="utf-8")
        required_headers = [
            "## Target",
            "## Current State",
            "## Desired State",
            "## User Journey",
            "## Success Criteria",
            "## Scope",
        ]
        missing_headers = [h for h in required_headers if h not in scenario_text]
        check(
            "fixture scenario has all wds-8 wds-2 headers (Target/Current/Desired/Journey/Success/Scope)",
            not missing_headers,
            "missing: " + ", ".join(missing_headers) if missing_headers else "all 6 present",
        )
        check(
            "fixture scenario has a frontmatter title",
            bool(re.search(r'^title:\s*"', scenario_text, re.MULTILINE)),
        )
        check(
            "fixture scenario has a 'Pages affected' bullet list under Scope",
            "**Pages affected:**" in scenario_text,
        )
    else:
        check("fixture scenario has all wds-8 wds-2 headers (Target/Current/Desired/Journey/Success/Scope)", False, "scenario file missing, skipped")
        check("fixture scenario has a frontmatter title", False, "scenario file missing, skipped")
        check("fixture scenario has a 'Pages affected' bullet list under Scope", False, "scenario file missing, skipped")

    # ------------------------------------------------------------------
    # (c-cont.) fixture is distinctive/traceable: NOT present in canonical sources
    # ------------------------------------------------------------------
    print()
    print("-- (c-cont.) fixture marker is distinctive and absent from canonical sources --")

    if CANONICAL_SCENARIOS.is_file():
        canonical_scenarios_text = CANONICAL_SCENARIOS.read_text(encoding="utf-8")
        check(
            f"'{DISTINCTIVE_MARKER}' absent from canonical {CANONICAL_SCENARIOS.relative_to(REPO_ROOT)}",
            DISTINCTIVE_MARKER not in canonical_scenarios_text,
        )
    else:
        check(
            f"canonical scenarios source exists ({CANONICAL_SCENARIOS.relative_to(REPO_ROOT)})",
            False,
            "cannot confirm absence — canonical file missing",
        )

    if CANONICAL_TRIGGER_MAP.is_file():
        canonical_trigger_text = CANONICAL_TRIGGER_MAP.read_text(encoding="utf-8")
        check(
            f"distinctive force snippet absent from canonical {CANONICAL_TRIGGER_MAP.relative_to(REPO_ROOT)}",
            DISTINCTIVE_FORCE_SNIPPET not in canonical_trigger_text,
        )
    else:
        check(
            f"canonical trigger-map exists ({CANONICAL_TRIGGER_MAP.relative_to(REPO_ROOT)})",
            False,
            "cannot confirm absence — canonical file missing",
        )

    if FIXTURE_FOCUSED_TRIGGER_MAP.is_file():
        focused_text = FIXTURE_FOCUSED_TRIGGER_MAP.read_text(encoding="utf-8")
        check(
            "fixture focused-trigger-map.md contains the distinctive force snippet",
            DISTINCTIVE_FORCE_SNIPPET in focused_text,
        )
    else:
        check("fixture focused-trigger-map.md contains the distinctive force snippet", False, "file missing, skipped")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print()
    total = len(RESULTS)
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    failed = total - passed
    print(f"SUMMARY: {passed}/{total} checks passed, {failed} failed")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
