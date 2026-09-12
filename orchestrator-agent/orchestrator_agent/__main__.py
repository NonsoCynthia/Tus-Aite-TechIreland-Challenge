"""CLI: `python -m orchestrator_agent --hospital 9001 --as-of-date
2026-08-30 --run-id run-0001` runs the full urgency -> capacity ->
coordinator -> rationale pipeline through the tool-calling agent and prints
its final narrative.
"""

from __future__ import annotations

import argparse
import sys

from .config import load_settings
from .run import run_pipeline


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the triage orchestrator + rationale agent end to end."
    )
    parser.add_argument("--hospital", required=True, help="4-character HIPE hospital code")
    parser.add_argument("--as-of-date", required=True, help="ISO date, e.g. 2026-08-30")
    parser.add_argument("--run-id", required=True, help="Shared run_id for this pipeline run")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    settings = load_settings()
    if not settings.openai_api_key:
        print(
            "OPENAI_API_KEY is not set -- required to run the orchestrator agent.",
            file=sys.stderr,
        )
        return 1

    narrative = run_pipeline(args.hospital, args.as_of_date, args.run_id, settings=settings)
    print(narrative)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
