# Track: Retrieval Service

**ID:** `retrieval-service_20260904`
**Type:** feature
**Status:** done
**Created:** 2026-09-04
**Completed:** 2026-09-04 (reopened repeatedly the same day — Phases 6-9 plus a post-completion
feature and a doc correction, all user-driven)

## Summary

A standalone FastAPI retrieval service, its own container in the (now consolidated, single) root
`docker-compose.yml` alongside `db` (Postgres) and `oxigraph`, mediating every read and write between
Postgres `core`/`agent` and the Oxigraph knowledge graph for the not-yet-built urgency/capacity/
coordinator agents and the clinician/hospital UI. This is the concrete implementation of **ADR-002**
(confirmed and recorded 2026-09-04): Postgres is the system of record; the graph gets a synchronous,
single-writer projection on successful Postgres commit. The service's port is published to the host
and every endpoint (except `/health`) requires bearer-token auth.

**Delivered 2026-09-04, Phases 1-5.** `POST /scores`/`/decisions`/`/overrides` implement the
write-projector; `GET` endpoints cover wait counters (wrapping `kg/queries/wait_counters.rq`
unmodified), decision/evidence audit-trail lookup, and role-scoped evidence lookup. Also consolidated
`dataset/docker-compose.yml` into the root compose file (one project, one network, one `.env`) at the
user's request, and closed a real gap found along the way: `eat:cites`' 1..n cardinality on
`RankedPlacement` wasn't enforced at the API layer.

**Reopened, Phase 6.** Three follow-up corrections, all from the user: `/health` no longer required
auth and now explicitly checks Postgres/Oxigraph connectivity (`200`/`503`); every citation returned by
the read endpoints is now resolved to its actual properties inline (not just an IRI, and not a separate
round-trip endpoint); every IRI in every response is short (namespace prefix stripped); `/docs` now
shows a real Authorize button and every endpoint has a `summary`/`description`.

**Reopened, Phase 7 (FR9).** The user asked how an urgency/capacity agent would actually get the data
it needs to judge one referral — a real input-side gap. Added
`GET /referrals/{hospital_hipe}/{pathway_number}/context`: observations, conditions, triage events, plus
capacity data for its specialty, read directly from Postgres `core.*` (not the graph).

**Reopened, Phase 8 (FR10).** Same question for the coordinator: what does it see before ranking? Added
`GET /hospitals/{hospital_hipe}/cohort/{as_of_date}` (which referrals need ranking) and
`GET /runs/{run_id}/hospitals/{hospital_hipe}/scores` (scores already written for them).

**Reopened, Phase 9 (CRT breach).** User asked to flag CRT breach on the cohort endpoint — reversed this
track's own earlier, more conservative call to leave it out as "the rule-checking layer's job": on
reflection `tech-stack.md` Decision 5 itself calls `RULE-CRT-*` "facts about the hospital, not invalid
graphs," i.e. date math against a normative threshold, not a ranking judgement. Added
`crt_threshold_days`/`crt_breached` to the cohort response, sourced from `core.ref_codes.crt_days`.

**Post-completion feature, FR11.** User: "the system doesn't account for new patients arriving" — added
`POST /referrals`, the clinician/hospital UI's write path for a brand-new referral (full ADR-002 flow:
Postgres commit, then graph projection into the same `inputs` graph the batch pipeline uses). Required a
narrow migration granting `agent_rw` INSERT on exactly the four `core.*` tables intake touches — the
first write path this service has ever had into `core` (everywhere else stays SELECT-only, NFR3).
Deliberately does not recompute scores or re-rank; that stays the agents' judgement.

**Post-completion correction.** User caught a mischaracterization: `POST /referrals` was initially
labelled "agent input" (grouped with FR9/FR10). Corrected everywhere — it's clinician/hospital UI input,
not agent input; no functional change, description/labelling only.

**Reopened, ADR-009.** `coordinating-agent_20260906` raised a real gap at their own Phase 1: `EvidenceType`
could express what a `Score` cites but not what a `RankedPlacement` cites (the agent's own `Score` node for
urgency/capacity; a `ReferralState`/`Rule` node, not a `triage_event`, for a CRT-breach-driven timeframe
position). Added a separate `DecisionEvidenceType` for `DecisionCitationIn.evidence_type` only
(`ScoreCitationIn` unchanged) — see [`decisions.md`](./decisions.md) for the full reasoning, including two
things the ontology already sanctioned that the original request missed.

**Final state:** 411 tests (+ new evidence-type coverage), 97% coverage on `app/`, 19 acceptance criteria
met against the running system, `ruff`/`mypy` clean. See [`retrieval/README.md`](../../../retrieval/README.md)
for the full endpoint list, consumer walkthrough, and how to run it.

Completing this track resolves the blocker recorded against
[`explainable-agent-based-triage_20260828`](../explainable-agent-based-triage_20260828/index.md) — its
decisions.md now records ADR-002, and its agents should call this service's write endpoints rather
than writing to Postgres or the graph directly.

## Documents

- [Specification](./spec.md) — requirements (FR1-FR11) and 19 acceptance criteria
- [Plan](./plan.md) — nine phases plus two post-completion sections, TDD-structured
- [Decisions](./decisions.md) — ADR-009 (decision-citation evidence types)
- [Metadata](./metadata.json)

## Phases

1. ADR-002 record + service scaffold
2. Fixture decision generator
3. Write endpoints — the ADR-002 projector
4. Read endpoints
5. Integration and acceptance pass
6. Evidence resolution (reopened) — citations resolved to real properties inline, IRIs shortened in
   every response, `/health` dependency-checked, `/docs` given real Authorize support and per-endpoint
   descriptions
7. Referral context (reopened, FR9) — agent input for judging one referral
8. Coordinator input (reopened, FR10) — cohort + already-written scores
9. CRT breach flag (reopened) — computed fact on the cohort endpoint

Post-completion: new-referral intake (FR11, `POST /referrals`) and a UI-vs-agent labelling correction.

## Project Context

- [Product Definition](../../product.md)
- [Tech Stack](../../tech-stack.md)
- [Workflow](../../workflow.md)
