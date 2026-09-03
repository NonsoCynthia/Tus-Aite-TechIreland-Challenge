# Decisions — Map conditions and observations to RDF

## 1. Two triples maps per observation column, sharing one named `rr:LogicalTable`

`sosa:hasMember`'s subject is the `eat:ObservationEvent`; the observation's own properties
(`observedProperty`/`hasSimpleResult`/`resultTime`/`hasFeatureOfInterest`) have the
`sosa:Observation` itself as subject. R2RML gives one subject per `rr:TriplesMap`, so these
cannot be the same map. Rather than duplicate each column's filtered SQL text twice, each
column gets one named `rr:LogicalTable` (e.g. `<#HrTable>`), referenced by both of that
column's `rr:TriplesMap`s. This keeps the `WHERE <column> IS NOT NULL` filter written once
per column, not twice.

## 2. `observations` has no `patient_id` — joined in from `core.referrals`

`sosa:hasFeatureOfInterest` must point at the patient, not the referral (per ontology.md's
own note on this property). `core.observations` is keyed on `(hospital_hipe,
pathway_number, obs_datetime)` only — no `patient_id` column. Every per-column
`rr:sqlQuery` therefore joins to `core.referrals` on `(hospital_hipe, pathway_number)` to
pull `patient_id` in, rather than inventing a shortcut (e.g. going via `eat:Referral`
indirectly at query time) that the mapping layer isn't positioned to do.

## 3. No SHACL `sh:datatype` constraint added for `sosa:hasSimpleResult`

requirements.md §4 already names this as the shapes track's job ("nothing in the ontology
enforces \[the per-column datatype\]... the shapes track must add a `sh:datatype`
constraint per observable property"). This track sets the correct `rr:datatype` on every
`sosa:hasSimpleResult` triple it produces, which is necessary but not the same thing as a
shape that would catch a future mapping getting it wrong — that remains explicitly
out of scope here, per the same reasoning `events`/`capacity` used for their own shapes.
