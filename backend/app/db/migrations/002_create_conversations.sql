BEGIN TRANSACTION;

-- Conversations table: represents a chat thread
CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title_preview TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT
);

-- Messages table: stores individual messages within a conversation
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL,
    sources_json TEXT,  -- JSON array of citation objects for assistant messages
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

-- Index for fast history retrieval: conversation messages ordered by time
CREATE INDEX IF NOT EXISTS idx_messages_conv_created 
    ON messages(conversation_id, created_at);

COMMIT;