# Quyết định thiết kế: khóa & nạp incremental (BS-5)

> Ngày chốt: 10/10/2026 · DB: PostgreSQL 17 (đổi từ SQL Server ngày 14/10/2026) · Căn cứ: [data_profiling.md](data_profiling.md) và kết quả chạy `py scripts/check_keys.py`
> (mọi số liệu dưới đây lấy từ script này, chạy trên 9 file gốc trong `data/raw/`).
> Mỗi quyết định gồm: **Quyết định / Lý do / Số liệu chứng minh / Rủi ro**.

## Tóm tắt

| # | Chủ đề | Quyết định ngắn |
|---|---|---|
| D1 | Khóa chính | 8 bảng có khóa unique đã kiểm chứng; `order_reviews` dùng khóa ghép (`review_id`, `order_id`); `geolocation` không có khóa |
| D2 | Khóa ngoại | 6 FK bắt buộc (0 mồ côi), 3 FK mềm (cho phép không khớp, LEFT JOIN) |
| D3 | Phân loại bảng | Giao dịch (theo tháng): `orders`, `order_items`, `order_payments`, `order_reviews`, `customers`. Tham chiếu (1 lần): `products`, `sellers`, `category_translation`, `geolocation` |
| D4 | Watermark | `orders.order_purchase_timestamp`, cửa sổ theo tháng `[đầu tháng, đầu tháng sau)`; nạp bằng **MERGE theo khóa chính** |
| D5 | Bảng con | `order_items`, `order_payments`, `customers` đi theo batch **đầu tiên** của đơn; `order_reviews` đi theo tháng khách **trả lời** review |
| D6 | Ranh giới batch | Full Load = đơn mua đến hết **2017-12**; Incremental = 8 batch **2018-01 … 2018-08** + batch cuối **2018-09+** (đơn mới + đối soát về trạng thái gốc) |
| D7 | Khách hàng | `dim_customer` khóa nghiệp vụ = `customer_unique_id`, khóa thay thế `customer_key`; SCD type 1 cho địa chỉ |
| D8 | Mô phỏng cập nhật | **Phương án B**: mỗi batch chỉ chứa những gì đã biết đến cuối tháng đó; đơn cũ có thay đổi được gửi lại ở batch sau → MERGE có cả INSERT và UPDATE |

---

## D1. Khóa chính của từng bảng

**Quyết định**

| Bảng | Khóa chính | Ghi chú |
|---|---|---|
| `orders` | `order_id` | |
| `order_items` | (`order_id`, `order_item_id`) | `order_item_id` = số thứ tự 1..n trong đơn |
| `order_payments` | (`order_id`, `payment_sequential`) | |
| `order_reviews` | (`review_id`, `order_id`) | **Không** dùng riêng `review_id` |
| `customers` | `customer_id` | Mã theo đơn – xem D7 |
| `sellers` | `seller_id` | |
| `products` | `product_id` | |
| `category_translation` | `product_category_name` | |
| `geolocation` | *(không có)* | Ở dbt gom về 1 dòng/zip → khóa `zip_code_prefix` của bảng đã gom |

**Lý do:** chọn khóa nhỏ nhất vừa unique vừa không NULL trên dữ liệu thật; với bảng con, khóa phải chứa `order_id` để MERGE theo batch (D4, D5).

**Số liệu chứng minh** (số dòng = số khóa khác nhau, 0 dòng trùng, 0 NULL trong cột khóa):

| Bảng | Số dòng | Khóa khác nhau | Trùng | NULL |
|---|---|---|---|---|
| orders | 99.441 | 99.441 | 0 | 0 |
| order_items | 112.650 | 112.650 | 0 | 0 |
| order_payments | 103.886 | 103.886 | 0 | 0 |
| order_reviews | 99.224 | 99.224 | 0 | 0 |
| customers | 99.441 | 99.441 | 0 | 0 |
| sellers | 3.095 | 3.095 | 0 | 0 |
| products | 32.951 | 32.951 | 0 | 0 |
| category_translation | 71 | 71 | 0 | 0 |

Các cột "trông giống khóa" nhưng **không** unique: `order_reviews.review_id` (814 dòng trùng), `order_reviews.order_id` (551), `customers.customer_unique_id` (3.345), `order_items.order_id` (13.984), `geolocation.zip` (981.148), `geolocation`(zip, lat, lng) (280.009).

**Rủi ro**
- Khóa của `order_reviews` đúng trên dữ liệu hiện tại nhưng là khóa *suy ra*, không phải khóa do nguồn công bố. → dbt test `dbt_utils.unique_combination_of_columns` trên (`review_id`, `order_id`) ở mỗi lần chạy.
- `payment_sequential` có 80 đơn bị đứt quãng (VD 1, 3) – vẫn unique nên dùng làm khóa được, nhưng không dùng để đếm số lần thanh toán.

## D2. Khóa ngoại

**Quyết định**

| Bảng con.cột | → Bảng cha.cột | Loại | Xử lý |
|---|---|---|---|
| `orders.customer_id` | `customers.customer_id` | Bắt buộc | dbt test `relationships` |
| `order_items.order_id` | `orders.order_id` | Bắt buộc | dbt test `relationships` |
| `order_items.product_id` | `products.product_id` | Bắt buộc | dbt test `relationships` |
| `order_items.seller_id` | `sellers.seller_id` | Bắt buộc | dbt test `relationships` |
| `order_payments.order_id` | `orders.order_id` | Bắt buộc | dbt test `relationships` |
| `order_reviews.order_id` | `orders.order_id` | Bắt buộc | dbt test `relationships` |
| `products.product_category_name` | `category_translation.product_category_name` | Mềm | LEFT JOIN; bổ sung 2 bản dịch bằng dbt seed; NULL → `unknown` |
| `customers.customer_zip_code_prefix` | `geolocation` (đã gom theo zip) | Mềm | LEFT JOIN, tọa độ NULL |
| `sellers.seller_zip_code_prefix` | `geolocation` (đã gom theo zip) | Mềm | LEFT JOIN, tọa độ NULL |

**Lý do:** FK bắt buộc khớp 100% trên dữ liệu thật nên kiểm tra được bằng test; FK mềm có dòng không khớp từ nguồn nên không thể ép buộc mà không mất dữ liệu.

**Số liệu chứng minh:** dòng mồ côi / dòng kiểm tra – 6 FK bắt buộc: **0** cho tất cả. FK mềm: category 13 / 32.341, zip khách 278 / 99.441, zip người bán 7 / 3.095.

**Rủi ro**
- Không tạo FK constraint vật lý trên bảng `staging` (Mage nạp từng bảng, thứ tự có thể đổi khi chạy lại) – FK chỉ kiểm tra bằng dbt test và đặt constraint ở tầng `dds` nếu cần.
- Nếu D3 thay đổi (VD nạp `products` theo tháng) thì FK `order_items.product_id` có thể tạm mồ côi giữa các batch.

## D3. Phân loại bảng

**Quyết định**

| Loại | Bảng | Cách nạp |
|---|---|---|
| **Giao dịch** | `orders`, `order_items`, `order_payments`, `order_reviews`, `customers` | Full Load phần lịch sử, sau đó Incremental theo tháng mua (D6) |
| **Tham chiếu / chiều** | `products`, `sellers`, `category_translation`, `geolocation` | Nạp **toàn bộ 1 lần** trong Full Load |

**Lý do**
- 4 bảng đầu là sự kiện gắn với một đơn và một thời điểm mua.
- `customers` xếp vào nhóm giao dịch vì `customer_id` là mã **theo từng đơn** (quan hệ 1–1 với `orders`): nạp toàn bộ một lần sẽ đưa vào staging khách của những đơn chưa xảy ra.
- 4 bảng tham chiếu không có cột thời gian, nên không có căn cứ để chia theo tháng; nạp trước giúp mọi batch giao dịch luôn thỏa FK.

**Số liệu chứng minh**
- `orders.customer_id` → mỗi customer_id có tối đa **1** đơn; 99.441 customer_id = 99.441 đơn.
- Không bảng tham chiếu nào có cột ngày; `geolocation` 1.000.163 dòng, `category_translation` 71 dòng.

**Rủi ro**
- *(Đã cân nhắc nạp `products` / `sellers` theo lần bán đầu tiên – thực tế hơn nhưng phức tạp và dễ vướng FK giữa các batch. Nhóm chốt 10/10/2026: **giữ nạp 1 lần**.)*
- Dimension chứa sẵn thực thể "của tương lai": **47,0%** sản phẩm (15.500 / 32.951) và **41,5%** người bán (1.284 / 3.095) chỉ bán lần đầu sau Full Load. → KPI như *số người bán đang hoạt động* phải đếm từ fact (có đơn trong kỳ), **không** đếm số dòng của dimension.
- Không lưu được thay đổi thuộc tính sản phẩm/người bán theo thời gian (nguồn cũng không có lịch sử).

## D4. Cột watermark cho Incremental

**Quyết định**
1. Watermark = `orders.order_purchase_timestamp`. Một batch = các đơn có `order_purchase_timestamp >= đầu tháng` **và** `< đầu tháng sau` (khoảng nửa mở).
2. Ghi vào `etl_log` cho mỗi lần chạy: `batch_id`, `watermark_from`, `watermark_to`, số dòng từng bảng, trạng thái, lỗi.
3. Mọi bảng giao dịch nạp vào staging bằng **`MERGE` theo khóa chính (D1)**, không dùng `INSERT` thuần → chạy lại cùng batch không sinh trùng; batch sau gửi lại đơn cũ thì đơn đó được **cập nhật**. MERGE **không xóa** dòng vắng mặt trong batch (không dùng `WHEN NOT MATCHED BY SOURCE ... DELETE`), vì mỗi batch chỉ là một phần dữ liệu.
4. Watermark quyết định đơn **mới** thuộc batch nào. Nội dung batch theo **phương án B (D8)**: chỉ chứa thông tin đã biết đến cuối tháng; đơn cũ có thay đổi trong tháng được gửi lại.

**Lý do**
- Là cột thời gian duy nhất **không NULL** ở mọi đơn và xảy ra **đầu tiên** trong vòng đời đơn – mỗi đơn rơi vào đúng 1 batch, không bao giờ đổi batch.
- Nguồn **không có** cột `updated_at` / `last_modified` nào, nên không có watermark kiểu "thay đổi gần nhất".
- Cột khác đều có NULL: `order_approved_at` 160, `order_delivered_carrier_date` 1.783, `order_delivered_customer_date` 2.965 → đơn chưa giao sẽ không thuộc batch nào.
- Cắt theo khoảng nửa mở `[from, to)` thay vì "`> giá trị lớn nhất đã nạp`": 556 mốc thời gian dùng chung bởi 1.122 đơn, so sánh `>` trên timestamp có nguy cơ bỏ sót đơn trùng giây nếu batch bị cắt giữa chừng.

**Số liệu chứng minh – điểm yếu: dữ liệu đến muộn so với cuối batch** (% đơn / review có mốc xảy ra **sau** ngày cuối của tháng batch):

| Batch | approved_at | delivered_carrier | delivered_customer | review_answer |
|---|---|---|---|---|
| FULL | 1,8% | 10,7% | 39,5% | 51,9% |
| 2018-01 | 1,9% | 10,1% | 39,7% | 52,5% |
| 2018-02 | 2,3% | 11,6% | 51,7% | 64,3% |
| 2018-03 | 1,1% | 10,4% | 48,5% | 54,8% |
| 2018-04 | 3,4% | 9,3% | 37,1% | 47,0% |
| 2018-05 | 0,6% | 6,7% | 34,1% | 38,2% |
| 2018-06 | 0,7% | 8,1% | 27,1% | 39,8% |
| 2018-07 | 2,6% | 10,5% | 31,7% | 46,0% |
| 2018-08 | 0,0% | 0,0% | 0,6% | 9,3% |

→ Trung bình **34,2%** đơn của các batch 2018-01…08 nhận hàng *sau* khi batch của nó kết thúc. Ngoài thực tế, những đơn này lúc nạp phải ở trạng thái `shipped`/`invoiced` và được cập nhật ở các lần chạy sau; dataset chỉ có trạng thái cuối nên nếu giữ nguyên, mỗi batch đã "biết trước" kết quả → lý do chọn phương án B (D8).

**Rủi ro**
- **Không có lịch sử trạng thái gốc**: phương án B tái tạo trạng thái trung gian từ các mốc ngày, nhưng đó là **suy diễn** (chi tiết và giới hạn ở D8). Phải ghi rõ trong báo cáo (mục 15 data_profiling.md).
- **Dữ liệu bị cắt cuối kỳ (right-censoring)**: số đơn/ngày tháng 2018-08 trung bình 273 đơn ở ngày 1–22 rồi rơi còn 144 → 1 đơn ở ngày 23–31; mốc giao vận chuyển muộn nhất 2018-09-11, chỉ 37 đơn giao sau 2018-09-03. Hệ quả: thời gian giao TB theo tháng mua giảm dần 11,5 (04) → 9,2 (06) → 9,0 (07) → **7,7 ngày (08)** – một phần do đơn giao chậm của các tháng cuối chưa/không có trong dữ liệu, không hẳn là vận hành tốt lên. Dashboard không được diễn giải mức giảm này là cải thiện nếu chưa kiểm chứng.
- Timestamp là giờ địa phương Brazil, không có múi giờ; có ngày chuyển giờ mùa hè (15/10/2017). Giữ nguyên, không quy đổi.

## D5. Bảng con đi theo đơn trong tháng

**Quyết định**
- **Batch đầu tiên** của một đơn được xác định **duy nhất từ `orders`**: tháng chứa `order_purchase_timestamp` (đơn đến hết 2017-12 → `FULL`).
- `order_items`, `order_payments`, `customers` là thông tin có ngay lúc mua → đi theo **batch đầu tiên** của đơn (semi-join theo `order_id` / `customer_id`), chỉ gửi 1 lần, **bỏ qua** cột ngày riêng (`shipping_limit_date`, …).
- `order_reviews` chỉ tồn tại sau khi khách trả lời → đi theo batch chứa **`review_answer_timestamp`** (D8), thường là batch sau batch đầu tiên của đơn. Đơn của review đã có ở staging từ batch trước nên FK luôn thỏa.
- `orders` có thể xuất hiện ở **nhiều batch**: lần đầu (đơn mới) và các lần sau khi có mốc mới (D8).
- Thứ tự nạp trong 1 batch: `customers` → `orders` → `order_items`, `order_payments` → `order_reviews` (bảng tham chiếu đã có từ Full Load).
- Đơn không có item (775), không có thanh toán (1), không có review (768) vẫn nạp vào `orders` như bình thường.

**Lý do:** mọi dòng con có đúng 1 `order_id` hợp lệ (0 mồ côi) → mỗi dòng items/payments/customers thuộc đúng 1 batch, tổng khớp tuyệt đối với file gốc. Review tách riêng theo thời điểm trả lời vì đó là lúc review thực sự "xuất hiện" (D8).

**Số liệu chứng minh** – số **đơn mới** và dòng con của chúng theo batch đầu tiên (cột `order_reviews` ở đây tính theo batch của *đơn*; theo phương án B, review sẽ dời sang batch chứa ngày trả lời, số dòng chính xác có khi viết script chia batch):

| Batch | Khoảng mua | orders | order_items | order_payments | order_reviews | customers |
|---|---|---|---|---|---|---|
| FULL | 2016-09-04 → 2017-12-31 | 45.430 | 51.234 | 47.871 | 45.370 | 45.430 |
| 2018-01 | 2018-01-01 → 01-31 | 7.269 | 8.208 | 7.563 | 7.245 | 7.269 |
| 2018-02 | 2018-02-01 → 02-28 | 6.728 | 7.672 | 6.952 | 6.758 | 6.728 |
| 2018-03 | 2018-03-01 → 03-31 | 7.211 | 8.217 | 7.512 | 7.187 | 7.211 |
| 2018-04 | 2018-04-01 → 04-30 | 6.939 | 7.975 | 7.209 | 6.894 | 6.939 |
| 2018-05 | 2018-05-01 → 05-31 | 6.873 | 7.925 | 7.135 | 6.848 | 6.873 |
| 2018-06 | 2018-06-01 → 06-30 | 6.167 | 7.078 | 6.419 | 6.147 | 6.167 |
| 2018-07 | 2018-07-01 → 07-31 | 6.292 | 7.092 | 6.507 | 6.269 | 6.292 |
| 2018-08 | 2018-08-01 → 08-31 | 6.512 | 7.248 | 6.698 | 6.487 | 6.512 |
| 2018-09+ | 2018-09-03 → 10-17 | 20 | 1 | 20 | 19 | 20 |
| **Tổng** | | **99.441** | **112.650** | **103.886** | **99.224** | **99.441** |

Tổng từng cột = đúng số dòng file gốc; số dòng con không gán được batch = 0 ở cả 3 bảng.

**Rủi ro**
- **31 `review_id`** dùng chung cho các đơn nằm ở **2 batch khác nhau** (1 khảo sát cho giỏ hàng bị tách đơn). Vì khóa là (`review_id`, `order_id`) nên MERGE không xung đột; nhưng KPI *số lượt đánh giá* (`COUNT(DISTINCT review_id)`) cộng dồn theo batch sẽ lệch nhẹ nếu tính riêng từng batch rồi cộng lại → luôn tính trên toàn bộ fact.
- Review của đơn tháng T ngoài thực tế thường đến ở tháng T+1 (47,8% trả lời sau tháng mua) – cùng hạn chế ảnh chụp như D4.

## D6. Ranh giới Full Load / Incremental

**Quyết định**
- **Full Load**: mọi đơn mua từ đầu dữ liệu đến hết **2017-12-31** (batch `FULL`). Lõi là **12 tháng dày 2017-01 → 2017-12**; 4 tháng thưa của 2016 (329 đơn) đi kèm làm lịch sử thay vì bỏ đi.
- **Incremental**: 8 batch theo tháng **2018-01 → 2018-08**.
- **Batch cuối `2018-09+`**: gộp 2018-09 và 2018-10 (20 đơn mới), chạy sau cùng, đồng thời là **batch đối soát** (D8): không cắt mốc thời gian nào và gửi lại mọi đơn/review chưa ở trạng thái gốc → sau batch này staging khớp hoàn toàn với file gốc.

**Lý do**
- 2017-01 là tháng đầu tiên dữ liệu liên tục (trước đó: 2016-11 = 0 đơn, 2016-12 = 1 đơn).
- Full Load gồm trọn năm 2017 → có đủ mùa vụ, kể cả đỉnh Black Friday 2017-11 (7.544 đơn, cao nhất cả dataset); sau Incremental, dashboard so sánh được cùng kỳ 2018 vs 2017 (tháng 1–8).
- 8 batch incremental có kích thước đều nhau (6.167 → 7.269 đơn), đủ lớn để demo và kiểm tra log số dòng.
- Giữ batch `2018-09+` thay vì bỏ: tổng các batch khớp file gốc (không mất dữ liệu âm thầm); với phương án B, batch này gần như chỉ gồm **cập nhật** (20 đơn mới) – ca kiểm thử tốt cho nhánh UPDATE.

**Số liệu chứng minh:** FULL 45.430 đơn (45,7%) · 8 batch 2018-01…08 tổng 53.991 đơn (54,3%) · 2018-09+ 20 đơn (16 + 4). Số đơn từng tháng: xem mục 13 data_profiling.md.

**Rủi ro**
- Batch `2018-09+` gần như toàn đơn hủy (15/16 đơn tháng 9 và 4/4 đơn tháng 10 là canceled/unavailable; chỉ 1 dòng order_items) → loại khỏi phân tích xu hướng (giữ khoảng 2017-01 → 2018-08 như data_profiling.md).
- Batch 2018-08 bị cắt cuối tháng (D4) – số đơn tuần cuối và thời gian giao của tháng này không đại diện.
- Full Load lớn hơn mỗi batch incremental ~7 lần; nếu demo cần nhanh có thể chia nhỏ Full Load, ranh giới 2017-12 vẫn giữ nguyên.

## D7. Khách hàng: `customer_id` vs `customer_unique_id`

**Quyết định**
- `customer_id` = mã khách **theo từng đơn** → chỉ dùng ở staging để nối `orders` ↔ `customers`.
- `customer_unique_id` = **khách hàng thật** → khóa nghiệp vụ (business key) của `dim_customer`.
- `dim_customer` có khóa thay thế `customer_key` (INT, sinh ở dbt), unique trên `customer_unique_id`.
- Thuộc tính địa chỉ (zip, thành phố, bang): **SCD type 1** – lấy theo đơn **gần nhất** của khách. Vị trí *tại thời điểm mua* (dùng cho phân tích theo vùng) lấy từ dòng `customers` của chính đơn đó và gắn vào fact qua chiều địa lý, không phụ thuộc SCD.
- Khi incremental, `dim_customer` được **MERGE theo `customer_unique_id`** (khách cũ quay lại → cập nhật, khách mới → thêm).
- KPI *tỉ lệ khách mua lại* tính theo **lần mua** (gộp các đơn cùng khách cách nhau ≤ 10 phút), không theo số đơn.

**Lý do**
- Mỗi `customer_id` chỉ có đúng 1 đơn → dựng chiều khách trên `customer_id` thì tỉ lệ mua lại luôn = 0%.
- Rất ít khách đổi địa chỉ nên SCD type 2 không đáng độ phức tạp; vị trí theo đơn đã được giữ ở fact.
- Giỏ hàng nhiều người bán bị tách thành nhiều đơn cách nhau vài giây (xem giải thích `review_id` trong data_dictionary.md) → đếm theo đơn làm tỉ lệ mua lại bị thổi phồng.

**Số liệu chứng minh**

| Chỉ số | Giá trị |
|---|---|
| `customer_id` / `customer_unique_id` | 99.441 / **96.096** |
| Phân bố số đơn mỗi khách | 1 đơn: 93.099 · 2: 2.745 · 3: 203 · 4: 30 · 5: 8 · 6: 6 · 7: 3 · 9: 1 · 17: 1 |
| Khách mua lại – đếm theo **đơn** (≥ 2 đơn) | 2.997 = 3,12% khách (chiếm 6.342 đơn = 6,38% đơn) |
| Khách mua lại – chỉ đơn delivered | 2.801 / 93.358 = 3,00% |
| Khách mua lại – theo **lần mua** (đơn cách nhau > 10 phút) | **2.245 = 2,34%** ← dùng cho KPI |
| Khách mua lại – theo ngày mua khác nhau | 2.149 = 2,24% |
| Khách có > 1 đơn tại cùng 1 thời điểm (giỏ hàng tách đơn) | 290 |
| Khách có > 1 zip / > 1 thành phố / > 1 bang | 250 / 122 / 39 |
| Khách xuất hiện ở > 1 batch | 1.251 |
| Khách quay lại (đã có ở batch trước) trong từng batch incremental | 2018-01: 141 · 02: 118 · 03: 150 · 04: 171 · 05: 192 · 06: 188 · 07: 159 · 08: 189 · 09+: 11 |

**Rủi ro**
- Tỉ lệ mua lại rất thấp (~2–3%) → phân tích cohort / vòng đời khách ít giá trị; nên nêu như một *insight* (Olist phụ thuộc khách mới) thay vì xây dashboard riêng.
- Ngưỡng 10 phút để gộp lần mua là quy ước của nhóm, cần ghi trong định nghĩa KPI. Theo ngày cho kết quả gần như nhau (2,24% vs 2,34%) nên quy ước này không nhạy.
- SCD type 1 làm mất địa chỉ cũ của 250 khách (0,26%) ở `dim_customer`; chấp nhận được vì vị trí theo đơn vẫn lưu ở fact.

## D8. Mô phỏng cập nhật trạng thái (phương án B)

**Quyết định**

1. **Mốc cắt (cutoff)** của batch T = 00:00 ngày đầu tháng sau T (batch `FULL`: 2018-01-01 00:00). Batch T chỉ chứa những gì **đã xảy ra trước cutoff**. Batch cuối `2018-09+` **không cắt** – gửi trạng thái gốc.
2. **Ảnh chụp một đơn tại cutoff c**:
   - Giữ nguyên `order_purchase_timestamp`, `order_estimated_delivery_date` (biết ngay lúc mua).
   - `order_approved_at`, `order_delivered_carrier_date`, `order_delivered_customer_date`: giữ nếu `< c`, ngược lại để **NULL**.
   - `order_status` = mốc **muộn nhất có timestamp trước c**, không vượt quá trạng thái gốc:

     | Trạng thái gốc | Điều kiện tại cutoff c | `order_status` gửi đi |
     |---|---|---|
     | `canceled`, `unavailable` | – (nguồn không có ngày hủy) | Giữ trạng thái gốc ngay từ batch đầu |
     | bất kỳ trạng thái còn lại | `delivered_customer_date < c` và gốc = `delivered` | `delivered` |
     | | `delivered_carrier_date < c` | `shipped` |
     | | `approved_at < c` | `approved`; riêng đơn gốc kẹt ở `invoiced` / `processing` → giữ trạng thái gốc |
     | | không mốc nào trước c | `created` |

3. **Đơn được gửi ở batch T** nếu: (a) là đơn **mới** (watermark D4), hoặc (b) là đơn cũ có **ảnh chụp tại cutoff T khác ảnh chụp tại cutoff T-1** (có mốc mới rơi vào tháng T). Batch `2018-09+` gửi mọi đơn có trạng thái gốc khác ảnh chụp cuối 2018-08.
4. **Review** được gửi ở batch chứa `review_answer_timestamp`; nếu batch đó sớm hơn batch đầu tiên của đơn thì dời về batch đầu tiên của đơn (= batch muộn hơn trong hai batch). Review chỉ INSERT, không cập nhật.
5. `order_items`, `order_payments`, `customers`: không mô phỏng, gửi 1 lần ở batch đầu tiên của đơn (D5).
6. Mỗi dòng trong file batch có cột `batch_id`; staging lưu thêm `_batch_id`, `_loaded_at` của lần nạp gần nhất. `etl_log` ghi **số dòng INSERT và số dòng UPDATE** riêng cho từng bảng (lấy từ `RETURNING merge_action()` của MERGE – có từ PostgreSQL 17).

**Ví dụ** – đơn `82a35d13f3b95427d47aa11e4afde83b` (mua 27/01/2018, giao vận chuyển 30/01, khách nhận 20/02, trả lời review 3★ ngày 23/02):

| Batch | Đơn có trong batch? | `order_status` | `delivered_carrier_date` | `delivered_customer_date` | Review | Tác động MERGE |
|---|---|---|---|---|---|---|
| 2018-01 (cutoff 01/02) | Có – đơn mới | `shipped` | 2018-01-30 | NULL | – | INSERT |
| 2018-02 (cutoff 01/03) | Có – có mốc mới | `delivered` | 2018-01-30 | 2018-02-20 | 3★ | UPDATE đơn, INSERT review |
| 2018-03 trở đi | Không | | | | | |

**Lý do**
- Đúng với cách ETL chạy ngoài thực tế: đơn mới chưa hoàn tất, được cập nhật ở các lần chạy sau → nhánh UPDATE của MERGE thật sự được dùng.
- Đề yêu cầu "cho phép chạy lại pipeline và kiểm tra kết quả": sau mỗi batch thấy rõ đơn nào đổi trạng thái.
- Seminar 3 (dashboard theo dõi từng lần chạy ETL) có số liệu *thêm / cập nhật* thật thay vì cột cập nhật luôn bằng 0.
- Toàn bộ logic nằm trong **script chia batch**; pipeline Mage và dbt không đổi so với phương án A.

**Số liệu chứng minh**
- Tỉ lệ đơn có mốc rơi **sau** cutoff của batch đầu tiên (bảng ở D4): giao vận chuyển 6,7–11,6%, khách nhận 27,1–51,7%, trả lời review 38,2–64,3% (các batch 2018-01…07) → mỗi batch incremental sẽ có một lượng lớn UPDATE đơn cũ và INSERT review của đơn tháng trước. Số dòng chính xác từng batch sẽ có khi viết script chia batch.
- Các mốc dùng để suy trạng thái đều có sẵn: NULL ở `order_approved_at` 160, `order_delivered_carrier_date` 1.783, `order_delivered_customer_date` 2.965 (chủ yếu đơn chưa giao / hủy – data_profiling.md mục 12).

**Rủi ro**
- **Trạng thái trung gian là suy diễn**: nguồn không có ngày chuyển sang `invoiced` / `processing` nên đơn đi `approved` → `shipped` sẽ bỏ qua 2 trạng thái này; đơn `canceled` (625) / `unavailable` (609) hiện trạng thái hủy ngay từ batch đầu vì không có ngày hủy. Báo cáo và video phải nói rõ đây là **dữ liệu mô phỏng**.
- **Mốc ngày sai thứ tự** sinh chuỗi trạng thái lạ: 1.359 đơn giao vận chuyển trước khi duyệt → có thể có ảnh chụp `shipped` với `approved_at` NULL; 8 đơn `delivered` thiếu ngày nhận sẽ ở `shipped` tới batch đối soát. Các đơn này đã được gắn cờ ngày không hợp lệ (data_profiling.md vấn đề #7).
- **Kiểm tra bắt buộc sau batch cuối**: staging phải khớp file gốc (số dòng từng bảng và giá trị từng cột của `orders`) – đặt trong `sql/checks/`. Nếu lệch là script chia batch hoặc MERGE có lỗi.
- **dbt phải xử lý cập nhật**: fact dựng từ staging đã được cập nhật tại chỗ. Cách an toàn nhất là materialize `table` (dựng lại mỗi lần chạy); nếu dùng `incremental` phải có `unique_key` và chiến lược cập nhật phù hợp (`dbt-postgres` hỗ trợ `merge` và `delete+insert`).
- Ảnh chụp giữa kỳ làm KPI tháng gần nhất "chưa đầy đủ" (VD tỉ lệ giao trễ chỉ tính trên đơn đã giao). Ngoài thực tế cũng vậy, nhưng phải giải thích khi demo.

---

## Quyết định đã chốt sau thảo luận

| Ngày | Câu hỏi | Kết luận |
|---|---|---|
| 10/10/2026 | Có mô phỏng cập nhật trạng thái không? | **Có – phương án B** (D8) |
| 10/10/2026 | Nạp `products` / `sellers` theo lần xuất hiện đầu tiên? | **Không** – giữ nạp 1 lần ở Full Load (D3) |
| 14/10/2026 | Giữ SQL Server hay đổi sang PostgreSQL? | **Đổi sang PostgreSQL 17** – dùng lại được Mage + Postgres của demo lớp, `dbt-postgres` là adapter chính thức của dbt Labs, nhẹ hơn khi chạy Docker. Các quyết định D1–D8 giữ nguyên (MERGE có trong Postgres từ bản 15, `RETURNING merge_action()` và `WHEN NOT MATCHED BY SOURCE` từ bản 17) |
