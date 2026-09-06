"""The coordinator's CLI entry point (spec.md FR11).

`python -m coordinator --hospital <hipe> --as-of <date> --run-id <id>`
fetches one hospital-day cohort, scores it (live or fixture, ADR-008),
ranks it (`coordinator.app.ranking`), assembles a `DecisionIn`-shaped
payload (`coordinator.app.decision`), and either prints it (`--dry-run`)
or posts it to `POST /decisions`.

The three HTTP-touching functions (`fetch_cohort`, `fetch_live_scores`,
`post_decision`) and `_load_config` are the seams: tests fake them rather
than performing network I/O (NFR5).

Per ADR-002, this is the coordinator's only contact with the retrieval
service -- Postgres and the graph are never touched directly.
"""

import argparse
import json
import os
from typing import Any, NoReturn
from uuid import uuid4

import httpx
from dotenv import load_dotenv

from coordinator.app.decision import (
    DecisionPostOutcome,
    build_coordinator_version,
    build_decision,
    build_ranking,
    interpret_decision_response,
)
from coordinator.app.priority import ALPHA_MAX, ALPHA_MIN
from coordinator.app.ranking import rank_cohort
from coordinator.app.rule_checks import check_order, check_tiebreak

SEMANTIC_VERSION = "0.1.0"

_REQUEST_TIMEOUT_SECONDS = 30.0

# Exit codes: 0 is the only code that means success. Per spec.md FR9, a
# 207 must be surfaced as a distinct, non-zero exit condition and never
# reported as success -- so PARTIAL/REJECTED/INVALID each get their own
# non-zero code rather than sharing one generic "failure" code.
_EXIT_OK = 0
_EXIT_PARTIAL = 2
_EXIT_REJECTED = 3
_EXIT_INVALID = 4


def _load_config() -> tuple[str, str]:
    """Loads the retrieval service base URL and bearer token from `.env`.

    Never hardcoded, never printed -- read fresh from the environment
    (via the repo-root `.env`) each run.

    Returns:
        `(base_url, token)`.

    Raises:
        RuntimeError: If `RETRIEVAL_BEARER_TOKENS` is unset.
    """
    load_dotenv()
    port = os.environ.get("RETRIEVAL_PORT", "8000")
    token = os.environ.get("RETRIEVAL_BEARER_TOKENS", "").split(",")[0].strip()
    if not token:
        raise RuntimeError(
            "RETRIEVAL_BEARER_TOKENS is not set (checked the environment and "
            "the repo-root .env) -- the coordinator cannot authenticate to "
            "the retrieval service without it."
        )
    return f"http://localhost:{port}", token


def fetch_cohort(
    hospital_hipe: str, as_of_date: str, *, base_url: str, token: str
) -> list[dict[str, Any]]:
    """Fetches the cohort via `GET /hospitals/{hospital_hipe}/cohort/{as_of_date}`.

    Args:
        hospital_hipe: 4-character HIPE hospital code.
        as_of_date: The hospital-day to rank (ISO date string).
        base_url: The retrieval service's base URL.
        token: The bearer token to authenticate with.

    Returns:
        The cohort's `referrals` list, as `retrieval.app.db.get_cohort`
        shapes it.
    """
    response = httpx.get(
        f"{base_url}/hospitals/{hospital_hipe}/cohort/{as_of_date}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=_REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    referrals: list[dict[str, Any]] = response.json()["referrals"]
    return referrals


def fetch_live_scores(
    run_id: str, hospital_hipe: str, *, base_url: str, token: str
) -> dict[str, dict[str, Any]]:
    """Fetches scores via `GET /runs/{run_id}/hospitals/{hospital_hipe}/scores`.

    Args:
        run_id: Identifies the agent run the scores were written under.
        hospital_hipe: 4-character HIPE hospital code.
        base_url: The retrieval service's base URL.
        token: The bearer token to authenticate with.

    Returns:
        Scores keyed by `pathway_number`, then by agent name
        (`"urgency"`/`"capacity"`), as
        `retrieval.app.db.get_scores_for_run` shapes it.
    """
    response = httpx.get(
        f"{base_url}/runs/{run_id}/hospitals/{hospital_hipe}/scores",
        headers={"Authorization": f"Bearer {token}"},
        timeout=_REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    scores: dict[str, dict[str, Any]] = response.json()["scores"]
    return scores


def fixture_scores(cohort: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """A deterministic fixture score source (ADR-008).

    For development and testing while the urgency and capacity agents
    don't yet exist. Never selected unless `--score-source fixture` is
    explicitly passed, and recorded in `coordinator_version` so a
    decision written from these scores can never be mistaken for one
    written from real agent output.

    Args:
        cohort: The cohort's `referrals` list.

    Returns:
        Scores shaped like `fetch_live_scores`'s return value.
    """
    scores: dict[str, dict[str, Any]] = {}
    for referral in cohort:
        pathway_number = referral["pathway_number"]
        specialty_hipe = referral["specialty_hipe"]
        scores[pathway_number] = {
            "urgency": {
                "score": (hash(pathway_number) % 1000) / 1000,
                "citations": [
                    {
                        "evidence_type": "observation",
                        "evidence_key": (
                            f"{referral['hospital_hipe']}/{pathway_number}/"
                            "2026-01-01%2000%3A00%3A00/hr"
                        ),
                    }
                ],
            },
            "capacity": {
                "score": (hash(specialty_hipe) % 1000) / 1000,
                "citations": [
                    {
                        "evidence_type": "bed_status",
                        "evidence_key": (
                            f"{referral['hospital_hipe']}/{specialty_hipe}/"
                            "2026-01-01%2000%3A00%3A00"
                        ),
                    }
                ],
            },
        }
    return scores


def merge_scores_into_cohort(
    cohort: list[dict[str, Any]], scores: dict[str, dict[str, Any]], *, run_id: str
) -> list[dict[str, Any]]:
    """Attaches each referral's scores and citations onto its cohort row.

    A referral absent from `scores`, or present with only one agent's
    key, gets `None` for the missing score(s) -- never defaulted to zero
    (ADR-008). `coordinator.app.ranking.rank_cohort` is what actually
    excludes a referral with no urgency score.

    Args:
        cohort: The cohort's `referrals` list.
        scores: As returned by `fetch_live_scores`/`fixture_scores`.
        run_id: Attached to every referral -- needed to build the
            `score` evidence_key (ADR-009).

    Returns:
        A new list of referral dicts, each carrying `run_id`,
        `urgency_score`, `urgency_citations`, `capacity_score` and
        `capacity_citations`.
    """
    merged = []
    for referral in cohort:
        referral_scores = scores.get(referral["pathway_number"], {})
        urgency = referral_scores.get("urgency")
        capacity = referral_scores.get("capacity")
        merged.append(
            {
                **referral,
                "run_id": run_id,
                "urgency_score": urgency["score"] if urgency else None,
                "urgency_citations": urgency["citations"] if urgency else [],
                "capacity_score": capacity["score"] if capacity else None,
                "capacity_citations": capacity["citations"] if capacity else [],
            }
        )
    return merged


def post_decision(payload: dict[str, Any], *, base_url: str, token: str) -> tuple[int, Any]:
    """Posts the assembled decision via `POST /decisions`.

    Args:
        payload: A `DecisionIn`-shaped dict (`coordinator.app.decision.
            build_decision`).
        base_url: The retrieval service's base URL.
        token: The bearer token to authenticate with.

    Returns:
        `(status_code, body)` -- `body` is the parsed JSON response, or
        the raw text if it isn't JSON.
    """
    response = httpx.post(
        f"{base_url}/decisions",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=_REQUEST_TIMEOUT_SECONDS,
    )
    try:
        body: Any = response.json()
    except ValueError:
        body = response.text
    return response.status_code, body


_CAPACITY_DIRECTION_REQUIRED_MESSAGE = (
    "--capacity-direction is required with no default (ADR-007): pass "
    "'availability' or 'pressure'. The coordinator refuses to guess "
    "whether capacity_score means available beds or system pressure -- "
    "getting this backwards silently inverts the ranking under load."
)


class _CoordinatorArgumentParser(argparse.ArgumentParser):
    """Substitutes the ADR-007 explanation for argparse's generic message.

    `--capacity-direction` is `required=True` so the usage line correctly
    shows it as required rather than in square brackets. That makes
    argparse itself raise "the following arguments are required:
    --capacity-direction" when it's omitted, before any application code
    runs -- this override replaces that generic message with the
    ADR-007-specific one (naming both accepted values and why there is no
    default) while leaving every other argparse error untouched.
    """

    def error(self, message: str) -> NoReturn:
        if message.startswith("the following arguments are required") and (
            "--capacity-direction" in message
        ):
            message = _CAPACITY_DIRECTION_REQUIRED_MESSAGE
        super().error(message)


def build_arg_parser() -> argparse.ArgumentParser:
    """Builds the CLI's argument parser.

    Returns:
        The configured `ArgumentParser`.
    """
    parser = _CoordinatorArgumentParser(
        prog="coordinator",
        description=(
            "Ranks one hospital's cohort for one day and posts the decision "
            "(spec.md FR1-FR11). Deterministic -- no LLM is involved."
        ),
    )
    parser.add_argument("--hospital", required=True, help="4-character HIPE hospital code.")
    parser.add_argument("--as-of", required=True, help="The hospital-day to rank (ISO date).")
    parser.add_argument("--run-id", required=True, help="The run_id this decision's scores use.")
    parser.add_argument(
        "--capacity-direction",
        choices=["availability", "pressure"],
        required=True,
        help=(
            "Required, no default (ADR-007). 'availability': 1.0 = most "
            "capacity free. 'pressure': 1.0 = maximum pressure."
        ),
    )
    parser.add_argument(
        "--score-source",
        choices=["live", "fixture"],
        default="live",
        help="Where scores come from (ADR-008). Defaults to 'live'.",
    )
    parser.add_argument(
        "--legacy-citations",
        action="store_true",
        help="Use the ADR-009 citation fallback, valid against today's EvidenceType.",
    )
    parser.add_argument(
        "--alpha-min",
        type=float,
        default=ALPHA_MIN,
        help=f"Alpha lower bound (default {ALPHA_MIN}).",
    )
    parser.add_argument(
        "--alpha-max",
        type=float,
        default=ALPHA_MAX,
        help=f"Alpha upper bound (default {ALPHA_MAX}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the assembled decision without posting it.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Runs the coordinator end to end.

    Args:
        argv: Command-line arguments, or `None` to use `sys.argv[1:]`.

    Returns:
        `0` on success or an empty cohort; a distinct non-zero code for
        each of `PARTIAL` (207), `REJECTED` (400) and `INVALID` (422) --
        a `207` is never reported as success (spec.md FR9).
    """
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    base_url, token = _load_config()

    cohort = fetch_cohort(args.hospital, args.as_of, base_url=base_url, token=token)
    if not cohort:
        print("Empty cohort -- nothing to rank.")
        return _EXIT_OK

    scores = (
        fixture_scores(cohort)
        if args.score_source == "fixture"
        else fetch_live_scores(args.run_id, args.hospital, base_url=base_url, token=token)
    )
    merged = merge_scores_into_cohort(cohort, scores, run_id=args.run_id)

    result = rank_cohort(
        merged,
        capacity_direction=args.capacity_direction,
        alpha_min=args.alpha_min,
        alpha_max=args.alpha_max,
    )

    if result.excluded:
        print(f"{len(result.excluded)} referral(s) excluded for want of an urgency score:")
        for referral in result.excluded:
            print(f"  {referral['pathway_number']}: {referral['exclusion_reason']}")

    if not result.rankings:
        print("No referrals could be ranked (no urgency scores available).")
        return _EXIT_OK

    # RULE-ORDER/RULE-TIEBREAK are whole-list properties (spec.md FR10):
    # computed once over the full ranked list, then attached to every
    # placement -- never per-referral in isolation.
    order_passed = check_order(result.rankings)
    tiebreak_passed = check_tiebreak(result.rankings)
    rankings = [
        build_ranking(
            referral,
            legacy_citations=args.legacy_citations,
            order_passed=order_passed,
            tiebreak_passed=tiebreak_passed,
        )
        for referral in result.rankings
    ]
    coordinator_version = build_coordinator_version(
        semantic_version=SEMANTIC_VERSION,
        capacity_direction=args.capacity_direction,
        alpha_min=args.alpha_min,
        alpha_max=args.alpha_max,
        score_source=args.score_source,
    )
    payload = build_decision(
        decision_id=f"dec-{uuid4()}",
        run_id=args.run_id,
        hospital_hipe=args.hospital,
        as_of_date=args.as_of,
        coordinator_version=coordinator_version,
        rankings=rankings,
    )

    if args.dry_run:
        print(json.dumps(payload, indent=2, default=str))
        return _EXIT_OK

    status_code, body = post_decision(payload, base_url=base_url, token=token)
    outcome = interpret_decision_response(status_code)

    if outcome is DecisionPostOutcome.OK:
        print(f"Decision {payload['decision_id']} posted: {len(rankings)} ranking(s).")
        return _EXIT_OK
    if outcome is DecisionPostOutcome.PARTIAL:
        print(
            f"Decision {payload['decision_id']} PARTIALLY written (207): Postgres "
            f"committed but the graph projection failed. This is NOT success. "
            f"Response: {body}"
        )
        return _EXIT_PARTIAL
    if outcome is DecisionPostOutcome.REJECTED:
        print(f"Decision rejected by Postgres (400): {body}")
        return _EXIT_REJECTED
    print(f"Decision failed validation (422): {body}")
    return _EXIT_INVALID
