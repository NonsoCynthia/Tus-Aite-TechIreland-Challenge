"""Trace audit checks for agent outputs.

The benchmark checks final scoring/ranking behaviour. This module checks the
trace around those outputs: score provenance, decision/run alignment,
citations, rule checks, safe rationale summaries, and missing-evidence
handling. It is deterministic and database-free, but it uses the same
coordinator builders and retrieval write schemas as the live path.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from typing import Any, Callable

from coordinator.app.citations import ROLE_EVIDENCE_TYPES, applicable_rule_id
from coordinator.app.decision import build_coordinator_version, build_decision, build_ranking
from coordinator.app.ranking import rank_cohort
from coordinator.app.rule_checks import check_order, check_tiebreak
from retrieval.app.schemas import DecisionIn, ScoreIn

RUN_ID = "run-trace-benchmark-001"
HOSPITAL = "9001"
AS_OF_DATE = "2026-08-30"


@dataclass(frozen=True)
class TraceAuditCheck:
    area: str
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class TraceAuditReport:
    checks: tuple[TraceAuditCheck, ...]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    @property
    def passed_count(self) -> int:
        return sum(check.passed for check in self.checks)

    @property
    def failed_count(self) -> int:
        return len(self.checks) - self.passed_count

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "checks": [asdict(check) for check in self.checks],
        }

    def render_text(self) -> str:
        lines = [
            "Trace Audit",
            f"Result: {'PASS' if self.passed else 'FAIL'} "
            f"({self.passed_count}/{len(self.checks)} checks passed)",
            "",
        ]
        for check in self.checks:
            status = "PASS" if check.passed else "FAIL"
            lines.append(f"[{status}] {check.area}: {check.name}")
            lines.append(f"  {check.detail}")
        return "\n".join(lines)


@dataclass(frozen=True)
class TraceFixture:
    score_payloads: tuple[dict[str, Any], ...]
    decision_payload: dict[str, Any]
    excluded: tuple[dict[str, Any], ...]


def run_trace_audit() -> TraceAuditReport:
    fixture = _trace_fixture()
    checks = [
        _check(
            "schema",
            "score and decision payloads validate against write contracts",
            lambda: _assert_schema_validation(fixture),
        ),
        _check(
            "provenance",
            "score traces carry run, method, version and evidence citations",
            lambda: _assert_score_provenance(fixture),
        ),
        _check(
            "provenance",
            "decision trace aligns with score run and coordinator settings",
            lambda: _assert_decision_alignment(fixture),
        ),
        _check(
            "ordering",
            "ranked placements are contiguous and deterministic",
            lambda: _assert_positions_and_order(fixture),
        ),
        _check(
            "safety",
            "missing urgency is excluded rather than ranked",
            lambda: _assert_missing_urgency_exclusion(fixture),
        ),
        _check(
            "citations",
            "placement citations resolve to expected score, state, rule and capacity evidence",
            lambda: _assert_citation_integrity(fixture),
        ),
        _check(
            "rules",
            "rule checks include applicable CRT/turnaround and list-order rules",
            lambda: _assert_rule_trace(fixture),
        ),
        _check(
            "rationale",
            "rationale summaries stay tied to trace evidence and avoid action language",
            lambda: _assert_rationale_trace(fixture),
        ),
    ]
    return TraceAuditReport(tuple(checks))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit deterministic agent traces for provenance, citations and rule evidence."
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = run_trace_audit()
    if args.format == "json":
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(report.render_text())
    return 0 if report.passed else 1


def _check(area: str, name: str, assertion: Callable[[], str]) -> TraceAuditCheck:
    try:
        detail = assertion()
    except AssertionError as exc:
        return TraceAuditCheck(area=area, name=name, passed=False, detail=str(exc))
    except Exception as exc:  # pragma: no cover - defensive CLI reporting.
        return TraceAuditCheck(
            area=area,
            name=name,
            passed=False,
            detail=f"{type(exc).__name__}: {exc}",
        )
    return TraceAuditCheck(area=area, name=name, passed=True, detail=detail)


def _trace_fixture() -> TraceFixture:
    source_referrals = [
        _referral(
            "PW-TRACE-001",
            cpc=1,
            crt_breached=True,
            adjusted_wait_days=45,
            urgency_score=0.9,
            capacity_score=0.8,
            referral_date="2026-07-01",
        ),
        _referral(
            "PW-TRACE-002",
            cpc=1,
            crt_breached=False,
            adjusted_wait_days=10,
            urgency_score=0.4,
            capacity_score=0.8,
            referral_date="2026-07-02",
        ),
        _referral(
            "PW-TRACE-003",
            cpc=3,
            crt_breached=True,
            adjusted_wait_days=100,
            crt_threshold_days=91,
            urgency_score=0.95,
            capacity_score=0.4,
            referral_date="2026-06-15",
        ),
        _referral(
            "PW-TRACE-004",
            cpc=1,
            crt_breached=True,
            adjusted_wait_days=60,
            urgency_score=None,
            capacity_score=0.8,
            referral_date="2026-06-01",
        ),
    ]
    cohort = rank_cohort(
        source_referrals,
        capacity_direction="pressure",
        alpha_min=0.35,
        alpha_max=0.75,
    )
    order_passed = check_order(cohort.rankings)
    tiebreak_passed = check_tiebreak(cohort.rankings)
    rankings = [
        build_ranking(
            referral,
            order_passed=order_passed,
            tiebreak_passed=tiebreak_passed,
        )
        for referral in cohort.rankings
    ]
    decision_payload = build_decision(
        decision_id="decision-trace-benchmark-001",
        run_id=RUN_ID,
        hospital_hipe=HOSPITAL,
        as_of_date=AS_OF_DATE,
        coordinator_version=build_coordinator_version(
            semantic_version="trace-benchmark-v1",
            capacity_direction="pressure",
            alpha_min=0.35,
            alpha_max=0.75,
            score_source="synthetic-trace-fixture",
        ),
        rankings=rankings,
    )
    return TraceFixture(
        score_payloads=tuple(
            payload
            for referral in cohort.rankings
            for payload in (_score_payloads_for(referral), _capacity_payloads_for(referral))
        ),
        decision_payload=decision_payload,
        excluded=tuple(cohort.excluded),
    )


def _score_payloads_for(referral: dict[str, Any]) -> dict[str, Any]:
    observation_key = (
        f"{HOSPITAL}/{referral['pathway_number']}/2026-08-30T08%3A00%3A00/hr"
    )
    return {
        "run_id": RUN_ID,
        "agent_name": "urgency",
        "hospital_hipe": HOSPITAL,
        "pathway_number": referral["pathway_number"],
        "as_of_date": AS_OF_DATE,
        "score": referral["urgency_score"],
        "method": "news2-benchmark-v1",
        "agent_version": "urgency-trace-v1",
        "citations": [
            {
                "evidence_type": "observation",
                "evidence_key": observation_key,
            }
        ],
    }


def _capacity_payloads_for(referral: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": RUN_ID,
        "agent_name": "capacity",
        "hospital_hipe": HOSPITAL,
        "pathway_number": referral["pathway_number"],
        "as_of_date": AS_OF_DATE,
        "score": referral["capacity_score"],
        "method": "capacity-pressure-benchmark-v1",
        "agent_version": "capacity-trace-v1",
        "citations": [
            {
                "evidence_type": "bed_status",
                "evidence_key": f"{HOSPITAL}/W01/2026-08-30T08%3A00%3A00",
            }
        ],
    }


def _referral(pathway_number: str, **overrides: object) -> dict[str, Any]:
    referral = {
        "run_id": RUN_ID,
        "hospital_hipe": HOSPITAL,
        "pathway_number": pathway_number,
        "specialty_hipe": "0100",
        "cpc": 1,
        "crt_breached": False,
        "triage_status": "triaged",
        "adjusted_wait_days": 10,
        "crt_threshold_days": 28,
        "days_awaiting_triage": None,
        "referral_date": "2026-07-01",
        "referral_state_valid_from": "2026-08-01",
        "urgency_score": 0.5,
        "capacity_score": 0.5,
        "urgency_citations": [
            {
                "evidence_type": "observation",
                "evidence_key": f"{HOSPITAL}/{pathway_number}/2026-08-30T08%3A00%3A00/hr",
            }
        ],
        "capacity_citations": [
            {
                "evidence_type": "bed_status",
                "evidence_key": f"{HOSPITAL}/W01/2026-08-30T08%3A00%3A00",
            }
        ],
    }
    referral.update(overrides)
    return referral


def _assert_schema_validation(fixture: TraceFixture) -> str:
    for score_payload in fixture.score_payloads:
        ScoreIn(**score_payload)
    DecisionIn(**fixture.decision_payload)
    return f"{len(fixture.score_payloads)} scores and 1 decision validate"


def _assert_score_provenance(fixture: TraceFixture) -> str:
    for payload in fixture.score_payloads:
        assert payload["run_id"] == RUN_ID, payload
        assert payload["method"], payload
        assert payload["agent_version"], payload
        assert 0.0 <= payload["score"] <= 1.0, payload
        assert payload["citations"], payload
    return "every score has run_id, method, version, bounded score and citations"


def _assert_decision_alignment(fixture: TraceFixture) -> str:
    decision = fixture.decision_payload
    assert decision["run_id"] == RUN_ID, decision["run_id"]
    version = decision["coordinator_version"]
    expected_tokens = (
        "trace-benchmark-v1",
        "capacity=pressure",
        "alpha=[0.35,0.75]",
        "scores=synthetic-trace-fixture",
    )
    for token in expected_tokens:
        assert token in version, version
    scored = {
        (payload["agent_name"], payload["pathway_number"])
        for payload in fixture.score_payloads
    }
    for ranking in decision["rankings"]:
        pathway = ranking["pathway_number"]
        assert ("urgency", pathway) in scored, pathway
        assert ("capacity", pathway) in scored, pathway
    return "decision run/version align with urgency and capacity score traces"


def _assert_positions_and_order(fixture: TraceFixture) -> str:
    rankings = fixture.decision_payload["rankings"]
    positions = [ranking["position"] for ranking in rankings]
    assert positions == list(range(1, len(rankings) + 1)), positions
    order = [ranking["pathway_number"] for ranking in rankings]
    assert order == ["PW-TRACE-001", "PW-TRACE-002", "PW-TRACE-003"], order
    return "positions are contiguous and respect CPC/CRT ordering"


def _assert_missing_urgency_exclusion(fixture: TraceFixture) -> str:
    ranked = {ranking["pathway_number"] for ranking in fixture.decision_payload["rankings"]}
    excluded = {referral["pathway_number"]: referral for referral in fixture.excluded}
    assert "PW-TRACE-004" not in ranked, ranked
    assert excluded["PW-TRACE-004"]["exclusion_reason"] == "missing_urgency_score", excluded
    return "missing urgency trace is excluded with explicit reason"


def _assert_citation_integrity(fixture: TraceFixture) -> str:
    score_keys = {_score_key(payload) for payload in fixture.score_payloads}
    for ranking in fixture.decision_payload["rankings"]:
        citations = ranking["citations"]
        by_role: dict[str, list[dict[str, Any]]] = {}
        for citation in citations:
            by_role.setdefault(citation["role"], []).append(citation)
            assert citation["evidence_type"] in ROLE_EVIDENCE_TYPES[citation["role"]], citation
        expected_score_key = f"{RUN_ID}/{HOSPITAL}/{ranking['pathway_number']}/urgency"
        assert any(
            citation["evidence_type"] == "score"
            and citation["evidence_key"] == expected_score_key
            for citation in by_role.get("urgency", [])
        ), ranking
        assert expected_score_key in score_keys, expected_score_key
        assert by_role.get("capacity"), ranking
        assert any(
            citation["evidence_type"] == "referral_state"
            for citation in by_role.get("timeframe", [])
        ), ranking
        rule_id = _rule_id_for(ranking["pathway_number"])
        if rule_id is not None:
            assert any(
                citation["evidence_type"] == "rule" and citation["evidence_key"] == rule_id
                for citation in by_role.get("timeframe", [])
            ), ranking
    return "all ranked placements cite score, capacity, referral-state and applicable rule evidence"


def _score_key(payload: dict[str, Any]) -> str:
    return (
        f"{payload['run_id']}/{payload['hospital_hipe']}/"
        f"{payload['pathway_number']}/{payload['agent_name']}"
    )


def _assert_rule_trace(fixture: TraceFixture) -> str:
    for ranking in fixture.decision_payload["rankings"]:
        rule_ids = {check["rule_id"] for check in ranking["rule_checks"]}
        assert {"RULE-ORDER", "RULE-TIEBREAK"}.issubset(rule_ids), rule_ids
        expected_rule = _rule_id_for(ranking["pathway_number"])
        if expected_rule is not None:
            assert expected_rule in rule_ids, (ranking["pathway_number"], rule_ids)
    return "rule checks include list-level and referral-level applicable rules"


def _assert_rationale_trace(fixture: TraceFixture) -> str:
    unsafe = ("admitted", "scheduled", "approved", "decided care", "diagnosed")
    for ranking in fixture.decision_payload["rankings"]:
        text = ranking["rationale_summary"].lower()
        assert "urgency score" in text, ranking["rationale_summary"]
        assert "capacity score" in text, ranking["rationale_summary"]
        assert "crt window" in text, ranking["rationale_summary"]
        assert not any(term in text for term in unsafe), ranking["rationale_summary"]
    return "rationale summaries cite score context and avoid clinical-action wording"


def _rule_id_for(pathway_number: str) -> str | None:
    lookup = {
        "PW-TRACE-001": {"cpc": 1, "triage_status": "triaged"},
        "PW-TRACE-002": {"cpc": 1, "triage_status": "triaged"},
        "PW-TRACE-003": {"cpc": 3, "triage_status": "triaged"},
    }
    return applicable_rule_id(lookup[pathway_number])


if __name__ == "__main__":
    raise SystemExit(main())
