# Implementation Plan — Map referral_daily, triage_events, patients and persons to RDF

### Phase 1 — Correct the graph gap and extend the mapping
- [x] Task: Added a constant `…/kg/graph/inputs` graph map to `ReferralStateMap` and
      `ReferralStateClosedMap`; switched `referral_state.ini` to N-QUADS output.
- [x] Task: Checked `kg.v_referral_state`'s columns against the task's required
      `eat:ReferralState` properties; found `clinic_code`/`clinic_classification`/
      `removal_reason` missing from the view and designed the join-back approach.
- [x] Task: Checked `core.referrals` for `record_creation_date`; found it absent, designed
      the correlated-subquery approach (verified constant per referral, so exact).
- [x] Task: Wrote all new triples maps: `ReferralState*` (appointment/arrived/clinicCode/
      clinicClassification/removalReason + the three NOT-NULL columns added directly),
      `Referral*`, `TriageEvent*` (base + 5 filtered + hasTriageEvent link), `Patient*`/
      `Person*` (+ isRecordOf, filtered on `ihi_number IS NOT NULL`).
- [x] Task: Ran `python -m morph_kgc mappings/referral_state.ini` from `kg/`; 209,560
      triples, zero `"None"`.
- [x] Task: Ran `pyshacl -s shapes/structural.ttl -df auto out/referral_state.nq`;
      `Conforms: True`.
- [x] Task: Verified `ReferralState` (13,772), `Referral` (5,200), `TriageEvent` (4,212),
      `Patient` (5,200), `Person` (3,412) counts, and ran decisions.md §4's unlinkable-patient
      `FILTER NOT EXISTS` query against the materialised graph — 1,788, matching
      5,200 − 3,412 exactly.
- [x] Task: Conductor - User Manual Verification 'Input layer complete' (Protocol in
      workflow.md) — confirmed all verification checks pass on a fresh run against the
      committed files, and `git status` shows only `kg/mappings/referral_state.rml.ttl` and
      this track's own directory changed (the `.ini` is git-ignored).
