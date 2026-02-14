# backend/app/api/admin.py
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
import json

from app.db.postgres_conn import get_db

router = APIRouter()


@router.get("/stats")
def get_stats():
    """Get system statistics."""
    with get_db() as conn:
        with conn.cursor() as cur:
            # Document counts by status
            cur.execute("SELECT status, COUNT(*) FROM documents GROUP BY status")
            doc_stats = {row[0]: row[1] for row in cur.fetchall()}
            
            # Total chunks
            cur.execute("SELECT COUNT(*) FROM chunks")
            chunk_count = cur.fetchone()[0]
            
            # Total conversations
            cur.execute("SELECT COUNT(*) FROM conversations")
            conv_count = cur.fetchone()[0]
            
            # Total messages
            cur.execute("SELECT COUNT(*) FROM messages")
            msg_count = cur.fetchone()[0]
    
    return {
        "documents": doc_stats,
        "total_chunks": chunk_count,
        "total_conversations": conv_count,
        "total_messages": msg_count,
    }


@router.post("/reset")
def reset_system():
    """Reset all data (use with caution!)."""
    with get_db() as conn:
        with conn.cursor() as cur:
            # Delete in order to respect foreign keys
            cur.execute("DELETE FROM faiss_index_map")
            cur.execute("DELETE FROM chunks")
            cur.execute("DELETE FROM documents")
            cur.execute("DELETE FROM messages")
            cur.execute("DELETE FROM conversations")
            cur.execute("DELETE FROM migrations_applied")
            conn.commit()
    
    return {"reset": True}
