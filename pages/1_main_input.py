"""MÀN HÌNH 1 - Giao diện chính: nhập yêu cầu bằng tiếng Việt hoặc tải ảnh thời khóa biểu.

Chạy:  streamlit run 1_main_input.py
(Chỉ là giao diện demo: kết quả AI là dữ liệu mẫu theo đúng cấu trúc JSON của đồ án, không cần API key.)

Giao diện dựa vào `status` để quyết định hiển thị:
  success             -> hiển thị nội dung đã hiểu / sang bước tiếp theo
  needs_clarification -> hiển thị clarification_question
  unsupported         -> hiển thị user_message và dừng
  error               -> hiển thị thông báo lỗi
  requires_confirmation = true -> hiển thị nút Xác nhận và Hủy
"""
import time
import streamlit as st
import requests
import base64
from navigation import render_stepper, stepper_css

N8N_WEBHOOK_URL = "https://k25416-thukyai.app.n8n.cloud/webhook/ai-secretary"

st.set_page_config(page_title="AI Secretary · Yêu cầu", page_icon="🗓️", layout="wide")

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


EXAMPLES = {
    "Họp dự án": "Đặt lịch họp dự án lúc 9 giờ sáng ngày 22/10/2026 trong một giờ.",
    "Chạy bộ": "Tìm cho tôi một giờ chạy bộ tại Công viên Gia Định trong tuần sau, ưu tiên buổi chiều và tránh lúc mưa.",
    "Thiếu thời lượng": "Đặt lịch gặp khách hàng lúc 14 giờ ngày 24/10/2026.",
    "Ngoài phạm vi": "Viết cho tôi một bài quảng cáo.",
}

# Dữ liệu mẫu theo đúng hợp đồng JSON (chỉ dùng các trường giao diện cần hiển thị)
SAMPLE = {
    "success": {
        "status": "success", "intent": "create_event",
        "event": {"title": "Họp dự án", "date_range_start": "2026-10-22", "specific_start_time": "09:00",
                  "duration_minutes": 60, "preferred_period": "morning", "location": None},
        "target_event": {}, "missing_fields": [], "clarification_question": None,
        "requires_confirmation": True,
        "user_message": "Đã xác định yêu cầu tạo lịch họp dự án lúc 9 giờ ngày 22/10/2026 trong một giờ.",
    },
    "needs_clarification": {
        "status": "needs_clarification", "intent": "create_event",
        "event": {"title": "Gặp khách hàng", "date_range_start": "2026-10-24", "specific_start_time": "14:00",
                  "duration_minutes": None, "preferred_period": "afternoon", "location": None},
        "target_event": {}, "missing_fields": ["event.specific_end_time", "event.duration_minutes"],
        "clarification_question": "Cuộc gặp khách hàng dự kiến kéo dài bao lâu?",
        "requires_confirmation": False,
        "user_message": "Tôi cần biết thời lượng hoặc giờ kết thúc của cuộc gặp.",
    },
    "unsupported": {
        "status": "unsupported", "intent": "unknown", "event": {}, "target_event": {},
        "missing_fields": [], "clarification_question": None, "requires_confirmation": False,
        "user_message": "Yêu cầu này nằm ngoài phạm vi quản lý lịch của hệ thống.",
    },
    "error": {
        "status": "error", "intent": "unknown", "event": {}, "target_event": {},
        "missing_fields": [], "clarification_question": None, "requires_confirmation": False,
        "user_message": "Dịch vụ AI đang gặp sự cố. Vui lòng thử lại sau ít phút.",
    },
    "image": {
        "status": "success", "intent": "import_schedule_image", "event": {}, "target_event": {},
        "missing_fields": [], "clarification_question": None, "requires_confirmation": False,
        "user_message": "Đã đọc được 5 sự kiện từ ảnh. Vui lòng kiểm tra ở bước tiếp theo trước khi thêm vào lịch.",
    },
}
INTENT_LABELS = {
    "create_event": "Tạo sự kiện", "find_suitable_time": "Tìm thời gian phù hợp", "view_events": "Xem lịch",
    "update_event": "Sửa sự kiện", "delete_event": "Xóa sự kiện", "check_availability": "Kiểm tra thời gian rảnh",
    "import_schedule_image": "Nhập lịch từ hình ảnh", "unknown": "Chưa xác định",
}
PERIOD_LABELS = {"morning": "Buổi sáng", "afternoon": "Buổi chiều", "evening": "Buổi tối", "any": "Bất kỳ"}


def set_text(prompt):
    st.session_state["request_text"] = prompt


def reset():
    for k in ("request_text", "pref_tod", "pref_avoid", "resp", "request_kind", "answered"):
        st.session_state.pop(k, None)


ss = st.session_state

# ----------------------------- Sidebar ----------------------------- #
with st.sidebar:
    st.markdown("### 🗓️ AI Secretary")
    st.success("🟢 Đã kết nối **student@gmail.com**")
    with st.expander("⚙️ Cài đặt"):
        st.selectbox("Múi giờ", ["Asia/Ho_Chi_Minh"], disabled=True)
        st.slider("Giờ làm việc", 0, 24, (7, 22))
    st.divider()
    st.caption("🧪 Điều khiển demo")
    demo = st.radio("Kết quả AI mô phỏng (status)",
                    ["success", "needs_clarification", "unsupported", "error"],
                    help="Chọn trạng thái để xem giao diện hiển thị tương ứng. Với ảnh, luôn mô phỏng success.")
    st.button("🔄 Làm lại từ đầu", on_click=reset)
    st.caption("Ứng dụng không lưu dữ liệu. Sự kiện chỉ nằm trong Google Calendar.")

# ----------------------------- Main ----------------------------- #
st.markdown('<div class="hero"><h2>🗓️ AI Secretary</h2><p>Hãy cho tôi biết cần sắp xếp gì, tôi sẽ tìm thời gian phù hợp.</p></div>',
            unsafe_allow_html=True)
render_stepper(1)
st.subheader("👋 Xin chào! Bạn muốn sắp xếp lịch gì?")

tab_text, tab_img = st.tabs(["✍️ Nhập yêu cầu", "🖼️ Tải ảnh thời khóa biểu"])

with tab_text:
    st.text_area("Yêu cầu của bạn", key="request_text", height=140, label_visibility="collapsed",
                 placeholder='Ví dụ: "Đặt lịch họp dự án lúc 9 giờ sáng ngày 22/10/2026 trong một giờ"')
    st.caption("Thử một ví dụ:")
    for col, (label, prompt) in zip(st.columns(len(EXAMPLES)), EXAMPLES.items()):
        col.button(label, key=f"chip_{label}", on_click=set_text, args=(prompt,))
    go_text = st.button("✨ Phân tích bằng AI", type="primary", key="go_text")

with tab_img:
    source = st.radio("Nguồn ảnh", ["📁 Tải tệp lên", "📷 Chụp ảnh"],
                      horizontal=True, label_visibility="collapsed")
    if source.startswith("📁"):
        up = st.file_uploader("Tải ảnh thời khóa biểu hoặc lịch trình", type=["png", "jpg", "jpeg"])
        if up is not None:
            st.image(up, caption=up.name, width=420)
    else:
        st.caption("Hãy cho phép trình duyệt truy cập camera. Đặt thời khóa biểu phẳng và chữ rõ nét.")
        up = st.camera_input("Chụp ảnh thời khóa biểu")

    go_img = st.button("✨ Phân tích bằng AI", type="primary", key="go_img")

with st.expander("▸ Tùy chọn thêm"):
    c1, c2 = st.columns(2)
    c1.multiselect("Buổi ưu tiên", ["Sáng", "Chiều", "Tối"], key="pref_tod")
    c2.multiselect("Ngày muốn tránh", ["Thứ 2", "Thứ 3", "Thứ 4", "Thứ 5", "Thứ 6", "Thứ 7", "Chủ nhật"],
                   key="pref_avoid")
    c1.number_input("Khoảng nghỉ giữa các sự kiện (phút)", 0, 120, 15, step=5)
    c2.checkbox("Tránh lúc trời mưa (kiểm tra thời tiết)")

# ----------------------------- Actions ----------------------------- #
if go_text or go_img:
    if go_text and not ss.get("request_text", "").strip():
        st.warning("Vui lòng nhập yêu cầu hoặc tải ảnh lên trước.")
    elif go_img and up is None:
        st.warning("Vui lòng nhập yêu cầu hoặc tải ảnh lên trước.")
    else:
        with st.status(
            "AI đang xử lý qua Workflow n8n...", expanded=True
        ) as stt:
            try:
                if go_text:
                    # Bổ sung đúng tên trường user_id và message mà n8n yêu cầu
                    payload = {
                        "action": "submit_request",
                        "user_id": "student@gmail.com",  # Thêm user_id cho n8n validate
                        "message": ss.get(
                            "request_text"
                        ),  # Thêm message theo đúng yêu cầu n8n
                        "prompt": ss.get("request_text"),
                        "user_email": "student@gmail.com",
                    }
                    res = requests.post(
                        N8N_WEBHOOK_URL, json=payload, timeout=30
                    )

                # MÃ MỚI ĐÃ SỬA CHUẨN
                elif go_img:
                    # 1. Chuyển đổi file ảnh sang dạng mã hóa Base64
                    bytes_data = up.getvalue()
                    base64_image = base64.b64encode(bytes_data).decode("utf-8")

                    # 2. Lấy MIME type của file ảnh (tự động fallback về image/jpeg nếu rỗng)
                    mime_type = (
                        up.type
                        if (up and hasattr(up, "type") and up.type)
                        else "image/jpeg"
                    )

                    # 3. Đóng gói dữ liệu JSON chứa đầy đủ image_base64 và mime_type
                    payload = {
                        "action": "submit_image",
                        "user_id": "student@gmail.com",
                        "user_email": "student@gmail.com",
                        "message": "Tải ảnh thời khóa biểu",
                        "image_base64": base64_image,
                        "mime_type": mime_type,
                    }

                    # 4. Gửi request dưới dạng JSON payload
                    res = requests.post(
                        N8N_WEBHOOK_URL, json=payload, timeout=30
                    )

                if res.status_code == 200:
                    stt.update(label="Đã phân tích xong!", state="complete")
                    data = res.json()

                    # Nếu n8n trả về danh sách [ {...} ], tự động lấy phần tử đầu tiên
                    if isinstance(data, list) and len(data) > 0:
                        data = data[0]

                    # Nếu dữ liệu bọc trong trường 'body'
                    if isinstance(data, dict) and "body" in data:
                        data = data["body"]

                    if isinstance(data, dict) and isinstance(data.get("response"), dict):
                        data = data["response"]
                    ss.resp = data
                    ss.request_kind = "image" if go_img else "text"
                    ss.pop("answered", None)
                    response_status = data.get("status") if isinstance(data, dict) else None
                    if go_img and response_status in ("import_ready", "success", "ok"):
                        st.switch_page("pages/2_review_edit.py")
                    elif go_text and response_status in ("proposals_ready", "success", "ok"):
                        st.switch_page("pages/3_suggest_slots.py")
                else:
                    stt.update(label="Lỗi xử lý!", state="error")
                    st.error(f"Lỗi n8n ({res.status_code}): {res.text}")
            except Exception as e:
                stt.update(label="Lỗi kết nối!", state="error")
                st.error(f"Không thể kết nối đến Webhook n8n: {e}")

# ----------------------------- Hiển thị theo status ----------------------------- #
resp = ss.get("resp")
if resp:
    # Lấy status và intent an toàn (tránh sập web nếu n8n trả thiếu trường)
    status = resp.get("status", "error") if isinstance(resp, dict) else "error"
    intent_val = resp.get("intent", "unknown") if isinstance(resp, dict) else "unknown"

    st.divider()
    st.caption("Kết quả phân tích · Ý định: **" + INTENT_LABELS.get(intent_val, intent_val) + "**")

    # Lấy thông điệp người dùng an toàn (tìm theo user_message, message hoặc error)
    msg = (
            resp.get("user_message")
            or resp.get("message")
            or resp.get("error")
            or "Đã nhận phản hồi từ hệ thống."
    )

    if status in ("success", "proposals_ready", "import_ready"):
        st.success(msg)
        ev = resp.get("event") or {}
        tags = []
        if isinstance(ev, dict):
            if ev.get("title"):
                tags.append(f'<span class="tag info">{ev["title"]}</span>')
            if ev.get("date_range_start"):
                try:
                    y, m, d = ev["date_range_start"].split("-")
                    tags.append(f'<span class="tag info">Ngày {d}/{m}/{y}</span>')
                except Exception:
                    tags.append(
                        f'<span class="tag info">Ngày {ev["date_range_start"]}</span>'
                    )
            if ev.get("specific_start_time"):
                tags.append(
                    f'<span class="tag info">Bắt đầu {ev["specific_start_time"]}</span>'
                )
            if ev.get("duration_minutes"):
                tags.append(
                    f'<span class="tag info">{ev["duration_minutes"]} phút</span>'
                )
            if ev.get("preferred_period"):
                tags.append(
                    f'<span class="tag info">{PERIOD_LABELS.get(ev["preferred_period"], "")}</span>'
                )
        if tags:
            st.markdown("".join(tags), unsafe_allow_html=True)

        req_confirm = resp.get("requires_confirmation", False)
        if req_confirm:
            st.info("Bạn có muốn tiếp tục với nội dung trên không?")
            b1, b2, _ = st.columns([1, 1, 4])
            if b1.button("✅ Xác nhận", type="primary", key="ok1"):
                ss.answered = "ok"
            if b2.button("❌ Hủy", key="no1"):
                ss.answered = "no"
            if ss.get("answered") == "ok":
                st.success(
                    "Đã xác nhận. Bước tiếp theo: kiểm tra thông tin ở Màn hình 2 (`2_review_edit.py`)."
                )
            elif ss.get("answered") == "no":
                st.info("Đã hủy yêu cầu. Bạn có thể nhập yêu cầu khác.")
        else:
            st.markdown(
                "➡️ Bước tiếp theo: kiểm tra thông tin ở Màn hình 2 (`2_review_edit.py`)."
            )

    elif status == "needs_clarification":
        cq = resp.get(
            "clarification_question", "Cần thêm thông tin để xử lý."
        )
        st.warning(cq)
        st.caption(msg)
        ans = st.text_input(
            "Câu trả lời của bạn",
            key="clarify_ans",
            placeholder="Ví dụ: 1 tiếng",
        )
        if st.button("Gửi câu trả lời", type="primary"):
            if ans.strip():
                st.toast("Đã gửi, AI sẽ phân tích lại", icon="📨")
            else:
                st.warning("Vui lòng nhập câu trả lời.")

    elif status == "unsupported":
        st.warning(msg)
        st.caption(
            "Bạn có thể nhập yêu cầu liên quan đến lịch: tạo, xem, sửa, xóa sự kiện hoặc tìm thời gian trống."
        )
        st.stop()

    else:  # error hoặc trạng thái khác
        st.error(msg)
        st.button("🔁 Thử lại")
        st.stop()
