import pandas as pd

from olist_etl.utils import etl_log
from olist_etl.utils.batch_files import manifest_row, manifest_row_by_lset
from olist_etl.utils.db import connect

if 'transformer' not in globals():
    from mage_ai.data_preparation.decorators import transformer


@transformer
def set_cet(lset_info, *args, **kwargs):
    """Incremental - bước 2 (Set CET): xác định batch cần nạp và khoảng [LSET, CET).

    Tra manifest.csv dòng có lset = LSET -> batch_id và CET = cet của dòng đó,
    rồi mở lần chạy mới: etl_log.pipeline_run status RUNNING.
    Đã nạp hết batch (action DONE) -> không làm gì, không ghi pipeline_run.
    Lần SUCCESS gần nhất đã khác lúc get_lset đọc (output cũ của get_lset) -> dừng, không mở lần chạy.
    """
    info = lset_info.iloc[0]
    if info['action'] == 'DONE':
        return lset_info

    if info['action'] == 'RERUN':
        batch = manifest_row(info['last_batch_id'])
    else:
        batch = manifest_row_by_lset(info['lset'])
        if batch is None:
            raise ValueError(f"manifest.csv không có batch nào có lset = {info['lset']}")

    triggered_by = kwargs.get('triggered_by') or 'manual'   # 'schedule' khi gắn trigger lịch (Seminar 3)
    conn = connect(autocommit=True)
    try:
        # Chạy riêng block này trong editor thì lset_info là output CŨ của get_lset -> LSET có thể đã đổi
        last = etl_log.last_success_run(conn)
        if last is None or last['run_id'] != int(info['last_run_id']):
            raise etl_log.StaleRunError(
                f"Lần SUCCESS gần nhất giờ là run_id {last['run_id'] if last else None}, không phải "
                f"run_id {info['last_run_id']} mà get_lset đã đọc: block đang nhận output cũ của get_lset "
                '(chạy riêng block trong editor Mage). Hãy chạy cả pipeline: Triggers -> Run@once'
            )
        run_id = etl_log.start_run(conn, 'incremental_load', 'INCREMENTAL', batch['batch_id'],
                                   batch['lset'], batch['cet'], triggered_by)
    finally:
        conn.close()

    print(f"Bắt đầu Incremental: run_id = {run_id}, batch {batch['batch_id']}, "
          f"[LSET, CET) = [{batch['lset']}, {batch['cet'] or 'không giới hạn'})")
    return pd.DataFrame([{
        'action': info['action'],
        'run_id': run_id,
        'batch_id': batch['batch_id'],
        'lset': batch['lset'],
        'cet': batch['cet'],
    }])
