-- =====================================================================
-- 05_dbt_log.sql - Nhật ký bước dbt trong pipeline Mage (BS-34, chốt 24/10/2026)
--
--   Từ BS-34, mỗi lần chạy pipeline Mage gồm 2 khâu: nạp staging (Stage ETL) rồi gọi
--   dbt build dựng dds (DDS ETL + DQ). Bảng dưới ghi kết quả khâu dbt, cùng run_id với
--   3 bảng ở 02_etl_log.sql:
--
--   pipeline_run   1 dòng = 1 lần chạy pipeline
--        │ 1──n
--   dbt_result     1 dòng = 1 node dbt (seed / model / test) trong 1 lần chạy
--
--   * Mage đọc dbt/target/run_results.json ngay sau khi dbt build xong rồi ghi vào đây
--     (mage/olist_etl/utils/dbt_runner.py). dbt không chạy được (VD thiếu profiles.yml) thì
--     không có dòng nào - lý do nằm ở pipeline_run.error_message.
--   * Không ghi chung vào table_load / quality_check: 2 bảng đó mô tả việc nạp staging từ file
--     (rows_inserted / rows_updated, PASS / WARN / FAIL do Mage đặt), còn dbt có trạng thái riêng.
--   * DB mới: tự chạy sau 00 - 04. DB đã có: chạy tay file này (setup_guide.md mục 5.2).
--     Chạy lại nhiều lần vẫn an toàn (IF NOT EXISTS), không xóa log có sẵn.
-- =====================================================================

-- status giữ đúng chữ của dbt (viết thường) và không đặt CHECK: tập giá trị do dbt quy định,
-- bản dbt sau có thể thêm giá trị mới - không để việc ghi log làm hỏng cả lần chạy.
CREATE TABLE IF NOT EXISTS etl_log.dbt_result (
    run_id          BIGINT         NOT NULL,
    unique_id       TEXT           NOT NULL,   -- mã node dbt, VD model.olist_dw.fact_sales; test có thêm mã hash ở cuối
    resource_type   VARCHAR(10)    NOT NULL,   -- seed / model / test
    node_name       TEXT           NOT NULL,   -- tên ngắn, VD fact_sales (tên test dài tới gần 200 ký tự)
    relation_name   TEXT,                      -- bảng / view dbt tạo, VD dds.fact_sales;
                                               -- test: bảng chứa dòng vi phạm trong dq (store_failures)
    status          VARCHAR(10)    NOT NULL,   -- seed, model: success / error / skipped
                                               -- test: pass / warn / fail / error / skipped
    rows_affected   INT,                       -- seed, model: số dòng Postgres báo (bảng table: số dòng của bảng;
                                               -- incremental: số dòng thêm / thay lần này); view: NULL
    failures        INT,                       -- test: số dòng vi phạm (0 = đạt)
    execution_time  NUMERIC(10,3),             -- số giây dbt chạy node này
    started_at      TIMESTAMP,                 -- giờ chạy thật (giờ Việt Nam); node bị bỏ qua (skipped): NULL
    finished_at     TIMESTAMP,
    message         TEXT,                      -- dbt báo, VD 'SELECT 101953', 'Got 1 result, configured to fail if != 0'
    CONSTRAINT pk_dbt_result PRIMARY KEY (run_id, unique_id),
    CONSTRAINT fk_dbt_result_run FOREIGN KEY (run_id)
        REFERENCES etl_log.pipeline_run (run_id) ON DELETE CASCADE
);
