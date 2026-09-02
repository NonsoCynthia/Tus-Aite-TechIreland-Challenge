# Hospital Referral Prioritisation Dataset

A synthetic dataset for the Explainable Agent-Based Triage Support Tool.
TechIreland National AI Challenge 2026.

---

## Contents

1. [What this is](#1-what-this-is)
2. [Words used in this document](#2-words-used-in-this-document)
3. [What informs it](#3-what-informs-it)
4. [What is copied and what is invented](#4-what-is-copied-and-what-is-invented)
5. [The hospitals](#5-the-hospitals)
6. [How the tables fit together](#6-how-the-tables-fit-together)
7. [The tables the data contains](#7-the-tables-the-data-contains)
8. [The tables the system writes](#8-the-tables-the-system-writes)
9. [Following one patient through](#9-following-one-patient-through)
10. [Four things worth understanding](#10-four-things-worth-understanding)
11. [What is deliberately not here](#11-what-is-deliberately-not-here)
12. [Summary of tables](#12-summary-of-tables)

---

## 1. What this is

This is a made-up dataset that behaves like a real Irish hospital waiting list.

No person in it is real. No hospital in it is real. But the **shape** of the data is real: the column names, the codes, the date formats and the rules all come from the actual system Irish public hospitals use.

The dataset covers four fictitious public hospitals and two fictitious private hospitals over a simulated period, and it exists to answer one question: **among patients a clinician has already marked as equally urgent, who should be seen next, and why?**

It contains 17 tables that get loaded into a database, 7 more that the system writes as it runs, and one held-out file used only for scoring.

---

## 2. Words used in this document

Read this once and the rest will make sense. Everything here is either an Irish healthcare term or an abbreviation used in the tables.

### Organisations

| Term | Full name | What it is |
|---|---|---|
| **HSE** | Health Service Executive | Runs Ireland's public health service. |
| **NTPF** | National Treatment Purchase Fund | Collects and publishes the national waiting list figures, sets the rules hospitals follow, and buys treatment from private hospitals when public capacity runs out. |
| **ESRI** | Economic and Social Research Institute | Irish research institute. We use its published hospital capacity figures. |
| **INMO** | Irish Nurses and Midwives Organisation | Publishes a daily count of patients waiting on trolleys. |

### The waiting list

| Term | Full name | What it means |
|---|---|---|
| **MDS** | Minimum Data Set | The file specification hospitals must follow when sending their waiting list to the NTPF. Our main source. See section 3.1. |
| **HIPE** | Hospital In-Patient Enquiry | Ireland's national hospital activity database. It gives us the numbering system used for hospitals and specialties, so "HIPE code" just means the official code number. |
| **OPD** | Outpatient Department | A hospital clinic you attend without being admitted. |
| **Referral** | | A letter, usually from a GP, asking a hospital to see a patient. Every row on a waiting list is a referral. |
| **Triage** | | A clinician reading a referral and deciding how urgent it is. |
| **CPC** | Clinical Prioritisation Category | The urgency a clinician assigns at triage: Urgent, Semi-Urgent or Routine. |
| **CRT** | Clinically Recommended Timeframe | The maximum time a patient in a given category should wait. Urgent is 28 days, Semi-Urgent is 91 days. |
| **DNA** | Did Not Attend | The patient missed their appointment. |
| **Suspension** | | A period when the patient's waiting clock is paused, because their treatment is being provided elsewhere. See section 10.4. |

### Identifying people

| Term | Full name | What it means |
|---|---|---|
| **MRN** | Medical Record Number | The number a hospital gives its own patients. Only unique inside that one hospital. |
| **IHI** | Individual Health Identifier | A national number for a person, the same at every hospital. Often missing. See section 10.2. |
| **PPSN** | Personal Public Service Number | Ireland's national ID number. Present in the real specification, not used here. |

### Clinical observations and scoring

| Term | Full name | What it means |
|---|---|---|
| **Observations** | | The umbrella term for everything recorded at a patient's bedside: measured vitals, reported symptoms, and clinical scores. Nurses call a set of them "obs". |
| **Vitals** | Vital signs | The measured ones: heart rate, blood pressure, breathing rate, temperature, oxygen. Objective. |
| **Symptoms** | | What the patient reports: pain, nausea, what they say is wrong. Subjective. Clinicians keep these separate from vitals. |
| **NEWS2** | National Early Warning Score, version 2 | A number from 0 upward, worked out from a patient's vital signs. Higher means more physically unwell right now. |
| **MTS** | Manchester Triage System | The colour-coded urgency scale used for adults in Irish emergency departments: red, orange, yellow, green, blue. |
| **ICTS** | Irish Children's Triage System | The children's version of the above. |
| **AVPU** | Alert, Voice, Pain, Unresponsive | A four-level check of how conscious a patient is. `A` is fully awake, `U` is unresponsive. |
| **SpO2** | Oxygen saturation | How much oxygen is in the blood, as a percentage. |
| **ICD-10-AM** | International Classification of Diseases, 10th revision, Australian Modification | The coding system Irish hospitals use to record diagnoses. `K83.1` means blocked bile duct. |
| **SNOMED CT** | Systematized Nomenclature of Medicine, Clinical Terms | A different, more detailed clinical coding system. Included for future compatibility. |
| **FHIR** | Fast Healthcare Interoperability Resources | The international standard for exchanging health data between systems. Pronounced "fire". Its `Observation` record holds exactly what our `observations` table holds. |

### Beds and capacity

| Term | What it means |
|---|---|
| **Ward** | A section of a hospital with beds in it. |
| **Outlier** | A patient placed in a ward that belongs to a different specialty, because their own ward was full. |
| **Surge capacity** | Extra beds opened somewhere unusual because the hospital is overwhelmed. Opening them usually means cancelling planned operations. |
| **Delayed transfer of care** | A patient who is medically ready to go home but is still occupying a bed, because their home care or nursing home place is not ready. |
| **GAR** | Green, Amber, Red. The HSE's traffic-light rating of how bad the pressure is at a hospital right now. |
| **Insourcing** | Treating a public patient in the public hospital, but outside normal hours. |
| **Outsourcing** | Paying a private hospital to treat a public patient. |

---

## 3. What informs it

### 3.1 The main source

Almost everything about the referral side of this dataset comes from one document:

> **Outpatient Waiting List Minimum Data Set, Version 2.6**
> National Treatment Purchase Fund
> https://www.ntpf.ie/app/uploads/2025/04/OP-MDS-2022_v2.6.pdf

This is the file specification every Irish public hospital follows. Once a week, each hospital produces a spreadsheet of its outpatient waiting list and sends it to the NTPF over a secure connection. The document defines exactly 74 fields that every record must contain, in a fixed order, along with fourteen lists of permitted codes.

We use it three ways:

1. **Column names.** Our referral table uses the real field names, not names we made up. `referral_received_date`, not `date_received`.
2. **Code values.** Specialties, priorities, referral sources, cancellation reasons and removal reasons are all real codes copied from the document.
3. **Rules.** The document says which fields are compulsory, which can be left blank, and when. We follow those rules, including the awkward ones.

### 3.2 What we learned from reading it

**The waiting list does record priority.** Field 64 holds a Clinical Prioritisation Category, assigned by a clinician at triage: Urgent, Semi-Urgent or Routine. That system works and we do not second-guess it.

**What the record cannot do is separate patients inside a category.**

Picture one hospital's urgent surgical list. Two hundred people, every one of them marked Urgent. The record tells you they are all urgent. It does not tell you which of the two hundred is the most urgent, and it has no way to, because of this: the specification has 74 fields and **not one of them says what is wrong with the patient.** No diagnosis. No condition code. No symptoms. No observations. The only clinical content on a national waiting list record is the specialty the patient was sent to, plus that one urgency number.

So inside a category there is nothing left to reason with except how long someone has waited. The protocol's own tie-break is oldest referral first, which is a fairness rule, not a clinical one.

That gives four linked problems:

1. Triage assigns a category. **This part works.**
2. Inside a category, the only thing left to order by is waiting time.
3. There is nothing better to build one from, because the record holds no clinical detail.
4. Separately, nothing checks the resulting order against real bed and clinic availability.

**This is what the dataset is built to address.** Not to assign priority, which triage already does, but to order patients *within* the priority a clinician set, using evidence the national record never captured, and to make that ordering explainable.

It follows that the system may **never** move a patient across a category boundary. An urgent referral outranks a semi-urgent one, always, whatever any score says. That constraint is written into the rules as `RULE-ORDER` (section 7.24).

### 3.3 The other sources

| Source | What we take from it | Link |
|---|---|---|
| NTPF Open Data | How many people wait, in which specialties, for how long. Used to size our lists realistically. | https://www.ntpf.ie/waiting-list-data/open-data/ |
| HSE Urgent and Emergency Care Report | The vocabulary and rhythm of bed reporting: surge capacity, delayed transfers, three counts a day. | https://www2.hse.ie/services/urgent-emergency-care-report/ |
| ESRI capacity projections (report RS213) | Bed occupancy rates and average length of stay. Used to make our bed simulation move realistically. | https://www.esri.ie/system/files/publications/RS213.pdf |
| MIMIC-IV-ED Demo (100 patients, open licence) | The real relationship between a patient's vital signs and the urgency a nurse assigns them. | https://physionet.org/content/mimic-iv-ed-demo/2.2/ |
| HIPE published data | Diagnosis mix and age distribution by specialty. | https://data.ehealthireland.ie/group/about/hpo-hipe |

None of these require an account, an application, or a waiting period.

---

## 4. What is copied and what is invented

This matters, and we state it openly.

```
┌─────────────────────────────────────────────────────────────┐
│  COPIED FROM THE REAL SYSTEM                                │
│                                                             │
│  Referral records, specialties, priorities, triage          │
│  categories, cancellation and removal reasons,              │
│  suspensions, geography codes, date formats                 │
│                                                             │
│  Source: NTPF Outpatient Minimum Data Set v2.6              │
└─────────────────────────────────────────────────────────────┘
                            +
┌─────────────────────────────────────────────────────────────┐
│  INVENTED BY US, INFORMED BY REAL SOURCES                   │
│                                                             │
│  Conditions and vital signs                                 │
│    → because the national dataset holds none                │
│    → shaped using MIMIC-IV-ED and HIPE                      │
│                                                             │
│  Wards, beds, clinic slots                                  │
│    → because no Irish file publishes this                   │
│    → named using HSE reporting vocabulary                   │
└─────────────────────────────────────────────────────────────┘
```

Wherever a field or a table is our own addition, it is marked **`OURS`** in the tables below, with a one-line reason.

The invented part is not a shortcut. It is the proposal. We are saying a clinical evidence layer should sit underneath the waiting list, and this dataset shows what that would look like.

---

## 5. The hospitals

Six sites. Names are invented. Hospital codes use the 9000 range so they cannot be confused with any real hospital's code.

| Code | Name | Region | Type | Size |
|---|---|---|---|---|
| 9001 | St Brendan's University Hospital | HSE Dublin and Midlands | Public | Large, all specialties |
| 9002 | Kilbrannan Regional Hospital | HSE West and North West | Public | Large regional |
| 9003 | Ardfinnan General Hospital | HSE South West | Public | Medium |
| 9004 | Loughrea District Hospital | HSE West and North West | Public | Small |
| 9101 | Rosslare Private Clinic | HSE South East | Private | Capacity only |
| 9102 | Riverbank Private Hospital | HSE Dublin and Midlands | Private | Capacity only |

**The private sites have no waiting list.** They appear only as available capacity. Public patients reach them through a suspension (section 10.4), which is how it works in reality: the HSE or NTPF pays a private provider to treat the patient, and the patient's waiting clock pauses while that happens.

Sizes vary deliberately. If all four public hospitals were the same, there would be no regional variation to show.

---

## 6. How the tables fit together

### 6.1 The big picture

```
   WHO                      WHAT THEY ARE WAITING FOR
   ───                      ─────────────────────────

   persons                        conditions
      │  (national ID)               ▲   what is wrong with them
      │                              │
   patients ──────────────► referral_daily ◄────── observations
      (hospital record)         │    │   ▲       vitals, symptoms, scores
                                │    │   │
                                │    │   └───── triage_events
                                │    │           the urgency decision
                                │    │
                    cancellation_events  suspension_events
                                │
                                │  which service?
                                ▼
                        hospital_specialty
                          │            │
                          ▼            ▼
                        wards      clinic_sessions
                          │         appointment slots
                          ▼
                     bed_status
                   how full, three times a day
```

Three lookup tables (`ref_specialty`, `ref_codes`, `ref_rules`) sit to the side. They are dictionaries. Almost every table points into them.

### 6.2 The seven groups

Section 7 describes every table, in this order:

| Group | Tables | Why they come where they do |
|---|---|---|
| **A. The waiting list** | `referral_daily`, `triage_events` | The heart of the dataset. Everything else attaches to these. |
| **B. The people** | `patients`, `persons` | Who the referrals belong to. |
| **C. The clinical layer** `OURS` | `conditions`, `observations` | What the national record is missing. |
| **D. The hospital's capacity** | `hospitals`, `hospital_specialty`, `wards`, `ward_specialty`, `bed_status`, `clinic_sessions` | What the hospital actually has available. |
| **E. What happened along the way** | `cancellation_events`, `suspension_events` | The referral's history. |
| **F. Dictionaries** | `ref_specialty`, `ref_codes`, `ref_rules` | Lookup lists. Consulted, not read start to finish. |
| **G. Held out** | `ground_truth` | The answer key. Kept out of the database so the system cannot read it. |

### 6.3 The two keys that hold it together

A hospital's patient number is only unique **inside that hospital**. Two hospitals can both have a patient number 4471, and they are different people. The same is true of referral numbers.

So every join in this dataset uses two columns, never one:

```
   hospital_hipe + patient_id       →  identifies a patient
   hospital_hipe + pathway_number   →  identifies a referral
```

The only column that works across hospitals is `ihi_number`, the national health identifier. It is often blank, and that is on purpose. See section 10.2.

---

## 7. The tables the data contains

Types shown are PostgreSQL types. `OURS` marks anything we added that is not in the national specification.

---

## Group A — The waiting list

---

### 7.1 `referral_daily` — the waiting list itself

**The central table.** One row per referral, per day.

The list is re-read every morning and each morning's version is kept. So a referral that has been waiting 200 days appears 200 times, once for each day, with its details as they stood on that day.

This is what makes it possible to ask later: *what did the system see on the 9th, and why did it rank her second?*

Field names come straight from the national specification. The last five are ours.

| Field | Type | Null? | Description |
|---|---|---|---|
| `hospital_hipe` | `char(4)` | no | Which hospital. Part of primary key. Field 1. |
| `pathway_number` | `text` | no | The referral's number. Part of primary key. Field 5. |
| `as_of_date` | `date` | no | Which day this row describes. Part of primary key. |
| `patient_id` | `text` | no | Links to `patients`. Field 4. |
| `specialty_hipe` | `char(4)` | no | Which service they were referred to. Field 33. |
| `referral_date` | `date` | no | Date on the GP's letter. Field 45. |
| `referral_received_date` | `date` | no | Date the hospital got it. Field 47. |
| `priority_level_gp` | `integer` | yes | What the GP said: 1 urgent, 2 routine. Field 46. |
| `referral_source` | `integer` | no | Who referred them. Field 48. |
| `triage_event_id` | `text` | yes | Links to `triage_events`. Blank if never triaged. |
| `appointment_date` | `date` | yes | Booked appointment. Field 52. |
| `arrived_date` | `date` | yes | When they actually attended. Field 53. |
| `clinic_code` | `text` | yes | Which clinic. Field 44. |
| `clinic_classification` | `integer` | yes | Type of clinic. Field 74. |
| `last_cancellation_date` | `date` | yes | Field 54. |
| `last_cancellation_reason` | `integer` | yes | Field 55. |
| `record_creation_date` | `date` | no | Field 58. |
| `suspension_start_date` | `date` | yes | Field 65. |
| `suspension_reason` | `integer` | yes | Field 66. |
| `suspension_end_date` | `date` | yes | Field 67. |
| `removal_date` | `date` | yes | Field 70. |
| `removal_reason` | `integer` | yes | Field 71. |
| `high_clinical_or_social_needs` | `integer` | no | 0 or 1, set by a clinician. Field 72. |
| `triage_status` | `text` | no | `OURS` — one word summarising where the referral stands: `awaiting_triage`, `triaged`, `redirected`, `rejected`, `removed`. The specification spreads this across four separate fields; collapsing it means no part of the system has to work it out. |
| `days_since_referral` | `integer` | no | `OURS` — see section 10.1. |
| `days_since_received` | `integer` | no | `OURS` — see section 10.1. |
| `adjusted_wait_days` | `integer` | no | `OURS` — see section 10.1. |
| `days_awaiting_triage` | `integer` | yes | `OURS` — see section 10.1. |

**Why the four waiting-time fields are ours:** the specification stores dates, not durations. Every part of the system would otherwise calculate waiting time for itself, and they would disagree. We calculate all four once when the day's file is loaded, store them, and nothing anywhere else recalculates. Section 10.1 explains why there are four.

**Example: one referral on three different days**

| hospital_hipe | pathway_number | as_of_date | specialty_hipe | referral_received_date | priority_level_gp | triage_event_id | triage_status | adjusted_wait_days |
|---|---|---|---|---|---|---|---|---|
| 9001 | PW-0412 | 2026-08-18 | 2600 | 2026-07-18 | 1 | *null* | awaiting_triage | 31 |
| 9001 | PW-0412 | 2026-08-25 | 2600 | 2026-07-18 | 1 | TE-0412 | triaged | 38 |
| 9001 | PW-0412 | 2026-08-28 | 2600 | 2026-07-18 | 1 | TE-0412 | triaged | 41 |

Same referral, three days. On the 18th nobody had triaged her yet, so there was no urgency category, only the GP's opinion. By the 25th there was. The wait keeps climbing.

---

### 7.2 `triage_events` — the urgency decision

A referral is triaged once. This table records that single event, so it does not get duplicated every day.

| Field | Type | Null? | Description |
|---|---|---|---|
| `triage_event_id` | `text` | no | Primary key. |
| `hospital_hipe` | `char(4)` | no | |
| `pathway_number` | `text` | no | Which referral. |
| `sent_for_triage_date` | `date` | no | Field 60. |
| `triage_date` | `date` | yes | Field 61. |
| `date_returned_from_triage` | `date` | yes | Field 62. |
| `triage_outcome` | `integer` | yes | 1 accept, 2 redirected, 3 reject. Field 63. |
| `triage_category` | `integer` | yes | 1 urgent, 2 routine, 3 semi-urgent. Field 64. |
| `turnaround_days` | `integer` | yes | `OURS` — how many days triage took. Stored rather than calculated, so that `RULE-TRIAGE-TURNAROUND` has a single number to test against. |

**Example**

| triage_event_id | pathway_number | sent_for_triage_date | date_returned_from_triage | triage_outcome | triage_category | turnaround_days |
|---|---|---|---|---|---|---|
| TE-0412 | PW-0412 | 2026-08-19 | 2026-08-22 | 1 | 1 | 3 |
| TE-5120 | PW-5120 | 2026-08-20 | 2026-08-21 | 1 | 1 | 1 |
| TE-3345 | PW-3345 | 2026-02-02 | 2026-02-14 | 1 | 2 | 12 |

Note that the GP marked PW-0412 urgent and triage agreed. That does not always happen, and the disagreements are interesting.

---

## Group B — The people

---

### 7.3 `patients` — hospital records

One row per patient **per hospital**. The same person attending two hospitals appears twice here.

| Field | Type | Null? | Description |
|---|---|---|---|
| `hospital_hipe` | `char(4)` | no | Part of primary key. Field 1. |
| `patient_id` | `text` | no | The hospital's own number. Part of primary key. Field 4. |
| `ihi_number` | `text` | **yes** | National identifier. Often blank. Field 2. |
| `patient_sex` | `char(1)` | no | `M`, `F` or `U`. Field 9. |
| `patient_date_of_birth` | `date` | no | Field 10. |
| `area_of_residence_code` | `char(4)` | no | Where they live, as an official code. Field 16. |

**Example**

| hospital_hipe | patient_id | ihi_number | patient_sex | patient_date_of_birth |
|---|---|---|---|---|
| 9001 | MRN-004412 | IHI-7781004 | F | 1959-03-11 |
| 9002 | MRN-119003 | IHI-7781004 | F | 1959-03-11 |
| 9001 | MRN-005120 | *null* | M | 1997-06-02 |

Rows 1 and 2 are the **same woman** at two hospitals. We know because the national identifier matches.

Row 3 has no national identifier. If that man is also waiting at another hospital, we cannot tell. That is deliberate. See section 10.2.

---

### 7.4 `persons` — national identity

One row per real human being, where we can identify them nationally. Sits above `patients`: one person, possibly several hospital records.

| Field | Type | Null? | Description |
|---|---|---|---|
| `ihi_number` | `text` | no | National identifier. Primary key. |
| `person_sex` | `char(1)` | no | |
| `person_date_of_birth` | `date` | no | |
| `area_of_residence_code` | `char(4)` | no | |

Patients with no national identifier have no row here at all. That absence is the point.

---

## Group C — The clinical layer

**Both tables in this group are ours.** The national record contains no clinical information whatsoever, which is the finding this whole project rests on (section 3.2). These two tables are what we are proposing be added.

---

### 7.5 `conditions` — what is wrong with the patient

`OURS` — because the national waiting list has no diagnosis field of any kind.

| Field | Type | Null? | Description |
|---|---|---|---|
| `hospital_hipe` | `char(4)` | no | Part of primary key. |
| `pathway_number` | `text` | no | Part of primary key. |
| `icd10am_code` | `text` | no | Diagnosis code, in the coding system Irish hospitals use. Part of primary key. |
| `condition_label` | `text` | no | Plain-English description. |
| `is_primary` | `boolean` | no | The main reason for the referral. |
| `snomed_ct_id` | `text` | yes | A second, more detailed clinical code. Optional, included so the data could later connect to national systems that use it. |

**Example**

| hospital_hipe | pathway_number | icd10am_code | condition_label | is_primary |
|---|---|---|---|---|
| 9001 | PW-0412 | K83.1 | Obstruction of bile duct | true |
| 9001 | PW-0412 | R17 | Unspecified jaundice | false |
| 9001 | PW-3345 | M16.1 | Primary osteoarthritis of hip | true |

---

### 7.6 `observations` — vitals, symptoms and triage scores

`OURS` — because the national waiting list records no clinical observations of any kind.

**Why it is called `observations` and not `vitals`.** In Irish and international clinical practice, "observations" (nurses say "obs") is the umbrella term for everything recorded on an observation chart at the bedside. That covers three different kinds of thing, and this table holds all three:

| Kind | Columns | Who produces it |
|---|---|---|
| **Vitals** — measured | `hr`, `sbp`, `dbp`, `rr`, `temp`, `spo2` | A machine or a nurse |
| **Symptoms** — reported | `pain`, `chiefcomplaint` | The patient |
| **Assessments and scores** — judged or calculated | `avpu`, `news2`, `mts_category`, `icts_category` | The clinician, or arithmetic |

Calling the table `vitals` would misfile the patient's own reported pain and complaint. Calling it `symptoms` would misfile the blood pressure. Clinicians keep measured and reported information strictly apart, because one is evidence and the other is testimony. `observations` is the standard word that correctly covers both, plus the scores that are neither.

It is also the exact term used in FHIR, the international standard for exchanging health data, where `Observation` is the resource holding vitals, scores and coded assessments together. That matters if this ever connects to a national system.

Individual column names deliberately match the MIMIC-IV-ED dataset (section 3.3), so real distributions can be fitted from it without renaming anything.

| Field | Type | Null? | Description |
|---|---|---|---|
| `hospital_hipe` | `char(4)` | no | Part of primary key. |
| `pathway_number` | `text` | no | Part of primary key. |
| `obs_datetime` | `timestamp` | no | When recorded. Part of primary key. |
| `hr` | `integer` | yes | *Vital.* Heart rate, beats per minute. |
| `sbp` | `integer` | yes | *Vital.* Systolic blood pressure, the higher of the two blood pressure numbers. |
| `dbp` | `integer` | yes | *Vital.* Diastolic blood pressure, the lower one. |
| `rr` | `integer` | yes | *Vital.* Respiratory rate, breaths per minute. |
| `temp` | `numeric(4,1)` | yes | *Vital.* Temperature in Celsius. |
| `spo2` | `integer` | yes | *Vital.* Oxygen saturation, as a percentage. |
| `pain` | `integer` | yes | *Symptom.* The patient's own pain rating, 0 to 10. |
| `chiefcomplaint` | `text` | yes | *Symptom.* What the patient says is wrong, in their words. |
| `avpu` | `char(1)` | yes | *Assessment.* How conscious they are: `A`, `V`, `P` or `U`. |
| `news2` | `integer` | yes | *Score.* Early warning score, calculated from the vitals above. |
| `mts_category` | `text` | yes | *Assessment.* Manchester Triage System colour, for adults. |
| `icts_category` | `text` | yes | *Assessment.* Irish Children's Triage System colour, for children. |

**Example**

| pathway_number | obs_datetime | hr | sbp | rr | temp | spo2 | news2 | mts_category |
|---|---|---|---|---|---|---|---|---|
| PW-0412 | 2026-08-19 09:14 | 104 | 118 | 22 | 38.2 | 96 | 5 | orange |
| PW-5120 | 2026-08-20 11:02 | 72 | 124 | 14 | 36.7 | 99 | 0 | green |
| PW-3345 | 2026-02-02 15:30 | 78 | 136 | 16 | 36.4 | 98 | 1 | green |

PW-5120 is a suspected melanoma. Every vital sign is normal, and the patient is clinically urgent.

**Vitals alone do not tell you who is urgent**, and this dataset is built so that stays true. If they did, the whole exercise would be circular.

This is now measured rather than asserted. Fitting the vitals distributions from real triage data (MIMIC-IV-ED Demo, 207 stays with a recorded acuity) shows an early warning score barely discriminates triage acuity at all: the best possible rule based on `news2` alone recovers the category only 17.5 percentage points better than guessing the most common one, and 54 to 59 per cent of the highest-acuity patients score `news2 <= 2`. NEWS2 was built to detect deterioration in admitted ward patients over time; triage acuity reflects predicted resource use and presenting complaint. They measure different things. See `docs/HOW_THE_DATA_WAS_MADE.md`.

---

## Group D — The hospital's capacity

**Every table in this group is ours.** No Irish source publishes ward, bed or clinic data in a reusable file. What we take from the real system is the *vocabulary*, so that the columns use terms a hospital bed manager would recognise.

---

### 7.7 `hospitals` — the six sites

`OURS` — the sites themselves are invented, though the code format is real.

| Field | Type | Null? | Description |
|---|---|---|---|
| `hospital_hipe` | `char(4)` | no | Primary key. |
| `hospital_name` | `text` | no | Fictitious name. |
| `hse_health_region` | `text` | no | One of the six HSE regions. |
| `hospital_type` | `text` | no | `public` or `private`. |
| `total_inpatient_beds` | `integer` | no | Size of the site. |

**Example**

| hospital_hipe | hospital_name | hse_health_region | hospital_type | total_inpatient_beds |
|---|---|---|---|---|
| 9001 | St Brendan's University Hospital | HSE Dublin and Midlands | public | 640 |
| 9004 | Loughrea District Hospital | HSE West and North West | public | 110 |
| 9102 | Riverbank Private Hospital | HSE Dublin and Midlands | private | 180 |

---

### 7.8 `hospital_specialty` — which services each hospital runs

`OURS` — and necessary, for a reason worth spelling out.

Cardiology at one hospital is a different service from cardiology at another. Different staff, different waiting list, different beds. This table names that unit.

Without it, a query asking "how full are the cardiology beds for this patient?" would pick up cardiology beds at every hospital in the country and return a meaningless number that looks perfectly reasonable.

| Field | Type | Null? | Description |
|---|---|---|---|
| `hospital_hipe` | `char(4)` | no | Part of primary key. |
| `specialty_hipe` | `char(4)` | no | Part of primary key. |
| `service_name` | `text` | no | Local name for the service. |
| `active` | `boolean` | no | Whether this hospital currently runs it. |

**Example**

| hospital_hipe | specialty_hipe | service_name | active |
|---|---|---|---|
| 9001 | 2600 | General Surgery, St Brendan's | true |
| 9001 | 0601 | Paediatric ENT, St Brendan's | true |
| 9004 | 2600 | General Surgery, Loughrea | true |
| 9004 | 0601 | *(not offered)* | false |

The small hospital does not run every service. That is realistic, and it gives the system somewhere to send patients.

---

### 7.9 `wards` — the wards

`OURS`.

| Field | Type | Null? | Description |
|---|---|---|---|
| `hospital_hipe` | `char(4)` | no | Part of primary key. |
| `ward_id` | `text` | no | Part of primary key. |
| `ward_name` | `text` | no | |
| `total_beds` | `integer` | no | |
| `ward_type` | `text` | no | `inpatient`, `day_case`, `assessment` or `icu`. |

---

### 7.10 `ward_specialty` — which specialties share which wards

`OURS` — and this is the table that lets the system see the actual problem.

Real wards are shared. A general medical ward takes cardiology patients, respiratory patients, whoever needs a bed. When a hospital is under pressure, specialties compete for the same beds and someone loses.

Without this table our capacity model could only say "this ward is full." With it, we can say "cardiology and respiratory are fighting over the same 30 beds."

| Field | Type | Null? | Description |
|---|---|---|---|
| `hospital_hipe` | `char(4)` | no | Part of primary key. |
| `ward_id` | `text` | no | Part of primary key. |
| `specialty_hipe` | `char(4)` | no | Part of primary key. |
| `nominal_beds` | `integer` | no | Beds notionally allocated to this specialty. |
| `is_primary` | `boolean` | no | Whether this is the ward's main specialty. |

**Example**

| hospital_hipe | ward_id | specialty_hipe | nominal_beds | is_primary |
|---|---|---|---|---|
| 9001 | W-STB-04 | 2600 | 24 | true |
| 9001 | W-STB-04 | 2400 | 6 | false |
| 9001 | W-STB-04 | 0900 | 4 | false |

One 34-bed ward, three specialties. Surgery has 24 on paper. When medicine overflows into it, surgery gets squeezed and planned operations get cancelled.

**That is the mechanism behind the trolley crisis**, and this table is what lets the system see it rather than just assert it.

---

### 7.11 `bed_status` — how full, three times a day

`OURS` — but every column name is borrowed from the HSE's own daily report, and the three-times-a-day rhythm is the real one: 08:00, 14:00 and 20:00.

| Field | Type | Null? | Description |
|---|---|---|---|
| `hospital_hipe` | `char(4)` | no | Part of primary key. |
| `ward_id` | `text` | no | Part of primary key. |
| `snapshot_datetime` | `timestamp` | no | Part of primary key. |
| `occupied` | `integer` | no | Beds in use. |
| `free` | `integer` | no | **Beds actually available.** |
| `occupancy_pct` | `numeric(5,2)` | no | Percentage full. |
| `outliers` | `integer` | no | Patients here who belong to another specialty. |
| `surge_capacity_in_use` | `integer` | no | Extra beds opened because of pressure. |
| `delayed_transfers_of_care` | `integer` | no | Patients ready to leave but still here. |
| `awaiting_admission_over_9h` | `integer` | no | Waiting more than 9 hours for a bed. |
| `awaiting_admission_over_24h` | `integer` | no | Waiting more than 24 hours. |
| `gar_status` | `char(1)` | no | `G` green, `A` amber, `R` red. |

**Example**

| ward_id | snapshot_datetime | occupied | free | occupancy_pct | outliers | surge_capacity_in_use | delayed_transfers_of_care | gar_status |
|---|---|---|---|---|---|---|---|---|
| W-STB-04 | 2026-08-28 08:00 | 34 | 0 | 100.00 | 9 | 4 | 6 | R |
| W-STB-04 | 2026-08-28 14:00 | 33 | 1 | 97.06 | 9 | 4 | 6 | R |
| W-LOU-01 | 2026-08-28 08:00 | 18 | 4 | 81.82 | 1 | 0 | 1 | G |

**`free` is the answer to "how many beds are available."** But read the other columns before trusting it. That first ward shows 0 free, 9 patients from other specialties, 4 emergency beds already opened and 6 people who should have gone home. One free bed at 14:00 does not mean the pressure lifted.

Also note: for a **clinic** appointment, the constraint is not a bed at all. It is a slot. See the next table.

---

### 7.12 `clinic_sessions` — appointment slots

`OURS`. Most outpatient referrals need a clinic appointment, not a bed, so this is where the real constraint usually sits.

| Field | Type | Null? | Description |
|---|---|---|---|
| `hospital_hipe` | `char(4)` | no | Part of primary key. |
| `clinic_code` | `text` | no | Part of primary key. |
| `session_date` | `date` | no | Part of primary key. |
| `clinic_name` | `text` | no | |
| `specialty_hipe` | `char(4)` | no | |
| `slots_total` | `integer` | no | Capacity of the session. |
| `slots_booked` | `integer` | no | Already filled. |
| `slots_available` | `integer` | no | `slots_total` minus `slots_booked`. |

**Example**

| clinic_code | session_date | clinic_name | specialty_hipe | slots_total | slots_booked | slots_available |
|---|---|---|---|---|---|---|
| CL-STB-GS1 | 2026-09-02 | General Surgery outpatients | 2600 | 22 | 22 | 0 |
| CL-STB-DE1 | 2026-09-02 | Dermatology outpatients | 0300 | 18 | 7 | 11 |
| CL-RIV-GS1 | 2026-09-03 | Riverbank surgical clinic | 2600 | 12 | 3 | 9 |

The third row is a **private** clinic. Public patients can only reach it through a suspension.

When a referral in `referral_daily` has an appointment date and a clinic code, it has consumed one of these slots. The two tables must agree.

---

## Group E — What happened along the way

---

### 7.13 `cancellation_events` — every cancellation, not just the last one

`OURS` in structure, real in content. The national record keeps only the most recent cancellation. We keep all of them, because the pattern matters more than the last instance.

| Field | Type | Null? | Description |
|---|---|---|---|
| `hospital_hipe` | `char(4)` | no | Part of primary key. |
| `pathway_number` | `text` | no | Part of primary key. |
| `cancellation_date` | `date` | no | Part of primary key. |
| `cancellation_reason` | `integer` | no | Real code from the national specification. |
| `initiated_by` | `char(1)` | no | `H` hospital or `P` patient. |

**Example**

| pathway_number | cancellation_date | cancellation_reason | initiated_by |
|---|---|---|---|
| PW-0412 | 2026-08-11 | 21 | H |
| PW-0412 | 2026-08-24 | 110 | H |
| PW-3345 | 2026-05-03 | 22 | P |

Both of PW-0412's cancellations were started by the hospital. Cross-referencing those dates against `bed_status` shows whether they happened on days the hospital was under pressure.

That turns "planned operations get cancelled because of overcrowding" from a claim into something you can check.

---

### 7.14 `suspension_events` — time when the clock stops

A suspension means the patient's care has been sent elsewhere, usually to a private hospital, and the waiting clock pauses.

| Field | Type | Null? | Description |
|---|---|---|---|
| `hospital_hipe` | `char(4)` | no | Part of primary key. |
| `pathway_number` | `text` | no | Part of primary key. |
| `suspension_start_date` | `date` | no | Part of primary key. |
| `suspension_end_date` | `date` | yes | Blank if still suspended. |
| `suspension_reason` | `integer` | no | 101 to 104, real codes. |
| `suspended_days` | `integer` | yes | `OURS` — the paused days, stored so waiting-time calculations do not have to work it out repeatedly. |

The four reasons, copied from the national specification:

| Code | Meaning | Plain English |
|---|---|---|
| 101 | NTPF Outsourcing Initiative | NTPF paid a private hospital to treat them |
| 102 | NTPF Insourcing Initiative | NTPF paid for extra evening or weekend clinics here |
| 103 | HSE Outsourcing Initiative | HSE paid a private hospital to treat them |
| 104 | HSE Insourcing Initiative | HSE paid for extra evening or weekend clinics here |

**Example**

| pathway_number | suspension_start_date | suspension_end_date | suspension_reason | suspended_days |
|---|---|---|---|---|
| PW-7781 | 2026-06-02 | 2026-06-22 | 103 | 20 |

This patient spent 20 days being treated privately. Those 20 days do not count against the hospital's waiting time. See section 10.1.

---

## Group F — Dictionaries

Three lookup tables. Small, fixed, and pointed at by almost everything else.

---

### 7.15 `ref_specialty` — the list of medical specialties

Every referral is sent to a specialty. This is the official list, copied from the national specification.

| Field | Type | Null? | Description |
|---|---|---|---|
| `specialty_hipe` | `char(4)` | no | Four-digit official code. Primary key. |
| `specialty_name` | `text` | no | Plain name. |
| `is_paediatric` | `boolean` | no | `OURS` — true for children's specialties. Needed because children are triaged on a different scale from adults. |

**Example**

| specialty_hipe | specialty_name | is_paediatric |
|---|---|---|
| 2600 | General Surgery | false |
| 0100 | Cardiology | false |
| 0300 | Dermatology | false |
| 1800 | Orthopaedics | false |
| 0700 | Gastro-Enterology | false |
| 0600 | Otolaryngology (ENT) | false |
| 0601 | Paediatric ENT | true |

These codes are real. `0601` really is Paediatric ENT in the Irish system.

---

### 7.16 `ref_codes` — all the other code lists in one table

The national specification has thirteen more code lists. Rather than thirteen tiny tables, we put them in one, separated by a `code_table` column.

| Field | Type | Null? | Description |
|---|---|---|---|
| `code_table` | `text` | no | Which list this belongs to. Part of primary key. |
| `code_value` | `text` | no | The code. Part of primary key. |
| `description` | `text` | no | What it means. |
| `severity_rank` | `integer` | yes | `OURS` — how urgent, 1 being most. Only filled in for triage categories. See below. |
| `crt_days` | `integer` | yes | `OURS` — the maximum days a patient in this category should wait. Only for triage categories. |

**Example**

| code_table | code_value | description | severity_rank | crt_days |
|---|---|---|---|---|
| triage_category | 1 | Urgent | 1 | 28 |
| triage_category | 3 | Semi-Urgent | 2 | 91 |
| triage_category | 2 | Routine/Non-Urgent | 3 | *null* |
| triage_category | 4 | Excluded | *null* | *null* |
| gp_priority | 1 | Urgent | | |
| gp_priority | 2 | Routine | | |
| referral_source | 12 | General Practitioners (GP) | | |
| referral_source | 6 | Emergency Department within the hospital | | |
| removal_reason | 104 | Admitted as inpatient, day case or emergency for the same condition | | |

**Read that first block carefully.** In the real system, Urgent is code 1, Routine is code 2, and Semi-Urgent is code **3**. The codes are not in order of severity. Sorting by `code_value` puts Routine ahead of Semi-Urgent, which is wrong, and it is wrong silently.

**That is why `severity_rank` is ours.** Every part of the system sorts on `severity_rank`, never on `code_value`. We fix the problem once, here, instead of five times in five different places and missing one.

`crt_days` is ours for the same reason. The time limits are real and come from the national protocol, but they live in a written document, not in the data. Putting them in a table means the rule checker reads them rather than having them typed into code.

---

### 7.17 `ref_rules` — the waiting time rules

The rules a ranking must respect. Stored as data, so that a rule being broken can be recorded as a fact rather than buried in a log file.

| Field | Type | Null? | Description |
|---|---|---|---|
| `rule_id` | `text` | no | Primary key. |
| `statement` | `text` | no | The rule in plain English. |
| `applies_to` | `text` | no | Which referrals it covers. |
| `threshold_days` | `integer` | yes | The limit, where there is one. |

**Example**

| rule_id | statement | applies_to | threshold_days |
|---|---|---|---|
| RULE-CRT-URGENT | An urgent referral should be seen within 28 days | triaged urgent | 28 |
| RULE-CRT-SEMI | A semi-urgent referral should be seen within 13 weeks | triaged semi-urgent | 91 |
| RULE-TRIAGE-TURNAROUND | A referral should not sit untriaged indefinitely | awaiting triage | 21 |
| RULE-ORDER | A referral may never be ranked above one of higher clinical priority. Ordering happens only within a category. | all | *null* |
| RULE-TIEBREAK | Same category and same status, oldest referral first unless clinical evidence justifies otherwise | all | *null* |

The first two come from the national protocol. The third is `OURS`, because untriaged referrals have no time limit of their own and would otherwise be invisible to every check in the system.

**`RULE-ORDER` is the hardest constraint here.** Categories come from clinicians at triage, and nothing in this system may reorder across them. Every urgent patient sits above every semi-urgent one, whatever the scores say. All of the system's work happens *inside* a category, which is exactly where the national record runs out of information (section 3.2).

A violation of this rule is a defect, not a judgement call. It is the one rule a clinician override should not be able to break silently, so when one is attempted the system warns first, then logs both the warning and the decision to proceed.

---

## Group G — Held out

One file, deliberately kept outside the database.

---

### 7.18 `ground_truth` — the answer key, never loaded

**This file is not part of the dataset the system sees.** The loader ignores it. Only the scoring script opens it, and only after a ranking has been produced.

#### Why it exists

To answer "did the ranking help?" you need to know who was genuinely at risk.

If that were sitting in the database, the urgency agent could read it and sort by it. The system would score perfectly and prove nothing. So the answer is kept in a separate file the system cannot reach, and the agents have to work risk out for themselves from vitals and conditions, the way a clinician would.

| Field | Type | Null? | Description |
|---|---|---|---|
| `hospital_hipe` | `char(4)` | no | Part of primary key. |
| `pathway_number` | `text` | no | Part of primary key. |
| `latent_hazard` | `numeric(4,3)` | no | Hidden risk of getting worse while waiting, 0 to 1. |
| `deterioration_date` | `date` | yes | If and when they did get worse. |
| `deterioration_type` | `text` | yes | `emergency_admission` or `death`. |

**Example**

| hospital_hipe | pathway_number | latent_hazard | deterioration_date | deterioration_type |
|---|---|---|---|---|
| 9001 | PW-0412 | 0.812 | 2026-08-26 | emergency_admission |
| 9001 | PW-3345 | 0.094 | *null* | *null* |

#### What informs it — an honest split

The two halves of this table have very different standing, and we do not blur them.

**The outcome columns are grounded in the national specification.**

`deterioration_type` is not invented vocabulary. It maps onto two real removal reason codes:

| Code | Meaning in the national specification | Our column |
|---|---|---|
| 104 | Admitted as inpatient, day case, or attended emergency for the same condition | `emergency_admission` |
| 11 | Is deceased | `death` |

Code 104 describes a patient who was waiting for a planned appointment and instead ended up admitted or in emergency for the very thing they were waiting about. That is deterioration while waiting, and the Irish system already records it.

This matters for what happens after the challenge. A real pilot would not need our simulation. It would count removal reason 104 in live data and measure exactly the same variable.

**The risk column is our assumption, and nothing more.**

`latent_hazard` has no source. No Irish document says a patient with a blocked bile duct has a 0.81 chance of deteriorating. That number does not exist anywhere. We generate it.

It is drawn once when the patient is created, loosely conditional on their condition and age, with deliberately **large unexplained variation**.

That variation is the important part, and it is there for a specific reason. If risk were a clean function of the early warning score, and the urgency agent also scores on the early warning score, then "our ranking reduces deterioration" would be true automatically, by construction, regardless of whether the system worked. The system would be graded against its own inputs.

The large random element prevents that. It means the vitals and conditions the agent can see only *partly* predict who deteriorates, which is also true in real medicine, where no clinician can reliably say who will get worse.

So the agent can only improve the outcome by genuinely identifying high-risk patients from partial information. That makes the claim testable rather than circular.

#### How to report it

Two numbers come out of the evaluation, and they should not be given equal weight.

| Metric | Needs `ground_truth`? | What the audience must accept |
|---|---|---|
| **Missed deadlines** | No | Nothing. A published 28-day rule, a date, and arithmetic. |
| **Deteriorations** | Yes | Our hazard model, which is synthetic and unvalidated. |

**Lead with missed deadlines.** Nobody has to trust anything to accept that number.

**Put deterioration second, and state plainly that the risk model is ours and unvalidated.** Hiding it invites a reader to assume the result is circular, and they would be right to.

---

## 8. The tables the system writes

Everything in section 7 is an **input**. Generated once, loaded, then read-only. Nothing ever writes to those tables again.

The agents write to a different set. These start empty and fill up as the system runs.

```
   INPUTS                          OUTPUTS
   17 tables                       7 tables
   generated once                  written every run
   never change                    only ever appended to
        │                               ▲
        │      ┌──────────────┐         │
        └─────►│ urgency      │─────────┤  agent_scores
        │      │ agent        │         │  agent_citations
        │      └──────────────┘         │
        │      ┌──────────────┐         │
        └─────►│ capacity     │─────────┤  agent_scores
        │      │ agent        │         │  agent_citations
        │      └──────────────┘         │
        │      ┌──────────────┐         │  decisions
        └─────►│ coordinator  │─────────┤  decision_rankings
               └──────────────┘         │  decision_citations
               ┌──────────────┐         │
               │ rule checker │─────────┤  rule_checks
               └──────────────┘         │
               ┌──────────────┐         │
               │ clinician    │─────────┘  overrides
               └──────────────┘
```

**Why the separation matters.** If a table could be both an input and something an agent writes, you could no longer tell what the system *saw* apart from what it *decided*. Keeping them apart is what makes it possible to replay any past ranking exactly.

---

### 8.1 `agent_scores`

One row each time an agent scores a referral. Two per referral per day: one from the urgency agent, one from the capacity agent.

| Field | Type | Null? | Description |
|---|---|---|---|
| `run_id` | `text` | no | Which run produced this. Part of primary key. |
| `agent_name` | `text` | no | `urgency` or `capacity`. Part of primary key. |
| `hospital_hipe` | `char(4)` | no | Part of primary key. |
| `pathway_number` | `text` | no | Part of primary key. |
| `as_of_date` | `date` | no | Which day's data was scored. |
| `score` | `numeric(4,3)` | no | Between 0 and 1. |
| `method` | `text` | no | How it was worked out, for example `NEWS2 plus triage category`. |
| `agent_version` | `text` | no | Which version of the agent. |
| `scored_at` | `timestamp` | no | |

Storing the version and the method means a score is never just a number. You can always say who produced it, when, and how.

---

### 8.2 `agent_citations`

What each score was based on. **This table is the reason explanation is possible at all.**

| Field | Type | Null? | Description |
|---|---|---|---|
| `run_id` | `text` | no | Part of primary key. |
| `agent_name` | `text` | no | Part of primary key. |
| `hospital_hipe` | `char(4)` | no | Part of primary key. |
| `pathway_number` | `text` | no | Part of primary key. |
| `evidence_type` | `text` | no | `observation`, `condition`, `triage_event`, `bed_status` or `clinic_session`. Part of primary key. |
| `evidence_key` | `text` | no | Points at the exact input row used. Part of primary key. |

**Example**

| run_id | agent_name | pathway_number | evidence_type | evidence_key |
|---|---|---|---|---|
| RUN-0931 | urgency | PW-0412 | observation | 9001:PW-0412:2026-08-19T09:14 |
| RUN-0931 | urgency | PW-0412 | condition | 9001:PW-0412:K83.1 |
| RUN-0931 | urgency | PW-0412 | triage_event | TE-0412 |
| RUN-0931 | capacity | PW-0412 | bed_status | 9001:W-STB-04:2026-08-28T08:00 |
| RUN-0931 | capacity | PW-0412 | clinic_session | 9001:CL-STB-GS1:2026-09-02 |

Without these rows you have a score of 0.87 and no way of knowing where it came from.

---

### 8.3 `decisions`

One row per ranking run, per hospital.

| Field | Type | Null? | Description |
|---|---|---|---|
| `decision_id` | `text` | no | Primary key. |
| `run_id` | `text` | no | |
| `hospital_hipe` | `char(4)` | no | Rankings are produced per hospital. |
| `as_of_date` | `date` | no | Which day's list. |
| `generated_at` | `timestamp` | no | |
| `cohort_size` | `integer` | no | How many referrals were ranked. |
| `coordinator_version` | `text` | no | |

---

### 8.4 `decision_rankings`

One row per patient per ranking. The list itself.

| Field | Type | Null? | Description |
|---|---|---|---|
| `decision_id` | `text` | no | Part of primary key. |
| `hospital_hipe` | `char(4)` | no | Part of primary key. |
| `pathway_number` | `text` | no | Part of primary key. |
| `position` | `integer` | no | Where they landed on the list. |
| `triage_category` | `integer` | yes | The category they were ranked within. |
| `urgency_score` | `numeric(4,3)` | no | |
| `capacity_score` | `numeric(4,3)` | no | |
| `rationale_summary` | `text` | no | One line, assembled from the citations. |

`triage_category` is stored here on purpose. It makes it possible to check at a glance that no ranking crossed a category boundary, which is `RULE-ORDER`.

---

### 8.5 `decision_citations`

What the coordinator pointed at for each position on the list.

| Field | Type | Null? | Description |
|---|---|---|---|
| `decision_id` | `text` | no | Part of primary key. |
| `hospital_hipe` | `char(4)` | no | Part of primary key. |
| `pathway_number` | `text` | no | Part of primary key. |
| `evidence_type` | `text` | no | Part of primary key. |
| `evidence_key` | `text` | no | Part of primary key. |
| `role` | `text` | no | `urgency`, `capacity`, `timeframe` or `multi_list`. |

The `role` column is what lets the clinician screen group the explanation into sections, rather than showing one undifferentiated pile of facts.

---

### 8.6 `rule_checks`

Every rule tested against every patient, whether it passed or failed.

| Field | Type | Null? | Description |
|---|---|---|---|
| `decision_id` | `text` | no | Part of primary key. |
| `rule_id` | `text` | no | Part of primary key. |
| `hospital_hipe` | `char(4)` | no | Part of primary key. |
| `pathway_number` | `text` | no | Part of primary key. |
| `passed` | `boolean` | no | |
| `detail` | `text` | yes | For example: `urgent, day 41 of 28, over by 13`. |

**Example**

| decision_id | rule_id | pathway_number | passed | detail |
|---|---|---|---|---|
| DEC-0931 | RULE-CRT-URGENT | PW-0412 | false | urgent, day 41 of 28, over by 13 |
| DEC-0931 | RULE-CRT-URGENT | PW-5120 | true | urgent, day 9 of 28 |
| DEC-0931 | RULE-ORDER | PW-5120 | true | ranked above semi-urgent, correct |

Keyed to the patient, not just the decision. That is what makes counting breaches a simple query rather than reading through text.

---

### 8.7 `overrides`

What the clinician changed, and why.

| Field | Type | Null? | Description |
|---|---|---|---|
| `override_id` | `text` | no | Primary key. |
| `decision_id` | `text` | no | Which ranking was changed. |
| `hospital_hipe` | `char(4)` | no | |
| `pathway_number` | `text` | no | Which patient was moved. |
| `clinician_id` | `text` | no | |
| `from_position` | `integer` | yes | Blank if the patient was held rather than moved. |
| `to_position` | `integer` | yes | |
| `reason` | `text` | no | Required. No override is recorded without one. |
| `rule_warning_accepted` | `boolean` | no | Whether a rule warning was overridden knowingly. |
| `created_at` | `timestamp` | no | |

A clinician can override anything, including a rule warning. The system warns, names the rule that would break, and then does what it is told. Both the warning and the decision to proceed are stored.

That mirrors existing Irish practice. Under the national ambulance dispatch standard, a dispatcher may override the priority the system assigns. Human judgement wins. The system's job is to make sure the reasoning on both sides is on the record.

---

## 9. Following one patient through

To show how the tables connect, here is a single patient across all of them.

```
persons
  IHI-7781004 · female · born 1959-03-11 · lives Dublin 12
        │
        ▼
patients
  hospital 9001 · MRN-004412
        │
        ▼
referral_daily          (one row per day; showing 2026-08-28)
  pathway PW-0412 · General Surgery (2600)
  referral letter dated 2026-07-15, received 2026-07-18
  GP said: urgent (1)
  adjusted wait: 41 days
        │
        ├──► conditions
        │      K83.1 Obstruction of bile duct  (primary)
        │
        ├──► observations
        │      2026-08-19 09:14 · HR 104 · RR 22 · Temp 38.2 · NEWS2 5
        │
        ├──► triage_events
        │      TE-0412 · returned 2026-08-22 · accepted · URGENT
        │      time limit: 28 days
        │
        ├──► cancellation_events
        │      2026-08-11 · cancelled by consultant/team · hospital
        │      2026-08-24 · service restructuring · hospital
        │
        └──► hospital_specialty
               9001 + 2600 · General Surgery, St Brendan's
                     │
                     ├──► ward_specialty ──► wards ──► bed_status
                     │      W-STB-04 · 24 nominal beds
                     │      2026-08-28 08:00 · 0 free · 9 outliers
                     │      4 surge beds open · 6 delayed transfers · RED
                     │
                     └──► clinic_sessions
                            CL-STB-GS1 · 2026-09-02 · 0 slots available
```

**What the dataset now says about her, in plain English:**

She is urgent. Her time limit was 28 days. She is at 41, so she is 13 days over. Her vital signs support the urgency. She has been cancelled twice, both times by the hospital. Her ward has no free beds, nine patients from other specialties in it, and six people who should have gone home. The next surgical clinic is full.

Not one of those facts is a judgement. They are all stored, and every one of them can be pointed at.

---

## 10. Four things worth understanding

### 10.1 There are four different "how long have they waited"

They give different answers for the same patient, sometimes by weeks. Each is calculated once, when the day's data is loaded, and stored. Nothing anywhere else recalculates a waiting time.

| Field | Counts from | Used for |
|---|---|---|
| `days_since_referral` | Date on the GP's letter | What we show the clinician. It is what the patient experiences. |
| `days_since_received` | Date the hospital got the letter | The hospital's own clock. |
| `adjusted_wait_days` | Received date, minus any suspended time | **Checking the 28 and 91 day rules.** |
| `days_awaiting_triage` | Received date, if never triaged | Referrals nobody has looked at yet. |

**Why the adjusted one matters.** Take an urgent referral received 40 days ago, suspended for 20 of those while being treated privately.

- Raw wait: 40 days. Looks like a 12-day breach.
- Adjusted wait: 20 days. No breach at all.

Use the raw number and you report breaches that are not breaches. The national specification is explicit that suspension dates exist so the paused time can be excluded.

### 10.2 The national identifier is often missing, and that is on purpose

Roughly a third of patients have no national identifier.

Where it exists, the same person waiting at two hospitals can be recognised as one person, and the system can say: *this patient is also waiting in dermatology here and cardiology at Kilbrannan.*

Where it does not, the two records are, as far as anything can tell, two unrelated strangers.

We could have filled in every identifier and made the demonstration tidier. We did not, because the gap is the point. It shows exactly what a national shared care record would fix.

> **Known limitation in v1.0.** The generator does not currently place any person at
> two hospitals, so this cross-hospital linkage is described here but not yet observable
> in the published data. See `docs/HOW_THE_DATA_WAS_MADE.md` §7.1.

### 10.3 A referral can exist with no urgency category at all

The national record only requires a triage category once the referral has come back from triage. Before that, there is a GP's opinion and nothing else.

Those referrals are the ones most likely to be forgotten, because they have no time limit to breach. `RULE-TRIAGE-TURNAROUND` exists specifically to make them visible.

In the data this shows as `triage_status` of `awaiting_triage` with a blank `triage_event_id`.

### 10.4 Private hospitals have no waiting list

The two private sites appear in `hospitals`, `wards`, `bed_status` and `clinic_sessions`. They never appear in `referral_daily`.

They are capacity, not a queue. A public patient reaches them by being suspended (reason 101 or 103), which is how the HSE and NTPF actually purchase private treatment.

That is why a suspension both pauses the clock and consumes a private slot. Those are the same event seen from two sides.

---

## 11. What is deliberately not here

**Names, addresses, phone numbers, emails.** The real specification carries all of them: two forenames, a surname, five address lines, postcode, two phone numbers and an email. We generate none of them. Nothing in this system needs them, so nothing in this system stores them.

**GP and consultant identities.** The real record names the referring GP and the consultant. We store neither. A ranking should not know whose patient it is.

**Free-text referral letters.** Out of scope. The system reasons over coded evidence.

**Anything from a real patient.** Every row is generated. The published sources we drew on are all aggregate statistics or openly licensed synthetic data.

---

## 12. Summary of tables

### Loaded in

| # | Table | Group | Rows roughly | Source of its shape |
|---|---|---|---|---|
| 1 | `referral_daily` | A | ~110,000 | **National specification, 23 real fields** |
| 2 | `triage_events` | A | ~6,000 | National specification, fields 60 to 64 |
| 3 | `patients` | B | ~8,000 | National specification, fields 1, 2, 4, 9, 10, 16 |
| 4 | `persons` | B | ~5,000 | National specification, field 2 |
| 5 | `conditions` | C | ~10,000 | `OURS`, shaped by HIPE |
| 6 | `observations` | C | ~12,000 | `OURS`, shaped by MIMIC-IV-ED |
| 7 | `hospitals` | D | 6 | `OURS` |
| 8 | `hospital_specialty` | D | ~30 | `OURS` |
| 9 | `wards` | D | ~40 | `OURS` |
| 10 | `ward_specialty` | D | ~90 | `OURS` |
| 11 | `bed_status` | D | ~1,700 | `OURS`, HSE vocabulary |
| 12 | `clinic_sessions` | D | ~800 | `OURS` |
| 13 | `cancellation_events` | E | ~1,500 | National specification, cancellation codes |
| 14 | `suspension_events` | E | ~200 | National specification, suspension codes |
| 15 | `ref_specialty` | F | 7 | National specification, specialty codes |
| 16 | `ref_codes` | F | ~120 | National specification, thirteen code lists |
| 17 | `ref_rules` | F | 5 | National outpatient protocol |
| — | `ground_truth` | G | ~8,000 | Outcome codes from the national specification; risk model `OURS`. Never loaded. |

Row counts assume roughly 2,000 active referrals per public hospital over a two-week simulated period with daily snapshots. They are estimates for planning, not targets.

### Written out

These are not generated. They start empty and fill as the system runs. Described in section 8.

| # | Table | Written by | Rows per run, roughly |
|---|---|---|---|
| 18 | `agent_scores` | urgency and capacity agents | 2 per referral |
| 19 | `agent_citations` | urgency and capacity agents | 4 to 6 per referral |
| 20 | `decisions` | coordinator | 1 per hospital per day |
| 21 | `decision_rankings` | coordinator | 1 per referral |
| 22 | `decision_citations` | coordinator | 3 to 5 per referral |
| 23 | `rule_checks` | rule checker | 2 to 5 per referral |
| 24 | `overrides` | clinician, through the interface | as many as they make |

**24 tables in total: 17 loaded in, 7 written out.**

Inputs never change. Outputs are only ever appended to. That is what makes it possible to reconstruct any past ranking exactly, and it is the whole basis of the audit trail.
