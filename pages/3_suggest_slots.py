"""MÀN HÌNH 3 - Gợi ý khung giờ trống, chọn lịch Google Calendar và tạo sự kiện.

Chạy:  streamlit run 1_main_input.py   (trang nằm trong pages/)

Khớp workflow:
  - Gợi ý lấy HOÀN TOÀN từ `proposals` của WF04 (top 3 S1..S3, đã chấm điểm theo buổi, thời tiết, khoảng nghỉ,
    nghỉ ngơi và thói quen học từ WF10). Không còn package `scheduling`.
  - Có proposals thật -> tạo lịch theo slot (request_id + selected_slot_code): WF05 khóa slot, kiểm tra xung đột,
    tạo Google Calendar. Trùng lịch (slot_taken) -> cho chọn lịch cần thay thế (replace_conflict).
  - Không có proposals (xem trước / dữ liệu mẫu) -> giữ dữ liệu mẫu FLEX/FIXED và tạo theo lô `events[]` như cũ.
  - "Gợi ý lại" gửi lại yêu cầu gốc kèm điều kiện ở khung bên trái để WF00 chạy lại pipeline.
  - Sau khi tạo thành công, sự kiện được lưu vào outcome_store để ghi nhận kết quả ở pages/4_record_outcome.py (WF10).
"""
from datetime import date, datetime, timedelta
import requests
import streamlit as st
from pages.confirm_action import confirm_action
from navigation import render_stepper, stepper_css
from outcome_store import add_events, parse_local, unwrap

N8N_WEBHOOK_URL = "https://aithuky.app.n8n.cloud/webhook/ai-secretary"
USER_ID = "student@gmail.com"
N8N_TIMEOUT = 120

st.set_page_config(page_title="AI Secretary · Chọn giờ", page_icon="🗓️", layout="wide")

CSS = """<style>
.block-container{padding-top:1.4rem;max-width:1150px}
.hero{background:linear-gradient(135deg,#4F46E5,#7C3AED 55%,#14B8A6 130%);color:#fff;padding:1rem 1.3rem;
 border-radius:16px;box-shadow:0 6px 20px rgba(79,70,229,.25);margin-bottom:1rem}
.hero h2{margin:0;color:#fff;font-size:1.45rem}.hero p{margin:.15rem 0 0;opacity:.9}
.stepper{display:flex;align-items:center;gap:.5rem;margin:.25rem 0 1.2rem}
.step{display:flex;align-items:center;gap:.5rem;font-weight:600;color:#94A3B8}
.dot{width:30px;height:30px;border-radius:50%;display:grid;place-items:center;background:#E2E8F0;color:#64748B;font-size:.9rem}
.step.active{color:#4F46E5}.step.active .dot{background:#4F46E5;color:#fff;box-shadow:0 0 0 4px #E0E7FF}
.step.done{color:#16A34A}.step.done .dot{background:#16A34A;color:#fff}
.bar{flex:1;height:3px;background:#E2E8F0;border-radius:3px;min-width:16px}.bar.done{background:#16A34A}
.tag{display:inline-block;padding:.1rem .55rem;border-radius:999px;font-size:.78rem;font-weight:600;margin:0 .3rem .25rem 0}
.tag.ok{background:#DCFCE7;color:#166534}.tag.warn{background:#FEF3C7;color:#92400E}
.tag.info{background:#E0E7FF;color:#3730A3}
.stButton>button{border-radius:10px;font-weight:600}
.stButton>button[kind="primary"]{background:linear-gradient(135deg,#4F46E5,#6366F1);border:none;
 box-shadow:0 4px 12px rgba(79,70,229,.3)}
</style>"""
st.markdown(CSS, unsafe_allow_html=True)
st.markdown(stepper_css(), unsafe_allow_html=True)


DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DAY_VN = {"Mon": "Thứ 2", "Tue": "Thứ 3", "Wed": "Thứ 4", "Thu": "Thứ 5", "Fri": "Thứ 6", "Sat": "Thứ 7",
          "Sun": "Chủ nhật"}
WINDOWS = {"Morning": [8, 9, 10, 11], "Afternoon": [13, 14, 15, 16], "Evening": [18, 19, 20]}
WINDOW_VN = {"Morning": "Buổi sáng", "Afternoon": "Buổi chiều", "Evening": "Buổi tối"}
BUSY = {("Wed", 9), ("Thu", 13)}
MAX_SLOTS = 3
BREAKDOWN_VN = {"period": "Đúng buổi", "weather": "Thời tiết", "buffer": "Khoảng nghỉ", "rest": "Nghỉ ngơi",
                "habit": "Hợp thói quen"}

FLEX = [
    ("Học: Ôn thi cơ sở dữ liệu", 120, "Cao", False),
    ("Họp nhóm dự án", 90, "Trung bình", False),
    ("Chạy bộ ở Công viên Gia Định", 60, "Thấp", True)
]
FIXED = [
    ("Toán cao cấp", 0, "07:30", "09:30", None),
    ("Vật lý", 1, "09:00", "11:00", "Lịch nha sĩ 09:00"),
    ("Tiếng Anh", 3, "08:00", "09:30", None),
]
CALENDARS = ["Cá nhân (chính)", "Học tập", "Việc làm thêm"]
REMINDERS = {0: "Không nhắc", 10: "Trước 10 phút", 30: "Trước 30 phút", 60: "Trước 1 giờ"}

ss = st.session_state
today = date.today()
ss.setdefault("cons", {"start": today, "end": today + timedelta(days=6), "tod": ["Morning"],
                       "avoid": ["Sun"], "buffer": 15})
ss.setdefault("seed", 0)


def day_key(d):
    """Mon..Sun, không phụ thuộc locale của máy."""
    return DAYS[d.weekday()]


def _constraint_text():
    """Điều kiện ở khung bên trái -> câu tiếng Việt gắn vào yêu cầu gốc khi gợi ý lại."""
    c = ss.cons
    parts = [f"Tìm trong khoảng từ ngày {c['start']:%d/%m/%Y} đến ngày {c['end']:%d/%m/%Y}"]
    if c["tod"]:
        parts.append("ưu tiên " + ", ".join(WINDOW_VN[t].lower() for t in c["tod"]))
    if c["avoid"]:
        parts.append("tránh " + ", ".join(DAY_VN[d].lower() for d in c["avoid"]))
    return ". ".join(parts) + "."


def _resubmit():
    """Gợi ý lại: gửi lại yêu cầu gốc + điều kiện mới cho WF00 (chạy lại AI parse -> lịch trống -> thời tiết -> chấm điểm)."""
    base = (ss.get("base_message") or "").strip()
    if not base:
        ss.regen_error = "Không còn yêu cầu gốc; hãy quay lại Màn hình 1 để nhập lại."
        return
    message = f"{base} {_constraint_text()}"
    try:
        with st.spinner("Đang lấy gợi ý mới từ n8n..."):
            res = requests.post(N8N_WEBHOOK_URL, timeout=N8N_TIMEOUT, json={
                "action": "submit_request", "user_id": USER_ID, "user_email": USER_ID,
                "message": message, "prompt": message,
            })
        if res.status_code != 200:
            ss.regen_error = f"Lỗi n8n ({res.status_code}): {res.text}"
            return
        data = unwrap(res.json())
    except Exception as e:
        ss.regen_error = f"Không thể kết nối đến Webhook n8n: {e}"
        return
    if isinstance(data, dict) and data.get("status") == "proposals_ready":
        ss.resp = data
        ss.request_kind = "text"
        st.toast("Đã cập nhật gợi ý", icon="🔄")
    else:
        msg = (data.get("message") or data.get("user_message")) if isinstance(data, dict) else None
        ss.regen_error = msg or "Không lấy được gợi ý mới."


if ss.pop("regen_pending", False):
    _resubmit()

BACKEND_RESPONSE = ss.get("resp", {})
BACKEND_PROPOSALS = (
    BACKEND_RESPONSE.get("proposals", [])
    if ss.get("request_kind") == "text"
    and isinstance(BACKEND_RESPONSE, dict)
    else []
)
REAL = bool(BACKEND_PROPOSALS)  # có proposals thật từ WF04 -> chạy theo workflow; ngược lại là xem trước dữ liệu mẫu
if REAL:
    FLEX = [(
        BACKEND_RESPONSE.get("title") or "Sự kiện",
        int(BACKEND_RESPONSE.get("duration_minutes") or 60),
        "AI đề xuất",
        bool(BACKEND_RESPONSE.get("avoid_rain", False)),
    )]


def _reasons(p):
    """Lý do hiển thị cho một proposal của WF04: điểm, các tiêu chí tốt, cảnh báo mưa."""
    ok, warn = [], []
    if p.get("score") is not None:
        try:
            ok.append(f"Điểm phù hợp: {float(p['score']):.0f}/100")
        except (TypeError, ValueError):
            ok.append(f"Điểm phù hợp: {p['score']}")
    bd = p.get("score_breakdown") or {}
    for key, label in BREAKDOWN_VN.items():
        v = bd.get(key)
        if isinstance(v, (int, float)) and v >= 80:
            ok.append(f"{label} tốt ({v:.0f})")
    rp = p.get("rain_probability")
    if p.get("is_suitable") is False:
        warn.append(f"🌧 Xác suất mưa cao ({rp}%)" if rp is not None else "🌧 Có thể mưa")
    elif rp is not None and BACKEND_RESPONSE.get("avoid_rain"):
        ok.append(f"Xác suất mưa {rp}%")
    return ok, warn


def make_slots(idx, n):
    if REAL:
        slots = []
        for p in BACKEND_PROPOSALS:
            start, end = parse_local(p.get("start_time")), parse_local(p.get("end_time"))
            if not start or not end or day_key(start) in ss.cons["avoid"]:
                continue
            ok, warn = _reasons(p)
            slots.append({
                "day": start.date(),
                "start": start.hour + start.minute / 60,
                "end": end.hour + end.minute / 60,
                "reasons": ok,
                "warns": warn,
                "rainy": p.get("is_suitable") is False,
                "minutes": int((end - start).total_seconds() // 60),
                "slot_code": p.get("slot_code"),
                "score": p.get("score"),
            })
        return slots[:n]
    c = ss.cons
    hours = [h for t in (c["tod"] or list(WINDOWS)) for h in WINDOWS[t]]
    minutes = FLEX[idx][1]
    slots, day = [], max(c["start"], today)
    while len(slots) < n and day <= c["end"]:
        wd = day_key(day)
        if wd not in c["avoid"]:
            for step in range(len(hours)):
                h = hours[(idx + day.toordinal() + ss.seed + step) % len(hours)]
                if (wd, h) in BUSY:
                    continue
                end_h = h + minutes / 60
                reasons = ["Trống trên Google Calendar"]
                if c["tod"]:
                    reasons.append("Đúng buổi ưu tiên")
                if idx == 0:
                    reasons.append("Trước hạn chót")
                rainy = FLEX[idx][3] and (day.toordinal() + step) % 4 == 0
                slots.append(
                    {"day": day, "start": h, "end": end_h, "reasons": reasons, "warns": [], "rainy": rainy,
                     "minutes": minutes})
                break
        day += timedelta(days=1)
    return slots


def fmt_time(x):
    h, m = int(x), int(round((x % 1) * 60))
    if m == 60:
        h, m = h + 1, 0
    return f"{h:02d}:{m:02d}"


def fmt(slot):
    return f"{DAY_VN[day_key(slot['day'])]} {slot['day']:%d/%m} · {fmt_time(slot['start'])}–{fmt_time(slot['end'])}"


def regenerate():
    ss.cons = {"start": ss.c_dates[0] if len(ss.c_dates) == 2 else today,
               "end": ss.c_dates[1] if len(ss.c_dates) == 2 else today + timedelta(days=6),
               "tod": ss.c_tod, "avoid": ss.c_avoid, "buffer": ss.c_buffer}
    ss.seed += 1
    if REAL:
        ss.regen_pending = True  # gửi lại WF00 ở lần chạy kế tiếp (đầu trang)
    else:
        st.toast("Đã cập nhật gợi ý", icon="🔄")


def reset():
    for k in ("results", "reconnected", "celebrated", "conflict_ctx", "registered"):
        ss.pop(k, None)


def register_outcomes(events):
    """Phương án C: lưu sự kiện vừa tạo để ghi nhận kết quả sau (WF10). Chỉ nhận phần tử có google_event_id."""
    try:
        ss.registered = ss.get("registered", 0) + add_events(USER_ID, events)
    except OSError as e:
        st.warning(f"Không lưu được danh sách ghi nhận kết quả: {e}")


# ----------------------------- Sidebar ----------------------------- #
with st.sidebar:
    st.markdown("### 🗓️ AI Secretary")
    st.success("🟢 Đã kết nối **student@gmail.com**")
    st.divider()

st.markdown(
    '<div class="hero"><h2>🗓️ AI Secretary</h2><p>Chọn khung giờ bạn thích, tôi sẽ thêm vào Google Calendar sau khi bạn xác nhận.</p></div>',
    unsafe_allow_html=True)
render_stepper(4 if "results" in ss else 3)


# ----------------------------- Gửi yêu cầu tạo lịch ----------------------------- #
def post_n8n(payload):
    res = requests.post(N8N_WEBHOOK_URL, json=payload, timeout=N8N_TIMEOUT)
    if res.status_code != 200:
        raise RuntimeError(res.text or f"HTTP {res.status_code}")
    data = unwrap(res.json())
    return data if isinstance(data, dict) else {"status": "error", "message": str(data)}


def handle_single(data, title, when, ctx):
    """Phản hồi WF05 theo slot: created | slot_taken | error."""
    status = data.get("status")
    if status == "created":
        ev = data.get("event") or {}
        ss.results = [{"title": title, "when": when, "ok": True, "err": ""}]
        ss.pop("conflict_ctx", None)
        register_outcomes([{"google_event_id": ev.get("google_event_id"), "title": ev.get("title") or title,
                            "start_time": ev.get("start_time"), "end_time": ev.get("end_time")}])
        return
    ss.results = [{"title": title, "when": when, "ok": False,
                   "err": data.get("message") or "Không tạo được sự kiện"}]
    if status == "slot_taken" and data.get("conflicts"):
        ss.conflict_ctx = {**ctx, "conflicts": data["conflicts"], "title": title, "when": when}
    else:
        ss.pop("conflict_ctx", None)


def handle_batch(data, items, events_payload):
    """Phản hồi WF05 theo lô: results[] cùng thứ tự với events[]."""
    per_event = data.get("results")
    if isinstance(per_event, list) and len(per_event) == len(items):
        ss.results = []
        to_register = []
        for (t, w), r in zip(items, per_event):
            ok = r.get("status") == "created"
            ss.results.append({"title": t, "when": w, "ok": ok,
                               "err": "" if ok else r.get("message", "Không tạo được sự kiện")})
            if ok and r.get("saved_to_db") is not False:  # chỉ sự kiện đã lưu CSDL mới ghi nhận kết quả được
                to_register.append({"google_event_id": r.get("google_event_id"), "title": r.get("title") or t,
                                    "start_time": r.get("start_time"), "end_time": r.get("end_time")})
        register_outcomes(to_register)
    else:
        err_msg = data.get("message", "Phản hồi không hợp lệ từ n8n")
        ss.results = [{"title": t, "when": w, "ok": False, "err": err_msg} for t, w in items]


# ----------------------------- Màn hình kết quả ----------------------------- #
def show_result():
    results = ss.results
    ok = [r for r in results if r["ok"]]
    failed = [r for r in results if not r["ok"]]
    if not failed:
        st.success(f"✅ Đã tạo {len(ok)} sự kiện trên Google Calendar.")
        if not ss.get("celebrated"):
            st.balloons()
            ss.celebrated = True
    else:
        st.warning(f"Đã tạo {len(ok)}, lỗi {len(failed)}.")
    st.subheader("Hoàn tất! 🎉")
    for r in results:
        with st.container(border=True):
            c1, c2 = st.columns([4, 1.5])
            if r["ok"]:
                c1.markdown(f"✅ **{r['title']}** · {r['when']}")
                c2.markdown("[Mở Google Calendar ↗](https://calendar.google.com)")
            else:
                c1.markdown(f"❌ **{r['title']}** · {r['when']}")
                c1.caption(r["err"])

    # Trùng lịch (WF05 slot_taken): cho chọn lịch cần thay thế rồi gửi replace_conflict
    ctx = ss.get("conflict_ctx")
    if ctx and ctx.get("conflicts"):
        conflicts = ctx["conflicts"]

        def _label(c):
            s = parse_local(c.get("start_time"))
            return f"{c.get('title', '(không tiêu đề)')} · {s:%d/%m %H:%M}" if s else c.get("title", "")

        with st.container(border=True):
            st.markdown("**⚠ Khung giờ này đang trùng với lịch khác**")
            pick = st.radio("Chọn lịch muốn thay thế", range(len(conflicts)), key="conflict_pick",
                            format_func=lambda i: _label(conflicts[i]))
            kq_rep = confirm_action(
                st.button("🔁 Thay thế lịch trùng", key="replace_btn"), key="replace",
                message=f"Xóa **{_label(conflicts[pick])}** và tạo **{ctx['title']}** · {ctx['when']}?")
            if kq_rep == "yes":
                try:
                    with st.spinner("Đang thay thế lịch..."):
                        data = post_n8n({
                            "action": "confirm_action", "confirm_action": "replace_conflict",
                            "sub_action": "replace_conflict", "user_id": USER_ID, "user_email": USER_ID,
                            "request_id": ctx["request_id"], "selected_slot_code": ctx["slot_code"],
                            "delete_event_id": conflicts[pick].get("event_id"),
                        })
                    handle_single(data, ctx["title"], ctx["when"], ctx)
                    ss.pop("celebrated", None)
                    st.rerun()
                except Exception as e:
                    st.error(f"Lỗi kết nối n8n: {e}")
    st.info("Mở Google Calendar để xem, sửa hoặc xóa sự kiện.")
    if ss.get("registered"):
        st.page_link("pages/4_record_outcome.py", label="📝 Ghi nhận kết quả khi sự kiện diễn ra")
    c1, c2, _ = st.columns([1.9, 1.7, 3])
    c1.button("➕ Sắp xếp lịch khác", type="primary", on_click=reset)
    c2.link_button("Mở Google Calendar", "https://calendar.google.com")


if "results" in ss:
    show_result()
    st.stop()

# ----------------------------- Màn hình chọn giờ ----------------------------- #
st.subheader("Chọn khung giờ bạn thích")
if REAL:
    loc = BACKEND_RESPONSE.get("location_used")
    st.caption("Gợi ý từ AI Secretary dựa trên Google Calendar, thời tiết và thói quen của bạn."
               + (f" Địa điểm kiểm tra thời tiết: {loc}." if loc else ""))
    for w in BACKEND_RESPONSE.get("warnings") or []:
        st.info(w.get("message", str(w)) if isinstance(w, dict) else str(w))
else:
    st.caption(f"Đã kiểm tra Google Calendar từ {ss.cons['start']:%d/%m} đến {ss.cons['end']:%d/%m}. "
               "(Dữ liệu mẫu: chưa có gợi ý từ n8n.)")
if ss.get("regen_error"):
    st.warning(ss.pop("regen_error"))

left, right = st.columns([1, 2.3])

with left:
    with st.container(border=True):
        st.markdown("**Điều kiện**")
        st.date_input("Khoảng ngày", value=(ss.cons["start"], ss.cons["end"]), key="c_dates")
        st.multiselect("Buổi trong ngày", list(WINDOWS), default=ss.cons["tod"], key="c_tod",
                       format_func=WINDOW_VN.get)
        st.number_input("Khoảng nghỉ (phút)", 0, 120, ss.cons["buffer"], step=5, key="c_buffer")
        st.multiselect("Ngày muốn tránh", DAYS, default=ss.cons["avoid"], key="c_avoid",
                       format_func=DAY_VN.get)
        st.button("🔄 Gợi ý lại", on_click=regenerate)

items = []
events_payload = []
skipped = 0

with right:
    for i, (title, minutes, prio, avoid_rain) in enumerate(FLEX):
        slots = make_slots(i, MAX_SLOTS)
        with st.container(border=True):
            st.markdown(f"**📘 {title}** · {minutes} phút <span class='tag info'>{prio}</span>"
                        + ("<span class='tag info'>🌧 Tránh mưa</span>" if avoid_rain else ""),
                        unsafe_allow_html=True)
            if not slots:
                st.warning("Không tìm thấy khung giờ trống trong khoảng này.")
                skipped += 1
                continue
            choice = st.radio("Chọn khung giờ", list(range(len(slots))) + [-1], key=f"slot{i}_{ss.seed}",
                              format_func=lambda k, s=slots: "Bỏ qua sự kiện này" if k == -1 else fmt(s[k]),
                              label_visibility="collapsed")
            if choice >= 0:
                s = slots[choice]
                when_str = fmt(s)
                items.append((title, when_str))
                events_payload.append({
                    "title": title,
                    "date_range_start": s["day"].strftime("%Y-%m-%d"),
                    "specific_start_time": fmt_time(s["start"]),
                    "specific_end_time": fmt_time(s["end"]),
                    "duration_minutes": minutes,
                    "slot_code": s.get("slot_code"),
                })
                tags = "".join(f"<span class='tag ok'>✔ {r}</span>" for r in s["reasons"])
                tags += "".join(f"<span class='tag warn'>{w}</span>" for w in s.get("warns", []))
                st.markdown(tags, unsafe_allow_html=True)
            else:
                skipped += 1

    with st.container(border=True):
        st.markdown("**🏫 Sự kiện cố định** (kiểm tra xung đột)")
        if REAL:
            st.caption("Dữ liệu mẫu để xem giao diện — không được tạo trên Google Calendar khi đang dùng gợi ý thật.")
        monday = today - timedelta(days=today.weekday())
        for j, (title, off, s, e, conflict) in enumerate(FIXED):
            d = monday + timedelta(days=off + (7 if monday + timedelta(days=off) < today else 0))
            c1, c2 = st.columns([3, 2])
            c1.markdown(f"**{title}** · {DAY_VN[day_key(d)]} {d:%d/%m} {s}–{e}")
            if conflict:
                c2.markdown(f"<span class='tag warn'>⚠ Trùng với {conflict}</span>", unsafe_allow_html=True)
                pick = st.radio("Xử lý xung đột", ["Vẫn giữ", "Bỏ qua"], horizontal=True, key=f"fx{j}",
                                label_visibility="collapsed")
                if pick == "Bỏ qua":
                    if not REAL:
                        skipped += 1
                    continue
            else:
                c2.markdown("<span class='tag ok'>✅ Không xung đột</span>", unsafe_allow_html=True)

            if REAL:
                continue  # dữ liệu mẫu: không đưa vào danh sách tạo lịch thật
            items.append((title, f"{DAY_VN[day_key(d)]} {d:%d/%m} · {s}–{e}"))
            events_payload.append({
                "title": title,
                "date_range_start": d.strftime("%Y-%m-%d"),
                "specific_start_time": s,
                "specific_end_time": e,
                "duration_minutes": 120
            })

    with st.container(border=True):
        st.markdown("**Tóm tắt**")
        c1, c2 = st.columns(2)
        c1.selectbox("Lịch đích", CALENDARS)
        c2.selectbox("Nhắc lịch", list(REMINDERS), index=2, format_func=REMINDERS.get)
        st.markdown(f"<span class='tag ok'>{len(items)} sẽ được tạo</span>"
                    + (f"<span class='tag warn'>{skipped} bỏ qua</span>" if skipped else ""),
                    unsafe_allow_html=True)

# ----------------------------- Nút hành động ----------------------------- #
b1, b2, _, b3 = st.columns([1, 1, 2, 2.4])
if b1.button("← Quay lại"):
    st.switch_page("1_main_input.py")
b2.button("❌ Hủy", key="cancel_all")
summary = (f"Tạo **{len(items)} sự kiện** trên Google Calendar?\n\n"
           + "\n".join(f"- **{t}** · {w}" for t, w in items))
kq = confirm_action(b3.button("📅 Tạo trên Google Calendar", type="primary", disabled=not items),
                    key="create", message=summary)

if ss.get("cancel_all") or kq == "no":
    st.info("Đã hủy. Chưa có sự kiện nào được tạo trên Google Calendar.")

if kq == "yes":
    bar = st.progress(0.0, text="Đang gửi yêu cầu tạo lịch tới n8n...")

    request_id = BACKEND_RESPONSE.get("request_id") if isinstance(BACKEND_RESPONSE, dict) else None
    by_slot = REAL and isinstance(request_id, int) and len(events_payload) == 1 and events_payload[0].get("slot_code")
    payload = {
        "action": "confirm_action",
        "confirm_action": "create",
        "sub_action": "create",
        "user_id": USER_ID,
        "user_email": USER_ID,
        "selected_slots": [{"title": t, "when": w} for t, w in items],
    }
    if by_slot:
        # Tạo theo slot đã lưu của WF04: WF05 khóa slot (chống bấm trùng), kiểm tra xung đột, tạo Google Calendar
        payload.update({"request_id": request_id, "selected_slot_code": events_payload[0]["slot_code"]})
    else:
        payload.update({"events": events_payload, "request_id": request_id if isinstance(request_id, int) else 1,
                        "selected_slot_code": (events_payload[0].get("slot_code") if events_payload else None) or "S1"})

    try:
        data = post_n8n(payload)
        bar.progress(1.0, text="Hoàn tất!")
        if by_slot:
            handle_single(data, items[0][0], items[0][1],
                          {"request_id": request_id, "slot_code": events_payload[0]["slot_code"]})
        else:
            handle_batch(data, items, events_payload)
        st.rerun()
    except Exception as e:
        st.error(f"Lỗi kết nối n8n: {e}")
