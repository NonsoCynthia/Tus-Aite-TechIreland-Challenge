"""Benchmark-aware rationale explanation evaluation."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from typing import Literal

from rationale.models import EvidenceItem, EvidencePack, Rationale

from .rationale_judge import JudgeEngine, RationaleJudgeReport, judge_rationale

_DEFAULT_MODEL = "gpt-4.1-mini"


@dataclass(frozen=True)
class RationaleBenchmarkCase:
    case_id: str
    expected_outcome: str
    required_terms: tuple[str, ...]
    pack: EvidencePack
    rationale: Rationale


@dataclass(frozen=True)
class RationaleCaseResult:
    case_id: str
    expected_outcome: str
    applicable_roles: tuple[str, ...]
    required_terms_present: bool
    judge_passed: bool
    passed: bool
    judge_report: RationaleJudgeReport

    def to_dict(self) -> dict[str, object]:
        return {
            "case_id": self.case_id,
            "expected_outcome": self.expected_outcome,
            "applicable_roles": self.applicable_roles,
            "required_terms_present": self.required_terms_present,
            "judge_passed": self.judge_passed,
            "passed": self.passed,
            "judge_report": self.judge_report.to_dict(),
        }


@dataclass(frozen=True)
class RationaleMetricSummary:
    metric: str
    passed: int
    total: int
    value: str


@dataclass(frozen=True)
class RationaleBenchmarkReport:
    engine: JudgeEngine
    case_results: tuple[RationaleCaseResult, ...]

    @property
    def passed(self) -> bool:
        return all(result.passed for result in self.case_results)

    @property
    def passed_count(self) -> int:
        return sum(result.passed for result in self.case_results)

    @property
    def failed_count(self) -> int:
        return len(self.case_results) - self.passed_count

    @property
    def metric_summary(self) -> tuple[RationaleMetricSummary, ...]:
        return _metric_summary(self.case_results)

    def to_dict(self) -> dict[str, object]:
        return {
            "engine": self.engine,
            "passed": self.passed,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "metric_summary": [asdict(metric) for metric in self.metric_summary],
            "case_results": [result.to_dict() for result in self.case_results],
        }

    def render_text(self) -> str:
        lines = [
            f"Rationale Benchmark ({self.engine})",
            f"Result: {'PASS' if self.passed else 'FAIL'} "
            f"({self.passed_count}/{len(self.case_results)} cases passed)",
            "",
            "| Case | Expected outcome | Result |",
            "|---|---|---|",
        ]
        for result in self.case_results:
            lines.append(
                f"| {result.case_id} | {result.expected_outcome} | "
                f"{'PASS' if result.passed else 'FAIL'} |"
            )
        lines.extend(
            [
                "",
                "| Metric | Result |",
                "|---|---|",
            ]
        )
        for metric in self.metric_summary:
            lines.append(f"| {metric.metric} | {metric.value} |")
        return "\n".join(lines)


def run_rationale_benchmark(
    *,
    engine: JudgeEngine = "heuristic",
    model: str = _DEFAULT_MODEL,
    api_key: str | None = None,
) -> RationaleBenchmarkReport:
    results: list[RationaleCaseResult] = []
    for case in benchmark_cases():
        judge_report = judge_rationale(
            case.pack,
            case.rationale,
            expected_outcome=case.expected_outcome,
            engine=engine,
            model=model,
            api_key=api_key,
        )
        lowered = case.rationale.text.lower()
        required_terms_present = all(term.lower() in lowered for term in case.required_terms)
        results.append(
            RationaleCaseResult(
                case_id=case.case_id,
                expected_outcome=case.expected_outcome,
                applicable_roles=tuple(sorted({item.role for item in case.pack.evidence})),
                required_terms_present=required_terms_present,
                judge_passed=judge_report.passed,
                passed=required_terms_present and judge_report.passed,
                judge_report=judge_report,
            )
        )
    return RationaleBenchmarkReport(engine=engine, case_results=tuple(results))


def benchmark_cases() -> tuple[RationaleBenchmarkCase, ...]:
    return (
        _high_urgency_case(),
        _capacity_pressure_case(),
        _crt_breach_case(),
        _cpc_ordering_case(),
        _missing_urgency_case(),
        _paediatric_refusal_case(),
    )


def _metric_summary(
    results: tuple[RationaleCaseResult, ...],
) -> tuple[RationaleMetricSummary, ...]:
    outputs = [result.judge_report.output for result in results]
    readability_total = sum(output.readability_score for output in outputs)
    readability_average = readability_total / max(1, len(outputs))
    readable_count = sum(output.readability_score >= 3 for output in outputs)
    return (
        _count_metric(
            "Faithful to evidence",
            sum(output.faithful_to_evidence for output in outputs),
            len(outputs),
        ),
        _count_metric(
            "Unsupported claims absent",
            sum(not output.unsupported_claims for output in outputs),
            len(outputs),
        ),
        _count_metric(
            "Diagnostic language avoided",
            sum(not output.diagnostic_language for output in outputs),
            len(outputs),
        ),
        _count_metric(
            "System-action language avoided",
            sum(not output.system_action_language for output in outputs),
            len(outputs),
        ),
        _role_metric(results, "urgency", "Urgency evidence mentioned when applicable"),
        _role_metric(results, "capacity", "Capacity evidence mentioned when applicable"),
        _timeframe_metric(results),
        RationaleMetricSummary(
            metric="Average readability",
            passed=readable_count,
            total=len(outputs),
            value=f"{readability_average:.1f}/5 ({readable_count}/{len(outputs)} >= 3)",
        ),
        _count_metric(
            "Required benchmark terms present",
            sum(result.required_terms_present for result in results),
            len(results),
        ),
    )


def _count_metric(metric: str, passed: int, total: int) -> RationaleMetricSummary:
    return RationaleMetricSummary(
        metric=metric,
        passed=passed,
        total=total,
        value=f"{passed}/{total} PASS",
    )


def _role_metric(
    results: tuple[RationaleCaseResult, ...], role: str, metric: str
) -> RationaleMetricSummary:
    applicable = [
        result for result in results if role in result.applicable_roles
    ]
    return _count_metric(
        metric,
        sum(_role_mentioned(result, role) for result in applicable),
        len(applicable),
    )


def _timeframe_metric(results: tuple[RationaleCaseResult, ...]) -> RationaleMetricSummary:
    applicable = [
        result
        for result in results
        if "timeframe" in result.applicable_roles
    ]
    return _count_metric(
        "CPC/CRT evidence mentioned when applicable",
        sum(result.judge_report.output.mentions_cpc_crt_status for result in applicable),
        len(applicable),
    )


def _role_mentioned(result: RationaleCaseResult, role: str) -> bool:
    if role == "urgency":
        return result.judge_report.output.mentions_urgency_evidence
    if role == "capacity":
        return result.judge_report.output.mentions_capacity_evidence
    raise ValueError(f"unsupported role: {role}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Judge rationale explanations tied to benchmark outcomes."
    )
    parser.add_argument("--engine", choices=("heuristic", "llm"), default="heuristic")
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", _DEFAULT_MODEL))
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = run_rationale_benchmark(
        engine=args.engine,
        model=args.model,
        api_key=os.getenv("OPENAI_API_KEY"),
    )
    if args.format == "json":
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(report.render_text())
    return 0 if report.passed else 1


def _high_urgency_case() -> RationaleBenchmarkCase:
    pack = _pack(
        "PW-RAT-001",
        (
            _item("urgency", "score/run-bench/PW-RAT-001/urgency", "Score", scoreValue="1.000"),
            _item("urgency", "obs/PW-RAT-001/rr", "Observation", rr="25", news2="17"),
        ),
    )
    rationale = _rationale(
        pack,
        "Referral PW-RAT-001 has urgency score 1.000, supported by NEWS2 17 and respiratory rate 25. This is decision support; clinician sign-off is required.",
    )
    return RationaleBenchmarkCase(
        case_id="high_urgency",
        expected_outcome="High NEWS2 benchmark case should explain high urgency and cited observation evidence.",
        required_terms=("urgency", "1.000", "NEWS2", "25"),
        pack=pack,
        rationale=rationale,
    )


def _capacity_pressure_case() -> RationaleBenchmarkCase:
    pack = _pack(
        "PW-RAT-002",
        (
            _item("capacity", "bed-status/PW-RAT-002/W01", "BedStatus", occupancyPct="100.0", freeBeds="0"),
            _item("capacity", "clinic-session/PW-RAT-002/CL01", "ClinicSession", slotsTotal="10", slotsBooked="10"),
        ),
    )
    rationale = _rationale(
        pack,
        "Referral PW-RAT-002 has capacity pressure evidence: the ward was 100.0 percent occupied with 0 beds free, and the clinic session had 10 of 10 slots booked.",
    )
    return RationaleBenchmarkCase(
        case_id="capacity_pressure",
        expected_outcome="Capacity benchmark case should explain high ward and clinic pressure.",
        required_terms=("capacity", "100.0", "0 beds", "10 of 10"),
        pack=pack,
        rationale=rationale,
    )


def _crt_breach_case() -> RationaleBenchmarkCase:
    pack = _pack(
        "PW-RAT-003",
        (
            _item("timeframe", "referral-state/PW-RAT-003", "ReferralState", adjustedWaitDays="45", triageStatus="triaged"),
            _item("timeframe", "rule/RULE-CRT-URGENT", "Rule", thresholdDays="28", statement="Urgent referrals should be seen within 28 days"),
        ),
    )
    rationale = _rationale(
        pack,
        "Referral PW-RAT-003 is outside the urgent CRT: adjusted wait is 45 days against the 28 day urgent timeframe rule.",
    )
    return RationaleBenchmarkCase(
        case_id="crt_breach",
        expected_outcome="CRT benchmark case should explain wait days and applicable urgent rule.",
        required_terms=("CRT", "45", "28", "urgent"),
        pack=pack,
        rationale=rationale,
    )


def _cpc_ordering_case() -> RationaleBenchmarkCase:
    pack = _pack(
        "PW-RAT-004",
        (
            _item("timeframe", "rule/RULE-ORDER", "Rule", statement="Urgent CPC ranks ahead of semi-urgent CPC"),
            _item("urgency", "score/run-bench/PW-RAT-004/urgency", "Score", scoreValue="0.200"),
        ),
    )
    rationale = _rationale(
        pack,
        "Referral PW-RAT-004 remains ahead because the urgent CPC band is non-compensatory; the lower urgency score 0.200 does not move it below a semi-urgent referral.",
    )
    return RationaleBenchmarkCase(
        case_id="cpc_ordering",
        expected_outcome="Coordinator benchmark case should explain CPC non-compensation.",
        required_terms=("urgent CPC", "non-compensatory", "0.200"),
        pack=pack,
        rationale=rationale,
    )


def _missing_urgency_case() -> RationaleBenchmarkCase:
    pack = _pack(
        "PW-RAT-005",
        (
            _item("urgency", "benchmark/PW-RAT-005/missing-urgency", "BenchmarkExpectation", reason="missing observation", outcome="excluded"),
        ),
    )
    rationale = _rationale(
        pack,
        "Referral PW-RAT-005 was excluded from ranking because urgency evidence is missing due to a missing observation; this is not treated as low urgency.",
    )
    return RationaleBenchmarkCase(
        case_id="missing_urgency",
        expected_outcome="Missing urgency benchmark case should explain exclusion, not low urgency.",
        required_terms=("excluded", "missing observation", "not treated as low urgency"),
        pack=pack,
        rationale=rationale,
    )


def _paediatric_refusal_case() -> RationaleBenchmarkCase:
    pack = _pack(
        "PW-RAT-006",
        (
            _item("urgency", "benchmark/PW-RAT-006/paediatric", "BenchmarkExpectation", specialty="0601", outcome="refused"),
        ),
    )
    rationale = _rationale(
        pack,
        "Referral PW-RAT-006 was refused by the urgency scorer because specialty 0601 is paediatric and NEWS2 is not used for this scope.",
    )
    return RationaleBenchmarkCase(
        case_id="paediatric_refusal",
        expected_outcome="Paediatric benchmark case should explain the scoped NEWS2 refusal.",
        required_terms=("refused", "0601", "paediatric", "NEWS2"),
        pack=pack,
        rationale=rationale,
    )


def _pack(pathway_number: str, evidence: tuple[EvidenceItem, ...]) -> EvidencePack:
    return EvidencePack(
        decision="decision/benchmark",
        placement=f"placement/benchmark/{pathway_number}",
        position=1,
        referral=f"referral/benchmark/{pathway_number}",
        pathway_number=pathway_number,
        evidence=evidence,
    )


def _item(role: str, iri: str, type_: str, **properties: str) -> EvidenceItem:
    return EvidenceItem(role=role, iri=iri, type=type_, properties=properties)


def _rationale(pack: EvidencePack, text: str) -> Rationale:
    return Rationale(
        pathway_number=pack.pathway_number,
        text=text,
        citation_iris=tuple(item.iri for item in pack.evidence),
    )


if __name__ == "__main__":
    raise SystemExit(main())
