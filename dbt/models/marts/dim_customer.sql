{#-
    dim_customer: 1 dòng / 1 khách hàng THỰC - customer_unique_id (96.096 dòng + 1 dòng -1). D7.
    Phân cấp Khách hàng -> Thành phố -> Bang -> Vùng. SCD Type 1: ghi đè thuộc tính, GIỮ khóa.
    Incremental (dbt_rules.md B4.2 mẫu 2): mỗi lần chạy tính lại thuộc tính MỚI NHẤT của MỌI khách từ toàn bộ
    dữ liệu; delete+insert theo customer_unique_id ghi đè dòng cũ; khóa lấy lại từ chính bảng ({{ this }}) nên
    khách cũ không đổi khóa, khách mới nhận khóa nối tiếp. Dòng -1 không nằm trong kết quả các lần sau nên không bị đụng.
    Đọc qua stg_ / int_ nên đơn đã xóa mềm tự bị loại (R10), nhưng khách vẫn được giữ (stg_customers không lọc).
-#}
{{ config(
    materialized='incremental',
    incremental_strategy='delete+insert',
    unique_key='customer_unique_id'
) }}

with customers as (                         -- danh sách khách: mọi khách có trong dữ liệu (kể cả chỉ có đơn hủy)
    select distinct customer_unique_id
    from {{ ref('stg_customers') }}
),

latest_order_address as (                   -- SCD 1: địa chỉ của đơn GẦN NHẤT, xét mọi đơn (kể cả hủy) - chốt 17/10/2026
    select
        customer_unique_id,
        customer_state,
        customer_city,                      -- đã chuẩn hóa R1 ở int_orders
        row_number() over (
            partition by customer_unique_id
            order by order_purchase_timestamp desc, order_id desc
        ) as rn
    from {{ ref('int_orders') }}
),

fallback_address as (                       -- khách không còn đơn nào (mọi đơn đã xóa mềm): lấy địa chỉ trong stg_customers
    select
        customer_unique_id,
        customer_state,
        coalesce({{ normalize_city('customer_city', 'customer_state') }}, 'Không xác định') as customer_city,
        row_number() over (partition by customer_unique_id order by customer_id desc) as rn
    from {{ ref('stg_customers') }}
),

purchases as (                              -- chỉ đơn hợp lệ (R4), lần mua đã gộp giỏ hàng tách đơn (R6)
    select
        customer_unique_id,
        min(order_purchase_timestamp)::date as first_purchase_date,
        max(purchase_seq)                   as purchase_count
    from {{ ref('int_purchase_sessions') }}
    group by customer_unique_id
),

src as (
    select
        c.customer_unique_id,
        coalesce(lo.customer_city, fa.customer_city)   as customer_city,
        coalesce(lo.customer_state, fa.customer_state) as customer_state,
        p.first_purchase_date,                                    -- NULL khi không có đơn hợp lệ (1.113 khách)
        coalesce(p.purchase_count, 0)                  as purchase_count
    from customers as c
    left join latest_order_address as lo
        on lo.customer_unique_id = c.customer_unique_id and lo.rn = 1
    left join fallback_address as fa
        on fa.customer_unique_id = c.customer_unique_id and fa.rn = 1
    left join purchases as p
        on p.customer_unique_id = c.customer_unique_id
),

keyed as (                                  -- khách đã có trong bảng thì lấy lại khóa cũ
    select
        s.*,
        {% if is_incremental() %} t.customer_key {% else %} null::int {% endif %} as old_key
    from src as s
    {% if is_incremental() %}
    left join {{ this }} as t
        on t.customer_unique_id = s.customer_unique_id
    {% endif %}
)

select
    coalesce(
        k.old_key,                          -- khách cũ giữ khóa; khách mới: khóa lớn nhất + thứ tự trong nhóm khách mới (R2)
        {% if is_incremental() %}(select greatest(max(customer_key), 0) from {{ this }}){% else %}0{% endif %}
            + row_number() over (partition by k.old_key is null order by k.customer_unique_id)
    )::int                                             as customer_key,
    k.customer_unique_id::varchar(32)                  as customer_unique_id,
    k.customer_city::varchar(100)                      as customer_city,
    k.customer_state::char(2)                          as customer_state,
    coalesce(st.region, 'Không xác định')::varchar(30) as customer_region,
    k.first_purchase_date,
    k.purchase_count::smallint                         as purchase_count,
    (case
        when k.purchase_count = 0 then 'Chưa có đơn hợp lệ'
        when k.purchase_count = 1 then 'Mua một lần'
        else 'Mua lại'
    end)::varchar(20)                                  as customer_type
from keyed as k
left join {{ ref('seed_brazil_states') }} as st
    on st.state_code = k.customer_state

{% if not is_incremental() %}
union all
select -1, '-1', 'Không xác định', null, 'Không xác định', null, null, 'Không xác định'   -- member -1: chỉ thêm lần chạy đầu
{% endif %}
