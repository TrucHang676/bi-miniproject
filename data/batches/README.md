# Batch dữ liệu – mô phỏng Full Load + Incremental Load

> Sinh bởi [`scripts/split_batches.py`](../../scripts/split_batches.py) (BS-19) từ `data/raw/`. Quy tắc chia: [docs/decisions.md](../../docs/decisions.md) D5, D6, D8 (phương án B).
> Các file batch **không commit** (`.gitignore`) – mỗi máy tự sinh, kết quả **giống hệt từng byte** trên mọi máy. File này là "hợp đồng" định dạng cho các task pipeline (BS-21 kiểm tra chất lượng, BS-22 Full Load, BS-23 Incremental Load, BS-24 ghi log).

## 1. Cách sinh

```powershell
docker compose exec mage python scripts/split_batches.py    # chạy trong container Mage – không cần cài Python
# hoặc: py scripts/split_batches.py                         # Python trên máy, cần pandas
```

Mất ~15 giây. Dòng cuối phải là **`TẤT CẢ ĐẠT (9/9 PASS)`** (mục 6). Chạy lại lúc nào cũng được: script xóa các thư mục batch cũ rồi ghi lại y hệt.

## 2. Cấu trúc

```
data/batches/
├── manifest.csv     1 dòng / batch, theo thứ tự chạy (mục 3)
├── FULL/            8 file: orders, order_items, order_payments, order_reviews, customers
│                            + products, sellers, category_translation (chỉ có ở FULL)
├── 2018-01/         5 file bảng giao dịch: orders, order_items, order_payments, order_reviews, customers
├── ...              (luôn đủ 5 file, kể cả khi 0 dòng – file chỉ có dòng tiêu đề)
├── 2018-08/
└── 2018-09+/        batch cuối: 20 đơn mới + đối soát (gửi lại 67 đơn về đúng trạng thái gốc)
```

## 3. `manifest.csv` – thứ tự chạy và số liệu mong đợi

| Cột | Ý nghĩa | Dùng cho |
|---|---|---|
| `seq` | Thứ tự chạy 1 → 10 | Incremental: nạp batch có `seq` nhỏ nhất chưa `SUCCESS` trong `etl_log.pipeline_run` |
| `batch_id` | `FULL`, `2018-01` … `2018-08`, `2018-09+` = tên thư mục | `etl_log.pipeline_run.batch_id`, cột `_batch_id` của staging |
| `load_type` | `FULL` / `INCREMENTAL` | `etl_log.pipeline_run.load_type` |
| `lset`, `cet` | Khoảng dữ liệu mô phỏng `[LSET, CET)`; trống = không giới hạn (FULL không có `lset`, batch cuối không có `cet`) | `etl_log.pipeline_run.lset`, `cet` |
| `orders` … `category_translation` | Số dòng của từng file | So với `etl_log.table_load.rows_source` |
| `orders_new`, `orders_resent` | Số đơn mới / số đơn cũ gửi lại trong `orders.csv` | Đáp án cho `rows_inserted` / `rows_updated` của bảng `orders` |

Số liệu hiện tại:

| seq | batch_id | lset → cet | orders (mới + gửi lại) | items | payments | reviews | customers |
|---|---|---|---|---|---|---|---|
| 1 | FULL | … → 2018-01-01 | 45.430 (45.430 + 0) | 51.234 | 47.871 | 42.381 | 45.430 |
| 2 | 2018-01 | 2018-01-01 → 2018-02-01 | 9.725 (7.269 + 2.456) | 8.208 | 7.563 | 6.272 | 7.269 |
| 3 | 2018-02 | 2018-02-01 → 2018-03-01 | 9.581 (6.728 + 2.853) | 7.672 | 6.952 | 6.096 | 6.728 |
| 4 | 2018-03 | 2018-03-01 → 2018-04-01 | 10.676 (7.211 + 3.465) | 8.217 | 7.512 | 7.655 | 7.211 |
| 5 | 2018-04 | 2018-04-01 → 2018-05-01 | 10.637 (6.939 + 3.698) | 7.975 | 7.209 | 7.621 | 6.939 |
| 6 | 2018-05 | 2018-05-01 → 2018-06-01 | 9.614 (6.873 + 2.741) | 7.925 | 7.135 | 7.516 | 6.873 |
| 7 | 2018-06 | 2018-06-01 → 2018-07-01 | 8.590 (6.167 + 2.423) | 7.078 | 6.419 | 6.366 | 6.167 |
| 8 | 2018-07 | 2018-07-01 → 2018-08-01 | 7.979 (6.292 + 1.687) | 7.092 | 6.507 | 5.822 | 6.292 |
| 9 | 2018-08 | 2018-08-01 → 2018-09-01 | 8.522 (6.512 + 2.010) | 7.248 | 6.698 | 8.810 | 6.512 |
| 10 | 2018-09+ | 2018-09-01 → … | 87 (20 + 67) | 1 | 20 | 685 | 20 |

FULL còn có `sellers` 3.095, `products` 32.951, `category_translation` 71 dòng.

## 4. Định dạng mỗi file CSV

- **Tên file = tên bảng staging** (`sql/init/01_staging_tables.sql`).
- **Cột = cột của CSV gốc**, cùng thứ tự, giữ cả tên sai chính tả (`product_name_lenght`) **+ cột `batch_id` ở cuối**. Khi nạp: `batch_id` → cột `_batch_id`, `_loaded_at` = `now()`.
- **Giá trị giữ nguyên chuỗi gốc**: zip có số 0 đầu (`01037`) → đọc bằng `dtype=str` rồi ép kiểu theo bảng staging; mốc thời gian dạng `YYYY-MM-DD HH:MM:SS`.
- **Ô trống = NULL** – gồm cả các mốc bị che vì "chưa xảy ra" ở thời điểm cắt batch (D8).
- UTF-8 không BOM, xuống dòng LF. Bình luận review có xuống dòng **bên trong ô** (nằm trong ngoặc kép) → đọc bằng CSV parser chuẩn (`pandas.read_csv`, `COPY ... CSV`), không đọc theo từng dòng.

## 5. Mỗi batch chứa gì

| File | Nội dung | Khi MERGE vào staging |
|---|---|---|
| `orders.csv` | Đơn **mới** (mua trong batch) + đơn **cũ gửi lại** vì có mốc mới trong batch (VD vừa được giao). Trạng thái là **ảnh chụp tại `cet`**: mốc chưa xảy ra để trống, `order_status` suy từ mốc muộn nhất (D8). Không có cột đánh dấu mới / cũ – MERGE theo `order_id` tự phân biệt | INSERT + UPDATE |
| `order_items.csv`, `order_payments.csv`, `customers.csv` | Chỉ dòng của đơn **mới** – mỗi dòng gửi đúng 1 lần (D5) | Chỉ INSERT |
| `order_reviews.csv` | Review khách **trả lời** trong batch – thường là của đơn batch trước (D8 mục 4) | Chỉ INSERT |
| `products.csv`, `sellers.csv`, `category_translation.csv` | Toàn bộ, **chỉ ở FULL** (D3) | Chỉ INSERT |

Ví dụ đơn `82a35d13f3b95427d47aa11e4afde83b` (mua 27/01/2018): ở `2018-01/orders.csv` là `shipped`, chưa có ngày khách nhận → INSERT; ở `2018-02/orders.csv` là `delivered`, ngày nhận 20/02 → UPDATE; review 3★ nằm ở `2018-02/order_reviews.csv`.

## 6. Script đã tự kiểm tra gì

Sau khi ghi, script đọc lại các file (như Mage sẽ đọc), phát lại 10 batch theo thứ tự và kiểm tra:

| # | Kiểm tra |
|---|---|
| 1 | Đủ file trong mọi thư mục batch |
| 2 | Số dòng mỗi file khớp `manifest.csv` |
| 3 | Không trùng khóa chính trong cùng 1 file (MERGE sẽ lỗi nếu 1 khóa xuất hiện 2 lần trong 1 lần nạp) |
| 4 | Bảng con / tham chiếu: mỗi dòng chỉ gửi 1 lần |
| 5 | Không batch nào chứa mốc xảy ra sau `cet` của nó (không "biết trước tương lai") |
| 6 | Khóa ngoại: dòng cha luôn có trước (hoặc cùng batch) dòng con |
| 7 | `orders`: trạng thái không đi lùi, mốc đã có không bị đổi |
| 8 | `orders`: số INSERT / UPDATE khi phát lại khớp `orders_new` / `orders_resent` |
| 9 | Phát lại hết 10 batch = file gốc `data/raw/` – mọi bảng, mọi cột |

Đã thử cố tình làm hỏng file (chèn ngày tương lai, xóa / lặp dòng, trạng thái đi lùi, đổi mốc, xóa file, đẩy review lên trước đơn): cả 8 trường hợp đều bị bắt.

## 7. Lưu ý cho pipeline Mage

1. **Nạp đúng thứ tự `seq`**, mỗi lần 1 batch. Trong 1 batch nạp theo thứ tự (D5): *(FULL: `products`, `sellers`, `category_translation` →)* `customers` → `orders` → `order_items`, `order_payments` → `order_reviews`.
2. **MERGE theo khóa chính** (D1), không xóa dòng vắng mặt trong batch (D4):

   | Bảng | Khóa chính |
   |---|---|
   | `orders` | `order_id` |
   | `order_items` | `order_id`, `order_item_id` |
   | `order_payments` | `order_id`, `payment_sequential` |
   | `order_reviews` | `review_id`, `order_id` |
   | `customers` | `customer_id` |
   | `sellers` / `products` / `category_translation` | `seller_id` / `product_id` / `product_category_name` |

3. **Số liệu mong đợi trong `etl_log.table_load`** khi nạp lần đầu theo đúng thứ tự: `rows_source` = số dòng trong manifest; `orders`: `rows_inserted` = `orders_new`, `rows_updated` = `orders_resent`; các bảng khác: `rows_inserted` = số dòng, `rows_updated` = 0. *Chạy lại* một batch đã nạp thì mọi dòng đều đã có khóa trong staging → 0 INSERT; số UPDATE = số dòng nếu MERGE cập nhật mọi dòng khớp khóa (hoặc 0 nếu chỉ cập nhật khi giá trị khác) – đúng, không phải lỗi.
4. Sau batch cuối `2018-09+`, staging phải **khớp 100% `data/raw/`** (D8) – nên có query đối soát trong `sql/checks/`.
5. Trạng thái trung gian trong batch là **dữ liệu mô phỏng** suy từ các mốc ngày (D8) – báo cáo và video demo phải nói rõ.
