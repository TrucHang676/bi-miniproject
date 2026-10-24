-- fact_review: đánh giá. 1 dòng = 1 lượt đánh giá của khách cho 1 đơn, gắn với 1 người bán của đơn đó.
-- Câu Q6 cần điểm trung bình của TỪNG người bán, nên đánh giá của đơn nhiều người bán được tính cho mọi người
-- bán của đơn: 99.224 lượt đánh giá -> 100.568 dòng. Đơn không có sản phẩm thì không có người bán -> seller_key = -1
-- (759 dòng). Khi tính điểm chung (K8, K9) phải lấy 1 điểm / đơn bằng cờ is_latest_review, tránh đếm lặp.
-- Dựng lại toàn bộ mỗi lần chạy (table): review mới đến ở batch sau thì is_latest_review của review cũ phải đổi
-- TRUE -> FALSE, và delivery_status_key (nằm trong khóa chính) đổi theo trạng thái giao hàng.

with reviews as (                           -- tính trên từng lượt đánh giá, TRƯỚC khi nhân theo người bán
    select
        review_id,
        order_id,
        review_score,
        review_creation_date,
        review_answer_timestamp,
        -- 547 đơn có hơn 1 đánh giá: đánh dấu đánh giá trả lời muộn nhất của mỗi đơn.
        -- review_id đứng cuối để khi trùng thời điểm thì lần chạy nào cũng chọn cùng một dòng.
        row_number() over (
            partition by order_id
            order by review_answer_timestamp desc, review_creation_date desc, review_id desc
        ) = 1 as is_latest_review,
        -- R8: có bình luận thật khi tiêu đề hoặc nội dung (sau khi bỏ khoảng trắng) có ít nhất 1 chữ cái.
        -- Các ô chỉ có '.', '...', '*****', chữ số hay emoji coi như không có bình luận.
        coalesce(trim(review_comment_title) ~ '[[:alpha:]]', false)
            or coalesce(trim(review_comment_message) ~ '[[:alpha:]]', false) as has_comment
    from {{ ref('stg_order_reviews') }}
),

order_sellers as (                          -- các người bán của mỗi đơn
    select distinct order_id, seller_id
    from {{ ref('stg_order_items') }}
),

review_lines as (                           -- nhân đánh giá theo người bán; đơn không có sản phẩm -> seller_id NULL
    select
        r.*,
        os.seller_id
    from reviews as r
    left join order_sellers as os
        on os.order_id = r.order_id
),

with_delivery_status as (
    select
        rl.*,
        o.customer_unique_id,
        o.customer_state,
        o.customer_city,
        o.order_purchase_timestamp,
        -- trạng thái giao hàng của đúng lượt (đơn, người bán) được đánh giá - lấy từ int_delivery_lines.
        -- Đơn không có người bán thì không có lượt giao hàng: bàn giao, tuyến = 'Không xác định';
        -- nhóm trễ = 'Chưa giao' nếu đơn chưa delivered, còn đơn ghi delivered mà không có sản phẩm là dữ liệu
        -- bất thường -> 'Không xác định' (trên dữ liệu thật: 0 đơn như vậy).
        coalesce(dl.order_status, o.order_status)            as order_status,
        coalesce(dl.handover_status, 'Không xác định')       as handover_status,
        coalesce(dl.route_type, 'Không xác định')            as route_type,
        coalesce(
            dl.delay_bucket,
            case when o.order_status = 'delivered' then 'Không xác định' else 'Chưa giao' end
        )                                                    as delay_bucket
    from review_lines as rl
    left join {{ ref('int_orders') }} as o
        on o.order_id = rl.order_id
    left join {{ ref('int_delivery_lines') }} as dl
        on dl.order_id = rl.order_id
       and dl.seller_id = rl.seller_id
)

select
    w.review_id::varchar(32)                                  as review_id,
    w.order_id::varchar(32)                                   as order_id,
    to_char(w.order_purchase_timestamp, 'YYYYMMDD')::int      as purchase_date_key,   -- R3: ngày đặt hàng
    to_char(w.review_answer_timestamp, 'YYYYMMDD')::int       as answer_date_key,     -- R3: ngày khách trả lời
    -- R5: tra khóa bằng left join; không tìm thấy thì -1
    coalesce(dc.customer_key, -1)                             as customer_key,
    coalesce(dg.geography_key, -1)                            as geography_key,
    coalesce(ds.seller_key, -1)                               as seller_key,
    dst.delivery_status_key,
    w.review_creation_date,
    w.review_answer_timestamp,
    w.has_comment,
    w.is_latest_review,
    w.review_score::smallint                                  as review_score
from with_delivery_status as w
left join {{ ref('dim_customer') }} as dc
    on dc.customer_unique_id = w.customer_unique_id
left join {{ ref('dim_geography') }} as dg
    on dg.state_code = w.customer_state
   and dg.city = w.customer_city
left join {{ ref('dim_seller') }} as ds
    on ds.seller_id = w.seller_id
left join {{ ref('dim_delivery_status') }} as dst
    on dst.order_status = w.order_status
   and dst.handover_status = w.handover_status
   and dst.route_type = w.route_type
   and dst.delay_bucket = w.delay_bucket
