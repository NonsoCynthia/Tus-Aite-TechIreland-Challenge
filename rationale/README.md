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
| `app/main.py` | FastAPI wrapper for frontend/backend integration. |
| `client.py` | Calls the retrieval service with the shared bearer token. |
| `config.py` | Reads the repo-root `.env` and finds retrieval settings. |
| `models.py` | Defines `EvidenceItem`, `EvidencePack`, and `Rationale`. |
| `evidence_pack.py` | Converts retrieval decision/evidence responses into evidence packs. |
| `render.py` | Deterministically renders technical audit text or clinician prose from cited evidence. |
| `llm_render.py` | Renders the same evidence pack via the OpenAI Agents SDK -- an alternative engine, not a replacement. See "LLM Rendering Engine" below. |
| `../evaluation/rationale_judge.py` | Optional explanation judge for checking rationale faithfulness, safety language and readability against the cited evidence pack. |
| `cli.py` / `__main__.py` | Runs rationale generation from the command line. |
| `tests/` | Unit tests for packing, rendering, config, client, CLI behavior, LLM-engine guardrails, and API behavior. |

The default engine is deterministic template rendering. An `llm` engine (below) is
also available: it receives this same evidence bundle and rewrites it as prose --
it does not decide which evidence matters, matching this package's original design
intent.

## LLM Rendering Engine

`--engine llm` / `?engine=llm` calls the OpenAI Agents SDK instead of the template
renderer, using the exact same `EvidencePack` as input. See ADR-010
(`conductor/tracks/explainable-agent-based-triage_20260828/decisions.md`) for why
OpenAI rather than the `claude-opus-5` tech-stack.md originally named, and for the
evidence-faithfulness guardrail this engine enforces in code.

Requires `OPENAI_API_KEY` (and optionally `OPENAI_MODEL`, default `gpt-4.1-mini`)
in the root `.env` -- **never commit a real value**. The deterministic engine
(the default) needs neither.

```bash
python -m rationale --hospital 9004 --as-of 2026-08-30 --pathway PW-9004-000123 \
  --style clinician --engine llm
```

```bash
curl "http://localhost:8010/rationale/9004/2026-08-30/PW-9004-000123?style=clinician&engine=llm"
```

**Evidence-faithfulness is enforced in code, not trusted from the prompt alone.**
The model must return `citation_iris` covering exactly the evidence pack's own
IRIs -- the same contract the deterministic renderer already guarantees by
construction. A mismatch retries once, then raises `RationaleGuardrailError`
(mapped to HTTP `503` by the API) rather than silently returning ungrounded text.
A caller wanting a rationale regardless should catch that and fall back to
`render.render_rationale`.

## Explanation Judging

The evaluation package includes an optional rationale judge:

```bash
make rationale-judge
make rationale-judge RATIONALE_JUDGE_ENGINE=llm
```

The local default is a deterministic heuristic over a sample evidence/rationale
pair. `RATIONALE_JUDGE_ENGINE=llm` uses AI-as-judge with structured output and
requires `OPENAI_API_KEY`. The judge is intentionally bounded: it reviews
whether explanation text is faithful to cited evidence, avoids diagnostic or
system-action language, mentions urgency/capacity/CPC-CRT evidence, and is
readable. It does not judge whether the underlying agent scores or rankings are
clinically correct.

The `agents` package import is lazy (inside `llm_render._default_agent_runner`),
so the deterministic engine, and every test except `tests/test_llm_render.py`'s
own mocked-transport tests, never require `openai-agents` to be installed.

## Current Implementation State

Implemented:

- CLI rationale generation with `python -m rationale` or `make rationale-run`.
- Docker Compose support for the CLI through the `rationale` service.
- HTTP API support through the `rationale-api` service for frontend/backend integration.
- `technical` output for audit/debug review, including cited graph node IRIs and resolved
  properties.
- `clinician` output for readable prose, hiding graph node IDs from the visible text while keeping
  `citation_iris` in JSON responses for traceability.
- Direct single-placement rationale lookup through retrieval's
  `GET /evidence/{hospital}/{date}/{pathway}` endpoint, avoiding full-decision timeouts.
- CPC/CRT evidence resolution aligned with the KG by using `referral_state_valid_from` for
  `ReferralState` citations.
- Unit tests for client behavior, evidence packing, rendering, CLI behavior, and the API wrapper.

- An `llm` render engine (OpenAI Agents SDK) as an alternative to the deterministic
  renderer, selectable via `--engine llm` / `?engine=llm`, with a code-enforced
  evidence-faithfulness guardrail. See "LLM Rendering Engine" above and ADR-010.

Not implemented yet:

- Prompt-cached wording, or a Message Batches-style bulk path, for the `llm` engine.
- A clinician web UI.
- User-facing authentication/authorization on the rationale API. The API is currently intended for
  local/internal Compose use and calls retrieval with the shared retrieval bearer token.

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
        |
        +--> CLI output
        |
        +--> HTTP JSON for frontend integration
```

The technical style includes the cited graph node IRI returned by the retrieval service in the
visible text. The clinician style hides those node IDs from the prose, but JSON output and API
responses still include `citation_iris` so each claim can be traced back to the supporting graph
node.

## Rationale Layer Change

The `--pathway` mode now calls the single-placement evidence endpoint directly instead of loading the
whole hospital-day decision and filtering locally. This avoids timeouts on larger ranked lists, because
retrieval resolves evidence only for the requested pathway.

The CLI also supports switchable wording styles:

| Style | Use |
|---|---|
| `technical` | Default. Shows grouped evidence nodes and resolved properties for audit/debug use. |
| `clinician` | Plain prose for clinician review, without evidence-node IDs in the visible text. |

The upstream coordinator/retrieval path was also aligned for rationale evidence: retrieval exposes
`referral_state_valid_from` in cohort rows, and the coordinator uses it for `referral_state` citations.
That matches the KG's `ReferralState` IRI template and lets CPC/CRT rationale evidence resolve.

## Collaborator Notes

The rationale layer is implemented as a deterministic Python package with both a CLI and a small
FastAPI wrapper. It reads resolved evidence from retrieval, builds one evidence pack per ranked
placement, and renders either technical audit output or clinician-facing prose. The default style is
`technical`; pass `--style clinician` for plain prose suitable for review.

What has been done:

- Added the `rationale/` package with a retrieval client, evidence-pack models, renderer, CLI, tests,
  and this README.
- Added `rationale/Dockerfile`, a `docker compose run --rm rationale ...` workflow for teammates,
  and a `rationale-api` Compose service for frontend/backend integration.
- Changed rationale `--pathway` mode to call `GET /evidence/{hospital}/{date}/{pathway}` directly, so
  it avoids full-decision timeouts on larger ranked lists.
- Changed retrieval cohort output to include `referral_state_valid_from`.
- Changed coordinator `referral_state` citations to use `referral_state_valid_from`, so CPC/CRT
  rationale evidence resolves to real `ReferralState` KG nodes.
- Added switchable output styles: `technical` for audit/debug output with evidence nodes, and
  `clinician` for readable prose grounded in the same cited evidence but without evidence-node IDs in
  the visible text.

Known local-data note: decisions already written before this change may still contain stale citations
in old run graphs. New coordinator runs cite the corrected `ReferralState` date.

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

Recommended from the repo root:

```bash
make rationale-run \
  HOSPITAL=9001 \
  AS_OF=2026-08-30 \
  PATHWAY=PW-9001-000007 \
  RATIONALE_STYLE=clinician
```

Render technical audit output instead:

```bash
make rationale-run \
  HOSPITAL=9001 \
  AS_OF=2026-08-30 \
  PATHWAY=PW-9001-000007 \
  RATIONALE_STYLE=technical
```

Use the `llm` engine (requires `OPENAI_API_KEY` in the root `.env`):

```bash
make rationale-run \
  HOSPITAL=9001 \
  AS_OF=2026-08-30 \
  PATHWAY=PW-9001-000007 \
  RATIONALE_STYLE=clinician \
  RATIONALE_ENGINE=llm
```

Run the full local scoring/ranking/rationale sequence:

```bash
make demo-run \
  HOSPITAL=9001 \
  AS_OF=2026-08-30 \
  RUN_ID=run-9001-rationale-001 \
  PATHWAY=PW-9001-000007 \
  RATIONALE_STYLE=clinician
```

Direct local Python usage is also supported. Install dependencies:

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

Render clinician-facing prose:

```bash
python -m rationale \
  --hospital 9004 \
  --as-of 2026-08-30 \
  --pathway PW-9004-000123 \
  --style clinician
```

Run the same CLI through Docker Compose:

```bash
docker compose run --rm rationale \
  --hospital 9004 \
  --as-of 2026-08-30 \
  --pathway PW-9004-000123
```

Compose with clinician-facing prose:

```bash
docker compose run --rm rationale \
  --hospital 9004 \
  --as-of 2026-08-30 \
  --pathway PW-9004-000123 \
  --style clinician
```

Return machine-readable output:

```bash
python -m rationale --hospital 9004 --as-of 2026-08-30 --format json
```

## Run As An HTTP API

Use the API when another application, such as the planned clinician frontend, needs rationale text
over HTTP.

Start the service from the repo root:

```bash
make rationale-api-up
```

The API listens on `http://localhost:${RATIONALE_PORT:-8010}`. The main endpoint is:

```http
GET /rationale/{hospital_hipe}/{as_of_date}/{pathway_number}?style=clinician
```

Example:

```bash
curl "http://localhost:${RATIONALE_PORT:-8010}/rationale/9001/2026-08-30/PW-9001-000007?style=clinician"
```

Response shape:

```json
{
  "hospital_hipe": "9001",
  "as_of_date": "2026-08-30",
  "pathway_number": "PW-9001-000007",
  "style": "clinician",
  "text": "Referral PW-9001-000007 is shown for clinician review...",
  "citation_iris": [
    "referral-state/9001/PW-9001-000007/2026-08-25"
  ]
}
```

Example clinician response text:

```text
Referral PW-9001-000007 is shown for clinician review. This is decision support; clinician sign-off is required.
The recorded urgency score is 0.225 on a 0 to 1 scale, which is in the lower range. It is supported by the cited oxygen saturation observation.
Capacity evidence reports the relevant ward was 83.52 percent occupied, with 15 beds free; and 1800 outpatients on 2026-08-28 had 12 of 25 slots available.
CPC/CRT evidence records the referral state was triaged from 2026-08-25 and did not record high clinical or social needs; and the applicable timeframe rule states: A semi-urgent referral should be seen within 13 weeks.
```

Example technical response text:

```text
Ranked placement. Referral PW-9001-000007. This is decision support; clinician sign-off is required.
Urgency evidence: Score score/run-9001-rationale-001/9001/PW-9001-000007/urgency: scoreValue=0.22499999999999998, method=urgency-news2-v1, agentVersion=urgency-agent-0.1.0, cites=obs/9001/PW-9001-000007/2026-08-16%2009%3A16%3A00/spo2, prov:wasGeneratedBy=activity/run-9001-rationale-001/urgency, scored=referral/9001/PW-9001-000007.
Capacity evidence: BedStatus bed-status/9001/W-9001-04/2026-08-30%2020%3A00%3A00: occupancyPct=83.52, surgeCapacityInUse=0, delayedTransfersOfCare=2, awaitingAdmissionOver24h=0, awaitingAdmissionOver9h=0, freeBeds=15. ClinicSession clinic-session/9001/CL-9001-1800/2026-08-28: slotsTotal=25, slotsBooked=13, slotsAvailable=12, clinicName=1800 outpatients, sessionDate=2026-08-28, sessionOf=service/9001/1800.
CPC/CRT evidence: ReferralState referral-state/9001/PW-9001-000007/2026-08-25: triageStatus=triaged, hasHighClinicalOrSocialNeeds=false, referredToService=service/9001/1800, stateOf=referral/9001/PW-9001-000007, validFrom=2026-08-25. Rule rule/RULE-CRT-SEMI: appliesTo=triaged_semi_urgent, statement=A semi-urgent referral should be seen within 13 weeks, thresholdDays=91.
```

Stop it with:

```bash
make rationale-api-down
```

## Test It

```bash
make rationale-check
```

Equivalent direct commands:

```bash
python -m pytest rationale/tests/ -q
python -m ruff check --config rationale/ruff.toml rationale/
python -m mypy --config-file rationale/mypy.ini rationale
```

The tests do not require Postgres, Oxigraph, or a running retrieval service.
HTTP calls are mocked at the client boundary.
