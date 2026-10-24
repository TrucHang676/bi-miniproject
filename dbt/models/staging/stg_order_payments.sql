-- stg_order_payments: 1 dòng / 1 lần thanh toán của đơn.
-- Chưa bảng dds nào dùng (không có fact_payment - mapping mục 4) nhưng vẫn làm cho đủ tầng staging.
-- Bảng con: chỉ giữ dòng của đơn còn trong stg_orders (R10).
select
    op.order_id,
    op.payment_sequential,
    op.payment_type,
    op.payment_installments,
    op.payment_value
from {{ source('staging', 'order_payments') }} as op
where op.order_id in (select order_id from {{ ref('stg_orders') }})
