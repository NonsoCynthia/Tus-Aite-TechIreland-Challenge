# Track: Coordinating Agent

**ID:** `coordinating-agent_20260906`
**Type:** feature
**Status:** pending
**Created:** 2026-09-06

## Summary

The coordinating agent: the component that takes one hospital's cohort for one day, the urgency and
capacity scores already written for that run, and produces a ranked, evidence-cited, rule-checked
`Decision` written through `POST /decisions`.

Carved out of `explainable-agent-based-triage_20260828` FR3 (and FR6 in part) as its own track so it
can be specified, built and merged independently of the urgency and capacity agents, which are being
built in parallel by other team members. Per **ADR-002**, the agent's only integration points are
three HTTP endpoints on `retrieval-service_20260904`: `GET /hospitals/.../cohort/...` and
`GET /runs/.../hospitals/.../scores` for input, `POST /decisions` for output. It never touches
Postgres or Oxigraph directly.

The coordinator is deterministic end to end. No LLM is involved anywhere in this track — the same
inputs must always produce the same ranking, byte for byte, and that is tested rather than asserted
(NFR4). The LLM rationale layer is parent-track FR4 and is out of scope here.

## The five decisions this track rests on

Recorded in full in `decisions.md`, ADR-003 to ADR-008:

- **Ordering is by `severity_rank`, never the raw `cpc` code.** The NTPF codes do not sort in
  clinical order (Urgent 1, Semi-Urgent **3**, Routine **2**), and sorting on them silently places
  every routine referral above every semi-urgent one while still passing a naive `RULE-ORDER` check.
- **Clinical priority is a hard, non-compensatory band.** No score moves a referral across a band;
  scores order within one. This reconciles FR3's rules-only tie-break chain with `RankingIn`'s
  required score fields, and makes `RULE-ORDER` unfailable by construction.
- **Capacity modulates the weights, never an individual referral.** `capacity_score` is a property
  of a specialty, not a patient, so putting it in the per-patient sort key would only reorder
  patients by which department referred them. Instead a single cohort-level scarcity value sets α in
  `priority = α·urgency + (1 − α)·wait_normalised`: under pressure, clinical need dominates; under
  slack, queue fairness gets more say.
- **Uncategorised and Excluded referrals are ranked last, as two distinguishable groups.** Never
  merged, never dropped — "no category recorded" is a data-quality defect someone must fix, while
  "Excluded" is a deliberate clinical statement, and only one of the two needs anyone's attention.
- **The `capacity_score` sign convention is required configuration with no default** (ADR-007,
  **still open**). Its direction is undocumented and owned by the capacity agent's author. Read
  backwards, the system weights urgency least when the hospital is under most pressure, with every
  number still in range and every ranking still plausible. The agent refuses to start unconfigured,
  and records the configured value in `coordinator_version` on every decision it writes.

## Status

Phases 1-6 are built: cohort/score fetching, CPC bands (ADR-003/004), scarcity/α/priority
(ADR-005/010), the full sort key and rule checks, citations and decision assembly (ADR-008/009),
and the CLI (`python -m coordinator`). 73 tests, 72 passing; the one failure is deliberate — see
below. Tier 1 (`bands.py`, `priority.py`, `ranking.py`, `rule_checks.py`) is at **100% coverage**,
well over the ≥80% bar. `ruff check`, `ruff format --check` and `mypy` are all clean.

Two tasks remain, and neither is work this track can do itself:

- **Task 6.6** (a full run against live scores) waits on the urgency and capacity agents existing
  and producing real output.
- **Task 6.7** (compliance review of the first real output) waits on the responsible-AI/compliance
  lead, already asked via the ADR-011 message below — and, transitively, on 6.6.

**Three ADRs are open, and each blocks something specific:**

- **ADR-007** (capacity sign convention unconfirmed) — blocks treating **any** decision this agent
  writes as final. Both conventions are implemented behind `--capacity-direction`; which one is
  correct for the real capacity agent is still unknown.
- **ADR-009** (default citations don't validate against today's `EvidenceType`) — blocks using the
  default citation mode against the live retrieval service; `--legacy-citations` is the working path
  until the change request lands. Tracked by a test that fails on purpose (see `coordinator/
  README.md`).
- **ADR-011** (CRT breach is a hard tier above clinical priority, not a decision anyone made on
  purpose) — blocks calling the ranking clinically final; referred to the responsible-AI/compliance
  lead and to clinical input, and is what task 6.7 is waiting to review.
