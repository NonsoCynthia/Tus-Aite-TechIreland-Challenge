"""llm_render.py tests: the guardrail/retry logic, exercised entirely
through an injected fake `AgentRunner` -- no `agents` package, no network,
no API key needed. The one thing NOT covered here is `_default_agent_runner`
itself (the real OpenAI Agents SDK call, deliberately excluded from
coverage -- see its own `# pragma: no cover` markers); that needs a live
key and is a manual/integration verification, documented in README.md.
"""

from __future__ import annotations

import pytest

from rationale.config import Settings
from rationale.llm_render import (
    LLMRationaleOutput,
    RationaleGuardrailError,
    render_many_llm,
    render_rationale_llm,
)
from rationale.models import EvidenceItem, EvidencePack


def _settings(*, openai_api_key: str | None = "sk-test-key") -> Settings:
    return Settings(
        retrieval_base_url="http://retrieval.test",
        bearer_token="tok",
        openai_api_key=openai_api_key,
        openai_model="gpt-4.1-mini",
    )


def _pack(pathway_number: str = "PW-1") -> EvidencePack:
    return EvidencePack(
        decision="decision/9004/2026-08-30",
        placement="placement/9004/2026-08-30/PW-1",
        position=3,
        referral="referral/9004/PW-1",
        pathway_number=pathway_number,
        evidence=(
            EvidenceItem(
                role="urgency",
                iri="score/run-1/9004/PW-1/urgency",
                type="Score",
                properties={"scoreValue": "0.750", "method": "news2-v1"},
            ),
            EvidenceItem(
                role="capacity",
                iri="bed-status/9004/W-1/2026-08-30%2009%3A00%3A00",
                type="BedStatus",
                properties={"occupancyPct": "100.00", "surgeCapacityInUse": "2"},
            ),
        ),
    )


class _FakeRunner:
    """Records every call and returns queued outputs in order, so a test can
    simulate "first attempt hallucinates, second attempt is grounded"."""

    def __init__(self, outputs: list[LLMRationaleOutput]) -> None:
        self._outputs = list(outputs)
        self.calls: list[dict[str, str]] = []

    def __call__(
        self, *, instructions: str, prompt: str, model: str, api_key: str
    ) -> LLMRationaleOutput:
        self.calls.append({"instructions": instructions, "prompt": prompt, "model": model})
        return self._outputs.pop(0)


class TestRenderRationaleLlm:
    def test_happy_path_returns_rationale_matching_full_citation_set(self) -> None:
        pack = _pack()
        expected_iris = [item.iri for item in pack.evidence]
        runner = _FakeRunner(
            [
                LLMRationaleOutput(
                    text="Ranked #3, clinician sign-off required.", citation_iris=expected_iris
                )
            ]
        )

        rationale = render_rationale_llm(
            pack, style="clinician", settings=_settings(), runner=runner
        )

        assert rationale.pathway_number == "PW-1"
        assert rationale.text == "Ranked #3, clinician sign-off required."
        assert set(rationale.citation_iris) == set(expected_iris)
        assert len(runner.calls) == 1

    def test_prompt_carries_style_and_evidence_pack_json(self) -> None:
        pack = _pack()
        expected_iris = [item.iri for item in pack.evidence]
        runner = _FakeRunner([LLMRationaleOutput(text="x", citation_iris=expected_iris)])

        render_rationale_llm(pack, style="technical", settings=_settings(), runner=runner)

        prompt = runner.calls[0]["prompt"]
        assert "style: technical" in prompt
        assert pack.pathway_number in prompt
        assert pack.evidence[0].iri in prompt
        assert pack.evidence[0].properties["scoreValue"] in prompt

    def test_retries_once_on_a_guardrail_failure_then_succeeds(self) -> None:
        pack = _pack()
        expected_iris = [item.iri for item in pack.evidence]
        runner = _FakeRunner(
            [
                LLMRationaleOutput(text="hallucinated", citation_iris=["not/a/real/iri"]),
                LLMRationaleOutput(text="grounded", citation_iris=expected_iris),
            ]
        )

        rationale = render_rationale_llm(
            pack, style="clinician", settings=_settings(), runner=runner
        )

        assert rationale.text == "grounded"
        assert len(runner.calls) == 2

    def test_raises_guardrail_error_after_every_attempt_fails(self) -> None:
        pack = _pack()
        runner = _FakeRunner(
            [
                LLMRationaleOutput(text="a", citation_iris=["wrong/1"]),
                LLMRationaleOutput(text="b", citation_iris=["wrong/2"]),
            ]
        )

        with pytest.raises(RationaleGuardrailError) as exc_info:
            render_rationale_llm(pack, style="clinician", settings=_settings(), runner=runner)

        assert "wrong/2" in str(exc_info.value)
        assert len(runner.calls) == 2

    def test_rejects_a_citation_subset_not_just_wrong_iris(self) -> None:
        # Citing only one of two evidence items is still a guardrail failure
        # -- the contract is "all of them," matching the deterministic
        # renderer, not "at least one."
        pack = _pack()
        one_iri = [pack.evidence[0].iri]
        runner = _FakeRunner(
            [
                LLMRationaleOutput(text="a", citation_iris=one_iri),
                LLMRationaleOutput(text="b", citation_iris=one_iri),
            ]
        )

        with pytest.raises(RationaleGuardrailError) as exc_info:
            render_rationale_llm(pack, style="clinician", settings=_settings(), runner=runner)

        assert "missing=" in str(exc_info.value)

    def test_raises_value_error_for_a_placement_with_no_evidence(self) -> None:
        pack = EvidencePack(
            decision="decision/9004/2026-08-30",
            placement="placement/9004/2026-08-30/PW-2",
            position=1,
            referral="referral/9004/PW-2",
            pathway_number="PW-2",
            evidence=(),
        )
        runner = _FakeRunner([])

        with pytest.raises(ValueError, match="no cited evidence"):
            render_rationale_llm(pack, style="clinician", settings=_settings(), runner=runner)
        assert runner.calls == []

    def test_raises_runtime_error_when_no_api_key_configured(self) -> None:
        pack = _pack()
        runner = _FakeRunner([])

        with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
            render_rationale_llm(
                pack, style="clinician", settings=_settings(openai_api_key=None), runner=runner
            )
        assert runner.calls == []


class TestRenderManyLlm:
    def test_renders_every_pack_independently(self) -> None:
        packs = [_pack("PW-1"), _pack("PW-2")]
        runner = _FakeRunner(
            [
                LLMRationaleOutput(
                    text="one", citation_iris=[item.iri for item in packs[0].evidence]
                ),
                LLMRationaleOutput(
                    text="two", citation_iris=[item.iri for item in packs[1].evidence]
                ),
            ]
        )

        rationales = render_many_llm(packs, style="clinician", settings=_settings(), runner=runner)

        assert [r.pathway_number for r in rationales] == ["PW-1", "PW-2"]
        assert [r.text for r in rationales] == ["one", "two"]
