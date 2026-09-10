# Clinician interface

The screens a clinician reads: the ranked list, one patient's evidence, the hospital
overview, a run in progress, the decision record and the cohort graph.

React 19 and TypeScript, built by Vite, served as static files by the orchestrator in
[`../orchestrator/`](../orchestrator/).

**Nothing clinical is worked out here.** Every figure on screen arrives over `/api/*`.
The ordering comes from [`../coordinator/`](../coordinator/README.md), the scores from
[`../urgency-agent/`](../urgency-agent/README.md) and
[`../capacity-agent/`](../capacity-agent/README.md). What this track owns is how those
numbers are shown, and refusing to show one without the caveat that belongs to it.

Three decisions made on other tracks limit what these screens may say. They are recorded
in `conductor/tracks/<track>/decisions.md`, and the numbering restarts on each track, so
the track name matters as much as the number.

- Capacity is a measure of **pressure**, not spare capacity. It sets one weight for a
  whole hospital-day and never moves one person past another.
  (`coordinating-agent_20260906`, ADR-007)
- Paediatric referrals are **refused, not scored**. A refused row must never show an
  adult NEWS2 as if it were that child's acuity, and must never be sorted on one.
  (`explainable-agent-based-triage_20260828`, ADR-007)
- The urgency score uses NEWS2 only, and is knowingly incomplete. 31% of Urgent
  referrals score zero. (`explainable-agent-based-triage_20260828`, ADR-004)

## Get it running

```bash
# 1. From the repo root, not from web/. This starts the database, pgadmin,
#    Oxigraph and retrieval. It does NOT start the interface. There is no
#    `make ui` and no `make web`.
make up

# 2. The interface. The bundle is compiled inside the image, so nothing you
#    build on your own machine is used, and --build is needed every time.
docker compose up -d --build orchestrator

# 3. Open http://localhost:8080
#    The port comes from UI_PORT, which is not in .env or .env.example, so
#    8080 is the only value that applies unless you set it yourself.

# 4. Optional. Live reload while you work, with the container above still up.
cd web && npm install && npm run dev     # serves :5173
```

`npm run dev` sends `/api` calls to `127.0.0.1:8080` rather than straight to retrieval.
Retrieval allows no cross-origin calls and the access token must never reach the browser,
so the browser has to see the API on the same address as the page. In the container that
is literally true: one process serves both.

## The endpoints these screens use

| path | what it carries |
|---|---|
| `/api/health` | whether the database, the graph store and retrieval are up, and whether a decision came from a run or from a restored snapshot |
| `/api/cohort/{hospital}/{date}` | who is on the list, with their category, waits and targets |
| `/api/decision/{hospital}/{date}` | the ranking. Returns 404 until a run has produced one, which is normal and not an error |
| `/api/hospital-days/{hospital}` | which days hold a list, found from the data rather than typed in, and which single day can be scored |
| `/api/operations/{hospital}/{date}` | every ward's own snapshot, clinic sessions, how old each reading is |
| `/api/context/{hospital}/{pathway}` | one referral's observations, conditions and triage events |
| `/api/reference` | specialty names, the official target days, the five rule statements |
| `/api/hospitals` | hospital codes and names. An empty list means the read failed, not that there are no hospitals |
| `/api/overrides/{hospital}/{date}` | what a clinician did, read back with their name and reason |
| `/api/graph/cohort/{run_id}` | the whole decision as nodes and links |
| `/api/runs` | starts a run, then reports its progress |
| `/api/scores/{run_id}/{hospital}` | each agent's score with the evidence it cited |
| `/api/overrides` | records what a clinician did |
| `/api/hospital-days/{hospital}/refresh` | looks again for days that hold a list |

Defined in `orchestrator/app/main.py`, typed in `src/lib/api.ts`. A path matching none of
them returns a page, not a 404, so a 200 does not prove an endpoint exists.

## Read this before trusting the screen

- **An override belongs to one ranking, not to a date.** Run the agents again and you get
  a new ranking, so earlier placements are shown as "not applied" rather than quietly
  moved onto a list they were never made against.
- **Targets apply to 165 of the 308 referrals.** The other 143 have no target, so they
  can never be late. A count of breaches is always out of 165.
- **Ward and clinic figures are the same on every day.** They are read newest-first with
  no date filter, so each panel shows its own snapshot date and says so when they differ.
  They must never be labelled as the selected day's.
- **An old reading is missing information, not good news.** Its age is always shown
  beside it, and no reassuring word is allowed to stand in for the number.
- **Five colours are reserved for the clinical categories** and are used in exactly five
  places. Two of those class names are assembled in code rather than written out, so a
  search for them finds nothing. A tidy-up once deleted them and two categories lost
  their colour.

## Three numbers are typed into this code, not fetched

Each is correct against this repository today. Each would go out of date quietly: nothing
breaks, no test fails, the figure on screen is simply wrong.

| number | where | what makes it go stale |
|---|---|---|
| The national waiting-list figures | `src/surfaces/Overview.tsx:82` | The source is republished monthly. An earlier hand-typed total had already drifted by 1,278 people |
| `DAILY_ROWS = 70_022` | `src/surfaces/Overview.tsx:101` | The row count of the intake file. Load a different data profile and it changes with nothing to notice |
| The category-code to name map | `src/lib/api.ts:171-178` | Code 3 ranks above code 2, so sorting on the raw number puts Routine above Semi-Urgent. Always go through `bandOf()` |

## Which slice of the data you loaded

`make load` fetches the **sample** by default: 2 hospitals and 609 referrals, about 1.3 MB.
The full set is 6 hospitals and 5,200 referrals, about 11 MB.

```bash
make load FETCH_PROFILE=full
```

The dataset track's own advice is to **use `full` for anything you show people**, because
the sample holds only the two largest hospitals and so leaves out the contrast between a
640-bed teaching hospital and a 110-bed district one, which is part of what the data
exists to show. See `dataset/docs/GETTING_THE_DATA.md`.

Two things to know before you switch:

- **The 81 checks in `demo_path.py` are pinned to the sample's exact numbers**: 308
  referrals, 165 with a target, 305 ranked, 7 wards, and so on. On the full set they fail
  on the counts. That is the tripwire working as intended, not a broken system, but the
  numbers have to be updated before the checks mean anything again.
- **`DAILY_ROWS` in `src/surfaces/Overview.tsx:101` is the sample's row count** and is
  typed in, so it will be quietly wrong until someone changes it.

Everything else follows the data. The hospital list, the days that hold a list, the target
days and the specialty names are all read at runtime, so six hospitals appear without any
code change. Two of the six are private sites that carry capacity and no referrals by
design: picking one shows a short screen saying so, rather than an empty list.

## Layout

```
src/
  App.tsx        the shell: side rail, top bar, hospital and day pickers, Run
  tokens.css     every colour, spacing and motion value. No colour is written anywhere else
  surfaces/      one screen per file
  components/    the pieces screens share: vitals, agent inputs, severity marks, Aside
  lib/           api calls, types, target days, NEWS2 tables, the severity scale
```

## Checks

```bash
cd web
./node_modules/.bin/tsc --noEmit -p tsconfig.json   # the real type check
npm run build
python3 ../orchestrator/tests/demo_path.py          # 81 checks, needs the stack running
```

**`npm run build` does not fail on a type error.** It runs the compiler with checking
turned off, so run the first command yourself.

**There are no unit tests, no linter and no formatter** in this folder. What stands in for
them is `demo_path.py`, which makes 81 checks against the running system rather than
against mocks, plus the review record in `BUILD_LEDGER.md`. It starts a real run, so do
not use it during a demo.

## More documentation

| | |
|---|---|
| [BUILD_LEDGER.md](BUILD_LEDGER.md) | What was built and what was found: every task with its evidence, every review finding, and what was deliberately left alone |
| [DESIGN_PACK.md](DESIGN_PACK.md) | The full interface specification: screens, components, exact wording, the data contract. Where it and this file disagree, it wins |
| [`../coordinator/README.md`](../coordinator/README.md) | What produced the order these screens draw |
| [`../retrieval/README.md`](../retrieval/README.md) | The service the orchestrator reads from |
