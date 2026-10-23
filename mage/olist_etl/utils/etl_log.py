"""Ghi nhật ký vào schema etl_log (sql/init/02_etl_log.sql; ghi lúc nào: pipeline_rules.md A3, B5).

Mọi hàm nhận 1 kết nối autocommit (db.connect(autocommit=True)): mỗi dòng log lưu ngay,
nên khi phần nạp staging bị hoàn tác (rollback) thì log vẫn còn để biết chuyện gì đã xảy ra.
"""
import pandas as pd
from psycopg2.extras import Json, execute_values

MAX_ERROR_LENGTH = 1000
INTERRUPTED_MESSAGE = 'Bị ngắt giữa chừng'


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


def fail_interrupted_runs(conn):
    """Lần chạy cũ còn kẹt RUNNING (container dừng, tắt máy giữa chừng...) -> FAILED (pipeline_rules.md B2.4).

    Gọi ở đầu mỗi lần chạy mới. Trả về danh sách run_id đã đổi.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE etl_log.pipeline_run
            SET status = 'FAILED', finished_at = now(), error_message = %s
            WHERE status = 'RUNNING'
            RETURNING run_id
            """,
            (INTERRUPTED_MESSAGE,),
        )
        run_ids = [row[0] for row in cur.fetchall()]
        if run_ids:
            cur.execute(
                """
                UPDATE etl_log.table_load
                SET status = 'FAILED', finished_at = coalesce(finished_at, now()), error_message = %s
                WHERE run_id = ANY(%s) AND status = 'RUNNING'
                """,
                (INTERRUPTED_MESSAGE, run_ids),
            )
        return run_ids


def last_success_run(conn):
    """Lần chạy SUCCESS gần nhất (dict run_id, pipeline_name, batch_id, lset, cet) hoặc None. Dùng cho bước Get LSET."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT run_id, pipeline_name, batch_id, lset, cet
            FROM etl_log.pipeline_run
            WHERE status = 'SUCCESS'
            ORDER BY run_id DESC
            LIMIT 1
            """
        )
        row = cur.fetchone()
    if row is None:
        return None
    return dict(zip(['run_id', 'pipeline_name', 'batch_id', 'lset', 'cet'], row))


class StaleRunError(Exception):
    """Block nhận thông tin của lần chạy đã kết thúc (output cũ của block trước) -> dừng, không ghi gì."""


def ensure_running(conn, run_id):
    """Dừng nếu lần chạy run_id không còn RUNNING.

    Bấm ▶ chạy riêng 1 block trong editor Mage: Mage đưa vào output CŨ của block trước, tức run_id của
    lần chạy đã kết thúc. Không chặn thì block ghi đè lần chạy đó (VD SUCCESS -> FAILED) và LSET bị lùi.
    """
    with conn.cursor() as cur:
        cur.execute('SELECT status FROM etl_log.pipeline_run WHERE run_id = %s', (run_id,))
        row = cur.fetchone()
    status = row[0] if row else None
    if status != 'RUNNING':
        state = f'đã {status}' if status else 'không có trong etl_log.pipeline_run'
        raise StaleRunError(
            f'run_id {run_id} {state}, không còn RUNNING: block đang nhận output cũ của block trước '
            '(chạy riêng block trong editor Mage). Hãy chạy cả pipeline: Triggers -> Run@once'
        )


def finish_run(conn, run_id):
    """Kết thúc thành công. Với Incremental, cet của dòng này thành LSET của lần sau.

    Chỉ đổi lần chạy còn RUNNING (ensure_running): không biến lần chạy đã FAILED thành SUCCESS.
    """
    ensure_running(conn, run_id)
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE etl_log.pipeline_run SET status = 'SUCCESS', finished_at = now(), error_message = NULL "
            "WHERE run_id = %s AND status = 'RUNNING'",
            (run_id,),
        )


def fail_run(conn, run_id, message):
    """Kết thúc thất bại. LSET không tiến -> lần sau nạp lại đúng batch này.

    Chỉ đổi lần chạy còn RUNNING: không ghi đè lần chạy đã kết thúc (VD SUCCESS -> FAILED).
    """
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE etl_log.pipeline_run SET status = 'FAILED', finished_at = now(), error_message = %s "
            "WHERE run_id = %s AND status = 'RUNNING'",
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


def record_deleted(conn, run_id, deleted):
    """Số đơn bị đánh dấu xóa mềm (B6) - ghi ở dòng table_name = 'orders'."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE etl_log.table_load SET rows_deleted = %s WHERE run_id = %s AND table_name = 'orders'",
            (deleted, run_id),
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


# ---------- quality_check + dq.rejected_rows: kết quả kiểm tra chất lượng (B4.2, B4.3) ----------

def add_check(conn, run_id, table, check_name, failed_rows, status, detail=None):
    """1 dòng / 1 phép kiểm tra trên 1 bảng, ghi cả khi PASS."""
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO etl_log.quality_check (run_id, table_name, check_name, failed_rows, status, detail)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (run_id, table, check_name, failed_rows, status, detail),
        )


def add_rejected(conn, run_id, table, check_name, rows):
    """Ghi các dòng bị loại vào dq.rejected_rows. rows = [(source_row, row_data dict, reason), ...].

    Phải gọi SAU add_check của cùng phép kiểm tra: dq.rejected_rows có khóa ngoại về etl_log.quality_check.
    """
    if not rows:
        return
    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO dq.rejected_rows (run_id, table_name, check_name, source_row, row_data, reason)
            VALUES %s
            """,
            [(run_id, table, check_name, source_row, Json(row_data), reason)
             for source_row, row_data, reason in rows],
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
