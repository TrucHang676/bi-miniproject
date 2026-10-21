"""Kết nối PostgreSQL của đồ án.

Thông tin kết nối lấy từ biến môi trường POSTGRES_* mà compose.yaml nạp vào container Mage từ file .env
(cùng nguồn với profile default trong io_config.yaml).
"""
import os

import psycopg2


def connect(autocommit=False):
    """Mở 1 kết nối mới.

    autocommit=True : mỗi câu lệnh lưu ngay - dùng để ghi etl_log, để log vẫn còn khi phần nạp bị hoàn tác.
    autocommit=False: các lệnh gom trong 1 transaction, phải conn.commit() - dùng để ghi staging.
    """
    conn = psycopg2.connect(
        host=os.environ['POSTGRES_HOST'],
        port=os.environ.get('POSTGRES_PORT', '5432'),
        dbname=os.environ['POSTGRES_DB'],
        user=os.environ['POSTGRES_USER'],
        password=os.environ['POSTGRES_PASSWORD'],
        application_name='olist_etl',
    )
    conn.autocommit = autocommit
    return conn
