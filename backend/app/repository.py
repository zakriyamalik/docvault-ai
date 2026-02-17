import uuid
def _safe_json_loads(value, default=None):
    """Safely parse JSONB column that may already be a dict."""
    if value is None:
        return default if default is not None else {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        return json.loads(value)
    return default if default is not None else {}

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


def create_conversation(title: str = "New Conversation") -> str:
    """Create a new conversation and return its ID."""
    conv_id = str(uuid.uuid4())
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO conversations (id, created_at, updated_at) VALUES (%s, NOW(), NOW())",
                (conv_id,)
            )
            conn.commit()
    return conv_id



def insert_message(conversation_id: str, role: str, content: str, sources: Optional[List[Dict]] = None) -> str:
    """Insert a message into a conversation."""
    msg_id = str(uuid.uuid4())
    # Build meta_json with sources if provided
    meta = {}
    if sources:
        meta["sources"] = sources
    meta_json = json.dumps(meta) if meta else None
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO messages (id, conversation_id, role, content, meta_json, created_at) VALUES (%s, %s, %s, %s, %s, NOW())",
                (msg_id, conversation_id, role, content, meta_json)
            )
            # Update conversation timestamp
            cur.execute(
                "UPDATE conversations SET updated_at = NOW() WHERE id = %s",
                (conversation_id,)
            )
            conn.commit()
    return msg_id

def get_conversation_history(conversation_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Get message history for a conversation."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, role, content, meta_json, created_at FROM messages WHERE conversation_id = %s ORDER BY created_at LIMIT %s",
                (conversation_id, limit)
            )
            rows = cur.fetchall()
            messages = []
            for row in rows:
                meta_json = row[3] or "{}"
                if isinstance(meta_json, dict):
                    meta = meta_json
                else:
                    meta = json.loads(meta_json)
                msg = {
                    "id": row[0],
                    "message_id": row[0],  # For compatibility
                    "role": row[1],
                    "content": row[2],
                    "sources": meta.get("sources", []),
                    "created_at": str(row[4])
                }
                messages.append(msg)
            return messages

def conversation_exists(conversation_id: str) -> bool:
    """Check if a conversation exists."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM conversations WHERE id = %s",
                (conversation_id,)
            )
            return cur.fetchone() is not None

def list_conversations() -> List[Dict[str, Any]]:
    """List all conversations with message count."""
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT c.id, c.user_query, c.created_at, c.updated_at, COUNT(m.id) as message_count 
                FROM conversations c 
                LEFT JOIN messages m ON c.id = m.conversation_id 
                GROUP BY c.id, c.user_query, c.created_at, c.updated_at 
                ORDER BY c.updated_at DESC
            """)
            rows = cur.fetchall()
            return [
                {
                    "id": row[0],
                    "title": row[1] or "Untitled Conversation",
                    "created_at": str(row[2]),
                    "updated_at": str(row[3]),
                    "message_count": row[4]
                }
                for row in rows
            ]



def delete_conversation(conversation_id: str) -> bool:
    """Delete a conversation and all its messages."""
    with get_db() as conn:
        with conn.cursor() as cur:
            # First delete all messages
            cur.execute(
                "DELETE FROM messages WHERE conversation_id = %s",
                (conversation_id,)
            )
            # Then delete the conversation
            cur.execute(
                "DELETE FROM conversations WHERE id = %s",
                (conversation_id,)
            )
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
            meta_json = row[1] or "{}"
            if isinstance(meta_json, dict):
                meta = meta_json
            else:
                meta = json.loads(meta_json)
            return {
                "status": row[0],
                "ingest_started_at": meta.get("ingest_started_at"),
                "ingest_finished_at": meta.get("ingest_finished_at"),
                "chunks_count": meta.get("chunks_count"),
                "error_message": meta.get("error", {}).get("message") if meta.get("error") else None,
            }
