"""
Context Condenser — smart compression for large context that exceeds model capacity.

Instead of blindly truncating text at character limits (losing everything past the
cutoff), this module uses a fast LLM to summarize large context so downstream models
get all the important information in a condensed form.

Usage:
    condenser = ContextCondenser(fallback_clients)
    compressed = condenser.condense(large_text, max_chars=3000)
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# Prompts for different condensation scenarios
_CONDENSE_PROMPT = """You are a context compression engine. Summarize the following text while preserving ALL important details, key facts, file paths, commands, error messages, configurations, and technical specifics. Do NOT add commentary or opinions — just compress the information faithfully.

Be concise but complete. Preserve:
- File paths and names
- Command syntax and arguments
- Error messages and codes
- Configuration values and settings
- Variable names and function names
- Key decisions and outcomes
- Numbers, dates, and versions

TEXT TO COMPRESS:
{text}

COMPRESSED SUMMARY:"""

_CONDENSE_FILE_PROMPT = """Summarize this file content while preserving all important details. Keep key structure, settings, function names, imports, and notable code patterns. Be concise but don't lose technical specifics.

FILE CONTENT:
{text}

SUMMARY:"""


class ContextCondenser:
    """Compresses large text using a fast LLM when it exceeds capacity thresholds."""

    def __init__(
        self,
        clients: list[Any] | None = None,
        on_condense: Callable[[int, int, str], None] | None = None,
    ):
        """
        Args:
            clients: List of LLM client instances to use for compression.
                     Tries each in order; first successful response wins.
                     Groq clients are preferred (fastest inference).
            on_condense: Optional callback fired when condensation occurs.
                         Receives (original_chars, condensed_chars, source_label).
                         Use this for UI feedback.
        """
        self._clients = list(clients or [])
        # Reorder: put Groq clients first for speed
        self._clients = sorted(
            self._clients,
            key=lambda c: 0 if "Groq" in type(c).__name__ else 1,
        )
        self._on_condense = on_condense

    def _call_llm(self, prompt: str) -> Optional[str]:
        """Call the first available LLM client, bypassing memory enrichment."""
        # Add marker to prevent enrich_prompt from injecting memory
        safe_prompt = f"--- MEMORY CONTEXT ---\n--- END MEMORY ---\n\n{prompt}"
        for client in self._clients:
            try:
                response = client.generate_response(safe_prompt)
                if response and response.strip():
                    return response.strip()
            except Exception as e:
                logger.debug(f"Condenser client {type(client).__name__} failed: {e}")
                continue
        return None

    def _notify(self, original_len: int, condensed_len: int, label: str) -> None:
        """Fire the on_condense callback if registered."""
        if self._on_condense:
            try:
                self._on_condense(original_len, condensed_len, label)
            except Exception:
                pass

    def condense(
        self,
        text: str,
        max_chars: int = 3000,
        prompt_template: str | None = None,
        label: str = "context",
    ) -> str:
        """Compress text if it exceeds max_chars using LLM summarization.

        Args:
            text: The text to potentially compress.
            max_chars: Character threshold. Text under this is returned as-is.
            prompt_template: Custom prompt with {text} placeholder.
                           Falls back to the default compression prompt.
            label: Human-readable label for what is being condensed
                   (e.g. "file content", "memory context"). Used in UI feedback.

        Returns:
            Original text if under threshold, or LLM-compressed summary.
            Falls back to truncation if LLM compression fails.
        """
        if not text or len(text) <= max_chars:
            return text

        original_len = len(text)

        if not self._clients:
            # No clients available — fall back to truncation
            self._notify(original_len, max_chars, label)
            return text[:max_chars] + "\n... (truncated)"

        template = prompt_template or _CONDENSE_PROMPT
        # Feed the full text (up to a generous limit to avoid API token bombs)
        feed_text = text[:50000] if len(text) > 50000 else text
        prompt = template.format(text=feed_text)

        try:
            result = self._call_llm(prompt)
            if result and len(result) < len(text):
                self._notify(original_len, len(result), label)
                return result
        except Exception as e:
            logger.debug(f"Context condensation failed: {e}")

        # Fallback: truncate if LLM failed
        self._notify(original_len, max_chars, label)
        return text[:max_chars] + "\n... (truncated)"

    def condense_file(self, content: str, max_chars: int = 4000) -> str:
        """Specialized condensation for file contents."""
        return self.condense(
            content,
            max_chars=max_chars,
            prompt_template=_CONDENSE_FILE_PROMPT,
            label="file content",
        )
