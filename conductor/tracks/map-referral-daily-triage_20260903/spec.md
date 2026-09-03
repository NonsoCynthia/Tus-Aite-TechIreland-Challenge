# Map referral_daily, triage_events, patients and persons to RDF (Track A/B)

## Overview
Track A/B — the hardest of the parallel tracks, and the one that completes the input layer.
Extends `kg/mappings/referral_state.rml.ttl` (rather than starting fresh) to add
`eat:Referral`, the remaining `eat:ReferralState` properties, `eat:TriageEvent`,
`eat:Patient` and `eat:Person`. 209,560 triples materialised, zero `"None"`, `pyshacl`
conforms, and every count matches exactly.

## First: the named-graph correction
`referral_state.rml.ttl` predated the named-graph decision and emitted N-Triples with no
graph. Every `rr:subjectMap` in the file now carries a constant
`rr:graphMap` of `…/kg/graph/inputs`, matching `reference_layer`/`events`/`capacity`/
`clinical`; `referral_state.ini` (git-ignored) switched to `output_format: N-QUADS`,
`.nq` output.

## Two modelling decisions made while extending the mapping
1. **`clinic_code`, `clinic_classification`, `removal_reason` aren't in
   `kg.v_referral_state`.** They aren't R1 material fields, so the change-detection view
   correctly excludes them — but `add-missing-data-layer_20260903` still declared
   `eat:clinicCode`/`eat:clinicClassification`/`eat:removalReason` on `eat:ReferralState`.
   Resolved by joining back to `core.referral_daily` for the specific day each applies to:
   `clinic_code`/`clinic_classification` track `appointment_date` (itself material, so fixed
   for the whole state once set) and are read as of the state's own `valid_from`;
   `removal_reason` is read as of `valid_to`, the day the referral was actually removed.
   Both are data lookups, not change-detection logic — the logic itself stays in the SQL
   view, per requirements.md §4's own rule.
2. **`record_creation_date` isn't a column of `core.referrals`.** Only `referral_daily`
   carries it. `add-missing-data-layer_20260903` verified it constant per referral in
   Postgres, so a correlated `MIN()` per `(hospital_hipe, pathway_number)` in
   `eat:Referral`'s own `rr:sqlQuery` is exact, not an approximation.
3. **`eat:areaOfResidenceCode` added to `eat:Patient`/`eat:Person`**, beyond the task's
   literal `sex`/`dateOfBirth` list — it's a real, non-null column on both tables and an
   already-declared property; omitting it would leave the input layer visibly incomplete
   for no stated reason.

## What the mapping produces (verified counts)
| Node | Expected | Materialised |
|---|---|---|
| `eat:ReferralState` | 13,772 (`kg.v_referral_state` row count) | 13,772 |
| `eat:Referral` | 5,200 (`core.referrals` row count) | 5,200 |
| `eat:TriageEvent` | 4,212 (`core.triage_events` row count) | 4,212 |
| `eat:Patient` | 5,200 (`core.patients` row count) | 5,200 |
| `eat:Person` | 3,412 (`core.persons` row count; fewer than `Patient`, as expected) | 3,412 |
| Unlinkable patients (decisions.md §4's `FILTER NOT EXISTS` query) | 5,200 − 3,412 = 1,788 | **1,788** |

`grep -c 'None'` → 0. `pyshacl -s kg/shapes/structural.ttl -df auto kg/out/referral_state.nq`
→ `Conforms: True`.

## Functional Requirements
1. `eat:ReferralState` (extends `ReferralStateMap`/`ReferralStateClosedMap`): added
   `eat:triageStatus`/`eat:hasHighClinicalOrSocialNeeds`/`eat:referredToService` directly
   (columns are NOT NULL on the source, verified live); `eat:appointmentDate`/
   `eat:arrivedDate`, each its own `IS NOT NULL` map; `eat:clinicCode`/
   `eat:clinicClassification`/`eat:removalReason` via the joins described above, each its
   own filtered map.
2. `eat:Referral` (`ReferralMap`, `ReferralGpPriorityMap`): `eat:referralDate`,
   `eat:referralReceivedDate`, `eat:recordCreationDate`, `eat:referralSource` (object
   property), `eat:atHospital`, `eat:forPatient`; `eat:gpPriority` (object property) in its
   own `IS NOT NULL` map (nullable).
3. `eat:TriageEvent` (`TriageEventMap` + 5 filtered maps + `ReferralHasTriageEventMap`):
   `eat:sentForTriageDate` (NOT NULL); `eat:triageDate`, `eat:dateReturnedFromTriage`,
   `eat:hasTriageOutcome`, `eat:assignedCategory`, `eat:turnaroundDays` — each schema-nullable
   (even though fully populated in this profile) and each its own map. Linked via
   `eat:hasTriageEvent`.
4. `eat:Patient`/`eat:Person` (`PatientMap`, `PatientIsRecordOfMap`, `PersonMap`):
   `eat:sex`, `eat:dateOfBirth`, `eat:areaOfResidenceCode` on both; `eat:atHospital` on
   `Patient`; `eat:isRecordOf` only where `ihi_number IS NOT NULL` — no placeholder, no
   blank node, per decisions.md §4.
5. All object properties pointing at coded values (`gpPriority`, `referralSource`,
   `hasTriageOutcome`, `assignedCategory`, `clinicClassification`, `removalReason`) use the
   reference-layer concept IRIs `reference_layer.rml.ttl` already mints — no bare literals
   for anything in `ref_codes` (R6).

## Acceptance Criteria
- All six counts in the table above match exactly.
- Zero `"None"`; `pyshacl` conforms.
- `referral_state.rml.ttl`'s existing maps carry a graph map; `referral_state.ini` emits
  N-Quads.
- No file outside `kg/mappings/referral_state.rml.ttl` and this track's own directory is
  touched.

## Out of Scope
- SHACL shapes for the new classes.
- Any change to mappings already committed (`reference_layer`, `events`, `capacity`,
  `clinical`).
