"""Plain, undecorated tool implementations -- agent.py wraps these with the
OpenAI Agents SDK's `function_tool`. Kept undecorated here so every one of
them is an ordinary Python function, directly unit-testable with no SDK, no
network, and no API key (tests/test_tools.py).

Two kinds of tool, both bounded the same way every ADR in this repo already
requires: they *trigger* one of the existing deterministic packages exactly
as its own CLI already runs it, or they *read* what a package already wrote.
Neither kind computes a score, reorders a ranking, or invents a citation --
the LLM decides *when* to call these, never *what they compute*.

- run_urgency_agent / run_capacity_agent / run_coordinator: shell out to the
  root Makefile's `*-run` targets (unchanged) -- the same targets a human
  operator already runs by hand. Each one is `make`'s own concern to know
  how to execute (Docker, network, env) -- this module has no opinion on
  that and would not need to change if the team's execution strategy did.
- generate_rationale: imports `rationale` directly (sys.path-injected, the
  same PYTHONPATH=<package> convention the Makefile itself already uses for
  every sibling package) and calls its already-guardrailed
  `render_rationale_llm` (ADR-010) per placement -- never re-implements
  evidence fetching or rendering.
- get_referral_context / get_wait_counters / get_cohort / get_decision /
  get_evidence: read-only GETs against retrieval-service_20260904 (ADR-012),
  backing the clinician Q&A mode. These can never write anything -- the
  clinician asking a question can prompt the model into calling any number
  of them, in any order, without touching the determinism boundary the
  trigger tools hold.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Literal

from .config import load_settings, repo_root
from .retrieval_client import RetrievalClient as QARetrievalClient
from .retrieval_client import RetrievalClientError

RationaleStyle = Literal["clinician", "technical"]
CitationRole = Literal["urgency", "capacity", "timeframe", "multi_list"]

# `rationale` is a top-level package (rationale/__init__.py) -- the repo
# root must be on sys.path for `import rationale.client` etc. to resolve,
# not rationale/ itself (which would look for rationale/rationale/...).
_REPO_ROOT_STR = str(repo_root())
if _REPO_ROOT_STR not in sys.path:
    sys.path.insert(0, _REPO_ROOT_STR)

# Module-level, not lazy: unlike `agents` (an optional, heavy SDK confined to
# agent.py/run.py), `rationale` is a required, lightweight dependency of this
# specific tool (httpx + pydantic, both already in requirements.txt) --
# importing it here also lets tests monkeypatch these names directly on
# `tools`, rather than needing to patch inside a function-local import.
from rationale.client import RetrievalClient, RetrievalServiceError  # noqa: E402
from rationale.config import Settings as RationaleSettings  # noqa: E402
from rationale.config import load_settings as load_rationale_settings  # noqa: E402
from rationale.evidence_pack import packs_from_decision_response  # noqa: E402
from rationale.llm_render import (  # noqa: E402
    AgentRunError,
    RationaleGuardrailError,
    render_rationale_llm,
)
from rationale.models import EvidencePack, Rationale  # noqa: E402
from rationale.render import render_rationale  # noqa: E402

# Output is a tool-call result the LLM reads directly -- keep it bounded so
# one verbose CLI run can't blow out the model's context.
_MAX_OUTPUT_CHARS = 4000
_MAKE_TIMEOUT_SECONDS = 900.0


class ToolExecutionError(RuntimeError):
    """A wrapped `make` target could not be run at all (missing `make`,
    timed out) -- distinct from the target running and reporting a non-zero
    exit, which is returned as text for the agent to read and explain, not
    raised: `coordinator-run`'s own 207/400/422 exit codes are meaningful
    results, not failures of this tool."""


def _run_make_target(target: str, cwd: Path | None = None, **make_vars: str) -> str:
    args = ["make", target, *(f"{key}={value}" for key, value in make_vars.items())]
    try:
        result = subprocess.run(
            args,
            cwd=cwd or repo_root(),
            capture_output=True,
            text=True,
            timeout=_MAKE_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        raise ToolExecutionError(f"`make` is not on PATH: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ToolExecutionError(
            f"`{' '.join(args)}` did not finish within {_MAKE_TIMEOUT_SECONDS:.0f}s"
        ) from exc

    output = (result.stdout + result.stderr).strip()
    summary = f"exit code {result.returncode}\n{output}"
    return summary[-_MAX_OUTPUT_CHARS:]


def run_urgency_agent(hospital_hipe: str, as_of_date: str, run_id: str) -> str:
    """Scores every referral in one hospital-day's cohort with the urgency
    agent (NEWS2, ADR-004) and writes each score via POST /scores.

    Args:
        hospital_hipe: 4-character HIPE hospital code, e.g. "9001".
        as_of_date: ISO date, e.g. "2026-08-30".
        run_id: Shared run_id for this pipeline run -- capacity and the
            coordinator must use the same value to find these scores.

    Returns:
        The CLI's own exit code and output, e.g. how many referrals were
        scored, refused (paediatric, ADR-007), or skipped.
    """
    return _run_make_target("urgency-run", HOSPITAL=hospital_hipe, AS_OF=as_of_date, RUN_ID=run_id)


def run_capacity_agent(hospital_hipe: str, as_of_date: str, run_id: str) -> str:
    """Scores every referral in one hospital-day's cohort with the capacity
    agent (ward/clinic resource pressure, ADR-003) and writes each score via
    POST /scores.

    Args:
        hospital_hipe: 4-character HIPE hospital code, e.g. "9001".
        as_of_date: ISO date, e.g. "2026-08-30".
        run_id: Must match the run_id already used for run_urgency_agent.

    Returns:
        The CLI's own exit code and output.
    """
    return _run_make_target("capacity-run", HOSPITAL=hospital_hipe, AS_OF=as_of_date, RUN_ID=run_id)


def run_coordinator(
    hospital_hipe: str, as_of_date: str, run_id: str, capacity_direction: str = "pressure"
) -> str:
    """Ranks one hospital-day's cohort from the urgency and capacity scores
    already written under run_id, and writes the Decision via POST
    /decisions. Must be called after run_urgency_agent and
    run_capacity_agent for the same run_id -- a referral missing an urgency
    score is excluded and reported, never defaulted (ADR-008,
    coordinating-agent_20260906).

    Args:
        hospital_hipe: 4-character HIPE hospital code, e.g. "9001".
        as_of_date: ISO date, e.g. "2026-08-30".
        run_id: Must match the run_id used for both scoring agents.
        capacity_direction: Always "pressure" for this system's capacity
            agent (ADR-007/ADR-003) -- do not pass "availability" unless a
            human has explicitly asked you to, since it inverts every
            capacity-weighted ranking.

    Returns:
        The CLI's own exit code and output.
    """
    return _run_make_target(
        "coordinator-run",
        HOSPITAL=hospital_hipe,
        AS_OF=as_of_date,
        RUN_ID=run_id,
        CAPACITY_DIRECTION=capacity_direction,
    )


def generate_rationale(
    hospital_hipe: str,
    as_of_date: str,
    style: RationaleStyle = "clinician",
    limit: int = 5,
    pathway_number: str | None = None,
) -> str:
    """Explains an already-ranked Decision: fetches every placement's cited
    evidence from the retrieval service and renders rationale text for each,
    via this system's OpenAI-backed, citation-guardrailed rationale engine
    (ADR-010). This is the ONLY tool that should be used to answer a "why"
    or "explain" question -- e.g. "why is this referral ranked here", "why
    is X ranked above Y". Never compose that kind of explanation yourself
    from get_decision/get_evidence's raw JSON (ADR-014): unlike this tool,
    those return unverified data, with no check that a sentence built from
    them actually matches what they say. Use get_decision/get_evidence
    instead when the clinician wants the raw facts or graph node
    references, not an explanation.

    Must be called after run_coordinator has written a Decision for this
    (hospital_hipe, as_of_date) -- if none exists yet, this reports that
    rather than inventing one.

    Args:
        hospital_hipe: 4-character HIPE hospital code, e.g. "9001".
        as_of_date: ISO date, e.g. "2026-08-30".
        style: "clinician" (default, short readable prose) or "technical"
            (structured audit detail).
        limit: Maximum number of ranked placements to explain when
            pathway_number is not given, highest priority first -- keeps
            tool-call latency and OpenAI cost bounded for a large cohort.
            Default 5. Ignored when pathway_number is given (exactly one
            placement is explained).
        pathway_number: Explain only this one referral's ranked position --
            use this whenever the question is about a specific referral,
            e.g. "why is PW-9001-000007 ranked here". Omit to explain the
            top `limit` placements instead.

    Returns:
        One rationale per explained placement, in ranked order. If
        pathway_number was given but isn't in this hospital-day's Decision,
        says so plainly rather than explaining a different placement.
    """
    settings = load_rationale_settings()
    if pathway_number is not None:
        try:
            with RetrievalClient(settings.retrieval_base_url, settings.bearer_token) as client:
                evidence_response = client.get_placement_evidence(
                    hospital_hipe,
                    as_of_date,
                    pathway_number,
                )
        except RetrievalServiceError as exc:
            return (
                f"could not fetch the evidence for {hospital_hipe}/{as_of_date}/"
                f"{pathway_number}: {exc}"
            )

        pack = EvidencePack.from_evidence_response(
            decision=f"decision/{hospital_hipe}/{as_of_date}",
            pathway_number=pathway_number,
            response=evidence_response,
        )
        if not pack.evidence:
            return (
                f"{pathway_number} has no cited evidence in the Decision for "
                f"{hospital_hipe}/{as_of_date}"
            )
        rationale = _render_rationale_for_tool(pack, style=style, settings=settings)
        return rationale.text

    try:
        with RetrievalClient(settings.retrieval_base_url, settings.bearer_token) as client:
            decision = client.get_decision(hospital_hipe, as_of_date)
    except RetrievalServiceError as exc:
        return f"could not fetch the decision for {hospital_hipe}/{as_of_date}: {exc}"

    packs = packs_from_decision_response(decision)
    if not packs:
        return (
            f"no ranked placements found for {hospital_hipe}/{as_of_date} -- "
            "has run_coordinator been called for this hospital-day yet?"
        )

    packs = packs[:limit]

    rendered = []
    for pack in packs:
        rationale = _render_rationale_for_tool(pack, style=style, settings=settings)
        rendered.append(rationale.text)
    return "\n\n".join(rendered)


def _render_rationale_for_tool(
    pack: EvidencePack, *, style: RationaleStyle, settings: RationaleSettings
) -> Rationale:
    try:
        return render_rationale_llm(pack, style=style, settings=settings)
    except (AgentRunError, RationaleGuardrailError):
        return render_rationale(pack, style=style)


PAEDIATRIC_REFUSAL = (
    "This referral is in the paediatric specialty, and this system refuses to "
    "score paediatric referrals rather than scoring them badly (ADR-007). NEWS2 "
    "is an adult early warning score and is not validated in children, whose "
    "normal vital-sign ranges differ: a resting heart rate that scores in an "
    "adult is unremarkable in a small child. So this referral has no urgency "
    "score, no NEWS2, and no place in the ranked list.\n\n"
    "That absence is a deliberate, recorded exclusion, NOT missing evidence, an "
    "incomplete record, or a referral still awaiting triage. Say so plainly if "
    "asked why it is not ranked.\n\n"
    "Its vital signs and clinical observations are withheld here on purpose, "
    "because quoting them invites exactly the adult-scale reading the refusal "
    "exists to prevent. Do not state or estimate this referral's NEWS2, urgency, "
    "vital signs or acuity, and do not compare it with another referral on any "
    "of those grounds. A clinician needing these readings should use the "
    "paediatric pathway, which uses PEWS rather than NEWS2."
)
"""What the read-only tools return in place of a refused referral's vitals.

ADR-007 refuses paediatric referrals at scoring time, but the Q&A tools read
retrieval directly and so never passed through that decision: asked for one of
these referrals, they handed back the whole context payload, vitals included,
and the assistant duly scored a child on an adult scale in prose. Enforced here
rather than in the instructions because an instruction is a preference the
model can be argued out of, and this is the system's clearest safety claim.
"""


def _refused_paediatric(context: dict[str, Any]) -> bool:
    """Whether a context payload belongs to a refused paediatric referral.

    Exact match, never a prefix: specialty 0600 differs by one character and is
    NOT paediatric (urgency_agent.scoring). The specialty is the only paediatric
    signal available, since the context endpoint returns no patient age.
    """
    from urgency_agent.scoring import PAEDIATRIC_SPECIALTY

    referral = context.get("referral") or {}
    return str(referral.get("specialty_hipe") or "") == PAEDIATRIC_SPECIALTY


def _qa_client() -> QARetrievalClient:
    settings = load_settings()
    return QARetrievalClient(settings.retrieval_base_url, settings.bearer_token)


def _format_json(data: object) -> str:
    return json.dumps(data, indent=2, default=str)[:_MAX_OUTPUT_CHARS]


def get_referral_context(hospital_hipe: str, pathway_number: str) -> str:
    """Answers "what do we know about this referral": its own record
    (specialty, dates, triage status), every observation (vitals),
    condition, and triage event, plus capacity data for its specialty
    (wards, latest bed status, recent clinic sessions).

    Args:
        hospital_hipe: 4-character HIPE hospital code, e.g. "9001".
        pathway_number: The referral's pathway number, e.g. "PW-9001-000007".

    Returns:
        The raw context as JSON, or a plain-language error if the referral
        doesn't exist. For a paediatric referral the clinical half is withheld
        and PAEDIATRIC_REFUSAL is returned in its place (ADR-007); the
        administrative record is still returned, since the referral's dates,
        specialty and triage status are not the thing being refused.
    """
    try:
        with _qa_client() as client:
            data = client.get_referral_context(hospital_hipe, pathway_number)
    except RetrievalClientError as exc:
        return f"could not fetch context for {hospital_hipe}/{pathway_number}: {exc}"
    if _refused_paediatric(data):
        return f"{PAEDIATRIC_REFUSAL}\n\nAdministrative record only:\n" + _format_json(
            {"referral": data.get("referral") or {}}
        )
    return _format_json(data)


def get_wait_counters(hospital_hipe: str, pathway_number: str, as_of_date: str) -> str:
    """Answers "how long has this referral been waiting": days since
    referral, days since received, days awaiting triage, and the
    suspension-adjusted wait -- the same four counters every agent and the
    rule checker use, from one shared source (kg/queries/wait_counters.rq).

    Args:
        hospital_hipe: 4-character HIPE hospital code, e.g. "9001".
        pathway_number: The referral's pathway number, e.g. "PW-9001-000007".
        as_of_date: ISO date to compute the counters as of, e.g. "2026-08-30".

    Returns:
        The four counters as JSON, or a plain-language error if there's no
        data for that referral/date in the graph.
    """
    try:
        with _qa_client() as client:
            data = client.get_wait_counters(hospital_hipe, pathway_number, as_of_date)
    except RetrievalClientError as exc:
        return f"could not fetch wait counters for {hospital_hipe}/{pathway_number}: {exc}"
    return _format_json(data)


def get_cohort(hospital_hipe: str, as_of_date: str) -> str:
    """Answers "which referrals are on the waiting list, and has this one
    been ranked yet": every referral still on the list for that
    hospital-day, oldest first, with CPC, wait counters, and whether its
    CRT has been breached.

    Args:
        hospital_hipe: 4-character HIPE hospital code, e.g. "9001".
        as_of_date: ISO date, e.g. "2026-08-30".

    Returns:
        The cohort as JSON. An empty `referrals` list means nothing is on
        the list that day, not an error.
    """
    try:
        with _qa_client() as client:
            data = client.get_cohort(hospital_hipe, as_of_date)
    except RetrievalClientError as exc:
        return f"could not fetch the cohort for {hospital_hipe}/{as_of_date}: {exc}"
    return _format_json(data)


def get_decision(hospital_hipe: str, as_of_date: str) -> str:
    """Answers "what's the ranked list": every ranked placement for that
    hospital-day, in order, with its cited evidence already resolved to raw
    graph-backed data (IRIs, property values) -- NOT prose, and not
    verified for faithfulness the way generate_rationale's output is
    (ADR-014). Use this only when the clinician wants the underlying facts
    or graph node references themselves. For any "why" or "explain"
    question -- including "why is X ranked here" -- call generate_rationale
    instead of writing that explanation yourself from this tool's output.

    Args:
        hospital_hipe: 4-character HIPE hospital code, e.g. "9001".
        as_of_date: ISO date, e.g. "2026-08-30".

    Returns:
        The decision as JSON, or a plain-language message if nothing has
        been ranked for that hospital-day yet.
    """
    try:
        with _qa_client() as client:
            data = client.get_decision(hospital_hipe, as_of_date)
    except RetrievalClientError as exc:
        if "404" in str(exc):
            return (
                f"no decision found for {hospital_hipe}/{as_of_date} -- "
                "has run_coordinator been called for this hospital-day yet?"
            )
        return f"could not fetch the decision for {hospital_hipe}/{as_of_date}: {exc}"
    return _format_json(data)


def get_evidence(
    hospital_hipe: str, as_of_date: str, pathway_number: str, role: CitationRole | None = None
) -> str:
    """Answers "what evidence supports this specific ranked position": one
    placement's cited evidence, resolved to real values. Narrower than
    get_decision (one placement, not the whole list) and, like
    get_decision, raw and unverified rather than prose -- do not compose a
    "why"/"explain" answer from this tool's output; call generate_rationale
    instead (see get_decision's own note, ADR-014).

    Args:
        hospital_hipe: 4-character HIPE hospital code, e.g. "9001".
        as_of_date: ISO date, e.g. "2026-08-30".
        pathway_number: The ranked referral's pathway number.
        role: Narrow to one citation role (urgency/capacity/timeframe/
            multi_list), or omit for all four.

    Returns:
        The resolved evidence as JSON. A refused paediatric referral has no
        placement and so no citations; rather than report that as an empty
        result, which reads as a gap in the data, this returns the actual
        reason (ADR-007).
    """
    try:
        with _qa_client() as client:
            data = client.get_evidence(hospital_hipe, as_of_date, pathway_number, role=role)
            # Only on the empty path, so the ordinary case still costs one call.
            # "No citations" and "deliberately excluded" look identical from
            # here, and answering the first when it is the second told a
            # clinician the evidence was missing for a referral the system had
            # in fact refused on purpose.
            if not _has_citations(data):
                try:
                    context = client.get_referral_context(hospital_hipe, pathway_number)
                except RetrievalClientError:
                    context = {}
                if context and _refused_paediatric(context):
                    return PAEDIATRIC_REFUSAL
    except RetrievalClientError as exc:
        return (
            f"could not fetch evidence for {hospital_hipe}/{as_of_date}/{pathway_number}: {exc}"
        )
    return _format_json(data)


def _has_citations(data: object) -> bool:
    """Whether an evidence payload actually carries anything.

    Shape-tolerant on purpose: this decides only whether to spend one more call
    working out WHY a result is empty, so an unfamiliar shape should read as
    non-empty and leave the payload untouched.
    """
    if isinstance(data, dict):
        for key in ("citations", "evidence", "placements"):
            if key in data:
                return bool(data[key])
        return bool(data)
    return bool(data)
