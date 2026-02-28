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
    file_content: Optional[str] = None # For FILE_WRITE operations
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
   - Set `"headless": false` for interactive browsing
   - Optional: `"filename_pattern": "*.pdf"` (ONLY if downloading a file)

2. **TERMINAL**: For shell commands (system operations, service management)
   - Use for `apt install`, `systemctl restart`, `docker run`, etc.

3. **CHECK**: For verifying if a SPECIFIC FILE, CLI TOOL, or STATE exists
   - VERY IMPORTANT: Use to verify dependencies (e.g., `which nginx`) before attempting to use them.
   - Use for state validation (e.g., `systemctl is-active nginx`).

4. **FILE_WRITE**: For safely creating or overwriting configuration files.
   - Requires `"command": "/absolute/path/to/file"`
   - Requires `"file_content": "multiline string data"`

### PLANNING INTELLIGENCE

**UNDERSTAND THE REQUEST FIRST:**
- What is the user's PRIMARY goal?
- Do they want to RETRIEVE data, DOWNLOAD a file, CHECK system state, DEPLOY a service, or DO something?

**TASK TYPE RECOGNITION:**

1. **System Administration Tasks** (install, deploy, configure services like Nginx/Docker):
   - Step 1: CHECK dependency (e.g., `which nginx || exit 1`)
   - Step 2: TERMINAL install if checking failed
   - Step 3: FILE_WRITE for configuration files (DO NOT use `echo "..." > file`)
   - Step 4: CHECK state validation (e.g., `systemctl is-active nginx`)

2. **Data Retrieval Tasks** (news, posts, weather, trending topics):
   - NO CHECK step needed (data changes constantly)
   - Direct BROWSER action with headless=true
   - Example: "show me latest news" → Just fetch and display

3. **Download Tasks** (download file, get installer):
   - CHECK if file pattern provided and resumability matters
   - BROWSER with filename_pattern for download
   - Optional TERMINAL for post-processing

4. **Interactive Tasks** (open website):
   - BROWSER with headless=false
   - NO CHECK step

### CRITICAL RULES

1. **DON'T OVER-ENGINEER**:
   - User asks "show me news" → Just fetch the news, don't check if news exists locally (makes no sense!)
   - User asks "get weather" → Just get weather, don't check cache

2. **CHECK Step Guidelines**:
   - ✅ USE CHECK: Verifying dependencies before sysadmin tasks (`which docker`) or avoiding re-downloads.
   - ❌ DON'T CHECK: "Show me trending news" (news changes, no local check makes sense).
   - ❌ DON'T CHECK: "Get weather in Delhi" (weather is live data).

3. **Headless Decision**:
   - Data retrieval (news, posts, weather) → headless: true
   - User wants to "watch", "see", "open" → headless: false

4. **Minimal Steps**:
   - If one BROWSER action fulfills the request → Use ONE step.
   - Don't add verification unless explicitly needed (like DevOps/SysAdmin tasks).

### EXAMPLES (LEARN FROM THESE)

Request: "Create an Nginx server that returns Hello World on port 8080"
Plan:
[
  {{
    "description": "Check if Nginx is installed",
    "action": "CHECK",
    "command": "which nginx || exit 1"
  }},
  {{
    "description": "Install Nginx if missing",
    "action": "TERMINAL",
    "command": "sudo apt-get update && sudo apt-get install -y nginx"
  }},
  {{
    "description": "Write Nginx configuration block",
    "action": "FILE_WRITE",
    "command": "/etc/nginx/sites-available/hello_world",
    "file_content": "server {{\n    listen 8080;\n    location / {{\n        return 200 'Hello World';\n        add_header Content-Type text/plain;\n    }}\n}}"
  }},
  {{
    "description": "Enable site and restart Nginx",
    "action": "TERMINAL",
    "command": "sudo ln -s /etc/nginx/sites-available/hello_world /etc/nginx/sites-enabled/ && sudo systemctl restart nginx"
  }},
  {{
    "description": "Verify Nginx is serving the response",
    "action": "CHECK",
    "command": "curl -f http://localhost:8080"
  }}
]

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

OUTPUT FORMAT (JSON ONLY):
[
  {{
    "description": "Clear description of this step",
    "action": "BROWSER" | "TERMINAL" | "CHECK" | "FILE_WRITE",
    "command": "Specific terminal command, browser instruction, or absolute file path",
    "filename_pattern": "optional_pattern_for_downloads",
    "file_content": "optional content for FILE_WRITE only",
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
        self.fallback_clients = fallback_clients or []
        self.planner = Planner(llm_client, fallback_clients=fallback_clients)
        
    def reflect_and_fix(self, failed_command: str, error_output: str) -> Optional[str]:
        """Ask the LLM to analyze a failed execution and provide a fixed command."""
        prompt = f"""
        You are a senior DevOps engineer diagnosing a failed terminal command.
        
        FAILED COMMAND: `{failed_command}`
        
        ERROR OUTPUT / CONTEXT:
        {error_output}
        
        Analyze why the command failed. 
        If the error is due to an unmet dependency, generating a fix that installs it first is acceptable if chaining (e.g., `apt install -y X && <original command>`).
        If it's a syntax error or a missing flag, correct the command.
        If the error indicates the command fundamentally cannot work in this environment, try an alternative approach that achieves the same goal.
        
        OUTPUT FORMAT:
        Return ONLY the raw, fixed shell command to execute. Do not include markdown blocks, explanations, or quotes.
        If it cannot be fixed automatically, return the exact word: UNFIXABLE
        """
        
        clients = [self.llm_client] + self.fallback_clients
        for client in clients:
            try:
                response = client.generate_response(prompt).strip()
                clean_response = response.replace("```bash", "").replace("```sh", "").replace("```", "").strip()
                if clean_response.upper() == "UNFIXABLE" or not clean_response:
                    return None
                return clean_response
            except Exception as e:
                import logging
                logging.warning(f"Self-heal model failed: {e}")
                continue
                
        return None

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
                if step.status == "success" and "Skipped" in step.output:
                    # Intelligently skipped by previous CHECK pass (e.g., dependency already exists)
                    continue
                    
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
                        # Execute the Check Command
                        live.stop()
                        try:
                            return_code, stdout, stderr = await asyncio.to_thread(self.executor.run, step.command, False, None, False)
                        finally:
                            live.start()
                        
                        if return_code == 0:
                            step.output = f"Check passed: {stdout.strip()}"
                            step.status = "success"
                            live.update(self.generate_view(steps))
                            
                            # SYSADMIN INTELLIGENCE: If the check passed (e.g., docker is installed), 
                            # and the immediately following step is an installation for that tool,
                            # we should mark the NEXT step as 'skipped' so we don't reinstall it.
                            # We heuristic match if next step action is TERMINAL and contains install/update.
                            current_index = steps.index(step)
                            if current_index + 1 < len(steps):
                                next_step = steps[current_index + 1]
                                if next_step.action == "TERMINAL" and any(k in next_step.command.lower() for k in ["install", "apt-get", "pacman", "dnf", "brew"]):
                                    next_step.status = "success"
                                    next_step.output = "Skipped: Dependency verified in previous step."
                                    next_step.description += " (Skipped)"
                                    
                            # Determine if this was the ONLY step in the plan (e.g. just checking a file)
                            if len(steps) == 1:
                                self.console.print(f"[bold green]✨ State Verified: {stdout.strip()}.[/bold green]")
                        else:
                            current_index = steps.index(step)
                            if current_index == len(steps) - 1:
                                # This is the final step (a verification checkpoint). Failure here means the overall task failed.
                                step.output = f"Verification failed (RC={return_code}): {stderr if stderr else stdout}"
                                step.status = "failed"
                            else:
                                # It's a pre-check (e.g., checking if docker exists before installing). Proceed normally.
                                step.output = f"Check failed (Not found/Not active). Proceeding."
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

                    elif step.action == "FILE_WRITE":
                        if not step.file_content:
                            step.output = "Error: No file_content provided for FILE_WRITE action."
                            step.status = "failed"
                        elif not step.command:
                            step.output = "Error: No absolute file path provided in command field for FILE_WRITE action."
                            step.status = "failed"
                        else:
                            import shlex
                            file_path = step.command.strip()
                            content = step.file_content
                            # Use sudo tee to safely write multiline content to potentially restricted directories
                            # We pipe the content securely into the command
                            # shlex.quote handles spaces, but since we are executing via subprocess/shell, 
                            # we construct the command securely to avoid injection from the path.
                            safe_path = shlex.quote(file_path)
                            write_command = f"sudo tee {safe_path} > /dev/null"
                            
                            import subprocess
                            live.stop()
                            try:
                                process = await asyncio.to_thread(
                                    subprocess.run,
                                    write_command,
                                    input=content,
                                    text=True,
                                    shell=True,
                                    capture_output=True
                                )
                                # Ensure we capture return code accurately
                                if process.returncode == 0:
                                    step.output = f"Successfully wrote to {file_path}"
                                    step.status = "success"
                                else:
                                    step.output = f"Failed to write file (RC={process.returncode}): {process.stderr}"
                                    step.status = "failed"
                            except Exception as fe:
                                step.output = f"FILE_WRITE Exception: {fe}"
                                step.status = "failed"
                            finally:
                                live.start()

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
                    fixed_command = await asyncio.to_thread(self.reflect_and_fix, step.command, error_context) # type: ignore
                    if fixed_command:
                        self.console.print(f"[bold cyan]🔄 Retrying with:[/bold cyan] {fixed_command}")
                        step.command = fixed_command
                        # Retry once
                        live.stop()
                        try:
                            if step.action in ("TERMINAL", "CHECK"):
                                rc, out, err = await asyncio.to_thread(self.executor.run, fixed_command, False, None, False)
                                step.output = out if rc == 0 else err
                                step.status = "success" if rc == 0 else "failed"
                                if rc == 0: context["last_output"] = out
                            else:
                                step.output = "Retry skipped (unsupported action)"
                        except Exception as retry_e:
                            step.output = f"Retry failed: {retry_e}"
                            step.status = "failed"
                        finally:
                            live.start()

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
            # We use the planner's primary LLM client
            fix = self.planner.llm_clients[0].generate_response(prompt).strip().replace("`", "")
            if "NO_FIX" in fix:
                return None
            return fix
        except:
            return None
