from __future__ import annotations

import sys
from typing import Callable, TextIO

from src.adapters.base import Adapter


class TerminalAdapter(Adapter):
    """Terminal adapter for interactive and one-shot CLI interaction."""

    id: str = "terminal"
    name: str = "Terminal"

    def __init__(
        self,
        stdin: TextIO | None = None,
        stdout: TextIO | None = None,
    ) -> None:
        self._stdin = stdin or sys.stdin
        self._stdout = stdout or sys.stdout
        self._running = False
        self._callback: Callable[[str, str], str] | None = None

    def send(self, to: str, message: str) -> None:
        """Print a message to stdout."""
        self._stdout.write(f"\n{message}\n")
        self._stdout.flush()

    def listen(self, callback: Callable[[str, str], str]) -> None:
        """Start interactive mode — read from stdin in a loop."""
        self._callback = callback
        self._running = True
        self._stdout.write("pyclaw> Type a message (Ctrl+C to quit)\n")
        self._stdout.flush()

        while self._running:
            try:
                self._stdout.write("\nyou> ")
                self._stdout.flush()
                line = self._stdin.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                response = callback("user", line)
                self._stdout.write(f"\npyclaw> {response}\n")
                self._stdout.flush()
            except (KeyboardInterrupt, EOFError):
                break

        self._running = False

    def stop(self) -> None:
        """Stop the interactive loop."""
        self._running = False

    def ask(self, query: str, callback: Callable[[str, str], str]) -> str:
        """One-shot mode: send a single query and return the response."""
        response = callback("user", query)
        self._stdout.write(f"{response}\n")
        self._stdout.flush()
        return response
