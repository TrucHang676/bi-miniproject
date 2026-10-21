-- =====================================================================
-- 01_pipeline_demo.sql - Câu truy vấn xem kết quả pipeline Mage (docs/pipeline_rules.md B10.4)
--   Dùng khi kiểm thử và khi chụp ảnh demo (báo cáo mục 6.1.6).
--   DBeaver: đặt con trỏ vào 1 câu -> Ctrl + Enter. Câu có :run_id thì DBeaver hỏi giá trị -> điền run_id lấy ở Q1.
--   Đối chiếu số liệu với data/batches/manifest.csv (data/batches/README.md mục 3).
-- =====================================================================

-- Q1. Các lần chạy (LSET / CET = thời gian mô phỏng của batch; started_at / finished_at = giờ chạy thật)
SELECT run_id, pipeline_name, batch_id, lset, cet, status, error_message, started_at, finished_at
FROM etl_log.pipeline_run
ORDER BY run_id;

-- Q2. Từng bảng của 1 lần chạy
SELECT table_name, rows_source, rows_inserted, rows_updated, rows_rejected, rows_deleted, status, error_message
FROM etl_log.table_load
WHERE run_id = :run_id
ORDER BY started_at;

-- Q3. Các phép kiểm tra chất lượng của 1 lần chạy
SELECT table_name, check_name, failed_rows, status, detail
FROM etl_log.quality_check
WHERE run_id = :run_id
ORDER BY checked_at;

-- Q4. Dòng bị loại của 1 lần chạy (DQ database)
SELECT table_name, check_name, source_row, row_data, reason
FROM dq.rejected_rows
WHERE run_id = :run_id;

-- Q5. Số dòng staging
-- Sau batch FULL: orders 45.430 · order_items 51.234 · order_payments 47.871 · order_reviews 42.381
--                 customers 45.430 · sellers 3.095 · products 32.951 · category_translation 71
-- Sau cả 10 batch (= data/raw/): orders 99.441 · order_items 112.650 · order_payments 103.886
--                 order_reviews 99.224 · customers 99.441 · sellers 3.095 · products 32.951 · category_translation 71
SELECT 'orders' AS bang, count(*) AS so_dong FROM staging.orders
UNION ALL SELECT 'order_items', count(*) FROM staging.order_items
UNION ALL SELECT 'order_payments', count(*) FROM staging.order_payments
UNION ALL SELECT 'order_reviews', count(*) FROM staging.order_reviews
UNION ALL SELECT 'customers', count(*) FROM staging.customers
UNION ALL SELECT 'sellers', count(*) FROM staging.sellers
UNION ALL SELECT 'products', count(*) FROM staging.products
UNION ALL SELECT 'category_translation', count(*) FROM staging.category_translation;
