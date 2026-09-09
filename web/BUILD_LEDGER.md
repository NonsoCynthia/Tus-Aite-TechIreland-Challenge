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

## B · Design system

| ID | Task | Gate | Status | Evidence |
|---|---|---|---|---|
| B1 | Token rewrite — full-bleed grid, density, elevation by role, icons | S | TODO | |
| B2 | App shell — left rail, top bar, Run CTA, run pill | S | TODO | |
| B3 | Brand lockup asset; `lockup-white`; descriptor behind a hairline | S | TODO | |
| B4 | Glass recipe scoped to five uses, never behind a number | C | TODO | |
| B5 | Motion vocabulary; nothing animates across a category boundary | C | TODO | |
| B6 | Synthetic-data label (`README.md:36`) | C | TODO | |

## C · Overview → operational dashboard

| ID | Task | Gate | Status | Evidence |
|---|---|---|---|---|
| C1 | Header band as instrument readouts | S | TODO | |
| C2 | By specialty, real NTPF names | D | TODO | |
| C3 | Against the national NTPF picture | D | TODO | |
| C4 | Intake over 14 days; zero removals | D | TODO | |
| C5 | Clinic capacity — slots booked vs total | D | TODO | |
| C6 | Ward pressure v2 — free, DTOC, surge, specialty | D | TODO | |
| C7 | Live rule board, `RULE-TRIAGE-TURNAROUND` surfaced | C | TODO | |
| C8 | Staleness as an instrument | C | TODO | |

## D · The list

| ID | Task | Gate | Status | Evidence |
|---|---|---|---|---|
| D1 | Full-width table, sticky header, sort, filter, density | S | TODO | |
| D2 | Row anatomy v2 — spine, specialty, ratio, rule ID, override badge | C | TODO | |
| D3 | Inline evidence expander (`README.md:117`, NFR5) | C | TODO | |
| D4 | Reconciliation ledger — four buckets, never summed | C | TODO | |
| D5 | Override v2 — read back, badge, row moves, system position kept | C | TODO | |

## E · Patient

| ID | Task | Gate | Status | Evidence |
|---|---|---|---|---|
| E1 | Re-order the page | S | TODO | |
| E2 | Vitals as NEWS2 instrument cards | C | TODO | |
| E3 | "What informed the agents" — urgency and capacity lanes | C | TODO | |
| E4 | Journey v2 | S | TODO | |
| E5 | Instrument-limits panel; MTS in a neutral register | C | TODO | |
| E6 | Rule checks + `rationale_summary` per referral | C | TODO | |

## F · Run

| ID | Task | Gate | Status | Evidence |
|---|---|---|---|---|
| F1 | Pre-run state | S | TODO | |
| F2 | Live lanes, committed-row counter, spine building | S | TODO | |
| F3 | Completion resolves into the cohort graph | S | TODO | |
| F4 | Copy as telemetry | C | TODO | |
| F5 | Day strip — 14 days, intake, runnable vs view-only | C | TODO | |

## G · Knowledge graph

| ID | Task | Gate | Status | Evidence |
|---|---|---|---|---|
| G1 | Cohort graph surface, full-bleed, glass panels | S | TODO | |
| G2 | Controls — zoom/fit/reset, focus, hover path, legend, layout | S | TODO | |
| G3 | Clusters by evidence type, size by citation count | S | TODO | |
| G4 | Per-patient graph v2; "on record" graph for view-only days | C | TODO | |
| G5 | WebGL context-loss guard; SpO₂ glyph fix | D | TODO | |
| G6 | State that the `inputs` graph is unloaded | C | TODO | |

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
