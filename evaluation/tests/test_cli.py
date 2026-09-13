from evaluation.cli import build_parser


def test_cli_parser_accepts_required_decision_id() -> None:
    args = build_parser().parse_args(["--decision-id", "decision-1", "--format", "json"])

    assert args.decision_id == "decision-1"
    assert args.format == "json"
