# Quy tắc xây dựng pipeline Mage – Full Load, Incremental Load, kiểm tra chất lượng, ghi log, xóa đơn

> **Dành cho người làm BS-21 → BS-24.** Đọc **Phần A** để hiểu việc cần làm và một lần chạy diễn ra thế nào; mở **Phần B** khi bắt tay viết code; viết báo cáo (mục 6.1.2 → 6.1.6) theo **B10**.
> Quy tắc gom từ: [decisions.md](decisions.md) (D1–D8 + bảng cuối), [data/batches/README.md](../data/batches/README.md) (định dạng file batch), [`sql/init/`](../sql/init/) (bảng đích), [architecture.md](architecture.md) (vị trí của Mage trong hệ thống).
> Nếu thấy mâu thuẫn: `decisions.md` là gốc – báo nhóm để sửa file này.
> **[Bắt buộc]** = nhóm đã chốt, muốn làm khác phải bàn lại · **[Gợi ý]** = cách đề xuất, làm khác được nếu ra cùng kết quả.
> Cập nhật: 19/10/2026 · 24/10/2026: thêm **B12** – pipeline gọi dbt sau khi nạp staging (BS-34).

---

# Phần A – Nhiệm vụ

## A1. Pipeline Mage nằm ở đâu

Mage là khâu **Stage ETL** của kiến trúc Single DDS: lấy file batch, kiểm tra, nạp vào `staging`, ghi lại mọi chuyện đã xảy ra. Làm sạch / dựng `dds` là việc của dbt, **không** làm trong Mage – từ BS-34 Mage chỉ **gọi** dbt ở cuối mỗi lần chạy (B12).

```
data/batches/<batch>/*.csv ──► Mage ──► staging (8 bảng)         ──► dbt ──► dds
     + manifest.csv             │
                                ├──► etl_log  (nhật ký: lần chạy, từng bảng, từng phép kiểm tra)
                                └──► dq       (chính các dòng dữ liệu bị loại)
```

**Đã có sẵn – không phải làm:**

| Thứ | Ở đâu | Ghi chú |
|---|---|---|
| 10 batch + `manifest.csv` | `data/batches/` – sinh bằng `docker compose exec mage python scripts/split_batches.py` | Đã tự kiểm tra 9/9 PASS. Định dạng: [data/batches/README.md](../data/batches/README.md) |
| Bảng đích | `staging.*` (8 bảng), `etl_log.pipeline_run` / `table_load` / `quality_check`, `dq.rejected_rows` | Tạo bởi `sql/init/00` → `04`; kiểm tra bằng `sql/checks/00_check_init.sql` (19 dòng PASS) |
| Môi trường | Container `olist-mage` (Mage 0.9.79, pandas 1.5.3, psycopg2, sqlalchemy) | Trong container, repo nằm ở `/home/src` → batch ở `/home/src/data/batches/` |
| Project Mage | `mage/olist_etl/` (còn trống) | `io_config.yaml` profile `default` đã nối Postgres qua biến môi trường |

## A2. Bốn task và kết quả cần nộp

| Task | Làm gì | Kết quả nộp | Quy tắc |
|---|---|---|---|
| **BS-22 Full Load** | Pipeline `full_load`: nạp batch `FULL` (8 file) vào `staging` | Chạy 1 lần → `staging` có đúng số dòng của dòng `seq = 1` trong manifest | B2.1, B3, B4 |
| **BS-21 Kiểm tra chất lượng** | Bước kiểm tra **dùng chung** cho 2 pipeline: đủ file, đúng cột, khóa không rỗng / không trùng; tách dòng hỏng ra `dq` | Mỗi lần chạy có đủ dòng trong `etl_log.quality_check`; dòng hỏng nằm trong `dq.rejected_rows` | B4.2, B4.3 |
| **BS-24 Ghi log & xử lý lỗi** | Ghi `etl_log` ở **mọi** lần chạy; lỗi thì đánh dấu `FAILED` và không để batch bị tính là đã nạp | `etl_log` đủ 3 bảng; demo được 1 lần chạy lỗi rồi chạy lại thành công | B5, B2.4 |
| **BS-23 Incremental Load** | Pipeline `incremental_load`: mỗi lần chạy tự tìm batch kế tiếp bằng LSET / CET, nạp bằng MERGE; xử lý file xóa đơn | Chạy 9 lần nạp hết; chạy lại không sinh trùng; demo xóa đơn | B2.2–B2.4, B6 |

**Thứ tự nên làm [Gợi ý]:** BS-22 (dựng khung đơn giản nhất) → BS-21 (chèn bước kiểm tra) → BS-24 (ghi log – Incremental cần log để biết LSET) → BS-23 (dùng lại toàn bộ khung + thêm LSET / CET + xóa đơn).
Bốn task **dùng chung code**: viết một lần các hàm đọc file, kiểm tra, MERGE, ghi log (VD trong `mage/olist_etl/utils/`), hai pipeline cùng gọi.

## A3. Một lần chạy diễn ra thế nào – và ghi log lúc nào

Ví dụ lần chạy Incremental nạp batch `2018-01` (Full Load giống hệt, chỉ khác bước 1 và có thêm TRUNCATE – B2.1):

| # | Việc làm | Ghi vào `etl_log` / `dq` ngay lúc đó |
|---|---|---|
| 1 | **Tìm batch:** lấy LSET = `cet` của lần chạy `SUCCESS` gần nhất → tra `manifest.csv` dòng có `lset` = LSET → được `batch_id = 2018-01`, CET = `2018-02-01` | Chưa ghi gì (chỉ đọc) |
| 2 | **Bắt đầu lần chạy** | `pipeline_run`: INSERT 1 dòng `status = RUNNING`, `batch_id`, `lset`, `cet`, `started_at` → lấy `run_id` dùng cho mọi dòng log sau |
| 3 | **Kiểm tra cấp batch:** đủ 5 file chưa | `quality_check`: 1 dòng `file_exists`. Thiếu file → FAIL → nhảy tới bước 7 |
| 4 | **Từng bảng** theo thứ tự `customers` → `orders` → `order_items`, `order_payments` → `order_reviews` (B3): | |
| 4a | Đọc file | `table_load`: INSERT 1 dòng `status = RUNNING`, `rows_source` = số dòng đọc được |
| 4b | Kiểm tra cột, khóa | `quality_check`: 1 dòng / phép kiểm tra, **kể cả khi PASS** |
| 4c | Tách dòng hỏng | `dq.rejected_rows`: 1 dòng / dòng bị loại (sau khi đã có dòng `quality_check` tương ứng) |
| 4d | MERGE dòng sạch vào `staging` | `table_load`: UPDATE `rows_inserted`, `rows_updated`, `rows_rejected`, `status = SUCCESS`, `finished_at` |
| 5 | **Xóa mềm** nếu batch có `deleted_orders.csv` (B6) | `quality_check` + `dq` cho file xóa; `table_load` dòng `orders`: `rows_deleted` |
| 6 | **Kết thúc thành công** | `pipeline_run`: UPDATE `status = SUCCESS`, `finished_at` → `cet` của dòng này thành **LSET của lần sau** |
| 7 | **Lỗi ở bất kỳ bước nào** | `table_load` đang chạy (nếu có): `FAILED` + `error_message`; `pipeline_run`: `FAILED` + `error_message`, `finished_at`. LSET **không** đổi → lần sau nạp lại đúng batch này |

Vì sao ghi `RUNNING` **trước** khi làm: nếu pipeline chết giữa chừng (tắt máy, container dừng), dòng kẹt ở `RUNNING` là dấu vết cho biết có lần chạy dở dang (B2.4).

## A4. Khi nào coi là xong
Chạy được hết các kịch bản ở **B8** và số liệu khớp `manifest.csv`. Viết báo cáo mục 6.1.2 → 6.1.6 và chụp ảnh demo theo **B10**.

---

# Phần B – Quy tắc chi tiết

## B1. Đầu vào và đầu ra [Bắt buộc]

| | Nội dung |
|---|---|
| **Đầu vào** | `data/batches/<batch_id>/<bảng>.csv` + `data/batches/manifest.csv` + (tùy chọn) `deleted_orders.csv` trong thư mục batch. Định dạng: [data/batches/README.md](../data/batches/README.md) |
| **Đầu ra** | `staging.*` · `etl_log.pipeline_run`, `table_load`, `quality_check` · `dq.rejected_rows` |
| **Không đụng tới** | `dds` (dbt làm), file trong `data/raw/` |

`manifest.csv` có 10 dòng theo thứ tự chạy (`seq` 1 → 10). Cột dùng cho pipeline: `batch_id`, `load_type`, `lset`, `cet` (trống = không giới hạn: `FULL` không có `lset`, `2018-09+` không có `cet`), số dòng từng file, `orders_new`, `orders_resent`.

## B2. Hai pipeline

### B2.1 Full Load – `full_load` [Bắt buộc]
- Nạp batch `FULL` (`seq = 1`): 8 file. Ghi `pipeline_run` với `load_type = 'FULL'`, `batch_id = 'FULL'`, `lset = NULL`, `cet = '2018-01-01 00:00:00'`.
- **Mỗi lần chạy Full Load = làm lại từ đầu:** `TRUNCATE` cả 8 bảng `staging` rồi mới nạp `FULL`. **Không** xóa `etl_log`, `dq` (là lịch sử).
  Lý do: nếu chỉ MERGE `FULL` lên `staging` đã có các batch sau, đơn sẽ bị đưa về trạng thái cũ (VD đơn đã `delivered` ở batch `2018-02` bị trả về `shipped` như trong `FULL`).
- Sau một lần Full Load làm lại, Incremental tự chạy lại từ `2018-01` (vì lần SUCCESS gần nhất giờ là `FULL` – B2.2), và dbt phải chạy `dbt build --full-refresh` để dựng lại các model `incremental` (từ BS-34 block `dbt_build_full` tự chạy – B12).

### B2.2 Incremental Load – `incremental_load` [Bắt buộc]
Làm đúng 4 bước của Bài 4 (slide 49, control flow slide 67):

| Bước (bài giảng) | Làm gì |
|---|---|
| **Get LSET** – lấy từ metadata | `SELECT batch_id, cet FROM etl_log.pipeline_run WHERE status = 'SUCCESS' ORDER BY run_id DESC LIMIT 1`<br>• Không có dòng nào → **dừng**, báo "chưa chạy Full Load".<br>• `cet` IS NULL (lần gần nhất là `2018-09+`) → **dừng**, báo "đã nạp hết batch", không ghi `pipeline_run`.<br>• Còn lại: LSET = `cet` đó |
| **Set CET** – xác định khoảng nạp | Tra `manifest.csv` dòng có `lset` = LSET → lấy `batch_id` và CET = `cet` của dòng đó |
| **Extract + Load** | Nạp thư mục batch đó: 5 file (B3, B4) + xóa mềm nếu có `deleted_orders.csv` (B6) |
| **Set LSET** – ghi CET làm LSET mới | `pipeline_run` → `SUCCESS` (dòng này đã lưu `cet`, nên lần sau tự đọc ra làm LSET). Lỗi → `FAILED` → LSET giữ nguyên |

- Mỗi lần chạy nạp **đúng 1 batch**. Nạp hết = chạy 9 lần (Seminar 3 sẽ gắn trigger lịch).
- LSET / CET là **thời gian mô phỏng** = mốc cắt batch, không phải giờ chạy thật (chốt 17/10/2026). Giờ chạy thật ghi ở `started_at`, `finished_at`.

### B2.3 Chạy lại [Bắt buộc phần giới hạn, Gợi ý phần cách làm]
- Đề yêu cầu "cho phép chạy lại pipeline và kiểm tra kết quả". **Chỉ cho chạy lại batch của lần SUCCESS gần nhất** – an toàn vì MERGE theo khóa chính: không sinh trùng, ra 0 INSERT và 0 UPDATE nếu làm theo B4.4.
- **Không** chạy lại một batch cũ hơn khi đã nạp các batch sau: trạng thái đơn sẽ bị ghi đè bằng trạng thái cũ. Muốn quay về → chạy lại Full Load (B2.1) rồi Incremental từ đầu.
- [Gợi ý] Thêm biến pipeline `rerun_last` (mặc định `false`): `true` thì bỏ qua bước tìm batch, nạp lại `batch_id` của lần SUCCESS gần nhất, ghi một dòng `pipeline_run` mới với cùng `lset`, `cet`.

### B2.4 Xử lý lỗi [Bắt buộc]
- Lỗi ở đâu cũng phải kết thúc bằng `pipeline_run.status = 'FAILED'` + `error_message` (thông báo lỗi ngắn gọn) + `finished_at`.
- **LSET chỉ tiến khi SUCCESS.** Nạp lại một batch đã lỗi dở dang phải ra cùng kết quả cuối với nạp 1 lần trọn vẹn – MERGE theo khóa chính đảm bảo điều này. (Lưu ý: khi đó số `rows_inserted` của lần chạy lại sẽ nhỏ hơn manifest vì một phần đã vào ở lần lỗi – đúng, không phải lỗi.)
- Không chạy dbt khi lần chạy gần nhất là `FAILED` (staging có thể đang dở batch). Từ BS-34 dbt chỉ chạy trong cùng lần chạy, **sau khi** staging đã commit (B12).
- [Gợi ý] Đầu mỗi lần chạy: đổi các dòng `pipeline_run` còn `RUNNING` (lần chạy cũ bị ngắt) thành `FAILED` với `error_message = 'Bị ngắt giữa chừng'`.
- [Gợi ý] Gói mọi thay đổi `staging` của 1 batch trong **một transaction** (lỗi → ROLLBACK, staging như chưa chạy), còn `etl_log` / `dq` ghi bằng **kết nối riêng, autocommit** để lỗi vẫn còn log. Không bắt buộc vì quy tắc "LSET chỉ tiến khi SUCCESS + MERGE chạy lại được" đã đủ đúng; transaction chỉ giúp staging không dở dang trong lúc chờ chạy lại.

## B3. Thứ tự nạp bảng trong một batch [Bắt buộc] (D5)

```
(chỉ FULL:) products, sellers, category_translation
          → customers → orders → order_items, order_payments → order_reviews
          → (chỉ Incremental, nếu có file:) xóa mềm theo deleted_orders.csv
```
Bảng cha trước bảng con. Xóa mềm làm **sau cùng** để nếu đơn bị xóa cũng nằm trong `orders.csv` của batch đó thì việc xóa vẫn thắng.

| Bảng | Khóa chính (D1) – cột MERGE `ON` |
|---|---|
| `orders` | `order_id` |
| `order_items` | `order_id`, `order_item_id` |
| `order_payments` | `order_id`, `payment_sequential` |
| `order_reviews` | `review_id`, `order_id` |
| `customers` | `customer_id` |
| `sellers` / `products` / `category_translation` | `seller_id` / `product_id` / `product_category_name` |

## B4. Nạp một bảng

### B4.1 Đọc file [Bắt buộc]
- `pandas.read_csv(path, dtype=str, keep_default_na=False, na_values=[''])` – mọi cột đọc dạng **chuỗi** (giữ số 0 đầu của zip `01037`), **chỉ ô trống** mới thành NULL (tránh pandas tự biến chữ `NA` thành NULL).
- Dùng CSV parser chuẩn: bình luận review có xuống dòng **bên trong ô** – không đọc theo từng dòng.
- `rows_source` = số dòng dữ liệu (không tính tiêu đề).

### B4.2 Kiểm tra chất lượng – BS-21

Chạy **theo thứ tự**; phép sau chỉ xét các dòng còn lại sau phép trước. Mỗi phép ghi **1 dòng** `quality_check` (kể cả PASS), `failed_rows` = số dòng bị phép đó loại.

| `check_name` | Kiểm tra | Không đạt thì | `status` | |
|---|---|---|---|---|
| `file_exists` | Đủ file của batch (`FULL`: 8, còn lại: 5) – ghi với `table_name` = tên file thiếu | Dừng cả batch | `FAIL` | Bắt buộc |
| `columns_match` | Dòng tiêu đề đúng tên, đúng thứ tự cột như [README mục 4](../data/batches/README.md) (cột gốc + `batch_id`) | Dừng cả batch | `FAIL` | Bắt buộc |
| `batch_id_match` | Mọi dòng có `batch_id` = batch đang nạp | Dừng cả batch | `FAIL` | Bắt buộc |
| `not_null_key` | Cột khóa chính (B3) không rỗng | Loại dòng → `dq` | `WARN` | Bắt buộc |
| `duplicate_key` | Khóa không lặp lại trong file | Loại **mọi** dòng mang khóa trùng (không đoán dòng nào đúng) → `dq`. Lý do: MERGE báo lỗi nếu một khóa xuất hiện 2 lần trong nguồn | `WARN` | Bắt buộc |
| `type_cast` | Giá trị ép được sang kiểu của bảng staging (TIMESTAMP, DATE, NUMERIC, INT, SMALLINT) | Loại dòng → `dq` | `WARN` | Gợi ý |
| `row_count_match` | `rows_source` = số dòng ghi trong manifest | Vẫn nạp, ghi chú `detail` | `WARN` | Gợi ý |

- `status`: `PASS` = 0 dòng lỗi · `WARN` = có dòng bị loại nhưng bảng vẫn nạp · `FAIL` = dừng (ràng buộc `CHECK` trong `02_etl_log.sql` chỉ nhận 3 giá trị này).
- Dữ liệu Olist sạch về khóa (D1) nên chạy thật thường **toàn PASS**. Muốn demo WARN / FAIL: sửa **bản sao** của một file batch (xóa trống 1 ô khóa, xóa 1 cột) rồi chạy.

### B4.3 Lưu dòng bị loại vào `dq` [Bắt buộc]
- Ghi dòng `quality_check` **trước**, rồi mới ghi `dq.rejected_rows` – bảng này có khóa ngoại (`run_id`, `table_name`, `check_name`) → `etl_log.quality_check`, làm ngược sẽ bị chặn.
- Mỗi dòng bị loại ghi **1 lần**, theo phép kiểm tra đầu tiên nó không qua:

| Cột | Giá trị |
|---|---|
| `run_id`, `table_name`, `check_name` | Lần chạy, bảng, phép kiểm tra |
| `source_row` | Bản ghi thứ mấy trong file (1 = bản ghi đầu sau tiêu đề) |
| `row_data` | Nguyên dòng gốc dạng JSON `{"tên cột": "giá trị"}`, giá trị để dạng chuỗi như trong file |
| `reason` | Mô tả ngắn, VD `order_id rỗng` |

- Đối soát: `table_load.rows_rejected` = số dòng `dq.rejected_rows` cùng `run_id` + `table_name` = tổng `failed_rows` của các phép cấp dòng.

### B4.4 MERGE vào staging [Bắt buộc]
- Đưa dòng sạch vào **bảng tạm** (VD `CREATE TEMP TABLE tmp_<bảng>` toàn cột TEXT rồi `COPY ... FROM STDIN WITH CSV` qua psycopg2 – ô trống tự thành NULL), sau đó MERGE theo khóa chính, ép kiểu trong câu `USING`.
- **Không** dùng `WHEN NOT MATCHED BY SOURCE ... DELETE`: mỗi batch chỉ là một phần dữ liệu, dòng vắng mặt không có nghĩa là bị xóa (D4). Xóa đi đường riêng (B6).
- `batch_id` trong file → cột `_batch_id`; `_loaded_at = now()` – đặt cả khi INSERT lẫn UPDATE.
- **Không** cập nhật `_is_deleted`, `_deleted_at` trong MERGE: đơn đã xóa vẫn giữ trạng thái xóa dù batch sau gửi lại.
- [Khuyến nghị] Chỉ UPDATE khi dữ liệu **thật sự khác** (`IS DISTINCT FROM`): `rows_updated` = số dòng đổi thật, chạy lại batch → 0 / 0, dễ giải thích khi demo.
- Đếm INSERT / UPDATE bằng `RETURNING merge_action()` (PostgreSQL 17). Câu mẫu cho `orders` – **đã chạy thử trên Postgres của đồ án** (ra đúng 2 INSERT, chạy lại 0 / 0); bảng khác viết theo cùng khuôn:

```sql
WITH m AS (
  MERGE INTO staging.orders AS t
  USING (
    SELECT order_id, customer_id, order_status,
           order_purchase_timestamp::timestamp       AS order_purchase_timestamp,
           order_approved_at::timestamp              AS order_approved_at,
           order_delivered_carrier_date::timestamp   AS order_delivered_carrier_date,
           order_delivered_customer_date::timestamp  AS order_delivered_customer_date,
           order_estimated_delivery_date::date       AS order_estimated_delivery_date,  -- '2017-10-18 00:00:00' -> 2017-10-18
           batch_id                                  AS _batch_id
    FROM tmp_orders
  ) AS s
  ON t.order_id = s.order_id
  WHEN MATCHED AND (t.customer_id, t.order_status, t.order_purchase_timestamp, t.order_approved_at,
                    t.order_delivered_carrier_date, t.order_delivered_customer_date, t.order_estimated_delivery_date)
       IS DISTINCT FROM
                   (s.customer_id, s.order_status, s.order_purchase_timestamp, s.order_approved_at,
                    s.order_delivered_carrier_date, s.order_delivered_customer_date, s.order_estimated_delivery_date)
  THEN UPDATE SET customer_id = s.customer_id, order_status = s.order_status,
                  order_purchase_timestamp = s.order_purchase_timestamp, order_approved_at = s.order_approved_at,
                  order_delivered_carrier_date = s.order_delivered_carrier_date,
                  order_delivered_customer_date = s.order_delivered_customer_date,
                  order_estimated_delivery_date = s.order_estimated_delivery_date,
                  _batch_id = s._batch_id, _loaded_at = now()
  WHEN NOT MATCHED THEN
    INSERT (order_id, customer_id, order_status, order_purchase_timestamp, order_approved_at,
            order_delivered_carrier_date, order_delivered_customer_date, order_estimated_delivery_date, _batch_id)
    VALUES (s.order_id, s.customer_id, s.order_status, s.order_purchase_timestamp, s.order_approved_at,
            s.order_delivered_carrier_date, s.order_delivered_customer_date, s.order_estimated_delivery_date, s._batch_id)
  RETURNING merge_action() AS action
)
SELECT count(*) FILTER (WHERE action = 'INSERT') AS rows_inserted,
       count(*) FILTER (WHERE action = 'UPDATE') AS rows_updated
FROM m;
```

## B5. Ghi log – BS-24 [Bắt buộc]

Thời điểm ghi: xem bảng ở **A3**. Ý nghĩa từng cột:

| Bảng | Cột | Ghi gì |
|---|---|---|
| `pipeline_run` | `pipeline_name` | `full_load` / `incremental_load` (= tên pipeline Mage) |
| | `load_type` | `FULL` / `INCREMENTAL` |
| | `batch_id`, `lset`, `cet` | Lấy từ manifest. `FULL`: `lset` NULL; `2018-09+`: `cet` NULL |
| | `triggered_by` | `manual` (chạy tay) / `schedule` (trigger lịch – Seminar 3) |
| | `started_at`, `finished_at` | Giờ chạy thật (DB đã đặt giờ Việt Nam – `now()` là đủ) |
| | `status`, `error_message` | `RUNNING` → `SUCCESS` / `FAILED`; lỗi thì ghi thông báo ngắn |
| `table_load` | `rows_source` | Số dòng đọc từ file |
| | `rows_inserted`, `rows_updated` | Từ `merge_action()` (B4.4) |
| | `rows_rejected` | Số dòng bị loại (= số dòng `dq.rejected_rows` của bảng) |
| | `rows_deleted` | Chỉ dòng `orders`: số đơn bị đánh dấu xóa (B6); bảng khác = 0 |
| `quality_check` | `check_name`, `failed_rows`, `status`, `detail` | Mỗi phép kiểm tra 1 dòng (B4.2); `detail` VD `'thiếu cột price'` |

**Số liệu mong đợi** khi nạp lần đầu đúng thứ tự (đối chiếu với `manifest.csv`): `rows_source` = số dòng trong manifest; `orders`: `rows_inserted` = `orders_new`, `rows_updated` = `orders_resent`; bảng khác: `rows_inserted` = số dòng, `rows_updated` = 0; `rows_rejected` = 0, `rows_deleted` = 0 (dữ liệu sạch, không demo xóa).

## B6. Xóa đơn (soft delete) [Bắt buộc] – chốt 19/10/2026

Vì sao cần: Incremental chỉ thấy dòng **có mặt** trong batch nên không tự biết đơn nào bị xóa ở nguồn (Bài 4, slide 52–53). Nhóm chọn cách **nguồn báo xóa + kho xóa mềm**.

- **Đầu vào:** file tùy chọn `deleted_orders.csv` trong thư mục batch Incremental – cột `order_id`, `deleted_at` (`YYYY-MM-DD HH:MM:SS`, thời gian mô phỏng), `batch_id`. Không có file = batch không có đơn bị xóa. `split_batches.py` **không** sinh file này (Olist không có nghiệp vụ xóa – đơn hủy là đổi trạng thái `canceled`) → chỉ tạo tay khi demo. Ở batch `FULL` không xét.
- **Kiểm tra** (ghi `quality_check` / `dq` với `table_name = 'deleted_orders'`):

  | `check_name` | Kiểm tra | Không đạt |
  |---|---|---|
  | `columns_match` | Đúng 3 cột theo thứ tự trên | `FAIL` – dừng cả batch |
  | `not_null_key` | `order_id` không rỗng | `WARN` – loại dòng → `dq` |
  | `key_exists` | Đơn có trong `staging.orders` và **chưa** bị xóa | `WARN` – loại dòng → `dq` |
  | `in_window` | `LSET ≤ deleted_at < CET` (nguồn không thể báo xóa ở tương lai) | `WARN` – loại dòng → `dq` |

- **Xử lý** (sau khi MERGE xong mọi bảng của batch – B3): đưa các dòng hợp lệ vào bảng tạm `tmp_deleted_orders` rồi

  ```sql
  UPDATE staging.orders AS o
  SET _is_deleted = TRUE, _deleted_at = d.deleted_at::timestamp,
      _batch_id = d.batch_id, _loaded_at = now()
  FROM tmp_deleted_orders AS d
  WHERE o.order_id = d.order_id AND NOT o._is_deleted;   -- số dòng UPDATE -> table_load(orders).rows_deleted
  ```
  (đã chạy thử: lần 1 → 1 dòng, chạy lại → 0 dòng).
- **Không** xóa hẳn dòng, **không** đụng bảng con (`order_items`, `order_payments`, `order_reviews`, `customers`): dbt tự bỏ chúng qua `order_id` (R10 trong [source_to_target_mapping.md](source_to_target_mapping.md)).
- **Demo** (VD đã nạp tới `2018-02`):
  1. Chọn 1 đơn đã có: `SELECT order_id FROM staging.orders WHERE _batch_id = 'FULL' AND NOT _is_deleted LIMIT 1;`
  2. Tạo `data/batches/2018-03/deleted_orders.csv`:
     ```
     order_id,deleted_at,batch_id
     <order_id vừa chọn>,2018-03-10 09:00:00,2018-03
     ```
  3. Chạy Incremental → `table_load` dòng `orders`: `rows_deleted = 1`; trong `staging` dòng vẫn còn, `_is_deleted = TRUE`.
  4. Chạy dbt → đơn biến mất khỏi các fact và dashboard.
  - ⚠ Chạy lại `split_batches.py` sẽ **xóa file demo** (script dựng lại thư mục batch).
  - ⚠ Sau khi demo xóa, đối soát "staging khớp `data/raw/`" sau batch cuối sẽ lệch đúng số đơn đã xóa. Muốn sạch: chạy lại Full Load rồi Incremental từ đầu.

## B7. Gợi ý cấu trúc pipeline trong Mage [Gợi ý]

```
mage/olist_etl/
├── pipelines/
│   ├── full_load
│   │   ├── start_full_run     (data_loader)    đổi RUNNING cũ → FAILED; ghi pipeline_run RUNNING (batch FULL)
│   │   ├── load_batch         (data_exporter)  B4 cho 8 bảng theo thứ tự B3 (TRUNCATE trước), ghi table_load / quality_check / dq
│   │   └── finish_run         (callback)       success → SUCCESS · failure → FAILED + error_message
│   └── incremental_load
│       ├── get_lset_cet       (data_loader)    Get LSET (etl_log) + Set CET (manifest); ghi pipeline_run RUNNING
│       ├── load_batch         (data_exporter)  dùng chung code với full_load + xóa mềm (B6)
│       └── finish_run         (callback)       Set LSET = ghi SUCCESS
└── utils/                                      hàm dùng chung: đọc file, kiểm tra, MERGE, ghi log
```
- Đặt tên block theo các bước của slide 67 (**Set CET → Get LSET → Extract → Set LSET**) để khi demo nhìn là thấy khớp bài giảng.
- Giữa các block chỉ truyền thông tin nhỏ (`run_id`, `batch_id`, `lset`, `cet`); việc đọc – kiểm tra – MERGE từng bảng làm trong vòng lặp bên trong 1 block.
- Mage 0.9.79 có **callback block**: hàm gắn `@callback('success')` / `@callback('failure')`, lỗi được truyền vào `kwargs['__error']` – tiện để ghi `SUCCESS` / `FAILED`. Cách đơn giản hơn: `try / except` trong block, ghi `FAILED` rồi `raise` lại lỗi.
- Code trong `utils/` import theo tên project, VD `from olist_etl.utils.loader import merge_table` (thử lại trong Mage nếu báo lỗi import).
- Kết nối DB: dùng profile `default` trong `io_config.yaml` hoặc đọc thẳng biến môi trường `POSTGRES_*` (container đã có từ `.env`).

## B8. Kịch bản kiểm thử – tiêu chí hoàn thành

| # | Kịch bản | Kết quả mong đợi |
|---|---|---|
| 1 | Full Load lần đầu | `pipeline_run` SUCCESS; `table_load` khớp manifest `seq = 1`: `orders` 45.430 INSERT, `order_items` 51.234, `order_payments` 47.871, `order_reviews` 42.381, `customers` 45.430, `sellers` 3.095, `products` 32.951, `category_translation` 71; `quality_check` toàn PASS |
| 2 | Incremental lần 1 | Tự chọn `2018-01`; `orders` 7.269 INSERT + 2.456 UPDATE; `order_reviews` 6.272 INSERT; `order_items` 8.208; `order_payments` 7.563; `customers` 7.269 |
| 3 | Chạy lại batch vừa nạp (B2.3) | 0 INSERT, 0 UPDATE ở mọi bảng; LSET không đổi |
| 4 | Lỗi: sửa bản sao 1 file batch cho thiếu cột rồi chạy | `quality_check` `columns_match` FAIL; `pipeline_run` FAILED; LSET không đổi. Trả file về → chạy lại → nạp đúng batch đó |
| 5 | Dòng hỏng: để trống 1 ô khóa | `not_null_key` WARN, `failed_rows = 1`; 1 dòng `dq.rejected_rows`; `rows_rejected = 1`; bảng vẫn nạp |
| 6 | Xóa đơn (B6) | `rows_deleted = 1`; dòng còn trong staging với `_is_deleted = TRUE` |
| 7 | Chạy hết 10 batch | Số dòng staging: `orders` 99.441 · `order_items` 112.650 · `order_payments` 103.886 · `order_reviews` 99.224 · `customers` 99.441 · `sellers` 3.095 · `products` 32.951 · `category_translation` 71 (khớp `data/raw/`, D8) |
| 8 | Incremental khi đã nạp hết | Dừng, báo "đã nạp hết batch"; không ghi `pipeline_run` |
| 9 | Full Load làm lại sau khi đã chạy vài batch | Staging chỉ còn dữ liệu `FULL`; Incremental kế tiếp chọn lại `2018-01` |

## B9. Đối chiếu bài giảng (Bài 4 – ETL)

| Slide | Nội dung | Đồ án |
|---|---|---|
| 46–47 | Incremental extract dựa vào cột thời gian đáng tin | `order_purchase_timestamp` – không NULL ở mọi đơn (D4) |
| 48–49, 64–67 | LSET / CET lưu ở metadata, 4 bước Get LSET → Set CET → Extract → Set LSET | B2.2; metadata = `etl_log.pipeline_run` |
| 50 | Dữ liệu đến muộn | Đơn cũ có mốc mới được gửi lại ở batch sau (phương án B, D8) – không cần lùi LSET |
| 51 | Dùng ID tăng dần (LSEI) | Không dùng được: `order_id` là mã hash |
| 52 | Chịu lỗi: không sót, không trùng | LSET chỉ tiến khi SUCCESS + MERGE theo khóa chính (B2.4) |
| 53 | Xử lý xóa | Soft delete theo file `deleted_orders.csv` (B6) |
| 61 | Stage giữ cấu trúc như nguồn; nên **không** đặt ràng buộc để bắt được "bad data" | Giữ cấu trúc như CSV. Staging **có** khóa chính vì MERGE cần khóa duy nhất; "bad data" không bị mất vì đã chặn và **lưu ở `dq`** trước khi vào staging |
| 62–63 | 3 cách tổ chức bảng stage | Cách 1: giữ dữ liệu các lần trước trong cùng bảng, có cột thời điểm nạp (`_loaded_at`, `_batch_id`) |
| 68–69 | Data firewall, DQ database | Bước kiểm tra B4.2 (trước staging) + dbt test (sau biến đổi); dòng lỗi lưu ở `dq` |

## B10. Gợi ý viết báo cáo – mục 6.1.2 → 6.1.6 [Gợi ý]

Mục lục phần Yến trong báo cáo:

```
6.1.2. Pipeline Full Load
6.1.3. Pipeline Incremental Load
6.1.4. Kiểm tra cấu trúc và chất lượng dữ liệu đầu vào
6.1.5. Ghi nhận trạng thái thực thi (ETL Log)
6.1.6. Kịch bản demo
   6.1.6.1 → 6.1.6.8 (B10.3)
```

### B10.1 Nguyên tắc chung
- **6.1.2 – 6.1.5 viết thiết kế + cách làm**, **6.1.6 chứa bằng chứng chạy** (ảnh). Cuối mỗi mục 6.1.2 – 6.1.5 chỉ dẫn "kết quả chạy: mục 6.1.6.x", không lặp ảnh.
- Mỗi quyết định kèm **lý do** (lấy từ cột *Lý do* trong [decisions.md](decisions.md) hoặc các đoạn "Lý do" trong file này) – cô hay hỏi "sao làm vậy" hơn là "làm gì".
- Gắn với bài giảng: dùng đúng thuật ngữ LSET / CET, data firewall, Control + Audit, DQ database; bảng đối chiếu slide **B9** đưa được thẳng vào báo cáo.
- Nói rõ batch là **dữ liệu mô phỏng** từ bộ Olist tĩnh (D8) – cách chia batch thuộc phần khác của báo cáo, ở đây chỉ dẫn lại.
- **Không dán code dài**: trích đoạn ngắn (câu Get LSET, khung câu MERGE), code đầy đủ nằm trong repo `mage/olist_etl/`.
- Số liệu lấy từ `manifest.csv` / B8, ghi đúng tên bảng, tên cột như trong database.

### B10.2 Mục 6.1.2 – 6.1.5 viết gì

| Mục | Ý chính (theo thứ tự nên viết) | Hình / bảng nên có | Lấy từ |
|---|---|---|---|
| **6.1.2 Pipeline Full Load** | (1) Mục đích: nạp lần đầu batch `FULL` (8 file, lịch sử đến hết 2017) vào `staging` · (2) Các block trong Mage và việc của từng block · (3) Quy trình: ghi `RUNNING` → TRUNCATE → kiểm tra → nạp 8 bảng → `SUCCESS` / `FAILED` · (4) Vì sao TRUNCATE (chạy lại Full Load sau các batch Incremental sẽ đưa đơn về trạng thái cũ) và vì sao **không** xóa `etl_log`, `dq` · (5) Thứ tự nạp cha → con · (6) Vì sao vẫn dùng MERGE khi kho trống (dùng chung code với Incremental) | Hình: cây block pipeline trong Mage · Bảng: thứ tự nạp + khóa chính từng bảng | A3, B2.1, B3 |
| **6.1.3 Pipeline Incremental Load** | (1) Cột watermark `order_purchase_timestamp` và khoảng nửa mở `[LSET, CET)` · (2) **4 bước Get LSET → Set CET → Extract + Load → Set LSET** (slide 49, 67), kèm câu SQL Get LSET; LSET lưu ở `etl_log.pipeline_run` · (3) MERGE: chưa có thì INSERT, khác thật thì UPDATE (`IS DISTINCT FROM`), dòng vắng mặt giữ nguyên; đếm bằng `RETURNING merge_action()` · (4) Vì sao có UPDATE (đơn cũ được gửi lại – phương án B) · (5) Chạy lại: chỉ batch gần nhất, ra 0 / 0 (idempotent) · (6) Xử lý lỗi: LSET chỉ tiến khi SUCCESS · (7) **Tiểu mục xử lý đơn bị xóa ở nguồn**: vì sao Incremental không tự biết (slide 52–53), file `deleted_orders.csv`, xóa mềm, dbt lọc ở `stg_` | Hình: sơ đồ 4 bước LSET / CET (vẽ theo slide 67) · Bảng: chuỗi LSET → CET qua các batch (có 1 lần FAILED) · Đoạn trích khung câu MERGE | B2.2 – B2.4, B4.4, B6, D4, D8 |
| **6.1.4 Kiểm tra cấu trúc và chất lượng dữ liệu đầu vào** | (1) Vị trí: **data firewall** trước `staging` (slide 68–69) · (2) 7 phép kiểm tra, mức `FAIL` (dừng batch) / `WARN` (loại dòng) / `PASS` · (3) Quy tắc: chạy theo thứ tự, mỗi dòng lỗi ghi 1 lần, trùng khóa thì loại mọi dòng mang khóa đó (lý do) · (4) DQ database: `dq.rejected_rows` giữ nguyên dòng lỗi + lý do; ghi `quality_check` trước rồi mới ghi `dq` · (5) Đối soát `rows_rejected` = số dòng `dq` = tổng `failed_rows` · (6) Khác dbt test chỗ nào | Bảng: 7 phép kiểm tra · Bảng: cấu trúc `dq.rejected_rows` | B4.1 – B4.3, [architecture.md](architecture.md) mục 3.3 – 4 |
| **6.1.5 Ghi nhận trạng thái thực thi (ETL Log)** | (1) Vai trò **Control + Audit**: Audit = xem lại lần chạy (dashboard ETL ở Seminar 3), Control = Incremental đọc log để chọn batch · (2) 3 bảng `pipeline_run` → `table_load` → `quality_check`, nối bằng `run_id`; ý nghĩa từng cột · (3) **Ghi lúc nào**: ghi dần trong lúc chạy, `RUNNING` trước để lần chạy bị ngắt vẫn để lại dấu vết · (4) Xử lý lỗi: `FAILED` + `error_message`, không chạy dbt khi lần gần nhất `FAILED` · (5) Số liệu mong đợi đối chiếu với `manifest.csv` | Hình: sơ đồ quan hệ 3 bảng `etl_log` + `dq.rejected_rows` (ER diagram của DBeaver là đủ) · Bảng: "một lần chạy – ghi gì lúc nào" (A3) | A3, B2.4, B5, `sql/init/02_etl_log.sql`, `03_dq.sql` |

### B10.3 Mục 6.1.6 – thứ tự demo
Mỗi kịch bản B8 = 1 mục con. Xếp để chạy **liên tục** được; 2 kịch bản làm hỏng dữ liệu (6.1.6.7, 6.1.6.8) để **cuối** vì làm lệch đối soát với `data/raw/`.

| Mục | Kịch bản | KB (B8) | Trạng thái trước khi chạy |
|---|---|---|---|
| 6.1.6.1 | Full Load lần đầu | 1 | `staging` trống, `etl_log` trống |
| 6.1.6.2 | Incremental Load nạp batch kế tiếp | 2 | Đã Full Load |
| 6.1.6.3 | Chạy lại batch vừa nạp | 3 | Đã nạp `2018-01` |
| 6.1.6.4 | Batch lỗi cấu trúc và chạy lại | 4 | Đã nạp `2018-01`; làm hỏng 1 file của `2018-02` |
| 6.1.6.5 | Nạp hết các batch và đối soát dữ liệu gốc | 7, 8 | Đã nạp `2018-02` |
| 6.1.6.6 | Chạy lại Full Load từ đầu | 9 | Đã nạp hết 10 batch |
| 6.1.6.7 | Loại dòng dữ liệu hỏng vào DQ database | 5 | Vừa Full Load lại; làm trống 1 khóa trong `2018-01/order_payments.csv` |
| 6.1.6.8 | Xóa đơn hàng ở nguồn (xóa mềm) | 6 | Đã nạp `2018-01`; thêm `2018-02/deleted_orders.csv` |

Mỗi mục con viết cùng khuôn: **Mục đích → Chuẩn bị (ảnh setup) → Thao tác → Kết quả mong đợi → Kết quả thực tế (ảnh kết quả) → Nhận xét**. Mở đầu 6.1.6 đặt 1 bảng tổng hợp: kịch bản / kết quả mong đợi / kết quả thực tế / đạt.

### B10.4 Câu truy vấn dùng chung để chụp kết quả

```sql
-- Q1. Các lần chạy
SELECT run_id, pipeline_name, batch_id, lset, cet, status, error_message, started_at, finished_at
FROM etl_log.pipeline_run ORDER BY run_id;

-- Q2. Từng bảng của 1 lần chạy
SELECT table_name, rows_source, rows_inserted, rows_updated, rows_rejected, rows_deleted, status
FROM etl_log.table_load WHERE run_id = :run_id ORDER BY started_at;

-- Q3. Các phép kiểm tra của 1 lần chạy
SELECT table_name, check_name, failed_rows, status, detail
FROM etl_log.quality_check WHERE run_id = :run_id ORDER BY checked_at;

-- Q4. Dòng bị loại của 1 lần chạy
SELECT table_name, check_name, source_row, row_data, reason
FROM dq.rejected_rows WHERE run_id = :run_id;

-- Q5. Số dòng staging
SELECT 'orders' AS bang, count(*) FROM staging.orders
UNION ALL SELECT 'order_items', count(*) FROM staging.order_items
UNION ALL SELECT 'order_payments', count(*) FROM staging.order_payments
UNION ALL SELECT 'order_reviews', count(*) FROM staging.order_reviews
UNION ALL SELECT 'customers', count(*) FROM staging.customers
UNION ALL SELECT 'sellers', count(*) FROM staging.sellers
UNION ALL SELECT 'products', count(*) FROM staging.products
UNION ALL SELECT 'category_translation', count(*) FROM staging.category_translation;
```

### B10.5 Ảnh cần chụp cho từng mục 6.1.6.x

| Mục | Ảnh setup (trước khi chạy) | Ảnh kết quả (sau khi chạy) |
|---|---|---|
| 6.1.6.1 | (1) Cây block pipeline `full_load` trong Mage · (2) thư mục `data/batches/FULL/` đủ 8 file · (3) Q5 ra toàn 0 | (1) Mage báo chạy thành công · (2) Q1: 1 dòng `FULL` SUCCESS · (3) Q2 đặt cạnh dòng `seq = 1` của `manifest.csv` · (4) Q3 toàn PASS |
| 6.1.6.2 | (1) Q1: lần SUCCESS gần nhất `FULL`, `cet = 2018-01-01` · (2) dòng `seq = 2` của manifest | (1) Q1: dòng mới `2018-01`, `lset 2018-01-01`, `cet 2018-02-01` · (2) Q2: `orders` 7.269 INSERT + 2.456 UPDATE |
| 6.1.6.3 | Biến `rerun_last = true` trong Mage (hoặc cách chạy lại nhóm chọn) | (1) Q1: 2 dòng `2018-01` cùng `lset`, `cet` · (2) Q2 của lần chạy lại: mọi bảng 0 / 0 |
| 6.1.6.4 | (1) Sao lưu file gốc · (2) tiêu đề file `2018-02/order_payments.csv` đã xóa 1 cột | Lần lỗi: (1) Mage báo lỗi · (2) Q3: `columns_match` FAIL · (3) Q1: `2018-02` FAILED + `error_message`. Trả file về, chạy lại: (4) Q1: `2018-02` SUCCESS ngay sau dòng FAILED |
| 6.1.6.5 | Q1 trước khi chạy các batch còn lại | (1) Q1: đủ 10 batch SUCCESS, `cet` của `2018-09+` trống · (2) Q5 đặt cạnh số dòng `data/raw/` (B8 KB7) · (3) chạy thêm 1 lần: Mage báo "đã nạp hết batch", Q1 không thêm dòng |
| 6.1.6.6 | Q5 khi đang có đủ 10 batch | (1) Q5 = số dòng `FULL` · (2) Q1: dòng `full_load` mới SUCCESS · (3) chạy Incremental: Q1 chọn lại `2018-01` |
| 6.1.6.7 | Dòng trong `2018-01/order_payments.csv` có `order_id` để trống | (1) Q3: `not_null_key` WARN, `failed_rows = 1` · (2) Q4: dòng bị loại kèm `row_data`, `reason` · (3) Q2: `order_payments` `rows_rejected = 1`, status SUCCESS |
| 6.1.6.8 | (1) Câu chọn 1 đơn đã có (B6) · (2) nội dung `2018-02/deleted_orders.csv` | (1) Q2: `orders` `rows_deleted = 1` · (2) `SELECT order_id, _is_deleted, _deleted_at, _batch_id FROM staging.orders WHERE order_id = '...'` · (3) khi đã có dbt: đơn không còn trong `dds.fact_sales` |

- Làm trống khóa ở **`order_payments`** (6.1.6.7) vì bảng này không có bảng con; làm trống `order_id` trong `orders.csv` sẽ khiến dòng con thành mồ côi, dbt test báo lỗi lan sang chỗ khác.
- 6.1.6.4 và 6.1.6.7 sửa trực tiếp file trong thư mục batch: **sao lưu trước**, demo xong chép lại hoặc chạy lại `split_batches.py` (cũng xóa luôn `deleted_orders.csv` của 6.1.6.8).
- Ảnh chụp từ DBeaver (lưới kết quả) và giao diện Mage; nên thấy được `run_id` và thời gian để người đọc nối các ảnh với nhau. Đặt tên ảnh theo mục, VD `6.1.6.4_setup.png`, `6.1.6.4_ketqua_1.png`.
- Sau 6.1.6.7 / 6.1.6.8 muốn có dữ liệu sạch lại: chạy lại Full Load rồi Incremental từ đầu.

---

## B11. Ghi chú khi triển khai (21/10/2026)

> Pipeline đã làm xong theo các quy tắc trên. Bảng dưới ghi những chỗ **code thực tế khác hoặc cụ thể hơn** phần quy tắc, để đọc file này không bị lệch với code. Mô tả code đầy đủ: [mage/README.md](../mage/README.md).

| Mục | Quy tắc ghi | Code thực tế | Vì sao |
|---|---|---|---|
| B7 – tên block `full_load` | `start_full_run` → `load_batch` → `finish_run` | `start_full_run` → `load_full_batch` → `finish_full_run` | Tên block trong Mage là duy nhất trong cả project; tách tên để không trùng với block của `incremental_load` |
| B7 – tên block `incremental_load` | `get_lset_cet` → `load_batch` → `finish_run` | `get_lset` → `set_cet` → `extract_load` → `set_lset` | Mỗi block đúng 1 bước của slide 67, khi demo nhìn là thấy khớp bài giảng. Lần chạy `RUNNING` được ghi ở `set_cet` (sau khi đã biết batch) |
| B7 – callback | Gợi ý `@callback` hoặc `try / except` | `try / except` trong `utils/runner.py`: lỗi thì ghi `FAILED` rồi báo lỗi lại cho Mage | Đơn giản, chạy giống nhau khi chạy bằng giao diện hay dòng lệnh |
| B2.2 – chưa có lần SUCCESS | Dừng, báo "chưa chạy Full Load" | Báo lỗi (block `get_lset` màu đỏ), không ghi `pipeline_run` | Đây là thao tác sai nên cho hiện lỗi rõ; trường hợp "đã nạp hết batch" thì dừng êm, không báo lỗi |
| B2.4 – chạy lại sau lỗi | `rows_inserted` của lần chạy lại có thể nhỏ hơn manifest | Ra **đúng** số manifest | Đã làm phần [Gợi ý] transaction: cả batch là 1 transaction, lỗi thì hoàn tác toàn bộ (kể cả TRUNCATE của Full Load) |
| B4.2 – `failed_rows` | Số dòng bị phép đó loại | `columns_match`, `row_count_match`, `file_exists` ghi `failed_rows = 0` (`row_count_match` ghi độ lệch trong `detail`); `batch_id_match` ghi số dòng sai batch | Giữ đúng phép đối soát B4.3: tổng `failed_rows` = số dòng trong `dq` |
| B4.2 – `type_cast` | Ép được sang kiểu staging | Dùng `pg_input_is_valid()` của PostgreSQL 17 theo kiểu đọc từ bảng staging; **kiểm thêm** cột `NOT NULL` ngoài khóa (VD `orders.customer_id`) | Kiểm giống hệt lúc MERGE; dòng trống ở cột bắt buộc sẽ làm MERGE lỗi cả batch nếu không loại trước |
| B4.2 – file không đọc được | Không nhắc | Ghi `columns_match` FAIL với `detail` "Không đọc được file: …" | Coi là lỗi cấu trúc file |
| B4.2 – `file_exists` | Ghi với `table_name` = tên file thiếu | Ghi 1 dòng cho **mọi** file của batch (PASS hoặc FAIL) | Thống nhất "mỗi phép 1 dòng, kể cả khi PASS" |
| B5 – `table_load.status` | `SUCCESS` sau khi MERGE xong bảng | Để `RUNNING` tới khi cả batch commit rồi mới `SUCCESS`; lỗi thì bảng gây lỗi ghi lỗi thật, các bảng đã MERGE ghi "Đã hoàn tác (rollback) vì lần chạy bị lỗi ở bước sau" | Vì có transaction, trước lúc commit dữ liệu vẫn có thể bị hoàn tác |
| B10.3 – kịch bản 6.1.6.7, 6.1.6.8 | Sửa file batch `2018-01` / `2018-02` | Đã chạy trên `2018-02/order_payments.csv` và `2018-03/deleted_orders.csv` | Kịch bản 6.1.6.6 đã nạp lại `2018-01`, nên dùng batch kế tiếp để chạy liên tục được, không phải chạy lại |
| B10.5 – ảnh | Chụp DBeaver + Mage | Ảnh Mage ở `docs/images/pipeline_demo/`; kết quả truy vấn đưa vào báo cáo dạng bảng Word (số lấy thẳng từ `etl_log`) | Bảng dễ đọc hơn ảnh chụp lưới DBeaver |

Kết quả 9 kịch bản B8: đều đạt (chi tiết số liệu trong báo cáo mục 6.1.6). Chạy thử nhanh không cần giao diện: `docker compose exec mage mage run /home/src/mage/olist_etl full_load` (thay `incremental_load` cho Incremental).

## B12. Bước dbt trong pipeline – BS-34 (24/10/2026)

> Ngay sau khi `staging` commit, pipeline gọi `dbt build` dựng `dds`; dbt xong mới ghi `SUCCESS`. Code: `mage/olist_etl/utils/dbt_runner.py`.
> Mô tả + kết quả kiểm thử: [mage/README.md](../mage/README.md) mục Bước dbt · lý do chọn cách làm: bảng cuối [decisions.md](decisions.md) (24/10/2026).

| # | Quy tắc | Vì sao |
|---|---|---|
| 1 | Thứ tự: `full_load` = `start_full_run` → `load_full_batch` → **`dbt_build_full`** → `finish_full_run`; `incremental_load` = `get_lset` → `set_cet` → `extract_load` → **`dbt_build`** → `set_lset` | Giống mẫu cô demo: nạp stage → dbt → chốt watermark. So với slide 67: thêm bước Transform giữa Extract + Load và Set LSET |
| 2 | Full Load chạy `dbt build --full-refresh`; Incremental chạy `dbt build` | B2.1: staging làm lại từ đầu thì 2 dimension incremental (`dim_customer`, `dim_geography`) cũng dựng lại, khóa cấp lại từ 1 |
| 3 | dbt lỗi (model lỗi, test FAIL, dbt không chạy được) → `pipeline_run` `FAILED` + `error_message`, **không** ghi `SUCCESS` → LSET không tiến | `SUCCESS` nghĩa là batch đã vào tới `dds`: không có chuyện log báo xong mà dashboard thiếu batch |
| 4 | Staging **không** hoàn tác khi dbt lỗi (đã commit ở bước trước); `table_load` giữ `SUCCESS` | dbt dùng kết nối riêng nên chỉ thấy dữ liệu đã commit. MERGE chạy lại được: lần sau nạp lại đúng batch đó ra 0 INSERT / 0 UPDATE rồi chạy dbt lại |
| 5 | Full Load lỗi ở bước dbt (hoặc bị ngắt sau khi staging commit) → `incremental_load` báo lỗi, phải chạy lại `full_load` | Staging đã bị TRUNCATE + nạp `FULL` nhưng lần SUCCESS gần nhất vẫn là lần cũ → LSET cũ làm Incremental nạp nhảy cóc, mất các tháng ở giữa |
| 6 | Incremental lỗi ở bước dbt rồi chạy `rerun_last = true` → báo lỗi, phải chạy bình thường | Staging đã có batch mới hơn batch của lần SUCCESS: nạp lại batch cũ đè lên đưa đơn về trạng thái cũ (B2.3) |
| 7 | Mỗi lần chạy ghi kết quả từng node dbt vào `etl_log.dbt_result` (`sql/init/05_dbt_log.sql`) | Control + Audit phủ cả 2 khâu ETL của Single DDS; dashboard ETL ở Seminar 3 vẽ được kết quả dbt theo batch |
| 8 | Không gõ `dbt` tay trong lúc pipeline đang chạy | Hai lần dbt cùng dựng `dds` và cùng ghi `dbt/target/` |

Kịch bản kiểm thử bổ sung cho B8 (kết quả: [mage/README.md](../mage/README.md) mục Bước dbt):

| # | Kịch bản | Kết quả mong đợi |
|---|---|---|
| 10 | Full Load + 9 Incremental (có bước dbt) trên DB trống | Lần nào cũng `SUCCESS`, 177 node dbt đạt; số dòng 3 fact sau từng batch khớp [dbt/README.md](../dbt/README.md) mục 4 (kịch bản 3) |
| 11 | dbt test FAIL ở 1 batch Incremental | `FAILED`, LSET không đổi, `error_message` nêu tên test + bảng `dq` chứa dòng vi phạm. Sửa dữ liệu → chạy lại → `SUCCESS` đúng batch đó |
| 12 | dbt không chạy được (VD không tìm thấy `profiles.yml`) | `FAILED`, `error_message` = mấy dòng cuối log dbt; `dbt_result` không có dòng nào |
| 13 | Full Load lỗi ở bước dbt rồi chạy Incremental | Bị chặn, báo chạy lại `full_load`. Chạy lại `full_load` → Incremental nạp lại từ `2018-01` |
| 14 | Incremental lỗi ở bước dbt rồi chạy `rerun_last = true` | Bị chặn. Chạy bình thường → nạp lại đúng batch đó |
