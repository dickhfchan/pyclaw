from __future__ import annotations

import time
from pathlib import Path

import pytest

from src.session import Session, SessionManager


def test_create_session() -> None:
    mgr = SessionManager()
    session = mgr.create_session()
    assert session.id
    assert session.messages == []


def test_get_session() -> None:
    mgr = SessionManager()
    session = mgr.create_session()
    retrieved = mgr.get_session(session.id)
    assert retrieved is session


def test_get_session_missing() -> None:
    mgr = SessionManager()
    assert mgr.get_session("nonexistent") is None


def test_get_or_create_existing() -> None:
    mgr = SessionManager()
    session = mgr.create_session()
    retrieved = mgr.get_or_create_session(session.id)
    assert retrieved.id == session.id


def test_get_or_create_new() -> None:
    mgr = SessionManager()
    session = mgr.get_or_create_session(None)
    assert session.id


def test_touch_updates_timestamp() -> None:
    mgr = SessionManager()
    session = mgr.create_session()
    old_time = session.last_active
    time.sleep(0.01)
    mgr.touch(session.id)
    assert session.last_active >= old_time


def test_add_exchange() -> None:
    mgr = SessionManager()
    session = mgr.create_session()
    messages = [{"role": "user", "content": "hi"}]
    mgr.add_exchange(session.id, "hi", "hello", messages)
    assert session.messages == messages


def test_session_expiry() -> None:
    mgr = SessionManager(timeout_minutes=0)  # Expire immediately
    session = mgr.create_session()
    session.last_active = time.time() - 1  # Force into the past
    assert mgr.get_session(session.id) is None


def test_cleanup_expired() -> None:
    mgr = SessionManager(timeout_minutes=0)
    s1 = mgr.create_session()
    s2 = mgr.create_session()
    s1.last_active = time.time() - 1
    s2.last_active = time.time() - 1
    count = mgr.cleanup_expired()
    assert count == 2
    assert mgr.active_sessions == []


def test_active_sessions() -> None:
    mgr = SessionManager(timeout_minutes=60)
    s1 = mgr.create_session()
    s2 = mgr.create_session()
    assert len(mgr.active_sessions) == 2


def test_log_and_close(tmp_path: Path) -> None:
    daily_dir = tmp_path / "daily"
    mgr = SessionManager(daily_dir=daily_dir)
    session = mgr.create_session()
    mgr.add_exchange(session.id, "hello", "hi", [])

    mgr.log_and_close(
        session.id,
        query_summary="Test query",
        response_summary="Test response",
        decisions=["Decision A"],
    )

    # Session should be removed
    assert mgr.get_session(session.id) is None

    # Daily file should exist
    files = list(daily_dir.glob("*.md"))
    assert len(files) == 1
    content = files[0].read_text()
    assert "Test query" in content
    assert "Test response" in content
    assert "Decision A" in content


def test_log_and_close_missing_session() -> None:
    mgr = SessionManager()
    # Should not raise
    mgr.log_and_close("nonexistent", "q", "r")
