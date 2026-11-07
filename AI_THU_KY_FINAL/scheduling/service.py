"""Pure optimization service for the n8n-facing API."""

from datetime import datetime, timedelta
from typing import Any

from .constraints import is_valid_slot
from .models import BusyEvent, OptimizeRequest, Slot, UserProfile, PERIOD_WINDOWS, normalize_datetime
from .ranking import rank_slot, weather_for


def optimize_schedule(request: OptimizeRequest) -> dict[str, Any]:
    zone = request.zone
    busy_events = [BusyEvent(event, zone) for event in request.busy_events if event.transparency != "transparent"]
    profile = UserProfile(request.user_profile)
    constraints = request.scheduling_constraints
    window_start, window_end = PERIOD_WINDOWS[request.preferred_period]
    day_start = max(constraints.day_start, window_start)
    day_end = min(constraints.day_end, window_end)
    duration = timedelta(minutes=request.duration_minutes)
    step = timedelta(minutes=constraints.step_minutes)
    candidates: list[Slot] = []
    current_day = request.start_date
    while current_day <= request.end_date:
        starts = [request.specific_start_time] if request.specific_start_time else None
        current = normalize_datetime(datetime.combine(current_day, starts[0] if starts else day_start), zone)
        last_start = normalize_datetime(datetime.combine(current_day, request.specific_end_time if request.specific_end_time else day_end), zone) - duration
        while current <= last_start:
            end = current + duration
            rain = weather_for(current, end, [point.model_copy(update={"timestamp": normalize_datetime(point.timestamp, zone)}) for point in request.weather_data])
            valid, applied = is_valid_slot(current, end, busy_events, request.duration_minutes, constraints.min_buffer_minutes, constraints.travel_time_minutes)
            if valid and not (request.is_outdoor and constraints.avoid_rain and rain is not None and rain >= constraints.rain_probability_threshold):
                score, breakdown, explanation = rank_slot(
                    current, end, request.preferred_period, request.event_type, request.is_outdoor,
                    constraints.avoid_rain, rain, busy_events, profile,
                )
                if request.is_outdoor and constraints.avoid_rain and rain is None:
                    applied.append("weather_data_missing")
                elif request.is_outdoor and constraints.avoid_rain:
                    applied.append("weather")
                candidates.append(Slot(current, end, score, breakdown, explanation, applied))
            if starts:
                break
            current += step
        current_day += timedelta(days=1)
    candidates.sort(key=lambda slot: (-slot.score, slot.start))
    picked: list[Slot] = []
    for candidate in candidates:
        if len(picked) >= min(request.number_of_suggestions, constraints.max_results):
            break
        if all(abs((candidate.start - selected.start).total_seconds()) >= 2 * 3600 for selected in picked):
            picked.append(candidate)
    for candidate in candidates:
        if len(picked) >= min(request.number_of_suggestions, constraints.max_results):
            break
        if candidate not in picked:
            picked.append(candidate)
    suggestions = [slot.as_dict(f"S{index}") for index, slot in enumerate(picked, 1)]
    return {
        "success": True,
        "request_id": request.request_id,
        "suggestions": suggestions,
        "score": suggestions[0]["score"] if suggestions else None,
        "score_breakdown": suggestions[0]["score_breakdown"] if suggestions else {},
        "explanation": "Đã tạo và xếp hạng các khung giờ khả dụng." if suggestions else "Không tìm thấy khung giờ đáp ứng các ràng buộc.",
        "constraints_applied": sorted({item for slot in suggestions for item in slot["constraints_applied"]}),
        "error": None if suggestions else {"code": "NO_AVAILABLE_SLOTS", "message": "Không tìm thấy khung giờ phù hợp."},
    }
