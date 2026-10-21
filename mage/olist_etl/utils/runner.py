"""Nạp trọn 1 batch vào staging - phần chung của full_load và incremental_load (pipeline_rules.md A3, B3, B4).

Hai kết nối:
* staging_conn: 1 transaction cho cả batch. Lỗi ở bất kỳ bảng nào -> ROLLBACK, staging như chưa chạy.
* log_conn    : autocommit, ghi etl_log từng bước -> lỗi vẫn còn log.
"""
from olist_etl.utils import etl_log
from olist_etl.utils.batch_files import batch_file_path, read_csv
from olist_etl.utils.db import connect
from olist_etl.utils.settings import TABLES, tables_for
from olist_etl.utils.staging import merge_into_staging, truncate_staging


def load_batch(run_id, batch_id, load_type, truncate_first=False):
    """Nạp các file của batch theo thứ tự cha -> con. Trả về DataFrame kết quả từng bảng (etl_log.table_load).

    truncate_first=True: xóa sạch staging trước khi nạp (Full Load làm lại từ đầu - B2.1).
    Lỗi: ghi FAILED cho bảng đang nạp và lần chạy, rồi báo lỗi lại cho Mage (block hiện màu đỏ).
    """
    tables = tables_for(load_type)
    log_conn = connect(autocommit=True)
    staging_conn = connect(autocommit=False)
    current_table = None
    try:
        with staging_conn.cursor() as cur:
            if truncate_first:
                truncate_staging(cur, list(TABLES))
                print('Đã TRUNCATE 8 bảng staging')

            for table in tables:
                current_table = table
                df = read_csv(batch_file_path(batch_id, table))
                etl_log.start_table(log_conn, run_id, table, len(df))

                inserted, updated = merge_into_staging(cur, table, df)
                etl_log.record_table(log_conn, run_id, table, inserted, updated)
                print(f'{table}: đọc {len(df)} dòng -> INSERT {inserted}, UPDATE {updated}')

        current_table = None
        staging_conn.commit()
        etl_log.mark_tables_success(log_conn, run_id)
        return etl_log.table_summary(log_conn, run_id)

    except Exception as exc:
        staging_conn.rollback()
        message = etl_log.short_error(exc)
        if current_table:
            message = f'Bảng {current_table}: {message}'
        etl_log.fail_tables(log_conn, run_id, current_table, message)
        etl_log.fail_run(log_conn, run_id, message)
        print(f'LỖI - đã hoàn tác staging, ghi FAILED cho run_id {run_id}: {message}')
        raise

    finally:
        staging_conn.close()
        log_conn.close()
