"""
Tests for jarvis.modules.package_manager — AppInstaller.

Verifies that:
- Package name validation accepts valid names and rejects injection attempts
- Correct install/remove commands are generated per package manager
- Invalid package names return False without executing
- Update command is correct per distro
"""

from unittest.mock import MagicMock
from jarvis.modules.package_manager import AppInstaller
from jarvis.core.system_detector import SystemInfo, PackageManager


def _installer(pm: PackageManager = PackageManager.APT):
    executor = MagicMock()
    executor.run.return_value = (0, "", "")
    executor.run_interactive.return_value = 0
    detector = MagicMock()
    detector.get_info.return_value = SystemInfo(
        os_name="Ubuntu", os_version="24.04", package_manager=pm
    )
    return AppInstaller(executor=executor, system_detector=detector), executor


class TestPackageNameValidation:
    def test_simple_name(self):
        assert AppInstaller._validate_package_name("nginx") is True

    def test_name_with_dots(self):
        assert AppInstaller._validate_package_name("docker.io") is True

    def test_name_with_version_colon(self):
        assert AppInstaller._validate_package_name("gcc:amd64") is True

    def test_name_with_plus(self):
        assert AppInstaller._validate_package_name("g++") is True

    def test_name_with_hyphen(self):
        assert AppInstaller._validate_package_name("build-essential") is True

    def test_injection_semicolon(self):
        assert AppInstaller._validate_package_name("nginx; rm -rf /") is False

    def test_injection_pipe(self):
        assert AppInstaller._validate_package_name("nginx | cat /etc/passwd") is False

    def test_injection_backtick(self):
        assert AppInstaller._validate_package_name("`evil`") is False

    def test_injection_dollar(self):
        assert AppInstaller._validate_package_name("$(evil)") is False

    def test_empty_string(self):
        assert AppInstaller._validate_package_name("") is False

    def test_single_char(self):
        assert AppInstaller._validate_package_name("a") is False


class TestInstall:
    def test_apt_install_command(self):
        inst, executor = _installer(PackageManager.APT)
        inst.install("nginx")
        executor.run.assert_called_once()
        cmd = executor.run.call_args[0][0]
        assert "apt-get install -y nginx" in cmd

    def test_dnf_install_command(self):
        inst, executor = _installer(PackageManager.DNF)
        inst.install("nginx")
        cmd = executor.run.call_args[0][0]
        assert "dnf install -y nginx" in cmd

    def test_pacman_install_command(self):
        inst, executor = _installer(PackageManager.PACMAN)
        inst.install("nginx")
        cmd = executor.run.call_args[0][0]
        assert "pacman -S --noconfirm nginx" in cmd

    def test_invalid_name_returns_false_without_execution(self):
        inst, executor = _installer()
        result = inst.install("bad; rm -rf /")
        assert result is False
        executor.run.assert_not_called()

    def test_successful_install_returns_true(self):
        inst, _ = _installer()
        assert inst.install("nginx") is True

    def test_failed_install_returns_false(self):
        inst, executor = _installer()
        executor.run.return_value = (1, "", "E: Unable to locate package")
        assert inst.install("nonexistent-pkg") is False

    def test_unknown_pm_returns_false(self):
        inst, executor = _installer(PackageManager.UNKNOWN)
        assert inst.install("nginx") is False
        executor.run.assert_not_called()


class TestRemove:
    def test_apt_remove_command(self):
        inst, executor = _installer(PackageManager.APT)
        inst.remove("nginx")
        cmd = executor.run.call_args[0][0]
        assert "apt-get remove -y nginx" in cmd

    def test_invalid_name_returns_false(self):
        inst, executor = _installer()
        result = inst.remove("pkg$(whoami)")
        assert result is False
        executor.run.assert_not_called()


class TestUpdate:
    def test_apt_update_command(self):
        inst, executor = _installer(PackageManager.APT)
        inst.update_system()
        cmd = executor.run_interactive.call_args[0][0]
        assert "apt-get update" in cmd
        assert "apt-get upgrade -y" in cmd

    def test_dnf_update_command(self):
        inst, executor = _installer(PackageManager.DNF)
        inst.update_system()
        cmd = executor.run_interactive.call_args[0][0]
        assert "dnf upgrade -y" in cmd

    def test_unknown_pm_returns_false(self):
        inst, executor = _installer(PackageManager.UNKNOWN)
        assert inst.update_system() is False
