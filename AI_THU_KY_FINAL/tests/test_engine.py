from datetime import datetime
import json
from pathlib import Path

from scheduling.models import OptimizeRequest
from scheduling.service import optimize_schedule


def base_request(**overrides):
    value = {
        "user_id": "u-1",
        "request_id": "req-1",
        "title": "Họp dự án",
        "start_date": "2026-11-28",
        "end_date": "2026-11-28",
        "duration_minutes": 60,
        "preferred_period": "morning",
        "busy_events": [],
        "weather_data": [],
        "user_profile": {"habit_hours": {"work": [9]}},
        "scheduling_constraints": {"timezone": "Asia/Ho_Chi_Minh", "step_minutes": 15},
        "number_of_suggestions": 3,
    }
    value.update(overrides)
    return OptimizeRequest.model_validate(value)


def test_empty_busy_events_use_configured_timezone_and_15_minute_steps():
    result = optimize_schedule(base_request())
    assert result["success"] is True
    assert result["suggestions"]
    assert result["suggestions"][0]["start"].endswith("+07:00")
    assert all(datetime.fromisoformat(slot["start"]).minute % 15 == 0 for slot in result["suggestions"])


def test_busy_event_and_buffer_are_excluded():
    result = optimize_schedule(base_request(busy_events=[{
        "start": "2026-11-28T08:30:00+07:00",
        "end": "2026-11-28T10:00:00+07:00",
    }], scheduling_constraints={"min_buffer_minutes": 30}))
    assert all(slot["start"][11:16] not in {"08:00", "08:15", "08:30", "08:45", "09:00", "09:15", "09:30", "09:45", "10:00"} for slot in result["suggestions"])


def test_weather_hour_maps_to_quarter_hour_slot():
    result = optimize_schedule(base_request(
        is_outdoor=True,
        weather_data=[{"timestamp": "2026-11-28T09:00:00+07:00", "rain_probability": 80}],
        scheduling_constraints={"avoid_rain": True, "rain_probability_threshold": 60},
    ))
    assert all(slot["start"][11:13] != "09" for slot in result["suggestions"])


def test_no_slot_has_stable_error_shape():
    result = optimize_schedule(base_request(
        duration_minutes=120,
        specific_start_time="09:00:00",
        specific_end_time="11:00:00",
        busy_events=[{"start": "2026-11-28T08:00:00+07:00", "end": "2026-11-28T12:00:00+07:00"}],
    ))
    assert result["success"] is True
    assert result["suggestions"] == []
    assert result["error"]["code"] == "NO_AVAILABLE_SLOTS"


def test_all_workflows_are_valid_and_node_ids_unique():
    for path in sorted((Path(__file__).parents[1] / "n8n").glob("*.json")):
        workflow = json.loads(path.read_text(encoding="utf-8"))
        ids = [node["id"] for node in workflow["nodes"]]
        assert len(ids) == len(set(ids)), path
