# backend/app/tasks.py
import os
import json
import time
import logging
import traceback
from datetime import datetime, timezone
from typing import Optional, List, Tuple

from app.db.sqlite_conn import get_db, DB_PATH
from app.chunker.chunker import chunk_pages, persist_chunks_to_db
from app.chunker.tokenizer_wrapper import get_tokenizer
from app.parser.pdf_extractor import extract_pdf, extract_pdf_with_ocr
from app.parser.docx_extractor import extract_docx
from app.parser.txt_extractor import extract_txt
from app.embeddings.embeddings import EmbeddingWrapper
from app.faiss_manager import FAISSManager
from app.logging import get_logger  # structured logging
import redis  # added for DLQ

logger = logging.getLogger(__name__)
log = get_logger("ingest")  # structured logger

# Tunables (can be moved to env if you want)
BATCH_SIZE_CHUNKS = int(os.getenv("CHUNK_DB_BATCH", "128"))
BATCH_SIZE_EMBED = int(os.getenv("EMBED_BATCH", "64"))
FAISS_INDEX_NAME = os.getenv("FAISS_INDEX_NAME", "default")
FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", f"/data/faiss/{FAISS_INDEX_NAME}.faiss")

# Redis DLQ
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
r = redis.Redis.from_url(REDIS_URL)
INGEST_DLQ_KEY = "ingest_dlq"


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _detect_file_kind(path: str) -> str:
    p = (path or "").lower()
    if p.endswith(".pdf"):
        return "pdf"
    if p.endswith(".docx"):
        return "docx"
    if p.endswith(".txt"):
        return "txt"
    return "unknown"


def ingest_document_atomic(document_id: str, file_path: Optional[str] = None):
    """
    Atomic ingest pipeline:
      parse -> chunk -> persist -> embed -> FAISS -> faiss_index_map -> finalize
    """
    logger.info("ingest_document_atomic start: %s", document_id)
    meta = {}

    try:
        # -----------------------------
        # Load and mark processing start
        # -----------------------------
        with get_db() as conn:
            cur = conn.cursor()
            row = cur.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
            if not row:
                logger.error("Document not found: %s", document_id)
                return

            meta = json.loads(row["meta_json"]) if row["meta_json"] else {}
            meta["ingest_started_at"] = _now_iso()
            cur.execute(
                "UPDATE documents SET status = ?, meta_json = ? WHERE id = ?",
                ("processing", json.dumps(meta), document_id),
            )
            conn.commit()

        # Structured log: ingest started
        log.info(
            event="ingest_started",
            document_id=document_id,
            filename=row.get("filename") if row else None,
        )

        # -----------------------------
        # Phase 1: Validation
        # -----------------------------
        logger.info("[ingest:%s] Phase 1: validation", document_id)
        if not file_path:
            raise ValueError("file_path is required for ingestion")

        # -----------------------------
        # Phase 2: Parsing
        # -----------------------------
        logger.info("[ingest:%s] Phase 2: parsing", document_id)
        log.info(event="extraction_started", document_id=document_id, file_path=file_path)

        kind = _detect_file_kind(file_path)
        if kind == "pdf":
            pages = extract_pdf(file_path)
            if not pages or all(not (p.text and p.text.strip()) for p in pages):
                pages = extract_pdf_with_ocr(file_path)
                pages_len = len(pages) if hasattr(pages, "__len__") else None
                log.warning(event="ocr_fallback_used", document_id=document_id, pages=pages_len)
        elif kind == "docx":
            pages = extract_docx(file_path)
        elif kind == "txt":
            pages = extract_txt(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_path}")

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

        # -----------------------------
        # Phase 3: Chunking
        # -----------------------------
        logger.info("[ingest:%s] Phase 3: chunking", document_id)
        log.info(event="chunking_started", document_id=document_id)
        tokenizer = get_tokenizer()
        chunks = chunk_pages(document_id, norm_pages, tokenizer)

        if not chunks:
            raise ValueError("Chunker produced zero chunks")

        for i in range(0, len(chunks), BATCH_SIZE_CHUNKS):
            batch = chunks[i : i + BATCH_SIZE_CHUNKS]
            batch_index = i // BATCH_SIZE_CHUNKS
            log.info(event="chunk_batch", document_id=document_id, batch=batch_index, count=len(batch))
            persist_chunks_to_db(batch)

        # -----------------------------
        # Phase 4: Embeddings + FAISS
        # -----------------------------
        logger.info("[ingest:%s] Phase 4: embeddings + FAISS", document_id)
        ew = EmbeddingWrapper()
        faiss_mgr = FAISSManager()
        try:
            faiss_mgr.load_index(FAISS_INDEX_PATH)
            logger.info("Loaded FAISS index: %s", FAISS_INDEX_PATH)
            log.info(event="faiss_index_loaded", document_id=document_id, index_name=FAISS_INDEX_NAME, index_path=FAISS_INDEX_PATH)
        except FileNotFoundError:
            logger.info("FAISS index not found, creating: %s", FAISS_INDEX_PATH)
            faiss_mgr.create_index(FAISS_INDEX_PATH, dim=ew.dim)
            log.info(event="faiss_index_created", document_id=document_id, index_name=FAISS_INDEX_NAME, dim=ew.dim)

        vector_map: List[Tuple[str, str]] = []
        for i in range(0, len(chunks), BATCH_SIZE_EMBED):
            batch = chunks[i : i + BATCH_SIZE_EMBED]
            texts = [c["text"] for c in batch]
            embed_batch_index = i // BATCH_SIZE_EMBED
            log.info(event="embedding_batch", document_id=document_id, batch=embed_batch_index, count=len(texts))
            vectors = ew.embed_texts(texts)
            new_ids = faiss_mgr.add_vectors(vectors)
            for vid, c in zip(new_ids, batch):
                vector_map.append((vid, c["id"]))
            log.info(event="faiss_add_batch", document_id=document_id, batch=embed_batch_index, count=len(new_ids))

        faiss_mgr.save_index(FAISS_INDEX_PATH)
        logger.info("[ingest:%s] Added %d vectors to FAISS", document_id, len(vector_map))
        log.info(event="faiss_saved", document_id=document_id, index_name=FAISS_INDEX_NAME)

        # -----------------------------
        # Phase 5: Insert faiss_index_map
        # -----------------------------
        logger.info("[ingest:%s] Phase 5: writing faiss_index_map", document_id)
        created_at = _now_iso()
        with get_db() as conn:
            cur = conn.cursor()
            insert_rows = [(vid, chunk_id, FAISS_INDEX_NAME, ew.dim, created_at) for vid, chunk_id in vector_map]
            cur.executemany("INSERT INTO faiss_index_map (vector_id, chunk_id, index_name, dim, created_at) VALUES (?, ?, ?, ?, ?)", insert_rows)
            update_rows = [(vid, chunk_id) for vid, chunk_id in vector_map]
            cur.executemany("UPDATE chunks SET vector_id = ? WHERE id = ?", update_rows)
            conn.commit()

        # -----------------------------
        # Phase 6: Finalize document
        # -----------------------------
        meta["ingest_finished_at"] = _now_iso()
        meta["chunks_count"] = len(chunks)
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE documents SET status = ?, meta_json = ? WHERE id = ?", ("completed", json.dumps(meta), document_id))
            conn.commit()

        log.info(event="completed", document_id=document_id, chunks_count=len(chunks))
        logger.info("[ingest:%s] ingestion completed", document_id)
        return

    except Exception as e:
        # -----------------------------
        # 12.2: error handling + DLQ
        # -----------------------------
        logger.exception("[ingest:%s] failed", document_id)

        meta.setdefault("error", {})
        meta["error"] = {"message": str(e), "traceback": traceback.format_exc()}
        meta["ingest_failed_at"] = _now_iso()

        # Write stacktrace to log file
        os.makedirs("/data/logs", exist_ok=True)
        log_file = f"/data/logs/ingest_{document_id}.log"
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())

        # Push to Redis DLQ
        dlq_payload = json.dumps({"document_id": document_id, "error": str(e), "ts": _now_iso()})
        r.rpush(INGEST_DLQ_KEY, dlq_payload)

        # Update DB
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE documents SET status = ?, meta_json = ? WHERE id = ?", ("failed", json.dumps(meta), document_id))
            conn.commit()

        # Structured log
        log.error(event="ingest_failed", document_id=document_id, error=str(e))
        return

# Backward compatibility
ingest_document = ingest_document_atomic
