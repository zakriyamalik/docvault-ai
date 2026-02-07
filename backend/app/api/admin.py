# app/api/admin.py
import json
import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.db.sqlite_conn import get_db
from app.tasks import ingest_document  # function to enqueue/ingest a document
from app.faiss_manager import FAISSManager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin"])

# Config
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
INGEST_DLQ_KEY = os.getenv("INGEST_DLQ_KEY", "ingest_dlq")
RQ_QUEUE_NAME = os.getenv("RQ_QUEUE_NAME", "ingest")


# ----- Placeholder admin guard (replace with real auth later) -----
def require_admin():
    # Placeholder: in the future validate JWT/session/etc.
    return True


# ----- Helpers for Redis & RQ (lazy to allow easy mocking in tests) -----
def _get_redis():
    import redis

    try:
        return redis.from_url(REDIS_URL, decode_responses=True)
    except Exception:
        # Fallback for envs where from_url may not exist
        return redis.Redis(host="redis", port=6379, decode_responses=True)


def _get_rq_queue(redis_conn):
    from rq import Queue

    return Queue(RQ_QUEUE_NAME, connection=redis_conn)


# ----- Response models -----
class ReembedResponse(BaseModel):
    enqueued_job_id: str


class DLQItem(BaseModel):
    document_id: str
    error_snippet: Optional[str] = None
    failed_at: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None


class DLQListResponse(BaseModel):
    dlq: List[DLQItem]


# ------------------------------------------------------------------
# GET /admin/dlq
# ------------------------------------------------------------------
@router.get("/dlq", response_model=DLQListResponse, dependencies=[Depends(require_admin)])
def get_dlq():
    """
    Return the contents of the ingestion DLQ (ingest_dlq in Redis).
    Each entry is expected to be a JSON-serialized object with at least document_id.
    """
    redis_conn = _get_redis()
    try:
        items = redis_conn.lrange(INGEST_DLQ_KEY, 0, -1)
    except Exception as e:
        logger.exception("Failed to read DLQ from Redis: %s", e)
        raise HTTPException(status_code=500, detail="Failed to read DLQ")

    parsed = []
    for it in items:
        try:
            obj = json.loads(it)
        except Exception:
            # if the item is not valid JSON, return it as raw payload
            obj = {"document_id": None, "payload_raw": it}
        parsed.append(
            DLQItem(
                document_id=obj.get("document_id"),
                error_snippet=obj.get("error") or obj.get("error_snippet"),
                failed_at=obj.get("failed_at"),
                payload=obj,
            )
        )

    return {"dlq": parsed}


# ------------------------------------------------------------------
# POST /admin/dlq/retry/{document_id}
# ------------------------------------------------------------------
@router.post("/dlq/retry/{document_id}", dependencies=[Depends(require_admin)])
def dlq_retry(document_id: str):
    """
    Find and remove the first DLQ entry matching document_id, then re-enqueue the ingestion job.
    Returns the enqueued job id.
    """
    redis_conn = _get_redis()
    # Read DLQ
    try:
        items = redis_conn.lrange(INGEST_DLQ_KEY, 0, -1)
    except Exception as e:
        logger.exception("Failed to read DLQ from Redis: %s", e)
        raise HTTPException(status_code=500, detail="Failed to read DLQ")

    found_raw = None
    found_obj = None
    for it in items:
        try:
            obj = json.loads(it)
        except Exception:
            continue
        if obj.get("document_id") == document_id:
            found_raw = it
            found_obj = obj
            break

    if not found_raw:
        raise HTTPException(status_code=404, detail="DLQ entry not found")

    # Remove the found DLQ entry
    try:
        redis_conn.lrem(INGEST_DLQ_KEY, 0, found_raw)
    except Exception as e:
        logger.exception("Failed to remove DLQ entry from Redis: %s", e)
        raise HTTPException(status_code=500, detail="Failed to remove DLQ entry")

    # Enqueue job using file path in documents table if available, else payload path
    with get_db() as conn:
        cur = conn.cursor()
        row = cur.execute("SELECT filename FROM documents WHERE id = ?", (document_id,)).fetchone()
        if row and row["filename"]:
            file_path = f"/data/uploads/{row['filename']}"
        else:
            # fallback to any file path inside DLQ payload
            file_path = found_obj.get("file_path") or found_obj.get("filepath") or None

    try:
        rq_queue = _get_rq_queue(redis_conn)
        job = rq_queue.enqueue(ingest_document, document_id=document_id, file_path=file_path)
    except Exception as e:
        logger.exception("Failed to enqueue retry job: %s", e)
        raise HTTPException(status_code=500, detail="Failed to enqueue retry job")

    return {"requeued_job_id": getattr(job, "id", str(job))}


# ------------------------------------------------------------------
# POST /admin/documents/{document_id}/reembed
# ------------------------------------------------------------------
@router.post("/documents/{document_id}/reembed", response_model=ReembedResponse, dependencies=[Depends(require_admin)])
def reembed_document(document_id: str):
    """
    Re-embed a document:
      - Validate document exists
      - Delete chunks and faiss_index_map entries
      - Attempt to remove vectors from FAISS index (if available)
      - Enqueue ingestion job to reprocess the file
    """
    # Validate document exists and get filename / source ref
    with get_db() as conn:
        cur = conn.cursor()
        row = cur.execute("SELECT id, filename FROM documents WHERE id = ?", (document_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Document not found")
        filename = row["filename"]

    # Determine file_path (if stored)
    file_path = f"/data/uploads/{filename}" if filename else None

    # Begin "transactional" sequence:
    # 1) Mark document as queued for re-embed (helps visibility)
    try:
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE documents SET status = ? WHERE id = ?", ("queued", document_id))
            conn.commit()
    except Exception as e:
        logger.exception("Failed to set document queued status: %s", e)
        raise HTTPException(status_code=500, detail="Failed to update document status")

    # 2) Collect chunk_ids for cleanup
    try:
        with get_db() as conn:
            cur = conn.cursor()
            rows = cur.execute("SELECT id FROM chunks WHERE document_id = ?", (document_id,)).fetchall()
            chunk_ids = [r["id"] for r in rows]
    except Exception as e:
        logger.exception("Failed to read chunks for document: %s", e)
        raise HTTPException(status_code=500, detail="Failed to read chunks")

    # 3) Collect vector_ids from faiss_index_map for those chunks
    vector_ids = []
    if chunk_ids:
        try:
            placeholders = ",".join(["?"] * len(chunk_ids))
            with get_db() as conn:
                cur = conn.cursor()
                rows = cur.execute(
                    f"SELECT vector_id FROM faiss_index_map WHERE chunk_id IN ({placeholders})",
                    tuple(chunk_ids),
                ).fetchall()
                vector_ids = [r["vector_id"] for r in rows]
        except Exception as e:
            logger.exception("Failed to query faiss_index_map: %s", e)
            raise HTTPException(status_code=500, detail="Failed to query FAISS mapping")

    # 4) Delete faiss_index_map rows and chunks from DB
    try:
        with get_db() as conn:
            cur = conn.cursor()
            if chunk_ids:
                placeholders = ",".join(["?"] * len(chunk_ids))
                cur.execute(f"DELETE FROM faiss_index_map WHERE chunk_id IN ({placeholders})", tuple(chunk_ids))
                cur.execute(f"DELETE FROM chunks WHERE id IN ({placeholders})", tuple(chunk_ids))
            conn.commit()
    except Exception as e:
        logger.exception("Failed to delete DB chunk/faiss map records: %s", e)
        # Try to set error status
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE documents SET status = ? WHERE id = ?", ("error", document_id))
            conn.commit()
        raise HTTPException(status_code=500, detail="Failed to delete chunks or faiss mappings")

    # 5) Attempt to remove vectors from FAISS
    try:
        faiss_mgr = FAISSManager()
        # attempt to load index (FAISSManager implementations may vary)
        try:
            faiss_mgr.load_index()
        except Exception:
            # If index not present, we can skip removing vectors
            logger.warning("FAISS index not available; skipping vector removal")
            faiss_mgr = None

        if faiss_mgr and vector_ids:
            # Prefer a remove method name used in your FAISS manager, else attempt common names
            if hasattr(faiss_mgr, "remove_vectors"):
                faiss_mgr.remove_vectors(vector_ids)
            elif hasattr(faiss_mgr, "remove_ids"):
                faiss_mgr.remove_ids(vector_ids)
            else:
                # If no removal API available, log and proceed
                logger.warning("FAISS manager does not support vector removal; vector ids: %s", vector_ids)
    except Exception as e:
        logger.exception("Failed to remove vectors from FAISS: %s", e)
        # mark document as error and stop
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE documents SET status = ? WHERE id = ?", ("error", document_id))
            conn.commit()
        raise HTTPException(status_code=500, detail="Failed to remove vectors from FAISS")

    # 6) Enqueue ingestion job to rebuild document embeddings
    try:
        redis_conn = _get_redis()
        rq_queue = _get_rq_queue(redis_conn)
        job = rq_queue.enqueue(ingest_document, document_id=document_id, file_path=file_path)
    except Exception as e:
        logger.exception("Failed to enqueue re-embed job: %s", e)
        # mark as error
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute("UPDATE documents SET status = ? WHERE id = ?", ("error", document_id))
            conn.commit()
        raise HTTPException(status_code=500, detail="Failed to enqueue re-embed job")

    return {"enqueued_job_id": getattr(job, "id", str(job))}
