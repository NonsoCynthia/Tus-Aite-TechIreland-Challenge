# Project Workflow

> Tuned for a nine-person, seven-day build with a compliance story to defend.

## Task Workflow

1. Select the next task from the track's `plan.md`
2. Mark it in-progress `[~]`
3. Write failing tests first (see the tiered TDD policy below)
4. Implement until tests pass
5. Verify coverage against the tier's threshold
6. Commit
7. Mark complete `[x]`

## Tiered TDD Policy

Correctness is the product in some places and irrelevant in others. The gate reflects that.

| Tier | Scope | Policy | Coverage gate |
|---|---|---|---|
| **Tier 1 — Clinical core** | MTS scoring, NEWS2 scoring, capacity constraint rules, CPC/CRT validation, coordinator ranking and tie-breaking | Strict TDD. Test written and failing before implementation, no exceptions. Rubric-derived test cases cited to the source rubric. | **80%**, enforced in CI |
| **Tier 2 — Graph and pipeline** | Ontology load, SPARQL read/write helpers, `cites` edge construction, override write-back, synthetic generator | Tests required, TDD encouraged but not enforced. Round-trip tests over the graph count. | **60%**, enforced in CI |
| **Tier 3 — Surface** | Jinja templates, HTMX handlers, CLI entry points, demo scripts, LLM prompt wiring | Best effort. One smoke test per route proving it renders and does not 500. | No gate |

A Tier 1 file with no test is a blocking review failure. A Tier 3 file with no test is fine.

**Why tiered:** a uniform 80% gate over templates and demo glue burns hours in week one for no
auditability benefit, while the scoring logic is exactly what a judge, a compliance lead, or a
regulator would interrogate. The gate goes where the risk is.

## Rationale-Layer Testing

The LLM rationale layer gets a specific, non-negotiable test rather than a coverage percentage:

- **Evidence-faithfulness test** — assert that every clinical claim in generated rationale text
  corresponds to a `cites` edge in the graph. A rationale that introduces an uncited fact fails.
- Run against a fixed synthetic batch with a seeded generator so failures are reproducible.

## Quality Gates

Before any task is marked `[x]`:

- All tests pass
- Coverage meets the tier threshold
- `ruff check` and `ruff format --check` clean
- `mypy` clean on Tier 1 and Tier 2
- CPC/CRT rule-validation suite passes (once it exists, from Day 4 onward)
- No score rendered without cited evidence
- Documentation updated where behaviour changed

## Compliance Review Cadence

The responsible AI / compliance lead reviews each agent's output against CPC and CRT rules **as soon
as that agent produces output**, not on Day 6. Day 6 validation is a final check, never a first one.
Any CPC/CRT violation found is logged in the track's `decisions.md` with its resolution.

## Commit Format

```
<type>(<scope>): <description>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

Scopes: `graph`, `urgency`, `capacity`, `coordinator`, `data`, `sim`, `web`, `rationale`,
`compliance`, `conductor`

Commit at least once per completed task. With nine people on one repo, long-lived branches are the
main integration risk — merge to the integration branch daily.

## User Manual Verification Protocol

Each phase ends with a manual verification task. To complete one:

1. The implementing developer runs the phase's demo path end to end locally
2. They report what they ran and what they observed — not that it "should work"
3. The user (or team lead) confirms or rejects
4. Only on confirmation is the verification task marked `[x]`

A phase is not complete until its verification task is confirmed.
