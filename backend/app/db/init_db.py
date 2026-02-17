import os
import psycopg2
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
DATABASE_URL = os.getenv("DATABASE_URL")

def _connect():
    return psycopg2.connect(DATABASE_URL)

def _ensure_migrations_table(conn):
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS migrations_applied (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        applied_at TIMESTAMP NOT NULL DEFAULT NOW()
    );
    """)
    conn.commit()

def _applied_migrations(conn):
    cur = conn.cursor()
    try:
        cur.execute("SELECT name FROM migrations_applied")
        rows = cur.fetchall()
        return {r[0] for r in rows}
    except psycopg2.errors.UndefinedTable:
        conn.rollback()
        return set()

def apply_migration(conn, name, sql_text):
    cur = conn.cursor()
    try:
        cur.execute(sql_text)
        _ensure_migrations_table(conn)
        cur.execute("INSERT INTO migrations_applied (name) VALUES (%s) ON CONFLICT (name) DO NOTHING", (name,))
        conn.commit()
        print(f"Applied migration: {name}")
    except Exception as e:
        conn.rollback()
        print(f"Error in migration {name}: {e}")
        raise

def main():
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL environment variable not set")

    conn = _connect()
    try:
        # Always ensure migrations table exists first
        _ensure_migrations_table(conn)

        applied = _applied_migrations(conn)
        migrations = sorted(MIGRATIONS_DIR.glob("*.sql"))

        # Check if we need reset (if old migrations exist without proper tables)
        needs_reset = False
        if "001_create_documents_chunks.sql" in applied and "000_reset_database.sql" not in applied:
            # Check if documents table has proper columns
            cur = conn.cursor()
            try:
                cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'documents' AND column_name = 'meta_json'")
                if not cur.fetchone():
                    needs_reset = True
            except:
                needs_reset = True

        if needs_reset:
            print("Detected incompatible database schema. Running reset...")
            reset_file = MIGRATIONS_DIR / "000_reset_database.sql"
            if reset_file.exists():
                # Apply reset and CLEAR all migration tracking
                cur = conn.cursor()
                cur.execute(reset_file.read_text(encoding="utf-8"))
                conn.commit()
                print(f"Applied reset: {reset_file.name}")
                
                # Clear migrations_applied and start fresh
                _ensure_migrations_table(conn)
                cur.execute("DELETE FROM migrations_applied")
                cur.execute("INSERT INTO migrations_applied (name) VALUES (%s)", (reset_file.name,))
                conn.commit()
                
                # Refresh applied set - ONLY reset is applied now
                applied = {reset_file.name}

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
