# Ánh xạ nguồn → đích (Source-to-Target Mapping)

> **Task:** BS-15 · **Người thực hiện:** Nguyễn Nhựt Thanh · **Trạng thái:** Chưa làm
> Bản tóm tắt theo bảng nằm ở [dw_design.md](dw_design.md) mục 8; file này chi tiết đến **từng cột** của 9 bảng trong `dds`.
> Đây là "công thức" để viết model dbt: nhìn vào bảng là biết mỗi cột lấy từ đâu, biến đổi ra sao, không phải đoán.

---

## Hướng dẫn thực hiện (xóa mục này khi hoàn thành)

### Việc cần làm

1. Đọc các tài liệu tham khảo bên dưới, nắm grain và quy tắc của từng bảng.
2. Điền **mục 1 – Quy tắc dùng chung**: quy tắc nào lặp lại ở nhiều bảng thì chỉ viết một lần ở đây, các bảng sau dẫn chiếu lại (VD: "chuẩn hóa theo R1").
3. Với từng bảng ở **mục 2** (dimension) và **mục 3** (fact):
   - Điền phần **thông tin chung**: model dbt, bảng nguồn, điều kiện lọc / JOIN / GROUP BY để ra đúng grain, cách nạp.
   - Điền **bảng từng cột**. Cột đích và kiểu đã chép sẵn từ sơ đồ [images/dds_schema.drawio](images/dds_schema.drawio), chỉ cần điền 4 cột còn lại.
4. Điền **mục 4**: các cột nguồn không đưa vào `dds` và lý do.
5. Chốt các **điểm còn mở** bên dưới, ghi kết luận vào **mục 5**.
6. Báo nhóm review. Xong thì xóa mục hướng dẫn này và đổi trạng thái ở đầu file.

### Phạm vi

- **Nguồn:** 8 bảng trong schema `staging` (Mage nạp, giữ nguyên tên cột như CSV gốc – kiểu dữ liệu xem [data_dictionary.md](data_dictionary.md)) và các dbt seed (bản dịch danh mục bổ sung, bang → tên bang / vùng).
- **Đích:** 6 dimension + 3 fact trong schema `dds` (dbt tạo).
- Không cần ánh xạ bước CSV → `staging`: bước này giữ nguyên cột và đã mô tả trong `data_dictionary.md`.

### Tài liệu tham khảo

| Tài liệu | Lấy gì |
|---|---|
| [dw_design.md](dw_design.md) | Grain từng fact (mục 2), quy tắc từng dimension (mục 5, đặc biệt bảng quy tắc của `dim_delivery_status`), mô tả cột fact (mục 6), measures (mục 7), bản tóm tắt ánh xạ (mục 8) |
| [data_dictionary.md](data_dictionary.md) | Tên, kiểu và lỗi chất lượng của từng cột nguồn |
| [decisions.md](decisions.md) | D7 (khách hàng theo `customer_unique_id`, gộp các đơn cách nhau ≤ 10 phút thành 1 lần mua), D8 (mốc chưa xảy ra tại cutoff = NULL, đơn cũ được cập nhật ở batch sau) |
| [business_questions.md](business_questions.md) | Định nghĩa "đơn hợp lệ", cách tính KPI |
| [images/dds_schema.drawio](images/dds_schema.drawio) | Danh sách cột đích và kiểu (đã chép vào các bảng dưới) |

### Cách điền một dòng

| Cột | Ghi gì |
|---|---|
| Nguồn | `bảng.cột` ở staging (hoặc `tên_seed.cột`); nhiều cột thì liệt kê đủ. Cột không có nguồn ghi `(sinh)`, VD surrogate key |
| Biến đổi | Mô tả ngắn + biểu thức PostgreSQL khi cần (`CASE`, `COALESCE`, `EXTRACT`…). Không đổi gì thì ghi "Giữ nguyên" |
| NULL / lỗi | Gặp NULL, giá trị sai, lookup không khớp thì xử lý thế nào (`-1`, `'unknown'`, để NULL…) |
| Ghi chú | Bẫy dữ liệu liên quan, số dòng bị ảnh hưởng, dẫn chiếu tài liệu |

**Ví dụ đã điền** (3 dòng lấy từ các bảng khác nhau):

| Cột đích | Kiểu | Nguồn | Biến đổi | NULL / lỗi | Ghi chú |
|---|---|---|---|---|---|
| `dim_product.category_name_pt` | VARCHAR(60) | `products.product_category_name` | Giữ nguyên | NULL → `'unknown'` | 610 sản phẩm thiếu danh mục |
| `dim_product.weight_class` | VARCHAR(20) | `products.product_weight_g` | `CASE`: < 500 g → `< 0,5 kg`; … ; ≥ 10.000 g → `≥ 10 kg` | 0 hoặc NULL → `Không rõ` | Cột suy ra; các nhóm theo dw_design mục 5 |
| `fact_delivery.handover_delay_days` | NUMERIC(6,2) | `orders.order_delivered_carrier_date`, `order_items.shipping_limit_date` | `EXTRACT(EPOCH FROM (carrier − limit)) / 86400`, ép `NUMERIC(6,2)` | Thiếu 1 trong 2 mốc → NULL; mốc sai thứ tự: theo dw_design mục 6 | Dương = bàn giao trễ; `shipping_limit_date` lấy `MAX` theo (đơn, người bán) |

### Điểm còn mở cần chốt khi làm

Tài liệu hiện tại chưa nói rõ hoặc chưa thống nhất ở các điểm dưới đây. Khi làm, đề xuất cách xử lý, hỏi người liên quan, rồi ghi kết luận vào mục 5.

1. ~~**`dim_delivery_status.delay_bucket_order`** có trên sơ đồ nhưng `dw_design.md` mục 5 chưa mô tả~~ → **Đã chốt 17/10/2026**: bỏ cột này khỏi `dds` (đã xóa trên sơ đồ); thứ tự nhóm trễ tạo trong Power BI ([powerbi/README.md](../powerbi/README.md)). Không cần ánh xạ.
2. ~~**Đổi tên `product_name_lenght`, `product_description_lenght` ở lớp nào**~~ → **Đã chốt 17/10/2026**: Mage giữ tên gốc trong schema `staging`; model dbt `stg_products` đổi thành `product_name_length`, `product_description_length`; `dim_product` lấy tiếp thành `name_length`, `description_length`.
3. **Quy tắc chuẩn hóa tên thành phố** phải dùng chung cho `dim_geography`, `dim_customer`, `dim_seller` và bước lookup `geography_key` trong fact; lệch nhau là lookup trượt. `seller_city` bẩn hơn `customer_city` (có dấu, ghép bang `.../sp`, dấu ngoặc – data_dictionary mục 6) nên quy tắc phải xử lý được các trường hợp này.
4. **`dim_customer` lấy thành phố / bang theo "đơn gần nhất"**: gần nhất trong mọi đơn hay chỉ trong các đơn hợp lệ?
5. **`is_latest_review`**: nếu một đơn có 2 review trả lời cùng thời điểm thì chọn review nào? Cần một quy tắc phá hòa để `ROW_NUMBER()` cho cùng kết quả ở mọi lần chạy.
6. ~~**Cột kỹ thuật của staging** (`_batch_id`, `_loaded_at` – D8): có đưa vào `dds` không?~~ → **Đã chốt 17/10/2026**: không đưa (lý do ở bảng cuối `decisions.md`); đã ghi vào mục 4.

### Tiêu chí hoàn thành

- [ ] Cả 9 bảng điền đủ thông tin chung và mọi ô trong bảng từng cột; không còn dòng nào ghi kiểu `bảng.*`.
- [ ] Mọi cột trên sơ đồ đều có trong file này (sơ đồ đổi cột thì cập nhật theo).
- [ ] Mục 1 có đủ quy tắc dùng chung, các bảng dẫn chiếu đúng mã quy tắc.
- [ ] 6 điểm còn mở đã có kết luận ở mục 5.
- [ ] Đã báo nhóm review.

---

## 1. Quy tắc dùng chung

| Mã | Quy tắc | Mô tả / biểu thức | Dùng ở |
|---|---|---|---|
| R1 | Chuẩn hóa tên thành phố | | |
| R2 | Sinh surrogate key và member `-1` "Không xác định" | | |
| R3 | Đổi ngày → `date_key` (`YYYYMMDD`) | | |
| R4 | Đơn hợp lệ | | |
| R5 | Lookup khóa dimension trong fact (khách, địa lý, sản phẩm, người bán) | | |
| … | *(thêm nếu cần)* | | |

## 2. Dimension

### 2.1 `dim_date`

- **Grain:** một ngày dương lịch, 01/01/2016 → 31/12/2018 (dự kiến 1.096 dòng)
- **Model dbt:**
- **Nguồn:**
- **Lọc / JOIN / gộp:**
- **Cách nạp:**

| Cột đích | Kiểu | Nguồn | Biến đổi | NULL / lỗi | Ghi chú |
|---|---|---|---|---|---|
| `date_key` (PK) | INT | | | | |
| `full_date` | DATE | | | | |
| `day_of_month` | SMALLINT | | | | |
| `day_of_week` | SMALLINT | | | | |
| `day_name` | VARCHAR(20) | | | | |
| `is_weekend` | BOOLEAN | | | | |
| `month` | SMALLINT | | | | |
| `month_name` | VARCHAR(20) | | | | |
| `year_month` | INT | | | | |
| `quarter` | SMALLINT | | | | |
| `year` | SMALLINT | | | | |
| `is_analysis_period` | BOOLEAN | | | | |

### 2.2 `dim_customer`

- **Grain:** một khách hàng thực – `customer_unique_id` (dự kiến 96.096 dòng + 1 dòng `-1`)
- **Model dbt:**
- **Nguồn:**
- **Lọc / JOIN / gộp:**
- **Cách nạp:**

| Cột đích | Kiểu | Nguồn | Biến đổi | NULL / lỗi | Ghi chú |
|---|---|---|---|---|---|
| `customer_key` (PK) | INT | | | | |
| `customer_unique_id` (NK) | VARCHAR(32) | | | | |
| `customer_city` | VARCHAR(100) | | | | |
| `customer_state` | CHAR(2) | | | | |
| `customer_region` | VARCHAR(30) | | | | |
| `first_purchase_date` | DATE | | | | |
| `purchase_count` | SMALLINT | | | | |
| `customer_type` | VARCHAR(20) | | | | |

### 2.3 `dim_geography`

- **Grain:** một thành phố (đã chuẩn hóa) của một bang (dự kiến ≈ 4.309 dòng + 1 dòng `-1`)
- **Model dbt:**
- **Nguồn:**
- **Lọc / JOIN / gộp:**
- **Cách nạp:**

| Cột đích | Kiểu | Nguồn | Biến đổi | NULL / lỗi | Ghi chú |
|---|---|---|---|---|---|
| `geography_key` (PK) | INT | | | | |
| `state_code` (NK) | CHAR(2) | | | | |
| `city` (NK) | VARCHAR(100) | | | | |
| `state_name` | VARCHAR(50) | | | | |
| `region` | VARCHAR(30) | | | | |

### 2.4 `dim_product`

- **Grain:** một sản phẩm (dự kiến 32.951 dòng + 1 dòng `-1`)
- **Model dbt:**
- **Nguồn:**
- **Lọc / JOIN / gộp:**
- **Cách nạp:**

| Cột đích | Kiểu | Nguồn | Biến đổi | NULL / lỗi | Ghi chú |
|---|---|---|---|---|---|
| `product_key` (PK) | INT | | | | |
| `product_id` (NK) | VARCHAR(32) | | | | |
| `category_name_pt` | VARCHAR(60) | | | | |
| `category_name_en` | VARCHAR(60) | | | | |
| `weight_g` | INT | | | | |
| `length_cm` | INT | | | | |
| `height_cm` | INT | | | | |
| `width_cm` | INT | | | | |
| `weight_class` | VARCHAR(20) | | | | |
| `photos_qty` | SMALLINT | | | | |
| `name_length` | SMALLINT | | | | |
| `description_length` | SMALLINT | | | | |

### 2.5 `dim_seller`

- **Grain:** một người bán (dự kiến 3.095 dòng + 1 dòng `-1`)
- **Model dbt:**
- **Nguồn:**
- **Lọc / JOIN / gộp:**
- **Cách nạp:**

| Cột đích | Kiểu | Nguồn | Biến đổi | NULL / lỗi | Ghi chú |
|---|---|---|---|---|---|
| `seller_key` (PK) | INT | | | | |
| `seller_id` (NK) | VARCHAR(32) | | | | |
| `seller_city` | VARCHAR(100) | | | | |
| `seller_state` | CHAR(2) | | | | |
| `seller_region` | VARCHAR(30) | | | | |

### 2.6 `dim_delivery_status`

- **Grain:** một tổ hợp trạng thái giao hàng (dự kiến 672 dòng)
- **Model dbt:**
- **Nguồn:**
- **Lọc / JOIN / gộp:**
- **Cách nạp:**

| Cột đích | Kiểu | Nguồn | Biến đổi | NULL / lỗi | Ghi chú |
|---|---|---|---|---|---|
| `delivery_status_key` (PK) | INT | | | | |
| `order_status` (NK) | VARCHAR(20) | | | | |
| `handover_status` (NK) | VARCHAR(30) | | | | |
| `route_type` (NK) | VARCHAR(20) | | | | |
| `delay_bucket` (NK) | VARCHAR(30) | | | | |
| `delivery_result` | VARCHAR(30) | | | | |

## 3. Fact

### 3.1 `fact_sales`

- **Grain:** một sản phẩm do một người bán bán trong một đơn hàng hợp lệ, gộp các đơn vị cùng sản phẩm (dự kiến 101.953 dòng)
- **Model dbt:**
- **Nguồn:**
- **Lọc / JOIN / gộp:**
- **Cách nạp:**

| Cột đích | Kiểu | Nguồn | Biến đổi | NULL / lỗi | Ghi chú |
|---|---|---|---|---|---|
| `order_id` (PK, DD) | VARCHAR(32) | | | | |
| `purchase_date_key` (PK, FK) | INT | | | | |
| `customer_key` (PK, FK) | INT | | | | |
| `geography_key` (PK, FK) | INT | | | | |
| `product_key` (PK, FK) | INT | | | | |
| `seller_key` (PK, FK) | INT | | | | |
| `purchase_seq` | SMALLINT | | | | |
| `quantity` | SMALLINT | | | | |
| `unit_price` | NUMERIC(10,2) | | | | |
| `revenue` | NUMERIC(12,2) | | | | |
| `freight_value` | NUMERIC(10,2) | | | | |

### 3.2 `fact_delivery`

- **Grain:** một lượt bàn giao – giao hàng của một người bán cho một đơn hàng (dự kiến 100.010 dòng)
- **Model dbt:**
- **Nguồn:**
- **Lọc / JOIN / gộp:**
- **Cách nạp:**

| Cột đích | Kiểu | Nguồn | Biến đổi | NULL / lỗi | Ghi chú |
|---|---|---|---|---|---|
| `order_id` (PK, DD) | VARCHAR(32) | | | | |
| `purchase_date_key` (PK, FK) | INT | | | | |
| `customer_key` (PK, FK) | INT | | | | |
| `geography_key` (PK, FK) | INT | | | | |
| `seller_key` (PK, FK) | INT | | | | |
| `delivery_status_key` (PK, FK) | INT | | | | |
| `order_purchase_timestamp` | TIMESTAMP | | | | |
| `order_approved_at` | TIMESTAMP | | | | |
| `shipping_limit_date` | TIMESTAMP | | | | |
| `delivered_carrier_date` | TIMESTAMP | | | | |
| `delivered_customer_date` | TIMESTAMP | | | | |
| `estimated_delivery_date` | DATE | | | | |
| `handover_delay_days` | NUMERIC(6,2) | | | | |
| `transit_days` | NUMERIC(6,2) | | | | |
| `delivery_days` | NUMERIC(6,2) | | | | |
| `late_days` | SMALLINT | | | | |

### 3.3 `fact_review`

- **Grain:** một lượt đánh giá của khách cho một đơn hàng, gắn với một người bán của đơn đó (dự kiến 100.568 dòng)
- **Model dbt:**
- **Nguồn:**
- **Lọc / JOIN / gộp:**
- **Cách nạp:**

| Cột đích | Kiểu | Nguồn | Biến đổi | NULL / lỗi | Ghi chú |
|---|---|---|---|---|---|
| `review_id` (PK, DD) | VARCHAR(32) | | | | |
| `order_id` (PK, DD) | VARCHAR(32) | | | | |
| `purchase_date_key` (PK, FK) | INT | | | | |
| `answer_date_key` (PK, FK) | INT | | | | |
| `customer_key` (PK, FK) | INT | | | | |
| `geography_key` (PK, FK) | INT | | | | |
| `seller_key` (PK, FK) | INT | | | | |
| `delivery_status_key` (PK, FK) | INT | | | | |
| `review_creation_date` | DATE | | | | |
| `review_answer_timestamp` | TIMESTAMP | | | | |
| `has_comment` | BOOLEAN | | | | |
| `is_latest_review` | BOOLEAN | | | | |
| `review_score` | SMALLINT | | | | |

## 4. Cột nguồn không đưa vào `dds`

| Bảng.cột (staging) | Lý do không dùng |
|---|---|
| `order_payments` (cả bảng) | Không câu hỏi nào dùng thanh toán; doanh thu lấy từ `order_items.price` (dw_design mục 1) |
| `_batch_id`, `_loaded_at` (mọi bảng) | Cột kỹ thuật của lần nạp gần nhất (D8): theo dõi batch đã có `etl_log`, KPI không dùng ([decisions.md](decisions.md), 17/10/2026) |
| | |
| | |

## 5. Kết luận các điểm còn mở

| # | Điểm | Kết luận | Người chốt · ngày |
|---|---|---|---|
| 1 | Ý nghĩa và cách tính `delay_bucket_order` | Bỏ khỏi `dds`. Thứ tự hiển thị của `delay_bucket` tạo bằng cột tính toán DAX trong Power BI + *Sort by column* ([powerbi/README.md](../powerbi/README.md)) | Trúc Hằng · 17/10/2026 |
| 2 | Đổi tên cột `*_lenght` ở lớp nào | Ở model dbt `stg_products` (`*_lenght` → `*_length`). Schema `staging` do Mage nạp giữ tên gốc để đối soát với CSV; `dim_product` đổi tiếp thành `name_length`, `description_length` | Trúc Hằng · 17/10/2026 |
| 3 | Quy tắc chuẩn hóa tên thành phố dùng chung | | |
| 4 | "Đơn gần nhất" của `dim_customer` tính trên đơn nào | | |
| 5 | Quy tắc phá hòa cho `is_latest_review` | | |
| 6 | Cột kỹ thuật `_batch_id`, `_loaded_at` có vào `dds` không | Không – dừng ở `staging`; theo dõi batch dùng `etl_log`, LSET/CET lưu ở metadata | Trúc Hằng · 17/10/2026 |
