from __future__ import annotations

import json
import logging
import os
import urllib.request
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import quote

import asyncio

from claude_agent_sdk import (
    ClaudeAgentOptions,
    TextBlock,
    query,
    tool,
    create_sdk_mcp_server,
)
from openai import AsyncAzureOpenAI

from src.config import Config
from src.memory.manager import MemoryManager
from src.skills.loader import format_skills_list
from src.skills.types import Skill

logger = logging.getLogger(__name__)

# OpenAI-format tools for Azure OpenAI
AZURE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_memory",
            "description": "Search the user's memory files (SOUL.md, USER.md, MEMORY.md, daily logs) for relevant information.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "Search query"}},
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_notification",
            "description": "Send a notification to the user via a specific channel.",
            "parameters": {
                "type": "object",
                "properties": {
                    "notification_type": {"type": "string", "description": "Channel (e.g. whatsapp, terminal)"},
                    "message": {"type": "string", "description": "Message to send"},
                },
                "required": ["notification_type", "message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather or short forecast for a city using wttr.in (no API key required). Use for live conditions or when the user asks for weather.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "City name (e.g. Shanghai, London, New York)"},
                    "format": {"type": "string", "description": "Output format: '3' for one-line summary, 'v2' for detailed forecast. Default '3'.", "default": "3"},
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_web",
            "description": "Search the web for current information, news, or facts. Use when the user asks about recent events, needs live data, or wants to look something up online. Uses DuckDuckGo by default; set BRAVE_API_KEY for Brave Search.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query (e.g. 'latest OpenAI news', 'Python 3.12 release')"},
                    "max_results": {"type": "integer", "description": "Max number of results to return (default 5)", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_stock_quote",
            "description": "Get the current stock price (and basic quote info) for a ticker symbol from Yahoo Finance. Use when the user asks for a stock price, quote, or ticker (e.g. MU, AAPL, MSFT). Returns price in USD.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {"type": "string", "description": "Stock ticker symbol (e.g. MU, AAPL, GOOGL)"},
                },
                "required": ["symbol"],
            },
        },
    },
]


async def _prompt_stream(text: str) -> AsyncIterator[dict[str, Any]]:
    """Wrap a string prompt as an async iterable user message.

    Using an AsyncIterable prompt instead of a plain string ensures the SDK
    goes through ``stream_input()``, which keeps stdin open long enough for
    bidirectional MCP control-protocol exchanges before closing the channel.
    """
    yield {
        "type": "user",
        "session_id": "",
        "message": {"role": "user", "content": text},
        "parent_tool_use_id": None,
    }


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


def _search_web_sync(query: str, max_results: int = 5) -> str:
    """Run web search (DuckDuckGo or Brave if API key set). Call from asyncio.to_thread."""
    query = (query or "").strip()
    if not query:
        return "Please provide a search query."
    brave_key = os.environ.get("BRAVE_API_KEY") or os.environ.get("BRAVE_SEARCH_API_KEY")
    if brave_key:
        try:
            url = "https://api.search.brave.com/res/v1/web/search"
            req = urllib.request.Request(
                f"{url}?q={quote(query)}",
                headers={
                    "Accept": "application/json",
                    "X-Subscription-Token": brave_key,
                },
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            results = (data.get("web") or {}).get("results") or []
            if not results:
                return "No web results found."
            lines = []
            for r in results[:max_results]:
                title = r.get("title") or ""
                link = r.get("url") or ""
                desc = (r.get("description") or "").strip()
                lines.append(f"- **{title}**\n  {link}\n  {desc}")
            return "\n\n".join(lines)
        except Exception as e:
            logger.warning("Brave search failed: %s", e)
            # fall through to DuckDuckGo
    try:
        from ddgs import DDGS
        results = list(DDGS().text(query, max_results=max_results))
        if not results:
            return "No web results found."
        lines = []
        for r in results[:max_results]:
            title = (r.get("title") or "").strip()
            link = (r.get("href") or r.get("url") or "").strip()
            body = (r.get("body") or "").strip()
            lines.append(f"- **{title}**\n  {link}\n  {body}")
        return "\n\n".join(lines)
    except Exception as e:
        logger.warning("Web search failed: %s", e)
        return f"Web search failed: {e}"


def _get_stock_quote_sync(symbol: str) -> str:
    """Fetch current stock quote from Yahoo Finance. Call from asyncio.to_thread."""
    symbol = (symbol or "").strip().upper()
    if not symbol:
        return "Please provide a stock ticker symbol (e.g. MU, AAPL)."
    url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={quote(symbol)}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "curl/7"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        results = (data.get("quoteResponse") or {}).get("result") or []
        if not results:
            return f"No quote found for {symbol}. Check the ticker symbol."
        r = results[0]
        price = r.get("regularMarketPrice")
        name = r.get("shortName") or r.get("longName") or symbol
        curr = r.get("currency", "USD")
        change = r.get("regularMarketChange")
        change_pct = r.get("regularMarketChangePercent")
        if price is None:
            return f"No price for {symbol} ({name})."
        parts = [f"**{name}** ({symbol}): **{curr} {price:,.2f}**"]
        if change is not None and change_pct is not None:
            sign = "+" if change >= 0 else ""
            parts.append(f" {sign}{change:,.2f} ({sign}{change_pct:.2f}%)")
        return "".join(parts)
    except Exception as e:
        logger.warning("Stock quote failed: %s", e)
        return f"Could not fetch quote for {symbol}: {e}"


async def _fetch_weather(city: str, format: str = "3") -> str:
    """Fetch weather for a city from wttr.in (no API key). Runs in thread to avoid blocking."""
    if not city or not city.strip():
        return "Please specify a city (e.g. Shanghai, London)."
    city_escaped = quote(city.strip())
    url = f"https://wttr.in/{city_escaped}?format={format}"
    try:
        def _get() -> str:
            req = urllib.request.Request(url, headers={"User-Agent": "curl/7"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.read().decode("utf-8", errors="replace").strip()
        return await asyncio.to_thread(_get)
    except Exception as e:
        logger.warning("Weather fetch failed: %s", e)
        return f"Could not fetch weather for {city}: {e}"


def _extract_text(messages: list[Any]) -> str:
    """Extract text content from SDK response messages."""
    text_parts: list[str] = []
    for msg in messages:
        if hasattr(msg, "content"):
            for block in msg.content:
                if isinstance(block, TextBlock) or hasattr(block, "text"):
                    text_parts.append(block.text)
    return "\n".join(text_parts)


@asynccontextmanager
async def _azure_client():
    """Yield an Azure OpenAI client and close it on exit to avoid 'Event loop is closed' errors."""
    endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    api_version = os.environ.get("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
    if not endpoint or not api_key:
        raise ValueError("AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY must be set when provider=AZURE_OPENAI")
    client = AsyncAzureOpenAI(
        azure_endpoint=endpoint.rstrip("/"),
        api_key=api_key,
        api_version=api_version,
    )
    async with client:
        yield client


class Agent:
    """Agent using Azure OpenAI (default) or Claude Agent SDK (ANTHROPIC)."""

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

        @tool("get_weather", "Get current weather or short forecast for a city using wttr.in (no API key). Use for live conditions.", {"city": str, "format": str})
        async def get_weather_tool(args: dict[str, Any]) -> dict[str, Any]:
            text = await _fetch_weather(args.get("city", ""), args.get("format", "3"))
            return {"content": [{"type": "text", "text": text}]}

        @tool("search_web", "Search the web for current information, news, or facts. Use for recent events or lookups.", {"query": str, "max_results": int})
        async def search_web_tool(args: dict[str, Any]) -> dict[str, Any]:
            text = await asyncio.to_thread(
                _search_web_sync,
                args.get("query", ""),
                args.get("max_results", 5),
            )
            return {"content": [{"type": "text", "text": text}]}

        @tool("get_stock_quote", "Get current stock price for a ticker from Yahoo Finance (e.g. MU, AAPL).", {"symbol": str})
        async def get_stock_quote_tool(args: dict[str, Any]) -> dict[str, Any]:
            text = await asyncio.to_thread(_get_stock_quote_sync, args.get("symbol", ""))
            return {"content": [{"type": "text", "text": text}]}

        self._search_memory_tool = search_memory_tool
        self._send_notification_tool = send_notification_tool
        self._mcp_server = (
            create_sdk_mcp_server(
                name="pyclaw",
                version="0.1.0",
                tools=[search_memory_tool, send_notification_tool, get_weather_tool, search_web_tool, get_stock_quote_tool],
            )
            if config.agent.provider == "ANTHROPIC"
            else None
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
                "mcp__pyclaw__get_weather",
                "mcp__pyclaw__search_web",
                "mcp__pyclaw__get_stock_quote",
            ],
        )

    async def _run_azure_tool(self, name: str, arguments: dict[str, Any]) -> str:
        """Run one Azure tool by name and return result text."""
        if name == "search_memory":
            context = self.memory.get_context(arguments.get("query", ""))
            return context if context else "No relevant memory found."
        if name == "send_notification":
            if self.notifier is None:
                return "Notification system not configured."
            try:
                self.notifier.notify(
                    arguments.get("notification_type", ""),
                    arguments.get("message", ""),
                )
                return f"Notification sent ({arguments.get('notification_type', '')})."
            except Exception as e:
                return f"Failed to send notification: {e}"
        if name == "get_weather":
            return await _fetch_weather(
                arguments.get("city", ""),
                arguments.get("format", "3"),
            )
        if name == "search_web":
            return await asyncio.to_thread(
                _search_web_sync,
                arguments.get("query", ""),
                arguments.get("max_results", 5),
            )
        if name == "get_stock_quote":
            return await asyncio.to_thread(_get_stock_quote_sync, arguments.get("symbol", ""))
        return f"Unknown tool: {name}"

    async def _chat_azure(
        self, messages: list[dict[str, Any]], query_text: str
    ) -> tuple[str, list[dict[str, Any]]]:
        """One conversation turn using Azure OpenAI with tool calling."""
        system_prompt = _build_system_prompt(self.memory, self.skills, query_text)
        deployment = self.config.agent.model
        openai_messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            *messages,
            {"role": "user", "content": query_text},
        ]
        max_turns = 15
        async with _azure_client() as client:
            for _ in range(max_turns):
                response = await client.chat.completions.create(
                    model=deployment,
                    messages=openai_messages,
                    tools=AZURE_TOOLS,
                    tool_choice="auto",
                )
                choice = response.choices[0]
                msg = choice.message
                if not getattr(msg, "tool_calls", None) or len(msg.tool_calls) == 0:
                    text = (msg.content or "").strip()
                    updated = messages + [
                        {"role": "user", "content": query_text},
                        {"role": "assistant", "content": text},
                    ]
                    return text, updated
                tool_calls_payload = [
                    {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments or "{}"}}
                    for tc in msg.tool_calls
                ]
                openai_messages.append(
                    {"role": "assistant", "content": msg.content or "", "tool_calls": tool_calls_payload}
                )
                for tc in msg.tool_calls:
                    name = tc.function.name
                    try:
                        args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                    except json.JSONDecodeError:
                        args = {}
                    result = await self._run_azure_tool(name, args)
                    openai_messages.append(
                        {"role": "tool", "tool_call_id": tc.id, "content": result}
                    )
        logger.warning("Azure chat hit max_turns")
        text = openai_messages[-1].get("content", "") if openai_messages else ""
        updated = messages + [
            {"role": "user", "content": query_text},
            {"role": "assistant", "content": text},
        ]
        return text, updated

    async def _reason_azure(self, context: str, prompt: str) -> str | None:
        """Single-turn reasoning using Azure OpenAI (no tools)."""
        try:
            async with _azure_client() as client:
                response = await client.chat.completions.create(
                    model=self.config.agent.model,
                    messages=[
                        {"role": "system", "content": context},
                        {"role": "user", "content": prompt},
                    ],
                )
                text = (response.choices[0].message.content or "").strip()
                return text or None
        except Exception:
            logger.exception("Azure reason call failed")
            return None

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
        if self.config.agent.provider == "AZURE_OPENAI":
            return await self._chat_azure(messages, query_text)

        system_prompt = _build_system_prompt(self.memory, self.skills, query_text)
        options = self._build_options(system_prompt)

        # Collect response messages
        # Use async-iterable prompt so the SDK keeps stdin open for MCP control requests
        response_messages: list[Any] = []
        async for message in query(prompt=_prompt_stream(query_text), options=options):
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
        if self.config.agent.provider == "AZURE_OPENAI":
            return await self._reason_azure(context, prompt)
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
