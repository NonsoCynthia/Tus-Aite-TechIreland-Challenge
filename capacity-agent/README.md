# Capacity Agent

Deterministic constraint reasoning over ward bed-status and clinic-session capacity for one
referral's specialty (`conductor/tracks/explainable-agent-based-triage_20260828/spec.md` FR2). Per
ADR-002, this agent never queries SPARQL or Postgres directly -- it only ever calls
[`retrieval-service_20260904`](../retrieval/README.md): `GET /referrals/{hospital_hipe}/{pathway_number}/context`
to gather input, `POST /scores` to write output.

Full spec/plan: [`conductor/tracks/explainable-agent-based-triage_20260828/`](../conductor/tracks/explainable-agent-based-triage_20260828/)
(Phase 2).

## What it scores

`capacity_score ∈ [0, 1]` is a resource-**pressure** score, the same polarity as the urgency agent's
score: `0.0` = ample capacity, no constraint pressure; `1.0` = severe constraint pressure. This
interpretation isn't specified by the proposal or spec.md -- it's a documented design decision (see
`conductor/tracks/explainable-agent-based-triage_20260828/decisions.md`), chosen so both agents'
scores share one polarity for the coordinator to combine.

Two independently-weighted signals, calibrated in [`capacity_agent/calibration.yml`](capacity_agent/calibration.yml)
(committed, inspectable config, not hidden constants -- `conductor/product.md`'s Calibration
Configuration principle):

- **`ward_pressure`** -- the specialty's primary ward's latest `BedStatus`: a continuous occupancy
  component plus a boolean escalation component over `surge_capacity_in_use`,
  `delayed_transfers_of_care`, `awaiting_admission_over_24h`, and `outliers` -- the fields
  `graph-foundation_20260826` found actually carry overcrowding, since `bs_occupancy_range` caps
  `occupancy_pct` at 100 by construction.
- **`clinic_pressure`** -- the specialty's most recent `ClinicSession`'s booked/total ratio (a
  clinic with zero sessions scheduled scores as maximal pressure, not a 0/0 crash).

The two combine by calibrated weight, renormalised over whichever signal is actually available. If a
specialty has neither a ward bed-status snapshot nor a clinic session to cite, scoring is refused
(`InsufficientCapacityEvidenceError`) rather than writing a score with nothing to cite (NFR5;
`POST /scores`'s `citations` field requires at least one).

## Layout

```
capacity_agent/
  calibration.py    Pydantic-validated weights, loaded from calibration.yml
  calibration.yml    the committed scoring config -- edit this, not scoring.py, to retune
  models.py          typed views over GET /referrals/.../context's response
  scoring.py         the deterministic scorer (ward_pressure, clinic_pressure, score_capacity)
  client.py          RetrievalClient -- the only way this agent talks to retrieval-service_20260904
  run.py             orchestration: score_referral (one), run_for_cohort (a whole hospital-day)
  config.py          Settings -- reads the same RETRIEVAL_BEARER_TOKENS/RETRIEVAL_PORT as retrieval/
  __main__.py        CLI: `python -m capacity_agent --hospital ... --as-of-date ... --run-id ...`
tests/
  test_calibration.py        calibration validation (Tier 1)
  test_scoring.py            the scorer, pure functions, no I/O (Tier 1, strict TDD)
  test_client.py             RetrievalClient against a mocked transport (Tier 2)
  test_run.py                orchestration against an in-memory fake service (Tier 2)
  test_run_integration.py    genuine round trip against a *running* retrieval service --
                              skips cleanly if one isn't reachable, see its own docstring
  test_main.py               CLI argument parsing smoke test
```

## Running

```bash
cd capacity-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

# Unit/mocked tests -- no infrastructure needed:
pytest

# Live round-trip test too: bring up the stack from the repo root first
# (docker compose up -d db oxigraph retrieval), then:
pytest tests/test_run_integration.py

ruff check .
mypy capacity_agent tests
```

Reads `RETRIEVAL_BASE_URL` (default `http://localhost:8000`) and `RETRIEVAL_BEARER_TOKENS` (the
same root `.env` value `retrieval/` itself validates against) from the environment.

To score a hospital-day's whole cohort:

```bash
python -m capacity_agent --hospital 9001 --as-of-date 2026-08-30 --run-id run-0001
```

From the repo root, collaborators can run the same job through the root `Makefile` without setting up
a local Python environment:

```bash
make capacity-run HOSPITAL=9001 AS_OF=2026-08-30 RUN_ID=run-0001
```
