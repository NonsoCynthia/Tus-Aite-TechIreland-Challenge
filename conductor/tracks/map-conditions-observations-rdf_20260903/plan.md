# Implementation Plan — Map conditions and observations to RDF

### Phase 1 — Write and run the mapping
- [x] Task: Checked `core.conditions`/`core.observations` row counts and per-column
      non-null counts live in SQL (6,977; 5,200; 52,000 total non-null measured values).
- [x] Task: Write `kg/mappings/clinical.rml.ttl` — 3 condition maps + 2 base observation
      maps + 13 × 2 per-column maps (26) = 31 triples maps, 13 shared `rr:LogicalTable`s.
- [x] Task: Write `kg/mappings/clinical.ini` (git-ignored).
- [x] Task: Ran `python -m morph_kgc mappings/clinical.ini` from `kg/`; 357,285 triples,
      zero `"None"`.
- [x] Task: Ran `pyshacl -s shapes/structural.ttl -df auto out/clinical.nq`; `Conforms: True`.
- [x] Task: Verified `eat:Condition` (6,977), `eat:ObservationEvent` (5,200),
      `sosa:Observation` (52,000), and `sosa:hasMember` (52,000) counts — all match exactly.
- [x] Task: Conductor - User Manual Verification 'Clinical layer mapped' (Protocol in
      workflow.md) — confirmed all verification checks pass on a fresh run against the
      committed files, and `git status` shows only `kg/mappings/clinical.rml.ttl` and this
      track's own directory changed.
