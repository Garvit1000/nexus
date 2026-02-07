import json
import asyncio
from typing import List, Dict, Optional
from dataclasses import dataclass
from rich.console import Console
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from rich.status import Status

@dataclass
class TaskStep:
    id: int
    description: str
    action: str # BROWSER, TERMINAL, LLM
    command: str
    filename_pattern: Optional[str] = None # For Smart Resume (checking existing downloads)
    status: str = "pending" # pending, running, success, failed
    output: str = ""

class Planner:
    def __init__(self, llm_client):
        self.llm_client = llm_client

    def create_plan(self, request: str) -> List[TaskStep]:
        # Transparency: Log model usage
        model_name = getattr(self.llm_client, "model_name", "Unknown Model")
        print(f"[dim]🧠 Planner Thinking with: {model_name}[/dim]")

        # --- RAG: Retrieve Proven Plans ---
        proven_context = ""
        if hasattr(self.llm_client, "memory_client") and self.llm_client.memory_client:
            # Query memory explicitly for plans
            rag_hits = self.llm_client.memory_client.query_memory(f"planned task {request}", limit=1)
            if rag_hits:
                print(f"[bold green]🧠 Recalled proven plan from memory![/bold green]")
                proven_context = f"\n### PROVEN PAST PLAN (ADAPT THIS)\n{rag_hits}\n"

        prompt = f"""
You are the Tactical Planner for Nexus.
Break down this user request into a sequence of precise, verifiable steps.

### MEMORY CONTEXT
{proven_context}

REQUEST: "{request}"

AVAILABLE ACTIONS:
- CHECK: Check if the request is already satisfied (e.g. check if app is installed).
- BROWSER: Use the browser to download files, find info, or navigate.
- TERMINAL: Run shell commands (e.g. tar, mv, sudo apt, git).

RULES:
1. **IDEMPOTENCY (CRITICAL)**:
   - Step 1 MUST be a `CHECK` action to see if the tool/app is already installed.
   - Use `which <app>` or `dpkg -l | grep <app>`.
   - If this passes (exit code 0), Nexus will skip the rest of the plan.
2. **DOWNLOADS**: 
   - Always download to `~/Downloads`.
   - If Step 1 is a download, Step 2 MUST refer to the file as `<DOWNLOADED_FILE>`. Nexus will replace this with the actual filename detected.
3. **handling FILE TYPES**:
   - **.deb**: `sudo dpkg -i <DOWNLOADED_FILE> && sudo apt-get install -f`
   - **.AppImage**: `chmod +x <DOWNLOADED_FILE> && ./<DOWNLOADED_FILE>` (or move to /opt)
   - **.zip**: `unzip <DOWNLOADED_FILE> -d /tmp`
   - **.tar.gz**: `tar -xzf <DOWNLOADED_FILE> -C /tmp`
4. **SYSTEM INTEGRITY**: 
   - Use `sudo` for any command modifying `/opt`, `/usr`, or `/etc`.

OUTPUT FORMAT (JSON ONLY):
[
  {{
    "description": "Check if installed",
    "action": "CHECK",
    "command": "which postman"
  }},
  {{
    "description": "Download Target File",
    "action": "BROWSER",
    "command": "Download [Software] for Linux 64-bit from [OfficialSite]",
    "filename_pattern": "postman*.tar.gz" 
  }},
  {{
    "description": "Install/Extract",
    "action": "TERMINAL",
    "command": "sudo dpkg -i <DOWNLOADED_FILE>" 
  }}
]
"""
        try:
            response = self.llm_client.generate_response(prompt).strip()
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
                    filename_pattern=step_data.get("filename_pattern")
                ))
            return steps
        except Exception as e:
            print(f"Planning failed: {e}")
            return []

class Orchestrator:
    def __init__(self, console: Console, executor, browser_manager, llm_client):
        self.console = console
        self.executor = executor
        self.browser_manager = browser_manager
        self.planner = Planner(llm_client)

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

    async def execute_plan(self, request: str):
        self.console.print(f"[bold cyan]🧠 Planning: {request}...[/bold cyan]")
        steps = self.planner.create_plan(request)
        
        if not steps:
            self.console.print("[red]Failed to generate a plan.[/red]")
            return

        with Live(self.generate_view(steps), refresh_per_second=4, console=self.console) as live:
            context = {"DOWNLOADED_FILE": None} 

            for step in steps:
                step.status = "running"
                live.update(self.generate_view(steps))
                
                # Context Injection
                if context["DOWNLOADED_FILE"] and "<DOWNLOADED_FILE>" in step.command:
                    step.command = step.command.replace("<DOWNLOADED_FILE>", context["DOWNLOADED_FILE"])
                
                # Execute based on action
                try:
                    if step.action == "CHECK":
                        # Pre-Flight Check
                        # If this command SUCCEEDS (0), it means the state is already verified, so we SKIP the rest.
                        return_code, stdout, stderr = self.executor.run(step.command)
                        if return_code == 0:
                            step.output = f"Check passed: {step.command}\nResource already exists. Skipping remaining steps."
                            step.status = "success"
                            live.update(self.generate_view(steps))
                            self.console.print(f"[bold green]✨ State Verified: {stdout.strip()}. Task already completed.[/bold green]")
                            return # EXIT PLAN EARLY
                        else:
                            step.output = f"Check failed (Not found). Proceeding with plan."
                            step.status = "failed" # It "failed" to find it, which is GOOD for the plan to proceed
                            # We don't want to show a big red X for a normal check failure
                            # So maybe we mark it as "success" (as in, check complete) but note it was not found?
                            # Or we can just let it be "failed" but explicitly continue.
                            # Let's mark it as "success" but with output "Not found, proceeding".
                            step.status = "success" 
                    
                    elif step.action == "BROWSER":
                        # --- Smart Resume: Check if file already exists ---
                        if step.filename_pattern:
                            import glob
                            import os
                            downloads_dir = os.path.expanduser("~/Downloads")
                            pattern = os.path.join(downloads_dir, step.filename_pattern)
                            matches = glob.glob(pattern)
                            if matches:
                                # Pick the most recent one
                                matches.sort(key=os.path.getmtime, reverse=True)
                                existing_file = matches[0]
                                step.output = f"Found existing file: {existing_file}\nSkipping Download."
                                step.status = "success" # Marked success to proceed
                                context["DOWNLOADED_FILE"] = existing_file
                                live.update(self.generate_view(steps))
                                continue

                        if self.browser_manager:
                            # 1. Run Browser Task
                            result = await asyncio.to_thread(self.browser_manager.run_task, step.command)
                            step.output = str(result)
                            
                            # 2. Wait for Download (Robustness)
                            if "download" in step.description.lower() or "download" in step.command.lower():
                                step.output += "\nWaiting for download..."
                                live.update(self.generate_view(steps))
                                downloaded_file = await self._wait_for_download()
                                if downloaded_file:
                                    step.output += f"\nFile captured: {downloaded_file}"
                                    context["DOWNLOADED_FILE"] = downloaded_file
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
                        # Smart context injection: Replace placeholders if we had them
                        # For now, rely on LLM getting paths right or using generic paths
                        return_code, stdout, stderr = self.executor.run(step.command)
                        step.output = stdout if return_code == 0 else stderr
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
                    fixed_command = self.reflect_and_fix(step.command, error_context)
                    if fixed_command:
                        self.console.print(f"[bold cyan]🔄 Retrying with:[/bold cyan] {fixed_command}")
                        step.command = fixed_command
                        # Retry once
                        try:
                            if step.action == "TERMINAL":
                                rc, out, err = self.executor.run(fixed_command)
                                step.output = out if rc == 0 else err
                                step.status = "success" if rc == 0 else "failed"
                            # We don't verify Browser retries yet as they are elusive
                        except Exception as retry_e:
                            step.output = f"Retry failed: {retry_e}"
                            step.status = "failed"

                live.update(self.generate_view(steps))
                
                if step.status == "success":
                    success_count += 1
                else:
                    self.console.print(f"[red]Step {step.id} Failed: {step.output}[/red]")
                    break # Stop on failure

        # --- Record Success to Memory ---
        if success_count == len(steps) and hasattr(self.planner.llm_client, "memory_client") and self.planner.llm_client.memory_client:
            # We construct a summary of the plan
            plan_summary = {
                "request": request,
                "steps": [
                    {"action": s.action, "command": s.command, "description": s.description} 
                    for s in steps
                ]
            }
            # Add to memory
            self.console.print(f"[dim]🧠 Memorizing successful plan for '{request}'...[/dim]")
            asyncio.create_task(
                self.planner.llm_client.memory_client.add_to_memory(
                    f"Planned task: {request}", 
                    metadata={"type": "plan", "content": json.dumps(plan_summary)}
                )
            )

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
