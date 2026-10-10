# dbt – Data Transformation

## Tầng model

| Tầng | Thư mục | Tiền tố | Materialization | Vai trò |
|------|---------|---------|-----------------|---------|
| Staging | `models/staging/` | `stg_` | view | Làm sạch, đổi tên, ép kiểu – 1 model / 1 bảng nguồn |
| Intermediate | `models/intermediate/` | `int_` | view / ephemeral | Join, tính toán trung gian |
| Marts | `models/marts/` | `dim_`, `fact_` | table / incremental | Star Schema cho Power BI |

## Danh sách model

| Model | Tầng | Phụ thuộc | Mô tả |
|-------|------|-----------|-------|
|       |      |           |       |

## Data tests

| Model.Cột | Test | Mục đích |
|-----------|------|----------|
|           | `unique`, `not_null` | |
|           | `relationships` | Kiểm tra FK fact → dim |
|           | `accepted_values` | |
|           | Custom (`tests/`) | |

## Lineage graph

![Lineage](../docs/images/dbt_lineage.png)
