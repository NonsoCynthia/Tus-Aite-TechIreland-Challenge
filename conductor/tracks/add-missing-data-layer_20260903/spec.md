# Add missing data-layer literal properties to the ontology

## Overview
`wait-counter-sparql-fragment_20260903` found `eat:Referral` has no property for `referral_date`
or `referral_received_date`. Auditing every data-layer class in `ontology.md` §2 against its
source table (`dataset/DATASET_README.md` §7 and the live Postgres schema) shows the gap is
much wider: §3 declares object properties (relationships between nodes) almost exclusively —
outside `validFrom`/`validTo`, essentially no table's own attribute columns (names, dates,
counts, flags) have a property at all. This track closes that gap and resolves one modelling
inconsistency the audit surfaced: `eat:referredToService` is declared on `eat:Referral`, but
`specialty_hipe` is one of R1's material fields (changes on redirect) — under decisions.md's
Type-2 model, a mutable fact belongs on `eat:ReferralState`, not the enduring `eat:Referral`.

## Background — audit method
For every class in `ontology.md` §2, every column of its source table was checked against:
1. Already carried by an existing object property (e.g. `patient_id` → `eat:forPatient`) — skip.
2. Carried by a dedicated event node that makes the column redundant (e.g. `referral_daily.last_cancellation_date`
   is redundant with `eat:CancellationEvent.eat:cancellationDate` on every linked cancellation) — skip, noted.
3. Already computed by the Type-2 change-detection view and re-expressed as something else
   already in the ontology (`removal_date` → `eat:validTo`, per decisions.md §1) — skip.
4. A code column present in `core.ref_codes` (confirmed live: `cancellation_reason`,
   `clinic_classification`, `gp_priority`, `referral_source`, `removal_reason`,
   `suspension_reason`, `triage_category`, `triage_outcome`) — becomes an **object property**
   with range `skos:Concept` (or the dedicated class, e.g. `eat:CPC`/`eat:TriageOutcome`, where
   `ontology.md` §2 already names one), never a literal, per requirements.md R6.
5. Otherwise — a genuine gap. Add a datatype property.

One pre-existing omission surfaced by the same audit, without which the vitals/symptoms/
assessments modelled in §5 have no way to state a value at all: `sosa:hasSimpleResult` and
`sosa:resultTime`, named in ontology.md §1's vocabulary-reuse table but never given a
domain/range refinement in §3. Fixed here as the same kind of gap.

Per the user's explicit decision, two related fixes are included even though they are object
properties, not literals, because they are required for R2/R1 and are minimal, no-new-IRI-scheme
extensions of properties already in the ontology:
- `eat:atHospital`'s domain extended to include `eat:Ward` (currently no triple states which
  hospital a ward belongs to).
- `time:hasTime` (OWL-Time, reused) domain-refined to link `eat:SuspensionEvent` to a
  `time:Interval`, which decisions.md names as a hard requirement for `adjusted_wait_days`.

## Functional Requirements

**1. Resolve the `referredToService` inconsistency.** Move `eat:referredToService` from
`eat:Referral` to `eat:ReferralState` (domain change only; range `eat:HospitalService`,
cardinality 1, functional, unchanged).

**2. Add missing literal/object properties** — see the full class-by-class list below.

**3. Extend `eat:atHospital`'s domain** from `unionOf(Patient, Referral)` to
`unionOf(Patient, Referral, Ward)`.

**4. Do not touch `kg/mappings/`, `kg/shapes/`, or `kg/sql/`.**

**5. Amend `conductor/kg/ontology.md` first, then `kg/ontology/eat.ttl` to match exactly.**

### Full property list by class
- `eat:Referral`: `eat:referralDate` (xsd:date, 1); `eat:referralReceivedDate` (xsd:date, 1);
  `eat:recordCreationDate` (xsd:date, 1, verified constant per referral in Postgres);
  `eat:gpPriority` (object → skos:Concept, 0..1); `eat:referralSource` (object → skos:Concept, 1).
- `eat:ReferralState`: `eat:referredToService` (moved here); `eat:triageStatus` (xsd:string, 1);
  `eat:appointmentDate` (xsd:date, 0..1); `eat:arrivedDate` (xsd:date, 0..1);
  `eat:hasHighClinicalOrSocialNeeds` (xsd:boolean, 1); `eat:clinicCode` (xsd:string, 0..1);
  `eat:clinicClassification` (object → skos:Concept, 0..1); `eat:removalReason` (object →
  skos:Concept, 0..1).
- `eat:TriageEvent`: `eat:sentForTriageDate` (xsd:date, 1); `eat:triageDate` (xsd:date, 0..1);
  `eat:dateReturnedFromTriage` (xsd:date, 0..1); `eat:hasTriageOutcome` (object →
  eat:TriageOutcome, 0..1); `eat:turnaroundDays` (xsd:nonNegativeInteger, 0..1).
- `eat:Condition`: `eat:conditionLabel` (xsd:string, 1); `eat:isPrimary` (xsd:boolean, 1).
- `sosa:Observation` (reused-term refinement): `sosa:hasSimpleResult` (domain
  sosa:Observation, datatype varies by column, cardinality 1); `sosa:resultTime` (domain
  sosa:Observation, range xsd:dateTime, cardinality 1).
- `eat:SuspensionEvent`: `time:hasTime` (reused, domain-refined to eat:SuspensionEvent, range
  time:Interval, cardinality 1); `eat:suspensionReason` (object → skos:Concept, 1);
  `eat:suspendedDays` (xsd:nonNegativeInteger, 0..1).
- `eat:CancellationEvent`: `eat:cancellationDate` (xsd:date, 1); `eat:cancellationReason`
  (object → skos:Concept, 1); `eat:initiatedBy` (xsd:string, 1).
- `eat:Hospital`: `eat:hospitalName`, `eat:hseHealthRegion`, `eat:hospitalType` (xsd:string, 1
  each); `eat:totalInpatientBeds` (xsd:nonNegativeInteger, 1).
- `eat:HospitalService`: `eat:serviceName` (xsd:string, 1); `eat:active` (xsd:boolean, 1).
- `eat:Specialty`: `eat:isPaediatric` (xsd:boolean, 1).
- `eat:Ward`: `eat:wardName` (xsd:string, 1); `eat:totalBeds` (xsd:nonNegativeInteger, 1);
  `eat:wardType` (xsd:string, 1).
- `eat:BedAllocation`: `eat:nominalBeds` (xsd:nonNegativeInteger, 1); `eat:isPrimaryWard`
  (xsd:boolean, 1).
- `eat:BedStatus`: `eat:snapshotDatetime` (xsd:dateTime, 1); `eat:occupiedBeds`,
  `eat:freeBeds`, `eat:outlierPatients`, `eat:surgeCapacityInUse`,
  `eat:delayedTransfersOfCare`, `eat:awaitingAdmissionOver9h`, `eat:awaitingAdmissionOver24h`
  (xsd:nonNegativeInteger, 1 each); `eat:occupancyPct` (xsd:decimal, 1); `eat:garStatus`
  (xsd:string, 1).
- `eat:ClinicSession`: `eat:sessionDate` (xsd:date, 1); `eat:clinicName` (xsd:string, 1);
  `eat:slotsTotal`, `eat:slotsBooked`, `eat:slotsAvailable` (xsd:nonNegativeInteger, 1 each).
- `eat:Rule`: `eat:statement`, `eat:appliesTo` (xsd:string, 1 each); `eat:thresholdDays`
  (xsd:nonNegativeInteger, 0..1).
- `eat:Person` / `eat:Patient` (shared): `eat:sex` (xsd:string, 1); `eat:dateOfBirth`
  (xsd:date, 1); `eat:areaOfResidenceCode` (xsd:string, 1). Domain `unionOf(Person, Patient)`.

## Non-Functional Requirements
- Valid Turtle: parses cleanly (rdflib).
- Every coded column (the 8 confirmed `ref_codes` tables) becomes an object property with
  `skos:Concept` (or the dedicated class) range — never a literal — per R6.
- Style matches the existing file: `rdfs:comment` naming the source column, grouped under the
  same §2/§3/§4/§5/§6 section headers, functional properties marked `owl:FunctionalProperty`.

## Acceptance Criteria
- Every column identified above has a property in both `ontology.md` and `eat.ttl`, with
  matching domain/range/cardinality/source-column.
- `eat:referredToService`'s domain is `eat:ReferralState`, not `eat:Referral`.
- `sosa:hasSimpleResult` and `sosa:resultTime` are present with domain refinements.
- `eat:SuspensionEvent` has a `time:hasTime` link to `time:Interval`.
- `eat:atHospital`'s domain includes `eat:Ward`.
- `eat.ttl` still parses (rdflib, triple count reported).
- No file outside `conductor/kg/ontology.md`, `kg/ontology/eat.ttl`, and this track's own
  directory is touched.

## Out of Scope
- Populating any of these properties with real data (mappings) — A/B/C/D/E tracks.
- SHACL shapes, SQL, `kg/queries/wait_counters.rq`.
- A dedicated per-referral "Appointment" class linking to `eat:ClinicSession`.
- Reference-layer SKOS materialisation of the 8 `ref_codes` tables (track 3).
