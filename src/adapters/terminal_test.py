from __future__ import annotations

import io

from src.adapters.terminal import TerminalAdapter


def test_send_writes_to_stdout() -> None:
    stdout = io.StringIO()
    adapter = TerminalAdapter(stdout=stdout)
    adapter.send("user", "Hello there!")
    output = stdout.getvalue()
    assert "Hello there!" in output


def test_one_shot_mode() -> None:
    stdout = io.StringIO()
    adapter = TerminalAdapter(stdout=stdout)

    def callback(sender: str, message: str) -> str:
        return f"Echo: {message}"

    result = adapter.ask("What is pyclaw?", callback)
    assert result == "Echo: What is pyclaw?"
    assert "Echo: What is pyclaw?" in stdout.getvalue()


def test_listen_processes_input() -> None:
    stdin = io.StringIO("hello\n")
    stdout = io.StringIO()
    adapter = TerminalAdapter(stdin=stdin, stdout=stdout)

    responses: list[str] = []

    def callback(sender: str, message: str) -> str:
        responses.append(message)
        return f"Reply: {message}"

    adapter.listen(callback)

    assert responses == ["hello"]
    output = stdout.getvalue()
    assert "Reply: hello" in output


def test_listen_skips_empty_lines() -> None:
    stdin = io.StringIO("\n\nhello\n")
    stdout = io.StringIO()
    adapter = TerminalAdapter(stdin=stdin, stdout=stdout)

    messages: list[str] = []

    def callback(sender: str, message: str) -> str:
        messages.append(message)
        return "ok"

    adapter.listen(callback)
    assert messages == ["hello"]


def test_stop_halts_listen() -> None:
    adapter = TerminalAdapter()
    adapter._running = True
    adapter.stop()
    assert adapter._running is False


def test_adapter_id_and_name() -> None:
    adapter = TerminalAdapter()
    assert adapter.id == "terminal"
    assert adapter.name == "Terminal"
