"""Kiểm tra chất lượng trước khi nạp staging - "data firewall" (BS-21, pipeline_rules.md B4.2, B4.3).

Thứ tự kiểm tra của 1 bảng (phép sau chỉ xét các dòng còn lại sau phép trước):

    check_name       hỏng thì                                   status
    file_exists      dừng cả batch (kiểm tra 1 lần cho cả batch) FAIL
    columns_match    dừng cả batch                              FAIL
    batch_id_match   dừng cả batch                              FAIL
    not_null_key     loại dòng -> dq.rejected_rows              WARN
    duplicate_key    loại MỌI dòng mang khóa trùng -> dq        WARN
    type_cast        loại dòng -> dq                            WARN
    row_count_match  vẫn nạp, ghi chú trong detail              WARN

Mỗi phép ghi đúng 1 dòng etl_log.quality_check (kể cả PASS). Mỗi dòng bị loại ghi 1 lần vào dq.rejected_rows,
theo phép kiểm tra đầu tiên nó không qua.
"""
import pandas as pd

from olist_etl.utils import etl_log
from olist_etl.utils.settings import TABLES
from olist_etl.utils.staging import column_info, copy_frame

# Kiểu không cần kiểm tra ép kiểu (chuỗi nào cũng hợp lệ)
_FREE_TYPES = {'text'}


class BatchCheckFailed(Exception):
    """Phép kiểm tra mức FAIL không đạt -> dừng cả batch, không nạp gì."""


def row_data(row):
    """1 dòng gốc dạng dict {tên cột: giá trị chuỗi như trong file}; ô trống -> ''."""
    return {col: ('' if pd.isna(value) else str(value)) for col, value in row.items()}


def reject_rows(log, run_id, table, check_name, df, reasons):
    """Ghi kết quả 1 phép kiểm tra cấp dòng và loại các dòng không đạt.

    reasons: pd.Series {index dòng trong df: lý do}. Rỗng = PASS.
    Trả về df sau khi bỏ các dòng không đạt.
    """
    failed = len(reasons)
    if failed == 0:
        etl_log.add_check(log, run_id, table, check_name, 0, 'PASS')
        return df

    first_index = reasons.index[0]
    detail = f'{failed} dòng bị loại, VD bản ghi {first_index + 1}: {reasons.iloc[0]}'
    etl_log.add_check(log, run_id, table, check_name, failed, 'WARN', detail)
    etl_log.add_rejected(
        log, run_id, table, check_name,
        [(int(idx) + 1, row_data(df.loc[idx]), reason) for idx, reason in reasons.items()],
    )
    return df.drop(index=reasons.index)


def check_files_exist(log, run_id, batch_id, tables, path_of):
    """file_exists: đủ file của batch (FULL: 8, Incremental: 5). Mỗi file 1 dòng quality_check."""
    missing = []
    for table in tables:
        path = path_of(batch_id, table)
        try:
            with open(path, 'rb'):
                pass
            etl_log.add_check(log, run_id, table, 'file_exists', 0, 'PASS')
        except OSError:
            missing.append(f'{table}.csv')
            etl_log.add_check(log, run_id, table, 'file_exists', 0, 'FAIL', f'Thiếu file {batch_id}/{table}.csv')
    if missing:
        raise BatchCheckFailed(f'file_exists không đạt: batch {batch_id} thiếu {", ".join(missing)}')


def check_columns(log, run_id, table, df, expected):
    """columns_match: tiêu đề đúng tên, đúng thứ tự như README mục 4 (cột gốc + batch_id)."""
    actual = list(df.columns)
    if actual == expected:
        etl_log.add_check(log, run_id, table, 'columns_match', 0, 'PASS')
        return

    missing = [c for c in expected if c not in actual]
    extra = [c for c in actual if c not in expected]
    parts = []
    if missing:
        parts.append('thiếu cột ' + ', '.join(missing))
    if extra:
        parts.append('thừa cột ' + ', '.join(extra))
    if not parts:
        parts.append('sai thứ tự cột: ' + ', '.join(actual))
    detail = '; '.join(parts)
    etl_log.add_check(log, run_id, table, 'columns_match', 0, 'FAIL', detail)
    raise BatchCheckFailed(f'columns_match không đạt ở {table}: {detail}')


def check_unreadable(log, run_id, table, exc):
    """File không đọc được (VD số ô mỗi dòng không đều) -> coi như sai cấu trúc: columns_match FAIL."""
    detail = f'Không đọc được file: {etl_log.short_error(exc)}'
    etl_log.add_check(log, run_id, table, 'columns_match', 0, 'FAIL', detail)
    raise BatchCheckFailed(f'columns_match không đạt ở {table}: {detail}')


def check_batch_id(log, run_id, table, df, batch_id):
    """batch_id_match: mọi dòng có batch_id = batch đang nạp (chống đặt nhầm file của batch khác)."""
    wrong = df['batch_id'].ne(batch_id) | df['batch_id'].isna()
    failed = int(wrong.sum())
    if failed == 0:
        etl_log.add_check(log, run_id, table, 'batch_id_match', 0, 'PASS')
        return
    sample = df.loc[wrong, 'batch_id'].fillna('(rỗng)').iloc[0]
    detail = f'{failed} dòng có batch_id khác {batch_id}, VD {sample}'
    etl_log.add_check(log, run_id, table, 'batch_id_match', failed, 'FAIL', detail)
    raise BatchCheckFailed(f'batch_id_match không đạt ở {table}: {detail}')


def check_not_null_key(log, run_id, table, df, key):
    """not_null_key: cột khóa chính không rỗng."""
    null_mask = df[key].isna()
    rows = null_mask.any(axis=1)
    reasons = null_mask[rows].apply(lambda r: ', '.join(c for c in key if r[c]) + ' rỗng', axis=1)
    return reject_rows(log, run_id, table, 'not_null_key', df, reasons)


def check_duplicate_key(log, run_id, table, df, key):
    """duplicate_key: khóa lặp trong file -> loại MỌI dòng mang khóa đó.

    Không đoán dòng nào đúng; và MERGE sẽ báo lỗi nếu 1 khóa xuất hiện 2 lần trong nguồn.
    """
    dup = df.duplicated(subset=key, keep=False)
    if not dup.any():
        return reject_rows(log, run_id, table, 'duplicate_key', df, pd.Series(dtype=object))
    counts = df[dup].groupby(key, dropna=False)[key[0]].transform('size')
    reasons = df[dup].apply(
        lambda r: 'khóa (' + ', '.join(f'{c}={r[c]}' for c in key) + f') lặp {counts[r.name]} lần trong file',
        axis=1,
    )
    return reject_rows(log, run_id, table, 'duplicate_key', df, reasons)


def _sql_literal(text):
    return "'" + text.replace("'", "''") + "'"


def check_type_cast(log, cur, run_id, table, df):
    """type_cast: giá trị ép được sang kiểu của bảng staging; cột NOT NULL (ngoài khóa) không rỗng.

    Dùng pg_input_is_valid() của PostgreSQL 16+ - kiểm tra đúng như lúc MERGE ép kiểu
    (số, ngày giờ, độ dài VARCHAR / CHAR), không tự viết lại luật ép kiểu bằng Python.
    """
    columns = TABLES[table]['columns']
    key = TABLES[table]['key']
    info = column_info(cur, table)
    if df.empty:
        return reject_rows(log, run_id, table, 'type_cast', df, pd.Series(dtype=object))

    checks = []
    for col in columns:
        data_type, not_null = info[col]
        if data_type not in _FREE_TYPES:
            checks.append(
                f"CASE WHEN {col} IS NOT NULL AND NOT pg_input_is_valid({col}, {_sql_literal(data_type)}) "
                f"THEN format('%s = \"%s\" không hợp lệ với kiểu %s', {_sql_literal(col)}, left({col}, 50), "
                f"{_sql_literal(data_type)}) END"
            )
        if not_null and col not in key:
            checks.append(f"CASE WHEN {col} IS NULL THEN {_sql_literal(col + ' rỗng (cột bắt buộc)')} END")

    work = df.assign(_row=(df.index + 1).astype(str))
    copy_frame(cur, f'tmp_check_{table}', work, columns + ['_row'])
    cur.execute(
        f"""
        SELECT _row::int, reason
        FROM (SELECT _row, concat_ws('; ', {', '.join(checks)}) AS reason FROM tmp_check_{table}) x
        WHERE reason <> ''
        ORDER BY _row::int
        """
    )
    bad = cur.fetchall()
    reasons = pd.Series({row - 1: reason for row, reason in bad}, dtype=object)
    return reject_rows(log, run_id, table, 'type_cast', df, reasons)


def check_row_count(log, run_id, table, rows_source, expected_rows):
    """row_count_match: số dòng đọc được = số dòng ghi trong manifest. Lệch vẫn nạp, chỉ cảnh báo.

    failed_rows = 0 vì phép này không loại dòng nào (đối soát B4.3: tổng failed_rows = số dòng trong dq).
    """
    if expected_rows is None:
        return
    expected = int(expected_rows)
    if rows_source == expected:
        etl_log.add_check(log, run_id, table, 'row_count_match', 0, 'PASS')
    else:
        etl_log.add_check(log, run_id, table, 'row_count_match', 0, 'WARN',
                          f'File có {rows_source} dòng, manifest ghi {expected} (lệch {rows_source - expected})')


def validate_table(log, cur, run_id, batch_id, table, df, expected_rows):
    """Chạy đủ các phép kiểm tra của 1 bảng. Trả về (DataFrame dòng sạch, số dòng bị loại).

    Phép FAIL ném BatchCheckFailed -> runner hoàn tác cả batch.
    """
    spec = TABLES[table]
    check_columns(log, run_id, table, df, spec['columns'] + ['batch_id'])
    check_batch_id(log, run_id, table, df, batch_id)

    clean = check_not_null_key(log, run_id, table, df, spec['key'])
    clean = check_duplicate_key(log, run_id, table, clean, spec['key'])
    clean = check_type_cast(log, cur, run_id, table, clean)
    check_row_count(log, run_id, table, len(df), expected_rows)
    return clean, len(df) - len(clean)
