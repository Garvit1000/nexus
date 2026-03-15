from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.markdown import Markdown
from rich.align import Align
from time import sleep

from ..core.config_manager import ConfigManager


class OnboardingUI:
    def __init__(self, config_manager: ConfigManager, console: Console):
        self.config_mgr = config_manager
        self.console = console

    def run(self):
        self.console.clear()
        self.show_welcome()

        # 1. API Keys Collection
        self.console.print("\n[bold blue]Step 1: Configure AI Providers[/bold blue]")
        self.console.print(
            "[dim]Nexus needs API keys to function. Your keys are stored locally.[/dim]\n"
        )

        # Google (Required)
        self.console.print(
            "[bold cyan]1. Google Gemini API Key[/bold cyan] [red](Required)[/red]"
        )
        self.console.print("[dim]Used for Search and Grounding capabilities.[/dim]")
        google_key = Prompt.ask("Enter Google API Key", password=True)
        while not google_key:
            self.console.print(
                "[red]Google API Key is required for search functions.[/red]"
            )
            google_key = Prompt.ask("Enter Google API Key", password=True)

        # OpenRouter (Required)
        self.console.print(
            "\n[bold cyan]2. OpenRouter API Key[/bold cyan] [red](Required)[/red]"
        )
        self.console.print("[dim]Used for main intelligence and reasoning.[/dim]")
        openrouter_key = Prompt.ask("Enter OpenRouter API Key", password=True)
        while not openrouter_key:
            self.console.print(
                "[red]OpenRouter API Key is required for core intelligence.[/red]"
            )
            openrouter_key = Prompt.ask("Enter OpenRouter API Key", password=True)

        # Groq (Optional)
        self.console.print(
            "\n[bold cyan]3. Groq API Key[/bold cyan] [green](Optional)[/green]"
        )
        self.console.print("[dim]Used for ultra-fast responses where applicable.[/dim]")
        groq_key = Prompt.ask("Enter Groq API Key (Press Enter to skip)", password=True)

        # 2. Memory Setup
        # Supermemory is provided by the system ("Ours"), so we don't ask the user for the key.
        # We just confirm if they want to use the intelligent features.
        self.console.print("\n[bold blue]Step 2: Intelligence & Memory[/bold blue]")

        # Check if we have the system key (loaded from env by ConfigManager)
        has_system_memory = self.config_mgr.config.supermemory_api_key is not None

        use_memory = False
        if has_system_memory:
            self.console.print("[green]✓ System Memory Key Detected[/green]")
            use_memory = Confirm.ask(
                "Enable [bold]Nexus Memory[/bold] (Context Intelligence)?", default=True
            )
        else:
            self.console.print(
                "[dim]System Memory Key not found in environment. Memory features disabled.[/dim]"
            )
            use_memory = False

        # 3. Save Configuration
        self.console.print(
            "\n[bold green]Setup Complete![/bold green] Saving configuration..."
        )
        self.config_mgr.update(
            onboarding_completed=True,
            google_api_key=google_key,
            openrouter_api_key=openrouter_key,
            groq_api_key=groq_key if groq_key else None,
            use_supermemory=use_memory,
            # supermemory_api_key IS NOT SAVED HERE, it relies on ENV or pre-existing config
            # Set default provider preference
            model_provider="openrouter",
        )
        sleep(1)
        self.console.print(
            "[bold green]Configuration saved![/bold green] Initializing Nexus...\n"
        )
        sleep(1)
        self.console.clear()

    def show_welcome(self):
        ascii_art = r"""
[bold blue]
   _   _  _______   __  _   _   ____  
  | \ | || ____\ \ / / | | | | / ___| 
  |  \| ||  _|  \ V /  | | | | \___ \ 
  | |\  || |___  > <   | |_| |  ___) |
  |_| \_||_____|/_/ \_\ \___/  |____/ 
[/bold blue]
[bold cyan]   SYSTEM ONLINE   [/bold cyan]
        """
        welcome_text = """
### Welcome to Nexus
**Your Intelligent Linux Assistant**

Nexus integrates deeply with your system to automate tasks, manage packages, and answer complex queries with context-aware intelligence.

*   **Smart Automation**: Generate and execute commands safely.
*   **Memory Core**: Remembers your preferences and past tasks.
*   **Web Integration**: Search and interact with the web.
        """
        self.console.print(Align.center(ascii_art))
        self.console.print(
            Panel(
                Markdown(welcome_text),
                title="[bold blue]System Initialization[/bold blue]",
                border_style="blue",
            )
        )
