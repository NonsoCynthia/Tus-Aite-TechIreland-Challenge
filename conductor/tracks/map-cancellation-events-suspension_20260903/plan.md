# Implementation Plan — Map cancellation_events and suspension_events to RDF

### Phase 1 — Write and run the mapping
- [x] Task: Write `kg/mappings/events.rml.ttl` (9 triples maps).
- [x] Task: Write `kg/mappings/events.ini` (git-ignored).
- [x] Task: Ran `python -m morph_kgc mappings/events.ini` from `kg/`; 10,832 triples, zero `"None"`.
- [x] Task: Ran `pyshacl -s shapes/structural.ttl -df auto out/events.nq`; `Conforms: True`.
- [x] Task: Verified `eat:CancellationEvent`/`eat:SuspensionEvent`/`time:Interval`/`time:Instant`
      counts against Postgres — all match exactly.

### Phase 2 — Fix the test harness's graph handling and add the real-mapping scenario
- [x] Task: Updated `test_wait_counters_sample.py`'s store-building and query-execution to be
      graph-correct (named `…/kg/graph/inputs` graph + `GRAPH { … }` wrapper).
- [x] Task: Added the real-mapping scenario (runs `events.rml.ttl` via `morph_kgc`, merges
      with hand-built referral facts, re-runs the 473-row comparison).
- [x] Task: Ran the updated test; both scenarios pass 473/473, exit 0.
- [x] Task: Conductor - User Manual Verification 'Events mapped, fragment validated against
      real output' (Protocol in workflow.md) — confirmed all verification checks pass on a
      fresh run, and `git status` shows only `kg/mappings/events.rml.ttl` and
      `kg/tests/test_wait_counters_sample.py` changed.
