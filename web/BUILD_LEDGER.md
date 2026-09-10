# Build ledger — final UI round

The accountability record for the plan at
`~/.claude/plans/we-are-setting-up-noble-lighthouse.md`. One row per task ID.

**Rules this ledger enforces.** A task moves to PASS only with **evidence** attached: a
`file:line`, a demo-path assertion, or a screenshot. A claim is not evidence. Nothing is
reported to the user as done unless the row below says PASS. What could not be verified is
recorded as loudly as what could.

Status: `TODO` · `WIP` · `REVIEW` · `PASS` · `FAIL` · `CUT`
Gates: **D** data truth · **C** clinical safety (veto) · **S** design

---

## A · Foundations — **CLOSED**, 66/66 demo-path assertions

| ID | Task | Gate | Status | Evidence |
|---|---|---|---|---|
| A1 | Orchestrator reaches Postgres + Oxigraph read-only | D | PASS | `orchestrator/app/sources.py`; compose env; `/api/health` → `sources: {postgres: ok, oxigraph: ok}` |
| A2 | Merge `rationale_summary` + `rule_checks` onto served rankings | D | PASS | `runner.py` merge by pathway; demo_path §11 — 305/305 carry rule_checks; RULE-TRIAGE-TURNAROUND fires once |
| A3 | Harvest `ward_pressure` / `clinic_pressure` | D | PASS | `runner.py` `capacity_detail`; demo_path §11 — ward 0.913 / clinic 0.923 on 305/305 |
| A4 | Decision snapshot to disk, restore on boot | D | PASS | `state.py` `_persist`/`_restore`; restart test — run_id + alpha identical across a container restart |
| A5 | `GET /api/reference` — specialties, codes, rules | D | PASS | `main.py` `/api/reference`; demo_path §10 — 7 names, crt 28/91 from seed, all 5 rule statements |
| A6 | `GET /api/overrides/{h}/{date}` | D | PASS | `main.py` `/api/overrides/{h}/{date}`; demo_path §14 — written override read back with attribution |
| A7 | `GET /api/graph/cohort/{run_id}` — SPARQL | D | PASS | `main.py` `/api/graph/cohort`; demo_path §13 — 931 nodes, 1,691 edges, 1,386 citations, one query |
| A8 | `clinic_sessions` + ward↔specialty in `/api/operations` | D | PASS | `main.py` operations; demo_path §12 — 7 clinics, cited session marked, free beds, ward↔specialty |
| A9 | `types.ts` declares what already arrives | D | PASS | `web/src/lib/types.ts` + `api.ts` — Citation, RuleCheck, Reference, Overrides, CohortGraph |
| A10 | `demo_path.py` covers every new endpoint | D | PASS | `orchestrator/tests/demo_path.py` §10–15 — **66 passed, 0 failed** (was 35) |

## B · Design system — **CLOSED**

| ID | Task | Gate | Status | Evidence |
|---|---|---|---|---|
| B1 | Token rewrite — full-bleed grid, density, elevation by role, icons | S | PASS | `tokens.css` rewritten — density scale `--d1..--d8`, `--lift-0/1/2` by role, `--icon`, `--rail-w`; `.pad` no longer caps at 1248px |
| B2 | App shell — left rail, top bar, Run CTA, run pill | S | PASS | `App.tsx` rail + top bar; screenshot `10-shell.png` — grouped nav, run pill (α 81%), Run CTA, 3-service status |
| B3 | Brand lockup asset; `lockup-white`; descriptor behind a hairline | S | PASS | `tus-aite-lockup-white.png` copied to public/brand and used in the rail; descriptor behind a hairline per the kit |
| B4 | Glass recipe scoped to five uses, never behind a number | C | PASS | one `.glass` recipe; used only on cohort-graph panels + camera controls, never behind a number — `cohortgraph.css` |
| B5 | Motion vocabulary; nothing animates across a category boundary | C | PASS | `--ease`/`--t-*` tokens; `useReducedMotion` honoured in Run and List; no cross-boundary animation |
| B6 | Synthetic-data label (`README.md:36`) | C | PASS | `.synthetic` in the rail foot — 'Synthetic data · no real patient', permanent chrome (README.md:36, previously absent everywhere) |

## X · Built directly (not in the original list)

| ID | Task | Gate | Status | Evidence |
|---|---|---|---|---|
| X1 | `DecisionRecord` surface — rule board with all 5 rule IDs, reconciliation, override log | C | PASS | `surfaces/DecisionRecord.tsx`; screenshot `12-record.png` — 776 checks, RULE-TRIAGE-TURNAROUND 1 breached |
| X2 | **Reconciliation bug found and fixed**: buckets overlap, so a sum reads 311 of 308 | D | PASS | 3 paediatric referrals are in `refused_paediatric` AND `excluded` (`missing_urgency_score`). Union = 308. demo_path §11 asserts it |
| X3 | `lib/news2.ts` — NEWS2 band table for per-vital sub-scores | D | PASS | **verified against all 308 referrals, 0 mismatches** vs the agent's stored `news2` |
| X4 | `lib/ref.ts` — reference lookups so nothing is hardcoded | D | PASS | `specialtyFull`, `crtDays`, `ruleStatement`, `checkLabel`, `failed` |

## C · Overview → operational dashboard

| ID | Task | Gate | Status | Evidence |
|---|---|---|---|---|
| C1 | Header band as instrument readouts | S | PASS | 8 instrument readouts, `Overview.tsx`; screenshot `25-ov-after-sweep.png` |
| C2 | By specialty, real NTPF names | D | PASS | By specialty, real NTPF names + ward/clinic pressure + capacity score per specialty |
| C3 | Against the national NTPF picture | D | PASS | NTPF four bands vs national 682,279; edges 183/365/548 from `generate.py:256`, cited on screen |
| C4 | Intake over 14 days; zero removals | D | PASS | Intake 283→308, +25 added 0 removed; verified against `dataset/out/referral_daily.csv` — 70,022 rows, 0 removals |
| C5 | Clinic capacity — slots booked vs total | D | PASS | Clinic capacity, 7 clinics, session series with the cited session marked |
| C6 | Ward pressure v2 — free, DTOC, surge, specialty | D | PASS | Ward pressure v2 — free/occupied/outliers/DTOC/surge/9h/24h/GAR + primary_for + as-of |
| C7 | Live rule board, `RULE-TRIAGE-TURNAROUND` surfaced | C | PASS | Rule panel, all 5 IDs; `RULE-TRIAGE-TURNAROUND` 1 of 1 breached, first time on screen |
| C8 | Staleness as an instrument | C | PASS | Age of the newest reading — 5 readouts + histogram, no prose |

## D · The list

| ID | Task | Gate | Status | Evidence |
|---|---|---|---|---|
| D1 | Full-width table, sticky header, sort, filter, density | S | PASS | `List.tsx` full width, sticky header, 8 sort keys, search, density toggle, page size |
| D2 | Row anatomy v2 — spine, specialty, ratio, rule ID, override badge | C | PASS | Rank spine (α-weighted), specialty name, wait ratio drawn, **rule ID chip**, override badge |
| D3 | Inline evidence expander (`README.md:117`, NFR5) | C | PASS | Inline expander — cited vitals, cited ward + clinic, rule checks, rationale (README:117, NFR5) |
| D4 | Reconciliation ledger — four buckets, never summed | C | PASS | Four buckets, separately labelled, reconciled by set union; folded so it does not push the table off screen |
| D5 | Override v2 — read back, badge, row moves, system position kept | C | PASS | Override read back, row moves, system position kept; `rule_warning_accepted` bug fixed — was sent from the band comparison, not the checkbox |

## E · Patient

| ID | Task | Gate | Status | Evidence |
|---|---|---|---|---|
| E1 | Re-order the page | S | PASS | Reordered: who → why → what informed the agents → journey → chain → limits |
| E2 | Vitals as NEWS2 instrument cards | C | PASS | `Vitals.tsx` — per-vital sub-score + band meter; `3+0+3+1+0+0 = 7 of 17` with a parts-vs-total check |
| E3 | "What informed the agents" — urgency and capacity lanes | C | PASS | `AgentInputs.tsx` — capacity lane opens with *capacity did not move this person*, cites `priority.py:158-162`, marks the one session read |
| E4 | Journey v2 | S | PASS | `Journey.tsx` — past-target and unmeasured stretches drawn, not asserted |
| E5 | Instrument-limits panel; MTS in a neutral register | C | PASS | Instrument limits + NEWS2 histogram: 268/308 (87%) ≤ 2, 20 of 84 Urgent score 0 — computed, not typed |
| E6 | Rule checks + `rationale_summary` per referral | C | PASS | Rules-tested table + coordinator's note, labelled deterministic — now that A2 delivers them |

## F · Run

| ID | Task | Gate | Status | Evidence |
|---|---|---|---|---|
| F1 | Pre-run state | S | PASS | Pre-run readouts: cohort 308, 2 agents, 616 scores, α range, direction; screenshot `13-run.png` |
| F2 | Live lanes, committed-row counter, spine building | S | PASS | Per-agent lanes with their own committed counts; total counts rows in agent.agent_scores |
| F3 | Completion resolves into the cohort graph | S | PASS | Completion offers *See what it cited* → the cohort graph |
| F4 | Copy as telemetry | C | PASS | Copy is telemetry: what each agent reads, how many rows per referral |
| F5 | Day strip — 14 days, intake, runnable vs view-only | C | PARTIAL | Day select labels intake + `view only` per day, and the Overview Intake panel draws the 14-day series. A dedicated day strip was **not** built — recorded, not hidden |

## G · Knowledge graph

| ID | Task | Gate | Status | Evidence |
|---|---|---|---|---|
| G1 | Cohort graph surface, full-bleed, glass panels | S | PASS | `CohortGraph.tsx` full-bleed with glass panels; screenshot `11-graph.png` |
| G2 | Controls — zoom/fit/reset, focus, hover path, legend, layout | S | PASS | zoom/fit/reset, click-to-focus with chain highlight, legend, 4 layouts, 3 sizes |
| G3 | Clusters by evidence type, size by citation count | S | PASS | Clusters coloured by evidence type, placements sized by citation count |
| G4 | Per-patient graph v2; "on record" graph for view-only days | C | PASS | `Provenance.tsx` on-record mode for view-only days; screenshot `26-viewonly.png` |
| G5 | WebGL context-loss guard; SpO₂ glyph fix | D | PASS | WebGL context-loss guard on both canvases; SpO₂ tofu fixed (three.js glyph set) |
| G6 | State that the `inputs` graph is unloaded | C | PASS | `inputs_graph_loaded: false` surfaced — cited nodes carry identity and role, not resolved values |

---

## Standing invariants — any gate may fail a task on these

1. Breaches are of the **165 that have a target**, never of 308. 143 have no target at all.
2. A reading's **age** always travels with the reading.
3. Colour is **never** the only channel. Every category carries a word.
4. Capacity **never** appears to move an individual — it sets alpha and nothing else.
5. The condition code is a random draw. It is **never** styled as a finding.
6. MTS hues **never** enter the triage palette.
7. `--capacity-direction` is **pressure**. ADR-007.
8. Nothing animates across a category boundary.
9. A stale normal reading is an **absence of information**, not reassurance.
10. Never sort on raw `cpc` — CPC 3 outranks CPC 2. Resolve through `bandOf()`.

---

## Review gates — round 1

Three reviewers, three lenses, run against the code and the live API.

### Gate C · clinical safety — 2 VETO, 14 MAJOR, 8 MINOR

| Finding | Status | Evidence |
|---|---|---|
| **VETO** `normal 111–219 mmHg` under every vital — an invented reference range; 111–219 spans stage-2 hypertension, and `news2.py` has no `normal` concept | **FIXED** | `lib/news2.ts` field renamed `zeroBand`; renders "111–219 mmHg scores 0" |
| **VETO** adult NEWS2 shown as acuity for paediatric refusals, under a note saying the system refuses to score them | **FIXED** | `List.tsx` — refused rows read "not applied · adult scale"; reading + age still travel |
| ARIA `role="button"` on rows stripped every cell from the a11y tree, including the reading's age | **FIXED** | row is a row; `.pw-open` is the named control |
| No live regions anywhere — run counter and override results silent | **FIXED** | 3 × `role="status" aria-live` |
| View-only day: dead disabled button, reason only in a `title`, explanation locked inside the overlay it opens | **FIXED** | `.cta-locked` states it inline, reason one click away |
| Service status: colour the only channel, `aria-hidden` dot, in two reserved triage hues | **FIXED** | word travels; hues off the triage set |
| `1 past target` for `RULE-TRIAGE-TURNAROUND`, which fires on a referral with **no target** | **FIXED** | `breachPhrase()` derives the phrase from the rule |
| Override boundary check asked `decision.rankings`, not the order on screen | **FIXED** | `displayedOrder` threaded through |
| Coordinator's note names a capacity score per-person; list didn't say it was template text | **FIXED** | scope + provenance stated beside it |
| Landing carried no synthetic marker — the screen the demo opens on | **FIXED** | `.landing-synth` |
| Unreported GAR rendered as "Green" | **FIXED** | `?? null` → "not reported" |
| `Provenance.tsx` palette was literally `--cat-routine` / `--cat-semi` as hex | **FIXED** | moved to the ink/clay/taupe axis |
| Verdict pills in reserved triage hues on 3 surfaces | **FIXED** | ink register; `--cat-*` now only GAR + band chips |
| Compare shows NEWS2 for two people with no reading age | **OPEN** | ages run 12–871 days; needs each side's age in `cmp-trow` |
| Patient page lacks the attribution caveat the other 3 surfaces carry | **OPEN** | |
| Overview shows `refused` in the capacity column for 0601 — the *urgency* agent refused | **OPEN** | capacity did score it, 0.781 |

### Gate D · data truth — 1 BLOCKER, 7 MAJOR, 7 MINOR

| Finding | Status | Evidence |
|---|---|---|
| **BLOCKER** journey axis anchored on the triage date, header on received date — disagreed on **259 of 308**, max 57 days, and **5 sign flips** where the header said past target and the axis drew none | **FIXED** | `Journey` takes `waitDays`/`targetDays`; adjusted wait excludes suspended time so it cannot be derived from dates |
| "776 checks" counted 2 whole-list rules as 305 verdicts each | **FIXED** | now "166 per-referral checks plus 2 whole-list" |
| Graph's "citations" was edges-minus-hasPlacement — 6 vitals collapse to 1 link, and 471 links are not evidence | **FIXED** | renamed `evidence_links` end to end; panel defines the term |
| "5 rules tested per referral" — no referral has 5 (166 have 3, 139 have 2) | **FIXED** | reads "2–3" |
| Citation forecast 2,464 vs actual 2,446 | **FIXED** | "at most, 8 per referral" |
| Run lane denominator `p.key === 'ranking' ? n : n` — a no-op; two lanes could never reach 100% | **FIXED** | denominators narrow once refusals are known, and say so |
| `capacity_direction` typed as a literal | **FIXED** | read from `/api/health` |
| 8 planted fixtures visible as raw pathway numbers | **FIXED** | `lib/planted.ts` — each named with what it demonstrates and the test that plants it |
| `131 of 305` vs `130 past target` on one screen | **OPEN** | the extra is the turnaround breach, not a CRT breach |
| List bands 86/54 vs Overview 88/55 — List routes refusals out before banding | **OPEN** | both internally correct, unreconciled across surfaces |
| Displayed terms fail to sum at 3 d.p. on 38 of 305 rows | **OPEN** | priority is exact; rounding artefact |
| "of 17" — six bands top out at 3 each, so 18 is reachable; the agent's own docstring contradicts its code | **OPEN — upstream** | not reachable on this data (max temp 35.2) |

**Verified correct and unchanged:** every count and denominator, the NTPF panel against `specialty_mix.yml`, zero removals against 70,022 CSV rows, α-weighting (`α·u + (1−α)·w == priority` on all 305, 0 mismatches), `wait_normalised` as a within-band percentile (0 mismatches), the capacity blend against `calibration.yml` for all 6 specialties, every rule tally, the union reconciliation, the ward panel, staleness, and the NEWS2 distribution.

### Gate S · design — 5 BLOCKER, 12 MAJOR

| Finding | Status | Evidence |
|---|---|---|
| **BLOCKER** `gap:1px` over `--rule` paints EMPTY cells — a 1170×145 grey block across the clinical readings | **FIXED** | 7 fluid grids moved to hairlines-on-children |
| **BLOCKER** Jost loaded from Google Fonts only — no internet, no brand, mid-presentation | **FIXED** | self-hosted; the app now makes **zero** external requests |
| **BLOCKER** at 1280×800 the table was cut by 340px with ~4 rows visible | **FIXED** | rail collapses below 1440; table 1182 in a 1182 viewport, 8 rows |
| **BLOCKER** clay had become the table's body colour — ~5 marks/row, true of 9 rows in 10, carrying 3 different meanings | **FIXED** | cut to 4 uses; only the overflow bar remains in the row |
| **BLOCKER** "past target" clay on the list, triage red on 3 other surfaces | **FIXED** | clay everywhere |
| `align-items: start` leaves ragged panel bottoms | **OPEN** | one line |
| Run overlay header on a different grid to its body (313px offset) | **OPEN** | |
| `.readout` background equals the overlay ground — invisible boxes | **OPEN** | |
| Graph palette contains amber, red-orange and green | **OPEN** | its own comment claims otherwise |
| `--lift-1/2` are drop shadows the kit forbids, and are unused | **OPEN** | delete |
| Overview accent on a 2px sparkline tick while 130 gets an invisible edge | **FIXED** | swapped |
| 289 words of caption prose across 7 `.ov-cite` blocks | **OPEN** | the last notebook on the Overview |
| `--t-micro` (11px) is the workhorse size for data, against its own token comment | **OPEN** | |
| Two 9px labels carrying values | **OPEN** | |

**Regression the gates caught:** the dead-CSS sweep removed `.cat-semiurgent` and `.cat-uncategorised`, which are built by string concatenation and invisible to a grep. Two of five triage swatches had been rendering with no colour. Restored, with a comment saying why they cannot be swept.

---

## Review gates — round 1 closed

All 15 findings left open after the first pass are now fixed, except one that is
not ours:

**`"of 17"` — OPEN, upstream.** `lib/news2.ts` mirrors the agent's six band
tables exactly, and they top out at 3 each, so 18 is reachable. The agent's
`NEWS2_MAX = 17` rests on a docstring claiming *"temperature's top band is 2"*,
which its own code contradicts (`temp <= 35.0 → 3`). Not reachable on this data —
the minimum temperature across 5,200 observations is 35.2 — and the UI shows the
constant the agent normalises against, so changing it here would desync the two.
**For the urgency-agent track to resolve.**

Final state: **50 planned tasks — 49 PASS, 1 PARTIAL (F5, day strip).
42 review findings — 41 fixed, 1 upstream.** demo_path.py 71/71.

---

# Round 2 — the thirteen points

Client feedback of 10 September. Plan at `~/.claude/plans/we-are-setting-up-noble-lighthouse.md`.
Same rule as round 1: **PASS requires evidence** — a `file:line`, a demo-path assertion, or a
screenshot. A claim is not evidence.

## Three corrections carried into this round

| | what I had been saying | what the measurement showed |
|---|---|---|
| 1 | flattening the triage hues off warnings was the fix | it was half a fix. Every attention state was left on a **1.55–1.75:1** hairline, and `.sub.is-over` — the class marking a referral 31× past target — **restated the base class verbatim and did nothing** |
| 2 | older days cannot be scored because evidence is date-blind | **3,963 referral-days, zero contamination.** Not one observation post-dates its own day. What *is* date-blind is **capacity** — all 14 days are served the same 30 Aug ward snapshot — which nobody had been citing, and which makes the Overview's ward panel a false statement on 13 of 14 days |
| 3 | point 8 looked like a stale component | **not stale.** All 30 query keys are scoped to `[hospital, date]`. `runnable` is always the newest day, so the string is accurate and merely ambiguous |

## A · Severity scale — **CLOSED**

| ID | Task | Status | Evidence |
|---|---|---|---|
| A1 | `--sev-1..4` tokens, both grounds | **PASS** | `tokens.css`. First draft was **non-monotonic** (6.27→6.16→5.86→8.90) — the fault it replaces. Re-solved twice more after that. Final light text **5.97 / 7.19 / 8.67 / 11.07**, fill-vs-page **1.09 / 1.36 / 8.67 / 11.07**; dark text **6.56 / 7.03 / 7.43 / 11.05**. Strictly rising on both axes on both grounds, recomputed independently at close |
| A2 | `lib/severity.ts` + `Severity.tsx` primitive | **PASS** | Bands chosen against observed ranges; demo_path §16 proves **every step fires** — wait ratio 35/28/43/39/20 |
| A3 | Wait against target | **PASS** | `sevWaitRatio` in `List.tsx`, `Run.tsx`, `Patient.tsx`. Replaces `.sub.is-over`, which **restated its base class verbatim** and drew nothing |
| A4 | Reading age | **PASS** | `sevReadingAge` in `Vitals.tsx`, `List.tsx`, `Overview.tsx`. Replaces a **1.75:1** dashed underline |
| A5 | NEWS2 sub-scores, monotonic | **PASS** | `sevNews2Sub` in `Vitals.tsx`. Old ladder was 3.56 / 5.99 / 15.37 / **14.70** — the most severe step was the *less* contrasty one |
| A6 | Rule verdicts, six registers unified | **PASS** | `sevBreach` in `Compare`, `Run`, `Overview`, `DecisionRecord`, `List`, `Patient` |
| A7 | Integrity alarms at sev-4 | **PASS** | `SEV_INTEGRITY` in `DecisionRecord.tsx`, `Overview.tsx`. The reconciliation gap had a **1.55:1** left edge as its entire signal |
| A8 | Occupancy and clinic pressure | **PASS** | `sevOccupancy` in `AgentInputs`, `Overview`; `sevBooked` in `Overview` |
| A9 | **`SevLegend` — the scale named on screen** | **PASS** | `Severity.tsx:138`, placed `List.tsx:1142`. Added at close: the scale spanned five axes and 595 marks and was explained only in code comments and in tooltips **26 of 30 chips never passed**. Built from the real chip classes, so legend and table cannot drift. Eyebrow reads *"how far past a line"* — deliberately **not** "severity", which `List.tsx` already uses for the CPC ordering field |

## B · Icons — **CLOSED**

| ID | Task | Status | Evidence |
|---|---|---|---|
| B1 | Adopt `--icon` / `--icon-sm` | **PASS** | were declared in `tokens.css` and used nowhere; now in `app.css` and `list.css` |
| B2 | One stroke per role; fix 12 unset call sites | **PASS** | **20 icon call sites, 0 without `strokeWidth`** |
| B3 | `TriangleAlert` and `Check` to one size each | **PASS** | were 5 sizes / 4 strokes for 6 meanings |

## C · Copy — **CLOSED**

| ID | Task | Status | Evidence |
|---|---|---|---|
| C1 | Remove em-dashes from running copy, keep bare placeholders | **PASS** | **0 in visible copy.** 10 remain, all in code comments; 51 bare `—` placeholders kept, which is a legitimate glyph |
| C2 | Remove the synthetic-data label entirely | **PASS** | client instruction. Only surviving mention is a comment at `Landing.tsx:23` recording that it must not come back. **README feature 1 still claims it appears "in the graph and the UI" — that line is now false and is outside the granted scope** |
| C3 | Remove "attribution, not authentication" | **PASS** | 0 occurrences |
| C4 | Cut box explainers to sources and caveats | **PASS** | |

## D · Before/after — **CLOSED**

| ID | Task | Status | Evidence |
|---|---|---|---|
| D1 | Pre-ranking view on unscored days | **PASS** | `Overview.tsx:402` `<section className="ov-before">`, `List.tsx:498`. The client's framing: see the state, then run and watch it become an order |
| D2 | **Ward and clinic panels carry their true snapshot date** | **PASS** | `Overview.tsx:1179-1190` — reads each ward's own `snapshot`, and says **"mixed snapshots"** rather than guessing when they disagree. **data-truth fix**; demo_path §17 pins why |
| D3 | "Check for new data" wired | **PASS** | `App.tsx:102`. `refreshDays` had existed and **no component had ever called it** |
| D4 | Point 8's wording | **PASS** | `App.tsx:158,238` — selected day and runnable day named separately; non-runnable days marked `· view only` |
| D5 | Run overlay states what changes | **PASS** | |

## E · Layout — **CLOSED**

| ID | Task | Status | Evidence |
|---|---|---|---|
| E1 | Table width above the fixed columns' sum | **PASS** | **the cause of client point 13.** Fixed columns summed 1154 against a `min-width: 1120`, so Referral got **0px** between 1440 and 1714. Replaced with a computed `tableMin()`; measured live at 1440×900 the columns were `[76,140,0,200,240,180,144,132,42]` |
| E2 | Compact rule for `.pw-line` | **PASS** | `list.css:802`. 8 planted rows ran 47px in a 36px row |
| E3 | `.rulez` must not silently clip a rule | **PASS** | `list.css:546,796` |
| E4 | Intake chart overflow | **PASS** | was 3.8px per column at 60 days |
| E5 | Ward table "Also backs" must wrap | **PASS** | inherited `nowrap` via `.c-dim`; would have pushed the table past 2,500px at 20 specialties |
| E6 | Bound the rule board and sparkline | **PASS** | 20 rules would have given two fixed-size siblings ~900px of blank paper |
| E7 | Override log: cap, page, sticky header | **PASS** | `DecisionRecord.tsx:343` `ovrRows.slice(0, ovrShown)`. 200 rows was ≈11,000px unlabelled |

## F · Brand — **CLOSED**

| ID | Task | Status | Evidence |
|---|---|---|---|
| F1 | Full-width rail above the kit's 13px cap floor | **PASS** | `App.tsx:173-190`. Was **8.7px** cap, 33% under the kit's own floor, stems resampling to **0.39 CSS px** and antialiasing to ~39% alpha — contrast collapsed 17.2:1 → ~3.5:1. That was the illegibility, and it was resampling, not colour. Now **15.74px** |
| F2 | Collapsed rail uses the mark SVG | **PASS** | `App.tsx:187-190` `<picture>` swaps to the vector mark below 1440. The lockup was 68px wide in a 48px box, hanging 10px past each edge and lapping the rail border. Now 17.83px in a 47px box |

## G · Correctness — **CLOSED**

| ID | Task | Status | Evidence |
|---|---|---|---|
| G1 | Tied priority shows what separates | **PASS** | `List.tsx:1413,1695`. **12 adjacent pairs** printed identical 3dp values and then said "decides it"; `is-precise` prints six decimals when they tie at display precision |
| G2 | "What separates this from the one above" on the page | **PASS** | client point 12 |
| G3 | KG context-lost: deps, latch, `isConnected`, z-index | **PASS** | `CohortGraph.tsx:346-357`, `cohortgraph.css:22`. `layout` was missing from the effect deps, so switching layout remounted the canvas and left the listener bound to the **detached** element; r3f then called `forceContextLoss()` on it 500ms later. A one-way latch too — Redraw never cleared `lost` |
| G4 | An untested rule must not render "holds" | **PASS** | `Overview.tsx:917-932`. Was filtered out of the board entirely while `DecisionRecord` rendered it as "not tested" — **two audit surfaces disagreeing about whether a rule exists** |
| G5 | Whole-list verdicts keyed by rule ID | **PASS** | `Overview.tsx:82-88`. A third whole-list rule would have silently taken `RULE-TIEBREAK`'s verdict |

## Closing batch — the review gates' own findings

| what | evidence |
|---|---|
| **The fifth ramp inversion** | Step 4 carried `box-shadow: inset 0 0 0 2px var(--sev-4-fg)` — a ring in the step's **foreground** colour, which on light is `--paper`. It added no area; it ate about a quarter of the block and replaced it with page. Mean luminance at equal glyph coverage: sev-3 **4.51**, sev-4 **2.35–2.64** across all three geometries it is used in. **The most severe step was 1.7–1.9× less present than the step below it.** Light-ground only, which is how it survived four reviews. Replaced with `outline: 2px solid var(--sev-4-bg)` — the fill's own colour grown outward, like `.wb-over`, so nothing reflows and the three surfaces that override `.sev` padding cannot erase it |
| **The breakpoint was two pixels early, not three** | I derived chrome as 303px. It is **302**: `box-sizing: border-box` keeps the rail's `border-right` *inside* the 236px track. `NINE_COL_PX` 1714 → **1716**, measured live at 1714/1715/1716 and confirmed by exhaustive scan to 2600. At 1714–1715 the nine-column table was 1414px inside a 1412/1413px box |
| **Rule statements left the tooltip** | They lived only in `title` on non-focusable spans, so keyboard and touch users never got them. The row chip's rule ID and the `+N more` count are now buttons that open the expander; the **sort-key ladder** — the surface whose whole job is explaining the order — prints each statement on screen. Step 3 cites two rules and only the first was ever even on the tooltip |
| **`SevBar` named its step to nobody** | Its `aria-label` was always factual ("92.4% occupied, over the 85% line") and never said which step that was, so for a screen-reader user the scale did not exist on bars at all |
| **The graph claimed totality** | Headline read "150 placements · 750 evidence links · 465 nodes" under "What the coordinator cited". True figures at `?limit=0` are **305 / 1,386 / 931**. Now reads "150 of 305" and says the counts follow the size control |
| **Two medians for one hospital-day** | Overview took the upper-middle element, List averaged the two middle values. They disagreed on 2026-08-21 (142 vs 141) and 2026-08-22 (143 vs 142), both n=286. One convention now, in `lib/stats.ts` |
| **`SAFE_OCCUPANCY` was declared three times** | The drawn 85% line and the band boundary under it could drift apart. Exported once from `lib/severity.ts:67`, cited to Bagust, Place & Posnett, BMJ 1999;319:155-8 |
| **`useNarrow` seeded from the wrong measurement** | `window.innerWidth` includes a classic scrollbar; `matchMedia` excludes it. On Windows and Linux that was one frame of nine columns at a seven-column width |
| **"Recent" for an 89-day-old reading** | A reassurance word directly below a panel arguing that a stale normal reading is an *absence* of information. Now states the age. Banding untouched — 52 of 308 rows sit in that 31–89 day window |
| **The landing claimed a population** | "308 people are waiting" over a documentary photograph of a real waiting room. The screen can see a list, not a population. Now "308 referrals are on this list". No disclaimer added, and the synthetic-data label did not come back |

## Three of my own faults, caught by the gates

| | what I published | what it actually was |
|---|---|---|
| 1 | worried `--sev-3` collided with `--cat-urgent` under protanopia | that pair is the **safest** (ΔE 15.1). The real collision was `--cat-routine` vs `--sev-3` at **ΔE 3.1**, below the just-noticeable difference, co-occurring in the same Overview table row |
| 2 | a contrast table measuring fills against `--surface` while the comment said "the page" | self-evidently wrong, since steps 3 and 4 use `--paper` as their foreground. Dark `--sev-2` published 6.90, actually **6.47** — non-monotonic |
| 3 | a `SevBar` ramp where step 0 fell through to `--text-3` | 4.30:1 against fills of **1.00** and 1.26 — going from no-severity to step 1 made the bar *less* visible, and step 1 was byte-indistinguishable from its own track |

## Verification

- **demo_path §16** — every severity step fires on real data; NEWS2 total is still too degenerate
  to grade on (148 of 308 tie at 0)
- **demo_path §17** — capacity evidence is date-blind, so it may never be labelled as the
  selected day's. Pins the fact that makes D2 necessary
- **81 passed, 0 failed** (was 71)
- Zero hex literals and zero raw `rgba()` across all eight surface CSS files, comment-stripped
  with a real parser rather than line-grep
- All 21 real `box-shadow` declarations `inset`; no gradient, glow or drop shadow anywhere
- `var(--cat-*)` confined to exactly five band-swatch rules in `app.css` — including
  `.cat-semiurgent` and `.cat-uncategorised`, which are built by **string concatenation** at
  `List.tsx:755` and `Patient.tsx:44` and are invisible to grep. Both traced and confirmed to land

## Known and deliberately not fixed

- **A latent flat step on the dark ground.** `--sev-2-edge` resolves to exactly `--clay`, so
  `SevBar` steps 1 and 2 are byte-identical there. It cannot currently reach a screen — every
  `SevBar` call site is on a light surface — and closing it needs a token measuring between
  1.97 and 3.09 on ink, which the frozen palette does not contain
- **Two exact-fit widths.** 1440 and 1716 fit with **zero** spare. On a platform with classic
  space-taking scrollbars, `.lst-vp`'s own vertical scrollbar eats ~15px and both would go
  short. No constant can model this; it is recorded at `List.tsx:141-143`
- **`.wait-x` left at `--t-micro`.** It is a value, but raising it grows the comfortable row
  56px → 57px, and the wait *bar* directly above already carries the graded channel
- **`.ev-rules li`'s 78px column at ≤1100px.** Pre-existing near-overlap: the "breached" chip
  is 87.5px and clears the rule ID by 2.5px. Raising its type would overlap by 1.6px
- **`Mark.tsx:18-19`** holds 2 hex literals as SVG fills, outside the eight audited stylesheets

## Review gates — round 2, and the adjudication

Three gates (data truth, clinical safety with a veto, design), then an adjudicator whose standing
instruction was to **assume a seventh ramp inversion until its own arithmetic said otherwise**.

| | finding | state |
|---|---|---|
| **VETO** | `<Limits>` was passed no refusal flag, so a specialty-0601 child's page drew an `--ink` bar on the adult NEWS2 histogram and the sentence **"this referral scores 4"**, one screen below six struck-through chips reading "refused". The round-1 veto verbatim, in a component the fix never reached | closed at 3 sites |
| **VETO-class** | Sweeping for it found a **third** escape: the evidence expander, reachable from every tab, receiving no refusal at all. And a **fourth**: the NEWS2 *sort key* ranked refused rows on the score the product refuses to display — ordering is a channel | closed; both now derive from the SPECIALTY at the point of use, so the per-tab grouping is no longer load-bearing. 18 render sites and 6 orderings proven gated at runtime on a day `/api/decision` 404s |
| **HIGH** | The past-target sentence named the **wrong** referral on four patient pages: a comparison against a string `tier()` can never return, so it always resolved backwards. The breached patient has the *lower* priority in both boundary pairs, so the side was never inferable from a score | closed |
| **HIGH** | Every patient page showed a ward holding more people than beds. `/api/context` carries one specialty's allocation where `/api/operations` carries the ward total. Reading ops would **not** have fixed it — W-9001-02 is 91 occupied against an establishment of 90 — only the census (occupied+free) reconciles | closed |
| **HIGH** | The clinic evidence line printed five-session totals beside one session's pressure: **"15 free slots at a pressure of 1.000"** | closed |
| **HIGH** | **THE SIXTH INVERSION.** `.sevbar-m` was `--text` at 0.7 painted over the fill, so the threshold marker fell **5.54 / 4.42 / 3.22 / 2.00 / 1.50 / 1.26** as severity rose. The 85% safe line and the cohort-median line vanished on exactly the wards and patients past them — 4 of 7 wards, 48 of 308 pages, under the 3:1 floor at steps 3-4 | closed: **5.07 / 5.86 / 8.67 / 11.07** light, **5.86 / 5.86 / 7.43 / 11.05** dark |
| **MUST-FIX** | **The threshold line was absent, not faint.** `left: 100%` inside a box that clips at 100%, with the `translateX(-1px)` applied only on the fill side. That is every referral still *inside* its target — 35 of the 165 — including **`PW-DEMO-02` at 88 of 91**, the planted fixture whose stated purpose is to demonstrate the 13-week timeframe. Neither gate saw it: one measured the marker's colour against six grounds correctly, the other confirmed `of` was the right number. Nobody asked what happens when that number is 1 | closed |
| **MUST-FIX** | The patient page showed a ward snapshot **six days in the future** and clinic sessions four days ahead, unlabelled, while its sibling surface flags exactly this at `SEV_INTEGRITY` | closed, borrowing Overview's sentence word for word |

**No seventh inversion.** Every channel recomputed from raw tokens on both grounds — chip fill, chip
text, SevBar fill, the threshold marker, and the Journey axis, which no table had ever measured.

## Five wrong published figures, all from one habit

Every one came from copying a number instead of recomputing it, or from naming no ground.

| published | actual | what it really was |
|---|---|---|
| chip step 1 vs track `1.78` | **1.00** | the chip's *edge*, not its fill — step 1 was indistinguishable from its own track |
| chip step 2 vs track `1.90` | **1.26** | a figure a neighbouring file had already withdrawn |
| overflow vs track `3.41` | **4.30** | measured against the step's own fill, not the track it sits on |
| dark marker step 0 `9.19` | **9.13** | against no ground that exists |
| "71 of the 130 at step 2" | **43** | 71 is steps 1 **and** 2 |

Every prose figure now names its ground.

## The browser walk — three defects no static check could find

Nothing in this round had been looked at; every agent reported "no browser, nothing was seen".

- **The page scrolled sideways 189px on the screen the demo opens on**, caused by a fix from this
  round. `.sev-sr`, added so a chip names its step to a screen reader, is `position: absolute` and
  `.sev` established no containing block — so its containing block was the viewport. Its
  `width: 1px; overflow: hidden` clips its *text*; it never clipped its *position*. The comment
  above it claimed it "cannot push a scrollbar"
- **Point 13 was not closed.** In compact, `.cell` and `.ovbadge` are siblings with no flex parent,
  so neither could shrink: a 208px badge started 290px into a 304px column and painted **194px**
  over the wait bar. The compact rule written for this was scoped to `.c-ref .cell`, and the badge
  is not inside `.cell`, so it had never applied
- **A regression of mine**, caught in the same pass: `overflow: visible` on `.sub.is-split` freed
  step 4's outline and let the row spill 44px sideways. The clip is restored and the outline is
  given padding to be drawn into

**Verified in a browser at 1280 / 1440 / 1715 / 1716 / 1920, both densities:** the breakpoint turns
exactly where computed (1715 → 7 columns, 1716 → 9, inner 1414 = scrollWidth 1414, **zero spare, no
scrollbar**); **no column is starved** at any width, which was the original point 13; zero visible
cell spills in either density; `PW-DEMO-02` draws its 91-day line; and the legend keys the quiet
mark each surface actually draws.

## Still needs the client

- **Clearing `agent.*`** — 43+ stacked decisions. Classifier-blocked
- **`node_modules` in the local commit history**, before anything is ever pushed
- **README feature 1** — claims the synthetic label appears "in the graph and the UI". The UI
  half was removed on instruction, so that line is now false. Outside the granted scope
  (`orchestrator/` and `web/` only), so it has been flagged rather than edited
