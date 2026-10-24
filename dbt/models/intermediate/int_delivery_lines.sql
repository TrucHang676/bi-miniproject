-- int_delivery_lines: 1 dòng / 1 cặp (đơn, người bán) = 1 lượt bàn giao - giao hàng. Mọi đơn có sản phẩm,
-- kể cả đơn hủy (để theo dõi trạng thái). Đơn không có sản phẩm thì không có người bán -> không có dòng.
-- Tính MỘT lần cho cả fact_delivery và fact_review:
--   * 4 measure số ngày (R7)       * handover_status, route_type, delay_bucket (R9)
-- Lưu ý: mốc bàn giao / khách nhận chỉ có ở CẤP ĐƠN -> lặp lại ở mọi người bán của đơn (1.278 đơn
-- nhiều người bán). KPI cấp đơn (K6, K7, M4) phải tính theo order_id riêng biệt.
with seller_lines as (                      -- hạn bàn giao là của từng người bán (1 giá trị / cặp - 0 ngoại lệ)
    select
        order_id,
        seller_id,
        max(shipping_limit_date) as shipping_limit_date
    from {{ ref('stg_order_items') }}
    group by order_id, seller_id
),

joined as (
    select
        sl.order_id,
        sl.seller_id,
        o.customer_unique_id,
        o.customer_state,
        o.customer_city,
        s.seller_state,
        o.order_status,
        o.order_purchase_timestamp,
        o.order_approved_at,
        sl.shipping_limit_date,
        o.order_delivered_carrier_date  as delivered_carrier_date,
        o.order_delivered_customer_date as delivered_customer_date,
        o.order_estimated_delivery_date as estimated_delivery_date
    from seller_lines as sl
    inner join {{ ref('int_orders') }} as o           -- stg_order_items đã chỉ còn đơn có trong stg_orders (R10)
        on o.order_id = sl.order_id
    left join {{ ref('stg_sellers') }} as s
        on s.seller_id = sl.seller_id
),

measures as (                               -- R7: số ngày = epoch / 86400; NULL khi thiếu mốc / sai thứ tự
    select
        *,
        -- dương = bàn giao trễ. Không tính khi chưa bàn giao hoặc ngày bàn giao trước ngày mua (mốc sai)
        case
            when delivered_carrier_date >= order_purchase_timestamp
                then round(extract(epoch from (delivered_carrier_date - shipping_limit_date)) / 86400, 2)
        end as handover_delay_days,
        -- 3 measure cấp đơn: chỉ đơn delivered (6 đơn canceled vẫn có ngày nhận ở nguồn -> bỏ)
        case
            when order_status = 'delivered' and delivered_customer_date >= delivered_carrier_date
                then round(extract(epoch from (delivered_customer_date - delivered_carrier_date)) / 86400, 2)
        end as transit_days,
        case
            when order_status = 'delivered' and delivered_customer_date is not null
                then round(extract(epoch from (delivered_customer_date - order_purchase_timestamp)) / 86400, 2)
        end as delivery_days,
        -- so theo NGÀY: ngày dự kiến luôn 00:00 (so cả giờ ra 8,11% là sai)
        case
            when order_status = 'delivered' and delivered_customer_date is not null
                then delivered_customer_date::date - estimated_delivery_date
        end as late_days
    from joined
)

select
    order_id,
    seller_id,
    customer_unique_id,
    customer_state,
    customer_city,
    seller_state,
    order_status,
    order_purchase_timestamp,
    order_approved_at,
    shipping_limit_date,
    delivered_carrier_date,
    delivered_customer_date,
    estimated_delivery_date,
    handover_delay_days::numeric(6, 2) as handover_delay_days,
    transit_days::numeric(6, 2)        as transit_days,
    delivery_days::numeric(6, 2)       as delivery_days,
    late_days::smallint                as late_days,
    -- R9: xét theo thứ tự, gặp điều kiện đầu tiên thì dừng (so theo giờ)
    case
        when delivered_carrier_date is null                     then 'Chưa bàn giao'
        when delivered_carrier_date < order_purchase_timestamp  then 'Không xác định'
        when delivered_carrier_date > shipping_limit_date       then 'Trễ hạn'
        else 'Đúng hạn'
    end as handover_status,
    case
        when customer_state is null or seller_state is null then 'Không xác định'
        when customer_state = seller_state                  then 'Nội bang'
        else 'Liên bang'
    end as route_type,
    case
        when order_status <> 'delivered'      then 'Chưa giao'
        when delivered_customer_date is null  then 'Không xác định'
        when late_days <= 0                   then 'Đúng hạn'
        when late_days <= 3                   then 'Trễ 1–3 ngày'
        when late_days <= 7                   then 'Trễ 4–7 ngày'
        when late_days <= 14                  then 'Trễ 8–14 ngày'
        else 'Trễ > 14 ngày'
    end as delay_bucket
from measures
