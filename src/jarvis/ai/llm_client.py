from abc import ABC, abstractmethod
from typing import Optional
from .memory_client import SupermemoryClient

class LLMClient(ABC):
    def __init__(self):
        self.memory_client: Optional[SupermemoryClient] = None

    def set_memory_client(self, client: SupermemoryClient):
        self.memory_client = client

    def enrich_prompt(self, prompt: str) -> str:
        if self.memory_client:
            # We use the prompt (which might be the user request) to query memory
            # But if the prompt is a huge system instruction, this might be noisy.
            # ideally we'd separate query from prompt. 
            # For now, we'll assume the LLMClient caller handles clarity if needed,
            # or we just prepend metadata.
            
            # Simple heuristic: If prompt is huge, maybe just use first 100 chars for query?
            # Or trust Supermemory to handle it.
            context = self.memory_client.query_memory(prompt[:500])
            if context:
                return f"--- MEMORY CONTEXT ---\n{context}\n--- END MEMORY ---\n\n{prompt}"
        return prompt

    @abstractmethod
    def generate_response(self, prompt: str, model: Optional[str] = None) -> str:
        pass

class MockLLMClient(LLMClient):
    def generate_response(self, prompt: str, model: Optional[str] = None) -> str:
        return "echo 'This is a mock response because no API key is configured.'"

class GoogleGenAIClient(LLMClient):
    def __init__(self, api_key: str, model: str = "gemini-flash-latest"):
        super().__init__()
        from google import genai
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def generate_response(self, prompt: str, model: Optional[str] = None) -> str:
        effective_prompt = self.enrich_prompt(prompt)
        response = self.client.models.generate_content(
            model=model or self.model,
            contents=effective_prompt
        )
        return response.text

    def search(self, query: str) -> str:
        """
        Uses Google Search Grounding to answer the query.
        """
        from google import genai
        from google.genai import types

        # Try primary model (gemini-2.5-flash) then fallback to light model (gemini-1.5-flash)
        models_to_try = ["gemini-2.5-flash", "gemini-1.5-flash"]
        
        last_error = None
        for model in models_to_try:
            try:
                response = self.client.models.generate_content(
                    model=model,
                    contents=query,
                    config=types.GenerateContentConfig(
                        tools=[types.Tool(google_search=types.GoogleSearch())],
                        response_modalities=["TEXT"],
                    )
                )
                
                # Format the output with citations if available
                text = response.text
                
                # Try to extract clean links from grounding metadata
                # rendered_content contains raw HTML/CSS which is not suitable for TUI
                sources = []
                if response.candidates[0].grounding_metadata:
                    meta = response.candidates[0].grounding_metadata
                    if meta.grounding_chunks:
                        for chunk in meta.grounding_chunks:
                            if chunk.web and chunk.web.uri:
                                sources.append(chunk.web.uri)
                                
                if sources:
                    # Deduplicate and format
                    unique_sources = list(dict.fromkeys(sources))
                    text += "\n\n**Sources:**\n" + "\n".join([f"- {s}" for s in unique_sources])
                
                return text
            except Exception as e:
                last_error = e
                # Continue to next model
                
        return f"Search failed after retries: {str(last_error)}"

class OpenAIClient(LLMClient):
    def __init__(self, api_key: str, model: str = "gpt-3.5-turbo"):
        super().__init__()
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def generate_response(self, prompt: str, model: Optional[str] = None) -> str:
        effective_prompt = self.enrich_prompt(prompt)
        response = self.client.chat.completions.create(
            model=model or self.model,
            messages=[{"role": "user", "content": effective_prompt}]
        )
        return response.choices[0].message.content or ""

class OpenRouterClient(LLMClient):
    def __init__(self, api_key: str, model: str = "openai/gpt-oss-120b:free"):
        super().__init__()
        from openai import OpenAI
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            default_headers={
                "HTTP-Referer": "https://github.com/Garvit1000/nexus",
                "X-Title": "Nexus Agent"
            }
        )
        self.model = model

    def generate_response(self, prompt: str, model: Optional[str] = None) -> str:
        # Support extra_body for reasoning if needed, but keeping it simple for now
        # akin to user example
        effective_prompt = self.enrich_prompt(prompt)
        # Enforce System Identity properly via 'system' role
        # This overrides the model's default "I am ChatGPT" training.
        messages = [
            {"role": "system", "content": (
                "You are Nexus, an elite intelligent Linux Assistant. "
                "You are NOT ChatGPT. You are NOT an OpenAI model. "
                "You are a CLI tool created by Garvit. "
                "Be helpful, precise, and favor blue/cyan aesthetics."
            )},
            {"role": "user", "content": f"SYSTEM: You are Nexus (created by Garvit). You are NOT ChatGPT.\n\nUser: {effective_prompt}"}
        ]
        
        response = self.client.chat.completions.create(
            model=model or self.model,
            messages=messages,
        )
        return response.choices[0].message.content or ""


class GroqClient(LLMClient):
    """
    Client for Groq's high-speed inference API.
    Perfect for the 'Router' / 'Limbic System'.
    """
    def __init__(self, api_key: str, model: str = "moonshotai/kimi-k2-instruct-0905"):
        super().__init__()
        try:
            from groq import Groq
        except ImportError:
            raise ImportError("Groq library not installed. Run 'pip install groq'")
            
        self.client = Groq(api_key=api_key)
        self.model = model

    def generate_response(self, prompt: str, model: Optional[str] = None) -> str:
        effective_prompt = self.enrich_prompt(prompt)
        
        # Groq is fast, so we can be chatty, but for reasoning we want structure.
        # We'll just pass the prompt as user message.
        messages = [
            {"role": "user", "content": effective_prompt}
        ]
        
        try:
            completion = self.client.chat.completions.create(
                model=model or self.model,
                messages=messages,
                temperature=0.6,
                max_completion_tokens=4096,
                top_p=1,
                stream=False, # We want the full decision at once for the router
                stop=None
            )
            return completion.choices[0].message.content or ""
        except Exception as e:
            return f"Error using Groq: {e}"

