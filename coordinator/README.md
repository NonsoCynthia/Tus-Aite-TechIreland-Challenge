# Coordinating Agent

Ranks one hospital's cohort for one day and writes the decision through the retrieval service.
Implements `explainable-agent-based-triage_20260828` FR3 (parent spec), carved out as its own track
so it could be built and merged independently of the urgency and capacity agents. Deterministic --
no LLM is involved anywhere in this agent; the same inputs always produce the same ranking, byte for
byte (NFR4). Per ADR-002, this agent never touches Postgres or the graph directly -- the retrieval
service is its only integration point, in both directions.

**What it does:** fetches a cohort, gathers urgency/capacity scores, resolves CPC bands
(`severity_rank`, never the raw `cpc` code -- ADR-003), computes a within-band priority from
urgency and wait (ADR-005), sorts by the full key, runs CPC/CRT/ordering rule checks, and posts one
cited, explained decision.

**What it deliberately does not do:** it never overrides, schedules, admits, triages, or otherwise
acts on a patient -- it ranks and explains, per `conductor/product-guidelines.md`'s verb rules. It
does not accept or intake referrals (`POST /referrals`), does not write overrides (`POST
/overrides`), does not retry after a partial write, and carries no LLM-generated rationale (that's
the parent track's separate FR4 layer -- `rationale_summary` here is the coordinator's own short,
deterministic note).

Full spec, plan and ADRs:
[`conductor/tracks/coordinating-agent_20260906/`](../conductor/tracks/coordinating-agent_20260906/).

## Running

This agent has no server process -- it is a CLI, run once per hospital-day:

```bash
# From the repo root. Reads RETRIEVAL_BEARER_TOKENS and RETRIEVAL_PORT from
# the repo-root .env -- same one the retrieval service itself uses.
python -m coordinator \
  --hospital 9004 \
  --as-of 2026-08-30 \
  --run-id run-2026-08-30-001 \
  --capacity-direction pressure \
  --dry-run
```

`--capacity-direction` is **required, with no default**, and the CLI refuses to start without it.
`capacity_score` is a 0-1 float whose direction (does 1.0 mean "most capacity free" or "maximum
pressure"?) is owned by the capacity agent's author, not this one -- read backwards, the whole
system's behaviour under load inverts while every number stays in range and the ranking stays
superficially plausible, and no test catches it without the convention being stated. A loud startup
failure is the cheapest version of that problem; the alternative is a silently inverted priority
system. See ADR-007.

`--dry-run` prints the assembled decision instead of posting it, so a ranking can always be
inspected before anything is written.

## Flags

| Flag | Default | Changes |
|---|---|---|
| `--hospital` | *(required)* | Which hospital's cohort to rank. |
| `--as-of` | *(required)* | Which hospital-day to rank. |
| `--run-id` | *(required)* | Which agent run the scores come from -- ties this decision to a specific urgency/capacity run. |
| `--capacity-direction` | *(required, no default)* | `availability` (`scarcity = 1 - capacity`) or `pressure` (`scarcity = capacity`). Inverts the direction of every capacity-driven weighting in the decision (ADR-005/ADR-007). Recorded in `coordinator_version`. |
| `--score-source` | `live` | `live` calls `GET /runs/.../scores`; `fixture` uses a deterministic, made-up score generator for development when the urgency/capacity agents haven't written anything yet (ADR-008). Recorded in `coordinator_version` so a decision written from stub scores can never be mistaken for a real one. |
| `--legacy-citations` | off | Switches citation construction to the ADR-009 fallback (see below) -- the only mode that validates against the retrieval service **today**. |
| `--alpha-min` | `0.5` | Lower bound on `alpha`, the urgency/wait weight -- urgency never counts for less than waiting time even at zero scarcity. |
| `--alpha-max` | `0.9` | Upper bound on `alpha` -- waiting time never drops out of the ordering entirely even at maximum scarcity. |
| `--dry-run` | off | Prints the assembled decision instead of posting it. Nothing is written. |

`alpha` is otherwise computed from cohort-level scarcity (ADR-005) and is identical for every
referral in one decision -- no flag sets it directly.

## Integration points

Per ADR-002, all three are HTTP calls to the retrieval service; this agent never queries Postgres or
Oxigraph itself.

| Direction | Endpoint | Purpose |
|---|---|---|
| input | `GET /hospitals/{hospital_hipe}/cohort/{as_of_date}` | Who is on the list, with CPC and CRT breach. |
| input | `GET /runs/{run_id}/hospitals/{hospital_hipe}/scores` | Urgency/capacity scores already written for this run (skipped entirely with `--score-source fixture`). |
| output | `POST /decisions` | The ranked list, atomically, with citations and rule checks. |

All four documented `POST /decisions` responses are handled distinctly: `200` ok; `207` Postgres
committed but the graph projection failed -- reported as a **distinct, non-zero exit code**, never
as success; `400` Postgres rejected the payload; `422` validation failed before either store was
touched.

## Things this README needs you to know before you trust any output

- **ADR-007 is open.** The capacity sign convention (`availability` vs. `pressure`) has not been
  confirmed with the capacity agent's author. Until it is, no decision this agent writes should be
  treated as final -- it may be running under the wrong convention, silently.
- **ADR-011 is open.** The sort key puts CRT breach above priority as a hard tier: within a band,
  every breached referral outranks every non-breached one at any score values. This was an
  incidental consequence of combining an older tie-break rule with a later scoring change, not a
  decision anyone made on purpose, and it is referred to the responsible-AI/compliance lead and to
  clinical input, unresolved.
- **ADR-009: the default citation mode does not validate today.** The coordinator's real evidence
  for the `urgency`/`timeframe` citation roles is a `Score` node and a `ReferralState`, neither of
  which is yet an accepted `evidence_type` in the retrieval service's schema. A change request is
  open. `--legacy-citations` is the working path in the meantime -- it validates today, at the cost
  of one hop of provenance (it cites the urgency agent's own evidence directly, and omits the
  `timeframe` role entirely).
- **One test fails on purpose.** `test_citation_contract.py::test_role_evidence_types_are_valid_evidence_types`
  fails today and is meant to -- it is the tracking mechanism for the ADR-009 change request, not a
  bug. Do not "fix" it by weakening the assertion; it turns green on its own once the retrieval
  service's `EvidenceType` is widened. (`test_decision.py`'s
  `test_assembled_payload_fails_real_decision_in_validation_today` is the same signal from the
  opposite side -- it passes today and is expected to go red on the same event, which is the
  handoff working as intended, not a regression.)

## Tests

```bash
# From the repo root.
python -m pytest coordinator/tests/ -v

python -m ruff check --config coordinator/ruff.toml coordinator/
python -m ruff format --config coordinator/ruff.toml --check coordinator/

# Unlike retrieval/ (which cd's into its own directory and runs `mypy app`),
# this is run from the repo root and points at the coordinator/ package as a
# whole rather than just coordinator/app/, so it type-checks coordinator/tests/
# too, not only the 8 app modules:
python -m mypy --config-file coordinator/mypy.ini --explicit-package-bases coordinator
```

Tier 1 files (band resolution, priority, the full sort key, rule checks) carry strict TDD tests at
≥80% coverage; Tier 2 (citations, decision assembly) at ≥60%; the CLI is Tier 3 -- one smoke test
proving it runs end to end without raising, not an exhaustive suite. No test performs network I/O
(NFR5) -- the retrieval service is faked at the seam everywhere it would otherwise be called.
