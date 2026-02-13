"""Integration test for the heartbeat pipeline.

Mocks Gmail/Calendar responses -> runs scheduler job -> verifies reasoning + notification.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.config import Config
from src.heartbeat.notifier import Notifier
from src.heartbeat.scheduler import HeartbeatScheduler


@pytest.fixture
def memory_manager(tmp_path: Path):
    mm = MagicMock()
    mm.get_file_content.side_effect = lambda name: {
        "SOUL.md": "I am a helpful assistant.",
        "USER.md": "User is a busy engineer.",
    }.get(name)
    return mm


@pytest.fixture
def notifier():
    return MagicMock(spec=Notifier)


@pytest.fixture
def config():
    return Config()


def test_gmail_check_triggers_notification(config, memory_manager, notifier):
    """When emails are found and Claude says to notify, notification is sent."""
    emails = [
        {
            "sender": "boss@company.com",
            "subject": "Urgent: Server down",
            "snippet": "Production server is unresponsive...",
            "timestamp": "2025-01-15T10:00:00Z",
        }
    ]

    def reason_fn(context: str, prompt: str) -> str:
        return "Your boss reports the production server is down. Immediate attention needed."

    scheduler = HeartbeatScheduler(
        config=config,
        notifier=notifier,
        memory_manager=memory_manager,
        reason_fn=reason_fn,
    )

    with patch("src.heartbeat.gmail.fetch_unread_emails", return_value=emails):
        scheduler._check_gmail()

    notifier.notify.assert_called_once()
    call_args = notifier.notify.call_args
    assert call_args[0][0] == "urgent_email"
    assert "server" in call_args[0][1].lower()


def test_gmail_check_no_notification(config, memory_manager, notifier):
    """When Claude says no notification needed, nothing is sent."""
    emails = [
        {
            "sender": "newsletter@example.com",
            "subject": "Weekly digest",
            "snippet": "Here's what happened this week...",
            "timestamp": "2025-01-15T10:00:00Z",
        }
    ]

    def reason_fn(context: str, prompt: str) -> str:
        return "NO_NOTIFICATION"

    scheduler = HeartbeatScheduler(
        config=config,
        notifier=notifier,
        memory_manager=memory_manager,
        reason_fn=reason_fn,
    )

    with patch("src.heartbeat.gmail.fetch_unread_emails", return_value=emails):
        scheduler._check_gmail()

    notifier.notify.assert_not_called()


def test_gmail_check_no_emails(config, memory_manager, notifier):
    """When there are no emails, no reasoning or notification happens."""
    def reason_fn(context: str, prompt: str) -> str:
        raise AssertionError("Should not be called")

    scheduler = HeartbeatScheduler(
        config=config,
        notifier=notifier,
        memory_manager=memory_manager,
        reason_fn=reason_fn,
    )

    with patch("src.heartbeat.gmail.fetch_unread_emails", return_value=[]):
        scheduler._check_gmail()

    notifier.notify.assert_not_called()


def test_calendar_check_triggers_notification(config, memory_manager, notifier):
    """When events are found and Claude says to notify, notification is sent."""
    events = [
        {
            "title": "Team standup",
            "start_time": "2025-01-15T09:00:00",
            "end_time": "2025-01-15T09:15:00",
            "location": "Zoom",
            "attendees": ["alice@company.com"],
        }
    ]

    def reason_fn(context: str, prompt: str) -> str:
        return "You have a team standup in 15 minutes on Zoom."

    scheduler = HeartbeatScheduler(
        config=config,
        notifier=notifier,
        memory_manager=memory_manager,
        reason_fn=reason_fn,
    )

    with patch("src.heartbeat.calendar.fetch_upcoming_events", return_value=events):
        scheduler._check_calendar()

    notifier.notify.assert_called_once()
    assert notifier.notify.call_args[0][0] == "calendar_reminder"


def test_daily_summary_sends_notification(config, memory_manager, notifier):
    """Daily summary gathers data and sends a summary notification."""
    events = [
        {
            "title": "Sprint review",
            "start_time": "2025-01-15T14:00:00",
            "end_time": "2025-01-15T15:00:00",
            "location": "Conference room",
            "attendees": [],
        }
    ]
    emails = [
        {
            "sender": "hr@company.com",
            "subject": "Benefits enrollment",
            "snippet": "Reminder to complete...",
            "timestamp": "2025-01-15T08:00:00Z",
        }
    ]

    def reason_fn(context: str, prompt: str) -> str:
        return "Good morning! You have a sprint review at 2 PM. Also check the HR email about benefits."

    scheduler = HeartbeatScheduler(
        config=config,
        notifier=notifier,
        memory_manager=memory_manager,
        reason_fn=reason_fn,
    )

    with patch("src.heartbeat.calendar.fetch_upcoming_events", return_value=events), \
         patch("src.heartbeat.gmail.fetch_unread_emails", return_value=emails):
        scheduler._daily_summary()

    notifier.notify.assert_called_once()
    assert notifier.notify.call_args[0][0] == "daily_summary"
