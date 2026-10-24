-- int_purchase_sessions: 1 dòng / đơn HỢP LỆ (R4), kèm purchase_seq = lần mua thứ mấy của khách (R6).
-- Giỏ hàng nhiều người bán bị Olist tách thành nhiều đơn cách nhau vài giây (D7) -> đếm theo đơn sẽ thổi phồng
-- tỉ lệ mua lại. Gộp: đơn cách ĐƠN LIỀN TRƯỚC của cùng khách <= 10 phút thì cùng 1 lần mua.
-- Dùng cho fact_sales.purchase_seq (K5 theo kỳ) và dim_customer.purchase_count / customer_type.
with valid_orders as (
    select
        order_id,
        customer_unique_id,
        order_purchase_timestamp
    from {{ ref('int_orders') }}
    where is_valid
),

with_previous as (                          -- thời điểm đặt của đơn liền trước của cùng khách
    select
        *,
        lag(order_purchase_timestamp) over (
            partition by customer_unique_id
            order by order_purchase_timestamp, order_id
        ) as previous_purchase_timestamp
    from valid_orders
),

flagged as (                                -- R6: đơn mở đầu một lần mua mới?
    select
        *,
        case
            when previous_purchase_timestamp is null then 1
            when order_purchase_timestamp - previous_purchase_timestamp > interval '10 minutes' then 1
            else 0
        end as is_new_purchase
    from with_previous
)

select
    order_id,
    customer_unique_id,
    order_purchase_timestamp,
    -- cộng dồn số lần mua mới tới đơn hiện tại -> 1, 2, 3…
    sum(is_new_purchase) over (
        partition by customer_unique_id
        order by order_purchase_timestamp, order_id
        rows between unbounded preceding and current row
    )::smallint as purchase_seq
from flagged
