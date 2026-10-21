import pandas as pd

from olist_etl.utils import etl_log
from olist_etl.utils.batch_files import manifest_row
from olist_etl.utils.db import connect

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader


@data_loader
def start_full_run(*args, **kwargs):
    """Full Load - bước 1: mở lần chạy mới.

    Đổi các lần chạy cũ còn kẹt RUNNING thành FAILED, lấy khoảng nạp của batch FULL trong manifest.csv
    (lset trống, cet = 2018-01-01) rồi ghi etl_log.pipeline_run status RUNNING. Trả về run_id cho các block sau.
    """
    batch = manifest_row('FULL')
    triggered_by = kwargs.get('triggered_by') or 'manual'   # 'schedule' khi gắn trigger lịch (Seminar 3)

    conn = connect(autocommit=True)
    try:
        interrupted = etl_log.fail_interrupted_runs(conn)
        if interrupted:
            print(f'Lần chạy bị ngắt giữa chừng -> FAILED: run_id {interrupted}')
        run_id = etl_log.start_run(conn, 'full_load', 'FULL', 'FULL', batch['lset'], batch['cet'], triggered_by)
    finally:
        conn.close()

    print(f"Bắt đầu Full Load: run_id = {run_id}, batch FULL, cet = {batch['cet']}")
    return pd.DataFrame([{
        'run_id': run_id,
        'batch_id': 'FULL',
        'load_type': 'FULL',
        'lset': batch['lset'],
        'cet': batch['cet'],
    }])
