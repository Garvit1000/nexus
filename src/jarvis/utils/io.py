import typer
from rich.console import Console
from rich.prompt import Confirm

console = Console()

def confirm_action(message: str, default: bool = False) -> bool:
    """
    Ask the user for confirmation using Rich.
    """
    return Confirm.ask(f"[bold yellow]{message}[/bold yellow]", default=default)

def print_warning(message: str):
    console.print(f"[bold red]WARNING:[/bold red] {message}")

def print_success(message: str):
    console.print(f"[bold green]SUCCESS:[/bold green] {message}")
