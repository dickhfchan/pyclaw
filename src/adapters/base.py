from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable


class Adapter(ABC):
    """Abstract base class for communication channel adapters."""

    id: str
    name: str

    @abstractmethod
    def send(self, to: str, message: str) -> None:
        """Send a message to the specified recipient."""
        ...

    @abstractmethod
    def listen(self, callback: Callable[[str, str], str]) -> None:
        """Start listening for incoming messages.

        The callback receives (sender, message) and returns a response string.
        """
        ...

    @abstractmethod
    def stop(self) -> None:
        """Stop the adapter and clean up resources."""
        ...
