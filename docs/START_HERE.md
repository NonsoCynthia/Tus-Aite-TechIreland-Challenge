# Start Here

The first thing to read. Everything else can wait.

---

## a. What this is

This repository builds a **synthetic Irish hospital outpatient waiting list** — patients
waiting for a clinic appointment, what is wrong with them, how urgent a clinician judged
them, and how full the hospital's wards and clinics are.

**Every record is invented.** No real patient, clinician or hospital appears anywhere in
it. The hospital names are made up and their codes use a reserved range that matches no
real facility.

By the end of this page you will have a database running on your own machine holding
about **21,000 rows** of that data, and a web tool for looking at it. That is the
*sample*, which is what the three commands below give you and is enough for most work.
The full set is about five times larger — section f explains how to get it and when you
need it.

---

## b. What you need before you start

| | |
|---|---|
| **Docker Desktop**, installed and running | [docker.com/get-started](https://www.docker.com/get-started/). "Running" means the whale icon is in your menu bar and not greyed out. |
| **A Hugging Face account** | Free, at [huggingface.co/join](https://huggingface.co/join). This is where the data lives. |
| **An invitation to the dataset** | It is private. Ask the dataset owner (**Thabang**, GitHub `ThabangIsaac1`) to invite your Hugging Face username — post in the team channel if you do not have them directly. See [HUGGINGFACE_ACCESS.md](HUGGINGFACE_ACCESS.md). |

You do not need to know Python, SQL, or Docker beyond starting the app.

**Waiting on the invitation?** You are not stuck. `make generate PROFILE=small` builds a
small dataset locally with no Hugging Face account at all, and everything from section e
onwards then works against it. It will not be byte-identical to the published release, so
use the real data for anything you report — but it unblocks you for setup and for reading
the code.

---

## c. Setting up your credentials

Copy `.env.example` to `.env`, then edit the values below. **The `.env` file is never
committed to git, so your passwords stay on your machine.**

```bash
cp .env.example .env
```

Now open `.env` in any text editor and set these:

| What | Where it goes | Where you get it | What breaks without it |
|---|---|---|---|
| `POSTGRES_USER` | `.env` | Already set to `triage_admin` — leave it | Database will not start |
| `POSTGRES_PASSWORD` | `.env` | Change it to anything you like — local-only, never leaves your machine | Database will not start |
| `POSTGRES_DB` | `.env` | Already set to `triage` — leave it | Database will not start |
| `POSTGRES_PORT` | `.env` | `5433` by default. Change only if that port is already taken on your machine | Port conflict error on `make up` |
| `PGADMIN_EMAIL` | `.env` | Any email address — it is only a login name, nothing is sent to it | Cannot log in to pgAdmin |
| `PGADMIN_PASSWORD` | `.env` | Change it to anything you like | Cannot log in to pgAdmin |
| `PGADMIN_PORT` | `.env` | `5050` by default. Change only if that port is taken | pgAdmin will not open |
| `HF_TOKEN` | `.env` | **Your own** read token — see [HUGGINGFACE_ACCESS.md](HUGGINGFACE_ACCESS.md) | Download fails with a permission error |
| `HF_DATASET_REPO` | `.env` | Already set — leave it | Nothing; it is informational |

The Postgres and pgAdmin passwords are **local-only**. The database is reachable from
your own machine and nowhere else, so these are not secrets in the security sense — but
they still live in `.env` and never in a committed file.

> **If you change `POSTGRES_USER` or `POSTGRES_DB`**, also update
> `db/pgadmin/servers.json`, which has them written in. A test will fail if the two
> disagree, so you will find out immediately rather than through a confusing login error.

---

## d. Three commands

```bash
cp .env.example .env      # then edit it — see the table above
make up                   # starts the database and pgAdmin
make load                 # downloads the data and loads it in
```

| Command | Takes | You should see |
|---|---|---|
| `make up` | 10–60s first time, then ~5s | `Postgres on localhost:5433` and `pgAdmin on http://localhost:5050` |
| `make load` | 1–2 minutes first time | A list of table names with row counts, ending `loaded 21,348 rows across 17 tables from 'sample'` |

The first `make up` downloads about 700 MB of Docker images. That happens once.

To check everything worked:

```bash
make verify
```

Expect `9 passed, 0 failed`. That is **seven checks, nine assertions** — check 1 tests
three schemas separately. Check 7 passes **by failing** — see below.

---

## e. Looking at the data

1. Open **http://localhost:5050**
2. Log in with the `PGADMIN_EMAIL` and `PGADMIN_PASSWORD` you put in `.env`
3. In the left sidebar, **Triage local** is already there. Expand it. It will ask for the
   password — that is your `POSTGRES_PASSWORD`.
4. Expand `Databases → triage → Schemas → core → Tables`

**You do not need to add a server. It is already configured.**

> **If you ever do add one by hand**, this is the single most common mistake in the
> project: from *inside* Docker the database is host **`db`**, port **`5432`**. From a
> tool running on *your own machine* it is host **`localhost`**, port **`5433`**.
> pgAdmin runs inside Docker, so it uses `db:5432`.

Three queries to try. Right-click the `triage` database → Query Tool, and paste:

```sql
-- How many patients are waiting, by urgency?
SELECT c.description, count(*)
FROM core.triage_events t
JOIN core.ref_codes c ON c.code_table='triage_category'
                     AND c.code_value = t.triage_category::text
GROUP BY c.description, c.severity_rank
ORDER BY c.severity_rank;
```

```sql
-- One patient's full picture
SELECT pathway_number, as_of_date, days_since_referral,
       adjusted_wait_days, triage_status
FROM core.referral_daily
WHERE pathway_number = 'PW-DEMO-01'
ORDER BY as_of_date;
```

```sql
-- How full are the wards?
SELECT ward_id, snapshot_datetime, occupied, free, occupancy_pct, gar_status
FROM core.bed_status
ORDER BY snapshot_datetime DESC, ward_id
LIMIT 10;
```

More, with expected results, in [VERIFY_IN_PGADMIN.md](VERIFY_IN_PGADMIN.md).

---


> **Schema 008 requires data v1.1 or later.** Migration 008 asserts that the stored
> wait counts equal their date arithmetic, and two planted referrals in `v1.0` violate
> it. Loading `v1.0` against schema 008 fails with a `rd_counts_match_dates` check
> violation. If you are pinned to `v1.0`, stay on schema 007. See
> `docs/CALIBRATION_FINDINGS.md` §7.4.

## f. Sample versus full

You get the **sample** by default: about 1.3 MB, 609 referrals, 21,348 rows. It is fast
and it is enough for most work.

The **full** set is about 11 MB, 5,200 referrals, 103,363 rows.

```bash
make load FETCH_PROFILE=full
```

One command — it downloads the full set **and** loads it. Passing `FETCH_PROFILE` to
`make fetch` alone would download the full data and then load the sample, which is not
what you want.

The download costs about 11 MB and roughly 70 MB once it is in the database. Both are
small.

**Use `full` for anything you will show people.** The sample covers two of the six
hospitals, and both are large and public: 9001 St Brendan's (640 beds) and 9002
Kilbrannan (420 beds). The full set adds 9003 Ardfinnan (280 beds), 9004 Loughrea (110
beds) and the two private sites. The contrast between a teaching hospital and a district
one is part of what the data exists to show, and a two-hospital slice cannot show it.

Why the sample is a proper slice and not just the first few rows is explained in
[GETTING_THE_DATA.md](GETTING_THE_DATA.md) — the short version is that the tables
reference each other, so a naive slice will not load.

---

## g. Starting over

```bash
make reset
```

Wipes the database and reloads it from scratch. Takes about two minutes.

**This is safe and you cannot break anything permanently.** It only removes this
project's own database — no other Docker project on your machine is touched, and the data
is re-downloaded from Hugging Face. Run it any time something looks wrong.

---

## h. When something goes wrong

| What you see | What happened | Fix |
|---|---|---|
| `Cannot connect to the Docker daemon` | Docker Desktop is not running | Start Docker Desktop and wait for the whale icon |
| `port is already allocated` | Something else is using 5433 or 5050 | Change `POSTGRES_PORT` or `PGADMIN_PORT` in `.env`, then `make up` |
| `401 Client Error` / `Repository Not Found` on `make load` | `HF_TOKEN` is missing, wrong, or you have not been invited | Check the token in `.env`; ask Thabang to invite you. See [HUGGINGFACE_ACCESS.md](HUGGINGFACE_ACCESS.md) |
| `password authentication failed` in pgAdmin | Wrong password, or you changed `POSTGRES_USER` without updating `servers.json` | Use `POSTGRES_PASSWORD` from `.env`; see the note in section c |
| pgAdmin says `could not translate host name "localhost"` | You added a server by hand using `localhost` | Use host `db`, port `5432` — pgAdmin runs inside Docker |
| `make: *** No rule to make target` | You are not in the repository root | `cd` into the folder containing `Makefile` |
| `Conflict. The container name "/triage_db" is already in use` | Another copy of this project is already running — a second clone, or an old one you forgot | `docker compose down` in the other copy first. The container names are fixed, so only one instance can run at a time on a machine. |
| `permission denied for schema eval` | **Nothing. This is correct.** | See below |

### The error that is supposed to happen

```sql
SET ROLE agent_rw;
SELECT count(*) FROM eval.ground_truth;   -- ERROR: permission denied for schema eval
```

`eval.ground_truth` is the answer key: which patients actually deteriorated while
waiting. If the ranking system could read it, it would score perfectly by looking up the
answer and the whole exercise would prove nothing. The database refuses the read, so the
guarantee holds by construction rather than by everyone remembering.

**That error is the test passing.** Please do not file it as a bug.

---

## Where to go next

| Document | What it covers |
|---|---|
| [HUGGINGFACE_ACCESS.md](HUGGINGFACE_ACCESS.md) | Getting your token, and how access is managed |
| [GETTING_THE_DATA.md](GETTING_THE_DATA.md) | Sample vs full in depth, and why the sample is closed |
| [VERIFY_IN_PGADMIN.md](VERIFY_IN_PGADMIN.md) | Seven queries that prove the install is good |
| [../DATASET_README.md](../DATASET_README.md) | What every table and column means. The specification. |
| [CALIBRATION_FINDINGS.md](CALIBRATION_FINDINGS.md) | Where the numbers came from, and what the data disproved |
| [BUILD_MANUAL.md](BUILD_MANUAL.md) + [addendum](BUILD_MANUAL_ADDENDUM.md) | The original specification. Code comments cite it by section. |
