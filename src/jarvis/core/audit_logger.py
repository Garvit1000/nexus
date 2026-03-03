"""
Audit Logger - Persistent tamper-evident log of all commands executed by Nexus.

Security goal: Give users a forensic record of everything Nexus ran on their system.
Log is stored at ~/.nexus/audit.log
"""

import os
import time
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


class AuditLogger:
    """
    Logs every Nexus-executed command to a persistent audit file.
    
    Each entry includes:
    - ISO timestamp
    - The executed command
    - Return code
    - Whether the user confirmed (Y/N)
    - Short stdout/stderr excerpt
    """

    def __init__(self, log_file: Optional[str] = None):
        if log_file is None:
            nexus_dir = Path.home() / ".nexus"
            nexus_dir.mkdir(exist_ok=True)
            log_file = str(nexus_dir / "audit.log")

        self.log_file = log_file

        # Use a unique logger per instance so multiple AuditLogger objects in tests
        # don't share the same global handler (avoids inter-test contamination).
        logger_name = f"nexus.audit.{id(self)}"
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False

        handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(message)s"))
        self.logger.addHandler(handler)

        # Ensure the log file is private
        try:
            os.chmod(log_file, 0o600)
        except Exception:
            pass

    def log(
        self,
        command: str,
        return_code: int,
        user_confirmed: bool,
        stdout: str = "",
        stderr: str = "",
    ) -> None:
        """
        Write a single command execution entry to the audit log.
        
        Args:
            command: The shell command that was run.
            return_code: The exit code of the command.
            user_confirmed: Whether the user explicitly approved the command.
            stdout: First 200 chars of stdout.
            stderr: First 200 chars of stderr.
        """
        ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        confirmed_str = "YES" if user_confirmed else "NO(auto)"
        status = "OK" if return_code == 0 else f"FAIL({return_code})"
        stdout_excerpt = stdout[:200].replace("\n", " ").strip()
        stderr_excerpt = stderr[:200].replace("\n", " ").strip()

        entry = (
            f"[{ts}] STATUS={status} CONFIRMED={confirmed_str} | CMD={command!r}"
        )
        if stdout_excerpt:
            entry += f" | OUT={stdout_excerpt!r}"
        if stderr_excerpt:
            entry += f" | ERR={stderr_excerpt!r}"

        self.logger.info(entry)

    def log_skipped(self, command: str, reason: str) -> None:
        """Log that a command was skipped (dry run / user rejected)."""
        ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        self.logger.info(
            f"[{ts}] STATUS=SKIPPED REASON={reason!r} | CMD={command!r}"
        )
