# Quy tắc xây dựng Semantic Model Power BI

> **Dành cho người làm BS-35 – Semantic Model.** Đọc **Phần A** để biết việc cần làm, thứ tự làm và khi nào coi là xong; mở **Phần B** khi làm trong Power BI Desktop.
> File này **không chép lại định nghĩa KPI**: định nghĩa nghiệp vụ nằm ở [business_questions.md](business_questions.md) mục 6 (K1–K13, M1–M5), cột nào tính KPI nào nằm ở [dw_design.md](dw_design.md) mục 7. File này nói **cách làm trong Power BI**: nạp bảng, quan hệ, hierarchy, mẫu DAX, số liệu nghiệm thu.
> Nếu thấy mâu thuẫn: [decisions.md](decisions.md) là gốc, sau đó đến `business_questions.md` → báo nhóm để sửa.
> **[Bắt buộc]** = nhóm đã chốt, muốn làm khác phải bàn lại · **[Gợi ý]** = cách đề xuất, làm khác được nếu ra cùng kết quả.
> Mẫu DAX trong file **chưa chạy thử trong Power BI** – viết theo cột thật của `dds` (dbt, 24/10/2026). Đúng hay sai đo bằng số nghiệm thu B6.
> Cập nhật: 26/10/2026.

---

# Phần A – Nhiệm vụ

## A1. Semantic Model nằm ở đâu

Kho `dds` là *tủ đồ ăn đã sơ chế*; Semantic Model là *công thức nấu chuẩn* đặt trong Power BI: nối các bảng lại với nhau, định nghĩa mỗi KPI **một lần**, để 3 trang dashboard (và ai vẽ thêm biểu đồ) đều ra cùng một con số.

```
Postgres olist_dw, schema dds (dbt dựng – 6 dim + 3 fact)
   │  Import (Get Data → PostgreSQL)
   ▼
SEMANTIC MODEL  ← BS-35 (file này)
   bảng + relationships + hierarchy + sort + measure DAX (K1–K13, M1–M5)
   │
   ▼
REPORT: Trang 1 Tổng quan · Trang 2 Giao hàng · Trang 3 Người bán · trang ẩn Chi tiết người bán   ← task dashboard (sau)
```

**Đã có sẵn – không phải làm:**

| Thứ | Ở đâu | Ghi chú |
|---|---|---|
| 9 bảng `dds` | Postgres `olist_dw` | Mô tả từng cột: `dbt/models/marts/_dim_models.yml`, `_fact_models.yml` (cũng nằm trong `COMMENT` của Postgres – DBeaver đọc được) |
| Định nghĩa KPI | [business_questions.md](business_questions.md) mục 6 | 13 KPI + 5 measure bổ trợ, kèm ngưỡng tốt / xấu |
| KPI → cột nào | [dw_design.md](dw_design.md) mục 7 | Bảng "Ánh xạ KPI → DW" |
| Cột DAX `delay_bucket_order` | [powerbi/README.md](../powerbi/README.md) | Chép nguyên, không viết lại |
| Phác thảo 3 trang | [powerbi/README.md](../powerbi/README.md) mục Dashboard | Để biết measure nào dùng ở biểu đồ nào |

## A2. Task và kết quả cần nộp

| Task | Làm gì | Kết quả nộp | Quy tắc |
|---|---|---|---|
| **BS-35** Semantic Model | Nạp 9 bảng, 16 relationship, hierarchy, sort, 18 measure | `powerbi/olist_dashboard.pbix` (chưa cần biểu đồ, trừ trang nháp kiểm tra B6); `powerbi/measures.dax`; điền các bảng trống trong `powerbi/README.md`; ảnh Model view `docs/images/powerbi_model.png` | B1 → B8 |

## A3. Chuẩn bị máy (làm 1 lần)

1. Power BI Desktop bản mới (Microsoft Store hoặc trang tải của Microsoft). Bản mới đã kèm driver PostgreSQL.
2. `dds` trên máy phải có **đủ 10 batch** và **không có đơn nào bị xóa mềm**, nếu không số nghiệm thu B6 sẽ lệch:

```powershell
git pull
docker compose up -d
# DB chưa có dữ liệu: chạy full_load + incremental_load tới hết batch (setup_guide.md mục 6.2) – dbt đã tự chạy trong pipeline
```

3. Kiểm tra bằng DBeaver: chạy `sql/checks/02_dds_checks.sql` → số dòng 9 bảng khớp số mong đợi ghi trong file (`fact_sales` 101.953, `fact_delivery` 100.010, `fact_review` 100.568).
4. Kết nối: Server `localhost:5432`, Database `olist_dw`, user / mật khẩu như `.env` (`POSTGRES_USER`, `POSTGRES_PASSWORD`). Lỗi SSL → [setup_guide.md](setup_guide.md) mục 8.

## A4. Thứ tự làm [Gợi ý]

1. Nạp 9 bảng (B2) → kiểm tra số dòng ngay trong Power BI (Table view, góc dưới).
2. Relationships (B3) → chụp Model view.
3. Đánh dấu Date table, hierarchy, sort, ẩn cột (B4).
4. Measure theo **thứ tự phụ thuộc** (B5): K1, K2 → K3; K6, K12 → M5; K1 → M1 → M2 …
5. Trang nháp toàn thẻ KPI + vài bảng nhỏ → so từng số với B6. Sai số nào sửa số đó rồi mới làm tiếp.
6. Chép DAX ra `measures.dax`, điền README, commit.

## A5. Khi nào coi là xong

- Model view đúng hình sao (B3): 3 fact, 6 dim, 16 quan hệ (15 active + 1 inactive), không có quan hệ 2 chiều, không có nhiều–nhiều.
- Đủ 18 measure, tất cả số ở B6 khớp (hoặc lệch có ghi lý do trong `powerbi/README.md`).
- Kiểm thử B7 đạt.
- Đã push `.pbix`, `measures.dax`, README, ảnh Model view; đã báo người làm dashboard.

---

# Phần B – Quy tắc chi tiết

## B1. Quy ước chung [Bắt buộc]

- **Không biến đổi dữ liệu trong Power Query.** Mọi làm sạch, đổi tên, tính cột đã làm ở dbt. Power Query chỉ được chọn bảng và (nếu cần) đổi kiểu dữ liệu. Thiếu cột → báo người làm dbt thêm vào `dds`, không tự tính bù ở Power BI. Ngoại lệ duy nhất: cột DAX `delay_bucket_order` (decisions.md, 17/10/2026).
- **Chế độ Import**, không dùng DirectQuery (dữ liệu nhỏ, DAX time intelligence chạy nhanh hơn, demo không phụ thuộc Docker đang bật).
- Mọi KPI hiển thị trên biểu đồ phải là **measure**, không kéo thẳng cột số (`revenue`, `review_score` …) vào visual – kéo thẳng cột thì Power BI tự cộng / trung bình theo dòng, sai grain (B5.1).
- Tên measure tiếng Việt, giống tên KPI trong `business_questions.md` (VD `Doanh thu`, `Tỉ lệ giao trễ`); mã K / M ghi ở ô **Description** của measure.
- Mỗi lần chỉ **1 người** mở và lưu file `.pbix` (file nhị phân, Git không gộp được). Ai muốn sửa model → nhắn người giữ file.

## B2. Nạp dữ liệu

Get Data → **PostgreSQL database** → `localhost:5432`, `olist_dw`, Import → chọn đúng 9 bảng schema `dds`:

| Loại | Bảng | Số dòng phải ra |
|---|---|---|
| Dim | `dds.dim_date` | 1.096 |
| Dim | `dds.dim_customer` | 96.097 |
| Dim | `dds.dim_geography` | 4.310 |
| Dim | `dds.dim_product` | 32.952 |
| Dim | `dds.dim_seller` | 3.096 |
| Dim | `dds.dim_delivery_status` | 672 |
| Fact | `dds.fact_sales` | 101.953 |
| Fact | `dds.fact_delivery` | 100.010 |
| Fact | `dds.fact_review` | 100.568 |

- [Gợi ý] Đổi tên bảng trong Power BI bỏ tiền tố `dds ` (Power BI hay đặt `dds dim_date`) → `dim_date` … cho DAX gọn. Tên cột **giữ nguyên** như `dds` để dò ngược về dbt.
- **Không** nạp `staging`, `dbt_stg`, `dbt_int`, `etl_log`, `dq`.
- Kiểm tra kiểu: các cột `*_key` là Whole number; `review_score` Whole number; `is_latest_review`, `has_comment`, `is_analysis_period`, `is_weekend` là True/False; `full_date` là Date.

## B3. Relationships [Bắt buộc]

Lược đồ Galaxy: 3 fact dùng chung dim. Tắt **Auto-detect relationships** (File → Options → Current file → Data Load) rồi nối tay để không có quan hệ thừa.

| # | Từ (Fact) | Đến (Dimension) | Cardinality | Hướng lọc | Trạng thái |
|---|---|---|---|---|---|
| 1 | `fact_sales[purchase_date_key]` | `dim_date[date_key]` | *:1 | Single | Active |
| 2 | `fact_sales[customer_key]` | `dim_customer[customer_key]` | *:1 | Single | Active |
| 3 | `fact_sales[geography_key]` | `dim_geography[geography_key]` | *:1 | Single | Active |
| 4 | `fact_sales[product_key]` | `dim_product[product_key]` | *:1 | Single | Active |
| 5 | `fact_sales[seller_key]` | `dim_seller[seller_key]` | *:1 | Single | Active |
| 6 | `fact_delivery[purchase_date_key]` | `dim_date[date_key]` | *:1 | Single | Active |
| 7 | `fact_delivery[customer_key]` | `dim_customer[customer_key]` | *:1 | Single | Active |
| 8 | `fact_delivery[geography_key]` | `dim_geography[geography_key]` | *:1 | Single | Active |
| 9 | `fact_delivery[seller_key]` | `dim_seller[seller_key]` | *:1 | Single | Active |
| 10 | `fact_delivery[delivery_status_key]` | `dim_delivery_status[delivery_status_key]` | *:1 | Single | Active |
| 11 | `fact_review[purchase_date_key]` | `dim_date[date_key]` | *:1 | Single | Active |
| 12 | `fact_review[answer_date_key]` | `dim_date[date_key]` | *:1 | Single | **Inactive** |
| 13 | `fact_review[customer_key]` | `dim_customer[customer_key]` | *:1 | Single | Active |
| 14 | `fact_review[geography_key]` | `dim_geography[geography_key]` | *:1 | Single | Active |
| 15 | `fact_review[seller_key]` | `dim_seller[seller_key]` | *:1 | Single | Active |
| 16 | `fact_review[delivery_status_key]` | `dim_delivery_status[delivery_status_key]` | *:1 | Single | Active |

Lý do và lưu ý:

- **Quan hệ 12 inactive**: `dim_date` đóng 2 vai (role-playing) với `fact_review`. Power BI chỉ cho 1 đường active giữa 2 bảng; mọi trang phân tích theo **ngày đặt hàng** (Q4 so điểm với tỉ lệ trễ của cùng tháng đặt) → ngày mua active. Cần theo ngày trả lời thì dùng `USERELATIONSHIP` (B5.3). Hiện chưa câu hỏi nào cần.
- **Single, không Both**: lọc 2 chiều giữa các fact qua dim chung dễ sinh vòng lặp / số sai. Measure cần kết hợp nhiều fact (M5) tự tính trong ngữ cảnh `dim_seller`.
- `dim_product` **chỉ** nối `fact_sales` → slicer danh mục không lọc được trang Giao hàng / Người bán. Đúng thiết kế (dw_design.md), không thêm quan hệ để "sửa".
- `geography_key` ở fact là **nơi nhận hàng của đơn** (bang khách). Bang người bán lấy từ `dim_seller[seller_state]`.
- Member `-1` "Không xác định" có trong mọi dim → không có dòng fact nào bị "mồ côi". Nếu Power BI báo quan hệ có giá trị không khớp → `dds` đang lỗi, báo người làm dbt.

## B4. Date table, hierarchy, sort, ẩn cột

### B4.1 Date table [Bắt buộc]

`dim_date` → **Mark as date table** → cột `full_date`. Không làm bước này thì `SAMEPERIODLASTYEAR` (M1) chạy sai khi lọc bằng cột của `dim_date`. Tắt **Auto date/time** (File → Options → Current file → Data Load) để Power BI không tự sinh bảng ngày ẩn cho từng cột ngày.

### B4.2 Hierarchies

| Bảng | Hierarchy | Ghi chú |
|---|---|---|
| `dim_date` | `year` → `quarter` → `month_name` → `full_date` | [Bắt buộc] – drill-down theo thời gian |
| `dim_geography` | `region` → `state_code` → `city` | [Bắt buộc] – bản đồ Q2 drill Vùng → Bang |
| `dim_seller` | `seller_region` → `seller_state` → `seller_city` | [Gợi ý] – trang 3 |
| `dim_delivery_status` | `delivery_result` → `delay_bucket` | [Gợi ý] – Q4 (Kết quả giao → Nhóm số ngày trễ) |
| `dim_customer` | `customer_region` → `customer_state` → `customer_city` | [Gợi ý] – bang **hiện tại** của khách (SCD 1), khác `dim_geography` là nơi nhận của từng đơn |

Trục tháng liên tục (01/2017 … 08/2018) dùng `year_month` (không gộp 03/2017 với 03/2018); trục so cùng kỳ Q1 dùng `month` / `month_name` + legend `year`.

### B4.3 Sort by column [Bắt buộc]

Theo bảng "Cột sắp xếp" trong [powerbi/README.md](../powerbi/README.md): `month_name` theo `month`, `day_name` theo `day_of_week`, `delay_bucket` theo cột DAX `delay_bucket_order` (chép nguyên công thức ở README). Kiểm tra: bảng `delay_bucket` + `delay_bucket_order` ra đúng 1–7 theo thứ tự Đúng hạn → … → Không xác định (công thức tính theo khóa, lý do ở README – bảng cuối `decisions.md`, 29/10/2026).

### B4.4 Ẩn cột và định dạng [Gợi ý]

- Ẩn mọi cột `*_key` (cả ở dim lẫn fact) và cột số của fact (`revenue`, `quantity`, `unit_price`, `freight_value`, `delivery_days`, `transit_days`, `late_days`, `handover_delay_days`, `review_score`, `purchase_seq`) → người vẽ dashboard chỉ thấy thuộc tính dim + measure, khó dùng nhầm.
- `year`, `month`, `quarter`, `date_key`: **Summarize by = Don't summarize** (Power BI hay tự Sum cột năm).
- `state_code`, `seller_state`: Data category = **State or Province**; `city`: **City** → bản đồ nhận đúng vị trí ở Brazil.
- Định dạng measure: tiền `#,0` hoặc `#,0.00` BRL; tỉ lệ Percentage 1–2 số lẻ; ngày, sao 2 số lẻ.

## B5. Measures (DAX)

### B5.1 Bốn cái bẫy grain [Bắt buộc – đọc trước khi viết]

| Bẫy | Vì sao | Cách tránh |
|---|---|---|
| `fact_delivery` 1 dòng = **(đơn, người bán)**, nhưng ngày giao khách là **cấp đơn** | 1.278 đơn nhiều người bán → `AVERAGE(delivery_days)` đếm 1 đơn nhiều lần | K6, K7, M4 tính theo **`order_id` riêng biệt**. Riêng K12 tính theo **dòng** (đúng grain đơn – người bán) |
| `fact_review` 1 dòng = **(review, người bán)**; 547 đơn có > 1 review | `AVERAGE(review_score)` đếm lặp | K8, K9 lọc `is_latest_review = TRUE` **và** lấy 1 điểm / `order_id` |
| `fact_sales` 1 dòng = 1 sản phẩm của 1 người bán trong 1 đơn | `COUNTROWS` ≠ số đơn | Số đơn = `DISTINCTCOUNT(order_id)`, số khách = `DISTINCTCOUNT(customer_key)` |
| DAX coi **BLANK < 3,5 là TRUE** | Người bán không có review sẽ bị gắn cờ M5 nhầm | Kiểm `NOT ISBLANK(...)` trước khi so ngưỡng |

`fact_sales` chỉ chứa đơn hợp lệ; `fact_delivery`, `fact_review` có cả đơn hủy → KPI giao hàng phải lọc qua `dim_delivery_status` như mẫu dưới, không đếm cả bảng.

### B5.2 Tổ chức [Bắt buộc]

- Tạo bảng rỗng `_Measures` (Enter data → 1 cột bất kỳ → xóa cột sau khi có measure đầu tiên) và đặt mọi measure vào đó.
- Display folder: `1 Tổng quan` (K1–K5, M1–M3), `2 Giao hàng` (K6–K9), `3 Người bán` (K10–K13, M4, M5), `0 Phụ` (measure trung gian).
- Chuỗi trong DAX (`"Trễ hạn"`, `"Đúng hạn"` …) phải giống **từng ký tự** giá trị dbt sinh ra (`dbt/models/marts/dim_delivery_status.sql`).

### B5.3 Mẫu DAX [Gợi ý]

```dax
// ===== 1 Tổng quan =====
Doanh thu = SUM ( fact_sales[revenue] )                                      // K1
Số đơn = DISTINCTCOUNT ( fact_sales[order_id] )                              // K2
Giá trị đơn TB = DIVIDE ( [Doanh thu], [Số đơn] )                            // K3
Số khách hàng = DISTINCTCOUNT ( fact_sales[customer_key] )                   // K4

Tỉ lệ khách mua lại =                                                        // K5: khách có >= 2 LẦN mua trong kỳ (R6)
VAR KhachMuaLai =
    COUNTROWS (
        FILTER (
            VALUES ( fact_sales[customer_key] ),
            CALCULATE ( DISTINCTCOUNT ( fact_sales[purchase_seq] ) ) >= 2
        )
    )
RETURN DIVIDE ( KhachMuaLai, [Số khách hàng] )

Doanh thu cùng kỳ =                                                          // M1: chỉ có nghĩa với 01–08/2018
VAR TrongKy =
    MIN ( dim_date[full_date] ) >= DATE ( 2018, 1, 1 )
        && MAX ( dim_date[full_date] ) <= DATE ( 2018, 8, 31 )
RETURN IF ( TrongKy, CALCULATE ( [Doanh thu], SAMEPERIODLASTYEAR ( dim_date[full_date] ) ) )

% tăng trưởng cùng kỳ = DIVIDE ( [Doanh thu] - [Doanh thu cùng kỳ], [Doanh thu cùng kỳ] )   // M2 (BLANK khi M1 BLANK)

% tổng doanh thu =                                                           // M3: bỏ lọc danh mục, bang
DIVIDE ( [Doanh thu], CALCULATE ( [Doanh thu], ALL ( dim_product ), ALL ( dim_geography ) ) )

// ===== 2 Giao hàng =====
Số đơn giao trễ =                                                            // phụ
CALCULATE ( DISTINCTCOUNT ( fact_delivery[order_id] ), dim_delivery_status[delivery_result] = "Trễ hạn" )
Số đơn đã giao =                                                             // phụ – mẫu số K6
CALCULATE ( DISTINCTCOUNT ( fact_delivery[order_id] ), dim_delivery_status[delivery_result] IN { "Đúng hạn", "Trễ hạn" } )
Tỉ lệ giao trễ = DIVIDE ( [Số đơn giao trễ], [Số đơn đã giao] )             // K6

Thời gian giao TB =                                                          // K7: 1 giá trị / đơn
CALCULATE (
    AVERAGEX ( VALUES ( fact_delivery[order_id] ), CALCULATE ( MAX ( fact_delivery[delivery_days] ) ) ),
    dim_delivery_status[delivery_result] IN { "Đúng hạn", "Trễ hạn" }
)

Điểm đánh giá TB =                                                           // K8: 1 điểm / đơn
CALCULATE (
    AVERAGEX ( VALUES ( fact_review[order_id] ), CALCULATE ( MAX ( fact_review[review_score] ) ) ),
    fact_review[is_latest_review] = TRUE ()
)

Tỉ lệ đánh giá tiêu cực =                                                    // K9
VAR DonCoReview =
    CALCULATE ( DISTINCTCOUNT ( fact_review[order_id] ), fact_review[is_latest_review] = TRUE () )
VAR DonTieuCuc =
    CALCULATE (
        DISTINCTCOUNT ( fact_review[order_id] ),
        fact_review[is_latest_review] = TRUE (),
        fact_review[review_score] <= 2
    )
RETURN DIVIDE ( DonTieuCuc, DonCoReview )

// ===== 3 Người bán =====
Số người bán hoạt động = DISTINCTCOUNT ( fact_sales[seller_key] )            // K10 – đếm trên fact, không đếm dim (D3)
Doanh thu TB mỗi người bán = DIVIDE ( [Doanh thu], [Số người bán hoạt động] )   // K11

Tỉ lệ bàn giao trễ =                                                         // K12: theo DÒNG (đơn, người bán)
DIVIDE (
    CALCULATE ( COUNTROWS ( fact_delivery ), dim_delivery_status[handover_status] = "Trễ hạn" ),
    CALCULATE ( COUNTROWS ( fact_delivery ), dim_delivery_status[handover_status] IN { "Đúng hạn", "Trễ hạn" } )
)

Tỷ trọng doanh thu top 10% người bán =                                       // K13
VAR SoTop = ROUNDUP ( [Số người bán hoạt động] * 0.1, 0 )
VAR TopNB = TOPN ( SoTop, VALUES ( fact_sales[seller_key] ), [Doanh thu], DESC )
RETURN DIVIDE ( CALCULATE ( [Doanh thu], TopNB ), [Doanh thu] )

Thời gian vận chuyển TB =                                                    // M4: 1 giá trị / đơn
CALCULATE (
    AVERAGEX ( VALUES ( fact_delivery[order_id] ), CALCULATE ( MAX ( fact_delivery[transit_days] ) ) ),
    dim_delivery_status[delivery_result] IN { "Đúng hạn", "Trễ hạn" }
)

Cờ người bán cần xử lý =                                                     // M5: tính trong ngữ cảnh 1 người bán
VAR Diem = [Điểm đánh giá TB]
VAR TreBG = [Tỉ lệ bàn giao trễ]
RETURN
    IF (
        [Số đơn] >= 30
            && ( ( NOT ISBLANK ( Diem ) && Diem < 3.5 ) || ( NOT ISBLANK ( TreBG ) && TreBG > 0.1 ) ),
        1,
        0
    )
```

Ghi chú:

- K13: "10% người bán" làm tròn lên hay làm tròn thường chưa chốt – thử cả hai, cách nào ra gần số B6 hơn thì dùng, ghi lại vào `decisions.md`.
- M1 lọc theo **cả kỳ đang xét**: thẻ K1 đặt trên trang lọc 01/2017 – 08/2018 sẽ ra BLANK. Muốn thẻ hiện "+138% (01–08/2018 so với 01–08/2017)" thì viết thêm 1 measure riêng cố định 2 khoảng ngày – bàn với người làm trang 1.
- Cần phân tích review theo **ngày trả lời**: `CALCULATE ( [Điểm đánh giá TB], USERELATIONSHIP ( fact_review[answer_date_key], dim_date[date_key] ) )`.

## B6. Số liệu nghiệm thu

Lọc **01/2017 – 08/2018** (`dim_date[is_analysis_period] = TRUE`), không lọc gì khác. Cột "Nguồn": **dds** = đã đối soát trên `dds` (dbt, 24/10/2026) – phải khớp đúng; **CSV** = kiểm chứng sơ bộ trên CSV gốc (`business_questions.md`) – lệch ở số lẻ cuối được, lệch nhiều phải tìm nguyên nhân.

| KPI | Phải ra | Nguồn |
|---|---|---|
| K1 Doanh thu | **13.449.529,68** BRL (cả kỳ, bỏ lọc: 13.494.400,74) | dds |
| K2 Số đơn | 97.905 | CSV (dw_design mục 7) |
| K3 Giá trị đơn TB | ≈ 137,4 BRL | = K1 / K2 |
| K4 Số khách hàng | ≈ 94.707 | CSV |
| K5 Tỉ lệ khách mua lại | 2,27% | dds |
| K6 Tỉ lệ giao trễ | **6.531 / 96.203 = 6,79%** (bỏ lọc: 6.534 / 96.470 = 6,77%) | dds |
| K7 Thời gian giao TB | ≈ 12,5 ngày | CSV |
| K8 Điểm đánh giá TB | 4,09 | dds |
| K9 Tỉ lệ đánh giá tiêu cực | 14,63% (bỏ lọc: 14,69%) | dds |
| K10 Số người bán hoạt động | ≈ 3.029 | CSV |
| K11 Doanh thu TB mỗi người bán | ≈ 4.440 BRL | CSV |
| K12 Tỉ lệ bàn giao trễ | **8.913 / 98.824 = 9,02%** (bỏ lọc) | dds |
| K13 Tỷ trọng top 10% người bán | ≈ 67,3% | CSV |
| M4 Thời gian vận chuyển TB | ≈ 9,33 ngày | dds |

Kiểm theo câu hỏi (dựng bảng / biểu đồ nháp):

| Câu | Phải thấy | Nguồn |
|---|---|---|
| Q1 | 01–08/2018 so với 01–08/2017: doanh thu 3,08 → 7,34 tr BRL (+138%); số đơn 22.562 → 53.530; AOV gần như không đổi (136,6 → 137,1); đỉnh 11/2017 | CSV |
| Q2 | Top 5 bang: SP 38,3%, RJ 13,4%, MG 11,7%, RS 5,5%, PR 5,0%; danh mục đầu: health_beauty 9,3% | CSV |
| Q3 | Tháng vượt 10%: 11/2017 (12,4%), 02/2018 (14,1%), 03/2018 (19,0%); bang cao nhất AL 21,5% | CSV |
| Q4 | Đúng hạn 4,29★, trễ 2,27★; trễ 1–3 ngày 3,29★ | CSV |
| Q5 | Bàn giao trễ → 21,0% đơn giao trễ; bàn giao đúng hạn → 5,3% | CSV |
| Q6 | 191 / 633 người bán (≥ 30 đơn) có M5 = 1 | CSV |

Số dòng 9 bảng: B2. Số nào lệch → ghi số ra được + nguyên nhân vào `powerbi/README.md`, **không** sửa công thức chỉ để ép cho khớp.

## B7. Kiểm thử

| # | Kịch bản | Kết quả mong đợi |
|---|---|---|
| 1 | Bảng nháp: `year_month` + K1, K2, K6, K8 | Có số mọi tháng 01/2017 – 08/2018; tổng dòng Total = số B6 (không phải tổng các tháng với K6, K8 – tỉ lệ / trung bình không cộng) |
| 2 | Bảng nháp: `delay_bucket` + K8 | Thứ tự Đúng hạn → Trễ 1–3 → … → Không xác định; số khớp Q4 |
| 3 | Bảng nháp: `seller_id` + Số đơn, K8, K12, M5; lọc Số đơn ≥ 30 | 633 dòng, 191 dòng M5 = 1 (Q6) |
| 4 | Chọn 1 bang ở slicer `dim_geography` | Cả 3 fact đổi theo (doanh thu, tỉ lệ trễ, điểm đều đổi) |
| 5 | Chọn 1 danh mục `dim_product` | Chỉ K1–K5 đổi; KPI giao hàng / đánh giá **không** đổi (đúng thiết kế, B3) |
| 6 | Line chart M2 theo `month`, legend `year` | Có giá trị 01–08/2018, BLANK ở mọi tháng khác (không có cột tăng hàng nghìn % ở 10/2017) |
| 7 | Chạy thêm 1 lần pipeline (`rerun_last`) → Refresh trong Power BI | Refresh không lỗi, mọi số không đổi |

## B8. Git và phối hợp [Bắt buộc]

- `git pull` trước khi làm; commit theo task, message tiếng Anh (VD `Add Power BI semantic model (BS-35)`).
- Commit: `powerbi/olist_dashboard.pbix`, `powerbi/measures.dax`, `powerbi/README.md`, `docs/images/powerbi_model.png`. **Không** commit file khóa `*.pbix.lock`, `.pbi/` (đã `.gitignore`).
- File `.pbix` lưu dữ liệu đã Import → trước khi commit, kiểm tra đã Refresh trên `dds` đủ 10 batch (B6), không phải DB đang demo xóa đơn.
- Đổi tên / thêm measure sau khi đã giao → báo người làm dashboard (visual dùng measure cũ sẽ báo lỗi).
- Thiếu cột / số `dds` sai → báo người làm dbt (Thanh), không sửa bù trong Power BI (B1). Định nghĩa KPI chưa rõ → hỏi nhóm, chốt vào `decisions.md`.

## B9. Gợi ý viết báo cáo [Gợi ý]

Nguyên tắc như [pipeline_rules.md](pipeline_rules.md) B10.1: viết thiết kế + **lý do**, gắn thuật ngữ bài giảng, số liệu lấy từ kết quả thật.

| Ý | Nội dung | Hình / bảng nên có |
|---|---|---|
| Vai trò Semantic Model | Lớp nghĩa nghiệp vụ giữa `dds` và report; định nghĩa KPI 1 lần, mọi trang dùng chung | Sơ đồ A1 |
| Kết nối | Import từ PostgreSQL, vì sao không DirectQuery, không biến đổi trong Power Query | – |
| Relationships | Galaxy, *:1 Single, role-playing `dim_date` (inactive + `USERELATIONSHIP`), vì sao không lọc 2 chiều | Ảnh Model view; bảng B3 |
| Hierarchy, sort | 3 hierarchy chính, cột DAX `delay_bucket_order` (vì sao không để trong `dds`) | Bảng B4.2 |
| Measures | 18 measure; xử lý grain (đếm đơn riêng biệt, `is_latest_review`), time intelligence M1/M2 có chặn kỳ | Bảng measure – công thức rút gọn – trang dùng; trích 2–3 DAX tiêu biểu (K6, K8, M5) |
| Kiểm chứng | So số Power BI với `dds` / CSV | Bảng B6 có cột "Power BI ra" |
