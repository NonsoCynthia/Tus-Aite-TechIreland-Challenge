# Extend structural shapes to every class

## Overview
`kg/shapes/structural.ttl` had shapes for only `eat:ReferralState`. This track adds
`sh:NodeShape`s for every other class currently in the graph: `eat:Referral`, `eat:Patient`,
`eat:Person`, `eat:TriageEvent`, `eat:Condition`, `eat:ObservationEvent`,
`sosa:Observation`, `eat:SuspensionEvent`, `eat:CancellationEvent`, `eat:Hospital`,
`eat:HospitalService`, `eat:Ward`, `eat:BedAllocation`, `eat:BedStatus`,
`eat:ClinicSession`, and `eat:Rule`. Domain/range/cardinality come straight from
`ontology.md` §3. Validated against all five `kg/out/*.nq` files — all `Conforms: True`.

## No `sh:closed` anywhere
Checked every class individually, as instructed, and closed none of them. Every one of
these classes accumulates properties from more than one independently-run mapping — e.g.
`eat:Referral` gets its own literal properties and `eat:hasTriageEvent` from
`referral_state.rml.ttl`, but `eat:hasCondition`, `eat:hasObservationEvent`,
`eat:hasSuspension`, and `eat:hasCancellation` from `clinical.rml.ttl`/`events.rml.ttl`.
Closing any of them risks a false negative from an incomplete enumeration, for no
corresponding benefit: `kg/tests/test_column_coverage.py` already catches missing
properties; `sh:closed` would only catch extra ones, and nothing in this project's design
adds properties a class shouldn't have.

## A real finding: `eat:hasCondition`'s cardinality can't be checked per-mapping-file
`eat:hasCondition` is `1..n` per `ontology.md` §3, and a first draft included
`sh:minCount 1` on `eat:ReferralShape`. Running it against `referral_state.nq` alone (per
this track's own per-file validation instruction) produced a violation on **every** Referral
node — not because the data is wrong, but because `eat:hasCondition` triples are produced by
`clinical.rml.ttl`, a different mapping from the one that mints `eat:Referral` and its other
properties. Each mapping's output is validated independently, per requirements.md §7's own
methodology, and no single mapping file ever carries both a class's typing triple and every
cross-mapping relationship pointing away from it. **Removed the constraint**, documented
here rather than silently dropped — it becomes checkable once integration produces a
combined graph. No other property in any of the 16 new shapes has this problem: every other
checked property's triple is produced by the same mapping file that types the subject node
(confirmed by tracing each one against its source `.rml.ttl` file).

## `sosa:hasSimpleResult`'s per-observable-property datatype constraint
requirements.md §4 notes `sosa:hasSimpleResult` has no declared range, since the datatype
varies by observed property, and nothing else enforces it. Expressed as `eat:ObservationResultDatatypeShape`,
an `sh:or` of 12 branch shapes (one per observable-property individual), each branch pinning
`sosa:observedProperty` to one individual (`sh:hasValue`) and `sosa:hasSimpleResult` to that
individual's required datatype (`xsd:integer` for `heartRate`/`systolicBP`/`diastolicBP`/
`respiratoryRate`/`oxygenSaturation`/`pain`/`news2`; `xsd:decimal` for `temperature`;
`xsd:string` for `avpu`/`chiefComplaint`/`mtsCategory`/`ictsCategory`). This stays in plain
`sh:property` terms — no `sh:sparql` — per the task's own guidance to keep structural shapes
free of SPARQL rule constraints where a property constraint suffices.

## Verification (pyshacl against all five kg/out/*.nq files)
| File | Conforms |
|---|---|
| `reference_layer.nq` | True |
| `events.nq` | True |
| `capacity.nq` | True |
| `clinical.nq` (357,285 triples, 52,000 `sosa:Observation` nodes — the file that actually
  exercises `ObservationResultDatatypeShape`'s 12-branch `sh:or`) | True |
| `referral_state.nq` (209,560 triples, 13,772 `eat:ReferralState` nodes — the file that
  exercises the pre-existing `sh:sparql` interval shape) | True |

## Functional Requirements
1. One `sh:NodeShape` per class named above, each `sh:targetClass`, following the existing
   file's Turtle style.
2. Every property with a declared cardinality in `ontology.md` §3 gets an `sh:property`
   constraint: `sh:datatype` for literal properties, `sh:minCount`/`sh:maxCount` matching the
   card. column (`1`/`functional` → min1max1; `0..1` → max1; `1..n` → min1; `0..n` →
   omitted, nothing to check).
3. `eat:ObservationResultDatatypeShape` for the `sosa:hasSimpleResult` per-column datatype
   constraint, as described above.
4. No `sh:sparql` anywhere in the new shapes.
5. No `sh:closed` anywhere.

## Acceptance Criteria
- `pyshacl -s kg/shapes/structural.ttl -df auto <file>` → `Conforms: True` for all five
  `kg/out/*.nq` files.
- No file outside `kg/shapes/structural.ttl` and this track's own directory is touched.

## Out of Scope
- `sh:sparql` rule constraints (per decisions.md §2, added once the coordinating agent
  produces its first ranking — a later phase).
- Cross-mapping cardinality constraints (e.g. `eat:hasCondition` on `eat:Referral`) —
  belongs at integration, once a combined graph exists.
