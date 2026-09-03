# Implementation Plan — Add missing data-layer literal properties

### Phase 1 — Amend ontology.md
- [x] Task: Move `referredToService` to `eat:ReferralState` in §3's table; add a short
      rationale note.
- [x] Task: Add the new property rows, grouped by class, to §3.
- [x] Task: Add the `sosa:hasSimpleResult` / `sosa:resultTime` refinement rows and the
      `time:hasTime` / `eat:atHospital`-domain-extension rows, each with a one-line rationale.
- [x] Task: Conductor - User Manual Verification 'ontology.md amended' (Protocol in
      workflow.md) — re-read the amended §2/§3 tables against the column-by-column audit and
      confirmed every gap has a corresponding row.

### Phase 2 — Amend eat.ttl to match
- [x] Task: Move `eat:referredToService`'s `rdfs:domain` to `eat:ReferralState` in `eat.ttl`.
- [x] Task: Add every new property from Phase 1 to `eat.ttl`.
- [x] Task: Add the `sosa:hasSimpleResult`/`sosa:resultTime` reused-term refinements and the
      `time:hasTime` refinement.
- [x] Task: Extend `eat:atHospital`'s `rdfs:domain` union to include `eat:Ward`.
- [x] Task: Validate with rdflib and report the new triple count.
- [x] Task: Conductor - User Manual Verification 'eat.ttl matches ontology.md' (Protocol in
      workflow.md) — confirmed every property in the amended `ontology.md` has an exact
      counterpart in `eat.ttl`, and that no mapping/shape/SQL file changed.
