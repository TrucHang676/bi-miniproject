-- dim_date: 1 dòng / 1 ngày dương lịch, 01/01/2016 -> 31/12/2018 (1.096 dòng; 2016 là năm nhuận).
-- Tự sinh (không có nguồn) - SCD Type 0. Khoảng ngày phủ đủ mọi ngày fact tham chiếu: ngày mua (04/09/2016 ->
-- 17/10/2018), ngày trả lời review (07/10/2016 -> 29/10/2018), ngày giao dự kiến (tới 12/11/2018).
-- Role-playing: ngày đặt hàng (cả 3 fact) và ngày trả lời đánh giá (fact_review). Không có dòng -1 (R3).
with days as (
    select d::date as full_date
    from generate_series('2016-01-01'::date, '2018-12-31'::date, interval '1 day') as d
),

parts as (
    select
        full_date,
        extract(day from full_date)::smallint     as day_of_month,
        extract(isodow from full_date)::smallint  as day_of_week,   -- ISO: 1 = Thứ Hai … 7 = Chủ nhật (không dùng DOW: 0 = CN)
        extract(month from full_date)::smallint   as month,
        extract(quarter from full_date)::smallint as quarter,
        extract(year from full_date)::smallint    as year
    from days
)

select
    to_char(full_date, 'YYYYMMDD')::int as date_key,      -- R3: khóa đọc được, VD 20180315
    full_date,
    day_of_month,
    day_of_week,
    (case day_of_week
        when 1 then 'Thứ Hai'
        when 2 then 'Thứ Ba'
        when 3 then 'Thứ Tư'
        when 4 then 'Thứ Năm'
        when 5 then 'Thứ Sáu'
        when 6 then 'Thứ Bảy'
        when 7 then 'Chủ nhật'
    end)::varchar(20)                       as day_name,          -- Power BI: Sort by column = day_of_week
    (day_of_week in (6, 7))                 as is_weekend,
    month,
    format('Tháng %s', month)::varchar(20)  as month_name,        -- Power BI: Sort by column = month
    (year * 100 + month)::int               as year_month,        -- khóa cấp Tháng: không gộp 03/2017 với 03/2018
    quarter,
    year,
    (full_date between '2017-01-01' and '2018-08-31') as is_analysis_period   -- phạm vi xu hướng (99,6% số đơn)
from parts
