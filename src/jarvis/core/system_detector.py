import distro
import shutil
from enum import Enum
from dataclasses import dataclass
from typing import Optional

class PackageManager(Enum):
    APT = "apt"
    DNF = "dnf"
    PACMAN = "pacman"
    UNKNOWN = "unknown"

@dataclass
class SystemInfo:
    os_name: str
    os_version: str
    package_manager: PackageManager

class SystemDetector:
    def __init__(self):
        self._info: Optional[SystemInfo] = None

    def get_info(self) -> SystemInfo:
        if self._info:
            return self._info

        os_name = distro.name()
        os_version = distro.version()
        pm = self._detect_package_manager()

        self._info = SystemInfo(
            os_name=os_name,
            os_version=os_version,
            package_manager=pm
        )
        return self._info

    def _detect_package_manager(self) -> PackageManager:
        # Check for binaries
        if shutil.which("apt-get"):
            return PackageManager.APT
        elif shutil.which("dnf"):
            return PackageManager.DNF
        elif shutil.which("pacman"):
            return PackageManager.PACMAN
        
        # Fallback to distro ID checks if binaries are ambiguous or missing
        dist_id = distro.id()
        if dist_id in ["ubuntu", "debian", "pop", "linuxmint"]:
            return PackageManager.APT
        elif dist_id in ["fedora", "centos", "rhel"]:
            return PackageManager.DNF
        elif dist_id in ["arch", "manjaro", "endeavouros"]:
            return PackageManager.PACMAN
            
        return PackageManager.UNKNOWN
