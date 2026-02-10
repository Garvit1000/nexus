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
    def __init__(self, llm_client=None, video_manager=None, browser_manager=None, executor=None, app_installer=None, router_client=None, translator=None, multilingual_ui=None, voice_handler=None):
        self.console = Console()
        self.session = PromptSession()
        self.is_running = True
        
        self.llm_client = llm_client
        self.video_manager = video_manager
        self.browser_manager = browser_manager
        self.executor = executor
        self.app_installer = app_installer
        self.translator = translator
        self.multilingual_ui = multilingual_ui
        self.voice_handler = voice_handler
        
        # Session Management - NEW
        from ..core.session_manager import SessionManager
        self.session_manager = SessionManager(max_history=50)
        
        # Decision Engine with session awareness
        self.decision_engine = DecisionEngine(llm_client, router_client, self.session_manager)
        self.orchestrator = None
        
        # Legacy context tracking (kept for backward compatibility)
        self.last_action_result = None
        self.last_action_type = None
        
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

    def record_feedback(self, command: str, success: bool, output: str):
        """Records the result of an action to Supermemory."""
        if self.llm_client and self.llm_client.memory_client:
            status = "Success" if success else "Failure"
            memory_content = f"Action Feedback:\nCommand: {command}\nResult: {status}\nOutput: {output}"
            meta = {
                "type": "feedback",
                "command": command,
                "status": status,
            }
            try:
                self.llm_client.memory_client.add_memory(memory_content, metadata=meta)
                self.console.print(f"[dim]📝 Experience recorded: {status}[/dim]")
            except Exception as e:
                self.console.print(f"[dim red]Failed to record feedback: {e}[/dim red]")

    async def handle_command(self, text: str) -> bool:
        """
        Handle a command.
        
        Returns:
            True if command succeeded, False otherwise
        """
        parts = text.split(" ", 1)
        command = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if command == "/video":
            if not self.video_manager:
                self.console.print("[red]Video Manager is not initialized.[/red]")
                return False
            
            self.console.print(Panel(f"Generating video for: {args}", title="aremotion", border_style="magenta"))
            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, self.video_manager.generate_video, args)
                self.console.print(Panel(str(result), title="Result", border_style="green"))
                self.record_feedback(text, True, str(result)[:200])
                return True
            except Exception as e:
                self.console.print(f"[red]Error:[/red] {e}")
                self.record_feedback(text, False, str(e))
                return False

        elif command == "/browse":
            if not self.browser_manager:
                self.console.print("[red]Browser Manager is not initialized.[/red]")
                return False
            
            self.console.print(Panel(f"Browsing: {args}", title="abrowser", border_style="blue"))
            try:
                 loop = asyncio.get_event_loop()
                 result = await loop.run_in_executor(None, self.browser_manager.run_task, args)
                 self.console.print(Panel(str(result), title="Result", border_style="green"))
                 self.record_feedback(text, True, str(result)[:200])
                 return True
            except Exception as e:
                self.console.print(f"[red]Error:[/red] {e}")
                self.record_feedback(text, False, str(e))
                return False
        
        elif command == "/search":
             if not self.llm_client:
                 self.console.print("[red]LLM Client is not initialized.[/red]")
                 return False
             self.console.print(f"[dim]Searching: {args}[/dim]")
             try:
                 loop = asyncio.get_event_loop()
                 if hasattr(self.llm_client, "search"):
                      result = await loop.run_in_executor(None, self.llm_client.search, args)
                      self.console.print(Panel(result, title="Search Result", border_style="green"))
                      self.record_feedback(text, True, str(result)[:200])
                      return True
                 else:
                      self.console.print("[yellow]Search not supported by current LLM provider.[/yellow]")
                      return False
             except Exception as e:
                 self.console.print(f"[red]Error searching:[/red] {e}")
                 self.record_feedback(text, False, str(e))
                 return False

        elif command == "/install":
             if not self.app_installer:
                  self.console.print("[red]App Installer is not initialized.[/red]")
                  return False
             self.console.print(f"[bold cyan]Installing:[/bold cyan] {args}")
             success = self.app_installer.install(args)
             self.record_feedback(text, success, "Package installed" if success else "Installation failed")
             if success:
                 self.console.print(f"[bold green]Successfully installed {args}![/bold green]")
             else:
                 self.console.print(f"[bold red]Failed to install {args}.[/bold red]")
             return success

        elif command == "/remove":
             if not self.app_installer:
                  self.console.print("[red]App Installer is not initialized.[/red]")
                  return False
             self.console.print(f"[bold cyan]Removing:[/bold cyan] {args}")
             success = self.app_installer.remove(args)
             self.record_feedback(text, success, "Package removed" if success else "Removal failed")
             if success:
                 self.console.print(f"[bold green]Successfully removed {args}![/bold green]")
             else:
                 self.console.print(f"[bold red]Failed to remove {args}.[/bold red]")
             return success

        elif command == "/update":
             if not self.app_installer:
                  self.console.print("[red]App Installer is not initialized.[/red]")
                  return False
             self.console.print("[bold cyan]Updating System...[/bold cyan]")
             success = self.app_installer.update_system()
             self.record_feedback(text, success, "System updated" if success else "Update failed")
             if success:
                 self.console.print("[bold green]System Updated![/bold green]")
             else:
                 self.console.print("[bold red]Update Failed.[/bold red]")
             return success

        elif command == "/help":
             help_text = """
             [bold cyan]Available Commands:[/bold cyan]
             - [cyan]/video <prompt>[/cyan]: Generate a video
             - [cyan]/browse <task>[/cyan]: Perform a browser task
             - [cyan]/search <query>[/cyan]: Search Google
             - [cyan]/install <pkg>[/cyan]: Install a package
             - [cyan]/remove <pkg>[/cyan]: Remove a package
             - [cyan]/update[/cyan]: Update system
             - [cyan]/translate <text> [--to lang][/cyan]: Translate text
             - [cyan]/speak <text> --lang <code>[/cyan]: Text to speech
             - [cyan]/voice --lang <code>[/cyan]: Voice command input
             - [cyan]/lang <code>[/cyan]: Set preferred language
             - [cyan]/langs[/cyan]: Show supported languages
             - [cyan]/exit[/cyan]: Exit Jarvis
             """
             self.console.print(Panel(help_text, title="Help", border_style="white"))
             return True
        
        elif command == "/translate":
             if not self.translator:
                  self.console.print("[red]Translator is not initialized.[/red]")
                  return False
             
             # Parse args: text and optional --to flag
             parts = args.split("--to")
             text = parts[0].strip()
             target_lang = parts[1].strip() if len(parts) > 1 else "en"
             
             result = self.translator.detect_and_translate(text, target_lang=target_lang)
             self.multilingual_ui.print_translation(result, show_original=True)
             return True
        
        elif command == "/speak":
             if not self.translator:
                  self.console.print("[red]Translator is not initialized.[/red]")
                  return False
             
             # Parse: /speak <text> --lang <code>
             parts = args.split("--lang")
             text = parts[0].strip()
             lang = parts[1].strip() if len(parts) > 1 else "hi-IN"
             
             self.multilingual_ui.print_voice_status("Generating speech...", lang)
             output_path = "/tmp/nexus_speech.mp3"
             success = self.translator.text_to_speech(text, output_path, language=lang)
             
             if success:
                  self.multilingual_ui.print_voice_status("Complete!", lang)
                  self.console.print(f"[green]✓ Audio saved: {output_path}[/green]")
                  
                  # Try to play MP3
                  try:
                       import subprocess
                       try:
                           subprocess.run(["mpg123", "-q", output_path], check=True, stderr=subprocess.DEVNULL)
                       except FileNotFoundError:
                           subprocess.run(["ffplay", "-nodisp", "-autoexit", output_path],
                                        check=True, stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
                  except:
                       pass
             else:
                  self.console.print("[red]Failed to generate speech[/red]")
             return success
        
        elif command == "/voice":
             if not self.voice_handler:
                  self.console.print("[red]Voice handler is not initialized.[/red]")
                  return False
             
             # Parse: /voice --lang <code> --duration <sec>
             import re
             lang_match = re.search(r'--lang\s+(\S+)', args)
             dur_match = re.search(r'--duration\s+(\d+)', args)
             
             lang = lang_match.group(1) if lang_match else "hi-IN"
             duration = int(dur_match.group(1)) if dur_match else 5
             
             self.multilingual_ui.print_voice_status("Recording...", lang)
             audio_path = self.voice_handler.record_audio(duration=duration)
             
             if not audio_path:
                  self.console.print("[red]Recording failed[/red]")
                  return False
             
             self.multilingual_ui.print_voice_status("Processing...", lang)
             command_text = self.voice_handler.process_voice_command(audio_path, language=lang)
             
             if command_text:
                  self.multilingual_ui.print_voice_status("Success!", lang)
                  self.console.print(Panel(
                       f"[cyan]Recognized:[/cyan]\n{command_text}",
                       title="Voice Command",
                       border_style="green"
                  ))
                  # Process as chat
                  loop = asyncio.get_event_loop()
                  loop.create_task(self.handle_chat(command_text))
                  return True
             else:
                  self.console.print("[red]Failed to recognize speech[/red]")
                  return False
        
        elif command == "/lang":
             if not self.translator:
                  self.console.print("[red]Translator is not initialized.[/red]")
                  return False
             
             lang_code = args.strip()
             self.translator.set_user_language(lang_code)
             self.translator.enable_auto_translate(lang_code != "en")
             
             self.console.print(f"[bold green]✓ Language set to:[/bold green] {lang_code}")
             return True
        
        elif command == "/langs":
             if not self.translator:
                  self.console.print("[red]Translator is not initialized.[/red]")
                  return False
             
             languages = self.translator.get_supported_languages()
             self.multilingual_ui.print_language_selector(languages, self.translator.user_language)
             return True

        else:
            self.console.print(f"[red]Unknown command: {command}[/red]")
            return False

    async def handle_chat(self, text: str):
        # --- Multilingual Input Processing ---
        original_text = text
        
        # If translator is available and enabled, detect and translate to English if needed
        if self.translator and self.translator.enabled:
            try:
                detected_lang = self.translator.client.detect_language(text)
                
                # Show detected language only if it's not English
                if detected_lang and detected_lang != "en":
                    self.multilingual_ui.print_language_detection(detected_lang)
                    
                    # Translate to English for command processing
                    text = self.translator.translate_to_english(text)
                    
                    if text != original_text:
                        self.console.print(f"[dim cyan]Translated input: {text}[/dim cyan]")
            except Exception as e:
                # Silent fallback - continue with original text
                import logging
                logging.debug(f"Translation skipped: {e}")
        
        # --- Intelligent Decision Engine (with session awareness) ---
        decision = self.decision_engine.analyze(text)
        
        # --- Handle SHOW_CACHED Intent ---
        if decision.action == "SHOW_CACHED":
            self.console.print(f"[dim]{decision.reasoning}[/dim]")
            self.console.print(Panel(
                decision.cached_result.strip(),
                title="[bold cyan]📋 Cached Results[/bold cyan]",
                border_style="cyan",
                padding=(1, 2)
            ))
            return
        
        # Log decision reasoning
        self.console.print(f"[dim italic]Intent: {decision.reasoning} (Confidence: {decision.confidence:.2f})[/dim italic]")
        
        if decision.action == "COMMAND":
            cmd_str = f"{decision.command} {decision.args}" if decision.args else decision.command
            success = await self.handle_command(cmd_str)
            # Record turn
            self.session_manager.add_turn(
                user_input=text,
                intent_action="COMMAND",
                intent_reasoning=decision.reasoning,
                result=f"Command executed: {cmd_str}",
                success=success
            )
            return

        elif decision.action == "PLAN":
            # Lazy load orchestrator
            orchestrator = self.orchestrator
            if not orchestrator:
                 from ..core.orchestrator import Orchestrator
                 orchestrator = Orchestrator(self.console, self.executor, self.browser_manager, self.llm_client)
                 self.orchestrator = orchestrator
            
            result = await orchestrator.execute_plan(text)
            
            # Record turn with full result
            self.session_manager.add_turn(
                user_input=text,
                intent_action="PLAN",
                intent_reasoning=decision.reasoning,
                result=result,
                success=result is not None
            )
            
            # Legacy cache for backward compatibility
            self.last_action_result = result
            self.last_action_type = "PLAN"
            return

        if not self.llm_client:
            self.console.print("[red]LLM Client is not initialized.[/red]")
            return

        # --- Memory Retrieval (RAG) ---
        context_str = ""
        
        if hasattr(self.llm_client, "memory_client") and self.llm_client.memory_client:
            with self.console.status("[dim]🧠 Recalling...[/dim]", spinner="dots"):
                try:
                    # Run in thread to allow UI to breathe
                    context_str = await asyncio.to_thread(
                        self.llm_client.memory_client.query_memory, 
                        text
                    )
                except Exception as e:
                    self.console.print(f"[dim red]Memory retrieval failed: {e}[/dim red]")

        # Enrich Prompt
        final_prompt = text
        if context_str:
             self.console.print(f"[dim]🧠 Recalled relevant context.[/dim]")
             final_prompt = f"Context from previous conversations:\n{context_str}\n\nUser: {text}"

        # Show a "Thinking..." spinner
        with self.console.status("[bold cyan]Nexus is thinking...[/bold cyan]", spinner="dots"):
            try:
                response = await asyncio.to_thread(self.llm_client.generate_response, final_prompt)
            except Exception as e:
                self.console.print(f"[red]Error during chat:[/red] {e}")
                return

        # --- Memory Storage (Learning) ---
        if hasattr(self.llm_client, "memory_client") and self.llm_client.memory_client:
             memory_content = f"User: {text}\nNexus: {response}"
             # Save in background using asyncio.to_thread (returns coroutine)
             asyncio.create_task(
                 asyncio.to_thread(
                     self.llm_client.memory_client.add_memory,
                     memory_content,
                     {"type": "chat_history"}
                 )
             )
        
        # Record turn
        self.session_manager.add_turn(
            user_input=text,
            intent_action="CHAT",
            intent_reasoning=decision.reasoning,
            result=response[:500],  # Truncate long responses
            success=True
        )

        # --- Multilingual Response Support ---
        if self.translator and self.translator.auto_translate and self.translator.user_language != "en":
            # Translate response to user's language
            translated = self.translator.translate_to_user_language(response)
            
            # Show both or just translated based on preference
            self.multilingual_ui.print_multilingual_response(
                english_text=response,
                translated_text=translated,
                target_lang=self.translator.user_language,
                show_both=False  # Show only translated version
            )
        else:
            # Print the response nicely
            self.console.print(Markdown(response), style="white")

if __name__ == "__main__":
    # Mock run
    app = JarvisApp()
    asyncio.run(app.run_repl())
