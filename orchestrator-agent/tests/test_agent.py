"""agent.py tests: the tool list and instructions are exactly what
tools.py/run.py depend on -- these are structural checks (the `agents`
package must be installed to build a real Agent), not behavioural ones. The
agent's actual tool-selection behaviour is an LLM call and is verified
manually against a live key (see README.md), not unit-tested here.
"""

from __future__ import annotations

from orchestrator_agent.agent import INSTRUCTIONS, QA_INSTRUCTIONS, build_agent, build_qa_agent


def test_instructions_fix_the_pipeline_order_explicitly() -> None:
    steps = ("run_urgency_agent", "run_capacity_agent", "run_coordinator", "generate_rationale")
    for step in steps:
        assert step in INSTRUCTIONS


def test_instructions_state_the_default_capacity_direction() -> None:
    assert "pressure" in INSTRUCTIONS


def test_instructions_describe_both_pipeline_and_qa_modes() -> None:
    assert "Pipeline mode" in INSTRUCTIONS
    assert "Q&A mode" in INSTRUCTIONS
    for read_tool in (
        "get_referral_context",
        "get_wait_counters",
        "get_cohort",
        "get_decision",
        "get_evidence",
    ):
        assert read_tool in INSTRUCTIONS


def test_build_agent_exposes_exactly_the_pipeline_and_read_tools() -> None:
    agent = build_agent(model="gpt-4.1-mini")

    tool_names = {tool.name for tool in agent.tools}
    assert tool_names == {
        "run_urgency_agent",
        "run_capacity_agent",
        "run_coordinator",
        "generate_rationale",
        "get_referral_context",
        "get_wait_counters",
        "get_cohort",
        "get_decision",
        "get_evidence",
    }


def test_build_agent_uses_the_configured_model() -> None:
    agent = build_agent(model="gpt-4.1")

    assert agent.model == "gpt-4.1"


def test_build_agent_wires_the_scope_guardrail() -> None:
    agent = build_agent(model="gpt-4.1-mini")

    guardrail_names = {g.get_name() for g in agent.input_guardrails}
    assert "triage-scope-guardrail" in guardrail_names


def test_build_qa_agent_excludes_pipeline_trigger_tools() -> None:
    agent = build_qa_agent(model="gpt-4.1-mini")

    tool_names = {tool.name for tool in agent.tools}
    assert tool_names == {
        "generate_rationale",
        "get_referral_context",
        "get_wait_counters",
        "get_cohort",
        "get_decision",
        "get_evidence",
    }
    assert not {"run_urgency_agent", "run_capacity_agent", "run_coordinator"} & tool_names


def test_qa_instructions_state_browser_chat_is_read_only() -> None:
    normalised = " ".join(QA_INSTRUCTIONS.split())

    assert "browser chat is read-only" in normalised
    assert "existing UI controls" in normalised


def test_qa_instructions_route_common_list_questions_to_tools() -> None:
    normalised = " ".join(QA_INSTRUCTIONS.split())

    assert "Current facts from orchestrator state" in normalised
    assert "answer from those facts and do not call a slower tool" in normalised
    assert "waiting list MUST call get_cohort" in normalised
    assert "first/top referral" in normalised
    assert "MUST call get_decision" in normalised


def test_instructions_require_generate_rationale_for_why_questions() -> None:
    # ADR-014: "why"/"explain" questions must route through the
    # citation-guardrailed generate_rationale, never a freehand answer
    # composed from get_decision/get_evidence's raw output. Whitespace is
    # normalised since the instructions are hand-wrapped prose.
    normalised = " ".join(INSTRUCTIONS.split())
    assert "MUST be answered by calling generate_rationale" in normalised
    assert "never by composing the explanation yourself" in normalised


# --- what the 19-question permutation test caught in the browser chat ---
#
# Each of these pins a sentence in QA_INSTRUCTIONS whose absence was a live,
# reproducible wrong answer, not a hypothetical one.


def _qa() -> str:
    from orchestrator_agent.agent import QA_INSTRUCTIONS

    return " ".join(QA_INSTRUCTIONS.split())


def test_counting_is_read_from_the_facts_block_not_tallied_by_hand() -> None:
    """Asked how many were past target (130) it said "I don't have the exact
    number", then timed out, then said "there is 1 breached referral" -- three
    answers, none right, because it was counting a 305-row payload itself."""
    normalised = _qa()
    assert 'Every "how many" question MUST be answered from a count' in normalised
    assert "never by tallying rows yourself" in normalised
    # and the honest out, so a missing count is declined rather than guessed
    assert "say plainly that you do not have that count" in normalised


def test_bands_are_named_and_never_converted_back_to_cpc_codes() -> None:
    """The codes are not ordinal: CPC 3 is Semi-Urgent and CPC 2 is Routine, so
    a model reading them positionally ranks Routine above Semi-Urgent."""
    normalised = _qa()
    assert "Never convert a band back to a CPC code" in normalised
    assert "CPC 3 (Semi-Urgent) is more urgent than CPC 2 (Routine)" in normalised


def test_the_vocabulary_is_pinned_so_it_cannot_be_invented() -> None:
    """It expanded CRT as "Cancer Risk Threshold", and separately as "Clinical
    Review Time". Neither phrase exists anywhere in this system's data."""
    normalised = _qa()
    assert "CRT: Clinically Recommended Timeframe" in normalised
    assert "CPC: Clinical Prioritisation Category" in normalised
    assert "NEWS2: National Early Warning Score 2" in normalised
    assert "never invent a definition" in normalised


def test_capacity_is_defined_as_pressure_not_availability() -> None:
    """The one definition that inverts the whole system if it is read backwards
    while every number stays in range (orchestrator/app/runner.py)."""
    normalised = _qa()
    assert "capacity score: resource PRESSURE, not availability" in normalised
    assert "Higher means the service is MORE constrained" in normalised


def test_urgency_is_not_described_as_news2_over_seventeen() -> None:
    """urgency is a calibrated curve, not a division: NEWS2 7 scores 1.0, where
    7/17 would be 0.41. Stating the wrong formula is worse than stating none."""
    normalised = _qa()
    assert "NOT NEWS2 divided by 17" in normalised
    assert "a NEWS2 of 7 already scores 1.0" in normalised


def test_band_is_stated_to_outrank_priority() -> None:
    normalised = _qa()
    assert "Band comes before priority" in normalised
    assert "never moves a referral above a more urgent band" in normalised


def test_qa_mode_routes_why_questions_the_same_way_pipeline_mode_does() -> None:
    """ADR-014's clause was in INSTRUCTIONS only. Without it in QA_INSTRUCTIONS,
    "why is X first" was answered from the facts line instead, twice producing
    the exact reverse of the truth ("low urgency, NEWS2 of 1" for a referral
    whose NEWS2 is 7 and whose urgency is 1.0)."""
    normalised = _qa()
    assert "MUST be answered by calling generate_rationale" in normalised
    assert "never by composing the explanation yourself" in normalised
    assert "The facts block answers WHAT. generate_rationale answers WHY." in normalised


def test_ordering_questions_are_refused_in_the_chat_instructions_too() -> None:
    """Defence in depth: the guardrail classifies, but if a phrasing slips past
    it the agent itself must still decline rather than pick a patient."""
    normalised = _qa()
    assert "This system can SHOW the order. It must not RECOMMEND it." in normalised
    assert "choosing is the clinician's call" in normalised


def test_a_news2_of_zero_is_not_a_missing_news2() -> None:
    """146 of 305 score zero and 0 are missing. Conflating them turns "how many
    have no NEWS2 recorded" into an answer that is wrong by 146."""
    assert "A NEWS2 of 0 is a recorded score, not a missing one" in _qa()


def test_paediatric_refusals_are_named_not_just_counted() -> None:
    """The count alone does not tell the assistant WHICH referrals are refused,
    so "why is this one not ranked" sent it looking, it found no placement, and
    it reported a deliberate exclusion as missing evidence."""
    normalised = _qa()
    assert "refused_paediatric_pathways" in normalised
    assert "absent from the ranked list BY DESIGN" in normalised


def test_the_refusal_is_the_whole_answer_not_one_reason_among_several() -> None:
    """First fix left it leading with "no cited evidence" and only then giving
    the real reason. Absent citations are a consequence of the refusal."""
    normalised = _qa()
    assert "check refused_paediatric_pathways BEFORE calling any tool" in normalised
    assert "consequences of the refusal, not additional or alternative reasons" in normalised


def test_no_clinical_reading_may_be_given_for_a_refused_referral() -> None:
    normalised = _qa()
    assert "Never state or estimate such a referral's NEWS2" in normalised
    assert "even if a tool somehow returns readings for it" in normalised
