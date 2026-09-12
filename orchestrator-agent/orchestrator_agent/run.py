"""Orchestration entrypoint: runs the tool-calling agent end to end for one
hospital-day and returns its final narrative.
"""

from __future__ import annotations

from typing import Protocol

from .config import Settings


class PipelineRunner(Protocol):
    def __call__(self, *, prompt: str, model: str, api_key: str) -> str: ...


def _default_pipeline_runner(*, prompt: str, model: str, api_key: str) -> str:
    """The real OpenAI Agents SDK run. Imported lazily -- see agent.py's own
    docstring for why the SDK dependency is confined to this call path."""
    from agents import Runner, set_default_openai_key

    from .agent import build_agent

    set_default_openai_key(api_key)
    agent = build_agent(model=model)
    result = Runner.run_sync(agent, prompt)
    return str(result.final_output)


def run_pipeline(
    hospital_hipe: str,
    as_of_date: str,
    run_id: str,
    *,
    settings: Settings,
    runner: PipelineRunner = _default_pipeline_runner,
) -> str:
    """Runs urgency -> capacity -> coordinator -> rationale via the agent and
    returns its final narrative.

    Args:
        hospital_hipe: 4-character HIPE hospital code.
        as_of_date: ISO date.
        run_id: Shared run_id for every score/decision this pipeline writes.
        settings: Must carry a non-empty `openai_api_key`.
        runner: Injectable agent run -- defaults to the real SDK; tests
            supply a fake so the pipeline-composition logic is verifiable
            without a network call or API key.

    Returns:
        The agent's final narrative summarising the whole run.

    Raises:
        RuntimeError: If no OpenAI API key is configured.
    """
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set -- required to run the orchestrator agent")

    prompt = (
        f"Run the full pipeline for hospital_hipe={hospital_hipe!r}, "
        f"as_of_date={as_of_date!r}, run_id={run_id!r}."
    )
    return runner(prompt=prompt, model=settings.openai_model, api_key=settings.openai_api_key)
