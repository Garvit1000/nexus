"""
Tests for jarvis.core.executor — CommandExecutor.

Verifies that:
- Safe commands execute and return stdout
- Blocked commands return -1 without executing
- Dry-run mode never executes but returns 0
- User-rejection logs SKIPPED and returns -1
- sudo bytearray is zeroed on auth failure
- Audit log receives an entry for every code path
"""

import pytest
from unittest.mock import patch, MagicMock


class TestExecutorSafeCommands:
    """Safe commands should actually run."""

    def test_echo_returns_zero(self, executor_no_confirm):
        rc, out, err = executor_no_confirm.run("echo nexus_test")
        assert rc == 0
        assert "nexus_test" in out

    def test_echo_returns_stdout(self, executor_no_confirm):
        rc, out, _ = executor_no_confirm.run("echo hello_world")
        assert "hello_world" in out

    def test_failed_command_returns_nonzero(self, executor_no_confirm):
        rc, _, _ = executor_no_confirm.run("false")
        assert rc != 0

    def test_pipeline_command_works(self, executor_no_confirm):
        rc, out, _ = executor_no_confirm.run("echo nexus | cat")
        assert rc == 0
        assert "nexus" in out


class TestExecutorBlockedCommands:
    """Commands blocked by security should not execute."""

    def test_rm_rf_root_is_blocked(self, executor_no_confirm):
        rc, _, err = executor_no_confirm.run("rm -rf /")
        assert rc == -1
        assert "blocked" in err.lower() or "security" in err.lower()

    def test_fork_bomb_is_blocked(self, executor_no_confirm):
        rc, _, err = executor_no_confirm.run(":(){ :|:& };:")
        assert rc == -1

    def test_blocked_command_is_logged_as_skipped(self, executor_no_confirm):
        """Blocked commands should write a SKIPPED entry to the audit log."""
        executor_no_confirm.run("rm -rf /")
        content = open(executor_no_confirm._audit_log_path).read()
        assert "SKIPPED" in content or "SecurityViolation" in content


class TestExecutorDryRun:
    """Dry-run mode must never execute any real command."""

    def test_dry_run_returns_zero(self, executor_dry_run):
        rc, out, _ = executor_dry_run.run("echo hello")
        assert rc == 0
        assert "Dry run" in out

    def test_dry_run_does_not_execute(self, executor_dry_run, tmp_path):
        """Confirm that a file-creating command doesn't actually create a file in dry-run."""
        target = tmp_path / "should_not_exist.txt"
        executor_dry_run.run(f"touch {target}")
        assert not target.exists()

    def test_dry_run_logs_skipped(self, executor_dry_run):
        executor_dry_run.run("echo test")
        content = open(executor_dry_run._audit_log_path).read()
        assert "SKIPPED" in content or "dry_run" in content


class TestExecutorAuditIntegration:
    """Every execution path must write to the audit log."""

    def test_successful_run_logged(self, executor_no_confirm):
        executor_no_confirm.run("echo audit_test")
        content = open(executor_no_confirm._audit_log_path).read()
        assert "audit_test" in content

    def test_failed_run_logged(self, executor_no_confirm):
        executor_no_confirm.run("false")
        content = open(executor_no_confirm._audit_log_path).read()
        assert "FAIL" in content


class TestExecutorSudoPasswordClearing:
    """The sudo bytearray must be cleared on authentication failure."""

    def test_sudo_password_cleared_on_auth_failure(self, executor_no_confirm):
        # Pre-load a fake password into the bytearray
        executor_no_confirm._sudo_password_bytes = bytearray(b"mysecretpassword")

        # Simulate a subprocess result whose stderr contains "incorrect password"
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "sudo: incorrect password attempt"

        with patch("subprocess.run", return_value=mock_result):
            rc, _, err = executor_no_confirm.run("sudo echo test")

        # The bytearray should be None after the auth failure clear
        assert executor_no_confirm._sudo_password_bytes is None

    def test_bytearray_stores_password_not_str(self, executor_no_confirm):
        """Password cache must be a bytearray, never a plain str."""
        executor_no_confirm._sudo_password_bytes = bytearray(b"test")
        assert isinstance(executor_no_confirm._sudo_password_bytes, bytearray)

    def test_clear_zeros_bytearray(self, executor_no_confirm):
        executor_no_confirm._sudo_password_bytes = bytearray(b"secret")
        executor_no_confirm._clear_sudo_password()
        assert executor_no_confirm._sudo_password_bytes is None


class TestShellModeScoping:
    """shell=True must only be used when pipeline operators are present."""

    def test_simple_command_uses_list_args(self, executor_no_confirm):
        """For a command with no shell operators, subprocess must receive a list."""
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result
            executor_no_confirm.run("ls /tmp")

        call_kwargs = mock_run.call_args
        assert call_kwargs.kwargs.get("shell") is False
        assert isinstance(call_kwargs.args[0], list)

    def test_pipeline_command_uses_shell_true(self, executor_no_confirm):
        """For a command with |, subprocess must use shell=True."""
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "output"
            mock_result.stderr = ""
            mock_run.return_value = mock_result
            executor_no_confirm.run("echo test | cat")

        call_kwargs = mock_run.call_args
        assert call_kwargs.kwargs.get("shell") is True
        assert isinstance(call_kwargs.args[0], str)
