"""Builds the Triage Orchestrator Agent: an OpenAI Agents SDK `Agent` whose
tools are tools.py's plain functions, wrapped here (not in tools.py) with
`function_tool` so tools.py stays importable and unit-testable without the
`agents` package (mirrors llm_render.py's lazy-import pattern in rationale/,
for the same reason: this module is the one place the SDK dependency is
required).

The instructions below fix the pipeline order explicitly -- this agent
executes a known-correct sequence, it does not discover one. See
conductor/tracks/explainable-agent-based-triage_20260828/decisions.md
ADR-011 for why that boundary matters here specifically.
"""

from __future__ import annotations

from agents import Agent, Tool, function_tool

from . import tools

INSTRUCTIONS = """
You are the triage orchestrator for a hospital referral prioritisation system.

Given a hospital, a date, and a run_id, run this EXACT sequence, in this exact
order, every time:

1. run_urgency_agent
2. run_capacity_agent
3. run_coordinator (capacity_direction="pressure" unless a human has
   explicitly told you otherwise)
4. generate_rationale

Never skip a step, never reorder them, and never invent a step of your own.
Each tool already scores or ranks deterministically on its own -- you are not
computing a score or a rank yourself; you are running the correct sequence and
then explaining, in plain language, what happened at each step, including any
failures, exclusions, or skipped referrals a tool reports (paediatric
exclusions and missing-evidence skips are expected, documented behaviour, not
errors -- report them plainly, don't alarm about them).

This is decision support only. Never phrase your summary as a diagnosis or a
clinical decision, and always make clear a clinician's sign-off is required.

If a tool call fails or times out, report exactly what failed and stop --
never guess at a workaround or invent a result a tool did not actually
return.
""".strip()

_TOOLS: list[Tool] = [
    function_tool(tools.run_urgency_agent),
    function_tool(tools.run_capacity_agent),
    function_tool(tools.run_coordinator),
    function_tool(tools.generate_rationale),
]


def build_agent(*, model: str) -> Agent:
    return Agent(
        name="triage-orchestrator",
        instructions=INSTRUCTIONS,
        model=model,
        tools=_TOOLS,
    )
