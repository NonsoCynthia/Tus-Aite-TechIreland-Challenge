# Complete the EXCLUSIONS dictionary in test_column_coverage.py

## Overview
`kg/tests/test_column_coverage.py` currently reports 50 columns with no matching property
and no EXCLUSIONS entry. Every one of the 50 was traced to a legitimate reason — none is a
genuine ontology gap. This track adds the EXCLUSIONS entries so the test exits 0, without
touching `eat.ttl` or `ontology.md`.

## Background — the 50, by category
Categories per the task: (a) carried by an object property or the IRI template
(`namespaces.md` §4); (b) carried by a dedicated event node; (c) re-expressed by the Type-2
view (`decisions.md` §1); (d) modelled as a separate node, not a literal; (e) present under a
different property name (`requirements.md` §4's divergence table).

- **Own IRI-key columns of a class with no reason to point at itself** (a):
  `core.hospitals.hospital_hipe`, `core.persons.ihi_number`, `core.patients.patient_id`,
  `core.wards.ward_id`, `core.triage_events.triage_event_id`.
- **Composite-key columns carried by an object property, per the IRI templates in
  `namespaces.md` §4** (a): `hospital_hipe`/`ward_id`/`specialty_hipe` on `bed_status`,
  `ward_specialty`, `hospital_specialty`, `clinic_sessions`, `wards` — via `eat:statusOf`,
  `eat:inWard`, `eat:forSpecialty`, `eat:providedBy`, `eat:sessionOf`, `eat:atHospital`
  (Ward's domain was widened for exactly this in `add-missing-data-layer_20260903`);
  `hospital_hipe`/`pathway_number` on `cancellation_events`, `conditions`, `observations`,
  `suspension_events` — via `eat:hasCancellation`, `eat:hasCondition`,
  `eat:hasObservationEvent`, `eat:hasSuspension`; `hospital_hipe`/`pathway_number` on
  `triage_events` — via `eat:hasTriageEvent`, the one place `namespaces.md`'s IRI template
  deliberately excludes them (`triage-event/{id}` alone, "already globally unique") because
  the referral link already carries it.
- **Name divergences already documented in `requirements.md` §4** (e):
  `bed_status.occupied`/`free`/`outliers` → `eat:occupiedBeds`/`eat:freeBeds`/
  `eat:outlierPatients`; `conditions.snomed_ct_id` → `eat:snomedCode`;
  `patients.patient_sex`/`patient_date_of_birth` and `persons.person_sex`/
  `person_date_of_birth` → `eat:sex`/`eat:dateOfBirth`; `referral_daily.priority_level_gp` →
  `eat:gpPriority`; `referral_daily.high_clinical_or_social_needs` →
  `eat:hasHighClinicalOrSocialNeeds`; `triage_events.triage_category` → `eat:assignedCategory`.
- **Two further divergences not yet in `requirements.md` §4's table**:
  `referral_daily.specialty_hipe` → `eat:referredToService` (moved to `eat:ReferralState` by
  `add-missing-data-layer_20260903`); `observations.obs_datetime` → `sosa:resultTime`.
- **Re-expressed by the Type-2 change-detection view** (c):
  `referral_daily.removal_date` → `eat:validTo`.
- **Modelled as separate nodes, not literals** (d):
  `observations.hr`/`sbp`/`dbp`/`rr`/`temp`/`spo2` — each becomes a `sosa:Observation` node
  (`sosa:observedProperty` pointing at `eat:heartRate`/`eat:systolicBP`/`eat:diastolicBP`/
  `eat:respiratoryRate`/`eat:temperature`/`eat:oxygenSaturation`, `sosa:hasSimpleResult`
  carrying the value); `suspension_events.suspension_start_date`/`suspension_end_date` —
  carried by the `time:Interval` reached via `time:hasTime` (`time:hasBeginning`/
  `time:hasEnd`), not as literals on `eat:SuspensionEvent` itself.

No column was left over — all 50 accounted for. No genuine gap found; `eat.ttl`/`ontology.md`
are not touched.

## Functional Requirements
1. Add exactly the 50 keys above to `EXCLUSIONS` in `kg/tests/test_column_coverage.py`, each
   with a specific reason.
2. Do not modify `kg/ontology/eat.ttl` or `conductor/kg/ontology.md`.
3. Do not modify `TABLES`, the matching logic, or any other test behaviour.
4. The test must exit 0 when run against the live `full`-profile database.

## Non-Functional Requirements
- Reasons follow the existing entries' style.
- No unrelated file changes.

## Acceptance Criteria
- `python kg/tests/test_column_coverage.py` prints `PASS: every source column is carried or
  explicitly excluded` and exits 0.
- `git diff` touches only `kg/tests/test_column_coverage.py` and this track's own directory.

## Out of Scope
- Amending `ontology.md`'s §4 divergence table with the two additional divergences found —
  noted in `decisions.md` as a follow-up suggestion only.
- Any change to mappings, shapes, or SQL.
