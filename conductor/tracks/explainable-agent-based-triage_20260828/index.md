# Track: Explainable Agent-Based Triage System — full build

**ID:** `explainable-agent-based-triage_20260828`
**Type:** feature
**Status:** pending
**Branch:** `feature/explainable-triage-system`

## Documents

- [Specification](./spec.md)
- [Implementation Plan](./plan.md)
- [Decisions](./decisions.md)
- [Metadata](./metadata.json)

## Summary

Builds the urgency agent, capacity agent, coordinating agent, rationale layer, clinician UI with
override loop, and CPC/CRT compliance validation on top of `graph-foundation_20260826`. Maps to
proposal §14 Days 3–6.

**2026-09-04:** ADR-002 (where agent outputs get written) is recorded in [decisions.md](./decisions.md)
— Postgres is the system of record, the graph gets a synchronous projection on commit. The write path
itself is implemented in `retrieval-service_20260904`, not in this track; agents built here call that
service rather than writing to Postgres or the graph directly.

**2026-09-08:** Phase 1 (urgency agent) built in `urgency-agent/` — NEWS2 scoring, the
retrieval-service write path, CLI and a committed mutation check. 113 tests passing, 5 skipped
(3 awaiting captured fixtures, 2 awaiting a live retrieval service), 97% coverage. Only the manual
verification task remains open in Phase 1, plus the MTS task, which is **not buildable from this
dataset** (ADR-004).

Four ADRs were added building it, two of them open and neither this track's to close:

- **ADR-004 (open)** — `urgency_score` v1 is NEWS2-only and is an *incomplete* urgency signal. The
  dataset team measured NEWS2 against triage category and published the result: correlation never
  exceeds 0.253, the best rule on `news2` alone beats guessing by 17.5 percentage points, and 54–59%
  of the highest-acuity patients score `news2 <= 2`. No ranked list built on v1 alone should be
  described as clinically prioritised.
- **ADR-008 (open)** — `GET /referrals/.../context` does not return `priority_level_gp`,
  `referral_source` or `high_clinical_or_social_needs`, three of the four inputs the dataset's own
  documentation says an urgency agent must read. A change request against
  `retrieval-service_20260904`; nothing in `urgency-agent/` can resolve it. **This blocks ADR-004's
  remedy.**

ADR-005 (score the most recent observation) and ADR-006 (normalise through escalation breakpoints,
not linearly) are accepted; ADR-006 is pending a distribution check against real data.

**2026-09-12:** the rationale layer (merged separately, `rationale/`) gained an `llm` render
engine (`rationale/llm_render.py`, ADR-010) — OpenAI Agents SDK, evidence-faithfulness enforced
in code via a citation-IRI guardrail, additive alongside the existing deterministic default. On
top of that, `orchestrator-agent/` adds a genuine tool-calling agent that runs the fixed
urgency → capacity → coordinator → rationale sequence end to end and narrates the result
(ADR-011) — its tools only trigger the existing packages' own `make *-run` targets or read what
they already wrote, never computing a score or inventing a citation itself. Both verified against
real OpenAI calls, not just mocked.

`orchestrator-agent/` then gained a second mode (ADR-012): a clinician can ask it a question
directly ("why is this referral ranked here", "has it been scored yet") via five new read-only
tools, with conversation history carried across follow-ups. Both modes are now bounded by a
code-enforced scope guardrail (ADR-013, OpenAI Agents SDK `InputGuardrail`) — a request outside
"run the pipeline" or "answer a question about data already in the system" is rejected before
either mode's tools are reachable at all, verified against real OpenAI calls including a
prompt-injection attempt.
