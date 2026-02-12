from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from src.config import Config
    from src.heartbeat.notifier import Notifier
    from src.memory.manager import MemoryManager

logger = logging.getLogger(__name__)


class HeartbeatScheduler:
    """Schedules periodic data-gathering jobs (Gmail, Calendar) and daily summaries.

    Each job gathers data, passes it to a reasoning function (Claude),
    and sends notifications if Claude decides to.
    """

    def __init__(
        self,
        config: Config,
        notifier: Notifier,
        memory_manager: MemoryManager,
        reason_fn: Callable[[str, str], str | None] | None = None,
    ) -> None:
        self._config = config
        self._notifier = notifier
        self._memory = memory_manager
        self._reason_fn = reason_fn
        self._scheduler: Any = None
        self._last_gmail_check: float = 0
        self._last_calendar_check: float = 0

    def start(self) -> None:
        """Start the background scheduler with configured jobs."""
        from apscheduler.schedulers.background import BackgroundScheduler  # type: ignore[import-untyped]

        self._scheduler = BackgroundScheduler()

        hb = self._config.heartbeat

        if hb.gmail.enabled:
            self._scheduler.add_job(
                self._check_gmail,
                "interval",
                minutes=hb.gmail.poll_interval_minutes,
                id="gmail_check",
            )

        if hb.calendar.enabled:
            self._scheduler.add_job(
                self._check_calendar,
                "interval",
                minutes=hb.calendar.poll_interval_minutes,
                id="calendar_check",
            )

        if hb.daily_summary.enabled:
            hour, minute = self._parse_time(hb.daily_summary.time)
            self._scheduler.add_job(
                self._daily_summary,
                "cron",
                hour=hour,
                minute=minute,
                id="daily_summary",
            )

        self._scheduler.start()
        logger.info("Heartbeat scheduler started")

    def stop(self) -> None:
        """Shut down the scheduler."""
        if self._scheduler:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None
            logger.info("Heartbeat scheduler stopped")

    def _check_gmail(self) -> None:
        """Poll Gmail for unread emails and reason over them."""
        try:
            from src.heartbeat.gmail import fetch_unread_emails

            emails = fetch_unread_emails(
                credentials_path=self._config.google.credentials_path,
                token_path=self._config.google.token_path,
                since_timestamp=self._last_gmail_check or None,
            )
            self._last_gmail_check = time.time()

            if not emails:
                return

            # Format email data for reasoning
            email_summary = self._format_emails(emails)
            context = self._get_user_context()
            prompt = (
                f"{context}\n\n"
                f"## New Emails\n{email_summary}\n\n"
                "Based on these emails and the user's preferences, "
                "should the user be notified about any of them? "
                "If yes, write a brief notification message. "
                "If no, respond with exactly: NO_NOTIFICATION"
            )

            response = self._reason(prompt)
            if response and "NO_NOTIFICATION" not in response:
                self._notifier.notify("urgent_email", response)

        except Exception as e:
            logger.error(f"Gmail check failed: {e}")

    def _check_calendar(self) -> None:
        """Poll Google Calendar for upcoming events and reason over them."""
        try:
            from src.heartbeat.calendar import fetch_upcoming_events

            events = fetch_upcoming_events(
                credentials_path=self._config.google.credentials_path,
                token_path=self._config.google.token_path,
                hours_ahead=self._config.heartbeat.calendar.hours_ahead,
            )
            self._last_calendar_check = time.time()

            if not events:
                return

            events_summary = self._format_events(events)
            context = self._get_user_context()
            prompt = (
                f"{context}\n\n"
                f"## Upcoming Events\n{events_summary}\n\n"
                "Based on these events and the user's preferences, "
                "should the user be reminded about anything? "
                "If yes, write a brief reminder. "
                "If no, respond with exactly: NO_NOTIFICATION"
            )

            response = self._reason(prompt)
            if response and "NO_NOTIFICATION" not in response:
                self._notifier.notify("calendar_reminder", response)

        except Exception as e:
            logger.error(f"Calendar check failed: {e}")

    def _daily_summary(self) -> None:
        """Generate and send a daily summary."""
        try:
            from src.heartbeat.calendar import fetch_upcoming_events
            from src.heartbeat.gmail import fetch_unread_emails

            context = self._get_user_context()
            parts = [context, "\n\n## Daily Summary Request\n"]

            try:
                events = fetch_upcoming_events(
                    credentials_path=self._config.google.credentials_path,
                    token_path=self._config.google.token_path,
                    hours_ahead=24,
                )
                if events:
                    parts.append(f"### Today's Calendar\n{self._format_events(events)}\n")
            except Exception:
                parts.append("### Calendar\n(Could not fetch calendar)\n")

            try:
                emails = fetch_unread_emails(
                    credentials_path=self._config.google.credentials_path,
                    token_path=self._config.google.token_path,
                    max_results=10,
                )
                if emails:
                    parts.append(f"### Unread Emails\n{self._format_emails(emails)}\n")
            except Exception:
                parts.append("### Email\n(Could not fetch emails)\n")

            parts.append(
                "Write a concise daily briefing for the user covering their schedule and important emails."
            )

            response = self._reason("\n".join(parts))
            if response:
                self._notifier.notify("daily_summary", response)

        except Exception as e:
            logger.error(f"Daily summary failed: {e}")

    def _reason(self, prompt: str) -> str | None:
        """Call the reasoning function (Claude) with the given prompt."""
        if self._reason_fn:
            return self._reason_fn("heartbeat", prompt)
        return None

    def _get_user_context(self) -> str:
        """Load SOUL.md and USER.md content for context."""
        parts = []
        soul = self._memory.get_file_content("SOUL.md")
        if soul:
            parts.append(soul)
        user = self._memory.get_file_content("USER.md")
        if user:
            parts.append(user)
        return "\n\n".join(parts) if parts else ""

    @staticmethod
    def _format_emails(emails: list[dict]) -> str:
        lines = []
        for e in emails:
            lines.append(f"- **From:** {e['sender']}")
            lines.append(f"  **Subject:** {e['subject']}")
            lines.append(f"  **Preview:** {e['snippet'][:200]}")
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _format_events(events: list[dict]) -> str:
        lines = []
        for e in events:
            lines.append(f"- **{e['title']}**")
            lines.append(f"  {e['start_time']} - {e['end_time']}")
            if e.get("location"):
                lines.append(f"  Location: {e['location']}")
            lines.append("")
        return "\n".join(lines)

    @staticmethod
    def _parse_time(time_str: str) -> tuple[int, int]:
        """Parse a time string like '08:00' into (hour, minute)."""
        parts = time_str.split(":")
        return int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
