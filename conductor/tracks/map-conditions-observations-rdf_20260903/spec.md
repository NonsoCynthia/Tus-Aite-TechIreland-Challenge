# Map conditions and observations to RDF (Track C)

## Overview
Track C of the KG build — the expansion case. Maps `core.conditions` and
`core.observations` via `kg/mappings/clinical.rml.ttl`, following `capacity.rml.ttl`'s
pattern. 357,285 triples materialised, zero `"None"`, `pyshacl` conforms, and every count
matches the SQL-computed expectation exactly.

## What the mapping produces (verified counts)
| Node | Postgres-derived expectation | Materialised |
|---|---|---|
| `eat:Condition` | 6,977 (`core.conditions` row count) | 6,977 |
| `eat:ObservationEvent` | 5,200 (`core.observations` row count) | 5,200 |
| `sosa:Observation` | 52,000 (sum of non-null counts across all 13 measured columns,
  computed in SQL: `hr`/`sbp`/`dbp`/`rr`/`temp`/`spo2`/`pain`/`avpu`/`news2` = 5,200 each,
  `mts_category` = 5,119, `icts_category` = 81, `chiefcomplaint` = 0) | 52,000 |
| `sosa:hasMember` triples | 52,000 (one per `sosa:Observation`) | 52,000 |
| `eat:snomedCode` triples | 0 (`snomed_ct_id` is `NULL` for all 6,977 conditions in this
  profile) | 0 |

`grep -c 'None'` → 0. `pyshacl -s kg/shapes/structural.ttl -df auto kg/out/clinical.nq` →
`Conforms: True`.

## Functional Requirements
1. **Conditions** (`ConditionMap`, `ConditionSnomedMap`, `ReferralHasConditionMap`):
   `eat:Condition`, `eat:conditionLabel`, `eat:isPrimary`, `eat:icd10amCode` (object property
   to a minted `.../kg/id/icd10am/{code}` IRI), `eat:snomedCode` (object property to
   `http://snomed.info/id/{snomed_ct_id}`, its own `IS NOT NULL` map — never minted under
   `eatd:`), `eat:hasCondition` from the referral.
2. **Observations** — the expansion case. `ObservationEventMap` mints one
   `eat:ObservationEvent` per row; `ReferralHasObservationEventMap` links it from the
   referral. For each of the 13 measured columns, a shared `rr:LogicalTable` (joined to
   `core.referrals` for `patient_id`, since `observations` has none) filtered
   `WHERE <column> IS NOT NULL` backs two `rr:TriplesMap`s:
   - one asserting the `sosa:Observation`'s own properties: `sosa:observedProperty` (a
     constant pointing at the matching observable-property individual — `eat:heartRate`,
     `eat:systolicBP`, …), `sosa:hasSimpleResult` with an explicit `rr:datatype` per column
     (`xsd:integer` for `hr`/`sbp`/`dbp`/`rr`/`spo2`/`pain`/`news2`, `xsd:decimal` for
     `temp`, `xsd:string` for `avpu`/`chiefcomplaint`/`mts_category`/`icts_category`),
     `sosa:resultTime` from `obs_datetime`, `sosa:hasFeatureOfInterest` → the **patient**
     IRI (joined in, not the referral);
   - one linking the parent `eat:ObservationEvent` to it via `sosa:hasMember`.
   Two separate `rr:TriplesMap`s per column are required because `sosa:hasMember`'s subject
   (the event) differs from the observation's own subject — R2RML gives one subject per
   `TriplesMap`. Sharing one `rr:LogicalTable` per column (named, referenced twice) avoids
   writing the same filtered SQL out twice.
   No unit is ever asserted on an observation — units live on the observable property,
   already declared once in `eat.ttl` (decisions.md §3).
3. `kg/mappings/clinical.ini` — git-ignored, not committed.
4. All 13 observation columns are nullable (`chiefcomplaint` happens to be null for every
   row in this profile, but the schema allows values) — each gets its own `IS NOT NULL`
   filter, verified live before writing the mapping.

## Acceptance Criteria
- `kg/mappings/clinical.rml.ttl` exists; materialised output matches every count above exactly.
- Zero `"None"`; `pyshacl` conforms.
- No file outside `kg/mappings/clinical.rml.ttl` and this track's own directory is touched.

## Out of Scope
- SHACL shapes for the new classes, including a `sh:datatype` constraint per observable
  property (requirements.md §4 already flags this as the shapes track's job).
- Any change to mappings already committed.
