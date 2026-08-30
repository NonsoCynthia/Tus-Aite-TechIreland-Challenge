# Getting the Data

Everything needed to go from an empty machine to a database you can query.

Companion documents: [`DATASET_README.md`](../DATASET_README.md) for what the data means,
[`HOW_THE_DATA_WAS_MADE.md`](HOW_THE_DATA_WAS_MADE.md) for where it came from.

---

## 1. What you need

Docker Desktop, running. A Hugging Face account. And access to the dataset, which is
gated: the page is public but the files are not, and Thabang approves each person
individually.

### Getting access

1. Open
   [huggingface.co/datasets/Thabang/irish-referral-prioritisation](https://huggingface.co/datasets/Thabang/irish-referral-prioritisation)
   while logged in, and click **Request access**. It has to be done in a browser. There is
   no way to request it from a script.
2. You will share your username and email address. Thabang approves it.
3. Ask before you request if you are unsure whether you should have it. A rejected request
   is final and cannot be made again.

### Your token

Once approved, make your own **read** token at
[huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) and put it on the
`HF_TOKEN` line of your `.env`. Name it something you will recognise later, like
`triage-dataset-read`.

## 2. Three commands

```bash
cp .env.example .env      # then edit it, see below
make up                   # Postgres and pgAdmin, ~1 min the first time
make load                 # downloads and loads, ~1 min
```

`make load` ends with `loaded 21,348 rows across 17 tables from 'sample'`.

### What goes in `.env`

`.env` is git-ignored, so your values stay on your machine.

| | Set it to |
|---|---|
| `HF_TOKEN` | Your own read token from step 1. Nothing works without it. |
| `POSTGRES_PASSWORD`, `PGADMIN_PASSWORD` | Anything you like. Local-only. The database is not reachable from outside your machine. |
| `PGADMIN_EMAIL` | Any address. It is only a login name. |
| Everything else | Leave it. |

If you change `POSTGRES_USER` or `POSTGRES_DB`, also change `db/pgadmin/servers.json`,
which has them written in. A test fails if the two disagree, so you find out immediately
rather than through a login error.

## 3. Looking at it

Open **http://localhost:5050**, log in with your `PGADMIN_EMAIL` and `PGADMIN_PASSWORD`.
**Triage local** is already in the sidebar. Expand it and give it your
`POSTGRES_PASSWORD`. Then `Databases → triage → Schemas → core → Tables`.

You do not need to add a server. But if you ever add one by hand, this is the mistake
almost everyone makes once:

| Connecting from | Host | Port |
|---|---|---|
| pgAdmin, which runs **inside** Docker | `db` | `5432` |
| A tool on **your own** machine | `localhost` | `5433` |

Same database, two addresses.

## 4. Checking it worked

```bash
make verify        # 9 passed, 0 failed
```

Seven checks, nine assertions. The first one tests three schemas separately.

Three worth running by eye, in the pgAdmin query tool:

```sql
-- Everything loaded: expect core 18, agent 7, eval 1
SELECT table_schema, count(*) FROM information_schema.tables
WHERE table_schema IN ('core','agent','eval') GROUP BY 1 ORDER BY 1;

-- Urgency sorts correctly: expect Urgent, Semi-Urgent, Routine, Excluded
SELECT description, severity_rank FROM core.ref_codes
WHERE code_table='triage_category' ORDER BY severity_rank NULLS LAST;

-- The answer key is unreachable: expect an ERROR
SET ROLE agent_rw; SELECT count(*) FROM eval.ground_truth; RESET ROLE;
```

**That last error is the test passing.** `eval.ground_truth` records which patients
actually deteriorated. If the ranking system could read it, it would score perfectly by
looking up the answer. The database refuses, so the guarantee holds by construction rather
than by everyone remembering. Do not file it as a bug.

Sorting on `code_value` instead of `severity_rank` is the other trap: the real codes are
Urgent 1, Routine 2, Semi-Urgent **3**, so sorting by code puts Routine ahead of
Semi-Urgent, silently.

## 5. Sample and full

| | Size | Hospitals | Referrals |
|---|---|---|---|
| **`sample`** (the default) | 1.3 MB | 2, both public | 609 |
| `full` | 11 MB | 6: 4 public, 2 private | 5,200 |

```bash
make load FETCH_PROFILE=full
```

Only the profile you ask for is downloaded; `sample` never fetches the full data at all.

**Use `full` for anything you show people.** The sample covers the two largest hospitals,
so the contrast between a 640-bed teaching hospital and a 110-bed district one, which is
part of what the data exists to show, is not in it. The private sites are capacity only
and carry no referrals by design; patients reach them through a suspension, which pauses
their waiting clock.

The sample is a real slice of the published data, not a separate generation, so anything
true of it is true of the full set. It is **closed under the foreign keys**: every table
describing a referral points back at `core.referrals`, so taking the first N rows of each
file gives you observations belonging to referrals that are not there, and the load dies
on a constraint violation *after* the download. Instead the sample picks a set of
referrals and takes every child row and every parent they need. It carries all seven
planted demo cases.

## 6. Starting over

```bash
make reset        # wipes and reloads, ~2 min
```

Safe. It removes only this project's own database. The compose project name is pinned, so no
other Docker project on your machine is in scope, and the data comes back from Hugging
Face.

## 7. When it goes wrong

| What you see | Fix |
|---|---|
| `Cannot connect to the Docker daemon` | Start Docker Desktop |
| `port is already allocated` | Change `POSTGRES_PORT` or `PGADMIN_PORT` in `.env` |
| `401`, `403` or `GatedRepoError` on `make load` | One of: no `HF_TOKEN` in `.env`, a wrong or deleted token, or your access request is still pending. Open the dataset page in a browser: if it shows a request form, you are not approved yet |
| `password authentication failed` in pgAdmin | Use `POSTGRES_PASSWORD` from `.env`; if you changed `POSTGRES_USER`, update `db/pgadmin/servers.json` too |
| `could not translate host name "localhost"` | You added a server by hand. Use `db:5432`. See section 3 |
| `container name "/triage_db" is already in use` | Another copy of this project is running. `docker compose down` there first |
| `rd_counts_match_dates` violation on load | You are loading data `v1.0` against schema 008. They are incompatible. Pin `v1.1` |
| `permission denied for schema eval` | Correct. See section 4 |

`make load` will not quietly generate data locally when it cannot reach Hugging Face. It
stops and says why. Two people silently holding different data is much harder to notice
than a download that failed, and much worse when someone presents a result from it.

## 8. Versions

`versions.yml` pins schema, data and code together:

```yaml
schema_version: "008"
data_version:   "v1.1"
hf_revision:    "v1.1"     # a tag, never a branch
```

**Nothing fetches "latest".** A tag means the version you loaded is one you can name. If
this said `main`, two people running the same command on the same day could get different
data and neither would know.

Schema 008 and data `v1.0` are incompatible: 008 asserts the stored wait counts equal
their date arithmetic, and two planted referrals in `v1.0` break that. If you are pinned
to `v1.0`, stay on schema 007.
