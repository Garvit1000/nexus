from browser_use import Agent
from browser_use.llm import ChatGoogle
from langchain_openai import ChatOpenAI
from browser_use_sdk import BrowserUse
import asyncio
import os
from typing import Optional

class BrowserManager:
    def __init__(self, api_key: str, openrouter_key: Optional[str] = None, provider: str = "google"):
        self.api_key = api_key
        # Initialize the model for Local Mode
        if provider == "openrouter":
             self.llm = ChatOpenAI(
                base_url="https://openrouter.ai/api/v1",
                model="openai/gpt-oss-120b:free",
                api_key=openrouter_key,
             )
             self.use_vision = False # OpenRouter free models often don't support vision
        else:
            # Default to Google (Gemini 2.5 Flash - best for browser tasks)
            self.llm = ChatGoogle(
               model="gemini-2.5-flash",
               api_key=api_key
            )
            self.use_vision = True  # Gemini 2.5 supports vision
        
        # Initialize Cloud Client if key is available
        self.cloud_client = None
        self.cloud_api_key = os.getenv("BROWSER_USE_API_KEY")
        if self.cloud_api_key:
            self.cloud_client = BrowserUse(api_key=self.cloud_api_key)

    def run_task(self, task_description: str, use_cloud: bool = False) -> str:
        """
        Executes a browser-based task.
        Args:
            task_description: The task to perform.
            use_cloud: If True, uses the BrowserUse Cloud SDK (headless). 
                       If False, uses local browser-use lib (live view).
        """
        try:
            if use_cloud:
                if not self.cloud_client:
                    return "Error: BROWSER_USE_API_KEY not set. Cannot run in cloud mode."
                
                # Cloud Mode (SDK)
                task = self.cloud_client.tasks.create_task(
                    task=task_description,
                    llm="browser-use-llm" # Using the default cloud model
                )
                result = task.complete()
                return result.output
            else:
                # Local Mode (Library)
                from browser_use import Browser
                
                # Smart Defaults: Force downloads to ~/Downloads
                downloads_path = os.path.expanduser("~/Downloads")
                os.makedirs(downloads_path, exist_ok=True)
                
                # Initialize Browser with specific connection settings
                # Note: Browser is an alias for BrowserSession
                browser = Browser(
                    headless=False, 
                    disable_security=True,
                    downloads_path=downloads_path
                )

                # Inject Intelligence Guidelines
                smart_task = (
                    f"{task_description}\n\n"
                    "--- ACTION GUIDELINES ---\n"
                    "1. DOWNLOADS: Files will save to ~/Downloads. Check there.\n"
                    "2. VERIFY: Click 'Download' ONCE. Wait for the file to appear or indicator to change.\n"
                    "3. NO RAGE CLICKING: Do not repeatedly click if it seems stuck. Check for popups.\n"
                    "4. EFFICIENCY: If the file already exists, skip downloading.\n"
                )

                # Transparency: Log the model being used
                model_name = getattr(self.llm, 'model_name', getattr(self.llm, 'model', 'Unknown Model'))
                print(f"\n[bold magenta]🤖 Browser Agent Thinking with: {model_name}[/bold magenta]")

                agent = Agent(
                    task=smart_task,
                    llm=self.llm,
                    browser=browser,
                    use_vision=self.use_vision
                )
                # Since Agent.run() is async, running in event loop
                history = asyncio.run(agent.run())
                return history.final_result()
            
        except Exception as e:
            return f"Error executing browser task: {str(e)}"
