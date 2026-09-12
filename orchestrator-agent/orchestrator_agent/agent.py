"""Builds the Triage Orchestrator Agent: an OpenAI Agents SDK `Agent` whose
tools are tools.py's plain functions, wrapped here (not in tools.py) with
`function_tool` so tools.py stays importable and unit-testable without the
`agents` package (mirrors llm_render.py's lazy-import pattern in rationale/,
for the same reason: this module is the one place the SDK dependency is
required).

The instructions below fix the pipeline order explicitly -- this agent
executes a known-correct sequence, it does not discover one. See
conductor/tracks/explainable-agent-based-triage_20260828/decisions.md
ADR-011 for why that boundary matters here specifically, ADR-012 for the
read-only clinician Q&A mode added alongside it, and ADR-013 for the
scope_guardrail.py input guardrail wired in below -- a request outside
those two modes is rejected in code before the main agent's tools are ever
reachable, not just discouraged by instruction.
"""

from __future__ import annotations

from agents import Agent, Tool, function_tool

from . import tools
from .scope_guardrail import scope_input_guardrail

INSTRUCTIONS = """
You are the triage orchestrator for a hospital referral prioritisation system.
You have two distinct modes -- work out which one a message calls for before
acting, and never blend them.

**Pipeline mode.** When asked to score, rank, or run the pipeline for a
hospital/date/run_id, run this EXACT sequence, in this exact order, every
time:

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

**Q&A mode.** When asked a question about existing data -- "why is this
referral ranked here", "has this been scored yet", "how long has this patient
been waiting", "what's the cohort for this hospital today" -- use
get_referral_context / get_wait_counters / get_cohort / get_decision /
get_evidence as needed, in whatever order actually answers the question. These
are read-only: calling any of them, any number of times, changes nothing.
Answer only from what the tools actually return. If a tool reports nothing
exists yet (no decision, no referral, empty cohort), say that plainly rather
than guessing at what the answer would probably be. Prefer get_decision/
get_evidence for the underlying facts and their graph node references;
prefer generate_rationale specifically when the clinician wants it explained
in plain language rather than shown the raw data.

Both modes share the same rule: this is decision support only. Never phrase a
summary or an answer as a diagnosis or a clinical decision, and always make
clear a clinician's sign-off is required. Never state a fact -- a score, a
rank, a wait time, a citation -- that a tool did not actually return.

If a tool call fails or times out, report exactly what failed and stop --
never guess at a workaround or invent a result a tool did not actually
return.
""".strip()

_TOOLS: list[Tool] = [
    function_tool(tools.run_urgency_agent),
    function_tool(tools.run_capacity_agent),
    function_tool(tools.run_coordinator),
    function_tool(tools.generate_rationale),
    function_tool(tools.get_referral_context),
    function_tool(tools.get_wait_counters),
    function_tool(tools.get_cohort),
    function_tool(tools.get_decision),
    function_tool(tools.get_evidence),
]


def build_agent(*, model: str) -> Agent:
    return Agent(
        name="triage-orchestrator",
        instructions=INSTRUCTIONS,
        model=model,
        tools=_TOOLS,
        input_guardrails=[scope_input_guardrail],
    )
