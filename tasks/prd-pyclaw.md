# PRD: pyclaw — Ultra-Personalized AI Agent

## 1. Introduction / Overview

**pyclaw** is a local-first, ultra-personalized AI agent built in Python, inspired by [OpenClaw](https://github.com). It acts as a personal assistant that remembers your decisions, monitors your email and calendar proactively, and is reachable from WhatsApp or the terminal. It uses Markdown files as the source of truth for memory, with SQLite + vector embeddings as a search index layer.

The core philosophy: **OpenClaw is the blueprint, not a dependency.** pyclaw re-implements the key patterns (memory, heartbeat, adapters, skills) in Python, keeping things simple and local-only.

### Problem it solves

Users want an AI assistant that truly knows them — their preferences, past decisions, and current context — without relying on cloud services or SaaS platforms. Existing AI assistants are stateless between sessions, require manual context-setting, and can't proactively act on your behalf.

---

## 2. Goals

1. **Persistent personal memory** — The agent accumulates knowledge across sessions via Markdown files (SOUL.md, USER.md, MEMORY.md, daily logs), searchable through hybrid vector + keyword search.
2. **Proactive awareness** — Scheduled polling of Gmail and Google Calendar, with Claude reasoning over new data and sending notifications when relevant.
3. **Multi-channel access** — Interact via WhatsApp or terminal (Claude Code), with configurable notification routing per type.
4. **Extensible skills** — Drop a `SKILL.md` file in the `skills/` directory and it's instantly available to the agent. No registry, no install step.
5. **Local-only, no supply chain risk** — All data stays on disk. No public skill registry. No cloud dependencies beyond the LLM API.

---

## 3. User Stories

1. **As a user**, I want the agent to remember my past decisions and preferences so that I don't have to repeat context every session.
2. **As a user**, I want to ask the agent questions from WhatsApp while away from my desk, and get the same quality of response as from the terminal.
3. **As a user**, I want the agent to check my Gmail and Google Calendar every N minutes and notify me on WhatsApp if something urgent comes up (e.g., a meeting in 15 minutes, an important email).
4. **As a user**, I want to receive a daily summary notification on WhatsApp each morning with my calendar for the day.
5. **As a user**, I want to add a new capability (e.g., "generate PowerPoint from notes") by dropping a single `SKILL.md` file into the `skills/` directory.
6. **As a user**, I want my memory files to sync via Obsidian so I can browse and edit them from any device.
7. **As a user**, I want to control which notification types go to which channel (e.g., urgent alerts to WhatsApp, daily summaries to terminal).

---

## 4. Functional Requirements

### 4.1 Memory System

Inspired by OpenClaw's `src/memory/` module (2,302-line manager.ts, SQLite + sqlite-vec, hybrid BM25 + vector search).

1. **Markdown as source of truth.** The following files/directories constitute the agent's memory:
   - `memory/SOUL.md` — Agent personality, values, tone of voice
   - `memory/USER.md` — User identity, preferences, habits
   - `memory/MEMORY.md` — Accumulated decisions, lessons learned, important facts
   - `memory/daily/` — Session logs, one file per day (e.g., `2026-02-12.md`)

2. **SQLite as the search index.** A local SQLite database stores:
   - **`files` table** — Tracks each indexed Markdown file (path, content hash, mtime, size)
   - **`chunks` table** — Stores chunked text with embeddings (id, path, start_line, end_line, hash, text, embedding vector, model used, updated_at)
   - **`chunks_fts` virtual table** — FTS5 full-text search index over chunk text (for BM25 keyword search)
   - **Vector index** — via `sqlite-vec` extension for cosine-similarity vector search

3. **Markdown chunking.** Markdown files are split into overlapping chunks for embedding:
   - Default chunk size: ~2000 tokens (~8000 chars)
   - Default overlap: ~200 tokens (~800 chars)
   - Chunks track start/end line numbers for source attribution

4. **Embedding generation** using `fastembed` (local, no API calls):
   - Generate embeddings for each chunk on index/sync
   - Cache embeddings by content hash to avoid re-computation
   - Store embeddings as serialized vectors in the `chunks` table

5. **Hybrid search** (modeled on OpenClaw's `hybrid.ts`):
   - **Vector search**: Query embedding vs. stored chunk embeddings (cosine similarity via sqlite-vec)
   - **Keyword search**: BM25 ranking via FTS5
   - **Merge**: Weighted combination of vector score and text score, configurable weights (default: 0.7 vector, 0.3 keyword)
   - Return top-K results with path, line range, score, and snippet

6. **Auto-sync on file change.** Watch the `memory/` directory for changes (file create/edit/delete) and re-index affected files automatically.

7. **Session logging.** After each agent interaction, append a summary to `memory/daily/YYYY-MM-DD.md` including:
   - Timestamp
   - User query summary
   - Agent response summary
   - Any decisions made or facts learned

8. **Memory injection into agent context.** Before each agent call:
   - Load full contents of `SOUL.md` and `USER.md` as system prompt context
   - Run a hybrid search with the user's query against all memory chunks
   - Include top-K relevant memory snippets (default K=5) in the system prompt

### 4.2 Heartbeat System

Inspired by OpenClaw's `src/web/auto-reply/heartbeat-runner.ts` and cron config.

9. **Scheduled polling.** A background scheduler runs data-gathering tasks at configurable intervals:
   - Gmail polling (default: every 15 minutes)
   - Google Calendar polling (default: every 15 minutes)
   - Intervals configurable in `config.yaml`

10. **Gmail integration** via Google API (OAuth2):
    - Fetch unread emails since last check
    - Extract sender, subject, snippet, timestamp, labels
    - Pass to Claude for reasoning: "Is this urgent? Should the user be notified?"

11. **Google Calendar integration** via Google API (OAuth2):
    - Fetch upcoming events for the next 24 hours
    - Extract title, start time, end time, location, attendees
    - Pass to Claude for reasoning: "Any meetings coming up soon? Should the user prepare?"

12. **Claude reasoning over data.** When new data is gathered:
    - Load user context (SOUL.md, USER.md, recent MEMORY.md entries)
    - Present the gathered data to Claude via the Agent SDK
    - Claude decides: (a) send notification, (b) no action needed
    - If notification needed, Claude drafts the message

13. **Notification routing** (configurable per type):
    - Configuration in `config.yaml` maps notification types to channels:
      ```yaml
      notifications:
        urgent_email: whatsapp
        calendar_reminder: whatsapp
        daily_summary: terminal
        default: terminal
      ```
    - Supported notification types: `urgent_email`, `calendar_reminder`, `daily_summary`, `task_alert`, `default`

14. **Daily summary.** A special scheduled task (configurable time, default 8:00 AM) that:
    - Summarizes today's calendar
    - Highlights any unread important emails
    - Sends via the configured channel for `daily_summary`

### 4.3 Adapters (Channels)

Inspired by OpenClaw's `ChannelPlugin` interface (`src/channels/plugins/types.plugin.ts`).

15. **Adapter interface.** Each adapter implements a common Python protocol/ABC:
    ```
    - id: str                     — Unique adapter identifier
    - name: str                   — Human-readable name
    - send(to, message) -> None   — Send a message to the user
    - listen(callback) -> None    — Start listening for incoming messages
    - stop() -> None              — Stop the adapter
    ```

16. **Terminal adapter** (Claude Code):
    - Direct stdin/stdout interaction
    - Full skill + hook access
    - Supports one-shot mode (`pyclaw ask "What's on my calendar?"`) and interactive mode
    - Formats responses with Markdown rendering

17. **WhatsApp adapter:**
    - Uses a WhatsApp messaging API (e.g., WhatsApp Business API or a library like `whatsapp-web.py`)
    - QR code pairing for initial setup
    - Receives incoming messages, passes to agent
    - Sends agent responses and heartbeat notifications
    - Supports text messages (media support out of scope for v1)

18. **Adapter registry.** A central registry that:
    - Discovers and loads enabled adapters from configuration
    - Routes outbound messages to the correct adapter based on notification config
    - Dispatches incoming messages from any adapter to the agent

### 4.4 Skills System

Inspired by OpenClaw's `skills/` directory (52 skills, each with a `SKILL.md`).

19. **Convention-based discovery.** The agent scans the `skills/` directory at startup. Each subdirectory containing a `SKILL.md` file is registered as a skill.

20. **SKILL.md format.** Each skill is defined by a single Markdown file with YAML frontmatter:
    ```markdown
    ---
    name: weather
    description: "Get current weather and forecasts (no API key required)."
    metadata:
      requires:
        bins: ["curl"]
    ---

    # Weather

    Instructions for the agent on how to use this skill...

    ## Usage

    ```bash
    curl -s "wttr.in/London?format=3"
    ```
    ```

    Required frontmatter fields:
    - `name` — Skill identifier (string)
    - `description` — One-line description shown in skill listings

    Optional frontmatter fields:
    - `metadata.requires.bins` — List of CLI tools that must be present
    - `metadata.requires.env` — List of environment variables that must be set

21. **Skill loading.** At startup (and on file change):
    - Scan `skills/` for directories containing `SKILL.md`
    - Parse YAML frontmatter for metadata
    - Validate that required binaries/env vars are available
    - Register the skill name and full Markdown content

22. **Skill injection into agent.** When the agent runs:
    - Include a list of available skills (name + description) in the system prompt
    - When the agent decides to use a skill, the full `SKILL.md` content is loaded into context
    - The agent follows the instructions in the Markdown to execute the skill (typically via shell commands)

23. **No public registry.** Skills are local files only. No `npm install`, no download step, no supply chain risk.

### 4.5 Configuration

24. **Central config file** at `config.yaml` with sections for:
    - `memory` — Memory directory path, chunk size, search weights
    - `heartbeat` — Polling intervals, enabled sources, notification routing
    - `adapters` — Which adapters to enable, adapter-specific settings
    - `skills` — Skills directory path
    - `agent` — Default model, system prompt additions
    - `google` — OAuth credentials path for Gmail/Calendar

25. **Environment variables** override config values (e.g., `PYCLAW_GOOGLE_CREDENTIALS_PATH`).

### 4.6 Core Agent

26. **Agent SDK integration.** The agent uses the Claude Agent SDK (`claude-agent-sdk`) as the reasoning engine:
    - System prompt assembled from: SOUL.md + USER.md + memory search results + available skills list
    - Tool use for: shell commands (skill execution), memory search, sending notifications
    - Conversation history maintained within a session

27. **Session management.** Each interaction creates or continues a session:
    - Sessions persist conversation history for multi-turn interactions
    - Sessions expire after configurable idle timeout (default: 30 minutes)
    - Session transcripts are logged to `memory/daily/`

---

## 5. Non-Goals (Out of Scope)

- **No web UI** — v1 is terminal + WhatsApp only
- **No multi-user support** — This is a single-user personal agent
- **No public skill registry** — Skills are local files only, by design
- **No media handling in WhatsApp** — v1 supports text messages only
- **No voice/TTS** — Text-only interactions
- **No real-time push notifications from Google** — Uses polling, not webhooks
- **No plugin SDK / extension API** — Skills via SKILL.md are the extension mechanism
- **No daemon/gateway architecture** — Runs as a single Python process
- **No encryption at rest** — Relies on OS-level disk encryption

---

## 6. Design Considerations

### Directory Structure

```
pyclaw/
  config.yaml                  # Central configuration
  memory/
    SOUL.md                    # Agent personality & values
    USER.md                    # User identity & preferences
    MEMORY.md                  # Accumulated decisions & lessons
    daily/                     # Session logs (YYYY-MM-DD.md)
  skills/
    weather/SKILL.md           # Example skill
    github/SKILL.md            # Example skill
    ...
  src/
    __init__.py
    main.py                    # Entry point
    agent.py                   # Claude Agent SDK integration
    memory/
      __init__.py
      manager.py               # Memory index manager
      schema.py                # SQLite schema setup
      chunker.py               # Markdown chunking
      embeddings.py            # fastembed integration
      search.py                # Hybrid search (vector + BM25)
    heartbeat/
      __init__.py
      scheduler.py             # APScheduler or similar
      gmail.py                 # Gmail polling
      calendar.py              # Google Calendar polling
      notifier.py              # Notification routing
    adapters/
      __init__.py
      base.py                  # Adapter ABC/protocol
      terminal.py              # Terminal adapter
      whatsapp.py              # WhatsApp adapter
      registry.py              # Adapter discovery & routing
    skills/
      __init__.py
      loader.py                # Skill discovery & loading
      types.py                 # Skill data classes
    config.py                  # Config loading & validation
  data/
    memory.db                  # SQLite database (auto-created)
  tests/
    ...
```

### Key Technology Choices

| Component | Technology | Rationale |
|-----------|-----------|-----------|
| Language | Python 3.12 | User requirement |
| LLM | Claude via Agent SDK | User requirement |
| Embeddings | fastembed | Local, no API key, fast |
| Vector DB | sqlite-vec | Single-file DB, no server |
| FTS | SQLite FTS5 | Built-in, BM25 ranking |
| Scheduler | APScheduler or `schedule` | Lightweight, in-process |
| Gmail/Calendar | Google API Python client | Official, well-documented |
| WhatsApp | whatsapp-web.py or Business API | Community library |
| Config | PyYAML | Simple, human-readable |
| File watching | watchdog | Cross-platform fs events |

---

## 7. Technical Considerations

- **Google OAuth2 setup** is required for Gmail and Calendar access. The user must create a Google Cloud project and download OAuth credentials. A one-time auth flow stores the refresh token locally.
- **fastembed models** run locally on CPU. The default model (`BAAI/bge-small-en-v1.5`, 384 dimensions) is small enough to run on any machine. First run downloads the model (~130MB).
- **sqlite-vec** requires a compiled extension. It can be installed via `pip install sqlite-vec`. Compatibility should be verified on the target platform.
- **WhatsApp adapter** may require running a browser session for QR pairing (if using `whatsapp-web.py`). Alternatively, WhatsApp Business API provides a more stable but complex setup.
- **Claude Agent SDK** is used for both interactive conversations and heartbeat reasoning. API key is required (`ANTHROPIC_API_KEY`).
- **Obsidian compatibility** — The `memory/` directory is a standard folder of Markdown files. Point Obsidian at it as a vault for cross-device sync and browsing. No special integration needed.
- **Concurrency** — The heartbeat scheduler runs in a background thread. Adapter listeners run in their own threads/async loops. The SQLite database uses WAL mode for concurrent read access.

---

## 8. Success Metrics

1. **Memory retrieval accuracy** — When asked about a past decision/preference, the agent finds the relevant memory chunk in the top-5 results at least 80% of the time.
2. **Heartbeat reliability** — Gmail and Calendar checks run on schedule with < 5% missed polls over a 24-hour period.
3. **Notification delivery** — Notifications reach the correct channel (WhatsApp or terminal) within 60 seconds of the heartbeat reasoning completing.
4. **Skill discovery** — A new `SKILL.md` dropped into `skills/` is available to the agent on next interaction without restart (or within 30 seconds via file watch).
5. **Session continuity** — The agent maintains context within a session and correctly references prior messages in multi-turn conversations.
6. **End-to-end latency** — From user message to agent response: < 10 seconds (excluding LLM API latency).

---

## 9. Open Questions

1. **WhatsApp library choice** — Should we use `whatsapp-web.py` (reverse-engineered protocol, may break) or WhatsApp Business API (official but requires Meta business verification)? Need to evaluate stability vs. setup complexity.
2. **Embedding model selection** — `fastembed` supports multiple models. Should we default to `BAAI/bge-small-en-v1.5` (fast, 384d) or `BAAI/bge-base-en-v1.5` (better quality, 768d)?
3. **Session log format** — What should the daily session log entries look like? Full conversation transcript vs. AI-generated summary?
4. **Memory file editing** — If the user edits `MEMORY.md` in Obsidian, should the agent detect and re-index immediately, or only on next startup?
5. **Heartbeat prompt** — What system prompt should Claude use when reasoning over Gmail/Calendar data? Should it be configurable or hardcoded?
6. **Google API quotas** — Gmail API has rate limits. At 15-minute polling intervals, are we within free tier limits?
