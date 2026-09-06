# Spec: Coordinating Agent — ranking, rule checks, decision write-back

**Track:** `coordinating-agent_20260906`
**Type:** feature
**Maps to:** `explainable-agent-based-triage_20260828` FR3 (and FR6 in part), carved out as its own
track so it can be built and merged independently of the urgency and capacity agents.

## Overview

Build the coordinating agent: the component that takes one hospital's cohort for one day, the
urgency and capacity scores already written for that run, and produces a ranked, evidence-cited,
rule-checked `Decision` written through `POST /decisions`.

The coordinator is deterministic. No LLM is involved at any point in this track — the same inputs
must always produce the same ranking, byte for byte. That reproducibility is the compliance claim
the whole project rests on (`tech-stack.md`, Agent Reasoning Model), and it is what makes a ranked
position defensible to a clinician, a judge, or a regulator.

End state: `python -m coordinator --hospital 9004 --as-of 2026-08-30 --run-id <id>` produces a
complete ranked list for that hospital-day, posts it, and every position carries its evidence and
its rule results.

## Background

Per **ADR-002** (`explainable-agent-based-triage_20260828/decisions.md`), agents never touch
Postgres or Oxigraph directly. `retrieval-service_20260904` is the single mediator in both
directions. The coordinator therefore has exactly three integration points, all HTTP:

| Direction | Endpoint | Purpose |
|---|---|---|
| input | `GET /hospitals/{hospital_hipe}/cohort/{as_of_date}` | who is on the list, with CPC and CRT breach |
| input | `GET /runs/{run_id}/hospitals/{hospital_hipe}/scores` | what urgency and capacity already decided |
| output | `POST /decisions` | the ranked list, atomically, with citations and rule checks |

**The urgency and capacity agents are being built in parallel by other team members and do not yet
exist.** `agent.agent_scores` is empty. `RankingIn.urgency_score` and `RankingIn.capacity_score`
are required fields with no defaults, so the coordinator cannot post a real decision until those
agents write scores. This track therefore builds against a **score-source seam** (FR2) so the
ranking logic can be developed, tested and merged now, and wired to live scores by changing one
adapter.

## Functional Requirements

### FR1 — Cohort acquisition

- Fetches the cohort for one `(hospital_hipe, as_of_date)` from the retrieval service.
- An empty `referrals` list is a valid result, not an error: the agent exits cleanly having written
  nothing (`POST /decisions` requires `min_length=1` on `rankings`, so posting an empty decision is
  impossible by contract).
- Never queries Postgres or the graph directly (ADR-002).

### FR2 — Score acquisition through a replaceable seam

- Scores are fetched through a single interface — one function/protocol — with two implementations:
  a live client calling `GET /runs/{run_id}/hospitals/{hospital_hipe}/scores`, and a deterministic
  fixture source for development and tests.
- Selection is by explicit configuration, never inferred. The live client is the default; the
  fixture source must be opted into and must be recorded in `coordinator_version` (FR9) so no
  decision written from stub scores can ever be mistaken for one written from real ones.
- Response is keyed by `pathway_number`, then by agent name (`urgency` / `capacity`). A referral may
  appear with only one of the two agents' scores, or not appear at all.
- **A referral with no urgency score cannot be ranked.** It is excluded from the decision and
  reported, rather than defaulted to zero — a missing score is missing information, not low urgency.
  A referral with an urgency score but no capacity score is ranked normally (capacity affects only
  the cohort-level weight, FR5, never an individual position).

### FR3 — CPC band resolution

- Clinical prioritisation category is a **hard, non-compensatory band boundary**. No score may move
  a referral across a band (ADR-004).
- Ordering is by `severity_rank`, **never** by the raw `cpc` code value. The NTPF codes do not sort
  numerically: Urgent is 1, Semi-Urgent is **3**, Routine is **2** (`core.ref_codes`, and
  `dataset/docs/GETTING_THE_DATA.md` §4 names this as the trap it is). Sorting on `cpc` silently
  places every routine referral above every semi-urgent one and still satisfies a naive
  `RULE-ORDER` check.
- The mapping is a module-level constant with a test asserting it against `core.ref_codes`, so a
  future change to the code table fails a test rather than silently reordering patients.

### FR4 — Unranked tails

Two referral groups have no `severity_rank` and are ranked after every categorised referral, as two
distinguishable groups, never merged (ADR-006):

1. **No CPC recorded** (`cpc: null`) — missing data. A referral with `triage_status: "triaged"` and
   no CPC has passed through triage without a category being recorded; this is a data-quality
   defect the UI must surface, not bury. `RULE-TRIAGE-TURNAROUND` is evaluated against these.
2. **Excluded** (code 4) — a positive clinical statement that this pathway does not apply. Ranked
   last.

Neither group is dropped from the decision. Both are ordered internally by the same chain as every
other band (FR5), so no position anywhere in the decision is arbitrary.

### FR5 — Ranking

Within a band, ordering is by a composite priority in which **capacity never acts on an individual
referral** (ADR-005):

```
priority   = α · urgency + (1 − α) · wait_normalised
α          = α_min + (α_max − α_min) · scarcity
```

- `scarcity` is computed **once per decision**, at hospital level, from the distinct specialty
  capacity scores present in the cohort. It is identical for every referral in that decision.
- `wait_normalised` is `adjusted_wait_days` min–max normalised **within the band**, since ordering
  only ever occurs within a band. The degenerate case (all waits equal) is defined explicitly and
  tested, not left to a division by zero.
- `α_min` and `α_max` are configuration with documented defaults (`0.5`, `0.9`): urgency never
  counts for less than waiting time, and waiting time never drops out of the ordering entirely.
  Both bounds are `modelled` parameters in the dataset's own labelling sense — a deliberate choice
  with a stated reason, not a fitted quantity.

The full sort key:

```
(severity_rank, crt_breached desc, priority desc, referral_date asc, pathway_number asc)
```

`pathway_number` is the final key purely to guarantee a total order: `referral_date` ties are
common in this dataset, and without a deterministic last resort two runs over the same data could
produce different rankings.

`crt_breached` is three-valued (`true` / `false` / `null` where no CRT applies to that CPC) and is
taken from the cohort response as given, never re-derived — the retrieval service already computes
it against `core.ref_rules`, and re-deriving it would create the divergence risk that
`tech-stack.md` Decisions 1 and 2 exist to prevent.

### FR6 — Capacity sign convention as required configuration

`capacity_score` is a 0–1 float whose direction is **undocumented** and owned by the capacity
agent's author. Read backwards, the system's entire behaviour under load inverts, the numbers stay
in range, and the ranking stays superficially plausible — no test catches it.

- The direction is **required configuration with no default**. The agent refuses to start
  unconfigured rather than guessing.
- Accepted values: `availability` (1.0 = most capacity free, so `scarcity = 1 − capacity`) and
  `pressure` (1.0 = maximum pressure, so `scarcity = capacity`).
- The configured value is recorded in `coordinator_version` on every decision (FR9), so any ranking
  ever written can be traced to the assumption it was made under.
- Resolving this with the capacity agent's author, and recording the answer in `decisions.md`, is a
  task in this track's plan.

### FR7 — Citations

- Every ranked position carries at least one citation (`RankingIn.citations` is `min_length=1` —
  an uncited placement is unwritable by contract, backing NFR5 of the parent track).
- Citations use the four `eat:cites` role subproperties: `urgency`, `capacity`, `timeframe`,
  `multi_list`.
- Evidence types and role values are taken from the `EvidenceType` and `CitationRole` enums in
  `retrieval/app/schemas.py`. **These are read from the source before any citation code is
  written** — they are not guessed at, and a wrong `evidence_key` format is rejected by
  `iri.validate_segment` at the service boundary.

### FR8 — Rationale summary

- `rationale_summary` is the coordinator's own short, deterministic note — not LLM output. The LLM
  rationale layer is FR4 of the parent track and is out of scope here.
- It states only what the ranking logic actually used: band, breach status, the two scores, and the
  weight in force. It makes no clinical claim beyond its cited evidence.
- It follows `conductor/product-guidelines.md` on verbs: the system ranks and explains; it never
  admits, schedules, or acts.

### FR9 — Decision assembly and write-back

- Assembles one `DecisionIn`: unique `decision_id`, the `run_id` the scores came from,
  `hospital_hipe`, `as_of_date`, `coordinator_version`, and one `RankingIn` per referral with a
  unique 1-based `position`.
- `coordinator_version` encodes the semantic version **and the configuration that changed the
  ranking** — capacity direction, α bounds, and score source — so two decisions produced under
  different assumptions are distinguishable after the fact.
- Posts once, atomically. Handles all four documented responses: `200` ok, `207` Postgres committed
  but graph projection failed (the row stands — reported, not retried; retry is out of scope per
  ADR-002), `400` Postgres rejected the payload, `422` validation failed before either store was
  touched.
- A `207` is surfaced as a distinct, non-zero exit condition. It is never reported as success.

### FR10 — Rule checks

Per ranked position, emits `RuleCheckIn` results against `core.ref_rules` (FK-enforced — an unknown
`rule_id` is a `400`, not a validation error):

| Rule | Evaluated against |
|---|---|
| `RULE-CRT-URGENT` | urgent referrals, 28-day threshold |
| `RULE-CRT-SEMI` | semi-urgent referrals, 91-day threshold |
| `RULE-TRIAGE-TURNAROUND` | `awaiting_triage` referrals, 21-day threshold |
| `RULE-ORDER` | no referral ranked above one of higher clinical priority |
| `RULE-TIEBREAK` | same band and status ordered oldest-first |

`RULE-ORDER` and `RULE-TIEBREAK` are properties of the **whole list**, not of one referral, and are
evaluated after the full ordering exists. By construction of FR3/FR5 they cannot fail; the check is
kept anyway, because a check that can only pass is exactly the check that catches the day someone
changes the sort key.

### FR11 — CLI entry point

- `python -m coordinator --hospital <hipe> --as-of <date> --run-id <id>` plus configuration flags.
- `--dry-run` prints the assembled decision without posting, so the ranking can be inspected before
  anything is written.
- A `main()` function called from `if __name__ == '__main__':`, per
  `conductor/code_styleguides/python.md`.

## Non-Functional Requirements

- **NFR1** — Ranking, band resolution, scarcity/α computation and rule checks are **Tier 1**
  (`workflow.md`): strict TDD, test written and failing before implementation, ≥80% coverage
  enforced in CI. A Tier 1 file with no test is a blocking review failure.
- **NFR2** — The retrieval client and citation construction are **Tier 2**: tests required, ≥60%.
- **NFR3** — The CLI is **Tier 3**: one smoke test proving it runs and does not raise.
- **NFR4** — **Determinism.** A property test asserts that ranking the same cohort twice, and
  ranking a shuffled copy of it, produce identical output. This is the reproducibility claim; it is
  tested, not asserted.
- **NFR5** — No unit test performs network I/O. The retrieval service is faked at the seam (FR2).
- **NFR6** — `ruff check`, `ruff format --check` and `mypy` clean on Tier 1 and Tier 2.
- **NFR7** — Google Python style per `conductor/code_styleguides/python.md`: 80-character lines,
  type annotations on public APIs, docstrings with `Args:` / `Returns:` / `Raises:`.

## Acceptance Criteria

1. Given a cohort and a set of scores, the coordinator produces a ranked list in which no referral
   is ranked above one of higher clinical priority, verified against `severity_rank` and not `cpc`.
2. A cohort containing `cpc: null` and Excluded referrals ranks all of them, after every
   categorised referral, in two distinguishable groups.
3. Ranking the same cohort twice produces identical output; ranking a shuffled copy produces
   identical output.
4. Changing the capacity sign configuration changes α and is visible in `coordinator_version`;
   running with no capacity configuration set fails at startup with a clear message.
5. Every ranked position carries at least one citation and its applicable rule checks.
6. A referral with no urgency score is excluded from the decision and reported, never defaulted.
7. A `207` from `POST /decisions` is surfaced distinctly from a `200`.
8. `--dry-run` against the live retrieval service on hospital 9004, 2026-08-30, produces a complete
   ranked list of the real cohort.
9. Tier 1 coverage ≥80%; `ruff` and `mypy` clean.

## Out of Scope

- The urgency and capacity agents (built in parallel by other team members).
- The LLM rationale layer — parent track FR4.
- The clinician UI, accept/reorder/override — parent track FR5.
- `POST /overrides` and `POST /referrals`; the coordinator neither overrides nor intakes.
- Retry or reconciliation after a `207`; detect-and-report only, per ADR-002.
- Any change to `retrieval-service_20260904`. If the coordinator needs something the service does
  not expose, that is a change request against that track, not a workaround here.
