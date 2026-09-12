"""tools.py tests: every trigger tool's `make` invocation, and
generate_rationale's wiring into `rationale`, mocked at the module boundary
-- no live retrieval service, no `make`, no OpenAI key needed.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

import pytest

from orchestrator_agent import tools
from orchestrator_agent.tools import ToolExecutionError
from rationale.client import RetrievalServiceError
from rationale.config import Settings as RationaleSettings
from rationale.models import EvidenceItem, EvidencePack, Rationale


@dataclass
class _FakeCompletedProcess:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class TestRunMakeTarget:
    def test_builds_the_documented_make_invocation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        captured: dict[str, object] = {}

        def fake_run(args: list[str], **kwargs: object) -> _FakeCompletedProcess:
            captured["args"] = args
            captured["kwargs"] = kwargs
            return _FakeCompletedProcess(returncode=0, stdout="scored 3 referral(s)")

        monkeypatch.setattr(subprocess, "run", fake_run)

        output = tools._run_make_target("urgency-run", HOSPITAL="9001", AS_OF="2026-08-30")

        assert captured["args"] == [
            "make",
            "urgency-run",
            "HOSPITAL=9001",
            "AS_OF=2026-08-30",
        ]
        assert "exit code 0" in output
        assert "scored 3 referral(s)" in output

    def test_non_zero_exit_is_returned_as_text_not_raised(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # coordinator-run's own 207/400/422 exit codes are meaningful results
        # the agent should read and explain, not tool failures.
        def fake_run(args: list[str], **kwargs: object) -> _FakeCompletedProcess:
            return _FakeCompletedProcess(returncode=207, stdout="", stderr="partial failure")

        monkeypatch.setattr(subprocess, "run", fake_run)

        output = tools._run_make_target("coordinator-run", HOSPITAL="9001")

        assert "exit code 207" in output
        assert "partial failure" in output

    def test_missing_make_binary_raises_tool_execution_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_run(args: list[str], **kwargs: object) -> _FakeCompletedProcess:
            raise FileNotFoundError("make")

        monkeypatch.setattr(subprocess, "run", fake_run)

        with pytest.raises(ToolExecutionError, match="not on PATH"):
            tools._run_make_target("urgency-run", HOSPITAL="9001")

    def test_timeout_raises_tool_execution_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_run(args: list[str], **kwargs: object) -> _FakeCompletedProcess:
            raise subprocess.TimeoutExpired(cmd="make", timeout=900.0)

        monkeypatch.setattr(subprocess, "run", fake_run)

        with pytest.raises(ToolExecutionError, match="did not finish"):
            tools._run_make_target("coordinator-run", HOSPITAL="9001")

    def test_output_is_truncated_to_the_tail(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def fake_run(args: list[str], **kwargs: object) -> _FakeCompletedProcess:
            return _FakeCompletedProcess(returncode=0, stdout="x" * 10_000)

        monkeypatch.setattr(subprocess, "run", fake_run)

        output = tools._run_make_target("urgency-run", HOSPITAL="9001")

        assert len(output) <= tools._MAX_OUTPUT_CHARS


class TestTriggerTools:
    def test_run_urgency_agent_passes_the_right_make_vars(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, object] = {}
        monkeypatch.setattr(
            tools,
            "_run_make_target",
            lambda target, **kwargs: captured.update(target=target, **kwargs) or "ok",
        )

        result = tools.run_urgency_agent("9001", "2026-08-30", "run-1")

        assert result == "ok"
        assert captured == {
            "target": "urgency-run",
            "HOSPITAL": "9001",
            "AS_OF": "2026-08-30",
            "RUN_ID": "run-1",
        }

    def test_run_capacity_agent_passes_the_right_make_vars(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, object] = {}
        monkeypatch.setattr(
            tools,
            "_run_make_target",
            lambda target, **kwargs: captured.update(target=target, **kwargs) or "ok",
        )

        tools.run_capacity_agent("9001", "2026-08-30", "run-1")

        assert captured == {
            "target": "capacity-run",
            "HOSPITAL": "9001",
            "AS_OF": "2026-08-30",
            "RUN_ID": "run-1",
        }

    def test_run_coordinator_defaults_capacity_direction_to_pressure(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, object] = {}
        monkeypatch.setattr(
            tools,
            "_run_make_target",
            lambda target, **kwargs: captured.update(target=target, **kwargs) or "ok",
        )

        tools.run_coordinator("9001", "2026-08-30", "run-1")

        assert captured == {
            "target": "coordinator-run",
            "HOSPITAL": "9001",
            "AS_OF": "2026-08-30",
            "RUN_ID": "run-1",
            "CAPACITY_DIRECTION": "pressure",
        }

    def test_run_coordinator_honours_an_explicit_capacity_direction(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, object] = {}
        monkeypatch.setattr(
            tools,
            "_run_make_target",
            lambda target, **kwargs: captured.update(target=target, **kwargs) or "ok",
        )

        tools.run_coordinator("9001", "2026-08-30", "run-1", capacity_direction="availability")

        assert captured["CAPACITY_DIRECTION"] == "availability"


def _rationale_settings() -> RationaleSettings:
    return RationaleSettings(
        retrieval_base_url="http://retrieval.test",
        bearer_token="tok",
        openai_api_key="sk-test",
        openai_model="gpt-4.1-mini",
    )


class _FakeRetrievalClient:
    def __init__(self, decision: dict | None = None, error: Exception | None = None) -> None:
        self._decision = decision
        self._error = error

    def __call__(self, base_url: str, bearer_token: str) -> _FakeRetrievalClient:
        return self

    def __enter__(self) -> _FakeRetrievalClient:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def get_decision(self, hospital_hipe: str, as_of_date: str) -> dict:
        if self._error is not None:
            raise self._error
        assert self._decision is not None
        return self._decision


class TestGenerateRationale:
    def test_reports_a_clear_message_when_retrieval_fails(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(tools, "load_rationale_settings", _rationale_settings)
        monkeypatch.setattr(
            tools, "RetrievalClient", _FakeRetrievalClient(error=RetrievalServiceError("boom"))
        )

        result = tools.generate_rationale("9001", "2026-08-30")

        assert "could not fetch" in result
        assert "boom" in result

    def test_reports_a_clear_message_when_no_decision_exists_yet(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(tools, "load_rationale_settings", _rationale_settings)
        monkeypatch.setattr(tools, "RetrievalClient", _FakeRetrievalClient(decision={}))
        monkeypatch.setattr(tools, "packs_from_decision_response", lambda decision: [])

        result = tools.generate_rationale("9001", "2026-08-30")

        assert "no ranked placements" in result
        assert "run_coordinator" in result

    def test_renders_up_to_limit_placements_via_the_llm_engine(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        packs = [
            EvidencePack(
                decision="decision/9001/2026-08-30",
                placement=f"placement/9001/2026-08-30/PW-{i}",
                position=i,
                referral=f"referral/9001/PW-{i}",
                pathway_number=f"PW-{i}",
                evidence=(
                    EvidenceItem(
                        role="urgency", iri=f"score/run-1/9001/PW-{i}/urgency", type="Score"
                    ),
                ),
            )
            for i in range(1, 4)
        ]
        monkeypatch.setattr(tools, "load_rationale_settings", _rationale_settings)
        monkeypatch.setattr(tools, "RetrievalClient", _FakeRetrievalClient(decision={}))
        monkeypatch.setattr(tools, "packs_from_decision_response", lambda decision: packs)

        rendered_for: list[str] = []

        def fake_render(pack: EvidencePack, *, style: str, settings: object) -> Rationale:
            rendered_for.append(pack.pathway_number)
            return Rationale(
                pathway_number=pack.pathway_number,
                text=f"text for {pack.pathway_number}",
                citation_iris=(),
            )

        monkeypatch.setattr(tools, "render_rationale_llm", fake_render)

        result = tools.generate_rationale("9001", "2026-08-30", limit=2)

        assert rendered_for == ["PW-1", "PW-2"]
        assert "text for PW-1" in result
        assert "text for PW-2" in result
        assert "PW-3" not in result
