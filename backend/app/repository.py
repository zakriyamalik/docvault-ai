# app/repository.py
import json
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import uuid4
from pathlib import Path

from app.db.sqlite_conn import get_db


# ============================================================================
# DOCUMENT HELPERS (Original - Preserved)
# ============================================================================

def create_document_row(filename: str, size_bytes: int, status: str = "queued") -> str:
    """
    Create a new document row in the database immediately after saving the file.

    Args:
        filename (str): Name of the saved file
        size_bytes (int): Size of file in bytes
        status (str, optional): Initial status of document. Defaults to 'queued'.

    Returns:
        str: document_id (UUID)
    """
    document_id = str(uuid4())  # generate unique document ID
    source_type = "upload"
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO documents (id, filename, size_bytes, status, source_type)
            VALUES (?, ?, ?, ?, ?)
            """,
            (document_id, filename, size_bytes, status, source_type)
        )
        conn.commit()

    return document_id


def get_document_status(document_id: str) -> Optional[Dict[str, Any]]:
    """Get document status and metadata."""
    with get_db() as conn:
        cur = conn.cursor()
        row = cur.execute(
            "SELECT id, filename, status, size_bytes, created_at FROM documents WHERE id = ?",
            (document_id,)
        ).fetchone()
        
        if not row:
            return None
        
        return {
            "id": row["id"],
            "filename": row["filename"],
            "status": row["status"],
            "size_bytes": row["size_bytes"],
            "created_at": row["created_at"]
        }


def update_document_status(document_id: str, status: str) -> bool:
    """Update document processing status."""
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE documents SET status = ? WHERE id = ?",
            (status, document_id)
        )
        conn.commit()
        return cur.rowcount > 0


def list_documents(limit: int = 100) -> List[Dict[str, Any]]:
    """List all documents with status."""
    with get_db() as conn:
        cur = conn.cursor()
        rows = cur.execute(
            """
            SELECT id, filename, status, size_bytes, created_at 
            FROM documents 
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()
    
    return [
        {
            "id": row["id"],
            "filename": row["filename"],
            "status": row["status"],
            "size_bytes": row["size_bytes"],
            "created_at": row["created_at"]
        }
        for row in rows
    ]


# ============================================================================
# CONVERSATION HELPERS (New - Step 2)
# ============================================================================

def create_conversation(title_preview: Optional[str] = None) -> str:
    """
    Create a new conversation thread.
    
    Args:
        title_preview: Truncated first message or custom title (auto-truncated to 120 chars)
    
    Returns:
        conversation_id (UUID string)
    """
    conv_id = str(uuid.uuid4())
    # Auto-truncate title to prevent DB bloat
    title = (title_preview or "")[:120]
    
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO conversations (id, title_preview, created_at, updated_at)
            VALUES (?, ?, datetime('now'), datetime('now'))
            """,
            (conv_id, title)
        )
        conn.commit()
    
    return conv_id


def list_conversations(limit: int = 20) -> List[Dict[str, Any]]:
    """
    List recent conversations ordered by most recently updated.
    
    Args:
        limit: Max number of conversations to return (max 100)
    
    Returns:
        List of conversation dicts with id, title, created_at, updated_at
    """
    # Safety cap to prevent abuse
    safe_limit = min(max(limit, 1), 100)
    
    with get_db() as conn:
        cur = conn.cursor()
        rows = cur.execute(
            """
            SELECT id, title_preview, created_at, updated_at
            FROM conversations
            ORDER BY updated_at DESC NULLS LAST, created_at DESC
            LIMIT ?
            """,
            (safe_limit,)
        ).fetchall()
    
    return [
        {
            "id": row["id"],
            "title": row["title_preview"] or "Untitled Conversation",
            "created_at": row["created_at"],
            "updated_at": row["updated_at"]
        }
        for row in rows
    ]


def delete_conversation(conversation_id: str) -> bool:
    """
    Delete a conversation and all its messages (cascade).
    
    Args:
        conversation_id: UUID of conversation to delete
    
    Returns:
        True if deleted, False if not found
    """
    with get_db() as conn:
        cur = conn.cursor()
        # Check if exists first
        row = cur.execute(
            "SELECT 1 FROM conversations WHERE id = ?",
            (conversation_id,)
        ).fetchone()
        
        if not row:
            return False
        
        # Cascade delete will handle messages
        cur.execute(
            "DELETE FROM conversations WHERE id = ?",
            (conversation_id,)
        )
        conn.commit()
        return True


def conversation_exists(conversation_id: str) -> bool:
    """Check if a conversation exists."""
    with get_db() as conn:
        cur = conn.cursor()
        row = cur.execute(
            "SELECT 1 FROM conversations WHERE id = ?",
            (conversation_id,)
        ).fetchone()
        return row is not None


# ============================================================================
# MESSAGE HELPERS (New - Step 2)
# ============================================================================

def insert_message(
    conversation_id: str,
    role: str,
    content: str,
    sources: Optional[List[Dict[str, Any]]] = None
) -> str:
    """
    Insert a message into a conversation.
    
    Args:
        conversation_id: UUID of parent conversation
        role: 'user', 'assistant', or 'system'
        content: Message text
        sources: Optional list of citation objects for assistant messages
    
    Returns:
        message_id (UUID string)
    
    Raises:
        ValueError: If role is invalid or conversation doesn't exist
    """
    # Validate role
    valid_roles = {"user", "assistant", "system"}
    if role not in valid_roles:
        raise ValueError(f"Invalid role '{role}'. Must be one of: {valid_roles}")
    
    # Verify conversation exists
    if not conversation_exists(conversation_id):
        raise ValueError(f"Conversation {conversation_id} not found")
    
    # Validate and serialize sources
    if sources is not None:
        if not isinstance(sources, list):
            raise ValueError("sources must be a list")
        # Limit sources size to prevent DB bloat
        sources_json = json.dumps(sources[:50])  # Max 50 sources stored
    else:
        sources_json = None
    
    # Content length safety (prevent DB bloat)
    safe_content = content[:50000] if content else ""  # 50k char limit
    
    msg_id = str(uuid.uuid4())
    
    with get_db() as conn:
        cur = conn.cursor()
        
        # Insert message
        cur.execute(
            """
            INSERT INTO messages (id, conversation_id, role, content, sources_json, created_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            """,
            (msg_id, conversation_id, role, safe_content, sources_json)
        )
        
        # Update conversation's updated_at timestamp
        cur.execute(
            """
            UPDATE conversations 
            SET updated_at = datetime('now')
            WHERE id = ?
            """,
            (conversation_id,)
        )
        
        conn.commit()
    
    return msg_id


def get_conversation_history(
    conversation_id: str,
    limit: int = 200
) -> List[Dict[str, Any]]:
    """
    Fetch message history for a conversation.
    
    Args:
        conversation_id: UUID of conversation
        limit: Max messages to return (max 500)
    
    Returns:
        List of message dicts ordered by created_at ASC (oldest first)
    """
    # Safety limits
    safe_limit = min(max(limit, 1), 500)
    
    with get_db() as conn:
        cur = conn.cursor()
        rows = cur.execute(
            """
            SELECT id, role, content, sources_json, created_at
            FROM messages
            WHERE conversation_id = ?
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (conversation_id, safe_limit)
        ).fetchall()
    
    history = []
    for row in rows:
        # Safely parse sources JSON
        sources = []
        if row["sources_json"]:
            try:
                sources = json.loads(row["sources_json"])
            except json.JSONDecodeError:
                sources = []  # Graceful degradation
        
        history.append({
            "id": row["id"],
            "role": row["role"],
            "content": row["content"],
            "sources": sources,
            "created_at": row["created_at"]
        })
    
    return history


def get_message_count(conversation_id: str) -> int:
    """Get total message count for a conversation."""
    with get_db() as conn:
        cur = conn.cursor()
        row = cur.execute(
            "SELECT COUNT(*) as cnt FROM messages WHERE conversation_id = ?",
            (conversation_id,)
        ).fetchone()
        return row["cnt"] if row else 0


def get_last_message(conversation_id: str) -> Optional[Dict[str, Any]]:
    """Get the most recent message in a conversation."""
    with get_db() as conn:
        cur = conn.cursor()
        row = cur.execute(
            """
            SELECT id, role, content, sources_json, created_at
            FROM messages
            WHERE conversation_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (conversation_id,)
        ).fetchone()
        
        if not row:
            return None
        
        sources = []
        if row["sources_json"]:
            try:
                sources = json.loads(row["sources_json"])
            except json.JSONDecodeError:
                sources = []
        
        return {
            "id": row["id"],
            "role": row["role"],
            "content": row["content"],
            "sources": sources,
            "created_at": row["created_at"]
        }