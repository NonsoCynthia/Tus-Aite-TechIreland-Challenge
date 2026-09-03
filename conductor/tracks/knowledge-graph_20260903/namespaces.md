# Namespaces and IRI conventions

**Read this before writing any mapping, shape, or ontology term.** It is authoritative.
Where this file and your own judgement disagree, this file wins. If a case is genuinely
not covered here, stop and ask rather than inventing a convention — a divergent IRI
scheme is expensive to unwind once several mappings depend on it.

---

## 1. Prefixes

```turtle
@prefix eat:  <https://nonsocynthia.github.io/Tus-Aite-TechIreland-Challenge/kg/ns#> .
@prefix eatd: <https://nonsocynthia.github.io/Tus-Aite-TechIreland-Challenge/kg/id/> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix sosa: <http://www.w3.org/ns/sosa/> .
@prefix time: <http://www.w3.org/2006/time#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix dcat: <http://www.w3.org/ns/dcat#> .
@prefix void: <http://rdfs.org/ns/void#> .
@prefix sct:  <http://snomed.info/id/> .
@prefix sh:   <http://www.w3.org/ns/shacl#> .
@prefix qudt: <http://qudt.org/schema/qudt/> .
@prefix unit: <http://qudt.org/vocab/unit/> .
@prefix rr:   <http://www.w3.org/ns/r2rml#> .
@prefix owl:  <http://www.w3.org/2002/07/owl#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd:  <http://www.w3.org/2001/XMLSchema#> .
```

`eat:` is the **vocabulary** — classes and properties we define.
`eatd:` is **instance data** — the actual referrals, patients, wards.

The split exists so a class and an instance can never collide on one IRI, and so the
ontology can be published without dragging the data with it. Never mint an instance
under `eat:`, and never define a class or property under `eatd:`.

`eat` stands for Explainable Agent Triage. It is a local prefix, not a public
vocabulary. The IRI is what identifies a term; the prefix is a convenience.

## 2. Hosting and stability

The namespace resolves to GitHub Pages for the repo. This is deliberate: it is the most
stable URL we actually control.

- **No branch name ever appears in an IRI.** `feature/knowledge-graph` merges into
  `main` and the namespace must survive that.
- **Lowercase paths only.** IRIs are case-sensitive; mixed case is a permanent typo hazard
  across hundreds of mappings.
- A `w3id.org` redirect would be more permanent and needs a PR to their repo. Not worth
  blocking on for this challenge. If it happens later, it is a search-and-replace on the
  base, which is why nothing else about the IRI scheme may depend on the host.

## 3. Oxigraph slash rule

Turtle prefixed names cannot contain an unescaped `/`. Every instance IRI in this project
contains slashes, so in `.ttl` files **write instance IRIs as full IRIs in angle
brackets**, not as `eatd:referral/9001/PW-0412`.

```turtle
# WRONG — Oxigraph rejects this
eatd:referral/9001/PW-0412 a eat:Referral .

# RIGHT
<https://nonsocynthia.github.io/Tus-Aite-TechIreland-Challenge/kg/id/referral/9001/PW-0412>
    a eat:Referral .
```

In R2RML `rr:template` values, always write the full IRI string. Documentation and slides
may use the abbreviated `eatd:` form for readability; files may not.

## 4. IRI templates

Every IRI is minted from the composite keys the dataset already uses, so the same row
always produces the same node. **No blank nodes anywhere in the input layer** — a blank
node cannot be cited, and citability is the point of the project.

### The composite key rule

A hospital's patient number is unique inside that hospital only. The same is true of
pathway numbers. **Every instance IRI for a hospital-scoped entity begins with
`hospital_hipe`.** `PW-0412` alone is not an identifier.

| Entity | Template (relative to `eatd:`) | Source columns |
|---|---|---|
| Referral | `referral/{hospital_hipe}/{pathway_number}` | `referral_daily` |
| ReferralState | `referral-state/{hospital_hipe}/{pathway_number}/{valid_from}` | `kg.v_referral_state` |
| Patient | `patient/{hospital_hipe}/{patient_id}` | `patients` |
| Person | `person/{ihi_number}` | `persons` — national, not hospital-scoped |
| TriageEvent | `triage-event/{triage_event_id}` | `triage_events` — already globally unique |
| Condition | `condition/{hospital_hipe}/{pathway_number}/{icd10am_code}` | `conditions` |
| ICD-10-AM code | `icd10am/{icd10am_code}` | minted; no public IRI scheme exists |
| SNOMED code | `sct:{snomed_ct_id}` | referenced, never minted under `eatd:` |
| ObservationEvent | `obs-event/{hospital_hipe}/{pathway_number}/{obs_datetime}` | `observations`, one per row |
| Observation | `obs/{hospital_hipe}/{pathway_number}/{obs_datetime}/{column}` | one per non-null measured column |
| Hospital | `hospital/{hospital_hipe}` | `hospitals` |
| HospitalService | `service/{hospital_hipe}/{specialty_hipe}` | `hospital_specialty` |
| Specialty | `specialty/{specialty_hipe}` | `ref_specialty` |
| Ward | `ward/{hospital_hipe}/{ward_id}` | `wards` |
| BedAllocation | `bed-allocation/{hospital_hipe}/{ward_id}/{specialty_hipe}` | `ward_specialty` |
| BedStatus | `bed-status/{hospital_hipe}/{ward_id}/{status_datetime}` | `bed_status` |
| ClinicSession | `clinic-session/{hospital_hipe}/{clinic_code}/{session_date}` | `clinic_sessions` — **confirm column names against the live schema before use** |
| CancellationEvent | `cancellation/{hospital_hipe}/{pathway_number}/{cancellation_date}` | `cancellation_events` |
| SuspensionEvent | `suspension/{hospital_hipe}/{pathway_number}/{suspension_start_date}` | `suspension_events` |
| CPC concept | `cpc/{code_value}` | `ref_codes` where `code_table='triage_category'` |
| Other code concepts | `{code_table}/{code_value}` | `ref_codes`, one scheme per `code_table` |
| Rule | `rule/{rule_id}` | `ref_rules` |
| Score | `score/{run_id}/{hospital_hipe}/{pathway_number}/{agent}` | `agent_scores` |
| Decision | `decision/{hospital_hipe}/{as_of_date}` | `decisions` — one per hospital per day |
| RankedPlacement | `placement/{hospital_hipe}/{as_of_date}/{pathway_number}` | `decision_rankings` |
| RuleCheck | `rule-check/{run_id}/{hospital_hipe}/{pathway_number}/{rule_id}` | `rule_checks` |
| Rationale | `rationale/{hospital_hipe}/{as_of_date}/{pathway_number}` | never overwritten |
| Override | `override/{hospital_hipe}/{as_of_date}/{pathway_number}/{override_id}` | `overrides` |

Where a template above references a column you cannot find, **check the live schema and
report the discrepancy** rather than guessing a substitute. The templates were derived
from the dataset documentation, which is not always current with schema 008.

## 5. Named graphs

| Graph | Holds | Writable by |
|---|---|---|
| `…/kg/graph/ontology` | TBox, SKOS schemes, SHACL shapes | build only |
| `…/kg/graph/reference` | `ref_specialty`, `ref_codes`, `ref_rules` | build only |
| `…/kg/graph/inputs/{as_of_date}` | referrals, states, clinical, capacity | loader only, immutable after load |
| `…/kg/graph/provenance` | `dcat:Dataset`, `void:` counts, seed, HF release tag | build only |
| `…/kg/graph/run/{run_id}` | scores, citations, decisions, placements, rule checks | agents |
| `…/kg/graph/rationale` | generated rationale text | rationale generator only; **no agent reads it** |
| `…/kg/graph/overrides` | clinician actions, append-only | UI only |

**Known gap.** The `referral_state` mapping currently emits N-Triples with no graph.
Moving the input layer into `…/graph/inputs/{as_of_date}` requires N-Quads output and a
graph map in the mapping. This is unresolved and must be settled before the input-layer
mappings are considered complete — see `spec.md` §Open questions.

## 6. Literals and datatypes

- Dates: `xsd:date`. Timestamps: `xsd:dateTime`.
- Booleans: `xsd:boolean`, not `"1"`/`"0"`.
- Codes that appear in `ref_codes` become `skos:Concept` IRIs, **never** bare literals.
  A code value in a literal cannot be ordered, labelled, or linked.
- Measured values carry no unit of their own. The unit lives on the observable property.
  See `decisions.md` §3.
- Severity ordering uses `eat:severityRank`, **never** `code_value`. The real codes are
  Urgent 1, Routine 2, Semi-Urgent 3, so sorting by code silently puts Routine ahead of
  Semi-Urgent.
