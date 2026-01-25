import uuid
from pathlib import Path

from app.chunker.tokenizer_wrapper import get_tokenizer, tokenize_text, token_spans_to_char_offsets
from app.chunker.chunker import chunk_pages, persist_chunks_to_db
from app.db import sqlite_conn


def test_chunker_end_to_end(tmp_path: Path):
    """End-to-end unit test for the chunker.

    - Uses a temporary sqlite DB (tmp_path) by overriding sqlite_conn.DB_PATH
    - Creates minimal `documents` and `chunks` tables matching migrations
    - Generates synthetic long text, runs chunk_pages(), verifies token counts,
      offsets <-> substring mapping, and persists chunks to DB.
    """
    # 1) Point DB to a temporary file
    sqlite_conn.DB_PATH = tmp_path / "test_db.sqlite"

    # 2) Create minimal schema (documents + chunks)
    with sqlite_conn.get_db() as conn:
        conn.execute(
            """
            CREATE TABLE documents (
                id TEXT PRIMARY KEY,
                filename TEXT,
                size_bytes INTEGER,
                status TEXT,
                source_type TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE chunks (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                chunk_index INTEGER NOT NULL,
                text TEXT NOT NULL,
                token_count INTEGER,
                vector_id TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()

    # 3) Insert a document row
    document_id = str(uuid.uuid4())
    with sqlite_conn.get_db() as conn:
        conn.execute(
            "INSERT INTO documents (id, filename, size_bytes, status, source_type) VALUES (?, ?, ?, ?, ?)",
            (document_id, "test.pdf", 123, "queued", "upload"),
        )
        conn.commit()

    # 4) Prepare synthetic text
    # Use <= 512 tokens so default tokenizer doesn't truncate
    text = "word " * 400  # ~400 tokens
    pages = [{"page": 1, "text": text}]

    # 5) Load tokenizer and produce chunks
    tokenizer = get_tokenizer()
    chunks = chunk_pages(document_id, pages, tokenizer, chunk_size_tokens=500, overlap_tokens=100)

    assert len(chunks) > 0, "No chunks were generated"

    # 6) Verify token counts and offsets
    full_token_ids, full_offsets = tokenize_text(tokenizer, text)
    total_tokens = len(full_token_ids)
    stride = 500 - 100

    expected_windows = []
    s = 0
    while s < total_tokens:
        e = min(s + 500, total_tokens)
        expected_windows.append((s, e))
        if e == total_tokens:
            break
        s += stride

    # It's normal that last chunk may be smaller than chunk_size_tokens
    assert len(expected_windows) == len(chunks), "Number of expected windows != generated chunks"

    for (start, end), chunk in zip(expected_windows, chunks):
        # token_count should match expected window
        assert chunk["token_count"] == (end - start)
        # char offsets match substring
        cs, ce = token_spans_to_char_offsets(full_offsets, start, end)
        assert chunk["text"] == text[cs:ce]

    # 7) Persist chunks and verify DB rows
    persist_chunks_to_db(chunks)
    with sqlite_conn.get_db() as conn:
        row = conn.execute("SELECT COUNT(*) as c FROM chunks WHERE document_id = ?", (document_id,)).fetchone()
        assert row["c"] == len(chunks)
