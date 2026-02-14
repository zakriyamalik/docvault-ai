# sqlite_conn.py - COMPLETE SCHEMA FROM MIGRATIONS
import sqlite3
import os
from contextlib import contextmanager
from pathlib import Path

DB_PATH = Path("/tmp/docvault.db")

def _init_schema(conn):
    """Initialize complete database schema from migration files"""
    conn.executescript("""
        -- migrations_applied table
        CREATE TABLE IF NOT EXISTS migrations_applied (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        -- Documents table (COMPLETE)
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            filename TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_ref TEXT,
            mime_type TEXT,
            size_bytes INTEGER,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT,
            meta_json TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at);

        -- Chunks table (COMPLETE)
        CREATE TABLE IF NOT EXISTS chunks (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            text TEXT NOT NULL,
            token_count INTEGER,
            vector_id TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);
        CREATE INDEX IF NOT EXISTS idx_chunks_vector_id ON chunks(vector_id);

        -- FAISS index mapping table
        CREATE TABLE IF NOT EXISTS faiss_index_map (
            vector_id TEXT PRIMARY KEY,
            chunk_id TEXT NOT NULL,
            index_name TEXT NOT NULL,
            dim INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (chunk_id) REFERENCES chunks(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_faiss_index_map_chunk_id ON faiss_index_map(chunk_id);

        -- Conversations table
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            title_preview TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT
        );

        -- Messages table
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
            content TEXT NOT NULL,
            sources_json TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_messages_conv_created ON messages(conversation_id, created_at);
    """)
    conn.commit()

def _make_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(DB_PATH), timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    
    # Initialize complete schema
    _init_schema(conn)
    
    return conn

@contextmanager
def get_db():
    conn = _make_conn()
    try:
        yield conn
    finally:
        conn.close()
