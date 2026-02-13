from __future__ import annotations

from unittest.mock import MagicMock

from src.adapters.whatsapp import WhatsAppAdapter, ConnectionState


def test_initial_state_disconnected() -> None:
    adapter = WhatsAppAdapter()
    assert adapter.state == ConnectionState.DISCONNECTED


def test_connect_with_client() -> None:
    client = MagicMock()
    adapter = WhatsAppAdapter(client=client)
    adapter.connect()
    client.connect.assert_called_once()
    assert adapter.state == ConnectionState.CONNECTED


def test_connect_without_client() -> None:
    adapter = WhatsAppAdapter()
    adapter.connect()  # Should not raise
    assert adapter.state == ConnectionState.DISCONNECTED


def test_send_with_connected_client() -> None:
    client = MagicMock()
    adapter = WhatsAppAdapter(client=client)
    adapter.connect()
    adapter.send("+1234567890", "Hello!")
    client.send_message.assert_called_once_with("+1234567890", "Hello!")


def test_send_without_client() -> None:
    adapter = WhatsAppAdapter()
    adapter.send("+1234567890", "Hello!")  # Should not raise


def test_send_when_disconnected() -> None:
    client = MagicMock()
    adapter = WhatsAppAdapter(client=client)
    # Don't connect, just try to send
    adapter.send("+1234567890", "Hello!")
    client.send_message.assert_not_called()


def test_listen_registers_callback() -> None:
    client = MagicMock()
    adapter = WhatsAppAdapter(client=client)

    def callback(sender: str, message: str) -> str:
        return "response"

    adapter.listen(callback)
    client.on_message.assert_called_once()
    assert adapter._callback is callback


def test_stop_disconnects() -> None:
    client = MagicMock()
    adapter = WhatsAppAdapter(client=client)
    adapter.connect()
    adapter.stop()
    client.disconnect.assert_called_once()
    assert adapter.state == ConnectionState.DISCONNECTED


def test_stop_without_connection() -> None:
    adapter = WhatsAppAdapter()
    adapter.stop()  # Should not raise
    assert adapter.state == ConnectionState.DISCONNECTED


def test_adapter_id_and_name() -> None:
    adapter = WhatsAppAdapter()
    assert adapter.id == "whatsapp"
    assert adapter.name == "WhatsApp"


def test_message_callback_sends_response() -> None:
    client = MagicMock()
    adapter = WhatsAppAdapter(client=client)
    adapter.connect()

    def callback(sender: str, message: str) -> str:
        return f"Reply to {message}"

    adapter.listen(callback)

    # Get the handler registered with on_message
    handler = client.on_message.call_args[0][0]
    handler("+1234567890", "test message")

    client.send_message.assert_called_with("+1234567890", "Reply to test message")
