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

    def run(self, command: str, require_sudo: bool = False, cwd: Optional[str] = None) -> Tuple[int, str, str]:
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
        if self.require_confirmation:
            if not confirm_action(f"Allow Jarvis to run: [cyan]{command}[/cyan]?", default=False):
                return -1, "", "User cancelled execution"

        try:
            console.print(f"[dim]Executing: {command}[/dim]")
            
            # Detect shell operators
            use_shell = any(op in command for op in ["&&", "||", ";", "|", ">", "<"])
            args = command if use_shell else shlex.split(command)
            
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                check=False,
                cwd=cwd,
                shell=use_shell
            )
            return result.returncode, result.stdout, result.stderr
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
