# Tus-Aite-TechIreland-Challenge: the knowledge graph

An RDF/OWL knowledge graph built from the synthetic Irish outpatient waiting list, and the
declarative pipeline that produces, validates and loads it. Built for the TechIreland
National AI Challenge 2026.

**This directory is the graph layer.** The dataset it reads from lives in
[`../dataset/`](../dataset/); the agents and the clinician interface are built elsewhere
and are not described here.

The graph exists so that a ranked referral can be explained: every position traces back
through `eat:cites` edges to the exact evidence that produced it. Nothing here ranks
anything — it builds the substrate the agents reason over.

## Get it running

The dataset must be loaded first (see [`../dataset/README.md`](../dataset/README.md)).
Then, from this directory:

```bash
cp .env.example .env      # add a password for the kg_loader role
make kg-views             # create the Type-2 view and the loader role
python -m morph_kgc mappings/<name>.ini   # once per mapping, five in total
```

Full setup, including loading into Oxigraph and verifying the result, is in
[docs/GETTING_THE_GRAPH.md](docs/GETTING_THE_GRAPH.md).

## Documentation

| | |
|---|---|
| [docs/GETTING_THE_GRAPH.md](docs/GETTING_THE_GRAPH.md) | **Start here.** Prerequisites, building the graph, loading it, checking it worked |
| [docs/HOW_THE_GRAPH_WAS_BUILT.md](docs/HOW_THE_GRAPH_WAS_BUILT.md) | The tech stack and why each piece, the five design decisions, what the build disproved, known limitations |
| [`../conductor/kg/`](../conductor/kg/) | The normative specification: requirements, namespaces, decisions, ontology |

The four files under `conductor/kg/` are authoritative. They live there rather than here
because the Conductor plugin's agents read `conductor/` as project context; where those
files and anything in `docs/` disagree, `conductor/kg/` wins.

| | |
|---|---|
| [`../conductor/kg/requirements.md`](../conductor/kg/requirements.md) | Normative requirements, measured facts, gotchas, verification procedure |
| [`../conductor/kg/namespaces.md`](../conductor/kg/namespaces.md) | Prefixes, IRI templates per class, named graphs. Authoritative on anything IRI-shaped |
| [`../conductor/kg/decisions.md`](../conductor/kg/decisions.md) | The five design decisions with their reasoning |
| [`../conductor/kg/ontology.md`](../conductor/kg/ontology.md) | Every class and property with domain, range and cardinality |

Per-track specifications, plans and decisions are under
[`../conductor/tracks/`](../conductor/tracks/), one directory per unit of work.

## What is in it

**590,814 triples** across two named graphs, built from the 17 input tables of the `full`
dataset profile. `eval.ground_truth` contributes nothing, by construction.

| Graph | Triples | Holds |
|---|---|---|
| `…/kg/graph/inputs` | 590,632 | Referrals, states, patients, clinical, capacity, events |
| `…/kg/graph/reference` | 182 | SKOS concept schemes and rules from `ref_*` |

Headline node counts, each verified against its Postgres row count:

| | |
|---|---|
| `eat:Referral` | 5,200 |
| `eat:ReferralState` | 13,772 (from 70,022 daily rows) |
| `eat:Patient` / `eat:Person` | 5,200 / 3,412 |
| `sosa:Observation` | 52,000 across 5,200 `eat:ObservationEvent` |
| `eat:Condition` | 6,977 |
| `eat:CancellationEvent` / `eat:SuspensionEvent` | 1,636 / 221 |
| `eat:BedStatus` | 840 |
| Patients with no national identifier | **1,788** |

That last number is the point of Decision 4, and it is a query result rather than a stored
fact — see [docs/HOW_THE_GRAPH_WAS_BUILT.md](docs/HOW_THE_GRAPH_WAS_BUILT.md).

## How it is built

Table-to-triple mapping is **declarative**, not a loader script: five R2RML mapping files
executed by Morph-KGC directly against Postgres. The mappings are reviewable artifacts —
for a project whose selling point is auditability, "here is the mapping that produced this
triple" is worth more than a script nobody reads.

Logic a mapping language cannot express — window functions for Type-2 change detection —
lives in a committed SQL view, `sql/001_v_referral_state.sql`, testable in psql
independently of any RDF tooling.

## Layout

```
kg/
├── ontology/eat.ttl          # the TBox: classes, properties, units, CPC ordering
├── mappings/                 # five R2RML files + their Morph-KGC .ini configs
│   ├── referral_state.rml.ttl    # referrals, states, triage events, patients, persons
│   ├── reference_layer.rml.ttl   # ref_codes, ref_specialty, ref_rules → SKOS
│   ├── events.rml.ttl            # cancellations, suspensions + time:Interval
│   ├── capacity.rml.ttl          # hospitals, services, wards, beds, clinics
│   └── clinical.rml.ttl          # conditions, observations
├── shapes/structural.ttl     # 19 SHACL node shapes
├── queries/wait_counters.rq  # the shared wait-counter fragment
├── sql/                      # Type-2 view, read-only loader role
├── tests/                    # coverage, loader isolation, wait-counter validation
└── Makefile                  # re-applies the SQL after a dataset reset
```

`.ini` files carry the loader password and are git-ignored, as is `out/`.
