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
