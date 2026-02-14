# postgres_conn.py - Production PostgreSQL connection
import os
import psycopg2
from contextlib import contextmanager
from urllib.parse import urlparse

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://docvault:DocVault2024Secure@docvault-db.ckvs6kwu40qt.us-east-1.rds.amazonaws.com:5432/docvault")

def _init_schema(conn):
    """Initialize schema if tables don't exist"""
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS migrations_applied (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                applied_at TIMESTAMP NOT NULL DEFAULT NOW()
            );
            
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_ref TEXT,
                mime_type TEXT,
                size_bytes INTEGER,
                status TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP,
                meta_json TEXT
            );
            
            CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at);
            
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                text TEXT NOT NULL,
                token_count INTEGER,
                vector_id TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
            );
            
            CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);
            CREATE INDEX IF NOT EXISTS idx_chunks_vector_id ON chunks(vector_id);
            
            CREATE TABLE IF NOT EXISTS faiss_index_map (
                vector_id TEXT PRIMARY KEY,
                chunk_id TEXT NOT NULL,
                index_name TEXT NOT NULL,
                dim INTEGER NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                FOREIGN KEY (chunk_id) REFERENCES chunks(id) ON DELETE CASCADE
            );
            
            CREATE INDEX IF NOT EXISTS idx_faiss_index_map_chunk_id ON faiss_index_map(chunk_id);
            
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title_preview TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
                content TEXT NOT NULL,
                sources_json TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            );
            
            CREATE INDEX IF NOT EXISTS idx_messages_conv_created ON messages(conversation_id, created_at);
        """)
        conn.commit()

@contextmanager
def get_db():
    """Get PostgreSQL database connection"""
    conn = psycopg2.connect(DATABASE_URL)
    try:
        # Enable autocommit for simplicity (can be changed if needed)
        conn.autocommit = False
        # Initialize schema on first connection
        _init_schema(conn)
        yield conn
    finally:
        conn.close()
