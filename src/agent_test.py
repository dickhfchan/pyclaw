from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.agent import Agent, _build_system_prompt, TOOLS
from src.config import Config
from src.skills.types import Skill


@pytest.fixture
def mock_memory():
    mm = MagicMock()
    mm.get_file_content.side_effect = lambda name: {
        "SOUL.md": "I am a helpful assistant.",
        "USER.md": "User prefers concise answers.",
    }.get(name)
    mm.get_context.return_value = "## Relevant Memory\nSome past decision."
    return mm


@pytest.fixture
def sample_skills():
    return [
        Skill(
            name="weather",
            description="Get weather info",
            content="Use curl for weather",
            path="skills/weather/SKILL.md",
            available=True,
        ),
    ]


@pytest.fixture
def config():
    return Config()


def test_build_system_prompt_includes_soul(mock_memory, sample_skills):
    prompt = _build_system_prompt(mock_memory, sample_skills, "test query")
    assert "helpful assistant" in prompt


def test_build_system_prompt_includes_user(mock_memory, sample_skills):
    prompt = _build_system_prompt(mock_memory, sample_skills, "test query")
    assert "concise answers" in prompt


def test_build_system_prompt_includes_memory(mock_memory, sample_skills):
    prompt = _build_system_prompt(mock_memory, sample_skills, "test query")
    assert "Relevant Memory" in prompt


def test_build_system_prompt_includes_skills(mock_memory, sample_skills):
    prompt = _build_system_prompt(mock_memory, sample_skills, "test query")
    assert "weather" in prompt


def test_build_system_prompt_no_skills(mock_memory):
    prompt = _build_system_prompt(mock_memory, [], "test query")
    assert "Available Skills" not in prompt


def test_tools_defined():
    tool_names = {t["name"] for t in TOOLS}
    assert "search_memory" in tool_names
    assert "execute_shell" in tool_names
    assert "send_notification" in tool_names


def test_handle_tool_search_memory(config, mock_memory, sample_skills):
    agent = Agent(config, mock_memory, sample_skills)
    result = agent._handle_tool("search_memory", {"query": "preferences"})
    assert "Relevant Memory" in result


def test_handle_tool_search_memory_no_results(config, mock_memory, sample_skills):
    mock_memory.get_context.return_value = ""
    agent = Agent(config, mock_memory, sample_skills)
    result = agent._handle_tool("search_memory", {"query": "unknown"})
    assert "No relevant memory" in result


def test_handle_tool_execute_shell(config, mock_memory, sample_skills):
    agent = Agent(config, mock_memory, sample_skills)
    result = agent._handle_tool("execute_shell", {"command": "echo hello"})
    assert "hello" in result


def test_handle_tool_send_notification_no_notifier(config, mock_memory, sample_skills):
    agent = Agent(config, mock_memory, sample_skills)
    result = agent._handle_tool(
        "send_notification",
        {"notification_type": "test", "message": "hello"},
    )
    assert "not configured" in result


def test_handle_tool_send_notification_with_notifier(config, mock_memory, sample_skills):
    notifier = MagicMock()
    agent = Agent(config, mock_memory, sample_skills, notifier=notifier)
    result = agent._handle_tool(
        "send_notification",
        {"notification_type": "urgent_email", "message": "Check your inbox"},
    )
    notifier.notify.assert_called_once_with("urgent_email", "Check your inbox")
    assert "sent" in result


def test_handle_tool_unknown(config, mock_memory, sample_skills):
    agent = Agent(config, mock_memory, sample_skills)
    result = agent._handle_tool("nonexistent_tool", {})
    assert "Unknown tool" in result


@patch("src.agent.anthropic.Anthropic")
def test_chat_returns_text(mock_anthropic_cls, config, mock_memory, sample_skills):
    # Mock the API response
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client

    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "Here is the answer."

    mock_response = MagicMock()
    mock_response.stop_reason = "end_turn"
    mock_response.content = [text_block]

    mock_client.messages.create.return_value = mock_response

    agent = Agent(config, mock_memory, sample_skills)
    response_text, messages = agent.chat([], "What time is it?")

    assert response_text == "Here is the answer."
    assert len(messages) >= 2  # user + assistant


@patch("src.agent.anthropic.Anthropic")
def test_chat_handles_tool_use(mock_anthropic_cls, config, mock_memory, sample_skills):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client

    # First response: tool use
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "search_memory"
    tool_block.input = {"query": "preferences"}
    tool_block.id = "tool_123"

    tool_response = MagicMock()
    tool_response.stop_reason = "tool_use"
    tool_response.content = [tool_block]

    # Second response: final text
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "Based on memory, you prefer X."

    final_response = MagicMock()
    final_response.stop_reason = "end_turn"
    final_response.content = [text_block]

    mock_client.messages.create.side_effect = [tool_response, final_response]

    agent = Agent(config, mock_memory, sample_skills)
    response_text, messages = agent.chat([], "What are my preferences?")

    assert response_text == "Based on memory, you prefer X."
    assert mock_client.messages.create.call_count == 2
