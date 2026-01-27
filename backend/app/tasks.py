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

logger = logging.getLogger(__name__)

# Tunables (can be moved to env if you want)
BATCH_SIZE_CHUNKS = int(os.getenv("CHUNK_DB_BATCH", "128"))
BATCH_SIZE_EMBED = int(os.getenv("EMBED_BATCH", "64"))
FAISS_INDEX_NAME = os.getenv("FAISS_INDEX_NAME", "default")
FAISS_INDEX_PATH = os.getenv("FAISS_INDEX_PATH", f"/data/faiss/{FAISS_INDEX_NAME}.faiss")


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
    Atomic ingest pipeline wiring using current project structure:
      - parse (pdf/docx/txt)
      - chunk (tokenizer + chunk_pages)
      - persist chunks (DB-first)
      - embed (EmbeddingWrapper) and add to FAISS (FAISSManager)
      - insert faiss_index_map and update chunks.vector_id
      - finalize document (status + meta_json)
    All timestamps / counts / errors are stored inside documents.meta_json (Option A).
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
        kind = _detect_file_kind(file_path)
        if kind == "pdf":
            pages = extract_pdf(file_path)
            # fallback to OCR if pages empty or nearly-empty
            if not pages or all(not (p.text and p.text.strip()) for p in pages):
                pages = extract_pdf_with_ocr(file_path)
        elif kind == "docx":
            pages = extract_docx(file_path)
        elif kind == "txt":
            pages = extract_txt(file_path)
        else:
            raise ValueError(f"Unsupported file type for ingestion: {file_path}")

        # Normalize pages to list[dict] expected by chunker
        norm_pages = []
        for p in pages:
            if hasattr(p, "text"):  # PageText dataclass
                text = p.text or ""
                page_no = getattr(p, "page", 1)
                meta_page = {"ocr_used": False}
            else:
                # dict-like from extract_pdf_with_ocr
                text = p.get("text", "") or ""
                page_no = int(p.get("page", 1))
                meta_page = {"ocr_used": bool(p.get("ocr_used", False))}
            if text.strip():
                norm_pages.append({"page": page_no, "text": text, "metadata": meta_page})

        if not norm_pages:
            raise ValueError("No extractable text pages found in document")

        # -----------------------------
        # Phase 3: Chunking
        # -----------------------------
        logger.info("[ingest:%s] Phase 3: chunking", document_id)
        tokenizer = get_tokenizer()
        chunks = chunk_pages(document_id, norm_pages, tokenizer)

        if not chunks:
            raise ValueError("Chunker produced zero chunks")

        # Persist chunks in batches (DB-first)
        logger.info("[ingest:%s] Persisting %d chunks", document_id, len(chunks))
        for i in range(0, len(chunks), BATCH_SIZE_CHUNKS):
            batch = chunks[i : i + BATCH_SIZE_CHUNKS]
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
        except FileNotFoundError:
            logger.info("FAISS index not found, creating: %s", FAISS_INDEX_PATH)
            faiss_mgr.create_index(FAISS_INDEX_PATH, dim=ew.dim)

        vector_map: List[Tuple[str, str]] = []  # list of (vector_id, chunk_id) pairs

        for i in range(0, len(chunks), BATCH_SIZE_EMBED):
            batch = chunks[i : i + BATCH_SIZE_EMBED]
            texts = [c["text"] for c in batch]
            vectors = ew.embed_texts(texts)
            new_ids = faiss_mgr.add_vectors(vectors)
            # zip new_ids with chunk ids in same order
            for vid, c in zip(new_ids, batch):
                vector_map.append((vid, c["id"]))

        # persist FAISS to disk under lock
        faiss_mgr.save_index(FAISS_INDEX_PATH)
        logger.info("[ingest:%s] Added %d vectors to FAISS", document_id, len(vector_map))

        # -----------------------------
        # Phase 5: Insert faiss_index_map and update chunks.vector_id
        # -----------------------------
        logger.info("[ingest:%s] Phase 5: writing faiss_index_map", document_id)
        created_at = _now_iso()
        with get_db() as conn:
            cur = conn.cursor()
            insert_rows = [
                (vid, chunk_id, FAISS_INDEX_NAME, ew.dim, created_at) for vid, chunk_id in vector_map
            ]
            cur.executemany(
                "INSERT INTO faiss_index_map (vector_id, chunk_id, index_name, dim, created_at) VALUES (?, ?, ?, ?, ?)",
                insert_rows,
            )
            # update chunks.vector_id
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
            cur.execute(
                "UPDATE documents SET status = ?, meta_json = ? WHERE id = ?",
                ("completed", json.dumps(meta), document_id),
            )
            conn.commit()

        logger.info("[ingest:%s] ingestion completed", document_id)
        return

    except Exception as e:
        logger.exception("[ingest:%s] failed", document_id)
        meta.setdefault("error", {})
        meta["error"] = {"message": str(e), "traceback": traceback.format_exc()}
        meta["ingest_failed_at"] = _now_iso()
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE documents SET status = ?, meta_json = ? WHERE id = ?",
                ("failed", json.dumps(meta), document_id),
            )
            conn.commit()
        return
# Backward compatibility for existing imports
ingest_document = ingest_document_atomic
