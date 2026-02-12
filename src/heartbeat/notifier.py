from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.adapters.registry import AdapterRegistry
    from src.config import NotificationsConfig


class Notifier:
    """Routes notifications to the correct adapter based on notification type."""

    def __init__(
        self,
        config: NotificationsConfig,
        adapter_registry: AdapterRegistry,
    ) -> None:
        self._config = config
        self._registry = adapter_registry

    def notify(self, notification_type: str, message: str, to: str = "user") -> None:
        """Send a notification via the configured channel for this type.

        Falls back to the default channel if the type is not explicitly configured.
        """
        channel = self._resolve_channel(notification_type)
        self._registry.send(channel, to, message)

    def _resolve_channel(self, notification_type: str) -> str:
        """Look up which channel to use for a given notification type."""
        # Check if there's a specific mapping for this type
        channel = getattr(self._config, notification_type, None)
        if channel and isinstance(channel, str):
            return channel
        # Fall back to default
        return self._config.default
