import re
from typing import List

class SecurityViolation(Exception):
    pass

class SafetyCheck:
    # A very basic blacklist. In a real system, this would be more sophisticated.
    BLACKLIST_PATTERNS = [
        r"rm\s+-rf\s+/",        # Classic nuque
        r"rm\s+-rf\s+/\*",      # Another variant
        r":\(\)\s*\{\s*:\|:\s*\&?\s*\}\s*;", # Fork bomb
        r"mkfs\.",              # Formatting drives
        r"dd\s+if=",            # Low level write
        r"chmod\s+777\s+/",     # Bad permissions
        r">\s*/dev/sda",        # Overwriting devices
    ]

    @classmethod
    def check_command(cls, command: str) -> bool:
        """
        Checks if a command command is potentially destructive.
        Returns True if safe, raises SecurityViolation if unsafe.
        """
        for pattern in cls.BLACKLIST_PATTERNS:
            if re.search(pattern, command):
                raise SecurityViolation(f"Command blocked by safety filter: matches pattern '{pattern}'")
        return True

    @classmethod
    def is_sudo_required(cls, command: str) -> bool:
        """
        Heuristic to check if a command likely needs sudo.
        """
        privileged_commands = ["apt", "dnf", "pacman", "systemctl", "mount", "umount", "chown", "chmod"]
        first_word = command.split()[0] if command else ""
        
        if first_word in privileged_commands:
            return True
        # Check for writes to system directories (basic heuristic)
        if " /etc/" in command or " /usr/" in command or " /var/" in command:
             # This is a weak check, but okay for a prototype
             return True
             
        return False
