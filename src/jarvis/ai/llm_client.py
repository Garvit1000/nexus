from abc import ABC, abstractmethod
from typing import Optional

class LLMClient(ABC):
    @abstractmethod
    def generate_response(self, prompt: str) -> str:
        pass

class MockLLMClient(LLMClient):
    def generate_response(self, prompt: str) -> str:
        return "echo 'This is a mock response because no API key is configured.'"

class GoogleGenAIClient(LLMClient):
    def __init__(self, api_key: str, model: str = "gemini-flash-latest"):
        from google import genai
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def generate_response(self, prompt: str) -> str:
        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt
        )
        return response.text

    def search(self, query: str) -> str:
        """
        Uses Google Search Grounding to answer the query.
        """
        from google import genai
        from google.genai import types

        # Use gemini-2.0-flash for search grounding
        model = "gemini-2.0-flash" 
        
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
            if response.candidates[0].grounding_metadata and response.candidates[0].grounding_metadata.search_entry_point:
                 text += f"\n\nSource: {response.candidates[0].grounding_metadata.search_entry_point.rendered_content}"
            
            return text
        except Exception as e:
            return f"Search failed: {str(e)}"

class OpenAIClient(LLMClient):
    def __init__(self, api_key: str, model: str = "gpt-3.5-turbo"):
        from openai import OpenAI
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def generate_response(self, prompt: str) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
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

    def generate_response(self, prompt: str) -> str:
        # Support extra_body for reasoning if needed, but keeping it simple for now
        # akin to user example
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            # Enable reasoning/COT if the model supports it via extra_body
            # but user didn't strictly mandate it for every call, just showed example.
            # We'll stick to standard generation for now.
        )
        return response.choices[0].message.content or ""
