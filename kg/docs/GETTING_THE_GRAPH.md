# Getting the Graph

Everything needed to go from a loaded dataset to a queryable knowledge graph.

Companion documents: [`HOW_THE_GRAPH_WAS_BUILT.md`](HOW_THE_GRAPH_WAS_BUILT.md) for the
design and the tech stack, [`../../conductor/kg/`](../../conductor/kg/) for the normative
specification.

---

## 1. What you need

**The dataset, loaded, at the `full` profile.** The graph is built directly from Postgres,
so [`../../dataset/docs/GETTING_THE_DATA.md`](../../dataset/docs/GETTING_THE_DATA.md) must
be complete first. Verify:

```sql
SELECT count(*) FROM core.referral_daily;   -- 70,022 on full
```

If that returns a smaller number you are on `sample`; run
`make load FETCH_PROFILE=full` in `dataset/`. Every count in this document assumes `full`.

**Docker**, running, for both Postgres and Oxigraph.

**Python 3.11+** with these packages. The versions are the ones this graph was built and
verified with:

```bash
pip install morph-kgc==2.10.0 pyshacl==0.31.0 "psycopg[binary]" "sqlalchemy>=2.0"
```

`owlrl` and `rdflib` arrive as pySHACL dependencies. `pyoxigraph` arrives with Morph-KGC
and is **pinned at 0.3.22** — `queries/wait_counters.rq` documents a workaround for a
version-specific quirk in it.

Two version constraints that will bite otherwise:

- **SQLAlchemy must be ≥ 2.0.** Older versions have no `postgresql+psycopg` dialect and
  fail with `NoSuchModuleError`.
- A **virtualenv is worth it**. Installing into a conda base environment produces
  dependency conflicts with conda's own `ruamel-yaml` and `pydantic`.

## 2. Database objects

Two things live in Postgres rather than in the mappings: the Type-2 change-detection view,
because window functions cannot be expressed in R2RML, and a read-only role.

```bash
cp .env.example .env        # then edit, see below
make kg-views               # applies sql/001 and sql/002
```

Then set the role's password, which is deliberately absent from the committed SQL. `docker-compose.yml`
lives at the repo root (db, pgadmin, loader, oxigraph and retrieval are all one compose project there):

```bash
cd ..
docker compose exec -T db psql -U triage_admin -d triage \
  -c "ALTER ROLE kg_loader PASSWORD 'the value from kg/.env';"
```

`make kg-views` will report `ERROR: role "kg_loader" already exists` on any run after the
first. That is expected and ignored — the Makefile prefixes that line with `-`.

### What goes in `.env`

`kg/.env` is git-ignored.

| | Set it to |
|---|---|
| `KG_LOADER_PASSWORD` | Anything. Local-only |
| `KG_DB_URL` | The same password, inside the connection string |
| `KG_OUTPUT_DIR` | Leave it |

You will also need the same connection string exported for the test scripts, in the plain
`postgresql://` form without the `+psycopg` suffix:

```bash
export KG_DB_URL_PSYCOPG="postgresql://kg_loader:$(grep KG_LOADER_PASSWORD .env | cut -d= -f2)@localhost:5433/triage"
```

Note **5433**. That is Postgres from your own machine. Port 5050 is pgAdmin's web
interface and 7878 is Oxigraph — three different services.

### Why the role exists

`kg_loader` has `SELECT` on `core`, `agent` and `kg`, and **no grant at all on `eval`**.
`eval.ground_truth` records which patients actually deteriorated; if the ranking system
could read it, it would score perfectly by looking up the answer. The mappings connect as
`kg_loader`, so a mapping that references it fails with a permission error rather than
succeeding quietly. Confirm:

```bash
tests/test_loader_isolation.sh      # PASS: eval.ground_truth is unreachable
```

## 3. Checking the view

```sql
SELECT count(*) FROM kg.v_referral_state;                        -- 13,772
SELECT count(*) FROM kg.v_referral_state WHERE valid_to IS NULL; -- 5,200
SELECT count(*) FROM kg.v_referral_state WHERE valid_to < valid_from; -- 0
```

13,772 states over 5,200 referrals: 5,200 first appearances and 8,572 real transitions,
from 70,022 daily rows. The second figure equals the referral count because no referral in
the `full` profile has a `removal_date` — see limitations in
[`HOW_THE_GRAPH_WAS_BUILT.md`](HOW_THE_GRAPH_WAS_BUILT.md).

## 4. Building the triples

Five mappings, each with its own `.ini`. Run them **from `kg/`** — paths inside a
Morph-KGC `.ini` are relative to the working directory, not to the `.ini` file:

```bash
python -m morph_kgc mappings/referral_state.ini
python -m morph_kgc mappings/reference_layer.ini
python -m morph_kgc mappings/events.ini
python -m morph_kgc mappings/capacity.ini
python -m morph_kgc mappings/clinical.ini
```

Expected output, which is also the verification:

| Mapping | Triples | Produces |
|---|---|---|
| `referral_state` | 209,560 | Referrals, states, triage events, patients, persons |
| `reference_layer` | 182 | 8 SKOS schemes, 31 concepts, 7 specialties, 5 rules |
| `events` | 10,832 | 1,636 cancellations, 221 suspensions, 221 intervals, 442 instants |
| `capacity` | 12,955 | 6 hospitals, 42 services, 20 wards, 45 allocations, 840 bed statuses, 330 clinic sessions |
| `clinical` | 357,285 | 6,977 conditions, 5,200 observation events, 52,000 observations |
| **Total** | **590,814** | |

Then, per mapping, two checks:

```bash
grep -c 'None' out/<name>.nq      # must be 0
head -1 out/<name>.nq             # must end with a graph IRI before the final period
```

The first is not optional. **Morph-KGC materialises SQL NULLs as the literal string
`"None"`** — a nullable column mapped directly produces `"None"^^xsd:date`, an ill-typed
literal asserting something false. Every nullable column needs its own triples map
filtering `IS NOT NULL`; the existing mappings do this throughout.

## 5. Loading into Oxigraph

From the repository root:

```bash
docker compose up -d oxigraph
curl -s http://localhost:7878/query --data-urlencode "query=ASK {?s ?p ?o}" \
  -H "Accept: application/sparql-results+json"        # {"boolean":false} — reachable, empty
```

```bash
for f in kg/out/*.nq; do
  curl -s -X POST http://localhost:7878/store \
    -H "Content-Type: application/n-quads" --data-binary "@$f"
done
```

`clinical.nq` is around 117 MB and takes longest.

## 6. Checking it worked

**Graph sizes.** Note the `GRAPH ?g` — everything is quad-tagged into named graphs, so a
query without it sees only the empty default graph and silently returns nothing:

```bash
curl -s http://localhost:7878/query \
  --data-urlencode "query=SELECT ?g (COUNT(*) AS ?n) WHERE { GRAPH ?g { ?s ?p ?o } } GROUP BY ?g" \
  -H "Accept: application/sparql-results+json"
```

Two graphs: `…/kg/graph/inputs` at 590,632 and `…/kg/graph/reference` at 182. A third,
unnamed group means a mapping is emitting untagged triples.

**The boundary that matters most** — no decision-layer predicate may appear in an input
graph. Must return `false`:

```sparql
PREFIX eat: <https://nonsocynthia.github.io/Tus-Aite-TechIreland-Challenge/kg/ns#>
ASK {
  GRAPH ?g { ?s ?p ?o }
  FILTER(STRSTARTS(STR(?g), "https://nonsocynthia.github.io/Tus-Aite-TechIreland-Challenge/kg/graph/inputs"))
  FILTER(?p IN (eat:cites, eat:position, eat:scoreValue, eat:passed))
}
```

**The answer key left no trace.** Must return 0:

```sparql
SELECT (COUNT(*) AS ?n) WHERE {
  ?s ?p ?o . FILTER(CONTAINS(STR(?s), "ground-truth") || CONTAINS(STR(?s), "ground_truth"))
}
```

**Decision 4's number.** Patients whose records cannot be linked to a national identity —
expect **1,788**:

```sparql
PREFIX eat: <https://nonsocynthia.github.io/Tus-Aite-TechIreland-Challenge/kg/ns#>
SELECT (COUNT(?p) AS ?unlinkable) WHERE {
  GRAPH ?g {
    ?p a eat:Patient .
    FILTER NOT EXISTS { ?p eat:isRecordOf ?person }
  }
}
```

**The test suite:**

```bash
python tests/test_column_coverage.py        # every source column carried or excluded
python tests/test_wait_counters_sample.py   # 473/473 rows match core.referral_daily
tests/test_loader_isolation.sh              # eval unreachable
```

**SHACL, against the union of all five files** — not file by file:

```bash
cat out/*.nq > /tmp/all.nq
python -m pyshacl -s shapes/structural.ttl -df auto /tmp/all.nq
```

`Conforms: True`. This takes roughly 20 minutes; run it in the background. Per-file
validation gives false negatives for any constraint spanning two mappings —
`eat:Referral` is minted by `referral_state.rml.ttl` but its conditions come from
`clinical.rml.ttl`, so `eat:hasCondition`'s cardinality fails per-file and passes on the
union.

## 7. When it goes wrong

| What you see | Fix |
|---|---|
| `NoSuchModuleError: sqlalchemy.dialects:postgresql.psycopg` | SQLAlchemy is below 2.0. `pip install --upgrade "sqlalchemy>=2.0"` |
| `FileNotFoundError: <name>.rml.ttl` | Run Morph-KGC from `kg/`, not from the repo root. `.ini` paths are relative to the working directory |
| `relation "kg.v_referral_state" does not exist` | Run `make kg-views`. A `make reset` in `dataset/` drops it |
| `permission denied for schema eval` | Correct. That is the isolation test passing. See section 2 |
| `fe_sendauth: no password supplied` from a test script | `KG_DB_URL_PSYCOPG` is not exported in this shell. See section 2 |
| `"None"` appears in a `.nq` file | A nullable column is mapped without an `IS NOT NULL` triples map. See section 4 |
| `Exception: Unknown namespace prefix : eat` from pySHACL | A `sh:sparql` constraint cannot see Turtle `@prefix` declarations. It needs `sh:prefixes` pointing at the `sh:declare` block in `shapes/structural.ttl` |
| A SPARQL query returns nothing that should return rows | It is probably reading the default graph. Wrap the pattern in `GRAPH ?g { … }` |
| `adjustedWaitDays` equals the unadjusted wait | `queries/wait_counters.rq` has no GRAPH clause by design. A consumer must wrap it in `GRAPH <…/kg/graph/inputs> { … }` or it matches nothing and fails silently |
| pySHACL appears to hang | It prints nothing until it finishes. On the full graph, allow 20+ minutes. Check with `ps aux \| grep pyshacl` |
| `container name "/triage_db" is already in use` | Another copy of the dataset project is running. Postgres runs once, from one checkout |

## 8. Versions

| | |
|---|---|
| Dataset | schema 008, data `v1.1`, `full` profile |
| Morph-KGC | 2.10.0 |
| pySHACL | 0.31.0 |
| owlrl | 7.1.4 |
| rdflib | 7.2.1 |
| pyoxigraph | **0.3.22, pinned** |
| Oxigraph server | 0.5.11 |
| SQLAlchemy | ≥ 2.0 |
