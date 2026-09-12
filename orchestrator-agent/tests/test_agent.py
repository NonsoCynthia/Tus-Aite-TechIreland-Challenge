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


def test_build_agent_exposes_exactly_the_four_pipeline_tools() -> None:
    agent = build_agent(model="gpt-4.1-mini")

    tool_names = {tool.name for tool in agent.tools}
    assert tool_names == {
        "run_urgency_agent",
        "run_capacity_agent",
        "run_coordinator",
        "generate_rationale",
    }


def test_build_agent_uses_the_configured_model() -> None:
    agent = build_agent(model="gpt-4.1")

    assert agent.model == "gpt-4.1"
