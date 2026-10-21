"""Ghi nhật ký vào schema etl_log (sql/init/02_etl_log.sql; ghi lúc nào: pipeline_rules.md A3, B5).

Mọi hàm nhận 1 kết nối autocommit (db.connect(autocommit=True)): mỗi dòng log lưu ngay,
nên khi phần nạp staging bị hoàn tác (rollback) thì log vẫn còn để biết chuyện gì đã xảy ra.
"""
import pandas as pd

MAX_ERROR_LENGTH = 1000


def short_error(exc):
    """Thông báo lỗi ngắn gọn để ghi vào cột error_message."""
    text = f'{type(exc).__name__}: {exc}'.strip()
    return text[:MAX_ERROR_LENGTH]


# ---------- pipeline_run: 1 dòng = 1 lần chạy ----------

def start_run(conn, pipeline_name, load_type, batch_id, lset, cet, triggered_by='manual'):
    """Ghi lần chạy mới với status RUNNING TRƯỚC khi làm gì (lần chạy chết giữa chừng vẫn để lại dấu vết). Trả về run_id."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO etl_log.pipeline_run (pipeline_name, load_type, batch_id, lset, cet, triggered_by)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING run_id
            """,
            (pipeline_name, load_type, batch_id, lset, cet, triggered_by),
        )
        return cur.fetchone()[0]


def finish_run(conn, run_id):
    """Kết thúc thành công. Với Incremental, cet của dòng này thành LSET của lần sau."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE etl_log.pipeline_run SET status = 'SUCCESS', finished_at = now(), error_message = NULL "
            "WHERE run_id = %s",
            (run_id,),
        )


def fail_run(conn, run_id, message):
    """Kết thúc thất bại. LSET không tiến -> lần sau nạp lại đúng batch này."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE etl_log.pipeline_run SET status = 'FAILED', finished_at = now(), error_message = %s "
            "WHERE run_id = %s",
            (message, run_id),
        )


# ---------- table_load: 1 dòng = 1 bảng trong 1 lần chạy ----------

def start_table(conn, run_id, table, rows_source):
    """Bắt đầu nạp 1 bảng: status RUNNING, rows_source = số dòng đọc được từ file."""
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO etl_log.table_load (run_id, table_name, rows_source) VALUES (%s, %s, %s)",
            (run_id, table, rows_source),
        )


def record_table(conn, run_id, table, inserted, updated, rejected=0, deleted=0):
    """Ghi số dòng của 1 bảng vừa MERGE xong.

    status vẫn để RUNNING: dữ liệu mới chỉ thật sự vào staging khi cả batch commit (runner.py),
    lúc đó mark_tables_success() mới đổi sang SUCCESS.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE etl_log.table_load
            SET rows_inserted = %s, rows_updated = %s, rows_rejected = %s, rows_deleted = %s, finished_at = now()
            WHERE run_id = %s AND table_name = %s
            """,
            (inserted, updated, rejected, deleted, run_id, table),
        )


def mark_tables_success(conn, run_id):
    """Batch đã commit: mọi bảng của lần chạy -> SUCCESS."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE etl_log.table_load SET status = 'SUCCESS' WHERE run_id = %s AND status = 'RUNNING'",
            (run_id,),
        )


def fail_tables(conn, run_id, failed_table, message):
    """Batch bị hoàn tác: bảng gây lỗi ghi đúng lỗi; các bảng đã MERGE trước đó cũng FAILED vì dữ liệu đã bị hoàn tác."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE etl_log.table_load
            SET status = 'FAILED',
                finished_at = coalesce(finished_at, now()),
                error_message = CASE WHEN table_name = %s THEN %s
                                     ELSE 'Đã hoàn tác (rollback) vì lần chạy bị lỗi ở bước sau' END
            WHERE run_id = %s AND status = 'RUNNING'
            """,
            (failed_table, message, run_id),
        )


def table_summary(conn, run_id):
    """Kết quả từng bảng của 1 lần chạy - để hiện trong Mage sau khi chạy."""
    return pd.read_sql(
        """
        SELECT run_id, table_name, rows_source, rows_inserted, rows_updated, rows_rejected, rows_deleted, status
        FROM etl_log.table_load
        WHERE run_id = %(run_id)s
        ORDER BY started_at, table_name
        """,
        conn,
        params={'run_id': int(run_id)},
    )
