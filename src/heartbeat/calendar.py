from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _get_calendar_service(credentials_path: str, token_path: str) -> Any:
    """Build and return an authenticated Google Calendar API service."""
    from google.auth.transport.requests import Request  # type: ignore[import-untyped]
    from google.oauth2.credentials import Credentials  # type: ignore[import-untyped]
    from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore[import-untyped]
    from googleapiclient.discovery import build  # type: ignore[import-untyped]

    SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
    creds = None

    if Path(token_path).exists():
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, "w") as f:
            f.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)


def fetch_upcoming_events(
    credentials_path: str = "credentials.json",
    token_path: str = "token.json",
    hours_ahead: int = 24,
    max_results: int = 20,
) -> list[dict[str, Any]]:
    """Fetch upcoming Google Calendar events.

    Args:
        credentials_path: Path to Google OAuth credentials file.
        token_path: Path to stored OAuth token.
        hours_ahead: How far ahead to look for events (in hours).
        max_results: Maximum number of events to return.

    Returns:
        List of dicts with: title, start_time, end_time, location, attendees.
    """
    service = _get_calendar_service(credentials_path, token_path)

    now = datetime.now(tz=timezone.utc)
    time_max = now + timedelta(hours=hours_ahead)

    events_result = (
        service.events()
        .list(
            calendarId="primary",
            timeMin=now.isoformat(),
            timeMax=time_max.isoformat(),
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    events: list[dict[str, Any]] = []
    for event in events_result.get("items", []):
        start = event.get("start", {}).get("dateTime") or event.get("start", {}).get("date", "")
        end = event.get("end", {}).get("dateTime") or event.get("end", {}).get("date", "")
        attendees = [
            a.get("email", "")
            for a in event.get("attendees", [])
        ]
        events.append({
            "title": event.get("summary", "(No title)"),
            "start_time": start,
            "end_time": end,
            "location": event.get("location", ""),
            "attendees": attendees,
        })

    return events
