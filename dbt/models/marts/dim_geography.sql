{#-
    dim_geography: 1 dòng / 1 thành phố (đã chuẩn hóa R1) của 1 bang = NƠI NHẬN HÀNG (4.309 dòng + 1 dòng -1).
    Phân cấp Thành phố -> Bang -> Vùng. SCD Type 0: chỉ THÊM tổ hợp mới, không sửa dòng đã có.
    Grain (bang, thành phố), không theo mã bưu chính vì 33 mã bưu chính thuộc hơn 1 bang.
    Incremental - giữ khóa qua các batch (dbt_rules.md B4.2 mẫu 1): tổ hợp đã có giữ khóa cũ,
    tổ hợp mới nhận khóa nối tiếp MAX + row_number. Build lại khi dữ liệu không đổi -> INSERT 0 0.
    Thành phố tính bằng ĐÚNG biểu thức của int_orders.customer_city -> fact tra geography_key luôn khớp (R5).
-#}
{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key=['state_code', 'city']
) }}

with src as (                               -- mọi tổ hợp (bang, thành phố) nơi nhận đang có trong dữ liệu
    select distinct
        customer_state as state_code,
        coalesce({{ normalize_city('customer_city', 'customer_state') }}, 'Không xác định') as city
        -- coalesce: NULL không so bằng được -> để NULL thì mỗi lần build lại chèn trùng
    from {{ ref('stg_customers') }}
),

new_rows as (                               -- lần đầu: mọi tổ hợp; các lần sau: tổ hợp CHƯA có trong bảng
    select s.state_code, s.city
    from src as s
    {% if is_incremental() %}
    where not exists (
        select 1 from {{ this }} as t
        where t.state_code = s.state_code and t.city = s.city
    )
    {% endif %}
),

numbered as (                               -- khóa mới nối tiếp khóa lớn nhất đang có (R2)
    select
        ({% if is_incremental() %}(select greatest(max(geography_key), 0) from {{ this }}){% else %}0{% endif %}
            + row_number() over (order by state_code, city))::int as geography_key,
        state_code,
        city
    from new_rows
)

select
    n.geography_key,
    n.state_code::char(2)                                  as state_code,
    n.city::varchar(100)                                   as city,
    coalesce(st.state_name, 'Không xác định')::varchar(50) as state_name,
    coalesce(st.region, 'Không xác định')::varchar(30)     as region
from numbered as n
left join {{ ref('seed_brazil_states') }} as st
    on st.state_code = n.state_code

{% if not is_incremental() %}
union all
select -1, null, 'Không xác định', 'Không xác định', 'Không xác định'   -- member -1: chỉ thêm ở lần chạy đầu
{% endif %}
