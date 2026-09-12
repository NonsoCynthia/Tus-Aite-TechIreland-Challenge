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
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Literal

from .config import repo_root

RationaleStyle = Literal["clinician", "technical"]

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
from rationale.config import load_settings as load_rationale_settings  # noqa: E402
from rationale.evidence_pack import packs_from_decision_response  # noqa: E402
from rationale.llm_render import render_rationale_llm  # noqa: E402

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
    hospital_hipe: str, as_of_date: str, style: RationaleStyle = "clinician", limit: int = 5
) -> str:
    """Explains an already-ranked Decision: fetches every placement's cited
    evidence from the retrieval service and renders rationale text for each,
    via this system's OpenAI-backed rationale engine (ADR-010). Must be
    called after run_coordinator has written a Decision for this
    (hospital_hipe, as_of_date) -- if none exists yet, this reports that
    rather than inventing one.

    Args:
        hospital_hipe: 4-character HIPE hospital code, e.g. "9001".
        as_of_date: ISO date, e.g. "2026-08-30".
        style: "clinician" (default, short readable prose) or "technical"
            (structured audit detail).
        limit: Maximum number of ranked placements to explain, highest
            priority first -- keeps tool-call latency and OpenAI cost
            bounded for a large cohort. Default 5.

    Returns:
        One rationale per explained placement, in ranked order.
    """
    settings = load_rationale_settings()
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

    rendered = []
    for pack in packs[:limit]:
        rationale = render_rationale_llm(pack, style=style, settings=settings)
        rendered.append(rationale.text)
    return "\n\n".join(rendered)
