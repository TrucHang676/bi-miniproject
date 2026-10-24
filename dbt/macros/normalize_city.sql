{#-
    R1 (docs/source_to_target_mapping.md mục 1): chuẩn hóa tên thành phố, 7 bước B1 -> B7.
    Trả về MỘT BIỂU THỨC SQL (không phải câu select) - gọi trong model như một hàm:
        {{ normalize_city('customer_city', 'customer_state') }}
    Kết quả NULL khi giá trị không phải tên thành phố (B7); nơi dùng tự coalesce thành 'Không xác định'.
    Dùng chung cho dim_geography, dim_customer, dim_seller và lookup geography_key -> mọi nơi khớp nhau.
    Cần extension unaccent (sql/init/00_schemas.sql).

    Đọc từ TRONG ra NGOÀI:
      B1  unaccent(lower(trim(city)))          'São Paulo'                  -> 'sao paulo'
      B2  cắt từ / \ , đầu tiên trở đi           'maua/sao paulo'             -> 'maua'
      B3  bỏ phần trong ngoặc ( )                'arraial d''ajuda (porto…)'  -> 'arraial d''ajuda '
      B4  '-' -> khoảng trắng                    'mogi-mirim'                 -> 'mogi mirim'
      B5  gộp nhiều khoảng trắng, trim           '  sao   paulo '             -> 'sao paulo'
      B6  bỏ mã bang CỦA CHÍNH DÒNG ở cuối       'sao paulo sp' (bang SP)     -> 'sao paulo'
      B7  NULL nếu chỉ còn mã bang / có @ / toàn chữ số / rỗng  ('sp', email, '04482255')
          -> thay cả chuỗi khớp mẫu rác bằng '' rồi nullif(…, '').
    KHÔNG coi tên trùng tên bang là rác: 'sao paulo', 'rio de janeiro' là thành phố thật (B7 chỉ so với MÃ bang).
-#}
{% macro normalize_city(city, state) -%}
nullif(
    regexp_replace(
        trim(regexp_replace(
            trim(regexp_replace(
                replace(
                    regexp_replace(
                        regexp_replace(
                            unaccent(lower(trim({{ city }}))),
                            '[/\\,].*$', ''),
                        '\([^)]*\)', '', 'g'),
                    '-', ' '),
                '\s+', ' ', 'g')),
            '\s' || coalesce(lower({{ state }}), '') || '$', '')),
        '^(.*@.*|[0-9]+|' || coalesce(lower({{ state }}), '') || ')$', ''),
    '')
{%- endmacro %}
