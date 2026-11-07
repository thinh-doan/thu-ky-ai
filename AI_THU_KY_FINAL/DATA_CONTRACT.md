# Data contract n8n <-> Python

## Input

```json
{
  "user_id": "u-123", "request_id": "req-20261128-001",
  "title": "Họp dự án", "start_date": "2026-11-28", "end_date": "2026-11-28",
  "duration_minutes": 60, "preferred_period": "morning",
  "specific_start_time": "09:00:00", "specific_end_time": "10:00:00",
  "event_type": "work", "is_outdoor": false,
  "busy_events": [{"start": "2026-11-28T08:00:00+07:00", "end": "2026-11-28T08:30:00+07:00"}],
  "weather_data": [],
  "user_profile": {"habit_hours": {"work": [9]}, "reschedule_rate": {"work": 0.1}},
  "scheduling_constraints": {"timezone": "Asia/Ho_Chi_Minh", "step_minutes": 15, "min_buffer_minutes": 15},
  "number_of_suggestions": 3
}
```

`busy_events` và `weather_data` có thể rỗng. WF01 phải trả trạng thái cần bổ sung nếu thiếu ngày/thời lượng; không tự đoán thời gian cụ thể.

## Output

```json
{
  "success": true, "request_id": "req-20261128-001",
  "suggestions": [{
    "slot_id": "S1", "start": "2026-11-28T09:00:00+07:00",
    "end": "2026-11-28T10:00:00+07:00", "score": 92.4,
    "score_breakdown": {"availability": 100, "habit": 100, "period": 100},
    "explanation": "Không xung đột lịch. Phù hợp thói quen cá nhân.",
    "constraints_applied": ["duration", "calendar_conflict", "buffer"]
  }],
  "score": 92.4, "score_breakdown": {}, "explanation": "...",
  "constraints_applied": ["duration", "calendar_conflict"], "error": null
}
```

WF05 chỉ nhận `slot_id`, `start`, `end` từ response đã lưu và tạo đúng khoảng thời gian đó sau khi người dùng xác nhận. Lỗi dùng `{success:false,error:{code,message}}`.
