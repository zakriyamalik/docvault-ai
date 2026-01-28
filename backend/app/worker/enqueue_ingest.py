# backend/app/worker/enqueue_ingest.py
from redis import Redis
from rq import Queue, Retry
from app.tasks import ingest_document  # ingest_document is alias to ingest_document_atomic
import os

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
redis_conn = Redis.from_url(REDIS_URL)
q = Queue("ingest", connection=redis_conn)

def enqueue_ingest(document_id: str, file_path: str):
    # Retry policy: 3 retries, delays: 10s, 30s, 60s
    retry = Retry(max=3, interval=[10, 30, 60])
    job = q.enqueue(ingest_document, args=(document_id, file_path), retry=retry)
    print("Enqueued job:", job.id)
    return job.id

if __name__ == "__main__":
    # quick test
    import sys
    if len(sys.argv) < 3:
        print("Usage: python enqueue_ingest.py <document_id> <file_path>")
        raise SystemExit(1)
    enqueue_ingest(sys.argv[1], sys.argv[2])
