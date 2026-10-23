# Quy tắc xây dựng model dbt – staging, intermediate, dimension, fact

> **Dành cho người làm BS-28 → BS-31 (Nhựt Thanh).** Đọc **Phần A** để biết việc cần làm, thứ tự làm và khi nào coi là xong; mở **Phần B** khi viết code; viết báo cáo mục 6.2 theo **B9**.
> File này **không chép lại công thức từng cột**: công thức nằm ở [source_to_target_mapping.md](source_to_target_mapping.md) (quy tắc R1–R10, 9 bảng đích). File này nói **cách làm trong dbt**: quy ước, mẫu code, cách kiểm tra, số liệu nghiệm thu.
> Nếu thấy mâu thuẫn: [decisions.md](decisions.md) là gốc, sau đó đến `source_to_target_mapping.md` – báo nhóm để sửa.
> **[Bắt buộc]** = nhóm đã chốt, muốn làm khác phải bàn lại · **[Gợi ý]** = cách đề xuất, làm khác được nếu ra cùng kết quả.
> Mọi mẫu code trong file **đã chạy thử** trên dữ liệu thật (DB tạm, nạp bằng pipeline Mage, 23/10/2026).
> Cập nhật: 23/10/2026.

---

# Phần A – Nhiệm vụ

## A1. dbt nằm ở đâu

Mage là khâu *đi chợ và sơ chế* (đưa dữ liệu vào `staging`); dbt là khâu *nấu*: biến đổi dữ liệu **bên trong** database thành kho `dds` – *tủ đồ ăn bày sẵn* cho Power BI.

```
staging (Mage nạp, 8 bảng)
   │  source()
   ▼
stg_          view,  schema dbt_stg   1 model / 1 bảng: chọn cột, đổi tên, bỏ đơn đã xóa mềm (R10)    ← BS-28
   │  ref()
   ▼
int_          view,  schema dbt_int   phép tính dùng chung: int_orders, int_purchase_sessions,        ← BS-29
   │                                  int_delivery_lines (+ macro normalize_city)
   ▼
dim_ / fact_  bảng,  schema dds       6 dimension + 3 fact – Power BI chỉ đọc schema này              ← BS-30, BS-31

seed (dbt_stg) ──► dim_        dbt test ──► dq (dòng vi phạm, store_failures)
```

**Đã có sẵn – không phải làm** (khởi tạo 23/10/2026, chi tiết [dbt/README.md](../dbt/README.md)):

| Thứ | Ở đâu | Ghi chú |
|---|---|---|
| Project dbt | `dbt/dbt_project.yml` | Tên `olist_dw`; schema + materialization của từng tầng đã cấu hình theo thư mục |
| Kết nối | `dbt/profiles.yml.example` | Copy thành `profiles.yml` (A3), đọc `POSTGRES_*` từ `.env` |
| Macro `generate_schema_name` | `dbt/macros/` | Model vào đúng schema `dbt_stg` / `dbt_int` / `dds` |
| Nguồn | `dbt/models/staging/_sources.yml` | 8 bảng `staging` + 8 test (6 khóa ngoại D2, mã bang khớp seed) |
| Seed | `dbt/seeds/` | `seed_brazil_states` (27 dòng), `seed_category_translation_extra` (2 dòng) + test |
| Package | `dbt/packages.yml` | `dbt_utils` 1.3.x |
| Công thức từng cột | [source_to_target_mapping.md](source_to_target_mapping.md) | Thanh viết (BS-15) |

## A2. Bốn task và kết quả cần nộp

| Task | Làm gì | Kết quả nộp | Quy tắc |
|---|---|---|---|
| **BS-28** Models tầng staging | 8 view `stg_` | 8 file `.sql` + `models/staging/_stg_models.yml`; số dòng = `staging` (khi chưa xóa đơn nào); test đạt | B1, B2 |
| **BS-29** Models tầng intermediate | Macro `normalize_city` (R1) + 3 view `int_` | `macros/normalize_city.sql` + test ví dụ R1; 3 file `.sql` + `models/intermediate/_int_models.yml` | B3 |
| **BS-30** Models Dimension | 6 `dim_` | 6 file + `models/marts/_dim_models.yml`; số dòng khớp B6; khóa không đổi qua các batch (B4.2) | B4 |
| **BS-31** Model Fact | 3 `fact_` + singular test xóa mềm | 3 file + `models/marts/_fact_models.yml` + `tests/`; số liệu đối soát khớp B6 | B5 |

## A3. Chuẩn bị máy (làm 1 lần)

Mỗi máy có Postgres riêng, nên phải tự nạp `staging` trước khi chạy dbt:

```powershell
git pull
docker compose up -d                                   # tạo lại container Mage để nhận biến DBT_* mới trong compose.yaml
Copy-Item dbt\profiles.yml.example dbt\profiles.yml
docker compose exec mage dbt deps                      # cài dbt_utils
docker compose exec mage dbt debug                     # phải ra: All checks passed!

# Nạp staging (bỏ dòng đầu nếu đã có data/batches – dòng cuối của script phải là TẤT CẢ ĐẠT (9/9 PASS))
docker compose exec mage python scripts/split_batches.py
docker compose exec mage mage run /home/src/mage/olist_etl full_load
1..9 | ForEach-Object { docker compose exec mage mage run /home/src/mage/olist_etl incremental_load }
```

- Có thể nạp bằng giao diện Mage thay cho 2 lệnh cuối: **Triggers → Run@once** ([setup_guide.md](setup_guide.md) mục 6.2).
- Kiểm tra: câu Q5 trong [`sql/checks/01_pipeline_demo.sql`](../sql/checks/01_pipeline_demo.sql) → `orders` 99.441 · `order_items` 112.650 · … (số mong đợi ghi sẵn trong file).
- Rồi chạy `docker compose exec mage dbt build` → `PASS=16` (2 seed + 14 test). Dòng `[WARNING]: … There are 3 unused configuration paths` là **bình thường** khi chưa có model, tự hết khi mỗi thư mục có model.

## A4. Thứ tự làm [Gợi ý]

BS-28 → BS-29 → BS-30 → BS-31 (đúng chiều phụ thuộc). Trong BS-30: `dim_date`, `dim_delivery_status` (tự sinh, không cần nguồn) → `dim_product`, `dim_seller` → `dim_geography` → `dim_customer` (cần `int_` và `normalize_city`).

Vòng làm 1 model:

1. Viết file `.sql` theo bảng tương ứng trong `source_to_target_mapping.md`.
2. `docker compose exec mage dbt build --select <tên_model>` – dựng model và chạy test của nó.
3. Xem dữ liệu bằng DBeaver ở schema `dbt_stg` / `dbt_int` / `dds` (bấm F5 nếu chưa thấy schema mới); so số dòng với **B6**.
4. Viết mô tả + test vào file yml của task → build lại.
5. Commit (B8).

## A5. Khi nào coi là xong

- `docker compose exec mage dbt build` cả project: `ERROR=0` (không test nào FAIL).
- Số dòng và số liệu đối soát khớp **B6**; chạy đạt các kịch bản **B7**.
- Điền `dbt/README.md` mục 5, 6; xuất ảnh lineage `docs/images/dbt_lineage.png`; viết báo cáo mục 6.2 theo **B9**.

---

# Phần B – Quy tắc chi tiết

## B1. Quy ước chung [Bắt buộc]

| Quy ước | Nội dung |
|---|---|
| Tên model | `stg_<tên bảng staging>`; `int_` đúng 3 tên ở mapping mục 0.1; `dim_` / `fact_` đúng tên trong [dw_design.md](dw_design.md). Tên file `.sql` = tên model |
| Đọc dữ liệu | **Chỉ** model `stg_` dùng `{{ source('staging', '<bảng>') }}`; mọi model khác dùng `{{ ref('<model hoặc seed>') }}`. **Không** gõ thẳng tên schema (`staging.orders`, `dds.dim_date`) trong model: dbt mất dấu phụ thuộc → chạy sai thứ tự, lineage thiếu |
| Không tự sửa | Bảng / cột `staging`, pipeline Mage, phần cấu hình schema trong `dbt_project.yml`, `profiles.yml.example`. Cần đổi → báo nhóm |
| Materialization | Không khai lại trong model (đã cấu hình theo thư mục) – **trừ** `dim_customer`, `dim_geography`: `incremental` (B4.2) |
| Kiểu dữ liệu | Cột trong `dds` đúng kiểu ghi ở mapping; ép tường minh ở `select` cuối (`::int`, `::smallint`, `::numeric(12,2)`). Cú pháp PostgreSQL |
| Khóa | Surrogate key là số nguyên theo R2 (`row_number()` / cấp nối tiếp) – **không** dùng `dbt_utils.generate_surrogate_key` (sinh chuỗi MD5) |
| Lookup khóa trong fact | `left join` dimension + `coalesce(<khóa>, -1)` (R5) – **không** `inner join` (mất dòng fact mà không báo lỗi) |
| Viết SQL | Mỗi bước 1 CTE (`with … as (…)`), tên CTE nói lên việc nó làm; liệt kê cột ở `select` cuối (không `select *` ở model trong `dds`); chú thích tiếng Việt kèm mã quy tắc (`-- R6: gộp giỏ hàng tách đơn`) |
| Tài liệu | Mỗi task 1 file yml cạnh model (tên ở A2): mô tả model (grain, nguồn), mô tả **mọi** cột bằng tiếng Việt, khai báo test. dbt docs (Metadata) lấy nội dung từ đây |

## B2. Tầng staging – BS-28

8 model: `stg_orders`, `stg_order_items`, `stg_order_payments`, `stg_order_reviews`, `stg_customers`, `stg_sellers`, `stg_products`, `stg_category_translation`. `stg_order_payments` chưa bảng `dds` nào dùng (mapping mục 4) nhưng vẫn làm cho đủ tầng – R10 có nhắc.

**Việc của `stg_`** [Bắt buộc]:

- Chọn cột; **bỏ** cột kỹ thuật `_batch_id`, `_loaded_at`, `_is_deleted`, `_deleted_at` (mapping mục 4).
- `stg_products`: đổi `product_name_lenght` → `product_name_length`, `product_description_lenght` → `product_description_length` (chốt 17/10/2026).
- Xóa mềm (R10): `stg_orders` bỏ đơn có `_is_deleted`; 3 bảng con (`order_items`, `order_payments`, `order_reviews`) chỉ giữ dòng của đơn còn trong `stg_orders`; `stg_customers` **không** lọc (dimension giữ thành viên).
- Ép kiểu / `TRIM`: chỉ khi bảng ánh xạ ghi – Mage đã ép đúng kiểu lúc nạp (`sql/init/01_staging_tables.sql`). Làm sạch thành phố (R1), bình luận (R8) đặt ở model dùng nó, để `stg_` vẫn đối chiếu 1–1 được với `staging`.

Mẫu `stg_orders` – 7 model còn lại viết cùng khuôn:

```sql
-- stg_orders: 1 dòng / đơn hàng chưa bị xóa ở nguồn (R10).
-- staging đã đúng kiểu dữ liệu (Mage ép kiểu lúc nạp) -> chọn cột cần dùng, bỏ cột kỹ thuật _batch_id, _loaded_at.
select
    order_id,
    customer_id,
    order_status,
    order_purchase_timestamp,
    order_approved_at,
    order_delivered_carrier_date,
    order_delivered_customer_date,
    order_estimated_delivery_date
from {{ source('staging', 'orders') }}
where not _is_deleted
```

Mẫu bảng con – lọc theo `stg_orders` để quy tắc xóa mềm chỉ viết ở **một** chỗ:

```sql
-- Bảng con: chỉ giữ dòng của đơn còn trong stg_orders -> quy tắc xóa mềm (R10) chỉ viết ở 1 chỗ.
select
    oi.order_id,
    oi.order_item_id,
    oi.product_id,
    oi.seller_id,
    oi.shipping_limit_date,
    oi.price,
    oi.freight_value
from {{ source('staging', 'order_items') }} as oi
where oi.order_id in (select order_id from {{ ref('stg_orders') }})
```

Test gợi ý trong `_stg_models.yml` [Gợi ý] – giá trị lấy từ [data_dictionary.md](data_dictionary.md). Khóa chính không cần test lại: `staging` đã có ràng buộc `PRIMARY KEY`, view lọc bớt dòng không làm trùng khóa.

```yaml
version: 2
models:
  - name: stg_orders
    description: 1 dòng = 1 đơn hàng chưa bị xóa ở nguồn (R10).
    columns:
      - name: order_status
        description: Trạng thái đơn tại batch đã nạp gần nhất (D8).
        data_tests:
          - accepted_values:
              values: ['created', 'approved', 'invoiced', 'processing', 'shipped', 'delivered', 'canceled', 'unavailable']
  - name: stg_order_payments
    columns:
      - name: payment_type
        data_tests:
          - accepted_values:
              values: ['credit_card', 'boleto', 'voucher', 'debit_card', 'not_defined']
  - name: stg_order_reviews
    columns:
      - name: review_score
        data_tests:
          - accepted_values:
              values: [1, 2, 3, 4, 5]
              quote: false        # cột số: so sánh không đặt trong ngoặc kép
```

## B3. Tầng intermediate – BS-29

| Model | Grain (1 dòng =) | Nội dung | Quy tắc |
|---|---|---|---|
| `int_orders` | 1 đơn – 99.441 dòng | `customer_unique_id`, bang + thành phố nơi nhận đã chuẩn hóa, `is_valid` | R1, R4 |
| `int_purchase_sessions` | 1 đơn hợp lệ – 98.199 dòng | `purchase_seq` | R6 |
| `int_delivery_lines` | 1 cặp (đơn, người bán) – 100.010 dòng | mốc thời gian, 4 measure số ngày, `handover_status`, `route_type`, `delay_bucket` | R7, R9 |

Cột cụ thể: lấy đủ những gì dimension / fact phía sau cần (mapping mục 0.1, 2, 3).

**Macro `normalize_city`** (R1) – file `macros/normalize_city.sql`. Macro trả về **một biểu thức SQL** (không phải câu `select`), gọi trong model như một hàm: `{{ normalize_city('customer_city', 'customer_state') }}`.

```sql
{#- R1 (source_to_target_mapping.md mục 1): chuẩn hóa tên thành phố, 7 bước B1 -> B7.
    Gọi trong model: {{ normalize_city('customer_city', 'customer_state') }} -#}
{% macro normalize_city(city, state) -%}
    ( ...biểu thức 7 bước; tham chiếu cột bằng {{ city }}, {{ state }}; bỏ dấu bằng unaccent() có sẵn trong DB... )
{%- endmacro %}
```

⚠ Chú thích bên trong macro / model phải dùng `{# … #}` (chú thích Jinja). Viết `{{ normalize_city(...) }}` sau dấu `--` thì dbt **vẫn chạy** đoạn đó.

Kiểm tra macro bằng **singular test dạng bảng ví dụ** – file `tests/test_normalize_city.sql`, mỗi dòng 1 ví dụ của R1, trả về ví dụ sai, 0 dòng = đạt (khuôn đã chạy thử: ví dụ sai hiện cả cột mong đợi lẫn kết quả thật trong bảng `dq.test_normalize_city`):

```sql
-- Mỗi dòng 1 ví dụ của R1: (giá trị gốc, mã bang, kết quả mong đợi). Trả về ví dụ SAI -> 0 dòng = đạt.
with cases (city, state, expected) as (
    values
        ('São Paulo',                       'SP', 'sao paulo'),         -- B1 bỏ dấu, chữ thường
        ('maua/sao paulo',                  'SP', 'maua'),              -- B2
        ('arraial d''ajuda (porto seguro)', 'BA', 'arraial d''ajuda'),  -- B3
        ('mogi-mirim',                      'SP', 'mogi mirim'),        -- B4
        ('  sao   paulo ',                  'SP', 'sao paulo'),         -- B5
        ('sao paulo - sp',                  'SP', 'sao paulo'),         -- B6
        ('sp',                              'SP', null),                -- B7
        ('loja@email.com',                  'SP', null),                -- B7
        ('04482255',                        'SP', null),                -- B7
        ('rio de janeiro',                  'RJ', 'rio de janeiro')     -- trùng tên bang nhưng là thành phố thật
)
select city, state, expected, {{ normalize_city('city', 'state') }} as actual
from cases
where {{ normalize_city('city', 'state') }} is distinct from expected
```

Kết quả đúng trên dữ liệu thật (R1): khách 4.309 tổ hợp (bang, thành phố), 0 NULL; người bán 636 → 610 giá trị, 7 dòng NULL.

Test gợi ý: `unique` `order_id` của `int_orders`, `int_purchase_sessions`; `dbt_utils.unique_combination_of_columns` (`order_id`, `seller_id`) của `int_delivery_lines`; `accepted_values` cho `handover_status` (4 giá trị), `route_type` (3), `delay_bucket` (7) – chép **đúng chuỗi** ở mapping mục 2.6 (có dấu tiếng Việt, gạch `–`).

## B4. Dimension – BS-30

### B4.1 Khóa và member `-1` (R2) [Bắt buộc]

| Loại | Dimension | Cách sinh khóa |
|---|---|---|
| Sinh tĩnh | `dim_date` | `date_key` = `YYYYMMDD` (R3), không có `-1` |
| | `dim_delivery_status` | `row_number()` theo thứ tự cố định của 4 danh sách (mapping 2.6), không có `-1` |
| Dựng lại toàn bộ (`table`) | `dim_product`, `dim_seller` | `row_number() over (order by <khóa tự nhiên>)` + `union all` dòng `-1` |
| `incremental` | `dim_geography`, `dim_customer` | Mẫu ở B4.2 |

Dòng `-1` "Không xác định": khóa `-1`; khóa tự nhiên `'-1'` (`customer_unique_id`, `product_id`, `seller_id`) – riêng `dim_geography`: `state_code` NULL, `city` `'Không xác định'`; thuộc tính chữ `'Không xác định'`, số / ngày NULL (giá trị cụ thể ghi ở từng bảng trong mapping).

### B4.2 Dimension incremental: khóa không đổi qua các batch [Bắt buộc phần kết quả, Gợi ý phần code]

Mỗi lần Mage nạp thêm batch rồi chạy `dbt build`: thực thể **đã có giữ khóa cũ**, thực thể mới nhận khóa **nối tiếp** (R2). Hai mẫu dưới đây đã chạy thử qua batch FULL → 2018-01: 0 dòng cũ đổi khóa, khóa mới nối tiếp liền mạch, đúng 1 dòng `-1`, 141 khách cũ được cập nhật thuộc tính – bằng đúng số "khách quay lại" của batch 2018-01 ở D7. Build lại khi dữ liệu không đổi: `dim_geography` báo `INSERT 0 0`.

**Mẫu 1 – chỉ thêm dòng mới** (`dim_geography`):

```sql
{{ config(materialized='incremental', unique_key=['state_code', 'city']) }}

with src as (                                   -- tổ hợp (bang, thành phố) đang có trong dữ liệu
    select distinct
        customer_state as state_code,
        coalesce({{ normalize_city('customer_city', 'customer_state') }}, 'Không xác định') as city
    from {{ ref('stg_customers') }}
),

new_rows as (                                   -- lần đầu: mọi tổ hợp; các lần sau: tổ hợp chưa có trong bảng
    select s.state_code, s.city
    from src as s
    {% if is_incremental() %}
    where not exists (
        select 1 from {{ this }} as t
        where t.state_code = s.state_code and t.city = s.city
    )
    {% endif %}
)

select
    ({% if is_incremental() %}(select greatest(max(geography_key), 0) from {{ this }}){% else %}0{% endif %}
        + row_number() over (order by state_code, city))::int as geography_key,   -- khóa mới nối tiếp khóa cũ
    state_code,
    city
from new_rows
{% if not is_incremental() %}
union all
select -1, null, 'Không xác định'               -- member -1: chỉ thêm ở lần chạy đầu
{% endif %}
```

Bản thật thêm `state_name`, `region` bằng `left join` tới `{{ ref('seed_brazil_states') }}` (mapping 2.3).

**Mẫu 2 – SCD 1: ghi đè thuộc tính, giữ khóa** (`dim_customer`):

```sql
{{ config(materialized='incremental', unique_key='customer_unique_id') }}

with src as (            -- thuộc tính MỚI NHẤT của MỌI khách, tính lại từ toàn bộ dữ liệu mỗi lần chạy (mapping 2.2)
    select customer_unique_id, customer_city   -- , các cột còn lại
    from ...
),

keyed as (               -- khách đã có trong bảng thì lấy lại khóa cũ
    select
        s.*,
        {% if is_incremental() %} t.customer_key {% else %} null::int {% endif %} as old_key
    from src as s
    {% if is_incremental() %}
    left join {{ this }} as t using (customer_unique_id)
    {% endif %}
)

select
    coalesce(
        old_key,         -- khách cũ giữ khóa; khách mới: khóa lớn nhất + thứ tự trong nhóm khách mới
        {% if is_incremental() %}(select greatest(max(customer_key), 0) from {{ this }}){% else %}0{% endif %}
            + row_number() over (partition by old_key is null order by customer_unique_id)
    )::int as customer_key,
    customer_unique_id,
    customer_city        -- , các cột còn lại
from keyed
{% if not is_incremental() %}
union all
select -1, '-1', 'Không xác định'               -- member -1: thêm đủ cột theo mapping 2.2
{% endif %}
```

Vì sao chạy đúng:

- `{{ this }}` là chính bảng đang dựng; `is_incremental()` đúng khi bảng đã có và **không** chạy `--full-refresh`.
- Mẫu 2 trả về **mọi** khách. dbt (`delete+insert` theo `unique_key`) xóa dòng của các khách đó rồi chèn lại → thuộc tính được ghi đè (SCD 1); khóa lấy từ `{{ this }}` nên không đổi. Dòng `-1` không nằm trong kết quả các lần sau nên không bị đụng.
- `greatest(max(…), 0)`: lỡ build khi `staging` còn trống thì bảng chỉ có dòng `-1` – khóa mới vẫn bắt đầu từ 1.
- `coalesce(…, 'Không xác định')` ở mẫu 1: NULL không so bằng được, để NULL thì mỗi lần build lại chèn trùng.
- Sau khi chạy lại Full Load: `dbt build --full-refresh` → bảng dựng lại từ đầu, khóa đánh lại 1…n. 3 fact là `table` dựng lại cùng lần chạy nên vẫn khớp.
- Không đổi `order by` trong `row_number()` giữa các lần chạy.

### B4.3 Test dimension

Theo mapping mục 5, cộng thêm: `unique` + `not_null` cho mọi `*_key` và khóa tự nhiên; `accepted_values` `customer_type`: `'Chưa có đơn hợp lệ'`, `'Mua một lần'`, `'Mua lại'`, `'Không xác định'`.

## B5. Fact – BS-31

- Cả 3 fact là `table` (đã cấu hình): dựng lại mỗi lần chạy để đơn bị xóa mềm biến mất và `delivery_status_key`, `is_latest_review` cập nhật theo batch (mapping 0.3).
- Grain, cột, cách tính: mapping mục 3. Khóa ngày: R3 `to_char(<cột>, 'YYYYMMDD')::int` – không có `-1`, test `not_null` + `relationships` tới `dim_date`.
- **Bẫy fan-out** [Bắt buộc]: không `SUM` sau khi nối `order_items` × `order_payments` / `order_reviews`. Doanh thu chỉ từ `order_items.price`; review nhân theo người bán chỉ ở `fact_review` (K8, K9 lấy 1 điểm / đơn qua `is_latest_review`). Measure cấp đơn lặp lại ở `fact_delivery` (K6, K7, M4 tính theo `order_id` riêng biệt) → ghi rõ trong mô tả cột để người làm Power BI biết.
- Test [Bắt buộc]: `dbt_utils.unique_combination_of_columns` với **đúng** các cột khóa (mapping mục 3: `fact_sales` 6 cột, `fact_delivery` 6, `fact_review` 8); `relationships` cho mọi khóa ngoại tới dimension; `accepted_values` `review_score` 1–5 (`quote: false`); `unit_price` MIN = MAX trong nhóm (mapping 3.1).

Mẫu khai báo trong `_fact_models.yml`:

```yaml
version: 2
models:
  - name: fact_sales
    description: 1 dòng = 1 sản phẩm của 1 người bán trong 1 đơn hợp lệ, gộp các đơn vị cùng sản phẩm (quantity).
    data_tests:
      - dbt_utils.unique_combination_of_columns:
          combination_of_columns: [order_id, purchase_date_key, customer_key, geography_key, product_key, seller_key]
    columns:
      - name: customer_key
        description: Khách hàng (customer_unique_id) - R5, không khớp thì -1.
        data_tests:
          - not_null
          - relationships:
              to: ref('dim_customer')
              field: customer_key
```

**Singular test xóa mềm** (R10) – file `tests/assert_no_deleted_orders_in_facts.sql` (khuôn đã chạy thử: đạt khi đã lọc ở `stg_`; quên lọc thì bắt được dòng vi phạm):

```sql
-- Đơn đã xóa mềm ở staging không được còn trong fact. 0 dòng = đạt.
select 'fact_sales' as fact_name, f.order_id
from {{ ref('fact_sales') }} as f
join {{ source('staging', 'orders') }} as o using (order_id)
where o._is_deleted
union all
select 'fact_delivery', f.order_id
from {{ ref('fact_delivery') }} as f
join {{ source('staging', 'orders') }} as o using (order_id)
where o._is_deleted
union all
select 'fact_review', f.order_id
from {{ ref('fact_review') }} as f
join {{ source('staging', 'orders') }} as o using (order_id)
where o._is_deleted
```

## B6. Số liệu nghiệm thu

Khi `staging` đã nạp đủ 10 batch và **không** xóa đơn nào. Số lấy từ mapping (mục 2, 3, 5) và D1 – đã kiểm chứng trên CSV gốc.

| Model | Số dòng | | Model | Số dòng |
|---|---|---|---|---|
| `stg_orders` | 99.441 | | `int_orders` | 99.441 (`is_valid` = TRUE: 98.199) |
| `stg_order_items` | 112.650 | | `int_purchase_sessions` | 98.199 |
| `stg_order_payments` | 103.886 | | `int_delivery_lines` | 100.010 (98.666 đơn) |
| `stg_order_reviews` | 99.224 | | `dim_date` | 1.096 |
| `stg_customers` | 99.441 | | `dim_customer` | 96.097 (gồm `-1`) |
| `stg_sellers` | 3.095 | | `dim_geography` | 4.310 (gồm `-1`) |
| `stg_products` | 32.951 | | `dim_product` | 32.952 (gồm `-1`) |
| `stg_category_translation` | 71 | | `dim_seller` | 3.096 (gồm `-1`) |
| | | | `dim_delivery_status` | 672 |
| | | | `fact_sales` | 101.953 |
| | | | `fact_delivery` | 100.010 |
| | | | `fact_review` | 100.568 |

Đối soát:

| Kiểm tra | Mong đợi |
|---|---|
| `SUM(fact_sales.quantity)` | 112.101; 7.049 dòng có `quantity` > 1 |
| `SUM(fact_sales.revenue)` cả kỳ / 01/2017 – 08/2018 | 13.494.400,74 / **13.449.529,68** BRL |
| `SUM(fact_sales.freight_value)` | 2.241.126,29 BRL |
| Số `order_id` riêng biệt của `fact_delivery` | 98.666 |
| `handover_status` ở `fact_delivery` | Đúng hạn 89.911 · Trễ hạn 8.913 · Chưa bàn giao 1.010 · Không xác định 176 |
| `route_type` ở `fact_delivery` | Liên bang 64.049 · Nội bang 35.961 |
| K6 (theo `order_id` riêng biệt) | 6.534 / 96.470 = 6,77% |
| K12 (theo dòng) | 8.913 / 98.824 = 9,02% |
| Số tổ hợp `delivery_status_key` được dùng | 47 |
| `fact_review`: `is_latest_review` = TRUE / `seller_key` = -1 / số (`review_id`, `order_id`) riêng biệt | 98.673 / 759 / 99.224 |
| `dim_customer.customer_type` | Chưa có đơn hợp lệ 1.113 · Mua một lần 92.827 · Mua lại 2.156 |
| `dim_product.category_name_en` = `'unknown'` / `dim_seller.seller_city` = `'Không xác định'` | 610 / 7 |

[Gợi ý] Ghi các câu đối soát vào `sql/checks/02_dds_checks.sql` (giống `01_pipeline_demo.sql`, số mong đợi ghi trong chú thích) – mapping mục 5 đã đề xuất. **Không** viết các tổng tiền thành dbt test cứng: demo xóa đơn sẽ làm chúng đổi.

## B7. Kịch bản kiểm thử

| # | Kịch bản | Kết quả mong đợi |
|---|---|---|
| 1 | `dbt build` sau khi nạp đủ 10 batch | `ERROR=0`; số liệu khớp B6 |
| 2 | `dbt build` thêm 1 lần, không đổi dữ liệu | Kết quả y hệt; khóa dimension không đổi; `dim_geography` báo `INSERT 0 0` |
| 3 | Chạy theo từng batch như lịch Seminar 3: Mage `full_load` → `dbt build --full-refresh` → lặp 9 lần (Mage `incremental_load` → `dbt build`) | Mỗi lần `ERROR=0`; khóa đã cấp không đổi giữa các lần; sau batch cuối số dòng và thuộc tính giống kịch bản 1 (so theo khóa tự nhiên – giá trị khóa có thể khác vì cấp dần) |
| 4 | Xóa mềm 1 đơn ([pipeline_rules.md](pipeline_rules.md) B6) → Mage `incremental_load` → `dbt build` | Đơn biến mất khỏi 3 fact; test xóa mềm đạt; khách của đơn vẫn còn trong `dim_customer` |
| 5 | Mage chạy lại `full_load` → `dbt build --full-refresh` | Dim / fact chỉ còn dữ liệu batch FULL, không lỗi |
| 6 | Demo 1 test FAIL (báo cáo 6.2.4) – xem đoạn SQL dưới | `dbt test --select source:staging` báo `FAIL 1`, dòng lỗi nằm trong bảng `dq` mà dbt in ra |

Đoạn SQL cho kịch bản 6 – chạy trong DBeaver, demo xong **phải** chạy câu `DELETE` để trả dữ liệu về:

```sql
-- Thêm 1 dòng order_items trỏ tới đơn không tồn tại -> test relationships của nguồn báo FAIL 1
INSERT INTO staging.order_items (order_id, order_item_id, product_id, seller_id, _batch_id)
SELECT 'demo_orphan_order', 1, product_id, seller_id, 'DEMO' FROM staging.order_items LIMIT 1;
-- docker compose exec mage dbt test --select source:staging
DELETE FROM staging.order_items WHERE order_id = 'demo_orphan_order';
```

## B8. Git và phối hợp [Bắt buộc]

- `git pull` trước khi làm; commit theo task, message tiếng Anh (VD `Add dbt staging models (BS-28)`).
- **Không** commit `dbt/profiles.yml`, `dbt/target/`, `dbt/logs/`, `dbt/dbt_packages/` (đã `.gitignore`). **Có** commit `dbt/package-lock.yml` nếu `dbt deps` làm nó đổi.
- Dữ liệu `staging` sai / pipeline lỗi → báo Yến (Mage) hoặc Hằng. Đổi quy tắc biến đổi → sửa `source_to_target_mapping.md` + thêm 1 dòng vào bảng cuối `decisions.md`; đổi grain / cột của `dds` → báo Kim Yến (`dw_design.md`, sơ đồ `dds_schema.drawio`).
- Đổi tên / xóa cột trong `dds` → báo người làm Power BI (semantic model sẽ hỏng).

## B9. Gợi ý viết báo cáo – mục 6.2.1 → 6.2.5 [Gợi ý]

Nguyên tắc như [pipeline_rules.md](pipeline_rules.md) B10.1: viết thiết kế + **lý do** (cô hay hỏi "sao làm vậy"), gắn thuật ngữ bài giảng (Stage → DDS, DQ database, Metadata), không dán code dài (trích đoạn ngắn, code đầy đủ ở repo), số liệu lấy từ B6 / kết quả chạy thật.

| Mục (đã có trong báo cáo) | Ý chính | Hình / bảng nên có | Lấy từ |
|---|---|---|---|
| **6.2.1** Tổ chức dbt project | Vị trí dbt trong Single DDS (DDS ETL); cấu trúc thư mục; 3 tầng → 3 schema và lý do tách `dbt_stg`, `dbt_int`; materialization từng bảng + lý do; chạy dbt trong container Mage; seed, package | Hình: cây thư mục `dbt/`; Bảng: tầng – thư mục – materialization – schema | `dbt/README.md` mục 2, `decisions.md` (23/10/2026), mapping 0.2 – 0.3 |
| **6.2.2** Staging models | Vai trò `stg_`; 8 model; đổi tên cột sai chính tả; xóa mềm R10 (vì sao lọc ngay ở `stg_`). Báo cáo **chưa có mục riêng cho intermediate** → trình bày `int_` + macro `normalize_city` ở cuối mục này (hoặc đổi tên mục thành "Staging và intermediate models") | Bảng 8 `stg_` (nguồn → việc làm); bảng 3 `int_` (grain, quy tắc); trích mẫu `stg_orders` | Mapping 0.1, R1, R4, R6, R7, R9, R10 |
| **6.2.3** Mart models | 6 dim: khóa số nguyên R2, member `-1`, SCD 1 incremental giữ khóa (giải thích mẫu B4.2); 3 fact: grain, lookup R5, vì sao `table` | Bảng số dòng dim / fact (B6); trích khung mẫu incremental | `dw_design.md`, mapping 2 – 3, file này B4 – B5 |
| **6.2.4** dbt tests | Các loại test: nguồn (D2), seed, generic (`unique`, `not_null`, `relationships`, `accepted_values`, `unique_combination_of_columns`), singular (R10, `normalize_city`); `store_failures` → `dq` – khác `dq.rejected_rows` của Mage ở đâu; kết quả `dbt build`; demo 1 test FAIL (B7 kịch bản 6) | Ảnh kết quả `dbt build`; ảnh bảng lỗi trong `dq` | [architecture.md](architecture.md) mục 3.3 – 4, file này B5 – B7 |
| **6.2.5** Data lineage và dbt docs | `dbt docs generate --static`; lineage graph; mô tả trong yml = Metadata của kiến trúc | Ảnh lineage toàn project (lưu `docs/images/dbt_lineage.png` – `dbt/README.md` đã trỏ tới); ảnh trang mô tả 1 model | `dbt/README.md` mục 1 |

Lấy ảnh lineage: mở `dbt/target/static_index.html` → nút xem lineage ở góc dưới bên phải → chụp màn hình toàn bộ đồ thị.
