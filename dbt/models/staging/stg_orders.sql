-- stg_orders: 1 dòng / đơn hàng chưa bị xóa ở nguồn (R10).
-- staging đã đúng kiểu dữ liệu (Mage ép kiểu lúc nạp) -> chọn cột cần dùng, bỏ cột kỹ thuật
-- _batch_id, _loaded_at, _is_deleted, _deleted_at (source_to_target_mapping.md mục 4).
-- Đây là chỗ DUY NHẤT viết quy tắc xóa mềm: 3 bảng con lọc theo model này.
select
    order_id,
    customer_id,
    order_status,
    order_purchase_timestamp,
    order_approved_at,
    order_delivered_carrier_date,
    order_delivered_customer_date,
    order_estimated_delivery_date
from {{ source('staging', 'orders') }}
where not _is_deleted   -- R10: đơn nguồn đã xóa coi như chưa từng có trong dds
