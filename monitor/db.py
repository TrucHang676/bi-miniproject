"""Kết nối Postgres cho dashboard theo dõi ETL (monitor/). Thông tin đăng nhập đọc từ .env ở gốc repo.

Chỉ ĐỌC: app này không ghi gì vào etl_log / dq / staging / dds.
"""
import os
from pathlib import Path

import pandas as pd
import psycopg
from dotenv import load_dotenv
from psycopg.types.numeric import FloatLoader

GOC_REPO = Path(__file__).resolve().parent.parent
load_dotenv(GOC_REPO / ".env")  # không ghi đè biến môi trường có sẵn (VD đổi POSTGRES_DB để thử trên DB tạm)


def _ket_noi() -> psycopg.Connection:
    # .env ghi POSTGRES_HOST=postgres là tên container (dùng bên trong Docker);
    # app chạy trên máy nên mặc định 127.0.0.1 (không dùng tên localhost: DB tắt thì Windows thử IPv6 rồi mới tới IPv4, chờ ~16 giây).
    # Đổi bằng biến MONITOR_DB_HOST.
    conn = psycopg.connect(
        host=os.getenv("MONITOR_DB_HOST", "127.0.0.1"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        connect_timeout=3,
        options="-c default_transaction_read_only=on",  # chốt an toàn: phiên này không ghi được
    )
    conn.adapters.register_loader("numeric", FloatLoader)  # NUMERIC -> float thay vì Decimal
    return conn


def truy_van(sql: str, tham_so: dict | None = None) -> pd.DataFrame:
    """Chạy 1 câu SELECT, trả về DataFrame."""
    with _ket_noi() as conn, conn.cursor() as cur:
        cur.execute(sql, tham_so or {})
        return pd.DataFrame(cur.fetchall(), columns=[c.name for c in cur.description])
