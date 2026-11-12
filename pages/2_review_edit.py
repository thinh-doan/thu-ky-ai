"""MÀN HÌNH 2 - Kiểm tra / chỉnh sửa thông tin AI đã hiểu trước khi thêm vào lịch.

Chạy:  streamlit run 2_review_edit.py
Sidebar chọn kiểu hiển thị:
  - Ảnh thời khóa biểu  (import_schedule_image): bảng sửa được
  - Tạo sự kiện         (create_event): thẻ `event` sửa được
  - Sửa sự kiện         (update_event): `target_event` (cũ) và `event` (mới)
  - Xóa sự kiện         (delete_event): `target_event` cần xóa
Khi requires_confirmation = true: có nút Xác nhận và Hủy (cửa sổ confirm_action).

Khớp workflow:
  - Ảnh TKB  -> WF07 confirm_import: gửi selected_items (tiết suy ra từ giờ theo bảng tiết trong phản hồi parse_image,
                applied_date / recurrence_until), nhận import_done.
  - Tạo      -> WF05 (batch event_data): gửi đúng giá trị người dùng đã sửa trong biểu mẫu.
  - Sửa/Xóa  -> WF06 qua WF00: gửi target_title + target_date (+ target_event_id khi người dùng chọn trong danh sách
                trùng) và updates{title, location, start_time, end_time}; xử lý target_ambiguous / target_not_found.
  - Thành công -> lưu kết quả vào session để màn 3 hiện màn hình "Hoàn tất"; sự kiện tạo mới được ghi vào
                outcome_store để ghi nhận kết quả sau (WF10).
"""
from datetime import date, datetime, time as dtime, timedelta

import pandas as pd
import streamlit as st
import requests
from navigation import render_stepper, stepper_css
from outcome_store import add_events, unwrap

N8N_WEBHOOK_URL = "https://aithuky.app.n8n.cloud/webhook/ai-secretary"
USER_ID = "student@gmail.com"
N8N_TIMEOUT = 120

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

_resp = st.session_state.get("resp", {})
IMAGE_RESPONSE = _resp if isinstance(_resp, dict) else {}
IMAGE_ITEMS = (
    IMAGE_RESPONSE.get("items", [])
    if st.session_state.get("request_kind") == "image"
    else []
)
# WF07 trả thứ dạng "Thứ Hai"; bảng trên giao diện dùng "Thứ 2"
THU_VN = {"Thứ Hai": "Thứ 2", "Thứ Ba": "Thứ 3", "Thứ Tư": "Thứ 4", "Thứ Năm": "Thứ 5",
          "Thứ Sáu": "Thứ 6", "Thứ Bảy": "Thứ 7", "Chủ Nhật": "Chủ nhật"}
P_START, P_END = {}, {}  # "07:30" -> số tiết (để đổi giờ người dùng sửa ngược về tiết cho WF07)
if IMAGE_ITEMS:
    period_table = IMAGE_RESPONSE.get("period_table", {})
    for _k, _v in period_table.items():
        try:
            P_START[str(_v[0])[:5]] = int(_k)
            P_END[str(_v[1])[:5]] = int(_k)
        except (TypeError, ValueError, IndexError):
            pass
    rows = []
    for item in IMAGE_ITEMS:
        start = period_table.get(str(item.get("start_period")), period_table.get(item.get("start_period"), ["", ""]))[0]
        end = period_table.get(str(item.get("end_period")), period_table.get(item.get("end_period"), ["", ""]))[1]
        start_time = dtime(*map(int, start.split(":")[:2])) if start else None
        end_time = dtime(*map(int, end.split(":")[:2])) if end else None
        rows.append({
            "Chọn": True,
            "Kiểm tra": "",
            "Tên sự kiện": item.get("ten_mon", ""),
            "Thứ": THU_VN.get(item.get("thu", ""), item.get("thu", "")),
            "Bắt đầu": start_time,
            "Kết thúc": end_time,
            "Địa điểm": item.get("phong_hoc") or "",
            "Lặp lại": "hằng tuần",
            "Độ tin cậy": 1.0,
            "Tiết bắt đầu": item.get("start_period"),
            "Tiết kết thúc": item.get("end_period"),
            "Ngày áp dụng": item.get("applied_date", ""),
            "Lặp đến": item.get("recurrence_until", ""),
            "Giảng viên": item.get("giang_vien") or "",
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


def parse_dmy(s):
    """'dd/mm/yyyy' -> 'YYYY-MM-DD' (None nếu sai định dạng)."""
    try:
        d, m, y = str(s).strip().split("/")
        return date(int(y), int(m), int(d)).isoformat()
    except Exception:
        return None


def parse_ymd(v):
    """'YYYY-MM-DD' -> date (None nếu rỗng/sai)."""
    try:
        return date.fromisoformat(str(v).strip())
    except Exception:
        return None


def _nz(v):
    """NaN/None của pandas -> None."""
    try:
        return None if pd.isna(v) else v
    except (TypeError, ValueError):
        return v


WD_IDX = {"Thứ 2": 0, "Thứ 3": 1, "Thứ 4": 2, "Thứ 5": 3, "Thứ 6": 4, "Thứ 7": 5, "Chủ nhật": 6}


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


def build_import_items(df):
    """Đổi bảng người dùng đã sửa -> selected_items cho WF07 confirm_import. Trả về (items, lỗi).
    Tiết suy ra từ giờ theo bảng tiết trong phản hồi parse_image; ngày áp dụng luôn được căn đúng thứ."""
    items, errs = [], []
    today_d = date.today()
    for i, r in df.iterrows():
        if not bool(_nz(r.get("Chọn"))):
            continue
        title = r["Tên sự kiện"] if isinstance(_nz(r["Tên sự kiện"]), str) else ""
        thu, t0, t1 = _nz(r["Thứ"]), _nz(r["Bắt đầu"]), _nz(r["Kết thúc"])
        if not title.strip() and not isinstance(thu, str) and t0 is None and t1 is None:
            continue  # dòng trống
        if not title.strip() or not isinstance(thu, str) or t0 is None or t1 is None:
            continue  # đã được validate_table báo lỗi
        label = f"“{title}”"
        sp, ep = P_START.get(f"{t0:%H:%M}"), P_END.get(f"{t1:%H:%M}")
        if sp is None or ep is None or ep < sp:
            errs.append(f"{label}: giờ bắt đầu/kết thúc phải trùng giờ bắt đầu/kết thúc của một tiết học.")
            continue
        raw_app, raw_until = _nz(r.get("Ngày áp dụng")), _nz(r.get("Lặp đến"))
        applied = parse_ymd(raw_app)
        if raw_app not in (None, "") and applied is None:
            errs.append(f"{label}: ngày áp dụng phải dạng YYYY-MM-DD.")
            continue
        base = applied or today_d
        applied = base + timedelta(days=(WD_IDX[thu] - base.weekday()) % 7)  # căn đúng thứ đã chọn
        until = parse_ymd(raw_until)
        if raw_until not in (None, "") and until is None:
            errs.append(f"{label}: ngày lặp đến phải dạng YYYY-MM-DD.")
            continue
        if until is None or until < applied:
            until = applied + timedelta(weeks=15)
        if _nz(r.get("Lặp lại")) == "không":
            until = applied
        items.append({
            "ten_mon": title.strip(), "thu": thu, "start_period": sp, "end_period": ep,
            "applied_date": applied.isoformat(), "recurrence_until": until.isoformat(),
            "phong_hoc": (_nz(r.get("Địa điểm")) or None), "giang_vien": (_nz(r.get("Giảng viên")) or None),
        })
    return items, errs


def event_form(ev, prefix):
    """Biểu mẫu sửa các trường của `event`. Trả về (title, lỗi, giá trị người dùng đã nhập)."""
    errs = []
    title = st.text_input("Tên sự kiện (title)", ev["title"], key=f"{prefix}_title")
    desc = st.text_input("Ghi chú (description)", ev["description"], key=f"{prefix}_desc")
    c = st.columns(2)
    d1 = c[0].text_input("Từ ngày (date_range_start)", fmt_date(ev["date_range_start"]), key=f"{prefix}_d1")
    d2 = c[1].text_input("Đến ngày (date_range_end)", fmt_date(ev["date_range_end"]), key=f"{prefix}_d2")
    c = st.columns(3)
    s = c[0].text_input("Giờ bắt đầu (HH:MM)", ev["specific_start_time"], key=f"{prefix}_st")
    e = c[1].text_input("Giờ kết thúc (HH:MM)", ev["specific_end_time"], key=f"{prefix}_et")
    dur = c[2].number_input("Thời lượng (phút)", 0, 720, ev["duration_minutes"] or 0, step=15, key=f"{prefix}_dur")
    c = st.columns(2)
    pp = c[0].selectbox("Buổi ưu tiên (preferred_period)", list(PERIODS), format_func=PERIODS.get,
                        index=list(PERIODS).index(ev["preferred_period"]), key=f"{prefix}_pp")
    loc = c[1].text_input("Địa điểm (location)", ev["location"], key=f"{prefix}_loc")
    c = st.columns(2)
    out = c[0].checkbox("Hoạt động ngoài trời (is_outdoor)", ev["is_outdoor"], key=f"{prefix}_out")
    rain = c[1].checkbox("Tránh lúc mưa (avoid_rain)", ev["avoid_rain"], key=f"{prefix}_rain")

    if not title.strip():
        errs.append("Thiếu tên sự kiện.")
    if not d1.strip():
        errs.append("Thiếu ngày.")
    elif not parse_dmy(d1):
        errs.append("Ngày không hợp lệ (định dạng dd/mm/yyyy).")
    if d2.strip() and not parse_dmy(d2):
        errs.append("Ngày kết thúc không hợp lệ (định dạng dd/mm/yyyy).")
    if not parse_hm(s):
        errs.append("Thiếu hoặc sai giờ bắt đầu (định dạng HH:MM).")
    if not (parse_hm(e) or dur):
        errs.append("Cần nhập giờ kết thúc hoặc thời lượng.")
    elif parse_hm(e) and parse_hm(s) and parse_hm(e) <= parse_hm(s):
        errs.append("Giờ kết thúc phải sau giờ bắt đầu.")
    iso1 = parse_dmy(d1)
    vals = {
        "title": title.strip(), "description": desc, "date_range_start": iso1,
        "date_range_end": parse_dmy(d2) or iso1, "specific_start_time": s.strip(),
        "specific_end_time": e.strip(), "duration_minutes": int(dur) or None,
        "preferred_period": pp, "location": loc, "is_outdoor": out, "avoid_rain": rain,
    }
    return title, errs, vals


def reanalyze_box():
    with st.expander("🔄 Có gì chưa đúng? Phân tích lại kèm gợi ý"):
        st.text_input("Gợi ý cho AI", placeholder="Ví dụ: Tuần bắt đầu từ thứ Hai; giờ theo định dạng 24 giờ.")
        if st.button("Phân tích lại"):
            st.toast("Đã phân tích lại", icon="🔄")


errors, summary = [], ""
edited, ev_vals, tgt, import_items = None, None, None, []

# ----------------------------- Ảnh thời khóa biểu ----------------------------- #
if variant == "Ảnh thời khóa biểu":
    low = int((TIMETABLE["Độ tin cậy"] < 0.7).sum())
    st.warning(f"Tôi đọc được **{len(TIMETABLE)} sự kiện** · **{low}** sự kiện cần kiểm tra (đánh dấu ⚠). "
               "Kết quả đọc ảnh cần bạn kiểm tra và xác nhận trước khi tạo lịch.")
    for w in (IMAGE_RESPONSE.get("warnings") or []) if IMAGE_ITEMS else []:
        st.info(w.get("message", str(w)) if isinstance(w, dict) else str(w))
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
                "Tiết bắt đầu": None, "Tiết kết thúc": None, "Giảng viên": None,  # cột phụ cho WF07, không hiển thị
                "Thứ": st.column_config.SelectboxColumn(options=DAYS),
                "Bắt đầu": st.column_config.TimeColumn(format="HH:mm", step=300),
                "Kết thúc": st.column_config.TimeColumn(format="HH:mm", step=300),
                "Lặp lại": st.column_config.SelectboxColumn(options=["không", "hằng tuần"], default="không"),
                "Độ tin cậy": st.column_config.ProgressColumn(min_value=0.0, max_value=1.0, format="%.2f"),
            })
        errors = validate_table(edited)
        if IMAGE_ITEMS and not errors:
            import_items, import_errs = build_import_items(edited)
            errors += import_errs
        n = int(edited["Chọn"].sum())
        summary = f"Thêm **{n} sự kiện** từ ảnh thời khóa biểu vào Google Calendar?"

# ----------------------------- Tạo sự kiện ----------------------------- #
elif variant == "Tạo sự kiện":
    st.success("Đã xác định yêu cầu tạo sự kiện.")
    with st.expander("💬 Tôi đã hiểu yêu cầu của bạn như sau"):
        st.write("“Đặt lịch họp dự án lúc 9 giờ sáng ngày 22/10/2026 trong một giờ.”")
        st.caption("Ý định: Tạo sự kiện · Múi giờ Asia/Ho_Chi_Minh")
    with st.container(border=True):
        title, errors, ev_vals = event_form(EVENT_CREATE, "cr")
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
        title, errors, ev_vals = event_form(EVENT_UPDATE, "up")
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

# ----------------------------- Gửi sang n8n ----------------------------- #
def post_n8n(payload):
    res = requests.post(N8N_WEBHOOK_URL, json=payload, timeout=N8N_TIMEOUT)
    if res.status_code != 200:
        raise RuntimeError(f"Lỗi n8n ({res.status_code}): {res.text}")
    data = unwrap(res.json())
    return data if isinstance(data, dict) else {"status": "error", "message": str(data)}


def show_warnings(data):
    for w in data.get("warnings") or []:
        st.caption("⚠ " + (w.get("message", str(w)) if isinstance(w, dict) else str(w)))


def fmt_fail(f):
    if isinstance(f, dict):
        return f"{f.get('ten_mon') or f.get('title') or 'Mục lỗi'}: {f.get('message') or f.get('error') or ''}".strip()
    return str(f)


def do_import():
    if not IMAGE_ITEMS:
        st.info("Đây là dữ liệu mẫu nên chưa gửi sang n8n. Hãy tải ảnh thời khóa biểu ở Màn hình 1 để nhập thật.")
        return
    data = post_n8n({
        "action": "confirm_import", "user_id": USER_ID, "user_email": USER_ID,
        "request_id": IMAGE_RESPONSE.get("request_id"), "selected_items": import_items,
    })
    if data.get("status") == "import_done":
        # import_done nghĩa là toàn bộ mục đã tạo (WF07: failed = [] mới trả import_done)
        st.session_state.results = [
            {"title": it["ten_mon"], "when": f"{it['thu']} · hằng tuần từ {fmt_date(it['applied_date'])}",
             "ok": True, "err": ""}
            for it in import_items
        ]
        st.switch_page("pages/3_suggest_slots.py")  # màn "Hoàn tất"
    else:
        st.error(f"[{data.get('error_code', 'ERROR')}] {data.get('message', 'Không nhập được thời khóa biểu.')}")
        for f in data.get("failed") or []:
            st.caption("• " + fmt_fail(f))
        show_warnings(data)


def do_create():
    vals = ev_vals
    data = post_n8n({
        "action": "confirm_action", "sub_action": "create", "confirm_action": "create",
        "user_id": USER_ID, "user_email": USER_ID, "request_id": None, "event_data": vals,
    })
    results = data.get("results") or []
    if data.get("status") in ("created", "partial") and results:
        when = f"{fmt_date(vals['date_range_start'])} · {vals['specific_start_time']}"
        st.session_state.results = [
            {"title": r.get("title") or vals["title"], "when": when, "ok": r.get("status") == "created",
             "err": "" if r.get("status") == "created" else r.get("message", "Không tạo được sự kiện")}
            for r in results
        ]
        try:  # phương án C: lưu để ghi nhận kết quả sau (chỉ sự kiện đã lưu được vào CSDL)
            n_saved = add_events(USER_ID, [
                {"google_event_id": r.get("google_event_id"), "title": r.get("title") or vals["title"],
                 "start_time": r.get("start_time"), "end_time": r.get("end_time")}
                for r in results if r.get("status") == "created" and r.get("saved_to_db") is not False
            ])
            st.session_state.registered = st.session_state.get("registered", 0) + n_saved
        except OSError as e:
            st.warning(f"Không lưu được danh sách ghi nhận kết quả: {e}")
        st.switch_page("pages/3_suggest_slots.py")  # màn "Hoàn tất"
    else:
        st.error(f"[{data.get('error_code', 'ERROR')}] {data.get('message', 'Không tạo được sự kiện.')}")
        show_warnings(data)


def run_manage(payload):
    """Gửi update/delete sang WF06 (qua WF00) và hiển thị kết quả theo status."""
    data = post_n8n(payload)
    status = data.get("status")
    if status in ("updated", "deleted"):
        ev = data.get("event") or {}
        name = ev.get("title") or data.get("title") or payload.get("target_title") or "sự kiện"
        st.success(f"Đã {'sửa' if status == 'updated' else 'xóa'} sự kiện “{name}” trên Google Calendar.")
        show_warnings(data)
    elif status == "target_ambiguous":
        st.session_state.p2_ambig = {"payload": payload, "candidates": data.get("candidates") or []}
        st.warning(data.get("message", "Có nhiều sự kiện phù hợp; vui lòng chọn đúng sự kiện."))
    elif status == "target_not_found":
        st.warning(data.get("message", "Không tìm thấy sự kiện cần thao tác."))
    else:
        st.error(f"[{data.get('error_code', 'ERROR')}] {data.get('message', 'Không thực hiện được.')}")


def do_manage(sub_act):
    payload = {
        "action": "confirm_action", "sub_action": sub_act, "confirm_action": sub_act,
        "user_id": USER_ID, "user_email": USER_ID,
        "target_event_id": None, "target_title": tgt["title"], "target_date": tgt["date"],
    }
    if sub_act == "update":
        v = ev_vals
        start_iso = end_iso = None
        sm, em = parse_hm(v["specific_start_time"]), parse_hm(v["specific_end_time"])
        if v["date_range_start"] and sm:
            start_iso = f"{v['date_range_start']}T{sm:%H:%M}:00+07:00"
            end_dt = (datetime.combine(date.fromisoformat(v["date_range_start"]), em) if em else
                      datetime.combine(date.fromisoformat(v["date_range_start"]), sm)
                      + timedelta(minutes=v["duration_minutes"] or 60))
            end_iso = end_dt.strftime("%Y-%m-%dT%H:%M:00+07:00")
        payload["updates"] = {k: x for k, x in {
            "title": v["title"], "location": v["location"], "start_time": start_iso, "end_time": end_iso,
        }.items() if x}
    run_manage(payload)


# ----------------------------- Nút hành động ----------------------------- #
# requires_confirmation = true -> có nút Xác nhận và Hủy
st.divider()
b1, b2, _, b3 = st.columns([1, 1, 2.2, 1.9])
if b1.button("← Quay lại"):
    st.switch_page("1_main_input.py")
b2.button("❌ Hủy yêu cầu", key="cancel_req")
label = "🗑 Xác nhận xóa" if variant == "Xóa sự kiện" else "✅ Xác nhận"
kq = confirm_action(b3.button(label, type="primary", disabled=bool(errors)), key="screen2", message=summary)
if variant == "Xóa sự kiện":
    tgt = {"title": "Chạy bộ", "date": "2026-10-21"}  # target_event của phần mẫu ở trên
if kq == "yes":
    with st.spinner("Đang gửi phản hồi sang n8n..."):
        try:
            if variant == "Ảnh thời khóa biểu":
                do_import()
            elif variant == "Tạo sự kiện":
                do_create()
            else:
                do_manage("delete" if variant == "Xóa sự kiện" else "update")
        except Exception as e:
            st.error(f"Lỗi kết nối n8n: {e}")
elif kq == "no":
    st.info("Bạn đã hủy. Chưa có thay đổi nào được thực hiện trên lịch.")
if st.session_state.get("cancel_req"):
    st.info("Đã hủy yêu cầu. Chưa có thay đổi nào được thực hiện trên lịch.")

# Nhiều sự kiện trùng khớp (WF06 trả target_ambiguous): cho chọn đúng sự kiện rồi gửi lại với target_event_id
amb = st.session_state.get("p2_ambig")
if amb and variant in ("Sửa sự kiện", "Xóa sự kiện"):
    cands = amb["candidates"]
    st.markdown("**Chọn đúng sự kiện**")
    pick = st.radio("Sự kiện trùng khớp", range(len(cands)), label_visibility="collapsed", key="p2_amb_pick",
                    format_func=lambda i: f"{cands[i].get('title')} · {cands[i].get('start_time')}")
    if st.button("Dùng sự kiện này", key="p2_amb_go", disabled=not cands):
        payload = {**amb["payload"], "target_event_id": cands[pick].get("google_event_id")}
        st.session_state.pop("p2_ambig", None)
        try:
            run_manage(payload)
        except Exception as e:
            st.error(f"Lỗi kết nối n8n: {e}")
