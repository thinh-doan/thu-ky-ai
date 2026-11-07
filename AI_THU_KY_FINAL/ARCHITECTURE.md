# Kiến trúc triển khai

`Client -> WF00 n8n Cloud -> WF01 Gemini -> WF02 Google Calendar -> WF03 Weather -> WF09 SQL Server -> WF04 Python API -> WF00 -> WF05 Google Calendar/SQL Server`.

Python là scheduling engine duy nhất. WF02 chỉ chuẩn hóa `busy_events`; WF03 chỉ chuẩn hóa `weather_data`; WF04 chỉ gọi HTTP API và kiểm tra response. WF06 quản lý sự kiện đã tồn tại, WF08 chỉ audit reminder, WF90 ghi lỗi.

SQL Server chạy trên máy cá nhân không thể được n8n Cloud gọi bằng `localhost`. Khuyến nghị private network/VPN hoặc một API adapter HTTPS đặt cạnh SQL Server, có TLS, mTLS/API key lưu trong n8n credential, allowlist IP và read/write user tối thiểu.
