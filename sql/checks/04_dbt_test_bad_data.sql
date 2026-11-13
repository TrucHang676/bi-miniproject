-- =====================================================================
-- 04_dbt_test_bad_data.sql - Dữ liệu sai mẫu để kiểm chứng dbt test (báo cáo mục 6.2.4, phần d - f)
--   Cố ý đưa 13 lỗi vào dữ liệu rồi chạy dbt, xem test nào phát hiện, dòng vi phạm nằm ở bảng dq nào.
--   CHỈ chạy trên BẢN SAO olist_dw_demo, không chạy trên kho thật olist_dw: mỗi khối sửa dữ liệu
--   đều tự kiểm tra tên database và dừng nếu không phải olist_dw_demo.
--   Kết quả mong đợi ghi theo lần chạy thật ngày 13/11/2026 (staging đủ 10 batch, dbt 1.8.7).
--
-- Cách dùng (PowerShell, ở thư mục gốc repo):
--   0) Tạo bản sao - phải ngắt mọi kết nối tới olist_dw trước (DBeaver: Disconnect), vì TEMPLATE cần DB nguồn rảnh:
--        docker compose exec postgres psql -U olist_user -d postgres -c "DROP DATABASE IF EXISTS olist_dw_demo;"
--        docker compose exec postgres psql -U olist_user -d postgres -c "CREATE DATABASE olist_dw_demo TEMPLATE olist_dw;"
--   1) Mở bản sao trong DBeaver (đổi Database của kết nối thành olist_dw_demo), chạy từng khối bên dưới
--      (đặt con trỏ trong khối -> Ctrl + Enter).
--   2) Chạy dbt trên bản sao: đổi biến POSTGRES_DB (profiles.yml đọc dbname từ biến này):
--        docker compose exec -e POSTGRES_DB=olist_dw_demo mage dbt build
--        docker compose exec -e POSTGRES_DB=olist_dw_demo mage dbt test
--   3) Xong thì xóa bản sao (mục 5).
-- =====================================================================


-- =====================================================================
-- 1. NHÓM 1 - DỮ LIỆU NGUỒN SAI (sửa staging, rồi chạy dbt build)
-- =====================================================================
DO $$
BEGIN
    IF current_database() <> 'olist_dw_demo' THEN
        RAISE EXCEPTION 'Chỉ chạy trên bản sao olist_dw_demo (đang ở %)', current_database();
    END IF;
    -- N1 accepted_values: phương thức thanh toán mới 'pix' chưa có trong danh sách hợp lệ
    UPDATE staging.order_payments SET payment_type = 'pix'
     WHERE order_id = '82a35d13f3b95427d47aa11e4afde83b' AND payment_sequential = 1;
    -- N2 relationships (nguồn): dòng chi tiết trỏ tới đơn không tồn tại
    INSERT INTO staging.order_items (order_id, order_item_id, product_id, seller_id,
                                     shipping_limit_date, price, freight_value, _batch_id)
    SELECT 'demo_orphan_order', 1, product_id, seller_id, shipping_limit_date, price, freight_value, 'DEMO'
      FROM staging.order_items
     WHERE order_id = '82a35d13f3b95427d47aa11e4afde83b' AND order_item_id = 1;
    -- N3 relationships (nguồn -> seed): mã bang viết thường 'sp'
    UPDATE staging.customers SET customer_state = 'sp'
     WHERE customer_id = (SELECT customer_id FROM staging.orders
                           WHERE order_id = '0758eac62489b47a99c64b7d67c5ff18');
    -- N4 accepted_values: điểm đánh giá ngoài thang 1-5
    UPDATE staging.order_reviews SET review_score = 6
     WHERE review_id = '630d569fee9f300cfbc52eaf4dfddfe9' AND order_id = '82a35d13f3b95427d47aa11e4afde83b';
    -- N5 not_null: thiếu thời điểm khách trả lời đánh giá
    UPDATE staging.order_reviews SET review_answer_timestamp = NULL
     WHERE review_id = '0a5b2897b129b210495b0e325a3fc56f' AND order_id = '0758eac62489b47a99c64b7d67c5ff18';
END $$;
--   docker compose exec -e POSTGRES_DB=olist_dw_demo mage dbt build
--   Mong đợi: Done. PASS=69 WARN=0 ERROR=5 SKIP=103 TOTAL=177
--     FAIL 1 source_relationships_staging_order_items_order_id__order_id__source_staging_orders_       (N2)
--     FAIL 1 source_relationships_staging_customers_customer_state__state_code__ref_seed_brazil_states_ (N3)
--     FAIL 1 accepted_values_stg_order_payments_payment_type__...                                      (N1)
--     FAIL 1 accepted_values_stg_order_reviews_review_score__False__1__2__3__4__5                      (N4)
--     FAIL 1 not_null_stg_order_reviews_review_answer_timestamp                                        (N5)
--     SKIP: stg_order_items, int_*, dim_geography, dim_customer, 3 fact và test của chúng
--     -> bảng dds giữ dữ liệu của lần chạy đạt gần nhất (fact_review của đơn 82a35d13 vẫn 3 sao).

-- Q1. Xem dòng vi phạm của nhóm 1 (tên bảng = tên dbt in sau "See test failures")
SELECT * FROM dq.source_relationships_staging_o_e2f0b1bc186e5bee3058cd672e745441;  -- from_field = demo_orphan_order
SELECT * FROM dq.source_relationships_staging_c_448610edeba1844ef55e472a721eb249;  -- from_field = sp
SELECT * FROM dq.accepted_values_stg_order_paym_7b13b62927324389263117e84178c52c;  -- pix | 1
SELECT * FROM dq.accepted_values_stg_order_revi_6b94ed5f3d4ce6f6910adf167ddde00b;  -- 6 | 1
SELECT * FROM dq.not_null_stg_order_reviews_review_answer_timestamp;               -- đánh giá 0a5b2897...
--   Liệt kê mọi bảng dq đang có dòng vi phạm: câu Q1 của sql/checks/03_dbt_test_demo.sql (ra đúng 5 bảng, mỗi bảng 1 dòng)

-- Hoàn tác nhóm 1 (trả đúng giá trị gốc)
DO $$
BEGIN
    IF current_database() <> 'olist_dw_demo' THEN
        RAISE EXCEPTION 'Chỉ chạy trên bản sao olist_dw_demo (đang ở %)', current_database();
    END IF;
    UPDATE staging.order_payments SET payment_type = 'credit_card'
     WHERE order_id = '82a35d13f3b95427d47aa11e4afde83b' AND payment_sequential = 1;
    DELETE FROM staging.order_items WHERE order_id = 'demo_orphan_order';
    UPDATE staging.customers SET customer_state = 'SP'
     WHERE customer_id = (SELECT customer_id FROM staging.orders
                           WHERE order_id = '0758eac62489b47a99c64b7d67c5ff18');
    UPDATE staging.order_reviews SET review_score = 3
     WHERE review_id = '630d569fee9f300cfbc52eaf4dfddfe9' AND order_id = '82a35d13f3b95427d47aa11e4afde83b';
    UPDATE staging.order_reviews SET review_answer_timestamp = '2017-12-20 20:16:42'
     WHERE review_id = '0a5b2897b129b210495b0e325a3fc56f' AND order_id = '0758eac62489b47a99c64b7d67c5ff18';
END $$;


-- =====================================================================
-- 2. NHÓM 2 - ĐÚNG KIỂU NHƯNG SAI NGHIỆP VỤ (sửa staging, rồi chạy dbt build)
--    Qua được kiểm tra của Mage và mọi test tầng nguồn / staging; chỉ lộ ra khi thành measure trong fact.
-- =====================================================================
DO $$
BEGIN
    IF current_database() <> 'olist_dw_demo' THEN
        RAISE EXCEPTION 'Chỉ chạy trên bản sao olist_dw_demo (đang ở %)', current_database();
    END IF;
    -- N6 accepted_range: giá bán bằng 0 (gốc 25.90)
    UPDATE staging.order_items SET price = 0
     WHERE order_id = '0758eac62489b47a99c64b7d67c5ff18' AND order_item_id = 3;
    -- N7 accepted_range: ngày khách nhận hàng gõ nhầm năm (gốc 2018-02-20) -> trước ngày đặt 2018-01-27
    UPDATE staging.orders SET order_delivered_customer_date = '2017-02-20 00:33:35'
     WHERE order_id = '82a35d13f3b95427d47aa11e4afde83b';
END $$;
--   docker compose exec -e POSTGRES_DB=olist_dw_demo mage dbt build
--   Mong đợi: Done. PASS=174 WARN=0 ERROR=3 SKIP=0 TOTAL=177
--     FAIL 1 dbt_utils_accepted_range_fact_sales_unit_price__False__0      (N6)
--     FAIL 1 dbt_utils_accepted_range_fact_sales_revenue__False__0         (N6)
--     FAIL 1 dbt_utils_accepted_range_fact_delivery_delivery_days__0       (N7: delivery_days = -341.88)
--   Lưu ý: test chạy SAU khi model được dựng -> fact_sales, fact_delivery của bản sao đang mang giá trị sai.
SELECT * FROM dq."dbt_utils_accepted_range_fact_sales_unit_price__False__0";   -- tên có chữ hoa -> phải đặt trong ""
SELECT * FROM dq."dbt_utils_accepted_range_fact_sales_revenue__False__0";
SELECT * FROM dq.dbt_utils_accepted_range_fact_delivery_delivery_days__0;

-- Hoàn tác nhóm 2, rồi chạy lại dbt build -> Mong đợi: PASS=177, câu Q1 của 03_dbt_test_demo.sql ra 0 dòng
DO $$
BEGIN
    IF current_database() <> 'olist_dw_demo' THEN
        RAISE EXCEPTION 'Chỉ chạy trên bản sao olist_dw_demo (đang ở %)', current_database();
    END IF;
    UPDATE staging.order_items SET price = 25.90
     WHERE order_id = '0758eac62489b47a99c64b7d67c5ff18' AND order_item_id = 3;
    UPDATE staging.orders SET order_delivered_customer_date = '2018-02-20 00:33:35'
     WHERE order_id = '82a35d13f3b95427d47aa11e4afde83b';
END $$;


-- =====================================================================
-- 3. NHÓM 3 - LỖI Ở KHÂU BIẾN ĐỔI (giả lập model viết sai: sửa thẳng bảng dds, rồi chạy dbt TEST)
--    Chạy SAU khi nhóm 2 đã hoàn tác và dbt build đạt PASS=177. Dùng dbt test (không build) để giữ lỗi.
-- =====================================================================
DO $$
BEGIN
    IF current_database() <> 'olist_dw_demo' THEN
        RAISE EXCEPTION 'Chỉ chạy trên bản sao olist_dw_demo (đang ở %)', current_database();
    END IF;
    -- B1 unique: một khách có 2 dòng trong dim_customer (khóa mới = khóa lớn nhất + 1)
    INSERT INTO dds.dim_customer
    SELECT * FROM dds.dim_customer WHERE customer_unique_id = 'b1a6621008f2bb41784232794e2ef0a3';
    UPDATE dds.dim_customer SET customer_key = (SELECT max(customer_key) + 1 FROM dds.dim_customer)
     WHERE ctid = (SELECT max(ctid) FROM dds.dim_customer
                    WHERE customer_unique_id = 'b1a6621008f2bb41784232794e2ef0a3');
    -- B2 relationships: fact trỏ tới khóa sản phẩm không có trong dim_product
    UPDATE dds.fact_sales SET product_key = 99999 WHERE order_id = 'e481f51cbdc54678b7cc49136f2d6af7';
    -- B3 unique_combination_of_columns + assert_facts_match_sources: nhân đôi 1 dòng fact
    INSERT INTO dds.fact_sales SELECT * FROM dds.fact_sales WHERE order_id = '82a35d13f3b95427d47aa11e4afde83b';
    -- B4 expression_is_true: đơn giá không khớp doanh thu (revenue 43.80 nhưng 2 x 23.90 = 47.80)
    UPDATE dds.fact_sales SET unit_price = 23.90
     WHERE order_id = '0758eac62489b47a99c64b7d67c5ff18' AND quantity = 2;
    -- B5 assert_dim_unknown_members: mất dòng -1 "Không xác định" của dim_geography
    DELETE FROM dds.dim_geography WHERE geography_key = -1;
    -- B6 assert_one_latest_review_per_order: 1 đơn có 2 đánh giá cùng được đánh dấu mới nhất
    UPDATE dds.fact_review SET is_latest_review = TRUE WHERE order_id = '0035246a40f520710769010f752e7507';
END $$;
--   docker compose exec -e POSTGRES_DB=olist_dw_demo mage dbt test
--   Mong đợi: Done. PASS=148 WARN=0 ERROR=7 SKIP=0 TOTAL=155
SELECT * FROM dq.unique_dim_customer_customer_unique_id;                            -- B1: b1a66210... | 2
SELECT * FROM dq.relationships_fact_sales_453d5d0845fe574c1a4bcd36495308f1;         -- B2: 99999
SELECT * FROM dq.dbt_utils_unique_combination_o_e3c08a3609b9b9d32910837d75bc47ed;   -- B3: khóa của đơn 82a35d13
SELECT * FROM dq.assert_facts_match_sources;                                        -- B3: 112102 / 112101; 13494600.64 / 13494400.74
SELECT * FROM dq.dbt_utils_expression_is_true_f_710c1fe5297dcd1402d4148a2474fc6c;   -- B4: quantity 2, unit_price 23.90, revenue 43.80
SELECT * FROM dq.assert_dim_unknown_members;                                        -- B5: dim_geography | 0
SELECT * FROM dq.assert_one_latest_review_per_order;                                -- B6: 0035246a... | 2
--   Sửa: dbt build bình thường CHƯA đủ -> Done. PASS=114 WARN=0 ERROR=2 SKIP=61 TOTAL=177
--     (dim_customer đọc lại chính bảng cũ để giữ khóa nên chép lại dòng trùng B1; dòng -1 chỉ thêm ở lần chạy đầu;
--      2 test này chặn dựng 3 fact nên B2, B3, B4, B6 còn nguyên)
--   Phải dựng lại từ đầu: docker compose exec -e POSTGRES_DB=olist_dw_demo mage dbt build --full-refresh
--     -> Done. PASS=177 WARN=0 ERROR=0 SKIP=0 TOTAL=177


-- =====================================================================
-- 4. KỊCH BẢN 4 - XÓA MỀM 1 ĐƠN (dbt_rules.md B7)
-- =====================================================================
--   Trước: fact_sales 101953, fact_delivery 100010, fact_review 100568; khách 871766c5... "Mua một lần"
DO $$
BEGIN
    IF current_database() <> 'olist_dw_demo' THEN
        RAISE EXCEPTION 'Chỉ chạy trên bản sao olist_dw_demo (đang ở %)', current_database();
    END IF;
    UPDATE staging.orders SET _is_deleted = TRUE, _deleted_at = '2018-03-15 10:00:00'
     WHERE order_id = '00010242fe8c5a6d1ba2dd792cb16214';
END $$;
--   a) Chưa dựng lại: docker compose exec -e POSTGRES_DB=olist_dw_demo mage dbt test --select assert_no_deleted_orders_in_facts
--      Mong đợi: FAIL 3 (đơn còn trong fact_sales, fact_delivery, fact_review)
SELECT * FROM dq.assert_no_deleted_orders_in_facts;
--   b) docker compose exec -e POSTGRES_DB=olist_dw_demo mage dbt build -> PASS=177
SELECT (SELECT count(*) FROM dds.fact_sales)    AS fact_sales,       -- 101952
       (SELECT count(*) FROM dds.fact_delivery) AS fact_delivery,    -- 100009
       (SELECT count(*) FROM dds.fact_review)   AS fact_review;      -- 100567
SELECT customer_key, customer_type, purchase_count                  -- khóa giữ nguyên, 'Chưa có đơn hợp lệ', 0
FROM dds.dim_customer WHERE customer_unique_id = '871766c5855e863f6eccc05f988b23cb';
--   c) Khôi phục rồi dbt build -> số liệu trở lại như "Trước"
DO $$
BEGIN
    IF current_database() <> 'olist_dw_demo' THEN
        RAISE EXCEPTION 'Chỉ chạy trên bản sao olist_dw_demo (đang ở %)', current_database();
    END IF;
    UPDATE staging.orders SET _is_deleted = FALSE, _deleted_at = NULL
     WHERE order_id = '00010242fe8c5a6d1ba2dd792cb16214';
END $$;


-- =====================================================================
-- 5. DỌN DẸP - xóa bản sao (ngắt kết nối DBeaver tới olist_dw_demo trước)
--   docker compose exec postgres psql -U olist_user -d postgres -c "DROP DATABASE IF EXISTS olist_dw_demo;"
-- =====================================================================
