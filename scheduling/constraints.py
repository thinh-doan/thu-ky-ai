"""Hard constraint checks for calendar candidates."""

from datetime import datetime, timedelta

from .models import BusyEvent, SchedulingRequest


def overlaps(start: datetime, end: datetime, event: BusyEvent) -> bool:
    return start < event.end and end > event.start


def has_required_buffer(
    start: datetime,
    end: datetime,
    busy_events: list[BusyEvent],
    buffer_minutes: int,
) -> bool:
    buffer_delta = timedelta(minutes=max(0, buffer_minutes))
    for event in busy_events:
        if start < event.end + buffer_delta:
            if end > event.start - buffer_delta:
                return False
    return True


def is_valid_slot(
    start: datetime,
    end: datetime,
    request: SchedulingRequest,
    busy_events: list[BusyEvent],
    rain_probability: float | None = None,
) -> bool:
    if end <= start or (end - start).total_seconds() != request.duration_minutes * 60:
        return False
    if any(overlaps(start, end, event) for event in busy_events):
        return False
    if not has_required_buffer(start, end, busy_events, request.min_buffer_minutes):
        return False
    if request.avoid_rain and request.is_outdoor and rain_probability is not None:
        if rain_probability >= 60:
            return False
    return True
