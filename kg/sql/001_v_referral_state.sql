CREATE SCHEMA IF NOT EXISTS kg;

CREATE OR REPLACE VIEW kg.v_referral_state AS
WITH marked AS (
  SELECT
    hospital_hipe, pathway_number, as_of_date,
    triage_status, triage_event_id, appointment_date, arrived_date,
    last_cancellation_date, suspension_start_date, suspension_end_date,
    removal_date, high_clinical_or_social_needs, specialty_hipe,
    (triage_status, triage_event_id, appointment_date, arrived_date,
     last_cancellation_date, suspension_start_date, suspension_end_date,
     removal_date, high_clinical_or_social_needs, specialty_hipe) AS cur,
    lag((triage_status, triage_event_id, appointment_date, arrived_date,
         last_cancellation_date, suspension_start_date, suspension_end_date,
         removal_date, high_clinical_or_social_needs, specialty_hipe))
      OVER (PARTITION BY hospital_hipe, pathway_number ORDER BY as_of_date) AS prev
  FROM core.referral_daily
)
SELECT
  hospital_hipe, pathway_number,
  as_of_date AS valid_from,
  COALESCE(
    lead(as_of_date) OVER (PARTITION BY hospital_hipe, pathway_number
                           ORDER BY as_of_date),
    removal_date
  ) AS valid_to,
  triage_status, triage_event_id, appointment_date, arrived_date,
  last_cancellation_date, suspension_start_date, suspension_end_date,
  removal_date, high_clinical_or_social_needs, specialty_hipe
FROM marked
WHERE cur IS DISTINCT FROM prev;
