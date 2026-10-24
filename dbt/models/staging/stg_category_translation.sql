-- stg_category_translation: 1 dòng / danh mục, bản dịch Bồ Đào Nha -> tiếng Anh (71 dòng).
-- 2 danh mục còn thiếu bản dịch được bổ sung bằng seed_category_translation_extra ở dim_product.
select
    product_category_name,
    product_category_name_english
from {{ source('staging', 'category_translation') }}
