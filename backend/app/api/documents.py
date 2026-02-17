# backend/app/api/documents.py
import os
import uuid
import json
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel

from app.db.postgres_conn import get_db
from app.repository import create_document, get_document, list_documents, get_document_status
from app.chunker.chunker import get_chunks_for_document
import boto3

router = APIRouter()

# S3 client
s3 = boto3.client("s3")
S3_BUCKET = os.getenv("S3_BUCKET", "docvault-uploads")

UPLOAD_DIR = "/data/uploads"


class DocumentResponse(BaseModel):
    id: str
    filename: str
    status: str
    created_at: str
    chunks_count: Optional[int] = 0


class DocumentStatusResponse(BaseModel):
    status: str
    ingest_started_at: Optional[str] = None
    ingest_finished_at: Optional[str] = None
    chunks_count: Optional[int] = 0
    error_message: Optional[str] = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@router.post("/upload", response_model=dict)
async def upload_document(
    file: UploadFile = File(...),
    source_type: str = Form("upload"),
):
    """Upload a document and queue it for processing."""
    doc_id = str(uuid.uuid4())
    file_ext = os.path.splitext(file.filename or "")[1]
    unique_filename = f"{uuid.uuid4().hex}{file_ext}"
    local_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    # Ensure upload directory exists
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    # Save file locally
    content = await file.read()
    with open(local_path, "wb") as f:
        f.write(content)
    
    file_size = len(content)
    mime_type = file.content_type or "application/octet-stream"
    
    # Upload to S3
    s3_key = f"uploads/{unique_filename}"
    try:
        s3.upload_file(local_path, S3_BUCKET, s3_key)
    except Exception as e:
        # S3 upload failed but we can still process locally
        print(f"S3 upload failed: {e}")
        s3_key = None
    
    # Create document record in PostgreSQL
    create_document(
        doc_id=doc_id,
        filename=file.filename or "unknown",
        source_type=source_type,
        source_ref=s3_key or local_path,
        mime_type=mime_type,
        size_bytes=file_size,
        status="queued",
        meta_json=json.dumps({
            "local_path": local_path,
            "s3_key": s3_key,
            "uploaded_at": _now_iso(),
        }),
    )
    
    # Enqueue job for processing
    try:
        from app.worker.enqueue_ingest import enqueue_ingest
        job_id = enqueue_ingest(doc_id, f"s3://{S3_BUCKET}/{s3_key}" if s3_key else local_path)
    except Exception as e:
        print(f"Failed to enqueue job: {e}")
        job_id = None
    
    return {
        "document_id": doc_id,
        "ingest_job_id": job_id,
    }


@router.get("/", response_model=List[DocumentResponse])
def list_documents_endpoint():
    """List all documents."""
    docs = list_documents()
    result = []
    for doc in docs:
        meta = json.loads(doc.get("meta_json") or "{}")
        result.append(DocumentResponse(
            id=doc["id"],
            filename=doc["filename"],
            status=doc["status"],
            created_at=str(doc["created_at"]),
            chunks_count=meta.get("chunks_count", 0),
        ))
    return result


@router.get("/{doc_id}/status", response_model=DocumentStatusResponse)
def get_document_status_endpoint(doc_id: str):
    """Get processing status of a document."""
    status = get_document_status(doc_id)
    if not status:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentStatusResponse(**status)


@router.get("/{doc_id}/chunks")
def get_document_chunks(doc_id: str):
    """Get chunks for a document."""
    doc = get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    chunks = get_chunks_for_document(doc_id)
    return {
        "document_id": doc_id,
        "chunks_count": len(chunks),
        "chunks": chunks,
    }


@router.delete("/{doc_id}")
def delete_document_endpoint(doc_id: str):
    """Delete a document and its chunks."""
    from app.repository import delete_document
    success = delete_document(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"deleted": True}
