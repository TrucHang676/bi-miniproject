-- Fact phải khớp với dữ liệu nguồn: không nhân dòng (fan-out) và không mất dòng khi nối bảng.
-- So fact với nguồn, KHÔNG so với một con số cố định -> vẫn đúng khi demo xóa đơn hay nạp thêm batch.
-- Trả về các phép so sánh không khớp -> 0 dòng = đạt.
with valid_orders as (
    select order_id from {{ ref('int_orders') }} where is_valid
),

checks as (
    -- 1. Tổng số lượng bán = số dòng order_items của đơn hợp lệ (mỗi dòng nguồn = 1 đơn vị)
    select
        'fact_sales: tổng quantity = số dòng order_items của đơn hợp lệ' as kiem_tra,
        (select sum(quantity) from {{ ref('fact_sales') }})::numeric as gia_tri_fact,
        (select count(*) from {{ ref('stg_order_items') }}
          where order_id in (select order_id from valid_orders))::numeric as gia_tri_nguon

    union all
    -- 2. Tổng doanh thu = tổng price của đơn hợp lệ (nếu nối nhầm làm nhân dòng thì tổng sẽ lớn hơn)
    select
        'fact_sales: tổng revenue = tổng price của đơn hợp lệ',
        (select sum(revenue) from {{ ref('fact_sales') }}),
        (select sum(price) from {{ ref('stg_order_items') }}
          where order_id in (select order_id from valid_orders))

    union all
    -- 3. Mỗi cặp (đơn, người bán) có sản phẩm xuất hiện đúng 1 lần trong fact_delivery
    select
        'fact_delivery: số dòng = số cặp (đơn, người bán) trong order_items',
        (select count(*) from {{ ref('fact_delivery') }}),
        (select count(*) from (select distinct order_id, seller_id from {{ ref('stg_order_items') }}) as pairs)

    union all
    -- 4. Mọi lượt đánh giá nguồn đều có trong fact_review (không mất lượt nào khi nhân theo người bán)
    select
        'fact_review: số lượt (review_id, order_id) = số dòng order_reviews',
        (select count(*) from (select distinct review_id, order_id from {{ ref('fact_review') }}) as r),
        (select count(*) from {{ ref('stg_order_reviews') }})
)

select kiem_tra, gia_tri_fact, gia_tri_nguon
from checks
where gia_tri_fact is distinct from gia_tri_nguon
