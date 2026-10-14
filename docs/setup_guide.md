# Hướng dẫn cài đặt & chạy hệ thống

## 1. Yêu cầu phần mềm

| Phần mềm | Phiên bản | Ghi chú |
|----------|-----------|---------|
| Docker Desktop | | |
| Python | | |
| dbt-postgres | | Adapter dbt cho PostgreSQL |
| Power BI Desktop | | |
| DBeaver (tùy chọn) | | Xem dữ liệu |

## 2. Chuẩn bị
1. Clone / giải nén project.
2. Tải dataset theo [dataset.md](dataset.md), đặt vào `data/raw/`.
3. Tạo file `.env` (thông tin kết nối database, API key của LLM).

## 3. Khởi tạo Data Warehouse
```bash
# [Lệnh chạy các file trong sql/ theo thứ tự 00 → 01 → 02]
```

## 4. Chạy Data Ingestion (Mage.ai)
```bash
# [Lệnh khởi động Mage]
```
- Mở Mage tại: `http://localhost:6789`
- **Full Load:** chạy pipeline `[tên]`
- **Incremental Load:** chạy pipeline `[tên]` với biến `[tên biến]`
- Kiểm tra log: `SELECT * FROM etl_log.[tên bảng] ORDER BY ...;`

## 5. Chạy Transformation (dbt)
```bash
cd dbt
dbt deps
dbt seed
dbt run
dbt test
dbt docs generate
dbt docs serve
```

## 6. Mở Power BI
1. Mở `powerbi/[tên].pbix`.
2. Cập nhật kết nối: [server, database].
3. Nhấn **Refresh**.

## 7. Chạy thành phần AI
```bash
cd ai
pip install -r requirements.txt
# [Lệnh chạy]
```

## 8. Lỗi thường gặp

| Lỗi | Nguyên nhân | Cách khắc phục |
|-----|-------------|----------------|
| Power BI báo lỗi chứng chỉ SSL khi kết nối PostgreSQL | Postgres chạy Docker không có chứng chỉ SSL hợp lệ | *File → Options and settings → Data source settings* → chọn nguồn → *Edit Permissions* → bỏ tick **Encrypt connections** |
| DBeaver báo `invalid value for parameter "TimeZone": "Asia/Saigon"` | Java gửi tên múi giờ cũ mà Postgres không nhận | Thêm dòng `-Duser.timezone=Asia/Ho_Chi_Minh` vào cuối `%LOCALAPPDATA%\DBeaver\dbeaver.ini`, mở lại DBeaver |
