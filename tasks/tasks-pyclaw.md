## Relevant Files

- `config.yaml` - Central configuration file for all subsystems (memory, heartbeat, adapters, skills, agent, google)
- `requirements.txt` - Python dependencies (claude-agent-sdk, fastembed, sqlite-vec, google-api-python-client, watchdog, pyyaml, apscheduler, etc.)
- `pyproject.toml` - Python project metadata and build configuration
- `src/__init__.py` - Package init
- `src/main.py` - CLI entry point, argument parsing, orchestration of all subsystems
- `src/main_test.py` - Tests for CLI entry point
- `src/config.py` - Config loading, validation, env var overrides
- `src/config_test.py` - Tests for config loading
- `src/memory/__init__.py` - Memory package init
- `src/memory/manager.py` - Memory index manager: sync, index, re-index orchestration
- `src/memory/manager_test.py` - Tests for memory manager
- `src/memory/schema.py` - SQLite schema setup (files, chunks, chunks_fts, embedding_cache tables)
- `src/memory/schema_test.py` - Tests for schema creation
- `src/memory/chunker.py` - Markdown chunking with overlap
- `src/memory/chunker_test.py` - Tests for chunking logic
- `src/memory/embeddings.py` - fastembed integration for generating embeddings
- `src/memory/embeddings_test.py` - Tests for embedding generation
- `src/memory/search.py` - Hybrid search (vector + BM25 merge)
- `src/memory/search_test.py` - Tests for hybrid search
- `src/skills/__init__.py` - Skills package init
- `src/skills/loader.py` - Skill discovery, YAML frontmatter parsing, validation
- `src/skills/loader_test.py` - Tests for skill loader
- `src/skills/types.py` - Skill data classes
- `src/adapters/__init__.py` - Adapters package init
- `src/adapters/base.py` - Adapter ABC/protocol definition
- `src/adapters/terminal.py` - Terminal adapter (interactive + one-shot)
- `src/adapters/terminal_test.py` - Tests for terminal adapter
- `src/adapters/whatsapp.py` - WhatsApp adapter (pairing, send, listen)
- `src/adapters/whatsapp_test.py` - Tests for WhatsApp adapter
- `src/adapters/registry.py` - Adapter discovery, loading, message routing
- `src/adapters/registry_test.py` - Tests for adapter registry
- `src/heartbeat/__init__.py` - Heartbeat package init
- `src/heartbeat/scheduler.py` - APScheduler setup, job registration
- `src/heartbeat/scheduler_test.py` - Tests for scheduler
- `src/heartbeat/gmail.py` - Gmail polling via Google API
- `src/heartbeat/gmail_test.py` - Tests for Gmail polling
- `src/heartbeat/calendar.py` - Google Calendar polling via Google API
- `src/heartbeat/calendar_test.py` - Tests for Calendar polling
- `src/heartbeat/notifier.py` - Notification routing (type -> channel mapping)
- `src/heartbeat/notifier_test.py` - Tests for notifier
- `src/agent.py` - Claude Agent SDK integration, system prompt assembly, tool definitions
- `src/agent_test.py` - Tests for agent integration
- `src/session.py` - Session management (history, expiry, transcript logging)
- `src/session_test.py` - Tests for session management
- `memory/SOUL.md` - Agent personality and values (user-authored)
- `memory/USER.md` - User identity and preferences (user-authored)
- `memory/MEMORY.md` - Accumulated decisions and lessons
- `memory/daily/` - Daily session log directory
- `skills/` - Skills directory (user drops SKILL.md files here)
- `data/memory.db` - SQLite database (auto-created at runtime)

### Notes

- Unit tests should be placed alongside the code files they test (e.g., `manager.py` and `manager_test.py` in the same directory).
- Use `python -m pytest [optional/path/to/test/file]` to run tests. Running without a path executes all tests.
- The project uses Python 3.12. Ensure your environment matches.
- `fastembed` will download the embedding model (~130MB) on first run.
- Google OAuth2 credentials must be set up manually before the heartbeat system can function.

## Instructions for Completing Tasks

**IMPORTANT:** As you complete each task, you must check it off in this markdown file by changing `- [ ]` to `- [x]`. This helps track progress and ensures you don't skip any steps.

Example:
- `- [ ] 1.1 Read file` → `- [x] 1.1 Read file` (after completing)

Update the file after completing each sub-task, not just after completing an entire parent task.

## Tasks

- [x] 0.0 Create feature branch
  - [x] 0.1 Create and checkout a new branch for this feature (`git checkout -b feature/pyclaw-core`)

- [x] 1.0 Set up project structure and configuration
  - [x] 1.1 Create `pyproject.toml` with project metadata, Python 3.12 requirement, and script entry point (`pyclaw = "src.main:main"`)
  - [x] 1.2 Create `requirements.txt` with all dependencies: `anthropic`, `claude-agent-sdk`, `fastembed`, `sqlite-vec`, `google-api-python-client`, `google-auth-oauthlib`, `watchdog`, `pyyaml`, `apscheduler`, `pytest`
  - [x] 1.3 Create the directory structure: `src/`, `src/memory/`, `src/skills/`, `src/adapters/`, `src/heartbeat/`, `memory/`, `memory/daily/`, `skills/`, `data/`, `tests/`
  - [x] 1.4 Create `__init__.py` files in all `src/` subdirectories
  - [x] 1.5 Create `config.yaml` with all config sections (memory, heartbeat, adapters, skills, agent, google) with sensible defaults
  - [x] 1.6 Implement `src/config.py` — load `config.yaml`, validate required fields, support env var overrides (e.g., `PYCLAW_GOOGLE_CREDENTIALS_PATH`, `ANTHROPIC_API_KEY`)
  - [x] 1.7 Write tests for `src/config.py` — test loading, defaults, env var overrides, missing file handling
  - [x] 1.8 Create starter `memory/SOUL.md`, `memory/USER.md`, and `memory/MEMORY.md` with template content and comments explaining their purpose
  - [x] 1.9 Add a `.gitignore` with entries for `data/`, `__pycache__/`, `.env`, `*.pyc`, `token.json` (Google OAuth)

- [x] 2.0 Implement the Memory System
  - [x] 2.1 Implement `src/memory/schema.py` — function `ensure_schema(db_path)` that creates/opens a SQLite database and creates the `files`, `chunks`, `chunks_fts` (FTS5), and `embedding_cache` tables. Load the `sqlite-vec` extension and create the vector virtual table. Enable WAL mode.
  - [x] 2.2 Write tests for `src/memory/schema.py` — verify all tables are created, verify idempotency (running twice doesn't error), verify WAL mode is set
  - [x] 2.3 Implement `src/memory/chunker.py` — function `chunk_markdown(content, chunk_tokens=2000, overlap_tokens=200)` that splits Markdown text into overlapping chunks. Each chunk records `start_line`, `end_line`, `text`, and a SHA-256 `hash`. Respect heading boundaries where possible.
  - [x] 2.4 Write tests for `src/memory/chunker.py` — test with short content (single chunk), long content (multiple chunks), overlap correctness, empty content, line number tracking
  - [x] 2.5 Implement `src/memory/embeddings.py` — class `EmbeddingProvider` wrapping `fastembed`. Methods: `embed(text) -> list[float]`, `embed_batch(texts) -> list[list[float]]`. Default model: `BAAI/bge-small-en-v1.5`. Cache embeddings by content hash in the `embedding_cache` table.
  - [x] 2.6 Write tests for `src/memory/embeddings.py` — test single embedding dimension (384), batch embedding, cache hit/miss
  - [x] 2.7 Implement `src/memory/search.py` — functions: `search_vector(db, query_embedding, top_k)` using sqlite-vec cosine similarity, `search_keyword(db, query_text, top_k)` using FTS5 BM25, and `search_hybrid(db, query_text, query_embedding, top_k, vector_weight=0.7, text_weight=0.3)` that merges both result sets with weighted scoring
  - [x] 2.8 Write tests for `src/memory/search.py` — test vector search returns ranked results, keyword search returns BM25-ranked results, hybrid merge correctly combines and deduplicates, edge cases (no results, single result)
  - [x] 2.9 Implement `src/memory/manager.py` — class `MemoryManager` that orchestrates: (a) scanning `memory/` for `.md` files, (b) detecting new/changed/deleted files by comparing content hash to `files` table, (c) chunking changed files, (d) generating embeddings for new chunks, (e) updating `chunks` and `files` tables, (f) updating FTS index. Methods: `sync()`, `search(query, top_k=5)`, `get_context(query)` (returns formatted memory snippets for agent prompt)
  - [x] 2.10 Write tests for `src/memory/manager.py` — test full sync cycle (add file, modify file, delete file), search after sync, context formatting
  - [x] 2.11 Implement file watching in `MemoryManager` using `watchdog` — watch `memory/` directory for `.md` file changes and trigger `sync()` automatically with a debounce (5 seconds)
  - [x] 2.12 Implement session logging — function `log_session(daily_dir, timestamp, query_summary, response_summary, decisions)` that appends an entry to `memory/daily/YYYY-MM-DD.md`

- [ ] 3.0 Implement the Skills System
  - [ ] 3.1 Implement `src/skills/types.py` — dataclass `Skill` with fields: `name: str`, `description: str`, `content: str` (full Markdown body), `path: str`, `requires_bins: list[str]`, `requires_env: list[str]`, `available: bool`
  - [ ] 3.2 Implement `src/skills/loader.py` — function `discover_skills(skills_dir)` that: (a) scans subdirectories for `SKILL.md` files, (b) parses YAML frontmatter to extract `name`, `description`, and `metadata`, (c) validates required bins are on `$PATH` via `shutil.which()`, (d) validates required env vars are set, (e) returns a list of `Skill` objects with `available` flag set accordingly
  - [ ] 3.3 Write tests for `src/skills/loader.py` — test discovery with valid SKILL.md, missing SKILL.md, invalid frontmatter, missing required binary, missing required env var, empty skills directory
  - [ ] 3.4 Implement skill listing for agent prompt — function `format_skills_list(skills)` that returns a concise Markdown list of available skills (name + description) for injection into the system prompt
  - [ ] 3.5 Implement skill content retrieval — function `get_skill_content(skills, skill_name)` that returns the full Markdown body of a skill for injection into agent context when the skill is invoked
  - [ ] 3.6 Add file watching to skill loader — watch `skills/` directory for changes to `SKILL.md` files and re-run discovery automatically

- [ ] 4.0 Implement the Adapters System
  - [ ] 4.1 Implement `src/adapters/base.py` — abstract base class `Adapter` with: `id: str`, `name: str`, abstract methods `send(to: str, message: str) -> None`, `listen(callback: Callable) -> None`, `stop() -> None`
  - [ ] 4.2 Implement `src/adapters/terminal.py` — class `TerminalAdapter(Adapter)` supporting: (a) interactive mode: read from stdin in a loop, call the agent callback with each message, print the response with Markdown formatting, (b) one-shot mode: accept a single query as CLI argument, print the response, and exit
  - [ ] 4.3 Write tests for `src/adapters/terminal.py` — test one-shot mode with mocked agent callback, test message formatting
  - [ ] 4.4 Implement `src/adapters/whatsapp.py` — class `WhatsAppAdapter(Adapter)` supporting: (a) QR code pairing for initial setup, (b) listening for incoming text messages, (c) sending text messages, (d) connection state management (connected/disconnected/reconnecting). Use a WhatsApp library (e.g., `whatsapp-web.py` or equivalent).
  - [ ] 4.5 Write tests for `src/adapters/whatsapp.py` — test send with mocked WhatsApp client, test message callback invocation, test connection state
  - [ ] 4.6 Implement `src/adapters/registry.py` — class `AdapterRegistry` that: (a) loads enabled adapters from config, (b) provides `get_adapter(channel_id)` to retrieve an adapter by ID, (c) provides `send(channel_id, to, message)` to route a message to the correct adapter, (d) starts all adapter listeners
  - [ ] 4.7 Write tests for `src/adapters/registry.py` — test adapter registration, routing to correct adapter, unknown adapter handling

- [ ] 5.0 Implement the Heartbeat System
  - [ ] 5.1 Implement `src/heartbeat/gmail.py` — function `fetch_unread_emails(credentials_path, since_timestamp)` that: (a) authenticates via Google OAuth2 (with stored refresh token), (b) fetches unread emails since last check, (c) returns a list of dicts with `sender`, `subject`, `snippet`, `timestamp`, `labels`. Handle OAuth token refresh automatically.
  - [ ] 5.2 Write tests for `src/heartbeat/gmail.py` — test with mocked Google API client, test token refresh, test empty inbox
  - [ ] 5.3 Implement `src/heartbeat/calendar.py` — function `fetch_upcoming_events(credentials_path, hours_ahead=24)` that: (a) authenticates via Google OAuth2, (b) fetches events for the next N hours, (c) returns a list of dicts with `title`, `start_time`, `end_time`, `location`, `attendees`
  - [ ] 5.4 Write tests for `src/heartbeat/calendar.py` — test with mocked Google API client, test no upcoming events, test multiple events
  - [ ] 5.5 Implement `src/heartbeat/notifier.py` — class `Notifier` that: (a) loads notification routing config (notification_type -> channel mapping), (b) provides `notify(notification_type, message)` that sends via the correct adapter from the registry, (c) falls back to `default` channel if type not configured
  - [ ] 5.6 Write tests for `src/heartbeat/notifier.py` — test routing to correct channel, test fallback to default, test unknown notification type
  - [ ] 5.7 Implement `src/heartbeat/scheduler.py` — class `HeartbeatScheduler` that: (a) uses APScheduler to register periodic jobs, (b) registers a Gmail check job (default: every 15 min), (c) registers a Calendar check job (default: every 15 min), (d) registers a daily summary job (default: 8:00 AM). Each job: gathers data, passes to Claude for reasoning with user context (SOUL.md + USER.md), and calls Notifier if Claude decides a notification is needed.
  - [ ] 5.8 Write tests for `src/heartbeat/scheduler.py` — test job registration, test job execution triggers data fetch + Claude reasoning, test notification sent when Claude decides to notify
  - [ ] 5.9 Implement Google OAuth2 first-time setup flow — a CLI command (`pyclaw auth google`) that runs the OAuth consent flow, stores `token.json` locally, and verifies access to Gmail and Calendar APIs

- [ ] 6.0 Implement the Core Agent
  - [ ] 6.1 Implement `src/agent.py` — class `Agent` that: (a) builds a system prompt from SOUL.md + USER.md + memory search results + available skills list, (b) defines tools for: `search_memory(query)`, `execute_shell(command)`, `send_notification(type, message)`, (c) calls Claude via the Agent SDK with the assembled prompt and tools, (d) handles tool use responses (execute tool, return result to Claude), (e) returns the final text response
  - [ ] 6.2 Write tests for `src/agent.py` — test system prompt assembly includes all components, test tool invocation dispatching, test conversation flow with mocked Claude API
  - [ ] 6.3 Implement `src/session.py` — class `SessionManager` that: (a) creates new sessions with a unique ID, (b) stores conversation history (list of messages) per session, (c) expires sessions after configurable idle timeout (default: 30 min), (d) logs completed sessions to `memory/daily/YYYY-MM-DD.md` via session logging
  - [ ] 6.4 Write tests for `src/session.py` — test session creation, history tracking, expiry after timeout, transcript logging
  - [ ] 6.5 Implement `src/main.py` — CLI entry point that: (a) parses args (`pyclaw chat` for interactive, `pyclaw ask "query"` for one-shot, `pyclaw auth google` for OAuth setup), (b) loads config, (c) initializes MemoryManager and runs initial sync, (d) loads skills, (e) initializes adapters and registry, (f) starts heartbeat scheduler in background thread, (g) starts the appropriate adapter listener based on mode
  - [ ] 6.6 Write tests for `src/main.py` — test CLI argument parsing, test component initialization order

- [ ] 7.0 Integration and end-to-end testing
  - [ ] 7.1 Write an integration test for the memory pipeline: create temp Markdown files -> sync -> search -> verify results contain expected content
  - [ ] 7.2 Write an integration test for the skills pipeline: create a temp `SKILL.md` -> discover -> verify skill appears in agent prompt -> verify skill content is retrievable
  - [ ] 7.3 Write an integration test for the heartbeat pipeline: mock Gmail/Calendar responses -> run scheduler job -> verify Claude is called with correct context -> verify notification is routed to correct adapter
  - [ ] 7.4 Write an integration test for the terminal adapter end-to-end: simulate user input -> verify agent receives message -> verify response is returned -> verify session is logged to daily file
  - [ ] 7.5 Manually test WhatsApp adapter: pair device, send a message, verify response, verify heartbeat notifications arrive
  - [ ] 7.6 Verify Obsidian compatibility: point Obsidian at `memory/` directory, confirm files are visible and editable, confirm edits trigger re-indexing
  - [ ] 7.7 Create a sample skill (`skills/weather/SKILL.md`) and verify the agent can discover and use it in a conversation
