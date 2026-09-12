# Evaluation

This package contains three evaluation paths:

- **agent benchmark** — controlled correctness checks for the urgency agent,
  capacity agent and coordinator
- **knowledge graph audit** — RDF/SHACL/provenance checks for graph-backed
  explainability and answer-key isolation
- **outcome evaluation** — optional scoring of a written decision against
  stored rule checks and the held-out synthetic answer key

The first two are database-free and are what `make evaluation-suite` runs.

## Standards and Evaluation Frame

This project is a KG-backed clinical decision-support prototype, so there is
no single standard called "agent evaluation" that covers the whole system. The
implemented evaluation combines:

- **W3C RDF/Turtle parsing**: ontology, SHACL shapes and RML mapping files must
  parse as RDF assets.
- **W3C SHACL**: graph constraints cover input graph classes and now also the
  agent-output decision layer (`Score`, `Decision`, `RankedPlacement`,
  `RuleCheck`).
- **W3C PROV-O**: the ontology requires generated scores, decisions and rule
  checks to carry provenance through `prov:wasGeneratedBy`, and `eat:cites`
  is a sub-property of `prov:used`.
- **Clinical decision-support safety posture**: no score without cited
  evidence, no hidden answer-key leakage, deterministic ranking, explicit
  refusals for unsupported cases, and CPC/CRT compliance checks.

## Agent Benchmark

`evaluation.agent_benchmark` checks that the urgency agent, capacity agent and
coordinator are working correctly on controlled benchmark cases. It does not
touch Postgres, Oxigraph, retrieval, or the held-out answer key.

It checks:

- urgency scoring: NEWS2 zero/high cases, most-recent-observation selection,
  citation count, paediatric refusal, and missing-observation refusal
- capacity scoring: weighted ward/clinic pressure, boolean escalation flags,
  ward-only renormalisation, saturation, and missing-evidence refusal
- coordinator ranking: CPC non-compensation, CRT breach ordering, missing
  urgency exclusion, and deterministic contiguous positions

```bash
python -m evaluation.agent_benchmark
python -m evaluation.agent_benchmark --format json
```

Root Make target:

```bash
make agent-benchmark
```

Latest run in this workspace:

```text
Agent Benchmark
Result: PASS (14/14 checks passed)
```

## Knowledge Graph Audit

`evaluation.kg_audit` checks that the KG/audit machinery supporting the agents
is intact.

It checks:

- all RDF assets parse: `kg/ontology/eat.ttl`,
  `kg/shapes/structural.ttl`, and every `kg/mappings/*.ttl`
- held-out answer-key terms are absent from KG ontology, shapes, mappings and
  queries
- decision-layer ontology terms exist: `Score`, `Decision`,
  `RankedPlacement`, `RuleCheck`, `eat:cites`, and the role-specific citation
  sub-properties
- SHACL target-class coverage exists for the decision-layer output classes
- retrieval graph/read citation role mappings match the coordinator's citation
  contract

```bash
python -m evaluation.kg_audit
python -m evaluation.kg_audit --format json
```

Root Make target:

```bash
make kg-audit
```

Latest run in this workspace:

```text
Knowledge Graph Audit
Result: PASS (5/5 checks passed)
```

## Evaluation Suite

Runs the agent benchmark and KG audit together.

```bash
make evaluation-suite
```

Latest run in this workspace:

```text
Evaluation Suite
Overall: PASS
Agent Benchmark: PASS (14/14 checks passed)
Knowledge Graph Audit: PASS (5/5 checks passed)
```

## Outcome Evaluation

`evaluation.cli` evaluates one written coordinator decision without exposing the
held-out answer key to any agent or retrieval endpoint.

It reports two kinds of result:

- **Compliance:** missed CPC/CRT deadlines from `agent.rule_checks`. Lead with
  these numbers because they are based on public rules and date arithmetic.
- **Held-out outcomes:** deterioration and high-hazard capture in the top `k`
  ranked referrals by joining `agent.decision_rankings` to `eval.ground_truth`.
  These are useful for demos and regression checks, but they depend on the
  synthetic, unvalidated risk model.

## Run

The evaluator uses an admin connection and then runs `SET ROLE evaluator`.
Normal agent roles should not be able to run it.

```bash
python -m evaluation.cli \
  --decision-id DECISION-ID \
  --top-k 10
```

Use `--format json` for machine-readable output.

This path was not run in the latest workspace evaluation because it requires an
existing `agent.decisions.decision_id` in the local database.

## Test Results

The evaluation package's own tests were run with:

```bash
make evaluation-test
```

Latest result:

```text
9 passed
```
