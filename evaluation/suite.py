"""Combined local evaluation suite."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass

from .agent_benchmark import BenchmarkReport, run_benchmark
from .kg_audit import KGAuditReport, run_audit
from .rationale_benchmark import RationaleBenchmarkReport, run_rationale_benchmark
from .scenario_benchmark import ScenarioBenchmarkReport, run_scenario_benchmark
from .trace_audit import TraceAuditReport, run_trace_audit


@dataclass(frozen=True)
class EvaluationSuiteReport:
    agent_benchmark: BenchmarkReport
    scenario_benchmark: ScenarioBenchmarkReport
    kg_audit: KGAuditReport
    rationale_benchmark: RationaleBenchmarkReport
    trace_audit: TraceAuditReport

    @property
    def passed(self) -> bool:
        return (
            self.agent_benchmark.passed
            and self.scenario_benchmark.passed
            and self.kg_audit.passed
            and self.rationale_benchmark.passed
            and self.trace_audit.passed
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "agent_benchmark": self.agent_benchmark.to_dict(),
            "scenario_benchmark": self.scenario_benchmark.to_dict(),
            "kg_audit": self.kg_audit.to_dict(),
            "rationale_benchmark": self.rationale_benchmark.to_dict(),
            "trace_audit": self.trace_audit.to_dict(),
        }

    def render_text(self) -> str:
        return "\n\n".join(
            [
                "Evaluation Suite",
                f"Overall: {'PASS' if self.passed else 'FAIL'}",
                self.agent_benchmark.render_text(),
                self.scenario_benchmark.render_text(),
                self.kg_audit.render_text(),
                self.rationale_benchmark.render_text(),
                self.trace_audit.render_text(),
            ]
        )


def run_suite() -> EvaluationSuiteReport:
    return EvaluationSuiteReport(
        agent_benchmark=run_benchmark(),
        scenario_benchmark=run_scenario_benchmark(),
        kg_audit=run_audit(),
        rationale_benchmark=run_rationale_benchmark(),
        trace_audit=run_trace_audit(),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run agent benchmark, scenario benchmark, KG audit, "
            "rationale benchmark and trace audit together."
        )
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = run_suite()
    if args.format == "json":
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(report.render_text())
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
