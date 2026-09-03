# Map cancellation_events and suspension_events to RDF (Track E)

## Overview
Track E of the KG build. Maps `core.cancellation_events` and `core.suspension_events` via
`kg/mappings/events.rml.ttl`, following `reference_layer.rml.ttl`'s pattern. 10,832 triples
materialised, zero `"None"`, `pyshacl` conforms, event counts match Postgres exactly (1,636
cancellations, 221 suspensions). **A real, previously-latent bug in how
`kg/queries/wait_counters.rq` is used was found and fixed in the test harness (not in the
fragment itself)** while wiring up the real mapping's output — confirmed with the user.

## The graph-clause finding
`wait_counters.rq`'s triple patterns have no `GRAPH` clause. The existing test
(`test_wait_counters_sample.py`) passed because it loaded its hand-built triples into
Oxigraph's *default* (unnamed) graph, which the fragment's unwrapped patterns match by
construction. namespaces.md §5 mandates real input-layer data lives in the *named*
`…/kg/graph/inputs` graph — once `events.rml.ttl`'s real, correctly graph-tagged output was
loaded and queried, the fragment matched nothing and `adjusted_wait_days` silently came back
equal to `days_since_received` (no error, just wrong).

**Root cause:** `wait_counters.rq` is a fragment meant to be spliced into a larger query —
graph-agnostic by design. **No fix to `wait_counters.rq` itself.** The fix is in how it's
tested: load test data into the named `…/kg/graph/inputs` graph and wrap the fragment's
execution in `GRAPH <…/kg/graph/inputs> { … }`, as a real consuming query is expected to.
Confirmed this resolves it (`adjusted_wait_days` = 681, matching Postgres, once both fixes
apply together).

Per the user's decision, both the existing hand-built test and the new real-mapping test
were updated to this graph-correct methodology.

## What the mapping produces (verified counts, Postgres vs. materialised output)
| Class | Postgres rows | Materialised |
|---|---|---|
| `eat:CancellationEvent` | 1,636 | 1,636 |
| `eat:SuspensionEvent` | 221 | 221 |
| `time:Interval` | — | 221 |
| `time:Instant` | — | 442 (221 begin + 221 end — every suspension in this profile is
  already closed; the open-suspension branch is implemented but untested by data) |

`grep -c 'None'` → 0. `pyshacl` → `Conforms: True`.

## Functional Requirements
1. `kg/mappings/events.rml.ttl`, 9 `rr:TriplesMap`s, all with constant `rr:graphMap`
   `…/kg/graph/inputs`: `CancellationEventMap`, `ReferralHasCancellationMap`,
   `SuspensionEventMap`, `SuspensionSuspendedDaysMap`, `ReferralHasSuspensionMap`,
   `SuspensionIntervalMap`, `SuspensionBeginInstantMap`, `SuspensionIntervalEndMap`,
   `SuspensionEndInstantMap`. IRIs for the interval/begin/end exactly match namespaces.md
   §4's templates (siblings, not nested).
2. `kg/mappings/events.ini` — git-ignored, not committed.
3. `kg/tests/test_wait_counters_sample.py` rewritten: both scenarios now load into the named
   `…/kg/graph/inputs` graph and run `wait_counters.rq` wrapped in `GRAPH { … }`; a second
   scenario materialises `events.rml.ttl` for real (subprocess `morph_kgc` call against a
   throwaway `.ini`) and re-runs the same 473-row comparison.
4. `eat:cancellationReason`/`eat:suspensionReason` are object properties to the
   reference-layer concepts (`.../cancellation_reason/{value}`, `.../suspension_reason/{value}`),
   never literals (R6).

## Acceptance Criteria
- `kg/mappings/events.rml.ttl` exists; materialised output matches every count above exactly.
- Zero `"None"`; `pyshacl` conforms.
- `kg/tests/test_wait_counters_sample.py` passes both scenarios, 473/473 each, exits 0.
- No file outside `kg/mappings/events.rml.ttl`, `kg/tests/test_wait_counters_sample.py`, and
  this track's own directory is touched.

## Out of Scope
- Any change to `kg/queries/wait_counters.rq`'s logic.
- SHACL shapes for the new classes.
- The open-suspension branch remaining untested by real data (none exists in the `full` profile).
