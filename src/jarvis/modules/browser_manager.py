from browser_use import Agent
from browser_use.llm import ChatGoogle
from langchain_openai import ChatOpenAI
from browser_use_sdk import BrowserUse
import asyncio
import os

class BrowserManager:
    def __init__(self, api_key: str, openrouter_key: str = None, provider: str = "google"):
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
             # Default to Google (Gemini)
             self.llm = ChatGoogle(
                model="gemini-flash-latest", 
                api_key=api_key
             )
             self.use_vision = False
        
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
                agent = Agent(
                    task=task_description,
                    llm=self.llm,
                    use_vision=self.use_vision  # Dynamic based on provider
                )
                # Since Agent.run() is async, running in event loop
                return asyncio.run(agent.run())
            
        except Exception as e:
            return f"Error executing browser task: {str(e)}"
