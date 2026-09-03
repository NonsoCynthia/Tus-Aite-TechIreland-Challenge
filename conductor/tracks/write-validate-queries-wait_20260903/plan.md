# Implementation Plan — Write and validate kg/queries/wait_counters.rq

### Phase 1 — Write and validate the fragment
- [x] Task: Write `kg/queries/wait_counters.rq`.
- [x] Task: Write `kg/tests/test_wait_counters_sample.py` and confirm it exits 0 with
      473/473 matches reported.
- [x] Task: Conductor - User Manual Verification 'wait_counters.rq validated' (Protocol in
      workflow.md) — re-ran the test script fresh, confirmed 473/473, confirmed no other file
      changed.

### Phase 2 — Supersede the earlier track
- [x] Task: Set `wait-counter-sparql-fragment_20260903/metadata.json` status to
      `"superseded"`; added a one-line pointer in its `index.md` to this track.
      `spec.md`/`decisions.md` left untouched.
