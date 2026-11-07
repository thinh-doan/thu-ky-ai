# Import workflow

1. Import từng JSON trong thư mục `n8n` vào n8n Cloud.
2. Tạo credential Google Calendar, Gemini và SQL Server trong n8n; không sửa secret vào JSON.
3. Đặt URL Python API HTTPS trong credential hoặc biến môi trường n8n `SCHEDULING_API_URL`.
4. Gán WF90 làm Error Workflow cho WF00-WF09, không gán cho chính WF90.
5. Kiểm tra WF02 chỉ trả busy events và WF04 chỉ có HTTP Request tới `/schedule/optimize`.
6. Kích hoạt WF00 sau khi test webhook. WF07 không nằm trong đường chính và có thể để inactive.
