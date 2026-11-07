"""MÀN HÌNH 2 - Kiểm tra / chỉnh sửa thông tin AI đã hiểu trước khi thêm vào lịch.

Chạy:  streamlit run 2_review_edit.py
Sidebar chọn kiểu hiển thị:
  - Ảnh thời khóa biểu  (import_schedule_image): bảng sửa được
  - Tạo sự kiện         (create_event): thẻ `event` sửa được
  - Sửa sự kiện         (update_event): `target_event` (cũ) và `event` (mới)
  - Xóa sự kiện         (delete_event): `target_event` cần xóa
Khi requires_confirmation = true: có nút Xác nhận và Hủy (cửa sổ confirm_action).
"""
from datetime import datetime, time as dtime

import pandas as pd
import streamlit as st
import requests
from navigation import render_stepper, stepper_css

N8N_WEBHOOK_URL = "https://k25416-thukyai.app.n8n.cloud/webhook/ai-secretary"

from pages.confirm_action import confirm_action

st.set_page_config(page_title="AI Secretary · Kiểm tra", page_icon="🗓️", layout="wide")

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
.tag.info{background:#E0E7FF;color:#3730A3}.tag.bad{background:#FEE2E2;color:#991B1B}
.stButton>button{border-radius:10px;font-weight:600}
.stButton>button[kind="primary"]{background:linear-gradient(135deg,#4F46E5,#6366F1);border:none;
 box-shadow:0 4px 12px rgba(79,70,229,.3)}
.fake{background:#fff;border:1px dashed #94A3B8;border-radius:12px;padding:.8rem;font-size:.8rem;color:#334155}
.fake table{width:100%;border-collapse:collapse}.fake td,.fake th{border:1px solid #CBD5E1;padding:.25rem .35rem}
.fake th{background:#F1F5F9}
</style>"""
st.markdown(CSS, unsafe_allow_html=True)
st.markdown(stepper_css(), unsafe_allow_html=True)


DAYS = ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"]
PERIODS = {"morning": "Buổi sáng", "afternoon": "Buổi chiều", "evening": "Buổi tối", "any": "Bất kỳ"}

# Dữ liệu mẫu mà "AI" đọc được từ ảnh thời khóa biểu
TIMETABLE = pd.DataFrame([
    (True, "", "Toán cao cấp", "Thứ 2", dtime(7, 30), dtime(9, 30), "Phòng A2-101", "hằng tuần", 0.97),
    (True, "⚠", "Vật lý?", "Thứ 3", dtime(9, 0), dtime(11, 0), "Phòng B1-204", "hằng tuần", 0.58),
    (True, "", "Cơ sở dữ liệu", "Thứ 4", dtime(13, 0), dtime(15, 0), "Lab C3", "hằng tuần", 0.95),
    (True, "", "Tiếng Anh", "Thứ 5", dtime(8, 0), dtime(9, 30), "Phòng A1-305", "hằng tuần", 0.91),
    (True, "⚠", "Lập trình", "Thứ 6", dtime(10, 0), dtime(12, 0), "Lab C1", "hằng tuần", 0.52),
    (True, "", "Xác suất thống kê", "Thứ 4", dtime(9, 30), dtime(11, 0), "Phòng A2-110", "không", 0.88),
], columns=["Chọn", "Kiểm tra", "Tên sự kiện", "Thứ", "Bắt đầu", "Kết thúc", "Địa điểm", "Lặp lại", "Độ tin cậy"])

IMAGE_RESPONSE = st.session_state.get("resp", {})
IMAGE_ITEMS = (
    IMAGE_RESPONSE.get("items", [])
    if st.session_state.get("request_kind") == "image"
    and isinstance(IMAGE_RESPONSE, dict)
    else []
)
if IMAGE_ITEMS:
    period_table = IMAGE_RESPONSE.get("period_table", {})
    rows = []
    for item in IMAGE_ITEMS:
        start = period_table.get(str(item.get("start_period")), period_table.get(item.get("start_period"), ["", ""]))[0]
        end = period_table.get(str(item.get("end_period")), period_table.get(item.get("end_period"), ["", ""]))[1]
        start_time = dtime(*map(int, start.split(":"))) if start else None
        end_time = dtime(*map(int, end.split(":"))) if end else None
        rows.append({
            "Chọn": True,
            "Kiểm tra": "",
            "Tên sự kiện": item.get("ten_mon", ""),
            "Thứ": item.get("thu", ""),
            "Bắt đầu": start_time,
            "Kết thúc": end_time,
            "Địa điểm": item.get("phong_hoc") or "",
            "Lặp lại": "hằng tuần",
            "Độ tin cậy": 1.0,
            "Tiết bắt đầu": item.get("start_period"),
            "Tiết kết thúc": item.get("end_period"),
            "Ngày áp dụng": item.get("applied_date", ""),
            "Lặp đến": item.get("recurrence_until", ""),
        })
    TIMETABLE = pd.DataFrame(rows)

# Mẫu cho create_event (cấu trúc event theo đặc tả)
EVENT_CREATE = {
    "title": "Họp dự án", "description": "", "date_range_start": "2026-10-22", "date_range_end": "2026-10-22",
    "specific_start_time": "09:00", "specific_end_time": "", "duration_minutes": 60,
    "preferred_period": "morning", "location": "", "is_outdoor": False, "avoid_rain": False,
}
# Mẫu cho update_event / delete_event
TARGETS = [  # target_event (event_id lấy từ Google Calendar, không hiển thị cho người dùng)
    {"event_id": "evt_001", "title": "Họp dự án", "date": "2026-10-22", "start_time": "09:00"},
    {"event_id": "evt_002", "title": "Họp dự án", "date": "2026-10-22", "start_time": "15:00"},
]
EVENT_UPDATE = {**EVENT_CREATE, "specific_start_time": "10:00", "specific_end_time": "11:00", "duration_minutes": None}

# ----------------------------- Sidebar ----------------------------- #
with st.sidebar:
    st.markdown("### 🗓️ AI Secretary")
    st.success("🟢 Đã kết nối **student@gmail.com**")
    st.divider()
    st.caption("🧪 Điều khiển demo")
    variant = st.radio("Xem trước", ["Ảnh thời khóa biểu", "Tạo sự kiện", "Sửa sự kiện", "Xóa sự kiện"])
    sample_img = st.file_uploader("Ảnh thời khóa biểu của bạn (tùy chọn)", type=["png", "jpg", "jpeg"])

st.markdown('<div class="hero"><h2>🗓️ AI Secretary</h2><p>Kiểm tra những gì tôi đã hiểu trước khi tiếp tục.</p></div>',
            unsafe_allow_html=True)
render_stepper(2)
st.subheader("Kiểm tra thông tin đã hiểu")


def parse_hm(s):
    try:
        h, m = s.split(":")
        return dtime(int(h), int(m))
    except Exception:
        return None


def fmt_date(iso):
    y, m, d = iso.split("-")
    return f"{d}/{m}/{y}"


# ----------------------------- Kiểm tra dữ liệu ----------------------------- #
def validate_table(df):
    errors = []
    for i, r in df.iterrows():
        if not bool(r["Chọn"]):
            continue
        title = r["Tên sự kiện"] if isinstance(r["Tên sự kiện"], str) else ""
        if (not title.strip() and not isinstance(r["Thứ"], str)
                and pd.isna(r["Bắt đầu"]) and pd.isna(r["Kết thúc"])):
            continue  # dòng trống, bỏ qua
        label = f"“{title}”" if title.strip() else f"Dòng {i + 1}"
        if not title.strip():
            errors.append(f"Dòng {i + 1}: thiếu tên sự kiện.")
        if not isinstance(r["Thứ"], str):
            errors.append(f"{label}: cần chọn thứ.")
        if pd.isna(r["Bắt đầu"]) or pd.isna(r["Kết thúc"]):
            errors.append(f"{label}: cần nhập giờ bắt đầu và giờ kết thúc.")
        elif r["Kết thúc"] <= r["Bắt đầu"]:
            errors.append(f"{label}: giờ kết thúc phải sau giờ bắt đầu.")
    return errors


def event_form(ev, prefix):
    """Biểu mẫu sửa các trường của `event`. Trả về (title, lỗi)."""
    errs = []
    title = st.text_input("Tên sự kiện (title)", ev["title"], key=f"{prefix}_title")
    st.text_input("Ghi chú (description)", ev["description"], key=f"{prefix}_desc")
    c = st.columns(2)
    d1 = c[0].text_input("Từ ngày (date_range_start)", fmt_date(ev["date_range_start"]), key=f"{prefix}_d1")
    d2 = c[1].text_input("Đến ngày (date_range_end)", fmt_date(ev["date_range_end"]), key=f"{prefix}_d2")
    c = st.columns(3)
    s = c[0].text_input("Giờ bắt đầu (HH:MM)", ev["specific_start_time"], key=f"{prefix}_st")
    e = c[1].text_input("Giờ kết thúc (HH:MM)", ev["specific_end_time"], key=f"{prefix}_et")
    dur = c[2].number_input("Thời lượng (phút)", 0, 720, ev["duration_minutes"] or 0, step=15, key=f"{prefix}_dur")
    c = st.columns(2)
    c[0].selectbox("Buổi ưu tiên (preferred_period)", list(PERIODS), format_func=PERIODS.get,
                   index=list(PERIODS).index(ev["preferred_period"]), key=f"{prefix}_pp")
    c[1].text_input("Địa điểm (location)", ev["location"], key=f"{prefix}_loc")
    c = st.columns(2)
    c[0].checkbox("Hoạt động ngoài trời (is_outdoor)", ev["is_outdoor"], key=f"{prefix}_out")
    c[1].checkbox("Tránh lúc mưa (avoid_rain)", ev["avoid_rain"], key=f"{prefix}_rain")

    if not title.strip():
        errs.append("Thiếu tên sự kiện.")
    if not d1.strip():
        errs.append("Thiếu ngày.")
    if not parse_hm(s):
        errs.append("Thiếu hoặc sai giờ bắt đầu (định dạng HH:MM).")
    if not (parse_hm(e) or dur):
        errs.append("Cần nhập giờ kết thúc hoặc thời lượng.")
    elif parse_hm(e) and parse_hm(s) and parse_hm(e) <= parse_hm(s):
        errs.append("Giờ kết thúc phải sau giờ bắt đầu.")
    return title, errs


def reanalyze_box():
    with st.expander("🔄 Có gì chưa đúng? Phân tích lại kèm gợi ý"):
        st.text_input("Gợi ý cho AI", placeholder="Ví dụ: Tuần bắt đầu từ thứ Hai; giờ theo định dạng 24 giờ.")
        if st.button("Phân tích lại"):
            st.toast("Đã phân tích lại", icon="🔄")


errors, summary = [], ""

# ----------------------------- Ảnh thời khóa biểu ----------------------------- #
if variant == "Ảnh thời khóa biểu":
    low = int((TIMETABLE["Độ tin cậy"] < 0.7).sum())
    st.warning(f"Tôi đọc được **{len(TIMETABLE)} sự kiện** · **{low}** sự kiện cần kiểm tra (đánh dấu ⚠). "
               "Kết quả đọc ảnh cần bạn kiểm tra và xác nhận trước khi tạo lịch.")
    left, right = st.columns([1, 1.8])
    with left:
        st.markdown("**Ảnh gốc**")
        if sample_img is not None:
            st.image(sample_img, caption=sample_img.name)
        else:
            st.markdown(
                '<div class="fake"><b>Ảnh thời khóa biểu mẫu</b><br><small>(ảnh bạn tải lên sẽ hiện ở đây)</small>'
                "<table><tr><th></th><th>T2</th><th>T3</th><th>T4</th><th>T5</th><th>T6</th></tr>"
                "<tr><td>7:30</td><td>Toán</td><td></td><td></td><td></td><td></td></tr>"
                "<tr><td>9:00</td><td></td><td>Vật…</td><td>XSTK</td><td>Anh</td><td></td></tr>"
                "<tr><td>10:00</td><td></td><td></td><td></td><td></td><td>Lập tr…</td></tr>"
                "<tr><td>13:00</td><td></td><td></td><td>CSDL</td><td></td><td></td></tr></table></div>",
                unsafe_allow_html=True)
    with right:
        st.markdown("**Sự kiện AI nhận diện** — sửa trực tiếp ô, thêm dòng (＋ ở cuối) hoặc xóa dòng")
        st.caption("Mẹo: dòng trống sẽ bị bỏ qua. Để xóa dòng, tick ô ở đầu dòng rồi nhấn Delete.")
        edited = st.data_editor(
            TIMETABLE, key="tt_editor", num_rows="dynamic", hide_index=True,
            column_config={
                "Chọn": st.column_config.CheckboxColumn(default=True, width="small"),
                "Kiểm tra": st.column_config.TextColumn("⚠", disabled=True, width="small"),
                "Thứ": st.column_config.SelectboxColumn(options=DAYS),
                "Bắt đầu": st.column_config.TimeColumn(format="HH:mm", step=300),
                "Kết thúc": st.column_config.TimeColumn(format="HH:mm", step=300),
                "Lặp lại": st.column_config.SelectboxColumn(options=["không", "hằng tuần"], default="không"),
                "Độ tin cậy": st.column_config.ProgressColumn(min_value=0.0, max_value=1.0, format="%.2f"),
            })
        errors = validate_table(edited)
        n = int(edited["Chọn"].sum())
        summary = f"Thêm **{n} sự kiện** từ ảnh thời khóa biểu vào Google Calendar?"

# ----------------------------- Tạo sự kiện ----------------------------- #
elif variant == "Tạo sự kiện":
    st.success("Đã xác định yêu cầu tạo sự kiện.")
    with st.expander("💬 Tôi đã hiểu yêu cầu của bạn như sau"):
        st.write("“Đặt lịch họp dự án lúc 9 giờ sáng ngày 22/10/2026 trong một giờ.”")
        st.caption("Ý định: Tạo sự kiện · Múi giờ Asia/Ho_Chi_Minh")
    with st.container(border=True):
        title, errors = event_form(EVENT_CREATE, "cr")
    summary = f"Tạo sự kiện **{title or '(chưa có tên)'}** trên Google Calendar?"

# ----------------------------- Sửa sự kiện ----------------------------- #
elif variant == "Sửa sự kiện":
    st.success("Đã xác định yêu cầu sửa sự kiện: “Dời lịch họp dự án từ 9 giờ sang 10 giờ.”")
    st.markdown("**1. Sự kiện cần sửa** (`target_event`)")
    st.caption("Có 2 sự kiện phù hợp, vui lòng chọn đúng sự kiện.")
    idx = st.radio("Chọn sự kiện", range(len(TARGETS)), label_visibility="collapsed",
                   format_func=lambda i: f"{TARGETS[i]['title']} · {fmt_date(TARGETS[i]['date'])} · {TARGETS[i]['start_time']}")
    tgt = TARGETS[idx]
    st.markdown("**2. Thông tin mới** (`event`)")
    with st.container(border=True):
        title, errors = event_form(EVENT_UPDATE, "up")
    st.markdown("**So sánh thay đổi**")
    cmp_l, cmp_r = st.columns(2)
    cmp_l.markdown(f'<span class="tag bad">Cũ</span> {tgt["title"]} · {fmt_date(tgt["date"])} · {tgt["start_time"]}',
                   unsafe_allow_html=True)
    cmp_r.markdown(f'<span class="tag ok">Mới</span> {title} · {fmt_date(EVENT_UPDATE["date_range_start"])} · '
                   f'{st.session_state.get("up_st", "")}', unsafe_allow_html=True)
    st.caption("Hệ thống sẽ kiểm tra xung đột lịch trước khi sửa ngày hoặc giờ.")
    summary = (f"Sửa sự kiện **{tgt['title']}** ({fmt_date(tgt['date'])} {tgt['start_time']}) "
               f"thành giờ bắt đầu **{st.session_state.get('up_st', '')}**?")

# ----------------------------- Xóa sự kiện ----------------------------- #
else:
    st.success("Đã xác định lịch cần xóa: “Xóa lịch chạy bộ lúc 17 giờ ngày 21/10/2026.”")
    st.markdown("**Sự kiện sẽ bị xóa** (`target_event`)")
    with st.container(border=True):
        st.markdown("🏃 **Chạy bộ**")
        c = st.columns(2)
        c[0].markdown("Ngày: **21/10/2026**")
        c[1].markdown("Giờ bắt đầu: **17:00**")
    st.warning("Sau khi xóa, sự kiện sẽ biến mất khỏi Google Calendar. Bạn cần xác nhận để tiếp tục.")
    summary = "Xóa sự kiện **Chạy bộ** (21/10/2026 17:00) khỏi Google Calendar?"

if errors:
    st.error("**Vui lòng sửa trước khi tiếp tục:**\n\n" + "\n".join(f"- {m}" for m in errors))

if variant in ("Ảnh thời khóa biểu", "Tạo sự kiện"):
    reanalyze_box()

# ----------------------------- Nút hành động ----------------------------- #
# requires_confirmation = true -> có nút Xác nhận và Hủy
st.divider()
b1, b2, _, b3 = st.columns([1, 1, 2.2, 1.9])
b1.button("← Quay lại")
b2.button("❌ Hủy yêu cầu", key="cancel_req")
label = "🗑 Xác nhận xóa" if variant == "Xóa sự kiện" else "✅ Xác nhận"
kq = confirm_action(b3.button(label, type="primary", disabled=bool(errors)), key="screen2", message=summary)
if kq == "yes":
    with st.spinner("Đang gửi phản hồi sang n8n..."):
        sub_act = (
            "delete"
            if variant == "Xóa sự kiện"
            else ("update" if variant == "Sửa sự kiện" else "create")
        )
        payload = {
            "action": "confirm_import" if variant == "Ảnh thời khóa biểu" else "confirm_action",
            "sub_action": sub_act,
            "confirm_action": sub_act,
            "user_id": "student@gmail.com",
            "user_email": "student@gmail.com",
            "request_id": IMAGE_RESPONSE.get("request_id") if variant == "Ảnh thời khóa biểu" else None,
            "selected_items": [
                {
                    "ten_mon": row["Tên sự kiện"],
                    "thu": row["Thứ"],
                    "start_period": int(row["Tiết bắt đầu"]),
                    "end_period": int(row["Tiết kết thúc"]),
                    "applied_date": row["Ngày áp dụng"],
                    "recurrence_until": row["Lặp đến"],
                    "phong_hoc": row["Địa điểm"] or None,
                }
                for _, row in edited[edited["Chọn"]].iterrows()
            ] if variant == "Ảnh thời khóa biểu" and IMAGE_ITEMS else None,
            "event_data": EVENT_CREATE if variant != "Ảnh thời khóa biểu" else None,
        }
        try:
            res = requests.post(N8N_WEBHOOK_URL, json=payload, timeout=30)
            if res.status_code == 200:
                st.success("Đã xác nhận với Workflow thành công!")
                if variant in ("Tạo sự kiện", "Ảnh thời khóa biểu"):
                    st.switch_page("pages/3_suggest_slots.py")
            else:
                st.error(f"Lỗi n8n ({res.status_code}): {res.text}")
        except Exception as e:
            st.error(f"Lỗi kết nối n8n: {e}")
elif kq == "no":
    st.info("Bạn đã hủy. Chưa có thay đổi nào được thực hiện trên lịch.")
if st.session_state.get("cancel_req"):
    st.info("Đã hủy yêu cầu. Chưa có thay đổi nào được thực hiện trên lịch.")
