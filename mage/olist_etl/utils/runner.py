"""Nạp trọn 1 batch vào staging - phần chung của full_load và incremental_load (pipeline_rules.md A3, B3, B4).

Một lần nạp:
    1. file_exists cho mọi file của batch                         (quality.py)
    2. từng bảng theo thứ tự cha -> con:
         đọc file -> table_load RUNNING -> kiểm tra chất lượng (dòng hỏng -> dq) -> MERGE dòng sạch
    3. Incremental: xóa mềm theo deleted_orders.csv nếu có          (soft_delete.py)
    4. COMMIT -> table_load SUCCESS

Hai kết nối:
* staging_conn: 1 transaction cho cả batch. Lỗi ở bất kỳ đâu -> ROLLBACK, staging như chưa chạy.
* log_conn    : autocommit, ghi etl_log / dq từng bước -> lỗi vẫn còn log.
"""
from olist_etl.utils import etl_log, quality
from olist_etl.utils.batch_files import batch_file_path, manifest_row, read_csv
from olist_etl.utils.db import connect
from olist_etl.utils.settings import TABLES, tables_for
from olist_etl.utils.soft_delete import TABLE as DELETED_TABLE
from olist_etl.utils.soft_delete import process_deleted_orders
from olist_etl.utils.staging import merge_into_staging, truncate_staging


def load_batch(run_id, batch_id, load_type, lset=None, cet=None, truncate_first=False):
    """Nạp các file của batch. Trả về DataFrame kết quả từng bảng (etl_log.table_load).

    lset, cet      : khoảng nạp của batch - dùng cho phép kiểm tra in_window của file xóa đơn.
    truncate_first : xóa sạch staging trước khi nạp (Full Load làm lại từ đầu - B2.1).
    Lỗi: ghi FAILED cho bảng đang nạp và lần chạy, rồi báo lỗi lại cho Mage (block hiện màu đỏ).
    """
    tables = tables_for(load_type)
    log_conn = connect(autocommit=True)   # không mở được thì cũng không ghi log được -> để Mage báo lỗi
    staging_conn = None
    current_table = None
    try:
        # Mọi lỗi từ đây (kể cả thiếu manifest, không mở được kết nối thứ hai) đều ghi FAILED đúng nguyên nhân
        expected = manifest_row(batch_id)   # số dòng mong đợi từng file (row_count_match)
        staging_conn = connect(autocommit=False)
        with staging_conn.cursor() as cur:
            quality.check_files_exist(log_conn, run_id, batch_id, tables, batch_file_path)

            if truncate_first:
                truncate_staging(cur, list(TABLES))
                print('Đã TRUNCATE 8 bảng staging')

            for table in tables:
                current_table = table
                try:
                    df = read_csv(batch_file_path(batch_id, table))
                except Exception as exc:
                    etl_log.start_table(log_conn, run_id, table, None)
                    quality.check_unreadable(log_conn, run_id, table, exc)
                etl_log.start_table(log_conn, run_id, table, len(df))

                clean, rejected = quality.validate_table(
                    log_conn, cur, run_id, batch_id, table, df, expected.get(table))
                inserted, updated = merge_into_staging(cur, table, clean)
                etl_log.record_table(log_conn, run_id, table, inserted, updated, rejected)
                print(f'{table}: đọc {len(df)} dòng, loại {rejected} -> INSERT {inserted}, UPDATE {updated}')

            if load_type == 'INCREMENTAL':
                current_table = DELETED_TABLE
                deleted = process_deleted_orders(log_conn, cur, run_id, batch_id, lset, cet)
                if deleted is not None:
                    etl_log.record_deleted(log_conn, run_id, deleted)
                    print(f'deleted_orders: đánh dấu xóa mềm {deleted} đơn')

        current_table = None
        staging_conn.commit()
        etl_log.mark_tables_success(log_conn, run_id)
        return etl_log.table_summary(log_conn, run_id)

    except Exception as exc:
        if staging_conn is not None:
            staging_conn.rollback()
        message = etl_log.short_error(exc) if not isinstance(exc, quality.BatchCheckFailed) else str(exc)
        if current_table and not isinstance(exc, quality.BatchCheckFailed):
            message = f'Bảng {current_table}: {message}'
        etl_log.fail_tables(log_conn, run_id, current_table, message)
        etl_log.fail_run(log_conn, run_id, message)
        print(f'LỖI - đã hoàn tác staging, ghi FAILED cho run_id {run_id}: {message}')
        raise

    finally:
        if staging_conn is not None:
            staging_conn.close()
        log_conn.close()
