# Decisions — Extend structural shapes to every class

## 1. `eat:hasCondition`'s cardinality is not checked on `eat:ReferralShape`

**Found while validating, not assumed.** A first draft included `sh:property [ sh:path
eat:hasCondition ; sh:minCount 1 ]` on `eat:ReferralShape`, matching `ontology.md` §3's
`1..n` cardinality. Running `pyshacl` against `referral_state.nq` alone produced a
`MinCountConstraintComponent` violation on every single `eat:Referral` node in the file.

**Root cause:** `eat:Referral` nodes are typed and given their other properties by
`referral_state.rml.ttl`; `eat:hasCondition` triples pointing away from those same nodes are
produced by `clinical.rml.ttl` — a completely different mapping, output to a different file
(`clinical.nq`). `referral_state.nq` never carries `hasCondition` triples by construction,
regardless of whether the underlying data is correct. Since this project's own verification
methodology (requirements.md §7) validates each mapping's output file independently before
integration, any shape checking a cross-mapping cardinality will register a false violation
on every correctly-produced file that only contains one side of the relationship.

**Decided: removed the constraint**, rather than working around it (e.g. by loading multiple
files together for shape validation, which would depart from the task's own "validate
against all five .nq files" — plural, separate — instruction). Documented instead of
silently dropped, so a future integration-time shapes pass knows to add it back once a
combined graph is the thing being validated.

**Checked every other property in every new shape against this same risk** by tracing which
`.rml.ttl` file produces each triple relative to which file types the subject node. No other
property has this problem — every other checked property's triple is produced by the same
mapping that types its subject.

## 2. No `sh:closed` on any of the 16 new shapes

Checked individually, as instructed, not defaulted. Every one of the 16 classes receives
properties from more than one mapping run independently of the others (see finding #1 above
for the clearest example — `eat:Referral` alone spans four different mapping files across
its various relationships). Closing a shape risks a false negative the moment a legitimate
property from a sibling mapping is present but wasn't enumerated in the shape. The benefit
`sh:closed` would provide — catching an unexpected extra property — has no corresponding
risk in this project's design: `kg/tests/test_column_coverage.py` already catches missing
properties from the other direction, and nothing in the mapping files ever asserts a
property beyond what `ontology.md` documents.

## 3. `sosa:hasSimpleResult`'s datatype constraint uses `sh:or`, not `sh:sparql`

The task explicitly asked to keep structural shapes free of `sh:sparql` where a
`sh:property` constraint suffices, since `sh:sparql` constraints are measured to cost
minutes, not seconds, at this project's data volumes. A per-observable-property conditional
constraint ("if `observedProperty` is X, `hasSimpleResult` must have datatype Y") is
expressible in plain SHACL core via `sh:or` of 12 branch shapes, each an implicit
conjunction of two `sh:property` constraints (`sh:hasValue` on `observedProperty`,
`sh:datatype` on `hasSimpleResult`). Validated against `clinical.nq`'s 52,000
`sosa:Observation` nodes — `Conforms: True`, and materially faster than an equivalent
`sh:sparql` per-focus-node query would have been at that volume.
