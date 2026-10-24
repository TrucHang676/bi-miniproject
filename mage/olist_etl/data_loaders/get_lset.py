import pandas as pd

from olist_etl.utils import etl_log
from olist_etl.utils.db import connect

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader

TIME_FORMAT = '%Y-%m-%d %H:%M:%S'


def _is_true(value):
    return str(value).strip().lower() in ('true', '1', 'yes')


@data_loader
def get_lset(*args, **kwargs):
    """Incremental - bước 1 (Get LSET, Bài 4 slide 49/67): đọc LSET từ metadata etl_log.

    LSET = cet của lần chạy SUCCESS gần nhất trong etl_log.pipeline_run.
    * chưa có lần SUCCESS nào  -> báo lỗi: phải chạy full_load trước
    * cet IS NULL              -> đã nạp hết batch (lần gần nhất là 2018-09+): dừng, không ghi pipeline_run
    * biến rerun_last = true   -> chạy lại đúng batch của lần SUCCESS gần nhất (B2.3)
    * staging đã đi trước LSET (lần chạy sau đã nạp staging nhưng lỗi ở bước dbt - B12) -> Full Load: báo lỗi,
      phải chạy lại full_load; Incremental: nạp lại đúng batch đó (rerun_last = true thì báo lỗi)
    """
    rerun_last = _is_true(kwargs.get('rerun_last', False))

    conn = connect(autocommit=True)
    try:
        interrupted = etl_log.fail_interrupted_runs(conn)
        if interrupted:
            print(f'Lần chạy bị ngắt giữa chừng -> FAILED: run_id {interrupted}')
        last = etl_log.last_success_run(conn)
        ahead = etl_log.check_staging_in_sync(conn, last, rerun_last) if last else None
    finally:
        conn.close()

    if last is None:
        raise ValueError('Chưa có lần chạy SUCCESS nào trong etl_log.pipeline_run: hãy chạy pipeline full_load trước')
    if ahead is not None:
        print(f"run_id {ahead['run_id']} đã nạp staging batch {ahead['batch_id']} nhưng chưa xong (lỗi ở bước dbt hoặc "
              'bị ngắt) -> nạp lại batch này (MERGE ra 0 INSERT / 0 UPDATE) rồi chạy dbt')

    if rerun_last:
        if last['batch_id'] == 'FULL':
            raise ValueError('Lần SUCCESS gần nhất là Full Load (batch FULL): muốn nạp lại thì chạy pipeline full_load')
        action, lset = 'RERUN', last['lset']
        print(f"Chạy lại batch {last['batch_id']} của lần SUCCESS gần nhất (run_id {last['run_id']})")
    elif last['cet'] is None:
        action, lset = 'DONE', None
        print(f"Đã nạp hết batch: lần SUCCESS gần nhất (run_id {last['run_id']}) là batch cuối {last['batch_id']}")
    else:
        action, lset = 'LOAD', last['cet']
        print(f"LSET = {lset:{TIME_FORMAT}} (cet của run_id {last['run_id']}, batch {last['batch_id']})")

    return pd.DataFrame([{
        'action': action,
        'lset': lset.strftime(TIME_FORMAT) if lset is not None else None,
        'last_run_id': last['run_id'],
        'last_batch_id': last['batch_id'],
    }])
