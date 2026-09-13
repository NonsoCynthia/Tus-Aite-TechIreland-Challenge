from evaluation.trace_audit import run_trace_audit


def test_trace_audit_passes_deterministic_fixture() -> None:
    report = run_trace_audit()

    assert report.passed
    assert report.failed_count == 0
    assert report.passed_count == 8


def test_trace_audit_covers_expected_trace_areas() -> None:
    report = run_trace_audit()

    assert {check.area for check in report.checks} == {
        "schema",
        "provenance",
        "ordering",
        "safety",
        "citations",
        "rules",
        "rationale",
    }
