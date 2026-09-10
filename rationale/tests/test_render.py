import pytest

from rationale.models import EvidenceItem, EvidencePack
from rationale.render import render_rationale


def test_render_rationale_names_rank_and_cited_evidence() -> None:
    pack = EvidencePack(
        decision="decision/9004/2026-08-30",
        placement="placement/9004/2026-08-30/PW-1",
        position=3,
        referral="referral/9004/PW-1",
        pathway_number="PW-1",
        evidence=(
            EvidenceItem(
                role="urgency",
                iri="score/run-1/9004/PW-1/urgency",
                type="Score",
                properties={"scoreValue": "0.750", "method": "news2-v1"},
            ),
            EvidenceItem(
                role="capacity",
                iri="bed-status/9004/W-1/2026-08-30%2009%3A00%3A00",
                type="BedStatus",
                properties={"occupancyPct": "100.00", "surgeCapacityInUse": "2"},
            ),
            EvidenceItem(
                role="timeframe",
                iri="referral-state/9004/PW-1/2026-08-01",
                type="ReferralState",
                properties={"adjustedWaitDays": "45", "triageStatus": "triaged"},
            ),
        ),
    )

    rationale = render_rationale(pack)

    assert "Ranked #3" in rationale.text
    assert "clinician sign-off is required" in rationale.text
    for citation in rationale.citation_iris:
        assert citation in rationale.text
    assert "scoreValue=0.750" in rationale.text
    assert "occupancyPct=100.00" in rationale.text
    assert "adjustedWaitDays=45" in rationale.text


def test_render_rationale_rejects_uncited_pack() -> None:
    pack = EvidencePack(
        decision="decision/9004/2026-08-30",
        placement="placement/9004/2026-08-30/PW-1",
        position=1,
        referral="referral/9004/PW-1",
        pathway_number="PW-1",
        evidence=(),
    )

    with pytest.raises(ValueError, match="no cited evidence"):
        render_rationale(pack)


def test_unresolved_evidence_is_reported_not_silently_dropped() -> None:
    pack = EvidencePack(
        decision="decision/9004/2026-08-30",
        placement="placement/9004/2026-08-30/PW-1",
        position=1,
        referral="referral/9004/PW-1",
        pathway_number="PW-1",
        evidence=(
            EvidenceItem(
                role="urgency",
                iri="score/run-1/9004/PW-1/urgency",
                type=None,
                properties={},
            ),
        ),
    )

    rationale = render_rationale(pack)

    assert "unresolved evidence" in rationale.text
    assert "properties were not resolved" in rationale.text


def test_clinician_style_renders_accessible_prose() -> None:
    pack = EvidencePack(
        decision="decision/9001/2026-08-30",
        placement="placement/9001/2026-08-30/PW-9001-000007",
        position=None,
        referral=None,
        pathway_number="PW-9001-000007",
        evidence=(
            EvidenceItem(
                role="urgency",
                iri="score/run-1/9001/PW-9001-000007/urgency",
                type="Score",
                properties={
                    "scoreValue": "0.22499999999999998",
                    "method": "urgency-news2-v1",
                    "cites": "obs/9001/PW-9001-000007/2026-08-16%2009%3A16%3A00/spo2",
                },
            ),
            EvidenceItem(
                role="capacity",
                iri="bed-status/9001/W-9001-04/2026-08-30%2020%3A00%3A00",
                type="BedStatus",
                properties={
                    "statusOf": "ward/9001/W-9001-04",
                    "occupancyPct": "83.52",
                    "freeBeds": "15",
                },
            ),
            EvidenceItem(
                role="capacity",
                iri="clinic-session/9001/CL-9001-1800/2026-08-28",
                type="ClinicSession",
                properties={
                    "clinicName": "1800 outpatients",
                    "sessionDate": "2026-08-28",
                    "slotsAvailable": "12",
                    "slotsTotal": "25",
                },
            ),
            EvidenceItem(
                role="timeframe",
                iri="referral-state/9001/PW-9001-000007/2026-08-25",
                type="ReferralState",
                properties={
                    "triageStatus": "triaged",
                    "validFrom": "2026-08-25",
                    "hasHighClinicalOrSocialNeeds": "false",
                },
            ),
            EvidenceItem(
                role="timeframe",
                iri="rule/RULE-CRT-SEMI",
                type="Rule",
                properties={
                    "statement": "A semi-urgent referral should be seen within 13 weeks",
                    "thresholdDays": "91",
                },
            ),
        ),
    )

    rationale = render_rationale(pack, style="clinician")

    assert "Referral PW-9001-000007 is shown for clinician review" in rationale.text
    assert "urgency score is 0.225 on a 0 to 1 scale" in rationale.text
    assert "lower range" in rationale.text
    assert "oxygen saturation observation" in rationale.text
    assert "relevant ward was 83.52 percent occupied, with 15 beds free" in rationale.text
    assert "12 of 25 slots available" in rationale.text
    assert "triaged from 2026-08-25" in rationale.text
    assert "semi-urgent referral should be seen within 13 weeks" in rationale.text
    assert "Evidence nodes:" not in rationale.text
    assert "score/run-1" not in rationale.text
    assert "bed-status/9001" not in rationale.text
