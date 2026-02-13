from __future__ import annotations

import logging
from typing import Callable

from src.adapters.base import Adapter
from src.config import AdaptersConfig

logger = logging.getLogger(__name__)


class AdapterRegistry:
    """Registry for managing communication adapters.

    Discovers, loads, and routes messages to adapters based on channel ID.
    """

    def __init__(self) -> None:
        self._adapters: dict[str, Adapter] = {}

    def register(self, adapter: Adapter) -> None:
        """Register an adapter."""
        self._adapters[adapter.id] = adapter

    def get_adapter(self, channel_id: str) -> Adapter | None:
        """Get an adapter by its channel ID."""
        return self._adapters.get(channel_id)

    def send(self, channel_id: str, to: str, message: str) -> bool:
        """Route a message to the correct adapter.

        Returns True if the message was sent, False if the adapter was not found.
        """
        adapter = self._adapters.get(channel_id)
        if adapter is None:
            logger.warning("No adapter found for channel: %s", channel_id)
            return False
        adapter.send(to, message)
        return True

    def start_all(self, callback: Callable[[str, str], str]) -> None:
        """Start listeners on all registered adapters."""
        for adapter in self._adapters.values():
            adapter.listen(callback)

    def stop_all(self) -> None:
        """Stop all registered adapters."""
        for adapter in self._adapters.values():
            adapter.stop()

    @property
    def adapter_ids(self) -> list[str]:
        """List all registered adapter IDs."""
        return list(self._adapters.keys())

    @classmethod
    def from_config(cls, config: AdaptersConfig) -> AdapterRegistry:
        """Create a registry with adapters based on configuration."""
        from src.adapters.terminal import TerminalAdapter
        from src.adapters.whatsapp import WhatsAppAdapter

        registry = cls()

        if config.terminal.enabled:
            registry.register(TerminalAdapter())

        if config.whatsapp.enabled:
            registry.register(WhatsAppAdapter())

        return registry
