import time
import redis
import os
import json

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = 6379
QUEUE_NAME = "document_jobs"

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

print("Worker started. Waiting for jobs...")

while True:
    job = r.blpop(QUEUE_NAME, timeout=5)
    if job:
        _, job_data = job
        job_dict = json.loads(job_data)
        print(f"Received job: {job_dict}")
    else:
        time.sleep(1)
