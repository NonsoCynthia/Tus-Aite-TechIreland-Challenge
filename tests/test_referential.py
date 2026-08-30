"""Referential integrity, and the two-column-key rule that keeps hospitals apart."""


def test_every_observation_belongs_to_a_real_referral(q):
    assert q("""SELECT count(*) FROM core.observations o
                LEFT JOIN core.referrals r USING (hospital_hipe, pathway_number)
                WHERE r.pathway_number IS NULL""")[0][0] == 0


def test_every_referral_has_exactly_one_primary_condition(q):
    assert q("""SELECT count(*) FROM (
                  SELECT hospital_hipe, pathway_number,
                         count(*) FILTER (WHERE is_primary) n
                  FROM core.conditions GROUP BY 1,2) x WHERE n <> 1""")[0][0] == 0


def test_ward_beds_reconcile(q):
    assert q("""SELECT count(*) FROM core.bed_status b
                JOIN core.wards w USING (hospital_hipe, ward_id)
                WHERE b.occupied + b.free <> w.total_beds + b.surge_capacity_in_use""")[0][0] == 0


def test_adjusted_wait_matches_recorded_suspensions(q):
    """Use adjusted_wait_days for breach checks, never the raw wait.

    An urgent referral received 40 days ago and suspended for 20 of them has a
    raw wait of 40, which looks like a 12-day breach, and an adjusted wait of 20,
    which is no breach at all.
    """
    assert q("""SELECT count(*) FROM core.referral_daily d
                WHERE d.adjusted_wait_days <> d.days_since_received - COALESCE((
                    SELECT sum(s.suspended_days) FROM core.suspension_events s
                    WHERE s.hospital_hipe = d.hospital_hipe
                      AND s.pathway_number = d.pathway_number
                      AND s.suspension_end_date <= d.as_of_date), 0)""")[0][0] == 0


def test_untriaged_referrals_have_no_triage_event(q):
    assert q("""SELECT count(*) FROM core.referral_daily
                WHERE triage_status='awaiting_triage' AND triage_event_id IS NOT NULL""")[0][0] == 0


def test_private_hospitals_have_no_referrals(q):
    """Private sites are capacity, not a queue. Patients reach them by suspension."""
    assert q("""SELECT count(*) FROM core.referrals r
                JOIN core.hospitals h USING (hospital_hipe)
                WHERE h.hospital_type='private'""")[0][0] == 0


def test_pathway_numbers_collide_across_hospitals_but_never_merge(q):
    """BUILD_MANUAL section 10.2, written out per the addendum.

    A pathway number is issued per hospital and is legitimately not globally
    unique. What must never happen is a join that forgets hospital_hipe merging
    two hospitals' referrals into one patient.

    The second assertion is the interesting one: if joining on pathway_number
    alone produced no extra rows there would be no collisions in the data and
    this test would prove nothing. A collision is planted between 9001 and 9002
    to guarantee it does.
    """
    pairs = q("SELECT count(*) FROM (SELECT DISTINCT hospital_hipe, pathway_number FROM core.referrals) x")[0][0]
    alone = q("SELECT count(DISTINCT pathway_number) FROM core.referrals")[0][0]
    assert pairs > alone, (
        "no cross-hospital pathway-number collisions exist, so this test proves "
        "nothing. Check that the planted collision reached this dataset.")

    # Correct join: composite key returns exactly the child table's row count.
    child = q("SELECT count(*) FROM core.observations")[0][0]
    correct = q("""SELECT count(*) FROM core.observations o
                   JOIN core.referrals r USING (hospital_hipe, pathway_number)""")[0][0]
    assert correct == child, "composite-key join changed the row count"

    # Wrong join: dropping hospital_hipe inflates it. That inflation is the bug.
    wrong = q("""SELECT count(*) FROM core.observations o
                 JOIN core.referrals r ON r.pathway_number = o.pathway_number""")[0][0]
    assert wrong > correct, "joining on pathway_number alone did not inflate; collision missing"
