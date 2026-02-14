from __future__ import annotations

import logging
from typing import Any

from claude_agent_sdk import (
    ClaudeAgentOptions,
    TextBlock,
    query,
    tool,
    create_sdk_mcp_server,
)

from src.config import Config
from src.memory.manager import MemoryManager
from src.skills.loader import format_skills_list
from src.skills.types import Skill

logger = logging.getLogger(__name__)


def _build_system_prompt(
    memory_manager: MemoryManager,
    skills: list[Skill],
    query_text: str,
) -> str:
    """Assemble the system prompt from SOUL.md, USER.md, memory search, and skills."""
    parts: list[str] = []

    # Load core identity files
    soul = memory_manager.get_file_content("SOUL.md")
    if soul:
        parts.append(soul)

    user = memory_manager.get_file_content("USER.md")
    if user:
        parts.append(user)

    # Search memory for relevant context
    memory_context = memory_manager.get_context(query_text)
    if memory_context:
        parts.append(memory_context)

    # List available skills
    skills_list = format_skills_list(skills)
    if skills_list:
        parts.append(skills_list)

    return "\n\n".join(parts)


def _extract_text(messages: list[Any]) -> str:
    """Extract text content from SDK response messages."""
    text_parts: list[str] = []
    for msg in messages:
        if hasattr(msg, "content"):
            for block in msg.content:
                if isinstance(block, TextBlock) or hasattr(block, "text"):
                    text_parts.append(block.text)
    return "\n".join(text_parts)


class Agent:
    """Claude-powered agent using the Claude Agent SDK."""

    def __init__(
        self,
        config: Config,
        memory_manager: MemoryManager,
        skills: list[Skill],
        notifier: Any = None,
    ) -> None:
        self.config = config
        self.memory = memory_manager
        self.skills = skills
        self.notifier = notifier

        # Define custom MCP tools that capture instance state
        @tool("search_memory", "Search the user's memory files (SOUL.md, USER.md, MEMORY.md, daily logs) for relevant information.", {"query": str})
        async def search_memory_tool(args: dict[str, Any]) -> dict[str, Any]:
            context = self.memory.get_context(args["query"])
            text = context if context else "No relevant memory found."
            return {"content": [{"type": "text", "text": text}]}

        @tool("send_notification", "Send a notification to the user via a specific channel.", {"notification_type": str, "message": str})
        async def send_notification_tool(args: dict[str, Any]) -> dict[str, Any]:
            if self.notifier is None:
                return {"content": [{"type": "text", "text": "Notification system not configured."}]}
            try:
                self.notifier.notify(args["notification_type"], args["message"])
                return {"content": [{"type": "text", "text": f"Notification sent ({args['notification_type']})."}]}
            except Exception as e:
                return {
                    "content": [{"type": "text", "text": f"Failed to send notification: {e}"}],
                    "is_error": True,
                }

        self._mcp_server = create_sdk_mcp_server(
            name="pyclaw",
            version="0.1.0",
            tools=[search_memory_tool, send_notification_tool],
        )
        self._custom_tools = [search_memory_tool, send_notification_tool]

    def _build_options(self, system_prompt: str) -> ClaudeAgentOptions:
        """Build SDK options with custom MCP tools and system prompt."""
        return ClaudeAgentOptions(
            model=self.config.agent.model,
            system_prompt=system_prompt,
            permission_mode=self.config.agent.permission_mode,
            mcp_servers={"pyclaw": self._mcp_server},
            allowed_tools=[
                "Read", "Write", "Bash", "Glob", "Grep",
                "mcp__pyclaw__search_memory",
                "mcp__pyclaw__send_notification",
            ],
        )

    async def chat(
        self, messages: list[dict[str, Any]], query_text: str
    ) -> tuple[str, list[dict[str, Any]]]:
        """Process a conversation turn.

        Args:
            messages: Conversation history (list of role/content dicts).
            query_text: The current user query.

        Returns:
            A tuple of (response_text, updated_messages).
        """
        system_prompt = _build_system_prompt(self.memory, self.skills, query_text)
        options = self._build_options(system_prompt)

        # Collect response messages
        response_messages: list[Any] = []
        async for message in query(prompt=query_text, options=options):
            response_messages.append(message)

        response_text = _extract_text(response_messages)

        # Update conversation history
        updated_messages = messages + [
            {"role": "user", "content": query_text},
            {"role": "assistant", "content": response_text},
        ]

        return response_text, updated_messages

    async def reason(self, context: str, prompt: str) -> str | None:
        """Simple reasoning call for heartbeat (no custom tools needed).

        Returns the response text, or None on failure.
        """
        try:
            options = ClaudeAgentOptions(
                model=self.config.agent.model,
                system_prompt=context,
                permission_mode=self.config.agent.permission_mode,
                max_turns=1,
            )

            response_messages: list[Any] = []
            async for message in query(prompt=prompt, options=options):
                response_messages.append(message)

            text = _extract_text(response_messages)
            return text if text else None
        except Exception:
            logger.exception("Reasoning call failed")
        return None
