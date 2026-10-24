-- fact_sales: bán hàng. 1 dòng = 1 sản phẩm do 1 người bán bán trong 1 đơn HỢP LỆ (R4).
-- order_items ghi mỗi đơn vị sản phẩm thành 1 dòng (mua 3 cái = 3 dòng). Ở đây gộp các dòng giống nhau
-- (cùng đơn, cùng sản phẩm, cùng người bán) thành 1 dòng có cột quantity. Gộp không mất thông tin vì trong
-- mỗi nhóm giá và phí ship giống hệt nhau (test revenue = quantity * unit_price kiểm tra điều này).
-- Doanh thu chỉ lấy từ order_items.price, không lấy từ order_payments (lệch ở 249 đơn do lãi trả góp, voucher).
-- Dựng lại toàn bộ mỗi lần chạy (table) để đơn bị xóa mềm (R10) biến mất khỏi fact.
-- Kết quả: 101.953 dòng khi nạp đủ 10 batch.

with valid_orders as (                      -- R4: bỏ đơn hủy / hết hàng / không có sản phẩm
    select
        order_id,
        customer_unique_id,
        customer_state,
        customer_city,                      -- đã chuẩn hóa R1, dùng để tra geography_key
        order_purchase_timestamp
    from {{ ref('int_orders') }}
    where is_valid
),

sales_lines as (                            -- gộp các đơn vị cùng sản phẩm thành 1 dòng
    select
        oi.order_id,
        oi.product_id,
        oi.seller_id,
        count(*)              as quantity,
        max(oi.price)         as unit_price, -- trong nhóm giá như nhau nên max = min
        sum(oi.price)         as revenue,
        sum(oi.freight_value) as freight_value
    from {{ ref('stg_order_items') }} as oi
    where oi.order_id in (select order_id from valid_orders)
    group by oi.order_id, oi.product_id, oi.seller_id
)

select
    sl.order_id::varchar(32)                                  as order_id,
    to_char(vo.order_purchase_timestamp, 'YYYYMMDD')::int     as purchase_date_key,   -- R3
    -- R5: tra khóa từ dimension bằng left join; không tìm thấy thì -1 (không bỏ dòng)
    coalesce(dc.customer_key, -1)                             as customer_key,
    coalesce(dg.geography_key, -1)                            as geography_key,
    coalesce(dp.product_key, -1)                              as product_key,
    coalesce(ds.seller_key, -1)                               as seller_key,
    ps.purchase_seq,                                          -- R6: lần mua thứ mấy của khách
    sl.quantity::smallint                                     as quantity,
    sl.unit_price::numeric(10, 2)                             as unit_price,
    sl.revenue::numeric(12, 2)                                as revenue,
    sl.freight_value::numeric(10, 2)                          as freight_value
from sales_lines as sl
-- sales_lines chỉ chứa đơn hợp lệ nên join với valid_orders không làm mất dòng nào
inner join valid_orders as vo
    on vo.order_id = sl.order_id
left join {{ ref('int_purchase_sessions') }} as ps
    on ps.order_id = sl.order_id
left join {{ ref('dim_customer') }} as dc
    on dc.customer_unique_id = vo.customer_unique_id
left join {{ ref('dim_geography') }} as dg                  -- nơi nhận của CHÍNH đơn này (vị trí lúc mua)
    on dg.state_code = vo.customer_state
   and dg.city = vo.customer_city
left join {{ ref('dim_product') }} as dp
    on dp.product_id = sl.product_id
left join {{ ref('dim_seller') }} as ds
    on ds.seller_id = sl.seller_id
