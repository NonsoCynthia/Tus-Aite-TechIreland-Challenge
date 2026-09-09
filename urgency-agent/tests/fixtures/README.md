# Fixtures

**Nothing is captured yet.** This file records what to capture and why, so the
real-data tests in `test_scoring.py` have a documented target rather than a
hand-built assumption. Those tests skip cleanly while the JSON files are absent
(see `_load_fixture` in that module).

`BUILDING_AN_AGENT_WITH_CONDUCTOR.md` Step 7 is the reason this matters: on the
coordinator, Phase 2's tests passed, coverage was 100%, the mutation check
succeeded -- and the code was still broken, because the hand-built fixtures made
exactly the same wrong assumption as the implementation. **At least one test per
module has to meet a real response.**

## What to capture

Bring the stack up from the repo root first:

```bash
docker compose up -d db oxigraph retrieval
```

Read the token from the repo-root `.env` (`RETRIEVAL_BEARER_TOKENS`, first
comma-separated value). Never commit it, never print it.

### 1. `context_adult.json` -- the ordinary path

Any non-paediatric referral (specialty **not** `0601`). `PW-9004-000286`
(specialty 1800) is known to exist from the coordinator's own cohort fixture:

```bash
TOKEN=$(grep -m1 '^RETRIEVAL_BEARER_TOKENS=' ../../.env | cut -d= -f2- | cut -d, -f1)
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/referrals/9004/PW-9004-000286/context" \
  > context_adult.json
```

What the NEWS2 tests need from it:

- **`observations[]`** with `hr`, `sbp`, `rr`, `temp`, `spo2`, `avpu` populated --
  every input NEWS2 scale 1 takes.
- **`observations[].news2`** -- the generator's own stored value, computed from
  those same vitals by `dataset/generator/generate.py:63`. This is the oracle:
  `score_news2()` recomputing from raw vitals must equal it exactly, on every
  observation in the file. A mismatch means our threshold boundaries are wrong,
  and no hand-built fixture would ever tell us that.
- **`observations[].obs_datetime`** -- needed verbatim to build citation
  `evidence_key`s, and the format matters (see the warning below).

### 2. `context_paediatric.json` -- the refusal path

A referral in specialty **`0601`**, to exercise ADR-007's refusal. Find one:

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/hospitals/9004/cohort/2026-08-30" \
| python3 -c "import json,sys; print([r['pathway_number'] for r in json.load(sys.stdin)['referrals'] if r['specialty_hipe']=='0601'][:5])"
```

Expect `mts_category` to be `""` and the colour to sit in `icts_category`
instead -- that asymmetry is real (`generate.py:554-556`), not a capture error.

## Timestamp format -- read before writing an evidence_key

`obs_datetime` arrives in the JSON as ISO `T`-separated (`2026-08-16T09:16:00`),
but the graph node Morph-KGC built from Postgres is **space**-separated
(`2026-08-16 09:16:00`), then percent-encoded. An `evidence_key` built from the
unconverted ISO form points at a node that was never loaded, and it fails
*silently* -- degrading to `type: null` when a reader resolves it, not raising.
The capacity agent hit this and documented it in `_bed_status_evidence_key`
(`capacity-agent/capacity_agent/scoring.py`); we take the same conversion.

Observation keys are also **per-column**, not per-row
(`retrieval/app/schemas.py:68-83`):
`{hospital_hipe}/{pathway_number}/{obs_datetime}/{column}`. Citing a NEWS2 score
therefore means one citation per vital actually used.

## Recapturing

Re-run the `curl`s above against a live `retrieval` instance, then re-run
`pytest tests/test_scoring.py -k real` and update the observed counts in this
file if they have moved.
