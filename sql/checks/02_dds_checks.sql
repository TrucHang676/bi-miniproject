-- =====================================================================
-- 02_dds_checks.sql - Đối soát kho dds sau khi chạy dbt (docs/dbt_rules.md B6, B7)
--   Dùng khi kiểm thử, khi chụp ảnh cho báo cáo mục 6.2 và khi demo.
--   DBeaver: đặt con trỏ vào 1 câu -> Ctrl + Enter.
--   Số "mong đợi" ghi trong mỗi câu là số khi staging đã nạp đủ 10 batch và CHƯA xóa đơn nào
--   (đã kiểm chứng trên CSV gốc và trên kết quả dbt build ngày 24/10/2026).
--   Sau khi demo xóa đơn, các tổng sẽ giảm theo -> đó là kết quả đúng, không phải lỗi.
-- =====================================================================

-- Q1. Số dòng 9 bảng trong dds (dim có thêm 1 dòng -1 "Không xác định", trừ dim_date và dim_delivery_status)
SELECT 'dim_date' AS bang, count(*) AS so_dong, 1096 AS mong_doi FROM dds.dim_date
UNION ALL SELECT 'dim_delivery_status', count(*), 672    FROM dds.dim_delivery_status
UNION ALL SELECT 'dim_customer',        count(*), 96097  FROM dds.dim_customer
UNION ALL SELECT 'dim_geography',       count(*), 4310   FROM dds.dim_geography
UNION ALL SELECT 'dim_product',         count(*), 32952  FROM dds.dim_product
UNION ALL SELECT 'dim_seller',          count(*), 3096   FROM dds.dim_seller
UNION ALL SELECT 'fact_sales',          count(*), 101953 FROM dds.fact_sales
UNION ALL SELECT 'fact_delivery',       count(*), 100010 FROM dds.fact_delivery
UNION ALL SELECT 'fact_review',         count(*), 100568 FROM dds.fact_review;

-- Q2. Bán hàng: số lượng, doanh thu (K1), phí vận chuyển
--   Mong đợi: quantity 112.101 (7.049 dòng > 1) · doanh thu cả kỳ 13.494.400,74 · 01/2017-08/2018: 13.449.529,68
--             · phí vận chuyển 2.241.126,29 BRL · số đơn (K2) cả kỳ 98.199
SELECT
    sum(f.quantity)                                    AS tong_so_luong,
    count(*) FILTER (WHERE f.quantity > 1)             AS so_dong_quantity_lon_hon_1,
    sum(f.revenue)                                     AS doanh_thu_ca_ky,
    sum(f.revenue) FILTER (WHERE d.is_analysis_period) AS doanh_thu_01_2017_08_2018,
    sum(f.freight_value)                               AS phi_van_chuyen,
    count(DISTINCT f.order_id)                         AS so_don_hop_le
FROM dds.fact_sales AS f
JOIN dds.dim_date AS d ON d.date_key = f.purchase_date_key;

-- Q3. Doanh thu theo tháng (Q1 của dashboard) - kiểm tra nhanh trước khi dựng biểu đồ Power BI
--   Mong đợi: tháng cao nhất 11/2017
SELECT d.year_month, count(DISTINCT f.order_id) AS so_don, sum(f.revenue) AS doanh_thu,
       round(sum(f.revenue) / count(DISTINCT f.order_id), 2) AS aov
FROM dds.fact_sales AS f
JOIN dds.dim_date AS d ON d.date_key = f.purchase_date_key
WHERE d.is_analysis_period
GROUP BY d.year_month
ORDER BY d.year_month;

-- Q4. Giao hàng: K6 tỉ lệ giao trễ (đếm THEO ĐƠN) và K12 tỉ lệ bàn giao trễ (đếm THEO DÒNG)
--   Mong đợi: K6 = 6.534 / 96.470 = 6,77% · K12 = 8.913 / 98.824 = 9,02% · 98.666 đơn · 47 tổ hợp trạng thái
SELECT
    count(DISTINCT f.order_id) FILTER (WHERE s.delivery_result = 'Trễ hạn')                AS don_tre,
    count(DISTINCT f.order_id) FILTER (WHERE s.delivery_result IN ('Đúng hạn', 'Trễ hạn')) AS don_da_giao,
    round(100.0 * count(DISTINCT f.order_id) FILTER (WHERE s.delivery_result = 'Trễ hạn')
        / count(DISTINCT f.order_id) FILTER (WHERE s.delivery_result IN ('Đúng hạn', 'Trễ hạn')), 2) AS k6_pct,
    count(*) FILTER (WHERE s.handover_status = 'Trễ hạn')                                   AS luot_ban_giao_tre,
    count(*) FILTER (WHERE s.handover_status IN ('Đúng hạn', 'Trễ hạn'))                    AS luot_co_ngay_ban_giao,
    round(100.0 * count(*) FILTER (WHERE s.handover_status = 'Trễ hạn')
        / count(*) FILTER (WHERE s.handover_status IN ('Đúng hạn', 'Trễ hạn')), 2)          AS k12_pct,
    count(DISTINCT f.order_id)                                                              AS so_don,
    count(DISTINCT f.delivery_status_key)                                                   AS so_to_hop_trang_thai
FROM dds.fact_delivery AS f
JOIN dds.dim_delivery_status AS s ON s.delivery_status_key = f.delivery_status_key;

-- Q5. Phân bố trạng thái bàn giao và tuyến giao (theo dòng)
--   Mong đợi: Đúng hạn 89.911 · Trễ hạn 8.913 · Chưa bàn giao 1.010 · Không xác định 176
--             Liên bang 64.049 · Nội bang 35.961
SELECT 'handover_status' AS thuoc_tinh, s.handover_status AS gia_tri, count(*) AS so_dong
FROM dds.fact_delivery AS f JOIN dds.dim_delivery_status AS s USING (delivery_status_key)
GROUP BY s.handover_status
UNION ALL
SELECT 'route_type', s.route_type, count(*)
FROM dds.fact_delivery AS f JOIN dds.dim_delivery_status AS s USING (delivery_status_key)
GROUP BY s.route_type
ORDER BY 1, 3 DESC;

-- Q6. Đánh giá: K8 điểm trung bình, K9 tỉ lệ 1-2 sao (1 điểm / đơn: lọc is_latest_review, bỏ trùng theo người bán)
--   Mong đợi: 98.673 đơn có đánh giá · 759 dòng seller_key = -1 · 99.224 lượt (review_id, order_id)
--             K8 = 4,09 · K9 = 14,69% (cả kỳ), 14,63% (01/2017-08/2018)
WITH one_per_order AS (
    SELECT DISTINCT order_id, review_id, review_score, purchase_date_key
    FROM dds.fact_review
    WHERE is_latest_review
)
SELECT
    count(*)                                                                 AS so_don_co_danh_gia,
    round(avg(review_score), 2)                                              AS k8_diem_tb,
    round(100.0 * count(*) FILTER (WHERE review_score <= 2) / count(*), 2)   AS k9_pct_tieu_cuc,
    (SELECT count(*) FROM dds.fact_review WHERE seller_key = -1)             AS dong_khong_co_nguoi_ban,
    (SELECT count(*) FROM (SELECT DISTINCT review_id, order_id FROM dds.fact_review) AS x) AS so_luot_danh_gia
FROM one_per_order;

-- Q7. Khách hàng: loại khách và K5 tỉ lệ mua lại
--   Mong đợi: Mua một lần 92.827 · Mua lại 2.156 · Chưa có đơn hợp lệ 1.113 · Không xác định 1 (dòng -1)
--             K5 cả kỳ = 2,27% (tính theo đơn hợp lệ, gộp đơn cách nhau <= 10 phút)
SELECT customer_type, count(*) AS so_khach
FROM dds.dim_customer
GROUP BY customer_type
ORDER BY so_khach DESC;

SELECT round(100.0 * count(*) FILTER (WHERE so_lan_mua >= 2) / count(*), 2) AS k5_pct_mua_lai
FROM (SELECT customer_key, count(DISTINCT purchase_seq) AS so_lan_mua FROM dds.fact_sales GROUP BY customer_key) AS x;

-- Q8. Fact không được trỏ vào dòng -1 ở khách / địa lý / sản phẩm (dữ liệu thật tra khớp 100%)
--   Mong đợi: 0 · 0 · 0 (riêng fact_review có 759 dòng seller_key = -1 - đơn không có sản phẩm, là đúng)
SELECT
    (SELECT count(*) FROM dds.fact_sales    WHERE customer_key = -1 OR geography_key = -1 OR product_key = -1 OR seller_key = -1) AS fact_sales_dong_am_1,
    (SELECT count(*) FROM dds.fact_delivery WHERE customer_key = -1 OR geography_key = -1 OR seller_key = -1)                     AS fact_delivery_dong_am_1,
    (SELECT count(*) FROM dds.fact_review   WHERE customer_key = -1 OR geography_key = -1)                                        AS fact_review_dong_am_1;

-- Q9. Demo xóa mềm (dbt_rules.md B7 kịch bản 4) - chạy từng bước, NHỚ chạy bước khôi phục khi demo xong
--   Bước 1: đánh dấu xóa 1 đơn (đơn này của khách chỉ có 1 đơn)
--     UPDATE staging.orders SET _is_deleted = TRUE, _deleted_at = now() WHERE order_id = '00010242fe8c5a6d1ba2dd792cb16214';
--   Bước 2: chạy dbt                    docker compose exec mage dbt build
--   Bước 3: xem kết quả - đơn phải biến mất khỏi 3 fact (0 · 0 · 0), mỗi fact giảm 1 dòng;
--           khách vẫn còn trong dim_customer, cùng customer_key, customer_type = 'Chưa có đơn hợp lệ'
SELECT
    (SELECT count(*) FROM dds.fact_sales    WHERE order_id = '00010242fe8c5a6d1ba2dd792cb16214') AS trong_fact_sales,
    (SELECT count(*) FROM dds.fact_delivery WHERE order_id = '00010242fe8c5a6d1ba2dd792cb16214') AS trong_fact_delivery,
    (SELECT count(*) FROM dds.fact_review   WHERE order_id = '00010242fe8c5a6d1ba2dd792cb16214') AS trong_fact_review;
--   Bước 4 (khôi phục): UPDATE staging.orders SET _is_deleted = FALSE, _deleted_at = NULL
--                       WHERE order_id = '00010242fe8c5a6d1ba2dd792cb16214';
--                       rồi chạy lại docker compose exec mage dbt build
