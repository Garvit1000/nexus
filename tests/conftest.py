"""
Shared pytest fixtures for the Nexus test suite.
"""

import os
import tempfile
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path


# ---------------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_audit_log(tmp_path):
    """Return a path to a temporary audit log file."""
    return str(tmp_path / "audit.log")


@pytest.fixture
def tmp_session_file(tmp_path):
    """Return a path to a temporary session JSON file."""
    return str(tmp_path / "session.json")


# ---------------------------------------------------------------------------
# Mock LLM clients
# ---------------------------------------------------------------------------

class _MockLLMClient:
    """Minimal LLM client that returns a predetermined response."""
    model_name = "mock-model"

    def __init__(self, response: str = ""):
        self._response = response

    def generate_response(self, prompt: str) -> str:  # noqa: ARG002
        return self._response

    def enrich_prompt(self, prompt: str, _context: str = "") -> str:
        return prompt


@pytest.fixture
def good_plan_client():
    """LLM client that returns a valid 1-step plan JSON."""
    plan = '[{"description": "Echo hello", "action": "TERMINAL", "command": "echo hello"}]'
    return _MockLLMClient(response=plan)


@pytest.fixture
def bad_plan_client():
    """LLM client that always raises an exception (simulates 429 / timeout)."""
    client = _MockLLMClient()
    client.generate_response = MagicMock(side_effect=Exception("Rate limited"))
    return client


@pytest.fixture
def unfixable_fix_client():
    """LLM client that returns UNFIXABLE when asked to fix a command."""
    return _MockLLMClient(response="UNFIXABLE")


@pytest.fixture
def good_fix_client():
    """LLM client that returns a corrected command when asked to fix."""
    return _MockLLMClient(response="echo fixed")


# ---------------------------------------------------------------------------
# Executor helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def executor_no_confirm(tmp_path):
    """CommandExecutor with confirmations disabled and isolated audit log."""
    import logging
    logging.getLogger("nexus.audit").handlers.clear()
    from jarvis.core.audit_logger import AuditLogger
    from jarvis.core.executor import CommandExecutor

    log_path = str(tmp_path / "audit.log")
    ex = CommandExecutor(dry_run=False, require_confirmation=False)
    ex.audit = AuditLogger(log_file=log_path)
    ex._audit_log_path = log_path  # expose for tests
    return ex


@pytest.fixture
def executor_dry_run(tmp_path):
    """CommandExecutor in dry-run mode (never actually executes anything)."""
    import logging
    logging.getLogger("nexus.audit").handlers.clear()
    from jarvis.core.audit_logger import AuditLogger
    from jarvis.core.executor import CommandExecutor

    log_path = str(tmp_path / "audit.log")
    ex = CommandExecutor(dry_run=True, require_confirmation=False)
    ex.audit = AuditLogger(log_file=log_path)
    ex._audit_log_path = log_path  # expose for tests
    return ex
