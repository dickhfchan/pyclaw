from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agent import Agent, _build_system_prompt, _extract_text
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


def test_extract_text_from_messages():
    msg = MagicMock()
    block = MagicMock()
    block.text = "Hello world"
    msg.content = [block]
    result = _extract_text([msg])
    assert result == "Hello world"


def test_extract_text_empty():
    msg = MagicMock(spec=[])  # no 'content' attribute
    result = _extract_text([msg])
    assert result == ""


def test_agent_init_creates_mcp_server(config, mock_memory, sample_skills):
    with patch("src.agent.create_sdk_mcp_server") as mock_create, \
         patch("src.agent.tool", side_effect=lambda *a, **kw: lambda fn: fn):
        mock_create.return_value = MagicMock()
        agent = Agent(config, mock_memory, sample_skills)
        mock_create.assert_called_once()


def test_agent_build_options(config, mock_memory, sample_skills):
    with patch("src.agent.create_sdk_mcp_server") as mock_create, \
         patch("src.agent.tool", side_effect=lambda *a, **kw: lambda fn: fn):
        mock_create.return_value = MagicMock()
        agent = Agent(config, mock_memory, sample_skills)
        options = agent._build_options("test system prompt")
        assert options.model == config.agent.model
        assert options.system_prompt == "test system prompt"
        assert options.permission_mode == config.agent.permission_mode
        assert "mcp__pyclaw__search_memory" in options.allowed_tools
        assert "mcp__pyclaw__send_notification" in options.allowed_tools


@pytest.mark.asyncio
async def test_chat_returns_text(config, mock_memory, sample_skills):
    with patch("src.agent.create_sdk_mcp_server") as mock_create, \
         patch("src.agent.tool", side_effect=lambda *a, **kw: lambda fn: fn):
        mock_create.return_value = MagicMock()
        agent = Agent(config, mock_memory, sample_skills)

    # Mock query to yield a message with text content
    mock_msg = MagicMock()
    block = MagicMock()
    block.text = "Here is the answer."
    mock_msg.content = [block]

    async def mock_query(**kwargs):
        yield mock_msg

    with patch("src.agent.query", side_effect=mock_query):
        response_text, messages = await agent.chat([], "What time is it?")

    assert response_text == "Here is the answer."
    assert len(messages) == 2  # user + assistant


@pytest.mark.asyncio
async def test_chat_preserves_history(config, mock_memory, sample_skills):
    with patch("src.agent.create_sdk_mcp_server") as mock_create, \
         patch("src.agent.tool", side_effect=lambda *a, **kw: lambda fn: fn):
        mock_create.return_value = MagicMock()
        agent = Agent(config, mock_memory, sample_skills)

    mock_msg = MagicMock()
    block = MagicMock()
    block.text = "Response"
    mock_msg.content = [block]

    async def mock_query(**kwargs):
        yield mock_msg

    existing = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]

    with patch("src.agent.query", side_effect=mock_query):
        _, messages = await agent.chat(existing, "follow up")

    assert len(messages) == 4  # 2 existing + user + assistant
    assert messages[-2]["content"] == "follow up"
    assert messages[-1]["content"] == "Response"


@pytest.mark.asyncio
async def test_reason_returns_text(config, mock_memory, sample_skills):
    with patch("src.agent.create_sdk_mcp_server") as mock_create, \
         patch("src.agent.tool", side_effect=lambda *a, **kw: lambda fn: fn):
        mock_create.return_value = MagicMock()
        agent = Agent(config, mock_memory, sample_skills)

    mock_msg = MagicMock()
    block = MagicMock()
    block.text = "Reasoning result"
    mock_msg.content = [block]

    async def mock_query(**kwargs):
        yield mock_msg

    with patch("src.agent.query", side_effect=mock_query):
        result = await agent.reason("context", "prompt")

    assert result == "Reasoning result"


@pytest.mark.asyncio
async def test_reason_returns_none_on_error(config, mock_memory, sample_skills):
    with patch("src.agent.create_sdk_mcp_server") as mock_create, \
         patch("src.agent.tool", side_effect=lambda *a, **kw: lambda fn: fn):
        mock_create.return_value = MagicMock()
        agent = Agent(config, mock_memory, sample_skills)

    async def mock_query(**kwargs):
        raise RuntimeError("API error")
        yield  # make it an async generator

    with patch("src.agent.query", side_effect=mock_query):
        result = await agent.reason("context", "prompt")

    assert result is None
