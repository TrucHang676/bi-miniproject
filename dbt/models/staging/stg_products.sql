-- stg_products: 1 dòng / sản phẩm. Chỉ nạp ở Full Load (D3).
-- Đổi tên 2 cột sai chính tả của nguồn ngay ở model đầu tiên (chốt 17/10/2026)
-- -> mọi model phía sau chỉ thấy tên đúng. Schema staging (Mage) giữ nguyên tên gốc.
select
    product_id,
    product_category_name,
    product_name_lenght        as product_name_length,
    product_description_lenght as product_description_length,
    product_photos_qty,
    product_weight_g,
    product_length_cm,
    product_height_cm,
    product_width_cm
from {{ source('staging', 'products') }}
