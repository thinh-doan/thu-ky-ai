# AI Thư Ký - Scheduling Engine

Bản phát hành này tách rõ trách nhiệm:

- n8n Cloud điều phối, gọi Gemini, Google Calendar, thời tiết và SQL Server.
- Python chỉ nhận dữ liệu đã tổng hợp, sinh ứng viên, kiểm tra ràng buộc, tính điểm và xếp hạng.
- Python không kết nối Google Calendar, SQL Server hoặc gửi thông báo.

## Chạy API

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn api:app --host 0.0.0.0 --port 8000
```

Kiểm tra `GET /health`. n8n Cloud cần gọi một URL HTTPS công khai có xác thực ở lớp reverse proxy/API gateway; `localhost` trên máy cá nhân không thể được n8n Cloud truy cập trực tiếp.

## API

`POST /schedule/optimize` nhận contract trong [DATA_CONTRACT.md](./DATA_CONTRACT.md). Tất cả datetime nên có offset; datetime không có offset được hiểu theo `Asia/Ho_Chi_Minh`.

## SQL Server và Google Calendar

Các workflow final giữ credential reference của n8n, không chứa secret. Với SQL Server cục bộ, dùng VPN/tunnel HTTPS hoặc triển khai SQL Server/API adapter ở mạng riêng có allowlist, TLS, xác thực và giới hạn quyền. Không expose cổng SQL trực tiếp ra Internet.
