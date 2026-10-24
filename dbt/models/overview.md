{% docs __overview__ %}
# Kho dữ liệu Olist – dbt project `olist_dw`

Đồ án BI tích hợp AI – Nhóm 3 (CSC12107). Project này biến đổi dữ liệu sàn thương mại điện tử Olist
(Brazil, 09/2016 – 10/2018, tiền tệ BRL) từ schema `staging` do **Mage** nạp thành kho **`dds`**
(Dimensional Data Store) cho **Power BI**. Trong kiến trúc Single DDS, dbt là khâu **DDS ETL + DQ**,
còn trang tài liệu này là **Metadata**.

## Các tầng

| Tầng | Tiền tố | Schema | Dạng | Việc làm |
|---|---|---|---|---|
| Nguồn | – | `staging` | bảng (Mage nạp) | 8 bảng giữ nguyên cột như CSV gốc |
| Staging | `stg_` | `dbt_stg` | view | 1 model / 1 bảng nguồn: chọn cột, đổi tên cột sai chính tả, bỏ đơn đã xóa mềm (R10) |
| Intermediate | `int_` | `dbt_int` | view | Phép tính dùng chung: khách thật, chuẩn hóa thành phố (R1), đơn hợp lệ (R4), lần mua (R6), số ngày giao và trạng thái giao hàng (R7, R9) |
| Marts | `dim_`, `fact_` | `dds` | bảng | 6 dimension + 3 fact (lược đồ Galaxy) – Power BI chỉ đọc schema này |
| Seed | `seed_` | `dbt_stg` | bảng | Tên bang + vùng của 27 bang, 2 bản dịch danh mục còn thiếu |
| dbt test | – | `dq` | bảng | Dòng vi phạm của mỗi test (`store_failures`), ghi đè ở mỗi lần chạy |

## Ba bảng fact

| Fact | Một dòng = | Câu hỏi |
|---|---|---|
| `fact_sales` | 1 sản phẩm của 1 người bán trong 1 đơn hợp lệ (gộp các đơn vị cùng sản phẩm thành `quantity`) | Q1, Q2, Q6 |
| `fact_delivery` | 1 cặp (đơn, người bán) – kể cả đơn hủy có sản phẩm (accumulating snapshot) | Q3 – Q6 |
| `fact_review` | 1 đánh giá × 1 người bán của đơn; cờ `is_latest_review` để lấy 1 điểm / đơn | Q4, Q6 |

Dimension dùng chung: `dim_date` (ngày đặt hàng, ngày trả lời đánh giá), `dim_customer`, `dim_geography`,
`dim_product`, `dim_seller`, `dim_delivery_status`. Khóa thay thế là số nguyên; dòng `-1` = "Không xác định".

## Cách đọc trang này

- **Sơ đồ lineage**: nút tròn màu xanh ở góc dưới bên phải – bảng nào được làm từ bảng nào, từ `staging`
  tới dashboard Power BI (exposure).
- **Mỗi model**: mô tả, từng cột (kiểu dữ liệu + ý nghĩa), test của cột, code SQL (tab *Source* / *Compiled*).
- Mã quy tắc trong mô tả (R1 – R10, D1 – D8, K1 – K13) giải thích ở repo:
  `docs/source_to_target_mapping.md`, `docs/decisions.md`, `docs/business_questions.md`.

## Chạy (trong container Mage, ở thư mục gốc repo)

- `docker compose exec mage dbt build` – seed → model → test theo đúng thứ tự phụ thuộc
- `docker compose exec mage dbt build --full-refresh` – sau khi chạy lại Full Load
- `docker compose exec mage dbt docs generate --static` – dựng lại trang này (`dbt/target/static_index.html`)
{% enddocs %}
