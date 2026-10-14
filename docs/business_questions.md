# Bài toán & Câu hỏi nghiệp vụ

> Căn cứ: [data_dictionary.md](data_dictionary.md), [data_profiling.md](data_profiling.md), [decisions.md](decisions.md).
> Phạm vi phân tích xu hướng: đơn mua **01/2017 – 08/2018** (99.092 đơn, 99,6%). Tiền tệ BRL.
> Số liệu ở cột "Kiểm chứng sơ bộ" tính trực tiếp trên 9 file CSV gốc (chưa qua DW), chỉ để xác nhận câu hỏi trả lời được –
> số chính thức lấy từ `dds` sau khi dựng xong và có thể lệch nhẹ do làm sạch (`is_date_valid`, gộp review…).

## 1. Bối cảnh ứng dụng

Hệ thống phục vụ **ban quản lý sàn Olist** – đơn vị vận hành nền tảng kết nối hàng nghìn cửa hàng nhỏ với các sàn TMĐT lớn ở Brazil.
Olist không tự bán hàng mà thu phí trên giá trị giao dịch, nên lợi ích của sàn phụ thuộc vào: (1) quy mô và tăng trưởng giao dịch,
(2) trải nghiệm giao hàng để khách hài lòng và quay lại, (3) chất lượng của mạng lưới người bán.

Vấn đề hiện tại:
- Dữ liệu đơn hàng, thanh toán, vận chuyển, đánh giá nằm ở 9 bảng rời; báo cáo phải tổng hợp thủ công, dễ tính sai
  (nhân dòng khi nối bảng, nhầm `customer_id` với khách thật, trùng `review_id`).
- Doanh thu 01–08/2018 tăng mạnh so với cùng kỳ, nhưng tỉ lệ giao trễ có những tháng tăng đột biến (11/2017, 02–03/2018)
  và đơn giao trễ bị đánh giá thấp rõ rệt → cần biết **trễ ở đâu, do ai, ảnh hưởng thế nào**.
- Tỉ lệ khách quay lại rất thấp (~2,3%) → tăng trưởng dựa gần như hoàn toàn vào khách mới, trải nghiệm lần mua đầu càng quan trọng.

## 2. Mục tiêu phân tích

1. **Theo dõi tình hình kinh doanh**: doanh thu, số đơn, giá trị đơn trung bình, khách hàng theo thời gian, khu vực, danh mục; so sánh cùng kỳ.
2. **Chẩn đoán chất lượng giao hàng và mức độ hài lòng**: tìm khu vực, thời điểm, khâu gây giao trễ và lượng hóa tác động của giao trễ lên điểm đánh giá.
3. **Tách nguyên nhân giao trễ và đánh giá người bán**: giao trễ do người bán bàn giao chậm hay do vận chuyển; người bán nào cần ưu tiên xử lý.

## 3. Đối tượng sử dụng

| Đối tượng | Nhu cầu | Dashboard sử dụng |
|-----------|---------|-------------------|
| Ban giám đốc | Nắm nhanh KPI tổng, tăng trưởng so với cùng kỳ, đọc tóm tắt do AI tạo | Trang 1 – Tổng quan kinh doanh + AI Summary |
| Quản lý kinh doanh / marketing | Danh mục, khu vực đóng góp doanh thu; tỉ lệ khách quay lại | Trang 1 |
| Quản lý vận hành – logistics | Bang/vùng giao trễ, thời gian giao; nguyên nhân tháng trễ bất thường | Trang 2 – Giao hàng & trải nghiệm khách hàng |
| Quản lý quan hệ người bán / logistics | Giao trễ do người bán hay do vận chuyển; người bán bàn giao trễ, bị đánh giá thấp | Trang 3 – Người bán & vận chuyển |
| Chuyên viên phân tích | Drill-down/drill-through, hỏi đáp bằng ngôn ngữ tự nhiên với AI | Cả 3 trang + AI Q&A |

## 4. Khả năng phân tích của dữ liệu

### 4.1. Các chiều phân tích có sẵn

| Chiều (dimension) | Thuộc tính / phân cấp | Nguồn | Ghi chú |
|---|---|---|---|
| Thời gian | Năm → Quý → Tháng → Ngày; thứ trong tuần; giờ đặt | `orders.order_purchase_timestamp` | Mốc chính. Cũng dựng được ngày giao, ngày dự kiến, ngày trả lời review (role-playing date) |
| Địa lý khách hàng | **Vùng (5 vùng)** → Bang (27) → Thành phố | `customers` (+ seed vùng) | Vùng không có sẵn → thêm dbt seed `state → region`. Thành phố bẩn → ưu tiên phân tích theo bang |
| Khách hàng | `customer_unique_id`; số lần mua; khách mới / quay lại | `customers` | Không có tuổi, giới tính, thu nhập |
| Sản phẩm | Danh mục (73 + `unknown`); khối lượng, kích thước, số ảnh, độ dài mô tả | `products`, `category_translation` | Không có tên sản phẩm, không có thương hiệu |
| Người bán | `seller_id`; Vùng → Bang → Thành phố | `sellers` | 3.095 người bán; SP chiếm 60% |
| Trạng thái đơn | delivered, shipped, canceled, unavailable… | `orders.order_status` | Chỉ có trạng thái cuối, không có lịch sử |
| Thanh toán | Phương thức (credit_card, boleto, voucher, debit_card); số kỳ trả góp | `order_payments` | |
| Đánh giá | Điểm 1–5; có / không có bình luận | `order_reviews` | Bình luận tiếng Bồ Đào Nha → đầu vào cho AI |
| Thuộc tính suy ra | Giao trễ / đúng hạn; số ngày trễ (nhóm); nội bang / liên bang; người bán bàn giao trễ | Tính ở dbt | Không có trong nguồn, tạo từ các cột ngày và bang |

### 4.2. Dữ liệu **không** cho phép phân tích

| Không phân tích được | Lý do |
|---|---|
| Lợi nhuận, biên lợi nhuận, phí hoa hồng Olist | Không có giá vốn, chi phí, phí sàn |
| Hiệu quả marketing, kênh bán, sàn nào bán | Không có dữ liệu kênh / chiến dịch / sàn đối tác |
| Chân dung nhân khẩu học khách hàng | Không có tuổi, giới tính, thu nhập |
| Tồn kho, hoàn trả – đổi hàng | Không có bảng tồn kho, không có trạng thái trả hàng |
| Thời gian đơn nằm ở từng trạng thái | Chỉ có trạng thái cuối (xem data_profiling.md mục 15) |
| Đơn vị vận chuyển nào giao trễ | Không có mã hãng vận chuyển |
| Xu hướng trước 01/2017 và sau 08/2018 | Dữ liệu quá thưa / bị cắt |

## 5. Câu hỏi nghiệp vụ

Hệ thống gồm **3 trang dashboard**, mỗi trang trả lời **2 câu hỏi**, mỗi câu hỏi dùng **2 biểu đồ** (tổng 6 câu hỏi, 12 biểu đồ):
trang 1 là phân tích mô tả (Overview), trang 2 và 3 là phân tích chẩn đoán (Diagnostic). Dashboard theo dõi ETL (bonus) không nằm trong danh sách này.

**Nguyên tắc:**
- Câu hỏi viết theo **SMART**: nêu rõ chỉ số (Specific), đơn vị/ngưỡng đo được (Measurable), có đủ dữ liệu để trả lời (Achievable),
  gắn với một quyết định quản lý (Relevant), có phạm vi thời gian **01/2017 – 08/2018** (Time-bound).
- Hai biểu đồ của một câu hỏi bổ sung cho nhau: biểu đồ (1) cho biết **hiện tượng** (cái gì, khi nào, ở đâu),
  biểu đồ (2) **giải thích hoặc khoanh vùng** (vì sao, do ai, mức độ).
- Hàng thẻ KPI đầu trang cho bức tranh tổng quan của chủ đề; câu trả lời cho từng câu hỏi nằm ở biểu đồ.
  Bố cục chi tiết: [powerbi/README.md](../powerbi/README.md).

### 5.1. Trang 1 – Tổng quan kinh doanh (Descriptive)

Thẻ KPI: K1 Doanh thu (kèm % so với cùng kỳ), K2 Số đơn, K3 AOV, K4 Số khách hàng, K5 Tỉ lệ khách mua lại.

| # | Câu hỏi (SMART) | Biểu đồ (1) – hiện tượng | Biểu đồ (2) – giải thích | Measure | Kiểm chứng sơ bộ |
|---|---|---|---|---|---|
| Q1 | Trong 01/2017 – 08/2018, doanh thu theo tháng biến động thế nào, doanh thu 01–08/2018 tăng bao nhiêu % so với 01–08/2017, và mức tăng đó đến từ tăng số đơn hay tăng giá trị đơn trung bình? | Line chart: X = tháng 1–12, Legend = năm (2017, 2018), Y = Doanh thu; tooltip % YoY (chỉ có ở 01–08/2018, xem M2) → thấy tháng đỉnh và khoảng cách 2018 so với 2017 | Combo chart: X = tháng (01/2017 – 08/2018), cột = Số đơn, đường = AOV (trục phụ) → thấy thành phần nào kéo doanh thu tăng | K1, K2, K3, M1, M2 | Đỉnh 11/2017. 01–08: doanh thu 3,08 → 7,34 tr BRL (+138%); số đơn 22.562 → 53.530 (+137%); AOV 136,6 → 137,1 BRL (gần như không đổi) → tăng trưởng hoàn toàn nhờ số đơn |
| Q2 | Trong 01/2017 – 08/2018, 10 danh mục và 5 bang có doanh thu cao nhất là những đâu và chiếm bao nhiêu % tổng doanh thu? | Clustered bar chart: top 10 danh mục theo doanh thu, nhãn % tổng doanh thu | Filled map theo bang (drill Vùng → Bang), màu = doanh thu; click 1 bang → biểu đồ (1) đổi thành top danh mục của bang đó | K1, M3 | Top 10 danh mục = 62% (health_beauty 9,3%, watches_gifts 8,9%, bed_bath_table 7,7%). Top 5 bang = 74% (SP 38,3%, RJ 13,4%, MG 11,7%, RS 5,5%, PR 5,0%) |

### 5.2. Trang 2 – Giao hàng & trải nghiệm khách hàng (Diagnostic)

Thẻ KPI: K6 Tỉ lệ giao trễ, K7 Thời gian giao TB, K8 Điểm đánh giá TB, K9 Tỉ lệ đánh giá tiêu cực.

| # | Câu hỏi (SMART) | Biểu đồ (1) – hiện tượng | Biểu đồ (2) – giải thích | Measure | Kiểm chứng sơ bộ |
|---|---|---|---|---|---|
| Q3 | Trong 01/2017 – 08/2018, những tháng nào có tỉ lệ giao trễ vượt ngưỡng 10%, và bang nào có tỉ lệ giao trễ cao nhất? | Line chart: X = tháng, Y = Tỉ lệ giao trễ, constant line 10% | Clustered bar chart: Y = bang (sắp giảm dần), X = Tỉ lệ giao trễ, tô đỏ bang > 10%; tooltip số đơn delivered; click 1 tháng ở (1) → (2) lọc theo tháng đó (bang nhỏ chỉ còn vài chục đơn/tháng → tỉ lệ dao động mạnh, đọc kèm số đơn) | K6 | Vượt 10%: 11/2017 (12,4%), 02/2018 (14,1%), 03/2018 (19,0%). Toàn kỳ cao nhất AL 21,5%, MA 17,5%, SE 15,4% |
| Q4 | Trong 01/2017 – 08/2018, điểm đánh giá TB của đơn giao trễ thấp hơn đơn đúng hạn bao nhiêu sao, và những tháng giao trễ tăng thì điểm đánh giá chung có giảm theo không? | Clustered column chart: X = nhóm số ngày trễ (đúng hạn, 1–3, 4–7, 8–14, > 14), Y = Điểm TB, constant line = điểm TB toàn sàn | Line chart 2 trục: X = tháng, trục trái = Tỉ lệ giao trễ, trục phải = Điểm TB | K6, K8 | Đúng hạn 4,29★ vs trễ 2,27★; theo nhóm: 1–3 ngày 3,29★, 4–7 ngày 2,10★, 8–14 ngày 1,67★, > 14 ngày 1,72★ (từ 8 ngày trở đi điểm chạm đáy, không giảm tiếp). Theo tháng: tương quan −0,92; 03/2018 trễ cao nhất → điểm thấp nhất (3,81★) |

### 5.3. Trang 3 – Người bán & vận chuyển (Diagnostic)

Thẻ KPI: K10 Số người bán hoạt động, K11 Doanh thu TB mỗi người bán, K12 Tỉ lệ người bán bàn giao trễ, K13 Tỷ trọng doanh thu top 10% người bán.

| # | Câu hỏi (SMART) | Biểu đồ (1) – hiện tượng | Biểu đồ (2) – giải thích | Measure | Kiểm chứng sơ bộ |
|---|---|---|---|---|---|
| Q5 | Trong 01/2017 – 08/2018, người bán bàn giao trễ làm tỉ lệ giao trễ tăng bao nhiêu lần, và các tháng giao trễ đột biến (11/2017, 02–03/2018) là do người bán bàn giao chậm hay do thời gian vận chuyển kéo dài? | Clustered column chart: X = người bán bàn giao đúng hạn / trễ, Legend = nội bang / liên bang, Y = Tỉ lệ giao trễ | Line chart 2 trục: X = tháng, trục trái = Tỉ lệ người bán bàn giao trễ, trục phải = Thời gian vận chuyển TB (ngày, từ bàn giao đến khách nhận) | K6, K12, M4 | Bàn giao trễ → 21,0% đơn giao trễ, bàn giao đúng hạn → 5,3% (≈ 4 lần); tách theo tuyến: đúng hạn 2,9% (nội bang) / 6,7% (liên bang). Tháng bình thường (10/2017, 04/2018): bàn giao trễ 6–8%, vận chuyển ~8,5 ngày. **11/2017** (bàn giao trễ 12,8%, vận chuyển 11,1 ngày) và **02/2018** (12,2%, 13,4 ngày) → do **cả hai khâu**; **03/2018** (8,4%, 13,0 ngày) → bàn giao bình thường, đột biến do **khâu vận chuyển** |
| Q6 | Trong số người bán có từ 30 đơn trở lên (01/2017 – 08/2018), những ai có điểm đánh giá TB < 3,5 hoặc tỉ lệ bàn giao trễ > 10%, và 10 người bán nào trong số đó có doanh thu lớn nhất cần ưu tiên xử lý? | Scatter chart: mỗi điểm = 1 người bán (≥ 30 đơn), X = Tỉ lệ bàn giao trễ, Y = Điểm TB, Size = Doanh thu, 2 constant line (10%, 3,5) chia 4 góc phần tư | Clustered bar chart: top 10 người bán vượt ngưỡng theo doanh thu, tooltip điểm TB và tỉ lệ bàn giao trễ; chuột phải → drill-through trang ẩn "Chi tiết người bán" | K1, K2, K8, K12, M5 | 191 / 633 người bán vượt ít nhất 1 ngưỡng (24 điểm < 3,5; 188 bàn giao trễ > 10%; 21 vi phạm cả hai), chiếm 21,9% doanh thu. Cách tính theo định nghĩa ở M5 |

## 6. Danh sách KPIs / Measures

13 KPI hiển thị trên thẻ (trang 1: 5, trang 2: 4, trang 3: 4) và 5 measure bổ trợ dùng trong biểu đồ.

Quy ước chung:
- **Đơn hợp lệ** = đơn có trạng thái khác `canceled`, `unavailable` và có ít nhất 1 dòng `order_items`.
- Doanh thu tính từ `order_items.price`, **không** dùng `order_payments` (lệch ở 249 đơn do lãi trả góp, voucher).
- KPI giao hàng chỉ tính trên đơn `delivered` có ngày hợp lệ (`is_date_valid = 1`); so trễ hạn **theo ngày**.
- KPI đánh giá giữ **1 dòng/đơn** (tránh nhân dòng do `review_id` dùng chung).

| Mã | KPI | Trang | Định nghĩa nghiệp vụ | Công thức | Đơn vị | Ngưỡng tốt/xấu (nhóm đề xuất) |
|----|-----|-------|----------------------|-----------|--------|-------------------------------|
| K1 | Doanh thu | 1 | Tổng giá trị hàng bán của đơn hợp lệ, không gồm phí vận chuyển. Thẻ hiển thị kèm % so với cùng kỳ (M2) | `SUM(price)` trên đơn hợp lệ | BRL | So với cùng kỳ (chỉ so được 01–08/2018 vs 2017) |
| K2 | Số đơn hàng | 1 | Số đơn hợp lệ | `COUNT(DISTINCT order_id)` | Đơn | So với cùng kỳ |
| K3 | Giá trị đơn trung bình (AOV) | 1 | Doanh thu bình quân mỗi đơn | K1 / K2 | BRL/đơn | – |
| K4 | Số khách hàng | 1 | Số khách thực có đơn hợp lệ trong kỳ | `COUNT(DISTINCT customer_unique_id)` | Khách | So với cùng kỳ |
| K5 | Tỉ lệ khách mua lại | 1 | % khách có từ 2 lần mua trở lên (các đơn cách nhau ≤ 10 phút gộp thành 1 lần mua) | Số khách ≥ 2 lần mua / K4 | % | Thấp → insight, không đặt mục tiêu. Đơn hợp lệ 01/2017 – 08/2018: 2,26% (toàn bộ dữ liệu: 2,34%, xem decisions.md) |
| K6 | Tỉ lệ giao trễ | 2 | % đơn đã giao mà khách nhận sau ngày giao dự kiến | Đơn có `DATE(delivered_customer_date) > estimated_delivery_date` / số đơn delivered hợp lệ | % | ≤ 5% tốt; > 10% cảnh báo |
| K7 | Thời gian giao trung bình | 2 | Số ngày từ lúc đặt đến lúc khách nhận | `AVG(delivered_customer_date − purchase_timestamp)` | Ngày | Càng thấp càng tốt. Tháng 08/2018 bị cắt dữ liệu → không đại diện |
| K8 | Điểm đánh giá trung bình | 2 | Mức hài lòng trung bình | `AVG(review_score)` (1 dòng/đơn) | Sao (1–5) | ≥ 4,0 tốt; < 3,5 cảnh báo |
| K9 | Tỉ lệ đánh giá tiêu cực | 2 | % đơn bị đánh giá 1–2 sao | Đơn có score ≤ 2 / đơn có review | % | ≤ 10% tốt; > 20% cảnh báo |
| K10 | Số người bán hoạt động | 3 | Số người bán có ít nhất 1 đơn hợp lệ trong kỳ | `COUNT(DISTINCT seller_id)` trên **fact** (không đếm dòng `dim_seller`, xem decisions.md D3) | Người bán | So với cùng kỳ |
| K11 | Doanh thu trung bình mỗi người bán | 3 | Quy mô bán hàng bình quân của một người bán | K1 / K10 | BRL | – |
| K12 | Tỉ lệ người bán bàn giao trễ | 3 | % lượt (đơn, người bán) giao cho vận chuyển sau hạn `shipping_limit_date` | Lượt có `delivered_carrier_date > shipping_limit_date` / lượt có ngày giao vận chuyển | % | ≤ 5% tốt; > 10% cảnh báo |
| K13 | Tỷ trọng doanh thu top 10% người bán | 3 | Mức độ tập trung doanh thu vào nhóm người bán lớn | Doanh thu của 10% người bán dẫn đầu / K1 | % | Cao → rủi ro phụ thuộc |

> Lưu ý K12: `delivered_carrier_date` ở cấp **đơn**, còn `shipping_limit_date` ở cấp **dòng hàng**; với 1.278 đơn nhiều người bán,
> ngày bàn giao là của cả đơn nên kết quả là xấp xỉ. Ghi rõ trong báo cáo.
>
> Lưu ý K8 theo người bán (Q6): review gắn với **đơn**, không gắn với người bán → đơn nhiều người bán thì mọi người bán
> trong đơn nhận chung một điểm. Cũng là giá trị xấp xỉ như K12.

**Measure bổ trợ cho biểu đồ** (không hiển thị trên thẻ):

| Mã | Measure | Công thức | Dùng cho |
|---|---|---|---|
| M1 | Doanh thu cùng kỳ | K1 của cùng tháng năm trước (`SAMEPERIODLASTYEAR`); trả về BLANK nếu kỳ đang xét không nằm trong 01–08/2018 | Q1 |
| M2 | % tăng trưởng so với cùng kỳ (YoY) | (K1 − M1) / M1; BLANK khi M1 BLANK | Q1, thẻ K1 |
| M3 | % tổng doanh thu | K1 / K1 toàn bộ (bỏ bộ lọc danh mục/bang) | Q2 |
| M4 | Thời gian vận chuyển trung bình | `AVG(delivered_customer_date − delivered_carrier_date)` trên đơn delivered hợp lệ (ngày) | Q5 |
| M5 | Cờ người bán cần xử lý | 1 nếu người bán có ≥ 30 đơn **và** (K8 < 3,5 **hoặc** K12 > 10%), ngược lại 0; dùng làm filter visual. Số đơn = đơn hợp lệ có hàng của người bán trong kỳ; K8 = TB điểm (1 dòng/đơn) trên các đơn đó; K12 = tỉ lệ bàn giao trễ trên các lượt (đơn, người bán) của người bán trong kỳ | Q6 |

> Lý do chặn M1/M2: tháng 10/2016 có 324 đơn, còn các tháng khác của 2016 gần như không có đơn. `SAMEPERIODLASTYEAR` ghi đè bộ lọc
> ngày của trang → nếu không chặn, tooltip 10/2017 so với 10/2016 sẽ ra mức tăng hàng nghìn %, các tháng 2017 khác ra BLANK/∞.

## 7. Ánh xạ câu hỏi → quy trình nghiệp vụ (đầu vào cho thiết kế DW)

| Quy trình | Câu hỏi | Bảng nguồn chính | Grain nhỏ nhất cần |
|---|---|---|---|
| Bán hàng | Q1, Q2, Q6 | `order_items` (+ `orders`, `customers`, `products`, `sellers`) | 1 dòng sản phẩm trong 1 đơn |
| Giao hàng | Q3, Q4, Q5, Q6 | `orders` (+ `order_items` cho người bán, hạn bàn giao) | 1 đơn (hoặc 1 đơn – 1 người bán cho K12) |
| Đánh giá | Q4, Q6 | `order_reviews` | 1 đánh giá của 1 đơn |

Thanh toán (`order_payments`) không có câu hỏi nào dùng tới → không cần fact riêng (theo Bước 2 Chương 5).

## 8. Câu hỏi dành cho AI

AI chỉ nhận số liệu đã tính từ `dds` (KPI dạng JSON) và phải trích dẫn lại số liệu; không tự tính hoặc bịa số.

1. **Tóm tắt (AI Summary)**: "Tóm tắt tình hình kinh doanh tháng 03/2018" → AI nêu 13 KPI của tháng, so với tháng trước và cùng kỳ, chỉ ra KPI vượt ngưỡng.
2. **Giải thích biến động**: "Vì sao tỉ lệ giao trễ tháng 03/2018 tăng mạnh?" → đầu vào là dữ liệu của Q3 và Q5 (tỉ lệ trễ theo bang, tỉ lệ bàn giao trễ, thời gian vận chuyển theo tháng); AI chỉ ra yếu tố đóng góp lớn nhất và tách rõ *sự thật từ dữ liệu* với *giả thuyết*.
3. **Hỏi đáp tự nhiên**: "Top 5 danh mục doanh thu năm 2018?", "Bang nào giao trễ nhiều nhất?", "Người bán nào cần xử lý?" → câu hỏi được ánh xạ sang truy vấn có sẵn trên `dds`, AI trả lời kèm số liệu.
