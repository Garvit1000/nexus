from abc import ABC, abstractmethod
from typing import Optional

class LLMClient(ABC):
    @abstractmethod
    def generate_response(self, prompt: str, model: Optional[str] = None) -> str:
        pass

class MockLLMClient(LLMClient):
    def generate_response(self, prompt: str, model: Optional[str] = None) -> str:
        return "echo 'This is a mock response because no API key is configured.'"

class GoogleGenAIClient(LLMClient):
    def __init__(self, api_key: str, model: str = "gemini-flash-latest"):
        from google import genai
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def generate_response(self, prompt: str, model: Optional[str] = None) -> str:
        response = self.client.models.generate_content(
            model=model or self.model,
            contents=prompt
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
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def generate_response(self, prompt: str, model: Optional[str] = None) -> str:
        response = self.client.chat.completions.create(
            model=model or self.model,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content or ""

class OpenRouterClient(LLMClient):
    def __init__(self, api_key: str, model: str = "openai/gpt-oss-120b:free"):
        from openai import OpenAI
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )
        self.model = model

    def generate_response(self, prompt: str, model: Optional[str] = None) -> str:
        # Support extra_body for reasoning if needed, but keeping it simple for now
        # akin to user example
        response = self.client.chat.completions.create(
            model=model or self.model,
            messages=[{"role": "user", "content": prompt}],
            # Enable reasoning/COT if the model supports it via extra_body
            # but user didn't strictly mandate it for every call, just showed example.
            # We'll stick to standard generation for now.
        )
        return response.choices[0].message.content or ""
