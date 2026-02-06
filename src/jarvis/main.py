import typer
import os
import sys
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
from .modules.video_manager import VideoManager
from .ai.llm_client import MockLLMClient, OpenAIClient, GoogleGenAIClient, OpenRouterClient, GroqClient
from .ai.memory_client import SupermemoryClient
from .ai.command_generator import CommandGenerator
from .ui.onboarding import OnboardingUI

app = typer.Typer(
    name="nexus",
    help="Nexus: Your Intelligent Linux Assistant",
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

# --- Onboarding Check (Before anything else) ---
if not config_mgr.config.onboarding_completed:
    # Check if we are in a subcommand or just running 'jarvis'
    # For simplicity, if config says not onboarded, we run it.
    # But we should only block if we are in interactive mode or main entry.
    # However, since this is CLI specific logic, we might want to do it inside appropriate command 
    # OR since app() is called at the end, we can do it here if we want global enforcement.
    # Let's do it here:
    onboarding = OnboardingUI(config_mgr, console)
    onboarding.run()
    # Reload config to get new keys
    config_mgr = ConfigManager()

# Setup AI
# Prioritize keys from config, then env vars
api_key = config_mgr.config.google_api_key or config_mgr.config.api_key or os.getenv("JARVIS_API_KEY") 
openrouter_key = config_mgr.config.openrouter_api_key or os.getenv("OPENROUTER_API_KEY")


# Setup Browser Manager (Local)
browser_manager = None
if openrouter_key: # Browser manager works best with OpenRouter/OpenAI 
    browser_manager = BrowserManager(
        api_key=api_key if api_key else "dummy", # It might use specific key
        openrouter_key=openrouter_key,
    )
if openrouter_key:
     llm_client = OpenRouterClient(api_key=openrouter_key)
elif api_key:
     llm_client = GoogleGenAIClient(api_key=api_key)
else:
     llm_client = MockLLMClient()

# Setup Groq Router (Limbic System)
groq_key = config_mgr.config.groq_api_key or os.getenv("GROQ_API_KEY")
router_client = None
if groq_key:
    try:
        router_client = GroqClient(api_key=groq_key)
        console.print("[dim green]⚡ Groq Brain Activated[/dim green]")
    except Exception as e:
        console.print(f"[dim red]Failed to init Groq: {e}[/dim red]")

    from .ai.memory_client import SupermemoryClient
    memory_client = SupermemoryClient(api_key=config_mgr.config.supermemory_api_key)
    llm_client.set_memory_client(memory_client)
    
    # --- Brain Initialization: Persist System Context ---
    # This ensures the agent "knows" what machine it is running on.
    info = sys_detector.get_info()
    sys_context = f"My System: OS={info.os_name} {info.os_version}, Package Manager={info.package_manager.value}"
    
    # Check if we already know this to avoid duplicate memories on restart
    existing_memories = memory_client.query_memory(sys_context)
    if sys_context not in existing_memories:
        console.print(f"[dim]🧠 Memorizing system context: {sys_context}[/dim]")
        memory_client.add_memory(sys_context, metadata={"type": "system_info"})
    else:
        # console.print("[dim]🧠 System context already known.[/dim]")
        pass

video_manager = VideoManager(executor, llm_client)

command_generator = CommandGenerator(llm_client, sys_detector.get_info())

@app.command()
def chat(prompt: str):
    """
    Chat with Nexus.
    """
    console.print(Panel(f"[bold blue]User:[/bold blue] {prompt}", title="Chat"))
    
    # Enforce Identity
    nexus_prompt = (
        "You are Nexus, an elite intelligent Linux Assistant. "
        "You are helpful, precise, and favor blue/cyan aesthetics. "
        "Never identify as ChatGPT. "
        f"User: {prompt}"
    )
    
    response = llm_client.generate_response(nexus_prompt)
    console.print(Panel(f"[bold cyan]Nexus:[/bold cyan] {response}", title="Response"))

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
         console.print("[yellow]No API Key found. Using mock mode. Set Keys to use real AI.[/yellow]")
    
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

@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """
    Nexus: Your AI Linux Assistant.
    """
    if ctx.invoked_subcommand is None:
        # Launch TUI
        import asyncio
        import sys
        
        # Ensure dependencies are passed
        from .ui.console_app import JarvisApp
        
        # We need to ensure dependencies like video_manager are initialized
        # existing code initialized them globally, which is fine.
        
        tui = JarvisApp(
            llm_client=llm_client, 
            video_manager=video_manager, 
            browser_manager=browser_manager,
            executor=executor,
            app_installer=app_installer,
            router_client=router_client
        )
        
        try:
            asyncio.run(tui.run_repl())
        except KeyboardInterrupt:
            console.print("[bold red]Goodbye![/bold red]")
            sys.exit(0)

if __name__ == "__main__":
    app()
