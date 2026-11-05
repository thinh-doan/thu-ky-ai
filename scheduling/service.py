"""Application service combining calendar data, profile and slot ranking."""

from dataclasses import dataclass
from datetime import datetime, time, timezone

from .candidates import generate_slots
from .google_calendar import GoogleCalendarClient, GoogleCalendarError
from .models import BusyEvent, SchedulingRequest, Slot, UserProfile


@dataclass(frozen=True)
class SchedulingResult:
    slots: list[Slot]
    busy_events: list[BusyEvent]
    source: str
    warning: str | None = None


class SchedulingService:
    def __init__(
        self,
        calendar_client: GoogleCalendarClient | None = None,
        profile: UserProfile | None = None,
    ):
        self.calendar_client = calendar_client or GoogleCalendarClient()
        self.profile = profile or UserProfile(
            habit_hours={"study": (9.0, 14.0), "personal": (17.0, 19.0)}
        )

    def get_busy_events(self, request: SchedulingRequest) -> tuple[list[BusyEvent], str, str | None]:
        start = datetime.combine(request.start_date, time.min, tzinfo=timezone.utc)
        end = datetime.combine(request.end_date, time.max, tzinfo=timezone.utc)
        try:
            busy = self.calendar_client.list_busy_events(start, end)
        except GoogleCalendarError as exc:
            return [], "unavailable", str(exc)
        return busy, "google_calendar", None

    def recommend(
        self, request: SchedulingRequest, busy_events: list[BusyEvent] | None = None
    ) -> SchedulingResult:
        if busy_events is None:
            busy_events, source, warning = self.get_busy_events(request)
            if warning:
                return SchedulingResult([], busy_events, source, warning)
        else:
            source, warning = "provided", None
        return SchedulingResult(
            generate_slots(request, busy_events, self.profile),
            busy_events,
            source,
            warning,
        )
