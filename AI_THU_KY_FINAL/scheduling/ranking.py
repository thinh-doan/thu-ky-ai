"""Deterministic ranking based on the existing engine's scoring factors."""

from datetime import datetime, timedelta
from math import inf

from .models import BusyEvent, UserProfile, WeatherPoint


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


def weather_for(start: datetime, end: datetime, points: list[WeatherPoint]) -> float | None:
    matching = [
        point.rain_probability
        for point in points
        if point.rain_probability is not None
        and start < point.timestamp + timedelta(hours=1)
        and end > point.timestamp
    ]
    return max(matching) if matching else None


def _period_score(start: datetime, end: datetime, preferred_period: str) -> float:
    windows = {"morning": (6, 12), "afternoon": (12, 18), "evening": (18, 22)}
    window = windows.get(preferred_period)
    if not window:
        return 100.0
    window_start = start.replace(hour=window[0], minute=0, second=0, microsecond=0)
    window_end = start.replace(hour=window[1], minute=0, second=0, microsecond=0)
    overlap = max(0, (min(end, window_end) - max(start, window_start)).total_seconds())
    return _clamp(overlap / (end - start).total_seconds() * 100)


def _buffer_score(start: datetime, end: datetime, busy_events: list[BusyEvent]) -> float:
    before = min((start - event.end).total_seconds() for event in busy_events if event.end <= start) if any(
        event.end <= start for event in busy_events
    ) else inf
    after = min((event.start - end).total_seconds() for event in busy_events if event.start >= end) if any(
        event.start >= end for event in busy_events
    ) else inf
    closest = min(before, after)
    return 100.0 if closest == inf else _clamp(closest / 3600 * 100)


def _workload_score(start: datetime, busy_events: list[BusyEvent]) -> float:
    day_start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = day_start + timedelta(days=1)
    minutes = sum(max(0, (min(event.end, day_end) - max(event.start, day_start)).total_seconds() / 60) for event in busy_events)
    if minutes <= 120:
        return 100.0
    if minutes >= 480:
        return 0.0
    return _clamp(100 - (minutes - 120) / 360 * 100)


def rank_slot(
    start: datetime,
    end: datetime,
    preferred_period: str,
    event_type: str,
    is_outdoor: bool,
    avoid_rain: bool,
    rain_probability: float | None,
    busy_events: list[BusyEvent],
    profile: UserProfile,
) -> tuple[float, dict[str, float], str]:
    habit = profile.hours_for(event_type)
    if habit:
        distance = min(abs(start.hour + start.minute / 60 - hour) for hour in habit)
        habit_score = 100 if distance <= 0.01 else 85 if distance <= 0.5 else 70 if distance <= 1.5 else 40 if distance <= 2.5 else 20
    else:
        habit_score = 50.0
    weather = 100.0 if not (avoid_rain and is_outdoor) else (50.0 if rain_probability is None else _clamp(100 - rain_probability))
    breakdown = {
        "availability": 100.0,
        "habit": float(habit_score),
        "period": _period_score(start, end, preferred_period),
        "workload": _workload_score(start, busy_events),
        "buffer": _buffer_score(start, end, busy_events),
        "weather": weather,
        "stability": _clamp(100 - profile.reschedule_rate_for(event_type) * 100),
    }
    weights = {"availability": 0.22, "habit": 0.20, "period": 0.14, "workload": 0.16, "buffer": 0.10, "weather": 0.08, "stability": 0.10}
    score = round(sum(breakdown[key] * weights[key] for key in weights), 2)
    reasons = ["Không xung đột lịch"]
    if breakdown["habit"] >= 70:
        reasons.append("Phù hợp thói quen cá nhân")
    if breakdown["workload"] >= 70:
        reasons.append("Tải trong ngày thấp")
    if breakdown["buffer"] >= 70:
        reasons.append("Có khoảng nghỉ tốt")
    if is_outdoor and avoid_rain:
        reasons.append("Đã đối chiếu dữ liệu thời tiết theo giờ")
    return score, {key: round(value, 1) for key, value in breakdown.items()}, ". ".join(reasons) + "."
