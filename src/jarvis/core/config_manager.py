import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser() / "nexus"
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class NexusConfig:
    dry_run: bool = False
    model_provider: str = "openrouter"  # Default to openrouter as it covers most cases
    api_key: Optional[str] = None  # Deprecated, kept for backward compat

    # Onboarding & Keys
    onboarding_completed: bool = False
    google_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    groq_gpt_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None

    # Memory
    use_supermemory: bool = False
    supermemory_api_key: Optional[str] = None

    dangerous_mode: bool = False  # Allow running without confirmation (not recommended)
    browser_use_api_key: Optional[str] = None


class ConfigManager:
    def __init__(self):
        self.config_file = CONFIG_FILE
        self._ensure_config_dir()
        self.config = self._load_config()

    def _ensure_config_dir(self):
        if not self.config_file.parent.exists():
            self.config_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_config(self) -> NexusConfig:
        config = NexusConfig()
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    data = json.load(f)
                    # Filter out keys that don't belong to NexusConfig
                    valid_keys = NexusConfig.__dataclass_fields__.keys()
                    filtered_data = {k: v for k, v in data.items() if k in valid_keys}
                    config = NexusConfig(**filtered_data)
            except (json.JSONDecodeError, TypeError):
                pass

        # Override with environment variables
        if os.getenv("JARVIS_API_KEY"):
            config.api_key = os.getenv("JARVIS_API_KEY")
        if os.getenv("JARVIS_MODEL_PROVIDER"):
            config.model_provider = str(os.getenv("JARVIS_MODEL_PROVIDER"))
        if os.getenv("JARVIS_DRY_RUN"):
            config.dry_run = os.getenv("JARVIS_DRY_RUN") == "1"
        if os.getenv("BROWSER_USE_API_KEY"):
            config.browser_use_api_key = os.getenv("BROWSER_USE_API_KEY")
        if os.getenv("OPENROUTER_API_KEY"):
            config.openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        if os.getenv("GOOGLE_API_KEY"):
            config.google_api_key = os.getenv("GOOGLE_API_KEY")
        if os.getenv("GROQ_API_KEY"):
            config.groq_api_key = os.getenv("GROQ_API_KEY")
        if os.getenv("GROQ_GPT_API_KEY"):
            config.groq_gpt_api_key = os.getenv("GROQ_GPT_API_KEY")
        if os.getenv("ANTHROPIC_API_KEY"):
            config.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        if os.getenv("SUPERMEMORY_API_KEY"):
            config.supermemory_api_key = os.getenv("SUPERMEMORY_API_KEY")
        return config

    def save_config(self):
        with open(self.config_file, "w") as f:
            json.dump(asdict(self.config), f, indent=4)
        try:
            os.chmod(self.config_file, 0o600)
        except OSError:
            pass

    def _update_env_file(self, **kwargs):
        try:
            from dotenv import set_key

            env_path = Path(".env").resolve()
            if not env_path.exists():
                return

            mapping = {
                "google_api_key": "GOOGLE_API_KEY",
                "openrouter_api_key": "OPENROUTER_API_KEY",
                "groq_api_key": "GROQ_API_KEY",
                "groq_gpt_api_key": "GROQ_GPT_API_KEY",
                "anthropic_api_key": "ANTHROPIC_API_KEY",
                "supermemory_api_key": "SUPERMEMORY_API_KEY",
                "browser_use_api_key": "BROWSER_USE_API_KEY",
                "api_key": "JARVIS_API_KEY",
                "model_provider": "JARVIS_MODEL_PROVIDER",
            }

            for key, value in kwargs.items():
                env_key = mapping.get(key)
                if env_key and value:
                    set_key(str(env_path), env_key, value)
        except Exception:
            pass

    def update(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        self.save_config()
        self._update_env_file(**kwargs)
