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
