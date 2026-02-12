from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class MemoryConfig:
    dir: str = "memory"
    db_path: str = "data/memory.db"
    chunk_tokens: int = 2000
    chunk_overlap: int = 200
    search_top_k: int = 5
    vector_weight: float = 0.7
    text_weight: float = 0.3
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    watch: bool = True
    watch_debounce_seconds: int = 5


@dataclass
class GmailConfig:
    enabled: bool = False
    poll_interval_minutes: int = 15


@dataclass
class CalendarConfig:
    enabled: bool = False
    poll_interval_minutes: int = 15
    hours_ahead: int = 24


@dataclass
class DailySummaryConfig:
    enabled: bool = False
    time: str = "08:00"


@dataclass
class HeartbeatConfig:
    enabled: bool = False
    gmail: GmailConfig = field(default_factory=GmailConfig)
    calendar: CalendarConfig = field(default_factory=CalendarConfig)
    daily_summary: DailySummaryConfig = field(default_factory=DailySummaryConfig)


@dataclass
class NotificationsConfig:
    urgent_email: str = "whatsapp"
    calendar_reminder: str = "whatsapp"
    daily_summary: str = "terminal"
    default: str = "terminal"


@dataclass
class TerminalAdapterConfig:
    enabled: bool = True


@dataclass
class WhatsAppAdapterConfig:
    enabled: bool = False


@dataclass
class AdaptersConfig:
    terminal: TerminalAdapterConfig = field(default_factory=TerminalAdapterConfig)
    whatsapp: WhatsAppAdapterConfig = field(default_factory=WhatsAppAdapterConfig)


@dataclass
class SkillsConfig:
    dir: str = "skills"


@dataclass
class AgentConfig:
    model: str = "claude-sonnet-4-20250514"
    session_timeout_minutes: int = 30


@dataclass
class GoogleConfig:
    credentials_path: str = "credentials.json"
    token_path: str = "token.json"


@dataclass
class Config:
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    heartbeat: HeartbeatConfig = field(default_factory=HeartbeatConfig)
    notifications: NotificationsConfig = field(default_factory=NotificationsConfig)
    adapters: AdaptersConfig = field(default_factory=AdaptersConfig)
    skills: SkillsConfig = field(default_factory=SkillsConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    google: GoogleConfig = field(default_factory=GoogleConfig)


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge override into base, recursively for nested dicts."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _apply_env_overrides(raw: dict[str, Any]) -> dict[str, Any]:
    """Override config values with environment variables."""
    env_map = {
        "ANTHROPIC_API_KEY": None,  # handled by SDK directly
        "PYCLAW_GOOGLE_CREDENTIALS_PATH": ("google", "credentials_path"),
        "PYCLAW_GOOGLE_TOKEN_PATH": ("google", "token_path"),
        "PYCLAW_MEMORY_DIR": ("memory", "dir"),
        "PYCLAW_MEMORY_DB_PATH": ("memory", "db_path"),
        "PYCLAW_SKILLS_DIR": ("skills", "dir"),
        "PYCLAW_AGENT_MODEL": ("agent", "model"),
    }
    for env_var, path in env_map.items():
        value = os.environ.get(env_var)
        if value is None or path is None:
            continue
        section, key = path
        if section not in raw:
            raw[section] = {}
        raw[section][key] = value
    return raw


def _build_nested_config(cls: type, data: dict[str, Any] | None) -> Any:
    """Recursively build a dataclass from a dict."""
    if data is None:
        return cls()
    kwargs = {}
    for f in cls.__dataclass_fields__.values():
        if f.name not in data:
            continue
        value = data[f.name]
        if hasattr(f.type, "__dataclass_fields__") if isinstance(f.type, type) else False:
            kwargs[f.name] = _build_nested_config(f.type, value)
        else:
            # Resolve string type annotations for nested dataclasses
            resolved_type = cls.__dataclass_fields__[f.name].type
            if isinstance(resolved_type, str):
                resolved_type = globals().get(resolved_type) or locals().get(resolved_type)
            if isinstance(resolved_type, type) and hasattr(resolved_type, "__dataclass_fields__"):
                kwargs[f.name] = _build_nested_config(resolved_type, value)
            else:
                kwargs[f.name] = value
    return cls(**kwargs)


_NESTED_TYPES = {
    "memory": MemoryConfig,
    "heartbeat": HeartbeatConfig,
    "notifications": NotificationsConfig,
    "adapters": AdaptersConfig,
    "skills": SkillsConfig,
    "agent": AgentConfig,
    "google": GoogleConfig,
}

_HEARTBEAT_NESTED = {
    "gmail": GmailConfig,
    "calendar": CalendarConfig,
    "daily_summary": DailySummaryConfig,
}

_ADAPTERS_NESTED = {
    "terminal": TerminalAdapterConfig,
    "whatsapp": WhatsAppAdapterConfig,
}


def _dict_to_config(raw: dict[str, Any]) -> Config:
    """Convert a raw dict to a Config dataclass."""
    kwargs: dict[str, Any] = {}
    for section_name, section_cls in _NESTED_TYPES.items():
        section_data = raw.get(section_name)
        if section_data is None:
            continue

        if section_name == "heartbeat" and isinstance(section_data, dict):
            hb_kwargs: dict[str, Any] = {}
            for k, v in section_data.items():
                if k in _HEARTBEAT_NESTED and isinstance(v, dict):
                    hb_kwargs[k] = _HEARTBEAT_NESTED[k](**v)
                else:
                    hb_kwargs[k] = v
            kwargs[section_name] = HeartbeatConfig(**hb_kwargs)
        elif section_name == "adapters" and isinstance(section_data, dict):
            adp_kwargs: dict[str, Any] = {}
            for k, v in section_data.items():
                if k in _ADAPTERS_NESTED and isinstance(v, dict):
                    adp_kwargs[k] = _ADAPTERS_NESTED[k](**v)
                else:
                    adp_kwargs[k] = v
            kwargs[section_name] = AdaptersConfig(**adp_kwargs)
        elif isinstance(section_data, dict):
            kwargs[section_name] = section_cls(**section_data)
        else:
            kwargs[section_name] = section_data

    return Config(**kwargs)


def load_config(config_path: str | Path = "config.yaml") -> Config:
    """Load configuration from a YAML file with env var overrides.

    If the file doesn't exist, returns default config.
    """
    config_path = Path(config_path)
    raw: dict[str, Any] = {}

    if config_path.exists():
        with open(config_path) as f:
            loaded = yaml.safe_load(f)
            if isinstance(loaded, dict):
                raw = loaded

    raw = _apply_env_overrides(raw)
    return _dict_to_config(raw)
