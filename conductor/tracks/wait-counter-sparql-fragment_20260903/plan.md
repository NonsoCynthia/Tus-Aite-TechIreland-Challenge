# Implementation Plan — Wait-counter SPARQL fragment (blocked)

### Phase 1 — Record the blocker
- [x] Task: Write track `spec.md` capturing the investigation (source-table columns, check
      constraints, the 317/5,200 measurement, the conclusion that all four counters are
      blocked on the same missing properties).
- [x] Task: Write track `plan.md` and `decisions.md` recording the "stop and report, do not
      add properties in this track" choice with the user's stated reasoning.
- [x] Task: Set `metadata.json` status to `blocked`.
- [x] Task: Conductor - User Manual Verification 'Blocker recorded' (Protocol in
      workflow.md) — confirmed no files outside `conductor/tracks/wait-counter-sparql-fragment_20260903/`
      were touched, and `kg/queries/` has no `wait_counters.rq`.
