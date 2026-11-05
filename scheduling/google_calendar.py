"""Google Calendar adapter for the single-account MVP."""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .models import BusyEvent


class GoogleCalendarError(RuntimeError):
    """Raised when Google Calendar cannot be queried."""


class GoogleCalendarClient:
    def __init__(self, credentials_path: str | None = None, token_path: str | None = None):
        self.credentials_path = Path(
            credentials_path or os.getenv("GOOGLE_CALENDAR_CREDENTIALS", "credentials.json")
        )
        self.token_path = Path(token_path or os.getenv("GOOGLE_CALENDAR_TOKEN", "token.json"))

    def list_busy_events(self, start: datetime, end: datetime) -> list[BusyEvent]:
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise GoogleCalendarError(
                "Thiếu thư viện Google Calendar. Cài dependencies trong requirements.txt."
            ) from exc
        scopes = ["https://www.googleapis.com/auth/calendar.readonly"]
        credentials = None
        if self.token_path.exists():
            credentials = Credentials.from_authorized_user_file(str(self.token_path), scopes)
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        if not credentials or not credentials.valid:
            if not self.credentials_path.exists():
                raise GoogleCalendarError(
                    f"Không tìm thấy credentials tại {self.credentials_path}. "
                    "Đặt GOOGLE_CALENDAR_CREDENTIALS hoặc tạo file secret ngoài repository."
                )
            credentials = InstalledAppFlow.from_client_secrets_file(
                str(self.credentials_path), scopes
            ).run_local_server(port=0)
            self.token_path.write_text(credentials.to_json(), encoding="utf-8")
        service = build("calendar", "v3", credentials=credentials, cache_discovery=False)
        calendars = service.calendarList().list(showDeleted=False).execute().get("items", [])
        events: list[BusyEvent] = []
        for calendar in calendars:
            response = service.events().list(
                calendarId=calendar["id"],
                timeMin=start.astimezone(timezone.utc).isoformat(),
                timeMax=end.astimezone(timezone.utc).isoformat(),
                singleEvents=True,
                orderBy="startTime",
                showDeleted=False,
            ).execute()
            for item in response.get("items", []):
                event_start = _parse_google_datetime(item.get("start", {}))
                event_end = _parse_google_datetime(item.get("end", {}))
                if event_start and event_end and event_end > event_start:
                    events.append(
                        BusyEvent(
                            start=event_start,
                            end=event_end,
                            title=item.get("summary", ""),
                            calendar_id=calendar["id"],
                            location=item.get("location", ""),
                        )
                    )
        return events


def _parse_google_datetime(value: dict[str, Any]) -> datetime | None:
    raw = value.get("dateTime") or value.get("date")
    if not raw:
        return None
    if "T" not in raw:
        return datetime.fromisoformat(raw).replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(raw.replace("Z", "+00:00"))
