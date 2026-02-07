# app/tests/test_admin_api.py
import json
import time
import sqlite3
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.sqlite_conn import get_db

client = TestClient(app)


# --------------------------
# Helpers to manipulate DB
# --------------------------
def create_document_row(
    document_id,
    filename,
    size_bytes=123,
    status="uploaded",
    source_type="upload",
):
    """
    Idempotent insert for documents row.
    Removes any existing row with the same id to avoid UNIQUE constraint failures.
    Retries briefly on OperationalError (database locked).
    """
    last_exc = None
    for attempt in range(5):
        try:
            with get_db() as conn:
                cur = conn.cursor()
                # remove existing (avoid UNIQUE constraint on repeated test runs)
                cur.execute("DELETE FROM documents WHERE id = ?", (document_id,))
                conn.commit()
                cur.execute(
                    """
                    INSERT INTO documents (id, filename, size_bytes, status, source_type)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (document_id, filename or "", size_bytes, status, source_type),
                )
                conn.commit()
            return
        except sqlite3.OperationalError as e:
            last_exc = e
            time.sleep(0.05)
    # if we get here, re-raise the last OperationalError for visibility
    raise last_exc


def insert_chunk_for_document(chunk_id: str, document_id: str, content: str = "preview", chunk_index: int = 0):
    """
    Insert chunk idempotently (INSERT OR REPLACE) and commit.
    """
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO chunks (id, document_id, chunk_index, text, content) VALUES (?, ?, ?, ?, ?)",
            (chunk_id, document_id, chunk_index, content, content),
        )
        conn.commit()


def insert_faiss_map(vector_id: int, chunk_id: str):
    """
    Insert faiss_index_map idempotently and commit.
    """
    with get_db() as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO faiss_index_map (vector_id, chunk_id, index_name, dim, created_at) VALUES (?, ?, ?, ?, datetime('now'))",
            (vector_id, chunk_id, "test_index", 768),
        )
        conn.commit()


# --------------------------
# Tests
# --------------------------
def test_get_dlq_returns_items(monkeypatch):
    """
    GET /api/v1/admin/dlq should return parsed DLQ items from Redis.
    """
    # Mock Redis _get_redis function used in admin router
    fake_items = [
        json.dumps({"document_id": "doc-x", "error": "parse error", "failed_at": "2025-01-01T00:00:00Z"})
    ]

    def fake_get_redis():
        mock_redis = Mock()
        mock_redis.lrange.return_value = fake_items
        return mock_redis

    monkeypatch.setattr("app.api.admin._get_redis", fake_get_redis)

    resp = client.get("/api/v1/admin/dlq")
    assert resp.status_code == 200
    data = resp.json()
    assert "dlq" in data
    assert len(data["dlq"]) == 1
    assert data["dlq"][0]["document_id"] == "doc-x"


def test_dlq_retry_removes_and_requeues(monkeypatch):
    """
    POST /api/v1/admin/dlq/retry/{document_id} should remove DLQ entry and enqueue job.
    """
    document_id = "doc-retry-1"
    # Ensure there's a document row in DB (so fallback can find filename)
    create_document_row(document_id, filename="file_retry.pdf")

    fake_dlq_item = json.dumps({"document_id": document_id, "file_path": "/data/uploads/file_retry.pdf"})

    # Mock _get_redis to return a redis-like object
    def fake_get_redis():
        mock_redis = Mock()
        mock_redis.lrange.return_value = [fake_dlq_item]
        # lrem should be callable and return positive count
        mock_redis.lrem.return_value = 1
        return mock_redis

    # Mock RQ queue to capture enqueue
    fake_job = Mock()
    fake_job.id = "job-xyz-123"

    def fake_get_rq_queue(redis_conn):
        mock_q = Mock()
        mock_q.enqueue.return_value = fake_job
        return mock_q

    monkeypatch.setattr("app.api.admin._get_redis", fake_get_redis)
    monkeypatch.setattr("app.api.admin._get_rq_queue", fake_get_rq_queue)

    resp = client.post(f"/api/v1/admin/dlq/retry/{document_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "requeued_job_id" in data
    assert data["requeued_job_id"] == "job-xyz-123"


def test_reembed_document_deletes_chunks_and_enqueues(monkeypatch):
    """
    POST /api/v1/admin/documents/{id}/reembed should:
      - delete chunks & faiss_index_map rows
      - attempt FAISS removal (mocked)
      - enqueue ingest job
    """
    document_id = "doc-reembed-1"
    create_document_row(document_id, filename="file_reembed.pdf")

    # Create chunks and faiss map entries
    chunk_ids = ["chunk-a-1", "chunk-a-2"]
    for idx, cid in enumerate(chunk_ids):
        # note: the schema fields in your repo might be different; insert minimal columns used by admin
        with get_db() as conn:
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO chunks (id, document_id, chunk_index, text) VALUES (?, ?, ?, ?)",
                (cid, document_id, idx, f"content {cid}"),
            )
            conn.commit()

    # Add faiss_index_map entries linking vector ids to chunk ids
    insert_faiss_map(101, chunk_ids[0])
    insert_faiss_map(102, chunk_ids[1])

    # Mock FAISSManager so remove_vectors/remove_ids is called
    class FakeFAISSMgr:
        def load_index(self):
            # pretend index exists
            return True

        def remove_vectors(self, vector_ids):
            # pretend to remove successfully
            self.removed = vector_ids
            return True

    # Mock queue
    fake_job = Mock()
    fake_job.id = "job-reembed-789"

    def fake_get_rq_queue(redis_conn):
        mock_q = Mock()
        mock_q.enqueue.return_value = fake_job
        return mock_q

    monkeypatch.setattr("app.api.admin.FAISSManager", lambda: FakeFAISSMgr())
    monkeypatch.setattr("app.api.admin._get_rq_queue", fake_get_rq_queue)
    monkeypatch.setattr("app.api.admin._get_redis", lambda: Mock())

    resp = client.post(f"/api/v1/admin/documents/{document_id}/reembed")
    assert resp.status_code == 200
    data = resp.json()
    assert "enqueued_job_id" in data
    assert data["enqueued_job_id"] == "job-reembed-789"

    # Verify DB chunks and faiss_index_map entries are deleted
    with get_db() as conn:
        cur = conn.cursor()
        chunks_left = cur.execute("SELECT COUNT(*) as c FROM chunks WHERE document_id = ?", (document_id,)).fetchone()["c"]
        faiss_left = cur.execute("SELECT COUNT(*) as c FROM faiss_index_map WHERE chunk_id IN (?, ?)", tuple(chunk_ids)).fetchone()["c"]
        assert chunks_left == 0
        assert faiss_left == 0
