-- Mỗi đơn có đánh giá phải có ĐÚNG 1 lượt đánh giá được đánh dấu is_latest_review = TRUE.
-- Nếu một đơn có 0 hoặc 2 lượt "mới nhất", điểm trung bình (K8) và tỉ lệ đánh giá tiêu cực (K9) sẽ thiếu hoặc
-- đếm lặp đơn đó. Đếm theo review_id riêng biệt vì cùng 1 đánh giá được nhân cho mọi người bán của đơn.
-- Trả về các đơn vi phạm -> 0 dòng = đạt.
select
    order_id,
    count(distinct review_id) filter (where is_latest_review) as so_danh_gia_moi_nhat
from {{ ref('fact_review') }}
group by order_id
having count(distinct review_id) filter (where is_latest_review) <> 1
