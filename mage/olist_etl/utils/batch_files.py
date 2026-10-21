"""Đọc manifest.csv và file CSV của batch (định dạng: data/batches/README.md, quy tắc đọc: pipeline_rules.md B4.1)."""
import os

import pandas as pd

from olist_etl.utils.settings import BATCH_DIR, MANIFEST_PATH


def read_csv(path):
    """Đọc 1 file CSV, mọi cột dạng chuỗi.

    dtype=str                  giữ nguyên giá trị như trong file (zip '01037' không mất số 0 đầu)
    keep_default_na=False,     chỉ ô trống mới thành NULL - pandas không tự biến chữ 'NA', 'null'... thành NULL
    na_values=['']
    pandas là CSV parser chuẩn nên đọc đúng bình luận review có xuống dòng bên trong ô (trong ngoặc kép).
    """
    return pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[''], encoding='utf-8')


def manifest_row(batch_id):
    """Thông tin 1 batch trong manifest.csv dạng dict. lset / cet trống -> None."""
    manifest = read_csv(MANIFEST_PATH)
    rows = manifest[manifest['batch_id'] == batch_id]
    if rows.empty:
        raise ValueError(f'manifest.csv không có batch {batch_id}')
    row = rows.iloc[0].to_dict()
    return {k: (None if pd.isna(v) else v) for k, v in row.items()}


def batch_file_path(batch_id, table):
    """Đường dẫn file của 1 bảng trong 1 batch, VD /home/src/data/batches/FULL/orders.csv."""
    return os.path.join(BATCH_DIR, batch_id, f'{table}.csv')
