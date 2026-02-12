from __future__ import annotations

import base64
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _get_gmail_service(credentials_path: str, token_path: str) -> Any:
    """Build and return an authenticated Gmail API service."""
    from google.auth.transport.requests import Request  # type: ignore[import-untyped]
    from google.oauth2.credentials import Credentials  # type: ignore[import-untyped]
    from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore[import-untyped]
    from googleapiclient.discovery import build  # type: ignore[import-untyped]

    SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
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

    return build("gmail", "v1", credentials=creds)


def fetch_unread_emails(
    credentials_path: str = "credentials.json",
    token_path: str = "token.json",
    since_timestamp: float | None = None,
    max_results: int = 20,
) -> list[dict[str, Any]]:
    """Fetch unread emails from Gmail.

    Args:
        credentials_path: Path to Google OAuth credentials file.
        token_path: Path to stored OAuth token.
        since_timestamp: Unix timestamp. Only fetch emails after this time.
        max_results: Maximum number of emails to return.

    Returns:
        List of dicts with: sender, subject, snippet, timestamp, labels.
    """
    service = _get_gmail_service(credentials_path, token_path)

    query = "is:unread"
    if since_timestamp:
        dt = datetime.fromtimestamp(since_timestamp, tz=timezone.utc)
        query += f" after:{dt.strftime('%Y/%m/%d')}"

    results = (
        service.users()
        .messages()
        .list(userId="me", q=query, maxResults=max_results)
        .execute()
    )

    messages = results.get("messages", [])
    emails: list[dict[str, Any]] = []

    for msg_ref in messages:
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=msg_ref["id"], format="metadata")
            .execute()
        )

        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        emails.append({
            "sender": headers.get("From", ""),
            "subject": headers.get("Subject", ""),
            "snippet": msg.get("snippet", ""),
            "timestamp": int(msg.get("internalDate", 0)) / 1000,
            "labels": msg.get("labelIds", []),
        })

    return emails
