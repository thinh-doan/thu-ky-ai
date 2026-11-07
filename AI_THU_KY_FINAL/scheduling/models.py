"""Internal scheduling value objects and API models."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DEFAULT_TIMEZONE = "Asia/Ho_Chi_Minh"
PERIOD_WINDOWS = {
    "morning": (time(6, 0), time(12, 0)),
    "afternoon": (time(12, 0), time(18, 0)),
    "evening": (time(18, 0), time(22, 0)),
    "any": (time(6, 0), time(22, 0)),
}


def configured_zone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(name or DEFAULT_TIMEZONE)
    except Exception as exc:
        raise ValueError(f"Unsupported timezone: {name}") from exc


def normalize_datetime(value: datetime, zone: ZoneInfo) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=zone)
    return value.astimezone(zone)


class BusyEventInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    start: datetime
    end: datetime
    title: str = ""
    calendar_id: str = ""
    location: str = ""
    transparency: str = "opaque"

    @model_validator(mode="after")
    def valid_range(self) -> "BusyEventInput":
        if self.end <= self.start:
            raise ValueError("busy event end must be after start")
        return self


class WeatherPoint(BaseModel):
    model_config = ConfigDict(extra="ignore")

    timestamp: datetime
    rain_probability: float | None = Field(default=None, ge=0, le=100)
    temperature_c: float | None = None
    condition: str | None = None


class UserProfileInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    habit_hours: dict[str, list[float]] = Field(default_factory=dict)
    preferred_periods: dict[str, list[str]] = Field(default_factory=dict)
    reschedule_rate: dict[str, float] = Field(default_factory=dict)

    @field_validator("habit_hours")
    @classmethod
    def validate_hours(cls, value: dict[str, list[float]]) -> dict[str, list[float]]:
        for event_type, hours in value.items():
            if any(hour < 0 or hour >= 24 for hour in hours):
                raise ValueError(f"habit_hours[{event_type}] must contain hours in [0, 24)")
        return value

    @field_validator("reschedule_rate")
    @classmethod
    def validate_rates(cls, value: dict[str, float]) -> dict[str, float]:
        if any(rate < 0 or rate > 1 for rate in value.values()):
            raise ValueError("reschedule_rate values must be between 0 and 1")
        return value


class SchedulingConstraints(BaseModel):
    model_config = ConfigDict(extra="ignore")

    timezone: str = DEFAULT_TIMEZONE
    day_start: time = time(6, 0)
    day_end: time = time(22, 0)
    step_minutes: int = Field(default=15, ge=15, le=60)
    min_buffer_minutes: int = Field(default=15, ge=0, le=240)
    travel_time_minutes: int = Field(default=0, ge=0, le=240)
    avoid_rain: bool = False
    rain_probability_threshold: float = Field(default=60, ge=0, le=100)
    max_results: int = Field(default=3, ge=1, le=20)

    @field_validator("step_minutes")
    @classmethod
    def quarter_hour_step(cls, value: int) -> int:
        if value % 15:
            raise ValueError("step_minutes must be a multiple of 15")
        return value

    @model_validator(mode="after")
    def valid_window(self) -> "SchedulingConstraints":
        if self.day_end <= self.day_start:
            raise ValueError("day_end must be after day_start")
        return self


class OptimizeRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    user_id: str = Field(min_length=1, max_length=200)
    request_id: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=500)
    start_date: date
    end_date: date
    duration_minutes: int = Field(ge=15, le=1440)
    preferred_period: Literal["morning", "afternoon", "evening", "any"] = "any"
    specific_start_time: time | None = None
    specific_end_time: time | None = None
    event_type: str = "personal"
    location: str = ""
    is_outdoor: bool = False
    busy_events: list[BusyEventInput] = Field(default_factory=list)
    weather_data: list[WeatherPoint] = Field(default_factory=list)
    user_profile: UserProfileInput = Field(default_factory=UserProfileInput)
    scheduling_constraints: SchedulingConstraints = Field(default_factory=SchedulingConstraints)
    number_of_suggestions: int = Field(default=3, ge=1, le=20)

    @model_validator(mode="after")
    def valid_dates_and_specific_time(self) -> "OptimizeRequest":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if (self.specific_start_time is None) != (self.specific_end_time is None):
            raise ValueError("specific_start_time and specific_end_time must be provided together")
        if self.specific_start_time and self.specific_end_time:
            start = datetime.combine(self.start_date, self.specific_start_time)
            end = datetime.combine(self.start_date, self.specific_end_time)
            if end <= start or int((end - start).total_seconds() / 60) != self.duration_minutes:
                raise ValueError("specific time range must match duration_minutes")
        return self

    @property
    def zone(self) -> ZoneInfo:
        return configured_zone(self.scheduling_constraints.timezone)


class BusyEvent:
    def __init__(self, value: BusyEventInput, zone: ZoneInfo):
        self.start = normalize_datetime(value.start, zone)
        self.end = normalize_datetime(value.end, zone)
        self.title = value.title
        self.calendar_id = value.calendar_id
        self.location = value.location


class UserProfile:
    def __init__(self, value: UserProfileInput):
        self.habit_hours = {key: tuple(hours) for key, hours in value.habit_hours.items()}
        self.preferred_periods = value.preferred_periods
        self.reschedule_rate = value.reschedule_rate

    def hours_for(self, event_type: str) -> tuple[float, ...]:
        return tuple(self.habit_hours.get(event_type, self.habit_hours.get("any", ())))

    def reschedule_rate_for(self, event_type: str) -> float:
        return max(0.0, min(1.0, self.reschedule_rate.get(event_type, 0.0)))


class Slot:
    def __init__(
        self,
        start: datetime,
        end: datetime,
        score: float,
        score_breakdown: dict[str, float],
        explanation: str,
        constraints_applied: list[str],
    ):
        self.start = start
        self.end = end
        self.score = score
        self.score_breakdown = score_breakdown
        self.explanation = explanation
        self.constraints_applied = constraints_applied

    def as_dict(self, slot_id: str) -> dict[str, Any]:
        return {
            "slot_id": slot_id,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "score": self.score,
            "score_breakdown": self.score_breakdown,
            "explanation": self.explanation,
            "constraints_applied": self.constraints_applied,
        }
