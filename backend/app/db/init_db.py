# init_db.py
import os
import sqlite3
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
DB_PATH = Path("/tmp/db/db.sqlite")

def _ensure_db_path():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not DB_PATH.exists():
        DB_PATH.touch(mode=0o644, exist_ok=True)

def _connect():
    conn = sqlite3.connect(str(DB_PATH), timeout=30, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn

def _applied_migrations(conn):
    cur = conn.cursor()
    cur.execute("SELECT name FROM migrations_applied")
    rows = cur.fetchall()
    return {r[0] for r in rows}

def apply_migration(conn, name, sql_text):
    cur = conn.cursor()
    try:
        cur.executescript(sql_text)
        cur.execute("INSERT OR IGNORE INTO migrations_applied (name) VALUES (?)", (name,))
        conn.commit()
        print(f"Applied migration: {name}")
    except Exception as e:
        conn.rollback()
        raise

def main():
    _ensure_db_path()
    conn = _connect()
    try:
        # ensure migrations_applied exists in case migration file didn't create it
        conn.execute("""
        CREATE TABLE IF NOT EXISTS migrations_applied (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """)
        conn.commit()

        applied = _applied_migrations(conn)

        migrations = sorted(MIGRATIONS_DIR.glob("*.sql"))
        for m in migrations:
            name = m.name
            if name in applied:
                print(f"Skipping already applied migration: {name}")
                continue
            sql_text = m.read_text(encoding="utf-8")
            print(f"Running migration: {name}")
            apply_migration(conn, name, sql_text)

        print("All migrations processed.")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
