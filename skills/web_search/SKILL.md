---
name: web_search
description: "Search the web for current information (DuckDuckGo by default; optional Brave Search API)."
metadata:
  requires:
    env: []   # optional: BRAVE_API_KEY for Brave Search
---

# Web Search

Search the web for up-to-date information, news, and data. Use this when the user asks about current events, recent news, factual lookups, or anything that requires live web results.

## Capabilities

- **Web search**: Run a query and get titles, URLs, and snippets from search results.
- **Backends**: Uses DuckDuckGo by default (no API key). If `BRAVE_API_KEY` is set in `.env`, uses Brave Search API for results.

## When to use

- "What's the latest on X?"
- "Search for recent news about Y"
- "Find information about Z"
- Any question that needs current or external web data

## Examples

- Search for recent events: use query "latest news OpenAI 2025"
- Look up facts: "Python 3.12 release date"
- Research: "best practices for async Python"

The agent will call the `search_web` tool with your query and summarize or use the results in its reply.
