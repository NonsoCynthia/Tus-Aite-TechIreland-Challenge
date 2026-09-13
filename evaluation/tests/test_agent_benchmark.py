from evaluation.agent_benchmark import build_parser, run_benchmark


def test_agent_benchmark_passes_all_controlled_checks() -> None:
    report = run_benchmark()

    assert report.passed
    assert report.failed_count == 0
    assert report.passed_count == 14


def test_agent_benchmark_parser_supports_json_output() -> None:
    args = build_parser().parse_args(["--format", "json"])

    assert args.format == "json"
