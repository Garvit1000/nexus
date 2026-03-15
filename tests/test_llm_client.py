"""
Tests for jarvis.ai.llm_client — LLMClient base class and MockLLMClient.

Verifies that:
- MockLLMClient returns a mock response
- enrich_prompt prepends memory context when available
- enrich_prompt skips memory when skip_memory is True
- enrich_prompt avoids double-enrichment
- generate_stream falls back to generate_response
- search raises NotImplementedError by default
"""

import pytest
from unittest.mock import MagicMock
from jarvis.ai.llm_client import LLMClient, MockLLMClient


class TestMockLLMClient:
    def test_returns_mock_response(self):
        client = MockLLMClient()
        resp = client.generate_response("anything")
        assert "mock response" in resp.lower()
        assert "no API key" in resp

    def test_generate_stream_yields_response(self):
        client = MockLLMClient()
        chunks = list(client.generate_stream("anything"))
        assert len(chunks) == 1
        assert "mock" in chunks[0].lower()


class TestEnrichPrompt:
    def test_no_memory_returns_prompt_unchanged(self):
        client = MockLLMClient()
        assert client.enrich_prompt("hello") == "hello"

    def test_empty_prompt_returns_empty(self):
        client = MockLLMClient()
        assert client.enrich_prompt("") == ""

    def test_skip_memory_returns_unchanged(self):
        client = MockLLMClient()
        mem = MagicMock()
        mem.query_memory.return_value = "some context"
        client.set_memory_client(mem)
        assert client.enrich_prompt("hello", skip_memory=True) == "hello"
        mem.query_memory.assert_not_called()

    def test_memory_context_prepended(self):
        client = MockLLMClient()
        mem = MagicMock()
        mem.query_memory.return_value = "You previously installed docker"
        client.set_memory_client(mem)
        enriched = client.enrich_prompt("install docker")
        assert "MEMORY CONTEXT" in enriched
        assert "You previously installed docker" in enriched
        assert "install docker" in enriched

    def test_no_double_enrichment(self):
        client = MockLLMClient()
        mem = MagicMock()
        mem.query_memory.return_value = "context"
        client.set_memory_client(mem)
        already_enriched = "--- MEMORY CONTEXT ---\nold\n--- END MEMORY ---\n\nhello"
        result = client.enrich_prompt(already_enriched)
        assert result == already_enriched
        mem.query_memory.assert_not_called()

    def test_empty_memory_response_no_prefix(self):
        client = MockLLMClient()
        mem = MagicMock()
        mem.query_memory.return_value = ""
        client.set_memory_client(mem)
        result = client.enrich_prompt("hello")
        assert result == "hello"

    def test_memory_exception_returns_original(self):
        client = MockLLMClient()
        mem = MagicMock()
        mem.query_memory.side_effect = Exception("API down")
        client.set_memory_client(mem)
        result = client.enrich_prompt("hello")
        assert result == "hello"


class TestSetMemoryClient:
    def test_sets_memory_client(self):
        client = MockLLMClient()
        mem = MagicMock()
        client.set_memory_client(mem)
        assert client.memory_client is mem


class TestSearch:
    def test_search_raises_not_implemented(self):
        client = MockLLMClient()
        with pytest.raises(NotImplementedError):
            client.search("test query")
