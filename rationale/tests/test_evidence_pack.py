import pytest

from rationale.evidence_pack import packs_from_decision_response, select_pack


def test_packs_from_decision_response_preserves_ranking_order() -> None:
    response = {
        "decision": "decision/9004/2026-08-30",
        "placements": [
            {
                "placement": "placement/9004/2026-08-30/PW-1",
                "position": 1,
                "referral": "referral/9004/PW-1",
                "pathway_number": "PW-1",
                "evidence": [
                    {
                        "role": "urgency",
                        "iri": "score/run-1/9004/PW-1/urgency",
                        "type": "Score",
                        "properties": {"scoreValue": "0.75"},
                    }
                ],
            },
            {
                "placement": "placement/9004/2026-08-30/PW-2",
                "position": 2,
                "referral": "referral/9004/PW-2",
                "pathway_number": "PW-2",
                "evidence": [
                    {
                        "role": "capacity",
                        "iri": "score/run-1/9004/PW-2/capacity",
                        "type": "Score",
                        "properties": {"scoreValue": "0.40"},
                    }
                ],
            },
        ],
    }

    packs = packs_from_decision_response(response)

    assert [pack.pathway_number for pack in packs] == ["PW-1", "PW-2"]
    assert packs[0].decision == "decision/9004/2026-08-30"
    assert select_pack(packs, "PW-2").position == 2


def test_packs_from_decision_response_rejects_uncited_placement() -> None:
    response = {
        "decision": "decision/9004/2026-08-30",
        "placements": [
            {
                "placement": "placement/9004/2026-08-30/PW-1",
                "position": 1,
                "referral": "referral/9004/PW-1",
                "pathway_number": "PW-1",
                "evidence": [],
            }
        ],
    }

    with pytest.raises(ValueError, match="no cited evidence"):
        packs_from_decision_response(response)


def test_select_pack_reports_missing_pathway() -> None:
    response = {
        "decision": "decision/9004/2026-08-30",
        "placements": [
            {
                "placement": "placement/9004/2026-08-30/PW-1",
                "position": 1,
                "referral": "referral/9004/PW-1",
                "pathway_number": "PW-1",
                "evidence": [
                    {
                        "role": "urgency",
                        "iri": "score/run-1/9004/PW-1/urgency",
                        "type": "Score",
                        "properties": {},
                    }
                ],
            }
        ],
    }
    packs = packs_from_decision_response(response)

    with pytest.raises(ValueError, match="PW-404"):
        select_pack(packs, "PW-404")
