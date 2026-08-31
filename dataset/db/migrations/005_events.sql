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
