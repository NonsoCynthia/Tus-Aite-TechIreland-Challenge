"""Every foreign key in sample/ must resolve inside sample/.

Without this, a broken sampler is only discovered by a failed load, and the error
names a Postgres constraint rather than the sampler that caused it.
"""
import pytest

CHILD_TABLES = ["triage_events", "conditions", "observations",
                "cancellation_events", "suspension_events", "ground_truth"]


@pytest.fixture(scope="module")
def referral_keys(sample):
    rd = sample("referral_daily")
    return set(zip(rd.hospital_hipe, rd.pathway_number))


@pytest.mark.parametrize("table", CHILD_TABLES)
def test_child_rows_point_inside_the_sample(sample, referral_keys, table):
    df = sample(table)
    orphans = [k for k in zip(df.hospital_hipe, df.pathway_number) if k not in referral_keys]
    assert not orphans, f"{table} has {len(orphans)} rows pointing outside the sample"


def test_referral_daily_points_at_patients_in_the_sample(sample):
    rd, pat = sample("referral_daily"), sample("patients")
    keys = set(zip(pat.hospital_hipe, pat.patient_id))
    orphans = [k for k in zip(rd.hospital_hipe, rd.patient_id) if k not in keys]
    assert not orphans, f"{len(orphans)} referral rows reference an absent patient"


def test_patients_point_at_persons_in_the_sample(sample):
    pat, per = sample("patients"), sample("persons")
    known = set(per.ihi_number)
    orphans = [i for i in pat.ihi_number if i and i not in known]
    assert not orphans, f"{len(orphans)} patients reference an absent person"


def test_triage_event_ids_resolve(sample):
    rd, te = sample("referral_daily"), sample("triage_events")
    used = {i for i in rd.triage_event_id if i}
    assert not (used - set(te.triage_event_id))


def test_all_seven_demo_cases_survive_into_the_sample(sample):
    present = set(sample("referral_daily").pathway_number)
    missing = {f"PW-DEMO-{i:02d}" for i in range(1, 8)} - present
    assert not missing, f"demo cases missing from the sample: {sorted(missing)}"


def test_the_planted_collision_survives_into_the_sample(sample):
    """The collision must be between 9001 and 9002 specifically.

    make_sample seeds from exactly those two hospitals. A collision planted
    anywhere else would never reach sample/, this test would pass, and the
    referential collision test would silently prove nothing on the default profile.
    """
    rd = sample("referral_daily")
    pairs = len(set(zip(rd.hospital_hipe, rd.pathway_number)))
    alone = rd.pathway_number.nunique()
    assert pairs > alone, "no cross-hospital collision in the sample"

    hosps = sorted(rd[rd.pathway_number == "PW-COLLIDE-01"].hospital_hipe.unique())
    assert hosps == ["9001", "9002"], f"collision is at {hosps}, not the sampled hospitals"
