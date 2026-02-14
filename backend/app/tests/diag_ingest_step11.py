# backend/app/tests/diag_ingest_step11.py

import os
import json
import time
import sqlite3
from uuid import uuid4

from app.tasks import ingest_document_atomic
from app.db.postgres_conn import get_db

# Optional: set EMBEDDING_STUB to avoid real embeddings
os.environ["EMBEDDING_STUB"] = "true"

# -----------------------------
# Configuration
# -----------------------------
SAMPLE_PDF = os.path.join(os.path.dirname(__file__), "fixtures/sample.pdf")
BATCH_POLL_INTERVAL = 1.0  # seconds
BATCH_POLL_TIMEOUT = 30.0  # max wait for ingestion

# -----------------------------
# Helper functions
# -----------------------------
def wait_for_status(conn, document_id, expected_status, timeout=BATCH_POLL_TIMEOUT):
    start = time.time()
    while True:
        cur = conn.cursor()
        doc = cur.execute("SELECT * FROM documents WHERE id = ?", (document_id,)).fetchone()
        if doc and doc["status"] == expected_status:
            return doc
        if time.time() - start > timeout:
            raise TimeoutError(f"Document {document_id} did not reach status {expected_status} in time")
        time.sleep(BATCH_POLL_INTERVAL)

def count_chunks(conn, document_id):
    cur = conn.cursor()
    return cur.execute("SELECT COUNT(*) FROM chunks WHERE document_id = ?", (document_id,)).fetchone()[0]

def count_faiss_map(conn, chunk_ids):
    cur = conn.cursor()
    query = f"SELECT COUNT(*) FROM faiss_index_map WHERE chunk_id IN ({','.join(['?']*len(chunk_ids))})"
    return cur.execute(query, chunk_ids).fetchone()[0]

# -----------------------------
# Main diagnostic
# -----------------------------
def main():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Step 1: Create a dummy document row
    document_id = str(uuid4())
    cur.execute(
        "INSERT INTO documents (id, filename, source_type, source_ref, mime_type, size_bytes, status, meta_json) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (document_id, "sample.pdf", "local", SAMPLE_PDF, "application/pdf", 12345, "pending", "{}"),
    )
    conn.commit()
    print(f"[diag] Inserted test document {document_id}")

    # Step 2: Run ingestion
    ingest_document_atomic(document_id, file_path=SAMPLE_PDF)
    print(f"[diag] ingest_document_atomic completed for {document_id}")

    # Step 3: Wait until status == completed
    doc = wait_for_status(conn, document_id, "completed")
    print(f"[diag] Document status: {doc['status']}")

    # Step 4: Check chunks count
    chunks_count_db = count_chunks(conn, document_id)
    meta = json.loads(doc["meta_json"])
    chunks_count_meta = meta.get("chunks_count", 0)
    assert chunks_count_db == chunks_count_meta, f"Chunk count mismatch! DB={chunks_count_db}, meta={chunks_count_meta}"
    print(f"[diag] Chunks count verified: {chunks_count_db}")

    # Step 5: Check FAISS map count
    cur.execute("SELECT id FROM chunks WHERE document_id = ?", (document_id,))
    chunk_ids = [row[0] for row in cur.fetchall()]
    faiss_count = count_faiss_map(conn, chunk_ids)
    assert faiss_count == chunks_count_db, f"FAISS map count mismatch! FAISS={faiss_count}, chunks={chunks_count_db}"
    print(f"[diag] FAISS mapping verified: {faiss_count}")

    # Step 6: Print timestamps
    print(f"[diag] Ingest started at: {meta.get('ingest_started_at')}")
    print(f"[diag] Ingest finished at: {meta.get('ingest_finished_at')}")

    print("[diag] All diagnostics passed successfully!")

    conn.close()


if __name__ == "__main__":
    main()
