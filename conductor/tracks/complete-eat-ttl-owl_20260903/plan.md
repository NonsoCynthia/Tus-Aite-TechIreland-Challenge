# Implementation Plan — Complete the eat.ttl OWL ontology

### Phase 1 — Write the complete ontology
- [x] Task: Add all missing `@prefix` declarations to `eat.ttl`, matching `namespaces.md` §1
      exactly.
- [x] Task: Add §2 data-layer classes (all `owl:Class`, with `rdfs:comment` from the "Notes"
      column, and `rdfs:subClassOf skos:Concept` / `sosa:Sampling` where specified).
- [x] Task: Add §4's implied decision-layer classes (`Score`, `Decision`, `RankedPlacement`,
      `RuleCheck`, `Override`, `Rationale`) as `owl:Class`.
- [x] Task: Add all §3 data-layer properties with domain/range/cardinality, plus the three
      reused-SOSA-term domain/range refinements.
- [x] Task: Add all §4 decision-layer properties with domain/range/cardinality, the four
      `cites*` sub-properties, `severityRank`/`crtDays`, plus the reused-PROV-term domain/range
      refinements.
- [x] Task: Add the three §5 `sosa:ObservableProperty` subclasses.
- [x] Task: Add the observable-property individuals (13) with `qudt:hasUnit` on the six that
      take one, per decisions.md §3.
- [x] Task: Add the §6 CPC scheme (`CPCScheme`, three concepts, `severityRank`, `crtDays`,
      `outranks` instance triples) with full bracketed IRIs.
- [ ] Task: Conductor - User Manual Verification 'Ontology complete' (Protocol in workflow.md)
      — re-read `eat.ttl` end-to-end against the ontology.md checklist (§2/§3/§4/§5/§6), confirm
      nothing outside `kg/ontology/eat.ttl` changed.
