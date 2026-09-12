"""Command line entry point for outcome evaluation."""

from __future__ import annotations

import argparse
import json

from .db import default_db_url, load_decision_bundle
from .metrics import evaluate_rankings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate one ranked decision against stored rule checks and "
            "the held-out eval.ground_truth answer key."
        )
    )
    parser.add_argument("--decision-id", required=True, help="agent.decisions.decision_id")
    parser.add_argument(
        "--db-url",
        default=default_db_url(),
        help="Postgres URL for a role that can SET ROLE evaluator.",
    )
    parser.add_argument("--top-k", type=int, default=10, help="Prefix size for capture metrics.")
    parser.add_argument(
        "--high-hazard-threshold",
        type=float,
        default=0.7,
        help="Inclusive latent_hazard threshold for high-hazard capture.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Output format.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    bundle = load_decision_bundle(args.decision_id, db_url=args.db_url)
    report = evaluate_rankings(
        decision_id=bundle.decision_id,
        run_id=bundle.run_id,
        hospital_hipe=bundle.hospital_hipe,
        as_of_date=bundle.as_of_date,
        rankings=bundle.rankings,
        rule_summaries=bundle.rule_summaries,
        top_k=args.top_k,
        high_hazard_threshold=args.high_hazard_threshold,
    )

    if args.format == "json":
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(report.render_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
