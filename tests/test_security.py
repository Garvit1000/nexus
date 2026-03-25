"""
Tests for jarvis.core.security — CommandValidator and SafetyCheck.

Verifies that:
- Destructive commands are blocked before any execution
- Dangerous-but-allowed commands raise warnings
- Safe commands pass through
- SafetyCheck.is_sudo_required correctly identifies privileged commands
"""

from pathlib import Path

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

    def test_chmod_user_file_does_not_require_sudo(self):
        """chmod on user paths must not force interactive sudo (TUI would hang)."""
        assert SafetyCheck.is_sudo_required("chmod +x /home/user/app.AppImage") is False
        assert SafetyCheck.is_sudo_required("chmod +x ~/.local/bin/foo") is False

    def test_chmod_system_path_still_requires_sudo_heuristic(self):
        assert SafetyCheck.is_sudo_required("chmod 644 /etc/hosts") is True


class TestFtpSecurity:
    """FTP-related patterns: credentials on CLI and anonymous login (FUTURE_SCOPE)."""

    def test_ftp_url_embedded_password_fails_strict(self):
        v = CommandValidator()
        r = v.validate(
            "curl -O ftp://alice:secret1@ftp.example.com/file.txt", strict=True
        )
        assert not r.is_valid
        blob = " ".join(r.warnings) + r.reasoning
        assert "FTP" in blob and "password" in blob.lower()

    def test_wget_ftp_password_flag_fails_strict(self):
        v = CommandValidator()
        r = v.validate(
            "wget --ftp-password=hunter2 ftp://ftp.example.com/pub/README",
            strict=True,
        )
        assert not r.is_valid

    def test_lftp_user_comma_password_fails_strict(self):
        v = CommandValidator()
        r = v.validate("lftp -u myuser,p4ss -e 'ls' ftp://ftp.example.com", strict=True)
        assert not r.is_valid

    def test_curl_anonymous_ftp_fails_strict(self):
        v = CommandValidator()
        r = v.validate("curl -u anonymous ftp://ftp.example.com/README", strict=True)
        assert not r.is_valid
        assert any("anonymous" in w.lower() for w in r.warnings)

    def test_plain_https_download_still_ok(self):
        v = CommandValidator()
        r = v.validate("curl -fsSL https://example.com/install.sh", strict=True)
        assert r.is_valid
        assert r.warnings == []


class TestPathWithinRoots:
    """Path.allowlist must use proper subtree checks, not str.startswith on home."""

    def test_sibling_directory_not_confused_with_home_prefix(self, tmp_path: Path):
        home = tmp_path / "user"
        home.mkdir()
        other = tmp_path / "user2"
        other.mkdir()
        secret = other / "secret.txt"
        secret.write_text("x", encoding="utf-8")
        assert SafetyCheck.is_path_within_any_root(secret, [home]) is False

    def test_descendant_of_root_allowed(self, tmp_path: Path):
        home = tmp_path / "user"
        nested = home / "proj" / "a.txt"
        nested.parent.mkdir(parents=True)
        nested.write_text("ok", encoding="utf-8")
        assert SafetyCheck.is_path_within_any_root(nested, [home]) is True

    def test_exact_root_allowed(self, tmp_path: Path):
        home = tmp_path / "user"
        home.mkdir()
        assert SafetyCheck.is_path_within_any_root(home, [home]) is True


class TestRmRfHeuristics:
    """rm -rf /tmp/... must not be misclassified as rm -rf / (root)."""

    def test_rm_tmp_cleanup_passes_strict(self):
        v = CommandValidator()
        cmd = (
            "update-desktop-database ~/.local/share/applications/ 2>/dev/null; "
            "rm -rf /tmp/recordly-extract && true"
        )
        r = v.validate(cmd, strict=True)
        assert r.is_valid, r.reasoning

    def test_rm_var_tmp_passes_strict(self):
        v = CommandValidator()
        r = v.validate("rm -rf /var/tmp/appimage-work && echo ok", strict=True)
        assert r.is_valid, r.reasoning

    def test_rm_tmp_after_newline_not_root_delete(self):
        """\\n after / must not satisfy 'whitespace after root' (\\s false positive)."""
        v = CommandValidator()
        cmd = "update-desktop-database ~/.local/share/applications/; rm -rf /\n/tmp/squashfs-root && true"
        r = v.validate(cmd, strict=True)
        assert r.is_valid, r.reasoning

    def test_rm_rf_root_still_blocked_strict(self):
        v = CommandValidator()
        r = v.validate("rm -rf / && echo done", strict=True)
        assert not r.is_valid

    def test_rm_rf_root_space_still_blocked(self):
        v = CommandValidator()
        r = v.validate("rm -rf / ", strict=True)
        assert not r.is_valid
