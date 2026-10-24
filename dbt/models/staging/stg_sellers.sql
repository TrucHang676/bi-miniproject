-- stg_sellers: 1 dòng / người bán. Chỉ nạp ở Full Load (D3).
-- Chuẩn hóa thành phố (R1) đặt ở dim_seller.
select
    seller_id,
    seller_zip_code_prefix,
    seller_city,
    seller_state
from {{ source('staging', 'sellers') }}
