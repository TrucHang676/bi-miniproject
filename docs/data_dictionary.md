# Từ điển dữ liệu (Data Dictionary) – Olist

> Nguồn: [Brazilian E-Commerce Public Dataset by Olist](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) – 9 file CSV trong `data/raw/`.
> Số liệu chất lượng lấy từ [data_profiling.md](data_profiling.md) (sinh bởi `scripts/profile_olist.py`). File này viết tay – cập nhật khi đổi thiết kế.

**Quy ước cột "Kiểu"**: kiểu PostgreSQL đề xuất khi nạp vào staging. Database tạo với encoding UTF-8 nên `VARCHAR` / `TEXT`
giữ đủ dấu tiếng Bồ Đào Nha (tên thành phố, bình luận); bình luận dài dùng `TEXT`, cột mã / giá trị cố định dùng `VARCHAR` / `CHAR`.
Mốc thời gian dùng `TIMESTAMP` (không múi giờ – dữ liệu là giờ địa phương Brazil), tiền dùng `NUMERIC`.
Mọi cột mã (`*_id`) là chuỗi hash MD5 32 ký tự hex đã ẩn danh, không mang ý nghĩa. Tiền tệ: **BRL** (real Brazil).

Quan hệ giữa các bảng:

```
customers 1──n orders 1──n order_items n──1 products n──1 category_translation
                 │  1──n order_payments        │
                 │  1──n order_reviews         n──1 sellers
customers.zip / sellers.zip  ··(n──n, không phải khóa)··  geolocation.zip   (geolocation: không nạp)
```

---

## 1. `orders` – Đơn hàng
`olist_orders_dataset.csv` · 99.441 dòng · **Grain:** 1 dòng = 1 đơn hàng · **PK:** `order_id`

| Cột | Kiểu | Mô tả nghiệp vụ | Ví dụ | Ghi chú chất lượng |
|---|---|---|---|---|
| `order_id` | VARCHAR(32) | Mã đơn hàng | `e481f51cbdc54678b7cc49136f2d6af7` | Duy nhất, không NULL |
| `customer_id` | VARCHAR(32) | Mã khách **gắn với đơn này** (mỗi đơn một mã riêng) | `9ef432eb6251297304e76186b10a928d` | Quan hệ 1–1 với đơn. Muốn biết khách thật phải join `customers` lấy `customer_unique_id` |
| `order_status` | VARCHAR(20) | Trạng thái hiện tại của đơn: `created` → `approved` → `invoiced` → `processing` → `shipped` → `delivered`; hoặc `canceled` / `unavailable` (hết hàng) | `delivered` | 8 giá trị; delivered chiếm 97% |
| `order_purchase_timestamp` | TIMESTAMP | Thời điểm khách đặt mua – **mốc thời gian chính** để phân tích | `2017-10-02 10:56:33` | 2016-09-04 → 2018-10-17; đầu/cuối kỳ rất thưa (nên dùng 2017-01 → 2018-08) |
| `order_approved_at` | TIMESTAMP | Thời điểm thanh toán được duyệt | `2017-10-02 11:07:15` | NULL 0,16% (chủ yếu đơn canceled/created; 14 đơn delivered) |
| `order_delivered_carrier_date` | TIMESTAMP | Thời điểm người bán giao hàng cho đơn vị vận chuyển | `2017-10-04 19:55:00` | NULL 1,79%; 166 đơn sớm hơn ngày mua, 1.359 đơn sớm hơn ngày duyệt |
| `order_delivered_customer_date` | TIMESTAMP | Thời điểm khách nhận hàng | `2017-10-10 21:25:13` | NULL 2,98% (đơn chưa giao); 8 đơn delivered thiếu, 6 đơn canceled lại có |
| `order_estimated_delivery_date` | DATE | Ngày giao dự kiến báo cho khách lúc mua | `2017-10-18` | Giờ luôn 00:00:00 → dùng kiểu DATE, so sánh trễ hạn theo ngày |

## 2. `order_items` – Chi tiết sản phẩm trong đơn
`olist_order_items_dataset.csv` · 112.650 dòng · **Grain:** 1 dòng = 1 đơn vị sản phẩm trong 1 đơn · **PK:** (`order_id`, `order_item_id`)

| Cột | Kiểu | Mô tả nghiệp vụ | Ví dụ | Ghi chú chất lượng |
|---|---|---|---|---|
| `order_id` | VARCHAR(32) | Mã đơn (FK → `orders`) | `00010242fe8c5a6d1ba2dd792cb16214` | 0 mồ côi; 775 đơn không có dòng nào ở bảng này |
| `order_item_id` | INT | Số thứ tự sản phẩm trong đơn (1..n). Mua 3 cái cùng loại = 3 dòng | `1` | 1–21; liên tục trong mọi đơn. Số lượng = đếm dòng, không có cột quantity |
| `product_id` | VARCHAR(32) | Mã sản phẩm (FK → `products`) | `4244733e06e7ecb4970a6e2683c13e61` | 0 mồ côi |
| `seller_id` | VARCHAR(32) | Mã người bán thực hiện dòng này (FK → `sellers`) | `48436dade18ac8b2bce089ec2a041202` | 0 mồ côi; 1.278 đơn có nhiều người bán |
| `shipping_limit_date` | TIMESTAMP | Hạn chót người bán phải giao hàng cho đơn vị vận chuyển | `2017-09-19 09:45:35` | Max tới 2020-04-09 (bất thường nhưng ít) |
| `price` | NUMERIC(10,2) | Giá bán 1 đơn vị sản phẩm (BRL) – **cơ sở tính doanh thu** | `58.90` | 0,85 – 6.735; không âm, không bằng 0 |
| `freight_value` | NUMERIC(10,2) | Phí vận chuyển phân bổ cho dòng này (BRL) | `13.29` | 383 dòng = 0 (miễn phí ship); 3,7% dòng có phí ship > giá |

## 3. `order_payments` – Thanh toán
`olist_order_payments_dataset.csv` · 103.886 dòng · **Grain:** 1 dòng = 1 lần/phương thức thanh toán của đơn · **PK:** (`order_id`, `payment_sequential`)

| Cột | Kiểu | Mô tả nghiệp vụ | Ví dụ | Ghi chú chất lượng |
|---|---|---|---|---|
| `order_id` | VARCHAR(32) | Mã đơn (FK → `orders`) | `b81ef226f3fe1789b1e8b2acac839d17` | 2.961 đơn có >1 dòng (VD thẻ + voucher); 1 đơn không có thanh toán |
| `payment_sequential` | INT | Thứ tự phương thức thanh toán trong đơn | `1` | 80 đơn bị đứt quãng → không dùng để đếm số lần trả |
| `payment_type` | VARCHAR(20) | Phương thức: `credit_card` (thẻ tín dụng), `boleto` (phiếu thanh toán tại ngân hàng/cửa hàng, phổ biến ở Brazil), `voucher`, `debit_card`, `not_defined` | `credit_card` | credit_card 74%, boleto 19%; 3 dòng `not_defined` |
| `payment_installments` | INT | Số kỳ trả góp khách chọn | `8` | 0–24; 2 dòng = 0 (nên coi là 1) |
| `payment_value` | NUMERIC(10,2) | Số tiền thanh toán ở dòng này (BRL) | `99.33` | 9 dòng = 0 (voucher, not_defined). Tổng theo đơn lệch (price + freight) ở 249 đơn → **không dùng tính doanh thu** |

## 4. `order_reviews` – Đánh giá của khách
`olist_order_reviews_dataset.csv` · 99.224 dòng · **Grain:** 1 dòng = 1 đánh giá cho 1 đơn · **PK thật:** (`review_id`, `order_id`)

| Cột | Kiểu | Mô tả nghiệp vụ | Ví dụ | Ghi chú chất lượng |
|---|---|---|---|---|
| `review_id` | VARCHAR(32) | Mã khảo sát hài lòng – 1 khảo sát có thể áp cho nhiều đơn của cùng một lần mua | `7bc2406110b926393aa56f80a40eba40` | **Không duy nhất**: 789 mã gắn với 2–3 đơn khác nhau (xem ghi chú bên dưới) |
| `order_id` | VARCHAR(32) | Mã đơn được đánh giá (FK → `orders`) | `73fc7af87114b39712e6da79b0a377eb` | 547 đơn có >1 review; 768 đơn không có review |
| `review_score` | SMALLINT | Điểm hài lòng 1–5 sao | `4` | Không lỗi; 5★ 57,8%, 1★ 11,5% |
| `review_comment_title` | TEXT | Tiêu đề bình luận (tiếng Bồ Đào Nha) | `recomendo` | NULL 88,3%; có khoảng trắng thừa, giá trị `?` / `-` |
| `review_comment_message` | TEXT | Nội dung bình luận (tiếng Bồ Đào Nha) – đầu vào cho phần AI | `Recebi bem antes do prazo estipulado.` | NULL 58,7%; 3.852 dòng có xuống dòng trong ô; 9.451 dòng có khoảng trắng thừa |
| `review_creation_date` | DATE | Ngày gửi khảo sát cho khách | `2018-01-18` | Thực chất chỉ có ngày (vài giá trị 01:00 do đổi giờ mùa hè 15/10/2017); 64 review trước ngày mua |
| `review_answer_timestamp` | TIMESTAMP | Thời điểm khách trả lời khảo sát | `2018-01-18 21:46:59` | Không có trường hợp trả lời trước ngày tạo |

> **Vì sao 1 `review_id` gắn với nhiều đơn?** Cả 789 trường hợp đều cùng 1 khách (`customer_unique_id`), cùng điểm, cùng bình luận,
> cùng ngày tạo và ngày trả lời. 730 trường hợp có các đơn đặt cách nhau ≤ 1 phút, 503 trường hợp các đơn do người bán khác nhau giao.
> Suy luận: giỏ hàng có sản phẩm của nhiều người bán bị Olist tách thành nhiều đơn, nhưng khách chỉ nhận **1 khảo sát cho cả lần mua**
> nên câu trả lời được chép sang mọi đơn (giống tính tiền ở 2 quầy nhưng chỉ điền 1 phiếu góp ý). Đây là suy luận từ dữ liệu,
> mô tả Kaggle không nói rõ; 41 trường hợp các đơn cách nhau > 1 ngày (xa nhất 127 ngày) chưa giải thích được.
>
> **Hệ quả:** khóa thật là (`review_id`, `order_id`) · đếm *số lượt đánh giá* bằng `COUNT(DISTINCT review_id)` ·
> điểm trung bình theo đơn/người bán giữ 1 dòng/đơn · dbt test `unique` đặt trên cặp (`review_id`, `order_id`), không đặt riêng `review_id`.

## 5. `customers` – Khách hàng
`olist_customers_dataset.csv` · 99.441 dòng · **Grain:** 1 dòng = 1 khách *theo từng đơn* · **PK:** `customer_id`

| Cột | Kiểu | Mô tả nghiệp vụ | Ví dụ | Ghi chú chất lượng |
|---|---|---|---|---|
| `customer_id` | VARCHAR(32) | Mã khách theo đơn (khóa nối với `orders`) | `06b8999e2fba1a1fbc88172c00ba8bc7` | Duy nhất; mỗi mã đúng 1 đơn |
| `customer_unique_id` | VARCHAR(32) | **Mã khách hàng thật** – dùng cho `dim_customer`, phân tích khách quay lại | `861eff4711a542e4b93843c6dd7febb0` | 96.096 giá trị; 2.997 khách mua ≥2 lần; 250 khách có >1 zip |
| `customer_zip_code_prefix` | CHAR(5) | 5 số đầu mã bưu chính nơi nhận hàng | `14409` | **Phải là chuỗi**: 23.995 dòng có số 0 đầu; 278 dòng không có trong geolocation |
| `customer_city` | VARCHAR(100) | Thành phố (viết thường, không dấu) | `franca` | Vài cách viết khác nhau (`mogi mirim` / `mogi-mirim`) |
| `customer_state` | CHAR(2) | Mã bang (27 bang) | `SP` | Hợp lệ 100%; SP chiếm 42% |

## 6. `sellers` – Người bán
`olist_sellers_dataset.csv` · 3.095 dòng · **Grain:** 1 dòng = 1 người bán · **PK:** `seller_id`

| Cột | Kiểu | Mô tả nghiệp vụ | Ví dụ | Ghi chú chất lượng |
|---|---|---|---|---|
| `seller_id` | VARCHAR(32) | Mã người bán (cửa hàng nhỏ bán qua Olist) | `3442f8959a84dea7ee197c632cb2df15` | Duy nhất; người bán nào cũng có ít nhất 1 đơn |
| `seller_zip_code_prefix` | CHAR(5) | 5 số đầu mã bưu chính của người bán | `13023` | Chuỗi; 1.027 dòng có số 0 đầu; 7 zip không có trong geolocation |
| `seller_city` | VARCHAR(100) | Thành phố người bán | `campinas` | Bẩn hơn customers: có dấu (`são paulo`), 2 khoảng trắng, ghép bang (`.../sp`), ngoặc |
| `seller_state` | CHAR(2) | Mã bang | `SP` | 23 bang; SP chiếm 60% |

## 7. `products` – Sản phẩm
`olist_products_dataset.csv` · 32.951 dòng · **Grain:** 1 dòng = 1 sản phẩm · **PK:** `product_id`

| Cột | Kiểu | Mô tả nghiệp vụ | Ví dụ | Ghi chú chất lượng |
|---|---|---|---|---|
| `product_id` | VARCHAR(32) | Mã sản phẩm | `1e9e8ef04dbcff4541ed26657ea517e5` | Duy nhất; sản phẩm nào cũng đã bán |
| `product_category_name` | VARCHAR(60) | Danh mục (tiếng Bồ Đào Nha, snake_case) | `perfumaria` | NULL 610 (1,85%); 73 danh mục, 2 danh mục thiếu bản dịch |
| `product_name_lenght` | INT | **Số ký tự** của tên sản phẩm (không có tên thật) | `40` | Sai chính tả gốc → đổi thành `product_name_length`; NULL cùng 610 dòng |
| `product_description_lenght` | INT | Số ký tự mô tả sản phẩm | `287` | Sai chính tả → `product_description_length`; NULL 610 |
| `product_photos_qty` | INT | Số ảnh sản phẩm đăng bán | `1` | 1–20; NULL 610 |
| `product_weight_g` | INT | Khối lượng (gram) | `225` | 4 dòng = 0, 2 dòng NULL |
| `product_length_cm` | INT | Chiều dài (cm) | `16` | 2 NULL |
| `product_height_cm` | INT | Chiều cao (cm) | `10` | 2 NULL |
| `product_width_cm` | INT | Chiều rộng (cm) | `14` | 2 NULL |

## 8. `category_translation` – Bản dịch danh mục
`product_category_name_translation.csv` · 71 dòng · **PK:** `product_category_name`

| Cột | Kiểu | Mô tả nghiệp vụ | Ví dụ | Ghi chú chất lượng |
|---|---|---|---|---|
| `product_category_name` | VARCHAR(60) | Tên danh mục tiếng Bồ Đào Nha (FK từ `products`) | `beleza_saude` | File có BOM → đọc bằng `utf-8-sig`; thiếu `pc_gamer`, `portateis_cozinha_e_preparadores_de_alimentos` |
| `product_category_name_english` | VARCHAR(60) | Tên danh mục tiếng Anh – dùng hiển thị trên dashboard | `health_beauty` | Không lỗi |

## 9. `geolocation` – Tọa độ theo mã bưu chính
`olist_geolocation_dataset.csv` · 1.000.163 dòng · **Grain:** 1 dòng = 1 điểm tọa độ mẫu của 1 zip · **Không có khóa**

> **Không nạp vào staging** (chốt 16/10/2026 – [decisions.md](decisions.md), bảng cuối file): không câu hỏi nào cần tọa độ, địa lý lấy
> bang / thành phố từ `customers`, `sellers`. Mô tả dưới đây giữ lại để tham khảo; cột "Kiểu" chỉ là đề xuất nếu sau này cần nạp.

| Cột | Kiểu | Mô tả nghiệp vụ | Ví dụ | Ghi chú chất lượng |
|---|---|---|---|---|
| `geolocation_zip_code_prefix` | CHAR(5) | 5 số đầu mã bưu chính | `01037` | Chuỗi; 19.015 zip, TB 52,6 dòng/zip → phải gom 1 dòng/zip trước khi join |
| `geolocation_lat` | NUMERIC(9,6) | Vĩ độ | `-23.545621` | 31 điểm nằm ngoài Brazil (max 45,07) |
| `geolocation_lng` | NUMERIC(9,6) | Kinh độ | `-46.639292` | Ngoài Brazil: tới 121,11 |
| `geolocation_city` | VARCHAR(100) | Thành phố | `sao paulo` | Bẩn nhất: 73.442 dòng có dấu, 2.055 tên nhiều cách viết, lỗi encoding `sa£o paulo` |
| `geolocation_state` | CHAR(2) | Mã bang | `SP` | 8 zip gắn với >1 bang |

**Toàn bảng:** 261.831 dòng trùng hoàn toàn (26%).
