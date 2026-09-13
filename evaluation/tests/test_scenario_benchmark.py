from evaluation.scenario_benchmark import run_scenario_benchmark


def test_scenario_benchmark_matches_regression_baseline() -> None:
    report = run_scenario_benchmark()

    assert report.passed
    assert report.failed_count == 0
    assert report.passed_count == 21
