# Spec: Explainable Agent-Based Triage System — full build

**Track:** `explainable-agent-based-triage_20260828`
**Type:** feature
**Maps to:** Proposal §14 Days 3–6 (builds on `graph-foundation_20260826`, Days 1–2)

## Overview

Build the urgency agent, capacity agent, coordinating agent, clinician-facing UI, and CPC/CRT
compliance validation on top of the seeded knowledge graph produced by `graph-foundation_20260826`.
End state: a clinician can load a ranked, evidence-cited shortlist from simulated data, accept/reorder/
override it, and have every ranking and override traceable back through the graph.

## Background

`graph-foundation_20260826` already covers proposal §14 Days 1–2 (OWL ontology, Oxigraph bootstrap,
synthetic referral generator, SimPy bed simulation). `conductor/tracks.md` lists the rest of the
proposal's schedule (Days 3–6) as five separate planned tracks; this track carries all of that
remaining scope through to a working, demoable prototype as a single unit of work.

Per `tech-stack.md`'s Agent Reasoning Model decision: scoring is deterministic and unit-tested against
MTS/NEWS2 and SimPy occupancy; only rationale *prose* is LLM-generated, strictly bound to `cites` edges
already in the graph. This is a compliance decision, not just a technical one — it's what keeps every
ranked position reproducible and auditable under the EU AI Act framing the proposal cites throughout.

## Functional Requirements

Per **ADR-002** (`decisions.md`): agents never write to Postgres or the graph directly, and don't need
to query the graph directly for input either. `retrieval-service_20260904` is the single mediator for
both directions — agent *input* (`GET /referrals/.../context`, `GET /hospitals/.../cohort/...`,
`GET /runs/.../hospitals/.../scores`) and agent *output* (`POST /scores`/`/decisions`/`/overrides`,
each writing Postgres first and synchronously projecting into the graph on success — no separate
mapping step). FR1–FR3 below describe what each agent computes; the read/write mechanics are that
service's endpoints throughout.

### FR1 — Urgency agent

- Gathers one referral's clinical data via `GET /referrals/{hospital_hipe}/{pathway_number}/context`
  (observations, conditions, triage events) rather than a direct SPARQL query.
- Computes MTS category and NEWS2 score deterministically from that data.
- Writes its score and citations via `POST /scores`.

### FR2 — Capacity agent

- Gathers the referral's specialty's capacity data — wards, latest bed status, recent clinic
  sessions — via the same `GET /referrals/{hospital_hipe}/{pathway_number}/context` call (it returns
  both clinical and capacity data together, spec.md FR9 of `retrieval-service_20260904`).
- Applies deterministic constraint reasoning (available capacity, overcrowding state) per specialty/ward.
- Writes its score and citations via `POST /scores`.

### FR3 — Coordinating agent

- Gathers its cohort via `GET /hospitals/{hospital_hipe}/cohort/{as_of_date}` (every referral still on
  the list, with CPC and computed CRT breach already included) and every score already written for it
  via `GET /runs/{run_id}/hospitals/{hospital_hipe}/scores`, then ranks with deterministic
  tie-breaking: CPC, then CRT breach status (`crt_breached`, no need to re-derive it), then
  oldest-referral-first.
- Writes the full ranked decision — rankings, citations, and rule checks — via one `POST /decisions`
  call, atomically. This is the audit trail per proposal §9–10; the graph projection (`Decision` nodes,
  `RankedPlacement`/`RuleCheck` nodes, `cites` edges) happens inside that same call.
- Never lets a `Decision` rank an urgent `Referral` behind a semi-urgent one still inside its CRT
  (enforces the OWL constraint declared in `graph-foundation`, checked via SHACL against the
  projected graph).

### FR4 — Rationale layer

- For each ranked position, generates human-readable rationale text from the graph's already-cited
  evidence only (Anthropic `claude-opus-5`, per `tech-stack.md`).
- Evidence-faithfulness: every clinical claim in the rationale must correspond to a `cites` edge.

### FR5 — Clinician UI

- FastAPI + Jinja2 + HTMX ranked-list view (per `tech-stack.md`), showing each patient's rank,
  rationale, and cited evidence.
- Accept / reorder / override controls per proposal §6.
- Every override is written via `POST /overrides` (`retrieval-service_20260904`), closing the loop
  (future rankings can account for it) — the same Postgres-then-graph write path as every other agent
  output.
- New referrals arrive via `POST /referrals` on the same service (`retrieval-service_20260904` FR11) —
  clinician/hospital UI input, not an agent action; entering a referral there is what makes it show up
  in the coordinator's `GET /hospitals/.../cohort/...` for a future run.

### FR6 — CPC/CRT compliance validation

- Automated rule-check suite run across a synthetic batch: flags any ranking that violates CPC/CRT
  ordering (proposal §11, e.g. urgent-within-28-days vs semi-urgent-within-13-weeks).
- Documents the responsible-AI boundary: coordinator may only rank and explain — no admit, discharge,
  schedule, or auto-action (proposal §12).

## Non-Functional Requirements

- **NFR1** — Tier 1 (urgency/capacity/coordinator scoring, CPC/CRT validation): strict TDD, ≥80%
  coverage, per `workflow.md`.
- **NFR2** — Tier 2 (graph read/write helpers, `cites` construction, override write-back): tests
  required, ≥60% coverage.
- **NFR3** — Tier 3 (Jinja templates, HTMX handlers, LLM prompt wiring): smoke test per route only.
- **NFR4** — Evidence-faithfulness test for rationale text is non-negotiable regardless of tier.
- **NFR5** — No score ever rendered without its cited evidence attached.
- **NFR6** — `ruff` and `mypy` clean on Tier 1/2.

## Acceptance Criteria

1. Given a seeded graph, the urgency agent produces MTS/NEWS2 scores for every referral, written as
   `scored` edges.
2. The capacity agent produces a constraint score per referral reflecting current `BedStatus`.
3. The coordinator produces a ranked list where every position has a `Decision` node and `cites` edges
   reconstructing its evidence.
4. A batch run across the synthetic cohort produces zero CPC/CRT ordering violations (or every
   violation is caught and logged, not silently ranked).
5. The clinician UI renders the ranked list with rationale and evidence for every entry, and supports
   accept / reorder / override.
6. Every override is persisted in the graph and visible on reload.
7. The evidence-faithfulness test passes on a fixed synthetic batch.
8. `docker compose up` plus documented commands take a clean checkout to a working demo end to end.

## Out of Scope

- Ontology, Oxigraph bootstrap, synthetic generator, bed simulation — already `graph-foundation_20260826`.
- Ambulance/NAS 999-112 dispatch prioritisation (post-challenge extension, proposal §13).
- Diagnosis-support agent (explicitly non-diagnostic, out of scope for the challenge build).
- Any live/real HSE system integration.
- Production deployment, multi-tenancy, authentication hardening.
- Day 7 rehearsal/pitch-deck work (not code).
