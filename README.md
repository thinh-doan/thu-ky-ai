# AI Secretary – bản đã chỉnh sửa

## Cấu trúc
- `app.py`: điểm vào ứng dụng.
- `navigation.py`: thanh tiến trình có thể bấm, khóa các bước chưa mở.
- `pages/1_main_input.py`: màn hình nhập yêu cầu.
- `pages/2_review_edit.py`: màn hình kiểm tra/chỉnh sửa.
- `pages/3_suggest_slots.py`: màn hình chọn giờ.
- `pages/confirm_action.py`: hộp thoại xác nhận.

## Chạy
Cài thư viện nếu máy chưa có:
```bash
pip install streamlit pandas requests
```
Chạy tại thư mục chứa `app.py`:
```bash
streamlit run app.py
```

## Quy tắc điều hướng
- Bước 1 luôn truy cập được.
- Bước 2 chỉ mở sau khi màn hình 1 nhận phản hồi thành công từ webhook.
- Bước 3 chỉ mở sau khi xác nhận ở màn hình 2 và màn hình 2 chuyển tiếp.
- Bước 4 hiện là nhãn trạng thái hoàn tất, không phải trang độc lập trong bộ mã hiện tại.

## Lưu ý
- Giữ nguyên URL webhook và payload n8n có trong mã gốc.
- Các dữ liệu demo, lựa chọn sidebar demo và một số phần xử lý nghiệp vụ vẫn theo mã gốc.
- `app.py` trước đây trỏ sai tên `pages/main_input.py`; bản này đã thống nhất với `pages/1_main_input.py`.
