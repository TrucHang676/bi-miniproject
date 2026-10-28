# Mage.ai – Data Ingestion

> Project Mage nằm ở `mage/olist_etl/` (Mage 0.9.79 chạy trong container `olist-mage` – cách bật: [docs/setup_guide.md](../docs/setup_guide.md)).
> Kết nối Postgres khai báo trong `olist_etl/io_config.yaml`, đọc giá trị từ `.env` qua `{{ env_var('...') }}`; code Python trong `utils/` đọc thẳng biến `POSTGRES_*` (cùng nguồn).
> Quy tắc đầy đủ (vì sao làm vậy): [docs/pipeline_rules.md](../docs/pipeline_rules.md). Định dạng file batch: [data/batches/README.md](../data/batches/README.md).
> **Từ 24/10/2026 (BS-34), mỗi lần chạy pipeline Mage gọi luôn dbt sau khi nạp xong `staging`**: một lần bấm chạy = CSV → `staging` → `dds` (mục [Bước dbt](#bước-dbt-bs-34)).

## Pipelines

| Pipeline | Loại | Mô tả | Nguồn → Đích |
|----------|------|-------|--------------|
| `full_load` | Full Load | TRUNCATE 8 bảng staging, nạp batch `FULL` (8 file) rồi `dbt build --full-refresh` dựng lại `dds` từ đầu. Chạy lần đầu, hoặc khi muốn làm lại từ đầu | `data/batches/FULL/` → `staging.*` (8 bảng) → `dds.*` (9 bảng) |
| `incremental_load` | Incremental | Mỗi lần chạy tự tìm **1** batch kế tiếp bằng LSET / CET, nạp bằng MERGE, xử lý file xóa đơn, rồi `dbt build` cập nhật `dds`. Nạp hết = chạy 9 lần | `data/batches/2018-01/` … `2018-09+/` → `staging.*` (5 bảng giao dịch) → `dds.*` |

Cả hai cùng ghi `etl_log.pipeline_run` / `table_load` / `quality_check` / `dbt_result` và `dq.rejected_rows`.

## Các block

| Pipeline | Block | Loại | Chức năng |
|----------|-------|------|-----------|
| `full_load` | `start_full_run` | Data loader | Đổi lần chạy cũ kẹt `RUNNING` → `FAILED`; ghi `pipeline_run` `RUNNING` (batch `FULL`, `cet` = 2018-01-01) |
| | `load_full_batch` | Transformer | TRUNCATE staging, kiểm tra chất lượng + MERGE 8 bảng (`utils/runner.py`); trả về kết quả từng bảng |
| | `dbt_build_full` | Transformer | **Transform**: `dbt build --full-refresh` (`utils/dbt_runner.py`) – dựng lại `dds` từ đầu, kể cả 2 dimension incremental; ghi `etl_log.dbt_result`; trả về kết quả từng node |
| | `finish_full_run` | Data exporter | `pipeline_run` → `SUCCESS` (chỉ khi cả nạp staging lẫn dbt thành công) |
| `incremental_load` | `get_lset` | Data loader | **Get LSET**: `cet` của lần `SUCCESS` gần nhất. Chưa Full Load → báo lỗi; đã nạp hết → dừng; Full Load gần nhất lỗi ở bước dbt → báo lỗi (mục [Bước dbt](#bước-dbt-bs-34)) |
| | `set_cet` | Transformer | **Set CET**: tra `manifest.csv` dòng có `lset` = LSET → batch + CET; ghi `pipeline_run` `RUNNING` |
| | `extract_load` | Transformer | **Extract + Load**: kiểm tra chất lượng + MERGE 5 bảng, xóa mềm theo `deleted_orders.csv` |
| | `dbt_build` | Transformer | **Transform**: `dbt build` cập nhật `dds` từ staging vừa nạp; ghi `etl_log.dbt_result`. Đã nạp hết batch → bỏ qua |
| | `set_lset` | Data exporter | **Set LSET**: `pipeline_run` → `SUCCESS` (dòng này đã lưu `cet` → thành LSET của lần sau). Chỉ chạy khi cả nạp staging lẫn dbt thành công |

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
| `etl_log.py` | Ghi / đọc `etl_log`; chặn Incremental khi staging đã đi trước LSET (`check_staging_in_sync`) |
| `runner.py` | Nạp trọn 1 batch: gọi các file trên theo đúng thứ tự, trong 1 transaction |
| `dbt_runner.py` | Bước dbt: chạy `dbt build`, in log dbt ra Mage, ghi `etl_log.dbt_result`, lỗi thì ghi `FAILED` |

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
- **Chọn batch**: LSET = `cet` của lần `SUCCESS` gần nhất → batch có `lset` = LSET trong `manifest.csv`. LSET **chỉ tiến khi SUCCESS** – tức khi cả nạp staging lẫn dbt đều xong: lần lỗi không làm mất hay nhảy batch.
- **Trùng lặp / cập nhật**: MERGE theo khóa chính – chưa có thì INSERT, đã có và khác thật (`IS DISTINCT FROM`) thì UPDATE, giống hệt thì bỏ qua → chạy lại 1 batch ra 0 INSERT / 0 UPDATE. Dòng vắng mặt trong batch giữ nguyên (không xóa).
- **Xóa ở nguồn**: file tùy chọn `deleted_orders.csv` → xóa mềm `staging.orders._is_deleted = TRUE`.
- **An toàn khi lỗi**: cả batch là 1 transaction – lỗi thì staging trở về như trước khi chạy; log ghi bằng kết nối riêng nên vẫn còn. Lỗi ở bước dbt thì staging **đã** commit (không hoàn tác) – xử lý ở mục [Bước dbt](#bước-dbt-bs-34).

## Bước dbt (BS-34)

Từ 24/10/2026, ngay sau khi `staging` commit, mỗi pipeline gọi `dbt build` dựng `dds` – giống hệt gõ tay `docker compose exec mage dbt build`, nhưng Mage tự làm trong cùng lần chạy. Chỉ khi dbt xong mới ghi `SUCCESS` (giống mẫu cô demo: nạp stage → dbt → chốt watermark):

```
full_load        : start_full_run → load_full_batch → dbt_build_full → finish_full_run
                                    (staging)         (dds, --full-refresh)
incremental_load : get_lset → set_cet → extract_load → dbt_build → set_lset
                                        (staging)      (dds)       (LSET tiến)
```

- **Cách gọi** (`utils/dbt_runner.py`): chạy `dbt build --project-dir /home/src/dbt --profiles-dir /home/src/dbt` (Full Load thêm `--full-refresh`) bằng tiến trình con – dbt nằm sẵn trong container Mage nên dùng đúng project + `profiles.yml` như lệnh gõ tay. Log của dbt (`1 of 177 START …` → `Done. PASS=177 …`) hiện ngay trong log của block; sau đó đọc `dbt/target/run_results.json` ghi vào `etl_log.dbt_result`. Output của block = bảng kết quả từng node: seed, model (kèm số dòng) rồi test.
- **Không dùng block dbt có sẵn của Mage**: block đó chỉ chạy lệnh dbt – không ghi được `etl_log`, không kiểm tra `run_id` còn `RUNNING` (`StaleRunError`) và không ghi `FAILED` khi lỗi nếu không viết thêm callback. Block Python dùng chung cơ chế với các block khác.
- **Cần có trên mỗi máy**: `dbt/profiles.yml` + `dbt deps` ([setup_guide.md](../docs/setup_guide.md) mục 6.3), thiếu thì block dbt đỏ, `error_message` ghi lý do. Không gõ `dbt` tay trong lúc pipeline đang chạy (2 lần dbt cùng dựng `dds`, cùng ghi `dbt/target/`).
- **Thời gian** (máy Hằng, 24/10/2026, 22 lần chạy thử): Full Load 53–63 giây (dbt 36–45); mỗi lần Incremental 41–62 giây (nạp ~10–15 + dbt 30–47). Lần dbt đầu tiên sau khi đổi database / `profiles.yml` lâu thêm ~8 giây vì dbt phải phân tích lại project (`Unable to do partial parsing`).

Khi lỗi:

| Lỗi ở | Staging | `dds` | `pipeline_run` | Lần chạy sau |
|---|---|---|---|---|
| Nạp staging (`load_full_batch` / `extract_load`) | Hoàn tác (rollback) | Không đổi – dbt không chạy | `FAILED` | Nạp lại đúng batch đó |
| dbt của Incremental (`dbt_build`) | **Đã có batch mới** (đã commit, `table_load` `SUCCESS`) | Dựng dở: node lỗi và các node phía sau nó bị bỏ qua (`skipped`) | `FAILED`, `error_message` = số node theo trạng thái + node lỗi | `get_lset` chọn lại đúng batch đó: MERGE ra 0 INSERT / 0 UPDATE (trừ dòng đã sửa) rồi chạy dbt lại |
| dbt của Full Load (`dbt_build_full`) | Đã làm lại từ đầu (chỉ còn batch FULL) | Dựng dở | `FAILED` | `incremental_load` **bị chặn**: "Full Load run_id … chưa xong" → chạy lại `full_load` |

- `rerun_last = true` sau một lần Incremental lỗi ở bước dbt cũng bị chặn: staging đã có batch mới hơn batch của lần SUCCESS, nạp lại batch cũ đè lên sẽ đưa đơn về trạng thái cũ (B2.3) → chạy bình thường (`rerun_last = false`).
- Cách chặn: `etl_log.check_staging_in_sync` (gọi ở `get_lset`, lặp lại ở `set_cet` phòng output cũ) tìm lần chạy **sau** lần SUCCESS gần nhất có `table_load` `SUCCESS` (= staging đã commit). Bắt được cả trường hợp pipeline bị ngắt sau khi staging commit.
- dbt test FAIL cũng làm lần chạy `FAILED`: `error_message` nêu tên test + bảng `dq` chứa dòng vi phạm (`etl_log.dbt_result.relation_name`). Sửa dữ liệu nguồn (hoặc chốt lại quy tắc của test) rồi chạy lại.

Kiểm thử (24/10/2026, máy Hằng, DB tạm `olist_test` đã xóa sau khi thử; chạy bằng `mage run`, lỗi giả làm trên bản sao batch trong `/tmp` của container qua biến `OLIST_BATCH_DIR` – không đụng file batch thật). Số kịch bản theo [pipeline_rules.md](../docs/pipeline_rules.md) B12:

| # | Kịch bản | Kết quả |
|---|---|---|
| 10 | `full_load` + 9 lần `incremental_load` trên DB trống | 10/10 `SUCCESS`, lần nào dbt cũng `PASS=177`. Số dòng 3 fact sau từng batch khớp bảng kịch bản 3 của [dbt/README.md](../dbt/README.md) mục 4 (FULL 46.418 · 45.394 · 42.867 → 2018-09+ 101.953 · 100.010 · 100.568); `02_dds_checks.sql` khớp mọi số mong đợi (doanh thu 01/2017 – 08/2018 13.449.529,68; K6 6,77%; K12 9,02%; K8 4,09; K5 2,27%) |
| – | Chạy thêm khi đã nạp hết | Dừng "đã nạp hết batch", block `dbt_build` bỏ qua (không chạy dbt), không ghi `pipeline_run` |
| 12 | `full_load` mà dbt không chạy được (biến `DBT_PROFILES_DIR` trỏ vào thư mục không có) | `FAILED`, `error_message` = lỗi của dbt (`Invalid value for '--profiles-dir'`); 8 bảng `table_load` `SUCCESS`; `dbt_result` 0 dòng |
| 13 | Ngay sau đó chạy `incremental_load` (thường và `rerun_last = true`) | Cả hai bị chặn: "Full Load run_id 11 đã làm lại staging từ đầu nhưng chưa xong…", không mở lần chạy mới. Chạy lại `full_load` → `SUCCESS`, `dds` về đúng số batch FULL; Incremental kế tiếp chọn lại `2018-01` |
| – | Chạy riêng block `dbt_build` (`mage run … --block-uuid dbt_build`) sau 1 lần `SUCCESS` | `StaleRunError` "run_id 13 đã SUCCESS…", dbt không chạy, lần chạy 13 giữ `SUCCESS` |
| 11 | Batch `2018-02` có 1 dòng thanh toán `payment_type = pix` (phương thức kho chưa biết) | Mage nạp bình thường (đúng kiểu); dbt `PASS=176 ERROR=1` – test `accepted_values` của `stg_order_payments.payment_type` FAIL 1. Lần chạy `FAILED`, `error_message` nêu tên test + bảng `dq` (chứa đúng 1 dòng `pix`); LSET giữ `2018-02-01` |
| 14 | Ngay sau đó `rerun_last = true` | Bị chặn: "Staging đã có batch 2018-02 (run_id 14 chưa xong…)" |
| – | Chạy bình thường với file đúng | Tự nạp lại `2018-02`: `order_payments` 0 INSERT / 1 UPDATE (`pix` → `credit_card`), bảng khác 0 / 0; dbt `PASS=177`; `SUCCESS` |
| – | Nạp tiếp tới `2018-09+`, so 9 bảng `dds` với kết quả kịch bản 10 | 7/7 `SUCCESS`, `PASS=177`. Mã md5 toàn bộ nội dung cả 9 bảng (kể cả khóa thay thế) **giống hệt** kịch bản 10: lỗi giữa chừng rồi chạy lại không làm lệch kho |

## Ghi log

| Bảng | 1 dòng = | Cột chính |
|------|----------|-----------|
| `etl_log.pipeline_run` | 1 lần chạy | `run_id`, `pipeline_name`, `load_type`, `batch_id`, `lset`, `cet`, `started_at`, `finished_at`, `status` (`RUNNING` → `SUCCESS` / `FAILED`), `error_message` |
| `etl_log.table_load` | 1 bảng trong 1 lần chạy | `rows_source`, `rows_inserted`, `rows_updated`, `rows_rejected`, `rows_deleted`, `status`, `error_message` |
| `etl_log.quality_check` | 1 phép kiểm tra trên 1 bảng | `check_name`, `failed_rows`, `status` (`PASS` / `WARN` / `FAIL`), `detail` |
| `etl_log.dbt_result` | 1 node dbt (seed / model / test) trong 1 lần chạy | `resource_type`, `node_name`, `relation_name`, `status` (chữ của dbt: `success` / `pass` / `warn` / `fail` / `error` / `skipped`), `rows_affected`, `failures`, `execution_time`, `message` |
| `dq.rejected_rows` | 1 dòng bị loại | `source_row`, `row_data` (JSONB), `reason` |

- `RUNNING` được ghi **trước** khi làm; lần chạy bị ngắt (tắt máy, container dừng) được lần chạy kế tiếp đổi thành `FAILED` – "Bị ngắt giữa chừng".
- `table_load` chỉ thành `SUCCESS` sau khi cả batch commit; batch lỗi thì bảng gây lỗi ghi lỗi thật, các bảng đã MERGE trước đó ghi "Đã hoàn tác (rollback)".
- Lỗi ở bước dbt: `table_load` vẫn `SUCCESS` (staging đã commit), `pipeline_run` `FAILED` với `error_message` dạng `dbt build lỗi (mã thoát 1): PASS=… ERROR=… SKIP=…` + vài node lỗi đầu tiên; test FAIL thì kèm tên bảng `dq` chứa dòng vi phạm.
- Block chỉ ghi cho lần chạy còn `RUNNING`. Bấm ▶ chạy riêng 1 block trong editor thì Mage đưa vào output **cũ** của block trước (`run_id` đã kết thúc, LSET cũ) → block dừng với lỗi `StaleRunError`, không ghi gì. Không chặn thì lần chạy cũ bị ghi đè `SUCCESS` → `FAILED`, LSET lùi và Incremental nhảy cóc batch. Muốn chạy lại thì chạy cả pipeline: **Run@once**, biến `rerun_last`.
- Đối soát: `rows_rejected` = số dòng `dq.rejected_rows` cùng `run_id` + bảng = tổng `failed_rows` của các phép cấp dòng.
- Câu truy vấn xem kết quả: [`sql/checks/01_pipeline_demo.sql`](../sql/checks/01_pipeline_demo.sql).

## Lưu ý khi lập lịch (Seminar 3)

> Kế hoạch đầy đủ (trigger nào, cài đặt, kịch bản kiểm thử): [docs/schedule_rules.md](../docs/schedule_rules.md).

- Cột `pipeline_run.triggered_by` lấy từ biến `triggered_by` (mặc định `manual`). Khi tạo trigger chạy theo lịch, thêm runtime variable `triggered_by = schedule` cho trigger đó để dashboard ETL phân biệt được lần chạy tay và lần chạy theo lịch.
- Pipeline không tự khóa chống chạy chồng: hai lần `incremental_load` chạy cùng lúc có thể cùng đọc một LSET. Khi lập lịch, để khoảng cách giữa các lần chạy dài hơn thời gian một lần chạy (~1 phút kể cả bước dbt – mục [Bước dbt](#bước-dbt-bs-34)) và không bấm Run@once trong lúc trigger đang chạy. Mỗi lần chạy mới cũng đổi mọi dòng còn `RUNNING` thành `FAILED`, nên chạy chồng sẽ làm sai trạng thái lần chạy kia.

## Chạy thử từ dòng lệnh (không cần mở giao diện)

```powershell
docker compose exec mage mage run /home/src/mage/olist_etl full_load
docker compose exec mage mage run /home/src/mage/olist_etl incremental_load
```
