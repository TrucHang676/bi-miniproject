-- Dùng ĐÚNG tên schema khai báo bằng +schema trong dbt_project.yml (dbt_stg, dbt_int, dds, dq).
-- Mặc định dbt ghép "<schema trong profiles.yml>_<+schema>" (VD dbt_stg_dds) - không khớp schema dds có sẵn
-- do sql/init/00_schemas.sql tạo. Model không khai +schema thì vào schema của profiles.yml.
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
