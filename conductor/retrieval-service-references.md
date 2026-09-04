# Retrieval service — source materials and file map

**Status, updated 2026-09-04:** built. `retrieval-service_20260904` implemented and verified this service —
see `retrieval/README.md` for the endpoint list and how to run it, and
`conductor/tracks/retrieval-service_20260904/` for the spec, plan, and implementation notes. This file's
original purpose (a reading index for *designing* the service) is now historical background; still useful
for understanding *why* it's shaped the way it is, but read `retrieval/README.md` first for how to actually
use it.
**Companion file:** `conductor/retrieval-database-onboarding.md` — also updated; ADR-002 is resolved, not
still open.

## Where the retrieval service sits

```
Postgres (core/agent schemas)  <-->  retrieval service  <-->  Oxigraph (RDF graph)
                                            ^
                                            |
                                    urgency / capacity / coordinator /
                                    rule-checker agents, clinician UI
```

This service is not a new idea invented from scratch — it was built as the practical implementation of the
ADR-002 decision (where agent outputs get written) plus the read-side patterns the graph-foundation work
already established (`wait_counters.rq`'s single-shared-fragment principle, named-graph scoping discipline).
Building this service *is* how ADR-002 got resolved in code, not just in a document — Postgres is the system
of record, one code path pushes a synchronous projection into the graph on successful commit. See
`conductor/tracks/explainable-agent-based-triage_20260828/decisions.md` for the recorded decision and
`retrieval/README.md` for the endpoints that implement it.

## The three external source materials you asked to link

| Document | Repo path / link | What it actually is | How current is it |
|---|---|---|---|
| Triage graph primer (my artifact) | https://claude.ai/code/artifact/e336c7af-1d54-4e16-a179-630424a41304 | A plain-English, glossary-annotated walkthrough of the dataset and the graph design, written for someone new to both. Web page, not a repo file — Claude Code can't open it directly unless it has web-fetch access. | Updated 4 Sep to match the real repo (Morph-KGC pipeline, 590,814 triples). Good orientation reading, not a spec — defer to the actual repo files below for anything you're implementing against. |
| Original project proposal | `conductor/reference/Explainable_Agent_Triage_Proposal.docx` | The founding TechIreland Challenge submission proposal. Section 9 ("Multi-agent information flow") and section 10 ("Applying the knowledge graph") describe the intended read/write flow between agents and the graph in general terms — worth reading for the *why*. Section 14 has the original team-role table and 7-day plan. | **Oldest document in this set.** Predates almost everything actually built: no mention of Postgres as a separate store, R2RML/Morph-KGC, SHACL, Type-2 states, or named-graph isolation — the original vision was graph-only, agents "write their scores back as graph nodes and edges." The team has since built something more sophisticated (and partly reconsidered that graph-only assumption — see ADR-002). Treat this as the origin story and the pitch/business framing (sections 1–3, 11–13), not as current architecture. Note: this proposal's team-role table has no role literally named "database and retrieval" — closest is "Knowledge graph engineer" and "Data and simulation engineer." Your role is a refinement that emerged as the build got more complex than the original one-week MVP plan. |
| Knowledge graph design review (24-slide deck) | `conductor/reference/knowledge-graph-design-review.pdf` | The detailed design deck: full Turtle syntax examples, the complete SHACL shape file walkthrough, domain/range/cardinality tables. Good for exact syntax reference. | **Superseded in specific, documented places** — most importantly, it originally specified one named graph per loaded date; the shipped design uses a single `inputs` graph instead (a `ReferralState` can span a date range). `conductor/kg/decisions.md` and `conductor/kg/namespaces.md` are the corrected, current version of everything this deck covers. If this deck and those two files disagree, the files win. |

## The in-repo files that are actually current — use these to build against

| File | Why it matters for the retrieval service |
|---|---|
| `kg/docs/GETTING_THE_GRAPH.md` | How to stand up Postgres + Oxigraph and load the graph locally. Do this before writing service code. |
| `kg/queries/wait_counters.rq` | The one existing example of "shared, single-source-of-truth retrieval logic" in this codebase. Your service should follow this pattern (one place computes a derived value, everything else includes it) rather than reimplementing logic per caller. |
| `conductor/kg/namespaces.md` | IRI-minting conventions and the current named-graph table — your service needs to construct/scope queries correctly against these graphs (`ontology`, `reference`, `inputs`, `run/{run_id}`, `rationale`, `overrides`). |
| `conductor/kg/requirements.md` | Normative MUST/MUST NOT rules (R1–R6) plus the Gotchas section — several of these are exactly the kind of bug a retrieval service would otherwise reintroduce (e.g. `eat:hasTriageEvent` absence isn't a safe "not triaged" proxy). |
| `conductor/kg/decisions.md` | The five foundational decisions, with real numbers — decision 5 (rationale graph, write-once, never read by agents) is a hard constraint your service must enforce, not just a convention. |
| `kg/sql/002_kg_loader_role.sql` | Shows the existing pattern for schema-level isolation (`kg_loader` can't see `eval`). Your service's own Postgres role should follow the same least-privilege shape once ADR-002 gives it a defined write path. |
| `kg/ontology/eat.ttl`, `kg/mappings/*.rml.ttl`, `kg/shapes/structural.ttl` | The actual TBox, the five R2RML mappings, and the 19 SHACL shapes — the real schema your service's queries and any writes need to conform to. |
| `conductor/retrieval-database-onboarding.md` | Status, gotchas, the ADR-002 proposal, and open threads (branch-base question, stale spec in the next track) — written directly for this work. |

## Priority order when sources conflict

Repo code and `conductor/kg/*.md` > `conductor/retrieval-database-onboarding.md` > the primer artifact > the
design review PDF > the original proposal docx. Newer, more specific, and closer to the actual running
system always wins over older and more aspirational.
