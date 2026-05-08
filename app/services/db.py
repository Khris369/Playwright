from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from app.database import db_connection


@contextmanager
def get_db_cursor() -> Iterator:
    conn = db_connection()
    try:
        with conn.cursor() as cursor:
            yield conn, cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
