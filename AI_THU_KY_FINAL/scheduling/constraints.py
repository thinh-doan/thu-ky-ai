"""Hard constraint checks. This module never reads external services."""

from datetime import datetime, timedelta

from .models import BusyEvent


def overlaps(start: datetime, end: datetime, event: BusyEvent, buffer_minutes: int = 0) -> bool:
    buffer_delta = timedelta(minutes=max(0, buffer_minutes))
    return start < event.end + buffer_delta and end > event.start - buffer_delta


def is_valid_slot(
    start: datetime,
    end: datetime,
    busy_events: list[BusyEvent],
    duration_minutes: int,
    min_buffer_minutes: int,
    travel_time_minutes: int = 0,
) -> tuple[bool, list[str]]:
    applied = ["duration", "calendar_conflict", "buffer"]
    if end <= start or (end - start).total_seconds() != duration_minutes * 60:
        return False, applied
    buffer = min_buffer_minutes + travel_time_minutes
    if any(overlaps(start, end, event, buffer) for event in busy_events):
        return False, applied
    if travel_time_minutes:
        applied.append("travel_time")
    return True, applied
