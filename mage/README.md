# Mage.ai – Data Ingestion

> Project Mage nằm ở `mage/olist_etl/` (Mage 0.9.79 chạy trong container `olist-mage` – cách bật: [docs/setup_guide.md](../docs/setup_guide.md)).
> Kết nối Postgres khai báo trong `olist_etl/io_config.yaml`, đọc giá trị từ `.env` qua `{{ env_var('...') }}`; code Python trong `utils/` đọc thẳng biến `POSTGRES_*` (cùng nguồn).
> Quy tắc đầy đủ (vì sao làm vậy): [docs/pipeline_rules.md](../docs/pipeline_rules.md). Định dạng file batch: [data/batches/README.md](../data/batches/README.md).

## Pipelines

| Pipeline | Loại | Mô tả | Nguồn → Đích |
|----------|------|-------|--------------|
| `full_load` | Full Load | TRUNCATE 8 bảng staging rồi nạp batch `FULL` (8 file). Chạy lần đầu, hoặc khi muốn làm lại từ đầu | `data/batches/FULL/` → `staging.*` (8 bảng) |
| `incremental_load` | Incremental | Mỗi lần chạy tự tìm **1** batch kế tiếp bằng LSET / CET, nạp bằng MERGE, xử lý file xóa đơn. Nạp hết = chạy 9 lần | `data/batches/2018-01/` … `2018-09+/` → `staging.*` (5 bảng giao dịch) |

Cả hai cùng ghi `etl_log.pipeline_run` / `table_load` / `quality_check` và `dq.rejected_rows`.

## Các block

| Pipeline | Block | Loại | Chức năng |
|----------|-------|------|-----------|
| `full_load` | `start_full_run` | Data loader | Đổi lần chạy cũ kẹt `RUNNING` → `FAILED`; ghi `pipeline_run` `RUNNING` (batch `FULL`, `cet` = 2018-01-01) |
| | `load_full_batch` | Transformer | TRUNCATE staging, kiểm tra chất lượng + MERGE 8 bảng (`utils/runner.py`); trả về kết quả từng bảng |
| | `finish_full_run` | Data exporter | `pipeline_run` → `SUCCESS` |
| `incremental_load` | `get_lset` | Data loader | **Get LSET**: `cet` của lần `SUCCESS` gần nhất. Chưa Full Load → báo lỗi; đã nạp hết → dừng |
| | `set_cet` | Transformer | **Set CET**: tra `manifest.csv` dòng có `lset` = LSET → batch + CET; ghi `pipeline_run` `RUNNING` |
| | `extract_load` | Transformer | **Extract + Load**: kiểm tra chất lượng + MERGE 5 bảng, xóa mềm theo `deleted_orders.csv` |
| | `set_lset` | Data exporter | **Set LSET**: `pipeline_run` → `SUCCESS` (dòng này đã lưu `cet` → thành LSET của lần sau) |

Biến pipeline `incremental_load`: `rerun_last` (mặc định `false`) – `true` thì nạp lại đúng batch của lần `SUCCESS` gần nhất (chỉ cho chạy lại batch gần nhất – B2.3).

Code dùng chung (`olist_etl/utils/`, import `from olist_etl.utils... import ...`):

| File | Nội dung |
|------|----------|
| `settings.py` | Cột, khóa chính từng bảng, thứ tự nạp cha → con. Kiểu dữ liệu **không** khai báo lại – đọc từ bảng staging trong DB |
| `db.py` | Mở kết nối PostgreSQL |
| `batch_files.py` | Đọc `manifest.csv`, file batch (`dtype=str`, chỉ ô trống là NULL) |
| `quality.py` | 7 phép kiểm tra chất lượng, ghi `quality_check` + `dq.rejected_rows` |
| `staging.py` | COPY vào bảng tạm (cột TEXT) rồi MERGE theo khóa chính, đếm INSERT / UPDATE bằng `merge_action()` |
| `soft_delete.py` | Kiểm tra `deleted_orders.csv` và đánh dấu `_is_deleted` |
| `etl_log.py` | Ghi / đọc `etl_log` |
| `runner.py` | Nạp trọn 1 batch: gọi các file trên theo đúng thứ tự, trong 1 transaction |

## Kiểm tra chất lượng cơ bản

Chạy theo thứ tự, phép sau chỉ xét các dòng còn lại; mỗi phép ghi 1 dòng `etl_log.quality_check` kể cả khi `PASS`; dòng bị loại nằm nguyên vẹn trong `dq.rejected_rows` (JSON + lý do).

- [x] `file_exists` – đủ file của batch (FULL 8, Incremental 5) → `FAIL`, dừng batch
- [x] `columns_match` – đúng tên, đúng thứ tự cột (cả khi file không đọc được) → `FAIL`, dừng batch
- [x] `batch_id_match` – cột `batch_id` đúng batch đang nạp → `FAIL`, dừng batch
- [x] `not_null_key` – khóa chính không rỗng → `WARN`, loại dòng
- [x] `duplicate_key` – khóa không lặp trong file → `WARN`, loại **mọi** dòng mang khóa trùng
- [x] `type_cast` – giá trị ép được sang kiểu staging (số, ngày giờ, độ dài chuỗi – dùng `pg_input_is_valid()` của PostgreSQL), cột `NOT NULL` ngoài khóa không rỗng → `WARN`, loại dòng
- [x] `row_count_match` – số dòng = manifest → `WARN`, vẫn nạp

File `deleted_orders.csv` có bộ kiểm tra riêng (`columns_match`, `not_null_key`, `key_exists`, `in_window`) – `pipeline_rules.md` B6.

## Cơ chế Incremental

- **Watermark**: `order_purchase_timestamp` theo tháng (D4); batch đã cắt sẵn bằng `scripts/split_batches.py`. Khoảng nạp `[LSET, CET)` là **thời gian mô phỏng** = mốc cắt batch, lưu ở cột `lset`, `cet` của `etl_log.pipeline_run`.
- **Chọn batch**: LSET = `cet` của lần `SUCCESS` gần nhất → batch có `lset` = LSET trong `manifest.csv`. LSET **chỉ tiến khi SUCCESS**: lần lỗi không làm mất hay nhảy batch.
- **Trùng lặp / cập nhật**: MERGE theo khóa chính – chưa có thì INSERT, đã có và khác thật (`IS DISTINCT FROM`) thì UPDATE, giống hệt thì bỏ qua → chạy lại 1 batch ra 0 INSERT / 0 UPDATE. Dòng vắng mặt trong batch giữ nguyên (không xóa).
- **Xóa ở nguồn**: file tùy chọn `deleted_orders.csv` → xóa mềm `staging.orders._is_deleted = TRUE`.
- **An toàn khi lỗi**: cả batch là 1 transaction – lỗi thì staging trở về như trước khi chạy; log ghi bằng kết nối riêng nên vẫn còn.

## Ghi log

| Bảng | 1 dòng = | Cột chính |
|------|----------|-----------|
| `etl_log.pipeline_run` | 1 lần chạy | `run_id`, `pipeline_name`, `load_type`, `batch_id`, `lset`, `cet`, `started_at`, `finished_at`, `status` (`RUNNING` → `SUCCESS` / `FAILED`), `error_message` |
| `etl_log.table_load` | 1 bảng trong 1 lần chạy | `rows_source`, `rows_inserted`, `rows_updated`, `rows_rejected`, `rows_deleted`, `status`, `error_message` |
| `etl_log.quality_check` | 1 phép kiểm tra trên 1 bảng | `check_name`, `failed_rows`, `status` (`PASS` / `WARN` / `FAIL`), `detail` |
| `dq.rejected_rows` | 1 dòng bị loại | `source_row`, `row_data` (JSONB), `reason` |

- `RUNNING` được ghi **trước** khi làm; lần chạy bị ngắt (tắt máy, container dừng) được lần chạy kế tiếp đổi thành `FAILED` – "Bị ngắt giữa chừng".
- `table_load` chỉ thành `SUCCESS` sau khi cả batch commit; batch lỗi thì bảng gây lỗi ghi lỗi thật, các bảng đã MERGE trước đó ghi "Đã hoàn tác (rollback)".
- Đối soát: `rows_rejected` = số dòng `dq.rejected_rows` cùng `run_id` + bảng = tổng `failed_rows` của các phép cấp dòng.
- Câu truy vấn xem kết quả: [`sql/checks/01_pipeline_demo.sql`](../sql/checks/01_pipeline_demo.sql).

## Chạy thử từ dòng lệnh (không cần mở giao diện)

```powershell
docker compose exec mage mage run /home/src/mage/olist_etl full_load
docker compose exec mage mage run /home/src/mage/olist_etl incremental_load
```
