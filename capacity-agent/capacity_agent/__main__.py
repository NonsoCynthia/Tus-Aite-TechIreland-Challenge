"""CLI entrypoint: `python -m capacity_agent --hospital 9001 --as-of-date
2026-08-30 --run-id run-0001` scores every referral in that hospital-day's
cohort and writes each score via retrieval-service_20260904.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

from .calibration import DEFAULT_CALIBRATION_PATH, load_calibration
from .client import RetrievalClient
from .config import settings
from .run import run_for_cohort


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Score a hospital-day's cohort with the capacity agent."
    )
    parser.add_argument("--hospital", required=True, help="4-character HIPE hospital code")
    parser.add_argument("--as-of-date", required=True, type=date.fromisoformat)
    parser.add_argument("--run-id", required=True, help="Shared run_id for this coordinator run")
    parser.add_argument(
        "--calibration",
        type=Path,
        default=DEFAULT_CALIBRATION_PATH,
        help="Path to a calibration YAML file (default: the committed calibration.yml)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO)
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    calibration = load_calibration(args.calibration)

    with RetrievalClient(settings.retrieval_base_url, settings.bearer_token) as client:
        result = run_for_cohort(
            client,
            calibration,
            run_id=args.run_id,
            hospital_hipe=args.hospital,
            as_of_date=args.as_of_date,
        )

    logging.info(
        "scored %d referral(s); %d skipped (no evidence); %d with graph projection failures",
        len(result.scored),
        len(result.skipped),
        len(result.graph_projection_failed),
    )
    return 0 if not result.skipped and not result.graph_projection_failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
