import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser() / "jarvis"
CONFIG_FILE = CONFIG_DIR / "config.json"

@dataclass
class JarvisConfig:
    dry_run: bool = False
    model_provider: str = "openrouter" # Default to openrouter as it covers most cases
    api_key: Optional[str] = None # Deprecated, kept for backward compat
    
    # Onboarding & Keys
    onboarding_completed: bool = False
    google_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    groq_gpt_api_key: Optional[str] = None
    
    # Memory
    use_supermemory: bool = False
    supermemory_api_key: Optional[str] = None
    
    dangerous_mode: bool = False # Allow running without confirmation (not recommended)
    browser_use_api_key: Optional[str] = None

class ConfigManager:
    def __init__(self):
        self.config_file = CONFIG_FILE
        self._ensure_config_dir()
        self.config = self._load_config()

    def _ensure_config_dir(self):
        if not self.config_file.parent.exists():
            self.config_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_config(self) -> JarvisConfig:
        config = JarvisConfig()
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    data = json.load(f)
                    # Filter out keys that don't belong to JarvisConfig
                    valid_keys = {k for k in JarvisConfig.__annotations__}
                    filtered_data = {k: v for k, v in data.items() if k in valid_keys}
                    config = JarvisConfig(**filtered_data)
            except (json.JSONDecodeError, TypeError):
                pass
        
        # Override with environment variables
        if os.getenv("JARVIS_API_KEY"):
            config.api_key = os.getenv("JARVIS_API_KEY")
        if os.getenv("JARVIS_MODEL_PROVIDER"):
            config.model_provider = os.getenv("JARVIS_MODEL_PROVIDER")
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
        if os.getenv("SUPERMEMORY_API_KEY"):
            config.supermemory_api_key = os.getenv("SUPERMEMORY_API_KEY")
        return config

    def save_config(self):
        with open(self.config_file, "w") as f:
            json.dump(asdict(self.config), f, indent=4)

    def update(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        self.save_config()
