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
