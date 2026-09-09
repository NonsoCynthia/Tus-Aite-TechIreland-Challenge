# Urgency Agent

Deterministic NEWS2 scoring over one referral's most recent observation
(`conductor/tracks/explainable-agent-based-triage_20260828/spec.md` FR1). Per ADR-002, this agent
never queries SPARQL or Postgres directly -- it only ever calls
[`retrieval-service_20260904`](../retrieval/README.md):
`GET /referrals/{hospital_hipe}/{pathway_number}/context` to gather input, `POST /scores` to write
output.

Full spec/plan: [`conductor/tracks/explainable-agent-based-triage_20260828/`](../conductor/tracks/explainable-agent-based-triage_20260828/)
(Phase 1).

## Read this before using the score

**`urgency_score` v1 cannot rank alone**, measured on this dataset (508 referrals holding both a
NEWS2 and a triage category):

| Category | n | mean NEWS2 | median | `news2 = 0` |
|---|---|---|---|---|
| Urgent | 155 | 1.66 | 1 | **31.0%** |
| Semi-Urgent | 175 | 0.98 | 1 | 43.4% |
| Routine | 178 | 0.46 | 0 | 68.5% |

Pearson r with `severity_rank` = **-0.367**.

The signal is **real and correctly directed** -- mean NEWS2 falls monotonically as urgency drops.
What makes it insufficient is the shape of the misses:

- **31% of Urgent referrals score `news2 = 0`**, so this agent gives 48 genuinely urgent patients
  0.0 -- indistinguishable from a routine patient with normal vitals. About a third of the urgent
  list is invisible to it.
- **Urgent and Semi-Urgent share a median of 1.** The instrument does not separate the two bands it
  most needs to.

`DATASET_README.md` §7.6 carries the worked case: a suspected melanoma, every vital normal,
clinically urgent. **This agent scores that patient 0.0** -- and the table above shows that is not a
rare edge case.

(`dataset/docs/HOW_THE_DATA_WAS_MADE.md` §4 reports lower figures still -- 0.253 correlation, 17.5
percentage points over guessing. Those come from the dataset team's MIMIC fitting work, not from
this cohort, and are the instrument's own limits rather than a measurement of this system. Quote the
table above when describing what this agent does.)

That is by construction, not by defect -- `latent_hazard` is never computed from `news2`
(`generate.py:767`), so an agent reading vitals cannot be graded against its own input. The same
section states what is actually required: *"an urgency agent must read condition, pathway, referral
source and the high-needs flag, not just physiology."* Three of those four are not reachable through
the context endpoint today (**ADR-008**).

A score from this agent is one auditable component of urgency. It is **not** a triage judgement, and
no ranked list built on it alone should be described as clinically prioritised. See **ADR-004**.

## What it scores

`urgency_score ∈ [0, 1]` is a clinical-urgency score -- `0.0` = no physiological derangement,
`1.0` = maximum. The same polarity as the capacity agent's pressure score (ADR-003), so a higher
number always means more reason to prioritise, for either agent.

**NEWS2, scale 1, breathing air.** Six vitals, each scored per the published rubric, summed:
`rr`, `spo2`, `sbp`, `hr`, `avpu`, `temp`. No scale 2 and no +2 for supplemental oxygen -- the data
carries no oxygen-therapy field, so neither is reachable.

Two rubric properties the code depends on:

- **The reachable maximum is 17, not 20.** Temperature's top band is 2 while every other component's
  is 3, so the generator's own `min(s, 20)` cap can never bind -- which is why recomputation and the
  stored `news2` column agree exactly.
- **Systolic BP is not a descending ladder.** `>= 220` scores 3, the same as `<= 90`. A scorer
  written as one downward staircase gets the hypertensive tail wrong and no mid-range case notices.

**MTS is not scored** (ADR-004), and this is measured rather than assumed. **0 of 609 observations
carry a chief complaint**, so no presentation flowchart can be selected. And across the 500
referrals holding both a colour and a triage category, `mts_category` never leaves its CPC band's
permitted set -- Urgent is only ever red/orange, Semi-Urgent only yellow/orange, Routine only
yellow/blue/green -- and is uniform within it. Given CPC, the colour is a coin flip, so scoring it
would double-count the band the coordinator already orders by.

Reading and *citing* the colour without scoring it stays open and costs nothing; only letting it
move rank is the problem.

### Normalisation (ADR-006)

NEWS2 maps to `[0, 1]` by linear interpolation between calibrated escalation breakpoints in
[`urgency_agent/calibration.yml`](urgency_agent/calibration.yml), **not** by a flat `news2/17`. A
linear divide compresses the whole population into the bottom of the range -- the same distribution
defect min-max normalisation produced on the coordinator, where the median referral sat at 0.18 in
every band. The anchors are NEWS2's own escalation thresholds (0-4 low, 5-6 low-medium, 7+ high).

Interpolation *within* a band is required, not optional: a step function would give hundreds of
referrals identical scores and hand the coordinator nothing but ties to break on waiting time.

**The breakpoints are measured, not assumed** (ADR-006, revised 2026-09-08 after the check ran
against all 609 observations in data v1.1). The top anchor is NEWS2 **7**, not `NEWS2_MAX` (17):
NEWS2 never exceeds 7 in this data, so anchoring at 17 capped the highest real referral at 0.636 and
left the top 36% of the range dead. 7 is also the clinically correct ceiling — it is the
emergency-response threshold, and scores saturate above it.

**One limit no calibration can fix:** 51.1% of referrals score `news2=0` and tie at exactly 0.0, and
88.2% sit at or below 0.15. Patients whose six vitals are all normal have identical inputs, so no
monotone mapping separates them. For half the cohort this agent contributes nothing to ranking and
order falls entirely to waiting time. That is ADR-004's finding again, from a third direction.

### Refusals

Scoring is **refused** rather than defaulted to a low score in two cases. The coordinator depends on
this distinction: `coordinating-agent_20260906`'s ADR-008 excludes a referral with no urgency score
and reports it, explicitly refusing to default it to zero, because a missing score is missing
information, not low urgency.

| Case | Raised | Reported as |
|---|---|---|
| Specialty `0601` (paediatric), ADR-007 | `PaediatricReferralRefusedError` | `refused_paediatric` |
| No observation to score or cite (NFR5) | `InsufficientUrgencyEvidenceError` | `skipped` |

NEWS2 is validated for adults; specialty 0601's patients are aged 2-14 (`generate.py:405`), and an
adult-scaled score for a child is in range, ordinally plausible, and clinically meaningless.
`specialty_hipe` is the only paediatric signal available -- the context endpoint returns no patient
demographics.

Those two buckets are kept **separate** on purpose. A whole specialty leaving the ranked list is a
coverage statement; a missing observation is a data-quality incident. Reported together, "we do not
cover paediatrics" would be indistinguishable from "some rows are broken".

### Citations

One citation per NEWS2 vital -- **all six, including the ones scoring 0**. The score is a function of
all six, so citing only the abnormal ones would leave a reader unable to reconstruct it, and a normal
vital is evidence of normality rather than an absence of evidence.

Evidence keys are per-column: `{hospital_hipe}/{pathway_number}/{obs_datetime}/{column}`. The
timestamp must be **space-separated and percent-encoded**, not the ISO `T` form the JSON carries --
an evidence_key built from the unconverted form points at a graph node that was never loaded and
fails *silently*, degrading to `type: null` when a reader resolves it.

## Layout

```
urgency_agent/
  news2.py           the NEWS2 rubric -- thresholds, NEWS2_VITALS, NEWS2_MAX
  models.py          typed views over GET /referrals/.../context's clinical half
  calibration.py     Pydantic-validated breakpoints, loaded from calibration.yml
  calibration.yml    the committed scoring config -- edit this, not scoring.py, to retune
  scoring.py         normalisation, citations, score_urgency (the refusals live here)
  client.py          RetrievalClient -- the only way this agent talks to retrieval-service_20260904
  run.py             orchestration: score_referral (one), run_for_cohort (a hospital-day)
  config.py          Settings -- reads the same RETRIEVAL_* env vars as retrieval/
  __main__.py        CLI
tests/
  test_scoring.py            the scorer, pure functions, no I/O (Tier 1, strict TDD)
  test_calibration.py        calibration validation (Tier 1)
  test_client.py             RetrievalClient against a mocked transport (Tier 2)
  test_run.py                orchestration against an in-memory fake service (Tier 2)
  test_run_integration.py    genuine round trip against a *running* retrieval service --
                              skips cleanly if one isn't reachable
  test_config.py             bearer-token parsing
  test_main.py               CLI argument parsing smoke test
tools/
  mutation_check.py  breaks the scorer on purpose, asserts the right tests notice
```

## Running

```bash
cd urgency-agent
conda create -n urgency python=3.12 -y && conda activate urgency
pip install -r requirements-dev.txt

# Unit/mocked tests -- no infrastructure needed:
pytest

# Live round-trip tests too: bring the stack up from the repo root first
# (docker compose up -d db oxigraph retrieval), then:
pytest tests/test_run_integration.py
```

Reads `RETRIEVAL_BASE_URL` (default `http://localhost:8000`) and `RETRIEVAL_BEARER_TOKENS` (the same
root `.env` value `retrieval/` itself validates against) from the environment.

To score a hospital-day's whole cohort:

```bash
python -m urgency_agent --hospital 9004 --as-of-date 2026-08-30 --run-id run-0001
```

Exit code is 0 when nothing was skipped and no graph projection failed. **Paediatric refusals do not
affect the exit code** -- a run that refuses every 0601 referral and scores the rest has done exactly
its job.

## Quality gates

Run these as four separate commands, never chained with `&&`: a deliberately failing test makes
pytest exit non-zero, and everything after the first `&&` then silently never runs.

```bash
pytest tests/ -q
ruff format --check .
ruff check .
mypy --config-file mypy.ini --explicit-package-bases .
python tools/mutation_check.py
```

`tools/mutation_check.py` is the fifth gate and the one worth understanding: 100% coverage means
every line executed, not that any behaviour is correct. It breaks the scorer six ways and asserts
that **exactly** the tests which should notice do -- so both a hole in the tests and coupling between
them are reported. Run it after touching `news2.py`, `scoring.py` or `run.py`.
