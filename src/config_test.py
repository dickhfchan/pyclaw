from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from src.config import Config, load_config, _load_dotenv


def _write_yaml(path: Path, data: dict) -> None:
    with open(path, "w") as f:
        yaml.dump(data, f)


class TestLoadConfig:
    def test_defaults_when_no_file(self, tmp_path: Path) -> None:
        cfg = load_config(tmp_path / "nonexistent.yaml")
        assert isinstance(cfg, Config)
        assert cfg.memory.dir == "memory"
        assert cfg.memory.chunk_tokens == 2000
        assert cfg.agent.provider == "AZURE_OPENAI"
        assert cfg.agent.model == "gpt-5"
        assert cfg.heartbeat.enabled is False
        assert cfg.adapters.terminal.enabled is True
        assert cfg.adapters.whatsapp.enabled is False

    def test_loads_from_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # So file value wins: don't load .env and clear env overrides for agent.model
        monkeypatch.setattr("src.config._load_dotenv", lambda _env_path=None: None)
        monkeypatch.delenv("AZURE_OPENAI_DEPLOYMENT_NAME", raising=False)
        monkeypatch.delenv("PYCLAW_AGENT_MODEL", raising=False)
        config_file = tmp_path / "config.yaml"
        _write_yaml(config_file, {
            "memory": {"dir": "custom_memory", "chunk_tokens": 1000},
            "agent": {"model": "claude-opus-4-20250514"},
        })
        cfg = load_config(config_file)
        assert cfg.memory.dir == "custom_memory"
        assert cfg.memory.chunk_tokens == 1000
        assert cfg.agent.model == "claude-opus-4-20250514"
        # Defaults for unspecified fields
        assert cfg.memory.vector_weight == 0.7
        assert cfg.heartbeat.enabled is False

    def test_nested_heartbeat_config(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        _write_yaml(config_file, {
            "heartbeat": {
                "enabled": True,
                "gmail": {"enabled": True, "poll_interval_minutes": 5},
                "calendar": {"enabled": True, "hours_ahead": 48},
                "daily_summary": {"enabled": True, "time": "09:30"},
            },
        })
        cfg = load_config(config_file)
        assert cfg.heartbeat.enabled is True
        assert cfg.heartbeat.gmail.enabled is True
        assert cfg.heartbeat.gmail.poll_interval_minutes == 5
        assert cfg.heartbeat.calendar.hours_ahead == 48
        assert cfg.heartbeat.daily_summary.time == "09:30"

    def test_nested_adapters_config(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        _write_yaml(config_file, {
            "adapters": {
                "terminal": {"enabled": False},
                "whatsapp": {"enabled": True},
            },
        })
        cfg = load_config(config_file)
        assert cfg.adapters.terminal.enabled is False
        assert cfg.adapters.whatsapp.enabled is True

    def test_env_var_overrides(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        config_file = tmp_path / "config.yaml"
        _write_yaml(config_file, {
            "google": {"credentials_path": "original.json"},
        })
        monkeypatch.setenv("PYCLAW_GOOGLE_CREDENTIALS_PATH", "/override/creds.json")
        monkeypatch.setenv("PYCLAW_AGENT_MODEL", "claude-opus-4-20250514")
        cfg = load_config(config_file)
        assert cfg.google.credentials_path == "/override/creds.json"
        assert cfg.agent.model == "claude-opus-4-20250514"

    def test_empty_yaml_file(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        config_file.write_text("")
        cfg = load_config(config_file)
        assert isinstance(cfg, Config)
        assert cfg.memory.dir == "memory"

    def test_notifications_config(self, tmp_path: Path) -> None:
        config_file = tmp_path / "config.yaml"
        _write_yaml(config_file, {
            "notifications": {
                "urgent_email": "terminal",
                "daily_summary": "whatsapp",
            },
        })
        cfg = load_config(config_file)
        assert cfg.notifications.urgent_email == "terminal"
        assert cfg.notifications.daily_summary == "whatsapp"
        assert cfg.notifications.default == "terminal"

    def test_load_dotenv(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text(
            '# comment\n'
            'ANTHROPIC_API_KEY=sk-test-123\n'
            'MY_VAR="quoted value"\n'
            "SINGLE='single quoted'\n"
            'EMPTY_LINE=\n'
        )
        # Ensure keys aren't already set
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("MY_VAR", raising=False)
        monkeypatch.delenv("SINGLE", raising=False)

        _load_dotenv(env_file)

        assert os.environ["ANTHROPIC_API_KEY"] == "sk-test-123"
        assert os.environ["MY_VAR"] == "quoted value"
        assert os.environ["SINGLE"] == "single quoted"

    def test_load_dotenv_does_not_override(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("MY_KEY=from_file\n")
        monkeypatch.setenv("MY_KEY", "from_env")

        _load_dotenv(env_file)

        # Existing env var should NOT be overridden
        assert os.environ["MY_KEY"] == "from_env"
