"""Ghi dữ liệu vào schema staging: bảng tạm + MERGE theo khóa chính (pipeline_rules.md B4.4)."""
import io

from olist_etl.utils.settings import STAGING_SCHEMA, TABLES


def column_info(cur, table):
    """Kiểu dữ liệu và ràng buộc NOT NULL từng cột của bảng staging, đọc từ DB.

    VD {'price': ('numeric(10,2)', False), 'order_id': ('character varying(32)', True), ...}
    """
    cur.execute(
        """
        SELECT a.attname, format_type(a.atttypid, a.atttypmod), a.attnotnull
        FROM pg_attribute a
        WHERE a.attrelid = %s::regclass AND a.attnum > 0 AND NOT a.attisdropped
        ORDER BY a.attnum
        """,
        (f'{STAGING_SCHEMA}.{table}',),
    )
    return {name: (data_type, not_null) for name, data_type, not_null in cur.fetchall()}


def column_types(cur, table):
    """Kiểu dữ liệu từng cột của bảng staging, VD {'price': 'numeric(10,2)', ...}."""
    return {name: data_type for name, (data_type, _) in column_info(cur, table).items()}


def truncate_staging(cur, tables):
    """Xóa sạch các bảng staging (chỉ Full Load dùng - B2.1). Không đụng etl_log, dq."""
    names = ', '.join(f'{STAGING_SCHEMA}.{t}' for t in tables)
    cur.execute(f'TRUNCATE {names}')


def copy_frame(cur, tmp, df, columns):
    """Đưa các cột `columns` của DataFrame vào bảng tạm `tmp` (mọi cột TEXT) bằng COPY.

    Bảng tạm tự xóa khi transaction kết thúc (ON COMMIT DROP).
    Ô NULL được ghi thành ô trống không ngoặc kép -> COPY ... CSV hiểu là NULL.
    """
    cur.execute(f'DROP TABLE IF EXISTS {tmp}')
    cur.execute(f'CREATE TEMP TABLE {tmp} ({", ".join(c + " TEXT" for c in columns)}) ON COMMIT DROP')

    buf = io.StringIO()
    df[columns].to_csv(buf, index=False, header=False, na_rep='')
    buf.seek(0)
    cur.copy_expert(f'COPY {tmp} ({", ".join(columns)}) FROM STDIN WITH (FORMAT csv)', buf)
    return tmp


def copy_to_temp(cur, table, df):
    """Đưa các dòng của 1 bảng vào bảng tạm tmp_<bảng> để MERGE."""
    return copy_frame(cur, f'tmp_{table}', df, TABLES[table]['columns'] + ['batch_id'])


def build_merge_sql(table, types):
    """Câu MERGE cho 1 bảng, theo khuôn câu mẫu của bảng orders trong pipeline_rules.md B4.4.

    * Chưa có khóa trong staging      -> INSERT
    * Đã có và dữ liệu khác thật      -> UPDATE (IS DISTINCT FROM: so sánh đúng cả khi có NULL)
    * Đã có và giống hệt              -> bỏ qua, nên chạy lại 1 batch ra 0 INSERT / 0 UPDATE
    * Dòng có trong staging mà vắng trong batch -> giữ nguyên (không WHEN NOT MATCHED BY SOURCE, D4)
    * Không đụng _is_deleted, _deleted_at: đơn đã xóa mềm vẫn giữ trạng thái xóa (B6)
    """
    columns = TABLES[table]['columns']
    key = TABLES[table]['key']
    non_key = [c for c in columns if c not in key]

    select_list = ',\n               '.join(f'{c}::{types[c]} AS {c}' for c in columns)
    on_clause = ' AND '.join(f't.{c} = s.{c}' for c in key)
    t_values = ', '.join(f't.{c}' for c in non_key)
    s_values = ', '.join(f's.{c}' for c in non_key)
    set_list = ', '.join(f'{c} = s.{c}' for c in non_key)
    insert_cols = ', '.join(columns + ['_batch_id'])
    insert_vals = ', '.join(f's.{c}' for c in columns + ['_batch_id'])

    return f"""
WITH m AS (
    MERGE INTO {STAGING_SCHEMA}.{table} AS t
    USING (
        SELECT {select_list},
               batch_id AS _batch_id
        FROM tmp_{table}
    ) AS s
    ON {on_clause}
    WHEN MATCHED AND ({t_values}) IS DISTINCT FROM ({s_values})
        THEN UPDATE SET {set_list}, _batch_id = s._batch_id, _loaded_at = now()
    WHEN NOT MATCHED
        THEN INSERT ({insert_cols}) VALUES ({insert_vals})
    RETURNING merge_action() AS action
)
SELECT count(*) FILTER (WHERE action = 'INSERT') AS rows_inserted,
       count(*) FILTER (WHERE action = 'UPDATE') AS rows_updated
FROM m
"""


def merge_into_staging(cur, table, df):
    """Nạp các dòng (đã qua kiểm tra) của 1 bảng vào staging. Trả về (số dòng INSERT, số dòng UPDATE)."""
    copy_to_temp(cur, table, df)
    cur.execute(build_merge_sql(table, column_types(cur, table)))
    inserted, updated = cur.fetchone()
    return inserted, updated
