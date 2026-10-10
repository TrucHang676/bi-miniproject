# Khảo sát dữ liệu (Data Profiling) – Olist

> File sinh tự động bởi `scripts/profile_olist.py` lúc 10/10/2026 14:09. **Không sửa tay** – sửa script rồi chạy lại.
> Toàn bộ file được đọc dạng chuỗi; ô rỗng = NULL. Số liệu ở đây là dữ liệu gốc, chưa làm sạch.

## 1. Tổng quan

| Bảng | File | Số dòng | Số cột | Dung lượng (MB) | Dòng trùng hoàn toàn | Khóa chính dự kiến | Dòng trùng khóa |
|---|---|---|---|---|---|---|---|
| `orders` | olist_orders_dataset.csv | 99.441 | 8 | 16,8 | 0 | order_id | 0 dòng / 0 mã |
| `order_items` | olist_order_items_dataset.csv | 112.650 | 7 | 14,7 | 0 | order_id, order_item_id | 0 dòng / 0 mã |
| `order_payments` | olist_order_payments_dataset.csv | 103.886 | 5 | 5,5 | 0 | order_id, payment_sequential | 0 dòng / 0 mã |
| `order_reviews` | olist_order_reviews_dataset.csv | 99.224 | 7 | 13,8 | 0 | review_id | 1.603 dòng / 789 mã |
| `customers` | olist_customers_dataset.csv | 99.441 | 5 | 8,6 | 0 | customer_id | 0 dòng / 0 mã |
| `sellers` | olist_sellers_dataset.csv | 3.095 | 4 | 0,2 | 0 | seller_id | 0 dòng / 0 mã |
| `products` | olist_products_dataset.csv | 32.951 | 9 | 2,3 | 0 | product_id | 0 dòng / 0 mã |
| `category_translation` | product_category_name_translation.csv | 71 | 2 | 0,0 | 0 | product_category_name | 0 dòng / 0 mã |
| `geolocation` | olist_geolocation_dataset.csv | 1.000.163 | 5 | 58,4 | 261.831 | (không có) | – |

## 2. Bảng `orders`

File `olist_orders_dataset.csv` – 99.441 dòng × 8 cột.

**Thống kê theo cột**

| Cột | Kiểu nghiệp vụ | Kiểu pandas mặc định | % NULL | Số giá trị khác nhau | Ví dụ | Vấn đề phát hiện |
|---|---|---|---|---|---|---|
| `order_id` | id | object | 0,00% | 99.441 | `e481f51cbdc54678b7cc49136f2d6af7` | – |
| `customer_id` | id | object | 0,00% | 99.441 | `9ef432eb6251297304e76186b10a928d` | – |
| `order_status` | enum | object | 0,00% | 8 | `delivered` | – |
| `order_purchase_timestamp` | datetime | object | 0,00% | 98.875 | `2017-10-02 10:56:33` | – |
| `order_approved_at` | datetime | object | 0,16% | 90.733 | `2017-10-02 11:07:15` | – |
| `order_delivered_carrier_date` | datetime | object | 1,79% | 81.018 | `2017-10-04 19:55:00` | – |
| `order_delivered_customer_date` | datetime | object | 2,98% | 95.664 | `2017-10-10 21:25:13` | – |
| `order_estimated_delivery_date` | datetime | object | 0,00% | 459 | `2017-10-18 00:00:00` | – |

**Cột ngày giờ**

| Cột | Min | Max | Sai định dạng | % giá trị có giờ = 00:00:00 |
|---|---|---|---|---|
| `order_purchase_timestamp` | 2016-09-04 21:15:19 | 2018-10-17 17:30:18 | 0 | 0,0% |
| `order_approved_at` | 2016-09-15 12:16:38 | 2018-09-03 17:40:06 | 0 | 0,0% |
| `order_delivered_carrier_date` | 2016-10-08 10:34:01 | 2018-09-11 19:48:28 | 0 | 0,0% |
| `order_delivered_customer_date` | 2016-10-11 13:46:32 | 2018-10-17 13:22:46 | 0 | 0,0% |
| `order_estimated_delivery_date` | 2016-09-30 00:00:00 | 2018-11-12 00:00:00 | 0 | 100,0% |

**Kiểm tra nghiệp vụ**

- Phân bố `order_status`: delivered 96.478 (97,02%), shipped 1.107 (1,11%), canceled 625 (0,63%), unavailable 609 (0,61%), invoiced 314 (0,32%), processing 301 (0,30%), created 5 (0,01%), approved 2 (0,00%)
- Mỗi `customer_id` xuất hiện tối đa 1 đơn → customer_id là mã khách *theo từng đơn*, không phải mã khách thật.

## 3. Bảng `order_items`

File `olist_order_items_dataset.csv` – 112.650 dòng × 7 cột.

**Thống kê theo cột**

| Cột | Kiểu nghiệp vụ | Kiểu pandas mặc định | % NULL | Số giá trị khác nhau | Ví dụ | Vấn đề phát hiện |
|---|---|---|---|---|---|---|
| `order_id` | id | object | 0,00% | 98.666 | `00010242fe8c5a6d1ba2dd792cb16214` | – |
| `order_item_id` | int | int64 | 0,00% | 21 | `1` | – |
| `product_id` | id | object | 0,00% | 32.951 | `4244733e06e7ecb4970a6e2683c13e61` | – |
| `seller_id` | id | object | 0,00% | 3.095 | `48436dade18ac8b2bce089ec2a041202` | – |
| `shipping_limit_date` | datetime | object | 0,00% | 93.318 | `2017-09-19 09:45:35` | – |
| `price` | float | float64 | 0,00% | 5.968 | `58.90` | – |
| `freight_value` | float | float64 | 0,00% | 6.999 | `13.29` | – |

**Cột ngày giờ**

| Cột | Min | Max | Sai định dạng | % giá trị có giờ = 00:00:00 |
|---|---|---|---|---|
| `shipping_limit_date` | 2016-09-19 00:15:34 | 2020-04-09 22:35:08 | 0 | 0,0% |

**Cột số**

| Cột | Min | Trung vị | p99 | Max | Số âm | Bằng 0 |
|---|---|---|---|---|---|---|
| `order_item_id` | 1,00 | 1,00 | 4,00 | 21,00 | 0 | 0 |
| `price` | 0,85 | 74,99 | 890,00 | 6.735,00 | 0 | 0 |
| `freight_value` | 0,00 | 16,26 | 84,52 | 409,68 | 0 | 383 |

**Kiểm tra nghiệp vụ**

- Số item mỗi đơn: 1 item: 88.863 đơn, 2 item: 7.516 đơn, 3 item: 1.322 đơn, 4 item: 505 đơn, 5 item: 204 đơn, 6 item: 198 đơn; tối đa 21 item/đơn.
- `order_item_id` đánh số liên tục 1..n trong mỗi đơn: 0 đơn bị đứt quãng.
- Đơn có nhiều người bán: 1.278.
- `freight_value = 0` (miễn phí ship): 383 dòng; phí ship > giá sản phẩm: 4.124 dòng (3,66%).
- Giá > p99 (890,00 BRL): 1.117 dòng – giá trị lớn nhưng hợp lý (đồ điện tử, nội thất), không phải lỗi.
- `shipping_limit_date` < ngày mua: 0 dòng.

## 4. Bảng `order_payments`

File `olist_order_payments_dataset.csv` – 103.886 dòng × 5 cột.

**Thống kê theo cột**

| Cột | Kiểu nghiệp vụ | Kiểu pandas mặc định | % NULL | Số giá trị khác nhau | Ví dụ | Vấn đề phát hiện |
|---|---|---|---|---|---|---|
| `order_id` | id | object | 0,00% | 99.440 | `b81ef226f3fe1789b1e8b2acac839d17` | – |
| `payment_sequential` | int | int64 | 0,00% | 29 | `1` | – |
| `payment_type` | enum | object | 0,00% | 5 | `credit_card` | – |
| `payment_installments` | int | int64 | 0,00% | 24 | `8` | – |
| `payment_value` | float | float64 | 0,00% | 29.077 | `99.33` | – |

**Cột số**

| Cột | Min | Trung vị | p99 | Max | Số âm | Bằng 0 |
|---|---|---|---|---|---|---|
| `payment_sequential` | 1,00 | 1,00 | 3,00 | 29,00 | 0 | 0 |
| `payment_installments` | 0,00 | 1,00 | 10,00 | 24,00 | 0 | 2 |
| `payment_value` | 0,00 | 100,00 | 1.039,92 | 13.664,08 | 0 | 9 |

**Kiểm tra nghiệp vụ**

- Phân bố `payment_type`: credit_card 76.795 (73,92%), boleto 19.784 (19,04%), voucher 5.775 (5,56%), debit_card 1.529 (1,47%), not_defined 3 (0,00%)
- `payment_value = 0`: 9 dòng (loại: voucher 6, not_defined 3); `payment_installments = 0`: 2; trả góp >1 kỳ nhưng không phải thẻ tín dụng: 0.
- Đơn có >1 dòng thanh toán: 2.961; `payment_sequential` bị đứt quãng: 80 đơn.
- Tổng thanh toán lệch tổng (price + freight) quá 1 BRL: 249 / 98.665 đơn (tổng price 13.591.644 + freight 2.251.910 = 15.843.553 vs tổng payment 16.008.872 BRL).

## 5. Bảng `order_reviews`

File `olist_order_reviews_dataset.csv` – 99.224 dòng × 7 cột.

**Thống kê theo cột**

| Cột | Kiểu nghiệp vụ | Kiểu pandas mặc định | % NULL | Số giá trị khác nhau | Ví dụ | Vấn đề phát hiện |
|---|---|---|---|---|---|---|
| `review_id` | id | object | 0,00% | 98.410 | `7bc2406110b926393aa56f80a40eba40` | – |
| `order_id` | id | object | 0,00% | 98.673 | `73fc7af87114b39712e6da79b0a377eb` | – |
| `review_score` | int | int64 | 0,00% | 5 | `4` | – |
| `review_comment_title` | text | object | 88,34% | 4.527 | `recomendo` | 1.998 dòng có khoảng trắng đầu/cuối (vd `Ótimo `, `Excelente `, `Muito bom `)<br>2 dòng là chuỗi giả-NULL (NA, null, -...) (vd `?`, `-`)<br>độ dài TB 12, tối đa 26 ký tự |
| `review_comment_message` | text | object | 58,70% | 36.159 | `Recebi bem antes do prazo estipulad…` | 9.451 dòng có khoảng trắng đầu/cuối (vd `Ótimo `, `Muito bom `, `Recomendo `)<br>7 dòng là chuỗi giả-NULL (NA, null, -...) (vd `?`, `-`, `N/a`)<br>3.852 dòng chứa ký tự xuống dòng bên trong ô (vd `  `, `muito bom  `, `Bom  `)<br>độ dài TB 69, tối đa 208 ký tự |
| `review_creation_date` | datetime | object | 0,00% | 636 | `2018-01-18 00:00:00` | – |
| `review_answer_timestamp` | datetime | object | 0,00% | 98.248 | `2018-01-18 21:46:59` | – |

**Cột ngày giờ**

| Cột | Min | Max | Sai định dạng | % giá trị có giờ = 00:00:00 |
|---|---|---|---|---|
| `review_creation_date` | 2016-10-02 00:00:00 | 2018-08-31 00:00:00 | 0 | 99,9% |
| `review_answer_timestamp` | 2016-10-07 18:32:28 | 2018-10-29 12:27:35 | 0 | 0,0% |

**Cột số**

| Cột | Min | Trung vị | p99 | Max | Số âm | Bằng 0 |
|---|---|---|---|---|---|---|
| `review_score` | 1,00 | 5,00 | 5,00 | 5,00 | 0 | 0 |

**Kiểm tra nghiệp vụ**

- Phân bố `review_score`: 1★ 11.424 (11,5%), 2★ 3.151 (3,2%), 3★ 8.179 (8,2%), 4★ 19.142 (19,3%), 5★ 57.328 (57,8%)
- `review_id` trùng: 789 mã (1.603 dòng); 1 review_id gắn với nhiều đơn khác nhau: 789 mã; cặp (review_id, order_id) trùng: 0 → khóa thật là (review_id, order_id).
- Phân tích 789 review_id gắn nhiều đơn: cùng 1 khách & cùng điểm, bình luận, ngày tạo, ngày trả lời: 789/789; các đơn đặt cách nhau ≤ 1 phút: 730; các đơn do người bán khác nhau giao: 503; cách nhau > 1 ngày: 41 (xa nhất 127 ngày). → Suy luận: giỏ hàng nhiều người bán bị tách thành nhiều đơn nhưng khách chỉ nhận **1 khảo sát cho cả lần mua**, câu trả lời được chép sang mọi đơn. Không phải lỗi nhập liệu (mô tả Kaggle không nói rõ điều này).
- Đơn có >1 review: 547.
- Review tạo trước ngày mua: 64; trả lời trước khi tạo review: 0.
- Có tiêu đề: 11,7%; có nội dung bình luận: 41,3% (tiếng Bồ Đào Nha).

## 6. Bảng `customers`

File `olist_customers_dataset.csv` – 99.441 dòng × 5 cột.

**Thống kê theo cột**

| Cột | Kiểu nghiệp vụ | Kiểu pandas mặc định | % NULL | Số giá trị khác nhau | Ví dụ | Vấn đề phát hiện |
|---|---|---|---|---|---|---|
| `customer_id` | id | object | 0,00% | 99.441 | `06b8999e2fba1a1fbc88172c00ba8bc7` | – |
| `customer_unique_id` | id | object | 0,00% | 96.096 | `861eff4711a542e4b93843c6dd7febb0` | – |
| `customer_zip_code_prefix` | zip | int64 | 0,00% | 14.994 | `14409` | pandas tự đọc thành int64 → mất số 0 đầu ở 23.995 dòng<br>23.995 dòng bắt đầu bằng số 0 (mất số 0 nếu ép kiểu số) (vd `07600`, `09371`, `06900`) |
| `customer_city` | city | object | 0,00% | 4.119 | `franca` | 1 dòng chứa ký tự lạ (số, dấu câu...) (vd `quilometro 14 do mutum`)<br>6 tên có nhiều cách viết (dấu/không dấu, gạch nối...); 11 dòng không theo cách viết phổ biến nhất (vd `santa barbara d'oeste` / `santa barbara d oeste`; `mogi mirim` / `mogi-mirim`) |
| `customer_state` | state | object | 0,00% | 27 | `SP` | – |

**Kiểm tra nghiệp vụ**

- `customer_unique_id` khác nhau: 96.096 (so với 99.441 customer_id); khách mua ≥2 lần: 2.997 (3,12%).
- Khách (unique_id) có nhiều zip khác nhau giữa các đơn (chuyển địa chỉ): 250 → cần quyết định SCD.
- Top 5 bang: SP 42,0%, RJ 12,9%, MG 11,7%, RS 5,5%, PR 5,1%

## 7. Bảng `sellers`

File `olist_sellers_dataset.csv` – 3.095 dòng × 4 cột.

**Thống kê theo cột**

| Cột | Kiểu nghiệp vụ | Kiểu pandas mặc định | % NULL | Số giá trị khác nhau | Ví dụ | Vấn đề phát hiện |
|---|---|---|---|---|---|---|
| `seller_id` | id | object | 0,00% | 3.095 | `3442f8959a84dea7ee197c632cb2df15` | – |
| `seller_zip_code_prefix` | zip | int64 | 0,00% | 2.246 | `13023` | pandas tự đọc thành int64 → mất số 0 đầu ở 1.027 dòng<br>1.027 dòng bắt đầu bằng số 0 (mất số 0 nếu ép kiểu số) (vd `01026`, `08710`, `09560`) |
| `seller_city` | city | object | 0,00% | 611 | `campinas` | 3 dòng có 2 khoảng trắng liền nhau (vd `sao  jose dos pinhais`, `sao  paulo`, `ferraz de  vasconcelos`)<br>1 dòng chứa dấu tổ hợp tách rời (Unicode chưa chuẩn hóa NFC) (vd `são paulo`)<br>3 dòng viết có dấu (đa số viết không dấu) (vd `santa barbara d´oeste`, `são paulo`)<br>21 dòng chứa ký tự lạ (số, dấu câu...) (vd `sao sebastiao da grama/sp`, `santo andre/sao paulo`, `arraial d'ajuda (porto seguro)`)<br>6 tên có nhiều cách viết (dấu/không dấu, gạch nối...); 9 dòng không theo cách viết phổ biến nhất (vd `sao paulo` / `são paulo` / `sao  paulo`; `sao jose dos pinhais` / `sao  jose dos pinhais`) |
| `seller_state` | state | object | 0,00% | 23 | `SP` | – |

**Kiểm tra nghiệp vụ**

- Top 5 bang: SP 59,7%, PR 11,3%, MG 7,9%, SC 6,1%, RJ 5,5%

## 8. Bảng `products`

File `olist_products_dataset.csv` – 32.951 dòng × 9 cột.

**Thống kê theo cột**

| Cột | Kiểu nghiệp vụ | Kiểu pandas mặc định | % NULL | Số giá trị khác nhau | Ví dụ | Vấn đề phát hiện |
|---|---|---|---|---|---|---|
| `product_id` | id | object | 0,00% | 32.951 | `1e9e8ef04dbcff4541ed26657ea517e5` | – |
| `product_category_name` | category | object | 1,85% | 73 | `perfumaria` | – |
| `product_name_lenght` | int | float64 | 1,85% | 66 | `40` | – |
| `product_description_lenght` | int | float64 | 1,85% | 2.960 | `287` | – |
| `product_photos_qty` | int | float64 | 1,85% | 19 | `1` | – |
| `product_weight_g` | int | float64 | 0,01% | 2.204 | `225` | – |
| `product_length_cm` | int | float64 | 0,01% | 99 | `16` | – |
| `product_height_cm` | int | float64 | 0,01% | 102 | `10` | – |
| `product_width_cm` | int | float64 | 0,01% | 95 | `14` | – |

**Cột số**

| Cột | Min | Trung vị | p99 | Max | Số âm | Bằng 0 |
|---|---|---|---|---|---|---|
| `product_name_lenght` | 5,00 | 51,00 | 63,00 | 76,00 | 0 | 0 |
| `product_description_lenght` | 4,00 | 595,00 | 3.286,20 | 3.992,00 | 0 | 0 |
| `product_photos_qty` | 1,00 | 1,00 | 8,00 | 20,00 | 0 | 0 |
| `product_weight_g` | 0,00 | 700,00 | 22.538,00 | 40.425,00 | 0 | 4 |
| `product_length_cm` | 7,00 | 25,00 | 100,00 | 105,00 | 0 | 0 |
| `product_height_cm` | 2,00 | 13,00 | 69,00 | 105,00 | 0 | 0 |
| `product_width_cm` | 6,00 | 20,00 | 63,00 | 118,00 | 0 | 0 |

**Kiểm tra nghiệp vụ**

- Sản phẩm thiếu danh mục: 610; trong đó 610 dòng cũng thiếu luôn name/description/photos (thiếu cùng lúc).
- Sản phẩm có khối lượng/kích thước = 0: 4; thiếu khối lượng/kích thước: 2.
- Tên cột gốc sai chính tả: `product_name_lenght`, `product_description_lenght` (đúng: *length*).
- Số danh mục: 73; danh mục không có bản dịch tiếng Anh: `pc_gamer`, `portateis_cozinha_e_preparadores_de_alimentos` (13 sản phẩm).

## 9. Bảng `category_translation`

File `product_category_name_translation.csv` – 71 dòng × 2 cột – **có BOM UTF-8**.

**Thống kê theo cột**

| Cột | Kiểu nghiệp vụ | Kiểu pandas mặc định | % NULL | Số giá trị khác nhau | Ví dụ | Vấn đề phát hiện |
|---|---|---|---|---|---|---|
| `product_category_name` | category | object | 0,00% | 71 | `beleza_saude` | – |
| `product_category_name_english` | category | object | 0,00% | 71 | `health_beauty` | – |

## 10. Bảng `geolocation`

File `olist_geolocation_dataset.csv` – 1.000.163 dòng × 5 cột.

**Thống kê theo cột**

| Cột | Kiểu nghiệp vụ | Kiểu pandas mặc định | % NULL | Số giá trị khác nhau | Ví dụ | Vấn đề phát hiện |
|---|---|---|---|---|---|---|
| `geolocation_zip_code_prefix` | zip | int64 | 0,00% | 19.015 | `01037` | pandas tự đọc thành int64 → mất số 0 đầu ở 245.733 dòng<br>245.733 dòng bắt đầu bằng số 0 (mất số 0 nếu ép kiểu số) (vd `07600`, `06454`, `06900`) |
| `geolocation_lat` | float | float64 | 0,00% | 717.372 | `-23.54562128115268` | – |
| `geolocation_lng` | float | float64 | 0,00% | 717.615 | `-46.63929204800168` | – |
| `geolocation_city` | city | object | 0,00% | 8.011 | `sao paulo` | 1 dòng có khoảng trắng đầu/cuối (vd `salvador `)<br>11 dòng có 2 khoảng trắng liền nhau (vd `itapejara d  oeste`, `diamante d  oeste`, `rancho alegre d  oeste`)<br>1 dòng lỗi encoding (mojibake) (vd `sa£o paulo`)<br>73.442 dòng viết có dấu (đa số viết không dấu) (vd `são paulo`, `brasília`, `são bernardo do campo`)<br>31 dòng chứa ký tự lạ (số, dấu câu...) (vd `colônia z-3`, `itabatan (mucuri)`, `4º centenario`)<br>2.055 tên có nhiều cách viết (dấu/không dấu, gạch nối...); 73.920 dòng không theo cách viết phổ biến nhất (vd `sao paulo` / `são paulo`; `brasilia` / `brasília`) |
| `geolocation_state` | state | object | 0,00% | 27 | `SP` | – |

**Cột số**

| Cột | Min | Trung vị | p99 | Max | Số âm | Bằng 0 |
|---|---|---|---|---|---|---|
| `geolocation_lat` | -36,61 | -22,92 | -2,50 | 45,07 | 998.827 | 0 |
| `geolocation_lng` | -101,47 | -46,64 | -34,94 | 121,11 | 1.000.160 | 0 |

**Kiểm tra nghiệp vụ**

- Không có khóa: 1.000.163 dòng cho 19.015 zip → trung bình 52,6, trung vị 29, tối đa 1.146 dòng/zip. Dòng trùng hoàn toàn: 261.831 (26,18%).
- Tọa độ nằm ngoài lãnh thổ Brazil: 31 dòng (vd zip 18243, 28165, 28155).
- Zip gắn với >1 bang: 8; zip gắn với >1 thành phố (sau khi bỏ dấu): 548.

## 11. Toàn vẹn tham chiếu

**Dòng mồ côi** (giá trị ở bảng con không tìm thấy ở bảng cha):

| Bảng con | Bảng cha | Số dòng kiểm tra | Dòng mồ côi | Giá trị mồ côi khác nhau | % | Ví dụ |
|---|---|---|---|---|---|---|
| `orders.customer_id` | `customers.customer_id` | 99.441 | 0 | 0 | 0,00% | – |
| `order_items.order_id` | `orders.order_id` | 112.650 | 0 | 0 | 0,00% | – |
| `order_items.product_id` | `products.product_id` | 112.650 | 0 | 0 | 0,00% | – |
| `order_items.seller_id` | `sellers.seller_id` | 112.650 | 0 | 0 | 0,00% | – |
| `order_payments.order_id` | `orders.order_id` | 103.886 | 0 | 0 | 0,00% | – |
| `order_reviews.order_id` | `orders.order_id` | 99.224 | 0 | 0 | 0,00% | – |
| `products.product_category_name` | `category_translation.product_category_name` | 32.341 | 13 | 2 | 0,04% | `pc_gamer`, `portateis_cozinha_e_…` |
| `customers.customer_zip_code_prefix` | `geolocation.geolocation_zip_code_prefix` | 99.441 | 278 | 157 | 0,28% | `72300`, `11547` |
| `sellers.seller_zip_code_prefix` | `geolocation.geolocation_zip_code_prefix` | 3.095 | 7 | 7 | 0,23% | `82040`, `91901` |

**Độ phủ** (bản ghi cha không có bản ghi con):

| Kiểm tra | Điều kiện | Số dòng | % | Theo trạng thái đơn |
|---|---|---|---|---|
| Khách hàng không có đơn | `customers` ∉ `orders` | 0 | 0,00% | – |
| Đơn không có sản phẩm | `orders` ∉ `order_items` | 775 | 0,78% | unavailable 603, canceled 164, created 5, invoiced 2 |
| Đơn không có thanh toán | `orders` ∉ `order_payments` | 1 | 0,00% | delivered 1 |
| Đơn không có review | `orders` ∉ `order_reviews` | 768 | 0,77% | delivered 646, shipped 75, canceled 20, unavailable 14 |
| Sản phẩm chưa từng bán | `products` ∉ `order_items` | 0 | 0,00% | – |
| Người bán chưa từng bán | `sellers` ∉ `order_items` | 0 | 0,00% | – |
| Bản dịch danh mục không dùng tới | `category_translation` ∉ `products` | 0 | 0,00% | – |

## 12. Logic ngày trong `orders`

| Kiểm tra | Số đơn | % trên tổng đơn (n = 99.441) | % trên đơn delivered (n = 96.478) | Trạng thái đơn chiếm nhiều nhất |
|---|---|---|---|---|
| Duyệt đơn trước khi mua (`approved_at` < `purchase`) | 0 | 0,00% | – | – |
| Giao cho vận chuyển trước khi mua (`carrier` < `purchase`) | 166 | 0,17% | – | delivered 165, shipped 1 |
| Giao cho vận chuyển trước khi duyệt (`carrier` < `approved_at`) | 1.359 | 1,37% | – | delivered 1350, shipped 9 |
| Khách nhận hàng trước khi mua (`delivered_customer` < `purchase`) | 0 | 0,00% | – | – |
| Khách nhận hàng trước khi giao vận chuyển (`delivered_customer` < `carrier`) | 23 | 0,02% | – | delivered 23 |
| Ngày dự kiến trước ngày mua (`estimated` < `purchase`) | 0 | 0,00% | – | – |
| Trạng thái khác `delivered` nhưng CÓ `delivered_customer_date` | 6 | 0,01% | – | canceled 6 |
| Trạng thái `delivered` nhưng thiếu `delivered_customer_date` | 8 | 0,01% | 0,01% | delivered 8 |
| Trạng thái `delivered` nhưng thiếu `delivered_carrier_date` | 2 | 0,00% | 0,00% | delivered 2 |
| Trạng thái `delivered` nhưng thiếu `approved_at` | 14 | 0,01% | 0,01% | delivered 14 |
| Đơn delivered có thời gian giao > 60 ngày | 306 | 0,31% | 0,32% | delivered 306 |
| **Giao trễ**: ngày nhận > ngày dự kiến (so theo ngày) | 6.534 | 6,57% | 6,77% | delivered 6534 |

Hai cột % khác mẫu số: VD giao trễ = 6.534 đơn là 6,57% *tổng đơn* nhưng 6,77% *đơn delivered*. **KPI tỉ lệ giao trễ dùng mẫu số là đơn delivered.** Cột thứ hai chỉ điền cho kiểm tra giới hạn trong đơn delivered.

- Thời gian giao (đơn delivered có ngày nhận): TB 12,6 ngày, trung vị 10,2, p95 29,3, max 209,6 ngày.
- Tỉ lệ giao trễ (so theo ngày, trên 96.478 đơn delivered): **6,77%**. Nếu so cả giờ (cách nhiều notebook Kaggle dùng) sẽ ra 8,11% – sai, vì `order_estimated_delivery_date` luôn là 00:00:00 nên đơn giao đúng ngày dự kiến bị tính là trễ.

**Ma trận NULL theo trạng thái đơn** (số đơn thiếu từng mốc thời gian):

| order_status | Số đơn | Thiếu approved_at | Thiếu delivered_carrier | Thiếu delivered_customer |
|---|---|---|---|---|
| delivered | 96.478 | 14 | 2 | 8 |
| shipped | 1.107 | 0 | 0 | 1.107 |
| canceled | 625 | 141 | 550 | 619 |
| unavailable | 609 | 0 | 609 | 609 |
| invoiced | 314 | 0 | 314 | 314 |
| processing | 301 | 0 | 301 | 301 |
| created | 5 | 5 | 5 | 5 |
| approved | 2 | 0 | 2 | 2 |

## 13. Số đơn theo tháng (`order_purchase_timestamp`)

Dùng để quyết định chia batch cho Incremental Load. Tháng đánh dấu ⚠️ có số đơn < 5% tháng cao nhất.

| Tháng | Tổng đơn | Delivered | Canceled + unavailable | % lũy kế | Ghi chú |
|---|---|---|---|---|---|
| 2016-09 | 4 | 1 | 2 | 0,0% | ⚠️ thưa |
| 2016-10 | 324 | 265 | 31 | 0,3% | ⚠️ thưa |
| 2016-11 | 0 | 0 | 0 | 0,3% | ⚠️ trống |
| 2016-12 | 1 | 1 | 0 | 0,3% | ⚠️ thưa |
| 2017-01 | 800 | 750 | 13 | 1,1% |  |
| 2017-02 | 1.780 | 1.653 | 62 | 2,9% |  |
| 2017-03 | 2.682 | 2.546 | 65 | 5,6% |  |
| 2017-04 | 2.404 | 2.303 | 27 | 8,0% |  |
| 2017-05 | 3.700 | 3.546 | 60 | 11,8% |  |
| 2017-06 | 3.245 | 3.135 | 40 | 15,0% |  |
| 2017-07 | 4.026 | 3.872 | 80 | 19,1% |  |
| 2017-08 | 4.331 | 4.193 | 59 | 23,4% |  |
| 2017-09 | 4.285 | 4.150 | 58 | 27,7% |  |
| 2017-10 | 4.631 | 4.478 | 84 | 32,4% |  |
| 2017-11 | 7.544 | 7.289 | 121 | 40,0% | cao nhất |
| 2017-12 | 5.673 | 5.513 | 53 | 45,7% |  |
| 2018-01 | 7.269 | 7.069 | 82 | 53,0% |  |
| 2018-02 | 6.728 | 6.555 | 103 | 59,8% |  |
| 2018-03 | 7.211 | 7.003 | 43 | 67,0% |  |
| 2018-04 | 6.939 | 6.798 | 20 | 74,0% |  |
| 2018-05 | 6.873 | 6.749 | 40 | 80,9% |  |
| 2018-06 | 6.167 | 6.099 | 22 | 87,1% |  |
| 2018-07 | 6.292 | 6.159 | 59 | 93,4% |  |
| 2018-08 | 6.512 | 6.351 | 91 | 100,0% |  |
| 2018-09 | 16 | 0 | 15 | 100,0% | ⚠️ thưa |
| 2018-10 | 4 | 0 | 4 | 100,0% | ⚠️ thưa |

- Khoảng 2017-01 → 2018-08: 99.092 đơn (99,6%).

## 14. Vấn đề cần làm sạch (xếp theo mức độ ảnh hưởng)

- **Cao**: làm sai KPI chính, sai khóa hoặc sai kết quả JOIN nếu không xử lý.
- **Trung bình**: ảnh hưởng một nhóm phân tích cụ thể.
- **Thấp**: ít dòng, hoặc chỉ cần lưu ý khi nạp dữ liệu.

| # | Mức độ | Vấn đề | Bằng chứng | Đề xuất xử lý |
|---|---|---|---|---|
| 1 | Cao | Nhân dòng (fan-out) khi JOIN bảng con vào orders | 9.803 đơn có >1 item, 2.961 đơn có >1 dòng thanh toán, 547 đơn có >1 review | Fact chính ở grain *1 item / 1 đơn*; gom payments & reviews về 1 dòng/đơn trước khi join; doanh thu tính từ order_items, không SUM sau khi join items × payments. |
| 2 | Cao | `customer_id` không phải khách hàng thật | 99.441 customer_id nhưng chỉ 96.096 customer_unique_id; mỗi customer_id chỉ có 1 đơn | `dim_customer` dựng theo `customer_unique_id`; nếu không, tỉ lệ khách quay lại luôn = 0%. |
| 3 | Cao | Dữ liệu đầu/cuối kỳ rất thưa, có tháng trống | Tháng < 5% tháng cao nhất: 2016-09 (4), 2016-10 (324), 2016-11 (0), 2016-12 (1), 2018-09 (16), 2018-10 (4) | Phân tích xu hướng trong 2017-01 → 2018-08 (giữ 99,6% số đơn); ghi rõ giới hạn này trên dashboard. |
| 4 | Cao | `review_id` không duy nhất | 789 review_id lặp (1.603 dòng); 789 review_id gắn với nhiều đơn. 789 trường hợp là cùng 1 câu trả lời của cùng 1 khách chép sang nhiều đơn; 730 trường hợp các đơn đặt cách nhau ≤ 1 phút – 1 khảo sát cho cả giỏ hàng bị tách đơn | Khóa `fact_review` = (review_id, order_id); không đặt PK/unique test chỉ trên review_id. KPI *số lượt đánh giá* dùng COUNT(DISTINCT review_id); KPI điểm theo đơn/người bán giữ 1 dòng/đơn. |
| 5 | Cao | Mã zip mất số 0 đầu nếu đọc kiểu số | 270.755 dòng zip bắt đầu bằng 0 (customers + sellers + geolocation); pandas mặc định đọc thành int64 | Ép kiểu CHAR(5) ngay từ staging (Mage dtype=str); join zip bằng chuỗi. |
| 6 | Cao | geolocation trùng lặp & nhiều tọa độ cho 1 zip | 261.831 dòng trùng hoàn toàn; 1.000.163 dòng cho 19.015 zip; 8 zip thuộc >1 bang | Không join trực tiếp; gom 1 dòng/zip (trung bình lat/lng, bang/thành phố phổ biến nhất). |
| 7 | Trung bình | Ngày tháng trong orders mâu thuẫn với trạng thái | `delivered` thiếu ngày nhận: 8; khác delivered nhưng có ngày nhận: 6; giao vận chuyển trước khi mua: 166; giao vận chuyển trước khi duyệt: 1.359; nhận hàng trước khi giao vận chuyển: 23 | Gắn cờ `is_date_valid` ở staging/dbt, loại các dòng này khỏi KPI thời gian giao & tỉ lệ trễ; thêm dbt test. |
| 8 | Trung bình | Đơn thiếu dữ liệu ở bảng con | Không có item: 775; không có thanh toán: 1; không có review: 768 | Dùng LEFT JOIN; KPI điểm review chỉ tính trên đơn có review; đơn không item không vào fact_order_item. |
| 9 | Trung bình | Sản phẩm thiếu danh mục / danh mục thiếu bản dịch | 610 sản phẩm không có danh mục; 2 danh mục không có bản dịch (pc_gamer, portateis_cozinha_e_preparadores_de_alimentos) | Gán `unknown`; bổ sung bản dịch bằng dbt seed. |
| 10 | Trung bình | Tổng thanh toán ≠ tổng tiền hàng + phí ship | 249 / 98.665 đơn lệch > 1 BRL (lãi trả góp, voucher...) | KPI doanh thu lấy từ order_items; payment chỉ dùng phân tích phương thức thanh toán. |
| 11 | Trung bình | Tên thành phố nhiều cách viết | customers: 6 tên / 11 dòng, sellers: 6 tên / 9 dòng, geolocation: 2.055 tên / 73.920 dòng; ký tự lạ (số, dấu câu): 53 dòng; lỗi encoding: 1 dòng; dấu tổ hợp chưa chuẩn hóa NFC: 1 dòng; khoảng trắng đầu/cuối: 1 dòng | Lưu NVARCHAR; chuẩn hóa ở dbt: bỏ dấu (`COLLATE Latin1_General_CI_AI` hoặc TRANSLATE), LOWER, TRIM, gộp khoảng trắng; ưu tiên phân tích theo bang. |
| 12 | Trung bình | Khách thay đổi địa chỉ giữa các đơn | 250 customer_unique_id có >1 zip | Chọn SCD: type 1 (lấy địa chỉ đơn gần nhất) hoặc lưu địa chỉ theo đơn trong fact. |
| 13 | Trung bình | Zip của khách/người bán không có trong geolocation | customers: 278 dòng; sellers: 7 dòng | LEFT JOIN, tọa độ để NULL; bản đồ vẽ theo bang thay vì điểm. |
| 14 | Trung bình | Giá trị thanh toán bất thường | payment_value = 0: 9; payment_type = not_defined: 3; installments = 0: 2 | Map `not_defined` → `unknown`; installments 0 → 1; giữ lại nhưng gắn cờ. |
| 15 | Thấp | Tọa độ ngoài lãnh thổ Brazil | 31 dòng geolocation | Loại khi gom tọa độ theo zip. |
| 16 | Thấp | Kích thước/khối lượng sản phẩm = 0 hoặc thiếu | = 0: 4 sản phẩm; thiếu: 2 sản phẩm | Đổi 0 → NULL; không dùng cho KPI chính. |
| 17 | Thấp | Tên cột sai chính tả | `product_name_lenght`, `product_description_lenght` | Đổi tên ở model stg_products. |
| 18 | Thấp | Bình luận review có xuống dòng bên trong ô | 3.852 dòng; file có 104.720 dòng vật lý cho 99.224 bản ghi | Nạp bằng CSV parser chuẩn (pandas, hoặc `BULK INSERT ... WITH (FORMAT = 'CSV', CODEPAGE = '65001')`), không đọc theo từng dòng; cột đích NVARCHAR(MAX). |
| 19 | Thấp | Cột ngày chỉ chứa phần ngày (giờ = 00:00:00) | `order_estimated_delivery_date` (100,0%); `review_creation_date` (99,9%). Phần còn lại là 01:00:00 ngày 2017-10-15 – ngày Brazil chuyển giờ mùa hè (không tồn tại mốc 00:00) | Ép kiểu DATE thay vì DATETIME2; so sánh với ngày dự kiến theo ngày, không theo giờ. |
| 20 | Thấp | Review có ngày bất thường | Review tạo trước ngày mua: 64 | Gắn cờ, không dùng cho KPI thời gian phản hồi review. |
| 21 | Thấp | Nội dung review có khoảng trắng thừa / giá trị giả-NULL | Khoảng trắng đầu/cuối: 11.449 dòng; giá trị như `?`, `-`, `N/a` thay cho rỗng | TRIM và đổi chuỗi giả-NULL thành NULL ở stg_order_reviews (phục vụ phần AI phân tích bình luận). |
| 22 | Thấp | `payment_sequential` không liên tục trong đơn | 80 đơn | Không dùng payment_sequential để đếm số lần thanh toán; đếm số dòng. |
| 23 | Thấp | File có BOM UTF-8 | product_category_name_translation.csv | Đọc bằng encoding `utf-8-sig`, nếu không tên cột đầu bị dính ký tự lạ. |

## 15. Hạn chế khi mô phỏng incremental

Dataset là **ảnh chụp cuối kỳ** (mốc thời gian muộn nhất trong dữ liệu: 2018-10-29 12:27:35): mỗi đơn chỉ có 1 dòng mang trạng thái *cuối cùng*, không có lịch sử thay đổi. Vì vậy `order_status` và các mốc giao hàng là trạng thái **tại lúc chụp**, không phải tại thời điểm mua. Khi chia batch theo tháng mua (mục 13), mỗi batch đã chứa sẵn thông tin chỉ có được về sau:

| Thông tin | Số dòng xảy ra ở tháng SAU tháng mua | % |
|---|---|---|
| `order_approved_at` | 1.684 | 1,7% |
| `order_delivered_carrier_date` | 9.391 | 9,4% |
| `order_delivered_customer_date` | 36.430 | 36,6% |
| `review_answer_timestamp` (order_reviews) | 47.439 | 47,8% |

- Đơn chưa hoàn tất (`shipped`, `invoiced`, `processing`, `created`, `approved`): 1.729 đơn; trong đó 1.626 đơn mua trước ngày mua cuối cùng (2018-10-17) hơn 90 ngày → không phải "đang xử lý" mà là bị kẹt ở trạng thái đó tại lúc chụp.

**Hệ quả**
- Chia batch theo tháng mua chỉ mô phỏng được **thêm đơn mới (insert-only)**: đơn đã nạp không bao giờ được batch sau cập nhật trạng thái, nên không thể hiện được upsert / thay đổi trạng thái trên dữ liệu gốc.
- KPI tính tại một batch giữa kỳ (VD tỉ lệ giao trễ của tháng mới nhất) đã "biết trước" kết quả giao → đầy đủ hơn thực tế ở thời điểm đó.
- Không phân tích được thời gian đơn nằm ở từng trạng thái (không có lịch sử trạng thái).

**Hướng xử lý (nhóm chọn 1)**
1. *Đơn giản*: chấp nhận incremental = thêm đơn mới theo tháng mua, ghi rõ hạn chế này trong báo cáo.
2. *Mô phỏng cập nhật*: khi tạo batch tháng T, ẩn các mốc xảy ra sau cuối tháng T (để NULL, lùi `order_status` về trạng thái tương ứng, VD `shipped`); batch sau gửi lại các đơn đó với thông tin mới → pipeline phải MERGE theo `order_id`. Trạng thái lùi lại là suy diễn, cần ghi rõ đây là dữ liệu mô phỏng.
