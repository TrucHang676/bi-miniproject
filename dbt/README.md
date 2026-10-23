# dbt – Data Transformation

> Project dbt `olist_dw`: biến đổi schema `staging` (Mage nạp) thành kho `dds` (Galaxy schema) cho Power BI.
> Công thức từng cột: [docs/source_to_target_mapping.md](../docs/source_to_target_mapping.md) · thiết kế kho: [docs/dw_design.md](../docs/dw_design.md).
> Khởi tạo 23/10/2026: cấu hình, kết nối, nguồn, seed – **chưa có model** (BS-28 → BS-31, mục 4).

## 1. Chạy dbt

dbt nằm sẵn trong container Mage (dbt-core 1.8.7, dbt-postgres 1.8.2). `compose.yaml` đặt `DBT_PROJECT_DIR` = `DBT_PROFILES_DIR` = `/home/src/dbt`, nên ở thư mục gốc repo chỉ cần gõ `docker compose exec mage dbt <lệnh>`.

**Lần đầu trên mỗi máy** (sau `git pull`):

```powershell
Copy-Item dbt\profiles.yml.example dbt\profiles.yml   # kết nối DB: đọc POSTGRES_* từ .env, không chứa mật khẩu
docker compose up -d                                   # tạo lại container Mage để nhận 2 biến DBT_* trong compose.yaml
docker compose exec mage dbt deps                      # cài dbt_utils đúng bản ghi trong package-lock.yml
docker compose exec mage dbt debug                     # phải ra: All checks passed!
```

`staging` phải có dữ liệu trước khi build: chạy Mage `full_load` + 9 lần `incremental_load` ([setup_guide.md](../docs/setup_guide.md) mục 6.2).
Khi chưa có model nào, dbt in `[WARNING]: … There are 3 unused configuration paths` – bình thường, tự hết khi mỗi thư mục có model.

| Muốn… | `docker compose exec mage …` |
|---|---|
| Dựng tất cả đúng thứ tự: seed → model → test | `dbt build` |
| 1 model và test của nó | `dbt build --select stg_orders` |
| 1 model và mọi model phía sau nó | `dbt build --select stg_orders+` |
| Chỉ test dữ liệu nguồn | `dbt test --select source:staging` |
| Sau khi chạy lại Full Load (staging làm lại từ đầu) | `dbt build --full-refresh` – dựng lại cả model `incremental` |
| Tài liệu + sơ đồ lineage | `dbt docs generate --static` → mở `dbt/target/static_index.html` bằng trình duyệt |

## 2. Cấu trúc và schema đích

| Thư mục | Tiền tố | Materialization | Schema | Nội dung |
|---|---|---|---|---|
| `models/staging/` | `stg_` | view | `dbt_stg` | 1 model / 1 bảng nguồn: ép kiểu, `TRIM`, đổi tên cột sai chính tả, bỏ đơn đã xóa mềm (R10) |
| `models/intermediate/` | `int_` | view | `dbt_int` | Phép tính dùng chung cho nhiều dim / fact: `int_orders`, `int_purchase_sessions`, `int_delivery_lines` |
| `models/marts/` | `dim_`, `fact_` | table (`dim_customer`, `dim_geography`: incremental) | `dds` | 6 dimension + 3 fact – Power BI chỉ đọc schema này |
| `seeds/` | `seed_` | table | `dbt_stg` | Dữ liệu tham chiếu nhóm tự bổ sung |
| `macros/` | | | | `generate_schema_name`: dùng đúng tên schema ở cột trên (mặc định dbt ghép thành `dbt_stg_dds`) |
| `tests/` | | | | Test viết tay (singular test), VD test xóa mềm R10 |
| dbt test | | table | `dq` | `store_failures`: dòng vi phạm của mỗi test vào 1 bảng, ghi đè ở mỗi lần chạy |

`staging` (Mage) và `dds` (Power BI) giữ đúng vai trò; view trung gian của dbt nằm riêng ở `dbt_stg`, `dbt_int` (dbt tự tạo 2 schema này).
Cấu hình: [dbt_project.yml](dbt_project.yml) · kết nối: [profiles.yml.example](profiles.yml.example) · package: [packages.yml](packages.yml).

## 3. Đã có sẵn

| Thứ | File | Ghi chú |
|---|---|---|
| Nguồn | `models/staging/_sources.yml` | 8 bảng `staging`. Model `stg_` đọc bằng `{{ source('staging', 'orders') }}`, tầng sau dùng `{{ ref('stg_orders') }}`. Test: 6 khóa ngoại (D2) + mã bang của `customers` / `sellers` có trong seed. Khóa chính không test lại vì `staging` đã có ràng buộc `PRIMARY KEY` |
| Seed | `seeds/seed_brazil_states.csv` | 27 bang → tên bang có dấu (VD `São Paulo`) + 5 vùng (Norte, Nordeste, Centro-Oeste, Sudeste, Sul) |
| | `seeds/seed_category_translation_extra.csv` | 2 bản dịch còn thiếu: `pc_gamer`, `portateis_cozinha_e_preparadores_de_alimentos` |
| Mô tả + test seed | `seeds/_seeds.yml` | Mã bang không trùng, vùng thuộc 5 giá trị |
| Package | `packages.yml` | `dbt_utils` 1.3.x – `unique_combination_of_columns` cho khóa ghép (mapping mục 5) |

Đã chạy thử trên dữ liệu đủ 10 batch (23/10/2026): `dbt build` đạt hết (2 seed, 14 test); làm mồ côi 1 đơn thì test báo `FAIL 1` và dòng lỗi nằm trong `dq`.

## 4. Việc tiếp theo

| Task | Tạo gì | Công thức (source_to_target_mapping.md) |
|---|---|---|
| BS-28 – Models tầng staging | 8 model `stg_<tên bảng>` + `_stg_models.yml` | Mục 0.1, R10; `stg_products` đổi `*_lenght` → `*_length` |
| BS-29 – Models tầng intermediate | `int_orders`, `int_purchase_sessions`, `int_delivery_lines` + macro `normalize_city` | R1, R4, R6, R7, R9 |
| BS-30 – Models Dimension | 6 model `dim_` | Mục 2, R2 (khóa số nguyên ổn định, member `-1`) |
| BS-31 – Model Fact | 3 model `fact_` + singular test xóa mềm trong `tests/` | Mục 3, R5; số dòng / test dự kiến ở mục 5 |

Quy ước: mỗi thư mục 1 file `_<tầng>_models.yml` (mô tả model, cột, test); mô tả viết tiếng Việt – dbt docs (Metadata) lấy từ đây. Điền mục 5, 6 khi làm.

## 5. Danh sách model

| Model | Tầng | Phụ thuộc | Mô tả |
|-------|------|-----------|-------|
|       |      |           |       |

## 6. Data tests

| Model.Cột | Test | Mục đích |
|-----------|------|----------|
|           | `unique`, `not_null` | |
|           | `relationships` | Kiểm tra FK fact → dim |
|           | `accepted_values` | |
|           | Custom (`tests/`) | |

## 7. Lineage graph

![Lineage](../docs/images/dbt_lineage.png)
