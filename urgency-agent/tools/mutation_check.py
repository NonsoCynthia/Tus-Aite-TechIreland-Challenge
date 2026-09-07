"""Mutation check for the Tier 1 scorer -- `BUILDING_AN_AGENT_WITH_CONDUCTOR.md` Step 6.

100% coverage means every line executed, not that any behaviour is correct.
This script breaks the scorer on purpose, one mutation at a time, and asserts
that exactly the tests which *should* notice do.

Run it after changing anything in `urgency_agent/news2.py` or `scoring.py`:

    python tools/mutation_check.py

Exit code 0 means every mutation was caught by exactly its expected tests.
Non-zero means either a mutation slipped through (the tests have a hole) or a
different set of tests fired than expected (the tests have become coupled, or
the expectation is stale and should be updated deliberately).

**Why this is a script and not a manual exercise.** A mutation check run once
by hand proves something about that afternoon. Committed, it proves the same
thing every time the scorer changes -- and the numbers below become a
reviewable record rather than a claim in a chat log.

**The `__pycache__` trap this script exists to avoid.** Most of these
mutations change a single character, so the mutated and original files are
byte-identical in length. Python validates cached bytecode on (mtime, size),
and a revert landing in the same second as the mutation changes neither in a
way it can see -- so the *mutant's* bytecode gets reused and the tests appear
to pass against code that is no longer on disk. That failure mode is silent
and it reads as good news. Every run here clears __pycache__ before invoking
pytest. The same trap applies to the `git checkout` revert the process doc
suggests, which is why this does not use it.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "urgency_agent"
TESTS = ROOT / "tests"


@dataclass(frozen=True)
class Mutation:
    """One deliberate defect, and the tests that must catch it.

    `expected_tests` is matched against the *start* of each reported test id,
    so a parametrised case like `test_temperature_boundaries[39.1-2]` is named
    by its full id when the specific case matters and by the bare function
    name when any case will do.
    """

    name: str
    rationale: str
    path: Path
    old: str
    new: str
    expected_tests: frozenset[str] = field(default_factory=frozenset)


MUTATIONS: list[Mutation] = [
    Mutation(
        name="M1 systolic BP hypertensive tail 3 -> 0",
        rationale=(
            "SBP is not a descending ladder: >= 220 scores 3, the same as <= 90. A scorer "
            "written as one downward staircase gets the hypertensive tail wrong, and no "
            "mid-range case notices."
        ),
        path=PACKAGE / "news2.py",
        old="    # Not a ladder: the hypertensive tail returns to 3.\n    return 3",
        new="    # Not a ladder: the hypertensive tail returns to 3.\n    return 0",
        expected_tests=frozenset({"test_systolic_blood_pressure_boundaries[220-3]"}),
    ),
    Mutation(
        name="M2 temperature ceiling 2 -> 3",
        rationale=(
            "Temperature is the only component whose top band is 2, which is the whole "
            "reason NEWS2_MAX is 17 rather than 18. Both the boundary case and the "
            "maximum must notice."
        ),
        path=PACKAGE / "news2.py",
        old="    # Ceiling of 2 -- the one component that never reaches 3.\n    return 2",
        new="    # Ceiling of 2 -- the one component that never reaches 3.\n    return 3",
        expected_tests=frozenset(
            {"test_temperature_boundaries[39.1-2]", "test_total_of_worst_case_is_news2_max"}
        ),
    ),
    Mutation(
        name="M3 score oldest observation instead of newest (ADR-005)",
        rationale=(
            "ADR-005 scores the most recent observation. Scoring the oldest must break "
            "the selection tests AND the citation test -- citations have to point at the "
            "same observation the score came from, or the audit trail reconstructs to a "
            "different number."
        ),
        path=PACKAGE / "scoring.py",
        old="context.observations[-1]",
        new="context.observations[0]",
        expected_tests=frozenset(
            {
                "test_scores_the_most_recent_observation",
                "test_does_not_take_the_worst_observation",
                "test_citations_reference_the_scored_observation_not_an_earlier_one",
            }
        ),
    ),
    Mutation(
        name="M4 flat news2/NEWS2_MAX instead of the banded curve (ADR-006)",
        rationale=(
            "The mutation that matters most: a linear divide keeps every score in [0,1] "
            "and every ranking superficially plausible. Only tests asserting the SHAPE of "
            "the curve catch it -- the boundary tests correctly do not."
        ),
        path=PACKAGE / "scoring.py",
        old="    points = calibration.breakpoints\n",
        new="    points = calibration.breakpoints\n    return total / NEWS2_MAX\n",
        expected_tests=frozenset(
            {
                "test_normalisation_separates_the_escalation_bands",
                "test_normalisation_is_not_linear_in_news2",
            }
        ),
    ),
    Mutation(
        name="M5 paediatric guard removed (ADR-007)",
        rationale=(
            "ADR-007 refuses specialty 0601 outright. Removing the guard must fail both "
            "refusal tests -- including the one asserting the refusal is on the specialty "
            "rather than on data quality."
        ),
        path=PACKAGE / "scoring.py",
        old="if referral.specialty_hipe == PAEDIATRIC_SPECIALTY:",
        new="if False:",
        expected_tests=frozenset(
            {
                "test_paediatric_specialty_is_refused",
                "test_paediatric_refusal_happens_before_scoring",
            }
        ),
    ),
]

FAILED_LINE = re.compile(r"^FAILED (?:tests/)?[\w/]+\.py::(?P<test>\S+)", re.MULTILINE)


def _clear_pycache() -> None:
    """See the module docstring: without this, a same-size revert silently
    leaves the mutant's bytecode in play."""
    for cache in ROOT.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)


def _run_tests() -> set[str]:
    """Return the set of failing test ids (empty means everything passed)."""
    _clear_pycache()
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", str(TESTS), "-q", "-p", "no:cacheprovider"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return {m.group("test") for m in FAILED_LINE.finditer(completed.stdout)}


def _matches(failed: set[str], expected: frozenset[str]) -> bool:
    """Expected ids may name a parametrised case exactly or a bare function
    name standing for any of its cases."""
    if failed == expected:
        return True
    if len(failed) != len(expected):
        return False
    return all(
        any(actual == want or actual.startswith(f"{want}[") for actual in failed)
        for want in expected
    )


def main() -> int:
    print("Baseline: the suite must be green before anything is mutated.")
    baseline = _run_tests()
    if baseline:
        print(f"  ABORT -- {len(baseline)} test(s) already failing: {sorted(baseline)}")
        print("  Mutation results are meaningless against a red baseline.")
        return 2
    print("  clean\n")

    failures: list[str] = []

    for mutation in MUTATIONS:
        original = mutation.path.read_text()
        if mutation.old not in original:
            print(f"{mutation.name}\n  ABORT -- anchor text not found in {mutation.path.name}.")
            print("  The scorer changed; update this mutation deliberately.\n")
            failures.append(mutation.name)
            continue

        backup = Path(tempfile.mkdtemp()) / mutation.path.name
        shutil.copy2(mutation.path, backup)
        try:
            mutation.path.write_text(original.replace(mutation.old, mutation.new, 1))
            failed = _run_tests()
        finally:
            shutil.copy2(backup, mutation.path)
            _clear_pycache()

        ok = _matches(failed, mutation.expected_tests)
        print(f"{mutation.name}\n  {mutation.rationale}")
        print(f"  caught by {len(failed)} test(s): {sorted(failed) or 'NONE'}")
        if ok:
            print("  OK -- exactly the expected tests fired\n")
        else:
            print(f"  MISMATCH -- expected: {sorted(mutation.expected_tests)}")
            if not failed:
                print("  Nothing failed: the tests do not actually check this behaviour.")
            else:
                print(
                    "  A different set fired: the tests may be coupled, or this "
                    "expectation is stale."
                )
            print()
            failures.append(mutation.name)

    restored = _run_tests()
    if restored:
        print(f"WARNING -- suite not green after restore: {sorted(restored)}")
        return 2

    if failures:
        print(f"{len(failures)} of {len(MUTATIONS)} mutation(s) not caught as expected.")
        return 1

    print(f"All {len(MUTATIONS)} mutations caught by exactly the expected tests.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
