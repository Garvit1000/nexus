from browser_use import Agent
from browser_use.llm import ChatGoogle
from langchain_openai import ChatOpenAI
from browser_use_sdk import BrowserUse
import asyncio
import os
from typing import Optional

class BrowserManager:
    def __init__(self, api_key: str | object, openrouter_key: Optional[str] = None, provider: str = "google"):
        if hasattr(api_key, 'get_current_key'):
            self.key_rotator = api_key
            self.api_key = api_key.get_current_key()
        else:
            self.key_rotator = None
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

    def run_task(self, task_description: str, use_cloud: bool = False, max_retries: int = 4) -> str:
        """
        Executes a browser-based task with automatic key rotation.
        
        Args:
            task_description: The task to perform.
            use_cloud: If True, uses the BrowserUse Cloud SDK (headless).
                       If False, uses local browser-use lib (live view).
            max_retries: Maximum number of keys to try (default: 4)
        """
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # Get current key if using rotator
                if self.key_rotator:
                    self.api_key = self.key_rotator.get_current_key()
                    import logging; logging.debug(f"Using key attempt {attempt + 1}/{max_retries}")
                    
                    # Reinitialize LLM with new key
                    self.llm = ChatGoogle(
                        model="gemini-2.5-flash",
                        api_key=self.api_key
                    )
                
                result = self._execute_task(task_description, use_cloud)
                
                # Mark success if using rotator
                if self.key_rotator:
                    self.key_rotator.mark_success()
                    import logging; logging.debug("Browser key succeeded")
                
                return result
                
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                
                # Check if it's a rate limit / quota error
                is_quota_error = any(phrase in error_str for phrase in [
                    '429', 'quota', 'rate limit', 'resource exhausted', '404 not_found'
                ])
                
                if self.key_rotator:
                    self.key_rotator.mark_failure(exhausted=is_quota_error)
                    import logging; logging.warning(f"Browser request failed: {error_str[:100]}")
                    
                    # Check if all keys exhausted
                    if self.key_rotator.all_exhausted():
                        break
                    
                    # Continue to next key
                    continue
                else:
                    # No rotator, just fail
                    raise
        
        # All keys exhausted or max retries reached
        return f"Error: All API keys exhausted or max retries reached. Last error: {str(last_error)}"
    
    def _execute_task(self, task_description: str, use_cloud: bool) -> str:
        """Internal method to execute the actual task."""
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
                    disable_security=False,
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

                agent = Agent(
                    task=smart_task,
                    llm=self.llm,
                    browser=browser,
                    use_vision=self.use_vision
                )
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

                if loop and loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        history = pool.submit(asyncio.run, agent.run()).result()
                else:
                    history = asyncio.run(agent.run())
                return history.final_result()
            
        except Exception as e:
            raise  # Re-raise for retry logic to handle
