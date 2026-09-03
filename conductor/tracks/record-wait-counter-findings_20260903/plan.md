# Implementation Plan — Record wait-counter findings

### Phase 1 — Ontology and namespace docs
- [x] Task: Add the three `time:*` rows to `ontology.md` §3.
- [x] Task: Add the matching three triples to `eat.ttl`; validated with rdflib (683 triples).
- [x] Task: Add the three IRI-template rows to `namespaces.md` §4 (corrected to match the
      test script's actual IRIs: begin/end are siblings of the interval, not nested under it).

### Phase 2 — Requirements gotchas and version pin
- [x] Task: Add the `eat:hasTriageEvent`-proxy gotcha to `requirements.md` §4.
- [x] Task: Add the unbound-`daysAwaitingTriage` contract gotcha to `requirements.md` §4.
- [x] Task: Add the `pyoxigraph==0.3.22` gotcha to `requirements.md` §4, and the dependency
      row to `tech-stack.md`.
- [x] Task: Add the explicit bound/unbound assertion to
      `kg/tests/test_wait_counters_sample.py`; re-ran it, 473/473 still passes.
- [x] Task: Conductor - User Manual Verification 'Findings recorded' (Protocol in
      workflow.md) — confirmed `wait_counters.rq` unchanged via `git diff`, `eat.ttl` parses,
      the test still passes, and every new doc row/gotcha traces back to one of the four
      findings.
