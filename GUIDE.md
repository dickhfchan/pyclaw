# pyclaw User Guide

A local-first, ultra-personalized AI agent powered by Claude. It remembers your decisions, monitors your email and calendar, and is reachable from WhatsApp or the terminal.

---

## 1. Prerequisites

- Python 3.12 or later
- An [Anthropic API key](https://console.anthropic.com/)

---

## 2. Installation

```bash
cd pyclaw
pip install -r requirements.txt
```

> First run downloads the embedding model (~130MB). This is a one-time download.

---

## 3. API Key

Create a `.env` file in the project root:

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

The app loads this automatically on startup. Alternatively, export it in your shell:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

---

## 4. Personalize Your Agent

### memory/SOUL.md

Defines the agent's personality, values, and communication style. Edit to shape how your agent thinks and responds.

### memory/USER.md

Your personal profile. The agent reads this to personalize responses. Example:

```markdown
# User

## Identity
- Name: Dick
- Role: Software Engineer
- Location: Hong Kong (UTC+8)

## Preferences
- Preferred language: English
- Communication style: Direct and concise

## Work Context
- Current projects: pyclaw
```

### memory/MEMORY.md

Accumulated decisions, lessons, and facts. The agent searches this during conversations. You can edit it manually or let it grow over time through session logging.

### memory/daily/

Session logs are automatically written here as `YYYY-MM-DD.md` files after each conversation.

---

## 5. Running the App

### Interactive Chat

```bash
python -m src.main chat
```

Type messages and get responses in a loop. Press `Ctrl+C` to exit.

### One-Shot Question

```bash
python -m src.main ask "What's the weather in London?"
```

Prints the response and exits.

---

## 6. Skills

Skills are capabilities you can add by dropping a folder with a `SKILL.md` file into the `skills/` directory.

A weather skill is included out of the box at `skills/weather/SKILL.md`.

### Creating a Skill

```
skills/
  my-skill/
    SKILL.md
```

SKILL.md format:

```markdown
---
name: my-skill
description: "Short description of what this skill does."
metadata:
  requires:
    bins: ["curl"]          # CLI tools that must be on PATH (optional)
    env: ["MY_API_KEY"]     # Environment variables that must be set (optional)
---

# My Skill

Instructions for the agent on how to use this skill.
The agent reads these instructions and follows them when the skill is invoked.

## Usage

\```bash
curl -s "https://api.example.com/data"
\```
```

- Skills are discovered automatically at startup and on file change (no restart needed)
- The `available` flag is set based on whether required binaries and env vars are present
- Available skills are listed in the agent's system prompt

---

## 7. Configuration

All settings are in `config.yaml`. Environment variables override config values.

### Environment Variable Overrides

| Env Var | Config Path |
|---------|-------------|
| `ANTHROPIC_API_KEY` | Used by Claude SDK directly |
| `PYCLAW_GOOGLE_CREDENTIALS_PATH` | `google.credentials_path` |
| `PYCLAW_GOOGLE_TOKEN_PATH` | `google.token_path` |
| `PYCLAW_MEMORY_DIR` | `memory.dir` |
| `PYCLAW_MEMORY_DB_PATH` | `memory.db_path` |
| `PYCLAW_SKILLS_DIR` | `skills.dir` |
| `PYCLAW_AGENT_MODEL` | `agent.model` |

### Key Config Sections

```yaml
memory:
  dir: memory                          # Memory files directory
  db_path: data/memory.db             # SQLite database path
  chunk_tokens: 2000                  # Chunk size for indexing
  search_top_k: 5                     # Number of search results
  vector_weight: 0.7                  # Weight for vector search
  text_weight: 0.3                    # Weight for keyword search
  watch: true                         # Auto-reindex on file change

agent:
  model: claude-sonnet-4-20250514     # Claude model to use
  session_timeout_minutes: 30         # Session idle timeout

skills:
  dir: skills                         # Skills directory

adapters:
  terminal:
    enabled: true
  whatsapp:
    enabled: false
```

---

## 8. Gmail & Calendar Heartbeat (Optional)

The heartbeat system polls Gmail and Google Calendar at regular intervals, uses Claude to reason over the data, and sends notifications when something needs your attention.

### Step 1: Google Cloud Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Enable the **Gmail API** and **Google Calendar API**
4. Go to **Credentials** > **Create Credentials** > **OAuth 2.0 Client ID**
5. Select **Desktop app** as the application type
6. Download the credentials file and save it as `credentials.json` in the project root

### Step 2: Authenticate

```bash
python -m src.main auth google
```

This opens a browser window for Google consent. After authorizing, a `token.json` file is saved locally. This is a one-time step — the token auto-refreshes.

### Step 3: Enable in Config

Edit `config.yaml`:

```yaml
heartbeat:
  enabled: true
  gmail:
    enabled: true
    poll_interval_minutes: 15
  calendar:
    enabled: true
    poll_interval_minutes: 15
    hours_ahead: 24
  daily_summary:
    enabled: true
    time: "08:00"
```

### Step 4: Configure Notification Routing

```yaml
notifications:
  urgent_email: whatsapp       # or "terminal"
  calendar_reminder: whatsapp  # or "terminal"
  daily_summary: terminal      # or "whatsapp"
  default: terminal
```

When the heartbeat detects something (e.g., an urgent email), Claude decides whether to notify you and drafts the message. The notification is routed to the configured channel.

---

## 9. WhatsApp Setup (Optional)

The WhatsApp adapter allows you to chat with pyclaw and receive heartbeat notifications via WhatsApp.

### Step 1: Install a WhatsApp Library

pyclaw's WhatsApp adapter accepts any client that implements `connect()`, `disconnect()`, `send_message(to, message)`, and `on_message(callback)`. A recommended option:

```bash
pip install whatsapp-web.py
```

> **Note:** WhatsApp Web libraries use reverse-engineered protocols and may break with WhatsApp updates. Alternatively, you can use the [WhatsApp Business API](https://developers.facebook.com/docs/whatsapp/) for a more stable (but more complex) setup.

### Step 2: Enable in Config

```yaml
adapters:
  terminal:
    enabled: true
  whatsapp:
    enabled: true
```

### Step 3: QR Code Pairing

On first run with WhatsApp enabled, the client will display a QR code in the terminal. Scan it with WhatsApp on your phone:

1. Open WhatsApp on your phone
2. Go to **Settings** > **Linked Devices** > **Link a Device**
3. Scan the QR code displayed in the terminal

Once paired, pyclaw will:
- Listen for incoming WhatsApp messages and respond via Claude
- Send heartbeat notifications (urgent emails, calendar reminders, daily summaries) to your WhatsApp

### Connection States

The WhatsApp adapter manages its connection state automatically:
- **disconnected** — Not connected
- **connecting** — Pairing/connecting in progress
- **connected** — Active and ready
- **reconnecting** — Recovering from a dropped connection

### Step 4: Route Notifications to WhatsApp

In `config.yaml`, set notification types to use the `whatsapp` channel:

```yaml
notifications:
  urgent_email: whatsapp
  calendar_reminder: whatsapp
  daily_summary: whatsapp
  default: terminal
```

---

## 10. Obsidian Sync (Optional)

The `memory/` directory is a standard folder of Markdown files. You can point [Obsidian](https://obsidian.md/) at it as a vault:

1. Open Obsidian
2. **Open folder as vault** > select the `memory/` directory
3. Browse and edit `SOUL.md`, `USER.md`, `MEMORY.md`, and daily logs from any device

Edits made in Obsidian are detected automatically by the file watcher and re-indexed within 5 seconds (configurable via `memory.watch_debounce_seconds`).

---

## 11. Running Tests

```bash
python -m pytest -v
```

This runs all 147+ tests across the full stack: config, memory, skills, adapters, agent, session, CLI, and integration tests.

---

## 12. Project Structure

```
pyclaw/
  .env                          # API keys (not committed)
  config.yaml                   # Central configuration
  requirements.txt              # Python dependencies
  memory/
    SOUL.md                     # Agent personality
    USER.md                     # Your profile
    MEMORY.md                   # Accumulated knowledge
    daily/                      # Session logs (YYYY-MM-DD.md)
  skills/
    weather/SKILL.md            # Sample skill
  src/
    main.py                     # CLI entry point
    agent.py                    # Claude integration + tools
    session.py                  # Session management
    config.py                   # Config loading
    memory/                     # Memory system (chunking, embeddings, search)
    skills/                     # Skill discovery + loading
    adapters/                   # Terminal, WhatsApp, registry
    heartbeat/                  # Gmail, Calendar, scheduler, notifier
  data/
    memory.db                   # SQLite database (auto-created)
  tests/                        # Integration tests
```

---

## 13. Troubleshooting

**"No module named 'fastembed'"** — Run `pip install -r requirements.txt`

**"load_extension" error with sqlite-vec** — Your Python's SQLite was compiled without extension loading. The app degrades gracefully to keyword-only search (no vector search). To fix, install Python from python.org or use `pyenv` with a build that supports extensions.

**"ANTHROPIC_API_KEY not set"** — Create a `.env` file with your key, or export it in your shell.

**Google OAuth fails** — Ensure `credentials.json` exists in the project root. Download it from [Google Cloud Console](https://console.cloud.google.com/) > Credentials.

**WhatsApp won't connect** — Ensure a WhatsApp library is installed (`pip install whatsapp-web.py`). Check that your phone has an active internet connection during QR pairing.

**Memory search returns no results** — Run `python -m src.main chat` first to trigger an initial sync, or check that your `memory/` directory contains `.md` files.
