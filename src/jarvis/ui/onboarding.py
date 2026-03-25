from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.markdown import Markdown
from rich.align import Align
from time import sleep
from typing import Optional

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

        # Anthropic / Claude (Optional)
        self.console.print(
            "\n[bold cyan]4. Anthropic (Claude) API Key[/bold cyan] [green](Optional)[/green]"
        )
        self.console.print(
            "[dim]High-quality reasoning fallback. Supports long context.[/dim]"
        )
        anthropic_key = Prompt.ask(
            "Enter Anthropic API Key (Press Enter to skip)", password=True
        )

        # 2. Memory (optional — bring your own Supermemory key)
        self.console.print(
            "\n[bold blue]Step 2: Optional memory (Supermemory)[/bold blue]"
        )
        self.console.print(
            "[dim]Nexus Memory (RAG) stores short snippets of your requests, generated "
            "commands, and command output in [bold]your[/bold] Supermemory project — "
            "not a shared server key. Each user should use their own API key. "
            "Create one at [link=https://supermemory.ai]supermemory.ai[/link].[/dim]\n"
        )

        # ConfigManager merges SUPERMEMORY_API_KEY from the environment on load.
        existing_sm_key: Optional[str] = self.config_mgr.config.supermemory_api_key
        use_memory = False
        supermemory_key_to_save: Optional[str] = None

        if existing_sm_key:
            self.console.print(
                "[green]✓ Supermemory API key found[/green] "
                "[dim]([cyan]SUPERMEMORY_API_KEY[/cyan] or saved config)[/dim]"
            )
            use_memory = Confirm.ask(
                "Enable [bold]Nexus Memory[/bold] (RAG) using this key?",
                default=True,
            )
        else:
            use_memory = Confirm.ask(
                "Enable [bold]Nexus Memory[/bold]? You will enter your Supermemory API key.",
                default=False,
            )
            if use_memory:
                sm_key = Prompt.ask(
                    "Supermemory API key [dim](stored locally in ~/.config/nexus/)[/dim]",
                    password=True,
                )
                if not sm_key.strip():
                    self.console.print(
                        "[yellow]No key entered — memory will stay disabled.[/yellow]"
                    )
                    use_memory = False
                else:
                    supermemory_key_to_save = sm_key.strip()

        # 3. Save Configuration
        self.console.print(
            "\n[bold green]Setup Complete![/bold green] Saving configuration..."
        )
        save_kwargs = dict(
            onboarding_completed=True,
            google_api_key=google_key,
            openrouter_api_key=openrouter_key,
            groq_api_key=groq_key if groq_key else None,
            anthropic_api_key=anthropic_key if anthropic_key else None,
            use_supermemory=use_memory,
            model_provider="openrouter",
        )
        if supermemory_key_to_save is not None:
            save_kwargs["supermemory_api_key"] = supermemory_key_to_save
        self.config_mgr.update(**save_kwargs)
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
*   **Memory Core** (optional): Your Supermemory key — RAG in your account only.
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
