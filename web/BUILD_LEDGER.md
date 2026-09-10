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
