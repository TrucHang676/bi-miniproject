import pandas as pd

from olist_etl.utils.runner import load_batch

if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer


def _value(x):
    """Ô trống (batch cuối 2018-09+ không có cet) -> None; Mage có thể đổi None thành NaN khi chuyển giữa các block."""
    return None if pd.isna(x) else x


@transformer
def extract_load(run_info, *args, **kwargs):
    """Incremental - bước 3 (Extract + Load): nạp 5 file của batch vào staging bằng MERGE.

    Thứ tự customers -> orders -> order_items, order_payments -> order_reviews, sau cùng xóa mềm
    theo deleted_orders.csv nếu batch có file này. Kiểm tra chất lượng trước khi MERGE; cả batch là
    1 transaction: lỗi thì staging trở về như trước khi chạy, lần chạy ghi FAILED, LSET không tiến.
    """
    run = run_info.iloc[0]
    if run['action'] == 'DONE':
        return run_info
    return load_batch(int(run['run_id']), run['batch_id'], 'INCREMENTAL',
                      lset=_value(run['lset']), cet=_value(run['cet']))
