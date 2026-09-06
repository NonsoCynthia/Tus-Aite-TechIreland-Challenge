# Plan: Coordinating Agent

**Track:** `coordinating-agent_20260906`

Task states: `[ ]` not started, `[~]` in progress, `[x]` complete.

Tier 1 tasks follow strict TDD per `conductor/workflow.md`: the test is written and **failing**
before the implementation task begins. Each phase ends with a manual verification task, confirmed
by observation, not by "should work".

---

## Phase 1 — Contracts, fixtures, configuration

Nothing here is guessed at. Every shape this agent produces is read from the source that validates
it.

- [ ] 1.1 Read `EvidenceType` and `CitationRole` enums from `retrieval/app/schemas.py`; record the
      exact permitted values in this track's `decisions.md`
- [ ] 1.2 Read `iri.validate_segment` to establish what an `evidence_key` may contain, so citation
      keys are built to pass it rather than discovered to fail it
- [ ] 1.3 Capture a real cohort response (`GET /hospitals/9004/cohort/2026-08-30`) as a committed
      test fixture; note that it contains `cpc: null`, `crt_breached: null`, and heavily breached
      waits, all of which the ranking must handle
- [ ] 1.4 Build a synthetic score fixture covering: both scores present, urgency only, capacity
      only, neither
- [ ] 1.5 Define the configuration object: capacity direction (required, no default), α bounds,
      score source, coordinator semantic version
- [ ] 1.6 **Ask the capacity agent's author** which direction `capacity_score` runs and record the
      answer in `decisions.md`, superseding ADR-005's open status
- [ ] 1.7 Verification: fixtures load, config rejects an unset capacity direction

## Phase 2 — CPC bands and tails (Tier 1)

- [ ] 2.1 Test: `severity_rank` mapping matches `core.ref_codes` exactly (1→1, 3→2, 2→3, 4→none)
- [ ] 2.2 Test: sorting on raw `cpc` produces a *different*, wrong order than sorting on
      `severity_rank` — the regression test for the NTPF code trap, asserting the bug is absent
- [ ] 2.3 Test: `cpc: null` and Excluded referrals both rank after every categorised referral
- [ ] 2.4 Test: the two tail groups stay distinguishable and are not merged
- [ ] 2.5 Test: no referral is ever dropped — every cohort member appears exactly once in the output
- [ ] 2.6 Implement band resolution and tail assignment
- [ ] 2.7 Verification: run against the Phase 1 cohort fixture, confirm band counts by eye

## Phase 3 — Scarcity, α, priority (Tier 1)

- [ ] 3.1 Test: scarcity is computed once per decision and is identical for every referral
- [ ] 3.2 Test: `availability` and `pressure` configurations produce inverse scarcity from the same
      input
- [ ] 3.3 Test: α stays within `[α_min, α_max]` across the full scarcity range
- [ ] 3.4 Test: `wait_normalised` is computed within band, and the all-equal degenerate case is
      handled without dividing by zero
- [ ] 3.5 Test: **capacity cannot reorder two referrals in the same band.** Given two referrals
      identical but for their specialty's capacity score, their relative order is unchanged. This
      is the test that enforces ADR-005 and it is the most important one in the track
- [ ] 3.6 Test: raising scarcity increases urgency's influence relative to waiting time
- [ ] 3.7 Implement scarcity, α, and priority
- [ ] 3.8 Verification: print α and scarcity for the real 9004 cohort under both sign conventions,
      confirm they are inverses

## Phase 4 — Sort key, determinism, rule checks (Tier 1)

- [ ] 4.1 Test: full sort key ordering, band by band
- [ ] 4.2 Test: an urgent referral is never ranked below a semi-urgent one, at any score values
- [ ] 4.3 Test: identical `referral_date` resolves deterministically via `pathway_number`
- [ ] 4.4 Test (NFR4): ranking a shuffled cohort produces identical output
- [ ] 4.5 Test: positions are 1-based, contiguous, and unique (`dr_unique_position`)
- [ ] 4.6 Test: a referral with no urgency score is excluded and reported, never defaulted to zero
- [ ] 4.7 Test: `RULE-CRT-URGENT`, `RULE-CRT-SEMI`, `RULE-TRIAGE-TURNAROUND` fire on the right
      referrals with the right thresholds
- [ ] 4.8 Test: `RULE-ORDER` and `RULE-TIEBREAK` are evaluated over the whole ordered list and pass
- [ ] 4.9 Test: `RULE-ORDER` *fails* on a deliberately mis-ordered list — proving the check has
      teeth rather than passing vacuously
- [ ] 4.10 Implement the sort key and the rule-check evaluator
- [ ] 4.11 Verification: rank the real 9004 cohort, inspect the top 20 and both tails by eye

## Phase 5 — Citations, decision assembly, write-back (Tier 2)

- [ ] 5.1 Test: every ranking carries ≥1 citation (contract: `min_length=1`)
- [ ] 5.2 Test: citation roles map correctly to the four subproperties
- [ ] 5.3 Test: `coordinator_version` encodes capacity direction, α bounds and score source
- [ ] 5.4 Test: `rationale_summary` states only what the ranking used and makes no uncited claim
- [ ] 5.5 Test: the assembled payload validates against `DecisionIn` (import the real model — do
      not reimplement it)
- [ ] 5.6 Test: `200`, `207`, `400`, `422` each handled; `207` surfaced distinctly from success
- [ ] 5.7 Implement the retrieval client, citation construction and decision assembly
- [ ] 5.8 Verification: `--dry-run` against the live service, payload inspected before any write

## Phase 6 — CLI and integration (Tier 3)

- [ ] 6.1 Smoke test: CLI runs end to end against the fixture score source without raising
- [ ] 6.2 Implement `main()` and argument parsing
- [ ] 6.3 `ruff check`, `ruff format --check`, `mypy` clean on Tier 1 and 2
- [ ] 6.4 Tier 1 coverage ≥80% confirmed
- [ ] 6.5 README for the coordinator: how to run it, what each configuration flag changes
- [ ] 6.6 Verification: full run against live scores **once the urgency and capacity agents have
      written some** — blocked on those tracks, and the only task here that is
- [ ] 6.7 Compliance review of the first real output against CPC/CRT rules, per `workflow.md`'s
      cadence: as soon as the agent produces output, not on Day 6

---

## Sequencing note

Phases 2 to 5 are unblocked today: they need the cohort endpoint (live) and scores (fixtures).
Only 6.6 waits on teammates. If the capacity direction (1.6) is still unanswered when Phase 3
starts, implement both conventions behind the config and let 6.6 confirm which is correct — that
is what makes it configuration rather than a guess.
