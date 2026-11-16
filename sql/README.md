# SQL – Khởi tạo database và truy vấn kiểm tra

> Database `olist_dw` trên PostgreSQL 17 (container `olist-postgres`). Thư mục `sql/` được gắn vào container ở đường dẫn `/sql`, nên chạy được mọi file bằng `psql -f /sql/...`.

## 1. `init/` – Khởi tạo database

Postgres **tự chạy** các file này theo thứ tự tên file ở lần bật đầu tiên, khi volume `pgdata` còn trống (`compose.yaml` gắn `sql/init` vào `/docker-entrypoint-initdb.d`). Mọi file viết dạng `IF NOT EXISTS` hoặc tạo lại view, nên chạy lại nhiều lần không mất dữ liệu.

| File | Tạo gì |
|---|---|
| `00_schemas.sql` | Schema `staging`, `etl_log`, `dds`; extension `unaccent` (bỏ dấu tên thành phố); múi giờ database `Asia/Ho_Chi_Minh` |
| `01_staging_tables.sql` | 8 bảng `staging`: tên cột giữ nguyên như CSV, kiểu theo [docs/data_dictionary.md](../docs/data_dictionary.md), khóa chính theo D1 ([docs/decisions.md](../docs/decisions.md)), không khóa ngoại; 2 cột kỹ thuật `_batch_id`, `_loaded_at` |
| `02_etl_log.sql` | Nhật ký ETL: `pipeline_run` (1 lần chạy), `table_load` (1 bảng trong 1 lần chạy), `quality_check` (1 phép kiểm tra trên 1 bảng) |
| `03_dq.sql` | Schema `dq` và bảng `dq.rejected_rows`: giữ nguyên nội dung các dòng bị loại khi nạp (dạng JSONB, kèm lý do) |
| `04_soft_delete.sql` | Cột `_is_deleted`, `_deleted_at` của `staging.orders` cho cơ chế xóa mềm đơn bị xóa ở nguồn |
| `05_dbt_log.sql` | Bảng `etl_log.dbt_result`: kết quả từng node dbt (seed, model, test) trong mỗi lần chạy pipeline |
| `06_etl_monitor.sql` | 3 view cho dashboard theo dõi ETL: `etl_log.v_run`, `v_batch_progress`, `v_quality_issue` (chỉ tạo view, không tạo bảng) |

Database đã dựng từ trước khi có một file mới thì chạy tay file đó (từ PowerShell; Git Bash cần đặt `MSYS_NO_PATHCONV=1` trước lệnh):

```powershell
docker compose exec postgres psql -U olist_user -d olist_dw -f /sql/init/06_etl_monitor.sql
```

## 2. `checks/` – Truy vấn kiểm tra và đối soát

Mở bằng DBeaver (`localhost:5432`, database `olist_dw`), đặt con trỏ vào một câu rồi bấm Ctrl + Enter; mỗi câu ghi sẵn kết quả mong đợi trong chú thích.

| File | Dùng khi | Nội dung |
|---|---|---|
| `00_check_init.sql` | Sau khi dựng môi trường | Kiểm tra đủ schema, bảng, cột, view: kết quả đúng là **23 dòng PASS** |
| `01_pipeline_demo.sql` | Sau mỗi lần chạy Mage | Các lần chạy, số dòng nạp từng bảng, kiểm tra chất lượng, dòng bị loại, số dòng staging, kết quả bước dbt, lần chạy theo lịch |
| `02_dds_checks.sql` | Sau khi dbt dựng `dds` | Số dòng 9 bảng, doanh thu theo tháng, các KPI nghiệm thu (K1, K5, K6, K8, K9, K12), fact không trỏ vào dòng `-1`, các bước demo xóa mềm một đơn |
| `03_dbt_test_demo.sql` | Khi dbt test báo FAIL, khi demo | Liệt kê test đang có dòng vi phạm trong `dq`, các bước demo một test FAIL, so khóa thay thế giữa 2 lần build |
| `04_dbt_test_bad_data.sql` | Kiểm chứng dbt test (báo cáo mục 6.2.4) | 13 lỗi mẫu chia 3 nhóm. **Chỉ chạy trên bản sao `olist_dw_demo`**: mỗi khối tự dừng nếu không phải bản sao |

Chạy cả file từ dòng lệnh, ví dụ:

```powershell
docker compose exec postgres psql -U olist_user -d olist_dw -f /sql/checks/00_check_init.sql
```
