-- =====================================================================
-- 03_dbt_test_demo.sql - Xem kết quả dbt test và demo kiểm thử dbt (docs/dbt_rules.md B7)
--   Dùng khi dbt build báo FAIL, khi demo / quay video, khi chụp ảnh cho báo cáo mục 6.2.4.
--   DBeaver: đặt con trỏ vào 1 câu -> Ctrl + Enter.
--   Mỗi dbt test lưu các dòng VI PHẠM vào 1 bảng riêng trong schema dq (store_failures, ghi đè ở mỗi lần chạy):
--   155 bảng, tên bảng = tên test (tên dài thì dbt cắt ngắn + thêm mã hash). Bảng 0 dòng = test đạt.
--   Khác dq.rejected_rows: bảng đó do Mage ghi - dòng bị LOẠI, không vào staging. dbt test chỉ PHÁT HIỆN,
--   dòng sai vẫn nằm trong staging / dds cho tới khi sửa nguồn rồi nạp lại.
-- =====================================================================

-- Q1. Test nào đang có dòng vi phạm (chạy sau mỗi dbt build / dbt test)
--   Mong đợi khi dữ liệu đúng: 0 dòng. Tên bảng ở đây = tên dbt in ra sau chữ "See test failures".
SELECT t.table_name AS bang_loi_dbt_test, x.so_dong_vi_pham
FROM information_schema.tables AS t
CROSS JOIN LATERAL (
    -- đếm số dòng của từng bảng (tên bảng lấy động từ information_schema)
    SELECT (xpath('/row/c/text()', query_to_xml(
               format('SELECT count(*) AS c FROM %I.%I', t.table_schema, t.table_name), false, true, '')))[1]::text::int
           AS so_dong_vi_pham
) AS x
WHERE t.table_schema = 'dq'
  AND t.table_name <> 'rejected_rows'
  AND x.so_dong_vi_pham > 0
ORDER BY x.so_dong_vi_pham DESC, t.table_name;

-- Q2. Tổng quan schema dq
--   Mong đợi: 155 bảng dbt test (= số test của project) · số dòng Mage loại tùy lần nạp (0 khi dữ liệu batch sạch)
SELECT
    (SELECT count(*) FROM information_schema.tables
      WHERE table_schema = 'dq' AND table_name <> 'rejected_rows') AS so_bang_dbt_test,
    (SELECT count(*) FROM dq.rejected_rows)                        AS so_dong_mage_da_loai;

-- Q3. Demo 1 test FAIL (dbt_rules.md B7 kịch bản 6) - chạy từng bước, NHỚ chạy bước 4 khi demo xong
--   Bước 1: thêm 1 dòng order_items trỏ tới đơn không tồn tại
--     INSERT INTO staging.order_items (order_id, order_item_id, product_id, seller_id, _batch_id)
--     SELECT 'demo_orphan_order', 1, product_id, seller_id, 'DEMO' FROM staging.order_items LIMIT 1;
--   Bước 2: docker compose exec mage dbt test --select source:staging
--     -> test source_relationships_staging_order_items_order_id__order_id__source_staging_orders_ báo FAIL 1
--        Done. PASS=8 WARN=0 ERROR=1 SKIP=0 TOTAL=9
--        (9 test = 8 test nguồn + assert_no_deleted_orders_in_facts, vì test đó cũng đọc staging.orders)
--   Bước 3: xem dòng lỗi - đúng bảng dbt in ra sau "See test failures" (Q1 cũng ra bảng này)
--     Mong đợi: 1 dòng, from_field = demo_orphan_order
SELECT * FROM dq.source_relationships_staging_o_e2f0b1bc186e5bee3058cd672e745441;
--   Bước 4 (dọn): DELETE FROM staging.order_items WHERE order_id = 'demo_orphan_order';
--                 rồi chạy lại bước 2 -> PASS=9, bảng ở bước 3 trống lại

-- Q4. Khóa dimension KHÔNG được đổi giữa 2 lần dbt build (B7 kịch bản 3 - nạp từng batch)
--   Bước 1 - TRƯỚC khi nạp batch: chụp khóa hiện tại vào bảng tạm (TEMP: chỉ sống trong phiên DBeaver
--            đang mở, đóng DBeaver là mất, không ghi gì vào DB)
CREATE TEMP TABLE khoa_truoc AS
SELECT 'dim_customer' AS dim, customer_unique_id AS nk, customer_key AS khoa
FROM dds.dim_customer WHERE customer_key <> -1
UNION ALL
SELECT 'dim_geography', state_code || '|' || city, geography_key
FROM dds.dim_geography WHERE geography_key <> -1;
--   Bước 2: docker compose exec mage mage run /home/src/mage/olist_etl incremental_load
--           docker compose exec mage dbt build
--   Bước 3: so khóa sau khi build với bảng tạm ở bước 1
--     Mong đợi: khoa_cu_bi_doi = 0 · noi_tiep = true (khóa mới bắt đầu từ khóa lớn nhất cũ + 1, không hở)
--     VD batch 2018-01: dim_customer 7.025 dòng mới, khóa 44.035 … 51.059; dim_geography 184 dòng mới, 3.414 … 3.597
WITH khoa_sau AS (
    SELECT 'dim_customer' AS dim, customer_unique_id AS nk, customer_key AS khoa
    FROM dds.dim_customer WHERE customer_key <> -1
    UNION ALL
    SELECT 'dim_geography', state_code || '|' || city, geography_key
    FROM dds.dim_geography WHERE geography_key <> -1
),
so_sanh AS (                                -- ghép từng thực thể trước / sau theo khóa tự nhiên
    SELECT coalesce(s.dim, t.dim) AS dim, t.khoa AS khoa_cu, s.khoa AS khoa_moi
    FROM khoa_sau AS s
    FULL JOIN khoa_truoc AS t ON t.dim = s.dim AND t.nk = s.nk
),
tong_hop AS (
    SELECT
        dim,
        count(*) FILTER (WHERE khoa_cu IS NOT NULL AND khoa_moi IS DISTINCT FROM khoa_cu) AS khoa_cu_bi_doi,
        count(*) FILTER (WHERE khoa_cu IS NULL)                                           AS so_dong_moi,
        coalesce(max(khoa_cu), 0)                                                         AS khoa_lon_nhat_cu,
        min(khoa_moi) FILTER (WHERE khoa_cu IS NULL)                                      AS khoa_moi_tu,
        max(khoa_moi) FILTER (WHERE khoa_cu IS NULL)                                      AS khoa_moi_den
    FROM so_sanh
    GROUP BY dim
)
SELECT
    *,
    (so_dong_moi = 0 OR (khoa_moi_tu = khoa_lon_nhat_cu + 1 AND khoa_moi_den = khoa_lon_nhat_cu + so_dong_moi)) AS noi_tiep
FROM tong_hop
ORDER BY dim;
--   Bước 4: DROP TABLE khoa_truoc;   (trước khi lặp lại bước 1 cho batch sau)
