-- The retrieval service's new-referral intake endpoint (spec.md FR11, user
-- request) is the first write path this service has into core.* -- every
-- prior core.* access (migration 007) was deliberately SELECT-only, since
-- core was exclusively the batch loader's territory (a live-intake API
-- didn't exist yet). Narrowly scoped: INSERT only, only on the four tables
-- intake actually touches -- not a blanket widening of core access, and no
-- UPDATE/DELETE (this service creates referrals, it does not amend or
-- remove them).
GRANT INSERT ON core.persons, core.patients, core.referrals, core.referral_daily TO agent_rw;

-- Mints a hospital-agnostic, monotonically increasing suffix for newly
-- intaken pathway_numbers ("PW-{hospital_hipe}-{seq}"), so the service
-- never has to race a `SELECT max(...)+1` under concurrent intake. Started
-- well above the batch-loaded dataset's own numbering (observed up to the
-- low thousands, e.g. PW-9001-001685) so a live-intake pathway_number can
-- never collide with a historical one for the same hospital.
CREATE SEQUENCE IF NOT EXISTS core.pathway_number_seq START WITH 900001;
GRANT USAGE ON SEQUENCE core.pathway_number_seq TO agent_rw;
