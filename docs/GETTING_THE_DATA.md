# Getting the Data

How to get a working database on your laptop, and why it is arranged this way.

Companion documents: `DATASET_README.md` (what the data means), `docs/VERIFY_IN_PGADMIN.md`
(how to check your install by hand).

---

## Contents

1. [What lives where](#1-what-lives-where)
2. [Three commands](#2-three-commands)
3. [Sample and full](#3-sample-and-full)
4. [Why the sample is a slice and not the first few rows](#4-why-the-sample-is-a-slice-and-not-the-first-few-rows)
5. [Switching to the full dataset](#5-switching-to-the-full-dataset)
6. [When it goes wrong](#6-when-it-goes-wrong)

---

## 1. What lives where

Three things are versioned separately, and a single file joins them.

| What | Where | How often it changes |
|---|---|---|
| **Schema** | Git, as numbered migration files | Rarely, and reviewed |
| **Data** | Hugging Face, as tagged releases | Often |
| **Code** | Git | Constantly |

`versions.yml` is the join:

```yaml
schema_version: "007"
data_version: "v1.0"
hf_repo: "Thabang/irish-referral-prioritisation"
hf_revision: "v1.0"        # a tag, never a branch
default_profile: "sample"
```

**Nothing ever fetches "latest".** `hf_revision` is a git tag on the Hugging Face
repository. If it said `main`, then two people running the same command on the same day
could get different data and neither would know. A tag means the version you loaded is
the version you can name.

The dataset is private. Put a Hugging Face token in your `.env` as `HF_TOKEN` before you
start. It is never written to disk by any script here and never committed — `.env` is
git-ignored.

---

## 2. Three commands

```bash
cp .env.example .env     # once
make up                  # start Postgres and pgAdmin
make load                # migrate, seed, fetch from Hugging Face, load
```

That is it. `make load` does four things in order, and each one is also available on its
own if you need it:

| Command | What it does |
|---|---|
| `make migrate` | Applies `db/migrations/*.sql` in filename order |
| `make seed` | Loads the three dictionary tables from `db/seeds/` |
| `make fetch` | Downloads the pinned revision from Hugging Face into `data/` |
| `make load` | All three, then loads the CSVs into Postgres |

Postgres is on **`localhost:5433`**, not 5432. Many people already have a Postgres on
5432 and the clash costs an hour on day one.

pgAdmin is at **http://localhost:5050**, and the server connection is already there when
you log in. You do not need to add it.

To confirm everything worked:

```bash
make verify
```

Seven checks, reported as nine assertions. The seventh one passes by *failing* — see section 6.

---

## 3. Sample and full

There are two slices of the same data.

| Profile | Size | Referrals | What it is for |
|---|---|---|---|
| **`sample`** | ~1.3 MB | ~600 | The default. Checking that the pipeline works. |
| `full` | ~11 MB | ~5,200 | Real runs, evaluation, anything you will present. |

`make load` pulls **`sample`**, because most of the time you are checking that something
works rather than measuring anything. Downloading eleven megabytes to find out whether
your migrations applied is a slow way to learn a fast fact.

Only the files for the profile you asked for are transferred. Asking for `sample` does
not download the full data and then discard it — it never requests it at all.

The sample is a real slice of the published data, not a separate generation. It is
derived from `full` by `scripts/make_sample.py`, so anything true of the sample is true
of the full dataset. It contains:

- All seven planted demo cases, `PW-DEMO-01` through `PW-DEMO-07`
- The planted cross-hospital pathway-number collision
- 300 ordinary referrals from each of the two public hospitals it covers, `9001` and `9002`
- Every child row belonging to those referrals, and every parent row they need
- All three dictionary tables, whole

---

## 4. Why the sample is a slice and not the first few rows

This is the part worth understanding, because the obvious approach fails in a way that
wastes your afternoon.

Every table describing a referral — `conditions`, `observations`, `triage_events`,
`cancellation_events`, `suspension_events` — has a foreign key pointing at
`core.referrals`. So the tables are not independent lists that can each be shortened.

Take the first 5,000 rows of each file and you get a set of observations belonging to
referrals that are not in your slice. Postgres refuses them, and the load stops partway
through with a foreign key violation. The error names a constraint, so it reads like a
schema problem. It is not. It is a sampling problem, and the error message points in
entirely the wrong direction.

So the sample is built the other way round:

```
1. Choose the referrals        the 7 demo cases, the planted collision,
                               and 300 each from hospitals 9001 and 9002
2. Take all their children     every referral_daily row for every day,
                               every observation, condition, triage event,
                               cancellation and suspension
3. Take the parents they need  the patients those referrals belong to, the
                               persons those patients are, the hospitals and
                               services involved
4. Take the capacity           wards, ward-specialty allocations, bed status
                               and clinic sessions for those hospitals
5. Take the dictionaries whole about 130 rows between them; slicing them
                               would only punch holes for no saving
```

The result is **closed**: every foreign key in the sample resolves inside the sample.
`tests/test_sample_closure.py` asserts exactly that, so if the sampler ever breaks you
find out from a test naming the sampler, rather than from Postgres naming a constraint.

The selection is deterministic — referrals sorted by `pathway_number`, then the first
300 — so the same full dataset always produces the same sample.

---

## 5. Switching to the full dataset

```bash
make load FETCH_PROFILE=full
```

One command. `make load` runs fetch and load together, and both take `FETCH_PROFILE`,
so passing it to `make fetch` alone would download the full set and then load the
sample over it.

It costs about 11 MB of download and roughly 70 MB in Postgres once indexes are built.
Both are small. Use `full` whenever you are measuring something rather than checking
that something runs.

**Use `full` for anything you will present.** The sample covers two of the six
hospitals, both large and both public: 9001 St Brendan's (640 beds) and 9002 Kilbrannan
(420 beds). The full set adds 9003 Ardfinnan (280) and 9004 Loughrea (110), plus the two
private sites. The regional variation between a teaching hospital and a district one is
part of what the dataset exists to show, and a two-hospital slice cannot show it.

---

## 6. When it goes wrong

| Symptom | Cause | Fix |
|---|---|---|
| Specialty `0601` is missing | Leading zeros lost | Read CSVs with `dtype=str` |
| Routine ranks above Semi-Urgent | Sorted on `code_value` | Sort on `severity_rank` |
| Two patients merged into one | Joined on `patient_id` alone | Always `hospital_hipe` **and** `patient_id` |
| Breach counts look too high | Used the raw wait | Use `adjusted_wait_days` |
| Foreign key violation loading observations | `referrals` not derived first | Follow `LOAD_ORDER` exactly |
| pgAdmin cannot connect | Used `localhost:5433` | From inside Docker it is `db:5432` |
| Port 5432 already in use | An existing local Postgres | Already handled — we use 5433 |
| `make fetch` fails on a private repo | No token | Set `HF_TOKEN` in `.env` |

**Two things that look like bugs and are not.**

Query 7 in `make verify` and in `docs/VERIFY_IN_PGADMIN.md` **fails on purpose**:

```sql
SET ROLE agent_rw;
SELECT count(*) FROM eval.ground_truth;   -- ERROR: permission denied
```

`eval.ground_truth` is the answer key. If an agent could read it, it would rank perfectly
by looking up the answer and the whole evaluation would mean nothing. The database
refuses the read, so the guarantee is a property of the system rather than something
everyone has to remember. **The error is the pass.**

And `make fetch` will not quietly generate data locally when it cannot reach Hugging
Face. It stops and tells you why. Data that silently differs between team members is the
exact failure this arrangement exists to prevent, and it is much harder to notice than a
download that failed.
