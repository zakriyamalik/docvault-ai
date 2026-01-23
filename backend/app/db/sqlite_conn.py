# sqlite_conn.py
import sqlite3
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path("/data/db/db.sqlite")


def _make_conn():
    conn = sqlite3.connect(str(DB_PATH), timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn


@contextmanager
def get_db():
    conn = _make_conn()
    try:
        yield conn
    finally:
        conn.close()
