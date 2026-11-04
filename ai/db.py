"""Kết nối Postgres (kho dds) cho phần AI. Thông tin đăng nhập đọc từ .env ở gốc repo."""
import os
from pathlib import Path

import pandas as pd
import psycopg
from dotenv import load_dotenv
from psycopg.types.numeric import FloatLoader

GOC_REPO = Path(__file__).resolve().parent.parent
load_dotenv(GOC_REPO / ".env")


def _ket_noi() -> psycopg.Connection:
    # .env ghi POSTGRES_HOST=postgres là tên container (dùng bên trong Docker);
    # app chạy trên máy nên mặc định localhost, giống Power BI (localhost:5432).
    conn = psycopg.connect(
        host=os.getenv("AI_DB_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.environ["POSTGRES_DB"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        connect_timeout=5,
    )
    conn.adapters.register_loader("numeric", FloatLoader)  # NUMERIC -> float thay vì Decimal
    return conn


def truy_van(sql: str, tham_so: dict | None = None) -> pd.DataFrame:
    """Chạy 1 câu SELECT, trả về DataFrame."""
    with _ket_noi() as conn, conn.cursor() as cur:
        cur.execute(sql, tham_so or {})
        return pd.DataFrame(cur.fetchall(), columns=[c.name for c in cur.description])
