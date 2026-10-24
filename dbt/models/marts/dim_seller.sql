-- dim_seller: 1 dòng / người bán (3.095 dòng + 1 dòng -1). Phân cấp Người bán -> Thành phố -> Bang -> Vùng. SCD Type 1.
-- Dựng lại toàn bộ (table): sellers chỉ nạp ở Full Load (D3) nên row_number theo seller_id luôn cho cùng khóa (R2).
-- Vị trí người bán cố định ở nguồn nên đặt thẳng trong dimension (star), không tách bảng địa lý riêng.
-- Dòng -1 dùng cho 759 dòng fact_review của đơn không có sản phẩm (không có người bán).
-- K10 (người bán hoạt động) đếm trên fact, KHÔNG đếm số dòng bảng này (41,5% người bán chỉ bán sau Full Load - D3).
with sellers as (
    select * from {{ ref('stg_sellers') }}
),

states as (
    select state_code, region from {{ ref('seed_brazil_states') }}
)

select
    row_number() over (order by s.seller_id)::int as seller_key,       -- R2
    s.seller_id::varchar(32)                       as seller_id,
    -- R1: 7 dòng không phải tên thành phố ('sp', email, chuỗi số) -> 'Không xác định';
    -- 77 dòng gõ sai / viết tắt giữ nguyên (không câu hỏi nào phân tích theo thành phố người bán)
    coalesce({{ normalize_city('s.seller_city', 's.seller_state') }}, 'Không xác định')::varchar(100) as seller_city,
    s.seller_state::char(2)                        as seller_state,
    coalesce(st.region, 'Không xác định')::varchar(30) as seller_region
from sellers as s
left join states as st
    on st.state_code = s.seller_state

union all

select -1, '-1', 'Không xác định', null, 'Không xác định'      -- R2: member -1
