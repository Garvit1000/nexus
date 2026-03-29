from abc import ABC, abstractmethod
from typing import Optional
from .memory_client import SupermemoryClient


class LLMClient(ABC):
    def __init__(self):
        self.memory_client: Optional[SupermemoryClient] = None

    def set_memory_client(self, client: SupermemoryClient):
        self.memory_client = client

    def enrich_prompt(self, prompt: str, skip_memory: bool = False) -> str:
        """Prepend relevant memory context to a prompt.

        Args:
            prompt: The raw prompt text.
            skip_memory: If True, bypass the memory query (e.g. for planner
                         calls that already perform their own RAG step).
        """
        # 1. Quick exits
        if skip_memory or not prompt or not self.memory_client:
            return prompt

        # 2. Avoid double-enrichment (e.g. if console_app already added context)
        if "--- MEMORY CONTEXT ---" in prompt:
            return prompt

        try:
            query_signal = prompt
            if "User: " in prompt and "\nNexus: " in prompt:
                query_signal = prompt.split("User: ")[-1]

            context = self.memory_client.query_memory(query_signal[:500])
            if context:
                context = str(context)
                # Condense large memory context instead of blind truncation
                if len(context) > 2000:
                    try:
                        from .context_condenser import ContextCondenser

                        condenser = ContextCondenser([self])
                        context = condenser.condense(context, max_chars=1500)
                    except Exception:
                        context = context[:2000]
                return (
                    f"--- MEMORY CONTEXT ---\n{context}\n--- END MEMORY ---\n\n{prompt}"
                )
        except Exception:
            pass
        return prompt

    @abstractmethod
    def generate_response(self, prompt: str, model: Optional[str] = None) -> str:
        pass

    def generate_stream(self, prompt: str, model: Optional[str] = None):
        """Yield response text in chunks as they stream from the API.

        Default implementation falls back to a single-chunk yield so callers
        can always iterate without caring whether a client supports streaming.
        """
        yield self.generate_response(prompt, model)

    def search(self, query: str) -> str:
        raise NotImplementedError("Search not supported by this provider.")


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
            model=model or self.model, contents=effective_prompt
        )
        return response.text

    def generate_stream(self, prompt: str, model: Optional[str] = None):
        """Yield text chunks using Gemini's server-sent streaming."""
        effective_prompt = self.enrich_prompt(prompt)
        for chunk in self.client.models.generate_content_stream(
            model=model or self.model,
            contents=effective_prompt,
        ):
            if chunk.text:
                yield chunk.text

    def search(self, query: str) -> str:
        """
        Uses Google Search Grounding to answer the query.
        """
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
                    ),
                )

                # Format the output with citations if available
                text = response.text

                # Try to extract clean links from grounding metadata
                # rendered_content contains raw HTML/CSS which is not suitable for TUI
                sources = []
                if response.candidates and response.candidates[0].grounding_metadata:
                    meta = response.candidates[0].grounding_metadata
                    if meta.grounding_chunks:
                        for chunk in meta.grounding_chunks:
                            if chunk.web and chunk.web.uri:
                                sources.append(chunk.web.uri)

                if sources:
                    # Deduplicate and format
                    unique_sources = list(dict.fromkeys(sources))
                    text += "\n\n**Sources:**\n" + "\n".join(
                        [f"- {s}" for s in unique_sources]
                    )

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
            messages=[{"role": "user", "content": effective_prompt}],
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
                "X-Title": "Nexus Agent",
            },
        )
        self.model = model

    def _messages(self, prompt: str) -> list:
        effective_prompt = self.enrich_prompt(prompt)
        return [
            {
                "role": "system",
                "content": (
                    "You are Nexus, an elite intelligent Linux Assistant. "
                    "You are NOT ChatGPT. You are a CLI tool created by Garvit. "
                    "Be helpful, precise, and concise."
                ),
            },
            {"role": "user", "content": effective_prompt},
        ]

    def generate_response(self, prompt: str, model: Optional[str] = None) -> str:
        response = self.client.chat.completions.create(
            model=model or self.model,
            messages=self._messages(prompt),
        )
        return response.choices[0].message.content or ""

    def generate_stream(self, prompt: str, model: Optional[str] = None):
        """Yield text chunks via OpenAI-compatible streaming."""
        stream = self.client.chat.completions.create(
            model=model or self.model,
            messages=self._messages(prompt),
            stream=True,
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta


class AnthropicClient(LLMClient):
    """Anthropic Claude client — high-quality reasoning and long context."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        super().__init__()
        try:
            from anthropic import Anthropic
        except ImportError:
            raise ImportError(
                "Anthropic library not installed. Run: pip install anthropic"
            )
        self.client = Anthropic(api_key=api_key)
        self.model = model

    def _call(self, prompt: str, model: str | None = None, stream: bool = False):
        effective_prompt = self.enrich_prompt(prompt)
        params = {
            "model": model or self.model,
            "max_tokens": 8192,
            "messages": [{"role": "user", "content": effective_prompt}],
            "system": (
                "You are Nexus, an elite intelligent Linux Assistant. "
                "You are NOT ChatGPT. You are a CLI tool created by Garvit. "
                "Be helpful, precise, and concise."
            ),
        }
        if stream:
            return self.client.messages.stream(**params)
        return self.client.messages.create(**params)

    def generate_response(self, prompt: str, model: Optional[str] = None) -> str:
        response = self._call(prompt, model)
        return response.content[0].text if response.content else ""

    def generate_stream(self, prompt: str, model: Optional[str] = None):
        """Yield text chunks via Anthropic streaming."""
        with self._call(prompt, model, stream=True) as stream:
            for text in stream.text_stream:
                yield text


class GroqClient(LLMClient):
    """Groq fast-inference client — used for the Decision Router."""

    def __init__(self, api_key: str, model: str = "moonshotai/kimi-k2-instruct-0905"):
        super().__init__()
        try:
            from groq import Groq
        except ImportError:
            raise ImportError("Groq library not installed. Run: pip install groq")
        self.client = Groq(api_key=api_key)
        self.model = model

    def generate_response(self, prompt: str, model: Optional[str] = None) -> str:
        effective_prompt = self.enrich_prompt(
            prompt, skip_memory=True
        )  # router never needs memory
        messages = [{"role": "user", "content": effective_prompt}]
        try:
            completion = self.client.chat.completions.create(
                model=model or self.model,
                messages=messages,
                temperature=0.6,
                max_completion_tokens=4096,
                stream=False,
            )
            return completion.choices[0].message.content or ""
        except Exception as e:
            # Propagate exception so fallback can catch it
            raise e


class GroqGPTClient(LLMClient):
    """Groq-hosted GPT-class model — primary chat brain."""

    def __init__(self, api_key: str, model: str = "openai/gpt-oss-120b"):
        super().__init__()
        try:
            from groq import Groq
        except ImportError:
            raise ImportError("Groq library not installed. Run: pip install groq")
        self.client = Groq(api_key=api_key)
        self.model = model

    def _messages(self, prompt: str) -> list:
        effective_prompt = self.enrich_prompt(prompt)
        return [
            {
                "role": "system",
                "content": (
                    "You are Nexus, an elite intelligent Linux Assistant. "
                    "You are NOT ChatGPT. You are a CLI tool created by Garvit. "
                    "Be helpful, precise, and concise."
                ),
            },
            {"role": "user", "content": effective_prompt},
        ]

    def generate_response(self, prompt: str, model: Optional[str] = None) -> str:
        try:
            completion = self.client.chat.completions.create(
                model=model or self.model,
                messages=self._messages(prompt),
                temperature=1,
                max_completion_tokens=8192,
                stream=False,
            )
            return completion.choices[0].message.content or ""
        except Exception as e:
            raise e

    def generate_stream(self, prompt: str, model: Optional[str] = None):
        """Yield text chunks — first token arrives in ~100ms on Groq."""
        try:
            stream = self.client.chat.completions.create(
                model=model or self.model,
                messages=self._messages(prompt),
                temperature=1,
                max_completion_tokens=8192,
                stream=True,
            )
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except Exception as e:
            raise e
