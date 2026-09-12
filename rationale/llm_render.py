"""LLM-backed rationale rendering (spec.md FR4) -- an alternative to
render.py's deterministic renderer, not a replacement for it.

Per this package's own stated boundary (README.md): "the model should
receive the evidence bundle and rewrite it, not decide which evidence
matters." This module holds to that exactly -- the model is handed an
already-resolved `EvidencePack` (built the same way for both engines) and
returns prose. It never calls the retrieval service, never chooses what
evidence to fetch, and never runs before the evidence pack exists.

Built on the OpenAI Agents SDK (`agents`) rather than a bare chat-completions
call so the "agent" here is real infrastructure -- instructions, a
structured `output_type`, a runtime built for tool-calling -- not just a
prompt with a marketing label. This agent's own job is deliberately narrow
(verbalise, don't decide), which is what keeps it compatible with every
ADR this project has already recorded about deterministic, auditable
scoring; the tool-calling capability the SDK provides is for a future,
broader orchestrator (see ADR-010), not exercised here.

Evidence-faithfulness (spec.md NFR4) is enforced in code, not trusted from
instructions alone: the model must return `citation_iris` covering exactly
the evidence pack's own IRIs -- the same contract render.render_rationale
already guarantees by construction. A mismatch raises
`RationaleGuardrailError` rather than being silently accepted; one retry
absorbs a transient formatting slip without papering over a systematic
problem on the second failure.

The actual OpenAI Agents SDK call is isolated behind `AgentRunner` (an
injectable callable) and imported lazily inside `_default_agent_runner` --
so importing this module, and every guardrail/retry test in
tests/test_llm_render.py, never requires the `agents` package or an API key.
Only actually calling `render_rationale_llm` with the default runner does.
"""

from __future__ import annotations

import json
from typing import Protocol

from pydantic import BaseModel

from .config import Settings
from .models import EvidencePack, Rationale
from .render import RenderStyle

_INSTRUCTIONS = """
You are a clinical rationale writer for a hospital triage decision-support system.

You will be given a JSON evidence pack: everything already established about one
ranked referral placement, already resolved from the audit-trail graph. You are
not given, and must not ask for, anything else.

Rules, all non-negotiable:
1. State ONLY facts present in the evidence pack's `properties` fields. Never
   introduce a clinical, numeric, or categorical claim that is not a faithful
   restatement of a supplied property value.
2. If a property needed to explain something is missing or unresolved, say so
   plainly ("this could not be resolved") rather than guessing or omitting it
   silently.
3. This is decision support only. Always make clear a clinician's sign-off is
   required. Never phrase anything as a diagnosis, an admission decision, or an
   instruction to a clinician.
4. Return `citation_iris` listing every evidence item's IRI from the pack --
   all of them, since every item was already cited by the placement itself,
   not a subset you personally chose to mention.

Style:
- "clinician": short, readable prose a clinician can scan in seconds.
- "technical": structured, roughly one line per evidence role, suitable for an
  audit log.
""".strip()


class LLMRationaleOutput(BaseModel):
    text: str
    citation_iris: list[str]


class RationaleGuardrailError(RuntimeError):
    """The model's output failed the evidence-faithfulness check --
    `citation_iris` must equal the evidence pack's own IRI set. Not
    swallowed: a caller wanting a rationale regardless should catch this and
    fall back to `render.render_rationale`, never silently accept ungrounded
    text."""


class AgentRunError(RuntimeError):
    """The underlying OpenAI Agents SDK call itself failed (network, auth,
    malformed structured output) -- distinct from a guardrail failure, which
    means the call succeeded but the content was wrong."""


class AgentRunner(Protocol):
    def __call__(
        self, *, instructions: str, prompt: str, model: str, api_key: str
    ) -> LLMRationaleOutput: ...


def _evidence_pack_json(pack: EvidencePack) -> str:
    return json.dumps(
        {
            "pathway_number": pack.pathway_number,
            "position": pack.position,
            "evidence": [
                {
                    "role": item.role,
                    "iri": item.iri,
                    "type": item.type,
                    "properties": item.properties,
                }
                for item in pack.evidence
            ],
        },
        indent=2,
    )


def _default_agent_runner(
    *, instructions: str, prompt: str, model: str, api_key: str
) -> LLMRationaleOutput:
    """The real OpenAI Agents SDK call. Imported lazily so this module (and
    every guardrail/retry test) never requires the `agents` package unless
    this specific function actually runs."""
    from agents import (  # noqa: PLC0415 (intentionally lazy, see module docstring)
        Agent,
        Runner,
        set_default_openai_key,
    )

    set_default_openai_key(api_key)
    agent = Agent(
        name="rationale-writer",
        instructions=instructions,
        model=model,
        output_type=LLMRationaleOutput,
    )
    try:
        result = Runner.run_sync(agent, prompt)
    except Exception as exc:  # pragma: no cover - real network/SDK failure path
        raise AgentRunError(f"OpenAI Agents SDK call failed: {exc}") from exc

    output = result.final_output
    if not isinstance(output, LLMRationaleOutput):
        raise AgentRunError(  # pragma: no cover - SDK contract violation
            f"expected LLMRationaleOutput, got {type(output)!r}"
        )
    return output


def _validate_citations(pack: EvidencePack, citation_iris: list[str]) -> None:
    expected = {item.iri for item in pack.evidence}
    got = set(citation_iris)
    if got != expected:
        missing = sorted(expected - got)
        unexpected = sorted(got - expected)
        raise RationaleGuardrailError(
            f"{pack.pathway_number}: citation_iris does not match the evidence pack "
            f"(missing={missing}, unexpected={unexpected})"
        )


def render_rationale_llm(
    pack: EvidencePack,
    *,
    style: RenderStyle,
    settings: Settings,
    max_attempts: int = 2,
    runner: AgentRunner = _default_agent_runner,
) -> Rationale:
    """Render one rationale via the `llm` engine, retrying once on a
    guardrail failure.

    Args:
        pack: A placement's already-resolved graph evidence -- same input
            render.render_rationale takes.
        style: `clinician` for prose, or `technical` for audit detail.
        settings: Must carry a non-empty `openai_api_key`.
        max_attempts: Total attempts including the first (default 2).
        runner: Injectable OpenAI call -- defaults to the real SDK; tests
            supply a fake.

    Returns:
        Rationale text plus the cited IRI list.

    Raises:
        ValueError: If the placement has no evidence (same as the
            deterministic renderer).
        RuntimeError: If no OpenAI API key is configured.
        RationaleGuardrailError: If every attempt fails the
            evidence-faithfulness check.
        AgentRunError: If the underlying SDK call itself fails.
    """
    if not pack.evidence:
        raise ValueError(f"{pack.pathway_number} has no cited evidence")
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set -- required for the llm rationale engine")

    prompt = f"style: {style}\n\nevidence_pack:\n{_evidence_pack_json(pack)}"

    last_error: RationaleGuardrailError | None = None
    for _ in range(max_attempts):
        output = runner(
            instructions=_INSTRUCTIONS,
            prompt=prompt,
            model=settings.openai_model,
            api_key=settings.openai_api_key,
        )
        try:
            _validate_citations(pack, output.citation_iris)
        except RationaleGuardrailError as exc:
            last_error = exc
            continue
        return Rationale(
            pathway_number=pack.pathway_number,
            text=output.text,
            citation_iris=tuple(output.citation_iris),
        )
    assert last_error is not None
    raise last_error


def render_many_llm(
    packs: list[EvidencePack],
    *,
    style: RenderStyle,
    settings: Settings,
    runner: AgentRunner = _default_agent_runner,
) -> list[Rationale]:
    """Render rationale text for every pack via the `llm` engine."""
    return [
        render_rationale_llm(pack, style=style, settings=settings, runner=runner)
        for pack in packs
    ]
