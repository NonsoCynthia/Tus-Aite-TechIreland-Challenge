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
