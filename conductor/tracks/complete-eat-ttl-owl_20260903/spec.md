# Complete the eat.ttl OWL ontology

## Overview
`kg/ontology/eat.ttl` is currently a five-term stub (`Referral`, `ReferralState`, `stateOf`,
`validFrom`, `validTo`). This track completes the TBox exactly as specified in
`conductor/kg/ontology.md`, using `conductor/kg/namespaces.md` as the authority on IRIs/prefixes
and `conductor/kg/decisions.md` for the reasoning behind property shapes (units, CPC ranking,
rationale text, person/patient split). Track 1 of the KG build; everything else (mappings,
shapes, reference layer) depends on it.

## Background
- Normative source: `conductor/kg/ontology.md` (§1 vocab reuse, §2 classes, §3/§4 properties,
  §5 observation subclasses, §6 CPC scheme, §7 explicit exclusions).
- `namespaces.md` fixes prefixes (`eat:` vocabulary vs `eatd:` instances) and datatype rules.
- `decisions.md` §3 gives the exact turtle for `qudt:hasUnit` on six observable-property
  individuals — confirmed in-scope per user answer, even though `ontology.md` §5 only lists
  the three subclasses.

## Functional Requirements
1. Add `@prefix` lines for every namespace used: `eatd`, `prov`, `sosa`, `time`, `skos`, `dcat`,
   `void`, `sct`, `sh`, `qudt`, `unit` (existing `eat`, `owl`, `rdfs`, `xsd` stay).
2. Declare every class in ontology.md §2 not already present: `Person`, `Patient`, `TriageEvent`,
   `CPC` (⊑ `skos:Concept`), `TriageOutcome` (⊑ `skos:Concept`), `Condition`, `ObservationEvent`
   (⊑ `sosa:Sampling`), `SuspensionEvent`, `CancellationEvent`, `Hospital`, `HospitalService`,
   `Specialty` (⊑ `skos:Concept`), `Ward`, `BedAllocation`, `BedStatus`, `ClinicSession`, `Rule`.
   Plus the decision-layer classes implied as domain/range in §4 (not tabulated in §2 but
   required for the properties to typecheck): `Score`, `Decision`, `RankedPlacement`,
   `RuleCheck`, `Override`, `Rationale`.
3. Declare every property in §3 with `rdfs:domain`, `rdfs:range`, and cardinality
   (`owl:FunctionalProperty` where max-card is 1; comment noting min-card where >1 or 0..n).
   Includes the already-present `stateOf`/`validFrom`/`validTo` (left as-is) plus:
   `isRecordOf`, `atHospital`, `forPatient`, `referredToService`, `hasTriageEvent`,
   `assignedCategory`, `outranks` (transitive), `hasCondition`, `icd10amCode`, `snomedCode`,
   `hasObservationEvent`, `providedBy`, `forSpecialty`, `inWard`, `statusOf`, `sessionOf`,
   `hasSuspension`, `hasCancellation`. Also add local `rdfs:domain`/`rdfs:range` refinement
   triples for the reused `sosa:hasMember`, `sosa:observedProperty`,
   `sosa:hasFeatureOfInterest`.
4. Declare every property in §4 similarly: `scored`, `scoreValue`, `method`, `agentVersion`,
   `cites` (`rdfs:subPropertyOf prov:used`), `citesUrgencyEvidence`, `citesCapacityEvidence`,
   `citesTimeframeEvidence`, `citesMultiListEvidence` (all `rdfs:subPropertyOf eat:cites`),
   `hasPlacement`, `position`, `ranks`, `withinCategory`, `testedRule`, `passed`, `revises`,
   `reason`, `acceptedWarning`, `rationaleText`, `promptHash`. Plus local domain/range
   refinement on reused PROV terms `wasGeneratedBy`, `wasAssociatedWith`, `wasDerivedFrom`,
   `used`, `wasAttributedTo`. `eat:severityRank` / `eat:crtDays` (domain `CPC`) are added here
   too since §6 requires them for ordering.
5. Add the three `sosa:ObservableProperty` subclasses from §5: `MeasuredVital`,
   `ReportedSymptom`, `ClinicalAssessment`, with the exact column mapping recorded as
   `rdfs:comment`.
6. Add the observable-property individuals per decisions.md §3: `heartRate`,
   `respiratoryRate`, `systolicBP`, `diastolicBP`, `temperature`, `oxygenSaturation` (`a
   eat:MeasuredVital`, with `qudt:hasUnit`); `pain`, `chiefComplaint` (`a
   eat:ReportedSymptom`, no unit); `avpu`, `news2`, `mtsCategory`, `ictsCategory` (`a
   eat:ClinicalAssessment`, no unit), each with a comment stating why no unit applies.
7. Add the CPC scheme from §6 verbatim (adapted to full IRIs, per namespaces.md's slash rule):
   `eat:CPCScheme a skos:ConceptScheme`, the three `eatd:cpc/{1,2,3}` concepts with
   `skos:inScheme`, `skos:notation`, `eat:severityRank`, `eat:crtDays` (only on 1 and 3), and
   the `outranks` instance triples.
8. Do not touch `kg/mappings/`, `kg/shapes/`, `kg/sql/`, or any other file — ontology only.
9. Do not invent any class/property absent from `ontology.md`/`decisions.md` — if a further
   gap turns up while writing, stop and report it rather than guessing.

## Non-Functional Requirements
- Valid Turtle: parses cleanly.
- Lowercase IRI paths only; instance-style example IRIs (CPC concepts) written as full
  `<https://…/kg/id/…>` IRIs in angle brackets, never as `eatd:cpc/1` (Oxigraph slash rule).
- Consistent style with the existing stub: `a owl:Class`/`owl:ObjectProperty`/
  `owl:DatatypeProperty` declarations, `rdfs:comment` for the "why", grouped by §2/§3/§4/§5/§6
  with a section-heading comment matching ontology.md's structure.

## Acceptance Criteria
- Every class named in ontology.md §2 exists as `owl:Class` in `eat.ttl`, correctly subclassed
  to `skos:Concept` / `sosa:Sampling` where specified.
- Every property in §3 and §4 exists with `rdfs:domain`, `rdfs:range`, and a cardinality
  annotation (functional where max=1), matching the table exactly.
- The three §5 subclasses exist, plus the observable-property individuals with units per
  decisions.md §3 exactly (six units, seven with none).
- The §6 CPC scheme block matches the ontology.md turtle example, with full IRIs per the
  slash rule.
- No triples touching `kg/mappings/`, `kg/shapes/`, or `kg/sql/`.
- No class or property appears that isn't traceable to ontology.md or decisions.md §3/§6.

## Out of Scope
- SHACL shapes (`kg/shapes/`) — separate "Shapes" track.
- RML mappings (`kg/mappings/`) — separate A/B/C/D/E tracks.
- `kg/queries/wait_counters.rq` — separate track (#2).
- Reference-layer SKOS concepts for `ref_specialty` / `ref_codes` (other than CPC) /
  `ref_rules` — track 3.
- `owl:Restriction` cardinality axioms or `sh:` shapes for structural enforcement —
  decisions.md §2 explicitly assigns that job to SHACL, not OWL.
