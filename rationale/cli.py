"""CLI for graph-backed rationale generation."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict

from .client import RetrievalClient
from .config import load_settings
from .evidence_pack import packs_from_decision_response
from .models import EvidencePack
from .render import render_many


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rationale",
        description=(
            "Render graph-backed rationale text for a hospital-day decision. "
            "Reads only from the retrieval service."
        ),
    )
    parser.add_argument("--hospital", required=True, help="4-character HIPE hospital code.")
    parser.add_argument("--as-of", required=True, help="Decision date, YYYY-MM-DD.")
    parser.add_argument(
        "--pathway",
        help="Optional pathway_number to render only one ranked placement.",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format. Defaults to text.",
    )
    parser.add_argument(
        "--style",
        choices=["technical", "clinician"],
        default="technical",
        help="Rationale wording style. Defaults to technical.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    settings = load_settings()

    with RetrievalClient(settings.retrieval_base_url, settings.bearer_token) as client:
        if args.pathway:
            evidence = client.get_placement_evidence(args.hospital, args.as_of, args.pathway)
            packs = [
                EvidencePack.from_evidence_response(
                    decision=f"decision/{args.hospital}/{args.as_of}",
                    pathway_number=args.pathway,
                    response=evidence,
                )
            ]
        else:
            decision = client.get_decision(args.hospital, args.as_of)
            packs = packs_from_decision_response(decision)
    rationales = render_many(packs, style=args.style)

    if args.format == "json":
        print(json.dumps([asdict(rationale) for rationale in rationales], indent=2))
        return 0

    for index, rationale in enumerate(rationales):
        if index:
            print()
        print(rationale.text)
    return 0
