"""MÀN HÌNH 3 - Gợi ý khung giờ trống, chọn lịch Google Calendar và tạo sự kiện.

Chạy:  streamlit run 3_suggest_slots.py
"""
import time
from datetime import date, datetime, timedelta
import requests
import streamlit as st
from pages.confirm_action import confirm_action
from navigation import render_stepper, stepper_css

N8N_WEBHOOK_URL = "https://k25416-thukyai.app.n8n.cloud/webhook/ai-secretary"

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

FLEX = [
    ("Học: Ôn thi cơ sở dữ liệu", 120, "Cao", False),
    ("Họp nhóm dự án", 90, "Trung bình", False),
    ("Chạy bộ ở Công viên Gia Định", 60, "Thấp", True)
]
BACKEND_RESPONSE = st.session_state.get("resp", {})
BACKEND_PROPOSALS = (
    BACKEND_RESPONSE.get("proposals", [])
    if st.session_state.get("request_kind") == "text"
    and isinstance(BACKEND_RESPONSE, dict)
    else []
)
if BACKEND_PROPOSALS:
    FLEX = [(
        BACKEND_RESPONSE.get("title", "Sự kiện"),
        int(BACKEND_RESPONSE.get("duration_minutes") or 60),
        "AI đề xuất",
        bool(BACKEND_RESPONSE.get("avoid_rain", False)),
    )]
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


def make_slots(idx, n):
    if BACKEND_PROPOSALS:
        slots = []
        for proposal in BACKEND_PROPOSALS[:n]:
            try:
                start = datetime.fromisoformat(proposal["start_time"].replace("Z", "+00:00"))
                end = datetime.fromisoformat(proposal["end_time"].replace("Z", "+00:00"))
            except (KeyError, TypeError, ValueError):
                continue
            slots.append({
                "day": start.date(),
                "start": start.hour + start.minute / 60,
                "end": end.hour + end.minute / 60,
                "reasons": [f"Điểm phù hợp: {proposal.get('score', 'N/A')}"],
                "rainy": False,
                "minutes": int((end - start).total_seconds() // 60),
                "slot_code": proposal.get("slot_code"),
            })
        return slots
    c = ss.cons
    hours = [h for t in (c["tod"] or list(WINDOWS)) for h in WINDOWS[t]]
    minutes = FLEX[idx][1]
    slots, day = [], max(c["start"], today)
    while len(slots) < n and day <= c["end"]:
        wd = day.strftime("%a")
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
                    {"day": day, "start": h, "end": end_h, "reasons": reasons, "rainy": rainy, "minutes": minutes})
                break
        day += timedelta(days=1)
    return slots


def fmt_time(x):
    return f"{int(x):02d}:{int(round((x % 1) * 60)):02d}"


def fmt(slot):
    return f"{DAY_VN[slot['day'].strftime('%a')]} {slot['day']:%d/%m} · {fmt_time(slot['start'])}–{fmt_time(slot['end'])}"


def regenerate():
    ss.cons = {"start": ss.c_dates[0] if len(ss.c_dates) == 2 else today,
               "end": ss.c_dates[1] if len(ss.c_dates) == 2 else today + timedelta(days=6),
               "tod": ss.c_tod, "avoid": ss.c_avoid, "buffer": ss.c_buffer}
    ss.seed += 1
    st.toast("Đã cập nhật gợi ý", icon="🔄")


def reset():
    for k in ("results", "reconnected", "celebrated"):
        ss.pop(k, None)


# ----------------------------- Sidebar ----------------------------- #
with st.sidebar:
    st.markdown("### 🗓️ AI Secretary")
    st.success("🟢 Đã kết nối **student@gmail.com**")
    st.divider()

st.markdown(
    '<div class="hero"><h2>🗓️ AI Secretary</h2><p>Chọn khung giờ bạn thích, tôi sẽ thêm vào Google Calendar sau khi bạn xác nhận.</p></div>',
    unsafe_allow_html=True)
render_stepper(3)


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
    st.info("Mở Google Calendar để xem, sửa hoặc xóa sự kiện.")
    c1, c2, _ = st.columns([1.9, 1.7, 3])
    c1.button("➕ Sắp xếp lịch khác", type="primary", on_click=reset)
    c2.link_button("Mở Google Calendar", "https://calendar.google.com")


if "results" in ss:
    show_result()
    st.stop()

# ----------------------------- Màn hình chọn giờ ----------------------------- #
st.subheader("Chọn khung giờ bạn thích")
st.caption(f"Đã kiểm tra Google Calendar từ {ss.cons['start']:%d/%m} đến {ss.cons['end']:%d/%m}.")

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
                st.markdown(tags, unsafe_allow_html=True)
            else:
                skipped += 1

    with st.container(border=True):
        st.markdown("**🏫 Sự kiện cố định** (kiểm tra xung đột)")
        monday = today - timedelta(days=today.weekday())
        for j, (title, off, s, e, conflict) in enumerate(FIXED):
            d = monday + timedelta(days=off + (7 if monday + timedelta(days=off) < today else 0))
            c1, c2 = st.columns([3, 2])
            c1.markdown(f"**{title}** · {DAY_VN[d.strftime('%a')]} {d:%d/%m} {s}–{e}")
            if conflict:
                c2.markdown(f"<span class='tag warn'>⚠ Trùng với {conflict}</span>", unsafe_allow_html=True)
                pick = st.radio("Xử lý xung đột", ["Vẫn giữ", "Bỏ qua"], horizontal=True, key=f"fx{j}",
                                label_visibility="collapsed")
                if pick == "Bỏ qua":
                    skipped += 1
                    continue
            else:
                c2.markdown("<span class='tag ok'>✅ Không xung đột</span>", unsafe_allow_html=True)

            items.append((title, f"{DAY_VN[d.strftime('%a')]} {d:%d/%m} · {s}–{e}"))
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
b1.button("← Quay lại")
b2.button("❌ Hủy", key="cancel_all")
summary = (f"Tạo **{len(items)} sự kiện** trên Google Calendar?\n\n"
           + "\n".join(f"- **{t}** · {w}" for t, w in items))
kq = confirm_action(b3.button("📅 Tạo trên Google Calendar", type="primary", disabled=not items),
                    key="create", message=summary)

if ss.get("cancel_all") or kq == "no":
    st.info("Đã hủy. Chưa có sự kiện nào được tạo trên Google Calendar.")

if kq == "yes":
    bar = st.progress(0.0, text="Đang gửi yêu cầu tạo lịch tới n8n...")

    payload = {
        "action": "confirm_action",
        "confirm_action": "create",
        "sub_action": "create",
        "user_id": "student@gmail.com",
        "user_email": "student@gmail.com",
        "request_id": BACKEND_RESPONSE.get("request_id", 1) if isinstance(BACKEND_RESPONSE, dict) else 1,
        "selected_slot_code": events_payload[0].get("slot_code", "S1") if events_payload else "S1",
        "events": events_payload,
        "selected_slots": [{"title": t, "when": w} for t, w in items]
    }



    try:
        res = requests.post(N8N_WEBHOOK_URL, json=payload, timeout=30)
        bar.progress(1.0, text="Hoàn tất!")

        if res.status_code == 200:
            resp_data = res.json()
            if isinstance(resp_data, list) and len(resp_data) > 0:
                resp_data = resp_data[0]
            if isinstance(resp_data, dict) and "body" in resp_data:
                resp_data = resp_data["body"]

            per_event = resp_data.get("results") if isinstance(resp_data, dict) else None
            if isinstance(per_event, list) and len(per_event) == len(items):
                ss.results = []
                for (t, w), r in zip(items, per_event):
                    ok = r.get("status") == "created"
                    ss.results.append({"title": t, "when": w, "ok": ok,
                                       "err": "" if ok else r.get("message", "Không tạo được sự kiện")})
            else:
                err_msg = resp_data.get("message", "Phản hồi không hợp lệ từ n8n") if isinstance(resp_data,
                                                                                                 dict) else str(
                    resp_data)
                ss.results = [{"title": t, "when": w, "ok": False, "err": err_msg} for t, w in items]
        else:
            ss.results = [{"title": t, "when": w, "ok": False, "err": res.text} for t, w in items]

        st.rerun()
    except Exception as e:
        st.error(f"Lỗi kết nối n8n: {e}")