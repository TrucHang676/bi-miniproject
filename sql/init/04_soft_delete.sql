-- =====================================================================
-- 04_soft_delete.sql - Cơ chế xóa mềm (soft delete) đơn hàng bị xóa ở nguồn (chốt 19/10/2026)
--
--   Bài 4, slide 52-53 "How about deletion?": Incremental Load chỉ thấy dòng CÓ MẶT trong batch,
--   đơn bị xóa ở nguồn không gửi tới nên không tự phát hiện được; cũng không thể coi "vắng mặt
--   trong batch" là "bị xóa" vì mỗi batch chỉ là một phần dữ liệu (D4).
--   -> Nguồn BÁO XÓA bằng file deleted_orders.csv trong batch (định dạng: data/batches/README.md);
--      Mage KHÔNG xóa hẳn mà đánh dấu _is_deleted = TRUE (giữ dấu vết để đối soát);
--      dbt bỏ qua đơn đã đánh dấu khi dựng dds (R10 trong docs/source_to_target_mapping.md).
--   Quy tắc cho pipeline: docs/pipeline_rules.md mục "Xóa đơn".
--
--   Viết dạng ALTER ... ADD COLUMN IF NOT EXISTS để:
--   * DB mới: tự chạy sau 01, 02 (thứ tự tên file) -> cột nằm cuối bảng;
--   * DB đã có: chạy tay file này là đủ, không cần dựng lại DB -> cột cũng nằm cuối bảng,
--     mọi máy giống nhau. Chạy lại nhiều lần vẫn an toàn.
-- =====================================================================

-- Chỉ đánh dấu ở bảng orders: bảng con (order_items, order_payments, order_reviews) đi theo đơn,
-- dbt lọc chúng qua order_id. customers không lọc: dimension giữ thành viên (R10).
ALTER TABLE staging.orders
    ADD COLUMN IF NOT EXISTS _is_deleted  BOOLEAN    NOT NULL DEFAULT FALSE,  -- TRUE = nguồn đã báo xóa
    ADD COLUMN IF NOT EXISTS _deleted_at  TIMESTAMP;                         -- lúc nguồn xóa (cột deleted_at
                                                                             -- trong file, thời gian mô phỏng)

-- Số đơn bị đánh dấu xóa trong 1 lần chạy (ghi ở dòng table_name = 'orders')
ALTER TABLE etl_log.table_load
    ADD COLUMN IF NOT EXISTS rows_deleted INT NOT NULL DEFAULT 0;
