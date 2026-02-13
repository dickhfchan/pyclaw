from __future__ import annotations

import logging
import subprocess
from typing import Any

import anthropic

from src.config import Config
from src.memory.manager import MemoryManager
from src.skills.loader import format_skills_list, get_skill_content
from src.skills.types import Skill

logger = logging.getLogger(__name__)

TOOLS = [
    {
        "name": "search_memory",
        "description": "Search the user's memory files (SOUL.md, USER.md, MEMORY.md, daily logs) for relevant information. Use this when you need context about the user's preferences, past decisions, or history.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to find relevant memory entries.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "execute_shell",
        "description": "Execute a shell command. Use this for running scripts, checking system info, or executing skill instructions. Always confirm potentially dangerous commands with the user first.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute.",
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "send_notification",
        "description": "Send a notification to the user via a specific channel (e.g., terminal, whatsapp).",
        "input_schema": {
            "type": "object",
            "properties": {
                "notification_type": {
                    "type": "string",
                    "description": "The type of notification (urgent_email, calendar_reminder, daily_summary, task_alert).",
                },
                "message": {
                    "type": "string",
                    "description": "The notification message to send.",
                },
            },
            "required": ["notification_type", "message"],
        },
    },
]


def _build_system_prompt(
    memory_manager: MemoryManager,
    skills: list[Skill],
    query: str,
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
    memory_context = memory_manager.get_context(query)
    if memory_context:
        parts.append(memory_context)

    # List available skills
    skills_list = format_skills_list(skills)
    if skills_list:
        parts.append(skills_list)

    return "\n\n".join(parts)


class Agent:
    """Claude-powered agent with memory, skills, and notification tools."""

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
        self._client = anthropic.Anthropic()

    def chat(self, messages: list[dict[str, Any]], query: str) -> tuple[str, list[dict[str, Any]]]:
        """Process a conversation turn.

        Args:
            messages: Conversation history (list of role/content dicts).
            query: The current user query (used for memory search context).

        Returns:
            A tuple of (response_text, updated_messages).
        """
        system_prompt = _build_system_prompt(self.memory, self.skills, query)

        # Add the user message
        updated_messages = messages + [{"role": "user", "content": query}]

        response = self._call_api(system_prompt, updated_messages)

        # Handle tool use loop
        while response.stop_reason == "tool_use":
            # Extract tool use blocks
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = self._handle_tool(block.name, block.input)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        }
                    )

            # Add assistant response and tool results to history
            updated_messages.append({"role": "assistant", "content": response.content})
            updated_messages.append({"role": "user", "content": tool_results})

            response = self._call_api(system_prompt, updated_messages)

        # Extract final text response
        text_parts = []
        for block in response.content:
            if hasattr(block, "text"):
                text_parts.append(block.text)
        final_text = "\n".join(text_parts)

        updated_messages.append({"role": "assistant", "content": response.content})

        return final_text, updated_messages

    def reason(self, context: str, prompt: str) -> str | None:
        """Simple reasoning call for heartbeat (no tools, no history).

        Returns the response text, or None on failure.
        """
        try:
            response = self._client.messages.create(
                model=self.config.agent.model,
                max_tokens=1024,
                system=context,
                messages=[{"role": "user", "content": prompt}],
            )
            for block in response.content:
                if hasattr(block, "text"):
                    return block.text
        except Exception:
            logger.exception("Reasoning call failed")
        return None

    def _call_api(
        self, system_prompt: str, messages: list[dict[str, Any]]
    ) -> Any:
        """Call the Claude API with tools."""
        return self._client.messages.create(
            model=self.config.agent.model,
            max_tokens=4096,
            system=system_prompt,
            messages=messages,
            tools=TOOLS,
        )

    def _handle_tool(self, tool_name: str, tool_input: dict[str, Any]) -> str:
        """Dispatch a tool call and return the result as a string."""
        if tool_name == "search_memory":
            return self._tool_search_memory(tool_input["query"])
        elif tool_name == "execute_shell":
            return self._tool_execute_shell(tool_input["command"])
        elif tool_name == "send_notification":
            return self._tool_send_notification(
                tool_input["notification_type"],
                tool_input["message"],
            )
        else:
            return f"Unknown tool: {tool_name}"

    def _tool_search_memory(self, query: str) -> str:
        """Search memory and return formatted results."""
        context = self.memory.get_context(query)
        return context if context else "No relevant memory found."

    def _tool_execute_shell(self, command: str) -> str:
        """Execute a shell command and return output."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR: {result.stderr}"
            if result.returncode != 0:
                output += f"\nExit code: {result.returncode}"
            return output[:5000] if output else "(no output)"
        except subprocess.TimeoutExpired:
            return "Command timed out after 30 seconds."
        except Exception as e:
            return f"Error executing command: {e}"

    def _tool_send_notification(self, notification_type: str, message: str) -> str:
        """Send a notification via the notifier."""
        if self.notifier is None:
            return "Notification system not configured."
        try:
            self.notifier.notify(notification_type, message)
            return f"Notification sent ({notification_type})."
        except Exception as e:
            return f"Failed to send notification: {e}"
