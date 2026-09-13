from evaluation.rationale_benchmark import benchmark_cases, run_rationale_benchmark


def test_rationale_benchmark_cases_cover_key_explanation_scenarios() -> None:
    cases = benchmark_cases()

    assert {case.case_id for case in cases} == {
        "high_urgency",
        "capacity_pressure",
        "crt_breach",
        "cpc_ordering",
        "missing_urgency",
        "paediatric_refusal",
    }


def test_rationale_benchmark_passes_with_local_heuristic_judge() -> None:
    report = run_rationale_benchmark()

    assert report.passed
    assert report.failed_count == 0
    assert report.passed_count == 6


def test_rationale_benchmark_reports_aggregate_metric_counts() -> None:
    report = run_rationale_benchmark()
    metrics = {metric.metric: metric for metric in report.metric_summary}

    assert metrics["Faithful to evidence"].value == "6/6 PASS"
    assert metrics["Unsupported claims absent"].value == "6/6 PASS"
    assert metrics["Diagnostic language avoided"].value == "6/6 PASS"
    assert metrics["System-action language avoided"].value == "6/6 PASS"
    assert metrics["Urgency evidence mentioned when applicable"].value == "4/4 PASS"
    assert metrics["Capacity evidence mentioned when applicable"].value == "1/1 PASS"
    assert metrics["CPC/CRT evidence mentioned when applicable"].value == "2/2 PASS"
    assert metrics["Average readability"].value == "4.8/5 (6/6 >= 3)"
    assert metrics["Required benchmark terms present"].value == "6/6 PASS"
