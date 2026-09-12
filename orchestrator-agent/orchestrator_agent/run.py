"""Orchestration entrypoints: run_pipeline() (pipeline mode -- one prompt,
one final narrative) and ask_question() (Q&A mode -- a conversation a
clinician can continue turn by turn). Both isolate the real OpenAI Agents
SDK call behind an injectable runner, same pattern rationale/llm_render.py
uses, so the composition logic here is unit-testable without a network
call or API key.
"""

from __future__ import annotations

from typing import Any, Protocol

from .config import Settings


class PipelineRunner(Protocol):
    def __call__(self, *, prompt: str, model: str, api_key: str) -> str: ...


def _default_pipeline_runner(*, prompt: str, model: str, api_key: str) -> str:
    """The real OpenAI Agents SDK run. Imported lazily -- see agent.py's own
    docstring for why the SDK dependency is confined to this call path.

    run_pipeline's own prompt is always machine-constructed from
    hospital/date/run_id, never raw user text, so the scope guardrail
    (ADR-013) should never actually trip here -- caught anyway as defence
    in depth, since a crash on an unexpected guardrail result would be a
    worse outcome than the same generic response ask_question gives."""
    from agents import InputGuardrailTripwireTriggered, Runner, set_default_openai_key

    from .agent import build_agent
    from .scope_guardrail import GENERIC_OUT_OF_SCOPE_RESPONSE

    set_default_openai_key(api_key)
    agent = build_agent(model=model)
    try:
        result = Runner.run_sync(agent, prompt)
    except InputGuardrailTripwireTriggered:
        return GENERIC_OUT_OF_SCOPE_RESPONSE
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


# One conversation turn's input items, as returned by RunResult.to_input_list()
# -- opaque to this module (the SDK's own item types are a large closed union
# not worth re-exporting here), just threaded through to the next call.
ConversationHistory = list[Any]


class AskRunner(Protocol):
    def __call__(
        self, *, history: ConversationHistory | None, question: str, model: str, api_key: str
    ) -> tuple[str, ConversationHistory]: ...


def _default_ask_runner(
    *, history: ConversationHistory | None, question: str, model: str, api_key: str
) -> tuple[str, ConversationHistory]:
    """The real OpenAI Agents SDK run, continuing a prior conversation when
    `history` is given. Imported lazily -- see agent.py's own docstring for
    why the SDK dependency is confined to this call path.

    A clinician's own question is exactly the kind of free-text input the
    scope guardrail (ADR-013) exists to check -- on a trip, the prior
    history is returned unchanged (nothing happened this turn) alongside
    the generic response, so the conversation can continue past a declined
    off-topic question rather than being reset."""
    from agents import InputGuardrailTripwireTriggered, Runner, set_default_openai_key

    from .agent import build_agent
    from .scope_guardrail import GENERIC_OUT_OF_SCOPE_RESPONSE

    set_default_openai_key(api_key)
    agent = build_agent(model=model)
    conversation_input: str | ConversationHistory = (
        question if history is None else [*history, {"role": "user", "content": question}]
    )
    try:
        result = Runner.run_sync(agent, conversation_input)
    except InputGuardrailTripwireTriggered:
        return GENERIC_OUT_OF_SCOPE_RESPONSE, history or []
    return str(result.final_output), result.to_input_list()


def _default_read_only_ask_runner(
    *, history: ConversationHistory | None, question: str, model: str, api_key: str
) -> tuple[str, ConversationHistory]:
    """The real OpenAI Agents SDK run for the browser UI's read-only chat.

    This intentionally builds the Q&A-only agent, whose tool list excludes the
    pipeline trigger tools.
    """
    from agents import InputGuardrailTripwireTriggered, Runner, set_default_openai_key

    from .agent import build_qa_agent
    from .scope_guardrail import GENERIC_OUT_OF_SCOPE_RESPONSE

    set_default_openai_key(api_key)
    agent = build_qa_agent(model=model)
    conversation_input: str | ConversationHistory = (
        question if history is None else [*history, {"role": "user", "content": question}]
    )
    try:
        result = Runner.run_sync(agent, conversation_input)
    except InputGuardrailTripwireTriggered:
        return GENERIC_OUT_OF_SCOPE_RESPONSE, history or []
    return str(result.final_output), result.to_input_list()


def ask_question(
    question: str,
    *,
    settings: Settings,
    history: ConversationHistory | None = None,
    runner: AskRunner = _default_ask_runner,
) -> tuple[str, ConversationHistory]:
    """Asks the agent a question in Q&A mode (read-only tools only -- see
    agent.py's instructions). Continues a prior conversation if `history` is
    given, so a clinician can ask a follow-up without repeating context.

    Args:
        question: The clinician's question, e.g. "why is PW-9001-000007
            ranked above PW-9001-000012?".
        settings: Must carry a non-empty `openai_api_key`.
        history: The second element returned by a prior call, to continue
            that same conversation -- omit to start a fresh one.
        runner: Injectable agent run -- defaults to the real SDK; tests
            supply a fake.

    Returns:
        `(answer, updated_history)` -- pass `updated_history` into the next
        call to continue this same conversation.

    Raises:
        RuntimeError: If no OpenAI API key is configured.
    """
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set -- required to run the orchestrator agent")

    return runner(
        history=history,
        question=question,
        model=settings.openai_model,
        api_key=settings.openai_api_key,
    )


def ask_question_read_only(
    question: str,
    *,
    settings: Settings,
    history: ConversationHistory | None = None,
    runner: AskRunner = _default_read_only_ask_runner,
) -> tuple[str, ConversationHistory]:
    """Ask a UI chat question with only read/rationale tools available."""
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set -- required to run the UI assistant")

    return runner(
        history=history,
        question=question,
        model=settings.openai_model,
        api_key=settings.openai_api_key,
    )
