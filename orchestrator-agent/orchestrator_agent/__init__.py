"""The Triage Orchestrator + Rationale Agent: a genuine OpenAI Agents SDK
tool-calling loop with two modes -- running the pipeline every referral
already goes through (urgency, then capacity, then the coordinator, then
rationale) and narrating the result, or answering a clinician's question
about existing data with read-only tools. See ../README.md and
conductor/tracks/explainable-agent-based-triage_20260828/decisions.md
ADR-011 (pipeline sequencing), ADR-012 (Q&A mode), and ADR-013 (the
code-enforced scope guardrail bounding both).
"""

__version__ = "0.1.0"
