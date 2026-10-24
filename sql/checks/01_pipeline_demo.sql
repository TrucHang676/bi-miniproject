-- =====================================================================
-- 01_pipeline_demo.sql - Câu truy vấn xem kết quả pipeline Mage (docs/pipeline_rules.md B10.4)
--   Dùng khi kiểm thử và khi chụp ảnh demo (báo cáo mục 6.1.6). Q6, Q7: bước dbt trong pipeline (BS-34).
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

-- Q6. Bước dbt của từng lần chạy (BS-34: Mage nạp staging xong thì gọi dbt build, kết quả ở etl_log.dbt_result)
--   Mong đợi khi dữ liệu đúng: mỗi lần SUCCESS có 177 node (2 seed, 20 model, 155 test), loi = 0, bo_qua = 0.
--   so_node = 0: lần chạy dừng trước bước dbt (lỗi khi nạp staging), hoặc dbt không chạy được (đọc error_message ở Q1).
SELECT r.run_id, r.pipeline_name, r.batch_id, r.status,
       count(d.unique_id)                                       AS so_node,
       count(*) FILTER (WHERE d.status IN ('success', 'pass'))  AS dat,
       count(*) FILTER (WHERE d.status = 'warn')                AS canh_bao,
       count(*) FILTER (WHERE d.status IN ('error', 'fail'))    AS loi,
       count(*) FILTER (WHERE d.status = 'skipped')             AS bo_qua,
       round(extract(epoch FROM max(d.finished_at) - min(d.started_at))::numeric, 1) AS so_giay_dbt
FROM etl_log.pipeline_run AS r
LEFT JOIN etl_log.dbt_result AS d USING (run_id)
GROUP BY r.run_id, r.pipeline_name, r.batch_id, r.status
ORDER BY r.run_id;

-- Q7. Kết quả dbt của 1 lần chạy: 9 bảng dds + mọi node không đạt
--   rows_affected: bảng table = số dòng của bảng; incremental (dim_customer, dim_geography) = số dòng thêm / thay lần này.
--   Test FAIL: relation_name = bảng trong dq chứa chính các dòng vi phạm -> SELECT * FROM <relation_name>.
--   Sau batch FULL:      fact_sales 46.418 · fact_delivery 45.394 · fact_review 42.867
--   Sau cả 10 batch:     fact_sales 101.953 · fact_delivery 100.010 · fact_review 100.568
SELECT resource_type, node_name, relation_name, status, rows_affected, failures, execution_time, message
FROM etl_log.dbt_result
WHERE run_id = :run_id
  AND (relation_name LIKE 'dds.%' OR status NOT IN ('success', 'pass'))
ORDER BY status IN ('success', 'pass'), relation_name;
