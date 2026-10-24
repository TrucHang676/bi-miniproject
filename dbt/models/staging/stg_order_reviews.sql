-- stg_order_reviews: 1 dòng / 1 đánh giá cho 1 đơn. Khóa (review_id, order_id) - review_id KHÔNG duy nhất.
-- Làm sạch bình luận (R8) đặt ở fact_review, để stg_ vẫn đối chiếu 1-1 được với staging.
-- Bảng con: chỉ giữ dòng của đơn còn trong stg_orders (R10).
select
    r.review_id,
    r.order_id,
    r.review_score,
    r.review_comment_title,
    r.review_comment_message,
    r.review_creation_date,
    r.review_answer_timestamp
from {{ source('staging', 'order_reviews') }} as r
where r.order_id in (select order_id from {{ ref('stg_orders') }})
