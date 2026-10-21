from olist_etl.utils import etl_log
from olist_etl.utils.db import connect

if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter


@data_exporter
def set_lset(summary, *args, **kwargs):
    """Incremental - bước 4 (Set LSET): ghi lần chạy SUCCESS.

    Dòng pipeline_run này đã lưu cet, nên lần chạy sau đọc ra làm LSET mới (LSET mới = CET).
    Chỉ chạy tới đây khi bước 3 thành công; lỗi thì bước 3 đã ghi FAILED và LSET giữ nguyên.
    """
    if 'action' in summary.columns and summary['action'].iloc[0] == 'DONE':
        print('Đã nạp hết batch - không có gì để nạp, không ghi etl_log.pipeline_run')
        return

    run_id = int(summary['run_id'].iloc[0])
    conn = connect(autocommit=True)
    try:
        etl_log.finish_run(conn, run_id)
    finally:
        conn.close()
    print(f'Incremental thành công: run_id = {run_id} -> CET của lần chạy này là LSET của lần sau')
