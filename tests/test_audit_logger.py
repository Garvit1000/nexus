"""
Tests for jarvis.core.audit_logger — AuditLogger.

Verifies that:
- Log file is created on construction
- Executed commands are written to the log with correct fields
- Skipped commands are written with SKIPPED status and reason
- Log file has restricted permissions (0o600)
"""

import os
import stat
import pytest
from jarvis.core.audit_logger import AuditLogger


@pytest.fixture
def isolated_logger(tmp_path):
    """Create an AuditLogger pointing at a temp file, reset handler state."""
    import logging

    # Remove any existing handlers for this logger name to avoid cross-test contamination
    logger = logging.getLogger("nexus.audit")
    logger.handlers.clear()
    log_path = str(tmp_path / "test_audit.log")
    return AuditLogger(log_file=log_path), log_path


class TestAuditLogCreation:
    def test_log_file_is_created(self, isolated_logger):
        _, log_path = isolated_logger
        assert os.path.exists(log_path)

    def test_log_file_has_restricted_permissions(self, isolated_logger):
        _, log_path = isolated_logger
        mode = stat.S_IMODE(os.stat(log_path).st_mode)
        assert mode == 0o600


class TestAuditLogEntries:
    def test_successful_command_is_logged(self, isolated_logger):
        logger, log_path = isolated_logger
        logger.log(
            "echo hello", return_code=0, user_confirmed=True, stdout="hello", stderr=""
        )
        content = open(log_path).read()
        assert "STATUS=OK" in content
        assert "echo hello" in content
        assert "CONFIRMED=YES" in content

    def test_failed_command_is_logged_with_fail_status(self, isolated_logger):
        logger, log_path = isolated_logger
        logger.log(
            "bad_command",
            return_code=1,
            user_confirmed=True,
            stdout="",
            stderr="not found",
        )
        content = open(log_path).read()
        assert "STATUS=FAIL(1)" in content
        assert "bad_command" in content

    def test_unconfirmed_command_logged_as_auto(self, isolated_logger):
        logger, log_path = isolated_logger
        logger.log("ls", return_code=0, user_confirmed=False)
        content = open(log_path).read()
        assert "CONFIRMED=NO(auto)" in content

    def test_stdout_excerpt_is_included(self, isolated_logger):
        logger, log_path = isolated_logger
        logger.log(
            "cat file",
            return_code=0,
            user_confirmed=True,
            stdout="file contents here",
            stderr="",
        )
        content = open(log_path).read()
        assert "file contents here" in content

    def test_skipped_command_is_logged(self, isolated_logger):
        logger, log_path = isolated_logger
        logger.log_skipped("rm -rf /", reason="SecurityViolation: blocked")
        content = open(log_path).read()
        assert "STATUS=SKIPPED" in content
        assert "rm -rf /" in content

    def test_multiple_entries_are_appended(self, isolated_logger):
        logger, log_path = isolated_logger
        logger.log("echo one", return_code=0, user_confirmed=True)
        logger.log("echo two", return_code=0, user_confirmed=True)
        lines = [line for line in open(log_path).readlines() if line.strip()]
        assert len(lines) == 2
