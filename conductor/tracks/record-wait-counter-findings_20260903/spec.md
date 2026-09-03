# Record wait-counter findings in the normative docs

## Overview
`write-validate-queries-wait_20260903` found four things while building
`kg/queries/wait_counters.rq` that the mapping tracks (A/B/C/D/E, Shapes) need to inherit
before they start: the `time:Interval` structure the fragment actually requires, the
`eat:hasTriageEvent`-is-not-a-safe-proxy gotcha, the SPARQL-unbinding contract the fragment
depends on, and the `pyoxigraph` version it was built and verified against. This track
records all four in the normative docs. **No `.rq` logic changed.**

## Functional Requirements

**1. `time:Interval` structure — `ontology.md` §3 + `eat.ttl` + `namespaces.md` §4**
Added three reused-term-refinement rows/triples (`time:hasBeginning`, `time:hasEnd`,
`time:inXSDDate`) to `ontology.md` §3 and `eat.ttl`, matching the existing `time:hasTime`
row's style. Added three IRI-template rows to `namespaces.md` §4 for the interval and its
begin/end instants, minted as IRIs (never blank nodes) — matching the IRIs
`kg/tests/test_wait_counters_sample.py` already mints (begin/end are siblings of the
interval node, not nested under it — corrected during this track after checking the actual
test script, not assumed).

**2. `eat:hasTriageEvent` is not a safe proxy — `requirements.md` §4**
Added a gotcha: 13,117 of 70,012 `referral_daily` rows (`full` profile) with
`triage_status = 'triaged'` have no linked `triage_events` row. `eat:hasTriageEvent`'s
absence must never be read as "not yet triaged" — use `eat:triageStatus`.

**3. The unbound-`daysAwaitingTriage` contract — `requirements.md` §4**
Added a gotcha documenting the `IF(cond, value, 1/0)` unbinding idiom and the requirement
that any future edit preserve genuine unbound-ness, not bind `0`. Added a dedicated
bound/unbound assertion to `kg/tests/test_wait_counters_sample.py`, separate from the value
comparison, per the gotcha's own requirement.

**4. Pin `pyoxigraph==0.3.22`**
Added a row to `tech-stack.md`'s Python dependencies table and a gotcha to
`requirements.md` §4, both noting the version-specific quirk `wait_counters.rq`'s header
comments document.

## Acceptance Criteria
- `ontology.md` §3 and `eat.ttl` both declare `time:hasBeginning`, `time:hasEnd`,
  `time:inXSDDate` with matching domain/range/cardinality; `eat.ttl` parses (rdflib, 683
  triples, up from 674).
- `namespaces.md` §4 has the three new IRI-template rows, matching the test script's IRIs
  exactly.
- `requirements.md` §4 has the three new gotchas.
- `tech-stack.md`'s Python dependencies table lists `pyoxigraph==0.3.22`.
- `kg/tests/test_wait_counters_sample.py` has the explicit bound/unbound assertion; still
  passes (473/473).
- `kg/queries/wait_counters.rq` is byte-identical to its committed version (verified via
  `git diff`, no changes).

## Out of Scope
- Any mapping, shape, or SQL file.
- Adding `time:Interval`/`time:Instant` to `ontology.md` §2's class table.
- Creating a `kg/versions.yml` — no such file exists; pins live in `tech-stack.md` and
  `requirements.md`, which is where this track pins `pyoxigraph`.
