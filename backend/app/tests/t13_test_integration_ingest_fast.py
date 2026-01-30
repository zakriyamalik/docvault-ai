import uuid
import sqlite3
import json
import os
from app.tasks import ingest_document_atomic

def create_document_t13():
    """Insert a test document row into DB without source_type."""
    conn = sqlite3.connect("/data/db/db.sqlite")
    cur = conn.cursor()
    SAMPLE_PDF = os.path.join(os.path.dirname(__file__), "fixtures/sample.pdf")
    doc_id = str(uuid.uuid4())
    cur.execute(
        "INSERT INTO documents (id, filename, source_type, source_ref, mime_type, size_bytes, status, meta_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (doc_id, "sample.pdf", "local", SAMPLE_PDF, "application/pdf", 12345, "pending", "{}"),
    )
    conn.commit()
    conn.close()
    return doc_id

def test_ingest_direct_end_to_end_t13():
    os.environ["EMBEDDING_STUB"] = "true"
    doc_id = create_document_t13()
    ingest_document_atomic(doc_id, "/app/app/tests/fixtures/sample.pdf")

    conn = sqlite3.connect("/data/db/db.sqlite")
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT status, meta_json FROM documents WHERE id = ?", (doc_id,)
    ).fetchone()
    conn.close()

    assert row["status"] == "completed"
    meta = json.loads(row["meta_json"] or "{}")
    assert meta.get("chunks_count", 0) > 0
