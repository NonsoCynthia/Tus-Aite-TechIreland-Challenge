# Evaluation

This package contains six evaluation paths:

- **agent benchmark** — controlled correctness checks for the urgency agent,
  capacity agent and coordinator
- **scenario/regression benchmark** — broader seeded synthetic cases and drift
  metrics for urgency, capacity and coordinator behaviour
- **knowledge graph audit** — RDF/SHACL/provenance checks for graph-backed
  explainability and answer-key isolation
- **rationale judge and benchmark** — explanation review against cited evidence
  and benchmark outcomes, using a local heuristic by default and an optional
  LLM judge when configured
- **trace audit** — deterministic checks that agent outputs carry expected
  provenance, citations, rule traces and safe rationale summaries
- **outcome evaluation** — optional scoring of a written decision against
  stored rule checks and the held-out synthetic answer key

The first five are database-free. `make evaluation-suite` runs the agent
benchmark, scenario benchmark, KG audit, rationale benchmark and trace audit.

## Latest Evaluation Results

These results were produced in this workspace with `make evaluation-suite` and
`make evaluation-test`.

| Evaluation run | Command | What it evaluates | Result |
|---|---|---|---|
| Full evaluation suite | `make evaluation-suite` | Core benchmark, scenario benchmark, KG audit, rationale benchmark, and trace audit | PASS |
| Agent benchmark | included in `make evaluation-suite` / `make agent-benchmark` | Urgency agent, capacity agent, and coordinator controlled correctness cases | 14/14 PASS |
| Scenario benchmark | included in `make evaluation-suite` / `make scenario-benchmark` | Seeded synthetic urgency, capacity, and coordinator scenarios with regression metrics | 21/21 PASS |
| Knowledge graph audit | included in `make evaluation-suite` / `make kg-audit` | RDF/Turtle parsing, SHACL decision-layer coverage, provenance terms, answer-key isolation, citation role contracts | 5/5 PASS |
| Rationale benchmark | included in `make evaluation-suite` / `make rationale-benchmark` | Benchmark-aware explanation faithfulness, unsafe language, evidence coverage, and readability | 6/6 PASS |
| Trace audit | included in `make evaluation-suite` / `make trace-audit` | Agent trace provenance, schema validation, citations, rules, ordering, exclusions and rationale summaries | 8/8 PASS |
| Evaluation package tests | `make evaluation-test` | Unit tests for benchmarks, KG audit, trace audit, outcome evaluator, suite, and rationale judging | 19/19 PASS |
| Outcome evaluation | `make evaluation-run DECISION_ID=...` | Optional held-out outcome scoring for a written decision | NOT RUN: requires a local `DECISION_ID` |

| Evaluation area | Metric / check | Result |
|---|---|---|
| Overall suite | Core benchmark + scenario benchmark + KG audit + rationale benchmark + trace audit | PASS |
| Rationale judge | Explanation faithful to sample cited evidence | PASS |
| Rationale judge | Unsupported claims | 0 |
| Rationale judge | Diagnostic language avoided | PASS |
| Rationale judge | System-action language avoided | PASS |
| Rationale judge | Mentions urgency, capacity and CPC/CRT evidence | PASS |
| Rationale judge | Readability score | 5/5 PASS |
| Rationale benchmark | Faithful to evidence | 6/6 PASS |
| Rationale benchmark | Unsupported claims absent | 6/6 PASS |
| Rationale benchmark | Diagnostic language avoided | 6/6 PASS |
| Rationale benchmark | System-action language avoided | 6/6 PASS |
| Rationale benchmark | Urgency evidence mentioned when applicable | 4/4 PASS |
| Rationale benchmark | Capacity evidence mentioned when applicable | 1/1 PASS |
| Rationale benchmark | CPC/CRT evidence mentioned when applicable | 2/2 PASS |
| Rationale benchmark | Average readability | 4.8/5; 6/6 cases scored >= 3 |
| Rationale benchmark | Required benchmark terms present | 6/6 PASS |
| Agent benchmark | Total controlled agent checks | 14/14 PASS |
| Scenario benchmark | Total seeded regression metrics | 21/21 PASS |
| Scenario benchmark | Urgency scenarios | 70 cases: 60 scored, 5 paediatric refusals, 5 missing-evidence refusals |
| Scenario benchmark | Capacity scenarios | 55 cases: 50 scored, 5 missing-evidence refusals |
| Scenario benchmark | Coordinator scenarios | 25 cohorts / 300 referrals, 0 order or determinism violations |
| Urgency agent | Normal adult observation scores zero with full NEWS2 citations | PASS |
| Urgency agent | High NEWS2 observation saturates at maximum urgency | PASS |
| Urgency agent | Most recent observation is scored | PASS |
| Urgency agent | Paediatric referrals are refused | PASS |
| Urgency agent | Missing observation is refused | PASS |
| Capacity agent | Ward and clinic pressure combine with configured weights | PASS |
| Capacity agent | Escalation flags are boolean, not magnitude-scaled | PASS |
| Capacity agent | Ward-only evidence is renormalised and cited | PASS |
| Capacity agent | Full ward and clinic pressure saturates at one | PASS |
| Capacity agent | Missing capacity evidence is refused | PASS |
| Coordinator | CPC band is non-compensatory | PASS |
| Coordinator | CRT breach outranks same-band non-breach | PASS |
| Coordinator | Missing urgency is excluded, not defaulted | PASS |
| Coordinator | Positions are contiguous and deterministic | PASS |
| Knowledge graph audit | Total KG audit checks | 5/5 PASS |
| Knowledge graph audit | RDF assets parse | PASS |
| Knowledge graph audit | Held-out answer key absent from KG assets | PASS |
| Knowledge graph audit | Decision ontology terms exist | PASS |
| Knowledge graph audit | SHACL covers agent output classes | PASS |
| Knowledge graph audit | Citation role mappings are consistent | PASS |
| Rationale benchmark | Benchmark-aware explanation cases | 6/6 PASS |
| Rationale benchmark | High urgency explanation | PASS |
| Rationale benchmark | Capacity pressure explanation | PASS |
| Rationale benchmark | CRT breach explanation | PASS |
| Rationale benchmark | CPC ordering explanation | PASS |
| Rationale benchmark | Missing urgency exclusion explanation | PASS |
| Rationale benchmark | Paediatric refusal explanation | PASS |
| Trace audit | Total trace checks | 8/8 PASS |
| Trace audit | Score and decision payload schemas | PASS |
| Trace audit | Score provenance: run, method, version and citations | PASS |
| Trace audit | Decision run/version alignment | PASS |
| Trace audit | Contiguous ranked placements and CPC/CRT ordering | PASS |
| Trace audit | Missing urgency excluded rather than ranked | PASS |
| Trace audit | Placement citation integrity | PASS |
| Trace audit | Applicable CRT/turnaround and list-order rule checks | PASS |
| Trace audit | Rationale summaries tied to trace evidence and safe language | PASS |
| Evaluation tests | Package test suite | 19/19 PASS |
| Outcome evaluation | Held-out decision outcome scoring | NOT RUN: requires a local `DECISION_ID` |

## What The Evaluation Result Means

The evaluation result is **PASS** for prototype-level agent evaluation. This
means the implemented agents behave as designed on deterministic controlled
cases and on a broader seeded synthetic scenario benchmark: the urgency agent
applies the expected NEWS2 and refusal logic, the capacity agent computes and
cites pressure evidence as expected, and the coordinator respects CPC/CRT
ordering, excludes missing urgency scores, and produces deterministic
positions. The scenario regression digest also gives us a compact drift check
for future scoring/ranking changes. The KG audit passing means the repository's
RDF/SHACL/provenance assets are structurally sound for this evaluation layer,
the decision-output classes have SHACL coverage, citation role mappings are
consistent, and the held-out answer-key terms are absent from KG assets. The
rationale benchmark passing means explanations tied to the benchmark outcomes
are faithful to their cited evidence, avoid diagnostic or system-action
language, mention the expected evidence categories, and are readable. The
trace audit passing means the benchmark decision trace has valid write
schemas, run/version provenance, role-specific citations, rule checks,
missing-evidence exclusions, and safe coordinator rationale summaries.

This result does **not** prove clinical effectiveness or outcome improvement.
It proves that the current agent implementation is working correctly and
traceably on the benchmark cases we defined. Clinical validation would require
larger scenario sets, held-out outcome evaluation, clinician review,
subgroup/fairness checks, and prospective evaluation.

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
- **AI-as-judge, bounded to explanation review**: optional LLM judging is used
  only to assess rationale faithfulness/readability against supplied evidence,
  not to decide whether scores or rankings are clinically correct.
- **Traceability and provenance audit**: deterministic trace checks verify
  that scores, decisions, citations, rule checks and rationale summaries can
  be followed back to their supporting evidence.

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

## Scenario And Regression Benchmark

`evaluation.scenario_benchmark` adds a broader seeded synthetic benchmark on
top of the controlled checks. It generates deterministic urgency contexts,
capacity contexts, and coordinator cohorts from a fixed seed, then compares
aggregate metrics and a regression digest against expected values.

It currently covers:

- 70 urgency scenarios: 60 scored adult cases, 5 paediatric refusals, and 5
  missing-observation refusals
- 55 capacity scenarios: 50 scored cases and 5 missing-evidence refusals
- 25 coordinator cohorts containing 300 referrals
- range checks, monotonicity checks, exclusion counts, ordering checks,
  contiguous positions, shuffle determinism, and a regression digest

```bash
python -m evaluation.scenario_benchmark
python -m evaluation.scenario_benchmark --format json
```

Root Make target:

```bash
make scenario-benchmark
```

Latest run in this workspace:

```text
Scenario Benchmark
Result: PASS (21/21 metrics passed)
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

## Rationale Judge

`evaluation.rationale_judge` judges explanation text against its cited
`EvidencePack`.

It checks:

- faithfulness to cited evidence
- unsupported claims
- diagnostic language
- system-action language such as implying the system admitted, scheduled,
  triaged or decided care
- whether urgency, capacity and CPC/CRT evidence are mentioned when present
- clinician readability

The default `heuristic` engine is deterministic and local. The optional `llm`
engine is the actual AI-as-judge path and requires `OPENAI_API_KEY`.

```bash
python -m evaluation.rationale_judge \
  --input evaluation/fixtures/rationale_judge_sample.json

python -m evaluation.rationale_judge \
  --input evaluation/fixtures/rationale_judge_sample.json \
  --engine llm
```

Root Make target:

```bash
make rationale-judge
make rationale-judge RATIONALE_JUDGE_ENGINE=llm
```

Latest local heuristic run in this workspace:

```text
Rationale Judge (heuristic)
Result: PASS
```

## Rationale Benchmark

`evaluation.rationale_benchmark` connects explanations to benchmark outcomes
rather than judging a single standalone sample. Each case includes a known
benchmark outcome, an evidence pack, a rationale, and required explanation
terms. The local heuristic judge runs by default; `--engine llm` / 
`RATIONALE_BENCHMARK_ENGINE=llm` uses the optional AI-as-judge path.

It currently covers:

- high urgency explanation
- capacity pressure explanation
- CRT breach explanation
- CPC non-compensation explanation
- missing urgency exclusion explanation
- paediatric NEWS2 refusal explanation

```bash
python -m evaluation.rationale_benchmark
python -m evaluation.rationale_benchmark --engine llm
```

Root Make target:

```bash
make rationale-benchmark
make rationale-benchmark RATIONALE_BENCHMARK_ENGINE=llm
```

Latest local heuristic run in this workspace:

```text
Rationale Benchmark (heuristic)
Result: PASS (6/6 cases passed)
```

| Metric | Result |
|---|---|
| Faithful to evidence | 6/6 PASS |
| Unsupported claims absent | 6/6 PASS |
| Diagnostic language avoided | 6/6 PASS |
| System-action language avoided | 6/6 PASS |
| Urgency evidence mentioned when applicable | 4/4 PASS |
| Capacity evidence mentioned when applicable | 1/1 PASS |
| CPC/CRT evidence mentioned when applicable | 2/2 PASS |
| Average readability | 4.8/5 (6/6 >= 3) |
| Required benchmark terms present | 6/6 PASS |

## Trace Audit

`evaluation.trace_audit` checks the traceability of deterministic agent
outputs. It builds a synthetic benchmark decision through the coordinator
contract, validates it against the retrieval write schemas, and audits the
evidence and rule trace around the decision.

It currently checks:

- score and decision payload schema validity
- score provenance: run ID, method, version, bounded score and citations
- decision alignment to the score run and coordinator settings
- contiguous ranked placements and expected CPC/CRT ordering
- missing urgency exclusion instead of unsafe default ranking
- placement citations for score, referral-state, rule and capacity evidence
- applicable CRT/turnaround rules plus list-level order/tiebreak rules
- rationale summaries tied to trace evidence and free of clinical-action
  language

```bash
python -m evaluation.trace_audit
python -m evaluation.trace_audit --format json
```

Root Make target:

```bash
make trace-audit
```

Latest run in this workspace:

```text
Trace Audit
Result: PASS (8/8 checks passed)
```

## Evaluation Suite

Runs the controlled agent benchmark, scenario benchmark, KG audit, rationale
benchmark, and trace audit together.

```bash
make evaluation-suite
```

Latest run in this workspace:

```text
Evaluation Suite
Overall: PASS
Agent Benchmark: PASS (14/14 checks passed)
Scenario Benchmark: PASS (21/21 metrics passed)
Knowledge Graph Audit: PASS (5/5 checks passed)
Rationale Benchmark: PASS (6/6 cases passed)
Trace Audit: PASS (8/8 checks passed)
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
19 passed
```
