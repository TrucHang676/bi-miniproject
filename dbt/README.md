# dbt – Data Transformation

> Project dbt `olist_dw`: biến đổi schema `staging` (Mage nạp) thành kho `dds` (Galaxy schema) cho Power BI.
> Công thức từng cột: [docs/source_to_target_mapping.md](../docs/source_to_target_mapping.md) · thiết kế kho: [docs/dw_design.md](../docs/dw_design.md).
> **Quy tắc, mẫu code, số liệu nghiệm thu cho người viết model: [docs/dbt_rules.md](../docs/dbt_rules.md).**
> Khởi tạo 23/10/2026: cấu hình, kết nối, nguồn, seed. Model BS-28 → BS-31 làm xong 24/10/2026: 20 model, 155 test (mục 4 – 6); đã chạy đủ 6 kịch bản kiểm thử B7 (mục 4). Từ 24/10/2026 (BS-34) pipeline Mage tự gọi `dbt build` sau mỗi lần nạp (mục 1).
> Đối soát số liệu kho `dds` sau khi chạy: [sql/checks/02_dds_checks.sql](../sql/checks/02_dds_checks.sql) · xem test đang lỗi, demo test FAIL, kiểm khóa giữa 2 lần build: [sql/checks/03_dbt_test_demo.sql](../sql/checks/03_dbt_test_demo.sql).

## 1. Chạy dbt

dbt nằm sẵn trong container Mage (dbt-core 1.8.7, dbt-postgres 1.8.2). `compose.yaml` đặt `DBT_PROJECT_DIR` = `DBT_PROFILES_DIR` = `/home/src/dbt`, nên ở thư mục gốc repo chỉ cần gõ `docker compose exec mage dbt <lệnh>`.

**Lần đầu trên mỗi máy** (sau `git pull`):

```powershell
Copy-Item dbt\profiles.yml.example dbt\profiles.yml   # kết nối DB: đọc POSTGRES_* từ .env, không chứa mật khẩu
docker compose up -d                                   # tạo lại container Mage để nhận 2 biến DBT_* trong compose.yaml
docker compose exec mage dbt deps                      # cài dbt_utils đúng bản ghi trong package-lock.yml
docker compose exec mage dbt debug                     # phải ra: All checks passed!
```

**Khi nạp dữ liệu không cần gõ lệnh dbt**: từ 24/10/2026 (BS-34) pipeline Mage tự chạy `dbt build` ngay sau khi nạp `staging` – `full_load` chạy `dbt build --full-refresh`, mỗi lần `incremental_load` chạy `dbt build`; dbt lỗi thì lần chạy `FAILED`, LSET không tiến; kết quả từng node ghi vào `etl_log.dbt_result` ([mage/README.md](../mage/README.md) mục Bước dbt). Vì vậy 4 lệnh "lần đầu" ở trên phải làm **trước** khi chạy pipeline Mage.
Các lệnh dưới đây dùng khi sửa model / gỡ lỗi (không chạy trong lúc pipeline Mage đang chạy); `staging` phải có dữ liệu trước khi build.

| Muốn… | `docker compose exec mage …` |
|---|---|
| Dựng tất cả đúng thứ tự: seed → model → test | `dbt build` |
| 1 model và test của nó | `dbt build --select stg_orders` |
| 1 model và mọi model phía sau nó | `dbt build --select stg_orders+` |
| Chỉ test dữ liệu nguồn | `dbt test --select source:staging` |
| Sau khi chạy lại Full Load (staging làm lại từ đầu) | `dbt build --full-refresh` – dựng lại cả model `incremental` |
| Tài liệu + sơ đồ lineage (mục 7) | `dbt docs generate --static` → mở `dbt/target/static_index.html` bằng trình duyệt |

## 2. Cấu trúc và schema đích

| Thư mục | Tiền tố | Materialization | Schema | Nội dung |
|---|---|---|---|---|
| `models/staging/` | `stg_` | view | `dbt_stg` | 1 model / 1 bảng nguồn: chọn cột, bỏ cột kỹ thuật, đổi tên cột sai chính tả, bỏ đơn đã xóa mềm (R10). Không ép kiểu lại – Mage đã nạp đúng kiểu |
| `models/intermediate/` | `int_` | view | `dbt_int` | Phép tính dùng chung cho nhiều dim / fact: `int_orders`, `int_purchase_sessions`, `int_delivery_lines` |
| `models/marts/` | `dim_`, `fact_` | table (`dim_customer`, `dim_geography`: incremental) | `dds` | 6 dimension + 3 fact – Power BI chỉ đọc schema này |
| `seeds/` | `seed_` | table | `dbt_stg` | Dữ liệu tham chiếu nhóm tự bổ sung |
| `macros/` | | | | `generate_schema_name`: dùng đúng tên schema ở cột trên (mặc định dbt ghép thành `dbt_stg_dds`); `normalize_city`: chuẩn hóa tên thành phố (R1). Mô tả cho dbt docs: `_macros.yml` |
| `tests/` | | | | Test viết tay (singular test), VD test xóa mềm R10 |
| dbt test | | table | `dq` | `store_failures`: dòng vi phạm của mỗi test vào 1 bảng, ghi đè ở mỗi lần chạy |

`staging` (Mage) và `dds` (Power BI) giữ đúng vai trò; view trung gian của dbt nằm riêng ở `dbt_stg`, `dbt_int` (dbt tự tạo 2 schema này).
Cấu hình: [dbt_project.yml](dbt_project.yml) · kết nối: [profiles.yml.example](profiles.yml.example) · package: [packages.yml](packages.yml).

## 3. Nguồn, seed, package

| Thứ | File | Ghi chú |
|---|---|---|
| Nguồn | `models/staging/_sources.yml` | 8 bảng `staging`. Model `stg_` đọc bằng `{{ source('staging', 'orders') }}`, tầng sau dùng `{{ ref('stg_orders') }}`. Test: 6 khóa ngoại (D2) + mã bang của `customers` / `sellers` có trong seed. Khóa chính không test lại vì `staging` đã có ràng buộc `PRIMARY KEY` |
| Seed | `seeds/seed_brazil_states.csv` | 27 bang → tên bang có dấu (VD `São Paulo`) + 5 vùng (Norte, Nordeste, Centro-Oeste, Sudeste, Sul) |
| | `seeds/seed_category_translation_extra.csv` | 2 bản dịch còn thiếu: `pc_gamer`, `portateis_cozinha_e_preparadores_de_alimentos` |
| Mô tả + test seed | `seeds/_seeds.yml` | Mã bang không trùng, vùng thuộc 5 giá trị |
| Package | `packages.yml` | `dbt_utils` 1.3.x – `unique_combination_of_columns` cho khóa ghép (mapping mục 5) |

## 4. Trạng thái và kết quả kiểm thử

**Trạng thái (24/10/2026): 4 task BS-28 → BS-31 đã xong** (Nhựt Thanh). `dbt build` cả project: `PASS=177 ERROR=0` (2 seed, 20 model, 155 test). Số dòng và số liệu đối soát khớp [dbt_rules.md](../docs/dbt_rules.md) B6 ([sql/checks/02_dds_checks.sql](../sql/checks/02_dds_checks.sql)).
Quy ước: mỗi tầng 1 file yml cạnh model (`_stg_models.yml`, `_int_models.yml`, `_dim_models.yml`, `_fact_models.yml`) chứa mô tả model, cột, test bằng tiếng Việt – dbt docs (Metadata) lấy từ đây.

Kết quả 6 kịch bản kiểm thử ([dbt_rules.md](../docs/dbt_rules.md) B7). Kịch bản 2, 4 chạy trên máy Thanh; kịch bản 1, 3, 5, 6 chạy trên máy Hằng (24/10/2026, DB trống, nạp `staging` bằng chính pipeline Mage):

| # | Kịch bản | Kết quả |
|---|---|---|
| 1 | Nạp đủ 10 batch rồi dựng `dds` từ đầu (`dbt build --full-refresh`) | `PASS=177 ERROR=0`. Số dòng 9 bảng và mọi số B6 khớp: doanh thu 01/2017 – 08/2018 13.449.529,68 BRL; K6 6.534 / 96.470 = 6,77%; K12 8.913 / 98.824 = 9,02%; K8 4,09; K9 14,69% cả kỳ / 14,63% trong kỳ; K5 2,27%; 47 tổ hợp trạng thái; 0 dòng fact trỏ vào `-1` ở khách / địa lý / sản phẩm |
| 2 | Build lại khi dữ liệu không đổi | Khóa 4 dimension giữ nguyên 100%; `dim_geography` báo `INSERT 0 0` |
| – | Có khách / thành phố mới (mô phỏng: xóa 200 khách, 20 thành phố khỏi dimension rồi build lại) | Khách cũ giữ khóa; khách mới nhận khóa nối tiếp 96.097 → 96.296; vẫn đúng 1 dòng `-1` |
| 3 | Nạp từng batch như lịch Seminar 3: Mage `full_load` → `dbt build --full-refresh` → 9 lần (Mage `incremental_load` → `dbt build`) | Cả 10 lần `PASS=177 ERROR=0` (mỗi vòng: Mage ~12 giây + dbt ~35 giây). Sau mỗi lần build, so khóa với lần build trước: **0** khách / thành phố / sản phẩm / người bán bị đổi khóa, khóa mới nối tiếp liền mạch (bảng dưới), luôn đúng 1 dòng `-1`. Sau batch cuối, so với kịch bản 1 theo khóa tự nhiên: cả 9 bảng giống hệt (0 dòng chênh cả 2 chiều). Chỉ **giá trị** khóa của `dim_customer`, `dim_geography` khác kịch bản 1 (cấp dần theo batch thay vì theo thứ tự mã) – đúng thiết kế R2, fact dựng lại cùng lần nên vẫn khớp |
| 4 | Xóa mềm 1 đơn rồi build | Đơn biến mất khỏi 3 fact (mỗi fact giảm 1 dòng); khách vẫn còn trong `dim_customer`, giữ khóa, chuyển sang "Chưa có đơn hợp lệ". Khôi phục đơn → số liệu trở lại như cũ |
| 5 | Mage chạy lại `full_load` → `dbt build --full-refresh` | `PASS=177 ERROR=0`. Cả 9 bảng giống hệt (kể cả khóa) kết quả sau Full Load lần đầu của kịch bản 3: chỉ còn dữ liệu batch FULL (đơn mới nhất 31/12/2017; `fact_sales` 46.418 dòng) |
| 6 | Demo 1 test FAIL: thêm 1 dòng `order_items` trỏ tới đơn không tồn tại → `dbt test --select source:staging` | Test `relationships` của `order_items.order_id` báo `FAIL 1` (`PASS=8 ERROR=1`); dòng lỗi (`demo_orphan_order`) nằm trong bảng `dq` mà dbt in ra. Xóa dòng demo, chạy lại → `PASS=9`, bảng lỗi trống lại. Cách làm: mục 6 |

Kịch bản 3 – khóa được cấp qua từng batch ở 2 dimension incremental, và số dòng fact sau mỗi lần build:

| Batch | Khách mới → khóa | Thành phố mới → khóa | `fact_sales` · `fact_delivery` · `fact_review` |
|---|---|---|---|
| FULL | 44.034 → 1 … 44.034 | 3.413 → 1 … 3.413 | 46.418 · 45.394 · 42.867 |
| 2018-01 | 7.025 → 44.035 … 51.059 | 184 → 3.414 … 3.597 | 53.901 · 52.727 · 49.224 |
| 2018-02 | 6.451 → 51.060 … 57.510 | 151 → 3.598 … 3.748 | 60.704 · 59.473 · 55.390 |
| 2018-03 | 6.965 → 57.511 … 64.475 | 142 → 3.749 … 3.890 | 68.101 · 66.754 · 63.115 |
| 2018-04 | 6.711 → 64.476 … 71.186 | 108 → 3.891 … 3.998 | 75.317 · 73.823 · 70.863 |
| 2018-05 | 6.622 → 71.187 … 77.808 | 85 → 3.999 … 4.083 | 82.414 · 80.790 · 78.512 |
| 2018-06 | 5.940 → 77.809 … 83.748 | 67 → 4.084 … 4.150 | 88.803 · 87.064 · 84.991 |
| 2018-07 | 6.071 → 83.749 … 89.819 | 85 → 4.151 … 4.235 | 95.255 · 93.438 · 90.904 |
| 2018-08 | 6.271 → 89.820 … 96.090 | 74 → 4.236 … 4.309 | 101.952 · 100.009 · 99.869 |
| 2018-09+ | 6 → 96.091 … 96.096 | 0 (`INSERT 0 0`) | 101.953 · 100.010 · 100.568 |

Mỗi lần build, dbt báo `dim_customer` `INSERT` lại **toàn bộ** khách (VD `INSERT 0 51059` sau batch 2018-01): mẫu SCD 1 tính lại thuộc tính của mọi khách rồi `delete+insert`, khóa vẫn lấy lại từ bảng cũ. Batch 2018-09+ chỉ có 20 đơn mới nhưng `fact_review` vẫn tăng 699 dòng: đánh giá đến theo tháng khách **trả lời** (D8), nhiều đơn tháng 8 được trả lời sang tháng 9.
Cách so khóa trước / sau 1 lần build (dùng lại khi demo nạp từng batch): [sql/checks/03_dbt_test_demo.sql](../sql/checks/03_dbt_test_demo.sql) câu Q4.

Lỗi môi trường đã gặp: build song song 3 fact báo `could not resize shared memory segment … No space left on device` (lúc có lúc không). Nguyên nhân: Docker mặc định cho container Postgres 64 MB bộ nhớ dùng chung (`/dev/shm`). Đã thêm `shm_size: 256mb` cho service `postgres` trong `compose.yaml` – máy nào đã bật container trước đó thì chạy `docker compose up -d` để tạo lại container (dữ liệu trong volume không mất).

## 5. Danh sách model

20 model + 1 macro. Mô tả từng cột nằm trong file yml cạnh model (xem bằng `dbt docs`).

| Model | Tầng (schema) | Đọc từ | Một dòng là | Số dòng |
|-------|---------------|--------|-------------|---------|
| `stg_orders` | staging (`dbt_stg`, view) | `source: staging.orders` | 1 đơn chưa bị xóa (R10 lọc ở đây) | 99.441 |
| `stg_order_items` | staging | `source: order_items`, `stg_orders` | 1 đơn vị sản phẩm trong 1 đơn | 112.650 |
| `stg_order_payments` | staging | `source: order_payments`, `stg_orders` | 1 lần thanh toán (chưa bảng dds nào dùng) | 103.886 |
| `stg_order_reviews` | staging | `source: order_reviews`, `stg_orders` | 1 đánh giá cho 1 đơn | 99.224 |
| `stg_customers` | staging | `source: customers` | 1 `customer_id` = địa chỉ nhận của 1 đơn | 99.441 |
| `stg_sellers` | staging | `source: sellers` | 1 người bán | 3.095 |
| `stg_products` | staging | `source: products` | 1 sản phẩm (đổi tên `*_lenght` → `*_length`) | 32.951 |
| `stg_category_translation` | staging | `source: category_translation` | 1 bản dịch danh mục | 71 |
| `int_orders` | intermediate (`dbt_int`, view) | `stg_orders`, `stg_customers`, `stg_order_items` | 1 đơn + khách thật, nơi nhận đã chuẩn hóa (R1), cờ đơn hợp lệ (R4) | 99.441 |
| `int_purchase_sessions` | intermediate | `int_orders` | 1 đơn hợp lệ + lần mua thứ mấy (R6) | 98.199 |
| `int_delivery_lines` | intermediate | `stg_order_items`, `int_orders`, `stg_sellers` | 1 cặp (đơn, người bán) + 4 số ngày (R7) + 3 nhãn trạng thái (R9) | 100.010 |
| `dim_date` | marts (`dds`, table) | tự sinh | 1 ngày, 2016 – 2018 | 1.096 |
| `dim_delivery_status` | marts (table) | tự sinh | 1 tổ hợp trạng thái giao hàng (8 × 4 × 3 × 7) | 672 |
| `dim_product` | marts (table) | `stg_products`, `stg_category_translation`, seed | 1 sản phẩm | 32.952 |
| `dim_seller` | marts (table) | `stg_sellers`, seed | 1 người bán | 3.096 |
| `dim_geography` | marts (incremental) | `stg_customers`, seed | 1 thành phố của 1 bang (nơi nhận) | 4.310 |
| `dim_customer` | marts (incremental) | `stg_customers`, `int_orders`, `int_purchase_sessions`, seed | 1 khách hàng thực | 96.097 |
| `fact_sales` | marts (table) | `stg_order_items`, `int_orders`, `int_purchase_sessions`, 4 dim | 1 sản phẩm của 1 người bán trong 1 đơn hợp lệ | 101.953 |
| `fact_delivery` | marts (table) | `int_delivery_lines`, 4 dim | 1 cặp (đơn, người bán) | 100.010 |
| `fact_review` | marts (table) | `stg_order_reviews`, `stg_order_items`, `int_orders`, `int_delivery_lines`, 4 dim | 1 đánh giá × 1 người bán của đơn | 100.568 |

Số dòng dim có tính 1 dòng `-1` "Không xác định" (trừ `dim_date`, `dim_delivery_status`). Macro `normalize_city` (R1) dùng ở `int_orders`, `dim_geography`, `dim_customer`, `dim_seller`.

## 6. Data tests

155 test: nguồn 8, seed 6, staging 6, intermediate 17, dimension 60, fact 58. Mỗi test trả về các dòng **vi phạm**; 0 dòng = đạt. Dòng vi phạm được lưu vào schema `dq` (mỗi test 1 bảng, ghi đè mỗi lần chạy).

| Model.Cột | Test | Mục đích |
|-----------|------|----------|
| Nguồn `staging` | `relationships` (6 khóa ngoại D2, mã bang khớp seed) | Phát hiện dòng mồ côi do Mage nạp thiếu |
| Mọi `*_key` của dimension, khóa tự nhiên (`customer_unique_id`, `product_id`, `seller_id`, `full_date`), `order_id` của `int_orders`, `int_purchase_sessions` | `unique`, `not_null` | Mỗi thực thể đúng 1 dòng, không có khóa rỗng |
| `int_delivery_lines` (đơn, người bán); `dim_geography` (bang, thành phố); `dim_delivery_status` (4 nhãn); khóa chính 3 fact (6 / 6 / 8 cột) | `dbt_utils.unique_combination_of_columns` | Đúng grain: không nhân dòng khi nối bảng |
| Mọi khóa ngoại của 3 fact; mã bang của `dim_seller`, `dim_geography`, `dim_customer` | `relationships` | Fact chỉ trỏ tới khóa có thật trong dimension; mã bang có trong seed |
| `order_status`, `payment_type`, `review_score` (1–5), `handover_status`, `route_type`, `delay_bucket`, `delivery_result`, `customer_type`, `weight_class`, `region`, thứ / tháng / quý / năm của `dim_date` | `accepted_values` | Nhãn đúng chính tả (có dấu, gạch "–") để fact tra được `dim_delivery_status` và Power BI lọc đúng |
| `quantity` ≥ 1, `unit_price` > 0, `revenue` > 0, `freight_value` ≥ 0, `purchase_seq` ≥ 1, `purchase_count` ≥ 0, `delivery_days` ≥ 0, `transit_days` ≥ 0 | `dbt_utils.accepted_range` | Số liệu không âm / không bằng 0 bất thường |
| `fact_sales`: `revenue = quantity × unit_price`; `dim_date`: `date_key` khớp ngày, `year_month`, `is_weekend`; `dim_customer`: loại khách khớp số lần mua; `dim_product`: nhóm khối lượng khớp khối lượng; `fact_delivery`: `late_days` và `delivery_days` cùng có / cùng NULL | `dbt_utils.expression_is_true` | Các cột phải khớp nhau theo quy tắc nghiệp vụ |
| `tests/test_normalize_city.sql` | Viết tay | 10 ví dụ của R1 (bỏ dấu, cắt `/`, bỏ ngoặc, mã bang, email…) phải cho đúng kết quả |
| `tests/assert_dim_unknown_members.sql` | Viết tay | Mỗi dimension có đúng 1 dòng `-1` (quan trọng với 2 dimension incremental) |
| `tests/assert_no_deleted_orders_in_facts.sql` | Viết tay | Đơn đã xóa mềm (R10) không còn trong fact nào |
| `tests/assert_one_latest_review_per_order.sql` | Viết tay | Mỗi đơn có đúng 1 đánh giá `is_latest_review` → K8, K9 không đếm lặp |
| `tests/assert_facts_match_sources.sql` | Viết tay | Tổng `quantity`, tổng `revenue`, số dòng `fact_delivery`, số lượt đánh giá khớp nguồn → không nhân dòng, không mất dòng. So với nguồn chứ không so với số cố định nên vẫn đúng khi xóa đơn |

Tổng tiền, số dòng **không** viết thành test cứng (demo xóa đơn sẽ làm chúng đổi) – đối soát bằng `sql/checks/02_dds_checks.sql`.

### Khi có test FAIL – xem dòng vi phạm ở đâu

- dbt in tên test và câu `select * from "olist_dw"."dq"."<tên bảng>"` (dòng *See test failures*) → chạy câu đó trong DBeaver để xem dòng sai. Trong `dbt build`, test FAIL làm các model / test **phía sau** bị `SKIP`, nên dữ liệu sai không chảy tiếp vào `dds`.
- Mỗi test có 1 bảng trong schema `dq` (155 bảng), ghi đè ở mỗi lần chạy; bảng 0 dòng = test đạt. Liệt kê nhanh các test đang có dòng vi phạm: [sql/checks/03_dbt_test_demo.sql](../sql/checks/03_dbt_test_demo.sql) câu Q1.
- Khác `dq.rejected_rows`: bảng đó do Mage ghi – dòng **bị loại**, không vào `staging`. dbt test chỉ **phát hiện**; dòng sai vẫn nằm trong `staging` / `dds` cho tới khi sửa nguồn rồi nạp lại.

**Demo 1 test FAIL** (B7 kịch bản 6, các bước ở câu Q3 của file trên): thêm 1 dòng `order_items` trỏ tới đơn `demo_orphan_order` không tồn tại → `dbt test --select source:staging` ra:

```
3 of 9 FAIL 1 source_relationships_staging_order_items_order_id__order_id__source_staging_orders_  [FAIL 1 in 0.44s]
...
Failure in test source_relationships_staging_order_items_order_id__order_id__source_staging_orders_ (models/staging/_sources.yml)
  Got 1 result, configured to fail if != 0
  ...
  See test failures:
  select * from "olist_dw"."dq"."source_relationships_staging_o_e2f0b1bc186e5bee3058cd672e745441"
Done. PASS=8 WARN=0 ERROR=1 SKIP=0 TOTAL=9
```

Bảng lỗi có đúng 1 dòng `from_field = demo_orphan_order`. `TOTAL=9` = 8 test nguồn + `assert_no_deleted_orders_in_facts` (test này cũng đọc `staging.orders` nên được chọn theo). Xóa dòng demo, chạy lại → `PASS=9`, bảng lỗi trống lại. Tên bảng lỗi giống nhau ở mọi máy (máy Thanh, máy Hằng).

## 7. Tài liệu dbt (dbt docs) và lineage

`docker compose exec mage dbt docs generate --static` → mở `dbt/target/static_index.html` bằng trình duyệt (1 file, không cần chạy server). Thư mục `dbt/target/` không lên GitHub nên mỗi máy tự generate, sau khi đã `dbt build`. Trong kiến trúc Single DDS, đây là phần **Metadata**.

| Trang docs có gì | Lấy từ |
|---|---|
| Trang mở đầu (Overview): các tầng – schema, grain 3 fact, cách đọc trang, lệnh chạy | `models/overview.md` (khối `{% docs __overview__ %}`) |
| Mỗi model / seed: mô tả, **mọi** cột có mô tả (176 / 176 cột), test của từng cột, code SQL (*Source* / *Compiled*) | file yml cạnh model, `seeds/_seeds.yml` |
| 2 macro: mô tả + tham số, model nào đang dùng | `macros/_macros.yml` |
| Exposure **Dashboard Power BI**: 9 bảng `dds` → dashboard. Lineage đi tới tận Power BI; trang exposure liệt kê bảng dashboard dùng – đổi / xóa cột ở các bảng này thì báo người làm Power BI | `models/marts/_exposures.yml` (`maturity: low` – dashboard đang làm, xong thì nâng lên) |
| Bảng nguồn `staging`: mô tả cấp bảng; mô tả từng cột xem ở model `stg_` cùng tên cột hoặc [docs/data_dictionary.md](../docs/data_dictionary.md) | `models/staging/_sources.yml` |

- Mô tả còn được ghi thành **`COMMENT`** của bảng / cột trong Postgres (`+persist_docs` trong `dbt_project.yml`, cập nhật ở mỗi lần build): 22 bảng / view trong `dds`, `dbt_stg`, `dbt_int` và 176 cột → mở DBeaver cũng đọc được ý nghĩa cột (tab *Columns*, cột *Comment*) mà không cần mở trang docs.
- Xem lineage: nút tròn ở góc dưới bên phải. Muốn ẩn test cho gọn: ô *resources* ở thanh dưới → bỏ chọn `test` → *Update Graph*.

Ảnh lineage dưới đây (model + seed + source, ẩn test) xuất trước khi có exposure nên chưa có nút *Dashboard Power BI* – sơ đồ trong trang docs hiện tại có thêm nút này ở cuối.

![Lineage](../docs/images/dbt_lineage.png)
