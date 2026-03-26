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

    async def _grounded_web_search(self, query: str) -> tuple[Optional[str], Optional[str]]:
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
