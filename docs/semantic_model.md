# Semantic Model Power BI – hồ sơ bàn giao (BS-40)

> **Ai đọc file này:** người làm dashboard (Seminar 2), người viết báo cáo phần Power BI, và AI trợ lý của các bạn trong nhóm.
> **File này ghi lại *đã làm gì, vì sao, dùng thế nào*.** Số liệu chi tiết (16 quan hệ, 5 hierarchy, 20 measure, bảng nghiệm thu B6/B7) **không chép lại** – xem [powerbi/README.md](../powerbi/README.md). Quy tắc gốc: [powerbi_rules.md](powerbi_rules.md) (trong đó gọi task là BS-35; trên bảng công việc là BS-40).
> Người làm: Trần Kim Yến · Hoàn thành: 29/10/2026 · Commit `6b2545a`.

---

## 1. Tóm tắt

| Hạng mục | Kết quả |
|---|---|
| File model | `powerbi/olist_dashboard.pbix` (~29 MB, đã kèm dữ liệu) – cùng nội dung với file chung trên OneDrive `Dashboard seminar [Group-3].pbix` |
| Nguồn | Postgres `olist_dw`, schema `dds` (9 bảng, đủ 10 batch), chế độ **Import** |
| Nội dung | 9 bảng · 16 quan hệ (15 active + 1 inactive) · 5 hierarchy · 3 cột sắp xếp · bảng `_Measures` chứa 20 measure |
| DAX sao lưu | `powerbi/measures.dax` (trùng khớp với model) |
| Ảnh Model view | `docs/images/powerbi_model.png` |
| Kiểm thử | B2, B6, B7 #1–#7 của `powerbi_rules.md` **đạt hết** (kết quả từng số: `powerbi/README.md`) |
| Phiên bản Power BI | Power BI Desktop **bản Microsoft Store** 2.159 – cả nhóm nên dùng bản Store để mở file không lệch phiên bản |

Chưa có biểu đồ: trang "Page 1" để trống, chờ task dashboard.

## 2. Model gồm những gì

```
Postgres olist_dw.dds (dbt dựng)          Power BI – olist_dashboard.pbix
┌───────────────────────────┐   Import    ┌────────────────────────────────────────────┐
│ 6 dim + 3 fact            │ ──────────► │ 9 bảng (tên giữ nguyên như dds)             │
└───────────────────────────┘             │ + quan hệ *:1 Single, hierarchy, sort       │
                                          │ + _Measures: K1–K13, M1–M5, 2 measure phụ  │
                                          └────────────────────────────────────────────┘
```

- **Lược đồ Galaxy**: 3 fact (`fact_sales`, `fact_delivery`, `fact_review`) dùng chung dim. Mọi quan hệ một chiều (Single), nhiều–một.
- **`dim_date` đóng 2 vai** với `fact_review`: ngày đặt hàng (active) và ngày trả lời đánh giá (inactive, dùng `USERELATIONSHIP` khi cần).
- **`dim_product` chỉ nối `fact_sales`** → chọn danh mục chỉ đổi KPI bán hàng (K1–K5), KPI giao hàng / đánh giá giữ nguyên. Đây là thiết kế, không phải lỗi.
- **Cột ẩn**: mọi `*_key` và cột số của fact (`revenue`, `review_score`, `delivery_days` …) bị ẩn → người vẽ dashboard chỉ thấy thuộc tính dim + measure, tránh kéo nhầm cột số (sai grain).
- **Không biến đổi gì trong Power Query** – mọi làm sạch đã ở dbt. Ngoại lệ duy nhất: cột DAX `delay_bucket_order` (mục 4).

### Measure xử lý "bẫy grain" thế nào

| Bẫy | Measure liên quan | Cách xử lý trong DAX |
|---|---|---|
| `fact_sales` 1 dòng = 1 sản phẩm của 1 người bán trong 1 đơn | K2, K4, K10 | Đếm `DISTINCTCOUNT(order_id / customer_key / seller_key)`, không `COUNTROWS` |
| `fact_delivery` 1 dòng = (đơn, người bán), ngày giao là cấp đơn | K6, K7, M4 | Tính trên `order_id` riêng biệt; chỉ đơn có `delivery_result` = "Đúng hạn" / "Trễ hạn" |
| | K12 | Ngược lại, tính theo **dòng** (đúng grain đơn – người bán) |
| `fact_review` có đơn nhiều review | K8, K9 | Lọc `is_latest_review = TRUE` + lấy 1 điểm / `order_id` |
| DAX coi BLANK < 3,5 là đúng | M5 | Kiểm `NOT ISBLANK(...)` trước khi so ngưỡng |

## 3. Đã làm như thế nào

Không làm tay từng bước trong giao diện mà dựng bằng **Power BI Project (PBIP) + TMDL**: model lưu thành các file chữ → viết tự động theo đúng bảng trong `powerbi_rules.md`, kiểm tra bằng thư viện của chính Power BI, rồi mới mở trong Desktop.

1. Chuẩn bị: cài Power BI bản Store; `dds` nạp đủ 10 batch bằng pipeline Mage (`etl_log` run 57 FULL → run 66 `2018-09+`), không có đơn xóa mềm.
2. Mở file chung (đang trống) → *Save as* dạng `.pbip` vào thư mục làm việc **ngoài repo** `D:\HK7\BI\Seminar\bi-pbip\` (máy Yến, không commit).
3. Sinh file TMDL cho 9 bảng (cột lấy từ `information_schema` của `dds`), 16 quan hệ, hierarchy, sort, bảng `_Measures`; kiểm tra offline (đọc lại được, mọi cột DAX tham chiếu có thật, chuỗi "Trễ hạn"/"Đúng hạn"… khớp từng ký tự với dbt).
4. Mở `.pbip` → Refresh (nhập tài khoản Postgres) → kiểm tự động bằng truy vấn DAX vào engine của Power BI Desktop, đối chiếu với SQL tính thẳng trên `dds`.
5. *Save as* `.pbix` → commit. File chung trên OneDrive được chia sẻ lẻ (không mở / ghi đè được từ máy khác) → gửi Hằng **Upload → Replace** đúng file cũ để giữ link.

## 4. Quyết định mới và chỗ khác với `powerbi_rules.md`

| Chỗ | Đã làm | Lý do |
|---|---|---|
| Cột `delay_bucket_order` | `MOD ( dim_delivery_status[delivery_status_key] - 1, 7 ) + 1` thay cho `SWITCH` trên `delay_bucket` | Công thức cũ gây lỗi *circular dependency* khi dùng làm Sort by column cho chính `delay_bucket`. Khóa do dbt đánh số theo thứ tự cố định nên suy được thứ tự 1–7. **Đổi thứ tự / số nhóm trễ trong dbt thì phải sửa số 7.** Ghi ở bảng cuối `decisions.md` (29/10/2026) |
| K13 làm tròn | Giữ `ROUNDUP` | Trong kỳ `ROUNDUP` = `ROUND` (cùng 303 người bán, 67,38%); "top 10%" hiểu là *ít nhất* 10%. `decisions.md` 29/10/2026 |
| Số nghiệm thu K6 | Sửa `powerbi_rules.md` B6: trong kỳ **6,79%** (6.531 / 96.203); 6,77% là số bỏ lọc | Bảng B6 ghi nhầm số bỏ lọc ở dòng K6 |
| Kiểu cột tiền / số ngày | Power BI tự để `Decimal number` (double) | Desktop tự đổi khi nạp từ Postgres; các cột này bị ẩn, measure không bị ảnh hưởng |
| K4, Q5 | Power BI ra 94.703; 21,08% / 5,39% | Khác số sơ bộ trên CSV (≈ 94.707; 21,0% / 5,3%), nhưng **khớp SQL trên `dds`** → giữ, không ép công thức |

## 5. Dùng model để vẽ dashboard

- **Mở file**: `powerbi/olist_dashboard.pbix` (hoặc file chung trên OneDrive sau khi Hằng replace). Muốn dữ liệu mới nhất → **Refresh**. Lần đầu Power BI hỏi tài khoản PostgreSQL: `Database` → user / mật khẩu như `.env` (`POSTGRES_USER`, `POSTGRES_PASSWORD`) → hỏi kết nối không mã hóa thì **OK** (Postgres chạy Docker không có SSL). Docker phải đang chạy khi Refresh; chỉ xem thì không cần.
- **Chỉ kéo measure** trong `_Measures` vào biểu đồ (thư mục `1 Tổng quan`, `2 Giao hàng`, `3 Người bán`; `0 Phụ` là measure trung gian). Mỗi measure có mã K/M trong ô *Description*. Bảng "measure → dùng ở trang nào": `powerbi/README.md` mục Measures.
- **Trục thời gian**: tháng liên tục 01/2017 – 08/2018 dùng `dim_date[year_month]`; so cùng kỳ (Q1) dùng `month` / `month_name` + legend `year`. Lọc kỳ phân tích: `dim_date[is_analysis_period] = TRUE`.
- **M1 / M2 (cùng kỳ)** chỉ có giá trị khi khung đang xét nằm trong 01–08/2018; thẻ đặt trên cả kỳ 01/2017 – 08/2018 sẽ ra BLANK – muốn thẻ "+138%" cố định thì viết thêm 1 measure riêng (`powerbi_rules.md` B5.3, ghi chú).
- **Địa lý**: `dim_geography` = nơi nhận hàng của đơn (bang khách); bang người bán lấy `dim_seller[seller_state]`. Hierarchy Vùng → Bang → Thành phố có ở cả 3 bảng `dim_geography`, `dim_seller`, `dim_customer`.
- **Nhóm số ngày trễ** (`delay_bucket`) đã tự sắp đúng thứ tự Đúng hạn → … → Không xác định.
- **Mỗi lần chỉ 1 người mở và lưu file `.pbix`** (Git không gộp được file nhị phân). Đổi tên / xóa measure → báo cả nhóm vì visual đang dùng sẽ lỗi.

## 6. Sửa model sau này

- Thêm / sửa measure trong Power BI → chép DAX mới vào `powerbi/measures.dax` và cập nhật bảng Measures trong `powerbi/README.md` cùng commit.
- Chuỗi so sánh trong DAX (`"Trễ hạn"`, `"Đúng hạn"`, `"Trễ 1–3 ngày"` – gạch dài `–`) phải giống từng ký tự giá trị dbt sinh ra (`dbt/models/marts/dim_delivery_status.sql`).
- Thiếu cột / số `dds` sai → sửa ở dbt (báo Thanh), không tính bù trong Power Query.
- `dds` đổi cấu trúc (thêm / đổi tên cột) → mở `.pbix`, Refresh; cột mới cần kéo vào model thì *Transform data* chỉ để chọn cột, không biến đổi.

## 7. Kiểm tra lại nhanh

Sau mỗi lần Refresh, mở **DAX query view** (biểu tượng thứ 4 bên trái) và chạy:

```dax
EVALUATE
CALCULATETABLE (
    ROW (
        "K1 Doanh thu", [Doanh thu],
        "K2 Số đơn", [Số đơn],
        "K6 Tỉ lệ giao trễ", [Tỉ lệ giao trễ],
        "K8 Điểm TB", [Điểm đánh giá TB],
        "K13 Top 10%", [Tỷ trọng doanh thu top 10% người bán]
    ),
    dim_date[is_analysis_period] = TRUE ()
)
```

Phải ra 13.449.529,68 · 97.905 · 0,0679 · 4,089 · 0,6738 (khi `dds` đủ 10 batch, không đơn nào bị xóa mềm). Lệch → kiểm `dds` bằng `sql/checks/02_dds_checks.sql` trước khi nghi model.

## 8. Viết báo cáo

Gợi ý ý chính và hình / bảng cần có: `powerbi_rules.md` mục B9. Nguồn số liệu: `powerbi/README.md` (bảng Nghiệm thu B6 có cột "Power BI ra", Kiểm thử B7); ảnh `docs/images/powerbi_model.png` (ảnh lược đồ draw.io ở `docs/images/dds/` nét hơn nếu cần in). DAX tiêu biểu nên trích: K6 (đếm đơn riêng biệt), K8 (`is_latest_review`), M5 (kiểm BLANK) – lấy từ `powerbi/measures.dax`.

## 9. Việc còn mở

- Hằng upload **Replace** file chung trên OneDrive bằng `olist_dashboard.pbix` (giữ tên `Dashboard seminar [Group-3].pbix`).
- Task dashboard: vẽ 3 trang + trang ẩn "Chi tiết người bán" theo phác thảo `powerbi/README.md`.
