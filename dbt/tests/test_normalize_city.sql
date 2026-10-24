-- Kiểm tra macro normalize_city (R1) bằng bảng ví dụ: mỗi dòng 1 ví dụ (giá trị gốc, mã bang, kết quả mong đợi).
-- Trả về các ví dụ SAI -> 0 dòng = đạt. Ví dụ sai được lưu vào bảng dq.test_normalize_city (store_failures),
-- hiện cả cột mong đợi lẫn kết quả thật để dễ sửa.
with cases (city, state, expected) as (
    values
        ('São Paulo',                       'SP', 'sao paulo'),         -- B1 bỏ dấu, chữ thường
        ('maua/sao paulo',                  'SP', 'maua'),              -- B2 cắt từ dấu /
        ('arraial d''ajuda (porto seguro)', 'BA', 'arraial d''ajuda'),  -- B3 bỏ phần trong ngoặc
        ('mogi-mirim',                      'SP', 'mogi mirim'),        -- B4 gạch nối -> khoảng trắng
        ('  sao   paulo ',                  'SP', 'sao paulo'),         -- B5 gộp khoảng trắng
        ('sao paulo - sp',                  'SP', 'sao paulo'),         -- B6 bỏ mã bang của chính dòng ở cuối
        ('sp',                              'SP', null),                -- B7 chỉ còn mã bang
        ('loja@email.com',                  'SP', null),                -- B7 email
        ('04482255',                        'SP', null),                -- B7 toàn chữ số
        ('rio de janeiro',                  'RJ', 'rio de janeiro')     -- trùng TÊN bang nhưng là thành phố thật
)
select
    city,
    state,
    expected,
    {{ normalize_city('city', 'state') }} as actual
from cases
where {{ normalize_city('city', 'state') }} is distinct from expected
