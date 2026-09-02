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
