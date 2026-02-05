import os
from rich.console import Console
from ..core.executor import CommandExecutor
from ..ai.llm_client import LLMClient

console = Console()

class VideoManager:
    def __init__(self, executor: CommandExecutor, llm_client: LLMClient):
        self.executor = executor
        self.llm_client = llm_client
        
        # Check if we are ALREADY in a video workspace to avoid nesting
        current_dir = os.getcwd()
        if os.path.exists(os.path.join(current_dir, "remotion.config.ts")) or \
           os.path.exists(os.path.join(current_dir, "package.json")):
            # Heuristic: assume current dir is the workspace if it looks completely like one
            self.workspace_dir = current_dir
        else:
            self.workspace_dir = os.path.abspath("jarvis-video-workspace")

    def ensure_workspace(self) -> bool:
        """
        Ensures the Remotion workspace exists and is valid. If not, creates it.
        """
        # Check if it seems valid (has package.json)
        is_valid = os.path.exists(os.path.join(self.workspace_dir, "package.json"))

        if not is_valid:
            console.print(f"[bold cyan]Creating/Repairing video workspace at {self.workspace_dir}...[/bold cyan]")
            
            # Clean up if it exists but is broken (folder exists but no package.json)
            if os.path.exists(self.workspace_dir) and not os.listdir(self.workspace_dir):
                 # Only remove if empty or explicitly known broken; safety first
                 pass
            elif os.path.exists(self.workspace_dir):
                 # If directory exists but invalid, maybe we should just error or warn?
                 # For now, let's try to init inside it if empty, or fail if populated.
                 pass

            os.makedirs(self.workspace_dir, exist_ok=True)
            
            # Initialize Remotion project
            # Uses the standard blank template
            console.print("[cyan]Running init command (npx create-video@latest)...[/cyan]")
            console.print("[yellow]Please interact with the terminal if prompted.[/yellow]")
            cmd = "npx create-video@latest . --template=blank"
            return_code = self.executor.run_interactive(cmd, cwd=self.workspace_dir)
            
            if return_code != 0:
                console.print(f"[bold red]Failed to init Remotion (Exit Code: {return_code})[/bold red]")
                return False
            
            console.print("[green]Remotion project initialized successfully![/green]")
        else:
             console.print("[green]Workspace valid (package.json found).[/green]")

        # Ensure dependencies are installed
        # Ensure dependencies are installed
        if not os.path.exists(os.path.join(self.workspace_dir, "node_modules")):
            console.print("[cyan]Installing dependencies (npm install)...[/cyan]")
            console.print("[yellow]Please interact with the terminal if prompted.[/yellow]")
            return_code = self.executor.run_interactive("npm install", cwd=self.workspace_dir)
            if return_code != 0:
                console.print(f"[bold red]Failed to install dependencies (Exit Code: {return_code})[/bold red]")
                return False

        # Ensure extra packages are installed even if node_modules exists
        # We check for one key package to avoid re-running every time
        if not os.path.exists(os.path.join(self.workspace_dir, "node_modules", "@remotion", "transitions")):
            console.print("[cyan]Installing extra Remotion packages (fonts, shapes, transitions, media)...[/cyan]")
            extra_pkgs = "npm install @remotion/google-fonts @remotion/shapes @remotion/transitions @remotion/media"
            self.executor.run_interactive(extra_pkgs, cwd=self.workspace_dir)
        
        return True

    def generate_video(self, prompt: str) -> str:
        """
        Generates a video based on the prompt with strict validation.
        1. Ensures workspace
        2. Generates Code
        3. Validates Code (npx tsc) -> Auto-Fix Loop
        4. Renders video
        """
        if not self.ensure_workspace():
            return "Failed to setup workspace."

        current_prompt = prompt
        usage_context = "User Request: " + prompt
        
        # Retry Loop for Code Generation & Validation
        max_retries = 3
        for attempt in range(max_retries):
            console.print(f"[cyan]Attempt {attempt+1}/{max_retries}: Generating reference code...[/cyan]")
            
            # 1. Generate/Refine Code
            if attempt == 0:
                composition_code = self._get_composition_code(usage_context)
            else:
                # context now contains error details
                composition_code = self._get_composition_code(usage_context, is_fix=True)
            
            # 2. Write Code
            comp_path = os.path.join(self.workspace_dir, "src", "Composition.tsx")
            with open(comp_path, "w") as f:
                f.write(composition_code)
                
            # 3. Validate
            console.print("[dim]Validating code (npx tsc)...[/dim]")
            validation_error = self._validate_code()
            
            if not validation_error:
                console.print("[green]Code validation passed![/green]")
                break
            else:
                console.print(f"[bold red]Validation failed:[/bold red]\n{validation_error[:500]}...")
                # Update context for next iteration
                # Update context for next iteration to include original prompt, current code, and errors
                usage_context = (
                    f"ORIGINAL PROMPT: {current_prompt}\n\n"
                    f"CURRENT CODE (Needs Fix):\n```tsx\n{composition_code}\n```\n\n"
                    f"ERRORS:\n{validation_error}\n\n"
                    "INSTRUCTIONS: Please FIX the code above to resolve the errors. "
                    "Maintain the original video content and structure. "
                    "Return ONLY the corrected code."
                )
                
        # 4. Render (Proceed even if validation failed on last attempt, as a hail mary)
        console.print("[cyan]Starting render process...[/cyan]")
        output_file = "out.mp4"
        cmd = f"npx remotion render src/index.ts MyComp {output_file}"
        return_code = self.executor.run_interactive(cmd, cwd=self.workspace_dir)
        
        # ... (self healing removed as it's superseded by the validation loop)
        
        if return_code != 0:
            console.print(f"[bold red]Render Command Failed (Exit Code: {return_code})[/bold red]")
            return f"Rendering failed with exit code {return_code}"
            
        final_path = os.path.join(self.workspace_dir, output_file)
        console.print(f"[bold green]Render complete![/bold green]")
        return f"Video generated successfully at: {final_path}"

    def _validate_code(self) -> str | None:
        """
        Runs `npx tsc` to check for type/syntax errors.
        Returns the error string if failed, or None if passed.
        """
        # We use --noEmit so it just checks types
        cmd = "npx tsc --noEmit --skipLibCheck"
        # We need to capture output, so we can't use run_interactive easily for this silent check
        # But our executor.run captures output.
        return_code, stdout, stderr = self.executor.run(cmd, cwd=self.workspace_dir)
        
        if return_code != 0:
            # TSC output is usually in stdout, but check both
            return (stdout + "\n" + stderr).strip()
        return None

    def _get_composition_code(self, context: str, is_fix: bool = False) -> str:
        """
        Asks LLM to write the React code.
        """
        system_prompt = (
            "You are an expert Remotion Developer. "
            "Write the contents of a 'Composition.tsx' file using React and Remotion. "
            "The component export name MUST be 'MyComposition'. "
            "\n\n"
            "### 1. CORE RULES\n"
            "- **NO Hallucinations**: Do NOT invent components. \n"
            "  - BAD: `import { Series } ...` -> `<Series.Sequence>` (This DOES NOT exist).\n"
            "  - GOOD: `import { TransitionSeries } ...` -> `<TransitionSeries.Sequence>`.\n"
            "- **Animations**: Use `useCurrentFrame()`, `interpolate()`, and `spring()`.\n"
            "- **No CSS Animations**: Do NOT use keyframes or standard CSS transitions.\n"
            "\n"
            "### 2. COMPONENT STRUCTURE (TransitionSeries)\n"
            "You MUST use the `TransitionSeries` API for sequencing scenes. \n"
            "Example of CORRECT usage:\n"
            "```tsx\n"
            "import { TransitionSeries, linearTiming } from '@remotion/transitions';\n"
            "import { fade } from '@remotion/transitions/fade';\n"
            "// ... other imports\n"
            "\n"
            "export const MyComposition: React.FC = () => {\n"
            "  return (\n"
            "    <AbsoluteFill>\n"
            "      <TransitionSeries>\n"
            "        <TransitionSeries.Sequence durationInFrames={60}>\n"
            "             <TitleScene />\n"
            "        </TransitionSeries.Sequence>\n"
            "\n"
            "        <TransitionSeries.Transition\n"
            "             presentation={fade()} \n"
            "             timing={linearTiming({ durationInFrames: 15 })}\n"
            "        />\n"
            "\n"
            "        <TransitionSeries.Sequence durationInFrames={90}>\n"
            "             <ContentScene />\n"
            "        </TransitionSeries.Sequence>\n"
            "      </TransitionSeries>\n"
            "    </AbsoluteFill>\n"
            "  );\n"
            "};\n"
            "```\n"
            "\n"
            "### 3. IMPORTS\n"
            "- `import { TransitionSeries, linearTiming } from '@remotion/transitions';`\n"
            "- `import { fade } from '@remotion/transitions/fade';` (Specific import!)\n"
            "- `import { slide } from '@remotion/transitions/slide';` (Specific import!)\n"
            "- `import { spring, interpolate, useCurrentFrame, useVideoConfig, AbsoluteFill } from 'remotion';`\n"
            "- `import { loadFont } from '@remotion/google-fonts/Inter';`\n"
            "\n"
            "### 4. COMMON MISTAKES TO AVOID\n"
            "- **DO NOT use `<Series>` or `import { Series }`. It does not exist.**\n"
            "- **DO NOT use `<TransitionSeries.Transition transition={...} />`.** Use `presentation={...}`.\n"
            "- **DO NOT put `durationInFrames` on `<TransitionSeries.Transition>`.** Put it inside `timing={linearTiming({ durationInFrames: X })}`.\n"
            "\n"
            "### REQUIRED EXPORTS:\n"
            "- `export const MyComposition: React.FC = () => { ... }`\n"
            "- `export const durationInFrames = 150;` (Calculate based on total length).\n"
            "\n"
            "### Output Format:\n"
            "Return ONLY the raw TypeScript/React code. No markdown, no explanations."
        )
        
        if is_fix:
            full_prompt = f"{system_prompt}\n\nFIX REQUEST:\n{context}"
        else:
            full_prompt = f"{system_prompt}\n\nUSER REQUEST:\n{context}"
        
        # Use Gemini 2.5 Flash for speed and quality
        code = self.llm_client.generate_response(full_prompt, model="gemini-2.5-flash")
        
        # Clean up text if LLM adds markdown
        code = code.replace("```tsx", "").replace("```typescript", "").replace("```", "").strip()
        return code
