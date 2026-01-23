from app.db.sqlite_conn import get_db
from uuid import uuid4
from pathlib import Path

def create_document_row(filename: str, size_bytes: int, status: str = "queued") -> str:
    """
    Create a new document row in the database immediately after saving the file.

    Args:
        filename (str): Name of the saved file
        size_bytes (int): Size of the file in bytes
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
            INSERT INTO documents (id, filename, size_bytes, status,source_type)
            VALUES (?, ?, ?, ?, ?)
            """,
            (document_id, filename, size_bytes, status, source_type)  # <-- use document_id here
        )
        conn.commit()

    return document_id  # <-- return the correct ID
