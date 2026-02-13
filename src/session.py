from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from src.memory.manager import log_session


@dataclass
class Session:
    """A conversation session with the agent."""

    id: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)


class SessionManager:
    """Manages conversation sessions with timeout and logging."""

    def __init__(
        self,
        timeout_minutes: int = 30,
        daily_dir: str | Path = "memory/daily",
    ) -> None:
        self.timeout_minutes = timeout_minutes
        self.daily_dir = Path(daily_dir)
        self._sessions: dict[str, Session] = {}

    def create_session(self) -> Session:
        """Create a new session with a unique ID."""
        session = Session(id=str(uuid.uuid4()))
        self._sessions[session.id] = session
        return session

    def get_session(self, session_id: str) -> Session | None:
        """Get an active session by ID, or None if expired/missing."""
        session = self._sessions.get(session_id)
        if session is None:
            return None
        if self._is_expired(session):
            self._expire_session(session_id)
            return None
        return session

    def get_or_create_session(self, session_id: str | None = None) -> Session:
        """Get an existing session or create a new one."""
        if session_id:
            session = self.get_session(session_id)
            if session:
                return session
        return self.create_session()

    def touch(self, session_id: str) -> None:
        """Update the last_active timestamp for a session."""
        session = self._sessions.get(session_id)
        if session:
            session.last_active = time.time()

    def add_exchange(
        self,
        session_id: str,
        query: str,
        response: str,
        messages: list[dict[str, Any]] | None = None,
    ) -> None:
        """Record a query/response exchange in the session."""
        session = self._sessions.get(session_id)
        if session is None:
            return
        if messages is not None:
            session.messages = messages
        session.last_active = time.time()

    def log_and_close(
        self,
        session_id: str,
        query_summary: str,
        response_summary: str,
        decisions: list[str] | None = None,
    ) -> None:
        """Log the session to the daily file and remove it."""
        session = self._sessions.get(session_id)
        if session is None:
            return

        timestamp = datetime.fromtimestamp(session.last_active).isoformat()
        log_session(
            daily_dir=self.daily_dir,
            timestamp=timestamp,
            query_summary=query_summary,
            response_summary=response_summary,
            decisions=decisions,
        )

        del self._sessions[session_id]

    def cleanup_expired(self) -> int:
        """Remove expired sessions. Returns the number of sessions cleaned up."""
        expired = [
            sid for sid, session in self._sessions.items()
            if self._is_expired(session)
        ]
        for sid in expired:
            self._expire_session(sid)
        return len(expired)

    @property
    def active_sessions(self) -> list[str]:
        """List IDs of all active (non-expired) sessions."""
        return [
            sid for sid, session in self._sessions.items()
            if not self._is_expired(session)
        ]

    def _is_expired(self, session: Session) -> bool:
        """Check if a session has exceeded the idle timeout."""
        elapsed = time.time() - session.last_active
        return elapsed > self.timeout_minutes * 60

    def _expire_session(self, session_id: str) -> None:
        """Remove an expired session."""
        if session_id in self._sessions:
            del self._sessions[session_id]
