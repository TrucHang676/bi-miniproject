-- stg_order_items: 1 dòng / 1 đơn vị sản phẩm trong 1 đơn (chưa gộp - gộp thành quantity ở fact_sales).
-- Bảng con: chỉ giữ dòng của đơn còn trong stg_orders -> quy tắc xóa mềm (R10) chỉ viết ở 1 chỗ.
select
    oi.order_id,
    oi.order_item_id,
    oi.product_id,
    oi.seller_id,
    oi.shipping_limit_date,
    oi.price,
    oi.freight_value
from {{ source('staging', 'order_items') }} as oi
where oi.order_id in (select order_id from {{ ref('stg_orders') }})
