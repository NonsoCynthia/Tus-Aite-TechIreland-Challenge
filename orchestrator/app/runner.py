"""One ranking run: urgency, then capacity, then the coordinator's own functions.

Composed from each track's public functions -- never their main() or CLI. All of
the coordinator's fetch/rank/post helpers take base_url as a keyword; only
_load_config() hardcodes localhost, and main() is its sole caller, so this runs
correctly inside a container pointed at http://retrieval:8000.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from datetime import date, datetime, timezone

logger = logging.getLogger(__name__)

# ADR-007, coordinator/README.md: the capacity agent documents capacity_score as
# a resource-PRESSURE score (1.0 = severe constraint). Read as 'availability' the
# whole system inverts while every number stays in range and the ranking stays
# superficially plausible. Not configurable here on purpose.
CAPACITY_DIRECTION = "pressure"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def coerce_scores(scores: dict) -> int:
    """Belt and braces: rank_cohort sums these, and a string operand raises.

    retrieval served numeric(4,3) as a JSON string until it set
    response_model=None on its GET routes, so this now coerces nothing and logs
    0. Kept because the cost is one isinstance per score and the failure it
    guards is a TypeError mid-run. Returns how many were coerced, for the log.
    """
    n = 0
    for pathway in scores.values():
        for agent in pathway.values():
            if isinstance(agent.get("score"), str):
                agent["score"] = float(agent["score"])
                n += 1
    return n


class _Progress:
    """Counts rows the agents have actually committed, by polling the same
    endpoint the coordinator reads. The agents' run_for_cohort reports nothing
    until it returns, so without this the bar jumps 0 -> 305 -> 613 at agent
    boundaries. Counting committed rows means the bar cannot advance unless work
    really happened -- no interpolation, no timer."""

    def __init__(self, run_id: str, hospital_hipe: str, store, base_url: str, token: str):
        self._args = (run_id, hospital_hipe, store, base_url, token)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def __enter__(self) -> "_Progress":
        self._thread = threading.Thread(target=self._poll, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _poll(self) -> None:
        run_id, hosp, store, base_url, token = self._args
        import httpx
        url = f"{base_url}/runs/{run_id}/hospitals/{hosp}/scores"
        headers = {"Authorization": f"Bearer {token}"}
        while not self._stop.wait(0.6):
            try:
                r = httpx.get(url, headers=headers, timeout=5.0)
                if r.status_code != 200:
                    continue
                by_pathway = r.json().get("scores", {})
                # one row per (pathway, agent): this is the real committed count
                store.update(run_id, scored=sum(len(v) for v in by_pathway.values()))
            except Exception:                                   # noqa: BLE001
                continue


def execute(run, store, *, base_url: str, token: str) -> None:
    """Runs to completion on a worker thread, updating `store` as it goes."""
    from capacity_agent.calibration import load_calibration as load_capacity_calibration
    from capacity_agent.client import RetrievalClient as CapacityClient
    from capacity_agent.run import run_for_cohort as run_capacity
    from coordinator.app.cli import (
        SEMANTIC_VERSION,
        build_coordinator_version,
        build_ranking,
        fetch_cohort,
        fetch_live_scores,
        merge_scores_into_cohort,
        post_decision,
    )
    from coordinator.app.decision import build_decision, interpret_decision_response
    from coordinator.app.ranking import rank_cohort
    from coordinator.app.rule_checks import check_order, check_tiebreak
    from urgency_agent.calibration import load_calibration as load_urgency_calibration
    from urgency_agent.client import RetrievalClient as UrgencyClient
    from urgency_agent.run import run_for_cohort as run_urgency

    rid, hosp, as_of = run.run_id, run.hospital_hipe, run.as_of_date
    store.update(rid, started_at=_now())

    try:
        cohort = fetch_cohort(hosp, as_of, base_url=base_url, token=token)
        # The empty-cohort guard lives only in coordinator main(), which we do not
        # call, so it is re-implemented here rather than thrown away.
        if not cohort:
            store.update(rid, status="failed", error="empty cohort: nothing to rank",
                         finished_at=_now())
            return
        store.update(rid, cohort_size=len(cohort), status="scoring_urgency")

        as_of_d = date.fromisoformat(as_of)

        # --- urgency -------------------------------------------------------
        u_cal = load_urgency_calibration()
        with _Progress(rid, hosp, store, base_url, token), UrgencyClient(base_url, token) as client:
            u = run_urgency(client, u_cal, run_id=rid, hospital_hipe=hosp, as_of_date=as_of_d)
        store.update(rid, urgency_scored=len(u.scored),
                     refused_paediatric=len(u.refused_paediatric), skipped=len(u.skipped),
                     status="scoring_capacity")

        # --- capacity ------------------------------------------------------
        c_cal = load_capacity_calibration()
        with _Progress(rid, hosp, store, base_url, token), CapacityClient(base_url, token) as client:
            c = run_capacity(client, c_cal, run_id=rid, hospital_hipe=hosp, as_of_date=as_of_d)
        store.update(rid, capacity_scored=len(c.scored),
                     scored=len(u.scored) + len(c.scored), status="ranking")


        # --- rank ----------------------------------------------------------
        scores = fetch_live_scores(rid, hosp, base_url=base_url, token=token)
        coerced = coerce_scores(scores)
        logger.info("coerced %d string scores to float", coerced)

        merged = merge_scores_into_cohort(cohort, scores, run_id=rid)
        result = rank_cohort(merged, capacity_direction=CAPACITY_DIRECTION)
        if not result.rankings:
            store.update(rid, status="failed", excluded=len(result.excluded),
                         error="no referral could be ranked (no urgency scores)",
                         finished_at=_now())
            return

        # Whole-list properties: computed once, attached to every placement.
        order_ok = check_order(result.rankings)
        tiebreak_ok = check_tiebreak(result.rankings)
        rankings = [build_ranking(r, order_passed=order_ok, tiebreak_passed=tiebreak_ok)
                    for r in result.rankings]

        decision_id = f"dec-{uuid.uuid4()}"
        payload = build_decision(
            decision_id=decision_id, run_id=rid, hospital_hipe=hosp, as_of_date=as_of,
            coordinator_version=build_coordinator_version(
                semantic_version=SEMANTIC_VERSION, capacity_direction=CAPACITY_DIRECTION,
                alpha_min=0.5, alpha_max=0.9, score_source="live"),
            rankings=rankings)

        head = result.rankings[0]
        # news2 is NOT in the cohort payload (14 fields, no vitals). Harvest it
        # from the urgency agent's own pass so the UI never needs 308 context calls.
        news2 = {pw: getattr(r, "news2", None) for pw, r in u.scored.items()}
        # The capacity agent computes ward_pressure and clinic_pressure on its way
        # to a score (CapacityScoreResult) and then discards both -- POST /scores
        # carries only the score, so neither reaches Postgres, the graph or the
        # UI. news2 above proved the pattern; this is the missing other half, and
        # it is what lets a patient page say WHAT informed the capacity agent
        # rather than only that it ran.
        capacity_detail = {
            pw: {"ward_pressure": getattr(r, "ward_pressure", None),
                 "clinic_pressure": getattr(r, "clinic_pressure", None)}
            for pw, r in c.scored.items()
        }

        # rank_cohort returns the raw ranked dicts -- alpha, priority, band,
        # wait_normalised, severity_rank, both citation lists. build_ranking
        # returns a DIFFERENT eight-key shape, and is the only place
        # rationale_summary and rule_checks are ever attached.
        #
        # Storing result.rankings alone silently dropped every per-referral rule
        # check the coordinator computed -- RULE-CRT-URGENT, RULE-CRT-SEMI,
        # RULE-TRIAGE-TURNAROUND -- and the coordinator's own rationale, which is
        # why no rule ID appeared anywhere in the product although all five are
        # seeded in core.ref_rules and written to Postgres and the graph.
        #
        # Swapping one for the other would lose alpha and priority instead, so
        # the two are MERGED by pathway_number.
        enriched = {r["pathway_number"]: r for r in rankings}
        served = []
        for row in result.rankings:
            extra = enriched.get(row["pathway_number"], {})
            served.append({
                **row,
                "rationale_summary": extra.get("rationale_summary"),
                "rule_checks": extra.get("rule_checks") or [],
                "capacity_detail": capacity_detail.get(row["pathway_number"]),
            })
        with_checks = sum(1 for r in served if r["rule_checks"])
        logger.info("merged rationale + rule_checks onto %d of %d placements",
                    with_checks, len(served))

        store.put_decision(hosp, as_of, {
            "decision_id": decision_id, "run_id": rid,
            "hospital_hipe": hosp, "as_of_date": as_of,
            "alpha": head["alpha"], "scarcity": head["scarcity"],
            "capacity_direction": CAPACITY_DIRECTION,
            "rule_order_passed": order_ok, "rule_tiebreak_passed": tiebreak_ok,
            "rankings": served, "excluded": result.excluded,
            "refused_paediatric": sorted(u.refused_paediatric),
            "skipped": sorted(u.skipped), "news2": news2,
            "built_at": _now(),
        })
        store.update(rid, ranked=len(result.rankings), excluded=len(result.excluded),
                     alpha=head["alpha"], scarcity=head["scarcity"], decision_id=decision_id)

        code, _ = post_decision(payload, base_url=base_url, token=token)
        outcome = interpret_decision_response(code)
        logger.info("POST /decisions -> %s %s", code, outcome.name)
        store.update(rid, status="done", finished_at=_now())

    except Exception as exc:                                    # noqa: BLE001
        logger.exception("run %s failed", rid)
        store.update(rid, status="failed", error=f"{type(exc).__name__}: {exc}",
                     finished_at=_now())
