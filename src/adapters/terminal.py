from __future__ import annotations

import os
import sys
from typing import Callable, TextIO

from src.adapters.base import Adapter

try:
    import readline  # noqa: F401 - enables arrow keys and history when using input()
except ImportError:
    readline = None  # Windows may not have readline

_DEFAULT_HISTORY_PATH = os.path.expanduser("~/.pyclaw_history")
_READLINE_HISTORY_LEN = 100


class TerminalAdapter(Adapter):
    """Terminal adapter for interactive and one-shot CLI interaction.

    With readline available (Unix/macOS), supports arrow keys for line editing
    and up/down for input history. History is persisted to ~/.pyclaw_history.
    """

    id: str = "terminal"
    name: str = "Terminal"

    def __init__(
        self,
        stdin: TextIO | None = None,
        stdout: TextIO | None = None,
        history_path: str | None = None,
    ) -> None:
        self._stdin = stdin or sys.stdin
        self._stdout = stdout or sys.stdout
        self._history_path = history_path or _DEFAULT_HISTORY_PATH
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
        if readline and self._stdin is sys.stdin:
            self._stdout.write("      (Arrow keys: edit line; Up/Down: history)\n")
        self._stdout.flush()

        if readline:
            try:
                readline.read_history_file(self._history_path)
            except OSError:
                pass
            readline.set_history_length(_READLINE_HISTORY_LEN)

        while self._running:
            try:
                self._stdout.write("\nyou> ")
                self._stdout.flush()
                if readline and self._stdin is sys.stdin:
                    line = input().strip()
                else:
                    line = self._stdin.readline()
                    if not line:
                        break
                    line = line.strip()
                if not line:
                    continue
                if readline and self._stdin is sys.stdin:
                    readline.add_history(line)
                response = callback("user", line)
                self._stdout.write(f"\npyclaw> {response}\n")
                self._stdout.flush()
            except (KeyboardInterrupt, EOFError):
                break

        if readline:
            try:
                readline.write_history_file(self._history_path)
            except OSError:
                pass
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
