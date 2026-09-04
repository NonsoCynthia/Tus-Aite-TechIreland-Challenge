# Architecture Decision Records

**Track:** `explainable-agent-based-triage_20260828`

> Log decisions here as they're made during implementation. Each entry: date, decision, rationale,
> trade-off accepted.

---

### ADR-002: Postgres is the write target for agent outputs, the graph projects it

**Date:** 2026-09-04
**Status:** accepted

**Context:** Raised 2026-08-31 while reconciling `graph-foundation_20260826` against ADR-001 (see that
track's `decisions.md`, item 3, and `spec.md`'s "Unresolved" section). Migration 006 already models
the entire agent output surface in Postgres — `agent.agent_scores`, `agent_citations`, `decisions`,
`decision_rankings`, `decision_citations`, `rule_checks`, `overrides` — with `agent_rw` holding INSERT
on all of them, and `rule_checks` carrying a foreign key to `core.ref_rules`. The proposal (§9) says
agents write scores back to the graph directly. Three options were on the table; team decided
2026-09-04.

**Decision:** Postgres is the write target. Agents (urgency, capacity, coordinator) write `scored`
rows, `Decision`/`decision_rankings`/`decision_citations` rows, and overrides directly to
`agent.*` via `agent_rw`. The graph never receives a direct write from an agent.

A projection step — the same pattern `kg/mappings/` already uses for `core.*` (declarative
R2RML/Morph-KGC mappings, not a hand-written client) — mirrors `agent.*` into the graph as
`eat:Score` nodes, `Decision` nodes, and `cites` edges. The audit trail is still walkable in the
graph; Postgres is just the source of record it's projected from, exactly as ADR-001 already settled
for cohort data.

**Rationale:** Consistent with ADR-001's one-source-of-record logic. Relational constraints do real
work here that would otherwise need reimplementing in SHACL or application code: `dr_unique_position`
makes two patients holding the same rank impossible, `dc_role_valid` constrains why evidence was
cited, and the FK to `ref_rules` means a rule violation can never name a rule that doesn't exist.
Extending the existing `dataset/` → `kg/` projection pattern to `agent.*` is also less new surface
than standing up a second write path this week — one mapping style, one place bugs like the `"None"`
literal gotcha (`conductor/kg/requirements.md` §4) get handled, instead of two.

**Trade-off accepted:** the graph is a query surface over Postgres, not the write target the proposal
originally described. This doesn't cost the audit-trail claim — `cites` edges still exist in the graph
and are still walkable backward from any ranked position — but the pitch language should say "the
graph exposes the audit trail" rather than "the graph is the write target," since it no longer is.

**Follow-on work this creates:** a sixth mapping file (`kg/mappings/agent_outputs.rml.ttl` or similar)
projecting `agent.agent_scores` / `decisions` / `decision_rankings` / `decision_citations` /
`overrides` into `eat:Score` / `Decision` / `cites` triples. This is new scope relative to the
original `plan.md` phase list — see the note added to Phase 3.
