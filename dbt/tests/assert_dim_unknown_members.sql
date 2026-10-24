-- Mỗi dimension có member "Không xác định" phải có ĐÚNG 1 dòng khóa -1 (R2) - fact tra không ra thì trỏ vào đây.
-- dim_date, dim_delivery_status không có dòng -1 (sinh đủ mọi giá trị). Trả về dimension sai -> 0 dòng = đạt.
-- Quan trọng với dim_customer, dim_geography (incremental): dòng -1 chỉ thêm ở lần chạy đầu, không được mất / nhân đôi.
with counts as (
    select 'dim_customer' as dim_name, count(*) as so_dong_am_1 from {{ ref('dim_customer') }} where customer_key = -1
    union all
    select 'dim_geography', count(*) from {{ ref('dim_geography') }} where geography_key = -1
    union all
    select 'dim_product', count(*) from {{ ref('dim_product') }} where product_key = -1
    union all
    select 'dim_seller', count(*) from {{ ref('dim_seller') }} where seller_key = -1
)

select dim_name, so_dong_am_1
from counts
where so_dong_am_1 <> 1
