"""Tests for jarvis.core.model_catalog — shared task/model catalog."""

from jarvis.core.model_catalog import (
    apply_stored_task_models,
    choices_for_task,
    key_flags_from_onboarding,
    resolve_provider_for_model,
)
from jarvis.core.config_manager import NexusConfig


def test_key_flags_groq_backs_groq_gpt():
    f = key_flags_from_onboarding("x", "x", "groq-secret", "")
    assert f["groq_api_key"] is True
    assert f["groq_gpt_api_key"] is True


def test_choices_for_task_respects_keys():
    flags = {
        "google_api_key": True,
        "openrouter_api_key": False,
        "groq_api_key": False,
        "groq_gpt_api_key": False,
        "anthropic_api_key": False,
    }
    chat = choices_for_task("chat", flags)
    ids = [m for _, m in chat]
    assert "gemini-2.5-flash" in ids
    assert not any("openai/gpt-oss-120b:free" in m for m in ids)


def test_resolve_provider_for_model():
    assert (
        resolve_provider_for_model("chat", "openai/gpt-oss-120b:free")
        == "OpenRouterClient"
    )
    assert resolve_provider_for_model("router", "nope") is None


def test_apply_stored_task_models_updates_primary():
    from jarvis.ai.llm_client import OpenRouterClient, GroqClient

    or1 = OpenRouterClient(api_key="k", model="openai/gpt-oss-120b:free")
    gq = GroqClient(api_key="k2")
    fallbacks = [or1, gq]
    cfg = NexusConfig()
    cfg.chat_model = "moonshotai/kimi-k2-instruct-0905"
    llm, router = apply_stored_task_models(cfg, or1, gq, fallbacks)
    assert llm is gq
    assert llm.model == "moonshotai/kimi-k2-instruct-0905"


def test_apply_skips_unknown_model_id():
    from jarvis.ai.llm_client import OpenRouterClient

    or1 = OpenRouterClient(api_key="k", model="openai/gpt-oss-120b:free")
    cfg = NexusConfig()
    cfg.chat_model = "totally/fake-model:xyz"
    llm, _ = apply_stored_task_models(cfg, or1, None, [or1])
    assert llm is or1
    assert llm.model == "openai/gpt-oss-120b:free"


def test_shared_llm_router_skips_second_model_when_chat_applied():
    from jarvis.ai.llm_client import GroqClient

    gq = GroqClient(api_key="k")
    cfg = NexusConfig()
    cfg.chat_model = "moonshotai/kimi-k2-instruct-0905"
    cfg.router_model = "moonshotai/kimi-k2-instruct-0905"
    llm, router = apply_stored_task_models(cfg, gq, gq, [gq])
    assert llm is gq is router
    assert llm.model == "moonshotai/kimi-k2-instruct-0905"
