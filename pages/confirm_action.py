"""confirm_action.py - Cửa sổ xác nhận Đồng ý / Hủy dùng chung.

Xem giao diện:   streamlit run confirm_action.py
Dùng ở file khác (cần Streamlit >= 1.37):

    from confirm_action import confirm_action

    kq = confirm_action(st.button("Xóa sự kiện"), key="xoa", message="Sự kiện này sẽ bị xóa.")
    # kq == "yes" (Đồng ý) / "no" (Hủy) ở lần chạy ngay sau khi bấm, còn lại là None

Hàm cần được gọi ở mọi lần chạy của trang (như ví dụ trên).
Dùng khi requires_confirmation = true (tạo / sửa / xóa sự kiện).
"""
import time

import streamlit as st

TITLE = "Xác nhận yêu cầu"
SUCCESS_TEXT = "Thành công"
CANCEL_TEXT = "Đã hủy"

_NOTICE_CSS = """<style>
.cf-overlay{position:fixed;inset:0;z-index:999999;display:flex;align-items:center;justify-content:center;
 background:rgba(15,23,42,.30);pointer-events:none}
.cf-card{background:#fff;border-radius:16px;padding:1.2rem 2rem;text-align:center;
 box-shadow:0 20px 50px rgba(15,23,42,.30)}
.cf-icon{width:52px;height:52px;margin:0 auto .5rem;border-radius:50%;color:#fff;
 font-size:1.8rem;display:grid;place-items:center}
.cf-icon.yes{background:#16A34A}.cf-icon.no{background:#64748B}
.cf-text{font-weight:700;color:#0F172A}
</style>"""


def _show_notice(result: str) -> None:
    """Thẻ nhỏ hiện 1 giây rồi tự biến mất. Đồng ý -> 'Thành công', Hủy -> 'Đã hủy'."""
    text, icon = (SUCCESS_TEXT, "✓") if result == "yes" else (CANCEL_TEXT, "✕")
    holder = st.empty()
    holder.markdown(
        f'{_NOTICE_CSS}<div class="cf-overlay"><div class="cf-card">'
        f'<div class="cf-icon {result}">{icon}</div><div class="cf-text">{text}</div></div></div>',
        unsafe_allow_html=True,
    )
    time.sleep(1)
    holder.empty()


def _open_dialog(key: str, message: str) -> None:
    @st.dialog(TITLE)
    def _dialog() -> None:
        st.markdown(message)
        _, c_yes, c_no, _ = st.columns([1, 1, 1, 1])
        if c_yes.button("Đồng ý", key=f"{key}_yes", type="primary"):
            st.session_state[f"_confirm::{key}"] = "yes"
            st.rerun()
        if c_no.button("Hủy", key=f"{key}_no"):
            st.session_state[f"_confirm::{key}"] = "no"
            st.rerun()

    _dialog()


def confirm_action(trigger: bool, *, key: str, message: str):
    """Mở cửa sổ xác nhận khi `trigger` là True.

    Sau khi bấm Đồng ý hoặc Hủy: cửa sổ đóng, thẻ thông báo hiện 1 giây
    ("Thành công" nếu Đồng ý, "Đã hủy" nếu Hủy).
    Trả về "yes" / "no" ở lần chạy ngay sau khi bấm, còn lại trả về None.
    """
    result = st.session_state.pop(f"_confirm::{key}", None)
    if result:
        _show_notice(result)
    if trigger:
        _open_dialog(key, message)
    return result


# Chạy trực tiếp file này để xem giao diện
if __name__ == "__main__":
    st.set_page_config(page_title="Xem trước cửa sổ xác nhận", layout="centered")
    confirm_action(
        st.button("Mở cửa sổ xác nhận", type="primary"),
        key="preview",
        message="Nội dung",
    )
