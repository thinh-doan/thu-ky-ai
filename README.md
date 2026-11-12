# AI Thư Ký

Ứng dụng Streamlit hỗ trợ sắp xếp lịch bằng tiếng Việt. Người dùng có thể nhập
yêu cầu tự nhiên hoặc tải ảnh thời khóa biểu, kiểm tra thông tin hệ thống đọc
được, chọn khung giờ phù hợp và theo dõi kết quả của sự kiện đã tạo.

## Luồng sử dụng

1. **Yêu cầu** – nhập yêu cầu bằng tiếng Việt hoặc tải ảnh thời khóa biểu.
2. **Kiểm tra** – xem và chỉnh sửa dữ liệu trước khi ghi vào lịch.
3. **Chọn giờ** – xem tối đa các khung giờ được đề xuất, lý do chấm điểm và
   chọn khung giờ để tạo sự kiện.
4. **Ghi nhận kết quả** – đánh dấu sự kiện là hoàn thành, một phần hoặc bỏ lỡ
   để hệ thống cập nhật hồ sơ thói quen.

Ứng dụng cũng hỗ trợ xem, sửa và xóa sự kiện; xử lý sự kiện trùng lịch; nhập
lịch lặp từ ảnh; và gửi kết quả thực tế của sự kiện về n8n.

## Kiến trúc

```text
Streamlit (app.py)
        │
        └── Webhook n8n
             ├── AI Parse Request (Gemini)
             ├── Google Calendar
             ├── Weather
             ├── Python Scheduling Engine
             ├── PostgreSQL / Data Store
             └── Activity Tracker
```

- **Streamlit**: giao diện, kiểm tra dữ liệu người dùng, hiển thị đề xuất và
  lưu danh sách sự kiện chờ ghi nhận.
- **n8n**: điều phối các workflow, gọi Gemini, Google Calendar, thời tiết và
  lớp lưu trữ.
- **Python Scheduling Engine**: nhận dữ liệu đã tổng hợp từ n8n, kiểm tra ràng
  buộc, tính điểm và xếp hạng khung giờ.
- **Google Calendar, PostgreSQL và credential**: chỉ được truy cập qua n8n;
  không đặt secret trong mã nguồn Streamlit.

Các workflow mẫu nằm trong thư mục [`n8n/`](./n8n/). Workflow chính là
`test_00_Main_Request_Orchestrator.json`; các workflow còn lại xử lý phân tích
yêu cầu, đọc lịch, thời tiết, chấm điểm, tạo/quản lý sự kiện, nhập ảnh, nhắc
lịch, lưu dữ liệu và logging lỗi.

## Yêu cầu

- Python 3.10 trở lên
- Một instance n8n có webhook công khai qua HTTPS
- Các credential/service tương ứng nếu chạy với dữ liệu thật:
  Gemini, Google Calendar, weather và PostgreSQL/Data Store

## Cài đặt và chạy

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Sau đó mở URL được Streamlit in ra, thường là
`http://localhost:8501`.

`app.py` là entry point của ứng dụng. Các màn hình nhiều trang nằm trong
[`pages/`](./pages/):

- `1_main_input.py` – nhập yêu cầu và ảnh thời khóa biểu
- `2_review_edit.py` – kiểm tra/chỉnh sửa và xác nhận
- `3_suggest_slots.py` – chọn khung giờ và tạo sự kiện
- `4_record_outcome.py` – ghi nhận kết quả sự kiện

## Chế độ demo và n8n thật

Giao diện có dữ liệu mẫu để xem trước khi webhook n8n không phản hồi hoặc chưa
được cấu hình đầy đủ. Chế độ này chỉ phục vụ trình diễn; không tạo sự kiện
thật trên Google Calendar.

Khi chạy tích hợp thật, các trang Streamlit gửi request tới webhook
`ai-secretary` và trang ghi nhận kết quả gửi tới webhook
`ai-secretary-outcome`. Hãy kiểm tra URL webhook và `USER_ID` trong các file
trong [`pages/`](./pages/) trước khi triển khai cho người dùng khác. Không dùng
`localhost` làm URL webhook nếu n8n chạy trên cloud.

## Dữ liệu cục bộ

Danh sách sự kiện chờ ghi nhận được lưu trong
[`data/pending_outcomes.json`](./data/pending_outcomes.json). Đây là state cục
bộ của bản demo, không phải database dùng cho triển khai nhiều người dùng.
Khi triển khai production, nên thay bằng storage dùng chung và cấu hình định
danh người dùng thay vì giữ giá trị mẫu trong mã nguồn.

## Lưu ý triển khai

- Chỉ expose webhook/API qua HTTPS và có xác thực ở reverse proxy hoặc API
  gateway.
- Không expose trực tiếp cổng SQL Server/PostgreSQL ra Internet.
- Giới hạn quyền của credential n8n theo đúng thao tác cần thiết.
- Không commit secret, token, credential hoặc file secrets vào repository.
