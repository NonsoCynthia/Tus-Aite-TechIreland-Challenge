# Product Definition

## Initial Concept

An explainable, agent-based triage support tool for Irish hospital patient flow, built for the
TechIreland National AI Challenge 2026 (28 August – 14 September 2026, regional presentations
14 September, National AI Meet in Galway 24 September).

Source of truth for the concept: `.context/attachments/a2kOEY/Explainable_Agent_Triage_Proposal-2.docx.txt`.

A multi-agent system turns fragmented referral, bed flow, and urgency data into a ranked,
explainable, auditable prioritisation — one a clinician can trust, interrogate, and override,
without the reasoning ever being a black box.

---

## Vision

Make an existing but fragmented clinical prioritisation process explainable and consistent, so that
every ranked position traces back through a knowledge graph to the specific evidence that produced it.

## Problem Statement

Ireland's hospital waiting lists reached a record 1,008,600 people at the end of May 2026, with
669,506 waiting for a first outpatient appointment (up 14% year on year). The IHCA ties the growth
to elective cancellations driven by ED overcrowding — roughly 24,500 appointments and operations
cancelled in January 2026 alone, on top of 286,500+ across 2025.

Underneath the capacity numbers sits a **decision quality problem**: who gets seen next, on what
basis, and how that reasoning is recorded is largely opaque to patients, clinicians, and management.

This project does not invent a new prioritisation scheme. Ireland already has formal ones — MTS,
ICTS, NEWS2, EMEWS, and the NTPF's Clinical Prioritisation Category with its Clinically Recommended
Timeframes. The problem is that these are fragmented across systems and their application is not
auditable. We make the existing scheme explainable and consistent.

## Target Users

**Primary user (the human in the loop):** the clinician who accepts, reorders, or overrides a ranking.
The system is decision *support*; the clinician is the decision *maker*.

**Primary buyer:** HSE Regional Executive Officers across the six HSE Health Regions, formally
accountable for reducing regional variation under the Waiting Time Action Plan 2026, and able to
draw on AI for Care Operations-pillar funding.

**Secondary buyers:** National Treatment Purchase Fund (owns the CPC/CRT rules this system respects
and could help audit); private hospital groups mid-transition to shared EHR platforms (Blackrock
Health, Mater Private, Beacon, Bon Secours, UPMC Ireland); the National Ambulance Service (post-
challenge 999/112 extension); health tech vendors bidding into the National EHR procurement who need
a reference pattern for explainable human-in-the-loop agent architectures. Health insurers (VHI,
Laya, Irish Life Health) are a weaker, longer-horizon possibility and are explicitly *not* a near-term
buying case.

## Success Criteria

Success is **not** the agent deciding. It is a measurably faster, more consistent, and fully
explainable shortlist that a human still signs off on.

1. A ranked list is produced from a simulated referral and bed-status feed.
2. Every ranked patient carries a per-patient rationale naming which urgency signals and which
   capacity constraints drove the position.
3. Every rationale is reconstructible by walking the graph backwards from the ranked position — the
   `cites` relationship *is* the audit trail.
4. A clinician can accept, reorder, or override any ranking, and every override is logged back into
   the graph.
5. Rankings are validated against CPC/CRT rules: a ranking that puts a semi-urgent referral past its
   13-week window behind an urgent one still inside its 28-day window is a detectable rule violation.
6. No urgency score is ever displayed without its contributing evidence attached.

## Core Features

1. **Synthetic data generation** — patient and referral generator calibrated to HIPE specialty mix,
   age/sex distribution, and length-of-stay statistics, plus NTPF list structure and volume, so the
   case mix looks Irish though no individual record is real.
2. **Bed occupancy simulation** — discrete-event queue (SimPy) calibrated to published HSE/INMO
   trolley and occupancy figures, so the capacity agent is stress-tested against realistic contention.
3. **Knowledge graph** — RDF/OWL store that doubles as the audit log, not merely a data store.
4. **Urgency agent** — MTS and NEWS2 scoring logic, reading the graph via SPARQL and writing scored
   edges back.
5. **Capacity agent** — bed and resource constraint reasoning against the simulated occupancy model,
   also writing scored edges back.
6. **Coordinating agent** — merges both agents' outputs into a ranked list via SPARQL over both sets
   of triples, materialising `Decision` nodes and `cites` relationships.
7. **Clinician interface** — ranked list view with accept, reorder, and override controls; overrides
   written back into the graph, closing the loop.
8. **Compliance validation** — automated CPC/CRT rule checks across synthetic batches, plus documented
   human-in-the-loop boundary.

## Non-Goals

Hard implementation boundary — the coordinating agent may **only rank and explain**:

- It cannot admit, discharge, schedule, or auto-action anything.
- No diagnosis. Any diagnosis-support extension is explicitly non-diagnostic output requiring
  clinician validation before use, and is out of scope for the challenge build.
- No real patient data. No PII. Synthetic and de-identified public data only.
- No ambulance/NAS 999-112 dispatch prioritisation — named as a post-challenge extension only.
- No integration with live HSE systems, Shared Care Record, or National EHR — the graph is designed
  to make that plausible later, not to do it now.
- No production deployment, multi-tenancy, or authentication hardening.

## Constraints

- **Time:** the prototype must be demo-ready in one week (Day 1 ≈ 28 August 2026), leaving week two
  for judge/mentor feedback, refinement, and rehearsal before the 14 September regional presentation.
- **Team:** at most nine people across nine roles (team lead/clinical liaison, knowledge graph
  engineer, data/simulation engineer, urgency agent developer, capacity agent developer, coordinating
  agent developer, frontend developer, responsible AI/compliance lead, pitch/business lead).
- **Sequencing:** agent work on days 3–4 depends on schema and seed data from days 1–2, so those
  earlier steps must not slip.
- **Compliance posture:** human oversight and EU AI Act alignment are central, per Ireland's AI for
  Care strategy 2026–2030 and forthcoming HIQA guidance. The compliance lead reviews each agent's
  output against CPC/CRT rules as soon as it exists, so Day 6 validation is a final check, not a first one.
- **Data availability:** no single Irish dataset links referrals, urgency, and live bed capacity.
  That gap is why simulation is necessary; real datasets keep the simulation grounded.

## Grounding Data Sources

| Source | Role |
|---|---|
| NTPF Open Data (data.gov.ie, ntpf.ie) | Waiting list volumes by hospital, specialty, time band — calibrates list size and specialty mix |
| HIPE (Healthcare Pricing Office) | ~1.7M discharges/yr, ICD-10-AM/ACHI/ACS coded — diagnosis mix, admission type, length of stay |
| HSE/INMO daily trolley watch | Calibrates the synthetic bed occupancy time series |
| CSO Open Data health statistics | County and age-level context |
| MIMIC-IV-ED | De-identified US ED vitals, chief complaint, triage acuity — urgency feature structure |
| Synthea | Synthetic longitudinal encounters, conditions, vitals, procedures |
| MTS / NEWS2 rubrics | Starting ontology for urgency scoring |
| NTPF CPC / CRT timeframes | Validation target: urgent ≤28 days, semi-urgent ≤13 weeks, same-category ordered oldest-referral-first |

## Regulatory Landscape

**Emergency / walk-in triage:** the National Emergency Medicine Programme mandates MTS for all adult
ED patients (reinforced by the HIQA Tallaght Report). ICTS is the paediatric equivalent. EMEWS
interfaces with MTS and aligns with NEWS2. The National ED Triage Quality Improvement Framework
2025–2027 aims specifically at restoring triage to prioritising relative clinical urgency.

**Scheduled / elective care:** the National Outpatient Waiting List Management Protocol and the
radiology equivalent define the CPC. Urgent → booked within a CRT of ≤28 days; semi-urgent → ≤13 weeks;
same-category patients ordered oldest referral first. The National Waiting List Management Policy (2014)
is the standardised HSE approach for inpatient, day case, and planned procedure lists.

**Ambulance dispatch (extension only):** NAS NEOC uses AMPDS via ProQA under PHECC's EMS Priority
Dispatch Standard, sorting calls into Echo, Delta, Charlie, Bravo, Alpha, Omega — with dispatchers
retaining discretion to override the system's assigned priority. That override provision is a useful
precedent for this project's own human-in-the-loop design.

## Why This Is Agent-Shaped

**Structurally:** clinical urgency scoring (risk stratification) and bed/capacity reasoning (operations
research style resource allocation) are genuinely different problem types that do not collapse well
into one model. They need separate specialist agents whose outputs a coordinator reconciles and ranks.

**Institutionally:** the HSE's own AI governance demands this shape. AI for Care requires a
human-in-the-loop approach that enables rather than replaces clinicians, and a decomposed agent
architecture is what makes a full audit trail — which agent flagged what and why — possible. A single
end-to-end model cannot produce that traceability.

## Post-Challenge Opportunity

The HSE is actively standing up an AI Implementation Framework, a National Shared Care Record, and a
National EHR (vendor shortlisting completed Q1 2026) that a prioritisation tool could plug into as a
regional pilot. The stated extensions — NAS call prioritisation and a diagnosis support agent — map
onto AI for Care's Clinical Care and Operations pillars.
