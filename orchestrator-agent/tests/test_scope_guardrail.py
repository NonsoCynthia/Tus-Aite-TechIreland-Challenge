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


# --- the refusals a 19-question permutation test found missing ----------
#
# Every one of these is a prompt string. Nothing in the code fails if someone
# edits it away, which is exactly why they are pinned here: the failures below
# were all live behaviour before they were written, not hypotheticals.


def test_ordering_questions_are_named_out_of_scope() -> None:
    """"Who should I see first" was answered, 5 phrasings out of 5.

    It passes the older "beyond what the system's own recorded data says"
    wording because the data IS recorded. The boundary is not the data, it is
    who makes the call, so the classifier has to be told the class by name.
    """
    from orchestrator_agent.scope_guardrail import _SCOPE_CHECK_INSTRUCTIONS

    normalised = " ".join(_SCOPE_CHECK_INSTRUCTIONS.split())
    assert "recommend, choose, defer, or triage BETWEEN patients" in normalised
    for phrasing in (
        "who should I see first",
        "which patient is most at risk",
        "should I see X before Y",
        "can I safely postpone X",
        "if I only have time for five",
    ):
        assert phrasing in normalised, phrasing
    # and the distinction that keeps it from over-blocking the whole panel
    assert "Reporting the computed order is IN SCOPE" in normalised


def test_asking_what_our_own_terms_mean_stays_in_scope() -> None:
    """Tightening the guardrail made "what does CRT stand for?" a refusal.

    It names no hospital, referral or date, so the ambiguity rule sent it out of
    scope. Refusing to define our own vocabulary reads as broken to a clinician.
    """
    from orchestrator_agent.scope_guardrail import _SCOPE_CHECK_INSTRUCTIONS

    in_scope = _SCOPE_CHECK_INSTRUCTIONS.split("OUT OF SCOPE")[0]
    assert "terms, abbreviations, scores or bands" in " ".join(in_scope.split())
    for term in ("CPC", "CRT", "NEWS2", "alpha", "priority"):
        assert term in in_scope, term


def test_clinical_decision_refusal_shows_the_order_but_declines_the_call() -> None:
    from orchestrator_agent.scope_guardrail import CLINICAL_DECISION_RESPONSE

    assert "can show you the ranked order" in CLINICAL_DECISION_RESPONSE
    assert "advise which patient to see, defer, or prioritise" in CLINICAL_DECISION_RESPONSE
    # the guardrail also catches "how unwell is X", so the message has to read
    # correctly for an assessment question, not only an ordering one
    assert "judge how unwell someone is" in CLINICAL_DECISION_RESPONSE
    assert "decision support only" in CLINICAL_DECISION_RESPONSE
    # same leak check the generic response gets
    for leaky_term in ("run_coordinator", "function_tool", "subprocess", "make "):
        assert leaky_term not in CLINICAL_DECISION_RESPONSE


def test_response_for_picks_the_message_from_the_classifier_category() -> None:
    from orchestrator_agent.scope_guardrail import (
        CLINICAL_DECISION_RESPONSE,
        _ScopeCheck,
        response_for,
    )

    class _Exc(Exception):
        def __init__(self, check: object) -> None:
            self.guardrail_result = type(
                "R", (), {"output": type("O", (), {"output_info": check})()}
            )()

    clinical = _ScopeCheck(in_scope=False, reasoning="x", category="clinical_decision")
    assert response_for(_Exc(clinical)) == CLINICAL_DECISION_RESPONSE

    other = _ScopeCheck(in_scope=False, reasoning="x", category="other")
    assert response_for(_Exc(other)) == GENERIC_OUT_OF_SCOPE_RESPONSE


def test_response_for_falls_back_rather_than_raising_at_a_clinician() -> None:
    """The attribute path runs through the SDK's exception shape, not ours.

    A wrong refusal message is a far smaller problem than a traceback, so every
    way of failing to read the category has to land on the generic response.
    """
    from orchestrator_agent.scope_guardrail import response_for

    assert response_for(Exception("no guardrail_result at all")) == GENERIC_OUT_OF_SCOPE_RESPONSE

    class _Half(Exception):
        guardrail_result = object()  # has the attribute, nothing underneath

    assert response_for(_Half()) == GENERIC_OUT_OF_SCOPE_RESPONSE


def test_category_defaults_to_other_so_a_silent_model_gets_the_generic_refusal() -> None:
    from orchestrator_agent.scope_guardrail import _ScopeCheck

    assert _ScopeCheck(in_scope=False, reasoning="x").category == "other"
