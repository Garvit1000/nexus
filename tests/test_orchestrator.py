"""
Tests for jarvis.core.orchestrator — Orchestrator class.

Verifies that:
- _extract_missing_binary detects common 'not found' patterns
- reflect_and_fix returns install-and-retry for missing binaries
- reflect_and_fix uses _PKG_ALIAS for well-known tools
- reflect_and_fix validates package names (rejects injection)
- reflect_and_fix falls back to LLM for non-missing-binary errors
- generate_view builds a Rich Table with correct column count
- execute_plan returns failure when plan is empty
"""

import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from rich.console import Console
from jarvis.core.orchestrator import Orchestrator, TaskStep, OrchestratorResult


def _mock_orchestrator(llm_response="UNFIXABLE"):
    console = Console(force_terminal=True, width=120)
    executor = MagicMock()
    executor.run.return_value = (0, "ok", "")
    browser_mgr = MagicMock()
    llm = MagicMock()
    llm.generate_response.return_value = llm_response
    llm.memory_client = None
    orch = Orchestrator(
        console=console,
        executor=executor,
        browser_manager=browser_mgr,
        llm_client=llm,
        fallback_clients=[],
    )
    return orch


class TestExtractMissingBinary:
    def test_bash_command_not_found(self):
        orch = _mock_orchestrator()
        binary = orch._extract_missing_binary(
            "bash: docker: command not found", "docker ps"
        )
        assert binary == "docker"

    def test_sh_not_found(self):
        orch = _mock_orchestrator()
        binary = orch._extract_missing_binary(
            "/bin/sh: 1: ffmpeg: not found", "ffmpeg -i video.mp4"
        )
        assert binary == "ffmpeg"

    def test_which_no_binary(self):
        orch = _mock_orchestrator()
        binary = orch._extract_missing_binary(
            "which: no htop in (/usr/bin:/bin)", "htop"
        )
        assert binary == "htop"

    def test_no_match_returns_none(self):
        orch = _mock_orchestrator()
        binary = orch._extract_missing_binary(
            "permission denied", "ls /root"
        )
        assert binary is None

    def test_fallback_first_token(self):
        orch = _mock_orchestrator()
        binary = orch._extract_missing_binary(
            "jq: command not found", "jq '.name' data.json"
        )
        assert binary == "jq"


class TestReflectAndFix:
    def test_missing_binary_returns_install_and_retry(self):
        orch = _mock_orchestrator()
        fix = orch.reflect_and_fix("docker ps", "bash: docker: command not found")
        assert fix is not None
        assert "apt-get install" in fix
        assert "docker" in fix
        assert "docker ps" in fix

    def test_pkg_alias_used(self):
        orch = _mock_orchestrator()
        fix = orch.reflect_and_fix("node --version", "bash: node: command not found")
        assert fix is not None
        assert "nodejs" in fix

    def test_invalid_pkg_name_returns_none(self):
        orch = _mock_orchestrator()
        orch._PKG_ALIAS["evil;cmd"] = "evil;cmd"
        fix = orch.reflect_and_fix("evil;cmd", "bash: evil;cmd: command not found")
        assert fix is None
        del orch._PKG_ALIAS["evil;cmd"]

    def test_llm_fallback_for_permission_error(self):
        orch = _mock_orchestrator(llm_response="sudo ls /root")
        fix = orch.reflect_and_fix("ls /root", "Permission denied")
        assert fix == "sudo ls /root"

    def test_unfixable_returns_none(self):
        orch = _mock_orchestrator(llm_response="UNFIXABLE")
        fix = orch.reflect_and_fix("impossible_cmd", "some weird error")
        assert fix is None

    def test_llm_exception_tries_fallback(self):
        console = Console(force_terminal=True, width=120)
        primary = MagicMock()
        primary.generate_response.side_effect = Exception("Rate limited")
        primary.memory_client = None
        fallback = MagicMock()
        fallback.generate_response.return_value = "sudo ls /root"
        orch = Orchestrator(
            console=console,
            executor=MagicMock(),
            browser_manager=None,
            llm_client=primary,
            fallback_clients=[fallback],
        )
        fix = orch.reflect_and_fix("ls /root", "Permission denied")
        assert fix == "sudo ls /root"


class TestGenerateView:
    def test_table_has_four_columns(self):
        orch = _mock_orchestrator()
        steps = [
            TaskStep(id=1, description="Test step", action="TERMINAL", command="echo hi"),
        ]
        table = orch.generate_view(steps)
        assert len(table.columns) == 4

    def test_table_contains_step_data(self):
        orch = _mock_orchestrator()
        steps = [
            TaskStep(id=1, description="Echo hello", action="TERMINAL", command="echo hello"),
            TaskStep(id=2, description="Check status", action="CHECK", command="which docker", status="success"),
        ]
        table = orch.generate_view(steps)
        assert table.row_count == 2


class TestExecutePlan:
    def test_empty_steps_returns_failure(self):
        orch = _mock_orchestrator()
        result = asyncio.run(orch.execute_plan([]))
        assert result.success is False
        assert "Plan generation failed" in result.output

    def test_string_request_with_bad_llm_returns_failure(self):
        orch = _mock_orchestrator(llm_response="not json")
        result = asyncio.run(orch.execute_plan("install docker"))
        assert result.success is False

    @patch("jarvis.utils.io.Confirm")
    def test_user_cancellation(self, mock_confirm_cls):
        mock_confirm_cls.ask.return_value = False
        orch = _mock_orchestrator()
        steps = [
            TaskStep(id=1, description="Echo test", action="TERMINAL", command="echo test"),
        ]
        result = asyncio.run(orch.execute_plan(steps, require_confirmation=True))
        assert "cancelled" in result.output.lower()

    def test_terminal_step_executes(self):
        orch = _mock_orchestrator()
        orch.executor.run.return_value = (0, "hello", "")
        steps = [
            TaskStep(id=1, description="Echo hello", action="TERMINAL", command="echo hello"),
        ]
        result = asyncio.run(orch.execute_plan(steps, require_confirmation=False))
        assert result.success is True
        orch.executor.run.assert_called()
