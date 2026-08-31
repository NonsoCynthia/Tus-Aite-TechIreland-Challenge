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
