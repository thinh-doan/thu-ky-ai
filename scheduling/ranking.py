"""Personalized deterministic ranking for feasible calendar slots."""

from datetime import datetime, timedelta
from math import inf

from .models import BusyEvent, SchedulingRequest, UserProfile

PERIODS = {"morning": (6, 12), "afternoon": (12, 18), "evening": (18, 22)}


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


def _period_score(start: datetime, end: datetime, preferred: str) -> float:
    window = PERIODS.get(preferred)
    if not window:
        return 100.0
    window_start = start.replace(hour=window[0], minute=0, second=0, microsecond=0)
    window_end = start.replace(hour=window[1], minute=0, second=0, microsecond=0)
    overlap_start = max(start, window_start)
    overlap_end = min(end, window_end)
    overlap = max(0.0, (overlap_end - overlap_start).total_seconds())
    duration = (end - start).total_seconds()
    return _clamp(overlap / duration * 100)


def _buffer_score(start: datetime, end: datetime, busy_events: list[BusyEvent]) -> float:
    before = inf
    after = inf
    for event in busy_events:
        if event.end <= start:
            before = min(before, (start - event.end).total_seconds())
        elif event.start >= end:
            after = min(after, (event.start - end).total_seconds())
    closest = min(before, after)
    return 100.0 if closest == inf else _clamp(closest / 3600 * 100)


def _workload_score(start: datetime, busy_events: list[BusyEvent]) -> float:
    day_start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    minutes = sum(
        max(
            0.0,
            (min(event.end, day_end) - max(event.start, day_start)).total_seconds() / 60,
        )
        for event in busy_events
    )
    if minutes <= 120:
        return 100.0
    if minutes >= 480:
        return 0.0
    return _clamp(100 - (minutes - 120) / 360 * 100)


def _habit_score(start: datetime, event_type: str, profile: UserProfile) -> float:
    hours = profile.hours_for(event_type)
    if not hours:
        return 50.0
    hour = start.hour + start.minute / 60
    distance = min(abs(hour - preferred) for preferred in hours)
    if distance < 0.01:
        return 100.0
    if distance <= 0.5:
        return 85.0
    if distance <= 1.5:
        return 70.0
    if distance <= 2.5:
        return 40.0
    return 20.0


def rank_slot(
    start: datetime,
    end: datetime,
    request: SchedulingRequest,
    busy_events: list[BusyEvent],
    profile: UserProfile,
    rain_probability: float | None = None,
) -> tuple[float, dict[str, float], tuple[str, ...]]:
    weather = 100.0
    if request.avoid_rain and request.is_outdoor:
        weather = 50.0 if rain_probability is None else _clamp(100 - rain_probability)
    breakdown = {
        "availability": 100.0,
        "habit": _habit_score(start, request.event_type, profile),
        "period": _period_score(start, end, request.preferred_period),
        "workload": _workload_score(start, busy_events),
        "buffer": _buffer_score(start, end, busy_events),
        "weather": weather,
        "stability": _clamp(100 - profile.reschedule_rate_for(request.event_type) * 100),
    }
    weights = {
        "availability": 0.22,
        "habit": 0.20,
        "period": 0.14,
        "workload": 0.16,
        "buffer": 0.10,
        "weather": 0.08,
        "stability": 0.10,
    }
    score = round(sum(breakdown[key] * weights[key] for key in weights), 2)
    reasons = ["Không xung đột lịch"]
    if breakdown["habit"] >= 70:
        reasons.append("Phù hợp thói quen cá nhân")
    if breakdown["workload"] >= 70:
        reasons.append("Tải trong ngày thấp")
    if breakdown["buffer"] >= 70:
        reasons.append("Có khoảng nghỉ tốt")
    return score, {key: round(value, 1) for key, value in breakdown.items()}, tuple(reasons)
