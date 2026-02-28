import subprocess
import shlex
from rich.console import Console
from typing import Tuple, Optional
from .security import SafetyCheck, SecurityViolation
from ..utils.io import confirm_action

console = Console()

class CommandExecutor:
    def __init__(self, dry_run: bool = False, require_confirmation: bool = True):
        self.dry_run = dry_run
        self.require_confirmation = require_confirmation
        self._sudo_password: Optional[str] = None

    def _get_sudo_password(self) -> Optional[str]:
        """Prompt for sudo password securely if needed."""
        if self._sudo_password is None:
            from rich.prompt import Prompt
            console.print("[yellow]System administration task requires privilege escalation.[/yellow]")
            pwd = Prompt.ask("[bold cyan]Enter sudo password[/bold cyan]", password=True)
            self._sudo_password = pwd
        return self._sudo_password

    def run(self, command: str, require_sudo: bool = False, cwd: Optional[str] = None, require_confirmation: Optional[bool] = None) -> Tuple[int, str, str]:
        """
        Executes a shell command.
        Returns: (return_code, stdout, stderr)
        """
        # 1. Safety Check
        try:
            SafetyCheck.check_command(command)
        except SecurityViolation as e:
            return -1, "", str(e)

        # 2. Sudo Check
        if require_sudo or SafetyCheck.is_sudo_required(command):
            if not command.strip().startswith("sudo"):
                command = f"sudo {command}"

        # 3. Dry Run
        if self.dry_run:
            console.print(f"[bold yellow][DRY RUN][/bold yellow] Would execute in {cwd or '.'}: [cyan]{command}[/cyan]")
            return 0, "Dry run", ""

        # 4. Confirmation
        should_confirm = self.require_confirmation if require_confirmation is None else require_confirmation
        if should_confirm:
            if not confirm_action(f"Allow Jarvis to run: [cyan]{command}[/cyan]?", default=False):
                return -1, "", "User cancelled execution"

        try:
            console.print(f"[dim]Executing: {command}[/dim]")
            
            # Detect shell operators
            use_shell = any(op in command for op in ["&&", "||", ";", "|", ">", "<"])
            
            needs_sudo = command.strip().startswith("sudo")
            if needs_sudo:
                # Force sudo to read from stdin (-S)
                command = command.replace("sudo ", "sudo -S ", 1)
                sudo_pwd = self._get_sudo_password()
                input_data = f"{sudo_pwd}\n" if sudo_pwd else None
            else:
                input_data = None

            args = command if use_shell else shlex.split(command)
            
            console.print(f"[bold magenta]DEBUG EXECUTOR: Running -> {args}[/bold magenta]")
            
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                check=False,
                cwd=cwd,
                shell=use_shell,
                input=input_data,
                timeout=30  # Prevent indefinite hanging
            )
            
            # Clear password if authentication failed to allow retry next time
            if result.returncode != 0 and ("incorrect password" in result.stderr.lower() or "sorry, try again" in result.stderr.lower()):
                self._sudo_password = None
                return result.returncode, result.stdout, "Sudo authentication failed. Incorrect password."

            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired as e:
            return -1, "", f"Command timed out after 30 seconds: {e}"
        except Exception as e:
            return -1, "", str(e)

    def  run_interactive(self, command: str, require_sudo: bool = False, cwd: Optional[str] = None) -> int:
        """
        Runs a command allowing it to take over stdin/stdout/stderr. 
        Useful for interactive tools like vim, nano, or apt prompts.
        """
         # 1. Safety Check
        try:
            SafetyCheck.check_command(command)
        except SecurityViolation as e:
            console.print(f"[bold red]Security Error:[/bold red] {e}")
            return -1

        # 2. Sudo Check
        if require_sudo or SafetyCheck.is_sudo_required(command):
             if not command.strip().startswith("sudo"):
                command = f"sudo {command}"

        # 3. Dry Run
        if self.dry_run:
            console.print(f"[bold yellow][DRY RUN][/bold yellow] Would execute interactively in {cwd or '.'}: [cyan]{command}[/cyan]")
            return 0

        # 4. Confirmation
        if self.require_confirmation:
             if not confirm_action(f"Allow Jarvis to run INTERACTIVELY: [cyan]{command}[/cyan]?", default=False):
                console.print("[yellow]Cancelled.[/yellow]")
                return -1

        try:
            console.print(f"[dim]Executing interactively: {command}[/dim]")
            
            # Detect shell operators
            use_shell = any(op in command for op in ["&&", "||", ";", "|", ">", "<"])
            args = command if use_shell else shlex.split(command)
            
            return subprocess.call(args, cwd=cwd, shell=use_shell)
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            return -1
