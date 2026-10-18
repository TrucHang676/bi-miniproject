-- =====================================================================
-- 00_schemas.sql - Tạo schema và extension cho Data Warehouse olist_dw
-- Chạy lại nhiều lần vẫn an toàn (IF NOT EXISTS), không xóa dữ liệu có sẵn.
-- =====================================================================

-- Schema = một "khu" trong database, gom các bảng theo vai trò
CREATE SCHEMA IF NOT EXISTS staging;   -- dữ liệu thô Mage nạp từ CSV (giữ nguyên tên cột gốc)
CREATE SCHEMA IF NOT EXISTS etl_log;   -- nhật ký mỗi lần chạy pipeline
CREATE SCHEMA IF NOT EXISTS dds;       -- Dimensional Data Store: dim / fact do dbt tạo

-- unaccent: bỏ dấu tiếng Bồ Đào Nha ('são paulo' -> 'sao paulo'),
-- dùng trong macro dbt normalize_city (chuẩn hóa tên thành phố)
CREATE EXTENSION IF NOT EXISTS unaccent;
