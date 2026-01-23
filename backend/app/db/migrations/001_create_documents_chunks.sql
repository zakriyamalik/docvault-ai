-- 001_create_documents_chunks.sql
BEGIN TRANSACTION;


-- migrations_applied table to track applied migrations (idempotent)
CREATE TABLE IF NOT EXISTS migrations_applied (
id INTEGER PRIMARY KEY AUTOINCREMENT,
name TEXT NOT NULL UNIQUE,
applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);


-- Documents table
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


-- Chunks table
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


COMMIT;