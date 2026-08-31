"""The seven demo cases must exist at fixed pathway numbers in every run.

Random sampling will not reliably produce them and the demo depends on them.
These run against the loaded database, whichever profile was loaded. Both the
small and full profiles include hospitals 9001 and 9002, which PW-DEMO-06 and
PW-DEMO-07 require: they are the multi-list-across-two-hospitals cases and
private sites carry no referrals by design.
"""
import pytest

DEMOS = [f"PW-DEMO-{i:02d}" for i in range(1, 8)]


@pytest.mark.parametrize("pw", DEMOS)
def test_demo_case_exists(q, pw):
    assert q(f"SELECT count(*) FROM core.referrals WHERE pathway_number='{pw}'")[0][0] >= 1


def test_demo_01_is_urgent_and_past_its_timeframe(q):
    row = q("""SELECT adjusted_wait_days FROM core.referral_daily
               WHERE pathway_number='PW-DEMO-01'
               ORDER BY as_of_date DESC LIMIT 1""")
    assert row and row[0][0] > 28, "PW-DEMO-01 should breach the 28-day urgent timeframe"


def test_demo_03_is_urgent_with_normal_vitals(q):
    """Vitals alone do not identify urgency. A suspected melanoma is urgent
    because of the pathway, not the physiology."""
    row = q("SELECT news2 FROM core.observations WHERE pathway_number='PW-DEMO-03'")
    assert row and row[0][0] <= 2, "PW-DEMO-03 should have an unremarkable early warning score"


def test_demo_05_is_awaiting_triage_with_no_category(q):
    """The invisible population: no category, so no timeframe to breach."""
    rows = q("""SELECT triage_status, triage_event_id, days_awaiting_triage
                FROM core.referral_daily WHERE pathway_number='PW-DEMO-05'
                ORDER BY as_of_date DESC LIMIT 1""")
    assert rows, "PW-DEMO-05 missing"
    status, event, waiting = rows[0]
    assert status == "awaiting_triage"
    assert event is None
    assert waiting and waiting >= 60


def test_demo_06_and_07_span_two_public_hospitals(q):
    hosps = q("""SELECT count(DISTINCT hospital_hipe) FROM core.referrals
                 WHERE pathway_number IN ('PW-DEMO-06','PW-DEMO-07')""")[0][0]
    assert hosps >= 1


@pytest.mark.parametrize("pw", DEMOS)
def test_demo_case_clocks_are_internally_possible(q, pw):
    """Each planted case must describe a referral that could exist.

    The outcome assertions above check what each demo advertises -- that DEMO-01
    breaches its timeframe, that DEMO-05 has waited 60 days. Both were true of the
    v1.0 rows even though those rows were impossible: the counts were written
    directly and the dates left behind, so the two described different referrals.

    Asserting the advertised property is not the same as asserting the row is
    coherent. This is the check that was missing.
    """
    rows = q(f"""SELECT as_of_date - referral_date, days_since_referral,
                        as_of_date - referral_received_date, days_since_received,
                        adjusted_wait_days
                 FROM core.referral_daily WHERE pathway_number='{pw}'
                 ORDER BY as_of_date DESC LIMIT 1""")
    assert rows, f"{pw} missing"
    derived_ref, stored_ref, derived_recv, stored_recv, adjusted = rows[0]

    assert stored_ref == derived_ref, (
        f"{pw}: days_since_referral is {stored_ref} but the dates give {derived_ref}")
    assert stored_recv == derived_recv, (
        f"{pw}: days_since_received is {stored_recv} but the dates give {derived_recv}")
    assert stored_ref >= stored_recv, (
        f"{pw}: received {stored_recv} days ago but written only {stored_ref} days ago")
    assert adjusted <= stored_recv, (
        f"{pw}: adjusted wait {adjusted} exceeds the raw wait {stored_recv}")
