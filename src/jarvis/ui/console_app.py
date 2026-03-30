"""
Nexus TUI — product-quality terminal interface.

Design principles:
  • Zero debug noise in the output stream
  • Every state transition has a visual indicator (spinner, rule, panel)
  • Consistent colour palette: cyan accent, dim for secondary info, red for errors
  • Prompt is clean — a single ❯ character, no angle-bracket HTML fragments
  • Errors are shown once, clearly, and never swallowed silently
"""

import asyncio
from typing import Optional, TYPE_CHECKING, cast

from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text
from rich import box
import pyfiglet
from prompt_toolkit import PromptSession, HTML
from prompt_toolkit.styles import Style as PromptStyle
from prompt_toolkit.history import InMemoryHistory

if TYPE_CHECKING:
    from ..ai.decision_engine import Intent

from ..ai.decision_engine import DecisionEngine, Intent
from ..core.model_catalog import (
    TASK_MODEL_OPTIONS,
    find_client_for_provider,
    resolve_provider_for_model,
)


# ── Colour palette ────────────────────────────────────────────────────────────
ACCENT = "cyan"
DIM = "dim"
SUCCESS = "green"
ERROR = "red"
WARN = "yellow"
NEUTRAL = "white"

# ── Prompt style ──────────────────────────────────────────────────────────────
_PROMPT_STYLE = PromptStyle.from_dict(
    {
        "prompt": "#00d7ff bold",  # bright cyan
        "": "#ffffff",  # input text
    }
)


class NexusApp:
    """Main interactive TUI for Nexus."""

    def __init__(
        self,
        llm_client=None,
        browser_manager=None,
        executor=None,
        app_installer=None,
        router_client=None,
        fallback_clients=None,
    ):
        self.console = Console(highlight=False)
        self.session = PromptSession(history=InMemoryHistory())
        self.is_running = True

        self.llm_client = llm_client
        self.fallback_clients = fallback_clients or []
        self.browser_manager = browser_manager
        self.executor = executor
        self.app_installer = app_installer

        from ..core.persistent_session_manager import PersistentSessionManager

        self.session_manager = PersistentSessionManager(max_history=50)

        self.decision_engine = DecisionEngine(
            llm_client, router_client, self.session_manager
        )
        self.orchestrator = None

        self.last_action_result: Optional[str] = None
        self.last_action_type: str = "CHAT"
        # /think toggle — show the thinking block by default
        self._show_thinking: bool = True

    # ── Header ────────────────────────────────────────────────────────────────

    def _print_header(self):
        """Print the Nexus splash header once on startup."""
        self.console.clear()

        # banner3-D font, replacing '#' → '█' gives the Claude Code pixel-block look
        logo = pyfiglet.figlet_format("NEXUS", font="banner3-D")
        logo = logo.replace("#", "█").replace(":", " ")  # clean up filler dots
        self.console.print(
            Panel(
                Text(logo, style=f"bold {ACCENT}", justify="center"),
                subtitle="[dim]Your AI-powered Linux assistant[/dim]",
                border_style=ACCENT,
                box=box.DOUBLE_EDGE,
                padding=(0, 4),
            )
        )
        self.console.print(
            "  [dim]Type your request or [cyan]/help[/cyan] for commands  ·  "
            "[cyan]/exit[/cyan] to quit[/dim]\n"
        )

    # ── REPL ──────────────────────────────────────────────────────────────────

    async def run_repl(self):
        """Main event loop."""
        self._print_header()

        while self.is_running:
            try:
                user_input = await self.session.prompt_async(
                    HTML("<b><style color='#00d7ff'>❯</style></b> "),
                    style=_PROMPT_STYLE,
                )

                if not user_input or not user_input.strip():
                    continue

                user_input = user_input.strip()

                if user_input.lower() in ("/exit", "/quit", "exit", "quit"):
                    self.console.print(f"\n[{DIM}]Goodbye.[/{DIM}]\n")
                    self.is_running = False
                    break

                await self._handle_input(user_input)

            except (KeyboardInterrupt, EOFError):
                self.console.print(f"\n[{DIM}]Interrupted.[/{DIM}]\n")
                self.is_running = False

    # ── Input dispatch ────────────────────────────────────────────────────────

    async def _handle_input(self, text: str):
        self.console.print()  # breathing room

        if text.startswith("/"):
            await self._handle_command(text)
        else:
            await self._handle_chat(text)

        self.console.print()  # breathing room after response

    # ── Slash commands ────────────────────────────────────────────────────────

    async def _handle_command(self, text: str) -> bool:
        parts = text.split(" ", 1)
        command = parts[0].lower()
        args = parts[1].strip() if len(parts) > 1 else ""

        if command == "/help":
            self._show_help()
            return True

        if command == "/think":
            self._show_thinking = not self._show_thinking
            state = (
                "[green]on[/green]" if self._show_thinking else "[yellow]off[/yellow]"
            )
            self.console.print(f"  [{DIM}]Thinking block {state}[/{DIM}]")
            return True

        if command == "/browse":
            return await self._cmd_browse(args)

        if command == "/search":
            return await self._cmd_search(args)

        if command == "/install":
            return self._cmd_package("install", args)

        if command == "/remove":
            return self._cmd_package("remove", args)

        if command == "/update":
            return self._cmd_update()

        if command == "/status":
            self._show_status()
            return True

        if command == "/settings":
            return await self._cmd_settings(args)

        if command == "/find":
            return await self._cmd_find(args)

        if command == "/read":
            return await self._cmd_read(args)

        if command == "/do":
            return await self._cmd_do(args)

        self.console.print(
            f"[{ERROR}]Unknown command: {command}[/{ERROR}]  Type [cyan]/help[/cyan] for a list."
        )
        return False

    def _show_help(self):
        rows = [
            ("  /browse [i]task[/i]", "Perform a browser-based task"),
            ("  /search [i]query[/i]", "Answer a question via web search"),
            ("  /find [i]query[/i]", "Search for files or text on filesystem"),
            ("  /read [i]path[/i]", "Read a local file with syntax highlighting"),
            ("  /do [i]request[/i]", "Execute a natural-language command directly"),
            ("  /install [i]pkg[/i]", "Install a system package"),
            ("  /remove [i]pkg[/i]", "Remove a system package"),
            ("  /update", "Update all system packages"),
            ("  /think", "Toggle the Thinking block on/off"),
            ("  /status", "Show active AI provider and mode"),
            ("  /settings", "Show current config (models, keys, status)"),
            ("  /settings help", "Detailed settings usage guide"),
            ("  /settings model", "Switch model per task (chat/router/browser)"),
            ("  /settings key", "Add or update an API key"),
            ("  /help", "Show this help"),
            ("  /exit", "Quit Nexus"),
        ]
        lines = "\n".join(
            f"[cyan]{cmd}[/cyan]  [{DIM}]{desc}[/{DIM}]" for cmd, desc in rows
        )
        self.console.print(
            Panel(lines, title="Commands", border_style=ACCENT, padding=(1, 2))
        )

    def _show_status(self):
        provider = type(self.llm_client).__name__ if self.llm_client else "None"
        browser = "Ready" if self.browser_manager else "Not configured"
        executor_mode = (
            "Dry-run"
            if (self.executor and getattr(self.executor, "dry_run", False))
            else "Live"
        )
        lines = (
            f"[{DIM}]AI provider :[/{DIM}]   [cyan]{provider}[/cyan]\n"
            f"[{DIM}]Browser     :[/{DIM}]   [{WARN if browser == 'Not configured' else SUCCESS}]{browser}[/{WARN if browser == 'Not configured' else SUCCESS}]\n"
            f"[{DIM}]Executor    :[/{DIM}]   [cyan]{executor_mode}[/cyan]"
        )
        self.console.print(
            Panel(lines, title="Status", border_style=ACCENT, padding=(0, 2))
        )

    # ── Settings command ──────────────────────────────────────────────────

    async def _cmd_settings(self, args: str) -> bool:
        """Handle /settings subcommands: show, model, key, help."""
        parts = args.split(" ", 1) if args else [""]
        subcmd = parts[0].lower()
        subargs = parts[1].strip() if len(parts) > 1 else ""

        if subcmd == "show" or subcmd == "":
            return self._settings_show()
        elif subcmd == "help":
            return self._settings_help()
        elif subcmd == "model":
            return await self._settings_model(subargs)
        elif subcmd == "key":
            return await self._settings_key(subargs)
        else:
            self.console.print(
                f"[{WARN}]Unknown settings subcommand: {subcmd}[/{WARN}]\n"
                f"[{DIM}]Usage: /settings | /settings help | /settings model | /settings key[/{DIM}]"
            )
            return False

    def _settings_show(self) -> bool:
        """Display current configuration with per-task model breakdown."""
        chat_provider = type(self.llm_client).__name__ if self.llm_client else "None"
        chat_model = (
            getattr(self.llm_client, "model", "N/A") if self.llm_client else "N/A"
        )

        router_client = getattr(self.decision_engine, "router_client", None)
        router_provider = type(router_client).__name__ if router_client else "None"
        router_model = (
            getattr(router_client, "model", "N/A") if router_client else "N/A"
        )

        browser_status = "Not configured"
        browser_model = "N/A"
        if self.browser_manager:
            browser_status = "Ready"
            browser_llm = getattr(self.browser_manager, "llm", None)
            if browser_llm:
                browser_model = getattr(browser_llm, "model", None) or getattr(
                    browser_llm, "model_name", "unknown"
                )

        browser_style = SUCCESS if self.browser_manager else WARN

        from ..ai.llm_client import GoogleGenAIClient

        search_model = "N/A (needs GOOGLE_API_KEY)"
        candidates = [self.llm_client] + self.fallback_clients
        for c in candidates:
            if isinstance(c, GoogleGenAIClient):
                search_model = "gemini-2.5-flash → gemini-1.5-flash"
                break

        fallback_names = (
            [type(c).__name__ for c in self.fallback_clients]
            if self.fallback_clients
            else ["None"]
        )

        has_memory = (
            (
                hasattr(self.llm_client, "memory_client")
                and self.llm_client.memory_client
            )
            if self.llm_client
            else False
        )
        memory_status = "Active" if has_memory else "Disabled"
        memory_style = SUCCESS if has_memory else DIM

        executor_mode = (
            "Dry-run"
            if (self.executor and getattr(self.executor, "dry_run", False))
            else "Live"
        )

        cache_stats = ""
        if hasattr(self.decision_engine, "get_cache_stats"):
            stats = self.decision_engine.get_cache_stats()
            cache_stats = (
                f"hits={stats.get('hits', 0)}, misses={stats.get('misses', 0)}, "
                f"size={stats.get('size', 0)}"
            )

        lines = (
            f"[bold {ACCENT}]Task Assignments:[/bold {ACCENT}]\n"
            f"[{DIM}]  Chat       :[/{DIM}]  [cyan]{chat_model}[/cyan]  [{DIM}]({chat_provider})[/{DIM}]\n"
            f"[{DIM}]  Router     :[/{DIM}]  [cyan]{router_model}[/cyan]  [{DIM}]({router_provider})[/{DIM}]\n"
            f"[{DIM}]  Browser    :[/{DIM}]  [cyan]{browser_model}[/cyan]  [{browser_style}]{browser_status}[/{browser_style}]\n"
            f"[{DIM}]  Search     :[/{DIM}]  [cyan]{search_model}[/cyan]\n"
            f"[{DIM}]  Planning   :[/{DIM}]  [{DIM}]Uses Chat model + fallbacks[/{DIM}]\n"
            f"[{DIM}]  /do        :[/{DIM}]  [{DIM}]Uses Chat model[/{DIM}]\n"
            f"\n[bold {ACCENT}]System:[/bold {ACCENT}]\n"
            f"[{DIM}]  Fallbacks  :[/{DIM}]  [{DIM}]{' → '.join(fallback_names)}[/{DIM}]\n"
            f"[{DIM}]  Memory     :[/{DIM}]  [{memory_style}]{memory_status}[/{memory_style}]\n"
            f"[{DIM}]  Executor   :[/{DIM}]  [cyan]{executor_mode}[/cyan]"
        )
        if cache_stats:
            lines += f"\n[{DIM}]  Route Cache:[/{DIM}]  [{DIM}]{cache_stats}[/{DIM}]"

        self.console.print(
            Panel(lines, title="⚙ Settings", border_style=ACCENT, padding=(1, 2))
        )
        self.console.print(
            f"[{DIM}]Tip: /settings model [task] to switch model per task, "
            f"/settings key to update a key, "
            f"/settings help for full guide[/{DIM}]"
        )
        return True

    def _settings_help(self) -> bool:
        """Display comprehensive /settings usage guide."""
        chat_model = (
            getattr(self.llm_client, "model", "N/A") if self.llm_client else "N/A"
        )
        router_client = getattr(self.decision_engine, "router_client", None)
        router_model = (
            getattr(router_client, "model", "N/A") if router_client else "N/A"
        )
        browser_llm = (
            getattr(self.browser_manager, "llm", None) if self.browser_manager else None
        )
        browser_model = "N/A"
        if browser_llm:
            browser_model = getattr(browser_llm, "model", None) or getattr(
                browser_llm, "model_name", "unknown"
            )

        guide = (
            f"[bold {ACCENT}]Subcommands:[/bold {ACCENT}]\n"
            f"  [cyan]/settings[/cyan]              Show current config\n"
            f"  [cyan]/settings help[/cyan]         This guide\n"
            f"  [cyan]/settings model[/cyan]        Switch model (interactive)\n"
            f"  [cyan]/settings model chat[/cyan]   Switch chat/planning model\n"
            f"  [cyan]/settings model router[/cyan] Switch router/decision model\n"
            f"  [cyan]/settings model browser[/cyan] Switch browser automation model\n"
            f"  [cyan]/settings key[/cyan]          Update API key (interactive)\n"
            f"  [cyan]/settings key google <key>[/cyan]\n"
            f"\n"
            f"[bold {ACCENT}]Current Models by Task:[/bold {ACCENT}]\n"
            f"  [cyan]Chat[/cyan]     {chat_model}  [{DIM}]Powers: chat, /do, planning[/{DIM}]\n"
            f"  [cyan]Router[/cyan]   {router_model}  [{DIM}]Powers: intent routing[/{DIM}]\n"
            f"  [cyan]Browser[/cyan]  {browser_model}  [{DIM}]Powers: /browse[/{DIM}]\n"
            f"  [cyan]Search[/cyan]   gemini-2.5-flash  [{DIM}]Powers: /search (hardcoded)[/{DIM}]\n"
            f"\n"
            f"[bold {ACCENT}]Chat Fallback Chain:[/bold {ACCENT}]\n"
            f"  [{DIM}]OpenRouter → Anthropic → GroqGPT → Groq Kimi → Google Gemini → Mock[/{DIM}]\n"
            f"\n"
            f"[bold {ACCENT}]API Key Providers:[/bold {ACCENT}]\n"
            f"  [{DIM}]google, openrouter, groq, groq_gpt, anthropic, supermemory, browser[/{DIM}]\n"
            f"\n"
            f"[bold {ACCENT}]Examples:[/bold {ACCENT}]\n"
            f"  [cyan]/settings model chat openai/gpt-oss-120b:free[/cyan]\n"
            f"  [cyan]/settings model router moonshotai/kimi-k2-instruct-0905[/cyan]\n"
            f"  [cyan]/settings key openrouter sk-or-v1-...[/cyan]"
        )
        self.console.print(
            Panel(guide, title="⚙ Settings Help", border_style=ACCENT, padding=(1, 2))
        )
        return True

    async def _interactive_select(self, options: list[str]) -> Optional[str]:
        if not options:
            return None

        from prompt_toolkit.application import Application
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout.containers import Window
        from prompt_toolkit.layout.controls import FormattedTextControl
        from prompt_toolkit.layout.layout import Layout
        from prompt_toolkit.styles import Style

        index = [0]
        kb = KeyBindings()

        @kb.add("up")
        def _(event):
            index[0] = max(0, index[0] - 1)

        @kb.add("down")
        def _(event):
            index[0] = min(len(options) - 1, index[0] + 1)

        @kb.add("enter")
        def _(event):
            event.app.exit(result=options[index[0]])

        @kb.add("c-c")
        def _(event):
            event.app.exit(result=None)

        def get_text():
            result = [
                (
                    "class:title",
                    "◆ Select a model (↑/↓ to navigate, Enter to select):\n",
                )
            ]
            for i, opt in enumerate(options):
                if i == index[0]:
                    result.append(("class:selected", f"  ● {opt}\n"))
                else:
                    result.append(("", f"  ○ {opt}\n"))
            return result

        control = FormattedTextControl(get_text)
        window = Window(content=control, height=len(options) + 1)
        layout = Layout(window)

        style = Style(
            [
                ("title", "#00d7ff bold"),
                ("selected", "#00d7ff bold"),
            ]
        )

        app = Application(
            layout=layout, key_bindings=kb, style=style, mouse_support=True
        )
        return await app.run_async()

    async def _settings_model(self, args: str) -> bool:
        parts = args.split(" ", 1) if args else [""]
        task_name = parts[0].lower()
        model_name = parts[1].strip() if len(parts) > 1 else ""

        valid_tasks = list(TASK_MODEL_OPTIONS.keys())

        if not task_name:
            task_labels = [
                f"{t}  ({TASK_MODEL_OPTIONS[t]['label']})" for t in valid_tasks
            ]
            selected = await self._interactive_select(task_labels)
            if not selected:
                self.console.print(f"[{DIM}]Model selection cancelled.[/{DIM}]")
                return False
            task_name = selected.split(" ")[0].strip()

        if task_name not in valid_tasks:
            self.console.print(
                f"[{WARN}]Unknown task: {task_name}[/{WARN}]\n"
                f"[{DIM}]Available tasks: {', '.join(valid_tasks)}[/{DIM}]"
            )
            return False

        if not model_name:
            from ..core.config_manager import ConfigManager

            config = ConfigManager().config

            task_info = TASK_MODEL_OPTIONS[task_name]
            options = []
            for key_field, group in task_info["models"].items():
                if getattr(config, key_field, None):
                    for m in group["items"]:
                        provider_tag = group["provider"].replace("Client", "")
                        options.append(f"{m}  ({provider_tag})")

            if not options:
                self.console.print(
                    f"[{WARN}]No API keys configured for {task_name} models. "
                    f"Set an API key first with /settings key[/{WARN}]"
                )
                return False

            target = self._get_task_target(task_name)
            current = getattr(target, "model", None) if target else None
            if current:
                for i, opt in enumerate(options):
                    bare_model = opt.split("  (")[0]
                    if bare_model == current:
                        options[i] = f"{opt}  ◄ current"
                        options.insert(0, options.pop(i))
                        break

            selected = await self._interactive_select(options)
            if not selected:
                self.console.print(f"[{DIM}]Model selection cancelled.[/{DIM}]")
                return False
            model_name = selected.split("  (")[0].strip()

        target_provider = resolve_provider_for_model(task_name, model_name)

        old_target = self._get_task_target(task_name)
        old_model = getattr(old_target, "model", "unknown") if old_target else "unknown"
        old_provider = type(old_target).__name__ if old_target else "None"

        new_client = old_target
        provider_switched = False
        if target_provider and old_provider != target_provider:
            candidate = find_client_for_provider(
                self.fallback_clients,
                getattr(self.decision_engine, "router_client", None),
                target_provider,
            )
            if candidate:
                new_client = candidate
                provider_switched = True
            else:
                self.console.print(
                    f"[{WARN}]No {target_provider} instance available in fallback chain. "
                    f"Model set on current provider ({old_provider}).[/{WARN}]"
                )

        if not new_client:
            self.console.print(
                f"[{ERROR}]No provider configured for {task_name}.[/{ERROR}]"
            )
            return False

        new_client.model = model_name
        self._set_task_target(task_name, new_client)

        # Persist model choice to config so it survives across sessions
        config_field = f"{task_name}_model"
        from ..core.config_manager import ConfigManager as _CM

        _CM().update(**{config_field: model_name})

        new_provider = type(new_client).__name__
        switch_info = f"  [cyan]({new_provider})[/cyan]" if provider_switched else ""
        self.console.print(
            f"[{SUCCESS}]✓[/{SUCCESS}] [{DIM}]{task_name}[/{DIM}] model switched: "
            f"[{DIM}]{old_model}[/{DIM}] → [cyan]{model_name}[/cyan]{switch_info}"
        )
        return True

    def _get_task_target(self, task_name: str):
        if task_name == "chat":
            return self.llm_client
        if task_name == "router":
            return getattr(self.decision_engine, "router_client", None)
        if task_name == "browser":
            if self.browser_manager:
                return getattr(self.browser_manager, "llm", None)
            return None
        return None

    def _set_task_target(self, task_name: str, client) -> None:
        if task_name == "chat":
            self.llm_client = client
            if self.orchestrator:
                self.orchestrator.llm_client = client
            if self.decision_engine:
                self.decision_engine.llm_client = client
        elif task_name == "router":
            if self.decision_engine:
                self.decision_engine.router_client = client
        elif task_name == "browser":
            if self.browser_manager:
                self.browser_manager.llm = client

    async def _settings_key(self, args: str) -> bool:
        SUPPORTED_PROVIDERS = {
            "google": "google_api_key",
            "openrouter": "openrouter_api_key",
            "groq": "groq_api_key",
            "groq_gpt": "groq_gpt_api_key",
            "anthropic": "anthropic_api_key",
            "supermemory": "supermemory_api_key",
            "browser": "browser_use_api_key",
            "google_api_key": "google_api_key",
            "openrouter_api_key": "openrouter_api_key",
            "groq_api_key": "groq_api_key",
            "groq_gpt_api_key": "groq_gpt_api_key",
            "anthropic_api_key": "anthropic_api_key",
            "supermemory_api_key": "supermemory_api_key",
            "browser_use_api_key": "browser_use_api_key",
            "sarvam_api_key": "sarvam_api_key",
            "groq_api": "groq_api_key",
        }

        FIELD_TO_ALIAS = {
            "google_api_key": "google",
            "openrouter_api_key": "openrouter",
            "groq_api_key": "groq",
            "groq_gpt_api_key": "groq_gpt",
            "anthropic_api_key": "anthropic",
            "supermemory_api_key": "supermemory",
            "browser_use_api_key": "browser",
        }

        parts = args.split(" ", 1) if args else [""]
        provider = parts[0].strip()
        key_value = parts[1].strip() if len(parts) > 1 else ""

        if not provider or not key_value:
            from dotenv import dotenv_values
            from pathlib import Path

            env_path = Path(".env").resolve()
            env_keys = []
            if env_path.exists():
                env_keys = list(dotenv_values(env_path).keys())

            ADD_NEW_KEY_OPTION = "➕ Add a new key"
            options = env_keys + [ADD_NEW_KEY_OPTION]

            selected = await self._interactive_select(options)
            if not selected:
                self.console.print(f"[{DIM}]Key selection cancelled.[/{DIM}]")
                return False

            if selected == ADD_NEW_KEY_OPTION:
                new_key_name = await self.session.prompt_async(
                    HTML(
                        "<b><style color='#00d7ff'>Provider/Key Name (e.g. GROQ_API_KEY):</style></b> "
                    )
                )
                if not new_key_name or not new_key_name.strip():
                    self.console.print(f"[{DIM}]Cancelled.[/{DIM}]")
                    return False
                provider = new_key_name.strip()
            else:
                provider = selected

            new_key_value = await self.session.prompt_async(
                HTML(
                    f"<b><style color='#00d7ff'>New value for {provider}:</style></b> "
                )
            )
            if not new_key_value or not new_key_value.strip():
                self.console.print(f"[{DIM}]Cancelled.[/{DIM}]")
                return False
            key_value = new_key_value.strip()

        try:
            from ..core.config_manager import ConfigManager

            config_mgr = ConfigManager()

            provider_lower = provider.lower()

            if provider_lower in SUPPORTED_PROVIDERS:
                config_field = SUPPORTED_PROVIDERS[provider_lower]
                config_mgr.update(**{config_field: key_value})
                target_alias = FIELD_TO_ALIAS.get(config_field, provider_lower)
                display_name = provider
            else:
                from dotenv import set_key
                from pathlib import Path

                env_path = Path(".env").resolve()
                env_key = provider.upper()
                if env_path.exists():
                    set_key(str(env_path), env_key, key_value)
                display_name = env_key
                target_alias = provider_lower

            from ..ai.llm_client import (
                AnthropicClient,
                GoogleGenAIClient,
                GroqClient,
                GroqGPTClient,
                OpenRouterClient,
            )

            for c in [self.llm_client] + self.fallback_clients:
                if not c:
                    continue
                try:
                    if target_alias == "google" and isinstance(c, GoogleGenAIClient):
                        from google import genai

                        c.client = genai.Client(api_key=key_value)
                    elif target_alias == "openrouter" and isinstance(
                        c, OpenRouterClient
                    ):
                        from openai import OpenAI

                        c.client = OpenAI(
                            base_url="https://openrouter.ai/api/v1",
                            api_key=key_value,
                            default_headers={
                                "HTTP-Referer": "https://github.com/Garvit1000/nexus",
                                "X-Title": "Nexus Agent",
                            },
                        )
                    elif target_alias == "groq" and isinstance(c, GroqClient):
                        from groq import Groq

                        c.client = Groq(api_key=key_value)
                    elif target_alias == "groq_gpt" and isinstance(c, GroqGPTClient):
                        from groq import Groq

                        c.client = Groq(api_key=key_value)
                    elif target_alias == "anthropic" and isinstance(c, AnthropicClient):
                        from anthropic import Anthropic

                        c.client = Anthropic(api_key=key_value)
                except Exception as e:
                    self.console.print(
                        f"[{WARN}]Failed to live-reload client {type(c).__name__}: {e}[/{WARN}]"
                    )

        except Exception as e:
            self.console.print(f"[{ERROR}]Failed to save config:[/{ERROR}] {e}")
            return False

        if len(key_value) > 10:
            masked = key_value[:5] + "•" * (len(key_value) - 8) + key_value[-3:]
        else:
            masked = "•" * len(key_value)

        self.console.print(
            f"[{SUCCESS}]✓[/{SUCCESS}] API key for [cyan]{display_name}[/cyan] updated, saved, and loaded live!\n"
            f"[{DIM}]Key: {masked}[/{DIM}]"
        )
        return True

    async def _cmd_browse(self, args: str) -> bool:
        if not args:
            self.console.print(
                f"[{WARN}]Usage: /browse [i]task description[/i][/{WARN}]"
            )
            return False
        if not self.browser_manager:
            self.console.print(
                f"[{ERROR}]Browser is not configured. Install [cyan]nexus[browser][/cyan] and ensure an API key is set.[/{ERROR}]"
            )
            return False
        with self.console.status(f"[{ACCENT}]Browsing…[/{ACCENT}]", spinner="dots"):
            try:
                result = await asyncio.get_event_loop().run_in_executor(
                    None, self.browser_manager.run_task, args
                )
            except Exception as e:
                self.console.print(f"[{ERROR}]Browser error:[/{ERROR}] {e}")
                return False
        self.console.print(
            Panel(str(result), title="Browser Result", border_style=SUCCESS)
        )
        return True

    def _google_search_client(self):
        """First configured Gemini client (supports Google Search grounding)."""
        from ..ai.llm_client import GoogleGenAIClient

        for c in [self.llm_client] + list(self.fallback_clients):
            if isinstance(c, GoogleGenAIClient):
                return c
        return None

    async def _grounded_web_search(
        self, query: str
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Run Gemini + Google Search grounding for ``query``.

        Returns:
            (answer_text, None) on success.
            (None, user_facing_error) on failure (missing client or API error).
        """
        if not query.strip():
            return None, "Empty search query."
        if not self.llm_client:
            return None, "No AI provider is configured."

        search_client = self._google_search_client()
        if not search_client:
            return None, (
                "Web search requires a Google (Gemini) provider. "
                "Set GOOGLE_API_KEY to enable grounded answers."
            )

        try:
            result = await asyncio.to_thread(search_client.search, query.strip())
        except Exception as e:
            return None, f"Search error: {e}"

        if not (result and str(result).strip()):
            return None, "Search returned no answer."
        return str(result).strip(), None

    async def _cmd_search(self, args: str) -> bool:
        if not args:
            self.console.print(f"[{WARN}]Usage: /search [i]query[/i][/{WARN}]")
            return False

        with self.console.status(f"[{ACCENT}]Searching…[/{ACCENT}]", spinner="dots"):
            result, err = await self._grounded_web_search(args)

        if err:
            tag = WARN if "requires a Google" in err else ERROR
            self.console.print(f"[{tag}]{err}[/{tag}]")
            return False

        self.console.print(Panel(result, title="Search Result", border_style=SUCCESS))
        return True

    def _cmd_package(self, action: str, pkg: str) -> bool:
        if not pkg:
            self.console.print(f"[{WARN}]Usage: /{action} [i]package[/i][/{WARN}]")
            return False
        if not self.app_installer:
            self.console.print(
                f"[{ERROR}]Package installer is not available.[/{ERROR}]"
            )
            return False
        label = "Installing" if action == "install" else "Removing"
        with self.console.status(
            f"[{ACCENT}]{label} [bold]{pkg}[/bold]…[/{ACCENT}]", spinner="dots"
        ):
            fn = (
                self.app_installer.install
                if action == "install"
                else self.app_installer.remove
            )
            success = fn(pkg)
        if success:
            past = "installed" if action == "install" else "removed"
            self.console.print(
                f"[{SUCCESS}]✓[/{SUCCESS}] [bold]{pkg}[/bold] {past} successfully."
            )
        else:
            self.console.print(
                f"[{ERROR}]✗[/{ERROR}] Failed to {action} [bold]{pkg}[/bold]."
            )
        return success

    def _cmd_update(self) -> bool:
        if not self.app_installer:
            self.console.print(
                f"[{ERROR}]Package installer is not available.[/{ERROR}]"
            )
            return False
        with self.console.status(
            f"[{ACCENT}]Updating system packages…[/{ACCENT}]", spinner="dots"
        ):
            success = self.app_installer.update_system()
        if success:
            self.console.print(f"[{SUCCESS}]✓[/{SUCCESS}] System updated.")
        else:
            self.console.print(f"[{ERROR}]✗[/{ERROR}] System update failed.")
        return success

    async def _cmd_find(self, args: str) -> bool:
        if not args:
            self.console.print(f"[{WARN}]Usage: /find [i]query[/i][/{WARN}]")
            return False
        import shlex as _shlex

        safe_q = _shlex.quote(args)
        if not self.executor:
            self.console.print(f"[{ERROR}]Executor not available.[/{ERROR}]")
            return False

        fd_ok = (
            await asyncio.to_thread(self.executor.run, "which fd", False, None, False)
        )[0] == 0
        rg_ok = (
            await asyncio.to_thread(self.executor.run, "which rg", False, None, False)
        )[0] == 0

        if "." in args and " " not in args:
            cmd = (
                f"fd {safe_q} ."
                if fd_ok
                else f"find . -maxdepth 4 -name '*'{safe_q}'*' -not -path '*/.*'"
            )
        else:
            cmd = (
                f"rg -l -- {safe_q} ."
                if rg_ok
                else f"grep -rIl --max-count=1 -- {safe_q} . | head -n 20"
            )

        rc, out, err = await asyncio.to_thread(
            self.executor.run, cmd, False, None, False
        )

        if rc == 0 and not out.strip() and "." in args:
            self.console.print(f"[{DIM}]No local matches. Searching broader…[/{DIM}]")
            l_rc, _, _ = await asyncio.to_thread(
                self.executor.run, "which locate", False, None, False
            )
            if l_rc == 0:
                cmd = f"locate -l 10 '*'{safe_q}'*'"
            else:
                cmd = f"find / -name '*'{safe_q}'*' 2>/dev/null | head -n 10"
            rc, out, err = await asyncio.to_thread(
                self.executor.run, cmd, False, None, False
            )

        if rc == 0 and out.strip():
            self.console.print(
                Panel(out.strip(), title="Search Results", border_style=SUCCESS)
            )
        elif rc == 0:
            self.console.print(f"[{WARN}]No matches found.[/{WARN}]")
        else:
            self.console.print(f"[{ERROR}]Search failed:[/{ERROR}] {err}")
        return rc == 0

    async def _cmd_read(self, args: str) -> bool:
        if not args:
            self.console.print(f"[{WARN}]Usage: /read [i]path[/i][/{WARN}]")
            return False
        from pathlib import Path as _Path

        abs_path = _Path(args).expanduser().resolve()
        home = _Path.home()
        cwd = _Path.cwd()
        if not (
            str(abs_path).startswith(str(home)) or str(abs_path).startswith(str(cwd))
        ):
            self.console.print(
                f"[{ERROR}]Reading files outside your home directory is not allowed.[/{ERROR}]"
            )
            return False
        if not abs_path.exists():
            self.console.print(f"[{ERROR}]File not found: {abs_path}[/{ERROR}]")
            return False
        if not abs_path.is_file():
            self.console.print(f"[{ERROR}]Not a file: {abs_path}[/{ERROR}]")
            return False
        content = abs_path.read_text(encoding="utf-8", errors="ignore")
        from ..utils.syntax_output import print_syntax

        print_syntax(self.console, content, str(abs_path))
        return True

    async def _cmd_do(self, args: str) -> bool:
        if not args:
            self.console.print(
                f"[{WARN}]Usage: /do [i]natural language request[/i][/{WARN}]"
            )
            return False
        if not self.llm_client:
            self.console.print(f"[{ERROR}]No AI provider configured.[/{ERROR}]")
            return False
        from ..ai.command_generator import CommandGenerator
        from ..core.system_detector import SystemDetector

        sys_info = SystemDetector().get_info()
        gen = CommandGenerator(
            self.llm_client, sys_info, fallback_clients=self.fallback_clients
        )
        with self.console.status(
            f"[{ACCENT}]Generating command…[/{ACCENT}]", spinner="dots"
        ):
            try:
                command = await asyncio.to_thread(gen.generate_command, args)
            except Exception as e:
                self.console.print(f"[{ERROR}]Command generation failed:[/{ERROR}] {e}")
                return False
        from ..utils.syntax_output import print_inline_command

        self.console.print(f"[{DIM}]Generated:[/{DIM}]")
        print_inline_command(self.console, command)
        self.console.print()
        rc, out, err = await asyncio.to_thread(self.executor.run, command)
        if rc == 0 and out:
            from ..utils.syntax_output import print_command_output

            print_command_output(self.console, out, action="do", success=True)
        elif err:
            from ..utils.syntax_output import print_error_output

            print_error_output(self.console, err, action="do")
        return rc == 0

    # ── Chat handler ──────────────────────────────────────────────────────────

    async def _handle_chat(self, text: str):
        """
        Handles a natural-language input:
          1. Runs decision engine + memory in parallel (shows streaming reasoning)
          2. For PLAN: streams plan-build tokens live under a collapsible header
          3. For CHAT: streams LLM tokens directly to the terminal (no buffering)
        """
        has_memory = (
            hasattr(self.llm_client, "memory_client") and self.llm_client.memory_client
        )

        # ── Step 1: Decision engine + memory in parallel ───────────────────────
        has_memory = (
            hasattr(self.llm_client, "memory_client") and self.llm_client.memory_client
        )
        decision = None
        context_str = ""

        # Print the thinking header (toggleable via /think)
        think_icon = "▼" if self._show_thinking else "▶"
        think_hint = "(/think to toggle)"

        # Immediate memory feedback
        if has_memory:
            self.console.print("[dim]🧠 Querying long-term memory...[/dim]")

        if self._show_thinking:
            self.console.print(
                Text.assemble(
                    (f"{think_icon} ", f"bold {ACCENT}"),
                    ("Thinking", ACCENT),
                    ("  ", ""),
                    (think_hint, DIM),
                )
            )

        async def _run_decision():
            return await asyncio.to_thread(self.decision_engine.analyze, text)

        async def _run_memory():
            if not has_memory:
                return ""
            try:
                return await asyncio.to_thread(
                    self.llm_client.memory_client.query_memory, text
                )
            except Exception:
                return ""

        try:
            # Run decision and memory lookup sequentially to help linter inference
            # or use gather with explicit results if desired.
            # Sequential is safer for the linter here.
            res_decision = await _run_decision()
            res_memory = await _run_memory()

            # Explicitly cast for Pyre
            decision: "Intent" = cast("Intent", res_decision)
            context_str: str = cast(str, res_memory)
        except Exception as e:
            self.console.print(f"[{ERROR}]Decision engine error:[/{ERROR}] {e}")
            return

        # Print reasoning under the thinking header if visible
        if self._show_thinking:
            # decision should be the un-wrapped Intent object
            reasoning = getattr(decision, "reasoning", "") or ""
            if reasoning:
                self.console.print(
                    Text.assemble(("  ", ""), (reasoning, f"dim italic {ACCENT}")),
                    highlight=False,
                )
            self.console.print()  # space after thinking block

        # ── Cached context shortcut ───────────────────────────────────────────
        if decision.action == "SHOW_CACHED":
            # Show the cached response using the same visual style as a live reply
            cached_text = (decision.cached_result or "").strip()
            self.console.print(Rule(style="dim"))
            self.console.print(
                Text.assemble(
                    ("● ", f"bold {ACCENT}"),
                    ("Nexus", f"bold {ACCENT}"),
                    ("  ", ""),
                    ("(cached)", DIM),
                )
            )
            self.console.print()
            self.console.print(Markdown(cached_text))
            self.console.print()
            self.console.print(Rule(style="dim"))
            return

        # Dispatch on intent
        if decision.action == "CLARIFY":
            self.console.print(
                f"[{WARN}]🤔 I'm not sure what you mean. Did you mean:[/{WARN}]"
            )
            if decision.clarification_options:
                for i, opt in enumerate(decision.clarification_options, 1):
                    self.console.print(f"  {i}. {opt}")
            else:
                self.console.print("  1. Something else?")

            self.session_manager.add_turn(
                user_input=text,
                intent_action="CLARIFY",
                intent_reasoning=decision.reasoning,
                result="Clarified intent",
                success=True,
            )
            return

        if decision.action == "COMMAND":
            cmd_str = (
                f"{decision.command} {decision.args}".strip()
                if decision.args
                else decision.command
            )
            if cmd_str and cmd_str.startswith("/"):
                success = await self._handle_command(cmd_str)
                if success:
                    self.session_manager.add_turn(
                        user_input=text,
                        intent_action="COMMAND",
                        intent_reasoning=decision.reasoning,
                        result=f"Command: {cmd_str}",
                        success=True,
                    )
                    return
                if hasattr(self.decision_engine, "invalidate_cache"):
                    self.decision_engine.invalidate_cache()
            decision.action = "PLAN"

        if decision.action == "DIRECT_EXECUTE":
            if not self.llm_client or not self.executor:
                decision.action = "PLAN"
            else:
                from ..ai.command_generator import CommandGenerator
                from ..core.system_detector import SystemDetector

                sys_info = SystemDetector().get_info()
                gen = CommandGenerator(
                    self.llm_client, sys_info, fallback_clients=self.fallback_clients
                )
                with self.console.status(
                    f"[{ACCENT}]Generating command...[/{ACCENT}]", spinner="dots"
                ):
                    try:
                        command = await asyncio.to_thread(gen.generate_command, text)
                    except Exception as e:
                        self.console.print(
                            f"[{ERROR}]Command generation failed:[/{ERROR}] {e}"
                        )
                        decision.action = "PLAN"
                        command = None

                if decision.action == "DIRECT_EXECUTE" and command:
                    from ..utils.syntax_output import print_inline_command

                    self.console.print(f"[{DIM}]Generated:[/{DIM}]")
                    print_inline_command(self.console, command)
                    self.console.print()
                    rc, out, err = await asyncio.to_thread(
                        self.executor.run, command, False, None, None
                    )
                    if rc == 0 and out:
                        from ..utils.syntax_output import print_command_output

                        print_command_output(
                            self.console, out.strip(), action="execute", success=True
                        )
                    elif rc == 0:
                        self.console.print(f"[{SUCCESS}]Done.[/{SUCCESS}]")
                    elif err:
                        from ..utils.syntax_output import print_error_output

                        print_error_output(self.console, err, action="execute")
                    else:
                        self.console.print(
                            f"[{ERROR}]Command failed (RC={rc}).[/{ERROR}]"
                        )

                    self.session_manager.add_turn(
                        user_input=text,
                        intent_action="DIRECT_EXECUTE",
                        intent_reasoning=decision.reasoning,
                        result=out if rc == 0 else (err or f"RC={rc}"),
                        success=rc == 0,
                    )
                    self.last_action_result = out if rc == 0 else err
                    self.last_action_type = "DIRECT_EXECUTE"
                    return

        if decision.action == "PLAN":
            if not self.orchestrator:
                from ..core.orchestrator import Orchestrator

                self.orchestrator = Orchestrator(
                    self.console,
                    self.executor,
                    self.browser_manager,
                    self.llm_client,
                    fallback_clients=self.fallback_clients,
                )
            recent_context = ""
            if self.session_manager:
                recent_history = self.session_manager.get_recent_history(limit=3)
                if recent_history:
                    history_text = "\n".join(
                        [
                            f"Previous user request: {t['user_input']}"
                            for t in recent_history
                        ]
                    )
                    recent_context = f"Context from previous turns:\n{history_text}\n"

            # ── Stream plan tokens live ───────────────────────────────────────
            steps_accumulator: list[str] = []
            if self._show_thinking:
                self.console.print(
                    Text.assemble(
                        ("▼ ", f"bold {ACCENT}"),
                        ("Planning", ACCENT),
                        ("  ", ""),
                        ("building your plan…", DIM),
                    )
                )

                try:
                    found_steps = set()

                    safe_recent = str(recent_context or "")[:500]
                    safe_memory = str(context_str or "")[:1000]

                    if self.orchestrator is None:
                        return

                    # Use local variable for type narrowing
                    orch = self.orchestrator
                    planning_prompt = orch.planner._build_prompt(
                        text, safe_recent + safe_memory
                    )
                    # Add a marker so the LLM starts outputting the REAL JSON array
                    planning_prompt += "\n\nCRITICAL: Start your response with '[' and follow the JSON format exactly."

                    # Consumer function to run in background thread
                    def consume_and_print(
                        client, prompt, accumulator, found_set, console_ref
                    ):
                        import re

                        json_started = False
                        # Use passed arguments to avoid closure type inference issues
                        for token in client.generate_stream(prompt):
                            t_str = str(token)
                            if "[" in t_str:
                                json_started = True

                            if not json_started:
                                continue

                            accumulator.append(t_str)
                            current_text = "".join(accumulator)
                            # Find "description": "..." patterns
                            matches = re.finditer(
                                r'["\']description["\']\s*:\s*["\']([^"\']+)["\']',
                                current_text,
                            )
                            for m in matches:
                                d_desc = m.group(1)
                                if d_desc not in found_set:
                                    console_ref.print(
                                        f"  [dim cyan]→[/dim cyan] [dim]{d_desc}[/dim]"
                                    )
                                    found_set.add(d_desc)

                    # Use to_thread with explicit arguments
                    await asyncio.to_thread(
                        consume_and_print,
                        self.llm_client,
                        planning_prompt,
                        steps_accumulator,
                        found_steps,
                        self.console,
                    )  # type: ignore
                except Exception:
                    pass  # planning stream is best-effort
                self.console.print()

            # ── Execute the plan ──────────────────────────────────────────────
            # To save time, we can parse the steps we just streamed
            # instead of asking the orchestrator to plan from scratch.
            try:
                import json
                from ..core.orchestrator import TaskStep

                full_raw = "".join(steps_accumulator)
                clean_json = full_raw.replace("```json", "").replace("```", "").strip()
                start_idx = clean_json.find("[")
                end_idx = clean_json.rfind("]")
                if start_idx != -1 and end_idx != -1:
                    # Explicit indexing to avoid slice lints
                    json_raw = clean_json[start_idx:]
                    clean_json = json_raw[: end_idx - start_idx + 1]

                plan_data = json.loads(clean_json)
                steps = []
                for i, s_data in enumerate(plan_data, 1):
                    import os as _os

                    step_cwd = s_data.get("cwd")
                    if step_cwd:
                        step_cwd = _os.path.expanduser(str(step_cwd))
                    steps.append(
                        TaskStep(
                            id=i,
                            description=s_data.get("description", ""),
                            action=s_data.get("action", ""),
                            command=s_data.get("command", ""),
                            filename_pattern=s_data.get("filename_pattern"),
                            file_content=s_data.get("file_content"),
                            use_cloud=s_data.get("headless", False),
                            cwd=step_cwd,
                        )
                    )

                if not steps:
                    raise ValueError("No steps in plan")

                orch = self.orchestrator
                if orch:
                    result = await orch.execute_plan(steps, context_str=recent_context)
                else:
                    result = None

                if not result:
                    raise ValueError("Plan execution failed")
            except Exception:
                # Fallback: Let orchestrator do its own (non-streaming) planning
                orch = self.orchestrator
                if orch:
                    result = await orch.execute_plan(text, context_str=recent_context)
                else:
                    self.console.print(
                        f"[{ERROR}]Execution engine error: Orchestrator unavailable.[/{ERROR}]"
                    )
                    return

            # Store result for session
            self.session_manager.add_turn(
                user_input=text,
                intent_action="PLAN",
                intent_reasoning=getattr(decision, "reasoning", "Autonomous Planning"),
                result=result.output,
                success=result.success,
            )
            self.last_action_result = result.output
            self.last_action_type = "PLAN"
            return

        # ── Fact lookup — grounded web search (same pipeline as /search) ─────────
        if decision.action == "SEARCH":
            with self.console.status(
                f"[{ACCENT}]Searching the web…[/{ACCENT}]", spinner="dots"
            ):
                search_text, search_err = await self._grounded_web_search(text)

            if search_text:
                self.console.print(Rule(style="dim"))
                self.console.print(
                    Text.assemble(
                        ("● ", f"bold {ACCENT}"),
                        ("Nexus", f"bold {ACCENT}"),
                        ("  ", ""),
                        ("(web)", DIM),
                    )
                )
                self.console.print()
                self.console.print(Panel(search_text, border_style=SUCCESS))
                self.console.print(Rule(style="dim"))

                if hasattr(self.decision_engine, "store_response"):
                    self.decision_engine.store_response(text, search_text)

                safe_response = (
                    search_text[:500] if len(search_text) > 500 else search_text
                )
                self.session_manager.add_turn(
                    user_input=text,
                    intent_action="SEARCH",
                    intent_reasoning=decision.reasoning,
                    result=safe_response,
                    success=True,
                )
                self.last_action_result = search_text
                self.last_action_type = "SEARCH"
                if (
                    hasattr(self.llm_client, "memory_client")
                    and self.llm_client.memory_client
                ):
                    asyncio.create_task(
                        asyncio.to_thread(
                            self.llm_client.memory_client.add_memory,
                            f"User: {text}\nNexus (web): {search_text}",
                            {"type": "chat_history"},
                        )
                    )
                return

            # No grounded search — explain once, then answer without claiming live web
            if search_err:
                self.console.print(f"[{WARN}]{search_err}[/{WARN}]")
                self.console.print(
                    f"[{DIM}]Answering from the chat model only (no live web).[/{DIM}]\n"
                )

        # ── Pure chat — stream with Rich Live for beautiful rendering ──────────
        if not self.llm_client:
            self.console.print(
                f"[{ERROR}]No AI provider configured. Set an API key in your .env file.[/{ERROR}]"
            )
            return

        final_prompt = text
        if context_str:
            # Mark it so enrich_prompt can skip if it wants
            final_prompt = (
                f"--- MEMORY CONTEXT ---\n{context_str}\n--- END MEMORY ---\n\n{text}"
            )

        self.console.print(Rule(style="dim"))
        self.console.print(
            Text.assemble(("● ", f"bold {ACCENT}"), ("Nexus", f"bold {ACCENT}")),
        )
        self.console.print()

        # ── Chat Generation Loop (with fallback) ─────────────────────────────
        response = ""
        # Try primary, then fallbacks
        clients_to_try = [self.llm_client] + [
            c for c in self.fallback_clients if c != self.llm_client
        ]

        for i, client in enumerate(clients_to_try):
            response_buf: list[str] = []

            # Capture the client in a local var for the closure
            current_client = client

            def _stream_with_live(client_ref, prompt_ref, live_ref) -> list[str]:
                parts: list[str] = []
                for chunk in client_ref.generate_stream(prompt_ref):
                    if not chunk:
                        continue
                    parts.append(str(chunk))
                    live_ref.update(Markdown("".join(parts)))
                return parts

            try:
                with Live(
                    Markdown(""),
                    console=self.console,
                    refresh_per_second=12,
                    vertical_overflow="ellipsis",
                ) as live_inst:
                    response_buf = await asyncio.to_thread(
                        _stream_with_live, current_client, final_prompt, live_inst
                    )  # type: ignore

                response = "".join(response_buf).strip()
                if response:
                    break  # Success!

            except Exception as e:
                # If it's the last client, show the error. Otherwise, try next.
                if i == len(clients_to_try) - 1:
                    self.console.print(f"[{ERROR}]AI error:[/{ERROR}] {e}")
                    return
                else:
                    self.console.print(
                        "[dim yellow]⚠ Primary model failed, trying fallback...[/dim yellow]"
                    )
                    continue

        if not response:
            self.console.print(
                "[dim italic]No response received from any AI model.[/dim italic]"
            )
        self.console.print(Rule(style="dim"))

        # Store response in decision engine cache so the next identical query
        # returns SHOW_CACHED immediately (no LLM call).
        if response and hasattr(self.decision_engine, "store_response"):
            self.decision_engine.store_response(text, response)

        # Store to memory in the background
        if hasattr(self.llm_client, "memory_client") and self.llm_client.memory_client:
            asyncio.create_task(
                asyncio.to_thread(
                    self.llm_client.memory_client.add_memory,
                    f"User: {text}\nNexus: {response}",
                    {"type": "chat_history"},
                )
            )

            # Limit result size to avoid excessive memory usage in history
            safe_response = response or ""
            if len(safe_response) > 500:
                truncated_result = safe_response[0:500]
            else:
                truncated_result = safe_response

            self.session_manager.add_turn(
                user_input=text,
                intent_action="CHAT",
                intent_reasoning=getattr(decision, "reasoning", "Standard Query"),
                result=truncated_result,
                success=True,
            )


# Keep the old class name as an alias so main.py doesn't break
JarvisApp = NexusApp
