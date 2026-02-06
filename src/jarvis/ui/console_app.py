import asyncio
import sys
import shutil
from typing import Optional, List
from rich.console import Console, Group
from rich.layout import Layout
from rich.panel import Panel
from rich.text import Text
from rich.markdown import Markdown
from rich.align import Align
from rich import box
import pyfiglet
from prompt_toolkit import PromptSession, HTML
from prompt_toolkit.styles import Style as PromptStyle
from ..ai.decision_engine import DecisionEngine

class JarvisApp:
    def __init__(self, llm_client=None, video_manager=None, browser_manager=None, executor=None, app_installer=None, router_client=None):
        self.console = Console()
        self.session = PromptSession()
        self.is_running = True
        
        self.llm_client = llm_client
        self.video_manager = video_manager
        self.browser_manager = browser_manager
        self.executor = executor
        self.app_installer = app_installer
        self.decision_engine = DecisionEngine(llm_client, router_client)
        
        # Style for the prompt
        self.style = PromptStyle.from_dict({
            'prompt': '#00ff88 bold',  # blue prompt
            'input': '#ffffff',
        })

    def print_header(self):
        """Prints the constant header."""
        self.console.clear()
        
        # ASCII Art Logo
        title_font = pyfiglet.figlet_format("NEXUS", font="slant")
        title_text = Text(title_font, style="bold blue")
        
        # Metadata
        meta_text = Text()
        meta_text.append("v2.1.0 · Your AI Agent · API Usage Billing\n", style="dim white")
        meta_text.append("~/Nexus agent", style="dim blue")

        # Combine into a header panel
        header_content = Group(Align.center(title_text), Align.center(meta_text))
        
        # Claude Code style header is often a box at the top
        header_panel = Panel(
            header_content,
            border_style="blue",
            box=box.ROUNDED,
            padding=(1, 2),
            title="Welcome back User!",
            title_align="center"
        )
        self.console.print(header_panel)
        self.console.print(Text("Tips: Type /help for commands or just chat.", style="dim"), justify="center")
        self.console.print() # Spacer

    async def run_repl(self):
        """
        Runs the main loop. 
        Unlike the previous version, strictly linear log to avoid input-box issues,
        but with a 'clear' effect to simulate a persistent app if desired.
        
        User requested 'Constant' interface. The best way to achieve 'Input Box' 
        feel with prompt_toolkit is to clear and reprint history, 
        and ensure the prompt stays at the bottom.
        """
        # Initial Header
        self.print_header()
        
        history = [] # List of (Role, Content) tuple
        
        while self.is_running:
            # We want the input to feel like it's in a box?
            # Creating a true input box in TUI is hard without full-screen lib.
            # Best approximation: Line logic.
            
            try:
                # Custom prompt imitation
                # We can print a "box top" before the prompt?
                # No, that breaks when user types.
                
                # Claude Code look:
                # > Input
                
                user_input = await self.session.prompt_async(
                    HTML("<b><style color='#ff8800'>></style></b> "),
                    style=self.style
                )
                
                if not user_input:
                    continue
                    
                if user_input.strip().lower() in ["/exit", "/quit"]:
                    self.console.print("[yellow]Shutting down...[/yellow]")
                    self.is_running = False
                    break
                    
                # Process input
                await self.handle_input(user_input)
                
            except (KeyboardInterrupt, EOFError):
                 self.is_running = False

    async def handle_input(self, text: str):
        # Print User Message immediately (so it stays on screen)
        # In a real REPL, the input stays. We just need to maybe style it?
        # prompt_toolkit leaves the input there.
        # We can add a separator or blank line.
        
        # self.console.print() # Spacer
        
        if text.startswith("/"):
            await self.handle_command(text)
        else:
            await self.handle_chat(text)
            
        self.console.print() # Spacer after response

    async def handle_command(self, text: str):
        parts = text.split(" ", 1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if command == "/video":
            if not self.video_manager:
                self.console.print("[red]Video Manager is not initialized.[/red]")
                return
            
            self.console.print(Panel(f"Generating video for: {args}", title="aremotion", border_style="magenta"))
            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, self.video_manager.generate_video, args)
                self.console.print(Panel(str(result), title="Result", border_style="green"))
            except Exception as e:
                self.console.print(f"[red]Error:[/red] {e}")

        elif command == "/browse":
            if not self.browser_manager:
                self.console.print("[red]Browser Manager is not initialized.[/red]")
                return
            
            self.console.print(Panel(f"Browsing: {args}", title="abrowser", border_style="blue"))
            try:
                 loop = asyncio.get_event_loop()
                 result = await loop.run_in_executor(None, self.browser_manager.run_task, args)
                 self.console.print(Panel(str(result), title="Result", border_style="green"))
            except Exception as e:
                self.console.print(f"[red]Error:[/red] {e}")
        
        elif command == "/search":
             if not self.llm_client:
                 self.console.print("[red]LLM Client is not initialized.[/red]")
                 return
             self.console.print(f"[dim]Searching: {args}[/dim]")
             try:
                 loop = asyncio.get_event_loop()
                 if hasattr(self.llm_client, "search"):
                      result = await loop.run_in_executor(None, self.llm_client.search, args)
                      self.console.print(Panel(result, title="Search Result", border_style="green"))
                 else:
                      self.console.print("[yellow]Search not supported by current LLM provider.[/yellow]")
             except Exception as e:
                 self.console.print(f"[red]Error searching:[/red] {e}")

        elif command == "/install":
             if not self.app_installer:
                  self.console.print("[red]App Installer is not initialized.[/red]")
                  return
             self.console.print(f"[bold cyan]Installing:[/bold cyan] {args}")
             success = self.app_installer.install(args)
             if success:
                 self.console.print(f"[bold green]Successfully installed {args}![/bold green]")
             else:
                 self.console.print(f"[bold red]Failed to install {args}.[/bold red]")

        elif command == "/remove":
             if not self.app_installer:
                  self.console.print("[red]App Installer is not initialized.[/red]")
                  return
             self.console.print(f"[bold cyan]Removing:[/bold cyan] {args}")
             success = self.app_installer.remove(args)
             if success:
                 self.console.print(f"[bold green]Successfully removed {args}![/bold green]")
             else:
                 self.console.print(f"[bold red]Failed to remove {args}.[/bold red]")

        elif command == "/update":
             if not self.app_installer:
                  self.console.print("[red]App Installer is not initialized.[/red]")
                  return
             self.console.print("[bold cyan]Updating System...[/bold cyan]")
             success = self.app_installer.update_system()
             if success:
                 self.console.print("[bold green]System Updated![/bold green]")
             else:
                 self.console.print("[bold red]Update Failed.[/bold red]")

        elif command == "/help":
             help_text = """
             [bold cyan]Available Commands:[/bold cyan]
             - [cyan]/video <prompt>[/cyan]: Generate a video
             - [cyan]/browse <task>[/cyan]: Perform a browser task
             - [cyan]/search <query>[/cyan]: Search Google
             - [cyan]/install <pkg>[/cyan]: Install a package
             - [cyan]/remove <pkg>[/cyan]: Remove a package
             - [cyan]/update[/cyan]: Update system
             - [cyan]/exit[/cyan]: Exit Jarvis
             """
             self.console.print(Panel(help_text, title="Help", border_style="white"))

        else:
            self.console.print(f"[red]Unknown command: {command}[/red]")

    async def handle_chat(self, text: str):
        # --- Intelligent Decision Engine ---
        decision = self.decision_engine.analyze(text)
        
        if decision.action == "COMMAND":
            self.console.print(f"[dim italic]Detected intent: {decision.reasoning}[/dim italic]")
            cmd_str = f"{decision.command} {decision.args}" if decision.args else decision.command
            await self.handle_command(cmd_str)
            return

        if not self.llm_client:
            self.console.print("[red]LLM Client is not initialized.[/red]")
            return

        # Show a "Thinking..." spinner
        with self.console.status("[bold cyan]Nexus is thinking...[/bold cyan]", spinner="dots"):
            try:
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, self.llm_client.generate_response, text)
            except Exception as e:
                self.console.print(f"[red]Error during chat:[/red] {e}")
                return

        # Print the response nicely
        self.console.print(Markdown(response), style="white")

if __name__ == "__main__":
    # Mock run
    app = JarvisApp()
    asyncio.run(app.run_repl())
