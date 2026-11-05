"""Candidate generation from a date range and calendar availability."""

from datetime import datetime, time, timedelta

from .constraints import is_valid_slot
from .models import BusyEvent, SchedulingRequest, Slot, UserProfile
from .ranking import rank_slot


def generate_slots(
    request: SchedulingRequest,
    busy_events: list[BusyEvent],
    profile: UserProfile,
    rain_probabilities: dict[datetime, float] | None = None,
) -> list[Slot]:
    rain_probabilities = rain_probabilities or {}
    slots: list[Slot] = []
    current_day = request.start_date
    timezone_info = busy_events[0].start.tzinfo if busy_events else None
    step = timedelta(minutes=max(5, request.step_minutes))
    duration = timedelta(minutes=request.duration_minutes)
    while current_day <= request.end_date:
        current = datetime.combine(current_day, time(6, 0), tzinfo=timezone_info)
        day_end = datetime.combine(current_day, time(22, 0), tzinfo=timezone_info)
        while current + duration <= day_end:
            end = current + duration
            rain = rain_probabilities.get(current)
            if is_valid_slot(current, end, request, busy_events, rain):
                score, breakdown, reasons = rank_slot(
                    current, end, request, busy_events, profile, rain
                )
                slots.append(
                    Slot(
                        start=current,
                        end=end,
                        score=score,
                        score_breakdown=breakdown,
                        reasons=reasons,
                        rain_probability=rain,
                    )
                )
            current += step
        current_day += timedelta(days=1)
    slots.sort(key=lambda slot: (-slot.score, slot.start))
    selected: list[Slot] = []
    for slot in slots:
        if len(selected) >= request.max_results:
            break
        if all(abs((slot.start - chosen.start).total_seconds()) >= 2 * 3600 for chosen in selected):
            selected.append(slot)
    if len(selected) < request.max_results:
        for slot in slots:
            if len(selected) >= request.max_results:
                break
            if slot not in selected:
                selected.append(slot)
    return [
        Slot(
            start=slot.start,
            end=slot.end,
            score=slot.score,
            score_breakdown=slot.score_breakdown,
            reasons=slot.reasons,
            rain_probability=slot.rain_probability,
            slot_code=f"S{index}",
        )
        for index, slot in enumerate(selected, 1)
    ]
