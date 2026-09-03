# Map the six capacity tables to RDF (Track D)

## Overview
Track D of the KG build. Maps `core.hospitals`, `core.hospital_specialty`, `core.wards`,
`core.ward_specialty`, `core.bed_status`, and `core.clinic_sessions` via
`kg/mappings/capacity.rml.ttl`, following `events.rml.ttl`'s pattern. 12,955 triples
materialised, zero `"None"`, `pyshacl` conforms, and every class count matches Postgres
exactly.

## No nullable columns anywhere
Every column across all six tables was checked live: none are nullable. So — unlike
`referral_state`/`reference_layer`/`events`, all of which needed `IS NOT NULL` companion
maps for at least one column — every table here gets exactly one `TriplesMap`. This was
verified, not assumed, before writing the mapping.

## Two IRI-template findings, checked against the live schema
1. **`clinic_sessions` — confirmed accurate, no correction needed.** namespaces.md §4
   flagged this table's template as needing confirmation. Both `clinic_code` and
   `session_date` exist exactly as templated; no change required.
2. **`bed_status` — a real error, found and corrected.** namespaces.md §4's `BedStatus`
   template read `bed-status/{hospital_hipe}/{ward_id}/{status_datetime}`, but the live
   column is `snapshot_datetime` — `status_datetime` doesn't exist. Confirmed with the user
   and corrected in `namespaces.md` §4 as part of this track.

## What the mapping produces (verified counts, Postgres vs. materialised output)
| Class | Postgres rows | Materialised |
|---|---|---|
| `eat:Hospital` | 6 | 6 |
| `eat:HospitalService` | 42 | 42 |
| `eat:Ward` | 20 | 20 |
| `eat:BedAllocation` | 45 | 45 |
| `eat:BedStatus` | 840 | 840 |
| `eat:ClinicSession` | 330 | 330 |

`grep -c 'None'` → 0. `pyshacl -s kg/shapes/structural.ttl -df auto kg/out/capacity.nq` →
`Conforms: True` (vacuously — `structural.ttl` only targets `eat:ReferralState`).

## Functional Requirements
1. `kg/mappings/capacity.rml.ttl`, 6 `rr:TriplesMap`s (one per table — no nullable columns
   means no filtered companions), all with constant `rr:graphMap` `…/kg/graph/inputs`:
   - `HospitalMap` — `eat:Hospital`.
   - `HospitalServiceMap` — the n-ary node: `eat:HospitalService`, `eat:providedBy` →
     hospital IRI, `eat:forSpecialty` → the reference-layer specialty concept IRI.
   - `WardMap` — `eat:Ward`, `eat:atHospital` → hospital IRI (domain widened for exactly
     this by `add-missing-data-layer_20260903`).
   - `BedAllocationMap` — the other n-ary node: `eat:BedAllocation`, `eat:inWard` → ward IRI,
     `eat:forSpecialty` → specialty concept IRI, `eat:nominalBeds`, `eat:isPrimaryWard`
     (source column `is_primary`, per requirements.md §4's divergence table).
   - `BedStatusMap` — `eat:BedStatus`, `eat:statusOf` → ward IRI, plus
     `eat:occupiedBeds`/`eat:freeBeds`/`eat:outlierPatients` from `occupied`/`free`/`outliers`
     (per the same divergence table) and the remaining literal properties.
   - `ClinicSessionMap` — `eat:ClinicSession`, `eat:sessionOf` → the `eat:HospitalService`
     IRI for that hospital+specialty.
2. `kg/mappings/capacity.ini` — git-ignored, not committed.
3. `namespaces.md` §4: `BedStatus` template corrected to `{snapshot_datetime}`;
   `ClinicSession` row's note updated to record that it was confirmed, not just flagged.
4. No column whose values appear in `core.ref_codes` exists in any of these six tables —
   checked against the confirmed 8-table list; none of `hospital_type`, `ward_type`,
   `gar_status` are `ref_codes` code_tables, so all stay literals, correctly.

## Acceptance Criteria
- `kg/mappings/capacity.rml.ttl` exists; materialised output matches every count above exactly.
- Zero `"None"`; `pyshacl` conforms.
- `namespaces.md` §4's `BedStatus` template is corrected.
- No file outside `kg/mappings/capacity.rml.ttl`, `namespaces.md` §4, and this track's own
  directory is touched.

## Out of Scope
- SHACL shapes for the new classes.
- Any change to `kg/queries/wait_counters.rq` or the mapping tracks already committed.
