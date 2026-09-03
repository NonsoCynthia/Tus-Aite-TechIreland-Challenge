# Implementation Plan — Map the six capacity tables to RDF

### Phase 1 — Write and run the mapping
- [x] Task: Checked every column across all six tables for nullability — none are nullable.
- [x] Task: Checked namespaces.md §4's templates for all six tables against the live schema;
      found and confirmed the `bed_status`/`clinic_sessions` findings.
- [x] Task: Write `kg/mappings/capacity.rml.ttl` (6 triples maps).
- [x] Task: Write `kg/mappings/capacity.ini` (git-ignored).
- [x] Task: Ran `python -m morph_kgc mappings/capacity.ini` from `kg/`; 12,955 triples, zero `"None"`.
- [x] Task: Ran `pyshacl -s shapes/structural.ttl -df auto out/capacity.nq`; `Conforms: True`.
- [x] Task: Verified all six class counts against Postgres — all match exactly.

### Phase 2 — Correct namespaces.md §4
- [x] Task: Corrected the `BedStatus` IRI template (`{status_datetime}` →
      `{snapshot_datetime}`); confirmed with the user before editing.
- [x] Task: Updated the `ClinicSession` row's note to record confirmation.
- [x] Task: Conductor - User Manual Verification 'Capacity tables mapped' (Protocol in
      workflow.md) — confirmed all verification checks pass on a fresh run, and `git status`
      shows only the stated files changed.
