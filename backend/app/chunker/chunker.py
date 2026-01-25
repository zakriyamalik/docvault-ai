# backend/app/chunker/chunker.py
from __future__ import annotations
from typing import List, Dict, Any
from uuid import uuid4
from datetime import datetime

from app.chunker.tokenizer_wrapper import tokenize_text, token_spans_to_char_offsets
from app.db.sqlite_conn import get_db  # Correct DB access

DEFAULT_CHUNK_SIZE = 500
DEFAULT_OVERLAP = 100


def _iso_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def chunk_pages(
    document_id: str,
    pages: List[Dict[str, Any]],
    tokenizer,
    chunk_size_tokens: int = DEFAULT_CHUNK_SIZE,
    overlap_tokens: int = DEFAULT_OVERLAP,
) -> List[Dict[str, Any]]:
    """
    Chunk pages into token-based chunks using tokenizer offsets.

    Returns list of chunk dicts (memory-only for now):
        - id, document_id, chunk_index, text, token_count, created_at
        - page, char_start_page, char_end_page, ocr_used, preview (in memory)
    """
    if chunk_size_tokens <= 0:
        raise ValueError("chunk_size_tokens must be > 0")
    if overlap_tokens < 0:
        raise ValueError("overlap_tokens must be >= 0")

    stride = max(1, chunk_size_tokens - overlap_tokens)

    chunks: List[Dict[str, Any]] = []
    global_chunk_index = 0

    for p_idx, page in enumerate(pages):
        text = (page.get("text") or "")
        page_num = page.get("page", p_idx + 1)
        ocr_used = page.get("ocr_used", False)

        token_ids, offsets = tokenize_text(tokenizer, text)
        total_tokens = len(token_ids)

        # fallback for empty tokenization
        if total_tokens == 0 and text.strip():
            chunk = {
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
            }
            chunks.append(chunk)
            global_chunk_index += 1
            continue

        start = 0
        while start < total_tokens:
            end = min(start + chunk_size_tokens, total_tokens)
            try:
                char_start, char_end = token_spans_to_char_offsets(offsets, start, end)
            except Exception:
                break

            char_start = max(0, int(char_start))
            char_end = min(len(text), int(char_end))
            chunk_text = text[char_start:char_end]

            if not chunk_text:
                if end == total_tokens:
                    break
                start += stride
                continue

            chunk = {
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
            }
            chunks.append(chunk)
            global_chunk_index += 1

            if end == total_tokens:
                break
            start += stride

    return chunks


def persist_chunks_to_db(chunks: List[Dict]):
    """
    Insert chunk dicts into DB matching the actual chunks table schema.
    """
    insert_sql = """
    INSERT INTO chunks (id, document_id, chunk_index, text, token_count, created_at)
    VALUES (?, ?, ?, ?, ?, ?)
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
        conn.executemany(insert_sql, rows)
        conn.commit()