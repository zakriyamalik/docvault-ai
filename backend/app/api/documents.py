# backend/app/api/documents.py

from fastapi import APIRouter, UploadFile, Depends, HTTPException
from uuid import uuid4
from pathlib import Path

from app.storage import save_upload
from app.repository import create_document_row
from app.db.sqlite_conn import get_db

import redis
from rq import Queue

router = APIRouter(
    prefix="/api/v1/documents",
    tags=["documents"],
)


# ---- Auth placeholder ----
def get_current_user():
    return None


# ---- Redis / RQ setup (skeleton) ----
redis_conn = redis.Redis(host="redis", port=6379, decode_responses=True)
rq_queue = Queue("ingest", connection=redis_conn)


@router.post("/upload")
def upload_document(
    file: UploadFile,
    current_user=Depends(get_current_user),
):
    """
    Upload a document and enqueue ingestion job.
    """

    # 1️⃣ Enforce system-wide document limit (≤ 50)
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM documents;")
        doc_count = cur.fetchone()[0]

    if doc_count >= 50:
        raise HTTPException(
            status_code=400,
            detail="Document limit reached (max 50 documents allowed)",
        )

    try:
        # 2️⃣ Save file (Task-3)
        saved_path, size_bytes = save_upload(file)

        # 3️⃣ Insert DB row
        document_id = create_document_row(
            filename=saved_path.name,
            size_bytes=size_bytes,
            status="queued",
        )

        # 4️⃣ Enqueue ingestion job (Task-5 executes it)
        job = rq_queue.enqueue(
            "tasks.ingest_document",
            document_id=document_id,
            file_path=str(saved_path),
        )

        # 5️⃣ Return response
        return {
            "document_id": document_id,
            "ingest_job_id": job.id,
        }

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(exc)}",
        )
@router.get("/{document_id}/status")
def get_document_status(document_id: str, current_user=Depends(get_current_user)):
    """
    Get ingestion status for a specific document.
    """
    with get_db() as conn:
        cur = conn.cursor()

        # Fetch document row
        cur.execute(
            "SELECT id, status, updated_at, meta_json FROM documents WHERE id = ?",
            (document_id,)
        )
        doc = cur.fetchone()

        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        # Count chunks for this document
        cur.execute(
            "SELECT COUNT(*) FROM chunks WHERE document_id = ?",
            (document_id,)
        )
        chunks_count = cur.fetchone()[0]

        # Extract error_message if present in meta_json
        import json
        meta_json = doc["meta_json"]
        error_message = None
        if meta_json:
            try:
                meta = json.loads(meta_json)
                error_message = meta.get("error_message")
            except Exception:
                pass

        return {
            "status": doc["status"],
            "ingest_started_at": doc["updated_at"],  # placeholder for started timestamp
            "ingest_finished_at": None,  # will be updated later after ingestion
            "chunks_count": chunks_count,
            "error_message": error_message,
        }
@router.get("/")
def list_documents(current_user=Depends(get_current_user)):
    """
    Return a list of all documents with metadata:
    id, filename, status, created_at, chunks_count
    """
    with get_db() as conn:
        cur = conn.cursor()
        # Fetch basic document info
        cur.execute("""
            SELECT id, filename, status, created_at
            FROM documents
            ORDER BY created_at DESC
        """)
        docs = cur.fetchall()

        result = []
        for doc in docs:
            doc_id = doc["id"]
            # Count chunks for this document
            cur.execute("SELECT COUNT(*) FROM chunks WHERE document_id = ?", (doc_id,))
            chunks_count = cur.fetchone()[0]

            result.append({
                "id": doc_id,
                "filename": doc["filename"],
                "status": doc["status"],
                "created_at": doc["created_at"],
                "chunks_count": chunks_count
            })

    return result
@router.get("/{document_id}/chunks")
def get_document_chunks(document_id: str, current_user=Depends(get_current_user)):
    """
    Return all chunks for a specific document.
    """
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, chunk_index, text
            FROM chunks
            WHERE document_id = ?
            ORDER BY chunk_index ASC
            """,
            (document_id,),
        )
        rows = cur.fetchall()

    # Format rows to return preview
    chunks = []
    for row in rows:
        text = row["text"]
        preview = text[:100] + "..." if len(text) > 100 else text
        chunks.append({
            "id": row["id"],
            "chunk_index": row["chunk_index"],
            "preview": preview,
            # Optional fields
            "char_start": 0,  # you can populate if you store these
            "char_end": len(text)
        })

    return chunks
