# Build Manual — Referral Prioritisation Dataset Repository

Instructions for an AI coding agent.
Companion document: `DATASET_README.md` (the data specification).

---

## 0. How to use this manual

Work through the phases **in order**. Each phase ends with an **Acceptance check** — a command that must pass before you move on. Do not proceed past a failing check.

If something in this manual contradicts `DATASET_README.md`, the README wins on *what the data means*, this manual wins on *how it is built*. If you find a genuine contradiction, stop and report it rather than guessing.

Do not invent columns. Do not rename columns. The column names in the README are taken from a real national specification and changing them breaks the project's central claim.

---

## 1. What you are building

A repository that produces a synthetic Irish hospital waiting list dataset, publishes it as a versioned Hugging Face dataset, and loads it into a local PostgreSQL database that any team member can stand up with one command.

**Three things are versioned separately:**

| What | Where | Changes |
|---|---|---|
| Schema | Git, as numbered migration files | Rarely, reviewed |
| Data | Hugging Face, as tagged releases | Often |
| Code | Git | Constantly |

A pinned version file joins them. Nothing ever fetches "latest".

**Non-goals for this build.** No frontend. No agents. No API. Those come later and depend on this. Build only what is described here.

---

## 2. Prerequisites

Verify each of these before starting. Report and stop if any is missing.

| Requirement | Check command | Minimum |
|---|---|---|
| Docker | `docker --version` | 24.0 |
| Docker Compose | `docker compose version` | v2.20 |
| Python | `python3 --version` | 3.11 |
| Git | `git --version` | 2.40 |
| GitHub MCP | tool list | present |
| Hugging Face MCP | tool list | present |

**Ask the operator for these before Phase 1:**

1. GitHub organisation or username, and the repository name to create
2. Whether the GitHub repo should be private (**default: private**)
3. Hugging Face namespace (user or org) for the dataset
4. Whether the HF dataset should be private (**default: private**)

Do not guess these. Do not create public repositories without explicit confirmation.

---

## 3. Repository structure

Create exactly this. No extra top-level directories.

```
.
├── README.md
├── DATASET_README.md            copied in, do not rewrite
├── Makefile
├── .env.example
├── .gitignore
├── docker-compose.yml
├── versions.yml                 the pin
├── db/
│   ├── migrations/
│   │   ├── 001_extensions.sql
│   │   ├── 002_dictionaries.sql
│   │   ├── 003_core.sql
│   │   ├── 004_capacity.sql
│   │   ├── 005_events.sql
│   │   ├── 006_outputs.sql
│   │   └── 007_roles_and_grants.sql
│   └── seeds/
│       ├── ref_specialty.csv
│       ├── ref_codes.csv
│       └── ref_rules.csv
├── generator/
│   ├── __init__.py
│   ├── config.yml
│   ├── generate.py
│   ├── calibration/
│   │   ├── specialty_mix.yml
│   │   ├── vitals_by_category.yml
│   │   └── length_of_stay.yml
│   └── writers.py
├── loader/
│   ├── __init__.py
│   ├── fetch.py                 pulls pinned data from Hugging Face
│   ├── load.py                  CSVs into Postgres
│   └── load_order.py
├── tests/
│   ├── test_schema.py
│   ├── test_referential.py
│   ├── test_determinism.py
│   ├── test_plausibility.py
│   └── test_planted_cases.py
├── scripts/
│   ├── publish_to_hf.py
│   └── verify_install.sh
└── docs/
    └── VERIFY_IN_PGADMIN.md
```

---

## 4. Credentials and secrets policy

**Rules, no exceptions:**

1. No password, token, or key is ever written into a tracked file.
2. `.env` is git-ignored. `.env.example` is committed with placeholder values only.
3. The Postgres password is local-development-only, on a container not exposed beyond localhost. It is not a secret in the security sense, but it still lives in `.env`, never in `docker-compose.yml`.
4. Hugging Face and GitHub tokens are supplied by the operator at run time and never written to disk by you.
5. If you ever find yourself about to commit a value that looks like a token, stop and report it.

**`.env.example` — commit this exactly:**

```
# Local development only. Copy to .env and change if you like.
POSTGRES_USER=triage_admin
POSTGRES_PASSWORD=change_me_locally
POSTGRES_DB=triage
POSTGRES_PORT=5433

# pgAdmin web console
PGADMIN_EMAIL=admin@example.com
PGADMIN_PASSWORD=change_me_locally
PGADMIN_PORT=5050

# Hugging Face dataset to pull from. Must match versions.yml.
HF_DATASET_REPO=<namespace>/<dataset-name>

# Supplied at runtime by the operator. Never commit a real value.
HF_TOKEN=
```

**`.gitignore` — commit this exactly:**

```
.env
__pycache__/
*.pyc
.venv/
venv/
data/
out/
.pytest_cache/
.DS_Store
pgadmin-data/
```

**Note on port 5433.** Use 5433, not 5432. Many developers already have a Postgres on 5432 and the clash wastes an hour on day one.

---

## 5. Phase 1 — Repository and containers

### 5.1 Create the repository

Use the GitHub MCP. Private unless the operator said otherwise. Add a Python `.gitignore` and no licence yet (the operator decides that).

### 5.2 `docker-compose.yml`

Three services. Postgres, pgAdmin, and a one-shot loader.

```yaml
services:
  db:
    image: postgres:16-alpine
    container_name: triage_db
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    ports:
      - "127.0.0.1:${POSTGRES_PORT}:5432"
    volumes:
      - db_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 5s
      timeout: 5s
      retries: 10

  pgadmin:
    image: dpage/pgadmin4:latest
    container_name: triage_pgadmin
    restart: unless-stopped
    environment:
      PGADMIN_DEFAULT_EMAIL: ${PGADMIN_EMAIL}
      PGADMIN_DEFAULT_PASSWORD: ${PGADMIN_PASSWORD}
      PGADMIN_CONFIG_SERVER_MODE: "False"
    ports:
      - "127.0.0.1:${PGADMIN_PORT}:80"
    volumes:
      - pgadmin_data:/var/lib/pgadmin
    depends_on:
      db:
        condition: service_healthy

  loader:
    build: .
    container_name: triage_loader
    profiles: ["tools"]
    env_file: .env
    environment:
      PGHOST: db
      PGPORT: 5432
    depends_on:
      db:
        condition: service_healthy
    volumes:
      - ./:/app

volumes:
  db_data:
  pgadmin_data:
```

Binding to `127.0.0.1` matters. Without it, Docker publishes the port on every interface and the database is reachable from the local network.

### 5.3 `Makefile`

```makefile
.PHONY: up down migrate seed fetch load reset test verify logs psql

up:
	docker compose up -d db pgadmin
	@echo "Postgres on localhost:$${POSTGRES_PORT:-5433}"
	@echo "pgAdmin  on http://localhost:$${PGADMIN_PORT:-5050}"

down:
	docker compose down

migrate:
	docker compose run --rm loader python -m loader.load --migrate-only

seed:
	docker compose run --rm loader python -m loader.load --seeds-only

fetch:
	docker compose run --rm loader python -m loader.fetch

load: migrate seed fetch
	docker compose run --rm loader python -m loader.load

generate:
	docker compose run --rm loader python -m generator.generate

reset:
	docker compose down -v
	docker compose up -d db pgadmin
	sleep 5
	$(MAKE) load

test:
	docker compose run --rm loader pytest tests/ -v

verify:
	./scripts/verify_install.sh

psql:
	docker compose exec db psql -U $${POSTGRES_USER} -d $${POSTGRES_DB}
```

### Acceptance check — Phase 1

```bash
cp .env.example .env
make up
docker compose ps          # both db and pgadmin healthy
```

Then open `http://localhost:5050` and confirm the pgAdmin login page loads. Confirm `git status` shows no `.env`.

---

## 6. Phase 2 — Schema

Numbered migration files, applied in filename order. **Never edit an applied migration.** To change something, add a new file.

### 6.1 One addition to the README's table list

The README lists 17 input tables. The DDL needs **one more**: a `referrals` table holding the durable identity of each referral, separate from `referral_daily` which holds its state on a given day.

**Why.** `referral_daily` is keyed on `(hospital_hipe, pathway_number, as_of_date)`. Other tables — conditions, observations, triage events, cancellations, suspensions — belong to the referral as a whole, not to one particular day. Without a `referrals` table they have nothing valid to point a foreign key at, and the database cannot enforce that an observation belongs to a referral that exists.

`referrals` is **derived by the loader** from the distinct referral identities in `referral_daily`. It is not a CSV and nobody generates it.

Record this addition in the repo README as a deliberate deviation.

### 6.2 `001_extensions.sql`

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS agent;
CREATE SCHEMA IF NOT EXISTS eval;

COMMENT ON SCHEMA core  IS 'Input data. Loaded once, read-only thereafter.';
COMMENT ON SCHEMA agent IS 'Written by the agents at run time. Append only.';
COMMENT ON SCHEMA eval  IS 'Held-out ground truth. Agents must not read this.';
```

Three schemas, and the separation is load-bearing. `eval` exists so that the answer key can be enforced as unreachable by database permission rather than by everyone remembering not to query it.

### 6.3 `002_dictionaries.sql`

```sql
CREATE TABLE core.ref_specialty (
    specialty_hipe   char(4)  PRIMARY KEY,
    specialty_name   text     NOT NULL,
    is_paediatric    boolean  NOT NULL DEFAULT false
);

CREATE TABLE core.ref_codes (
    code_table    text     NOT NULL,
    code_value    text     NOT NULL,
    description   text     NOT NULL,
    severity_rank integer,
    crt_days      integer,
    PRIMARY KEY (code_table, code_value),
    CONSTRAINT ref_codes_rank_only_for_triage
        CHECK (severity_rank IS NULL OR code_table = 'triage_category'),
    CONSTRAINT ref_codes_crt_only_for_triage
        CHECK (crt_days IS NULL OR code_table = 'triage_category'),
    CONSTRAINT ref_codes_crt_positive
        CHECK (crt_days IS NULL OR crt_days > 0)
);

COMMENT ON COLUMN core.ref_codes.severity_rank IS
  'Our addition. Triage codes are NOT in severity order (Urgent=1, Routine=2, Semi-Urgent=3). Always sort on this, never on code_value.';

CREATE TABLE core.ref_rules (
    rule_id        text    PRIMARY KEY,
    statement      text    NOT NULL,
    applies_to     text    NOT NULL,
    threshold_days integer,
    CONSTRAINT ref_rules_threshold_positive
        CHECK (threshold_days IS NULL OR threshold_days > 0)
);
```

### 6.4 `003_core.sql`

```sql
CREATE TABLE core.hospitals (
    hospital_hipe        char(4) PRIMARY KEY,
    hospital_name        text    NOT NULL,
    hse_health_region    text    NOT NULL,
    hospital_type        text    NOT NULL,
    total_inpatient_beds integer NOT NULL,
    CONSTRAINT hospitals_type_valid CHECK (hospital_type IN ('public','private')),
    CONSTRAINT hospitals_beds_positive CHECK (total_inpatient_beds > 0)
);

CREATE TABLE core.hospital_specialty (
    hospital_hipe  char(4) NOT NULL REFERENCES core.hospitals(hospital_hipe),
    specialty_hipe char(4) NOT NULL REFERENCES core.ref_specialty(specialty_hipe),
    service_name   text    NOT NULL,
    active         boolean NOT NULL DEFAULT true,
    PRIMARY KEY (hospital_hipe, specialty_hipe)
);

CREATE TABLE core.persons (
    ihi_number             text    PRIMARY KEY,
    person_sex             char(1) NOT NULL,
    person_date_of_birth   date    NOT NULL,
    area_of_residence_code char(4) NOT NULL,
    CONSTRAINT persons_sex_valid CHECK (person_sex IN ('M','F','U'))
);

CREATE TABLE core.patients (
    hospital_hipe          char(4) NOT NULL REFERENCES core.hospitals(hospital_hipe),
    patient_id             text    NOT NULL,
    ihi_number             text    REFERENCES core.persons(ihi_number),
    patient_sex            char(1) NOT NULL,
    patient_date_of_birth  date    NOT NULL,
    area_of_residence_code char(4) NOT NULL,
    PRIMARY KEY (hospital_hipe, patient_id),
    CONSTRAINT patients_sex_valid CHECK (patient_sex IN ('M','F','U'))
);

COMMENT ON COLUMN core.patients.ihi_number IS
  'Nullable on purpose. Around a third of patients have no national identifier, which is why cross-hospital linkage is incomplete. Do not backfill.';

-- Derived by the loader. Not a CSV.
CREATE TABLE core.referrals (
    hospital_hipe          char(4) NOT NULL,
    pathway_number         text    NOT NULL,
    patient_id             text    NOT NULL,
    specialty_hipe         char(4) NOT NULL REFERENCES core.ref_specialty(specialty_hipe),
    referral_date          date    NOT NULL,
    referral_received_date date    NOT NULL,
    priority_level_gp      integer,
    referral_source        integer NOT NULL,
    PRIMARY KEY (hospital_hipe, pathway_number),
    FOREIGN KEY (hospital_hipe, patient_id)
        REFERENCES core.patients(hospital_hipe, patient_id),
    FOREIGN KEY (hospital_hipe, specialty_hipe)
        REFERENCES core.hospital_specialty(hospital_hipe, specialty_hipe),
    CONSTRAINT referrals_received_after_written
        CHECK (referral_received_date >= referral_date),
    CONSTRAINT referrals_gp_priority_valid
        CHECK (priority_level_gp IS NULL OR priority_level_gp IN (1,2))
);

CREATE TABLE core.triage_events (
    triage_event_id           text    PRIMARY KEY,
    hospital_hipe             char(4) NOT NULL,
    pathway_number            text    NOT NULL,
    sent_for_triage_date      date    NOT NULL,
    triage_date               date,
    date_returned_from_triage date,
    triage_outcome            integer,
    triage_category           integer,
    turnaround_days           integer,
    FOREIGN KEY (hospital_hipe, pathway_number)
        REFERENCES core.referrals(hospital_hipe, pathway_number),
    CONSTRAINT triage_outcome_valid
        CHECK (triage_outcome IS NULL OR triage_outcome IN (1,2,3)),
    CONSTRAINT triage_category_valid
        CHECK (triage_category IS NULL OR triage_category IN (1,2,3,4)),
    CONSTRAINT triage_category_required_when_accepted
        CHECK (date_returned_from_triage IS NULL
               OR triage_outcome IN (2,3)
               OR triage_category IS NOT NULL),
    CONSTRAINT triage_dates_ordered
        CHECK (date_returned_from_triage IS NULL
               OR date_returned_from_triage >= sent_for_triage_date)
);

COMMENT ON CONSTRAINT triage_category_required_when_accepted ON core.triage_events IS
  'Mirrors the national spec: category is mandatory once the referral returns from triage, unless it was redirected or rejected.';

CREATE TABLE core.referral_daily (
    hospital_hipe                 char(4) NOT NULL,
    pathway_number                text    NOT NULL,
    as_of_date                    date    NOT NULL,
    patient_id                    text    NOT NULL,
    specialty_hipe                char(4) NOT NULL,
    referral_date                 date    NOT NULL,
    referral_received_date        date    NOT NULL,
    priority_level_gp             integer,
    referral_source               integer NOT NULL,
    triage_event_id               text    REFERENCES core.triage_events(triage_event_id),
    appointment_date              date,
    arrived_date                  date,
    clinic_code                   text,
    clinic_classification         integer,
    last_cancellation_date        date,
    last_cancellation_reason      integer,
    record_creation_date          date    NOT NULL,
    suspension_start_date         date,
    suspension_reason             integer,
    suspension_end_date           date,
    removal_date                  date,
    removal_reason                integer,
    high_clinical_or_social_needs integer NOT NULL DEFAULT 0,
    triage_status                 text    NOT NULL,
    days_since_referral           integer NOT NULL,
    days_since_received           integer NOT NULL,
    adjusted_wait_days            integer NOT NULL,
    days_awaiting_triage          integer,
    PRIMARY KEY (hospital_hipe, pathway_number, as_of_date),
    FOREIGN KEY (hospital_hipe, pathway_number)
        REFERENCES core.referrals(hospital_hipe, pathway_number),
    CONSTRAINT rd_triage_status_valid
        CHECK (triage_status IN
               ('awaiting_triage','triaged','redirected','rejected','removed')),
    CONSTRAINT rd_high_needs_valid
        CHECK (high_clinical_or_social_needs IN (0,1)),
    CONSTRAINT rd_waits_non_negative
        CHECK (days_since_referral >= 0
               AND days_since_received >= 0
               AND adjusted_wait_days >= 0),
    CONSTRAINT rd_adjusted_not_greater_than_raw
        CHECK (adjusted_wait_days <= days_since_received),
    CONSTRAINT rd_awaiting_triage_has_no_event
        CHECK (triage_status <> 'awaiting_triage' OR triage_event_id IS NULL),
    CONSTRAINT rd_suspension_dates_ordered
        CHECK (suspension_end_date IS NULL
               OR suspension_start_date IS NULL
               OR suspension_end_date >= suspension_start_date)
);

CREATE INDEX idx_rd_as_of        ON core.referral_daily (as_of_date);
CREATE INDEX idx_rd_hosp_as_of   ON core.referral_daily (hospital_hipe, as_of_date);
CREATE INDEX idx_rd_status       ON core.referral_daily (triage_status);

CREATE TABLE core.conditions (
    hospital_hipe   char(4) NOT NULL,
    pathway_number  text    NOT NULL,
    icd10am_code    text    NOT NULL,
    condition_label text    NOT NULL,
    is_primary      boolean NOT NULL,
    snomed_ct_id    text,
    PRIMARY KEY (hospital_hipe, pathway_number, icd10am_code),
    FOREIGN KEY (hospital_hipe, pathway_number)
        REFERENCES core.referrals(hospital_hipe, pathway_number)
);

CREATE UNIQUE INDEX idx_conditions_one_primary
    ON core.conditions (hospital_hipe, pathway_number)
    WHERE is_primary;

CREATE TABLE core.observations (
    hospital_hipe  char(4)   NOT NULL,
    pathway_number text      NOT NULL,
    obs_datetime   timestamp NOT NULL,
    hr             integer,
    sbp            integer,
    dbp            integer,
    rr             integer,
    temp           numeric(4,1),
    spo2           integer,
    pain           integer,
    avpu           char(1),
    chiefcomplaint text,
    news2          integer,
    mts_category   text,
    icts_category  text,
    PRIMARY KEY (hospital_hipe, pathway_number, obs_datetime),
    FOREIGN KEY (hospital_hipe, pathway_number)
        REFERENCES core.referrals(hospital_hipe, pathway_number),
    CONSTRAINT obs_avpu_valid  CHECK (avpu IS NULL OR avpu IN ('A','V','P','U')),
    CONSTRAINT obs_news2_range CHECK (news2 IS NULL OR news2 BETWEEN 0 AND 20),
    CONSTRAINT obs_pain_range  CHECK (pain  IS NULL OR pain  BETWEEN 0 AND 10),
    CONSTRAINT obs_spo2_range  CHECK (spo2  IS NULL OR spo2  BETWEEN 50 AND 100),
    CONSTRAINT obs_hr_range    CHECK (hr    IS NULL OR hr    BETWEEN 20 AND 250),
    CONSTRAINT obs_rr_range    CHECK (rr    IS NULL OR rr    BETWEEN 4  AND 60),
    CONSTRAINT obs_temp_range  CHECK (temp  IS NULL OR temp  BETWEEN 30.0 AND 43.0),
    CONSTRAINT obs_bp_ordered  CHECK (sbp IS NULL OR dbp IS NULL OR sbp > dbp),
    CONSTRAINT obs_mts_valid
        CHECK (mts_category IS NULL
               OR mts_category IN ('red','orange','yellow','green','blue')),
    CONSTRAINT obs_one_scale_only
        CHECK (mts_category IS NULL OR icts_category IS NULL)
);

CREATE INDEX idx_obs_datetime ON core.observations (obs_datetime);
```

The `obs_one_scale_only` constraint enforces something clinical: a patient is triaged on the adult scale or the children's scale, never both.

### 6.5 `004_capacity.sql`

```sql
CREATE TABLE core.wards (
    hospital_hipe char(4) NOT NULL REFERENCES core.hospitals(hospital_hipe),
    ward_id       text    NOT NULL,
    ward_name     text    NOT NULL,
    total_beds    integer NOT NULL,
    ward_type     text    NOT NULL,
    PRIMARY KEY (hospital_hipe, ward_id),
    CONSTRAINT wards_type_valid
        CHECK (ward_type IN ('inpatient','day_case','assessment','icu')),
    CONSTRAINT wards_beds_positive CHECK (total_beds > 0)
);

CREATE TABLE core.ward_specialty (
    hospital_hipe  char(4) NOT NULL,
    ward_id        text    NOT NULL,
    specialty_hipe char(4) NOT NULL REFERENCES core.ref_specialty(specialty_hipe),
    nominal_beds   integer NOT NULL,
    is_primary     boolean NOT NULL DEFAULT false,
    PRIMARY KEY (hospital_hipe, ward_id, specialty_hipe),
    FOREIGN KEY (hospital_hipe, ward_id) REFERENCES core.wards(hospital_hipe, ward_id),
    CONSTRAINT ws_nominal_positive CHECK (nominal_beds > 0)
);

CREATE UNIQUE INDEX idx_ws_one_primary
    ON core.ward_specialty (hospital_hipe, ward_id)
    WHERE is_primary;

CREATE TABLE core.bed_status (
    hospital_hipe               char(4)   NOT NULL,
    ward_id                     text      NOT NULL,
    snapshot_datetime           timestamp NOT NULL,
    occupied                    integer   NOT NULL,
    free                        integer   NOT NULL,
    occupancy_pct               numeric(5,2) NOT NULL,
    outliers                    integer   NOT NULL DEFAULT 0,
    surge_capacity_in_use       integer   NOT NULL DEFAULT 0,
    delayed_transfers_of_care   integer   NOT NULL DEFAULT 0,
    awaiting_admission_over_9h  integer   NOT NULL DEFAULT 0,
    awaiting_admission_over_24h integer   NOT NULL DEFAULT 0,
    gar_status                  char(1)   NOT NULL,
    PRIMARY KEY (hospital_hipe, ward_id, snapshot_datetime),
    FOREIGN KEY (hospital_hipe, ward_id) REFERENCES core.wards(hospital_hipe, ward_id),
    CONSTRAINT bs_gar_valid CHECK (gar_status IN ('G','A','R')),
    CONSTRAINT bs_counts_non_negative
        CHECK (occupied >= 0 AND free >= 0 AND outliers >= 0
               AND surge_capacity_in_use >= 0 AND delayed_transfers_of_care >= 0),
    CONSTRAINT bs_occupancy_range CHECK (occupancy_pct BETWEEN 0 AND 100),
    CONSTRAINT bs_24h_subset_of_9h
        CHECK (awaiting_admission_over_24h <= awaiting_admission_over_9h)
);

CREATE INDEX idx_bs_snapshot ON core.bed_status (snapshot_datetime);

CREATE TABLE core.clinic_sessions (
    hospital_hipe   char(4) NOT NULL REFERENCES core.hospitals(hospital_hipe),
    clinic_code     text    NOT NULL,
    session_date    date    NOT NULL,
    clinic_name     text    NOT NULL,
    specialty_hipe  char(4) NOT NULL REFERENCES core.ref_specialty(specialty_hipe),
    slots_total     integer NOT NULL,
    slots_booked    integer NOT NULL,
    slots_available integer NOT NULL,
    PRIMARY KEY (hospital_hipe, clinic_code, session_date),
    CONSTRAINT cs_slots_non_negative CHECK (slots_total >= 0 AND slots_booked >= 0),
    CONSTRAINT cs_booked_within_total CHECK (slots_booked <= slots_total),
    CONSTRAINT cs_available_is_difference
        CHECK (slots_available = slots_total - slots_booked)
);

CREATE INDEX idx_cs_date ON core.clinic_sessions (session_date);
```

`cs_available_is_difference` is the database refusing to let the generator produce arithmetic that does not add up. Constraints like this catch generator bugs at load time instead of on stage.

### 6.6 `005_events.sql`

```sql
CREATE TABLE core.cancellation_events (
    hospital_hipe       char(4) NOT NULL,
    pathway_number      text    NOT NULL,
    cancellation_date   date    NOT NULL,
    cancellation_reason integer NOT NULL,
    initiated_by        char(1) NOT NULL,
    PRIMARY KEY (hospital_hipe, pathway_number, cancellation_date),
    FOREIGN KEY (hospital_hipe, pathway_number)
        REFERENCES core.referrals(hospital_hipe, pathway_number),
    CONSTRAINT ce_initiator_valid CHECK (initiated_by IN ('H','P'))
);

CREATE TABLE core.suspension_events (
    hospital_hipe         char(4) NOT NULL,
    pathway_number        text    NOT NULL,
    suspension_start_date date    NOT NULL,
    suspension_end_date   date,
    suspension_reason     integer NOT NULL,
    suspended_days        integer,
    PRIMARY KEY (hospital_hipe, pathway_number, suspension_start_date),
    FOREIGN KEY (hospital_hipe, pathway_number)
        REFERENCES core.referrals(hospital_hipe, pathway_number),
    CONSTRAINT se_reason_valid CHECK (suspension_reason IN (101,102,103,104)),
    CONSTRAINT se_dates_ordered
        CHECK (suspension_end_date IS NULL
               OR suspension_end_date >= suspension_start_date),
    CONSTRAINT se_days_non_negative
        CHECK (suspended_days IS NULL OR suspended_days >= 0)
);

CREATE TABLE eval.ground_truth (
    hospital_hipe      char(4)      NOT NULL,
    pathway_number     text         NOT NULL,
    latent_hazard      numeric(4,3) NOT NULL,
    deterioration_date date,
    deterioration_type text,
    PRIMARY KEY (hospital_hipe, pathway_number),
    CONSTRAINT gt_hazard_range CHECK (latent_hazard BETWEEN 0 AND 1),
    CONSTRAINT gt_type_valid
        CHECK (deterioration_type IS NULL
               OR deterioration_type IN ('emergency_admission','death')),
    CONSTRAINT gt_type_requires_date
        CHECK ((deterioration_date IS NULL) = (deterioration_type IS NULL))
);

COMMENT ON TABLE eval.ground_truth IS
  'HELD OUT. Deliberately has NO foreign key to core.referrals so the schemas stay decoupled and this table can be dropped for a demo build. No agent may read this schema.';
```

### 6.7 `006_outputs.sql`

```sql
CREATE TABLE agent.agent_scores (
    run_id         text         NOT NULL,
    agent_name     text         NOT NULL,
    hospital_hipe  char(4)      NOT NULL,
    pathway_number text         NOT NULL,
    as_of_date     date         NOT NULL,
    score          numeric(4,3) NOT NULL,
    method         text         NOT NULL,
    agent_version  text         NOT NULL,
    scored_at      timestamp    NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, agent_name, hospital_hipe, pathway_number),
    CONSTRAINT as_score_range CHECK (score BETWEEN 0 AND 1),
    CONSTRAINT as_agent_valid CHECK (agent_name IN ('urgency','capacity'))
);

CREATE TABLE agent.agent_citations (
    run_id         text    NOT NULL,
    agent_name     text    NOT NULL,
    hospital_hipe  char(4) NOT NULL,
    pathway_number text    NOT NULL,
    evidence_type  text    NOT NULL,
    evidence_key   text    NOT NULL,
    PRIMARY KEY (run_id, agent_name, hospital_hipe, pathway_number,
                 evidence_type, evidence_key),
    CONSTRAINT ac_evidence_type_valid
        CHECK (evidence_type IN ('observation','condition','triage_event',
                                 'bed_status','clinic_session'))
);

CREATE TABLE agent.decisions (
    decision_id         text      PRIMARY KEY,
    run_id              text      NOT NULL,
    hospital_hipe       char(4)   NOT NULL,
    as_of_date          date      NOT NULL,
    generated_at        timestamp NOT NULL DEFAULT now(),
    cohort_size         integer   NOT NULL,
    coordinator_version text      NOT NULL,
    CONSTRAINT d_cohort_positive CHECK (cohort_size > 0)
);

CREATE TABLE agent.decision_rankings (
    decision_id       text         NOT NULL REFERENCES agent.decisions(decision_id),
    hospital_hipe     char(4)      NOT NULL,
    pathway_number    text         NOT NULL,
    position          integer      NOT NULL,
    triage_category   integer,
    urgency_score     numeric(4,3) NOT NULL,
    capacity_score    numeric(4,3) NOT NULL,
    rationale_summary text         NOT NULL,
    PRIMARY KEY (decision_id, hospital_hipe, pathway_number),
    CONSTRAINT dr_position_positive CHECK (position > 0),
    CONSTRAINT dr_unique_position UNIQUE (decision_id, position)
);

CREATE TABLE agent.decision_citations (
    decision_id    text    NOT NULL REFERENCES agent.decisions(decision_id),
    hospital_hipe  char(4) NOT NULL,
    pathway_number text    NOT NULL,
    evidence_type  text    NOT NULL,
    evidence_key   text    NOT NULL,
    role           text    NOT NULL,
    PRIMARY KEY (decision_id, hospital_hipe, pathway_number,
                 evidence_type, evidence_key),
    CONSTRAINT dc_role_valid
        CHECK (role IN ('urgency','capacity','timeframe','multi_list'))
);

CREATE TABLE agent.rule_checks (
    decision_id    text    NOT NULL REFERENCES agent.decisions(decision_id),
    rule_id        text    NOT NULL REFERENCES core.ref_rules(rule_id),
    hospital_hipe  char(4) NOT NULL,
    pathway_number text    NOT NULL,
    passed         boolean NOT NULL,
    detail         text,
    PRIMARY KEY (decision_id, rule_id, hospital_hipe, pathway_number)
);

CREATE TABLE agent.overrides (
    override_id           text      PRIMARY KEY,
    decision_id           text      NOT NULL REFERENCES agent.decisions(decision_id),
    hospital_hipe         char(4)   NOT NULL,
    pathway_number        text      NOT NULL,
    clinician_id          text      NOT NULL,
    from_position         integer,
    to_position           integer,
    reason                text      NOT NULL,
    rule_warning_accepted boolean   NOT NULL DEFAULT false,
    created_at            timestamp NOT NULL DEFAULT now(),
    CONSTRAINT o_reason_not_blank CHECK (length(trim(reason)) > 0)
);
```

`dr_unique_position` means the database will not accept two patients at position 3. `o_reason_not_blank` means an override without a reason cannot be recorded, which is a policy commitment enforced in the schema rather than in the UI.

### 6.8 `007_roles_and_grants.sql`

```sql
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agent_rw') THEN
        CREATE ROLE agent_rw NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'evaluator') THEN
        CREATE ROLE evaluator NOLOGIN;
    END IF;
END $$;

GRANT USAGE ON SCHEMA core TO agent_rw;
GRANT SELECT ON ALL TABLES IN SCHEMA core TO agent_rw;
GRANT USAGE ON SCHEMA agent TO agent_rw;
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA agent TO agent_rw;

REVOKE ALL ON SCHEMA eval FROM agent_rw;
REVOKE ALL ON ALL TABLES IN SCHEMA eval FROM agent_rw;

GRANT USAGE ON SCHEMA core, agent, eval TO evaluator;
GRANT SELECT ON ALL TABLES IN SCHEMA core, agent, eval TO evaluator;
```

Two roles. `agent_rw` can read inputs, write outputs, and **cannot see the answer key**. `evaluator` can see everything and is used only by the scoring script.

This makes the held-out guarantee a property of the database, not a convention people remember.

### Acceptance check — Phase 2

```bash
make up && make migrate
docker compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB -c "\dt core.*"
docker compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB -c "\dt agent.*"
docker compose exec db psql -U $POSTGRES_USER -d $POSTGRES_DB -c "\dt eval.*"
```

Expect 18 tables in `core`, 7 in `agent`, 1 in `eval`.

Then prove the permission barrier works:

```sql
SET ROLE agent_rw;
SELECT * FROM eval.ground_truth LIMIT 1;   -- MUST fail: permission denied
RESET ROLE;
```

If that query succeeds, Phase 2 is not complete.

---

## 7. Phase 3 — Seeds

The three dictionary tables are **transcribed by hand** from the national specification. They are not generated. Commit them as CSVs in `db/seeds/`.

### 7.1 `ref_specialty.csv`

```csv
specialty_hipe,specialty_name,is_paediatric
2600,General Surgery,false
0100,Cardiology,false
0300,Dermatology,false
1800,Orthopaedics,false
0700,Gastro-Enterology,false
0600,Otolaryngology (ENT),false
0601,Paediatric ENT,true
```

Preserve the leading zeros. They are part of the code. Read the CSV with `dtype=str` or you will silently get `100` instead of `0100`.

### 7.2 `ref_codes.csv`

At minimum these rows. Transcribe the rest of the referral source, cancellation reason and removal reason lists from the specification.

```csv
code_table,code_value,description,severity_rank,crt_days
triage_category,1,Urgent,1,28
triage_category,3,Semi-Urgent,2,91
triage_category,2,Routine/Non-Urgent,3,
triage_category,4,Excluded,,
gp_priority,1,Urgent,,
gp_priority,2,Routine,,
referral_source,12,General Practitioners (GP),,
referral_source,6,Emergency Department within the hospital,,
referral_source,7,Assessment unit within the hospital,,
referral_source,11,Advanced Nurse Practitioners,,
referral_source,4,Consultants within the hospital,,
triage_outcome,1,Accept,,
triage_outcome,2,Redirected,,
triage_outcome,3,Reject,,
suspension_reason,101,NTPF Outsourcing Initiative,,
suspension_reason,102,NTPF Insourcing Initiative,,
suspension_reason,103,HSE Outsourcing Initiative,,
suspension_reason,104,HSE Insourcing Initiative,,
cancellation_reason,21,Cancelled by Consultant/Team,,
cancellation_reason,22,Cancelled by Patient/Guardian (non-clinical),,
cancellation_reason,12,Patient Did Not Attend,,
cancellation_reason,30,Patient Unfit,,
cancellation_reason,110,Service Restructuring,,
removal_reason,104,Admitted or attended ED for the same condition,,
removal_reason,11,Is deceased,,
removal_reason,91,Failed to attend appointment,,
removal_reason,109,Had their referral rejected,,
clinic_classification,10000,Procedures Clinics,,
clinic_classification,20000,Medical Consultation Clinics,,
clinic_classification,30000,Stand-alone Diagnostics Clinics,,
clinic_classification,40000,Allied Health/CNS/ANP Clinics,,
```

**Check the triage rows carefully.** Urgent is code 1, Routine is code 2, Semi-Urgent is code **3**. The codes are not in severity order. `severity_rank` corrects this and everything downstream must sort on it.

### 7.3 `ref_rules.csv`

```csv
rule_id,statement,applies_to,threshold_days
RULE-CRT-URGENT,An urgent referral should be seen within 28 days,triaged_urgent,28
RULE-CRT-SEMI,A semi-urgent referral should be seen within 13 weeks,triaged_semi_urgent,91
RULE-TRIAGE-TURNAROUND,A referral should not sit untriaged indefinitely,awaiting_triage,21
RULE-ORDER,A referral may never be ranked above one of higher clinical priority,all,
RULE-TIEBREAK,Same category and status ordered oldest referral first,all,
```

### Acceptance check — Phase 3

```sql
SELECT code_value, description, severity_rank, crt_days
FROM core.ref_codes
WHERE code_table = 'triage_category'
ORDER BY severity_rank NULLS LAST;
```

Must return Urgent, Semi-Urgent, Routine, Excluded **in that order**. If Routine appears second, the seed is wrong.

```sql
SELECT specialty_hipe FROM core.ref_specialty WHERE specialty_hipe = '0601';
```

Must return one row. If it returns nothing, leading zeros were lost.

---

## 8. Phase 4 — Generator

### 8.1 `generator/config.yml`

```yaml
seed: 20260901

simulation:
  start_date: 2026-08-17
  end_date:   2026-08-30
  snapshot_times: ["08:00", "14:00", "20:00"]

hospitals:
  - hipe: "9001"
    name: "St Brendan's University Hospital"
    region: "HSE Dublin and Midlands"
    type: public
    beds: 640
    active_referrals: 2000
  - hipe: "9002"
    name: "Kilbrannan Regional Hospital"
    region: "HSE West and North West"
    type: public
    beds: 420
    active_referrals: 1600
  - hipe: "9003"
    name: "Ardfinnan General Hospital"
    region: "HSE South West"
    type: public
    beds: 280
    active_referrals: 1100
  - hipe: "9004"
    name: "Loughrea District Hospital"
    region: "HSE West and North West"
    type: public
    beds: 110
    active_referrals: 500
  - hipe: "9101"
    name: "Rosslare Private Clinic"
    region: "HSE South East"
    type: private
    beds: 90
    active_referrals: 0
  - hipe: "9102"
    name: "Riverbank Private Hospital"
    region: "HSE Dublin and Midlands"
    type: private
    beds: 180
    active_referrals: 0

ihi_coverage: 0.65
awaiting_triage_share: 0.18
multi_list_share: 0.12
cross_hospital_share: 0.04
```

### 8.2 Generation order

Order matters. Each step depends on the one before.

1. **Hospitals, wards, ward-specialty** from config. Wards must be genuinely shared: at least one ward per public hospital serving three specialties.
2. **Persons**, with national identifiers, for `ihi_coverage` of the population.
3. **Patients**, per hospital. `cross_hospital_share` of persons get a patient record at two hospitals. Patients outside `ihi_coverage` get a NULL identifier.
4. **Referrals.** Assign `priority_level_gp` first. Back-date `referral_date` so wait times match published Irish distributions. `referral_received_date` is 1 to 14 days later.
5. **Triage events** for the referrals that have been triaged. Triage category is *usually* but not always what the GP said. Disagreement is realistic and interesting.
6. **Conditions**, conditional on specialty. Exactly one primary per referral.
7. **Observations**, conditional on triage category, **with deliberate overlap**. See 8.3.
8. **Bed occupancy** via a SimPy model over the simulated period, three snapshots a day.
9. **Clinic sessions**, with `slots_booked` consistent with referrals that have appointments.
10. **Cancellation and suspension events.**
11. **Daily snapshots.** For each day, one row per active referral, with the four wait clocks computed.
12. **Ground truth**, written to a separate file.

### 8.3 The two rules that keep the project honest

**Rule 1 — observations must overlap across categories.**

If urgent referrals always had a high early warning score and routine ones always had a low one, the urgency agent would simply be rediscovering the label it is being scored against. The result would be meaningless.

So: sample vitals conditional on triage category, but with heavy overlap. Some urgent patients must have entirely normal vitals — a suspected melanoma is urgent because of the pathway, not the physiology. Some routine patients must have mildly abnormal ones.

Target: the early warning score should explain roughly 35 to 50 percent of the variance in triage category. Not 90 percent.

**Rule 2 — the hazard must not be a function of what the agent sees.**

`latent_hazard` is drawn loosely from condition and age with a **large** random component. It must never be computed from the early warning score.

Concretely: `latent_hazard = clip(base_by_condition + age_effect + normal(0, 0.25), 0, 1)`

The noise term is the point. It ensures the agent can only improve outcomes by genuinely identifying risk from partial information, which is the real clinical problem.

Deterioration then fires as a function of hazard multiplied by days waited. Write it to `ground_truth.csv` and nowhere else.

### 8.4 Planted cases

Random sampling will not reliably produce the cases the demo needs. Plant them, at fixed pathway numbers, in every run.

| Pathway | Profile | What it demonstrates |
|---|---|---|
| `PW-DEMO-01` | Urgent, past its timeframe, worst bed pressure, no clinic slots | Capacity must not demote clinical urgency |
| `PW-DEMO-02` | Routine, longest wait in the list, emptiest ward, slots available | Easy to treat is not a reason to treat first |
| `PW-DEMO-03` | Urgent by pathway, entirely normal vitals | Vitals alone do not identify urgency |
| `PW-DEMO-04` | Semi-urgent, three days from its timeframe | Proximity escalation |
| `PW-DEMO-05` | Awaiting triage 60+ days, no category at all | The invisible population |
| `PW-DEMO-06` | Same person on four lists across two hospitals, identifier present | Multi-list visibility |
| `PW-DEMO-07` | Same profile, identifier absent | What is lost without national linkage |

`test_planted_cases.py` asserts all seven exist with the expected properties.

### 8.5 Determinism

Non-negotiable. Same seed, byte-identical output.

- Seed `random`, `numpy`, and any other source at start
- Never iterate a `set`
- Sort every dataframe before writing
- Write CSVs with a fixed column order and `lineterminator="\n"`
- Format all dates as `YYYY-MM-DD`, all timestamps as `YYYY-MM-DD HH:MM:SS`
- No `datetime.now()` anywhere in generated content

### Acceptance check — Phase 4

```bash
make generate && sha256sum out/*.csv > /tmp/a.txt
rm -rf out && make generate && sha256sum out/*.csv > /tmp/b.txt
diff /tmp/a.txt /tmp/b.txt && echo "DETERMINISTIC"
```

Must print `DETERMINISTIC`. If it does not, stop and fix it before anything else — every downstream guarantee depends on this.

---

## 9. Phase 5 — Loader

### 9.1 `versions.yml`

```yaml
schema_version: "007"
data_version: "v1.0"
hf_repo: "<namespace>/<dataset-name>"
hf_revision: "v1.0"
```

`hf_revision` is a tag, never a branch. Never `main`. Never "latest".

### 9.2 Load order

Foreign keys mean order is not optional.

```python
LOAD_ORDER = [
    "ref_specialty",        # seed
    "ref_codes",            # seed
    "ref_rules",            # seed
    "hospitals",
    "hospital_specialty",
    "persons",
    "patients",
    "referral_daily_stage", # temp table, see below
    "referrals",            # DERIVED from the stage table
    "triage_events",
    "referral_daily",       # from stage, now that FKs resolve
    "conditions",
    "observations",
    "wards",
    "ward_specialty",
    "bed_status",
    "clinic_sessions",
    "cancellation_events",
    "suspension_events",
    "ground_truth",         # into eval schema, optional
]
```

**The `referrals` derivation.** Load `referral_daily.csv` into an unconstrained staging table first, derive `core.referrals` from the earliest snapshot of each referral, then insert the real `referral_daily` rows.

```sql
INSERT INTO core.referrals (
    hospital_hipe, pathway_number, patient_id, specialty_hipe,
    referral_date, referral_received_date, priority_level_gp, referral_source)
SELECT DISTINCT ON (hospital_hipe, pathway_number)
    hospital_hipe, pathway_number, patient_id, specialty_hipe,
    referral_date, referral_received_date, priority_level_gp, referral_source
FROM staging.referral_daily
ORDER BY hospital_hipe, pathway_number, as_of_date;
```

### 9.3 Loading technique

Use `COPY`, not row-by-row inserts. `psycopg.copy` or `COPY ... FROM STDIN WITH CSV HEADER`.

Wrap the whole load in **one transaction**. A partial load is worse than no load, because it looks like it worked.

Log a row count per table on completion.

### 9.4 `loader/fetch.py`

Pull the pinned revision from Hugging Face into `data/`.

```python
from huggingface_hub import snapshot_download

snapshot_download(
    repo_id=cfg["hf_repo"],
    revision=cfg["hf_revision"],   # a tag, never a branch
    repo_type="dataset",
    local_dir="data/",
)
```

If `HF_TOKEN` is absent and the dataset is private, fail with a clear message telling the operator to set it. Do not fall back to generating locally — silently diverging data is the exact failure this architecture exists to prevent.

### Acceptance check — Phase 5

```bash
make reset
```

Must complete with no constraint violations and print a row count per table. Then:

```sql
SELECT 'referrals' t, count(*) FROM core.referrals
UNION ALL SELECT 'referral_daily', count(*) FROM core.referral_daily
UNION ALL SELECT 'observations', count(*) FROM core.observations
UNION ALL SELECT 'bed_status', count(*) FROM core.bed_status;
```

---

## 10. Phase 6 — Tests

All tests run against a freshly loaded database. `make test` must be green before anything is published.

### 10.1 `test_schema.py`

- 18 tables in `core`, 7 in `agent`, 1 in `eval`
- Every table has a primary key
- `agent_rw` is denied `SELECT` on `eval.ground_truth`
- Every expected index exists

### 10.2 `test_referential.py`

```sql
-- Every observation belongs to a real referral
SELECT count(*) FROM core.observations o
LEFT JOIN core.referrals r USING (hospital_hipe, pathway_number)
WHERE r.pathway_number IS NULL;               -- expect 0

-- No observation postdates the snapshot that could cite it
SELECT count(*) FROM core.observations o
JOIN core.referral_daily d USING (hospital_hipe, pathway_number)
WHERE o.obs_datetime::date > d.as_of_date
  AND d.as_of_date = (SELECT min(as_of_date) FROM core.referral_daily);

-- Every referral has exactly one primary condition
SELECT count(*) FROM (
  SELECT hospital_hipe, pathway_number, count(*) FILTER (WHERE is_primary) n
  FROM core.conditions GROUP BY 1,2) x WHERE n <> 1;   -- expect 0

-- Ward beds reconcile
SELECT count(*) FROM core.bed_status b
JOIN core.wards w USING (hospital_hipe, ward_id)
WHERE b.occupied + b.free <> w.total_beds + b.surge_capacity_in_use;

-- Adjusted wait matches recorded suspensions
SELECT count(*) FROM core.referral_daily d
WHERE d.adjusted_wait_days <> d.days_since_received - COALESCE((
    SELECT sum(s.suspended_days) FROM core.suspension_events s
    WHERE s.hospital_hipe = d.hospital_hipe
      AND s.pathway_number = d.pathway_number
      AND s.suspension_end_date <= d.as_of_date), 0);   -- expect 0

-- Untriaged referrals have no triage event
SELECT count(*) FROM core.referral_daily
WHERE triage_status = 'awaiting_triage' AND triage_event_id IS NOT NULL;

-- Private hospitals have no referrals
SELECT count(*) FROM core.referrals r
JOIN core.hospitals h USING (hospital_hipe)
WHERE h.hospital_type = 'private';             -- expect 0

-- No pathway number collides across hospitals in a way that merges patients
SELECT count(*) FROM (
  SELECT pathway_number, count(DISTINCT hospital_hipe) n
  FROM core.referrals GROUP BY 1) x WHERE n > 1 AND ...;  -- collisions allowed, merges not
```

### 10.3 `test_determinism.py`

Generate twice, compare SHA-256 of every output file.

### 10.4 `test_plausibility.py`

These catch a generator that produces structurally valid nonsense.

- Identifier coverage within 5 percentage points of `ihi_coverage`
- Between 10 and 25 percent of referrals awaiting triage
- Mean occupancy between 80 and 98 percent
- ~~**Correlation between `news2` and `severity_rank` is between 0.35 and 0.65.**~~
  **FALSIFIED by the Phase 3b fit and replaced.** This band was specified without checking
  whether NEWS2 discriminates triage acuity. It does not: a coupling sweep across 0.3-5.0
  never exceeded |r| 0.253. The band also measured the wrong quantity, asking whether vitals
  predict *which category* a patient is in, when this system never assigns categories and
  only ever orders *within* one. Replaced by two assertions:
  - **Realism**: `AUC(news2, Urgent vs Semi-Urgent) <= auc_mimic + 0.05`, where
    `auc_mimic = 0.6516` is measured from the source rows rather than chosen. One-sided:
    overlap looser than reality passes; only cleaner-than-real separation fails.
  - **Within-category discriminability**: per category, `sd(news2)` and the share scoring
    `>= 4` must stay in ranges derived from the MIMIC-fitted distributions.
  See `docs/CALIBRATION_FINDINGS.md`.
- At least 15 percent of urgent referrals have `news2 <= 2`
- ~~Some referrals breach their timeframe, but fewer than 40 percent~~
  **FALSIFIED.** NTPF's own published wait bands imply ~91% breach the 28-day urgent
  target: 28 days is under one month and only 59.6% of the national list waits under six.
  The assertion is now anchored to the NTPF-implied rate +/- 5 points.
- At least one ward per public hospital serves three or more specialties

### 10.5 `test_planted_cases.py`

Assert each of the seven demo pathways exists with its expected properties.

### Acceptance check — Phase 6

```bash
make test
```

All green. The correlation test in 10.4 is the single most important assertion in the repository — it is what stops the project from being circular.

---

## 11. Phase 7 — Publish to Hugging Face

Only after `make test` passes.

### 11.1 Create the dataset repository

Use the Hugging Face MCP. Private unless the operator said otherwise. `repo_type="dataset"`.

### 11.2 Dataset card

`README.md` at the dataset root, with YAML front matter:

```yaml
---
license: cc-by-4.0
language: [en]
tags: [synthetic, healthcare, ireland, waiting-list, triage]
pretty_name: Synthetic Irish Hospital Referral Prioritisation Dataset
size_categories: [100K<n<1M]
---
```

The body must state, near the top and unmistakably:

> Every record in this dataset is synthetic. No real patient, clinician, or hospital is represented. Hospital names are invented and hospital codes use a reserved range that does not correspond to any real facility.

Then: what the dataset is, which fields come from the national specification, which are our addition and why, the file list, and a link to the source specification.

Do not copy `DATASET_README.md` wholesale. Write a shorter card and link to the repository for the full specification.

### 11.3 Upload and tag

Upload the 17 CSVs plus `ground_truth.csv`. Then create a **git tag** matching `data_version` in `versions.yml`.

The tag is what everyone pins to. Without it there is no versioning, only a moving target.

### 11.4 Bump the pin

Update `versions.yml` in the GitHub repo and open a pull request. Do not push directly to the default branch. The pull request is how the team sees a data change coming.

### Acceptance check — Phase 7

From a clean checkout with an empty `data/`:

```bash
make reset
```

Must pull the pinned revision from Hugging Face and load successfully without ever running the generator.

---

## 12. Phase 8 — Verification in pgAdmin

Write `docs/VERIFY_IN_PGADMIN.md` so any team member can confirm their install by hand.

**Connecting:**

1. Open `http://localhost:5050`
2. Log in with `PGADMIN_EMAIL` and `PGADMIN_PASSWORD` from your `.env`
3. Add New Server
4. General tab, Name: `Triage local`
5. Connection tab:
   - Host: `db` (the container name, **not** `localhost` — pgAdmin runs inside Docker)
   - Port: `5432` (the internal port, **not** 5433)
   - Database: value of `POSTGRES_DB`
   - Username: value of `POSTGRES_USER`
   - Password: value of `POSTGRES_PASSWORD`

The host and port catch nearly everyone once. From inside the Docker network the database is `db:5432`. From your laptop it is `localhost:5433`.

**Seven queries that prove the install is good.** Include these in the document with expected results.

```sql
-- 1. Table counts
SELECT table_schema, count(*)
FROM information_schema.tables
WHERE table_schema IN ('core','agent','eval')
GROUP BY 1 ORDER BY 1;
-- expect: agent 7, core 18, eval 1

-- 2. Triage categories sort correctly
SELECT code_value, description, severity_rank, crt_days
FROM core.ref_codes WHERE code_table='triage_category'
ORDER BY severity_rank NULLS LAST;
-- expect Urgent, Semi-Urgent, Routine, Excluded IN THAT ORDER

-- 3. The four wait clocks differ for the same patient
SELECT pathway_number, days_since_referral, days_since_received,
       adjusted_wait_days, days_awaiting_triage
FROM core.referral_daily
WHERE as_of_date = (SELECT max(as_of_date) FROM core.referral_daily)
  AND adjusted_wait_days < days_since_received
LIMIT 5;
-- expect rows; adjusted < received proves suspensions are being applied

-- 4. Vitals do NOT determine urgency
SELECT t.triage_category, round(avg(o.news2),2) mean_news2,
       count(*) FILTER (WHERE o.news2 <= 2) low_score, count(*) total
FROM core.observations o
JOIN core.referral_daily d USING (hospital_hipe, pathway_number)
JOIN core.triage_events t ON t.triage_event_id = d.triage_event_id
GROUP BY 1 ORDER BY 1;
-- expect means to rise with urgency BUT every category to contain low scores

-- 5. Shared wards exist
SELECT hospital_hipe, ward_id, count(*) specialties
FROM core.ward_specialty GROUP BY 1,2 HAVING count(*) >= 3;
-- expect at least one row per public hospital

-- 6. Private hospitals have capacity but no queue
SELECT h.hospital_name,
       (SELECT count(*) FROM core.referrals r WHERE r.hospital_hipe=h.hospital_hipe) referrals,
       (SELECT count(*) FROM core.clinic_sessions c WHERE c.hospital_hipe=h.hospital_hipe) sessions
FROM core.hospitals h WHERE h.hospital_type='private';
-- expect referrals = 0, sessions > 0

-- 7. The answer key is unreachable
SET ROLE agent_rw;
SELECT count(*) FROM eval.ground_truth;
-- expect: ERROR permission denied
RESET ROLE;
```

Query 7 failing with a permission error **is the pass condition**. Say so in the document, or someone will file it as a bug.

---

## 13. Definition of done

Every item must be true.

**Repository**
- [ ] Private GitHub repo, structure exactly as section 3
- [ ] `.env` git-ignored, `.env.example` committed with placeholders only
- [ ] No token, password, or key in any tracked file
- [ ] Repo README explains the three-track versioning and the `referrals` addition

**Database**
- [ ] `make up` gives a healthy Postgres and pgAdmin in under two minutes
- [ ] Ports bound to `127.0.0.1` only
- [ ] 18 tables in `core`, 7 in `agent`, 1 in `eval`
- [ ] `agent_rw` denied access to `eval`
- [ ] Every foreign key and check constraint from section 6 present

**Data**
- [ ] Generator produces byte-identical output across runs
- [ ] All 17 CSVs plus `ground_truth.csv` written
- [ ] All seven planted demo cases present
- [ ] Correlation between `news2` and `severity_rank` between 0.35 and 0.65

**Distribution**
- [ ] HF dataset created with a card carrying the synthetic-data statement
- [ ] Data uploaded and tagged
- [ ] `versions.yml` pins a tag, never a branch
- [ ] Clean checkout + `make reset` loads from HF without generating

**Tests**
- [ ] `make test` green
- [ ] `docs/VERIFY_IN_PGADMIN.md` written with all seven queries and expected results

---

## 14. Known failure modes

Things that will go wrong. Check for them.

| Symptom | Cause | Fix |
|---|---|---|
| Specialty `0601` missing | Leading zeros lost | Read CSVs with `dtype=str` |
| Routine ranks above Semi-Urgent | Sorted on `code_value` | Sort on `severity_rank` |
| Two patients merged | Joined on `patient_id` alone | Always `hospital_hipe + patient_id` |
| Breach counts too high | Used raw wait not adjusted | Use `adjusted_wait_days` |
| `news2` correlation above 0.65 | Vitals sampled too tightly | Widen the overlap in 8.3 |
| Hash mismatch between runs | Unordered iteration or unseeded RNG | Sort before write, seed everything |
| pgAdmin cannot connect | Used `localhost:5433` | Use `db:5432` from inside Docker |
| Port 5432 in use | Existing local Postgres | Already handled: we use 5433 |
| Capacity picks wrong hospital's beds | Joined on `specialty_hipe` alone | Join `hospital_hipe + specialty_hipe` |
| FK violation loading observations | `referrals` not derived first | Follow `LOAD_ORDER` exactly |

---

## 15. Reporting back

When finished, report:

1. Repository URL and default branch
2. Hugging Face dataset URL and the tag published
3. Output of `make test`, in full
4. Row count per table
5. The measured `news2` / `severity_rank` correlation
6. Anything in this manual you could not follow, and what you did instead

If you deviated from this manual anywhere, say so explicitly. A documented deviation is fine. An undocumented one is not.
