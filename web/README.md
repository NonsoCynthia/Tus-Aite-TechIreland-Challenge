# Clinician Interface

The ranked list a clinician actually reads, and the evidence behind every position
(`conductor/tracks/explainable-agent-based-triage_20260828/spec.md` FR5). React 19 + TypeScript,
built by Vite, served as static files by the FastAPI orchestrator in
[`../orchestrator/`](../orchestrator/). **Nothing clinical is computed here** — every figure on
screen arrives over `/api/*` from the coordinator, the two agents and the retrieval service. What
this track owns is display order, formatting, and refusing to render a number without the caveat
that travels with it (spec.md NFR5).

**Scope:** `web/` and `../orchestrator/`, which has no README of its own. Neither writes to Postgres
or Oxigraph — the orchestrator's two direct reads open read-only at the session level rather than
trusting the SQL to stay well behaved (`orchestrator/app/sources.py:10-13`).

Three cross-track ADRs bind what may appear on screen, qualified by track because ADR numbers
**collide** — each `conductor/tracks/<track-id>/decisions.md` numbers its own `###` sections from
ADR-001, so a bare "ADR-007" names two of them.

- (`coordinating-agent_20260906` ADR-007) `capacity_score` is resource **pressure**, not
  availability. It sets `alpha` for the whole hospital-day and never moves an individual.
- (`explainable-agent-based-triage_20260828` ADR-007) specialty `0601` is **refused**, not scored.
  Refused rows must never show an adult NEWS2 as acuity, and must never be ordered on one.
- (`explainable-agent-based-triage_20260828` ADR-004) `urgency_score` is NEWS2-only and knowingly
  incomplete: 31% of Urgent referrals score 0 (`../urgency-agent/README.md`).

## Get it running

```bash
# 1. From the REPO ROOT, not here. Starts db, pgadmin, oxigraph, retrieval --
#    and NOT the orchestrator (Makefile:22-27). There is no `make ui` and no
#    `make web` target; the UI is a compose service like any other.
make up

# 2. The bundle is compiled INSIDE the image (orchestrator/Dockerfile stage 1),
#    so nothing built on the host is used and `--build` is needed every time.
docker compose up -d --build orchestrator

# 3. http://localhost:8080. UI_PORT appears once, at docker-compose.yml:139,
#    and is in NEITHER .env NOR .env.example -- the `:-8080` default is the
#    only value that applies. Every other port here is declared in .env.

# 4. Optional live-reload loop, container above still up. Serves :5173.
cd web && npm install && npm run dev
```

`npm run dev` proxies `/api` to `127.0.0.1:8080` (`vite.config.ts:10`) rather than calling retrieval
directly: retrieval ships no CORS middleware and `Authorization` is not a safelisted request header,
so every cross-origin call dies at preflight and the browser must see the API as same-origin. In the
container that is literal — one process serves both, and the bearer token never reaches the browser
(`main.py:3-6`). `orchestrator/Dockerfile` is two-stage: `node:22-alpine` runs `npm run build` on
`web/`, then the `python:3.12-slim` image copies `/ui/dist` to `/app/web/dist`
(`Dockerfile:7-12,33,39`).

## The endpoints this UI consumes

| | path | what it carries |
|---|---|---|
| `GET` | `/api/health` | retrieval + postgres + oxigraph status, `capacity_direction`, which hospital-days hold a decision and whether it came from a run or the restored snapshot |
| `GET` | `/api/cohort/{h}/{date}` | who is on the list: CPC, wait counters, `crt_threshold_days`, `crt_breached` |
| `GET` | `/api/decision/{h}/{date}` | the ranking the orchestrator built. **404 until a run exists — a normal state, not an error** |
| `GET` | `/api/hospital-days/{h}` | which days hold a cohort, discovered not hardcoded, plus the one `runnable` day |
| `POST` | `/api/hospital-days/{h}/refresh` | re-probes that window ("check for new data") |
| `GET` | `/api/operations/{h}/{date}` | every ward's own snapshot, clinic sessions with the one cited session marked, reading ages, per-referral `news2` |
| `GET` | `/api/context/{h}/{pathway}` | one referral's observations, conditions, triage events |
| `GET` | `/api/scores/{run_id}/{h}` | urgency and capacity scores with citations as lists, not collapsed |
| `GET` | `/api/reference` | `core.ref_*`: specialty names, authoritative `crt_days`, all five rule statements |
| `GET` | `/api/hospitals` | `core.hospitals`: HIPE ids and display names. **An empty array means the read failed, not that no hospitals exist** (`main.py:412-416`) |
| `GET` | `/api/overrides/{h}/{date}` | the override log, read back with attribution |
| `GET` | `/api/graph/cohort/{run_id}` | the whole decision as nodes and evidence links, one SPARQL query |
| `POST` `GET` | `/api/runs`, `/api/runs/{run_id}` | starts a ranking run; then its live progress |
| `POST` | `/api/overrides` | writes a clinician override through retrieval |

All same-origin, defined in `orchestrator/app/main.py`, typed in `src/lib/api.ts`. A path matching
none of them returns **`200 text/html`**, not 404: the catch-all at `main.py:657-662` serves
`index.html` for everything unmatched, `/api/*` included.

## Non-clinical constants typed into this frontend, not fetched

Three remain. Each verifies exactly against this repo today, and each would go stale **silently**:
nothing throws, no test breaks, the figure is simply wrong on screen.

| constant | where | what goes stale |
|---|---|---|
| NTPF national figures — snapshot `2026-07-30`, total 683,553, four band counts | `src/surfaces/Overview.tsx:81-96` | NTPF republishes monthly. The comment above it records that the last hand-written total had already drifted 1,278 people, which is why the band total is now derived rather than typed |
| `DAILY_ROWS = 70_022` | `src/surfaces/Overview.tsx:100` | the row count of `dataset/out/referral_daily.csv`, backing the claim that this list only ever accretes. A reload at another profile changes it and nothing notices |
| the cpc → band-name map | `src/lib/api.ts:171-178` | **cpc 3 outranks cpc 2.** `SEVERITY_RANK` maps 1→1, 3→2, 2→3, so sorting on the raw code puts Routine above Semi-Urgent. Always resolve through `bandOf()`. Its `target` days (28/91) are a first-paint fallback only — authoritative CRT is `core.ref_codes.crt_days` via `crtDays()` (`src/lib/ref.ts:33`) |

A fourth was fixed while this README was written: the hospital ids and names were a literal in
`App.tsx`. `GET /api/hospitals` now exists (`main.py:398-432`, reading `core.hospitals`),
`api.hospitals()` consumes it (`src/lib/api.ts:41`) and the selector builds from the roster
(`App.tsx:167-172`). **The running container still serves the pre-change bundle** — that path
answers `200 text/html` on `:8080` until `docker compose up -d --build orchestrator` runs again.

## Read this before you trust anything on the screen

- **An override is bound by foreign key to a `decision_id`**, not a date (`main.py:447-450`), so
  re-running a hospital-day drops the placements a prior override named. Those show as **"not
  applied"** with the decision id that owned them (`List.tsx:1496-1502`); `List.tsx:220-239` filters
  on `o.decision_id === d.decision_id`, so nothing re-applies to a list this run never built.
- **Breaches are of the 165 referrals with a target, never of 308.** 143 have no target at all.
  Never hardcode 28 or 91; read `crtDays()`.
- **Capacity evidence is date-blind.** All 14 days are served the same 30 August ward snapshot, so
  ward and clinic panels carry their *own* snapshot date and say "mixed snapshots" when wards
  disagree (`Overview.tsx:1385-1400`). It may never be labelled as the selected day's.
- **A stale reading is an absence of information, not reassurance.** Its age travels with it, and
  no reassurance word may stand in for the number.
- **`--cat-urgent` / `-semi` / `-routine` / `-uncat` / `-outside` are reserved for CPC band chips**
  — exactly five rules in `src/app.css:212-215,267`. Two of those class names, `.cat-semiurgent` and
  `.cat-uncategorised`, are built by **string concatenation** at `List.tsx:776` (from `TAB_TOKEN`,
  `List.tsx:195-198`) and `Patient.tsx:44`, so both are invisible to grep; a dead-CSS sweep deleted
  them once, leaving two of the five swatches with no colour.

## Layout

```
src/
  App.tsx              shell: rail, top bar, hospital/day selector, Run action
  app.css / tokens.css shell styles, the five reserved .cat-* rules, and every colour,
                       density and motion token. No hex literal lives outside tokens.css
  surfaces/            one route per file, six stylesheets between them
    Overview.tsx         hospital-day instruments: NTPF, intake, wards, clinics, rule board
    List.tsx             the ranked table, inline evidence expander, override, sort-key ladder
    Patient.tsx          one referral: who, why, what informed the agents, journey, limits
    Run.tsx              per-agent lanes while a run executes, then the cohort graph
    CohortGraph.tsx      the decision as a graph, WebGL, with a context-loss guard
    DecisionRecord.tsx   all five rule IDs, the reconciliation, the override log
    Landing.tsx          the screen the demo opens on
  components/          Vitals (NEWS2 sub-scores), AgentInputs (the two agent lanes), Severity
                       (the ramp + its legend), Aside, Journey, Compare, Override, Provenance, Mark
  lib/                 api.ts (every fetch, and BANDS), types.ts, ref.ts (crtDays,
                       isRefusedPaediatric), news2.ts (the agent's six band tables), severity.ts
                       (the ramp, SAFE_OCCUPANCY), stats, planted, useNarrow
```

## Quality gates

```bash
cd web
./node_modules/.bin/tsc --noEmit -p tsconfig.json   # the real type gate
npm run build
python3 ../orchestrator/tests/demo_path.py          # 81 assertions, needs the stack up
```

**`npm run build` is `tsc -b --noCheck && vite build` (`package.json:8`) — `--noCheck` means a type
error does not fail the build.** Run `tsc --noEmit` yourself; the build will not do it for you.
**There is no `test` script and no `lint` script** in `web/package.json`: no unit tests, no ESLint,
no formatter. Standing in for them: `orchestrator/tests/demo_path.py`, 81 assertions walked against
the *running* stack rather than mocks, plus the review gates in `BUILD_LEDGER.md`. It **starts a real
run** (`demo_path.py:80` posts `/api/runs`) — not read-only, never mid-demo.

## Documentation

| | |
|---|---|
| [BUILD_LEDGER.md](BUILD_LEDGER.md) | The accountability record, 406 lines. One row per task with its evidence, every review finding with its state, five published contrast figures that were wrong and why, and what was deliberately **not** fixed |
| [DESIGN_PACK.md](DESIGN_PACK.md) | The normative UI spec, 2,966 lines: geometry, screens, components, canonical strings, the data contract field by field, accessibility. Where it and this README disagree, it wins |
| [`../conductor/tracks/explainable-agent-based-triage_20260828/`](../conductor/tracks/explainable-agent-based-triage_20260828/) | spec.md FR5 (clinician UI) and NFR5, plus ADR-004 and ADR-007 |
| [`../coordinator/README.md`](../coordinator/README.md) · [`../retrieval/README.md`](../retrieval/README.md) | What produced the order this UI draws (and ADR-011, still open), and the service the orchestrator proxies |
