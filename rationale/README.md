# Rationale Layer

Graph-backed rationale generation for ranked triage placements.

This component explains **why a referral is in a ranked position** by reading the
retrieval service's resolved graph evidence. It does not score, rank, query
Postgres, query SPARQL directly, diagnose, schedule, admit, or make a clinical
decision.

## What Was Done

The `rationale/` package now contains:

| File | Purpose |
|---|---|
| `client.py` | Calls the retrieval service with the shared bearer token. |
| `config.py` | Reads the repo-root `.env` and finds retrieval settings. |
| `models.py` | Defines `EvidenceItem`, `EvidencePack`, and `Rationale`. |
| `evidence_pack.py` | Converts `GET /decisions/...` responses into evidence packs. |
| `render.py` | Deterministically renders concise rationale text from cited evidence. |
| `cli.py` / `__main__.py` | Runs rationale generation from the command line. |
| `tests/` | Unit tests for packing, rendering, config, client, and CLI behavior. |

The first version is deliberately deterministic. An LLM can be added later as a
wording layer, but only after this evidence pack exists; the model should receive
the evidence bundle and rewrite it, not decide which evidence matters.

## How It Works

```text
GET /decisions/{hospital_hipe}/{as_of_date}
or, when --pathway is passed:
GET /evidence/{hospital_hipe}/{as_of_date}/{pathway_number}
        |
        v
resolved placement evidence from retrieval-service_20260904
        |
        v
EvidencePack
        |
        v
deterministic rationale text
```

Every evidence sentence includes the cited graph node IRI returned by the
retrieval service. That keeps the rationale auditable: each claim can be traced
back to the node that supports it.

## Rationale Layer Change

The `--pathway` mode now calls the single-placement evidence endpoint directly instead of loading the
whole hospital-day decision and filtering locally. This avoids timeouts on larger ranked lists, because
retrieval resolves evidence only for the requested pathway.

The upstream coordinator/retrieval path was also aligned for rationale evidence: retrieval exposes
`referral_state_valid_from` in cohort rows, and the coordinator uses it for `referral_state` citations.
That matches the KG's `ReferralState` IRI template and lets CPC/CRT rationale evidence resolve.

## Prerequisites

From the repo root:

```bash
make up
make load
```

The root `.env` must include:

```bash
RETRIEVAL_PORT=8000
RETRIEVAL_BEARER_TOKENS=<your_local_bearer_token>
RETRIEVAL_DB_URL=postgresql://retrieval_rw:<password>@db:5432/triage
```

The retrieval service must already have decisions to explain. A typical flow is:

```bash
# 1. Run urgency and capacity agents for the same run_id.
cd urgency-agent
python -m urgency_agent --hospital 9004 --as-of-date 2026-08-30 --run-id run-0001

cd ../capacity-agent
python -m capacity_agent --hospital 9004 --as-of-date 2026-08-30 --run-id run-0001

# 2. Post a coordinator decision.
cd ../
python -m coordinator \
  --hospital 9004 \
  --as-of 2026-08-30 \
  --run-id run-0001 \
  --capacity-direction pressure
```

## Run Rationale Generation

Install local dependencies:

```bash
python3 -m venv .venv-rationale
source .venv-rationale/bin/activate
pip install -r rationale/requirements-dev.txt
```

Render every placement in a hospital-day decision:

```bash
python -m rationale --hospital 9004 --as-of 2026-08-30
```

Render one placement:

```bash
python -m rationale \
  --hospital 9004 \
  --as-of 2026-08-30 \
  --pathway PW-9004-000123
```

Run the same CLI through Docker Compose:

```bash
docker compose run --rm rationale \
  --hospital 9004 \
  --as-of 2026-08-30 \
  --pathway PW-9004-000123
```

Return machine-readable output:

```bash
python -m rationale --hospital 9004 --as-of 2026-08-30 --format json
```

## Test It

```bash
python -m pytest rationale/tests/ -q
python -m ruff check --config rationale/ruff.toml rationale/
python -m mypy --config-file rationale/mypy.ini rationale
```

The tests do not require Postgres, Oxigraph, or a running retrieval service.
HTTP calls are mocked at the client boundary.
