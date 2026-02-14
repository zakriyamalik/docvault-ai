# backend/app/repository.py
from typing import List, Dict, Any, Optional
import json
from datetime import datetime, timezone
from app.db.postgres_conn import get_db


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def create_document(
    doc_id: str,
    filename: str,
    source_type: str,
    source_ref: Optional[str] = None,
    mime_type: Optional[str] = None,
    size_bytes: Optional[int] = None,
    status: str = "queued",
    meta_json: Optional[str] = None,
) -> None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO documents (id, filename, source_type, source_ref, mime_type, size_bytes, status, created_at, meta_json)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), %s)
                """,
                (doc_id, filename, source_type, source_ref, mime_type, size_bytes, status, meta_json or "{}"),
            )
            conn.commit()


def get_document(doc_id: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, filename, source_type, source_ref, mime_type, size_bytes, status, created_at, updated_at, meta_json FROM documents WHERE id = %s",
                (doc_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            colnames = [desc[0] for desc in cur.description]
            return dict(zip(colnames, row))


def update_document_status(doc_id: str, status: str, meta_json: Optional[str] = None) -> None:
    with get_db() as conn:
        with conn.cursor() as cur:
            if meta_json:
                cur.execute(
                    "UPDATE documents SET status = %s, meta_json = %s, updated_at = NOW() WHERE id = %s",
                    (status, meta_json, doc_id),
                )
            else:
                cur.execute(
                    "UPDATE documents SET status = %s, updated_at = NOW() WHERE id = %s",
                    (status, doc_id),
                )
            conn.commit()


def list_documents() -> List[Dict[str, Any]]:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, filename, status, created_at, meta_json FROM documents ORDER BY created_at DESC"
            )
            rows = cur.fetchall()
            colnames = [desc[0] for desc in cur.description]
            return [dict(zip(colnames, row)) for row in rows]


def delete_document(doc_id: str) -> bool:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
            conn.commit()
            return cur.rowcount > 0


def get_document_status(doc_id: str) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT status, meta_json FROM documents WHERE id = %s",
                (doc_id,),
            )
            row = cur.fetchone()
            if not row:
                return None
            meta = json.loads(row[1] or "{}")
            return {
                "status": row[0],
                "ingest_started_at": meta.get("ingest_started_at"),
                "ingest_finished_at": meta.get("ingest_finished_at"),
                "chunks_count": meta.get("chunks_count"),
                "error_message": meta.get("error", {}).get("message") if meta.get("error") else None,
            }
