"""Combined local evaluation suite."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass

from .agent_benchmark import BenchmarkReport, run_benchmark
from .kg_audit import KGAuditReport, run_audit


@dataclass(frozen=True)
class EvaluationSuiteReport:
    agent_benchmark: BenchmarkReport
    kg_audit: KGAuditReport

    @property
    def passed(self) -> bool:
        return self.agent_benchmark.passed and self.kg_audit.passed

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "agent_benchmark": self.agent_benchmark.to_dict(),
            "kg_audit": self.kg_audit.to_dict(),
        }

    def render_text(self) -> str:
        return "\n\n".join(
            [
                "Evaluation Suite",
                f"Overall: {'PASS' if self.passed else 'FAIL'}",
                self.agent_benchmark.render_text(),
                self.kg_audit.render_text(),
            ]
        )


def run_suite() -> EvaluationSuiteReport:
    return EvaluationSuiteReport(agent_benchmark=run_benchmark(), kg_audit=run_audit())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run agent correctness and KG audit evaluations together."
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
