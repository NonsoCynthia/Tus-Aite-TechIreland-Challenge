"""Judge rationale explanations against their cited evidence.

The deterministic agent/KG checks prove the system computed and cited evidence
correctly. This module evaluates the explanation surface: whether a rationale
is faithful to the evidence pack, avoids unsafe clinical language, and remains
readable. It supports a local heuristic mode for repeatable checks and an
optional LLM judge for qualitative review.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from rationale.models import EvidenceItem, EvidencePack, Rationale

JudgeEngine = Literal["heuristic", "llm"]

_DEFAULT_MODEL = "gpt-4.1-mini"
_DIAGNOSTIC_TERMS = (
    "diagnose",
    "diagnosed",
    "diagnosis",
    "likely sepsis",
    "likely cancer",
    "has sepsis",
    "has cancer",
)
_SYSTEM_ACTION_TERMS = (
    "we admitted",
    "we scheduled",
    "we approved",
    "we triaged",
    "the system admitted",
    "the system scheduled",
    "the system approved",
    "the system decided",
    "should be admitted",
)


class JudgeOutput(BaseModel):
    faithful_to_evidence: bool
    unsupported_claims: list[str] = Field(default_factory=list)
    diagnostic_language: bool
    system_action_language: bool
    mentions_urgency_evidence: bool
    mentions_capacity_evidence: bool
    mentions_cpc_crt_status: bool
    readability_score: int = Field(ge=1, le=5)
    explanation: str

    @property
    def passed(self) -> bool:
        return (
            self.faithful_to_evidence
            and not self.unsupported_claims
            and not self.diagnostic_language
            and not self.system_action_language
            and self.mentions_urgency_evidence
            and self.mentions_capacity_evidence
            and self.mentions_cpc_crt_status
            and self.readability_score >= 3
        )


@dataclass(frozen=True)
class RationaleJudgeReport:
    pathway_number: str
    engine: JudgeEngine
    output: JudgeOutput

    @property
    def passed(self) -> bool:
        return self.output.passed

    def to_dict(self) -> dict[str, Any]:
        return {
            "pathway_number": self.pathway_number,
            "engine": self.engine,
            "passed": self.passed,
            "output": self.output.model_dump(),
        }

    def render_text(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        lines = [
            f"Rationale Judge ({self.engine})",
            f"Result: {status}",
            f"Pathway: {self.pathway_number}",
            "",
            "| Metric | Result |",
            "|---|---|",
            f"| Faithful to cited evidence | {_result(self.output.faithful_to_evidence)} |",
            f"| Unsupported claims | {len(self.output.unsupported_claims)} |",
            f"| Diagnostic language | {_result(not self.output.diagnostic_language)} |",
            f"| System action language | {_result(not self.output.system_action_language)} |",
            f"| Mentions urgency evidence | {_result(self.output.mentions_urgency_evidence)} |",
            f"| Mentions capacity evidence | {_result(self.output.mentions_capacity_evidence)} |",
            f"| Mentions CPC/CRT status | {_result(self.output.mentions_cpc_crt_status)} |",
            f"| Readability score | {self.output.readability_score}/5 |",
            "",
            self.output.explanation,
        ]
        if self.output.unsupported_claims:
            lines.append("")
            lines.append("Unsupported claims:")
            lines.extend(f"- {claim}" for claim in self.output.unsupported_claims)
        return "\n".join(lines)


class JudgeRunner(Protocol):
    def __call__(self, *, instructions: str, prompt: str, model: str, api_key: str) -> JudgeOutput:
        ...


_INSTRUCTIONS = """
You are an evaluator for a graph-backed clinical decision-support rationale.

You will receive:
1. An evidence pack containing cited graph evidence for one ranked referral.
2. A rationale text generated from that evidence.

Judge only the rationale text against the supplied evidence. Do not judge the
clinical correctness of the underlying referral, score, or ranking.

Return structured output with:
- faithful_to_evidence: true only if every substantive claim in the rationale
  is supported by the evidence pack.
- unsupported_claims: exact short descriptions of claims not supported by the
  evidence pack.
- diagnostic_language: true if the text states or implies a diagnosis.
- system_action_language: true if the text implies the system admitted,
  scheduled, approved, triaged, or decided care.
- mentions_urgency_evidence: true if it names urgency score/signals or clearly
  states urgency evidence was used.
- mentions_capacity_evidence: true if it names capacity/bed/clinic evidence.
- mentions_cpc_crt_status: true if it names CPC, CRT, timeframe, or referral
  state evidence.
- readability_score: 1 poor, 5 excellent for a time-pressured clinician.

Be strict about unsupported facts, but do not require exact wording.
""".strip()


def judge_rationale(
    pack: EvidencePack,
    rationale: Rationale,
    *,
    expected_outcome: str | None = None,
    engine: JudgeEngine = "heuristic",
    model: str = _DEFAULT_MODEL,
    api_key: str | None = None,
    runner: JudgeRunner | None = None,
) -> RationaleJudgeReport:
    if engine == "heuristic":
        output = _heuristic_judge(pack, rationale)
    else:
        output = _llm_judge(
            pack,
            rationale,
            expected_outcome=expected_outcome,
            model=model,
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            runner=runner or _default_runner,
        )
    return RationaleJudgeReport(
        pathway_number=rationale.pathway_number,
        engine=engine,
        output=output,
    )


def load_judge_case(path: Path) -> tuple[EvidencePack, Rationale]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    pack = _pack_from_json(raw["evidence_pack"])
    rationale = Rationale(
        pathway_number=str(raw["rationale"]["pathway_number"]),
        text=str(raw["rationale"]["text"]),
        citation_iris=tuple(str(value) for value in raw["rationale"]["citation_iris"]),
    )
    return pack, rationale


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Judge a graph-backed rationale against its cited evidence pack."
    )
    parser.add_argument(
        "--input",
        default="evaluation/fixtures/rationale_judge_sample.json",
        help="JSON file containing evidence_pack and rationale objects.",
    )
    parser.add_argument("--engine", choices=("heuristic", "llm"), default="heuristic")
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL", _DEFAULT_MODEL))
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    pack, rationale = load_judge_case(Path(args.input))
    report = judge_rationale(pack, rationale, engine=args.engine, model=args.model)
    if args.format == "json":
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(report.render_text())
    return 0 if report.passed else 1


def _heuristic_judge(pack: EvidencePack, rationale: Rationale) -> JudgeOutput:
    text = rationale.text
    lowered = text.lower()
    evidence_terms = _evidence_terms(pack)
    unsupported_claims = _unsupported_numeric_claims(text, evidence_terms)

    expected_iris = {item.iri for item in pack.evidence}
    got_iris = set(rationale.citation_iris)
    if got_iris != expected_iris:
        unsupported_claims.append(
            f"citation_iris mismatch: missing={sorted(expected_iris - got_iris)}, "
            f"unexpected={sorted(got_iris - expected_iris)}"
        )

    roles = {item.role for item in pack.evidence}
    mentions_urgency = "urgency" in lowered or any(
        token in lowered for token in ("news2", "score", "oxygen", "heart-rate")
    )
    mentions_capacity = any(
        token in lowered for token in ("capacity", "ward", "bed", "clinic", "slot")
    )
    mentions_timeframe = any(
        token in lowered for token in ("cpc", "crt", "timeframe", "referral state", "triaged")
    )

    diagnostic = any(term in lowered for term in _DIAGNOSTIC_TERMS)
    system_action = any(term in lowered for term in _SYSTEM_ACTION_TERMS)
    readability = _readability_score(text)
    faithful = not unsupported_claims

    return JudgeOutput(
        faithful_to_evidence=faithful,
        unsupported_claims=unsupported_claims,
        diagnostic_language=diagnostic,
        system_action_language=system_action,
        mentions_urgency_evidence=("urgency" not in roles) or mentions_urgency,
        mentions_capacity_evidence=("capacity" not in roles) or mentions_capacity,
        mentions_cpc_crt_status=("timeframe" not in roles) or mentions_timeframe,
        readability_score=readability,
        explanation="Heuristic judge checked citation coverage, unsafe language, evidence-role mentions and unsupported numeric claims.",
    )


def _llm_judge(
    pack: EvidencePack,
    rationale: Rationale,
    *,
    expected_outcome: str | None,
    model: str,
    api_key: str | None,
    runner: JudgeRunner,
) -> JudgeOutput:
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is required for --engine llm")
    prompt = json.dumps(
        {
            "evidence_pack": _pack_to_json(pack),
            "rationale": {
                "pathway_number": rationale.pathway_number,
                "text": rationale.text,
                "citation_iris": list(rationale.citation_iris),
            },
            "expected_benchmark_outcome": expected_outcome,
        },
        indent=2,
    )
    return runner(instructions=_INSTRUCTIONS, prompt=prompt, model=model, api_key=api_key)


def _default_runner(*, instructions: str, prompt: str, model: str, api_key: str) -> JudgeOutput:
    from agents import Agent, Runner, set_default_openai_key  # noqa: PLC0415

    set_default_openai_key(api_key)
    agent = Agent(
        name="rationale-judge",
        instructions=instructions,
        model=model,
        output_type=JudgeOutput,
    )
    result = Runner.run_sync(agent, prompt)
    output = result.final_output
    if not isinstance(output, JudgeOutput):  # pragma: no cover - SDK contract failure
        raise RuntimeError(f"expected JudgeOutput, got {type(output)!r}")
    return output


def _pack_from_json(raw: dict[str, Any]) -> EvidencePack:
    return EvidencePack(
        decision=str(raw["decision"]),
        placement=str(raw["placement"]),
        position=int(raw["position"]) if raw.get("position") is not None else None,
        referral=str(raw.get("referral") or ""),
        pathway_number=str(raw["pathway_number"]),
        evidence=tuple(EvidenceItem.from_json(item) for item in raw.get("evidence", [])),
    )


def _pack_to_json(pack: EvidencePack) -> dict[str, Any]:
    return {
        "decision": pack.decision,
        "placement": pack.placement,
        "position": pack.position,
        "referral": pack.referral,
        "pathway_number": pack.pathway_number,
        "evidence": [
            {
                "role": item.role,
                "iri": item.iri,
                "type": item.type,
                "properties": item.properties,
            }
            for item in pack.evidence
        ],
    }


def _evidence_terms(pack: EvidencePack) -> set[str]:
    terms = {pack.pathway_number.lower()}
    if pack.position is not None:
        terms.add(str(pack.position))
    for item in pack.evidence:
        terms.add(item.iri.lower())
        if item.type:
            terms.add(item.type.lower())
        terms.add(item.role.lower())
        for key, value in item.properties.items():
            value_text = str(value).lower()
            terms.add(str(key).lower())
            terms.add(value_text)
            terms.update(re.findall(r"\b\d+(?:\.\d+)?\b", value_text))
    return terms


def _unsupported_numeric_claims(text: str, evidence_terms: set[str]) -> list[str]:
    claims: list[str] = []
    numeric_claims = re.findall(r"(?<![A-Za-z0-9-])\d+(?:\.\d+)?(?![A-Za-z0-9-])", text)
    for value in numeric_claims:
        if value in {"0", "1"} and "0 to 1 scale" in text.lower():
            continue
        if value.lower() in evidence_terms:
            continue
        if f"{float(value):.3f}" in evidence_terms:
            continue
        claims.append(f"numeric value {value!r} not found in evidence properties")
    return claims


def _readability_score(text: str) -> int:
    words = re.findall(r"\b\w+\b", text)
    sentences = [s for s in re.split(r"[.!?]+", text) if s.strip()]
    if not words:
        return 1
    avg_sentence = len(words) / max(1, len(sentences))
    if len(words) <= 120 and avg_sentence <= 24:
        return 5
    if len(words) <= 180 and avg_sentence <= 30:
        return 4
    if len(words) <= 240 and avg_sentence <= 36:
        return 3
    if len(words) <= 320:
        return 2
    return 1


def _result(value: bool) -> str:
    return "PASS" if value else "FAIL"


if __name__ == "__main__":
    raise SystemExit(main())
