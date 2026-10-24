-- dim_product: 1 dòng / sản phẩm (32.951 dòng + 1 dòng -1). Phân cấp Sản phẩm -> Danh mục. SCD Type 1.
-- Dựng lại toàn bộ (table): products chỉ nạp ở Full Load (D3) nên row_number theo product_id luôn cho cùng khóa (R2).
-- Nguồn: stg_products (đã đổi tên *_lenght), bản dịch danh mục + seed bổ sung 2 bản dịch còn thiếu.
with products as (
    select * from {{ ref('stg_products') }}
),

translations as (                           -- 71 bản dịch nguồn + 2 bản dịch nhóm tự bổ sung (seed)
    select product_category_name, product_category_name_english
    from {{ ref('stg_category_translation') }}
    union all
    select product_category_name, product_category_name_english
    from {{ ref('seed_category_translation_extra') }}
),

cleaned as (
    select
        p.product_id,
        coalesce(p.product_category_name, 'unknown')         as category_name_pt,   -- 610 sản phẩm thiếu danh mục
        coalesce(t.product_category_name_english, 'unknown') as category_name_en,
        nullif(p.product_weight_g, 0)   as weight_g,     -- 0 g là lỗi nhập liệu (4 sản phẩm), không phải "rất nhẹ"
        nullif(p.product_length_cm, 0)  as length_cm,
        nullif(p.product_height_cm, 0)  as height_cm,
        nullif(p.product_width_cm, 0)   as width_cm,
        p.product_photos_qty            as photos_qty,
        p.product_name_length           as name_length,
        p.product_description_length    as description_length
    from products as p
    left join translations as t
        on t.product_category_name = p.product_category_name
)

select
    row_number() over (order by product_id)::int as product_key,     -- R2
    product_id::varchar(32)          as product_id,
    category_name_pt::varchar(60)    as category_name_pt,
    category_name_en::varchar(60)    as category_name_en,
    weight_g::int                    as weight_g,
    length_cm::int                   as length_cm,
    height_cm::int                   as height_cm,
    width_cm::int                    as width_cm,
    -- nhóm khối lượng; cận dưới thuộc nhóm trên (500 g -> '0,5–2 kg'); dùng weight_g SAU nullif
    (case
        when weight_g is null  then 'Không rõ'
        when weight_g < 500    then '< 0,5 kg'
        when weight_g < 2000   then '0,5–2 kg'
        when weight_g < 5000   then '2–5 kg'
        when weight_g < 10000  then '5–10 kg'
        else '≥ 10 kg'
    end)::varchar(20)                as weight_class,
    photos_qty::smallint             as photos_qty,
    name_length::smallint            as name_length,
    description_length::smallint     as description_length
from cleaned

union all

-- R2: member -1 "Không xác định" cho dòng fact không tra được sản phẩm
select -1, '-1', 'Không xác định', 'Không xác định', null, null, null, null, 'Không xác định', null, null, null
