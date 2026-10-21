"""Xóa mềm đơn hàng bị xóa ở nguồn theo file deleted_orders.csv (pipeline_rules.md B6, sql/init/04_soft_delete.sql).

Incremental chỉ thấy dòng CÓ MẶT trong batch nên không tự biết đơn nào bị xóa (Bài 4, slide 52-53):
nguồn báo xóa bằng file tùy chọn deleted_orders.csv, kho chỉ đánh dấu _is_deleted = TRUE (không xóa hẳn,
không đụng bảng con - dbt tự lọc qua order_id). Làm SAU khi MERGE xong mọi bảng của batch (B3).
"""
import os

import pandas as pd

from olist_etl.utils import etl_log
from olist_etl.utils.batch_files import read_csv
from olist_etl.utils.quality import BatchCheckFailed, check_unreadable, reject_rows
from olist_etl.utils.settings import BATCH_DIR
from olist_etl.utils.staging import copy_frame

TABLE = 'deleted_orders'
COLUMNS = ['order_id', 'deleted_at', 'batch_id']


def deleted_file_path(batch_id):
    return os.path.join(BATCH_DIR, batch_id, f'{TABLE}.csv')


def process_deleted_orders(log, cur, run_id, batch_id, lset, cet):
    """Kiểm tra file xóa đơn rồi đánh dấu xóa mềm. Trả về số đơn bị đánh dấu, None nếu batch không có file.

    Kiểm tra (table_name = 'deleted_orders'):
      columns_match  đúng 3 cột order_id, deleted_at, batch_id   FAIL - dừng cả batch
      not_null_key   order_id không rỗng                          WARN - loại dòng -> dq
      key_exists     đơn có trong staging.orders, chưa bị xóa     WARN - loại dòng -> dq
      in_window      LSET <= deleted_at < CET                     WARN - loại dòng -> dq
    """
    path = deleted_file_path(batch_id)
    if not os.path.isfile(path):
        return None

    try:
        df = read_csv(path)
    except Exception as exc:  # file hỏng cấu trúc
        check_unreadable(log, run_id, TABLE, exc)

    if list(df.columns) != COLUMNS:
        detail = 'cần đúng 3 cột order_id, deleted_at, batch_id; file có: ' + ', '.join(df.columns)
        etl_log.add_check(log, run_id, TABLE, 'columns_match', 0, 'FAIL', detail)
        raise BatchCheckFailed(f'columns_match không đạt ở {TABLE}: {detail}')
    etl_log.add_check(log, run_id, TABLE, 'columns_match', 0, 'PASS')

    null_ids = df['order_id'].isna()
    df = reject_rows(log, run_id, TABLE, 'not_null_key', df,
                     pd.Series('order_id rỗng', index=df.index[null_ids], dtype=object))

    # key_exists + in_window tính bằng SQL trong cùng transaction -> thấy cả đơn vừa MERGE ở batch này
    status = pd.DataFrame(columns=['key_ok', 'window_ok'])
    if not df.empty:
        copy_frame(cur, 'tmp_deleted_check', df.assign(_row=(df.index + 1).astype(str)),
                   ['order_id', 'deleted_at', '_row'])
        cur.execute(
            """
            SELECT d._row::int,
                   EXISTS (SELECT 1 FROM staging.orders o WHERE o.order_id = d.order_id AND NOT o._is_deleted),
                   CASE WHEN pg_input_is_valid(d.deleted_at, 'timestamp')
                        THEN d.deleted_at::timestamp >= %(lset)s
                             AND (%(cet)s::timestamp IS NULL OR d.deleted_at::timestamp < %(cet)s::timestamp)
                        ELSE false END
            FROM tmp_deleted_check d
            """,
            {'lset': lset, 'cet': cet},
        )
        status = pd.DataFrame(
            {row - 1: (key_ok, window_ok) for row, key_ok, window_ok in cur.fetchall()},
            index=['key_ok', 'window_ok'],
        ).T

    bad_key = status.index[~status['key_ok'].astype(bool)]
    df = reject_rows(log, run_id, TABLE, 'key_exists', df,
                     pd.Series('đơn không có trong staging.orders hoặc đã bị xóa trước đó',
                               index=bad_key, dtype=object))

    window = f'[{lset}, {cet or "không giới hạn"})'
    bad_window = [i for i in df.index if not bool(status.loc[i, 'window_ok'])]
    df = reject_rows(log, run_id, TABLE, 'in_window', df,
                     pd.Series(f'deleted_at rỗng, sai định dạng hoặc nằm ngoài khoảng {window}',
                               index=bad_window, dtype=object))

    if df.empty:
        return 0
    copy_frame(cur, 'tmp_deleted_orders', df, COLUMNS)
    cur.execute(
        """
        UPDATE staging.orders AS o
        SET _is_deleted = TRUE, _deleted_at = d.deleted_at::timestamp,
            _batch_id = d.batch_id, _loaded_at = now()
        FROM tmp_deleted_orders AS d
        WHERE o.order_id = d.order_id AND NOT o._is_deleted
        """
    )
    return cur.rowcount
