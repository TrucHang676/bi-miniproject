-- stg_customers: 1 dòng / customer_id = địa chỉ nhận hàng của 1 đơn. Khách thật là customer_unique_id (D7).
-- KHÔNG lọc xóa mềm: dimension giữ thành viên kể cả khi đơn của họ bị xóa (dbt_rules.md B2).
-- Chuẩn hóa thành phố (R1) đặt ở int_orders / dim_geography / dim_customer.
select
    customer_id,
    customer_unique_id,
    customer_zip_code_prefix,
    customer_city,
    customer_state
from {{ source('staging', 'customers') }}
