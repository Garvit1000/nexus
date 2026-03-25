"""
Tests for jarvis.ai.command_generator — CommandGenerator.

Verifies that:
- A valid LLM response is returned as a cleaned command
- Markdown fences are stripped from the response
- Unsafe generated commands raise SecurityViolation
- Memory client is invoked when present
- Prompt contains system info
"""

import pytest
from unittest.mock import MagicMock, patch
from jarvis.ai.command_generator import CommandGenerator
from jarvis.core.security import SecurityViolation
from jarvis.core.system_detector import SystemInfo, PackageManager


def _mock_llm(response: str = "echo hello", memory_client=None):
    client = MagicMock()
    client.generate_response.return_value = response
    client.memory_client = memory_client
    return client


def _sys_info():
    return SystemInfo(
        os_name="Ubuntu", os_version="24.04", package_manager=PackageManager.APT
    )


class TestCommandGeneration:
    def test_returns_cleaned_command(self):
        gen = CommandGenerator(_mock_llm("echo hello"), _sys_info())
        cmd = gen.generate_command("say hello")
        assert cmd == "echo hello"

    def test_strips_markdown_fences(self):
        gen = CommandGenerator(_mock_llm("```bash\nls -la\n```"), _sys_info())
        cmd = gen.generate_command("list files")
        assert cmd == "ls -la"

    def test_strips_inline_backticks(self):
        gen = CommandGenerator(_mock_llm("`docker ps`"), _sys_info())
        cmd = gen.generate_command("show containers")
        assert cmd == "docker ps"

    def test_whitespace_trimmed(self):
        gen = CommandGenerator(_mock_llm("  echo test  \n"), _sys_info())
        cmd = gen.generate_command("test")
        assert cmd == "echo test"


class TestSecurityValidation:
    def test_unsafe_command_raises(self):
        gen = CommandGenerator(_mock_llm("rm -rf /"), _sys_info())
        with pytest.raises(SecurityViolation):
            gen.generate_command("delete everything")

    def test_safe_command_passes(self):
        gen = CommandGenerator(_mock_llm("ls /tmp"), _sys_info())
        cmd = gen.generate_command("list tmp")
        assert cmd == "ls /tmp"


class TestMemoryIntegration:
    def test_memory_add_called_on_success(self):
        mem = MagicMock()
        mem.query_memory.return_value = ""
        gen = CommandGenerator(_mock_llm("echo ok", memory_client=mem), _sys_info())
        gen.generate_command("say ok")
        mem.add_memory.assert_called_once()

    def test_memory_query_used_in_prompt(self):
        mem = MagicMock()
        mem.query_memory.return_value = "Use apt-get for Ubuntu"
        llm = _mock_llm("apt-get update", memory_client=mem)
        gen = CommandGenerator(llm, _sys_info())
        gen.generate_command("update system")
        mem.query_memory.assert_called_once()

    def test_no_memory_client_skips_memory(self):
        gen = CommandGenerator(_mock_llm("echo hi"), _sys_info())
        cmd = gen.generate_command("say hi")
        assert cmd == "echo hi"


class TestFallbackClients:
    @patch("jarvis.ai.command_generator.time.sleep")
    def test_tries_fallback_on_primary_failure(self, _mock_sleep):
        primary = MagicMock()
        # Non-transient error: skip per-client retries, go straight to fallback.
        primary.generate_response.side_effect = RuntimeError("invalid_api_key 401")
        fallback = MagicMock()
        fallback.generate_response.return_value = "echo recovered"
        gen = CommandGenerator(primary, _sys_info(), fallback_clients=[fallback])
        cmd = gen.generate_command("say hi")
        assert cmd == "echo recovered"
        primary.generate_response.assert_called_once()
        fallback.generate_response.assert_called_once()

    @patch("jarvis.ai.command_generator.time.sleep")
    def test_retries_same_client_on_rate_limit_then_succeeds(self, _mock_sleep):
        primary = MagicMock()
        primary.generate_response.side_effect = [
            RuntimeError("Error 429: rate limit exceeded"),
            RuntimeError("Error 429: rate limit exceeded"),
            "echo third_try",
        ]
        gen = CommandGenerator(primary, _sys_info(), fallback_clients=[])
        cmd = gen.generate_command("say hi")
        assert cmd == "echo third_try"
        assert primary.generate_response.call_count == 3

    @patch("jarvis.ai.command_generator.time.sleep")
    def test_empty_response_then_fallback(self, _mock_sleep):
        primary = MagicMock()
        primary.generate_response.side_effect = ["", "   ", "\n"]
        fallback = MagicMock()
        fallback.generate_response.return_value = "echo from_fallback"
        gen = CommandGenerator(primary, _sys_info(), fallback_clients=[fallback])
        cmd = gen.generate_command("say hi")
        assert cmd == "echo from_fallback"
        assert primary.generate_response.call_count == 3
        fallback.generate_response.assert_called_once()

    @patch("jarvis.ai.command_generator.time.sleep")
    def test_fallback_memory_client_receives_add_memory(self, _mock_sleep):
        """Gemini: store command-gen memory on the client that succeeded, not only primary."""
        primary = MagicMock()
        primary.generate_response.side_effect = RuntimeError("401 invalid")
        primary_mem = MagicMock()
        primary.memory_client = primary_mem
        fallback = MagicMock()
        fallback.generate_response.return_value = "echo fb"
        fb_mem = MagicMock()
        fallback.memory_client = fb_mem
        gen = CommandGenerator(primary, _sys_info(), fallback_clients=[fallback])
        gen.generate_command("x")
        primary_mem.add_memory.assert_not_called()
        fb_mem.add_memory.assert_called_once()

    def test_dedupes_same_client_in_fallback_list(self):
        shared = _mock_llm("echo once")
        gen = CommandGenerator(shared, _sys_info(), fallback_clients=[shared])
        cmd = gen.generate_command("x")
        assert cmd == "echo once"
        assert shared.generate_response.call_count == 1


class TestPromptContent:
    def test_prompt_contains_os_info(self):
        llm = _mock_llm("echo test")
        gen = CommandGenerator(llm, _sys_info())
        gen.generate_command("test")
        prompt = llm.generate_response.call_args[0][0]
        assert "Ubuntu" in prompt
        assert "apt" in prompt.lower()

    def test_prompt_contains_user_request(self):
        llm = _mock_llm("echo test")
        gen = CommandGenerator(llm, _sys_info())
        gen.generate_command("restart nginx server")
        prompt = llm.generate_response.call_args[0][0]
        assert "restart nginx server" in prompt
