# Can pyclaw run each Awesome OpenClaw use case?

This document maps [Awesome OpenClaw Use Cases](https://github.com/hesamsheikh/awesome-openclaw-usecases) to **pyclaw**’s current capabilities.  
**Legend:** ✅ Yes (or close) · ⚠️ Partial (needs extra work) · ❌ No (blocked by design or missing pieces).

---

## Pyclaw capabilities (summary)

| Area | What pyclaw has |
|------|------------------|
| **Channels** | Terminal (interactive + one-shot), WhatsApp (optional) |
| **Memory** | SOUL.md, USER.md, MEMORY.md, daily logs; **hybrid search** (vector + FTS5), auto-sync from `memory/` |
| **Tools** | `search_memory`, `send_notification`, `get_weather`, `search_web` (DuckDuckGo/Brave), `get_stock_quote` |
| **Skills** | Loaded from `skills/` (e.g. weather, web_search); agent sees skill list in system prompt |
| **Scheduling** | Heartbeat: Gmail poll, Calendar poll, **daily summary** at a configurable time |
| **LLM** | Azure OpenAI (default) or Anthropic |
| **Missing vs OpenClaw** | No Telegram, Discord, Slack, iMessage; no phone/voice; no Reddit/YouTube/X/Todoist/n8n skills; no multi-agent; no “build me a Next.js app” flow |

---

## Social Media

| Use case | Verdict | Notes |
|----------|---------|--------|
| **Daily Reddit Digest** | ❌ | Needs a Reddit (read-only) skill; pyclaw has no Reddit integration. |
| **Daily YouTube Digest** | ❌ | Needs YouTube/subscriptions skill; not implemented. |
| **X Account Analysis** | ❌ | Needs X/Twitter API skill; not implemented. |
| **Multi-Source Tech News Digest** | ⚠️ | **Partial:** You can use `search_web` + heartbeat + daily summary to pull tech news and get a daily digest to terminal/WhatsApp. No RSS/GitHub/Twitter aggregation or 109-source pipeline out of the box. |

---

## Creative & Building

| Use case | Verdict | Notes |
|----------|---------|--------|
| **Goal-Driven Autonomous Tasks / overnight mini-app builder** | ❌ | OpenClaw-style autonomous task scheduling and “build mini-apps overnight” is not implemented; no multi-step execution engine. |
| **YouTube Content Pipeline** | ❌ | No YouTube skills or video-idea automation. |
| **Multi-Agent Content Factory (Discord)** | ❌ | No Discord adapter; no multi-agent pipeline. |
| **Autonomous Game Dev Pipeline** | ❌ | No game-dev lifecycle, backlog, or “Bugs First” automation. |

---

## Infrastructure & DevOps

| Use case | Verdict | Notes |
|----------|---------|--------|
| **n8n Workflow Orchestration** | ❌ | No n8n/webhook integration; agent cannot call n8n workflows. |
| **Self-Healing Home Server** | ❌ | No SSH runner, cron delegation, or “always-on infra agent” pattern. |

---

## Productivity

| Use case | Verdict | Notes |
|----------|---------|--------|
| **Autonomous Project Management (STATE.yaml, multi-agent)** | ❌ | No STATE.yaml pattern or multi-agent orchestration. |
| **Multi-Channel AI Customer Service** | ❌ | No Instagram, Google Reviews, or 24/7 multi-channel inbox. |
| **Phone-Based Personal Assistant** | ❌ | No voice/SMS/phone integration. |
| **Inbox De-clutter** | ⚠️ | **Partial:** Heartbeat can poll Gmail; you could add a scheduled “summarize last 24h newsletters” job and send digest via notifier (terminal/WhatsApp). Would need Gmail OAuth and prompt design; no built-in “newsletter digest” skill. |
| **Personal CRM** | ⚠️ | **Partial:** Gmail + Calendar heartbeat exist; no CRM DB, contact extraction, or “who needs follow-up” queries. Would need a CRM skill and storage. |
| **Health & Symptom Tracker** | ⚠️ | **Partial:** Memory + scheduling could support “log food/symptoms and remind me”; no dedicated tracker skill or UI. |
| **Multi-Channel Personal Assistant (Telegram, Slack, email, calendar)** | ⚠️ | **Partial:** Terminal + WhatsApp + calendar heartbeat; no Telegram or Slack. |
| **Project State Management** | ❌ | No event-driven project tracking or Kanban replacement. |
| **Dynamic Dashboard** | ❌ | No real-time dashboard or parallel API/social fetch UI. |
| **Todoist Task Manager** | ❌ | No Todoist sync or reasoning-log export. |
| **Family Calendar & Household Assistant** | ⚠️ | **Partial:** One calendar in heartbeat + memory; no multi-calendar aggregation or household inventory. |
| **Multi-Agent Specialized Team (Telegram)** | ❌ | No Telegram; no multi-agent team. |
| **Custom Morning Brief** | ⚠️ | **Partial:** Daily summary at a time + web search + memory: you can get a morning brief (news, tasks from memory, recommendations) to **terminal or WhatsApp**, not Telegram/Discord/iMessage. No Todoist/Asana/Apple Reminders pull. |
| **Second Brain** | ⚠️ | **Partial:** “Text to remember + search” works: terminal/WhatsApp + persistent memory + hybrid search. No Next.js dashboard; you’d need to build your own UI or use `memory/` + grep/search. |
| **Event Guest Confirmation (voice calls)** | ❌ | No voice calling or guest-call automation. |

---

## Research & Learning

| Use case | Verdict | Notes |
|----------|---------|--------|
| **AI Earnings Tracker** | ⚠️ | **Partial:** `search_web` + `get_stock_quote` + heartbeat could deliver earnings-related summaries and stock data to terminal/WhatsApp; no dedicated earnings skill or alerts. |
| **Personal Knowledge Base (RAG)** | ⚠️ | **Partial:** Memory is already RAG-like (hybrid search). No “drop URL in chat → ingest” flow; you could add a skill/tool to fetch URL and append to memory (or a dedicated KB). |
| **Market Research & Product Factory** | ❌ | No Reddit/X “Last 30 Days” skill or “build MVP” automation. |
| **Semantic Memory Search** | ✅ | **Yes.** Pyclaw already has vector + FTS5 hybrid search over `memory/` and auto-sync. No separate memsearch/Milvus needed for core “search memory by meaning” use case. |

---

## Finance & Trading

| Use case | Verdict | Notes |
|----------|---------|--------|
| **Polymarket Autopilot** | ❌ | No prediction-market or paper-trading integration. |

---

## Summary counts

| Verdict | Count |
|---------|--------|
| ✅ Yes | 1 |
| ⚠️ Partial | 10 |
| ❌ No | 18 |

---

## What would make more use cases “Yes” or “Partial”?

1. **More channels:** Telegram, Discord, Slack adapters (and/or notifier routing to them).
2. **More skills/tools:** Reddit, YouTube, X, Gmail OAuth (read/send), Todoist/Reminders, n8n webhook.
3. **Scheduled prompts:** User-defined cron-like “run this prompt at 8am and send to X” (heartbeat is close but fixed to Gmail/Calendar/daily summary).
4. **URL ingest:** “Add this URL to memory/KB” tool + optional RAG over a dedicated KB.
5. **Multi-agent / orchestration:** Not in scope for current pyclaw; would be a larger design change.

---

*Assessment based on pyclaw as of the agent_sdk branch (Azure/Anthropic, terminal/WhatsApp, memory, web/weather/stock tools, heartbeat).*
