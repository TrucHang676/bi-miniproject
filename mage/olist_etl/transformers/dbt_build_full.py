from olist_etl.utils.dbt_runner import run_dbt_build

if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer


@transformer
def dbt_build_full(summary, *args, **kwargs):
    """Full Load - bước 3 (Transform, BS-34): dbt build --full-refresh dựng lại dds từ đầu.

    Staging vừa được làm lại từ đầu (TRUNCATE + batch FULL) nên dds cũng dựng lại từ đầu: --full-refresh
    xóa và tạo lại cả model incremental (dim_customer, dim_geography) -> khóa cấp lại từ 1.
    Kết quả từng node ghi vào etl_log.dbt_result.
    dbt lỗi -> lần chạy ghi FAILED, finish_full_run không chạy; Incremental bị chặn cho tới khi
    chạy lại full_load thành công (staging đã làm lại nhưng dds chưa dựng xong).
    """
    return run_dbt_build(int(summary['run_id'].iloc[0]), full_refresh=True)
