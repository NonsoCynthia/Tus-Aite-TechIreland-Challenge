# Implementation Plan — Extend structural shapes to every class

### Phase 1 — Write and validate the shapes
- [x] Task: Extracted domain/range/cardinality for all 16 classes from `ontology.md` §3.
- [x] Task: Wrote one `sh:NodeShape` per class, `sh:property` constraints only
      (`sh:datatype` + `sh:minCount`/`sh:maxCount` per the card. column), no `sh:sparql`.
- [x] Task: Wrote `eat:ObservationResultDatatypeShape` (`sh:or` of 12 branches) for
      `sosa:hasSimpleResult`'s per-observable-property datatype.
- [x] Task: Checked every class individually for `sh:closed` suitability; closed none
      (documented reasoning in `decisions.md`).
- [x] Task: Ran `pyshacl` against all five `kg/out/*.nq` files individually; found and fixed
      a cross-mapping cardinality bug (`eat:hasCondition` on `eat:Referral` — see
      `decisions.md`); reran and confirmed `Conforms: True` for all five.
- [x] Task: Conductor - User Manual Verification 'All five files conform' (Protocol in
      workflow.md) — confirmed a fresh run of `pyshacl` against each of the five committed
      `kg/out/*.nq` files reports `Conforms: True`, and `git status` shows only
      `kg/shapes/structural.ttl` and this track's own directory changed.
