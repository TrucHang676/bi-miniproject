-- =====================================================================
-- 02_etl_log.sql - Sổ nhật ký ETL trong schema etl_log (3 bảng, chốt 18/10/2026)
--
--   pipeline_run   1 dòng = 1 lần chạy pipeline (Full Load / Incremental Load)
--        │ 1──n
--   table_load     1 dòng = 1 bảng staging được nạp trong 1 lần chạy
--   quality_check  1 dòng = 1 phép kiểm tra chất lượng trên 1 bảng trong 1 lần chạy
--
--   * Mage ghi vào đây; Incremental đọc lần chạy SUCCESS gần nhất để biết batch kế tiếp;
--     Seminar 3 dựng dashboard theo dõi ETL từ 3 bảng này.
--   * lset, cet = thời gian MÔ PHỎNG của dữ liệu (mốc cắt batch - D4, D8), KHÔNG phải giờ chạy.
--     started_at, finished_at = giờ chạy thật (giờ Việt Nam - xem 00_schemas.sql).
--   * Chạy lại nhiều lần vẫn an toàn (IF NOT EXISTS), không xóa log có sẵn.
-- =====================================================================

-- Lần chạy pipeline. Quy trình ghi: bắt đầu INSERT (status RUNNING) -> kết thúc UPDATE
-- status SUCCESS / FAILED + finished_at. Dòng kẹt ở RUNNING = pipeline chết giữa chừng.
CREATE TABLE IF NOT EXISTS etl_log.pipeline_run (
    run_id         BIGINT       GENERATED ALWAYS AS IDENTITY,  -- tự tăng 1, 2, 3...
    pipeline_name  VARCHAR(50)  NOT NULL,                      -- tên pipeline Mage
    load_type      VARCHAR(20)  NOT NULL,                      -- FULL / INCREMENTAL
    batch_id       VARCHAR(10)  NOT NULL,                      -- FULL, 2018-01 ... 2018-09+
    lset           TIMESTAMP,                                  -- đầu khoảng [LSET, CET); NULL = từ đầu dữ liệu
    cet            TIMESTAMP,                                  -- cuối khoảng; NULL = batch cuối, không cắt
    triggered_by   VARCHAR(10)  NOT NULL DEFAULT 'manual',     -- manual / schedule (lập lịch ở Seminar 3)
    started_at     TIMESTAMP    NOT NULL DEFAULT now(),
    finished_at    TIMESTAMP,                                  -- NULL khi đang chạy
    status         VARCHAR(10)  NOT NULL DEFAULT 'RUNNING',
    error_message  TEXT,
    CONSTRAINT pk_pipeline_run PRIMARY KEY (run_id),
    CONSTRAINT ck_pipeline_run_load_type    CHECK (load_type IN ('FULL', 'INCREMENTAL')),
    CONSTRAINT ck_pipeline_run_triggered_by CHECK (triggered_by IN ('manual', 'schedule')),
    CONSTRAINT ck_pipeline_run_status       CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED'))
);

-- Kết quả nạp từng bảng trong 1 lần chạy. Số INSERT / UPDATE lấy từ
-- MERGE ... RETURNING merge_action() (PostgreSQL 17 - D8).
CREATE TABLE IF NOT EXISTS etl_log.table_load (
    run_id         BIGINT       NOT NULL,
    table_name     VARCHAR(30)  NOT NULL,                      -- tên bảng staging, VD orders
    rows_source    INT,                                        -- số dòng đọc từ file batch
    rows_inserted  INT          NOT NULL DEFAULT 0,            -- dòng mới thêm vào staging
    rows_updated   INT          NOT NULL DEFAULT 0,            -- dòng đã có, được cập nhật
    rows_rejected  INT          NOT NULL DEFAULT 0,            -- dòng bị loại vì không qua kiểm tra chất lượng (nội dung dòng: dq.rejected_rows)
    started_at     TIMESTAMP    NOT NULL DEFAULT now(),
    finished_at    TIMESTAMP,
    status         VARCHAR(10)  NOT NULL DEFAULT 'RUNNING',
    error_message  TEXT,
    CONSTRAINT pk_table_load PRIMARY KEY (run_id, table_name),
    CONSTRAINT fk_table_load_run FOREIGN KEY (run_id)
        REFERENCES etl_log.pipeline_run (run_id) ON DELETE CASCADE,
    CONSTRAINT ck_table_load_status CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED'))
);

-- Kết quả từng phép kiểm tra chất lượng (VD đủ cột, khóa không NULL, khóa không trùng).
-- Khóa ngoại trỏ về pipeline_run (không phải table_load) để Mage ghi kết quả kiểm tra
-- được cả khi bảng chưa kịp nạp, VD file thiếu cột nên dừng trước bước MERGE.
CREATE TABLE IF NOT EXISTS etl_log.quality_check (
    run_id       BIGINT       NOT NULL,
    table_name   VARCHAR(30)  NOT NULL,
    check_name   VARCHAR(50)  NOT NULL,                        -- VD columns_match, not_null_key, duplicate_key
    failed_rows  INT          NOT NULL DEFAULT 0,              -- số dòng vi phạm (0 = đạt)
    status       VARCHAR(4)   NOT NULL,                        -- PASS / WARN / FAIL
    detail       TEXT,                                         -- mô tả ngắn, VD 'thiếu cột price'
    checked_at   TIMESTAMP    NOT NULL DEFAULT now(),
    CONSTRAINT pk_quality_check PRIMARY KEY (run_id, table_name, check_name),
    CONSTRAINT fk_quality_check_run FOREIGN KEY (run_id)
        REFERENCES etl_log.pipeline_run (run_id) ON DELETE CASCADE,
    CONSTRAINT ck_quality_check_status CHECK (status IN ('PASS', 'WARN', 'FAIL'))
);
