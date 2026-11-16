# Script phụ trợ

> Chạy ở thư mục gốc repo. `split_batches.py` và `demo_faults.py` chạy được ngay trong container Mage (không cần cài Python trên Windows); hai script khảo sát chạy bằng Python trên máy (`py`, cần pandas).

| Script | Việc | Cách chạy | Kết quả |
|---|---|---|---|
| `profile_olist.py` | Khảo sát chất lượng 9 file CSV gốc: số dòng, giá trị rỗng, trùng khóa, định dạng, khoảng thời gian, toàn vẹn tham chiếu | `py scripts/profile_olist.py` | Ghi đè [docs/data_profiling.md](../docs/data_profiling.md) (file sinh tự động, không sửa tay) |
| `check_keys.py` | Kiểm chứng khóa chính, khóa ngoại và phương án chia batch | `py scripts/check_keys.py` | In kết quả ra màn hình; số liệu dùng cho [docs/decisions.md](../docs/decisions.md) D1–D7 |
| `split_batches.py` | Chia dữ liệu gốc thành 10 batch (`FULL`, `2018-01` … `2018-08`, `2018-09+`) để mô phỏng Full Load và Incremental Load, rồi tự kiểm tra 9 điều kiện | `docker compose exec mage python scripts/split_batches.py` | Thư mục `data/batches/` và `manifest.csv`; dòng cuối phải là `TẤT CẢ ĐẠT (9/9 PASS)`. Định dạng: [data/batches/README.md](../data/batches/README.md) |
| `demo_faults.py` | Tạo tình huống lỗi trên file batch để demo pipeline Mage, rồi trả file về nguyên trạng | `docker compose exec mage python scripts/demo_faults.py <lệnh> [batch]` | Xem bảng dưới |

Các script chỉ **đọc** `data/raw/`, không sửa dữ liệu gốc. `split_batches.py` chạy lại lúc nào cũng được: script xóa các thư mục batch cũ rồi ghi lại giống hệt từng byte.

## Lệnh của `demo_faults.py`

Chỉ sửa file trong `data/batches/`, không đụng database. Mọi file bị sửa được sao lưu vào `data/batches/_demo_backup/` trước khi sửa.

| Lệnh | Thay đổi | Pipeline sẽ thấy |
|---|---|---|
| `status` | Không sửa gì | In ra các file batch đang bị sửa, hoặc báo file batch còn nguyên gốc |
| `missing-column <batch>` | `order_payments.csv` mất tên cột `payment_type` ở dòng tiêu đề | `columns_match` FAIL, cả batch dừng, lần chạy FAILED, staging hoàn tác |
| `missing-file <batch>` | `order_payments.csv` bị đổi tên thành `.csv.hidden` | `file_exists` FAIL, cả batch dừng, lần chạy FAILED |
| `bad-rows <batch>` | `order_payments.csv` có 1 dòng trống `order_id`, 1 dòng bị lặp, 1 dòng `payment_value = 'abc'` | `not_null_key`, `duplicate_key`, `type_cast` WARN; 4 dòng vào `dq.rejected_rows`; các dòng còn lại vẫn nạp, lần chạy SUCCESS |
| `delete-order <batch>` | Thêm `deleted_orders.csv`: 1 đơn có thật của batch FULL và 1 mã đơn không tồn tại | Đơn có thật bị xóa mềm (`rows_deleted = 1`); dòng còn lại `key_exists` WARN |
| `restore` | Chép lại các file gốc từ bản sao lưu | Batch trở về nguyên trạng |

Ví dụ: `docker compose exec mage python scripts/demo_faults.py missing-column 2018-02`, chạy `incremental_load`, xem kết quả bằng [sql/checks/01_pipeline_demo.sql](../sql/checks/01_pipeline_demo.sql), rồi `restore` và chạy lại.
