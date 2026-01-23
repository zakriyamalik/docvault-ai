import redis
import os
import json
import uuid

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = 6379
QUEUE_NAME = "document_jobs"

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

job = {
    "job_id": str(uuid.uuid4()),
    "file_path": "/data/uploads/dummy.pdf",
    "status": "pending"
}

r.rpush(QUEUE_NAME, json.dumps(job))
print(f"Job enqueued: {job['job_id']}")
