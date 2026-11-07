-- =====================================================================
-- 06_etl_monitor.sql - View phục vụ dashboard theo dõi ETL (BS-54, Seminar 3)
--
--   Chỉ TẠO VIEW trong schema etl_log, KHÔNG tạo bảng mới, KHÔNG sửa bảng cũ - số liệu vẫn
--   là của 4 bảng log (pipeline_run, table_load, quality_check, dbt_result) và dq.rejected_rows.
--   Dùng chung cho: app Streamlit monitor/ (trang Tổng quan / Chất lượng / Chi tiết lần chạy),
--   DBeaver, và phần AI giải thích ETL về sau (đọc v_run là có đủ bức tranh 1 lần chạy).
--
--   etl_log.v_run             1 dòng = 1 lần chạy pipeline, kèm tổng hợp từ table_load / quality_check /
--                             dbt_result / dq.rejected_rows, số lượt nạp, số lần thử, thời gian từng khâu
--   etl_log.v_batch_progress  1 dòng = 1 batch x 1 lượt nạp (10 batch chuẩn x mọi lượt): đã nạp chưa, thử mấy lần
--   etl_log.v_quality_issue   mọi phép kiểm tra WARN / FAIL của Mage + mọi dbt test không đạt
--
--   * Giờ trong view là GIỜ VIỆT NAM (cột log đã lưu giờ VN, xem 00_schemas.sql) - không cộng thêm 7 giờ.
--   * "Lượt nạp" (cycle_no): mỗi lần chạy Full Load mở một lượt mới (TRUNCATE staging, nạp lại từ đầu);
--     trong một lượt, 10 batch FULL, 2018-01 ... 2018-08, 2018-09+ được nạp lần lượt.
--     CHỈ tính là mở lượt mới khi Full Load có ít nhất 1 bảng table_load = SUCCESS (đã commit). Full Load lỗi
--     ở khâu nạp staging bị hoàn tác (rollback) nên staging vẫn thuộc lượt cũ -> lần chạy lỗi đó nằm ở lượt cũ.
--     Hạn chế còn lại: Full Load ĐANG CHẠY (chưa commit, vài giây đầu) cũng được xếp vào lượt cũ cho tới khi
--     có bảng đầu tiên SUCCESS; attempt_no đếm cả lần Full Load lỗi đã rollback đó là 1 lần thử của batch FULL.
--   * Số dòng: rows_inserted / rows_updated / rows_deleted = số ĐÃ COMMIT vào staging (chỉ tính table_load SUCCESS).
--     Lần chạy lỗi ở khâu nạp bị rollback cả batch: số đã xử lý nhưng hoàn tác nằm ở rows_*_rollback.
--     rows_source = số dòng đọc từ file (mọi bảng, kể cả bị hoàn tác). rows_rejected = số dòng dq.rejected_rows
--     của lần chạy (đếm thẳng, gồm cả dòng bị loại của file deleted_orders mà table_load không đếm).
--   * Thời gian một lần chạy = [Mage khởi động + nạp staging] -> dbt khởi động / parse -> dbt build -> ghi log:
--     staging_s (từ bảng đầu tới bảng cuối), dbt_prep_s (từ bảng staging cuối tới node dbt đầu, ~17-20 giây),
--     dbt_s (node dbt đầu tới node cuối), mage_s = phần còn lại (khởi động block, ghi log).
--   * Trạng thái dbt lạ (ngoài success / pass / warn / skipped) được tính là LỖI.
--   * Lần chạy theo lịch khi đã nạp hết batch KHÔNG ghi vào etl_log (decisions.md 05/11/2026)
--     nên không có trong các view này.
--   * CREATE OR REPLACE VIEW: chạy lại nhiều lần vẫn an toàn.
--     DB mới: tự chạy sau 00 - 05. DB đã có: chạy tay (từ PowerShell, hoặc Git Bash đặt MSYS_NO_PATHCONV=1)
--       docker compose exec postgres psql -U olist_user -d olist_dw -f /sql/init/06_etl_monitor.sql
--     File tự DROP VIEW v_run / v_batch_progress trước khi tạo lại (đổi danh sách cột view thì CREATE OR REPLACE không đủ);
--     không ảnh hưởng dữ liệu vì view không lưu gì.
--     DROP cố ý KHÔNG dùng CASCADE để không âm thầm xóa view của người khác: nếu có view khác dựa trên v_run hoặc
--     v_batch_progress thì DROP báo lỗi và file dừng - khi đó tự DROP view đó (hoặc DROP ... CASCADE) rồi chạy file này,
--     sau đó TẠO LẠI view đó.
-- =====================================================================

DROP VIEW IF EXISTS etl_log.v_batch_progress;
DROP VIEW IF EXISTS etl_log.v_run;

-- ---------------------------------------------------------------------
-- 1. v_run - một dòng = một lần chạy
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW etl_log.v_run AS
WITH tl AS (            -- nạp staging: tổng hợp table_load
    SELECT t.run_id,
           count(*)                                      AS n_bang,
           count(*) FILTER (WHERE t.status = 'FAILED')   AS n_bang_loi,
           count(*) FILTER (WHERE t.status = 'SUCCESS')  AS n_bang_ok,
           count(*) FILTER (WHERE t.status = 'RUNNING')  AS n_bang_dang,
           COALESCE(sum(t.rows_source), 0)               AS rows_source,
           -- đã commit vào staging = table_load SUCCESS
           COALESCE(sum(t.rows_inserted) FILTER (WHERE t.status = 'SUCCESS'), 0) AS rows_inserted,
           COALESCE(sum(t.rows_updated)  FILTER (WHERE t.status = 'SUCCESS'), 0) AS rows_updated,
           COALESCE(sum(t.rows_deleted)  FILTER (WHERE t.status = 'SUCCESS'), 0) AS rows_deleted,
           -- đã xử lý nhưng bị hoàn tác (batch lỗi): KHÔNG nằm trong staging
           COALESCE(sum(t.rows_inserted) FILTER (WHERE t.status = 'FAILED'), 0)  AS rows_inserted_rollback,
           COALESCE(sum(t.rows_updated)  FILTER (WHERE t.status = 'FAILED'), 0)  AS rows_updated_rollback,
           min(t.started_at)                             AS t_dau,
           -- đang nạp dở: bảng chưa xong tính tới bây giờ
           max(COALESCE(t.finished_at, CASE WHEN r.status = 'RUNNING' THEN localtimestamp END)) AS t_cuoi
    FROM etl_log.table_load t
    JOIN etl_log.pipeline_run r ON r.run_id = t.run_id
    GROUP BY t.run_id
), dq AS (              -- dòng bị loại: đếm thẳng dq.rejected_rows
    SELECT run_id, count(*) AS rows_rejected
    FROM dq.rejected_rows
    GROUP BY run_id
), qc AS (              -- kiểm tra chất lượng của Mage
    SELECT run_id,
           count(*)                                 AS n_check,
           count(*) FILTER (WHERE status = 'PASS')  AS n_check_pass,
           count(*) FILTER (WHERE status = 'WARN')  AS n_check_warn,
           count(*) FILTER (WHERE status = 'FAIL')  AS n_check_fail
    FROM etl_log.quality_check
    GROUP BY run_id
), db AS (              -- khâu dbt. Trạng thái lạ (ngoài success / pass / warn / skipped) = lỗi
    SELECT run_id,
           count(*)                                                                     AS dbt_n_node,
           count(*) FILTER (WHERE status IN ('success', 'pass'))                        AS dbt_n_ok,
           count(*) FILTER (WHERE status = 'warn')                                      AS dbt_n_warn,
           count(*) FILTER (WHERE status NOT IN ('success', 'pass', 'warn', 'skipped')) AS dbt_n_fail,
           count(*) FILTER (WHERE status = 'skipped')                                   AS dbt_n_skipped,
           count(*) FILTER (WHERE resource_type = 'test'
                              AND status NOT IN ('success', 'pass', 'warn', 'skipped')) AS dbt_test_fail,
           count(*) FILTER (WHERE resource_type = 'test' AND status = 'warn')           AS dbt_test_warn,
           count(*) FILTER (WHERE resource_type = 'model'
                              AND status NOT IN ('success', 'pass', 'warn', 'skipped')) AS dbt_model_error,
           min(started_at)                                                              AS t_dau,
           max(finished_at)                                                             AS t_cuoi
    FROM etl_log.dbt_result
    GROUP BY run_id
), moi AS (             -- Full Load có ít nhất 1 bảng đã commit = mở lượt nạp mới
    SELECT r.*,
           (r.load_type = 'FULL'
            AND EXISTS (SELECT 1 FROM etl_log.table_load t WHERE t.run_id = r.run_id AND t.status = 'SUCCESS'))::int AS mo_luot
    FROM etl_log.pipeline_run r
), base AS (
    SELECT m.*,
           sum(m.mo_luot) OVER (ORDER BY m.run_id)                                                AS cycle_no,
           m.started_at - lag(m.started_at) OVER (PARTITION BY m.pipeline_name ORDER BY m.run_id) AS gap_prev
    FROM moi m
)
SELECT b.run_id,
       b.pipeline_name,
       b.load_type,
       b.batch_id,
       b.lset,
       b.cet,
       b.triggered_by,
       b.started_at,
       b.finished_at,
       b.status,
       b.error_message,
       -- lượt nạp + lần thử
       b.cycle_no::int                                                             AS cycle_no,
       (row_number() OVER (PARTITION BY b.cycle_no, b.batch_id ORDER BY b.run_id))::int AS attempt_no,
       -- thời gian (giây). duration_s = NULL khi đang chạy; elapsed_s = đã chạy bao lâu tính tới bây giờ
       round(EXTRACT(EPOCH FROM (b.finished_at - b.started_at))::numeric, 1)       AS duration_s,
       round(EXTRACT(EPOCH FROM (COALESCE(b.finished_at, localtimestamp) - b.started_at))::numeric, 1) AS elapsed_s,
       round(EXTRACT(EPOCH FROM (tl.t_cuoi - tl.t_dau))::numeric, 1)               AS staging_s,
       round(EXTRACT(EPOCH FROM (db.t_dau - tl.t_cuoi))::numeric, 1)               AS dbt_prep_s,
       round(EXTRACT(EPOCH FROM (db.t_cuoi - db.t_dau))::numeric, 1)               AS dbt_s,
       -- phần còn lại: Mage khởi động block + ghi log
       round(GREATEST(EXTRACT(EPOCH FROM (COALESCE(b.finished_at, localtimestamp) - b.started_at))
                      - COALESCE(EXTRACT(EPOCH FROM (tl.t_cuoi - tl.t_dau)), 0)
                      - COALESCE(EXTRACT(EPOCH FROM (db.t_dau - tl.t_cuoi)), 0)
                      - COALESCE(EXTRACT(EPOCH FROM (db.t_cuoi - db.t_dau)), 0), 0)::numeric, 1) AS mage_s,
       round(EXTRACT(EPOCH FROM b.gap_prev)::numeric, 0)                           AS gap_from_prev_s,
       -- đang chạy mà quá 15 phút = nghi kẹt (một lần chạy bình thường 40 - 70 giây)
       (b.status = 'RUNNING' AND localtimestamp - b.started_at > interval '15 minutes') AS is_stuck,
       -- đang chạy ở khâu nào: staging (chưa có bảng nào / đang nạp) -> dbt (staging xong, chưa có kết quả dbt)
       CASE WHEN b.status <> 'RUNNING' THEN NULL
            WHEN COALESCE(tl.n_bang, 0) = 0 OR COALESCE(tl.n_bang_dang, 0) > 0 THEN 'staging'
            WHEN db.run_id IS NULL THEN 'dbt'
            ELSE 'ghi_log' END                                                     AS phase,
       -- lần FAILED thuộc khâu nào (bị ngắt xét trước vì lúc ngắt Mage cũng đánh dấu table_load FAILED)
       CASE WHEN b.status <> 'FAILED' THEN NULL
            WHEN b.error_message LIKE 'Bị ngắt giữa chừng%'   THEN 'bi_ngat'
            WHEN b.error_message LIKE 'dbt build%'            THEN 'dbt'
            WHEN COALESCE(tl.n_bang_loi, 0) > 0 OR COALESCE(qc.n_check_fail, 0) > 0 THEN 'staging'
            ELSE 'khac' END                                                        AS failed_stage,
       -- nạp staging
       COALESCE(tl.n_bang, 0)::int                    AS n_bang,
       COALESCE(tl.n_bang_loi, 0)::int                AS n_bang_loi,
       COALESCE(tl.rows_source, 0)::bigint            AS rows_source,
       COALESCE(tl.rows_inserted, 0)::bigint          AS rows_inserted,
       COALESCE(tl.rows_updated, 0)::bigint           AS rows_updated,
       COALESCE(dq.rows_rejected, 0)::bigint          AS rows_rejected,
       COALESCE(tl.rows_deleted, 0)::bigint           AS rows_deleted,
       COALESCE(tl.rows_inserted_rollback, 0)::bigint AS rows_inserted_rollback,
       COALESCE(tl.rows_updated_rollback, 0)::bigint  AS rows_updated_rollback,
       -- kiểm tra chất lượng
       COALESCE(qc.n_check, 0)::int           AS n_check,
       COALESCE(qc.n_check_pass, 0)::int      AS n_check_pass,
       COALESCE(qc.n_check_warn, 0)::int      AS n_check_warn,
       COALESCE(qc.n_check_fail, 0)::int      AS n_check_fail,
       -- dbt
       COALESCE(db.dbt_n_node, 0)::int        AS dbt_n_node,
       COALESCE(db.dbt_n_ok, 0)::int          AS dbt_n_ok,
       COALESCE(db.dbt_n_warn, 0)::int        AS dbt_n_warn,
       COALESCE(db.dbt_n_fail, 0)::int        AS dbt_n_fail,
       COALESCE(db.dbt_n_skipped, 0)::int     AS dbt_n_skipped,
       COALESCE(db.dbt_test_fail, 0)::int     AS dbt_test_fail,
       COALESCE(db.dbt_test_warn, 0)::int     AS dbt_test_warn,
       COALESCE(db.dbt_model_error, 0)::int   AS dbt_model_error
FROM base b
LEFT JOIN tl ON tl.run_id = b.run_id
LEFT JOIN dq ON dq.run_id = b.run_id
LEFT JOIN qc ON qc.run_id = b.run_id
LEFT JOIN db ON db.run_id = b.run_id;

COMMENT ON VIEW etl_log.v_run IS
    '1 dòng = 1 lần chạy pipeline + tổng hợp table_load / quality_check / dbt_result / dq.rejected_rows. Dùng cho dashboard theo dõi ETL (monitor/).';
COMMENT ON COLUMN etl_log.v_run.cycle_no IS 'Lượt nạp: mỗi Full Load có >= 1 bảng commit mở lượt mới (0 = trước Full Load đầu tiên)';
COMMENT ON COLUMN etl_log.v_run.attempt_no IS 'Lần thử thứ mấy của cùng batch trong cùng lượt nạp (chạy lại sau lỗi thì tăng)';
COMMENT ON COLUMN etl_log.v_run.rows_inserted IS 'Số dòng INSERT ĐÃ COMMIT vào staging (table_load SUCCESS); batch lỗi bị rollback thì 0';
COMMENT ON COLUMN etl_log.v_run.rows_inserted_rollback IS 'Số dòng INSERT đã xử lý nhưng bị hoàn tác (table_load FAILED) - không nằm trong staging';
COMMENT ON COLUMN etl_log.v_run.rows_rejected IS 'Số dòng của lần chạy trong dq.rejected_rows (đếm thẳng, gồm cả file deleted_orders)';
COMMENT ON COLUMN etl_log.v_run.staging_s IS 'Giây từ lúc bắt đầu nạp bảng đầu tiên tới lúc xong bảng cuối (đang nạp dở: tới bây giờ)';
COMMENT ON COLUMN etl_log.v_run.dbt_prep_s IS 'Giây từ lúc xong bảng staging cuối tới node dbt đầu tiên (dbt khởi động / parse project)';
COMMENT ON COLUMN etl_log.v_run.dbt_s IS 'Giây từ node dbt đầu tiên tới node cuối (khâu dbt build)';
COMMENT ON COLUMN etl_log.v_run.mage_s IS 'Phần còn lại của thời gian chạy: Mage khởi động block, ghi log';
COMMENT ON COLUMN etl_log.v_run.is_stuck IS 'TRUE = RUNNING quá 15 phút (nghi pipeline chết giữa chừng)';
COMMENT ON COLUMN etl_log.v_run.phase IS 'Chỉ có khi RUNNING: staging / dbt / ghi_log';
COMMENT ON COLUMN etl_log.v_run.failed_stage IS 'Chỉ có khi FAILED: bi_ngat / dbt / staging / khac';

-- ---------------------------------------------------------------------
-- 2. v_batch_progress - tiến độ 10 batch của MỖI lượt nạp (nguồn duy nhất cho lưới 10 ô và thẻ tiến độ)
--    Danh sách batch chép từ data/batches/manifest.csv (cột seq, batch_id); thêm batch thì sửa VALUES ở đây.
--    "Lượt mới nhất" = cycle_no lớn nhất. Chưa có lần chạy nào: trả 10 dòng của lượt 0 (đều PENDING).
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW etl_log.v_batch_progress AS
WITH manifest (seq, batch_id) AS (
    VALUES (1, 'FULL'), (2, '2018-01'), (3, '2018-02'), (4, '2018-03'), (5, '2018-04'),
           (6, '2018-05'), (7, '2018-06'), (8, '2018-07'), (9, '2018-08'), (10, '2018-09+')
), luot AS (
    SELECT DISTINCT cycle_no FROM etl_log.v_run
    UNION
    SELECT 0 WHERE NOT EXISTS (SELECT 1 FROM etl_log.v_run)
), tong AS (
    SELECT cycle_no, batch_id,
           count(*)::int                                   AS so_lan_thu,
           (count(*) FILTER (WHERE status = 'FAILED'))::int AS so_lan_failed,
           max(run_id)                                     AS run_id_cuoi,
           max(run_id) FILTER (WHERE status = 'SUCCESS')   AS run_id_success
    FROM etl_log.v_run
    GROUP BY cycle_no, batch_id
)
SELECT m.seq,
       m.batch_id,
       l.cycle_no,
       COALESCE(t.so_lan_thu, 0)                            AS so_lan_thu,
       COALESCE(t.so_lan_failed, 0)                         AS so_lan_failed,
       (t.run_id_success IS NOT NULL)                       AS da_nap,
       COALESCE(rc.status, 'PENDING')                       AS trang_thai_cuoi,   -- trạng thái lần chạy gần nhất; PENDING = chưa chạy
       t.run_id_success,
       t.run_id_cuoi,
       rs.finished_at                                       AS xong_luc,          -- giờ xong lần SUCCESS gần nhất
       rs.triggered_by                                      AS kich_hoat,
       rs.lset,
       rs.cet
FROM luot l
CROSS JOIN manifest m
LEFT JOIN tong t ON t.cycle_no = l.cycle_no AND t.batch_id = m.batch_id
LEFT JOIN etl_log.v_run rc ON rc.run_id = t.run_id_cuoi
LEFT JOIN etl_log.v_run rs ON rs.run_id = t.run_id_success
ORDER BY l.cycle_no, m.seq;

COMMENT ON VIEW etl_log.v_batch_progress IS
    '10 batch chuẩn (data/batches/manifest.csv) x mọi lượt nạp: đã nạp chưa, thử mấy lần, lúc xong. Lượt mới nhất = cycle_no lớn nhất.';

-- ---------------------------------------------------------------------
-- 3. v_quality_issue - mọi điểm chất lượng "không sạch"
--    nguon = mage: phép kiểm tra WARN / FAIL trước khi nạp staging (failed_rows = số dòng bị loại, nội dung ở dq.rejected_rows)
--    nguon = dbt : test không đạt - fail / error / warn / trạng thái lạ (failed_rows = số dòng vi phạm,
--                  bảng chứa dòng đó ở dq_table)
-- ---------------------------------------------------------------------
CREATE OR REPLACE VIEW etl_log.v_quality_issue AS
SELECT q.run_id,
       r.batch_id,
       r.triggered_by,
       r.started_at,
       'mage'::text                 AS nguon,
       q.table_name,
       q.check_name,
       q.status,
       q.failed_rows::bigint        AS failed_rows,
       q.detail,
       NULL::text                   AS dq_table,
       q.checked_at                 AS luc_ghi
FROM etl_log.quality_check q
JOIN etl_log.pipeline_run r ON r.run_id = q.run_id
WHERE q.status <> 'PASS'
UNION ALL
SELECT d.run_id,
       r.batch_id,
       r.triggered_by,
       r.started_at,
       'dbt'::text,
       NULL::text,
       d.node_name,
       upper(d.status),
       d.failures::bigint,
       d.message,
       d.relation_name,
       COALESCE(d.finished_at, r.started_at)
FROM etl_log.dbt_result d
JOIN etl_log.pipeline_run r ON r.run_id = d.run_id
WHERE d.resource_type = 'test' AND d.status NOT IN ('pass', 'success', 'skipped');

COMMENT ON VIEW etl_log.v_quality_issue IS
    'Phép kiểm tra WARN / FAIL của Mage + dbt test không đạt (fail / error / warn / trạng thái lạ), kèm batch và cách kích hoạt của lần chạy.';
