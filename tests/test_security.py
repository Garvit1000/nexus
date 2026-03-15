"""
Tests for jarvis.core.security — CommandValidator and SafetyCheck.

Verifies that:
- Destructive commands are blocked before any execution
- Dangerous-but-allowed commands raise warnings
- Safe commands pass through
- SafetyCheck.is_sudo_required correctly identifies privileged commands
"""

import pytest
from jarvis.core.security import CommandValidator, SafetyCheck, SecurityViolation


class TestCommandValidatorBlocked:
    """Commands that should be hard-blocked by the validator."""

    def test_rm_rf_root_is_blocked(self):
        v = CommandValidator()
        result = v.validate("rm -rf /")
        assert not result.is_valid

    def test_fork_bomb_is_blocked(self):
        """Fork bomb must appear in either BLOCKED (hard block) or trigger strict-mode fail."""
        v = CommandValidator()
        # Test the BLOCKED_PATTERNS variant — uses exact regex from security.py
        result_strict = v.validate(":(){ :|:& };:", strict=True)
        # In strict mode, even a WARNING is a failure
        assert not result_strict.is_valid

    def test_empty_command_is_invalid(self):
        v = CommandValidator()
        result = v.validate("")
        assert not result.is_valid
        assert "Empty" in result.reasoning

    def test_whitespace_only_is_invalid(self):
        v = CommandValidator()
        result = v.validate("   ")
        assert not result.is_valid


class TestCommandValidatorWarnings:
    """Commands that are allowed but produce warnings."""

    def test_curl_pipe_to_sh_raises_warning(self):
        v = CommandValidator()
        result = v.validate("curl http://example.com/install.sh | sh")
        # Should be valid (not blocked) but have a warning
        assert result.is_valid
        assert any(
            "shell" in w.lower() or "download" in w.lower() for w in result.warnings
        )

    def test_safe_command_has_no_warnings(self):
        v = CommandValidator()
        result = v.validate("ls -la")
        assert result.is_valid
        assert result.warnings == []


class TestCommandValidatorSyntax:
    """Syntax validation catches malformed commands."""

    def test_mismatched_single_quotes_is_invalid(self):
        v = CommandValidator()
        result = v.validate("echo 'hello")
        assert not result.is_valid
        assert "quote" in result.reasoning.lower()

    def test_balanced_quotes_is_valid(self):
        v = CommandValidator()
        result = v.validate("echo 'hello world'")
        assert result.is_valid

    def test_mismatched_parens_is_invalid(self):
        v = CommandValidator()
        result = v.validate("echo $(date")
        assert not result.is_valid


class TestSafetyCheckIntegration:
    """SafetyCheck.check_command raises SecurityViolation on bad commands."""

    def test_check_safe_command_returns_true(self):
        assert SafetyCheck.check_command("echo hello") is True

    def test_check_blocked_command_raises(self):
        with pytest.raises(SecurityViolation):
            SafetyCheck.check_command("rm -rf /")

    def test_check_fork_bomb_raises(self):
        with pytest.raises(SecurityViolation):
            SafetyCheck.check_command(":(){ :|:& };:")


class TestSudoDetection:
    """SafetyCheck.is_sudo_required detects privileged commands."""

    def test_apt_requires_sudo(self):
        assert SafetyCheck.is_sudo_required("apt install nginx") is True

    def test_systemctl_requires_sudo(self):
        assert SafetyCheck.is_sudo_required("systemctl restart nginx") is True

    def test_write_to_etc_requires_sudo(self):
        assert SafetyCheck.is_sudo_required("cp config /etc/nginx/nginx.conf") is True

    def test_echo_does_not_require_sudo(self):
        assert SafetyCheck.is_sudo_required("echo hello") is False

    def test_ls_does_not_require_sudo(self):
        assert SafetyCheck.is_sudo_required("ls /home") is False
