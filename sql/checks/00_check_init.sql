-- =====================================================================
-- 00_check_init.sql - Kiểm tra database đã khởi tạo đủ (sau khi dựng môi trường)
-- Cách chạy (chọn 1):
--   * Terminal: docker compose exec postgres psql -U olist_user -d olist_dw -f /sql/checks/00_check_init.sql
--   * DBeaver : dán cả file vào SQL Editor, đặt con trỏ trong câu lệnh, Ctrl + Enter
-- Kết quả đúng: 23 dòng, MỌI dòng có ket_qua = PASS.
-- =====================================================================
WITH
expected_schemas(stt, schema_name) AS (
    VALUES (1, 'staging'), (2, 'etl_log'), (3, 'dq'), (4, 'dds')
),
expected_views(stt, table_name, so_cot) AS (                    -- view cho dashboard theo dõi ETL (06)
    VALUES (40, 'v_run',            44),
           (41, 'v_batch_progress', 13),
           (42, 'v_quality_issue',  12)
),
expected_tables(stt, table_schema, table_name, so_cot) AS (     -- số cột theo sql/init/01 - 05
    VALUES (10, 'staging', 'orders',               12),    -- 10 + _is_deleted, _deleted_at (04)
           (11, 'staging', 'order_items',           9),
           (12, 'staging', 'order_payments',        7),
           (13, 'staging', 'order_reviews',         9),
           (14, 'staging', 'customers',             7),
           (15, 'staging', 'sellers',               6),
           (16, 'staging', 'products',             11),
           (17, 'staging', 'category_translation',  4),
           (20, 'etl_log', 'pipeline_run',         11),
           (21, 'etl_log', 'table_load',           11),    -- 10 + rows_deleted (04)
           (22, 'etl_log', 'quality_check',         7),
           (23, 'etl_log', 'dbt_result',           12),    -- kết quả bước dbt trong pipeline Mage (05)
           (30, 'dq',      'rejected_rows',         8)
),
actual_cols AS (
    SELECT table_schema, table_name, count(*) AS so_cot
    FROM information_schema.columns
    WHERE table_schema IN ('staging', 'etl_log', 'dq')
    GROUP BY table_schema, table_name
),
actual_pk AS (
    SELECT table_schema, table_name
    FROM information_schema.table_constraints
    WHERE constraint_type = 'PRIMARY KEY'
),
db_settings AS (   -- cấu hình gắn với database (không phải phiên DBeaver đang mở)
    SELECT coalesce(s.setconfig, '{}') AS setconfig, pg_encoding_to_char(d.encoding) AS encoding
    FROM pg_database d
    LEFT JOIN pg_db_role_setting s ON s.setdatabase = d.oid AND s.setrole = 0
    WHERE d.datname = current_database()
),
results(stt, kiem_tra, thuc_te, dat) AS (
    SELECT stt, 'Schema ' || schema_name,
           CASE WHEN n.oid IS NULL THEN 'không có' ELSE 'có' END,
           n.oid IS NOT NULL
    FROM expected_schemas e LEFT JOIN pg_namespace n ON n.nspname = e.schema_name

    UNION ALL
    SELECT 5, 'Extension unaccent', coalesce(unaccent('são paulo'), '-'), unaccent('são paulo') = 'sao paulo'

    UNION ALL
    SELECT 6, 'Encoding database', encoding, encoding = 'UTF8' FROM db_settings

    UNION ALL
    SELECT 7, 'Múi giờ database', coalesce(array_to_string(setconfig, ', '), ''),
           'TimeZone=Asia/Ho_Chi_Minh' = ANY (setconfig)
    FROM db_settings

    UNION ALL
    SELECT e.stt, 'Bảng ' || e.table_schema || '.' || e.table_name,
           format('%s/%s cột, khóa chính: %s', coalesce(a.so_cot, 0), e.so_cot,
                  CASE WHEN p.table_name IS NULL THEN 'không có' ELSE 'có' END),
           a.so_cot = e.so_cot AND p.table_name IS NOT NULL
    FROM expected_tables e
    LEFT JOIN actual_cols a USING (table_schema, table_name)
    LEFT JOIN actual_pk  p USING (table_schema, table_name)

    UNION ALL
    SELECT e.stt, 'View etl_log.' || e.table_name,
           format('%s/%s cột', coalesce(a.so_cot, 0), e.so_cot),
           a.so_cot = e.so_cot
    FROM expected_views e
    LEFT JOIN actual_cols a ON a.table_schema = 'etl_log' AND a.table_name = e.table_name
)
SELECT kiem_tra, thuc_te, CASE WHEN dat THEN 'PASS' ELSE 'FAIL' END AS ket_qua
FROM results
ORDER BY stt;
