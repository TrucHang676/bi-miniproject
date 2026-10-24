-- int_orders: 1 dòng / đơn hàng (chưa bị xóa - đọc qua stg_orders, R10).
-- Gom những gì nhiều dimension / fact cần về một chỗ:
--   * customer_unique_id: khách THẬT của đơn (D7) - customer_id chỉ là mã theo đơn
--   * bang + thành phố nơi nhận CỦA CHÍNH ĐƠN, đã chuẩn hóa (R1) - dùng tra geography_key (R5)
--   * is_valid: đơn hợp lệ (R4) - dùng lọc fact_sales, tính purchase_count
with orders as (
    select * from {{ ref('stg_orders') }}
),

customers as (
    select * from {{ ref('stg_customers') }}
),

orders_with_items as (                      -- R4: đơn phải có ít nhất 1 sản phẩm
    select distinct order_id
    from {{ ref('stg_order_items') }}
)

select
    o.order_id,
    o.customer_id,
    c.customer_unique_id,
    o.order_status,
    o.order_purchase_timestamp,
    o.order_approved_at,
    o.order_delivered_carrier_date,
    o.order_delivered_customer_date,
    o.order_estimated_delivery_date,
    c.customer_state,
    -- R1: cùng biểu thức với dim_geography -> tra geography_key luôn khớp; NULL hiển thị 'Không xác định'
    coalesce({{ normalize_city('c.customer_city', 'c.customer_state') }}, 'Không xác định') as customer_city,
    -- R4: khác canceled / unavailable VÀ có sản phẩm
    (o.order_status not in ('canceled', 'unavailable') and oi.order_id is not null) as is_valid
from orders as o
left join customers as c
    on c.customer_id = o.customer_id
left join orders_with_items as oi
    on oi.order_id = o.order_id
