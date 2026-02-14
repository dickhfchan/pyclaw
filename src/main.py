from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from src.config import load_config, Config

logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def _init_memory(config: Config) -> "MemoryManager":
    from src.memory.manager import MemoryManager

    db_dir = Path(config.memory.db_path).parent
    db_dir.mkdir(parents=True, exist_ok=True)

    mm = MemoryManager(
        memory_dir=config.memory.dir,
        db_path=config.memory.db_path,
        embedding_model=config.memory.embedding_model,
        chunk_tokens=config.memory.chunk_tokens,
        chunk_overlap=config.memory.chunk_overlap,
        search_top_k=config.memory.search_top_k,
        vector_weight=config.memory.vector_weight,
        text_weight=config.memory.text_weight,
    )
    stats = mm.sync()
    logger.info("Memory sync: %s", stats)

    if config.memory.watch:
        mm.start_watching(config.memory.watch_debounce_seconds)

    return mm


def _init_skills(config: Config) -> list:
    from src.skills.loader import discover_skills
    skills = discover_skills(config.skills.dir)
    logger.info("Skills loaded: %d", len(skills))
    return skills


def _init_adapters(config: Config):
    from src.adapters.registry import AdapterRegistry
    registry = AdapterRegistry.from_config(config.adapters)
    logger.info("Adapters: %s", registry.adapter_ids)
    return registry


def _init_agent(config: Config, memory_manager, skills, notifier=None):
    from src.agent import Agent
    return Agent(
        config=config,
        memory_manager=memory_manager,
        skills=skills,
        notifier=notifier,
    )


def _init_heartbeat(config: Config, memory_manager, notifier, agent):
    from src.heartbeat.scheduler import HeartbeatScheduler

    def reason_fn(context: str, prompt: str) -> str | None:
        return asyncio.run(agent.reason(context, prompt))

    scheduler = HeartbeatScheduler(
        config=config,
        notifier=notifier,
        memory_manager=memory_manager,
        reason_fn=reason_fn,
    )
    return scheduler


def _init_notifier(config: Config, registry):
    from src.heartbeat.notifier import Notifier
    return Notifier(config=config, adapter_registry=registry)


def _run_chat(config: Config) -> None:
    """Interactive chat mode."""
    memory = _init_memory(config)
    skills = _init_skills(config)
    registry = _init_adapters(config)
    notifier = _init_notifier(config, registry)
    agent = _init_agent(config, memory, skills, notifier)

    # Start heartbeat if enabled
    scheduler = None
    if config.heartbeat.enabled:
        scheduler = _init_heartbeat(config, memory, notifier, agent)
        scheduler.start()

    from src.session import SessionManager
    session_mgr = SessionManager(
        timeout_minutes=config.agent.session_timeout_minutes,
        daily_dir=Path(config.memory.dir) / "daily",
    )
    session = session_mgr.create_session()

    from src.adapters.terminal import TerminalAdapter
    terminal = registry.get_adapter("terminal")
    if terminal is None:
        terminal = TerminalAdapter()

    def callback(sender: str, message: str) -> str:
        response, messages = asyncio.run(
            agent.chat(session.messages, message)
        )
        session_mgr.add_exchange(session.id, message, response, messages)
        return response

    try:
        terminal.listen(callback)
    except KeyboardInterrupt:
        pass
    finally:
        if scheduler:
            scheduler.stop()
        session_mgr.log_and_close(
            session.id,
            query_summary="Interactive session",
            response_summary="Session ended",
        )
        memory.close()


async def _run_ask(config: Config, query: str) -> None:
    """One-shot ask mode."""
    memory = _init_memory(config)
    skills = _init_skills(config)
    agent = _init_agent(config, memory, skills)

    response, _ = await agent.chat([], query)
    print(response)
    memory.close()


def _run_auth_google(config: Config) -> None:
    """Run Google OAuth2 consent flow."""
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow

        scopes = [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/calendar.readonly",
        ]

        flow = InstalledAppFlow.from_client_secrets_file(
            config.google.credentials_path,
            scopes=scopes,
        )
        creds = flow.run_local_server(port=0)

        token_path = Path(config.google.token_path)
        token_path.write_text(creds.to_json())
        print(f"Google OAuth2 token saved to {token_path}")
        print("Gmail and Calendar access verified.")

    except FileNotFoundError:
        print(
            f"Error: Credentials file not found at {config.google.credentials_path}\n"
            "Please download OAuth2 credentials from Google Cloud Console."
        )
        sys.exit(1)
    except Exception as e:
        print(f"OAuth2 setup failed: {e}")
        sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="pyclaw",
        description="Ultra-personalized AI agent",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to config file (default: config.yaml)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    subparsers.add_parser("chat", help="Start interactive chat mode")

    ask_parser = subparsers.add_parser("ask", help="Ask a single question")
    ask_parser.add_argument("query", help="The question to ask")

    auth_parser = subparsers.add_parser("auth", help="Authentication setup")
    auth_parser.add_argument("service", choices=["google"], help="Service to authenticate")

    return parser


def main(args: list[str] | None = None) -> None:
    """CLI entry point."""
    _setup_logging()
    parser = build_parser()
    parsed = parser.parse_args(args)
    config = load_config(parsed.config)

    if parsed.command == "chat":
        _run_chat(config)
    elif parsed.command == "ask":
        asyncio.run(_run_ask(config, parsed.query))
    elif parsed.command == "auth":
        if parsed.service == "google":
            _run_auth_google(config)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
