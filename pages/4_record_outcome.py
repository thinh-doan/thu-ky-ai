"""TRANG 4 - Ghi nhận kết quả sự kiện (Hoàn thành / Một phần / Bỏ lỡ) cho WF10 Activity Tracker.

Vì sao có trang này:
  WF04 học thói quen từ bảng `habit_profiles`, do WF10 dựng lại từ `activity_logs`. Nguồn dữ liệu là kết quả
  người dùng báo ở đây (webhook /ai-secretary-outcome). Nếu không báo, WF10 tự ghi `missed` sau 6 giờ
  (source = auto, trọng số học chỉ 25%); báo tay luôn ghi đè bản tự động.

Dữ liệu: danh sách sự kiện chờ báo nằm trong outcome_store (file data/pending_outcomes.json, phương án C),
được ghi mỗi khi màn 2/3 tạo lịch thành công nên vẫn còn khi người dùng quay lại ở phiên khác.
Lịch thời khóa biểu lặp hằng tuần (WF07) không đưa vào đây vì WF10 ghi kết quả theo từng sự kiện.
"""
import html
from datetime import timedelta

import requests
import streamlit as st
from outcome_store import list_events, mark_recorded, now_vn, parse_local, remove_event, unwrap

N8N_OUTCOME_URL = "https://aithuky.app.n8n.cloud/webhook/ai-secretary-outcome"

USER_ID = "student@gmail.com"
AUTO_MISSED_AFTER = timedelta(hours=6)  # khớp grace_hours của WF10 (mark_missed_due)

st.set_page_config(page_title="AI Secretary · Ghi nhận kết quả", page_icon="🗓️", layout="wide")

CSS = """<style>
.block-container{padding-top:1.4rem;max-width:1150px}
.hero{background:linear-gradient(135deg,#4F46E5,#7C3AED 55%,#14B8A6 130%);color:#fff;padding:1rem 1.3rem;
 border-radius:16px;box-shadow:0 6px 20px rgba(79,70,229,.25);margin-bottom:1rem}
.hero h2{margin:0;color:#fff;font-size:1.45rem}.hero p{margin:.15rem 0 0;opacity:.9}
.tag{display:inline-block;padding:.1rem .55rem;border-radius:999px;font-size:.78rem;font-weight:600;margin:0 .3rem .25rem 0}
.tag.ok{background:#DCFCE7;color:#166534}.tag.warn{background:#FEF3C7;color:#92400E}
.tag.info{background:#E0E7FF;color:#3730A3}.tag.bad{background:#FEE2E2;color:#991B1B}
.stButton>button{border-radius:10px;font-weight:600}
.stButton>button[kind="primary"]{background:linear-gradient(135deg,#4F46E5,#6366F1);border:none;
 box-shadow:0 4px 12px rgba(79,70,229,.3)}
</style>"""
st.markdown(CSS, unsafe_allow_html=True)

OUTCOME_LABEL = {"completed": ("✅ Hoàn thành", "ok"), "partial": ("⚠ Một phần", "warn"), "missed": ("❌ Bỏ lỡ", "bad")}

ss = st.session_state

with st.sidebar:
    st.markdown("### 🗓️ AI Secretary")
    st.success("🟢 Đã kết nối **student@gmail.com**")
    st.divider()

st.markdown('<div class="hero"><h2>🗓️ AI Secretary</h2>'
            "<p>Cho tôi biết bạn đã hoàn thành hay bỏ lỡ để lần sau gợi ý giờ phù hợp hơn.</p></div>",
            unsafe_allow_html=True)
st.subheader("Ghi nhận kết quả sự kiện")
st.caption("Nếu không báo trong 6 giờ sau khi sự kiện kết thúc, hệ thống tự ghi là bỏ lỡ với trọng số học thấp. "
           "Báo tay sẽ ghi đè bản tự động.")

flash = ss.pop("_outcome_flash", None)
if flash:
    getattr(st, flash[0])(flash[1])


def fmt_when(rec):
    s, e = parse_local(rec.get("start_time")), parse_local(rec.get("end_time"))
    if not s:
        return ""
    return f"{s:%d/%m/%Y} · {s:%H:%M}" + (f"–{e:%H:%M}" if e and e > s else "")


def send_outcome(rec, outcome, minutes, note):
    """Gửi kết quả sang WF10. Thành công -> đánh dấu đã báo và tải lại trang."""
    payload = {"user_id": USER_ID, "google_event_id": rec["google_event_id"], "outcome": outcome}
    if minutes and outcome != "missed":
        payload["actual_minutes"] = int(minutes)
    if (note or "").strip():
        payload["note"] = note.strip()
    try:
        with st.spinner("Đang gửi kết quả sang n8n..."):
            res = requests.post(N8N_OUTCOME_URL, json=payload, timeout=30)
        data = unwrap(res.json()) if res.status_code == 200 else None
    except Exception as e:
        st.error(f"Không thể kết nối đến Webhook n8n: {e}")
        return
    if res.status_code != 200:
        st.error(f"Lỗi n8n ({res.status_code}): {res.text}")
    elif isinstance(data, dict) and data.get("status") == "outcome_recorded":
        mark_recorded(USER_ID, rec["google_event_id"], outcome, int(minutes) if minutes else None, note)
        ss["_outcome_flash"] = ("success", f"Đã ghi nhận “{rec['title']}”: {OUTCOME_LABEL[outcome][0]}. "
                                           "Hồ sơ thói quen đang được cập nhật.")
        st.rerun()
    else:
        d = data if isinstance(data, dict) else {}
        st.error(f"[{d.get('error_code', 'ERROR')}] {d.get('message', 'Không ghi nhận được kết quả.')}")
        if d.get("error_code") == "EVENT_NOT_FOUND":
            st.caption("Sự kiện có thể đã bị xóa khỏi Google Calendar. Bạn có thể bỏ nó khỏi danh sách.")


# ----------------------------- Sự kiện chờ ghi nhận ----------------------------- #
pending = list_events(USER_ID, "pending")
now = now_vn()

if not pending:
    st.info("Chưa có sự kiện nào cần ghi nhận. Sự kiện bạn tạo ở Màn hình 2 và 3 sẽ xuất hiện ở đây.")
    st.page_link("1_main_input.py", label="➕ Sắp xếp lịch mới")

for rec in pending:
    gid = rec["google_event_id"]
    start, end = parse_local(rec.get("start_time")), parse_local(rec.get("end_time"))
    not_started = bool(start and now < start)
    if not_started:
        status_tag = '<span class="tag info">Chưa diễn ra</span>'
    elif end and now <= end:
        status_tag = '<span class="tag warn">Đang diễn ra</span>'
    else:
        status_tag = '<span class="tag ok">Đã kết thúc</span>'
        if end and now > end + AUTO_MISSED_AFTER:
            status_tag += '<span class="tag bad">Quá 6 giờ — có thể đã tự ghi bỏ lỡ</span>'

    with st.container(border=True):
        st.markdown(f"**📌 {html.escape(rec.get('title') or '')}** · {fmt_when(rec)}<br>{status_tag}",
                    unsafe_allow_html=True)
        with st.expander("Thêm chi tiết (tùy chọn)"):
            d1, d2 = st.columns([1, 2])
            d1.number_input("Thời lượng thực tế (phút, 0 = không rõ)", 0, 1440, 0, step=5, key=f"min_{gid}")
            d2.text_input("Ghi chú", key=f"note_{gid}", max_chars=500)
        b = st.columns([1, 1, 1, 1.2])
        choice = None
        if b[0].button("✅ Hoàn thành", key=f"ok_{gid}", type="primary", disabled=not_started):
            choice = "completed"
        if b[1].button("⚠ Một phần", key=f"part_{gid}", disabled=not_started):
            choice = "partial"
        if b[2].button("❌ Bỏ lỡ", key=f"miss_{gid}", disabled=not_started):
            choice = "missed"
        if b[3].button("🗑 Bỏ khỏi danh sách", key=f"rm_{gid}"):
            remove_event(USER_ID, gid)
            st.rerun()
        if not_started:
            st.caption("Sự kiện chưa bắt đầu nên chưa thể ghi nhận kết quả.")
        if choice:
            send_outcome(rec, choice, ss.get(f"min_{gid}", 0), ss.get(f"note_{gid}", ""))

# ----------------------------- Đã ghi nhận ----------------------------- #
done = list_events(USER_ID, "recorded")
if done:
    with st.expander(f"📚 Đã ghi nhận ({len(done)})"):
        for rec in done:
            label, kind = OUTCOME_LABEL.get(rec.get("outcome"), (rec.get("outcome") or "", "info"))
            extra = f" · {rec['actual_minutes']} phút" if rec.get("actual_minutes") else ""
            st.markdown(f"**{html.escape(rec.get('title') or '')}** · {fmt_when(rec)}{extra} "
                        f'<span class="tag {kind}">{label}</span>', unsafe_allow_html=True)
