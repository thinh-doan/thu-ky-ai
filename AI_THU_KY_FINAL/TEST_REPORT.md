# Test report

Đã kiểm tra bằng dữ liệu giả lập trong test suite:

- sinh slot bước 15 phút và giới hạn giờ hoạt động;
- timezone không phụ thuộc busy event và xử lý busy rỗng;
- loại xung đột, buffer và travel time;
- ánh xạ weather theo giờ cho slot 15 phút;
- profile thực tế ảnh hưởng ranking;
- không có slot trả lỗi có cấu trúc;
- JSON workflow parse được, node id duy nhất và kết nối hợp lệ.

Chưa thể kiểm thử thật Google Calendar, Gemini, SQL Server hoặc n8n Cloud vì workspace không có credential và SQL Server public endpoint. Đây là giới hạn môi trường, không được báo cáo là kết nối thành công.
