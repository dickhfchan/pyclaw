from __future__ import annotations

import logging
from enum import Enum
from typing import Any, Callable

from src.adapters.base import Adapter

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"


class WhatsAppAdapter(Adapter):
    """WhatsApp adapter for sending and receiving text messages.

    Uses a WhatsApp messaging library for communication.
    QR code pairing is required for initial setup.
    """

    id: str = "whatsapp"
    name: str = "WhatsApp"

    def __init__(self, client: Any = None) -> None:
        self._client = client
        self._state = ConnectionState.DISCONNECTED
        self._callback: Callable[[str, str], str] | None = None

    @property
    def state(self) -> ConnectionState:
        return self._state

    def connect(self) -> None:
        """Connect to WhatsApp (triggers QR pairing if needed)."""
        if self._client is None:
            logger.warning("No WhatsApp client configured. Install a WhatsApp library to enable.")
            return
        self._state = ConnectionState.CONNECTING
        try:
            self._client.connect()
            self._state = ConnectionState.CONNECTED
        except Exception:
            logger.exception("Failed to connect to WhatsApp")
            self._state = ConnectionState.DISCONNECTED
            raise

    def send(self, to: str, message: str) -> None:
        """Send a text message via WhatsApp."""
        if self._client is None:
            logger.warning("WhatsApp client not configured, message not sent: %s", message)
            return
        if self._state != ConnectionState.CONNECTED:
            logger.warning("WhatsApp not connected, message not sent: %s", message)
            return
        self._client.send_message(to, message)

    def listen(self, callback: Callable[[str, str], str]) -> None:
        """Start listening for incoming WhatsApp messages."""
        self._callback = callback
        if self._client is None:
            logger.warning("WhatsApp client not configured, cannot listen.")
            return

        def _on_message(sender: str, message: str) -> None:
            if self._callback:
                response = self._callback(sender, message)
                self.send(sender, response)

        self._client.on_message(_on_message)

    def stop(self) -> None:
        """Disconnect from WhatsApp."""
        if self._client is not None and self._state == ConnectionState.CONNECTED:
            try:
                self._client.disconnect()
            except Exception:
                logger.exception("Error disconnecting from WhatsApp")
        self._state = ConnectionState.DISCONNECTED
        self._callback = None
