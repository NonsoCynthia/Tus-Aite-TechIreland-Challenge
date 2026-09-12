"""agent.py tests: the tool list and instructions are exactly what
tools.py/run.py depend on -- these are structural checks (the `agents`
package must be installed to build a real Agent), not behavioural ones. The
agent's actual tool-selection behaviour is an LLM call and is verified
manually against a live key (see README.md), not unit-tested here.
"""

from __future__ import annotations

from orchestrator_agent.agent import INSTRUCTIONS, build_agent


def test_instructions_fix_the_pipeline_order_explicitly() -> None:
    steps = ("run_urgency_agent", "run_capacity_agent", "run_coordinator", "generate_rationale")
    for step in steps:
        assert step in INSTRUCTIONS


def test_instructions_state_the_default_capacity_direction() -> None:
    assert "pressure" in INSTRUCTIONS


def test_instructions_describe_both_pipeline_and_qa_modes() -> None:
    assert "Pipeline mode" in INSTRUCTIONS
    assert "Q&A mode" in INSTRUCTIONS
    for read_tool in (
        "get_referral_context",
        "get_wait_counters",
        "get_cohort",
        "get_decision",
        "get_evidence",
    ):
        assert read_tool in INSTRUCTIONS


def test_build_agent_exposes_exactly_the_pipeline_and_read_tools() -> None:
    agent = build_agent(model="gpt-4.1-mini")

    tool_names = {tool.name for tool in agent.tools}
    assert tool_names == {
        "run_urgency_agent",
        "run_capacity_agent",
        "run_coordinator",
        "generate_rationale",
        "get_referral_context",
        "get_wait_counters",
        "get_cohort",
        "get_decision",
        "get_evidence",
    }


def test_build_agent_uses_the_configured_model() -> None:
    agent = build_agent(model="gpt-4.1")

    assert agent.model == "gpt-4.1"


def test_build_agent_wires_the_scope_guardrail() -> None:
    agent = build_agent(model="gpt-4.1-mini")

    guardrail_names = {g.get_name() for g in agent.input_guardrails}
    assert "triage-scope-guardrail" in guardrail_names


def test_instructions_require_generate_rationale_for_why_questions() -> None:
    # ADR-014: "why"/"explain" questions must route through the
    # citation-guardrailed generate_rationale, never a freehand answer
    # composed from get_decision/get_evidence's raw output. Whitespace is
    # normalised since the instructions are hand-wrapped prose.
    normalised = " ".join(INSTRUCTIONS.split())
    assert "MUST be answered by calling generate_rationale" in normalised
    assert "never by composing the explanation yourself" in normalised
