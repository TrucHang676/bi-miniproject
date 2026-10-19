-- =====================================================================
-- 00_schemas.sql - Tạo schema và extension cho Data Warehouse olist_dw
-- Chạy lại nhiều lần vẫn an toàn (IF NOT EXISTS), không xóa dữ liệu có sẵn.
-- =====================================================================

-- Schema = một "khu" trong database, gom các bảng theo vai trò
CREATE SCHEMA IF NOT EXISTS staging;   -- dữ liệu thô Mage nạp từ CSV (giữ nguyên tên cột gốc)
CREATE SCHEMA IF NOT EXISTS etl_log;   -- nhật ký mỗi lần chạy pipeline (Control + Audit)
CREATE SCHEMA IF NOT EXISTS dq;        -- DQ database: chính các dòng dữ liệu lỗi (Mage loại + dbt test)
CREATE SCHEMA IF NOT EXISTS dds;       -- Dimensional Data Store: dim / fact do dbt tạo

-- unaccent: bỏ dấu tiếng Bồ Đào Nha ('são paulo' -> 'sao paulo'),
-- dùng trong macro dbt normalize_city (chuẩn hóa tên thành phố)
CREATE EXTENSION IF NOT EXISTS unaccent;

-- Múi giờ mặc định của DB = giờ Việt Nam (Postgres trong Docker mặc định UTC, chậm 7 tiếng)
-- -> now() trả giờ VN cho giờ chạy thật: etl_log.*.started_at / finished_at, staging.*._loaded_at.
-- Không ảnh hưởng dữ liệu Olist: cột TIMESTAMP (không múi giờ) không bị quy đổi.
-- Chỉ áp dụng cho kết nối MỚI (kết nối đang mở phải ngắt rồi nối lại).
DO $$
BEGIN
    EXECUTE format('ALTER DATABASE %I SET timezone TO %L', current_database(), 'Asia/Ho_Chi_Minh');
END $$;
