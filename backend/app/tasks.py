# backend/app/tasks.py
import os
import json
import time
import logging
import traceback
from datetime import datetime, timezone
from typing import Optional, List, Tuple

# CHANGE: Use PostgreSQL instead of SQLite
from app.db.postgres_conn import get_db

from app.chunker.chunker import chunk_pages, persist_chunks_to_db
from app.chunker.tokenizer_wrapper import get_tokenizer
from app.parser.pdf_extractor import extract_pdf, extract_pdf_with_ocr
from app.parser.docx_extractor import extract_docx
from app.parser.txt_extractor import extract_txt
from app.embeddings.embeddings import EmbeddingWrapper
from app.faiss_manager import FAISSManager
from app.logging import get_logger
import redis

logger = logging.getLogger(__name__)
log = get_logger("ingest")

# Tunables
BATCH_SIZE_CHUNKS = int(os.getenv("CHUNK_DB_BATCH", "128"))
BATCH_SIZE_EMBED = int(os.getenv("EMBED_BATCH", "64"))
FAISS_INDEX_NAME = os.getenv("FAISS_INDEX_NAME", "default")
FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", f"/data/faiss/{FAISS_INDEX_NAME}.faiss")

# Redis DLQ
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
r = redis.Redis.from_url(REDIS_URL)
INGEST_DLQ_KEY = "ingest_dlq"

def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def _detect_file_kind(path: str) -> str:
    p = (path or "").lower()
    if p.endswith(".pdf"): return "pdf"
    if p.endswith(".docx"): return "docx"
    if p.endswith(".txt"): return "txt"
    return "unknown"

def ingest_document_atomic(document_id: str, file_path: Optional[str] = None):
    """Atomic ingest pipeline"""
    logger.info("ingest_document_atomic start: %s", document_id)
    meta = {}
    
    try:
        # Load and mark processing start
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM documents WHERE id = %s", (document_id,))
                row = cur.fetchone()
                if not row:
                    logger.error("Document not found: %s", document_id)
                    return
                
                # Get column names from cursor description
                colnames = [desc[0] for desc in cur.description]
                rowdict = dict(zip(colnames, row))
                
                meta = json.loads(rowdict.get("meta_json") or "{}")
                meta["ingest_started_at"] = _now_iso()
                
                cur.execute(
                    "UPDATE documents SET status = %s, meta_json = %s WHERE id = %s",
                    ("processing", json.dumps(meta), document_id)
                )
                conn.commit()
                
                filename = rowdict.get("filename")
        
        # Structured log
        log.info(event="ingest_started", document_id=document_id, filename=filename)
        
        # Phase 1: Validation
        logger.info("[ingest:%s] Phase 1: validation", document_id)
        if not file_path:
            raise ValueError("file_path is required")
        
        # Phase 2: Parsing
        logger.info("[ingest:%s] Phase 2: parsing", document_id)
        log.info(event="extraction_started", document_id=document_id, file_path=file_path)
        
        kind = _detect_file_kind(file_path)
        if kind == "pdf":
            pages = extract_pdf(file_path)
            if not pages or all(not (p.text and p.text.strip()) for p in pages):
                pages = extract_pdf_with_ocr(file_path)
                log.warning(event="ocr_fallback_used", document_id=document_id, pages=len(pages) if pages else 0)
        elif kind == "docx":
            pages = extract_docx(file_path)
        elif kind == "txt":
            pages = extract_txt(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_path}")
        
        # Normalize pages
        norm_pages = []
        for p in pages:
            if hasattr(p, "text"):
                text = p.text or ""
                page_no = getattr(p, "page", 1)
                meta_page = {"ocr_used": False}
            else:
                text = p.get("text", "") or ""
                page_no = int(p.get("page", 1))
                meta_page = {"ocr_used": bool(p.get("ocr_used", False))}
            if text.strip():
                norm_pages.append({"page": page_no, "text": text, "metadata": meta_page})
        
        if not norm_pages:
            raise ValueError("No extractable text pages found")
        
        # Phase 3: Chunking
        logger.info("[ingest:%s] Phase 3: chunking", document_id)
        log.info(event="chunking_started", document_id=document_id)
        tokenizer = get_tokenizer()
        chunks = chunk_pages(document_id, norm_pages, tokenizer)
        
        if not chunks:
            raise ValueError("Chunker produced zero chunks")
        
        # Persist chunks in batches
        for i in range(0, len(chunks), BATCH_SIZE_CHUNKS):
            batch = chunks[i:i + BATCH_SIZE_CHUNKS]
            persist_chunks_to_db(batch)
            log.info(event="chunk_batch", document_id=document_id, batch=i//BATCH_SIZE_CHUNKS, count=len(batch))
        
        # Phase 4: Embeddings + FAISS
        logger.info("[ingest:%s] Phase 4: embeddings + FAISS", document_id)
        ew = EmbeddingWrapper()
        faiss_mgr = FAISSManager()
        
        try:
            faiss_mgr.load_index(FAISS_INDEX_PATH)
            log.info(event="faiss_index_loaded", document_id=document_id, index_name=FAISS_INDEX_NAME)
        except FileNotFoundError:
            faiss_mgr.create_index(FAISS_INDEX_PATH, dim=ew.dim)
            log.info(event="faiss_index_created", document_id=document_id, dim=ew.dim)
        
        vector_map = []
        for i in range(0, len(chunks), BATCH_SIZE_EMBED):
            batch = chunks[i:i + BATCH_SIZE_EMBED]
            texts = [c["text"] for c in batch]
            vectors = ew.embed_texts(texts)
            new_ids = faiss_mgr.add_vectors(vectors)
            for vid, c in zip(new_ids, batch):
                vector_map.append((vid, c["id"]))
            log.info(event="embedding_batch", document_id=document_id, batch=i//BATCH_SIZE_EMBED, count=len(texts))
        
        faiss_mgr.save_index(FAISS_INDEX_PATH)
        log.info(event="faiss_saved", document_id=document_id, count=len(vector_map))
        
        # Phase 5: Update database with vector mappings
        with get_db() as conn:
            with conn.cursor() as cur:
                for vid, chunk_id in vector_map:
                    cur.execute(
                        "INSERT INTO faiss_index_map (vector_id, chunk_id, index_name, dim, created_at) VALUES (%s, %s, %s, %s, NOW())",
                        (str(vid), chunk_id, FAISS_INDEX_NAME, ew.dim)
                    )
                    cur.execute(
                        "UPDATE chunks SET vector_id = %s WHERE id = %s",
                        (str(vid), chunk_id)
                    )
                conn.commit()
        
        # Phase 6: Finalize
        meta["ingest_finished_at"] = _now_iso()
        meta["chunks_count"] = len(chunks)
        
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE documents SET status = %s, meta_json = %s, updated_at = NOW() WHERE id = %s",
                    ("completed", json.dumps(meta), document_id)
                )
                conn.commit()
        
        log.info(event="completed", document_id=document_id, chunks_count=len(chunks))
        logger.info("[ingest:%s] ingestion completed", document_id)
        
    except Exception as e:
        logger.exception("[ingest:%s] failed", document_id)
        
        meta["error"] = {"message": str(e), "traceback": traceback.format_exc()}
        meta["ingest_failed_at"] = _now_iso()
        
        # Write to DLQ
        dlq_payload = json.dumps({"document_id": document_id, "error": str(e), "ts": _now_iso()})
        r.rpush(INGEST_DLQ_KEY, dlq_payload)
        
        # Update status to failed
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE documents SET status = %s, meta_json = %s, updated_at = NOW() WHERE id = %s",
                        ("failed", json.dumps(meta), document_id)
                    )
                    conn.commit()
        except Exception as db_err:
            logger.error("Failed to update error status: %s", db_err)
        
        log.error(event="ingest_failed", document_id=document_id, error=str(e))

# Backward compatibility
ingest_document = ingest_document_atomic
