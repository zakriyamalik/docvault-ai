-- Documents table
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY,
    filename TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_ref TEXT,
    mime_type TEXT,
    size_bytes INTEGER,
    status TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP,
    meta_json JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at);

-- Chunks table
CREATE TABLE IF NOT EXISTS chunks (
    id UUID PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    token_count INTEGER,
    vector_id TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_vector_id ON chunks(vector_id);

-- FAISS index mapping table
CREATE TABLE IF NOT EXISTS faiss_index_map (
    vector_id TEXT PRIMARY KEY,
    chunk_id UUID NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    index_name TEXT NOT NULL,
    dim INTEGER NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_faiss_index_map_chunk_id ON faiss_index_map(chunk_id);
