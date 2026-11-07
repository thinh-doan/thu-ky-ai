# Cấu hình

- Python: `SCHEDULING_API_HOST`, `SCHEDULING_API_PORT`, `LOG_LEVEL`.
- n8n: cấu hình `SCHEDULING_API_URL` là URL HTTPS public của API.
- Google Calendar: chọn credential hiện có trong node Google Calendar; không hardcode token.
- SQL Server: dùng node Microsoft SQL với credential n8n. Nếu DB ở máy cá nhân, dùng VPN/tunnel/private adapter, TLS và allowlist; không dùng `localhost` từ n8n Cloud.
- Timezone mặc định: `Asia/Ho_Chi_Minh`; workflow và Python truyền datetime ISO-8601 có offset.
