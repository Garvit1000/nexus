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
from .modules.browser_manager import BrowserManager
from .modules.video_manager import VideoManager
from .ai.llm_client import MockLLMClient, OpenAIClient, GoogleGenAIClient, OpenRouterClient
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

# Setup Browser Manager
# Setup AI
# For now, default to Mock unless API key is set
api_key = config_mgr.config.api_key or os.getenv("JARVIS_API_KEY")

# Setup Browser Manager (Local)
# It uses the same LLM key as the main agent
browser_manager = None
if api_key or config_mgr.config.openrouter_api_key:
    browser_manager = BrowserManager(
        api_key=api_key, 
        openrouter_key=config_mgr.config.openrouter_api_key,
        provider=config_mgr.config.model_provider
    )
if api_key or config_mgr.config.openrouter_api_key:
    if config_mgr.config.model_provider == "google":
         llm_client = GoogleGenAIClient(api_key=api_key)
    elif config_mgr.config.model_provider == "openrouter":
         llm_client = OpenRouterClient(api_key=config_mgr.config.openrouter_api_key)
    else:
         llm_client = OpenAIClient(api_key=api_key)
else:
    llm_client = MockLLMClient()

video_manager = VideoManager(executor, llm_client)

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

@app.command()
def browse(
    task: str,
    cloud: bool = typer.Option(False, "--cloud", help="Run in cloud mode (headless).")
):
    """
    Perform a browser-based task using AI.
    Default: Local (Live View). Use --cloud for headless cloud execution.
    """
    if not browser_manager:
        console.print("[bold red]Error:[/bold red] JARVIS_API_KEY is not set. Please add it to your .env file.")
        return

    mode = "Cloud (Headless)" if cloud else "Local (Live View)"
    console.print(Panel(f"[bold blue]Browser Task:[/bold blue] {task}\n[bold yellow]Mode:[/bold yellow] {mode}", title="Browsing"))
    
    with console.status(f"[bold cyan]Agent is browsing ({mode})...[/bold cyan]"):
        result = browser_manager.run_task(task, use_cloud=cloud)
    
    console.print(Panel(f"[bold green]Result:[/bold green]\n{result}", title="Browser Output"))

@app.command()
def search(query: str):
    """
    Quickly answer a question using Google Search (Save Tokens).
    Example: jarvis search "best places to eat in Dubai"
    """
    if isinstance(llm_client, MockLLMClient):
        console.print("[yellow]Mock Mode: Cannot search without API Key.[/yellow]")
        return
    
    if not isinstance(llm_client, GoogleGenAIClient):
        console.print("[red]Search is only supported with Google (Gemini) provider.[/red]")
        return

    console.print(Panel(f"[bold blue]Query:[/bold blue] {query}", title="Google Search"))
    with console.status("[bold cyan]Searching google...[/bold cyan]"):
        result = llm_client.search(query)
    
    console.print(Panel(f"[bold green]Result:[/bold green]\n{result}", title="Search Result"))

    console.print(Panel(f"[bold green]Result:[/bold green]\n{result}", title="Search Result"))

@app.command()
def video(prompt: str):
    """
    Generate a video using Remotion and AI.
    Example: jarvis video "Create a 5s countdown"
    """
    if isinstance(llm_client, MockLLMClient):
        console.print("[yellow]Mock Mode: Cannot generate video without AI.[/yellow]")
        return
        
    console.print(Panel(f"[bold magenta]Video Request:[/bold magenta] {prompt}", title="Remotion Video"))
    
    # Interactive process needs full terminal access, so no console.status spinner here
    result = video_manager.generate_video(prompt)
        
    console.print(Panel(f"[bold green]Result:[/bold green]\n{result}", title="Video Output"))

if __name__ == "__main__":
    app()
