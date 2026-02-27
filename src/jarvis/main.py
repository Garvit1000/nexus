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
from .ai.llm_client import MockLLMClient, OpenAIClient, GoogleGenAIClient, OpenRouterClient, GroqClient, GroqGPTClient

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
# Prioritize Groq (User Preference), then OpenRouter, then Google, then Mock
api_key = config_mgr.config.google_api_key or config_mgr.config.api_key or os.getenv("JARVIS_API_KEY") 
openrouter_key = config_mgr.config.openrouter_api_key or os.getenv("OPENROUTER_API_KEY")
groq_key = config_mgr.config.groq_api_key or os.getenv("GROQ_API_KEY")
groq_gpt_key = config_mgr.config.groq_gpt_api_key or os.getenv("GROQ_GPT_API_KEY") or groq_key

llm_client = None
router_client = None
fallback_clients = []

# 1. Setup Groq (Preferred Brain / Limbic System)
# Used for DECISIONS (Router) always if available
if groq_key:
    try:
        groq_client = GroqClient(api_key=groq_key, model="moonshotai/kimi-k2-instruct-0905")
        router_client = groq_client
        console.print("[dim green]⚡ Groq Brain Activated (Decisions + Fallback)[/dim green]")
    except Exception as e:
        console.print(f"[dim red]Failed to init Groq: {e}[/dim red]")

# 2. Setup Chat Brain (Cortex)
# Priority: OpenRouter (GPT-4o/etc) -> Groq GPT (openai/gpt-oss-120b) -> Groq (Kimi) -> Google (Gemini) -> Mock
if openrouter_key:
    llm_client = OpenRouterClient(api_key=openrouter_key)
    fallback_clients.append(llm_client)
    console.print("[dim blue]🧠 OpenRouter (GPT) Activated for Chat[/dim blue]")

if groq_gpt_key:  # Fallback to Groq GPT if OpenRouter missing/fails
    try:
        fallback_v = GroqGPTClient(api_key=groq_gpt_key, model="openai/gpt-oss-120b")
        if not llm_client:
            llm_client = fallback_v
            console.print("[dim cyan]🧠 Groq GPT (openai/gpt-oss-120b) Activated for Chat (Fallback)[/dim cyan]")
        fallback_clients.append(fallback_v)
    except Exception as e:
        console.print(f"[dim red]Failed to init Groq GPT, using Kimi: {e}[/dim red]")

if router_client:  # Fallback to Groq Kimi if Groq GPT failed
    if not llm_client:
        llm_client = router_client
        console.print("[dim green]🧠 Kimi (Groq) Activated for Chat (Fallback)[/dim green]")
    if router_client not in fallback_clients:
        fallback_clients.append(router_client)

if api_key:
    fallback_g = GoogleGenAIClient(api_key=api_key)
    if not llm_client:
        llm_client = fallback_g
        console.print("[dim blue]🧠 Gemini Activated for Chat (Fallback)[/dim blue]")
    fallback_clients.append(fallback_g)

if not llm_client:
    llm_client = MockLLMClient()
    fallback_clients.append(llm_client)
    console.print("[dim yellow]⚠️ Mock Mode Activated[/dim yellow]")

# Final Safety Check: Ensure llm_client is not None
if llm_client is None:
    console.print("[dim red]Failed to initialize any AI client. Falling back to Mock Mode.[/dim red]")
    llm_client = MockLLMClient()

# Setup Browser Manager (Local)
browser_manager = None
# Priority: Google Gemini (best for vision) -> OpenRouter
if api_key:  # Google API key available
    browser_manager = BrowserManager(
        api_key=api_key,
        openrouter_key=openrouter_key,
        provider="google"  # Use Gemini for browser tasks
    )
    console.print("[dim blue]🌐 Browser Manager: Using Gemini 2.5 Flash[/dim blue]")
elif openrouter_key:  # Fallback to OpenRouter
    browser_manager = BrowserManager(
        api_key="dummy",
        openrouter_key=openrouter_key,
        provider="openrouter"
    )
    console.print("[dim cyan]🌐 Browser Manager: Using OpenRouter (Fallback)[/dim cyan]")

# Setup Memory (if enabled)
if config_mgr.config.use_supermemory and config_mgr.config.supermemory_api_key:

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
    
    # --- Feedback Loop (Phase 7) ---
    if hasattr(llm_client, "memory_client") and llm_client.memory_client:
        status = "Success" if return_code == 0 else "Failure"
        output_snippet = stdout[:200] if return_code == 0 else stderr[:200]
        
        memory_content = f"Action Feedback:\nRequest: {request}\nCommand: {command}\nResult: {status}\nOutput: {output_snippet}"
        meta = {
            "type": "feedback",
            "request": request,
            "command": command,
            "status": status
        }
        try:
            llm_client.memory_client.add_memory(memory_content, metadata=meta)
            console.print(f"[dim]📝 Experience recorded: {status}[/dim]")
        except Exception:
            pass

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
        
        # We need to ensure dependencies are initialized
        # existing code initialized them globally, which is fine.
        
        tui = JarvisApp(
            llm_client=llm_client,
            browser_manager=browser_manager,
            executor=executor,
            app_installer=app_installer,
            fallback_clients=fallback_clients,
        )
        
        try:
            asyncio.run(tui.run_repl())
        except KeyboardInterrupt:
            console.print("[bold red]Goodbye![/bold red]")
            sys.exit(0)

if __name__ == "__main__":
    app()
