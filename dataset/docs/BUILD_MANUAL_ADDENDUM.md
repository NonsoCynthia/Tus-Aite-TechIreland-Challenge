# Addendum to the Build Manual

Read this alongside `BUILD_MANUAL.md` and `DATASET_README.md`.

Where this document and the build manual disagree, **this document wins**. Everything in the manual not mentioned here stands unchanged.

There are eleven items. Items 4 and 5 change the phase order, so read all of this before starting Phase 1.

---

## 1. Docker is already installed

The manual's Phase 0 asks you to check prerequisites. Docker Desktop is installed on this machine.

Run `docker system df` to confirm the daemon is running. If it is not, say so once and wait for it to be started. Do not attempt to install Docker, do not suggest alternatives, and do not treat this as a prerequisite failure.

---

## 2. The manual is missing two files. Add them.

Section 5.2 of the manual declares a `loader` service with `build: .`, but section 3's repository structure lists no `Dockerfile` and no requirements file. As written, `make migrate` cannot run.

Add both at the repository root.

**`Dockerfile`**

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
```

**`requirements.txt`**

```
psycopg[binary]>=3.1
huggingface_hub>=0.24
pyyaml>=6.0
pandas>=2.2
numpy>=1.26
simpy>=4.1
pytest>=8.0
```

Pin these versions in the committed file once you have a working install. Unpinned dependencies undermine the determinism guarantee in section 8.5 of the manual.

---

## 3. One query in the manual is truncated

Section 10.2 of the manual ends with an incomplete statement:

```sql
SELECT count(*) FROM (
  SELECT pathway_number, count(DISTINCT hospital_hipe) n
  FROM core.referrals GROUP BY 1) x WHERE n > 1 AND ...;  -- collisions allowed, merges not
```

Its intent: a pathway number **may legitimately repeat across hospitals**, because pathway numbers are issued per hospital and are not globally unique. What must never happen is two hospitals' referrals being merged into one patient by a join that forgot the hospital code.

Write the test as an assertion that no join anywhere merges across hospitals. Specifically, assert that for every child table, joining on `(hospital_hipe, pathway_number)` returns the same row count as the child table itself, and that joining on `pathway_number` alone returns *more* rows. The second half is the interesting one: if joining on the pathway number alone does **not** produce extra rows, your test data has no cross-hospital collisions in it and the test is proving nothing. In that case, plant one.

---

## 4. NEW Phase 3b — Calibration. Runs after seeds, before the generator.

**This is the most important item in this document.**

The manual creates `generator/calibration/` with three filenames and never says what goes in them. Without this phase you would invent plausible-looking numbers, and the dataset would be structurally perfect and distributionally fictional.

### Why this matters

The manual sets a target: the correlation between `news2` and `severity_rank` must land between 0.35 and 0.65. That band is a **guard rail on a fitted distribution**. It is not a number to tune toward. If you search parameter space for whatever hits 0.50, you have optimised against your own test and the resulting distributions came from nowhere.

Fit first. Measure second.

### What to download

Three sources. All free, all public, none require an account, an application, or a waiting period. Download them at the start of this phase.

**a) `vitals_by_category.yml` — from MIMIC-IV-ED Demo**

- URL: https://physionet.org/content/mimic-iv-ed-demo/2.2/
- Licence: Open Data Commons Open Database License. 100 patients, roughly 111 KB. No credentialing.
- Note: the **full** MIMIC-IV-ED requires PhysioNet credentialing and training. The **demo** subset does not. Use the demo. Do not attempt to register for the full dataset.

Read the `triage` table. Group by `acuity` (the Emergency Severity Index, 1 to 5). For each group, measure the mean and standard deviation of `heartrate`, `resprate`, `temperature`, `o2sat`, `sbp`, `dbp` and `pain`.

Map the acuity scale onto our triage categories:

| MIMIC acuity | Our category | Our code |
|---|---|---|
| 1–2 | Urgent | 1 |
| 3 | Semi-Urgent | 3 |
| 4–5 | Routine | 2 |

Record the measured values with a comment naming the source.

**One deliberate modelling decision, which you must document in the file.** The coupling between vitals and category in our generated data must be set **weaker** than MIMIC's measured coupling.

The reason: MIMIC's acuity is assigned by a nurse at the bedside who is looking at the patient and partly using the vitals themselves. Ireland's Clinical Prioritisation Category is assigned by a clinician reading a referral letter, often without ever having seen the patient. So the real Irish relationship between physiology and assigned urgency is necessarily looser. A weaker coupling is the clinically correct claim, not a modelling convenience.

Introduce a single parameter, `coupling_coefficient`, that scales the between-category mean separation. Everything else stays at the MIMIC-fitted values.

**b) `specialty_mix.yml` — from NTPF open data**

- URL: https://www.ntpf.ie/waiting-list-data/open-data/
- Direct CSV download, free, no account.

Take the most recent outpatient-by-specialty file. Extract the proportion of the national waiting list falling in each of our seven specialties, and the distribution across wait-time bands.

Important caveat to record in the file: statistical disclosure control aggregates counts below 20 into a "Small Volume" category. Exclude those rows when computing proportions, and note that you did.

**c) `length_of_stay.yml` — from ESRI report RS213**

- URL: https://www.esri.ie/system/files/publications/RS213.pdf

Extract inpatient average length of stay and inpatient occupancy rates. Use these to parameterise the SimPy bed model so that occupancy moves realistically rather than being a fixed number.

If any of the three downloads fails, **stop and report which one**. Do not substitute invented numbers and continue.

### Only one source is row-level. Understand the difference.

| Source | Granularity | What you can do with it |
|---|---|---|
| MIMIC-IV-ED Demo | **Row-level**, 100 real patients | Fit real distributions, including within-group spread |
| NTPF open data | Aggregate counts | Match proportions only |
| ESRI RS213 | Aggregate | Match occupancy and length-of-stay parameters |
| HIPE published tables | Aggregate | Match diagnosis and age mix |
| HSE daily report | Aggregate, daily | Match the occupancy curve and delayed transfers |

**No Irish source publishes patient-level waiting list data.** It does not exist publicly and cannot be obtained within this timeline. There are no Irish rows to copy, only Irish shapes to match. Do not go looking for an Irish patient-level dataset. If you find something that appears to be one, it is either not Irish or not real.

MIMIC is the only row-level source and it is the one that matters, because it is the only place you can observe how real nurse-assigned urgency relates to real vitals, including how often they disagree.

### Every parameter must declare its provenance

At the top of each calibration YAML, include a `provenance` block. Then label **every individual parameter** as exactly one of three kinds. Nothing may be left unlabelled.

```yaml
provenance:
  source: MIMIC-IV-ED Demo v2.2
  url: https://physionet.org/content/mimic-iv-ed-demo/2.2/
  licence: ODbL
  granularity: row-level, n=100
  retrieved: <date>

parameters:
  urgent_heartrate_mean:
    value: 96.4
    kind: fitted          # measured directly from the source

  coupling_coefficient:
    value: 0.62
    kind: modelled        # a deliberate choice with a stated reason
    reason: >
      MIMIC acuity is assigned at the bedside partly from the vitals themselves.
      Irish CPC is assigned by a clinician reading a referral letter, often
      without seeing the patient. The relationship must therefore be weaker
      than MIMIC's measured coupling.

  gp_triage_disagreement_rate:
    value: 0.18
    kind: assumed         # no published source exists
    note: >
      No source publishes how often GP-assigned priority and the triage
      category differ. This is a placeholder and must be flagged as
      unvalidated wherever results depend on it.
```

**Three parameters have no source at all and must be marked `assumed`:**

1. **Condition mix within each specialty.** HIPE aggregates cover part of it; the rest requires clinical judgement we do not have. Use a plausible spread, mark it assumed.
2. **The rate at which GP priority and triage category disagree.** Nothing published. Mark it assumed.
3. **The `latent_hazard` model** in `ground_truth`. Already documented as unvalidated in `DATASET_README.md` section 7.18. Mark it assumed and keep the large noise term described there.

### Then the calibration sweep

Only after the fitting above is done, sweep `coupling_coefficient` across a range and measure the resulting correlation each time. Everything else in the vitals model stays fixed at the MIMIC-fitted values.

Select the coefficient whose measured correlation is nearest 0.50 **and** which satisfies the manual's section 10.4 requirement that at least 15 percent of urgent referrals have `news2 <= 2`. That second condition exists because a suspected melanoma is urgent because of the referral pathway, not the physiology, and the dataset must contain such patients.

Confirm the chosen value still holds the band at full scale. Correlation measured on a few hundred rows is noisy; on a hundred thousand it is not.

---

## 5. Do not use the Gretel patient-events dataset

If you encounter `gretelai/gretel-patient-events-v1` referenced anywhere, ignore it. It was evaluated and rejected.

It is built from published case reports, carries no triage category, no structured vitals in the shape we need, no waiting list concept and no bed data. Its case mix is rare-and-dramatic rather than routine, which is the opposite of what a waiting list contains. It does not fit this schema.

---

## 6. The small generator profile needs a second public hospital

If your profile configuration uses a small profile containing only hospital `9001` and a private site, two of the seven planted demo cases cannot exist.

`PW-DEMO-06` and `PW-DEMO-07` (manual section 8.4) are the multi-list-across-two-hospitals cases. They require at least two **public** hospitals. Private sites have zero referrals by design (`DATASET_README.md` section 10.4), so they cannot supply the second list.

Fix: include `9002` in the small profile.

```yaml
small: { hospitals: ["9001", "9002", "9101"], days: 3, referrals_scale: 0.04 }
```

And state explicitly in `test_planted_cases.py` which profile it expects to run against.

---

## 7. Pre-provision the pgAdmin server connection

The manual's `make reset` runs `docker compose down -v`, which removes **all** named volumes including `pgadmin_data`. Every reset therefore wipes the saved server connection, and a teammate must re-enter it by hand.

That matters because the host and port are the single most common mistake here. From inside the Docker network the database is `db:5432`. From the laptop it is `localhost:5433`. Nearly everyone gets this wrong at least once.

Fix: add `db/pgadmin/servers.json` defining the connection, and mount it into the pgadmin service at `/pgadmin4/servers.json`. The server then appears automatically on first login and survives every reset.

Keep `docs/VERIFY_IN_PGADMIN.md` as specified in manual section 12, but note in it that the connection is pre-configured, and keep the host/port explanation for anyone adding one manually.

---

## 8. Check determinism at the full profile too

The manual's Phase 4 acceptance check generates twice and compares SHA-256 hashes. Run that check at **both** the small and full profiles.

Unstable iteration order and unseeded randomness surface at scale, not on a few hundred rows. If the full-profile output is not byte-identical across two runs, do not publish anything until it is.

---

## 9. Do not choose the licence

Leave the `license` field in the Hugging Face dataset card as `TODO`. Publish the dataset **private**. Ask before making it public or setting a licence.

A licence is awkward to change after publication, and this is not your decision.

Everything else in manual section 11.2 stands, including the synthetic-data statement, which must appear near the top of the card and be unmistakable.

---

## 10. ~~The graph layer is not a conflict. Do not raise it.~~ SUPERSEDED

> **SUPERSEDED.** This instruction asked for a paragraph in the repository README
> explaining the relationship to the graph layer. That paragraph has been removed and this
> section no longer applies.
>
> The reasoning that replaced it: this branch is scoped to the data, and the README should
> describe only what the branch builds. Naming the graph layer here imports a concern that
> belongs to the branches implementing it, and gives a newcomer a product tour instead of a
> path to the data. The substance of the instruction still holds — PostgreSQL is the
> generation and storage layer, RDF conversion is a downstream transform owned by the graph
> track — it simply does not need saying in this README.
>
> The rest of the section is kept below as the record of what was originally specified.

You may notice that `conductor/tech-stack.md` specifies Oxigraph, RDF and SPARQL, while this build uses PostgreSQL. This is **not** a contradiction and **not** an open item.

PostgreSQL is the generation and storage layer. RDF and SPARQL remain the team's stack for the graph work. Converting the relational tables into RDF is a downstream transform owned by the graph track, and the team will handle any preprocessing they need.

Do not modify `conductor/tech-stack.md`. Do not create a decision document. Do not raise this as a blocker or an open item in your report.

Add one paragraph to the repository README, under a heading such as "Relationship to the graph layer":

> This repository produces and stores the dataset in PostgreSQL. The graph layer described in `conductor/tech-stack.md` consumes it from there. Converting the relational tables to RDF is a downstream transform owned by the graph track, not by this repository. The relational schema is designed to make that transform straightforward: every table has an explicit primary key, all foreign keys are declared, and the agent output tables in the `agent` schema carry provenance on each row rather than in a side channel.

That is all this needs.

---

## 11. What to report when you finish

In addition to manual section 15, report:

1. **The measured correlation** between `news2` and `severity_rank`, at both profiles
2. **The chosen `coupling_coefficient`** and the range you swept
3. **The provenance split** — how many calibration parameters ended up `fitted`, how many `modelled`, how many `assumed`

On that last point: if more than a third of parameters are `assumed`, say so prominently. That is a signal the grounding is thinner than intended, and it needs to be known before any of this reaches a presentation.

Also report anything in this addendum or the manual that you could not follow, and what you did instead. A documented deviation is fine. An undocumented one is not.
