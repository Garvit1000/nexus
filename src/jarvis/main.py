import typer
import os
from rich.console import Console
from rich.panel import Panel
from dotenv import load_dotenv

load_dotenv()

from .core.config_manager import ConfigManager
from .core.system_detector import SystemDetector
from .core.executor import CommandExecutor
from .modules.package_manager import AppInstaller
from .ai.llm_client import MockLLMClient, OpenAIClient, GoogleGenAIClient
from .ai.command_generator import CommandGenerator

app = typer.Typer(
    name="jarvis",
    help="Your Linux Assistant",
    add_completion=False,
)
console = Console()

# --- Dependency Injection (Mock-ish) ---
config_mgr = ConfigManager()
sys_detector = SystemDetector()
# Check if dry run is enabled in config or env var
is_dry_run = config_mgr.config.dry_run or os.getenv("JARVIS_DRY_RUN") == "1"
executor = CommandExecutor(dry_run=is_dry_run)
app_installer = AppInstaller(executor, sys_detector)

# Setup AI
# For now, default to Mock unless API key is set
api_key = config_mgr.config.api_key or os.getenv("JARVIS_API_KEY")
if api_key:
    if config_mgr.config.model_provider == "google":
         llm_client = GoogleGenAIClient(api_key=api_key)
    else:
         llm_client = OpenAIClient(api_key=api_key)
else:
    llm_client = MockLLMClient()

command_generator = CommandGenerator(llm_client, sys_detector.get_info())

@app.command()
def chat(prompt: str):
    """
    Chat with Jarvis.
    """
    console.print(Panel(f"[bold blue]User:[/bold blue] {prompt}", title="Chat"))
    response = llm_client.generate_response(prompt)
    console.print(Panel(f"[bold green]Jarvis:[/bold green] {response}", title="Response"))

@app.command()
def install(package: str):
    """
    Install a package using the system's package manager.
    """
    console.print(f"[bold cyan]Request to install:[/bold cyan] {package}")
    success = app_installer.install(package)
    if success:
        console.print(f"[bold green]Successfully installed {package}![/bold green]")
    else:
        console.print(f"[bold red]Failed to install {package}.[/bold red]")

@app.command()
def remove(package: str):
    """
    Remove a package.
    """
    console.print(f"[bold cyan]Request to remove:[/bold cyan] {package}")
    success = app_installer.remove(package)
    if success:
        console.print(f"[bold green]Successfully removed {package}![/bold green]")
    else:
        console.print(f"[bold red]Failed to remove {package}.[/bold red]")

@app.command()
def update():
    """
    Update system packages.
    """
    console.print("[bold cyan]Updating system...[/bold cyan]")
    success = app_installer.update_system()
    if success:
        console.print("[bold green]System updated successfully![/bold green]")
    else:
        console.print("[bold red]System update failed.[/bold red]")

@app.command()
def do(request: str):
    """
    Interpret a natural language request and execute it.
    """
    console.print(f"[dim]Analyzing request: {request}...[/dim]")
    
    # 1. Generate Command
    if isinstance(llm_client, MockLLMClient):
         console.print("[yellow]No API Key found. Using mock mode. Set JARVIS_API_KEY to use real AI.[/yellow]")
    
    command = command_generator.generate_command(request)
    
    console.print(f"[bold]Generated Command:[/bold] [cyan]{command}[/cyan]")
    
    # 2. Execute (Executor handles safety and confirmation)
    return_code, stdout, stderr = executor.run(command)
    
    if return_code == 0:
        if stdout:
            console.print(Panel(stdout, title="Output", border_style="green"))
    else:
        console.print(Panel(stderr, title="Error", border_style="red"))

@app.command()
def info():
    """
    Show system info.
    """
    info = sys_detector.get_info()
    console.print(f"OS: [bold]{info.os_name} {info.os_version}[/bold]")
    console.print(f"Package Manager: [bold]{info.package_manager.value}[/bold]")

if __name__ == "__main__":
    app()
