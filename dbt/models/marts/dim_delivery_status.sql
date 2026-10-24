-- dim_delivery_status: 1 dòng / 1 tổ hợp trạng thái của một lượt giao hàng (672 dòng = 8 x 4 x 3 x 7).
-- Junk dimension: gom các thuộc tính suy ra (R9) thay vì lặp 4 cột chữ trên mỗi dòng fact. Tự sinh bằng tích
-- Descartes ĐỦ mọi tổ hợp -> fact tra khóa không bao giờ trượt, nên không cần dòng -1. SCD Type 0.
-- Khóa = thứ tự cố định của 4 danh sách dưới đây (giữ nguyên thứ tự -> mọi lần chạy cho cùng khóa).
-- Chuỗi phải GIỐNG HỆT int_delivery_lines (R9) - có dấu tiếng Việt, gạch "–".
with order_statuses (order_status, order_status_sort) as (
    values
        ('created', 1), ('approved', 2), ('invoiced', 3), ('processing', 4),
        ('shipped', 5), ('delivered', 6), ('canceled', 7), ('unavailable', 8)
),

handover_statuses (handover_status, handover_sort) as (
    values ('Đúng hạn', 1), ('Trễ hạn', 2), ('Chưa bàn giao', 3), ('Không xác định', 4)
),

route_types (route_type, route_sort) as (
    values ('Nội bang', 1), ('Liên bang', 2), ('Không xác định', 3)
),

delay_buckets (delay_bucket, bucket_sort) as (
    values
        ('Đúng hạn', 1), ('Trễ 1–3 ngày', 2), ('Trễ 4–7 ngày', 3), ('Trễ 8–14 ngày', 4),
        ('Trễ > 14 ngày', 5), ('Chưa giao', 6), ('Không xác định', 7)
)

select
    row_number() over (
        order by os.order_status_sort, hs.handover_sort, rt.route_sort, db.bucket_sort
    )::int                                   as delivery_status_key,
    os.order_status::varchar(20)             as order_status,
    hs.handover_status::varchar(30)          as handover_status,
    rt.route_type::varchar(20)               as route_type,
    db.delay_bucket::varchar(30)             as delay_bucket,
    -- cấp cha của delay_bucket (phân cấp Nhóm số ngày trễ -> Kết quả giao); K6 = 'Trễ hạn' / ('Đúng hạn' + 'Trễ hạn')
    (case
        when db.delay_bucket = 'Đúng hạn'   then 'Đúng hạn'
        when db.delay_bucket like 'Trễ%'    then 'Trễ hạn'
        else db.delay_bucket
    end)::varchar(30)                        as delivery_result
from order_statuses as os
cross join handover_statuses as hs
cross join route_types as rt
cross join delay_buckets as db
