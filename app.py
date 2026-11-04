"""Điểm vào ứng dụng AI Secretary. Chạy bằng: streamlit run app.py"""

from pathlib import Path
import runpy


runpy.run_path(
    str(Path(__file__).parent / "pages" / "1_main_input.py"),
    run_name="__main__",
)
