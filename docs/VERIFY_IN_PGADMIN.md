# Verifying Your Install in pgAdmin

Seven queries that prove the database is good. Run them by hand after `make load`.

If you would rather not click, `make verify` runs equivalent checks from the terminal and
prints `9 passed, 0 failed` — seven checks, nine assertions, because check 1 tests the
three schemas separately.

---

## Connecting

**The server connection is already configured.** Open pgAdmin, and *Triage local* is in
the sidebar waiting for you.

1. Open **http://localhost:5050**
2. Log in with `PGADMIN_EMAIL` and `PGADMIN_PASSWORD` from your `.env`
3. Expand **Triage local**. It asks for a password: that is `POSTGRES_PASSWORD`.
4. `Databases → triage → Schemas → core → Tables`

### If you ever add a server by hand

This catches nearly everyone once, so it is worth stating plainly:

| Connecting from | Host | Port |
|---|---|---|
| **pgAdmin** (runs inside Docker) | `db` | `5432` |
| A tool on **your own machine** (DBeaver, psql, TablePlus) | `localhost` | `5433` |

Same database, two addresses. pgAdmin lives inside the Docker network, so it uses the
container name and the internal port. Using `localhost:5433` from pgAdmin gives
`could not translate host name`.

Settings if you need them: General tab → Name `Triage local`. Connection tab → Host `db`,
Port `5432`, Database = your `POSTGRES_DB`, Username = your `POSTGRES_USER`, Password =
your `POSTGRES_PASSWORD`.

---

## Which profile you have loaded

Two queries below need the **full** dataset. Check what you have:

```sql
SELECT count(*) FROM core.referrals;
```

| Result | Profile |
|---|---|
| ~609 | `sample` — the default |
| ~5,200 | `full` |

Queries 5 and 6 are marked where the sample is not enough.

---

## 1. Table counts

```sql
SELECT table_schema, count(*)
FROM information_schema.tables
WHERE table_schema IN ('core','agent','eval')
GROUP BY 1 ORDER BY 1;
```

**Expect exactly:**

```
 table_schema | count
--------------+-------
 agent        |     7
 core         |    18
 eval         |     1
```

`core` holds the inputs, read-only once loaded. `agent` is where the ranking system
writes, append-only. `eval` holds the answer key.

## 2. Triage categories sort correctly

```sql
SELECT code_value, description, severity_rank, crt_days
FROM core.ref_codes WHERE code_table='triage_category'
ORDER BY severity_rank NULLS LAST;
```

**Expect Urgent, Semi-Urgent, Routine, Excluded — in that order:**

```
 code_value |    description     | severity_rank | crt_days
------------+--------------------+---------------+----------
 1          | Urgent             |             1 |       28
 3          | Semi-Urgent        |             2 |       91
 2          | Routine/Non-Urgent |             3 |
 4          | Excluded           |               |
```

**Look at the codes.** Urgent is 1, Routine is 2, Semi-Urgent is **3**. They are not in
severity order. Sorting on `code_value` puts Routine ahead of Semi-Urgent, and it does so
silently — no error, just a wrong list. `severity_rank` exists to fix this once. Sort on
it, never on `code_value`.

## 3. The wait clocks differ for the same patient

```sql
SELECT pathway_number, days_since_referral, days_since_received, adjusted_wait_days
FROM core.referral_daily
WHERE as_of_date = (SELECT max(as_of_date) FROM core.referral_daily)
  AND adjusted_wait_days < days_since_received
LIMIT 5;
```

**Expect rows, with `adjusted_wait_days` smaller than `days_since_received`:**

```
 pathway_number | days_since_referral | days_since_received | adjusted_wait_days
----------------+---------------------+---------------------+--------------------
 PW-9001-000011 |                 177 |                 169 |                144
 PW-9001-000030 |                 259 |                 245 |                217
```

The gap is suspended time — periods when the patient's care was bought from a private
hospital and their waiting clock paused. **Use `adjusted_wait_days` for breach checks.**
The raw wait reports breaches that are not breaches.

## 4. Vitals do NOT determine urgency

```sql
SELECT t.triage_category, round(avg(o.news2),2) mean_news2,
       count(*) FILTER (WHERE o.news2 <= 2) low_score, count(*) total
FROM core.observations o
JOIN core.referral_daily d USING (hospital_hipe, pathway_number)
JOIN core.triage_events t ON t.triage_event_id = d.triage_event_id
GROUP BY 1 ORDER BY 1;
```

**Expect means to rise with urgency, but every category to hold plenty of low scores:**

```
 triage_category | mean_news2 | low_score | total
-----------------+------------+-----------+-------
               1 |       1.66 |      1450 |  2063     <- Urgent
               2 |       0.47 |      2338 |  2422     <- Routine
               3 |       0.97 |      2376 |  2376     <- Semi-Urgent
```

**This is the most important query on the page.** Urgent patients average a higher early
warning score — but 1,450 of the 2,063 of them, about 70 per cent, score 2 or less. They
are physiologically unremarkable and clinically urgent at the same time.

That is not a flaw. A suspected melanoma is urgent because of the referral pathway, not
because of the patient's heart rate. If vitals alone identified urgency, a ranking system
reading vitals would just be rediscovering the label it is scored against, and the whole
exercise would prove nothing.

## 5. Shared wards exist

```sql
SELECT hospital_hipe, ward_id, count(*) specialties
FROM core.ward_specialty GROUP BY 1,2 HAVING count(*) >= 3;
```

**Expect at least one row per public hospital:**

```
 hospital_hipe |  ward_id  | specialties
---------------+-----------+-------------
 9001          | W-9001-01 |           3
 9002          | W-9002-01 |           3
```

Real wards are shared. When a hospital is under pressure, specialties compete for the
same beds and someone loses. This table is what lets the system see that rather than just
assert it.

*On the sample you will see two rows. On the full set, four.*

## 6. Private hospitals have capacity but no queue — **needs the full profile**

```sql
SELECT h.hospital_name,
       (SELECT count(*) FROM core.referrals r WHERE r.hospital_hipe=h.hospital_hipe) referrals,
       (SELECT count(*) FROM core.clinic_sessions c WHERE c.hospital_hipe=h.hospital_hipe) sessions
FROM core.hospitals h WHERE h.hospital_type='private';
```

**Expect `referrals = 0` and `sessions > 0`.**

> **On the sample this returns 0 rows, and that is correct.** The sample covers hospitals
> 9001 and 9002, both public. Load the full profile to see the private sites:
> `make load FETCH_PROFILE=full`

Private hospitals are capacity, not a queue. A public patient reaches one through a
suspension — the state buys the treatment and the waiting clock pauses. That is why they
have clinic sessions and no referrals of their own.

## 7. The answer key is unreachable

```sql
SET ROLE agent_rw;
SELECT count(*) FROM eval.ground_truth;
RESET ROLE;
```

**Expect this to FAIL:**

```
ERROR:  permission denied for schema eval
```

### The error is the pass condition

`eval.ground_truth` records which patients actually deteriorated while waiting. It is the
answer key. If the ranking system could read it, it would rank perfectly by looking up
the answer and the evaluation would measure nothing.

So the database refuses. The `agent_rw` role can read every input table and write every
output table, and cannot see `eval` at all. The guarantee is a property of the database
rather than something nine people have to remember for seven days.

**Please do not file this as a bug.** If this query ever *succeeds*, that is the bug —
the held-out guarantee has been broken and results computed after that point cannot be
trusted.

---

## If something does not match

| Query | Wrong result | Likely cause |
|---|---|---|
| 1 | Fewer tables | Migrations did not all apply — `make migrate` and read the output |
| 2 | Routine second | You sorted on `code_value`. Sort on `severity_rank`. |
| 3 | No rows | The profile has no ended suspensions in range; try the full profile |
| 4 | `low_score` near zero | The generated vitals are too clean. `make test` should be failing too. |
| 5 | No rows | Ward-specialty data missing — reload |
| 6 | 0 rows | You are on the sample. Expected — see the note above. |
| 7 | **Succeeds** | Serious. `007_roles_and_grants.sql` did not apply. `make reset`. |

Start over any time with `make reset`. It takes about two minutes and cannot break
anything permanently.
