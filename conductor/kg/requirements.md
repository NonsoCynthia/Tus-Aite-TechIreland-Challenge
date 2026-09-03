# Knowledge graph track — specification

**Read `namespaces.md`, `decisions.md` and `ontology.md` before writing anything.** Treat
`namespaces.md` as authoritative over anything you would otherwise infer.

Base branch for every workspace: `feature/knowledge-graph`, not `main`.

---

## 1. What exists already

A vertical slice is built and committed. It is the worked example for everything else.

| Artifact | State |
|---|---|
| `kg/sql/001_v_referral_state.sql` | Type-2 change-detection view. 13,772 states over 5,200 referrals on `full` |
| `kg/sql/002_kg_loader_role.sql` | `kg_loader` role. No grant on schema `eval` |
| `kg/ontology/eat.ttl` | Five-term stub — `Referral`, `ReferralState`, `stateOf`, `validFrom`, `validTo` |
| `kg/mappings/referral_state.rml.ttl` | Two triples maps. 49,888 triples, validated |
| `kg/shapes/structural.ttl` | Structural + interval shapes. `Conforms: True` |
| `kg/tests/test_loader_isolation.sh` | Passing |
| `kg/Makefile` | `make kg-views` re-applies both SQL files after a reset |

`002` has only ever run against a database where `kg_loader` already existed, so it always
errors on `CREATE ROLE`. **It is unverified on a clean database.**

## 2. Measured facts about the loaded data

Use these numbers, not the ones in the design deck, which predate measurement.

| Fact | Value | Profile |
|---|---|---|
| `core.referral_daily` rows | 70,022 | `full` |
| Distinct referrals | 5,200 | `full` |
| `kg.v_referral_state` rows | 13,772 | `full` |
| — of which first appearances | 5,200 | |
| — of which real transitions | 8,572 | |
| Open intervals (`valid_to IS NULL`) | 5,200 | no referral in this profile has a `removal_date` |
| Inverted intervals | 0 | |
| `referral_state` triples | 49,888 | |

The `full` profile has no removals, so the removal-closing branch of `valid_to` is
**correct but untested by the data**. Do not assume it has been exercised.

The design deck states ~110,000 rows and ~6,000 referrals, and derives its triple-count
estimates (~500k vs ~1.6M) from that base. Those figures are wrong. Correct the deck
before it is shown.

## 3. Normative requirements

### R1 — Referral state

- A `eat:ReferralState` **MUST** be minted only where the material-field tuple differs
  from the previous `as_of_date` for the same `(hospital_hipe, pathway_number)`.
- The material fields are exactly: `triage_status`, `triage_event_id`, `appointment_date`,
  `arrived_date`, `last_cancellation_date`, `suspension_start_date`,
  `suspension_end_date`, `removal_date`, `high_clinical_or_social_needs`,
  `specialty_hipe`. **The four wait counters are not material fields** — they change daily
  by construction and would mark every row changed.
- Change detection **MUST** live in `kg.v_referral_state`, not in a mapping. Mappings
  carry the shape of triples, never logic.
- `eat:validTo` **MUST** be absent for a live referral's current state, and equal to
  `removal_date` where the referral was removed.
- States for one referral **MUST NOT** overlap. Intervals are half-open:
  `validFrom <= d < validTo`.

### R2 — Wait counters

- `days_since_referral`, `days_since_received`, `days_awaiting_triage` and
  `adjusted_wait_days` **MUST NOT** be materialised as triples.
- They **MUST** be derived by a single shared SPARQL fragment in `kg/queries/`, used
  unmodified by every agent and by the rule checker.
- `adjusted_wait_days` **MUST** subtract suspended time, which requires
  `eat:SuspensionEvent` nodes carrying `time:Interval`.

### R3 — Identity

- `eat:Person` **MUST NOT** be minted where `ihi_number` is null. No placeholder, no blank
  node.
- `eat:isRecordOf` is functional.
- **No blank nodes anywhere in the input layer.** A blank node cannot be cited.

### R4 — Units

- `qudt:hasUnit` **MUST** be declared on the observable property in the ontology, once.
- No `sosa:Observation` may carry a unit of its own.
- `pain`, `chiefcomplaint`, `avpu`, `news2`, `mts_category`, `icts_category` **MUST NOT**
  be given units.

### R5 — Isolation

- No triple derived from `eval.ground_truth` may exist in any graph.
- No mapping may connect as `triage_admin`. All mappings use `kg_loader`.
- No decision-layer predicate may appear in an input graph.
- No agent query may read `…/graph/rationale`.

### R6 — Codes

- Every value that appears in `ref_codes` **MUST** become a `skos:Concept` IRI, never a
  bare literal.
- Ordering **MUST** use `eat:severityRank`. Any mapping or query that sorts by
  `code_value` is a defect.

## 4. Gotchas — read before your first run

These were found the hard way. Each will recur.

**Morph-KGC materialises SQL NULLs as the literal string `"None"`.** A nullable column
mapped directly produces `"None"^^xsd:date` — an ill-typed literal asserting something
false. **Filter NULLs in SQL, in a separate triples map**, as
`referral_state.rml.ttl` does:

```turtle
<#XClosedMap> a rr:TriplesMap ;
  rr:logicalTable [ rr:sqlQuery "SELECT * FROM … WHERE col IS NOT NULL" ] ;
  rr:subjectMap [ rr:template "…" ] ;          # no rr:class — already typed
  rr:predicateObjectMap [ … ] .
```

`referral_daily` alone has fourteen nullable columns. Check every one.
Verify with `grep -c 'None' <output>.nt` — expect 0.

**`sh:sparql` cannot see Turtle `@prefix` declarations.** Prefixes used inside a
`sh:select` string must be declared with `sh:declare` on an `owl:Ontology` node and
referenced with `sh:prefixes`. Without it: `Exception: Unknown namespace prefix`.

**`sh:sparql` constraints cost minutes, not seconds.** rdflib evaluates them per focus
node. 13,772 nodes took several minutes on 50k triples. Structural shapes run per mapping;
`sh:sparql` constraints run once at integration, scoped per hospital-day.

**Paths in a Morph-KGC `.ini` are relative to the working directory**, not to the `.ini`
file. Run from `kg/` and write `mappings/x.rml.ttl`.

**`postgresql+psycopg` needs SQLAlchemy ≥ 2.0.** Older SQLAlchemy only knows `psycopg2`
and fails with `NoSuchModuleError`.

**`make reset` in `dataset/` drops the `kg` schema and the loader role.** Run
`make kg-views` from `kg/` afterwards, then re-set the role password from `kg/.env`.

**Never run `make up` in a Conductor workspace.** Each workspace is a separate git
worktree with its own `dataset/`, and the second one hits `container name "/triage_db" is
already in use`. Postgres runs once, from the main checkout. Every workspace connects to
`localhost:5433`.

**`.env` is git-ignored, so no workspace inherits one.** Copy `kg/.env` into each
workspace, or copy `kg/.env.example` and fill it.

**`kg/mappings/*.ini` holds the loader password and is git-ignored.** Do not commit one,
and do not put a password in any `.sql` or `.ttl` file.

**Property names are deliberately readable and do not match column names.** The
source column for every property is in its `rdfs:comment` in `kg/ontology/eat.ttl`,
and that comment is normative for mappings — read it rather than assuming the
property name is the column. Known divergences:

| Property | Column |
|---|---|
| `eat:occupiedBeds` / `eat:freeBeds` / `eat:outlierPatients` | `occupied` / `free` / `outliers` |
| `eat:isPrimaryWard` | `is_primary` |
| `eat:snomedCode` | `snomed_ct_id` |
| `eat:gpPriority` | `priority_level_gp` |
| `eat:assignedCategory` | `triage_category` |
| `eat:hasHighClinicalOrSocialNeeds` | `high_clinical_or_social_needs` |
| `eat:sex` / `eat:dateOfBirth` | `patient_sex` / `patient_date_of_birth`, and the `person_*` equivalents |

**`sosa:hasSimpleResult` has no declared range**, because the datatype varies by
observed property — integer for `hr`, decimal for `temp`, string for
`mts_category`. Nothing in the ontology enforces it, so the shapes track must add
a `sh:datatype` constraint per observable property or ill-typed results will pass
validation.

## 5. Track order

Sequential, because everything depends on them:

| # | Track | Output |
|---|---|---|
| 1 | **Ontology** | `kg/ontology/eat.ttl` complete per `ontology.md`. One agent, no parallelism |
| 2 | **Wait-counter fragment** | `kg/queries/wait_counters.rq`. See §6 — this is a risk, not a formality |
| 3 | **Reference layer** | `ref_specialty`, `ref_codes`, `ref_rules` → SKOS. Every other mapping references these concept IRIs |

Then parallel, one workspace each:

| Track | Tables | Notes |
|---|---|---|
| **A/B** | `referral_daily`, `triage_events`, `patients`, `persons` | Hardest. Extends the existing `referral_state` mapping |
| **C** | `conditions`, `observations` | One obs row → many `sosa:Observation` nodes |
| **D** | `hospitals`, `hospital_specialty`, `wards`, `ward_specialty`, `bed_status`, `clinic_sessions` | Mostly mechanical; two n-ary nodes |
| **E** | `cancellation_events`, `suspension_events` | Suspensions need `time:Interval`; E blocks R2 |
| **Shapes** | — | Structural shapes for every class. Targets the ontology, not the data, so it runs alongside |

Then sequential again: **integration**, then **queries** (the `unlinkable` count, one
end-to-end citation walk).

## 6. The one real risk

Decision 1 stands or falls on `adjusted_wait_days` being cleanly derivable from
`validFrom` plus suspension intervals. **Nothing has tested this yet.** Write the
wait-counter fragment (track 2) before the A/B mapping, not after. If the derivation turns
out to be intractable in SPARQL, the fallback is to store `adjusted_wait_days` as a
literal on the state node with an annotation saying it is as-of-`validFrom` — but that is
a decision to take knowingly, not to discover after five mappings assume otherwise.

## 7. Verification

Per track, before the workspace is merged:

```bash
cd kg && python -m morph_kgc mappings/<track>.ini; cd ..
grep -c 'None' kg/out/<track>.nt          # expect 0
pyshacl -s kg/shapes/structural.ttl -df nt kg/out/<track>.nt
```

`Conforms: True` and zero `None` are both required. A mapping that has not been validated
is not done.

At integration:

- `sample` first, `full` second. An overlap bug is findable in 609 referrals and invisible
  in 5,200.
- State-node count on `full` equals `SELECT count(*) FROM kg.v_referral_state`.
- `kg/tests/test_loader_isolation.sh` passes.
- No decision predicate appears in an input graph:

```sparql
ASK {
  GRAPH ?g { ?s ?p ?o }
  FILTER(STRSTARTS(STR(?g), "https://nonsocynthia.github.io/Tus-Aite-TechIreland-Challenge/kg/graph/inputs"))
  FILTER(?p IN (eat:cites, eat:position, eat:scoreValue, eat:passed))
}
```

Must return **false**.

- The same seed produces byte-identical output across two runs.

## 8. Loading and inference

Materialise to files first, not straight into the store. The output is diffable,
reviewable in a PR, and reloadable without re-running the mappings — which matters while
shapes are still changing. `morph_kgc.materialize_oxigraph()` is right once mappings are
stable.

Run `owlrl` for the inference closure **into a separate named graph**, and validate
**after** that step, or shapes depending on inferred types pass vacuously.

Oxigraph has no built-in reasoner and no SHACL engine. Both jobs happen at build time,
which suits this project: it keeps inference inspectable and deterministic.

## 9. Open questions

Settle these before the parallel tracks start.

1. **Verify `002` on a clean database** — needs one `make reset` cycle.
2. **Pin the QUDT version** in `versions.yml`.
3. **Confirm `clinic_sessions` column names** against schema 008; the IRI template in
   `namespaces.md` is inferred from documentation, not from the live schema.
4. **`sh:closed true` on shapes** — catches loader typos but rejects any property not
   explicitly listed. Decide per class rather than globally.

## 10. Resolved — do not relitigate

**Named graphs in the input layer** (resolved 2026-09-03). The design deck specified
`…/graph/inputs/{as_of_date}`. That split was written for a node-per-day model, which
Decision 1 replaced. Under Type 2 a `ReferralState` spans a date range and has no single
`as_of_date`, so it has no per-date graph to belong in; and replay is already a range
query over `validFrom`/`validTo`, so the graph name carries nothing the triples do not.
**The input layer is a single `…/kg/graph/inputs` graph.** Every input-layer mapping emits
N-Quads with a constant graph map. The run graphs stay per-run, so View 4's "drop one
graph and re-run" promise is unaffected.

`referral_state.rml.ttl` predates this and emits N-Triples with no graph. Updating it is
part of the A/B track.
