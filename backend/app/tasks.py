# backend/app/tasks.py

import time
import logging
from app.db.sqlite_conn import get_db  # using raw sqlite connection

logger = logging.getLogger(__name__)


def ingest_document(document_id: int, file_path: str = None):
    import sqlite3
    from app.db.sqlite_conn import DB_PATH

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Fetch document
    doc = cursor.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
    if not doc:
        print(f"Document {document_id} not found")
        return

    # Update status to processing
    cursor.execute("UPDATE documents SET status = ? WHERE id = ?", ("processing", document_id))
    conn.commit()

    # Here you can use `file_path` if needed, e.g., read file or split chunks
    if file_path:
        print(f"Ingesting file at: {file_path}")

    # Simulate work
    import time
    time.sleep(1)

    # Update status to completed
    cursor.execute("UPDATE documents SET status = ? WHERE id = ?", ("completed", document_id))
    conn.commit()
    conn.close()
    print(f"Document {document_id} processed successfully")
