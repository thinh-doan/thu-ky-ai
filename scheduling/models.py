"""Typed models used by the scheduling engine."""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True)
class BusyEvent:
    start: datetime
    end: datetime
    title: str = ""
    calendar_id: str = ""
    location: str = ""


@dataclass(frozen=True)
class SchedulingRequest:
    title: str
    duration_minutes: int
    start_date: date
    end_date: date
    preferred_period: str = "any"
    event_type: str = "personal"
    is_outdoor: bool = False
    avoid_rain: bool = False
    location: str = ""
    min_buffer_minutes: int = 15
    step_minutes: int = 15
    max_results: int = 3


@dataclass(frozen=True)
class UserProfile:
    habit_hours: dict[str, tuple[float, ...]] = field(default_factory=dict)
    preferred_periods: dict[str, tuple[str, ...]] = field(default_factory=dict)
    reschedule_rate: dict[str, float] = field(default_factory=dict)

    def hours_for(self, event_type: str) -> tuple[float, ...]:
        return self.habit_hours.get(event_type, self.habit_hours.get("any", ()))

    def reschedule_rate_for(self, event_type: str) -> float:
        return max(0.0, min(1.0, self.reschedule_rate.get(event_type, 0.0)))


@dataclass(frozen=True)
class Slot:
    start: datetime
    end: datetime
    score: float
    score_breakdown: dict[str, float]
    reasons: tuple[str, ...] = ()
    rain_probability: float | None = None
    slot_code: str = ""
    source: str = "scheduling_engine"

    def as_dict(self) -> dict[str, Any]:
        return {
            "start_time": self.start.isoformat(),
            "end_time": self.end.isoformat(),
            "score": self.score,
            "score_breakdown": self.score_breakdown,
            "reasons": list(self.reasons),
            "rain_probability": self.rain_probability,
            "slot_code": self.slot_code,
            "source": self.source,
        }
