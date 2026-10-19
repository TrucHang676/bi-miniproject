-- =====================================================================
-- 03_dq.sql - DQ database: lưu CHÍNH CÁC DÒNG dữ liệu lỗi (chốt 19/10/2026)
--
--   Ứng với ô "DQ database" của kiến trúc Single DDS (bài giảng):
--   "stores the bad data detected by the data firewall".
--   etl_log chỉ ĐẾM số dòng lỗi (table_load.rows_rejected, quality_check.failed_rows);
--   dq giữ NGUYÊN NỘI DUNG dòng để người phụ trách xem, sửa nguồn rồi nạp lại.
--
--   Hai nguồn ghi vào schema dq:
--   * Mage : dòng bị loại TRƯỚC khi nạp staging -> bảng rejected_rows bên dưới
--            (dòng này không bao giờ vào staging nên dbt không thấy được).
--   * dbt  : dòng vi phạm dbt test -> dbt tự tạo bảng khi bật store_failures
--            (đặt +schema của tests trong dbt_project.yml; dbt ghi đè mỗi lần chạy).
--
--   Đối soát: etl_log.table_load.rows_rejected = số dòng rejected_rows cùng run_id + table_name.
--   Chạy sau 02_etl_log.sql (khóa ngoại trỏ về etl_log.quality_check).
--   Chạy lại nhiều lần vẫn an toàn (IF NOT EXISTS), không xóa dữ liệu có sẵn.
-- =====================================================================

-- 1 dòng = 1 dòng dữ liệu bị Mage loại trong 1 lần chạy.
-- Quy trình ghi: Mage ghi etl_log.quality_check (status WARN / FAIL, failed_rows) TRƯỚC,
-- rồi mới ghi các dòng bị loại của phép kiểm tra đó vào đây.
CREATE TABLE IF NOT EXISTS dq.rejected_rows (
    rejected_id  BIGINT       GENERATED ALWAYS AS IDENTITY,  -- tự tăng 1, 2, 3...
    run_id       BIGINT       NOT NULL,                      -- lần chạy nào (etl_log.pipeline_run)
    table_name   VARCHAR(30)  NOT NULL,                      -- bảng staging, VD orders
    check_name   VARCHAR(50)  NOT NULL,                      -- phép kiểm tra làm dòng bị loại, VD not_null_key
    source_row   INT,                                        -- bản ghi thứ mấy trong file batch (1 = bản ghi đầu sau tiêu đề);
                                                             -- không phải số dòng vật lý vì review có xuống dòng trong ô
    row_data     JSONB        NOT NULL,                      -- nguyên dòng gốc {"tên cột": "giá trị"}, giá trị để dạng chuỗi như trong file;
                                                             -- 8 bảng khác cột nên gói vào JSON để dùng chung 1 bảng
    reason       TEXT,                                       -- mô tả ngắn, VD 'order_id rỗng'
    rejected_at  TIMESTAMP    NOT NULL DEFAULT now(),
    CONSTRAINT pk_rejected_rows PRIMARY KEY (rejected_id),
    -- Mỗi dòng lỗi phải gắn với 1 phép kiểm tra CÓ THẬT trong etl_log -> 2 nơi không thể lệch nhau
    CONSTRAINT fk_rejected_rows_check FOREIGN KEY (run_id, table_name, check_name)
        REFERENCES etl_log.quality_check (run_id, table_name, check_name) ON DELETE CASCADE
);

-- Xem / đếm dòng lỗi theo lần chạy (đối soát với etl_log) nhanh hơn
CREATE INDEX IF NOT EXISTS ix_rejected_rows_check
    ON dq.rejected_rows (run_id, table_name, check_name);
