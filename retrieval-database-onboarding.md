# Retrieval & database work — briefing for Claude Code

**Written for:** Edward's Conductor track covering database and retrieval work, so agents can query the graph.
**As of:** 4 September 2026, checked out on `main`.
**How to use this file:** read it first, before touching code. It orients you and points at the authoritative
files — it deliberately does not restate everything those files say, since they can drift out of sync with
this briefing and you can read them directly. Where this file states a number or a fact, it was verified
against the actual repo, not the original design-review deck (which is now stale in places — noted below).

## One-paragraph status

**Updated 2026-09-04, end of `retrieval-service_20260904`.** Two of three major phases were already done
and merged to `main`: the synthetic relational dataset (`dataset/`) and the full RDF/OWL knowledge graph
built on top of it (`kg/`) — 590,814 triples, loaded via a declarative R2RML/Morph-KGC pipeline, validated
by 19 SHACL shapes. ADR-002 (where agent outputs get written) is now **resolved and recorded** in
`conductor/tracks/explainable-agent-based-triage_20260828/decisions.md`, and **built**: `retrieval/` is a
standalone FastAPI service, its own container in the (now consolidated, single) root `docker-compose.yml`,
implementing exactly that decision — `POST /scores`, `/decisions`, `/overrides` write Postgres first and
project matching RDF triples into the graph only on success, plus read endpoints (wait counters wrapping
`kg/queries/wait_counters.rq` unmodified, a decision/evidence-audit-trail lookup, role-scoped evidence
lookup). See `retrieval/README.md` for the endpoint list and how to run it. The remaining phase — the
urgency/capacity/coordinating agents and the clinician UI
(`conductor/tracks/explainable-agent-based-triage_20260828/`) — has a written spec and is no longer
blocked; those agents should call this service rather than writing to Postgres or the graph directly.

## Authoritative files — read these directly, don't rely only on this briefing

| File | What it covers |
|---|---|
| `kg/docs/GETTING_THE_GRAPH.md` | Step-by-step build/verify guide: dependency versions, the five Morph-KGC mapping commands, expected triple counts, loading into Oxigraph, verification queries, troubleshooting table. **Start here** to stand up your environment. |
| `kg/README.md` | Graph layer overview, measured node/triple counts, directory layout. |
| `conductor/kg/namespaces.md` | Authoritative IRI-minting conventions, prefix list, and the named-graph table. |
| `conductor/kg/requirements.md` | Normative MUST/MUST NOT requirements (R1–R6) plus an essential **Gotchas** section — read it in full before writing any query or mapping. |
| `conductor/kg/decisions.md` | The five foundational design decisions, with real measured numbers behind each. |
| `kg/ontology/eat.ttl` | The actual TBox (class/property definitions). |
| `kg/mappings/*.rml.ttl` | The five R2RML mapping files (the real "loader" — declarative, not hand-written Python). |
| `kg/shapes/structural.ttl` | The 19 SHACL shapes. |
| `kg/queries/wait_counters.rq` | The one shared SPARQL fragment for the four wait-time counters — **read this as the template** for how any retrieval query in this project should be structured and shared, not reimplemented per-consumer. |
| `kg/sql/001_v_referral_state.sql` | Type-2 change-detection Postgres view (LAG/LEAD window functions) — the one piece of decision-1 logic that couldn't be expressed in R2RML. |
| `kg/sql/002_kg_loader_role.sql` | The `kg_loader` Postgres role: `SELECT` on `core` and `agent` schemas, explicitly **not** on `eval` (where `ground_truth` lives) — enforces isolation from the answer key at the database level. |
| `conductor/tracks.md` | Track registry — what's done, pending, superseded. |
| Root `README.md` | Product overview, architecture diagram, current build track status. |

## Resolved: ADR-002 — where do agent outputs get written?

**Decided and built, 2026-09-04.** Recorded in
`conductor/tracks/explainable-agent-based-triage_20260828/decisions.md`. Three options were on the table
(see the team's one-pager, "ADR-002 team questions," 4 Sep 2026): Postgres as record with the graph a copy,
graph-only, or both independently. The last was rejected outright as a repeat of the exact
divergence-risk failure mode decisions 1 and 2 (shared wait-counter fragment, shared SHACL shape file)
were designed to prevent.

**What was decided and built:** Postgres `agent.*` is the system of record. The graph gets a synchronous,
single-writer projection: one code path writes to Postgres first, and only pushes the corresponding RDF
triples (`eat:Score`, `eat:Decision`, `eat:RankedPlacement`, `eat:RuleCheck`, `eat:Override`, `eat:cites` +
its four role subproperties) into `run/{run_id}` (or `overrides`) if that write succeeds. This is
`retrieval/` — a standalone FastAPI service, its own container in the root `docker-compose.yml`,
implementing `POST /scores`, `/decisions`, `/overrides` plus read endpoints. It does not reuse the
Morph-KGC mapping files (built for batch runs, not low-latency single-row writes); it's a small,
purpose-built writer applying the same deterministic IRI conventions from `conductor/kg/namespaces.md` via
SPARQL Update, immediately after each Postgres commit. See `retrieval/README.md` for the endpoint list and
`conductor/tracks/retrieval-service_20260904/` for the full spec, plan, and implementation notes —
including two IRI-scheme gaps `namespaces.md` didn't cover (citation-evidence target IRIs, Activity/Agent
IRIs) that were filled with a documented convention rather than invented silently, worth a second pair of
eyes from whoever owns `conductor/kg/`.

**For the urgency/capacity/coordinating agents (`explainable-agent-based-triage_20260828`):** call this
service's write endpoints rather than writing to Postgres or the graph directly — that's the whole point
of the single-writer projection.

## Gotchas worth knowing before you touch anything

- **Named graphs — one correction since the design deck:** `inputs` was originally planned as one graph per
  loaded date. It shipped as a single graph instead, because a `ReferralState` (decision 1) can span a range
  of dates and can't cleanly live inside one day's graph. If you see the per-date version referenced
  anywhere else (older docs, the original PDF deck), it's stale — `conductor/kg/namespaces.md` is current.
- Turtle prefixed names can't contain unescaped `/` — instance IRIs must be written as full `<...>` IRIs
  (`eatd:referral/9001/PW-0412` breaks; the full angle-bracket form doesn't).
- Morph-KGC has a known NULL-handling bug (NULL can come out as the literal string `"None"`) — check for it
  after any new mapping.
- `wait_counters.rq` has an Oxigraph-specific date-subtraction parsing trick and a pyoxigraph 0.3.22
  BIND/OPTIONAL workaround, both explained in the file's own header comments. Also: its `GRAPH` clause is
  meant to be added by whoever includes it, not baked into the fragment itself — don't forget it.
- `eat:hasTriageEvent` absence is **not** a safe proxy for "not yet triaged" — this was measured and found
  wrong, not assumed.
- Dependency versions are pinned for real reasons (Morph-KGC 2.10.0, pySHACL 0.31.0, pyoxigraph 0.3.22,
  Oxigraph server 0.5.11) — don't casually bump them without checking why they're pinned in
  `conductor/kg/requirements.md`.
- `ground_truth` is never loaded into Postgres via `kg_loader`'s visible schemas, and never enters the graph
  at all — this is enforced by the role grant, not just convention.

## Open questions worth confirming with the team before you branch

- `conductor/kg/requirements.md` states the base branch for every workspace should be
  `feature/knowledge-graph`, not `main` — but everything currently on `main` already has the graph
  foundation work merged in. Worth a quick check whether that instruction is stale (the branch already
  merged) or whether new work is still expected to branch from `feature/knowledge-graph`.
- `conductor/tracks/explainable-agent-based-triage_20260828/spec.md` (FR1–FR3) still describes `scored` as a
  bare edge property and `cites` as a plain two-way edge — both predate the richer reified classes actually
  built (`eat:Score`, `eat:RankedPlacement`, `eat:cites` subproperties, documented in
  `conductor/kg/decisions.md` and section 8 of the onboarding primer below). If you're building against that
  spec, build against the ontology as it actually exists, not the spec's older description.

## Suggested first steps

1. Follow `kg/docs/GETTING_THE_GRAPH.md` end to end to stand up Postgres + Oxigraph and load the graph
   locally — verify your triple counts match the documented ones per mapping.
2. Read `kg/queries/wait_counters.rq` in full, including its header comments, before writing any new query.
3. Read the Gotchas section of `conductor/kg/requirements.md` in full — it's short and will save real time.
4. ADR-002 is resolved and built (see above) — read `retrieval/README.md` and
   `conductor/tracks/retrieval-service_20260904/spec.md` before writing any code that touches agent
   outputs; call the service's endpoints rather than writing to Postgres or the graph directly.
5. A companion human-readable primer (glossary, dataset walkthrough, five decisions explained from scratch)
   is published separately — ask Edward for the link if useful background, but for actual build work this
   file and the authoritative files table above are the current source of truth.
