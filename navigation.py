"""Điều hướng các bước của AI Secretary."""
import streamlit as st

_PAGES = {
    1: ("Yêu cầu", "pages/1_main_input.py"),
    2: ("Kiểm tra", "pages/2_review_edit.py"),
    3: ("Chọn giờ", "pages/3_suggest_slots.py"),
}

def render_stepper(current: int) -> None:
    """Chỉ cho phép mở bước hiện tại và các bước đã được mở khóa."""
    st.session_state.setdefault("max_unlocked_step", 1)
    unlocked = max(1, min(3, int(st.session_state["max_unlocked_step"])))
    cols = st.columns([1.45, 1, 1.45, 1, 1.45, 1, 1.45])
    for i, step in enumerate((1, 2, 3)):
        state = "done" if step < current else ("active" if step == current else "")
        with cols[i * 2]:
            c1, c2 = st.columns([0.48, 1.5], vertical_alignment="center", gap="small")
            allowed = step <= unlocked
            label = "✓" if state == "done" else str(step)
            if c1.button(label, key=f"step_navigation_{step}",
                          help=f"Đi tới bước {step}: {_PAGES[step][0]}",
                          disabled=not allowed, type="primary" if step == current else "secondary"):
                if step != current:
                    st.switch_page(_PAGES[step][1])
            c2.markdown(f'<span class="step-name {state}">{_PAGES[step][0]}</span>',
                        unsafe_allow_html=True)
        if i < 2:
            with cols[i * 2 + 1]:
                st.markdown(f'<div class="step-line {"done" if step < current else ""}"></div>',
                            unsafe_allow_html=True)
    with cols[6]:
        final_state = "done" if current >= 4 else ""
        st.markdown(
            f'<div class="final-step"><span class="step-dot {final_state}">4</span>'
            f'<span class="step-name {final_state}">Hoàn tất</span></div>',
            unsafe_allow_html=True)

def stepper_css() -> str:
    return """<style>
.step-name{font-weight:600;color:#94A3B8;white-space:nowrap}
.step-name.active{color:#4F46E5}.step-name.done{color:#16A34A}
.step-line{height:3px;background:#E2E8F0;border-radius:3px;min-width:16px;margin-top:15px}
.step-line.done{background:#16A34A}
.final-step{display:flex;align-items:center;gap:.5rem}
.step-dot{width:30px;height:30px;border-radius:50%;display:inline-grid;place-items:center;
background:#E2E8F0;color:#64748B;font-size:.9rem;font-weight:700;flex:0 0 30px}
.step-dot.done{background:#16A34A;color:#fff}
div[data-testid="stHorizontalBlock"] button[kind="secondary"]{
border:1px solid #CBD5E1;background:#F8FAFC;color:#334155}
div[data-testid="stHorizontalBlock"] button:disabled{opacity:.42;cursor:not-allowed}
</style>"""
