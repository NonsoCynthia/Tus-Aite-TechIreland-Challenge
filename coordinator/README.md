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

## Documentation

| | |
|---|---|
| [docs/RUNNING_THE_COORDINATOR.md](docs/RUNNING_THE_COORDINATOR.md) | **Start here.** Everything needed to go from a fresh clone to a ranked, inspectable decision |
| [docs/HOW_THE_COORDINATOR_WAS_BUILT.md](docs/HOW_THE_COORDINATOR_WAS_BUILT.md) | The tech stack and why each piece, the design decisions, what the build disproved, what is still open |
| [docs/BUILDING_AN_AGENT_WITH_CONDUCTOR.md](docs/BUILDING_AN_AGENT_WITH_CONDUCTOR.md) | The process this agent was built with, for the urgency/capacity/rationale agents to follow |

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

Collaborators can run the posted-decision path through the root `Makefile` without setting up a local
Python environment:

```bash
make coordinator-run \
  HOSPITAL=9001 \
  AS_OF=2026-08-30 \
  RUN_ID=run-0001 \
  CAPACITY_DIRECTION=pressure
```

`--capacity-direction` is **required, with no default**, and the CLI refuses to start without it.
`capacity_score` is a 0-1 float whose direction (does 1.0 mean "most capacity free" or "maximum
pressure"?) is a choice, not a law of nature -- read backwards, the whole system's behaviour under
load inverts while every number stays in range and the ranking stays superficially plausible, and no
test catches it without the convention being stated. A loud startup failure is the cheapest version
of that problem; the alternative is a silently inverted priority system.

**Pass `pressure`.** ADR-007 is resolved: the capacity agent documents `capacity_score` as a
resource-pressure score (`0.0` = ample capacity, `1.0` = severe constraint pressure), so both
agents' scores share one polarity. The flag stays required regardless -- an explicit choice
recorded per decision is worth keeping even now that the convention is known.

`--dry-run` prints the assembled decision instead of posting it, so a ranking can always be
inspected before anything is written.

## Flags

| Flag | Default | Changes |
|---|---|---|
| `--hospital` | *(required)* | Which hospital's cohort to rank. |
| `--as-of` | *(required)* | Which hospital-day to rank. |
| `--run-id` | *(required)* | Which agent run the scores come from -- ties this decision to a specific urgency/capacity run. |
| `--capacity-direction` | *(required, no default)* | `availability` (`scarcity = 1 - capacity`) or `pressure` (`scarcity = capacity`). Inverts the direction of every capacity-driven weighting in the decision (ADR-005/ADR-007). Recorded in `coordinator_version`. **Pass `pressure`** against this system's capacity agent (confirmed, ADR-007). |
| `--score-source` | `live` | `live` calls `GET /runs/.../scores`; `fixture` uses a deterministic, made-up score generator for development when the urgency/capacity agents haven't written anything yet (ADR-008). Recorded in `coordinator_version` so a decision written from stub scores can never be mistaken for a real one. |
| `--legacy-citations` | off | Switches citation construction to the ADR-009 fallback (see below) -- cites the urgency agent's own evidence directly rather than its `Score` node. Both modes validate against the retrieval service today (ADR-009 resolved). |
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

## Rationale Layer Change

The coordinator now uses `referral_state_valid_from` from `GET /hospitals/.../cohort/...` when building
`referral_state` citations for the timeframe rationale. It no longer uses `referral_date` for that
citation.

The reason is graph identity: a `ReferralState` node is named as
`referral-state/{hospital_hipe}/{pathway_number}/{valid_from}`. `referral_date` is the date the
referral was made; it may not be the date the current waiting-list state began. Using
`referral_state_valid_from` means rationale can dereference the exact state node cited by the ranked
placement.

## Things this README needs you to know before you trust any output

- **ADR-007 is resolved: `pressure`.** The capacity agent documents `capacity_score` as a
  resource-pressure score, confirmed in `capacity-agent/capacity_agent/scoring.py` and
  `capacity-agent/README.md` line 14. `--capacity-direction` stays required -- an explicit choice
  recorded per decision is worth keeping -- but a decision written under `pressure` no longer needs
  to be treated as provisional on this point.
- **ADR-011 is open.** The sort key puts CRT breach above priority as a hard tier: within a band,
  every breached referral outranks every non-breached one at any score values. This was an
  incidental consequence of combining an older tie-break rule with a later scoring change, not a
  decision anyone made on purpose, and it is referred to the responsible-AI/compliance lead and to
  clinical input, unresolved.
- **ADR-009 is resolved, but not as originally requested.** The retrieval service did not widen
  `EvidenceType`; it added a separate, wider `DecisionEvidenceType` for placement citations (the
  original five clinical values plus `"score"`, `"referral_state"`, and `"rule"`), while
  `EvidenceType` stays at five values for score citations (Postgres' `ac_evidence_type_valid` CHECK
  requires it). Default-mode citations validate today. `--legacy-citations` still works and is still
  a legitimate choice, at the cost of one hop of provenance -- it is just no longer the *only* mode
  that validates.

## Pending decisions

Only ADR-011 remains open below; ADR-007 and ADR-009 are recorded here for the historical
reasoning, now resolved. None of the three was, or is, an engineering task. Condensed from
[`docs/HOW_THE_COORDINATOR_WAS_BUILT.md` §7](docs/HOW_THE_COORDINATOR_WAS_BUILT.md#7-what-is-still-open)
— see there and
[the track's `decisions.md`](../conductor/tracks/coordinating-agent_20260906/decisions.md) for the
full reasoning.

**ADR-007 — capacity sign convention — RESOLVED: `pressure`**
- Owned by: the capacity agent's author.
- Meanwhile *(while open)*: `--capacity-direction` was required with no default; every decision
  recorded which convention it used.
- Risk that was open: read backwards, urgency would be weighted *least* when the hospital is under
  most pressure, with every number still in range and every ranking still plausible.
- Resolved: the capacity agent documents `pressure`, confirmed in `capacity-agent/capacity_agent/
  scoring.py` and `capacity-agent/README.md` line 14. `pressure` is now the documented default
  guidance; the flag stays required regardless.

**ADR-009 — the `EvidenceType` change request — RESOLVED: via `DecisionEvidenceType`, not a widened `EvidenceType`**
- Owned by: the retrieval service's author.
- Meanwhile *(while open)*: `--legacy-citations` cited the urgency agent's own evidence directly
  (validated then, one hop shallower than intended); default mode cited the `Score`/`ReferralState`
  nodes it should, and failed validation until resolved.
- Risk that was open: the audit trail stayed one hop shallower than designed; no correctness risk.
- Resolved (PR #7), but not as requested: rather than widening `EvidenceType`, the retrieval service
  added a separate, wider `DecisionEvidenceType` for placement citations only — the original five
  values plus `"score"`, `"referral_state"`, and one more than asked, `"rule"` (the ontology's
  `citesTimeframeEvidence` already permits a `Rule` there). `EvidenceType` itself stays at five
  values, since `ScoreCitationIn` is still bound by Postgres' `ac_evidence_type_valid` CHECK, which
  `agent.decision_citations` carries no equivalent of. Default-mode citations now validate;
  `--legacy-citations` remains a legitimate, working choice, just no longer the only one.

**ADR-011 — CRT breach as a hard tier above clinical priority**
- Owned by: clinical and compliance review.
- Meanwhile: the code implements the hard tier, per FR3 — within a band, every breached referral
  outranks every non-breached one at any score.
- Risk if unresolved: never decided on purpose (FR3 predates scoring, ADR-004 inserted priority
  below it unasked); in the real 9004 cohort this puts 14 non-breached urgent referrals below 117
  breached ones regardless of urgency score.
- On resolution, one of three:
  1. *Keep the hard tier* — no code change; the rationale text states plainly that breach is a tier,
     not a factor.
  2. *Fold breach magnitude into `priority`* — `crt_breached` leaves the sort key; days-over-CRT
     becomes a normalised term in `priority` alongside urgency and wait.
  3. *Tier only beyond a margin* — `crt_breached` becomes "breached by more than N days"; smallest
     change of the three.

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
