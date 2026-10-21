from olist_etl.utils import etl_log
from olist_etl.utils.db import connect

if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter


@data_exporter
def finish_full_run(summary, *args, **kwargs):
    """Full Load - bước 3: đóng lần chạy, etl_log.pipeline_run -> SUCCESS.

    Chỉ chạy tới đây khi bước 2 thành công (lỗi thì bước 2 đã ghi FAILED và Mage dừng pipeline).
    Sau bước này, cet = 2018-01-01 của lần chạy thành LSET cho Incremental kế tiếp (nạp 2018-01).
    """
    run_id = int(summary['run_id'].iloc[0])
    conn = connect(autocommit=True)
    try:
        etl_log.finish_run(conn, run_id)
    finally:
        conn.close()
    print(f'Full Load thành công: run_id = {run_id}')
