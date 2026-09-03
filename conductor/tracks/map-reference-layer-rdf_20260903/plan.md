# Implementation Plan — Map the reference layer to RDF

### Phase 1 — Write and run the mapping
- [x] Task: Write `kg/mappings/reference_layer.rml.ttl` (9 triples maps).
- [x] Task: Write `kg/mappings/reference_layer.ini` (git-ignored, not committed).
- [x] Task: Ran `python -m morph_kgc mappings/reference_layer.ini` from `kg/`; 182 triples,
      zero `"None"`.
- [x] Task: Ran `pyshacl -s shapes/structural.ttl -df auto out/reference_layer.nq`;
      `Conforms: True`.
- [x] Task: Verified concept-count-per-scheme against Postgres row counts — all match
      exactly (see spec.md's table).

### Phase 2 — Amend ontology.md §6
- [x] Task: Added the 4th CPC concept (code 4, "Excluded") to §6's worked example and prose.
- [x] Task: Conductor - User Manual Verification 'Reference layer mapped' (Protocol in
      workflow.md) — confirmed all three verification checks pass on a fresh run against the
      committed files (not just the planning draft), and that `git status` shows only
      `conductor/kg/ontology.md` and `kg/mappings/reference_layer.rml.ttl` changed.
