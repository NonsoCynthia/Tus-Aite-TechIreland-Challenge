"""Does the generated data behave like real triage data?

These catch a generator producing structurally valid nonsense. The most important
one is test_not_cleaner_than_reality.

A note on what replaced the original correlation band. BUILD_MANUAL section 10.4
required the news2 x severity_rank correlation to fall in 0.35-0.65. That band was
specified without checking whether NEWS2 discriminates triage acuity, and the
Phase 3b fit showed it does not: peak |r| of 0.253 across a coupling sweep of
0.3-5.0. The band was also measuring the wrong quantity. It asked whether vitals
predict WHICH CATEGORY a patient is in, but this system never assigns categories
-- triage does, and RULE-ORDER forbids ever crossing a category boundary. The
system orders patients WITHIN a category.

So the band is replaced by a realism check anchored in the source data, plus a
within-category discriminability check, which is what a within-category ranker
actually depends on. See docs/CALIBRATION_FINDINGS.md.
"""
import numpy as np
import pandas as pd
import pytest

SEVERITY_RANK = {1: 1, 3: 2, 2: 3}


def auc(pos, neg):
    """AUC via the Mann-Whitney U statistic; average ranks handle ties."""
    pos, neg = np.asarray(pos, float), np.asarray(neg, float)
    r = pd.Series(np.concatenate([pos, neg])).rank().values
    n1, n2 = len(pos), len(neg)
    return (r[:n1].sum() - n1 * (n1 + 1) / 2) / (n1 * n2)


@pytest.fixture(scope="module")
def scored(q):
    """Rows for the distribution checks.

    These assert properties of the DATASET. Measured on the 609-referral sample
    they are dominated by sampling noise -- a 4.6 per cent share is about 8 rows --
    so they require the full profile and skip otherwise rather than failing
    spuriously or being loosened until a slice passes.
    """
    rows = q("""SELECT t.triage_category, o.news2
                FROM core.observations o
                JOIN core.referral_daily d USING (hospital_hipe, pathway_number)
                JOIN core.triage_events t ON t.triage_event_id = d.triage_event_id
                WHERE o.news2 IS NOT NULL AND t.triage_category IS NOT NULL
                GROUP BY t.triage_category, o.news2, o.hospital_hipe, o.pathway_number""")
    df = pd.DataFrame(rows, columns=["cat", "news2"]).astype({"news2": float})
    if len(df) < 2000:
        pytest.skip(f"only {len(df)} scored referrals loaded; these are dataset-level "
                    f"checks, not slice-level ones. Load the full set: "
                    f"make load FETCH_PROFILE=full")
    return df


def test_not_cleaner_than_reality(scored, cal):
    """The generated data must not separate Urgent from Semi-Urgent more cleanly
    than the real MIMIC rows do.

    The threshold is not a chosen number: it is measured from the same source the
    distributions came from. One-sided on purpose -- looser overlap than reality
    passes, because the direction worth catching is a generator tuned into
    producing tidier-than-real separation.

    Routine is excluded. It is derived from reference ranges rather than fitted
    (MIMIC's demo has 2 ESI 4-5 stays), and would otherwise let a revision of
    those ranges move a metric that is supposed to track the data.
    """
    gate = cal["realism_gate"]
    anchor = gate["auc_mimic"]["value"]
    tol = gate["tolerance"]["value"]

    urgent = scored[scored.cat == 1]["news2"]
    semi = scored[scored.cat == 3]["news2"]
    assert len(urgent) > 50 and len(semi) > 50, "too few rows to measure"

    got = auc(urgent, semi)
    assert got <= anchor + tol, (
        f"generated AUC {got:.4f} exceeds {anchor:.4f} + {tol} = {anchor + tol:.4f}. "
        f"The synthetic data separates the categories more cleanly than real triage "
        f"data does.")


@pytest.mark.parametrize("cat,label,min_sd,lo,hi", [
    (1, "Urgent", 1.5, 0.10, 0.45),
    (3, "Semi-Urgent", 1.0, 0.01, 0.20),
])
def test_within_category_discriminability(scored, cat, label, min_sd, lo, hi):
    """A within-category ranker needs spread to order on.

    Thresholds derived from the MIMIC-fitted distributions before any generated
    data was measured: Urgent sd 1.81, share news2>=4 26.9%; Semi-Urgent sd 1.19,
    share 4.6%. If every urgent patient scored identically the urgency agent could
    not distinguish them and the project would have no job to do.
    """
    s = scored[scored.cat == cat]["news2"]
    q1, q3 = np.percentile(s, [25, 75])
    assert s.std() >= min_sd, f"{label} news2 sd {s.std():.2f} < {min_sd}"
    assert q3 - q1 >= 1, f"{label} news2 IQR span {q3 - q1} is too narrow"
    assert lo <= (s >= 4).mean() <= hi, f"{label} share with news2>=4 out of range"


def test_urgent_referrals_include_physiologically_well_patients(scored):
    """BUILD_MANUAL section 10.4, and the one assertion from it that survived.

    A suspected melanoma is urgent because of the referral pathway, not the
    physiology, and the dataset must contain such patients.
    """
    urgent = scored[scored.cat == 1]["news2"]
    assert (urgent <= 2).mean() >= 0.15


def test_ed_case_mix_has_not_leaked_into_the_waiting_list(q):
    """MIMIC is an emergency department cohort, 55.6 per cent urgent. An outpatient
    waiting list is close to the inverse. Vitals come from MIMIC; the category mix
    must not."""
    rows = q("""SELECT t.triage_category, count(*) FROM core.triage_events t
                WHERE t.triage_category IS NOT NULL GROUP BY 1""")
    total = sum(n for _, n in rows)
    urgent = next((n for c, n in rows if c == 1), 0)
    assert urgent / total < 0.40, (
        f"{urgent / total:.1%} of referrals are Urgent. That resembles an ED cohort, "
        f"not a waiting list -- MIMIC's mix has leaked in.")


def test_national_identifier_coverage_is_deliberately_incomplete(q):
    """Roughly a third of patients have no IHI. The gap is the point: it shows
    what a national shared care record would fix."""
    total = q("SELECT count(*) FROM core.patients")[0][0]
    with_ihi = q("SELECT count(*) FROM core.patients WHERE ihi_number IS NOT NULL")[0][0]
    assert 0.50 <= with_ihi / total <= 0.80


def test_breach_rate_matches_what_ntpf_implies(q, scored):
    """BUILD_MANUAL section 10.4 expected fewer than 40 per cent of referrals to
    breach their timeframe. NTPF's own published wait bands imply about 91 per cent
    for the 28-day urgent target: 28 days is under one month, and only 59.6 per cent
    of the national list waits under six months.

    So the assertion is anchored to the source rather than to the original guess.
    The generator draws waits from those bands, so the two should agree; a wide gap
    means the wait model has drifted away from NTPF. See docs/CALIBRATION_FINDINGS.md.
    """
    import yaml
    from pathlib import Path
    cal = yaml.safe_load(
        (Path(__file__).resolve().parent.parent / "generator" / "calibration"
         / "specialty_mix.yml").read_text())
    b = cal["national_wait_band_distribution"]
    implied = b["m0_6"] * (183 - 28) / 182 + b["m6_12"] + b["m12_18"] + b["m18_plus"]

    got = q("""SELECT count(*) FILTER (WHERE d.adjusted_wait_days > 28)::float / count(*)
               FROM core.referral_daily d
               JOIN core.triage_events t ON t.triage_event_id = d.triage_event_id
               WHERE t.triage_category = 1""")[0][0]

    assert abs(got - implied) < 0.05, (
        f"urgent breach rate {got:.3f} differs from the NTPF-implied {implied:.3f} "
        f"by more than 5 points; the wait model has drifted from the fitted bands")
