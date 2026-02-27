import json
import asyncio
from typing import List, Dict, Optional, Union, Any
from dataclasses import dataclass
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.status import Status
from ..utils.io import confirm_action
from .security import SafetyCheck

@dataclass
class TaskStep:
    id: int
    description: str
    action: str # BROWSER, TERMINAL, LLM
    command: str
    filename_pattern: Optional[str] = None # For Smart Resume (checking existing downloads)
    use_cloud: bool = False # Headless/Cloud execution
    status: str = "pending" # pending, running, success, failed
    output: str = ""

class Planner:
    def __init__(self, llm_client, fallback_clients=None):
        self.llm_clients = [llm_client]
        if fallback_clients:
            for client in fallback_clients:
                if client not in self.llm_clients:
                    self.llm_clients.append(client)

    def create_plan(self, request: str) -> List[TaskStep]:
        # --- RAG: Retrieve Proven Plans ---
        proven_context = ""
        primary_client = self.llm_clients[0]
        if hasattr(primary_client, "memory_client") and primary_client.memory_client:
            # Query memory explicitly for plans
            rag_hits = primary_client.memory_client.query_memory(f"planned task {request}", limit=1)
            if rag_hits:
                print(f"[bold green]🧠 Recalled proven plan from memory![/bold green]")
                proven_context = f"\n### PROVEN PAST PLAN (ADAPT THIS)\n{rag_hits}\n"

        prompt = f"""
You are the Tactical Planner for Nexus.
You are an expert system architect and operations manager.

### CORE OBJECTIVE
Break down the user's request into a bulletproof, idempotent execution plan.

### MEMORY CONTEXT
{proven_context}

### REQUEST
"{request}"

### AVAILABLE ACTIONS
1. **BROWSER**: For web data retrieval, navigation, or downloads
   - Set `"headless": true` for data scraping (faster, no GUI)
   - Set `"headless": false` for interactive browsing or when user wants to "see" something
   - Optional: `"filename_pattern": "*.pdf"` (ONLY if downloading a file)

2. **TERMINAL**: For shell commands (system operations, file manipulation)

3. **CHECK**: For verifying if a SPECIFIC FILE or STATE exists
   - ONLY use when task is about checking if something already exists locally
   - Example: "Check if installer already downloaded" → CHECK makes sense
   - DON'T use for: web data queries, news requests, or general information retrieval

### PLANNING INTELLIGENCE

**UNDERSTAND THE REQUEST FIRST:**
- What is the user's PRIMARY goal?
- Do they want to RETRIEVE data, DOWNLOAD a file, CHECK system state, or DO something?

**TASK TYPE RECOGNITION:**
1. **Data Retrieval Tasks** (news, posts, weather, trending topics):
   - NO CHECK step needed (data changes constantly)
   - Direct BROWSER action with headless=true
   - Example: "show me latest news" → Just fetch and display

2. **Download Tasks** (download file, get installer):
   - CHECK if file pattern provided and resumability matters
   - BROWSER with filename_pattern for download
   - Optional TERMINAL for post-processing

3. **System Tasks** (install, update, check disk):
   - TERMINAL commands directly
   - CHECK only if verifying existing installation before reinstalling

4. **Interactive Tasks** (open website):
   - BROWSER with headless=false
   - NO CHECK step

### CRITICAL RULES

1. **DON'T OVER-ENGINEER**:
   - User asks "show me news" → Just fetch the news, don't check if news exists locally (makes no sense!)
   - User asks "get weather" → Just get weather, don't check cache
   
2. **CHECK Step Guidelines**:
   - ✅ USE CHECK: "Download VSCode installer" (check ~/Downloads for existing .deb file)
   - ❌ DON'T CHECK: "Show me trending news" (news changes, no local check makes sense)
   - ❌ DON'T CHECK: "Get weather in Delhi" (weather is live data)
   - ❌ DON'T CHECK: "Top 10 posts" (dynamic web content)

3. **Headless Decision**:
   - Data retrieval (news, posts, weather) → headless: true
   - User wants to "watch", "see", "open" → headless: false

4. **Minimal Steps**:
   - If one BROWSER action fulfills the request → Use ONE step
   - Don't add verification unless explicitly needed

### EXAMPLES (LEARN FROM THESE)

Request: "show me latest news in delhi top 10"
Plan:
[
  {{
    "description": "Fetch top 10 latest news for Delhi",
    "action": "BROWSER",
    "command": "Search for latest news in Delhi and extract top 10 headlines with summaries",
    "headless": true
  }}
]
Reasoning: Simple data retrieval. NO CHECK needed (news is dynamic). Headless for speed.

Request: "download latest VSCode installer"
Plan:
[
  {{
    "description": "Check if VSCode installer already exists",
    "action": "CHECK",
    "command": "test -f ~/Downloads/code*.deb && echo 'exists' || exit 1"
  }},
  {{
    "description": "Download VSCode .deb installer",
    "action": "BROWSER",
    "command": "Navigate to VSCode download page and download the latest Linux .deb installer",
    "filename_pattern": "code*.deb",
    "headless": true
  }}
]
Reasoning: Download task. CHECK makes sense to avoid re-downloading. Has filename_pattern.

Request: "show me top 10 hacker news posts"
Plan:
[
  {{
    "description": "Fetch top 10 posts from Hacker News",
    "action": "BROWSER",
    "command": "Go to news.ycombinator.com and extract the top 10 post titles and links",
    "headless": true
  }}
]
Reasoning: Web scraping. NO CHECK (HN posts change frequently). Headless for efficiency.

Request: "open youtube and play lofi music"
Plan:
[
  {{
    "description": "Open YouTube and play lofi music",
    "action": "BROWSER",
    "command": "Navigate to youtube.com, search for 'lofi music', and play the first result",
    "headless": false
  }}
]
Reasoning: Interactive task (user wants to see/hear). No headless. No CHECK.

OUTPUT FORMAT (JSON ONLY):
[
  {{
    "description": "Clear description of this step",
    "action": "BROWSER" | "TERMINAL" | "CHECK",
    "command": "Specific command or instruction",
    "filename_pattern": "optional_pattern_for_downloads",
    "headless": true | false
  }}
]
"""
        last_error = None
        for client in self.llm_clients:
            model_name = getattr(client, "model_name", getattr(client, "model", "Unknown Model"))
            print(f"[dim]🧠 Planner Thinking with: {model_name}[/dim]")
            try:
                response = client.generate_response(prompt).strip()
                # Clean generic markdown
                clean_response = response.replace("```json", "").replace("```", "").strip()
                plan_data = json.loads(clean_response)
                
                steps = []
                for i, step_data in enumerate(plan_data, 1):
                    steps.append(TaskStep(
                        id=i,
                        description=step_data.get("description", ""),
                        action=step_data.get("action", ""),
                        command=step_data.get("command", ""),
                        filename_pattern=step_data.get("filename_pattern"),
                        use_cloud=step_data.get("headless", False)
                    ))
                return steps
            except Exception as e:
                last_error = e
                print(f"[dim yellow]⚠️ Planner {model_name} failed: {e}. Trying fallback...[/dim yellow]")
                continue
                
        print(f"[bold red]Planning failed across all available AI clients. Last error: {last_error}[/bold red]")
        return []

class Orchestrator:
    def __init__(self, console: Console, executor, browser_manager, llm_client, fallback_clients=None):
        self.console = console
        self.executor = executor
        self.browser_manager = browser_manager
        self.llm_client = llm_client
        self.planner = Planner(llm_client, fallback_clients=fallback_clients)

    def generate_view(self, steps: List[TaskStep]) -> Table:
        table = Table(title="Nexus Execution Plan", expand=True, box=None)
        table.add_column("ID", style="dim", width=4)
        table.add_column("Status", width=12)
        table.add_column("Action", width=10)
        table.add_column("Description")
        
        for step in steps:
            if step.status == "pending":
                icon = "⬜"
                style = "dim"
            elif step.status == "running":
                icon = "⏳"
                style = "bold yellow"
            elif step.status == "success":
                icon = "✅"
                style = "bold green"
            else:
                icon = "❌"
                style = "bold red"
                
            table.add_row(
                str(step.id),
                f"[{style}]{icon} {step.status.upper()}[/{style}]",
                step.action,
                step.description
            )
        return table

    async def execute_plan(self, steps_or_request: Union[List[TaskStep], str]):
        if isinstance(steps_or_request, str):
            steps = self.planner.create_plan(steps_or_request)
        else:
            steps = steps_or_request

        if not steps:
            self.console.print("[yellow]No steps to execute.[/yellow]")
            return
            
        # Display plan and ask for confirmation before executing
        self.console.print(self.generate_view(steps))
        from ..utils.io import confirm_action
        if not confirm_action(f"Proceed with executing this {len(steps)}-step plan?", default=True):
            self.console.print("[yellow]Plan cancelled by user.[/yellow]")
            return

        with Live(self.generate_view(steps), refresh_per_second=4, console=self.console) as live:
            context: Dict[str, Any] = {"files": [], "last_output": ""} 
            success_count = 0
            # Track overall status for memory
            plan_status = "success"
            final_output = ""

            for step in steps:
                step.status = "running"
                live.update(self.generate_view(steps))
                
                # --- Context Injection ---
                # 1. Replace <DOWNLOADED_FILE> with the last file found
                if context["files"] and "<DOWNLOADED_FILE>" in step.command:
                    step.command = step.command.replace("<DOWNLOADED_FILE>", context["files"][-1])
                
                # 2. Replace <LAST_OUTPUT> with stdout of previous command
                if context["last_output"] and "<LAST_OUTPUT>" in step.command:
                    step.command = step.command.replace("<LAST_OUTPUT>", context["last_output"].strip())
                
                # Execute based on action
                try:
                    if step.action == "CHECK":
                        # Pre-Flight Check
                        return_code, stdout, stderr = await asyncio.to_thread(self.executor.run, step.command, False, None, False)
                        if return_code == 0:
                            step.output = f"Check passed: {step.command}\nResource verified. Skipping remaining steps."
                            step.status = "success"
                            live.update(self.generate_view(steps))
                            self.console.print(f"[bold green]✨ State Verified: {stdout.strip()}. Task already completed.[/bold green]")
                            # Log success before return
                            self._log_plan_result(steps, "success", "Check verified goal already met.")
                            return # EXIT PLAN EARLY
                        else:
                            step.output = f"Check failed (Not found). Proceeding with plan."
                            step.description += " (Proceeding)"
                            step.status = "success" 
                            live.update(self.generate_view(steps)) 
                    
                    elif step.action == "BROWSER":
                        # --- Smart Resume: Check if file already exists ---
                        if step.filename_pattern:
                            import glob
                            import os
                            downloads_dir = os.path.expanduser("~/Downloads")
                            pattern = os.path.join(downloads_dir, step.filename_pattern)
                            matches = glob.glob(pattern)
                            if matches:
                                matches.sort(key=os.path.getmtime, reverse=True)
                                existing_file = matches[0]
                                step.output = f"Found existing file: {existing_file}\nSkipping Download."
                                step.status = "success"
                                context["files"].append(existing_file)
                                live.update(self.generate_view(steps))
                                continue

                        if self.browser_manager:
                            # 1. Run Browser Task
                            result = await asyncio.to_thread(self.browser_manager.run_task, step.command, use_cloud=step.use_cloud)
                            step.output = str(result)
                            
                            # 2. Wait for Download ONLY if pattern provided
                            if step.filename_pattern:
                                step.output += "\nWaiting for download..."
                                live.update(self.generate_view(steps))
                                downloaded_file = await self._wait_for_download()
                                if downloaded_file:
                                    step.output += f"\nFile captured: {downloaded_file}"
                                    context["files"].append(downloaded_file)
                                    step.status = "success"
                                else:
                                    step.output += "\nDownload timeout or not found."
                                    step.status = "failed"
                            else:
                                step.status = "success"
                        else:
                            step.output = "Browser Manager not initialized"
                            step.status = "failed"
                            
                    elif step.action == "TERMINAL":
                        # Handle sudo interactively
                        if "sudo" in step.command or SafetyCheck.is_sudo_required(step.command):
                            live.stop()
                            try:
                                return_code = await asyncio.to_thread(self.executor.run_interactive, step.command, False, None)
                                stdout = "Command executed interactively."
                                stderr = ""
                            finally:
                                live.start()
                        else:
                            return_code, stdout, stderr = await asyncio.to_thread(self.executor.run, step.command, False, None, False)
                        
                        # Store output for context
                        if return_code == 0:
                            context["last_output"] = stdout
                        
                        step.output = stdout if return_code == 0 else f"Failed (RC={return_code}): {stderr if stderr else 'Interactive error'}"
                        step.status = "success" if return_code == 0 else "failed"

                    else:
                        step.output = "Unknown Action"
                        step.status = "failed"
                except Exception as e:
                    step.output = str(e)
                    step.status = "failed"
                
                # --- Auto-Reflection (Self-Healing) ---
                if step.status == "failed":
                    self.console.print(f"[yellow]⚠️ Step {step.id} Failed. Attempting Auto-Fix...[/yellow]")
                    
                    # Provide context to fixer
                    error_context = f"{step.output}\n(Context: {context})"
                    fixed_command = await asyncio.to_thread(self.reflect_and_fix, step.command, error_context)
                    if fixed_command:
                        self.console.print(f"[bold cyan]🔄 Retrying with:[/bold cyan] {fixed_command}")
                        step.command = fixed_command
                        # Retry once
                        try:
                            if step.action == "TERMINAL":
                                rc, out, err = await asyncio.to_thread(self.executor.run, fixed_command, False, None, False)
                                step.output = out if rc == 0 else err
                                step.status = "success" if rc == 0 else "failed"
                                if rc == 0: context["last_output"] = out
                        except Exception as retry_e:
                            step.output = f"Retry failed: {retry_e}"
                            step.status = "failed"

                live.update(self.generate_view(steps))
                
                if step.status == "success":
                    success_count += 1
                    final_output = step.output  # Capture last successful output
                    
                    # Print actual command output for transparency
                    if step.output and step.output.strip():
                        self.console.print(f"\n[dim cyan]► Output from Step {step.id} ({step.action}):[/dim cyan]\n{step.output.strip()}")
                else:
                    self.console.print(f"\n[bold red]⚠️ Step {step.id} Failed:[/bold red]\n{step.output}")
                    plan_status = "failed"
                    final_output = step.output
                    break # Stop on failure
            
        # --- Display Final Results ---
        if plan_status == "success" and final_output:
            self.console.print("\n" + "="*60)
            self.console.print(Panel(
                final_output.strip(),
                title="[bold green]✓ Task Completed[/bold green]",
                border_style="green",
                padding=(1, 2)
            ))
            self.console.print("="*60 + "\n")
        
        # --- Memory: Log Execution ---
        self._log_plan_result(steps, plan_status, final_output)
        
        return final_output  # Return output for potential use by caller

    def _log_plan_result(self, steps, status, output):
        """Helper to log plan execution to memory"""
        if hasattr(self.llm_client, "memory_client") and self.llm_client.memory_client:
            # Reconstruct original query roughly from description of step 1 for now, 
            # or ideally pass request down. For now use Step 1 description as proxy query.
            query_proxy = steps[0].description if steps else "Unknown Task"
            self.llm_client.memory_client.log_execution(query_proxy, steps, status, output)
            self.console.print(f"[dim]🧠 Task logged to memory: {status}[/dim]")

    async def _wait_for_download(self, timeout: int = 60) -> Optional[str]:
        """Watches ~/Downloads for a new file."""
        import os
        import time
        downloads_dir = os.path.expanduser("~/Downloads")
        
        # Snapshot before
        before_files = set(os.listdir(downloads_dir)) if os.path.exists(downloads_dir) else set()
        
        params = {"new_file": None}

        async def check_loop():
            for _ in range(timeout):
                if not os.path.exists(downloads_dir):
                    await asyncio.sleep(1)
                    continue
                    
                current_files = set(os.listdir(downloads_dir))
                new_files = current_files - before_files
                
                # Filter out .crdownload or .part files
                valid_new = [f for f in new_files if not f.endswith(".crdownload") and not f.endswith(".part") and not f.endswith(".tmp")]
                
                if valid_new:
                    # Return the most recent valid one
                    params["new_file"] = os.path.join(downloads_dir, valid_new[0])
                    return
                
                await asyncio.sleep(1)
        
        await check_loop()
        return params["new_file"]

    def reflect_and_fix(self, failed_command: str, error_output: str) -> Optional[str]:
        """Ask LLM to fix the failed command."""
        prompt = f"""
The following command failed:
CMD: {failed_command}
ERROR: {error_output}

Fix the command to resolve the error. Return ONLY the fixed command string.
If it's not fixable via command (e.g. network down), return "NO_FIX".
"""
        try:
            # We use the planner's LLM client
            fix = self.planner.llm_client.generate_response(prompt).strip().replace("`", "")
            if "NO_FIX" in fix:
                return None
            return fix
        except:
            return None
