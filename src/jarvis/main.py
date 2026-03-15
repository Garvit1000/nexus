import typer
import os
import sys
from typing import List, Optional
from rich.console import Console
from rich.panel import Panel
from dotenv import load_dotenv
from .utils.syntax_output import print_command_output, print_error_output, print_inline_command, print_syntax

load_dotenv()

from .core.config_manager import ConfigManager
from .core.system_detector import SystemDetector
from .core.executor import CommandExecutor
from .modules.package_manager import AppInstaller
from .modules.browser_manager import BrowserManager
from .ai.llm_client import LLMClient, MockLLMClient, OpenAIClient, GoogleGenAIClient, OpenRouterClient, GroqClient, GroqGPTClient

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

# Setup API key rotator for Google keys (supports GOOGLE_API_KEY, GOOGLE_API_KEY_2, etc.)
from .core.api_key_rotator import APIKeyRotator, load_keys_from_env
google_key_rotator: Optional[APIKeyRotator] = None
try:
    google_keys = load_keys_from_env()
    if google_keys:
        google_key_rotator = APIKeyRotator(google_keys)
except (ValueError, Exception):
    pass

# Setup AI
api_key = config_mgr.config.google_api_key or config_mgr.config.api_key or os.getenv("NEXUS_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("JARVIS_API_KEY")
openrouter_key = config_mgr.config.openrouter_api_key or os.getenv("NEXUS_OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY") or os.getenv("JARVIS_OPENROUTER_API_KEY")
groq_key = config_mgr.config.groq_api_key or os.getenv("NEXUS_GROQ_API_KEY") or os.getenv("GROQ_API_KEY") or os.getenv("JARVIS_GROQ_API_KEY")
groq_gpt_key = config_mgr.config.groq_gpt_api_key or os.getenv("NEXUS_GROQ_GPT_API_KEY") or os.getenv("GROQ_GPT_API_KEY") or groq_key

llm_client: Optional[LLMClient] = None
router_client: Optional[LLMClient] = None
fallback_clients: List[LLMClient] = []

# 1. Setup Groq (Preferred Brain / Limbic System)
# Used for DECISIONS (Router) always if available
if groq_key:
    try:
        # Groq uses different models: llama-3.3-70b-versatile, llama-3.1-8b-instant, etc.
        # kimi is NOT a groq model, but we keep it if that was intent via some proxy
        # but for native groq we should use a valid one.
        groq_client = GroqClient(api_key=groq_key, model="llama-3.3-70b-versatile")
        router_client = groq_client
    except Exception:
        pass

# 2. Setup Chat Brain (Cortex)
# Priority: OpenRouter -> Groq -> Google -> Mock
if openrouter_key:
    # Use user's requested models as fallbacks via OpenRouter
    llm_client = OpenRouterClient(api_key=openrouter_key)
    fallback_clients.append(llm_client)
    
    # Add Grok and Kimi as dedicated fallbacks if requested
    fallback_clients.append(OpenRouterClient(api_key=openrouter_key, model="x-ai/grok-2-1212"))
    fallback_clients.append(OpenRouterClient(api_key=openrouter_key, model="moonshotai/kimi-k2-instruct-0905"))

if groq_gpt_key:
    try:
        # Use a valid Groq model name
        fallback_v = GroqGPTClient(api_key=groq_gpt_key, model="llama-3.3-70b-versatile")
        if not llm_client:
            llm_client = fallback_v
        fallback_clients.append(fallback_v)
    except Exception:
        pass

if router_client:
    if not llm_client:
        llm_client = router_client
    if router_client not in fallback_clients:
        fallback_clients.append(router_client)

if api_key:
    fallback_g = GoogleGenAIClient(api_key=api_key)
    if not llm_client:
        llm_client = fallback_g
    fallback_clients.append(fallback_g)

if not llm_client:
    llm_client = MockLLMClient()
    fallback_clients.append(llm_client)
    console.print("[bold yellow]⚠ Running with reduced intelligence. Provide API keys for a better experience.[/bold yellow]")

if llm_client is None:
    llm_client = MockLLMClient()

# Setup Browser Manager (Local)
browser_manager = None
if api_key:
    browser_manager = BrowserManager(
        api_key=google_key_rotator if google_key_rotator else api_key,
        openrouter_key=openrouter_key,
        provider="google"
    )
elif openrouter_key:
    browser_manager = BrowserManager(
        api_key=openrouter_key,
        openrouter_key=openrouter_key,
        provider="openrouter"
    )

# Setup Memory (if enabled)
if config_mgr.config.use_supermemory and config_mgr.config.supermemory_api_key:
    memory_client = SupermemoryClient(api_key=config_mgr.config.supermemory_api_key)
    
    # Attach memory to ALL potential brains
    for client in fallback_clients:
        if client:
            client.set_memory_client(memory_client)
    if llm_client and llm_client not in fallback_clients:
        llm_client.set_memory_client(memory_client)
    info = sys_detector.get_info()
    sys_context = f"My System: OS={info.os_name} {info.os_version}, Package Manager={info.package_manager.value}"
    existing_memories = memory_client.query_memory(sys_context)
    if sys_context not in existing_memories:
        memory_client.add_memory(sys_context, metadata={"type": "system_info"})

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
    
    if llm_client is None:
        console.print("[bold red]Error:[/bold red] No AI brain configured.")
        return
        
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
    
    console.print("[dim]Generated command:[/dim]")
    print_inline_command(console, command, language="bash")
    console.print()
    
    # 2. Execute (Executor handles safety and confirmation)
    return_code, stdout, stderr = executor.run(command)
    
    # --- Feedback Loop (Phase 7) ---
    if llm_client is not None and hasattr(llm_client, "memory_client") and llm_client.memory_client:
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
            print_command_output(console, stdout, action="do", success=True)
    else:
        print_error_output(console, stderr or "(no output)", action="do")

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

    if llm_client is None:
        console.print("[bold red]Error:[/bold red] Search requires an active AI client.")
        return
        
    console.print(Panel(f"[bold blue]Query:[/bold blue] {query}", title="Google Search"))
    with console.status("[bold cyan]Searching google...[/bold cyan]"):
        result = llm_client.search(query)
    
    console.print(Panel(f"[bold green]Result:[/bold green]\n{result}", title="Search Result"))


@app.command()
def find(query: str):
    """
    Search for files or text within the current directory.
    Example: nexus find "config"
    """
    # Simply trigger the TUI with a pre-filled query for now, 
    # or implement a fast-track terminal logic.
    # We'll use the Orchestrator's internal logic for consistency.
    console.print(Panel(f"[bold blue]Searching for:[/bold blue] {query}", title="Local Search"))
    
    import asyncio
    import shlex
    from .core.executor import CommandExecutor
    exe = CommandExecutor()
    safe_q = shlex.quote(query)
    
    fd_exists = exe.run("which fd", require_confirmation=False)[0] == 0
    rg_exists = exe.run("which rg", require_confirmation=False)[0] == 0
    
    if "." in query and " " not in query:
        cmd = f"fd {safe_q} ." if fd_exists else f"find . -maxdepth 4 -name '*'{safe_q}'*' -not -path '*/.*'"
    else:
        cmd = f"rg -l -- {safe_q} ." if rg_exists else f"grep -rIl --max-count=1 -- {safe_q} . | head -n 20"
        
    rc, out, err = exe.run(cmd, require_confirmation=False)
    
    if rc == 0 and not out.strip() and "." in query:
        console.print("[dim]No local matches. Searching broader...[/dim]")
        check_locate = "which locate"
        l_rc, _, _ = exe.run(check_locate, require_confirmation=False)
        
        if l_rc == 0:
            cmd = f"locate -l 10 '*'{safe_q}'*'"
        else:
            cmd = f"find / -name '*'{safe_q}'*' 2>/dev/null | head -n 10"
            
        rc, out, err = exe.run(cmd, require_confirmation=False)

    if rc == 0:
        console.print(Panel(out.strip() if out.strip() else "[yellow]No matches found anywhere.[/yellow]", title="Search Results"))
    else:
        console.print(f"[red]Search failed:[/red] {err}")


@app.command()
def read(path: str):
    """
    Read the content of a local file.
    Example: nexus read "config.json"
    """
    from pathlib import Path
    abs_path = Path(path).expanduser().resolve()

    home = Path.home()
    cwd = Path.cwd()
    allowed = str(abs_path).startswith(str(home)) or str(abs_path).startswith(str(cwd))
    if not allowed:
        console.print(f"[red]Error:[/red] Reading files outside your home directory is not allowed: {abs_path}")
        return

    if not abs_path.exists():
        console.print(f"[red]Error:[/red] File not found: {abs_path}")
        return
    if not abs_path.is_file():
        console.print(f"[red]Error:[/red] Not a file: {abs_path}")
        return

    content = abs_path.read_text(encoding='utf-8', errors='ignore')
    print_syntax(console, content, str(abs_path))


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
        from .ui.console_app import NexusApp
        
        # We need to ensure dependencies are initialized
        # existing code initialized them globally, which is fine.
        
        # Heuristics for DecisionEngine (Restored)
        from .ai.decision_engine import Intent
        def apply_heuristics(text: str) -> Intent | None:
            if text.startswith("search for") or text.startswith("google "):
                query = text.replace("search for", "").replace("google ", "").strip()
                return Intent(action="COMMAND", command="/search", args=query, confidence=0.9)

            if text.startswith("find file") or text.startswith("search file"):
                 query = text.replace("find file", "").replace("search file", "").strip()
                 return Intent(action="COMMAND", command="/find", args=query, confidence=1.0)

            if text.startswith("read file") or text.startswith("cat "):
                 path = text.replace("read file", "").replace("cat ", "").strip()
                 return Intent(action="COMMAND", command="/read", args=path, confidence=1.0)
            return None

        tui = NexusApp(
            llm_client=llm_client,
            router_client=router_client,
            browser_manager=browser_manager,
            executor=executor,
            app_installer=app_installer,
            fallback_clients=fallback_clients,
        )
        
        # Inject heuristics if the engine supports it
        if hasattr(tui, 'decision_engine'):
            tui.decision_engine.add_heuristic(apply_heuristics)
        
        try:
            asyncio.run(tui.run_repl())
        except KeyboardInterrupt:
            console.print("[bold red]Goodbye![/bold red]")
            sys.exit(0)

if __name__ == "__main__":
    app()
