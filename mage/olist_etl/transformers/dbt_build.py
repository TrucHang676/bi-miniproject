from olist_etl.utils.dbt_runner import run_dbt_build

if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer


@transformer
def dbt_build(summary, *args, **kwargs):
    """Incremental - bước 4 (Transform, BS-34): dbt build cập nhật dds từ staging vừa nạp.

    seed -> model -> test theo đúng thứ tự phụ thuộc; kết quả từng node ghi vào etl_log.dbt_result.
    Model incremental (dim_customer, dim_geography) giữ khóa cũ, khách / thành phố mới nhận khóa nối tiếp.
    dbt lỗi (model lỗi, test FAIL) -> lần chạy ghi FAILED, set_lset không chạy nên LSET không tiến;
    staging đã nạp vẫn giữ, lần sau nạp lại đúng batch này (0 INSERT / 0 UPDATE) rồi chạy dbt lại.
    """
    if 'action' in summary.columns and summary['action'].iloc[0] == 'DONE':
        return summary   # đã nạp hết batch: không có dữ liệu mới, không chạy dbt
    return run_dbt_build(int(summary['run_id'].iloc[0]))
