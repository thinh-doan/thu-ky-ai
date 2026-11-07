"""Thanh tiến trình chỉ hiển thị trạng thái; điều hướng trang do sidebar của Streamlit đảm nhiệm."""
import streamlit as st


_STEPS = (
    "Yêu cầu",
    "Kiểm tra",
    "Chọn giờ",
    "Hoàn tất",
)


def render_stepper(current: int) -> None:
    """Hiển thị thanh tiến trình 4 bước, không có nút bấm/chuyển trang."""
    current = max(1, min(4, int(current)))

    # Mỗi bước và đường nối nằm trên cùng một hàng, tương tự giao diện ban đầu.
    widths = []
    for i in range(4):
        widths.append(1.45)
        if i < 3:
            widths.append(1.0)

    columns = st.columns(widths, vertical_alignment="center")

    for step_index, label in enumerate(_STEPS, start=1):
        state = "done" if step_index < current else "active" if step_index == current else "pending"
        dot_text = "✓" if state == "done" else str(step_index)

        with columns[(step_index - 1) * 2]:
            st.markdown(
                f'<div class="ai-step {state}">'
                f'<span class="ai-step-dot">{dot_text}</span>'
                f'<span class="ai-step-label">{label}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

        if step_index < 4:
            line_state = "done" if step_index < current else "pending"
            with columns[(step_index - 1) * 2 + 1]:
                st.markdown(
                    f'<div class="ai-step-line {line_state}"></div>',
                    unsafe_allow_html=True,
                )


def stepper_css() -> str:
    return """<style>
.ai-step{
    display:flex;
    align-items:center;
    gap:.45rem;
    min-height:34px;
    white-space:nowrap;
    font-size:.88rem;
    font-weight:600;
    color:#94A3B8;
}
.ai-step-dot{
    width:30px;
    height:30px;
    min-width:30px;
    border-radius:50%;
    display:inline-flex;
    align-items:center;
    justify-content:center;
    background:#E2E8F0;
    color:#64748B;
    font-size:.85rem;
    font-weight:700;
}
.ai-step.active{color:#4F46E5}
.ai-step.active .ai-step-dot{
    background:#4F46E5;
    color:#fff;
    box-shadow:0 0 0 4px #E0E7FF;
}
.ai-step.done{color:#16A34A}
.ai-step.done .ai-step-dot{
    background:#16A34A;
    color:#fff;
}
.ai-step-line{
    width:100%;
    height:2px;
    border-radius:3px;
    background:#D8DEE9;
}
.ai-step-line.done{background:#16A34A}
@media (max-width: 700px){
    .ai-step{gap:.25rem;font-size:.72rem}
    .ai-step-dot{width:26px;height:26px;min-width:26px}
}
</style>"""
