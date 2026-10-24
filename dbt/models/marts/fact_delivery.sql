-- fact_delivery: giao hàng. 1 dòng = 1 lượt bàn giao - giao hàng của 1 người bán cho 1 đơn
-- = 1 cặp (đơn, người bán). Gồm mọi đơn có sản phẩm, kể cả đơn hủy, để theo dõi trạng thái.
-- Loại fact: accumulating snapshot - dòng theo dõi đơn qua các mốc đặt -> duyệt -> bàn giao -> khách nhận.
-- Khi batch sau gửi lại đơn với mốc mới (D8), dòng đổi theo, kể cả delivery_status_key (nằm trong khóa chính)
-- -> dựng lại toàn bộ mỗi lần chạy (table), không cập nhật tại chỗ.
-- Phần tính toán (4 measure số ngày, 3 nhãn trạng thái) đã làm ở int_delivery_lines; model này chỉ tra khóa.
-- Lưu ý khi tính KPI: ngày bàn giao, ngày khách nhận chỉ có ở CẤP ĐƠN nên transit_days, delivery_days,
-- late_days lặp lại ở mọi người bán của 1.278 đơn nhiều người bán -> K6, K7, M4 tính theo order_id riêng biệt.
-- Kết quả: 100.010 dòng, 98.666 đơn.

select
    dl.order_id::varchar(32)                                  as order_id,
    to_char(dl.order_purchase_timestamp, 'YYYYMMDD')::int     as purchase_date_key,   -- R3
    -- R5: tra khóa bằng left join; không tìm thấy thì -1
    coalesce(dc.customer_key, -1)                             as customer_key,
    coalesce(dg.geography_key, -1)                            as geography_key,
    coalesce(ds.seller_key, -1)                               as seller_key,
    -- dim_delivery_status có sẵn đủ 672 tổ hợp nên luôn tra ra; nếu NULL thì test not_null sẽ báo
    dst.delivery_status_key,
    dl.order_purchase_timestamp,
    dl.order_approved_at,
    dl.shipping_limit_date,
    dl.delivered_carrier_date,
    dl.delivered_customer_date,
    dl.estimated_delivery_date,
    dl.handover_delay_days,
    dl.transit_days,
    dl.delivery_days,
    dl.late_days
from {{ ref('int_delivery_lines') }} as dl
left join {{ ref('dim_customer') }} as dc
    on dc.customer_unique_id = dl.customer_unique_id
left join {{ ref('dim_geography') }} as dg
    on dg.state_code = dl.customer_state
   and dg.city = dl.customer_city
left join {{ ref('dim_seller') }} as ds
    on ds.seller_id = dl.seller_id
left join {{ ref('dim_delivery_status') }} as dst           -- R9: tra theo bộ 4 nhãn đã tính ở int_delivery_lines
    on dst.order_status = dl.order_status
   and dst.handover_status = dl.handover_status
   and dst.route_type = dl.route_type
   and dst.delay_bucket = dl.delay_bucket
