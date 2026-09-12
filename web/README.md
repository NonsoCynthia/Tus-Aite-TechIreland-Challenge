# Clinician interface

The screens a clinician reads: the hospital overview, the ranked list, one patient's evidence, a run in
progress, the decision record, the cohort graph, and a read-only AI assistant panel for questions about the
current hospital-day or selected referral. The assistant is available from the landing page and across the
entered decision-support interface. React 19 and TypeScript, built by Vite, served as static files by the
orchestrator in [`../orchestrator/`](../orchestrator/).

**Nothing clinical is worked out here.** Every figure on screen arrives over `/api/*`: the ordering from
[`../coordinator/`](../coordinator/README.md), the scores from [`../urgency-agent/`](../urgency-agent/README.md)
and [`../capacity-agent/`](../capacity-agent/README.md). This track owns how those numbers are shown, and
refusing to show one without the caveat that belongs to it. Three decisions taken elsewhere bind these screens,
all recorded in `conductor/tracks/<track>/decisions.md`, where they are written as `ADR-00N` and each track
numbers its own, so the same number means different things on different tracks and the track name is part of
the citation:

- Capacity measures **pressure**, not spare capacity (`coordinating-agent_20260906` ADR-007), and it modulates
  the weights for a whole hospital-day rather than any one referral's score, so it can never move one person
  past another (same track, ADR-005).
- Paediatric referrals are **refused, not scored**, so such a row must never show an adult NEWS2 as that child's
  acuity, and must never be sorted on one (`explainable-agent-based-triage_20260828` ADR-007).
- The urgency score uses NEWS2 only and is knowingly incomplete: 31% of Urgent referrals score zero
  (`explainable-agent-based-triage_20260828` ADR-004).

## Get it running

You need Docker running, a copy of `.env` made from `.env.example`, and access to the dataset. The data is
**gated**: the page is public but the files are not, and Thabang approves each person by hand, in a browser.
There is no way to request it from a script, and a rejected request is final. Ask first if you are unsure.
`dataset/docs/GETTING_THE_DATA.md` walks through it.

```bash
# 1. From the repo root, not web/. Starts the database, pgadmin, Oxigraph and
#    retrieval. It does NOT start the interface. There is no `make ui`.
make up

# 2. The interface. The bundle is compiled inside the image, so nothing you
#    build on your own machine is used and --build is needed every time.
docker compose up -d --build orchestrator

# 3. Open http://localhost:8080. The port comes from UI_PORT, which is not in
#    .env or .env.example, so 8080 applies unless you set it yourself.
#    The AI assistant also needs OPENAI_API_KEY in the root .env.

# 4. Optional: live reload, with the container above still up.
cd web && npm install && npm run dev     # serves :5173

# 5. Before you push. `npm run build` runs the compiler with checking turned
#    off, so this is the only real type check.
./node_modules/.bin/tsc --noEmit -p tsconfig.json
```

`npm run dev` sends `/api` calls to `127.0.0.1:8080` rather than straight to retrieval. Retrieval refuses calls
that come from a different address, and the access token must never reach the browser, so the browser has to see
the API on the same address as the page. In the container that is literally true: one process serves both.

## How it is checked

There are no unit tests, no linter and no formatter in this folder. Standing in for them is
`orchestrator/tests/demo_path.py`: 83 checks walked against the running system rather than against mocks, from
the page being served through a real ranking run to the evidence behind one position. It starts that run itself,
so do not use it during a demo.

83 is what runs, not what is written: there are 82 call sites, one of which sits in a loop over two categories.

Two habits matter more than the count. Every claim on screen names the file and line it came from, so a reader
can check it. And the checks are pinned to this dataset's exact numbers on purpose, so a silent change in the
data fails them rather than passing quietly.

## How it is put together

```
src/
  main.tsx       mounts the app, loads tokens.css then app.css, sets the fetch defaults
  App.tsx        the shell: side rail, top bar, hospital and day pickers, Run
  tokens.css     every colour, spacing, type and motion value. Nothing else declares one
  app.css        the shell, and every shared piece with no stylesheet of its own
  surfaces/      one screen per file. Six of the seven have their own stylesheet;
                 Landing has none, its rules sit in app.css
  components/    severity marks, disclosures, vitals, agent inputs, journey, compare,
                 override, provenance, the mark, assistant panel
  lib/           api calls, types, target days, the NEWS2 tables, the severity scale
```

There is no router: `App.tsx:73` holds which screen is showing as ordinary state, and the rail sets it.

**A stylesheet is imported by the one module that owns it.** The rationale lives in that module's opening
comment; the stylesheet only spends tokens. All ten sheets have exactly one importer.

Name prefixes are looser than that. `overview.css` really does own `.ov-` and nothing else, but most sheets
carry several families: `list.css` holds `.lst .ev .key .recon .tb .spn`, `patient.css` holds `.pt .nb .j .cmp
.why`. Treat a sheet as belonging to its screen, not as owning one prefix. A shared component gets its own file
only when it is used on many screens, today `Severity` and `Aside`; the rest live in `app.css`. Load order is
`tokens.css`, then `app.css`, then each screen's sheet as that screen is imported, which is what lets three
sheets retune a piece `app.css` owns: `patient.css` restyles `.cmp-trow`, `record.css` restyles `.p-note` and
the section headings, `list.css` restyles `.n2`.

## The screens

| screen | the question it answers |
|---|---|
| `Landing.tsx` | What am I looking at, and how big is it? |
| `Overview.tsx` | What is the state of this hospital-day before I touch anything? |
| `List.tsx` | In what order should I work, and why is each row where it is? |
| `Patient.tsx` | Why is this person here? |
| `Run.tsx` | What is about to happen, and did it? Opens over the page, not as a destination |
| `CohortGraph.tsx` | What does the whole decision look like as evidence? |
| `DecisionRecord.tsx` | What was decided, and against which rules? |

`List.tsx` is the largest file here and the one to read first: nine columns wide, each row expanding in place
into the evidence behind that position.

## The design system

**Colour is declared in one file.** `tokens.css` holds every value: brand constants, then the light set, then
the dark set. Dark is not a page theme but opt in for a subtree, since the rail is dark while the table beside
it is light. No other stylesheet holds a colour literal. The one licensed exception is in TypeScript: the graph
library needs literal fills, so `Provenance.tsx` and `CohortGraph.tsx` carry palette objects, and `Mark.tsx`
carries two because it draws a shape.

**Five colours are reserved for the clinical categories** and mean only a category: urgent, semi-urgent,
routine, uncategorised, outside the ranking. Red, amber and green appear nowhere else, not even for Manchester
triage, which has its own colour vocabulary and is shown in a neutral register instead. The class names are
assembled by joining strings in two places, `List.tsx:785` and `Patient.tsx:45`. Searching the TypeScript for
`cat-semiurgent` therefore finds no place it is built, only the rule itself in `app.css` and two comments: a
tidy-up once read that as dead CSS, deleted the rules, and two categories lost their colour.

**The severity scale is the main visual language.** One scale, four steps, every attention state rendered
through it, so a reader learns it once.

| step | word | how it is drawn |
|---|---|---|
| 1 | noted | a hairline |
| 2 | attention | a tint |
| 3 | high | a solid block |
| 4 | severe | a solid block with a ring around it |

Step 0 is not a step, it is the absence of a mark. Steps escalate by **fill area** before hue, because a solid
block carries across a room and 11px of coloured text does not. What drives a step is always a number, never a
category: how far past target as a multiple, how old a reading is, one vital's NEWS2 contribution, ward
occupancy against the safe line, clinic slots booked. One band function per axis, all in `lib/severity.ts` from
line 57. Data that does not reconcile is fixed at step 4, the loudest thing the product can say, because a
clinician can act on a bad number.

**Colour is never the only channel.** A mark always renders its own value; the step is spoken to a screen reader
as a word plus its place in the scale (`Severity.tsx:49` gives "marked severe (4 of 4)"); fill area grows with
the step; and the legend names the steps in words on the same screen, painted from the same code the marks use.

Before changing a value: the smallest type is 11px (`tokens.css:188`) and **must not be raised**, since the
ranked table is measured to the pixel: 1,414 of columns, and 1,716 of viewport once the rail and padding are
counted, which is where the ninth column switches on (`List.tsx:110-153`). One step up reflows it. There
are no drop shadows, gradients or glows either; depth comes from four grounds and two weights of rule.

## How a screen gets its data

One trace: a clinician opens the ranked list, and one wait figure with its mark appears.

1. `main.tsx:4-5` loads the tokens and shell styles, and `main.tsx:8-10` sets the fetch defaults: no refetch
   on window focus, 30 seconds before a value is stale, one retry.
2. `App.tsx` holds the hospital and the day. The day is not hardcoded: it asks `/api/hospital-days/{hospital}`
   which days hold a list, and defaults to the newest one that can be scored.
3. `List.tsx:204-219` fires four calls, for the cohort, the operations snapshot, the decision and the overrides,
   merging them into one row per referral with any live override spliced in. A 404 on the decision is the normal
   "nothing has run yet" and is not retried.
4. The row carries a wait of 871 days and category code 1. The target comes from `crtDays()` in `lib/ref.ts:33`,
   which reads `/api/reference` and returns 28; the cohort row's own copy is a first-paint fallback only. The
   ratio is 31.107, which `sevWaitRatio()` at `lib/severity.ts:57` turns into step 4.
5. `List.tsx:1580` draws the cell: the number, a bar at step 4, then `31× over a 28-day target` below. The
   multiple is rounded once it passes ten (`List.tsx:68`), so the screen says 31 and the full figure stays in
   the tooltip. No chip here, deliberately: the bar already carries the graded channel for that exact fact.
   `list.css` resolves step 4 to a token and `tokens.css` resolves the token.

The legend above the table paints its steps from the same code the marks use, so key and mark cannot drift.

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
| `POST /api/runs` | starts a ranking run |
| `/api/runs/{run_id}` | that run's live progress while it works |
| `/api/scores/{run_id}/{hospital}` | each agent's score with the evidence it cited |
| `POST /api/overrides` | records what a clinician did |
| `POST /api/hospital-days/{hospital}/refresh` | looks again for days that hold a list |
| `POST /api/chat` | sends a clinician's read-only question to the server-side OpenAI assistant |

Unmarked rows are GET. Defined in `orchestrator/app/main.py`, typed in `src/lib/api.ts`. An unknown GET path
returns the page rather than a 404, so a 200 does not prove an endpoint exists.

## AI assistant

`AssistantPanel.tsx` adds a bottom-right Tus prompt that says "I am Tus, here to answer your questions."
It is rendered as an app-level overlay rather than inside one screen, so it remains visible on the landing page,
overview, ranked list, patient evidence view, knowledge graph, and decision record.
It sends the current hospital, date and selected pathway to `POST /api/chat`, so the model has UI context but the browser never sees
`OPENAI_API_KEY` or `RETRIEVAL_BEARER_TOKENS`.

The assistant is intentionally read-only in the UI. The orchestrator calls `orchestrator-agent`'s
Q&A-only agent, whose available tools can read retrieval/cohort/evidence data and generate rationale, but
cannot trigger urgency, capacity or coordinator runs. Running the agents remains the job of the existing
`Run the agents` control.

Common UI questions do not need the evidence-heavy retrieval Decision endpoint. Before the model sees a
question, `orchestrator/app/main.py` adds compact current facts from the same state the UI displays: hospital
name, waiting-list count, ranked count, first ranked referral, and the selected referral's rank when there is
one. This keeps questions such as "Who is ranked first?" and "How many referrals are on the list?" fast, while
the evidence and rationale tools remain available for "why" questions. Specific-referral rationale uses the
single-placement evidence endpoint, and falls back to deterministic prose if the LLM wording layer fails its
citation check.

The server also appends the decision-support caveat when the model omits it, so every chat response keeps the
clinical boundary visible.

## Numbers that are typed in rather than fetched

They fall into two kinds, and the difference matters. **No clinical figure is one of them:** every wait, breach,
score, ward figure, rule verdict and position on screen is fetched at runtime.

The first kind describes the outside world, and each would go out of date quietly: nothing breaks, no test
fails, the figure on screen is simply wrong. There are two.

- **The national waiting-list figures** at `src/surfaces/Overview.tsx:82`: snapshot date, totals, four band
  counts. The source is republished monthly. The file's own total and the sum of its four bands disagree by 4,
  which the screen states rather than hides, and the shares are taken from the band sum they are counted from.
- **The category-code to name map** at `src/lib/api.ts:180`. Code 3 ranks above code 2, so sorting on the raw
  number puts Routine above Semi-Urgent: always go through `bandOf()` at `src/lib/api.ts:187`. It also has no
  entry for code 4, "Excluded", which `/api/reference` publishes, so an excluded referral would show as
  "Uncategorised". No code 4 exists in the data today, so that one is latent rather than live.

The second kind is clinical rubrics and published thresholds, which belong in code rather than in a database
row. The NEWS2 band tables at `src/lib/news2.ts` mirror `../urgency-agent/urgency_agent/news2.py`; the 85% safe
occupancy line is a published figure (Bagust, Place and Posnett, British Medical Journal 1999); the ward and
clinic weights of 0.7 and 0.3 mirror the capacity agent's own settings file. These are checked rather than
trusted: the patient page recomputes the NEWS2 total and the capacity blend from the parts, compares them with
what the agent returned, and shows a visible warning when the two disagree.

## Behaviour that surprises people

**An override belongs to one ranking, not to a date.** Run the agents again and you get a new ranking, so
earlier placements show as "not applied" rather than being quietly moved onto a list they were never made against.

**Ward and clinic figures are the same on every day.** They are read newest first with no date filter, so each
panel shows its own snapshot date and says so when they differ. Never label them as the selected day's.

**An old reading is missing information, not good news.** Its age is always shown beside it, and no reassuring
word may stand in for the number.

**Which slice of the data you loaded matters.** `make load` fetches the **sample** by default: 2 hospitals, 609
referrals, about 1.3 MB. The full set is 6 hospitals and 5,200 referrals, about 11 MB, via
`make load FETCH_PROFILE=full`. The dataset track's advice is to use `full` for anything you show people, since
the sample holds only the two largest hospitals and loses the contrast between a 640-bed teaching hospital and a
110-bed district one. Two things before you switch:

- **The 83 checks in `orchestrator/tests/demo_path.py` are pinned to the sample's exact numbers**: 308
  referrals, 165 with a target, 305 ranked, 7 wards. On the full set they fail on the counts, and say so before
  they do. That is the tripwire working, but the numbers must be updated before the checks mean anything again.
- **Targets apply to 165 of the sample's 308 referrals.** The other 143 have no target and can never be late, so
  a count of breaches is always out of 165.

Everything else follows the data: hospitals, the days that hold a list, target days and specialty names are read
at runtime, so six hospitals appear with no code change. Two of the six are private sites carrying capacity and
no referrals by design, and picking one shows a short screen saying so rather than an empty list.

## Where to look next

| | |
|---|---|
| [BUILD_LEDGER.md](BUILD_LEDGER.md) | What was built and what was found: every task with its evidence, every review finding, and what was deliberately left alone |
| [DESIGN_PACK.md](DESIGN_PACK.md) | The full interface specification: screens, components, exact wording, the data contract. Where it and this file disagree, it wins |
| [`../coordinator/README.md`](../coordinator/README.md) | What produced the order these screens draw |
| [`../urgency-agent/README.md`](../urgency-agent/README.md) | Where the NEWS2 tables mirrored in `src/lib/news2.ts` come from |
| [`../retrieval/README.md`](../retrieval/README.md) | The service the orchestrator reads from |
