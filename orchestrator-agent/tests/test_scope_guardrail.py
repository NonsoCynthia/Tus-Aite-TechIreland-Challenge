"""scope_guardrail.py tests: structural checks only (building the guardrail
requires the `agents` package). The guardrail's actual classification
behaviour is itself an LLM call and is verified manually against a live key
(see README.md) -- run_pipeline/ask_question catching
InputGuardrailTripwireTriggered is likewise excluded from fast unit tests
for the same reason every other real-SDK call path is (run.py's own
docstrings)."""

from __future__ import annotations

from orchestrator_agent.scope_guardrail import (
    GENERIC_OUT_OF_SCOPE_RESPONSE,
    scope_input_guardrail,
)


def test_generic_response_does_not_reveal_internal_tool_names() -> None:
    # The refusal should read as a product boundary, not leak implementation
    # details an adversarial prompt could use (e.g. exact tool/function names).
    for leaky_term in ("run_coordinator", "function_tool", "subprocess", "make "):
        assert leaky_term not in GENERIC_OUT_OF_SCOPE_RESPONSE


def test_generic_response_is_non_empty_and_declines_clearly() -> None:
    assert GENERIC_OUT_OF_SCOPE_RESPONSE
    assert "can't help" in GENERIC_OUT_OF_SCOPE_RESPONSE


def test_guardrail_is_named_for_agent_py_to_reference() -> None:
    assert scope_input_guardrail.get_name() == "triage-scope-guardrail"
