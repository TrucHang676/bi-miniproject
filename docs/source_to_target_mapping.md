# Ánh xạ nguồn → đích (Source-to-Target Mapping)

> **Task:** BS-15 · **Người thực hiện:** Nguyễn Nhựt Thanh · **Trạng thái:** Đã điền đủ 9 bảng – chờ nhóm review
> Bản tóm tắt theo bảng nằm ở [dw_design.md](dw_design.md) mục 8; file này chi tiết đến **từng cột** của 9 bảng trong `dds`.
> Đây là "công thức" để viết model dbt: nhìn vào bảng là biết mỗi cột lấy từ đâu, biến đổi ra sao, không phải đoán.
> Mọi con số trong file được kiểm chứng bằng cách chạy đúng các quy tắc dưới đây trên 8 CSV gốc (= trạng thái `staging` sau batch đối soát `2018-09+`, D8).

---

## Cách đọc file

### Phạm vi

- **Nguồn:** 8 bảng trong schema `staging` (Mage nạp, giữ nguyên tên cột như CSV gốc – kiểu dữ liệu xem [data_dictionary.md](data_dictionary.md), DDL ở `sql/init/01_staging_tables.sql`) và 2 dbt seed (mục 0.2).
- **Đích:** 6 dimension + 3 fact trong schema `dds` (dbt tạo).
- Không ánh xạ bước CSV → `staging`: bước này giữ nguyên cột và đã mô tả trong `data_dictionary.md`.
- Cột kỹ thuật `_batch_id`, `_loaded_at` của `staging` không đi vào `dds` (mục 4).

### Ý nghĩa các cột trong bảng ánh xạ

| Cột | Ghi gì |
|---|---|
| Nguồn | `bảng.cột` ở staging (hoặc `tên_seed.cột`); nhiều cột thì liệt kê đủ. Cột không có nguồn ghi `(sinh)`, VD surrogate key |
| Biến đổi | Mô tả ngắn + biểu thức PostgreSQL khi cần. Không đổi gì thì ghi "Giữ nguyên"; quy tắc dùng chung ghi mã `R…` (mục 1) |
| NULL / lỗi | Gặp NULL, giá trị sai, lookup không khớp thì xử lý thế nào (`-1`, `'unknown'`, để NULL…) |
| Ghi chú | Bẫy dữ liệu liên quan, số dòng bị ảnh hưởng, dẫn chiếu tài liệu |

### Tài liệu tham khảo

| Tài liệu | Lấy gì |
|---|---|
| [dw_design.md](dw_design.md) | Grain từng fact (mục 2), quy tắc từng dimension (mục 5), mô tả cột fact (mục 6), measures và ánh xạ KPI (mục 7) |
| [data_dictionary.md](data_dictionary.md) | Tên, kiểu và lỗi chất lượng của từng cột nguồn |
| [decisions.md](decisions.md) | D7 (khách theo `customer_unique_id`, gộp đơn ≤ 10 phút), D8 (mốc chưa xảy ra tại cutoff = NULL, đơn cũ được cập nhật ở batch sau); bảng "Quyết định đã chốt sau thảo luận" cuối file |
| [business_questions.md](business_questions.md) | Định nghĩa "đơn hợp lệ", KPI K1–K13, measure M1–M5 |
| [images/dds_schema.drawio](images/dds_schema.drawio) | Danh sách cột đích (kiểu dữ liệu chỉ còn ghi ở file này) |

### Tiêu chí hoàn thành

- [x] Cả 9 bảng điền đủ thông tin chung và mọi ô trong bảng từng cột; không còn dòng nào ghi kiểu `bảng.*`.
- [x] Mọi cột trên sơ đồ đều có trong file này (sơ đồ đổi cột thì cập nhật theo).
- [x] Mục 1 có đủ quy tắc dùng chung, các bảng dẫn chiếu đúng mã quy tắc.
- [ ] Đã báo nhóm review (sau khi review: xóa mục "Cách đọc file → Tiêu chí hoàn thành" và đổi trạng thái ở đầu file).

---

## 0. Tổng quan luồng biến đổi

### 0.1. Thứ tự dựng model (lineage)

Mỗi bảng `dds` chỉ đọc từ `staging`, seed hoặc model trung gian (`int_`) – không đọc chéo giữa các fact. Ba model trung gian gom những phép tính dùng lại ở nhiều nơi, để 3 fact cho cùng một kết quả:

```
staging.*  ──► stg_*  (view, 1 model / 1 bảng: ép kiểu, TRIM, đổi tên cột sai chính tả, bỏ đơn đã xóa mềm – R10)
                │
                ├─► int_orders            1 dòng / đơn: customer_unique_id, bang + thành phố nơi nhận (R1), is_valid (R4)
                ├─► int_purchase_sessions 1 dòng / đơn hợp lệ: purchase_seq (R6)
                └─► int_delivery_lines    1 dòng / (đơn, người bán): mốc thời gian, 4 measure ngày (R7),
                                          handover_status, route_type, delay_bucket (R9)

seeds ──► dim_date, dim_delivery_status (sinh, không cần staging)
          dim_geography, dim_customer, dim_product, dim_seller
                │
                └─► fact_sales  (int_orders + int_purchase_sessions + order_items)
                    fact_delivery (int_delivery_lines)
                    fact_review (order_reviews + int_delivery_lines)
```

Thứ tự chạy `dbt build`: seed → `stg_` → `int_` → dimension → fact (dbt tự suy ra từ `ref()`).

### 0.2. dbt seed (dữ liệu tham chiếu tự bổ sung)

| Seed (tên đã chốt 23/10/2026, file trong `dbt/seeds/`) | Cột | Số dòng | Dùng cho | Lý do |
|---|---|---|---|---|
| `seed_brazil_states` | `state_code` CHAR(2), `state_name` VARCHAR(50), `region` VARCHAR(30) | 27 | `dim_geography`, `dim_customer`, `dim_seller` | Nguồn chỉ có mã bang (`SP`); tên bang và 5 vùng (Norte, Nordeste, Centro-Oeste, Sudeste, Sul) phục vụ phân cấp Vùng → Bang → Thành phố |
| `seed_category_translation_extra` | `product_category_name`, `product_category_name_english` | 2 | `dim_product` | 2 danh mục có sản phẩm nhưng thiếu bản dịch: `pc_gamer` → `pc_gamer`, `portateis_cozinha_e_preparadores_de_alimentos` → `portable_kitchen_and_food_preparers` (13 sản phẩm) |

### 0.3. Cách nạp từng bảng

| Bảng | Materialization | Lý do |
|---|---|---|
| `dim_date`, `dim_delivery_status` | `table` | Sinh tĩnh, không phụ thuộc batch |
| `dim_product`, `dim_seller` | `table` | Nguồn nạp **1 lần** ở Full Load (D3) → dựng lại mỗi lần vẫn cho cùng khóa (R2) |
| `dim_customer` | `incremental`, `unique_key = customer_unique_id` | Khách mới đến theo batch; khách cũ **giữ khóa**, cập nhật thuộc tính (SCD 1, D7) |
| `dim_geography` | `incremental`, `unique_key = (state_code, city)` | Thành phố mới xuất hiện theo batch; chỉ thêm, không sửa |
| `fact_sales` | `table` | **Đổi từ `incremental` ngày 19/10/2026:** đơn bị xóa ở nguồn (R10) phải biến mất khỏi fact, mà `incremental` chỉ thêm dòng mới chứ không xóa dòng cũ. Dựng lại ~102 nghìn dòng mỗi lần chạy vẫn nhanh; dbt `incremental` vẫn được dùng ở `dim_customer`, `dim_geography`. (Lý do cũ còn đúng nếu không có xóa: sản phẩm của đơn chỉ đến 1 lần ở batch đầu – D5 – và đơn hợp lệ không đổi thành không hợp lệ – D8) |
| `fact_delivery`, `fact_review` | `table` | `delivery_status_key` thuộc khóa và đổi theo batch; `is_latest_review` của review cũ phải đổi khi review mới đến (chốt 18/10/2026) |

---

## 1. Quy tắc dùng chung

| Mã | Quy tắc | Mô tả / biểu thức | Dùng ở |
|---|---|---|---|
| R1 | Chuẩn hóa tên thành phố | Macro dbt `normalize_city(city, state)` (cần extension `unaccent`), chạy lần lượt:<br>**B1** `unaccent(lower(trim(city)))` – `São Paulo` → `sao paulo`<br>**B2** cắt từ ký tự `/`, `\` hoặc `,` đầu tiên trở đi – `maua/sao paulo` → `maua`<br>**B3** bỏ phần trong ngoặc – `arraial d'ajuda (porto seguro)` → `arraial d'ajuda`<br>**B4** `-` → khoảng trắng – `mogi-mirim` → `mogi mirim`<br>**B5** gộp nhiều khoảng trắng thành một, `trim`<br>**B6** bỏ mã bang **của chính dòng** nếu nằm ở cuối – `sao paulo - sp` → `sao paulo`<br>**B7** trả NULL nếu chỉ còn mã bang, có `@` hoặc toàn chữ số (`sp`, email, `04482255`); ở dimension hiển thị "Không xác định".<br>**Không** gán NULL cho giá trị trùng *tên* bang: `sao paulo`, `rio de janeiro`, `goias`, `tocantins` là thành phố có thật.<br>Kiểm chứng trên CSV gốc: khách 4.309 tổ hợp (bang, thành phố), 0 NULL – giống quy tắc cũ; người bán 636 → 610, 7 dòng "Không xác định"; 77 dòng người bán còn gõ sai / viết tắt / lệch bang giữ nguyên (tùy chọn: seed `city_corrections.csv` nếu cần hiển thị đẹp ở trang chi tiết người bán) | `dim_geography`, `dim_customer`, `dim_seller`, lookup `geography_key` trong 3 fact |
| R2 | Sinh surrogate key và member `-1` "Không xác định" | **Khóa là số nguyên, ổn định qua các lần chạy** – fact chỉ lưu khóa nên khóa của một thực thể không được đổi.<br>• Dimension dựng lại toàn bộ (`dim_product`, `dim_seller`): `ROW_NUMBER() OVER (ORDER BY <NK>)` – nguồn không đổi giữa các batch nên kết quả luôn như nhau.<br>• Dimension incremental (`dim_customer`, `dim_geography`): `LEFT JOIN {{ this }}` theo NK; thực thể đã có giữ khóa cũ, thực thể mới nhận `MAX(khóa hiện có) + ROW_NUMBER() OVER (ORDER BY <NK>)`.<br>• Member `-1`: thêm bằng `UNION ALL` một dòng `key = -1`, NK = `'-1'`, thuộc tính chữ = `'Không xác định'`, thuộc tính số / ngày = NULL (với model incremental: chỉ thêm ở lần chạy đầu – `{% if not is_incremental() %}`).<br>• `dim_date`: khóa = `YYYYMMDD` (R3), không có `-1`. `dim_delivery_status`: khóa = thứ tự cố định của tổ hợp (mục 2.6), không có `-1` vì đủ mọi tổ hợp | 6 dimension |
| R3 | Đổi ngày → `date_key` (`YYYYMMDD`) | `TO_CHAR(<cột>, 'YYYYMMDD')::INT` – VD `2018-03-15 10:56:33` → `20180315`. Lấy phần ngày của `TIMESTAMP` theo giờ địa phương Brazil như nguồn, **không** quy đổi múi giờ.<br>Cột nguồn dùng R3 đều **không NULL** (`order_purchase_timestamp`, `review_answer_timestamp`: 0 NULL) và nằm trong khoảng `dim_date` (04/09/2016 → 29/10/2018) → dbt test `not_null` + `relationships` tới `dim_date`, không cần member `-1` | `purchase_date_key` (3 fact), `answer_date_key` |
| R4 | Đơn hợp lệ | `order_status NOT IN ('canceled', 'unavailable')` **và** `EXISTS (SELECT 1 FROM order_items WHERE order_id = o.order_id)` – định nghĩa của K1 (business_questions mục 6).<br>Trên dữ liệu đầy đủ: **98.199** đơn hợp lệ, 1.242 đơn không hợp lệ (1.234 hủy / hết hàng + 8 đơn trạng thái khác nhưng không có sản phẩm). Tính một lần ở `int_orders.is_valid` | `fact_sales` (lọc), `dim_customer` (`first_purchase_date`, `purchase_count`), R6 |
| R5 | Lookup khóa dimension trong fact | Luôn `LEFT JOIN` rồi `COALESCE(<key>, -1)` – không dùng `INNER JOIN` để không làm mất dòng fact âm thầm:<br>• **Khách:** `orders.customer_id` → `customers.customer_unique_id` → `dim_customer.customer_key`<br>• **Địa lý:** `customers.customer_state` + `normalize_city(customers.customer_city, customers.customer_state)` **của dòng `customers` gắn với chính đơn** → `dim_geography (state_code, city)` – vị trí tại thời điểm mua, không lấy địa chỉ SCD 1 trong `dim_customer`<br>• **Sản phẩm / người bán:** `order_items.product_id` / `seller_id` → NK của `dim_product` / `dim_seller`<br>Trên dữ liệu thật: 0 dòng rơi vào `-1` ở khách, địa lý, sản phẩm (toàn vẹn tham chiếu 100% – D2); `-1` người bán chỉ dùng cho 759 dòng `fact_review` của đơn không có sản phẩm | 3 fact |
| R6 | Lần mua (gộp giỏ hàng tách đơn) | Trên các **đơn hợp lệ** (R4) của một `customer_unique_id`, sắp `order_purchase_timestamp, order_id`:<br>`new_purchase = LAG(ts) IS NULL OR ts − LAG(ts) > INTERVAL '10 minutes'`<br>`purchase_seq = SUM(new_purchase::INT) OVER (PARTITION BY customer_unique_id ORDER BY ts, order_id)` → 1, 2, 3…<br>So với **đơn liền trước** (chuỗi), không so với đơn đầu tiên. Lý do: giỏ hàng nhiều người bán bị tách thành nhiều đơn cách nhau vài giây (D7) | `fact_sales.purchase_seq`, `dim_customer.purchase_count`, `customer_type` |
| R7 | Đổi khoảng thời gian → số ngày | `ROUND(EXTRACT(EPOCH FROM (<mốc sau> − <mốc trước>)) / 86400, 2)::NUMERIC(6,2)` (Postgres: `timestamp − timestamp` ra `INTERVAL`).<br>`late_days` là `DATE − DATE` nên ra số nguyên: `(<mốc>::DATE − estimated_delivery_date)::SMALLINT`.<br>Measure = NULL khi thiếu một trong hai mốc hoặc hai mốc sai thứ tự (điều kiện cụ thể ghi ở từng cột của `fact_delivery`) | 4 measure của `fact_delivery` |
| R8 | Làm sạch bình luận review | `NULLIF(TRIM(<cột>), '')`, sau đó coi là **không có bình luận** nếu không chứa chữ cái nào: `CASE WHEN TRIM(x) ~ '[[:alpha:]]' THEN TRIM(x) END` (database UTF-8 nên `[[:alpha:]]` nhận cả chữ có dấu tiếng Bồ Đào Nha).<br>Loại các giá trị giả-NULL kiểu `.`, `...`, `-`, `?`, `*****`, chuỗi số (`5`, `10`), emoji: 416 tiêu đề + 186 nội dung. Kết quả: **42.454** review (42,8%) có bình luận thật, so với 42.706 (43,0%) nếu chỉ kiểm NULL | `fact_review.has_comment` |
| R9 | Thuộc tính trạng thái giao hàng | Tính một lần ở `int_delivery_lines` cho mỗi cặp (đơn, người bán), xét **theo thứ tự**, gặp điều kiện đầu tiên thì dừng:<br>**handover_status** (so theo giờ): `delivered_carrier_date IS NULL` → `Chưa bàn giao` · `delivered_carrier_date < order_purchase_timestamp` → `Không xác định` · `delivered_carrier_date > shipping_limit_date` → `Trễ hạn` · còn lại → `Đúng hạn`<br>**route_type:** `customers.customer_state = sellers.seller_state` → `Nội bang` · khác → `Liên bang` · một trong hai NULL → `Không xác định`<br>**delay_bucket:** `order_status <> 'delivered'` → `Chưa giao` · `delivered_customer_date IS NULL` → `Không xác định` · `late_days ≤ 0` → `Đúng hạn` · 1–3 → `Trễ 1–3 ngày` · 4–7 → `Trễ 4–7 ngày` · 8–14 → `Trễ 8–14 ngày` · > 14 → `Trễ > 14 ngày`<br>Bộ 4 giá trị (`order_status`, `handover_status`, `route_type`, `delay_bucket`) → lookup `dim_delivery_status.delivery_status_key` | `fact_delivery`, `fact_review` |
| R10 | Đơn bị xóa ở nguồn (xóa mềm) | Pipeline Mage đặt `staging.orders._is_deleted = TRUE` khi nguồn báo xóa ([pipeline_rules.md](pipeline_rules.md) B6, chốt 19/10/2026). **Đơn bị xóa coi như chưa từng có trong `dds`**, lọc ngay ở lớp `stg_`:<br>• `stg_orders`: `WHERE NOT _is_deleted`<br>• `stg_order_items`, `stg_order_payments`, `stg_order_reviews`: chỉ giữ dòng của đơn chưa xóa – `WHERE order_id IN (SELECT order_id FROM <staging.orders> WHERE NOT _is_deleted)`<br>• `stg_customers`: **không lọc** – dimension giữ thành viên; các thuộc tính tính từ đơn (`purchase_count`, `customer_type`, địa chỉ đơn gần nhất) tự tính trên đơn chưa xóa vì đọc qua `stg_orders`<br>Hệ quả: 3 fact dựng lại mỗi lần chạy (`table`) để dòng của đơn vừa bị xóa biến mất (mục 0.3). Dữ liệu thật không có đơn bị xóa → mọi số liệu trong file này không đổi | `stg_*`, 3 fact |

---

## 2. Dimension

### 2.1 `dim_date`

- **Grain:** một ngày dương lịch, 01/01/2016 → 31/12/2018 (**1.096 dòng**, 2016 là năm nhuận)
- **Model dbt:** `dim_date`
- **Nguồn:** không có – sinh bằng `generate_series('2016-01-01'::DATE, '2018-12-31'::DATE, INTERVAL '1 day')`
- **Lọc / JOIN / gộp:** không. Khoảng ngày được chọn để phủ đủ mọi ngày mà fact tham chiếu: ngày mua (04/09/2016 → 17/10/2018), ngày trả lời review (07/10/2016 → 29/10/2018) và ngày giao dự kiến (đến 12/11/2018)
- **Cách nạp:** `table` – SCD Type 0, không phụ thuộc batch

| Cột đích | Kiểu | Nguồn | Biến đổi | NULL / lỗi | Ghi chú |
|---|---|---|---|---|---|
| `date_key` (PK) | INT | (sinh) | R3: `TO_CHAR(d, 'YYYYMMDD')::INT` | Không có | Khóa vừa duy nhất vừa đọc được (`20180315`) |
| `full_date` | DATE | (sinh) | `d::DATE` | Không có | Khóa tự nhiên |
| `day_of_month` | SMALLINT | (sinh) | `EXTRACT(DAY FROM d)::SMALLINT` | Không có | 1–31 |
| `day_of_week` | SMALLINT | (sinh) | `EXTRACT(ISODOW FROM d)::SMALLINT` | Không có | Chuẩn ISO: 1 = Thứ Hai … 7 = Chủ nhật. **Không** dùng `DOW` (0 = Chủ nhật) |
| `day_name` | VARCHAR(20) | (sinh) | `CASE day_of_week WHEN 1 THEN 'Thứ Hai' … WHEN 6 THEN 'Thứ Bảy' WHEN 7 THEN 'Chủ nhật' END` | Không có | Power BI: *Sort by column* = `day_of_week` |
| `is_weekend` | BOOLEAN | (sinh) | `day_of_week IN (6, 7)` | Không có | |
| `month` | SMALLINT | (sinh) | `EXTRACT(MONTH FROM d)::SMALLINT` | Không có | Trục X của biểu đồ so sánh cùng kỳ (Q1) |
| `month_name` | VARCHAR(20) | (sinh) | `FORMAT('Tháng %s', month)` | Không có | Power BI: *Sort by column* = `month` |
| `year_month` | INT | (sinh) | `year * 100 + month` – VD `201803` | Không có | Khóa duy nhất của cấp Tháng, tránh gộp 03/2017 với 03/2018 khi drill-down |
| `quarter` | SMALLINT | (sinh) | `EXTRACT(QUARTER FROM d)::SMALLINT` | Không có | 1–4 |
| `year` | SMALLINT | (sinh) | `EXTRACT(YEAR FROM d)::SMALLINT` | Không có | 2016–2018 |
| `is_analysis_period` | BOOLEAN | (sinh) | `d BETWEEN '2017-01-01' AND '2018-08-31'` | Không có | Bộ lọc mặc định của dashboard: 99,6% số đơn (bẫy dữ liệu #1). M1/M2 (cùng kỳ) chỉ có nghĩa trong khoảng này |

### 2.2 `dim_customer`

- **Grain:** một khách hàng thực – `customer_unique_id` (**96.096 dòng** + 1 dòng `-1`)
- **Model dbt:** `dim_customer`
- **Nguồn:** `staging.customers`, `staging.orders`, `staging.order_items` (qua `int_orders`, `int_purchase_sessions`), `seed_brazil_states`
- **Lọc / JOIN / gộp:**
  1. **Danh sách khách:** `DISTINCT customers.customer_unique_id` trên mọi dòng `customers` (mọi đơn, kể cả đơn hủy) – vì khách chỉ có đơn hủy vẫn xuất hiện ở `fact_delivery`, `fact_review`.
  2. **Địa chỉ (SCD 1):** `orders JOIN customers ON customer_id`, chọn đơn **gần nhất** của khách trong **mọi đơn**: `ROW_NUMBER() OVER (PARTITION BY customer_unique_id ORDER BY order_purchase_timestamp DESC, order_id DESC) = 1` (chốt 17/10/2026). 1.171 khách có đơn gần nhất là đơn không hợp lệ – vẫn lấy địa chỉ của đơn đó.
  3. **Lịch sử mua:** từ `int_purchase_sessions` (chỉ đơn hợp lệ – R4, R6), `GROUP BY customer_unique_id` → `MIN` ngày mua, `MAX(purchase_seq)`; `LEFT JOIN` vào danh sách ở bước 1 để giữ 1.113 khách không có đơn hợp lệ.
  4. `LEFT JOIN seed_brazil_states ON state_code = customer_state` → vùng.
- **Cách nạp:** `incremental`, `unique_key = customer_unique_id`. Mỗi lần chạy tính lại thuộc tính từ toàn bộ lịch sử trong `staging` (vì đơn mới làm đổi `purchase_count`, địa chỉ) rồi ghi đè (SCD 1); khóa giữ theo R2

| Cột đích | Kiểu | Nguồn | Biến đổi | NULL / lỗi | Ghi chú |
|---|---|---|---|---|---|
| `customer_key` (PK) | INT | (sinh) | R2 – khách cũ giữ khóa, khách mới `MAX + ROW_NUMBER() OVER (ORDER BY customer_unique_id)` | Dòng `-1` "Không xác định" | Khóa ổn định qua 10 batch để 3 fact (dựng lại mỗi lần chạy) luôn tra ra cùng khóa cho cùng một khách |
| `customer_unique_id` (NK) | VARCHAR(32) | `customers.customer_unique_id` | Giữ nguyên | Không NULL ở nguồn; dòng `-1`: `'-1'` | **Không** dùng `customer_id` (1 mã = 1 đơn → tỉ lệ mua lại luôn 0%) – D7. dbt test `unique` |
| `customer_city` | VARCHAR(100) | `customers.customer_city` (đơn gần nhất) | R1 `normalize_city(customer_city, customer_state)` | R1 trả NULL → `'Không xác định'` (0 dòng trên dữ liệu thật) | Địa chỉ hiện tại của khách; vị trí *tại lúc mua* nằm ở `fact.geography_key` |
| `customer_state` | CHAR(2) | `customers.customer_state` (đơn gần nhất) | Giữ nguyên | Không NULL ở nguồn; dòng `-1`: NULL | 27 bang; 39 khách từng đổi bang → lấy bang của đơn gần nhất |
| `customer_region` | VARCHAR(30) | `seed_brazil_states.region` | Lookup theo `customer_state` | Không khớp → `'Không xác định'` (0 dòng – seed đủ 27 bang) | Cấp trên cùng của phân cấp Khách hàng → Thành phố → Bang → Vùng |
| `first_purchase_date` | DATE | `orders.order_purchase_timestamp` (đơn hợp lệ) | `MIN(order_purchase_timestamp)::DATE` | Khách không có đơn hợp lệ → NULL (1.113 dòng) | |
| `purchase_count` | SMALLINT | `orders.order_purchase_timestamp`, `orders.order_id` (đơn hợp lệ) | R6 → `MAX(purchase_seq)` | Không có đơn hợp lệ → `0` (`COALESCE`) | Phân bố: 0 lần 1.113 · 1 lần 92.827 · 2 lần 1.988 · 3 lần 133 · 4–7 lần 34 · tối đa 16 lần (1 khách) |
| `customer_type` | VARCHAR(20) | (suy ra từ `purchase_count`) | `CASE WHEN purchase_count = 0 THEN 'Chưa có đơn hợp lệ' WHEN purchase_count = 1 THEN 'Mua một lần' ELSE 'Mua lại' END` | Dòng `-1`: `'Không xác định'` | 1.113 / 92.827 / **2.156** khách. Lưu ý: đây là phân loại theo **toàn bộ lịch sử**; K5 theo kỳ tính từ `fact_sales.purchase_seq` |

### 2.3 `dim_geography`

- **Grain:** một thành phố (đã chuẩn hóa) của một bang – nơi nhận hàng (**4.309 dòng** + 1 dòng `-1`)
- **Model dbt:** `dim_geography`
- **Nguồn:** `staging.customers` (mọi dòng), `seed_brazil_states`
- **Lọc / JOIN / gộp:** `SELECT DISTINCT customer_state, normalize_city(customer_city, customer_state)` trên **mọi** dòng `customers` (mỗi dòng = địa chỉ nhận của 1 đơn) → `LEFT JOIN seed_brazil_states`. Chỉ chứa nơi nhận hàng: thành phố người bán nằm thẳng trong `dim_seller` (dw_design mục 5)
- **Cách nạp:** `incremental`, `unique_key = (state_code, city)`, chỉ thêm thành phố mới xuất hiện ở batch sau; khóa theo R2

| Cột đích | Kiểu | Nguồn | Biến đổi | NULL / lỗi | Ghi chú |
|---|---|---|---|---|---|
| `geography_key` (PK) | INT | (sinh) | R2 – `MAX + ROW_NUMBER() OVER (ORDER BY state_code, city)` cho tổ hợp mới | Dòng `-1` "Không xác định" | |
| `state_code` (NK) | CHAR(2) | `customers.customer_state` | Giữ nguyên | Không NULL ở nguồn; dòng `-1`: NULL | Grain theo (bang, thành phố), **không** theo mã bưu chính: 33 mã bưu chính thuộc hơn 1 bang |
| `city` (NK) | VARCHAR(100) | `customers.customer_city`, `customers.customer_state` | R1 | R1 trả NULL → `'Không xác định'` (0 dòng) | 4.310 → 4.309 tổ hợp sau chuẩn hóa. Fact lookup bằng **đúng** macro này (R5) nên luôn khớp |
| `state_name` | VARCHAR(50) | `seed_brazil_states.state_name` | Lookup theo `state_code` | Không khớp / dòng `-1` → `'Không xác định'` | VD `SP` → `São Paulo` |
| `region` | VARCHAR(30) | `seed_brazil_states.region` | Lookup theo `state_code` | Không khớp / dòng `-1` → `'Không xác định'` | 5 vùng: Norte, Nordeste, Centro-Oeste, Sudeste, Sul – cấp trên cùng để drill-down bản đồ (Q2) |

### 2.4 `dim_product`

- **Grain:** một sản phẩm (**32.951 dòng** + 1 dòng `-1`)
- **Model dbt:** `dim_product` (đọc `stg_products` – nơi đã đổi tên `*_lenght` → `*_length`, chốt 17/10/2026)
- **Nguồn:** `staging.products`, `staging.category_translation`, `seed_category_translation_extra`
- **Lọc / JOIN / gộp:** `products LEFT JOIN (category_translation UNION ALL seed_category_translation_extra) USING (product_category_name)`. Không lọc, không gộp – 1 dòng nguồn = 1 dòng đích
- **Cách nạp:** `table`; khóa `ROW_NUMBER() OVER (ORDER BY product_id)` (R2) – `products` chỉ nạp ở Full Load nên khóa không đổi giữa các lần chạy

| Cột đích | Kiểu | Nguồn | Biến đổi | NULL / lỗi | Ghi chú |
|---|---|---|---|---|---|
| `product_key` (PK) | INT | (sinh) | R2 – `ROW_NUMBER() OVER (ORDER BY product_id)` | Dòng `-1` "Không xác định" | |
| `product_id` (NK) | VARCHAR(32) | `products.product_id` | Giữ nguyên | Không NULL; dòng `-1`: `'-1'` | dbt test `unique` |
| `category_name_pt` | VARCHAR(60) | `products.product_category_name` | Giữ nguyên | NULL → `'unknown'` (610 sản phẩm) | Cấp Danh mục của phân cấp Sản phẩm → Danh mục |
| `category_name_en` | VARCHAR(60) | `category_translation.product_category_name_english`, `seed_category_translation_extra.product_category_name_english` | Lookup theo `product_category_name` | Danh mục NULL → `'unknown'` (610); không có bản dịch → lấy từ seed (13 sản phẩm: `portateis_…` 10, `pc_gamer` 3) | Tên hiển thị trên dashboard (Q2 top 10 danh mục). dbt test `not_null` |
| `weight_g` | INT | `products.product_weight_g` | `NULLIF(product_weight_g, 0)` | `0` → NULL (4 sản phẩm); NULL giữ NULL (2) | Khối lượng 0 g là lỗi nhập liệu, không phải "rất nhẹ" |
| `length_cm` | INT | `products.product_length_cm` | `NULLIF(product_length_cm, 0)` | NULL giữ NULL (2); hiện 0 dòng = 0 | Áp cùng quy tắc với `weight_g` để batch sau có lỗi tương tự vẫn được xử lý |
| `height_cm` | INT | `products.product_height_cm` | `NULLIF(product_height_cm, 0)` | NULL giữ NULL (2); hiện 0 dòng = 0 | |
| `width_cm` | INT | `products.product_width_cm` | `NULLIF(product_width_cm, 0)` | NULL giữ NULL (2); hiện 0 dòng = 0 | |
| `weight_class` | VARCHAR(20) | `products.product_weight_g` | `CASE WHEN weight_g IS NULL THEN 'Không rõ' WHEN weight_g < 500 THEN '< 0,5 kg' WHEN weight_g < 2000 THEN '0,5–2 kg' WHEN weight_g < 5000 THEN '2–5 kg' WHEN weight_g < 10000 THEN '5–10 kg' ELSE '≥ 10 kg' END` (dùng `weight_g` **sau** `NULLIF`) | NULL hoặc 0 → `'Không rõ'` (6 sản phẩm) | Cận dưới thuộc nhóm trên (500 g → `0,5–2 kg`). Phân bố: 12.460 · 12.505 · 3.783 · 2.291 · 1.906 · 6 |
| `photos_qty` | SMALLINT | `products.product_photos_qty` | Ép `::SMALLINT` | NULL giữ NULL (610) | 1–20 ảnh |
| `name_length` | SMALLINT | `products.product_name_lenght` | Đổi tên ở `stg_products` (`product_name_length`) rồi ở đây (`name_length`); ép `::SMALLINT` | NULL giữ NULL (610) | Số **ký tự** của tên (nguồn không có tên thật); tối đa 76 |
| `description_length` | SMALLINT | `products.product_description_lenght` | Đổi tên như trên; ép `::SMALLINT` | NULL giữ NULL (610) | Tối đa 3.992 – vừa `SMALLINT` (≤ 32.767) |

### 2.5 `dim_seller`

- **Grain:** một người bán (**3.095 dòng** + 1 dòng `-1`)
- **Model dbt:** `dim_seller`
- **Nguồn:** `staging.sellers`, `seed_brazil_states`
- **Lọc / JOIN / gộp:** `sellers LEFT JOIN seed_brazil_states ON state_code = seller_state`. 1 dòng nguồn = 1 dòng đích
- **Cách nạp:** `table`; khóa `ROW_NUMBER() OVER (ORDER BY seller_id)` (R2) – `sellers` chỉ nạp ở Full Load

| Cột đích | Kiểu | Nguồn | Biến đổi | NULL / lỗi | Ghi chú |
|---|---|---|---|---|---|
| `seller_key` (PK) | INT | (sinh) | R2 – `ROW_NUMBER() OVER (ORDER BY seller_id)` | Dòng `-1` "Không xác định" | `-1` dùng cho 759 dòng `fact_review` của đơn không có sản phẩm |
| `seller_id` (NK) | VARCHAR(32) | `sellers.seller_id` | Giữ nguyên | Không NULL; dòng `-1`: `'-1'` | dbt test `unique` |
| `seller_city` | VARCHAR(100) | `sellers.seller_city`, `sellers.seller_state` | R1 | R1 trả NULL → `'Không xác định'` (7 dòng: `sp`, email, chuỗi số) | 77 dòng còn gõ sai / viết tắt giữ nguyên – không câu hỏi nào phân tích theo thành phố người bán |
| `seller_state` | CHAR(2) | `sellers.seller_state` | Giữ nguyên | Không NULL; dòng `-1`: NULL | 23 bang. Dùng để suy `route_type` (R9) |
| `seller_region` | VARCHAR(30) | `seed_brazil_states.region` | Lookup theo `seller_state` | Không khớp / dòng `-1` → `'Không xác định'` | |

### 2.6 `dim_delivery_status`

- **Grain:** một tổ hợp trạng thái giao hàng (**672 dòng** = 8 × 4 × 3 × 7)
- **Model dbt:** `dim_delivery_status`
- **Nguồn:** không có – sinh bằng 4 danh sách `VALUES` rồi `CROSS JOIN`
- **Lọc / JOIN / gộp:** tích Descartes đủ mọi tổ hợp để lookup ở fact (R9) **không bao giờ trượt**. Trên dữ liệu thật `fact_delivery` chỉ dùng 47 tổ hợp; các dòng còn lại vô hại (không có fact trỏ tới)
- **Cách nạp:** `table`, SCD Type 0. Khóa = `ROW_NUMBER() OVER (ORDER BY order_status_sort, handover_sort, route_sort, bucket_sort)` theo **thứ tự cố định** của từng danh sách dưới đây → 1…672, như nhau ở mọi lần chạy

Thứ tự các danh sách (cũng là thứ tự số `*_sort`):
- `order_status`: created, approved, invoiced, processing, shipped, delivered, canceled, unavailable
- `handover_status`: Đúng hạn, Trễ hạn, Chưa bàn giao, Không xác định
- `route_type`: Nội bang, Liên bang, Không xác định
- `delay_bucket`: Đúng hạn, Trễ 1–3 ngày, Trễ 4–7 ngày, Trễ 8–14 ngày, Trễ > 14 ngày, Chưa giao, Không xác định

| Cột đích | Kiểu | Nguồn | Biến đổi | NULL / lỗi | Ghi chú |
|---|---|---|---|---|---|
| `delivery_status_key` (PK) | INT | (sinh) | `ROW_NUMBER()` theo thứ tự cố định ở trên | Không có | Không cần `-1`: mọi tổ hợp đều có sẵn |
| `order_status` (NK) | VARCHAR(20) | (sinh) – khớp giá trị `orders.order_status` | Danh sách 8 giá trị | Không có | Trạng thái đơn **tại batch đang nạp** (D8) |
| `handover_status` (NK) | VARCHAR(30) | (sinh) | Danh sách 4 giá trị | Không có | Quy tắc suy ra: R9. Phân bố ở `fact_delivery`: Đúng hạn 89.911 · Trễ hạn 8.913 · Chưa bàn giao 1.010 · Không xác định 176 |
| `route_type` (NK) | VARCHAR(20) | (sinh) | Danh sách 3 giá trị | Không có | R9. `fact_delivery`: Liên bang 64.049 · Nội bang 35.961 |
| `delay_bucket` (NK) | VARCHAR(30) | (sinh) | Danh sách 7 giá trị | Không có | R9. Thứ tự hiển thị làm bằng cột DAX + *Sort by column* trong Power BI (bỏ `delay_bucket_order` – chốt 17/10/2026) |
| `delivery_result` | VARCHAR(30) | (suy ra từ `delay_bucket`) | `CASE WHEN delay_bucket = 'Đúng hạn' THEN 'Đúng hạn' WHEN delay_bucket LIKE 'Trễ%' THEN 'Trễ hạn' ELSE delay_bucket END` | Không có | Cấp cha của `delay_bucket` (4 giá trị). K6 = `Trễ hạn` / (`Đúng hạn` + `Trễ hạn`) theo `order_id` riêng biệt = **6.534 / 96.470 = 6,77%** |

## 3. Fact

### 3.1 `fact_sales`

- **Grain:** một sản phẩm do một người bán bán trong một đơn hàng hợp lệ, gộp các đơn vị cùng sản phẩm (**101.953 dòng**)
- **Model dbt:** `fact_sales`
- **Nguồn:** `staging.order_items`, `staging.orders`, `staging.customers` (qua `int_orders`, `int_purchase_sessions`) + 4 dimension để lấy khóa
- **Lọc / JOIN / gộp:**
  1. `order_items JOIN int_orders USING (order_id) WHERE is_valid` (R4) – loại **549 dòng `order_items`** (= 472 dòng sau gộp) của 467 đơn hủy / hết hàng.
  2. `GROUP BY order_id, product_id, seller_id` – gộp các đơn vị giống nhau thành `quantity`. Trong mỗi nhóm giá, phí ship và hạn bàn giao giống hệt nhau (0 ngoại lệ) nên gộp không mất thông tin; 112.101 đơn vị → 101.953 dòng.
  3. `LEFT JOIN int_purchase_sessions USING (order_id)` → `purchase_seq`; lookup khóa theo R3, R5.
- **Cách nạp:** `table` – dựng lại mỗi lần chạy để đơn bị xóa mềm (R10) biến mất khỏi fact (đổi từ `incremental` ngày 19/10/2026 – xem mục 0.3)

| Cột đích | Kiểu | Nguồn | Biến đổi | NULL / lỗi | Ghi chú |
|---|---|---|---|---|---|
| `order_id` (PK, DD) | VARCHAR(32) | `order_items.order_id` | Giữ nguyên | Không NULL | Degenerate dimension: 87 tổ hợp (khách, ngày, sản phẩm, người bán) xuất hiện ở hơn 1 đơn → cần `order_id` để khóa duy nhất. Đếm K2 bằng `DISTINCTCOUNT(order_id)` |
| `purchase_date_key` (PK, FK) | INT | `orders.order_purchase_timestamp` | R3 | Không NULL ở nguồn | Mọi KPI theo thời gian của trang 1 dùng ngày mua |
| `customer_key` (PK, FK) | INT | `orders.customer_id` → `customers.customer_unique_id` | R5 | Không khớp → `-1` (0 dòng) | K4 = `DISTINCTCOUNT(customer_key)` |
| `geography_key` (PK, FK) | INT | `customers.customer_state`, `customers.customer_city` (của đơn) | R1 + R5 | Không khớp → `-1` (0 dòng) | Vị trí **tại lúc mua** – Q2 bản đồ doanh thu theo bang |
| `product_key` (PK, FK) | INT | `order_items.product_id` | R5 | Không khớp → `-1` (0 dòng) | Q2 top 10 danh mục |
| `seller_key` (PK, FK) | INT | `order_items.seller_id` | R5 | Không khớp → `-1` (0 dòng) | K10, K11, K13, Q6 |
| `purchase_seq` | SMALLINT | `orders.order_purchase_timestamp`, `orders.order_id` (đơn hợp lệ của khách) | R6 – lấy `purchase_seq` của đơn | Không NULL (mọi đơn trong fact đều hợp lệ) | 1…16. K5 trong kỳ = số khách có ≥ 2 giá trị `purchase_seq` khác nhau / K4. Các đơn của cùng 1 giỏ hàng tách đơn có **cùng** `purchase_seq` |
| `quantity` | SMALLINT | `order_items.order_item_id` (đếm dòng) | `COUNT(*)` trong nhóm | Không NULL | 7.049 dòng có `quantity` > 1; `SUM` = 112.101 đơn vị. Measure additive |
| `unit_price` | NUMERIC(10,2) | `order_items.price` | `MAX(price)` trong nhóm | Không NULL ở nguồn | Giá trong nhóm giống nhau 100% → `MAX` = `MIN`; dbt test kiểm `MIN = MAX`. Non-additive: giá bình quân = `SUM(revenue) / SUM(quantity)` |
| `revenue` | NUMERIC(12,2) | `order_items.price` | `SUM(price)` (= `quantity × unit_price`) | Không NULL ở nguồn | **K1**. Không gồm phí ship, không lấy từ `order_payments` (lệch ở 249 đơn). Tổng: 13.494.400,74 BRL cả kỳ; **13.449.529,68 BRL** trong 01/2017 – 08/2018 (khớp dw_design mục 7) |
| `freight_value` | NUMERIC(10,2) | `order_items.freight_value` | `SUM(freight_value)` | Không NULL ở nguồn | Tổng 2.241.126,29 BRL. Additive. Không câu hỏi nào dùng trực tiếp – giữ để mở rộng |

### 3.2 `fact_delivery`

- **Grain:** một lượt bàn giao – giao hàng của một người bán cho một đơn hàng (**100.010 dòng**, 98.666 đơn)
- **Model dbt:** `fact_delivery` (đọc `int_delivery_lines`)
- **Nguồn:** `staging.order_items`, `staging.orders`, `staging.customers`, `staging.sellers`
- **Lọc / JOIN / gộp:**
  1. `order_items GROUP BY order_id, seller_id` → `MAX(shipping_limit_date)` (mỗi cặp chỉ có 1 hạn bàn giao – 0 ngoại lệ).
  2. `JOIN orders` (mốc thời gian, trạng thái), `JOIN customers` (bang khách), `JOIN sellers` (bang người bán).
  3. **Không** lọc theo R4: giữ cả đơn hủy có sản phẩm (461 canceled, 6 unavailable) để theo dõi trạng thái; 775 đơn không có sản phẩm không có người bán bàn giao nên không vào fact.
  4. Tính R7 (measure), R9 (3 thuộc tính) → lookup `delivery_status_key`.
- **Cách nạp:** `table` – dựng lại toàn bộ mỗi lần chạy (accumulating snapshot: dòng của đơn cũ đổi mốc và đổi `delivery_status_key` khi batch sau gửi lại đơn – D8)

> **Measure cấp đơn lặp lại:** `delivered_carrier_date`, `delivered_customer_date` chỉ có ở cấp đơn → `transit_days`, `delivery_days`, `late_days` lặp lại trên mỗi dòng người bán của 1.278 đơn nhiều người bán. KPI K6, K7, M4 phải tính theo **`order_id` riêng biệt**; chỉ `handover_delay_days` và K12 tính theo từng dòng.

| Cột đích | Kiểu | Nguồn | Biến đổi | NULL / lỗi | Ghi chú |
|---|---|---|---|---|---|
| `order_id` (PK, DD) | VARCHAR(32) | `order_items.order_id` | Giữ nguyên | Không NULL | |
| `purchase_date_key` (PK, FK) | INT | `orders.order_purchase_timestamp` | R3 | Không NULL ở nguồn | Q3, Q5 phân tích theo **tháng mua** |
| `customer_key` (PK, FK) | INT | `orders.customer_id` → `customers.customer_unique_id` | R5 | Không khớp → `-1` (0 dòng) | |
| `geography_key` (PK, FK) | INT | `customers.customer_state`, `customers.customer_city` (của đơn) | R1 + R5 | Không khớp → `-1` (0 dòng) | Q3 tỉ lệ giao trễ theo bang nơi nhận |
| `seller_key` (PK, FK) | INT | `order_items.seller_id` | R5 | Không khớp → `-1` (0 dòng) | |
| `delivery_status_key` (PK, FK) | INT | `orders.order_status`, `orders.order_delivered_carrier_date`, `orders.order_delivered_customer_date`, `orders.order_estimated_delivery_date`, `order_items.shipping_limit_date`, `customers.customer_state`, `sellers.seller_state` | R9 → lookup `dim_delivery_status` theo 4 thuộc tính | Luôn khớp (dimension đủ 672 tổ hợp) | Đổi theo batch (VD `shipped / Chưa giao` → `delivered / Trễ 1–3 ngày`) – lý do fact phải `table` |
| `order_purchase_timestamp` | TIMESTAMP | `orders.order_purchase_timestamp` | Giữ nguyên | Không NULL | Mốc đầu của chu trình |
| `order_approved_at` | TIMESTAMP | `orders.order_approved_at` | Giữ nguyên | NULL = chưa duyệt / mốc chưa xảy ra tại cutoff (D8) | Không measure nào dùng – giữ để mô tả đủ chu trình |
| `shipping_limit_date` | TIMESTAMP | `order_items.shipping_limit_date` | `MAX` theo (đơn, người bán) | Không NULL ở nguồn | Hạn bàn giao **của người bán**. Có giá trị bất thường đến 09/04/2020 |
| `delivered_carrier_date` | TIMESTAMP | `orders.order_delivered_carrier_date` | Giữ nguyên | NULL = chưa bàn giao (1.010 dòng) | Cấp đơn – chung cho mọi người bán của đơn |
| `delivered_customer_date` | TIMESTAMP | `orders.order_delivered_customer_date` | Giữ nguyên | NULL = chưa giao | Cấp đơn. 6 đơn `canceled` vẫn có ngày nhận ở nguồn → giữ nguyên ở cột này nhưng **không** tính measure (xem dưới) |
| `estimated_delivery_date` | DATE | `orders.order_estimated_delivery_date` | Giữ nguyên (`DATE`) | Không NULL ở nguồn | Giờ luôn 00:00 → so trễ hạn **theo ngày** (bẫy dữ liệu: so theo giờ ra 8,11% là sai) |
| `handover_delay_days` | NUMERIC(6,2) | `orders.order_delivered_carrier_date`, `order_items.shipping_limit_date` | R7: `delivered_carrier_date − shipping_limit_date` | NULL khi chưa bàn giao (1.010) hoặc ngày bàn giao trước ngày mua (176, `handover_status = 'Không xác định'`) | Dương = bàn giao trễ. Cấp người bán, additive. Từ −1.054 đến +116,8 ngày: giá trị âm rất lớn do `shipping_limit_date` bất thường → dashboard dùng **tỉ lệ** K12 (8.913 / 98.824 = 9,02%), không dùng trung bình |
| `transit_days` | NUMERIC(6,2) | `orders.order_delivered_customer_date`, `orders.order_delivered_carrier_date` | R7: `delivered_customer_date − delivered_carrier_date` | NULL khi đơn khác `delivered`, thiếu 1 mốc, hoặc khách nhận trước ngày bàn giao (23 đơn / 42 dòng) | **M4** (Q5 – khâu vận chuyển). Cấp đơn, semi-additive |
| `delivery_days` | NUMERIC(6,2) | `orders.order_delivered_customer_date`, `orders.order_purchase_timestamp` | R7: `delivered_customer_date − order_purchase_timestamp` | NULL khi đơn khác `delivered` hoặc thiếu ngày nhận | **K7**. Cấp đơn, semi-additive. Tối đa 209,6 ngày. Các tháng 06–08/2018 thấp giả tạo do dữ liệu bị cắt (bẫy #10) |
| `late_days` | SMALLINT | `orders.order_delivered_customer_date`, `orders.order_estimated_delivery_date` | R7: `(delivered_customer_date::DATE − estimated_delivery_date)::SMALLINT` | NULL khi đơn khác `delivered` hoặc thiếu ngày nhận (8 đơn) | Âm = giao sớm (−147 → +188). Là đầu vào của `delay_bucket` (R9). Cấp đơn, semi-additive |

### 3.3 `fact_review`

- **Grain:** một lượt đánh giá của khách cho một đơn hàng, gắn với một người bán của đơn đó (**100.568 dòng** từ 99.224 review)
- **Model dbt:** `fact_review`
- **Nguồn:** `staging.order_reviews`, `staging.order_items`, `staging.orders`, `staging.customers` (qua `int_orders`, `int_delivery_lines`)
- **Lọc / JOIN / gộp:**
  1. `order_reviews LEFT JOIN (SELECT DISTINCT order_id, seller_id FROM order_items) USING (order_id)` – review của đơn nhiều người bán được nhân cho mỗi người bán (Q6 cần điểm theo người bán). 759 dòng của đơn không có sản phẩm không có người bán → `seller_key = -1` (đơn unavailable 591, canceled 162, created 3, invoiced 2, shipped 1).
  2. `LEFT JOIN int_delivery_lines USING (order_id, seller_id)` → `delivery_status_key`. Với 759 dòng không có người bán (không có lượt giao hàng): `order_status` lấy từ đơn, `handover_status = 'Không xác định'`, `route_type = 'Không xác định'`, `delay_bucket = 'Chưa giao'` nếu đơn chưa `delivered`, ngược lại `'Không xác định'` (đơn không có sản phẩm mà ghi đã giao là dữ liệu bất thường). Dữ liệu thật: cả 759 dòng đều `'Chưa giao'` (unavailable 591, canceled 162, created 3, invoiced 2, shipped 1).
  3. `ROW_NUMBER()` theo đơn → `is_latest_review`; lookup ngày (R3), khách và địa lý (R5) qua `int_orders`.
- **Cách nạp:** materialized `table` – dựng lại toàn bộ mỗi lần chạy (đã chốt 18/10/2026: `is_latest_review` của review cũ phải đổi khi review mới đến ở batch sau; `delivery_status_key` thuộc khóa đổi theo batch)

| Cột đích | Kiểu | Nguồn | Biến đổi | NULL / lỗi | Ghi chú |
|---|---|---|---|---|---|
| `review_id` (PK, DD) | VARCHAR(32) | `order_reviews.review_id` | Giữ nguyên | Không NULL | **Không** duy nhất một mình: 789 mã dùng chung cho nhiều đơn (1 khảo sát cho giỏ hàng tách đơn) |
| `order_id` (PK, DD) | VARCHAR(32) | `order_reviews.order_id` | Giữ nguyên | Không NULL | (`review_id`, `order_id`) là khóa thật của nguồn (D1) |
| `purchase_date_key` (PK, FK) | INT | `orders.order_purchase_timestamp` | R3 | Không NULL ở nguồn | Q4: so điểm với tỉ lệ giao trễ **cùng tháng mua** |
| `answer_date_key` (PK, FK) | INT | `order_reviews.review_answer_timestamp` | R3 | Không NULL ở nguồn (0 dòng) | Role-playing `dim_date`: ngày sự kiện đánh giá xảy ra |
| `customer_key` (PK, FK) | INT | `orders.customer_id` → `customers.customer_unique_id` | R5 | Không khớp → `-1` (0 dòng) | |
| `geography_key` (PK, FK) | INT | `customers.customer_state`, `customers.customer_city` (của đơn) | R1 + R5 | Không khớp → `-1` (0 dòng) | |
| `seller_key` (PK, FK) | INT | `order_items.seller_id` (DISTINCT theo đơn) | R5 | Đơn không có sản phẩm → `-1` (759 dòng) | Đánh giá của đơn nhiều người bán tính cho **mọi** người bán của đơn |
| `delivery_status_key` (PK, FK) | INT | `int_delivery_lines` (đơn, người bán); đơn không có người bán: `orders.order_status` | R9 → lookup `dim_delivery_status` | Luôn khớp | Cho phép phân tích điểm theo nhóm số ngày trễ (Q4) và theo người bán bàn giao trễ (Q6) |
| `review_creation_date` | DATE | `order_reviews.review_creation_date` | Giữ nguyên (`DATE`) | Không NULL ở nguồn | 64 review có ngày tạo trước ngày mua (data_profiling #20) – giữ nguyên, không dùng cho KPI |
| `review_answer_timestamp` | TIMESTAMP | `order_reviews.review_answer_timestamp` | Giữ nguyên | Không NULL ở nguồn | Quyết định review vào batch nào (D8) và thứ tự `is_latest_review` |
| `has_comment` | BOOLEAN | `order_reviews.review_comment_title`, `order_reviews.review_comment_message` | R8 trên từng cột → `title_clean IS NOT NULL OR message_clean IS NOT NULL` | Cả hai NULL / giả-NULL → `FALSE` | 42.454 review (42,8%) có bình luận. Nội dung bình luận **không** vào `dds` (mục 4) |
| `is_latest_review` | BOOLEAN | `order_reviews.review_answer_timestamp`, `review_creation_date`, `review_id` | `ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY review_answer_timestamp DESC, review_creation_date DESC, review_id DESC) = 1` – tính trên **review** (trước khi nhân theo người bán) | Không NULL | 98.673 đơn có review → 98.673 review `TRUE`, 551 `FALSE`. Mọi dòng người bán của cùng 1 review có cùng giá trị cờ |
| `review_score` | SMALLINT | `order_reviews.review_score` | Giữ nguyên | Không NULL ở nguồn | dbt test `accepted_values` 1–5. **K8, K9**: lọc `is_latest_review = TRUE` và lấy **1 điểm / `order_id`** (dòng bị nhân theo người bán); Q6: lấy theo `seller_key` |

## 4. Cột nguồn không đưa vào `dds`

| Bảng.cột (staging) | Lý do không dùng |
|---|---|
| `order_payments` (cả bảng) | Không câu hỏi nào dùng thanh toán; doanh thu lấy từ `order_items.price` (dw_design mục 1) |
| `_batch_id`, `_loaded_at` (mọi bảng) | Cột kỹ thuật của lần nạp gần nhất (D8): theo dõi batch đã có `etl_log`, KPI không dùng ([decisions.md](decisions.md), 17/10/2026) |
| `orders._is_deleted`, `orders._deleted_at` | Cột xóa mềm: chỉ dùng để **lọc** ở lớp `stg_` (R10), đơn bị xóa không vào `dds` nên không cần mang cột theo |
| `customers.customer_id` | Mã theo từng đơn, chỉ dùng làm **cầu nối** `orders` → `customer_unique_id` trong dbt; khách thật là `customer_unique_id` (D7) |
| `customers.customer_zip_code_prefix`, `sellers.seller_zip_code_prefix` | Không nạp `geolocation` (chốt 16/10/2026) nên mã bưu chính không nối đi đâu; grain địa lý là (bang, thành phố) vì 33 mã bưu chính thuộc hơn 1 bang |
| `order_items.order_item_id` | Số thứ tự đơn vị trong đơn – mất ý nghĩa sau khi gộp thành `quantity` (grain `fact_sales`) |
| `order_reviews.review_comment_title`, `review_comment_message` | Chỉ giữ cờ `has_comment` (R8). Nội dung tiếng Bồ Đào Nha không phục vụ KPI; nếu phần AI mở rộng (tóm tắt phàn nàn – business_questions mục 8) cần văn bản thì đọc thẳng từ `staging` theo `review_id` |
| `category_translation.*` | Đã gộp vào `dim_product.category_name_en`, không cần bảng riêng |

---

## 5. Kiểm tra sau khi dựng (đề xuất dbt test và đối soát)

Số dòng dự kiến khi `staging` đã nạp đủ 10 batch (bằng số đã kiểm chứng ở trên):

| Bảng | Số dòng | Test chính |
|---|---|---|
| `dim_date` | 1.096 | `unique` + `not_null` `date_key` |
| `dim_customer` | 96.097 (gồm `-1`) | `unique` `customer_unique_id`; `accepted_values` `customer_type` |
| `dim_geography` | 4.310 (gồm `-1`) | `dbt_utils.unique_combination_of_columns` (`state_code`, `city`) |
| `dim_product` | 32.952 (gồm `-1`) | `unique` `product_id`; `not_null` `category_name_en` |
| `dim_seller` | 3.096 (gồm `-1`) | `unique` `seller_id` |
| `dim_delivery_status` | 672 | `unique_combination_of_columns` 4 cột NK |
| `fact_sales` | 101.953 | `unique_combination_of_columns` 6 cột PK; `relationships` mọi FK; `SUM(revenue)` 01/2017 – 08/2018 = 13.449.529,68 |
| `fact_delivery` | 100.010 | `unique_combination_of_columns` 6 cột PK; K6 = 6.534 / 96.470 đơn; K12 = 8.913 / 98.824 dòng |
| `fact_review` | 100.568 | `unique_combination_of_columns` 8 cột PK; `accepted_values` `review_score` 1–5; đúng 98.673 đơn có `is_latest_review = TRUE` |

Test riêng cho xóa mềm (R10 – singular test trong `dbt/tests/`): với mỗi fact, `SELECT f.order_id FROM <fact> f JOIN <staging.orders> o USING (order_id) WHERE o._is_deleted` phải ra **0 dòng**. Dữ liệu thật luôn đạt; có ý nghĩa khi demo xóa đơn.

Đối soát chéo nên chạy (`sql/checks/`): tổng `quantity` của `fact_sales` = số dòng `order_items` của đơn hợp lệ (112.101); số `order_id` riêng biệt của `fact_delivery` = số đơn có sản phẩm (98.666); số `review_id` + `order_id` riêng biệt của `fact_review` = số dòng `order_reviews` (99.224).

---

## 6. Điểm cần nhóm lưu ý (phát hiện khi điền file)

Các điểm dưới đây **không đổi thiết kế**, chỉ là chênh lệch số liệu giữa các tài liệu – cần thống nhất khi viết báo cáo:

| # | Phát hiện | Số liệu | Đề xuất |
|---|---|---|---|
| 1 | Tỉ lệ khách mua lại theo **đơn hợp lệ** thấp hơn số ghi trong tài liệu | Trên đơn hợp lệ (đúng định nghĩa K4, K5): 2.156 / 94.983 khách có đơn hợp lệ = **2,27%**. Số 2.245 = 2,34% ở D7 / CLAUDE.md tính trên **mọi** đơn kể cả đơn hủy | Báo cáo và dashboard dùng 2,27% (số mà `fact_sales` sẽ ra); ghi chú lý do lệch |
| 2 | Mẫu số K12 | Định nghĩa K12 (dw_design mục 7) chỉ lấy `Đúng hạn` + `Trễ hạn` → 8.913 / **98.824** = 9,02%. Câu kiểm chứng cuối dw_design mục 7 ghi 8.913 / 99.000 (gồm cả 176 dòng `Không xác định`) | Sửa câu kiểm chứng thành 98.824; kết luận ≈ 9,0% không đổi |
| 3 | Số dòng có `quantity` > 1 | dw_design mục 2 ghi 7.088 – đó là số nhóm trên **mọi** đơn; trong `fact_sales` (chỉ đơn hợp lệ) là **7.049** | Sửa thành 7.049 hoặc ghi rõ "trên mọi đơn" |
| 4 | "Loại 472 dòng của 467 đơn" (dw_design mục 2) | 472 là số dòng **sau gộp**; tính theo dòng `order_items` là 549 | Ghi rõ đơn vị để người viết dbt test không nhầm |
| 5 | `shipping_limit_date` có giá trị bất thường (đến 2020) | `handover_delay_days` âm tới −1.054 ngày | Dashboard dùng tỉ lệ K12, tránh trung bình `handover_delay_days`; ghi vào phần hạn chế |
| 6 | Tên 2 seed | `seed_brazil_states`, `seed_category_translation_extra` là tên **đề xuất** | **Đã chốt 23/10/2026** khi khởi tạo dbt: giữ nguyên 2 tên (`dbt/seeds/`) |
