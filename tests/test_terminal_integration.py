"""Integration test for the terminal adapter end-to-end flow.

Simulates user input -> agent callback -> response -> session logging.
"""
from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.adapters.terminal import TerminalAdapter
from src.session import SessionManager


@pytest.fixture
def session_mgr(tmp_path: Path):
    daily_dir = tmp_path / "daily"
    return SessionManager(timeout_minutes=30, daily_dir=daily_dir)


def test_terminal_oneshot_with_session(session_mgr):
    """One-shot mode processes a query and can log the session."""
    stdout = io.StringIO()
    adapter = TerminalAdapter(stdout=stdout)
    session = session_mgr.create_session()

    def callback(sender: str, message: str) -> str:
        session_mgr.add_exchange(
            session.id,
            message,
            f"Response to: {message}",
            [{"role": "user", "content": message}],
        )
        return f"Response to: {message}"

    result = adapter.ask("What is pyclaw?", callback)
    assert result == "Response to: What is pyclaw?"
    assert "Response to: What is pyclaw?" in stdout.getvalue()

    # Log and close
    session_mgr.log_and_close(
        session.id,
        query_summary="What is pyclaw?",
        response_summary="Response to: What is pyclaw?",
    )

    # Verify daily log was written
    daily_files = list(session_mgr.daily_dir.glob("*.md"))
    assert len(daily_files) == 1
    content = daily_files[0].read_text()
    assert "What is pyclaw?" in content


def test_terminal_interactive_with_session(session_mgr):
    """Interactive mode processes multiple messages and logs session."""
    stdin = io.StringIO("hello\nhow are you?\n")
    stdout = io.StringIO()
    adapter = TerminalAdapter(stdin=stdin, stdout=stdout)
    session = session_mgr.create_session()
    exchanges: list[tuple[str, str]] = []

    def callback(sender: str, message: str) -> str:
        response = f"Echo: {message}"
        exchanges.append((message, response))
        session_mgr.add_exchange(session.id, message, response)
        return response

    adapter.listen(callback)

    assert len(exchanges) == 2
    assert exchanges[0] == ("hello", "Echo: hello")
    assert exchanges[1] == ("how are you?", "Echo: how are you?")

    output = stdout.getvalue()
    assert "Echo: hello" in output
    assert "Echo: how are you?" in output


def test_adapter_registry_routes_send():
    """Verify the registry correctly routes messages."""
    from src.adapters.registry import AdapterRegistry

    registry = AdapterRegistry()
    terminal = TerminalAdapter(stdout=io.StringIO())
    registry.register(terminal)

    result = registry.send("terminal", "user", "Test notification")
    assert result is True

    result = registry.send("nonexistent", "user", "Test")
    assert result is False
