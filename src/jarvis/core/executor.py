import subprocess
import shlex
from rich.console import Console
from typing import Tuple, Optional
from .security import SafetyCheck, SecurityViolation
from ..utils.io import confirm_action
from .audit_logger import AuditLogger

console = Console()


class CommandExecutor:
    DEFAULT_TIMEOUT = 120

    def __init__(
        self,
        dry_run: bool = False,
        require_confirmation: bool = True,
        timeout: int = DEFAULT_TIMEOUT,
    ):
        self.dry_run = dry_run
        self.require_confirmation = require_confirmation
        self.timeout = timeout
        self._sudo_password_bytes: Optional[bytearray] = None
        self.audit = AuditLogger()

    # ------------------------------------------------------------------
    # P0: Secure sudo password management
    # ------------------------------------------------------------------
    def _get_sudo_password(self) -> Optional[str]:
        """Prompt for sudo password securely if not already cached."""
        if self._sudo_password_bytes is None:
            from rich.prompt import Prompt

            console.print(
                "[yellow]System administration task requires privilege escalation.[/yellow]"
            )
            pwd = Prompt.ask(
                "[bold cyan]Enter sudo password[/bold cyan]", password=True
            )
            # Store as bytearray so we can zero-out memory on clear
            self._sudo_password_bytes = bytearray(pwd.encode("utf-8"))
        return self._sudo_password_bytes.decode("utf-8")

    def _clear_sudo_password(self) -> None:
        """Securely zero-out the cached sudo password from memory."""
        if self._sudo_password_bytes is not None:
            buf = self._sudo_password_bytes
            for i in range(len(buf)):
                buf[i] = 0
            self._sudo_password_bytes = None

    # ------------------------------------------------------------------
    # Main execution
    # ------------------------------------------------------------------
    def run(
        self,
        command: str,
        require_sudo: bool = False,
        cwd: Optional[str] = None,
        require_confirmation: Optional[bool] = None,
        timeout: Optional[int] = None,
    ) -> Tuple[int, str, str]:
        """
        Executes a shell command safely.
        Returns: (return_code, stdout, stderr)

        timeout: override subprocess wall-clock limit in seconds; None uses self.timeout.
        """
        effective_timeout = self.timeout if timeout is None else timeout
        # 1. Safety validation
        try:
            SafetyCheck.check_command(command)
        except SecurityViolation as e:
            self.audit.log_skipped(command, f"SecurityViolation: {e}")
            return -1, "", str(e)

        # 2. Auto-prefix sudo if needed
        if require_sudo or SafetyCheck.is_sudo_required(command):
            if not command.strip().startswith("sudo"):
                command = f"sudo {command}"

        # 3. Dry run shortcut
        if self.dry_run:
            console.print(
                f"[bold yellow][DRY RUN][/bold yellow] Would execute in {cwd or '.'}: [cyan]{command}[/cyan]"
            )
            self.audit.log_skipped(command, "dry_run")
            return 0, "Dry run", ""

        # 4. User confirmation gate
        should_confirm = (
            self.require_confirmation
            if require_confirmation is None
            else require_confirmation
        )
        user_confirmed = True
        if should_confirm:
            if not confirm_action(
                f"Allow Nexus to run: [cyan]{command}[/cyan]?", default=False
            ):
                self.audit.log_skipped(command, "user_rejected")
                return -1, "", "User cancelled execution"

        # 5. Execute — P0: only use shell=True when pipeline operators are genuinely present
        try:
            shell_operators = ["&&", "||", ";", "|", ">", "<"]
            use_shell = any(op in command for op in shell_operators)

            needs_sudo = command.strip().startswith("sudo")
            if needs_sudo:
                # Use sudo -S so we can pipe the password non-interactively
                command = command.replace("sudo ", "sudo -S ", 1)
                sudo_pwd = self._get_sudo_password()
                input_data = f"{sudo_pwd}\n" if sudo_pwd else None
            else:
                input_data = None

            # P0: When no shell operators, parse into a list to avoid injection
            args = command if use_shell else shlex.split(command)

            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                check=False,
                cwd=cwd,
                shell=use_shell,
                input=input_data,
                timeout=effective_timeout,
            )

            if result.returncode != 0 and (
                "incorrect password" in result.stderr.lower()
                or "sorry, try again" in result.stderr.lower()
            ):
                self._clear_sudo_password()
                self.audit.log(
                    command, result.returncode, user_confirmed, "", "Sudo auth failed"
                )
                return (
                    result.returncode,
                    result.stdout,
                    "Sudo authentication failed. Please try again.",
                )

            self.audit.log(
                command, result.returncode, user_confirmed, result.stdout, result.stderr
            )
            return result.returncode, result.stdout, result.stderr

        except subprocess.TimeoutExpired as e:
            self.audit.log(command, -1, user_confirmed, "", f"Timeout: {e}")
            return (
                -1,
                "",
                f"Command timed out after {effective_timeout} seconds: {e}",
            )
        except Exception as e:
            self.audit.log(command, -1, user_confirmed, "", str(e))
            return -1, "", str(e)

    def run_interactive(
        self,
        command: str,
        require_sudo: bool = False,
        cwd: Optional[str] = None,
    ) -> int:
        """
        Runs a command interactively (stdin/stdout/stderr pass-through).
        Useful for interactive tools like vim, nano, apt prompts.
        """
        try:
            SafetyCheck.check_command(command)
        except SecurityViolation as e:
            console.print(f"[bold red]Security Error:[/bold red] {e}")
            self.audit.log_skipped(command, f"SecurityViolation: {e}")
            return -1

        if require_sudo or SafetyCheck.is_sudo_required(command):
            if not command.strip().startswith("sudo"):
                command = f"sudo {command}"

        if self.dry_run:
            console.print(
                f"[bold yellow][DRY RUN][/bold yellow] Would execute interactively: [cyan]{command}[/cyan]"
            )
            self.audit.log_skipped(command, "dry_run")
            return 0

        if self.require_confirmation:
            if not confirm_action(
                f"Allow Nexus to run INTERACTIVELY: [cyan]{command}[/cyan]?",
                default=False,
            ):
                console.print("[yellow]Cancelled.[/yellow]")
                self.audit.log_skipped(command, "user_rejected")
                return -1

        try:
            console.print(f"[dim]Executing interactively: {command}[/dim]")
            use_shell = any(op in command for op in ["&&", "||", ";", "|", ">", "<"])
            args = command if use_shell else shlex.split(command)
            rc = subprocess.call(args, cwd=cwd, shell=use_shell)
            self.audit.log(command, rc, True, "", "")
            return rc
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            self.audit.log(command, -1, True, "", str(e))
            return -1
