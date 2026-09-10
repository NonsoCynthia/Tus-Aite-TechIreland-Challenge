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
