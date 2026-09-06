# Running the Coordinator

Everything needed to go from a fresh clone to a ranked, inspectable decision.

Companion documents: [`HOW_THE_COORDINATOR_WAS_BUILT.md`](HOW_THE_COORDINATOR_WAS_BUILT.md)
for the design and what the build disproved,
[`BUILDING_AN_AGENT_WITH_CONDUCTOR.md`](BUILDING_AN_AGENT_WITH_CONDUCTOR.md) for the process
another agent author can follow,
[`../../conductor/tracks/coordinating-agent_20260906/`](../../conductor/tracks/coordinating-agent_20260906/)
for the normative specification.

---

## 1. What you need

**The whole stack up.** The coordinator is a client of `retrieval-service_20260904` and talks
to nothing else. It needs Postgres, Oxigraph and the retrieval service all running, which
means the dataset loaded and the graph built first:

```bash
cd <repo root>
make up
docker compose ps          # db, oxigraph, retrieval, pgadmin all Up
curl -s http://localhost:8000/health
```

You want `{"status":"ok","postgres":"ok","oxigraph":"ok"}`. A `503` means the service is up
but a dependency is not — see §7.

**The dataset at the `full` profile.**

```bash
docker compose exec -T db psql -U triage_admin -d triage \
  -c "SELECT count(*) FROM core.referral_daily;"    # 70,022 on full
```

A smaller number means you are on `sample`; run `make load FETCH_PROFILE=full`. The sample
covers two hospitals only, so the cross-specialty capacity variation the coordinator reasons
over is not in it.

**The graph loaded.**

```bash
curl -s http://localhost:7878/query \
  --data-urlencode "query=SELECT ?g (COUNT(*) AS ?n) WHERE { GRAPH ?g { ?s ?p ?o } } GROUP BY ?g" \
  -H "Accept: application/sparql-results+json"
```

Two named graphs, 590,632 and 182. Empty means the triples need rebuilding — see
[`../../kg/docs/GETTING_THE_GRAPH.md`](../../kg/docs/GETTING_THE_GRAPH.md) §4–5. If
`kg/out/*.nq` still exists from a previous build you can skip straight to the load step.

**Python 3.12 in its own environment.** Not conda base.
`kg/docs/GETTING_THE_GRAPH.md` warns that installing into conda base conflicts with its own
`ruamel-yaml` and `pydantic`, and `pydantic` matters here — the coordinator imports the
retrieval service's own models.

```bash
conda create -n coordinator python=3.12 -y
conda activate coordinator
pip install -r coordinator/requirements-dev.txt
```

`coordinator/requirements-dev.txt` is a frozen `pip freeze`, not a floor-constrained list.
The retrieval service's `requirements.txt` uses `>=` floors, so resolving it on two different
days gives two different dependency sets. The coordinator pins exactly.

Remember to `conda activate coordinator` in every new terminal. A test that passes in one tab
and fails in another is almost always this.

## 2. Two roles in Postgres

The coordinator itself needs no database credentials — it reaches Postgres only through the
retrieval service (ADR-002). But that service needs `retrieval_rw`, which arrived in
migration 009 and will not exist in a database volume created before it:

```bash
docker compose exec -T db psql -U triage_admin -d triage -c "\du"
```

If `retrieval_rw` is absent, apply the two migrations and set its password. Both are
idempotent and additive — no data is touched:

```bash
docker compose exec -T db psql -U triage_admin -d triage \
  -v ON_ERROR_STOP=1 -f - < dataset/db/migrations/009_retrieval_login_role.sql
docker compose exec -T db psql -U triage_admin -d triage \
  -v ON_ERROR_STOP=1 -f - < dataset/db/migrations/010_referral_intake_grants.sql
docker compose exec -T db psql -U triage_admin -d triage \
  -c "ALTER ROLE retrieval_rw PASSWORD '<value inside RETRIEVAL_DB_URL in .env>';"
docker compose restart retrieval
```

## 3. What goes in `.env`

The coordinator reads two values from the repo-root `.env`, both shared with the retrieval
service:

| | Used for |
|---|---|
| `RETRIEVAL_BEARER_TOKENS` | Bearer token on every request. Any one of the comma-separated values |
| `RETRIEVAL_PORT` | Host port the service is published on. Defaults to 8000 |

Neither is ever printed or logged. Check a token is set without revealing it:

```bash
grep -c '^RETRIEVAL_BEARER_TOKENS=' .env      # 1
```

## 4. Running it

```bash
python -m coordinator \
  --hospital 9004 \
  --as-of 2026-08-30 \
  --run-id run-2026-09-06-001 \
  --capacity-direction pressure \
  --dry-run
```

`coordinator/__main__.py` is a shim that calls `coordinator.app.cli.main()` and exits with
its return code, per `conductor/code_styleguides/python.md`; all CLI logic lives in
`coordinator/app/cli.py`. The exit codes below are that return code, so they are what a shell
or a CI step sees.

**Always `--dry-run` first.** It assembles the full decision and prints it without posting,
so the ranking can be read before anything is written. `POST /decisions` for the same
`(hospital_hipe, as_of_date)` adds placements to the same graph node rather than replacing
it, so a wrong decision is not simply overwritten by a right one.

### The flags

| Flag | Effect |
|---|---|
| `--hospital` | 4-character HIPE code. `9001`–`9004` are the public hospitals with waiting lists; `9101`/`9102` are private, capacity only, and return an empty cohort |
| `--as-of` | The hospital-day to rank. The dataset spans **2026-08-17 to 2026-08-30** inclusive, 14 days |
| `--run-id` | Ties this decision to the scores it was built from. Must match the `run_id` the urgency and capacity agents used |
| `--capacity-direction` | **Required, no default.** `availability` (1.0 = most capacity free) or `pressure` (1.0 = maximum pressure). See §5 |
| `--score-source` | `live` (default) reads `GET /runs/.../scores`; `fixture` reads committed test fixtures |
| `--legacy-citations` | Falls back to citations that validate against today's `EvidenceType`. **Currently required for any real post** — see §5 |
| `--alpha-min` / `--alpha-max` | Bounds on the urgency/waiting weight. Defaults 0.5 and 0.9 |
| `--dry-run` | Assemble and print; post nothing |

### Exit codes

| Code | Meaning |
|---|---|
| 0 | Decision posted, `200` |
| non-zero, distinct | `207` — Postgres committed but the graph projection failed. **Not success.** The row stands; the graph is behind. Retry and reconciliation are out of scope per ADR-002 |
| non-zero, distinct | `400` — Postgres rejected the payload |
| non-zero, distinct | `422` — validation failed before either store was touched |
| 2 | Argument error, including a missing `--capacity-direction` |

An undocumented status code raises rather than being silently accepted.

## 5. Two things that will bite

**`--capacity-direction` has no default and the agent refuses to start without it.** This is
deliberate (ADR-007). `capacity_score` is a 0–1 float whose direction is owned by the
capacity agent and, at the time of writing, undocumented. Read backwards, `scarcity` inverts,
α inverts, and the system weights clinical urgency *least* when the hospital is under most
pressure — with every number still in range and every ranking still superficially plausible.
No test catches that. A loud refusal is the cheapest version of the problem.

The configured value is recorded in `coordinator_version` on every decision, so any ranking
ever written is traceable to the assumption it was made under.

**Default citations do not validate today.** The coordinator's honest evidence for a ranked
position is the urgency `Score` node and the `ReferralState` carrying the wait against the
CRT. Neither is a member of the retrieval service's `EvidenceType`, so a default-mode post
fails with `422` and one `literal_error` per citation (ADR-009). Until that enum is widened,
use `--legacy-citations`, which copies the urgency agent's own citations for the `urgency`
role and omits `timeframe` entirely.

## 6. Checking it worked

```bash
python -m pytest coordinator/tests/ -q
```

**One test fails deliberately** —
`test_citation_contract.py::test_role_evidence_types_are_valid_evidence_types`. It is the
tracking mechanism for the ADR-009 change request and turns green when that lands. Do not fix
it. Its mirror in `test_decision.py` goes red on the same event; the two together are one
signal, not two problems.

The gates, run **separately** — `&&` short-circuits on pytest's non-zero exit and you will
never see mypy run:

```bash
ruff format --check coordinator/
ruff check coordinator/
python -m mypy --config-file coordinator/mypy.ini --explicit-package-bases coordinator
python -m pytest coordinator/tests/ --cov=coordinator/app --cov-report=term-missing -q
```

Expected: 18 files clean under mypy, **100% coverage on the six Tier 1 modules**
(`bands`, `citations`, `priority`, `ranking`, `rule_checks`, `decision`). `cli.py` is Tier 3
and has no coverage gate.

A dry run against the real 9004 cohort on 2026-08-30 should rank **500 referrals**, in bands
of 131 Urgent, 133 Semi-Urgent, 141 Routine and 95 uncategorised, in that order.

## 7. When it goes wrong

| What you see | Fix |
|---|---|
| `503` from `/health` | A dependency is down. The response body names which. Usually Oxigraph is empty or `retrieval_rw`'s password does not match `RETRIEVAL_DB_URL` |
| `role "retrieval_rw" does not exist` | Migration 009 never ran on this volume. See §2 |
| `KeyError: 3` from band resolution | `cpc` arrives from the endpoint as `int` or `None`, never `str`. Do not coerce with `str(cpc)` — that would accept `"03"` and `3.0` silently |
| `Source file found twice under different module names` from mypy | Use the documented invocation in §6. `coordinator/__init__.py` makes the package root unambiguous |
| mypy appears to pass but never ran | You chained the gates with `&&`. Pytest exits non-zero because of the deliberate failure. Run them separately |
| `ruff format` unwraps lines you just wrapped | `coordinator/ruff.toml` sets 100 columns; `conductor/code_styleguides/python.md` says 80. The `.toml` wins because the formatter reads it. This disagreement is unresolved across the repo |
| `coordinator: error: --capacity-direction is required` | Correct. That is ADR-007 working. Pass `availability` or `pressure` |
| `422` with `literal_error` on `evidence_type` | Expected in default citation mode. Use `--legacy-citations` (§5) |
| Empty cohort, no error | Either the hospital is private (`9101`/`9102`, capacity only, no queue) or the date is outside 2026-08-17 to 2026-08-30 |
| `ModuleNotFoundError: retrieval` | Run from the repo root. The coordinator imports the retrieval service's schemas directly rather than reimplementing them |
| `ModuleNotFoundError: coordinator` | Also run from the repo root. `python -m coordinator` resolves the package from the working directory |
| Dependency conflicts on install | You are in conda base. Create a dedicated 3.12 environment (§1) |
| A shell command runs twice | A paste artefact, not the code. Harmless for reads, not harmless for scripts that append |

## 8. Versions

| | |
|---|---|
| Python | 3.12.11 |
| Dataset | schema 008+010, data `v1.1`, `full` profile |
| Graph | 590,814 triples across two named graphs |
| Retrieval service | `retrieval-service_20260904` |
| ruff | see `coordinator/requirements-dev.txt`; config `coordinator/ruff.toml`, 100 columns |
| mypy | config `coordinator/mypy.ini`, `disallow_untyped_defs = True` |
| Tests | 73 total, 72 passing, 1 deliberately failing |
