from __future__ import annotations

from unittest.mock import MagicMock

from src.adapters.base import Adapter
from src.adapters.registry import AdapterRegistry
from src.config import AdaptersConfig, TerminalAdapterConfig, WhatsAppAdapterConfig


def _make_mock_adapter(adapter_id: str) -> Adapter:
    adapter = MagicMock(spec=Adapter)
    adapter.id = adapter_id
    adapter.name = adapter_id.title()
    return adapter


def test_register_and_get() -> None:
    registry = AdapterRegistry()
    adapter = _make_mock_adapter("terminal")
    registry.register(adapter)
    assert registry.get_adapter("terminal") is adapter


def test_get_unknown_adapter() -> None:
    registry = AdapterRegistry()
    assert registry.get_adapter("nonexistent") is None


def test_send_routes_to_adapter() -> None:
    registry = AdapterRegistry()
    adapter = _make_mock_adapter("terminal")
    registry.register(adapter)

    result = registry.send("terminal", "user", "Hello!")
    assert result is True
    adapter.send.assert_called_once_with("user", "Hello!")


def test_send_unknown_channel() -> None:
    registry = AdapterRegistry()
    result = registry.send("nonexistent", "user", "Hello!")
    assert result is False


def test_adapter_ids() -> None:
    registry = AdapterRegistry()
    registry.register(_make_mock_adapter("terminal"))
    registry.register(_make_mock_adapter("whatsapp"))
    assert sorted(registry.adapter_ids) == ["terminal", "whatsapp"]


def test_stop_all() -> None:
    registry = AdapterRegistry()
    a1 = _make_mock_adapter("terminal")
    a2 = _make_mock_adapter("whatsapp")
    registry.register(a1)
    registry.register(a2)

    registry.stop_all()
    a1.stop.assert_called_once()
    a2.stop.assert_called_once()


def test_start_all() -> None:
    registry = AdapterRegistry()
    a1 = _make_mock_adapter("terminal")
    registry.register(a1)

    def callback(sender: str, message: str) -> str:
        return "ok"

    registry.start_all(callback)
    a1.listen.assert_called_once_with(callback)


def test_from_config_terminal_enabled() -> None:
    config = AdaptersConfig(
        terminal=TerminalAdapterConfig(enabled=True),
        whatsapp=WhatsAppAdapterConfig(enabled=False),
    )
    registry = AdapterRegistry.from_config(config)
    assert "terminal" in registry.adapter_ids
    assert "whatsapp" not in registry.adapter_ids


def test_from_config_both_disabled() -> None:
    config = AdaptersConfig(
        terminal=TerminalAdapterConfig(enabled=False),
        whatsapp=WhatsAppAdapterConfig(enabled=False),
    )
    registry = AdapterRegistry.from_config(config)
    assert registry.adapter_ids == []
