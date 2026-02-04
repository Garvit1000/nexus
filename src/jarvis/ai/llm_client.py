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
