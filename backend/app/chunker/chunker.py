# backend/app/chunker/chunker.py
from __future__ import annotations
from typing import List, Dict, Any
from uuid import uuid4
from datetime import datetime

from app.chunker.tokenizer_wrapper import tokenize_text, token_spans_to_char_offsets
from app.db.postgres_conn import get_db  # Correct DB access

# Default chunk size (tokens) used by the chunker.
DEFAULT_CHUNK_SIZE = 500
DEFAULT_OVERLAP = 100
# Max tokens supported by the embedding model
DEFAULT_MAX_MODEL_TOKENS = 512


def _iso_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def chunk_pages(
    document_id: str,
    pages: List[Dict[str, Any]],
    tokenizer,
    chunk_size_tokens: int = DEFAULT_CHUNK_SIZE,
    overlap_tokens: int = DEFAULT_OVERLAP,
    max_model_tokens: int = DEFAULT_MAX_MODEL_TOKENS,
) -> List[Dict[str, Any]]:
    """
    Chunk pages into token-based chunks. Ensures **no chunk exceeds max_model_tokens**.
    Returns list of chunk dicts (memory-only for now).
    """
    if chunk_size_tokens <= 0:
        raise ValueError("chunk_size_tokens must be > 0")
    if overlap_tokens < 0:
        raise ValueError("overlap_tokens must be >= 0")
    if max_model_tokens <= 0:
        raise ValueError("max_model_tokens must be > 0")

    effective_chunk_size = min(chunk_size_tokens, max_model_tokens)
    stride = max(1, effective_chunk_size - overlap_tokens)

    chunks: List[Dict[str, Any]] = []
    global_chunk_index = 0

    for p_idx, page in enumerate(pages):
        text = page.get("text") or ""
        page_num = page.get("page", p_idx + 1)
        ocr_used = page.get("ocr_used", False)

        token_ids, offsets = tokenize_text(tokenizer, text)
        total_tokens = len(token_ids)

        # fallback for empty tokenization
        if total_tokens == 0 and text.strip():
            chunks.append({
                "id": str(uuid4()),
                "document_id": document_id,
                "chunk_index": global_chunk_index,
                "text": text,
                "token_count": 0,
                "created_at": _iso_now(),
                "page": page_num,
                "char_start_page": 0,
                "char_end_page": len(text),
                "ocr_used": bool(ocr_used),
                "preview": text[:256],
            })
            global_chunk_index += 1
            continue

        start = 0
        while start < total_tokens:
            end = min(start + effective_chunk_size, total_tokens)

            # Split large chunks into sub-chunks if they exceed max_model_tokens
            while end - start > max_model_tokens:
                sub_end = start + max_model_tokens
                try:
                    char_start, char_end = token_spans_to_char_offsets(offsets, start, sub_end)
                except Exception:
                    char_start = 0
                    char_end = len(text)
                
                chunk_text = text[char_start:char_end]
                chunks.append({
                    "id": str(uuid4()),
                    "document_id": document_id,
                    "chunk_index": global_chunk_index,
                    "text": chunk_text,
                    "token_count": sub_end - start,
                    "created_at": _iso_now(),
                    "page": page_num,
                    "char_start_page": char_start,
                    "char_end_page": char_end,
                    "ocr_used": bool(ocr_used),
                    "preview": chunk_text[:256],
                })
                global_chunk_index += 1
                start = sub_end

            # Normal chunk
            try:
                char_start, char_end = token_spans_to_char_offsets(offsets, start, end)
            except Exception:
                char_start = 0
                char_end = len(text)
            
            chunk_text = text[char_start:char_end]
            chunks.append({
                "id": str(uuid4()),
                "document_id": document_id,
                "chunk_index": global_chunk_index,
                "text": chunk_text,
                "token_count": end - start,
                "created_at": _iso_now(),
                "page": page_num,
                "char_start_page": char_start,
                "char_end_page": char_end,
                "ocr_used": bool(ocr_used),
                "preview": chunk_text[:256],
            })
            global_chunk_index += 1

            if end >= total_tokens:
                break
            start = min(start + stride, total_tokens - 1)
            if start >= total_tokens:
                break

    return chunks


def persist_chunks_to_db(chunks: List[Dict[str, Any]]) -> None:
    """
    Persist chunks to PostgreSQL database.
    Uses batch insert for performance.
    """
    if not chunks:
        return

    # PostgreSQL uses %s placeholders instead of ?
    insert_sql = """
        INSERT INTO chunks (id, document_id, chunk_index, text, token_count, created_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO NOTHING
    """
    
    rows = [
        (
            c["id"],
            c["document_id"],
            c["chunk_index"],
            c["text"],
            c["token_count"],
            c["created_at"],
        )
        for c in chunks
    ]

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.executemany(insert_sql, rows)
            conn.commit()


def get_chunks_for_document(doc_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve all chunks for a given document ID.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, document_id, chunk_index, text, token_count, vector_id FROM chunks WHERE document_id = %s ORDER BY chunk_index",
                (doc_id,),
            )
            rows = cur.fetchall()
            colnames = [desc[0] for desc in cur.description]
            return [dict(zip(colnames, row)) for row in rows]


def count_chunks_for_document(doc_id: str) -> int:
    """
    Count chunks for a document.
    """
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM chunks WHERE document_id = %s", (doc_id,))
            result = cur.fetchone()
            return result[0] if result else 0
