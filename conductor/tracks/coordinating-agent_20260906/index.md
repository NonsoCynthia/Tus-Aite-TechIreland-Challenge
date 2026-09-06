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

Phases 2 to 5 are unblocked today: they need the cohort endpoint, which is live, and scores, which
come from fixtures behind the seam of ADR-008. Only the final live-integration verification (task
6.6) waits on the urgency and capacity agents producing real output.

**ADR-007 is open.** Until the capacity direction is confirmed with its author and recorded, no
decision this agent writes should be treated as final.
