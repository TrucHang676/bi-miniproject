-- Đơn đã bị xóa ở nguồn (staging.orders._is_deleted = TRUE, quy tắc R10) không được còn trong fact nào.
-- Trả về các dòng vi phạm -> 0 dòng = đạt.
-- Dữ liệu Olist không có đơn bị xóa nên test luôn đạt; test có ý nghĩa khi demo xóa 1 đơn (dbt_rules.md B7 kịch bản 4).
-- Đọc thẳng staging.orders (source) vì stg_orders đã lọc mất các đơn bị xóa.
select 'fact_sales' as fact_name, f.order_id
from {{ ref('fact_sales') }} as f
inner join {{ source('staging', 'orders') }} as o
    on o.order_id = f.order_id
where o._is_deleted

union all

select 'fact_delivery', f.order_id
from {{ ref('fact_delivery') }} as f
inner join {{ source('staging', 'orders') }} as o
    on o.order_id = f.order_id
where o._is_deleted

union all

select 'fact_review', f.order_id
from {{ ref('fact_review') }} as f
inner join {{ source('staging', 'orders') }} as o
    on o.order_id = f.order_id
where o._is_deleted
