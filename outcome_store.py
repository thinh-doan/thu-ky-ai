"""outcome_store.py - Lưu CỤC BỘ danh sách sự kiện đang chờ người dùng ghi nhận kết quả (phương án C).

Đặt cạnh navigation.py (thư mục gốc, cùng cấp với 1_main_input.py) để các trang trong pages/ import được:

    from outcome_store import add_events, list_events, mark_recorded, remove_event, unwrap

Vì sao cần file này:
  WF10 (Activity Tracker) nhận kết quả theo `google_event_id`, nhưng người dùng không biết ID đó và WF00
  không có action "liệt kê sự kiện". Mỗi lần tạo lịch thành công (WF05 trả `google_event_id`), giao diện lưu
  sự kiện vào file JSON này; trang `pages/4_record_outcome.py` đọc lại để người dùng báo Hoàn thành / Một phần / Bỏ lỡ,
  kể cả khi họ quay lại ở một phiên khác (WF10 chỉ tự ghi `missed` sau 6 giờ, báo tay sẽ ghi đè).

File dữ liệu: <thư mục này>/data/pending_outcomes.json
Đổi thư mục bằng biến môi trường AI_SECRETARY_DATA_DIR nếu cần (ví dụ ổ đĩa bền vững khi deploy).
Giờ lưu theo giờ VN (UTC+7), dạng 'YYYY-MM-DD HH:MM:SS' - cùng quy ước với WF05/WF09.
"""
import json
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

VN_TZ = timezone(timedelta(hours=7))
DATA_DIR = Path(os.environ.get("AI_SECRETARY_DATA_DIR") or (Path(__file__).resolve().parent / "data"))
DATA_FILE = DATA_DIR / "pending_outcomes.json"
KEEP_RECORDED = 50  # chỉ giữ 50 bản ghi đã báo gần nhất để file không phình ra
_LOCK = threading.Lock()


# ----------------------------- tiện ích dùng chung ----------------------------- #
def now_vn() -> datetime:
    """Giờ hiện tại theo giờ VN (naive)."""
    return datetime.now(VN_TZ).replace(tzinfo=None)


def parse_local(value):
    """Chuỗi giờ (ISO có/không múi giờ, hoặc 'YYYY-MM-DD HH:MM:SS') -> datetime naive giờ VN. Lỗi -> None."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is not None:
        dt = dt.astimezone(VN_TZ).replace(tzinfo=None)
    return dt


def unwrap(data):
    """Bóc phản hồi n8n về dict: [ {...} ] -> {...}; {'body': {...}} -> {...}; {'response': {...}} -> {...}."""
    if isinstance(data, list) and data:
        data = data[0]
    if isinstance(data, dict) and isinstance(data.get("body"), (dict, list)):
        data = data["body"]
        if isinstance(data, list) and data:
            data = data[0]
    if isinstance(data, dict) and isinstance(data.get("response"), dict):
        data = data["response"]
    return data


def _fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else None


# ----------------------------- đọc / ghi file ----------------------------- #
def _read() -> list:
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else []


def _write(records: list) -> None:
    pending = [r for r in records if r.get("status") != "recorded"]
    recorded = [r for r in records if r.get("status") == "recorded"]
    recorded.sort(key=lambda r: r.get("recorded_at") or "", reverse=True)
    records = pending + recorded[:KEEP_RECORDED]
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = DATA_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_FILE)  # ghi nguyên tử: không để lại file hỏng nếu bị ngắt giữa chừng


# ----------------------------- API ----------------------------- #
def add_events(user_id: str, events: list) -> int:
    """Thêm sự kiện mới tạo vào danh sách chờ. Mỗi phần tử: {google_event_id, title, start_time, end_time}.
    Bỏ qua phần tử thiếu google_event_id hoặc đã có (idempotent). Trả về số bản ghi thực sự được thêm."""
    added = 0
    with _LOCK:
        records = _read()
        known = {(r.get("user_id"), r.get("google_event_id")) for r in records}
        for ev in events or []:
            gid = str((ev or {}).get("google_event_id") or "").strip()
            if not gid or (user_id, gid) in known:
                continue
            start, end = parse_local(ev.get("start_time")), parse_local(ev.get("end_time"))
            if start is None:
                continue
            records.append({
                "user_id": user_id,
                "google_event_id": gid,
                "title": str(ev.get("title") or "(không tiêu đề)")[:200],
                "start_time": _fmt(start),
                "end_time": _fmt(end or start),
                "status": "pending",
                "created_at": _fmt(now_vn()),
            })
            known.add((user_id, gid))
            added += 1
        if added:
            _write(records)
    return added


def list_events(user_id: str, status: str = "pending") -> list:
    """Danh sách bản ghi của user theo trạng thái ('pending' | 'recorded'), sắp xếp theo giờ bắt đầu."""
    with _LOCK:
        rows = [r for r in _read() if r.get("user_id") == user_id and r.get("status", "pending") == status]
    rows.sort(key=lambda r: r.get("start_time") or "", reverse=(status == "recorded"))
    return rows


def mark_recorded(user_id: str, google_event_id: str, outcome: str, actual_minutes=None, note=None) -> bool:
    """Đánh dấu đã báo kết quả (sau khi WF10 trả outcome_recorded). Trả True nếu tìm thấy bản ghi."""
    with _LOCK:
        records = _read()
        hit = False
        for r in records:
            if r.get("user_id") == user_id and r.get("google_event_id") == google_event_id:
                r.update(status="recorded", outcome=outcome, actual_minutes=actual_minutes,
                         note=note or None, recorded_at=_fmt(now_vn()))
                hit = True
        if hit:
            _write(records)
    return hit


def remove_event(user_id: str, google_event_id: str) -> bool:
    """Xóa bản ghi khỏi danh sách (ví dụ sự kiện đã bị xóa trên Google Calendar)."""
    with _LOCK:
        records = _read()
        kept = [r for r in records
                if not (r.get("user_id") == user_id and r.get("google_event_id") == google_event_id)]
        if len(kept) != len(records):
            _write(kept)
            return True
    return False
