-- The wait counts must agree with the dates they are computed from.
--
-- referral_daily stores both the dates and four derived day-counts. The counts are
-- computed once at generation time so that nothing downstream recalculates them and
-- disagrees. That is the right design, but nothing asserted the two stayed in step,
-- and in v1.0 two planted demo referrals shipped where they did not: PW-DEMO-01
-- recorded 58 days since receipt against a received date equal to the snapshot date,
-- and PW-DEMO-05 recorded 64 days of waiting on a letter written 12 days earlier --
-- a referral received before it was written.
--
-- These constraints make that combination unloadable. Data at v1.0 will therefore
-- FAIL to load against this schema, which is intended: schema 008 requires data
-- v1.1 or later. Anyone pinned to v1.0 should stay on schema 007.

ALTER TABLE core.referral_daily
    ADD CONSTRAINT rd_counts_match_dates CHECK (
            days_since_referral = as_of_date - referral_date
        AND days_since_received = as_of_date - referral_received_date),
    ADD CONSTRAINT rd_received_after_written CHECK (
            days_since_referral >= days_since_received);

COMMENT ON CONSTRAINT rd_counts_match_dates ON core.referral_daily IS
  'The stored day-counts must equal the date arithmetic. Exact, and catches the whole class of drift between dates and counts.';

COMMENT ON CONSTRAINT rd_received_after_written ON core.referral_daily IS
  'A hospital cannot receive a referral before the GP wrote it. Implied by rd_counts_match_dates, stated separately because this is the one a human reads and immediately understands.';
