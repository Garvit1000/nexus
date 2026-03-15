import re
from typing import Optional
from ..core.system_detector import SystemDetector, PackageManager
from ..core.executor import CommandExecutor

_VALID_PKG_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9.+\-:]+$")


class AppInstaller:
    def __init__(self, executor: CommandExecutor, system_detector: SystemDetector):
        self.executor = executor
        self.sys_info = system_detector.get_info()

    @staticmethod
    def _validate_package_name(name: str) -> bool:
        return bool(_VALID_PKG_RE.fullmatch(name))

    def install(self, package_name: str) -> bool:
        if not self._validate_package_name(package_name):
            from rich.console import Console

            Console().print(f"[red]Error:[/red] Invalid package name: {package_name!r}")
            return False
        cmd = self._get_install_command(package_name)
        if not cmd:
            import logging

            logging.warning(
                f"Unsupported package manager: {self.sys_info.package_manager}"
            )
            return False

        return_code, _, _ = self.executor.run(cmd, require_sudo=True)
        return return_code == 0

    def remove(self, package_name: str) -> bool:
        if not self._validate_package_name(package_name):
            from rich.console import Console

            Console().print(f"[red]Error:[/red] Invalid package name: {package_name!r}")
            return False
        cmd = self._get_remove_command(package_name)
        if not cmd:
            return False

        return_code, _, _ = self.executor.run(cmd, require_sudo=True)
        return return_code == 0

    def update_system(self) -> bool:
        """
        Updates the system packages.
        """
        cmd = self._get_update_command()
        if not cmd:
            return False

        # Updates are often interactive/long, so we might want run_interactive
        # But for now, let's just use run() or maybe run_interactive is better?
        # Let's use run_interactive for updates.
        return_code = self.executor.run_interactive(cmd, require_sudo=True)
        return return_code == 0

    def _get_install_command(self, package: str) -> Optional[str]:
        pm = self.sys_info.package_manager
        if pm == PackageManager.APT:
            return f"apt-get install -y {package}"
        elif pm == PackageManager.DNF:
            return f"dnf install -y {package}"
        elif pm == PackageManager.PACMAN:
            return f"pacman -S --noconfirm {package}"
        return None

    def _get_remove_command(self, package: str) -> Optional[str]:
        pm = self.sys_info.package_manager
        if pm == PackageManager.APT:
            return f"apt-get remove -y {package}"
        elif pm == PackageManager.DNF:
            return f"dnf remove -y {package}"
        elif pm == PackageManager.PACMAN:
            return f"pacman -Rns --noconfirm {package}"
        return None

    def _get_update_command(self) -> Optional[str]:
        pm = self.sys_info.package_manager
        if pm == PackageManager.APT:
            # We explicitly add sudo to the second command because 'sudo command1 && command2'
            # only runs command1 as root.
            return "apt-get update && sudo apt-get upgrade -y"
        elif pm == PackageManager.DNF:
            return "dnf upgrade -y"
        elif pm == PackageManager.PACMAN:
            return "pacman -Syu --noconfirm"
        return None
