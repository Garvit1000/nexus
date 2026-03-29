"""
Single source of truth for per-task LLM model options.

Used by /settings, onboarding, and startup application of saved preferences.
"""

from __future__ import annotations

from typing import Any, Optional

# Mirrors NexusConfig / .env field names for API keys.
TASK_MODEL_OPTIONS: dict[str, dict[str, Any]] = {
    "chat": {
        "label": "Chat / Planning / /do",
        "models": {
            "openrouter_api_key": {
                "provider": "OpenRouterClient",
                "items": [
                    "openai/gpt-oss-120b:free",
                    "moonshotai/kimi-k2-0905",
                ],
            },
            "anthropic_api_key": {
                "provider": "AnthropicClient",
                "items": [
                    "claude-sonnet-4-20250514",
                ],
            },
            "groq_gpt_api_key": {
                "provider": "GroqGPTClient",
                "items": [
                    "openai/gpt-oss-120b",
                ],
            },
            "groq_api_key": {
                "provider": "GroqClient",
                "items": [
                    "moonshotai/kimi-k2-instruct-0905",
                ],
            },
            "google_api_key": {
                "provider": "GoogleGenAIClient",
                "items": [
                    "gemini-2.5-flash",
                    "gemini-1.5-flash",
                    "gemini-flash-latest",
                ],
            },
        },
    },
    "router": {
        "label": "Router / Decision Engine",
        "models": {
            "groq_api_key": {
                "provider": "GroqClient",
                "items": [
                    "moonshotai/kimi-k2-instruct-0905",
                ],
            },
            "openrouter_api_key": {
                "provider": "OpenRouterClient",
                "items": [
                    "openai/gpt-oss-120b:free",
                    "moonshotai/kimi-k2-0905",
                ],
            },
            "google_api_key": {
                "provider": "GoogleGenAIClient",
                "items": [
                    "gemini-2.5-flash",
                    "gemini-1.5-flash",
                ],
            },
            "anthropic_api_key": {
                "provider": "AnthropicClient",
                "items": [
                    "claude-sonnet-4-20250514",
                ],
            },
            "groq_gpt_api_key": {
                "provider": "GroqGPTClient",
                "items": [
                    "openai/gpt-oss-120b",
                ],
            },
        },
    },
    "browser": {
        "label": "Browser Automation (/browse)",
        "models": {
            "google_api_key": {
                "provider": "GoogleGenAIClient",
                "items": [
                    "gemini-2.5-flash",
                    "gemini-1.5-flash",
                    "gemini-flash-latest",
                ],
            },
            "openrouter_api_key": {
                "provider": "OpenRouterClient",
                "items": [
                    "openai/gpt-oss-120b:free",
                ],
            },
        },
    },
}


def key_flags_from_onboarding(
    google_key: str,
    openrouter_key: str,
    groq_key: str,
    anthropic_key: str,
) -> dict[str, bool]:
    """Which config key fields are available after onboarding key entry."""
    g = bool(google_key and str(google_key).strip())
    o = bool(openrouter_key and str(openrouter_key).strip())
    q = bool(groq_key and str(groq_key).strip())
    a = bool(anthropic_key and str(anthropic_key).strip())
    return {
        "google_api_key": g,
        "openrouter_api_key": o,
        "groq_api_key": q,
        "groq_gpt_api_key": q,
        "anthropic_api_key": a,
    }


def choices_for_task(task: str, key_flags: dict[str, bool]) -> list[tuple[str, str]]:
    """Return [(display_label, model_id), ...] for Rich menus."""
    out: list[tuple[str, str]] = []
    task_info = TASK_MODEL_OPTIONS.get(task)
    if not task_info:
        return out
    for key_field, group in task_info["models"].items():
        if key_flags.get(key_field):
            for m in group["items"]:
                tag = group["provider"].replace("Client", "")
                out.append((f"{m} ({tag})", m))
    return out


def resolve_provider_for_model(task_name: str, model_name: str) -> Optional[str]:
    task_info = TASK_MODEL_OPTIONS.get(task_name)
    if not task_info:
        return None
    for _key_field, group in task_info["models"].items():
        if model_name in group["items"]:
            return group["provider"]
    return None


def find_client_for_provider(
    fallback_clients: list,
    router_client: Any,
    provider_class_name: str,
) -> Any:
    for client in fallback_clients:
        if client and type(client).__name__ == provider_class_name:
            return client
    if router_client and type(router_client).__name__ == provider_class_name:
        return router_client
    return None


def apply_stored_task_models(
    config: Any,
    llm_client: Any,
    router_client: Any,
    fallback_clients: list,
) -> tuple[Any, Any]:
    """
    Apply config.chat_model and config.router_model the same way /settings model does.
    Returns (llm_client, router_client), possibly reassigned.
    """
    out_llm, out_router = llm_client, router_client

    def get_target(task: str) -> Any:
        if task == "chat":
            return out_llm
        if task == "router":
            return out_router
        return None

    def set_primary_chat(client: Any) -> None:
        nonlocal out_llm
        out_llm = client

    def set_router(client: Any) -> None:
        nonlocal out_router
        out_router = client

    chat_branch_updated = False

    for task, attr in (("chat", "chat_model"), ("router", "router_model")):
        model_name = getattr(config, attr, None)
        if not model_name or not str(model_name).strip():
            continue
        model_name = str(model_name).strip()
        target_provider = resolve_provider_for_model(task, model_name)
        # Do not assign unknown IDs to whatever client we happen to hold (avoids
        # e.g. OpenRouter getting a Claude model string from a typo in config).
        if not target_provider:
            continue

        old_target = get_target(task)
        old_provider = type(old_target).__name__ if old_target else None

        # Router and primary chat can be the same GroqClient when only Groq keys
        # exist; applying both would make the second .model win. If we already
        # applied chat_model on that shared instance, skip router_model here.
        if (
            task == "router"
            and out_router is not None
            and out_router is out_llm
            and chat_branch_updated
        ):
            continue

        new_client = old_target
        if old_provider != target_provider:
            candidate = find_client_for_provider(
                fallback_clients, out_router, target_provider
            )
            if candidate:
                new_client = candidate

        if not new_client:
            continue

        new_client.model = model_name
        if task == "chat":
            set_primary_chat(new_client)
            chat_branch_updated = True
        else:
            set_router(new_client)

    return out_llm, out_router
