from pathlib import Path

import pytest

from evaluation.rationale_judge import JudgeOutput, judge_rationale, load_judge_case
from rationale.models import Rationale


_FIXTURE = Path("evaluation/fixtures/rationale_judge_sample.json")


def test_heuristic_judge_passes_grounded_sample() -> None:
    pack, rationale = load_judge_case(_FIXTURE)

    report = judge_rationale(pack, rationale)

    assert report.passed
    assert report.output.faithful_to_evidence
    assert report.output.mentions_urgency_evidence
    assert report.output.mentions_capacity_evidence
    assert report.output.mentions_cpc_crt_status


def test_heuristic_judge_flags_unsupported_numeric_claim() -> None:
    pack, rationale = load_judge_case(_FIXTURE)
    bad = Rationale(
        pathway_number=rationale.pathway_number,
        text=f"{rationale.text} The ward had 999 beds free.",
        citation_iris=rationale.citation_iris,
    )

    report = judge_rationale(pack, bad)

    assert not report.passed
    assert any("999" in claim for claim in report.output.unsupported_claims)


def test_llm_judge_uses_injected_runner_without_network() -> None:
    pack, rationale = load_judge_case(_FIXTURE)
    calls: list[dict[str, str]] = []

    def runner(*, instructions: str, prompt: str, model: str, api_key: str) -> JudgeOutput:
        calls.append(
            {
                "instructions": instructions,
                "prompt": prompt,
                "model": model,
                "api_key": api_key,
            }
        )
        return JudgeOutput(
            faithful_to_evidence=True,
            unsupported_claims=[],
            diagnostic_language=False,
            system_action_language=False,
            mentions_urgency_evidence=True,
            mentions_capacity_evidence=True,
            mentions_cpc_crt_status=True,
            readability_score=5,
            explanation="Grounded and readable.",
        )

    report = judge_rationale(
        pack,
        rationale,
        engine="llm",
        model="judge-model",
        api_key="sk-test",
        runner=runner,
    )

    assert report.passed
    assert calls[0]["model"] == "judge-model"
    assert "evidence_pack" in calls[0]["prompt"]
    assert rationale.text in calls[0]["prompt"]


def test_llm_judge_requires_api_key() -> None:
    pack, rationale = load_judge_case(_FIXTURE)

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        judge_rationale(pack, rationale, engine="llm", api_key=None)
