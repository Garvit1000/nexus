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
import sys
from typing import Optional

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text
from rich import box
import pyfiglet
from prompt_toolkit import PromptSession, HTML
from prompt_toolkit.styles import Style as PromptStyle
from prompt_toolkit.history import InMemoryHistory

from ..ai.decision_engine import DecisionEngine


# ── Colour palette ────────────────────────────────────────────────────────────
ACCENT   = "cyan"
DIM      = "dim"
SUCCESS  = "green"
ERROR    = "red"
WARN     = "yellow"
NEUTRAL  = "white"

# ── Prompt style ──────────────────────────────────────────────────────────────
_PROMPT_STYLE = PromptStyle.from_dict({
    "prompt": "#00d7ff bold",   # bright cyan
    "": "#ffffff",              # input text
})


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

        self.decision_engine = DecisionEngine(llm_client, router_client, self.session_manager)
        self.orchestrator = None

        self.last_action_result = None
        self.last_action_type = None

    # ── Header ────────────────────────────────────────────────────────────────

    def _print_header(self):
        """Print the Nexus splash header once on startup."""
        self.console.clear()

        logo = pyfiglet.figlet_format("NEXUS", font="slant")
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
            f"  [dim]Type your request or [cyan]/help[/cyan] for commands  ·  "
            f"[cyan]/exit[/cyan] to quit[/dim]\n"
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
        self.console.print()   # breathing room

        if text.startswith("/"):
            await self._handle_command(text)
        else:
            await self._handle_chat(text)

        self.console.print()   # breathing room after response

    # ── Slash commands ────────────────────────────────────────────────────────

    async def _handle_command(self, text: str) -> bool:
        parts   = text.split(" ", 1)
        command = parts[0].lower()
        args    = parts[1].strip() if len(parts) > 1 else ""

        if command == "/help":
            self._show_help()
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

        self.console.print(f"[{ERROR}]Unknown command: {command}[/{ERROR}]  Type [cyan]/help[/cyan] for a list.")
        return False

    def _show_help(self):
        rows = [
            ("  /browse [i]task[/i]",   "Perform a browser-based task"),
            ("  /search [i]query[/i]",  "Answer a question via web search"),
            ("  /install [i]pkg[/i]",   "Install a system package"),
            ("  /remove [i]pkg[/i]",    "Remove a system package"),
            ("  /update",               "Update all system packages"),
            ("  /status",               "Show active AI provider and mode"),
            ("  /help",                 "Show this help"),
            ("  /exit",                 "Quit Nexus"),
        ]
        lines = "\n".join(f"[cyan]{cmd}[/cyan]  [{DIM}]{desc}[/{DIM}]" for cmd, desc in rows)
        self.console.print(Panel(lines, title="Commands", border_style=ACCENT, padding=(1, 2)))

    def _show_status(self):
        provider = type(self.llm_client).__name__ if self.llm_client else "None"
        browser  = "Ready" if self.browser_manager else "Not configured"
        executor_mode = "Dry-run" if (self.executor and getattr(self.executor, "dry_run", False)) else "Live"
        lines = (
            f"[{DIM}]AI provider :[/{DIM}]   [cyan]{provider}[/cyan]\n"
            f"[{DIM}]Browser     :[/{DIM}]   [{WARN if browser == 'Not configured' else SUCCESS}]{browser}[/{WARN if browser == 'Not configured' else SUCCESS}]\n"
            f"[{DIM}]Executor    :[/{DIM}]   [cyan]{executor_mode}[/cyan]"
        )
        self.console.print(Panel(lines, title="Status", border_style=ACCENT, padding=(0, 2)))

    async def _cmd_browse(self, args: str) -> bool:
        if not args:
            self.console.print(f"[{WARN}]Usage: /browse [i]task description[/i][/{WARN}]")
            return False
        if not self.browser_manager:
            self.console.print(f"[{ERROR}]Browser is not configured. Install [cyan]nexus[browser][/cyan] and ensure an API key is set.[/{ERROR}]")
            return False
        with self.console.status(f"[{ACCENT}]Browsing…[/{ACCENT}]", spinner="dots"):
            try:
                result = await asyncio.get_event_loop().run_in_executor(
                    None, self.browser_manager.run_task, args
                )
            except Exception as e:
                self.console.print(f"[{ERROR}]Browser error:[/{ERROR}] {e}")
                return False
        self.console.print(Panel(str(result), title="Browser Result", border_style=SUCCESS))
        return True

    async def _cmd_search(self, args: str) -> bool:
        if not args:
            self.console.print(f"[{WARN}]Usage: /search [i]query[/i][/{WARN}]")
            return False
        if not self.llm_client:
            self.console.print(f"[{ERROR}]No AI provider is configured.[/{ERROR}]")
            return False
        if not hasattr(self.llm_client, "search"):
            self.console.print(f"[{WARN}]Search is not supported by the current AI provider.[/{WARN}]")
            return False
        with self.console.status(f"[{ACCENT}]Searching…[/{ACCENT}]", spinner="dots"):
            try:
                result = await asyncio.to_thread(self.llm_client.search, args)
            except Exception as e:
                self.console.print(f"[{ERROR}]Search error:[/{ERROR}] {e}")
                return False
        self.console.print(Panel(result, title="Search Result", border_style=SUCCESS))
        return True

    def _cmd_package(self, action: str, pkg: str) -> bool:
        if not pkg:
            self.console.print(f"[{WARN}]Usage: /{action} [i]package[/i][/{WARN}]")
            return False
        if not self.app_installer:
            self.console.print(f"[{ERROR}]Package installer is not available.[/{ERROR}]")
            return False
        label = "Installing" if action == "install" else "Removing"
        with self.console.status(f"[{ACCENT}]{label} [bold]{pkg}[/bold]…[/{ACCENT}]", spinner="dots"):
            fn = self.app_installer.install if action == "install" else self.app_installer.remove
            success = fn(pkg)
        if success:
            past = "installed" if action == "install" else "removed"
            self.console.print(f"[{SUCCESS}]✓[/{SUCCESS}] [bold]{pkg}[/bold] {past} successfully.")
        else:
            self.console.print(f"[{ERROR}]✗[/{ERROR}] Failed to {action} [bold]{pkg}[/bold].")
        return success

    def _cmd_update(self) -> bool:
        if not self.app_installer:
            self.console.print(f"[{ERROR}]Package installer is not available.[/{ERROR}]")
            return False
        with self.console.status(f"[{ACCENT}]Updating system packages…[/{ACCENT}]", spinner="dots"):
            success = self.app_installer.update_system()
        if success:
            self.console.print(f"[{SUCCESS}]✓[/{SUCCESS}] System updated.")
        else:
            self.console.print(f"[{ERROR}]✗[/{ERROR}] System update failed.")
        return success

    # ── Chat handler ──────────────────────────────────────────────────────────

    async def _handle_chat(self, text: str):
        # ── Run decision engine + memory query in PARALLEL ───────────────────
        # Both are network/CPU bound; running concurrently saves 300-600ms on cache-miss.
        has_memory = hasattr(self.llm_client, "memory_client") and self.llm_client.memory_client

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

        decision, context_str = await asyncio.gather(_run_decision(), _run_memory())

        # ── Cached context shortcut ───────────────────────────────────────────
        if decision.action == "SHOW_CACHED":
            self.console.print(Panel(
                (decision.cached_result or "").strip(),
                title="[bold]Cached Result[/bold]",
                border_style=ACCENT,
            ))
            return

        # ── Dispatch on intent ────────────────────────────────────────────────
        if decision.action == "CLARIFY":
            self.console.print(f"[{WARN}]🤔 I'm not sure what you mean. Did you mean:[/{WARN}]")
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
            cmd_str = f"{decision.command} {decision.args}".strip() if decision.args else decision.command
            # Only dispatch as a Nexus slash command if it starts with '/'
            # e.g. /install, /update, /browse — those are Nexus internals.
            # Shell commands decided by the LLM (e.g. 'docker run ...') are NOT
            # Nexus slash commands — fall through to PLAN so the executor runs them.
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
                # If slash command itself failed (unknown command), fall through to PLAN
                # and also invalidate the cache so next attempt re-routes correctly
                if hasattr(self.decision_engine, 'invalidate_cache'):
                    self.decision_engine.invalidate_cache()
            # Non-slash command or failed slash → treat as PLAN so the executor handles it
            decision.action = "PLAN"

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
            result = await self.orchestrator.execute_plan(text)
            self.session_manager.add_turn(
                user_input=text,
                intent_action="PLAN",
                intent_reasoning=decision.reasoning,
                result=result,
                success=result is not None,
            )
            self.last_action_result = result
            self.last_action_type   = "PLAN"
            return

        # ── Pure chat ─────────────────────────────────────────────────────────
        if not self.llm_client:
            self.console.print(f"[{ERROR}]No AI provider configured. Set an API key in your .env file.[/{ERROR}]")
            return

        # context_str already fetched in parallel with the decision above
        final_prompt = text
        if context_str:
            final_prompt = f"Context from previous conversations:\n{context_str}\n\nUser: {text}"

        with self.console.status(f"[{ACCENT}]Thinking…[/{ACCENT}]", spinner="dots"):
            try:
                # Check if streaming is supported (all real clients implement it)
                # Run in thread since generate_stream() is a sync generator
                chunks = await asyncio.to_thread(
                    lambda: list(self.llm_client.generate_stream(final_prompt))
                )
            except Exception as e:
                self.console.print(f"[{ERROR}]AI error:[/{ERROR}] {e}")
                return

        # Store to memory in the background — no user-visible output
        response = "".join(chunks)

        # Store to memory in the background — no user-visible output
        if hasattr(self.llm_client, "memory_client") and self.llm_client.memory_client:
            asyncio.create_task(asyncio.to_thread(
                self.llm_client.memory_client.add_memory,
                f"User: {text}\nNexus: {response}",
                {"type": "chat_history"},
            ))

        self.session_manager.add_turn(
            user_input=text,
            intent_action="CHAT",
            intent_reasoning=decision.reasoning,
            result=response[:500],
            success=True,
        )

        self.console.print(Rule(style="dim"))
        self.console.print(Markdown(response), style=NEUTRAL)


# Keep the old class name as an alias so main.py doesn't break
JarvisApp = NexusApp
