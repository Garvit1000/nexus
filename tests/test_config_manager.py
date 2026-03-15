"""
Tests for jarvis.core.config_manager — ConfigManager and NexusConfig.

Verifies that:
- Default config is created when no file exists
- Config round-trips through save/load
- Environment variables override config file values
- Corrupted JSON is handled gracefully
- Config file permissions are set to 0o600
- update() persists changes to disk
"""

import json
import os
import stat
import pytest

from jarvis.core.config_manager import ConfigManager, NexusConfig


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    """Redirect config to a temp directory."""
    cfg_dir = tmp_path / "nexus_cfg"
    cfg_dir.mkdir()
    cfg_file = cfg_dir / "config.json"
    monkeypatch.setattr("jarvis.core.config_manager.CONFIG_DIR", cfg_dir)
    monkeypatch.setattr("jarvis.core.config_manager.CONFIG_FILE", cfg_file)
    return cfg_dir, cfg_file


class TestDefaultConfig:
    def test_default_config_created_when_no_file(self, config_dir):
        _, cfg_file = config_dir
        mgr = ConfigManager()
        assert isinstance(mgr.config, NexusConfig)
        assert mgr.config.dry_run is False
        assert mgr.config.onboarding_completed is False

    def test_default_model_provider(self, config_dir):
        mgr = ConfigManager()
        assert mgr.config.model_provider == "openrouter"


class TestConfigPersistence:
    def test_save_creates_file(self, config_dir):
        _, cfg_file = config_dir
        mgr = ConfigManager()
        mgr.config.onboarding_completed = True
        mgr.save_config()
        assert cfg_file.exists()

    def test_saved_config_round_trips(self, config_dir):
        _, cfg_file = config_dir
        mgr = ConfigManager()
        mgr.config.google_api_key = "test-key-123"
        mgr.config.dry_run = True
        mgr.save_config()

        mgr2 = ConfigManager()
        assert mgr2.config.google_api_key == "test-key-123"
        assert mgr2.config.dry_run is True

    def test_update_persists_to_disk(self, config_dir):
        _, cfg_file = config_dir
        mgr = ConfigManager()
        mgr.update(groq_api_key="groq-key-abc")

        mgr2 = ConfigManager()
        assert mgr2.config.groq_api_key == "groq-key-abc"

    def test_update_ignores_unknown_keys(self, config_dir):
        mgr = ConfigManager()
        mgr.update(nonexistent_field="value")
        assert not hasattr(mgr.config, "nonexistent_field")

    def test_config_file_permissions(self, config_dir):
        _, cfg_file = config_dir
        mgr = ConfigManager()
        mgr.save_config()
        mode = stat.S_IMODE(os.stat(cfg_file).st_mode)
        assert mode == 0o600


class TestEnvOverrides:
    def test_jarvis_api_key_overrides_config(self, config_dir, monkeypatch):
        _, cfg_file = config_dir
        mgr = ConfigManager()
        mgr.config.api_key = "from-file"
        mgr.save_config()

        monkeypatch.setenv("JARVIS_API_KEY", "from-env")
        mgr2 = ConfigManager()
        assert mgr2.config.api_key == "from-env"

    def test_dry_run_env_override(self, config_dir, monkeypatch):
        monkeypatch.setenv("JARVIS_DRY_RUN", "1")
        mgr = ConfigManager()
        assert mgr.config.dry_run is True

    def test_openrouter_key_env_override(self, config_dir, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "or-key")
        mgr = ConfigManager()
        assert mgr.config.openrouter_api_key == "or-key"


class TestCorruptedConfig:
    def test_corrupted_json_loads_defaults(self, config_dir):
        _, cfg_file = config_dir
        cfg_file.write_text("not valid json {{{")
        mgr = ConfigManager()
        assert mgr.config.dry_run is False
        assert mgr.config.onboarding_completed is False

    def test_empty_file_loads_defaults(self, config_dir):
        _, cfg_file = config_dir
        cfg_file.write_text("")
        mgr = ConfigManager()
        assert isinstance(mgr.config, NexusConfig)

    def test_extra_keys_in_json_ignored(self, config_dir):
        _, cfg_file = config_dir
        cfg_file.write_text(json.dumps({"dry_run": True, "unknown_key": "hello"}))
        mgr = ConfigManager()
        assert mgr.config.dry_run is True
