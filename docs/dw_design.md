# Thiết kế Data Warehouse

## 1. Quy trình nghiệp vụ (Business Process)
[Quy trình nghiệp vụ được phân tích, ví dụ: bán hàng, đặt phòng, chuyến đi...]

## 2. Grain của bảng Fact
> Một dòng trong bảng fact đại diện cho: **[...]**

## 3. Sơ đồ lược đồ (Star / Snowflake Schema)

![Star Schema](images/star_schema.png)

## 4. Các schema trong database

| Schema | Mục đích | Được tạo bởi |
|--------|----------|--------------|
| `staging` | Dữ liệu thô nạp từ nguồn | Mage.ai |
| `etl_log` | Nhật ký chạy pipeline | `sql/` + Mage.ai |
| `dds` | Dimensional Data Store: bảng Dimension & Fact | dbt |

## 5. Bảng Dimension

### `dim_[tên]`
| Cột | Kiểu | Khóa | Mô tả | Nguồn |
|-----|------|------|-------|-------|
| `[tên]_key` | | PK (surrogate) | | |
|     |      |      |       |       |

- **SCD Type:** [0 / 1 / 2]
- **Hierarchy:** [VD: Năm → Quý → Tháng → Ngày]

### `dim_date`
| Cột | Kiểu | Khóa | Mô tả |
|-----|------|------|-------|
| `date_key` | int | PK | YYYYMMDD |
|     |      |      |       |

## 6. Bảng Fact

### `fact_[tên]`
| Cột | Kiểu | Loại | Mô tả |
|-----|------|------|-------|
| `[dim]_key` | | FK → `dim_[...]` | |
| `[measure]` | | Measure (additive / semi / non-additive) | |

## 7. Measures

| Measure | Cột nguồn | Phép tổng hợp | Tính chất cộng dồn |
|---------|-----------|---------------|--------------------|
|         |           |               |                    |

## 8. Ánh xạ nguồn → đích (Source-to-Target Mapping)

| Cột nguồn (staging) | Phép biến đổi | Cột đích (dds) |
|---------------------|---------------|----------------|
|                     |               |                |
