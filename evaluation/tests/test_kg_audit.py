from evaluation.kg_audit import run_audit
from evaluation.suite import run_suite


def test_kg_audit_passes_repository_artifacts() -> None:
    report = run_audit()

    assert report.passed
    assert report.failed_count == 0
    assert report.passed_count == 5


def test_evaluation_suite_combines_agent_and_kg_checks() -> None:
    report = run_suite()

    assert report.passed
    assert report.agent_benchmark.passed_count == 14
    assert report.kg_audit.passed_count == 5
